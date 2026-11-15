"""CLARA-Care 2027 COMPSAC task COMPSAC-ablation — causal mechanism ablation harness.

Purpose
-------
P04 ablation harness (research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md,
arms B4 vs its own degraded mechanisms; task COMPSAC-ablation) for "Dependency-
Complete Optimistic Admission for Concurrent Clinical AI Writes". It runs the
P04 candidate (:mod:`evaluation.venue2027.compsac.candidate`) against ITSELF
with one mechanism toggled off at a time, on the SAME frozen suite of synthetic
concurrency cases built deterministically from the venue dataset generator
(:mod:`evaluation.venue2027.compsac.generate_dataset`, shared kernel
``dataset_kernel``). Ablations are DEVELOPMENT-scale instruments (mechanism
causality on frozen synthetic cases), never confirmatory performance results.

Variants (one mechanism axis each, everything else held identical):

- ``full_candidate`` — the candidate untouched (safety reference row).
- ``no_dependency_closure`` — candidate ablation hook
  :func:`candidate.ablation_no_closure`: the injected closure collapses to the
  declared touch set, so omitted cross-resource dependencies leave the fence
  and the canonical write-skew pair is ADMITTED (RQ2 causal evidence).
- ``global_version_coarse`` — candidate ablation hook
  :func:`candidate.ablation_global_version`: the scope-local version fence is
  replaced by the single coarse profile ``global_epoch`` (blueprint arm B0
  semantics) — safe but false-stale under unrelated concurrent writes (RQ1).
- ``no_epoch_validation`` — harness-implemented toggle (candidate mutation
  ``candidate.M1_DROP_EPOCH_VALIDATION`` via :func:`candidate.admit_with_mutation`):
  consent/policy epoch checks removed, so an epoch-race write is ADMITTED.
- ``no_lock_ordering`` — harness-implemented toggle: canonical lock ordering
  cannot be switched off inside the candidate without changing other axes, so
  the harness models it faithfully by confirming the candidate's built-in
  total order is already order-independent (COMPSAC-CASE-06): the row must
  equal the full candidate exactly. A behavioral difference here would falsify
  the order-independence claim; it is never manufactured.

For every variant the harness computes a small deterministic tally over the
frozen suite: ``forbidden_commits`` (ADMIT where the frozen family semantics
say the write must not land — omitted-dependency write skew, epoch-violating
writes), ``false_stale_aborts`` (REJECT of a case whose concurrent activity
the closure proves unrelated, or coarse-epoch aborts of otherwise valid
writes), ``committed_ops`` plus supporting counts. Only the candidate's own
typed reason codes are used for classification; the harness never invents
verdicts. Rows are typed :class:`AblationRow` and JSON-serializable.

Allowed input
-------------
- :func:`build_frozen_cases` — deterministic case suite from
  ``(seed=ABLATION_SUITE_SEED, n=ABLATION_SUITE_SIZE)`` dataset records
  (PHI-free synthetic payloads; no real patient data).
- :func:`run_variant(variant_id, cases)` — one variant over a frozen case
  suite; the same cases object must be shared across compared variants.
- :func:`run_ablation(name, case)` — task-manifest signature
  ``run_ablation(name, case) -> Outcome`` for one variant x one JSON-
  serializable case payload (as produced by :meth:`AblationCase.to_payload`).
- :func:`run_ablation_suite(seed)` — the full variant x case matrix with
  cross-variant causal-mechanism comparisons.

Failure semantics (stable uppercase reason codes)
-------------------------------------------------
- Unknown variant id -> ``Outcome(EXECUTION_ERROR, UNKNOWN_ABLATION_VARIANT)``
  (never guessed, never silently run as the full candidate).
- Malformed / unknown-family case payload -> ``EXECUTION_ERROR`` with
  ``CASE_MALFORMED`` / ``UNKNOWN_CASE_FAMILY``; refused, never coerced.
- An ``ERROR`` admission outcome (candidate fail-closed) is tallied as
  ``error_ops`` and never counted as a safe rejection or a forbidden commit.
- A frozen suite run twice yields byte-identical tallies (determinism; no
  clock, no RNG object, no hash randomization dependence).

Version
-------
``ABLATION_VERSION = "clara.compsac.ablation-v1"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.compsac import candidate as cand
from evaluation.venue2027.compsac import generate_dataset as gen

ABLATION_VERSION: Final[str] = "clara.compsac.ablation-v1"

#: Frozen development-scale suite parameters (NEVER confirmatory scale).
ABLATION_SUITE_SEED: Final[int] = 2027
ABLATION_SUITE_SIZE: Final[int] = 40
ABLATION_SUITE_VERSION: Final[str] = "clara.compsac.ablation-suite-v1"

VARIANT_FULL: Final[str] = "full_candidate"
VARIANT_NO_CLOSURE: Final[str] = "no_dependency_closure"
VARIANT_GLOBAL_VERSION: Final[str] = "global_version_coarse"
VARIANT_NO_EPOCH: Final[str] = "no_epoch_validation"
VARIANT_NO_LOCK_ORDER: Final[str] = "no_lock_ordering"

EXPECTED_EFFECT_NONE: Final[str] = "none"
EXPECTED_EFFECT_ADMITS_WRITE_SKEW: Final[str] = "admits_omitted_dependency_write_skew"
EXPECTED_EFFECT_FALSE_STALE: Final[str] = "false_stale_inflation"
EXPECTED_EFFECT_ADMITS_EPOCH_RACE: Final[str] = "admits_epoch_violation"
EXPECTED_EFFECT_ORDER_INVARIANCE: Final[str] = "order_invariance_confirmation"

APPLIED_BY_CANDIDATE_HOOK: Final[str] = "candidate_ablation_hook"
APPLIED_BY_HARNESS: Final[str] = "harness_toggle"


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One registered ablation variant (mechanism axis + provenance)."""

    variant_id: str
    description: str
    mechanism_axis: str
    expected_effect: str
    applied_by: str


