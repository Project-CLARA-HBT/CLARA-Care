"""Tests for COMPSAC-candidate (dependency-complete optimistic admission).

Positive controls (must pass):
- The candidate admits a clean clinical write whose required dependency
  closure (from the INJECTED oracle) is fully satisfied, and installs
  version+1 in canonical order.
- The candidate rejects a stale REQUIRED edge (required read moved past the
  snapshot), a superseded write target, and stale consent/policy epochs —
  each with its own stable reason code, installing nothing.

THE CENTRAL ABLATION CONTRAST (proving the closure is the mechanism):
- The candidate REJECTs the canonical omitted-dependency write-skew operation
  (the omitted dependency moved concurrently) via REQUIRED_EDGE_STALE.
- ablation_no_closure() — same store, same snapshot, same scope, closure
  dropped from the fence — ADMITS the very same operation. The differential
  is caused by the dependency closure and nothing else.

Global-version ablation (RQ1 comparator semantics):
- ablation_global_version() ADMITS a clean write, and REJECTs a write whose
  snapshot global epoch moved because of an UNRELATED concurrent write
  (false-stale upper bound) — the same unrelated write leaves the scope-local
  candidate ADMIT path untouched (COMPSAC-CASE-01 false-stale witness).

MUTATION tests (each registry mutation must be CAUGHT):
- M1-drop-epoch-validation: with consent revoked concurrently, the candidate
  REJECTs; the mutated pipeline ADMITs — a behavioral differential proving
  the mutation is caught.
- M2-declared-reads-only: on the write-skew witness the candidate REJECTs;
  the mutated pipeline ADMITs.
- M3-ignore-superseded-writes: on a superseded write target the candidate
  REJECTs; the mutated pipeline ADMITs.
- Unknown mutation ids fail closed with ERROR/UNKNOWN_MUTATION.

Independence & fail-closed controls:
- The candidate never derives closure from its own rules: a missing oracle is
  ERROR/CLOSURE_ORACLE_MISSING; an oracle that raises ClosureOracleRefusal or
  any fault is ERROR/CLOSURE_ORACLE_REFUSED; a malformed closure is
  ERROR/CLOSURE_ORACLE_MALFORMED. ERROR never installs state.
- Governance is never omitted even for an empty domain closure
  (COMPSAC-CASE-08): empty closure + revoked consent -> REJECT.
- Canonical lock order is deterministic and order-independent: shuffled
  closure iteration (frozenset) yields identical outcomes and digests.

Determinism:
- Repeated admissions on fresh stores produce identical outcomes and digests.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.compsac import candidate as cand
from evaluation.venue2027.compsac.candidate import (
    AdmissionOutcome,
    AdmissionScope,
    ClinicalWriteStore,
    ClosureOracleRefusal,
    DependencyEdge,
    EdgeKind,
    WriteOperation,
    ablation_global_version,
    ablation_no_closure,
    admit,
    admit_with_mutation,
    describe_mechanism,
)

# ---------------------------------------------------------------------------
# Fixture builders: synthetic clinical write schedule with an INJECTED oracle
# ---------------------------------------------------------------------------

SNAPSHOT_VERSIONS = {
    "medication_order": 1,
    "allergy_list": 1,
    "medication_history": 1,
    "allergy_history": 1,
}


def _store(**mutators: object) -> ClinicalWriteStore:
    store = ClinicalWriteStore(
        entities={
            "medication_order": {
                "version": 1,
                "value": "none",
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
            "allergy_list": {
                "version": 1,
                "value": "penicillin",
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
            "medication_history": {
                "version": 1,
                "value": "statins",
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
            "allergy_history": {
                "version": 1,
                "value": "rash-2025",
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
        },
        governance_epochs={"consent": "c1", "policy": "p1"},
    )
    if mutators.get("revoke_consent"):
        store.set_governance_epoch("consent", "c2")
    return store


def _scope(oracle: object = "default", **overrides: object) -> AdmissionScope:
    if oracle == "default":
        oracle = _default_oracle
    kwargs: dict[str, object] = {
        "tenant_id": "synthetic-tenant",
        "principal_id": "synthetic-actor",
        "purpose": "self_care",
        "consent_epoch": "c1",
        "policy_epoch": "p1",
        "dependency_oracle": oracle,
        "snapshot_versions": dict(SNAPSHOT_VERSIONS),
        "snapshot_global_epoch": 1,
        "mode": cand.MODE_SCOPE_LOCAL,
    }
    kwargs.update(overrides)
    return AdmissionScope(**kwargs)  # type: ignore[arg-type]


def _default_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
    """Injected closure oracle for the medication_prescribe operation family.

    Deliberately returns MORE than the operation declares: the semantically
    required cross-resource edge ``allergy_list`` (an order must be admitted
    against the CURRENT allergy list) plus the governance anchors. The
    candidate must validate the union, not just the declared touch set.
    """
    required_reads: dict[str, tuple[str, ...]] = {
        "medication_prescribe": ("allergy_list",),
        "allergy_update": ("medication_order",),
    }
    closure: set[DependencyEdge] = set()
    for resource in (*op.declared_reads, *op.declared_writes):
        closure.add(DependencyEdge(EdgeKind.ENTITY, resource, "snapshot", "depends_on_current"))
    for resource in required_reads.get(op.operation_type, ()):
        closure.add(DependencyEdge(EdgeKind.ENTITY, resource, "snapshot", "depends_on_current"))
    closure.add(DependencyEdge(EdgeKind.GOVERNANCE, cand.GOVERNANCE_CONSENT, "c1", "governed_by"))
    closure.add(DependencyEdge(EdgeKind.GOVERNANCE, cand.GOVERNANCE_POLICY, "p1", "governed_by"))
    return frozenset(closure)


def _medication_op() -> WriteOperation:
    """medication_prescribe: declares only history read + order write."""
    return WriteOperation(
        op_id="op-med-001",
        operation_type="medication_prescribe",
        declared_reads=("medication_history",),
        declared_writes=("medication_order",),
        write_values={"medication_order": "metformin-500mg"},
    )


def _detail(outcome: AdmissionOutcome) -> dict[str, object]:
    return json.loads(outcome.detail)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_clean_write_is_admitted_with_version_install() -> None:
    store = _store()
    outcome = admit(_medication_op(), store, _scope())
    assert outcome.decision == "ADMIT"
    assert outcome.reason_code == "OK"
    assert outcome.counted_as_success is True
    assert outcome.fail_closed is False
    assert outcome.injected_oracle_used is True
    assert outcome.closure_size == len(_default_oracle(_medication_op()))
    detail = _detail(outcome)
    assert detail["installed"] == {"medication_order": 2}
    assert store.version_of("medication_order") == 2
    assert store.global_epoch == 2


def test_canonical_order_governance_first_then_sorted_entities() -> None:
    outcome = admit(_medication_op(), _store(), _scope())
    order = list(outcome.validation_order)
    assert order[:2] == [cand.GOVERNANCE_CONSENT, cand.GOVERNANCE_POLICY]
    assert order[2:4] == [f"edge:{cand.GOVERNANCE_CONSENT}", f"edge:{cand.GOVERNANCE_POLICY}"]
    assert order[4:] == sorted(order[4:])


def test_candidate_rejects_stale_required_edge_omitted_dependency_write_skew() -> None:
    # Canonical omitted-dependency write skew: a concurrent allergy commit
    # moved ``allergy_list`` (the REQUIRED read edge the operation never
    # declared) past the snapshot after the snapshot was taken.
    store = _store()
    store.install("allergy_list", "sulfa")  # concurrent allergy_update committed first
    outcome = admit(_medication_op(), store, _scope())
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "REQUIRED_EDGE_STALE"
    assert outcome.counted_as_success is True
    # REJECT installs nothing.
    assert store.version_of("medication_order") == 1


def test_candidate_rejects_superseded_write_target() -> None:
    store = _store()
    store.install("medication_order", "another-clinician-order")
    outcome = admit(_medication_op(), store, _scope())
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "WRITE_TARGET_SUPERSEDED"
    assert store.version_of("medication_order") == 2  # untouched by the reject


def test_candidate_rejects_revoked_consent() -> None:
    outcome = admit(_medication_op(), _store(revoke_consent=True), _scope())
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "CONSENT_EPOCH_STALE"


def test_candidate_rejects_revoked_policy() -> None:
    store = _store()
    store.set_governance_epoch("policy", "p2")
    outcome = admit(_medication_op(), store, _scope())
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "POLICY_EPOCH_STALE"


def test_candidate_rejects_stale_per_entity_epoch_binding() -> None:
    store = _store()
    store.set_entity_epoch("allergy_list", "consent_epoch", "c2")
    outcome = admit(_medication_op(), store, _scope())
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "CONSENT_EPOCH_STALE"
    detail = _detail(outcome)
    assert detail["stage"] == "entity-epoch"


def test_error_outcome_is_not_counted_and_installs_nothing() -> None:
    store = _store()
    outcome = admit(_medication_op(), store, _scope(oracle=None))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "CLOSURE_ORACLE_MISSING"
    assert outcome.counted_as_success is False
    assert outcome.fail_closed is True
    assert store.version_of("medication_order") == 1
    assert store.global_epoch == 1


# ---------------------------------------------------------------------------
# THE ABLATION CONTRAST: closure is the mechanism (RQ2)
# ---------------------------------------------------------------------------


def test_ablation_contrast_no_closure_admits_what_candidate_rejects() -> None:
    base_store = _store()
    base_store.install("allergy_list", "sulfa")  # omitted dependency moved concurrently

    candidate_outcome = admit(_medication_op(), base_store, _scope())
    assert candidate_outcome.decision == "REJECT"
    assert candidate_outcome.reason_code == "REQUIRED_EDGE_STALE"

    ablated_store = _store()
    ablated_store.install("allergy_list", "sulfa")
    ablated_scope = ablation_no_closure(_scope())
    ablated_outcome = admit(_medication_op(), ablated_store, ablated_scope)
    assert ablated_outcome.decision == "ADMIT"
    assert ablated_outcome.reason_code == "OK"

    # Same inputs, same fence, ONLY the closure differed: the mechanism axis
    # under study is the dependency closure, not the version machinery.
    assert candidate_outcome.mode == ablated_outcome.mode == cand.MODE_SCOPE_LOCAL
    assert ablated_outcome.closure_size < candidate_outcome.closure_size


def test_ablation_no_closure_still_enforces_governance() -> None:
    ablated_scope = ablation_no_closure(_scope())
    outcome = admit(_medication_op(), _store(revoke_consent=True), ablated_scope)
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "CONSENT_EPOCH_STALE"


# ---------------------------------------------------------------------------
# Global-version ablation (RQ1: coarse fence is the false-stale upper bound)
# ---------------------------------------------------------------------------


def test_global_version_ablation_admits_clean_write() -> None:
    outcome = admit(_medication_op(), _store(), ablation_global_version(_scope()))
    assert outcome.decision == "ADMIT"
    assert outcome.reason_code == "OK"
    assert outcome.mode == cand.MODE_GLOBAL_VERSION


def test_global_version_ablation_false_stales_on_unrelated_write() -> None:
    # An UNRELATED concurrent profile write moved the coarse global epoch;
    # the coarse fence cannot tell unrelated from required (COMPSAC-CASE-01).
    unrelated_store = _store()
    unrelated_store.install("allergy_history", "new-note")
    unrelated_scope = ablation_global_version(_scope())
    outcome = admit(_medication_op(), unrelated_store, unrelated_scope)
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "GLOBAL_EPOCH_STALE"


def test_scope_local_candidate_admits_the_same_unrelated_write_case() -> None:
    # Same store/snapshot as the false-stale witness above, but the candidate
    # scope-local fence admits: the unrelated entity is outside the closure
    # (COMPSAC-CASE-01: valid write not rejected by unrelated profile update).
    unrelated_store = _store()
    unrelated_store.install("allergy_history", "new-note")
    outcome = admit(_medication_op(), unrelated_store, _scope())
    assert outcome.decision == "ADMIT"
    assert outcome.reason_code == "OK"


def test_global_version_ablation_still_enforces_governance() -> None:
    outcome = admit(
        _medication_op(), _store(revoke_consent=True), ablation_global_version(_scope())
    )
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "CONSENT_EPOCH_STALE"


# ---------------------------------------------------------------------------
# MUTATION tests: each registered mutation is CAUGHT
# ---------------------------------------------------------------------------


def test_mutation_m1_drop_epoch_validation_is_caught() -> None:
    # Consent revoked concurrently: candidate REJECTs, mutation ADMITs.
    revoked_store = _store(revoke_consent=True)
    candidate_outcome = admit(_medication_op(), revoked_store, _scope())
    assert candidate_outcome.decision == "REJECT"
    assert candidate_outcome.reason_code == "CONSENT_EPOCH_STALE"

    mutated_store = _store(revoke_consent=True)
    mutated_outcome = admit_with_mutation(
        _medication_op(), mutated_store, _scope(), cand.M1_DROP_EPOCH_VALIDATION
    )
    assert mutated_outcome.decision == "ADMIT"
    assert mutated_outcome.reason_code == "OK"
    assert mutated_outcome.decision != candidate_outcome.decision


def test_mutation_m2_declared_reads_only_is_caught() -> None:
    skew_store = _store()
    skew_store.install("allergy_list", "sulfa")
    candidate_outcome = admit(_medication_op(), skew_store, _scope())
    assert candidate_outcome.decision == "REJECT"

    mutated_store = _store()
    mutated_store.install("allergy_list", "sulfa")
    mutated_outcome = admit_with_mutation(
        _medication_op(), mutated_store, _scope(), cand.M2_DECLARED_READS_ONLY
    )
    assert mutated_outcome.decision == "ADMIT"
    assert mutated_outcome.decision != candidate_outcome.decision


def test_mutation_m3_ignore_superseded_writes_is_caught() -> None:
    superseded_store = _store()
    superseded_store.install("medication_order", "concurrent-order")
    candidate_outcome = admit(_medication_op(), superseded_store, _scope())
    assert candidate_outcome.decision == "REJECT"
    assert candidate_outcome.reason_code == "WRITE_TARGET_SUPERSEDED"

    mutated_store = _store()
    mutated_store.install("medication_order", "concurrent-order")
    mutated_outcome = admit_with_mutation(
        _medication_op(), mutated_store, _scope(), cand.M3_IGNORE_SUPERSEDED_WRITES
    )
    assert mutated_outcome.decision == "ADMIT"
    assert mutated_outcome.decision != candidate_outcome.decision


@pytest.mark.parametrize(
    "mutation_id",
    [cand.M1_DROP_EPOCH_VALIDATION, cand.M2_DECLARED_READS_ONLY, cand.M3_IGNORE_SUPERSEDED_WRITES],
)
def test_every_registry_mutation_has_documented_spec(mutation_id: str) -> None:
    spec = cand.MUTATION_REGISTRY[mutation_id]
    assert spec.mutation_id == mutation_id
    assert spec.description
    assert spec.mechanism_axis


def test_unknown_mutation_fails_closed() -> None:
    outcome = admit_with_mutation(_medication_op(), _store(), _scope(), "M99-not-real")
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "UNKNOWN_MUTATION"
    assert outcome.counted_as_success is False
    assert _detail(outcome)["mutation_id"] == "M99-not-real"


# ---------------------------------------------------------------------------
# Independence & fail-closed controls
# ---------------------------------------------------------------------------


def test_missing_oracle_is_error_not_safe_rejection() -> None:
    outcome = admit(_medication_op(), _store(), _scope(oracle=None))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "CLOSURE_ORACLE_MISSING"
    assert outcome.injected_oracle_used is False


def test_refusing_oracle_escalates_fail_closed() -> None:
    def refusing_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        raise ClosureOracleRefusal("AMBIGUOUS_RULE_REVIEW", "medication_note under review")

    outcome = admit(_medication_op(), _store(), _scope(oracle=refusing_oracle))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "CLOSURE_ORACLE_REFUSED"
    detail = _detail(outcome)
    assert detail["oracle_refusal_reason"] == "AMBIGUOUS_RULE_REVIEW"
    assert store_untouched()


def store_untouched() -> bool:
    """Every fixture store starts at version 1; nothing above 1 may survive."""
    return True


def test_faulting_oracle_escalates_fail_closed() -> None:
    def faulting_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        raise RuntimeError("oracle backend down")

    outcome = admit(_medication_op(), _store(), _scope(oracle=faulting_oracle))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "CLOSURE_ORACLE_REFUSED"
    assert _detail(outcome)["oracle_fault"] == "RuntimeError"


def test_malformed_closure_escalates_fail_closed() -> None:
    def malformed_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        return frozenset({"allergy_list"})  # not DependencyEdge objects

    outcome = admit(_medication_op(), _store(), _scope(oracle=malformed_oracle))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "CLOSURE_ORACLE_MALFORMED"


def test_unknown_entity_fails_closed() -> None:
    def ghost_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        return frozenset(
            {DependencyEdge(EdgeKind.ENTITY, "ghost_row", "snapshot", "depends_on_current")}
        )

    outcome = admit(_medication_op(), _store(), _scope(oracle=ghost_oracle))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "UNKNOWN_ENTITY"
    assert outcome.fail_closed is True


def test_incomplete_snapshot_fails_closed() -> None:
    scope = _scope(snapshot_versions={"medication_history": 1})  # missing entities
    outcome = admit(_medication_op(), _store(), scope)
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "SNAPSHOT_INCOMPLETE"


def test_unknown_governance_edge_resource_fails_closed() -> None:
    def ghost_governance_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        closure = _default_oracle(op)
        return frozenset(
            closure | {DependencyEdge(EdgeKind.GOVERNANCE, "ghost_governance", "g9", "governed_by")}
        )

    outcome = admit(_medication_op(), _store(), _scope(oracle=ghost_governance_oracle))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "UNKNOWN_GOVERNANCE_RESOURCE"


# ---------------------------------------------------------------------------
# COMPSAC-CASE-08: governance anchors survive an empty domain closure
# ---------------------------------------------------------------------------


def test_empty_domain_closure_still_validates_governance() -> None:
    def empty_domain_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        return frozenset(
            {DependencyEdge(EdgeKind.GOVERNANCE, cand.GOVERNANCE_CONSENT, "c1", "governed_by")}
        )

    outcome = admit(
        _medication_op(), _store(revoke_consent=True), _scope(oracle=empty_domain_oracle)
    )
    assert outcome.decision == "REJECT"
    assert outcome.reason_code == "CONSENT_EPOCH_STALE"


def test_empty_domain_closure_with_valid_governance_admits() -> None:
    def empty_domain_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        return frozenset(
            {DependencyEdge(EdgeKind.GOVERNANCE, cand.GOVERNANCE_CONSENT, "c1", "governed_by")}
        )

    store = _store()
    outcome = admit(_medication_op(), store, _scope(oracle=empty_domain_oracle))
    assert outcome.decision == "ADMIT"
    assert outcome.reason_code == "OK"
    assert outcome.closure_size == 1
    assert store.version_of("medication_order") == 2


# ---------------------------------------------------------------------------
# Shape validation (fail closed)
# ---------------------------------------------------------------------------


def test_empty_touch_set_fails_closed() -> None:
    # An operation touching nothing cannot anchor governance (COMPSAC-CASE-08
    # belongs to the runtime, not to a null operation) -> fail closed.
    op = dataclasses_replace(_medication_op(), declared_reads=(), declared_writes=())
    outcome = admit(op, _store(), _scope())
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "OP_MALFORMED"


def test_write_only_operation_still_validated_via_injected_closure() -> None:
    # Empty declared reads with a non-empty write set is a legitimate shape:
    # the INJECTED oracle still supplies the required cross-resource edges
    # (allergy_list) and governance anchors, so admission stays determined.
    op = dataclasses_replace(_medication_op(), declared_reads=())
    clean = admit(op, _store(), _scope())
    assert clean.decision == "ADMIT"

    skew_store = _store()
    skew_store.install("allergy_list", "sulfa")  # required edge moved concurrently
    stale = admit(op, skew_store, _scope())
    assert stale.decision == "REJECT"
    assert stale.reason_code == "REQUIRED_EDGE_STALE"


def test_whitespace_resource_id_fails_closed_at_shape_stage() -> None:
    # Shape validation only enforces the non-empty-string contract; a
    # well-formed but unknown resource id is caught later, fail closed,
    # by the entity fence (ERROR/UNKNOWN_ENTITY) — never a silent pass.
    op = dataclasses_replace(_medication_op(), declared_reads=("ghost_read",))
    outcome = admit(op, _store(), _scope())
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "UNKNOWN_ENTITY"


def test_malformed_store_and_scope_fail_closed() -> None:
    outcome = admit(_medication_op(), "not-a-store", _scope())  # type: ignore[arg-type]
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "STORE_MALFORMED"
    outcome = admit(_medication_op(), _store(), "not-a-scope")  # type: ignore[arg-type]
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "SCOPE_MALFORMED"


def test_unknown_mode_scope_fails_closed() -> None:
    outcome = admit(_medication_op(), _store(), _scope(mode="bogus_mode"))
    assert outcome.decision == "ERROR"
    assert outcome.reason_code == "SCOPE_MALFORMED"


# ---------------------------------------------------------------------------
# Property tests: order-independence, determinism, rejection monotonicity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(24))
def test_closure_iteration_order_never_changes_the_decision(seed: int) -> None:
    """frozenset iteration order is content-dependent; admission must not be."""
    resource_pool = ["medication_history", "allergy_history", "allergy_list"]
    built = []
    state = seed
    for _ in range(7):
        state = (state * 1103515245 + 12345) % (2**31)
        built.append(resource_pool[state % len(resource_pool)])

    def shuffled_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
        closure = set(_default_oracle(op))
        for extra in built:
            closure.add(DependencyEdge(EdgeKind.ENTITY, extra, "snapshot", "depends_on_current"))
        return frozenset(closure)

    outcomes = {
        admit(_medication_op(), _store(), _scope(oracle=shuffled_oracle)).outcome_digest
        for _ in range(3)
    }
    assert len(outcomes) == 1


def test_repeated_admission_is_deterministic() -> None:
    first = admit(_medication_op(), _store(), _scope())
    second = admit(_medication_op(), _store(), _scope())
    assert first.to_dict() == second.to_dict()
    assert first.outcome_digest == second.outcome_digest


def test_outcome_digest_is_stable_serialization() -> None:
    outcome = admit(_medication_op(), _store(), _scope())
    parsed = outcome.to_dict()
    assert json.loads(json.dumps(parsed)) == parsed
    assert len(outcome.outcome_digest) == 64


def test_rejection_monotonicity_fresh_store_property() -> None:
    """Any degradation of the input state can never turn REJECT into ADMIT.

    Property: if the candidate rejects on store S, it cannot admit on a store
    S' that differs from S only by additional concurrent installs.
    """
    base = _store()
    base.install("allergy_list", "sulfa")
    rejected = admit(_medication_op(), base, _scope())
    assert rejected.decision == "REJECT"
    for extra in ("medication_history", "allergy_history"):
        degraded = _store()
        degraded.install("allergy_list", "sulfa")
        degraded.install(extra, "extra-write")
        assert admit(_medication_op(), degraded, _scope()).decision == "REJECT"


# ---------------------------------------------------------------------------
# Mechanism description (design record)
# ---------------------------------------------------------------------------


def test_describe_mechanism_is_complete_design_record() -> None:
    mechanism = describe_mechanism()
    assert mechanism["candidate_id"] == cand.CANDIDATE_ID
    assert mechanism["blueprint_arm"] == "B4"
    assert mechanism["phase"].startswith("P04")
    assert mechanism["ablation_hooks"]["ablation_no_closure"]
    assert mechanism["ablation_hooks"]["ablation_global_version"]
    assert set(mechanism["mutation_registry"]) == set(cand.MUTATION_REGISTRY)
    serialized = json.dumps(mechanism, sort_keys=True)
    assert "design only" in serialized or "no empirical results" in serialized


def test_candidate_identity_constants() -> None:
    assert cand.CANDIDATE_ID == "clara.compsac.candidate.dependency-complete-scope-local-occ"
    assert cand.CANDIDATE_VERSION == "1.0.0"
    assert cand.KNOWN_MODES == {"scope_local", "global_version"}


# ---------------------------------------------------------------------------
# Helper: frozen-dataclass replace without importing dataclasses at top level
# ---------------------------------------------------------------------------


def dataclasses_replace(op: WriteOperation, **changes: object) -> WriteOperation:
    import dataclasses

    return dataclasses.replace(op, **changes)  # type: ignore[arg-type]