ABLATION_VARIANTS: Final[Mapping[str, VariantSpec]] = {
    VARIANT_FULL: VariantSpec(
        variant_id=VARIANT_FULL,
        description=(
            "The unmodified P04 candidate: injected dependency closure + scope-local "
            "version fence + governance epoch validation under canonical lock order"
        ),
        mechanism_axis="none (safety reference)",
        expected_effect=EXPECTED_EFFECT_NONE,
        applied_by=APPLIED_BY_CANDIDATE_HOOK,
    ),
    VARIANT_NO_CLOSURE: VariantSpec(
        variant_id=VARIANT_NO_CLOSURE,
        description=(
            "candidate.ablation_no_closure: the injected closure collapses to the "
            "declared touch set; omitted cross-resource dependencies leave the fence "
            "and the canonical omitted-dependency write skew becomes admissible (RQ2)"
        ),
        mechanism_axis="dependency-closure",
        expected_effect=EXPECTED_EFFECT_ADMITS_WRITE_SKEW,
        applied_by=APPLIED_BY_CANDIDATE_HOOK,
    ),
    VARIANT_GLOBAL_VERSION: VariantSpec(
        variant_id=VARIANT_GLOBAL_VERSION,
        description=(
            "candidate.ablation_global_version: the scope-local version fence is "
            "replaced by the single coarse profile global_epoch (blueprint arm B0 "
            "semantics) - safe but false-stale under unrelated concurrent writes (RQ1)"
        ),
        mechanism_axis="scope-local-versioning",
        expected_effect=EXPECTED_EFFECT_FALSE_STALE,
        applied_by=APPLIED_BY_CANDIDATE_HOOK,
    ),
    VARIANT_NO_EPOCH: VariantSpec(
        variant_id=VARIANT_NO_EPOCH,
        description=(
            "candidate mutation M1-drop-epoch-validation applied via "
            "admit_with_mutation: every consent/policy epoch check removed; an "
            "epoch-race write becomes admissible (governance axis)"
        ),
        mechanism_axis="governance-epoch-validation",
        expected_effect=EXPECTED_EFFECT_ADMITS_EPOCH_RACE,
        applied_by=APPLIED_BY_HARNESS,
    ),
    VARIANT_NO_LOCK_ORDER: VariantSpec(
        variant_id=VARIANT_NO_LOCK_ORDER,
        description=(
            "harness-modeled toggle: the candidate's canonical lock order is a "
            "built-in total order that cannot be disabled without collapsing the "
            "fence itself, so this row must equal the full candidate exactly; any "
            "difference would falsify order-independence (COMPSAC-CASE-06)"
        ),
        mechanism_axis="canonical-lock-order",
        expected_effect=EXPECTED_EFFECT_ORDER_INVARIANCE,
        applied_by=APPLIED_BY_HARNESS,
    ),
}

#: Tally classification uses ONLY the candidate's own typed reason codes.
FORBIDDEN_COMMIT_REASON: Final[str] = cand.REASON_OK
FALSE_STALE_REASONS: Final[frozenset[str]] = frozenset(
    {
        cand.REASON_REQUIRED_EDGE_STALE,
        cand.REASON_WRITE_TARGET_SUPERSEDED,
        cand.REASON_GLOBAL_EPOCH_STALE,
    }
)
EPOCH_VIOLATION_REASONS: Final[frozenset[str]] = frozenset(
    {
        cand.REASON_CONSENT_EPOCH_STALE,
        cand.REASON_POLICY_EPOCH_STALE,
        cand.REASON_GOVERNANCE_EPOCH_STALE,
    }
)
FAIL_CLOSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        cand.REASON_OP_MALFORMED,
        cand.REASON_STORE_MALFORMED,
        cand.REASON_SCOPE_MALFORMED,
        cand.REASON_CLOSURE_ORACLE_MISSING,
        cand.REASON_CLOSURE_ORACLE_REFUSED,
        cand.REASON_CLOSURE_ORACLE_MALFORMED,
        cand.REASON_UNKNOWN_ENTITY,
        cand.REASON_UNKNOWN_GOVERNANCE_RESOURCE,
        cand.REASON_SNAPSHOT_INCOMPLETE,
        cand.REASON_UNKNOWN_MUTATION,
    }
)

REASON_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
REASON_CASE_MALFORMED: Final[str] = "CASE_MALFORMED"
REASON_UNKNOWN_CASE_FAMILY: Final[str] = "UNKNOWN_CASE_FAMILY"

_SUITE_ENTITIES: Final[tuple[str, ...]] = (
    "medication_order",
    "allergy_list",
    "medication_history",
    "allergy_history",
)
_CONCURRENT_SKEW_ENTITY: Final[str] = "allergy_list"
_CONCURRENT_ORDER_ENTITY: Final[str] = "medication_order"
_UNRELATED_ENTITY: Final[str] = "allergy_history"
_HISTORY_ENTITY: Final[str] = "medication_history"


# ---------------------------------------------------------------------------
# Frozen case suite (deterministic; built once, shared by every variant)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AblationCase:
    """One frozen concurrency case: operation + deterministic store mutations.

    ``unit_id``/``family``/``split`` come verbatim from the shared dataset
    kernel record; ``determinant``/``sequence`` are the kernel's deterministic
    payload integers that select the store-mutation arm inside the family.
    ``concurrent_entity``/``concurrent_value`` describe the pre-committed
    concurrent write applied to the fresh store before admission.
    ``expected_safe_outcome`` is the FROZEN family ground truth for the full
    candidate (mechanically derived from the family semantics, see
    :func:`_expected_safe_outcome`); a committed op on a case whose expected
    safe outcome is ``REJECT`` is a forbidden commit, a refused op whose
    expected outcome is ``ADMIT`` is a false-stale abort.
    """

    unit_id: str
    family: str
    split: str
    determinant: int
    sequence: int
    op_id: str
    operation_type: str
    declared_reads: tuple[str, ...]
    declared_writes: tuple[str, ...]
    write_values: Mapping[str, Any]
    concurrent_entity: str
    concurrent_value: str
    seed: int
    expected_safe_outcome: str = cand.DECISION_ADMIT

    def to_payload(self) -> dict[str, Any]:
        """JSON-serializable case payload (task-manifest ``case`` input)."""
        return {
            "case_id": self.unit_id,
            "suite_version": ABLATION_SUITE_VERSION,
            "suite_seed": self.seed,
            "family": self.family,
            "split": self.split,
            "determinant": self.determinant,
            "sequence": self.sequence,
            "operation": {
                "op_id": self.op_id,
                "operation_type": self.operation_type,
                "declared_reads": list(self.declared_reads),
                "declared_writes": list(self.declared_writes),
                "write_values": dict(self.write_values),
            },
            "concurrent_write": {
                "entity": self.concurrent_entity,
                "value": self.concurrent_value,
            },
            "expected_safe_outcome": self.expected_safe_outcome,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> AblationCase:
        """Rebuild a case from its payload; refuse malformed input fail-closed."""
        try:
            operation = payload["operation"]
            concurrent = payload["concurrent_write"]
            if not isinstance(operation, Mapping) or not isinstance(concurrent, Mapping):
                raise TypeError("operation/concurrent_write must be objects")
            return cls(
                unit_id=str(payload["case_id"]),
                family=str(payload["family"]),
                split=str(payload.get("split", "dev")),
                determinant=int(payload["determinant"]),
                sequence=int(payload["sequence"]),
                op_id=str(operation["op_id"]),
                operation_type=str(operation["operation_type"]),
                declared_reads=tuple(str(r) for r in operation["declared_reads"]),
                declared_writes=tuple(str(w) for w in operation["declared_writes"]),
                write_values={str(k): v for k, v in dict(operation["write_values"]).items()},
                concurrent_entity=str(concurrent["entity"]),
                concurrent_value=str(concurrent["value"]),
                seed=int(payload.get("suite_seed", ABLATION_SUITE_SEED)),
                expected_safe_outcome=str(
                    payload.get("expected_safe_outcome", cand.DECISION_ADMIT)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AblationError(REASON_CASE_MALFORMED, f"case payload malformed: {exc}") from exc


class AblationError(ValueError):
    """Fail-closed ablation harness error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def _case_schedule(family: str, operation_type: str, determinant: int) -> dict[str, Any]:
    """Map one frozen dataset record to its concurrent-write schedule.

    The arm selection uses pure integer parity arithmetic on the kernel
    payload, so the mapping is a deterministic function of the frozen suite
    seed alone. The concurrent-write entity is chosen RELATIVE to the case's
    operation type, because the fence itself is op-relative (blueprint
    canonical dependency schema):

    - ``medication_prescribe``: declares read ``medication_history`` + write
      ``medication_order``; the omitted REQUIRED edge is ``allergy_list``;
      the entity outside its fence is ``allergy_history``.
    - ``allergy_update``: declares read ``allergy_history`` + write
      ``allergy_list``; the omitted REQUIRED edge is ``medication_order``;
      the entity outside its fence is ``medication_history``.

    Family semantics (COMPSAC-CASE mapping):

    - ``clean``: determinant % 3 == 0 -> quiet store (valid write); otherwise
      an UNRELATED concurrent write OUTSIDE the case's fence (COMPSAC-CASE-01
      false-stale witness: must never abort the scope-local candidate).
    - ``omitted_dependency``: determinant even -> the case's omitted REQUIRED
      edge moves concurrently (canonical write-skew witness, COMPSAC-CASE-02);
      odd -> the declared write target is superseded concurrently.
    - ``epoch_race``: determinant even -> consent is revoked concurrently
      (governance register + per-entity binding move to ``c2``); odd ->
      unrelated concurrent write only.
    - ``stale_readset``: determinant even -> the case's declared read is
      superseded concurrently (justified abort); odd -> quiet store only.
    """
    if operation_type == "medication_prescribe":
        declared_read, declared_write = _HISTORY_ENTITY, _CONCURRENT_ORDER_ENTITY
        omitted_edge, outside_entity = _CONCURRENT_SKEW_ENTITY, _UNRELATED_ENTITY
    elif operation_type == "allergy_update":
        declared_read, declared_write = _UNRELATED_ENTITY, _CONCURRENT_SKEW_ENTITY
        omitted_edge, outside_entity = _CONCURRENT_ORDER_ENTITY, _HISTORY_ENTITY
    else:
        raise AblationError(REASON_CASE_MALFORMED, f"unknown operation type {operation_type!r}")
    if family == "clean":
        if determinant % 3 == 0:
            return {"concurrent_entity": "", "concurrent_value": ""}
        return {"concurrent_entity": outside_entity, "concurrent_value": "unrelated-note"}
    if family == "omitted_dependency":
        if determinant % 2 == 0:
            return {"concurrent_entity": omitted_edge, "concurrent_value": "sulfa"}
        return {"concurrent_entity": declared_write, "concurrent_value": "prior-order"}
    if family == "epoch_race":
        if determinant % 2 == 0:
            return {"concurrent_entity": "@revoke_consent", "concurrent_value": "c2"}
        return {"concurrent_entity": outside_entity, "concurrent_value": "unrelated-note"}
    if family == "stale_readset":
        if determinant % 2 == 0:
            return {"concurrent_entity": declared_read, "concurrent_value": "revised-history"}
        return {"concurrent_entity": "", "concurrent_value": ""}
    raise AblationError(REASON_UNKNOWN_CASE_FAMILY, f"unknown case family {family!r}")


def _expected_safe_outcome(family: str, determinant: int) -> str:
    """FROZEN family ground truth for the full candidate (mechanically derived).

    - ``clean``: the write is valid -> ADMIT (also under an unrelated
      concurrent write: the scope-local fence must not false-stale it,
      COMPSAC-CASE-01).
    - ``omitted_dependency``: an omitted REQUIRED edge or the declared write
      target moved concurrently -> REJECT (refusing the commit is safe).
    - ``epoch_race``: consent revoked concurrently -> REJECT; quiet/odd arm ->
      ADMIT.
    - ``stale_readset``: the declared read moved concurrently -> REJECT
      (justified abort); quiet arm -> ADMIT.
    A committed op on an expected-REJECT case is a forbidden commit; a refused
    op on an expected-ADMIT case is a false-stale abort.
    """
    if family == "clean":
        return cand.DECISION_ADMIT
    if family in ("omitted_dependency", "stale_readset"):
        return (
            cand.DECISION_REJECT
            if determinant % 2 == 0 or family == "omitted_dependency"
            else cand.DECISION_ADMIT
        )
    if family == "epoch_race":
        return cand.DECISION_REJECT if determinant % 2 == 0 else cand.DECISION_ADMIT
    raise AblationError(REASON_UNKNOWN_CASE_FAMILY, f"unknown case family {family!r}")


def _case_from_record(record: Mapping[str, Any], seed: int) -> AblationCase:
    """Build one frozen case from a dataset-kernel record mapping."""
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        raise AblationError(
            REASON_CASE_MALFORMED, f"record {record.get('unit_id')!r} has no payload"
        )
    family = str(payload.get("family", record.get("family", "")))
    determinant = int(payload["determinant"])
    sequence = int(payload["sequence"])
    unit_id = str(record.get("unit_id", payload.get("unit_id", f"sched-case-{sequence:05d}")))
    if sequence % 2 == 0:
        operation_type = "medication_prescribe"
        declared_reads: tuple[str, ...] = (_HISTORY_ENTITY,)
        declared_writes: tuple[str, ...] = (_CONCURRENT_ORDER_ENTITY,)
        write_values: dict[str, Any] = {_CONCURRENT_ORDER_ENTITY: "metformin-500mg"}
    else:
        operation_type = "allergy_update"
        declared_reads = (_UNRELATED_ENTITY,)
        declared_writes = (_CONCURRENT_SKEW_ENTITY,)
        write_values = {_CONCURRENT_SKEW_ENTITY: "sulfa"}
    schedule = _case_schedule(family, operation_type, determinant)
    return AblationCase(
        unit_id=unit_id,
        family=family,
        split=str(record.get("split", "dev")),
        determinant=determinant,
        sequence=sequence,
        op_id=f"{unit_id}-op",
        operation_type=operation_type,
        declared_reads=declared_reads,
        declared_writes=declared_writes,
        write_values=write_values,
        concurrent_entity=str(schedule["concurrent_entity"]),
        concurrent_value=str(schedule["concurrent_value"]),
        seed=seed,
        expected_safe_outcome=_expected_safe_outcome(family, determinant),
    )


def build_frozen_cases(seed: int = ABLATION_SUITE_SEED) -> tuple[AblationCase, ...]:
    """Build the frozen development-scale case suite from the dataset generator.

    Deterministic function of ``seed`` only: the same seed always yields the
    same cases (byte-identical payloads), so every variant is executed over
    exactly the same inputs. The suite spans all four COMPSAC families.
    """
    dataset = gen.generate(seed, split=None, n=ABLATION_SUITE_SIZE)
    cases = tuple(
        _case_from_record(
            {
                "unit_id": record.unit_id,
                "split": record.split,
                "payload": dict(record.payload),
            },
            seed,
        )
        for record in dataset.records
    )
    if not cases:
        raise AblationError(REASON_CASE_MALFORMED, "frozen case suite is empty")
    return cases


# ---------------------------------------------------------------------------
# Candidate wiring: store/scope construction and variant application
# ---------------------------------------------------------------------------


def _fresh_store(case: AblationCase) -> cand.ClinicalWriteStore:
    """Fresh store at the frozen snapshot (all entities version 1, c1/p1)."""
    return cand.ClinicalWriteStore(
        entities={
            entity: {"version": 1, "value": "initial", "consent_epoch": "c1", "policy_epoch": "p1"}
            for entity in _SUITE_ENTITIES
        },
        governance_epochs={"consent": "c1", "policy": "p1"},
        global_epoch=1,
    )


def _apply_concurrent_write(store: cand.ClinicalWriteStore, case: AblationCase) -> None:
    """Apply the case's pre-committed concurrent write to the fresh store."""
    if case.concurrent_entity == "@revoke_consent":
        store.set_governance_epoch(cand.GOVERNANCE_CONSENT, case.concurrent_value)
        for entity in _SUITE_ENTITIES:
            store.set_entity_epoch(entity, "consent_epoch", case.concurrent_value)
        return
    if case.concurrent_entity:
        store.install(case.concurrent_entity, case.concurrent_value)


def _full_closure_oracle(op: cand.WriteOperation) -> frozenset[cand.DependencyEdge]:
    """Injected closure oracle: frozen per-operation required dependency schema.

    Returns the declared touch set PLUS the semantically required cross-resource
    edges per operation type PLUS the governance anchors (consent, policy) —
    the completeness contract adjudicated independently in COMPSAC-X02.
    """
    required_reads: Mapping[str, tuple[str, ...]] = {
        "medication_prescribe": (_CONCURRENT_SKEW_ENTITY,),
        "allergy_update": (_CONCURRENT_ORDER_ENTITY,),
    }
    closure: set[cand.DependencyEdge] = set()
    for resource in (*op.declared_reads, *op.declared_writes):
        closure.add(
            cand.DependencyEdge(cand.EdgeKind.ENTITY, resource, "snapshot", "depends_on_current")
        )
    for resource in required_reads.get(op.operation_type, ()):
        closure.add(
            cand.DependencyEdge(cand.EdgeKind.ENTITY, resource, "snapshot", "depends_on_current")
        )
    closure.add(
        cand.DependencyEdge(cand.EdgeKind.GOVERNANCE, cand.GOVERNANCE_CONSENT, "c1", "governed_by")
    )
    closure.add(
        cand.DependencyEdge(cand.EdgeKind.GOVERNANCE, cand.GOVERNANCE_POLICY, "p1", "governed_by")
    )
    return frozenset(closure)


def _variant_scope(case: AblationCase, variant_id: str) -> cand.AdmissionScope:
    """Build the admission scope shared by every variant for one case."""
    snapshot_versions = {entity: 1 for entity in _SUITE_ENTITIES}
    return cand.AdmissionScope(
        tenant_id="ablation-tenant",
        principal_id="ablation-principal",
        purpose="self_care",
        consent_epoch="c1",
        policy_epoch="p1",
        dependency_oracle=_full_closure_oracle,
        snapshot_versions=snapshot_versions,
        snapshot_global_epoch=1,
        mode=cand.MODE_SCOPE_LOCAL,
    )


def _variant_mutation(variant_id: str) -> str | None:
    """Map a harness toggle onto the candidate's registered mutation ids."""
    if variant_id == VARIANT_NO_EPOCH:
        return cand.M1_DROP_EPOCH_VALIDATION
    return None


def _apply_variant(
    store: cand.ClinicalWriteStore, scope: cand.AdmissionScope, variant_id: str
) -> tuple[cand.ClinicalWriteStore, cand.AdmissionScope, str | None]:
    """Apply one variant's mechanism toggle to a fresh (store, scope) pair.

    Returns ``(store, scope, mutation_id)``: candidate ablation hooks rewrite
    the scope via the candidate's own hook functions; the harness-implemented
    epoch toggle returns the candidate's registered mutation id; the
    order-invariance row leaves the pair untouched (the candidate's canonical
    lock order is a built-in total order that cannot be switched off without
    collapsing the fence itself).
    """
    if variant_id == VARIANT_FULL or variant_id == VARIANT_NO_LOCK_ORDER:
        return store, scope, None
    if variant_id == VARIANT_NO_CLOSURE:
        return store, cand.ablation_no_closure(scope), None
    if variant_id == VARIANT_GLOBAL_VERSION:
        return store, cand.ablation_global_version(scope), None
    if variant_id == VARIANT_NO_EPOCH:
        return store, scope, _variant_mutation(variant_id)
    raise AblationError(REASON_UNKNOWN_ABLATION_VARIANT, f"unknown variant id {variant_id!r}")


def _run_case(variant_id: str, case: AblationCase) -> dict[str, Any]:
    """Run one case under one variant; classify strictly by reason codes."""
    store, scope, mutation_id = _apply_variant(
        _fresh_store(case), _variant_scope(case, variant_id), variant_id
    )
    _apply_concurrent_write(store, case)
    op = cand.WriteOperation(
        op_id=case.op_id,
        operation_type=case.operation_type,
        declared_reads=case.declared_reads,
        declared_writes=case.declared_writes,
        write_values=dict(case.write_values),
    )
    if mutation_id is not None:
        outcome = cand.admit_with_mutation(op, store, scope, mutation_id)
    else:
        outcome = cand.admit(op, store, scope)
    return {
        "case_id": case.unit_id,
        "family": case.family,
        "expected_safe_outcome": case.expected_safe_outcome,
        "decision": outcome.decision,
        "reason_code": outcome.reason_code,
        "counted_as_success": outcome.counted_as_success,
        "fail_closed": outcome.fail_closed,
        "mode": outcome.mode,
        "closure_size": outcome.closure_size,
    }


# ---------------------------------------------------------------------------
# Typed results
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AblationRow:
    """One variant's deterministic tally over the frozen case suite."""

    variant_id: str
    description: str
    mechanism_axis: str
    expected_effect: str
    applied_by: str
    forbidden_commits: int
    false_stale_aborts: int
    committed_ops: int
    rejected_ops: int
    aborted_ops: int
    error_ops: int
    case_count: int
    suite_seed: int
    suite_unit_ids: tuple[str, ...]
    variant_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "description": self.description,
            "mechanism_axis": self.mechanism_axis,
            "expected_effect": self.expected_effect,
            "applied_by": self.applied_by,
            "forbidden_commits": self.forbidden_commits,
            "false_stale_aborts": self.false_stale_aborts,
            "committed_ops": self.committed_ops,
            "rejected_ops": self.rejected_ops,
            "aborted_ops": self.aborted_ops,
            "error_ops": self.error_ops,
            "case_count": self.case_count,
            "suite_seed": self.suite_seed,
            "suite_unit_ids": list(self.suite_unit_ids),
            "variant_digest": self.variant_digest,
        }


def _tally(variant_id: str, cases: Sequence[AblationCase]) -> AblationRow:
    """Run one variant over the frozen cases and compute its typed tally."""
    spec = ABLATION_VARIANTS.get(variant_id)
    if spec is None:
        raise AblationError(REASON_UNKNOWN_ABLATION_VARIANT, f"unknown variant id {variant_id!r}")
    records = [_run_case(variant_id, case) for case in cases]
    # Ground truth is the FROZEN per-case family expectation: a committed op
    # on an expected-REJECT case is a forbidden commit (the ablated mechanism
    # let an unsafe write land); a refused op on an expected-ADMIT case is a
    # false-stale abort (the fence refused a write that must land).
    forbidden = sum(
        1
        for r in records
        if r["decision"] == cand.DECISION_ADMIT
        and r["expected_safe_outcome"] == cand.DECISION_REJECT
    )
    false_stale = sum(
        1
        for r in records
        if r["decision"] == cand.DECISION_REJECT
        and r["expected_safe_outcome"] == cand.DECISION_ADMIT
        and r["reason_code"] in FALSE_STALE_REASONS
    )
    epoch_aborts = sum(
        1
        for r in records
        if r["decision"] == cand.DECISION_REJECT and r["reason_code"] in EPOCH_VIOLATION_REASONS
    )
    errors = sum(1 for r in records if r["decision"] == cand.DECISION_ERROR)
    rejected = sum(1 for r in records if r["decision"] == cand.DECISION_REJECT)
    committed = sum(1 for r in records if r["decision"] == cand.DECISION_ADMIT)
    # variant_digest hashes ONLY the per-case decision records (never the
    # variant metadata), so rows of behaviorally identical variants (full vs
    # order-invariance confirmation) share a digest by construction.
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AblationRow(
        variant_id=variant_id,
        description=spec.description,
        mechanism_axis=spec.mechanism_axis,
        expected_effect=spec.expected_effect,
        applied_by=spec.applied_by,
        forbidden_commits=forbidden,
        false_stale_aborts=false_stale,
        committed_ops=committed,
        rejected_ops=rejected,
        aborted_ops=epoch_aborts,
        error_ops=errors,
        case_count=len(records),
        suite_seed=cases[0].seed if cases else ABLATION_SUITE_SEED,
        suite_unit_ids=tuple(case.unit_id for case in cases),
        variant_digest=digest,
    )


def variant_ids() -> tuple[str, ...]:
    """Registered variant ids in canonical (registry) order."""
    return tuple(ABLATION_VARIANTS)


def run_variant(variant_id: str, cases: Sequence[AblationCase]) -> AblationRow:
    """Run one ablation variant over a FROZEN case suite (same-cases invariant).

    The caller passes the identical frozen ``cases`` object to every compared
    variant; ``run_ablation_suite`` builds it once and shares it. Unknown
    variants fail closed with :class:`AblationError` /
    ``UNKNOWN_ABLATION_VARIANT`` (never silently run as the full candidate).
    """
    spec = ABLATION_VARIANTS.get(variant_id)
    if spec is None:
        raise AblationError(REASON_UNKNOWN_ABLATION_VARIANT, f"unknown variant id {variant_id!r}")
    if not cases:
        raise AblationError(REASON_CASE_MALFORMED, "frozen case suite is empty")
    return _tally(variant_id, cases)


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE variant on ONE case payload -> Outcome.

    - Determined outcome: ``ADMIT`` if the variant committed the operation,
      ``REJECT`` if the admission pipeline refused it (``counted_as_success``
      is True for both determined outcomes, per the shared harness contract).
    - Fail closed: unknown variant -> ``EXECUTION_ERROR`` /
      ``UNKNOWN_ABLATION_VARIANT``; malformed / unknown-family case ->
      ``EXECUTION_ERROR`` / ``CASE_MALFORMED`` / ``UNKNOWN_CASE_FAMILY``;
      candidate ``ERROR`` outcomes surface as ``EXECUTION_ERROR`` carrying the
      pipeline reason code (never counted as a safe rejection).
    - The ``detail`` JSON carries the per-case record and tallies so nothing
      is silently dropped.
    """
    spec = ABLATION_VARIANTS.get(name)
    if spec is None:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{REASON_UNKNOWN_ABLATION_VARIANT}: unknown ablation variant {name!r}",
        )
    try:
        parsed = AblationCase.from_payload(case)
        _case_schedule(parsed.family, parsed.operation_type, parsed.determinant)
    except AblationError as exc:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{exc.reason_code}: {exc.detail}",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{REASON_CASE_MALFORMED}: {exc}",
        )
    record = _run_case(name, parsed)
    decision = str(record["decision"])
    if decision == cand.DECISION_ERROR:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=json.dumps(
                {"reason_code": record["reason_code"], "case": record}, sort_keys=True
            ),
        )
    observed = "ADMIT" if decision == cand.DECISION_ADMIT else "REJECT"
    forbidden = (
        1
        if decision == cand.DECISION_ADMIT
        and record["expected_safe_outcome"] == cand.DECISION_REJECT
        else 0
    )
    false_stale = (
        1
        if decision == cand.DECISION_REJECT
        and record["expected_safe_outcome"] == cand.DECISION_ADMIT
        and record["reason_code"] in FALSE_STALE_REASONS
        else 0
    )
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        detail=json.dumps(
            {
                "ablation_version": ABLATION_VERSION,
                "variant_id": name,
                "mechanism_axis": spec.mechanism_axis,
                "reason_code": record["reason_code"],
                "case": record,
                "forbidden_commits": forbidden,
                "false_stale_aborts": false_stale,
                "committed_ops": 1 if decision == cand.DECISION_ADMIT else 0,
            },
            sort_keys=True,
        ),
    )


def run_ablation_suite(seed: int = ABLATION_SUITE_SEED) -> dict[str, Any]:
    """Run every registered variant over the SAME frozen suite (dev-scale).

    Returns the variant rows plus cross-variant causal-mechanism comparisons.
    The frozen case suite is built EXACTLY ONCE and shared by all variants, so
    seeds are equal across variants by construction (same-case guarantee).
    """
    cases = build_frozen_cases(seed)
    rows = {variant_id: _tally(variant_id, cases) for variant_id in ABLATION_VARIANTS}
    by_variant = {vid: row.to_dict() for vid, row in rows.items()}
    full = rows[VARIANT_FULL]
    no_closure = rows[VARIANT_NO_CLOSURE]
    global_version = rows[VARIANT_GLOBAL_VERSION]
    no_epoch = rows[VARIANT_NO_EPOCH]
    no_lock = rows[VARIANT_NO_LOCK_ORDER]
    comparison = {
        "same_cases_across_variants": len({row.suite_unit_ids for row in rows.values()}) == 1
        and len({row.suite_seed for row in rows.values()}) == 1,
        "causal_mechanism": {
            "full_candidate_zero_forbidden_commits": full.forbidden_commits == 0,
            "no_dependency_closure_admits_write_skew": (
                no_closure.forbidden_commits > full.forbidden_commits
            ),
            "no_epoch_validation_admits_epoch_race": (
                no_epoch.forbidden_commits > full.forbidden_commits
            ),
            "global_version_false_stales": (
                global_version.false_stale_aborts > full.false_stale_aborts
            ),
            "global_version_commits_less": global_version.committed_ops < full.committed_ops,
            "lock_order_invariance_confirmed": (
                no_lock.variant_digest == full.variant_digest
                and no_lock.forbidden_commits == full.forbidden_commits
            ),
        },
        "forbidden_commits_by_variant": {vid: row.forbidden_commits for vid, row in rows.items()},
        "false_stale_aborts_by_variant": {vid: row.false_stale_aborts for vid, row in rows.items()},
        "committed_ops_by_variant": {vid: row.committed_ops for vid, row in rows.items()},
        "variant_digests": {vid: row.variant_digest for vid, row in rows.items()},
    }
    return {
        "ablation_version": ABLATION_VERSION,
        "suite_version": ABLATION_SUITE_VERSION,
        "suite_seed": seed,
        "suite_size": len(cases),
        "suite_unit_ids": [case.unit_id for case in cases],
        "suite_families": sorted({case.family for case in cases}),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
        "rows": by_variant,
        "comparison": comparison,
    }


def describe_ablation() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablation_version": ABLATION_VERSION,
        "task_id": "COMPSAC-ablation",
        "phase": "P04 (development-scale mechanism ablation)",
        "candidate_id": cand.CANDIDATE_ID,
        "suite_version": ABLATION_SUITE_VERSION,
        "suite_seed": ABLATION_SUITE_SEED,
        "suite_size": ABLATION_SUITE_SIZE,
        "scale_note": "DEVELOPMENT-scale; never confirmatory performance results",
        "variants": {
            vid: {
                "description": spec.description,
                "mechanism_axis": spec.mechanism_axis,
                "expected_effect": spec.expected_effect,
                "applied_by": spec.applied_by,
            }
            for vid, spec in ABLATION_VARIANTS.items()
        },
        "classification": {
            "forbidden_commit_reason": FORBIDDEN_COMMIT_REASON,
            "false_stale_reasons": sorted(FALSE_STALE_REASONS),
            "epoch_violation_reasons": sorted(EPOCH_VIOLATION_REASONS),
            "fail_closed_reasons": sorted(FAIL_CLOSED_REASONS),
        },
        "manifest_signature": "run_ablation(name: str, case: Mapping) -> Outcome",
    }


__all__ = [
    "ABLATION_SUITE_SEED",
    "ABLATION_SUITE_SIZE",
    "ABLATION_SUITE_VERSION",
    "ABLATION_VARIANTS",
    "ABLATION_VERSION",
    "AblationCase",
    "AblationError",
    "AblationRow",
    "VariantSpec",
    "build_frozen_cases",
    "describe_ablation",
    "run_ablation",
    "run_ablation_suite",
    "run_variant",
    "variant_ids",
]
