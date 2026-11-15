"""CLARA-Care 2027 COMPSAC task COMPSAC-unit — deterministic property tests.

Purpose
-------
Property, metamorphic and mutation tests over the REAL COMPSAC OCC arms and
dependency DSL, imported live and never reimplemented or stubbed:

- ``evaluation/venue2027/compsac/baselines.py`` — the implemented blueprint
  arms via the public ``run_baseline`` entry point: B0
  ``global-profile-version-occ``, B1 ``silo-style-entity-readset-occ``,
  B3 ``entity-occ-no-closure-ablation`` and the candidate B4
  ``dependency-complete-scope-local-occ``;
- ``evaluation/venue2027/compsac/dependency_dsl.py`` — the typed dependency
  language (``compile_dependencies``, fail-closed compile rejections);
- ``evaluation/venue2027/compsac/independent_oracle.py`` — the independent
  FORBIDDEN-COMMIT adjudicator (frozen rule table, candidate-import-free);
- ``evaluation/venue2027/compsac/independent_closure_oracle.py`` — the
  independent declarative dependency-closure reference.

Test families (manifest ``COMPSAC-unit``, phase P05: "Write positive/negative/
unknown boundaries, skew/race scenarios, two-step metamorphic relations and
mutation tests; seed all randomness"):

1. **Positive boundaries** — documented guarantees hold end to end: clean
   single-transaction schedules admit on every implemented arm; B4 admits a
   correctly-declared concurrent dependency chain (no false-stale) and admits
   an unrelated concurrent write that the coarse B0 fence rejects
   (COMPSAC-CASE-01 witness); the DSL compiles a clean operation to a
   complete, stable closure; the independent oracles pass their built-in
   self-checks and live source-independence guards.
2. **Negative boundaries** — adversarial inputs fail closed with stable
   uppercase reason codes (``NOT_RUN_EXTERNAL``/``BASELINE_UNAVAILABLE``,
   ``EXECUTION_ERROR``/``CASE_MALFORMED``/``SCHEDULE_MALFORMED``,
   ``ENTITY_UNKNOWN``, ``UNKNOWN_MUTATION_TARGET``, ``UNKNOWN_PREDICATE``,
   ``SCHEMA_VERSION_MISMATCH``, ``EMPTY_OPERATION``, ``UNRULED_RESOURCE``,
   ``AMBIGUOUS_RULE_REVIEW``, ``STATE_MISMATCH``) and are never silently
   counted as safe rejections.
3. **Unknown boundaries** — ``INDETERMINATE`` is first-class: unmodelled and
   undeclared case families are never coerced to a safe verdict; a missing
   ``case_id`` raises the stable kernel error.
4. **Write-skew and policy-epoch race scenarios** — the canonical
   omitted-dependency skew (B4 rejects the second commit while B1/B3 admit
   both, in either schedule order), consent- and policy-epoch races on the
   omitted governance binding (B4 rejects the stale-epoch write while the
   declared-fence arms commit it — the documented RQ2 gap), liveness under
   the new epoch, and justified stale-readset rejections on every arm.
5. **Two-step metamorphic relations** — adding a required dependency edge to
   the frozen closure schema (step 2 after the base run) can only shrink the
   commit set and can only reduce forbidden commits, never increase them
   (asserted monotonically across seeded schedule orders/versions); declaring
   the omitted edge in the workload (step 2) reduces the declared-fence
   arms' forbidden commits to zero; adding an epoch binding can only reduce
   commits; DSL closures are monotone under added required reads and stable
   under added declared edges.
6. **Mutation checks** — canonical mutants are each killed by a surviving
   property: closure-drop and epoch-check-drop on B4 (caught by the safety
   invariant), all-deny B4 (caught by the liveness control — an arbitrary
   all-deny never passes correctness), an oracle rule-table flip (caught by
   the frozen self-checks), and a candidate-importing oracle (caught by the
   independence guard).

SAFETY INVARIANT (blueprint falsification rule)
-----------------------------------------------
Over the whole seeded schedule sweep, B4 never commits a transaction the
independent oracle labels forbidden: ``committed(B4) ∩ forbidden(schedule)``
is empty for every generated case, and every by-construction forbidden
schedule is oracle-``REJECT``-labeled while every ``ADMIT``-labeled family
carries no forbidden transaction.

Determinism
-----------
Every stochastic step uses an explicit ``random.Random(FIXED_SEED)``
instance created locally; there is no unseeded ``random`` call, no clock, no
network, no database. The modules under test are pure, so the seeded sweep
is replay-identical byte for byte.

Allowed input
-------------
Synthetic, JSON-serializable schedules only (versioned in-memory store,
declared read/write sets, consent/policy epoch bindings). No PHI/PII, no
provider, no PostgreSQL (B2 is out of scope here: it is exercised as
NOT_RUN_EXTERNAL honesty by the baseline fidelity suite).

Failure semantics
-----------------
A violated property surfaces as a normal assertion failure carrying the
structured per-transaction payload. Module-under-test stable reason codes
are asserted as-is; ``EXECUTION_ERROR``/``NOT_RUN_EXTERNAL`` outcomes are
never treated as determined acceptances. Mutations are injected only via
``unittest.mock.patch.object`` / ``patch.dict`` context managers and are
fully restored even on failure.

Version
-------
``COMPSAC_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"`` over
``COMPSAC_BASELINES_VERSION`` 1.0.0, ``DEPENDENCY_DSL_VERSION``
clara.compsac.dependency-dsl-v1 and the v1 independent oracles.
"""

from __future__ import annotations

import json
import random
import unittest.mock

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.compsac import baselines as bl
from evaluation.venue2027.compsac import dependency_dsl as dsl
from evaluation.venue2027.compsac import independent_closure_oracle as closure_oracle
from evaluation.venue2027.compsac import independent_oracle as oracle

COMPSAC_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"

#: Fixed seed for every randomized step of this suite (manifest: "seed all
#: randomness"). Never advanced, never derived from the environment.
FIXED_SEED = 20271116

ARMS: tuple[str, ...] = (
    bl.B0_GLOBAL_PROFILE,
    bl.B1_SILO_READSET,
    bl.B3_NO_CLOSURE_ABLATION,
    bl.B4_DEPENDENCY_COMPLETE,
)
B0 = bl.B0_GLOBAL_PROFILE
B1 = bl.B1_SILO_READSET
B3 = bl.B3_NO_CLOSURE_ABLATION
B4 = bl.B4_DEPENDENCY_COMPLETE

#: Oracle-registered COMPSAC case families (frozen kernel registry).
COMPSAC_FAMILIES: tuple[str, ...] = ("clean", "omitted_dependency", "epoch_race", "stale_readset")

ENTITIES: tuple[str, ...] = (
    "medication_order",
    "allergy_list",
    "medication_history",
    "allergy_history",
)
UNRELATED_ENTITY = "allergy_history"
VALUE_POOL: tuple[str, ...] = ("metformin-500mg", "sulfa", "note-42", "revised-history")

SWEEP_SIZE = 48
DSL_SWEEP_OPS = 16

#: Deterministic DSL resource universe (schema-registered rows only).
DSL_RESOURCE_KINDS: dict[str, dsl.DependencyKind] = {
    "consent": dsl.DependencyKind.GOVERNANCE,
    "policy": dsl.DependencyKind.GOVERNANCE,
    "medication": dsl.DependencyKind.ENTITY,
    "allergy": dsl.DependencyKind.ENTITY,
    "history": dsl.DependencyKind.ENTITY,
    "lab_digest": dsl.DependencyKind.EVIDENCE,
    "write_lease": dsl.DependencyKind.LEASE,
}


# ---------------------------------------------------------------------------
# Deterministic synthetic schedule builders (pure; no entropy, no clock)
# ---------------------------------------------------------------------------


def _ctx(seed: int = FIXED_SEED) -> RunContext:
    return RunContext(
        campaign_id="camp-compsac-algorithm-properties",
        case_id="case-algorithm-properties",
        arm_id="arm",
        seed=seed,
        source_commit="a" * 40,
        deadline_seconds=60.0,
    )


def _store(versions: dict[str, int], consent: str = "c1") -> dict[str, object]:
    return {
        entity: {"version": versions[entity], "value": "initial", "consent_epoch": consent}
        for entity in ENTITIES
    }


def _epochs(
    consent_map: dict[str, str] | None = None, policy_map: dict[str, str] | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if consent_map is not None:
        payload["consent_epochs"] = consent_map
    if policy_map is not None:
        payload["policy_epochs"] = policy_map
    return payload


def _tx_medication(
    *,
    v0: int,
    value: str = "metformin-500mg",
    consent: str = "c1",
    policy: str = "p1",
    declare_required_at: int | None = None,
) -> dict[str, object]:
    """medication_prescribe: declares medication_history, writes medication_order.

    Its semantically REQUIRED edge (allergy_list, per the frozen
    ``REQUIRED_DEPENDENCIES`` schema) stays OMITTED unless
    ``declare_required_at`` promotes it to a declared read at that version.
    """
    tx: dict[str, object] = {
        "tx_id": "t-med",
        "declared_reads": ["medication_history"],
        "declared_writes": ["medication_order"],
        "operation_type": "medication_prescribe",
        "read_versions": {"medication_history": v0},
        "write_values": {"medication_order": value},
        "consent_epoch": consent,
        "policy_epoch": policy,
    }
    if declare_required_at is not None:
        tx["read_versions"] = {**tx["read_versions"], "allergy_list": declare_required_at}  # type: ignore[dict-item]
        tx["declared_reads"] = ["medication_history", "allergy_list"]
    return tx


def _tx_allergy(
    *,
    v0: int,
    value: str = "sulfa",
    consent: str = "c1",
    policy: str = "p1",
    declare_required_at: int | None = None,
) -> dict[str, object]:
    """allergy_update: declares allergy_history, writes allergy_list; the
    REQUIRED edge medication_order stays OMITTED unless declared."""
    tx: dict[str, object] = {
        "tx_id": "t-allergy",
        "declared_reads": ["allergy_history"],
        "declared_writes": ["allergy_list"],
        "operation_type": "allergy_update",
        "read_versions": {"allergy_history": v0},
        "write_values": {"allergy_list": value},
        "consent_epoch": consent,
        "policy_epoch": policy,
    }
    if declare_required_at is not None:
        tx["read_versions"] = {**tx["read_versions"], "medication_order": declare_required_at}  # type: ignore[dict-item]
        tx["declared_reads"] = ["allergy_history", "medication_order"]
    return tx


def _tx_unrelated(*, v0: int, value: str = "note-42") -> dict[str, object]:
    """unknown_op outside every closure fence: reads+writes allergy_history."""
    return {
        "tx_id": "t-unrelated",
        "declared_reads": [UNRELATED_ENTITY],
        "declared_writes": [UNRELATED_ENTITY],
        "operation_type": "unknown_op",
        "read_versions": {UNRELATED_ENTITY: v0},
        "write_values": {UNRELATED_ENTITY: value},
    }


def _full_epoch_maps() -> dict[str, object]:
    return _epochs(
        consent_map={entity: "c1" for entity in ENTITIES},
        policy_map={entity: "p1" for entity in ENTITIES},
    )


def _schedule(
    transactions: list[dict[str, object]],
    *,
    v0: int = 1,
    consent: str = "c1",
    consent_map: dict[str, str] | None = None,
    policy_map: dict[str, str] | None = None,
) -> dict[str, object]:
    versions = {entity: v0 for entity in ENTITIES}
    payload: dict[str, object] = {"store": _store(versions, consent=consent)}
    if consent_map is None and policy_map is None:
        payload.update(_full_epoch_maps())
    else:
        payload.update(_epochs(consent_map, policy_map))
    payload["transactions"] = transactions
    return payload


def _case(schedule: dict[str, object], seed: int = FIXED_SEED) -> dict[str, object]:
    return {"case_id": "case-compsac-algorithm-properties", "seed": seed, "schedule": schedule}


def _run(arm: str, schedule: dict[str, object], seed: int = FIXED_SEED) -> Outcome:
    outcome = bl.run_baseline(arm, _case(schedule, seed), _ctx(seed))
    assert isinstance(outcome, Outcome)
    return outcome


def _detail(outcome: Outcome) -> dict[str, object]:
    return json.loads(outcome.detail)


def _records(outcome: Outcome) -> list[dict[str, object]]:
    records = _detail(outcome)["transactions"]
    assert isinstance(records, list) and records
    return [dict(r) for r in records]


def _committed(outcome: Outcome) -> set[str]:
    return {str(r["tx_id"]) for r in _records(outcome) if r["outcome"] == "COMMIT"}


def _abort_reasons(outcome: Outcome) -> dict[str, str]:
    return {
        str(r["tx_id"]): str(r["reason_code"]) for r in _records(outcome) if r["outcome"] == "ABORT"
    }


def _reason_of(outcome: Outcome, tx_id: str) -> str:
    reasons = _abort_reasons(outcome)
    assert tx_id in reasons, f"{tx_id} did not abort: {_records(outcome)}"
    return reasons[tx_id]


def _oracle_label(family: str) -> str:
    """Independent-oracle verdict for one case family (frozen rule table)."""
    result = oracle.adjudicate({"case_id": f"prop-{family}", "family": family})
    return str(result.outcome)


# ---------------------------------------------------------------------------
# Seeded property-case generator (the suite's sole randomness, fully seeded)
# ---------------------------------------------------------------------------


def _build_property_case(
    family: str, *, flip: bool, v0: int, med_value: str, allergy_value: str, unrelated_value: str
) -> tuple[dict[str, object], frozenset[str]]:
    """One (schedule, forbidden_tx_ids) pair for an oracle-registered family.

    The forbidden set is a by-construction property of the schedule shape
    (which transaction would commit over a superseded/stale required edge);
    the sweep ties every non-empty forbidden set to an oracle ``REJECT``
    label. ``flip`` swaps the transaction order / which op carries the race.
    """
    first, second = (_tx_allergy, _tx_medication) if flip else (_tx_medication, _tx_allergy)
    if family == "clean":
        if flip:  # clean-unrelated pair: unknown_op write outside every fence
            schedule = _schedule([_tx_medication(v0=v0, value=med_value), _tx_unrelated(v0=v0)], v0=v0)
            return schedule, frozenset()
        schedule = _schedule([_tx_medication(v0=v0, value=med_value)], v0=v0)
        return schedule, frozenset()
    if family == "omitted_dependency":
        tx_first = first(v0=v0, value=med_value if not flip else allergy_value)
        tx_second = second(v0=v0, value=allergy_value if not flip else med_value)
        schedule = _schedule([tx_first, tx_second], v0=v0)
        return schedule, frozenset({str(tx_second["tx_id"])})
    if family == "epoch_race":
        # The omitted governance binding moves to a new epoch before the
        # write commits; the tx still declares the epoch it started under.
        if flip:
            schedule = _schedule(
                [_tx_allergy(v0=v0, value=allergy_value)],
                v0=v0,
                consent_map={"medication_order": "c2"},
            )
        else:
            schedule = _schedule(
                [_tx_medication(v0=v0, value=med_value)],
                v0=v0,
                consent_map={"allergy_list": "c2"},
            )
        return schedule, frozenset({"t-med" if not flip else "t-allergy"})
    if family == "stale_readset":
        # A concurrent unrelated write supersedes the surviving tx's DECLARED
        # read; every declared-fence arm must reject it (justified abort).
        # The unrelated write targets the survivor's declared read, which is
        # the OTHER op's entity (medication_history / allergy_history).
        target = "medication_history" if flip else "allergy_history"
        tx_first: dict[str, object] = {
            "tx_id": "t-unrelated",
            "declared_reads": [target],
            "declared_writes": [target],
            "operation_type": "unknown_op",
            "read_versions": {target: v0},
            "write_values": {target: unrelated_value},
        }
        tx_second = second(v0=v0, value=allergy_value if not flip else med_value)
        schedule = _schedule([tx_first, tx_second], v0=v0)
        return schedule, frozenset({str(tx_second["tx_id"])})
    raise AssertionError(f"unmodelled family in generator: {family}")


def _generated_property_cases(seed: int) -> list[tuple[str, dict[str, object], frozenset[str]]]:
    """Deterministic family-balanced sweep: pure function of ``seed``."""
    rng = random.Random(seed)
    cases: list[tuple[str, dict[str, object], frozenset[str]]] = []
    for index in range(SWEEP_SIZE):
        family = COMPSAC_FAMILIES[index % len(COMPSAC_FAMILIES)]
        flip = rng.randrange(2) == 1
        v0 = rng.choice((1, 2))
        med_value = rng.choice(VALUE_POOL)
        allergy_value = rng.choice(VALUE_POOL)
        unrelated_value = rng.choice(VALUE_POOL)
        schedule, forbidden = _build_property_case(
            family,
            flip=flip,
            v0=v0,
            med_value=med_value,
            allergy_value=allergy_value,
            unrelated_value=unrelated_value,
        )
        cases.append((family, schedule, forbidden))
    return cases


def _b4_forbidden_commit_witnesses(
    cases: list[tuple[str, dict[str, object], frozenset[str]]],
) -> list[str]:
    """Run candidate B4 over the cases; return oracle-forbidden commits.

    The SAFETY INVARIANT: B4 never commits a transaction the independent
    oracle labels forbidden. Every committed tx whose id is in the case's
    by-construction forbidden set is a falsifying witness; an empty return
    upholds the blueprint claim for the whole sweep.
    """
    witnesses: list[str] = []
    for index, (family, schedule, forbidden) in enumerate(cases):
        outcome = _run(B4, schedule)
        bad = _committed(outcome) & set(forbidden)
        witnesses.extend(f"case-{index}/{family}/{tx}" for tx in sorted(bad))
    return witnesses


# ---------------------------------------------------------------------------
# 1. Positive boundaries: documented guarantees hold end to end
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    @pytest.mark.parametrize("arm", ARMS)
    def test_clean_single_tx_admits_on_every_implemented_arm(self, arm: str) -> None:
        schedule = _schedule([_tx_medication(v0=1)])
        outcome = _run(arm, schedule)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True
        assert _committed(outcome) == {"t-med"}
        detail = _detail(outcome)
        assert detail["baseline"] == arm
        assert detail["aborted"] == 0
        assert detail["final_versions"]["medication_order"] == 2

    def test_b4_admits_correctly_declared_concurrent_dependency_chain(self) -> None:
        """A concurrent pair whose REQUIRED edges are declared at their true
        observed versions commits under B4 — dependency completeness must not
        degenerate into an all-deny fence (liveness under contention)."""
        schedule = _schedule(
            [
                _tx_medication(v0=1),
                _tx_allergy(v0=1, declare_required_at=2),
            ]
        )
        outcome = _run(B4, schedule)
        assert outcome.observed_outcome == "ADMIT"
        assert _committed(outcome) == {"t-med", "t-allergy"}
        assert _abort_reasons(outcome) == {}

    def test_b4_scope_local_admits_unrelated_write_that_b0_false_stales(self) -> None:
        """COMPSAC-CASE-01 witness: an unrelated concurrent write outside the
        candidate's fence must not abort it (RQ1 false-stale control), while
        the coarse global-profile arm B0 aborts its second commit."""
        schedule = _schedule([_tx_medication(v0=1), _tx_unrelated(v0=1)])
        b4_outcome = _run(B4, schedule)
        assert _committed(b4_outcome) == {"t-med", "t-unrelated"}
        b0_outcome = _run(B0, schedule)
        assert _committed(b0_outcome) == {"t-med"}
        assert _reason_of(b0_outcome, "t-unrelated") == "GLOBAL_PROFILE_STALE"
        # B0 liveness: a lone transaction on a quiet profile still commits.
        assert _committed(_run(B0, _schedule([_tx_medication(v0=1)]))) == {"t-med"}

    def test_dsl_compiles_clean_operation_to_complete_stable_closure(self) -> None:
        schema = dsl.make_schema(resources=dict(DSL_RESOURCE_KINDS))
        op = dsl.Operation(
            op_id="op-clean",
            writes=("medication",),
            reads=("consent", "allergy"),
            declared_edges=(("allergy", "depends_on_current"),),
        )
        closure = dsl.compile_dependencies(op, schema)
        assert {d.resource for d in closure} == {"medication", "consent", "allergy"}
        by_resource = {d.resource: d for d in closure}
        assert by_resource["medication"].kind is dsl.DependencyKind.ENTITY
        assert by_resource["consent"].kind is dsl.DependencyKind.GOVERNANCE
        assert by_resource["allergy"].predicate == "depends_on_current"
        assert dsl.compile_dependencies(op, schema) == closure
        report = dsl.compile_with_report(op, schema)
        assert report.ok and report.closure_sha256 == dsl.compile_with_report(op, schema).closure_sha256
        dsl.assert_no_wildcard_omission(closure, op)

    def test_oracle_self_checks_and_live_independence_guards_hold(self) -> None:
        results = oracle.run_self_checks()
        assert {r.case_id.removeprefix("selfcheck-"): r.outcome for r in results} == {
            "clean": "ADMIT",
            "omitted_dependency": "REJECT",
            "epoch_race": "REJECT",
            "stale_readset": "REJECT",
        }
        oracle.verify_independence()  # live source: no candidate import
        closure_oracle.assert_oracle_independence()  # live source: DSL-free
        state = closure_oracle.OracleState(consent_epoch=7, policy_epoch=9)
        closure = closure_oracle.expected_dependencies(
            closure_oracle.OracleOperation("op", ("medication",), ("consent", "allergy")), state
        )
        epochs = {d.resource: d.required_version_or_epoch for d in closure}
        assert epochs == {"medication": "current", "consent": 7, "allergy": "current"}


# ---------------------------------------------------------------------------
# 2. Negative boundaries: fail closed with stable reason codes
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    @pytest.mark.parametrize("bad_id", ["", "unknown-arm", "postgresql-ssi-simulated", 42, None])
    def test_unknown_baseline_id_is_never_guessed(self, bad_id: object) -> None:
        outcome = bl.run_baseline(bad_id, _case(_schedule([_tx_medication(v0=1)])), _ctx())  # type: ignore[arg-type]
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert "BASELINE_UNAVAILABLE" in outcome.detail
        assert outcome.counted_as_success is False

    def test_non_mapping_case_fails_closed(self) -> None:
        for bad_case in ("case", 7, ["schedule"]):  # type: ignore[var-annotated]
            outcome = bl.run_baseline(B4, bad_case, _ctx())  # type: ignore[arg-type]
            assert outcome.observed_outcome == "EXECUTION_ERROR"
            assert outcome.detail == bl.REASON_CASE_MALFORMED
            assert outcome.counted_as_success is False

    @pytest.mark.parametrize("arm", ARMS)
    @pytest.mark.parametrize(
        "broken_schedule",
        [
            {"transactions": [{"tx_id": "t", "declared_reads": [], "declared_writes": []}]},
            {"store": {"medication_order": {"version": 1, "value": "x"}}, "transactions": []},
            {
                "store": {"medication_order": {"version": 1, "value": "x"}},
                "transactions": [
                    {
                        "tx_id": "t",
                        "declared_reads": ["medication_order"],
                        "declared_writes": [],
                        "read_versions": {"medication_order": True},
                    }
                ],
            },
        ],
    )
    def test_malformed_schedule_fails_closed_identically_on_every_arm(
        self, arm: str, broken_schedule: dict[str, object]
    ) -> None:
        outcome = _run(arm, broken_schedule)
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.detail.startswith(bl.REASON_SCHEDULE_MALFORMED)
        assert outcome.counted_as_success is False

    @pytest.mark.parametrize("arm", [B1, B3, B4])
    def test_read_of_unknown_entity_fails_closed_per_tx_not_silently(self, arm: str) -> None:
        schedule = _schedule([_tx_medication(v0=1)])
        tx = dict(schedule["transactions"][0])  # type: ignore[index]
        tx["declared_reads"] = ["ghost_entity", "medication_history"]  # type: ignore[index]
        schedule["transactions"] = [tx]
        outcome = _run(arm, schedule)
        assert outcome.observed_outcome == "REJECT"  # determined protocol outcome
        assert _reason_of(outcome, "t-med") == "ENTITY_UNKNOWN"
        assert _committed(outcome) == set()


# ---------------------------------------------------------------------------
# 3. Unknown boundaries: INDETERMINATE is first-class
# ---------------------------------------------------------------------------


class TestUnknownBoundaries:
    def test_oracle_unknown_and_undeclared_families_stay_indeterminate(self) -> None:
        unmodelled = oracle.adjudicate({"case_id": "c-unknown", "family": "unmodelled_family"})
        assert unmodelled.outcome == "INDETERMINATE"
        assert unmodelled.reason_code == "UNMODELLED_FAMILY"
        no_family = oracle.adjudicate({"case_id": "c-nofamily"})
        assert no_family.outcome == "INDETERMINATE"
        assert no_family.reason_code == "NO_FAMILY_DECLARED"
        for result in (unmodelled, no_family):
            assert result.outcome not in ("ADMIT", "REJECT")

    def test_oracle_missing_case_id_raises_stable_kernel_error(self) -> None:
        with pytest.raises(oracle_kernel.OracleError) as excinfo:
            oracle.adjudicate({"family": "clean"})
        assert excinfo.value.reason_code == "MISSING_CASE_ID"

    def test_closure_oracle_refuses_unruled_ambiguous_and_malformed_state(self) -> None:
        state = closure_oracle.OracleState(consent_epoch=1, policy_epoch=1)
        with pytest.raises(closure_oracle.OracleError) as unruled:
            closure_oracle.expected_dependencies(
                closure_oracle.OracleOperation("op", ("ghost_resource",), ()), state
            )
        assert unruled.value.reason_code == "UNRULED_RESOURCE"
        with pytest.raises(closure_oracle.OracleError) as ambiguous:
            closure_oracle.expected_dependencies(
                closure_oracle.OracleOperation("op", ("medication_note",), ()), state
            )
        assert ambiguous.value.reason_code == "AMBIGUOUS_RULE_REVIEW"
        with pytest.raises(closure_oracle.OracleError) as bad_state:
            closure_oracle.expected_dependencies(
                closure_oracle.OracleOperation("op", ("medication",), ()), object()  # type: ignore[arg-type]
            )
        assert bad_state.value.reason_code == "STATE_MISMATCH"

    def test_dsl_refuses_unknown_resources_predicates_and_versions(self) -> None:
        schema = dsl.make_schema(resources=dict(DSL_RESOURCE_KINDS))
        with pytest.raises(dsl.DependencyCompileError) as unknown_resource:
            dsl.compile_dependencies(
                dsl.Operation("op", ("medication",), ("ghost",), ()), schema
            )
        assert unknown_resource.value.reason_code == dsl.REASON_UNKNOWN_MUTATION_TARGET
        with pytest.raises(dsl.DependencyCompileError) as unknown_predicate:
            dsl.compile_dependencies(
                dsl.Operation("op", ("medication",), ("allergy",), (("allergy", "made_up"),)),
                schema,
            )
        assert unknown_predicate.value.reason_code == dsl.REASON_UNKNOWN_PREDICATE
        with pytest.raises(dsl.DependencyCompileError) as version_mismatch:
            dsl.compile_dependencies(
                dsl.Operation("op", ("medication",), (), ()),
                dsl.make_schema(version="other-v9", resources=dict(DSL_RESOURCE_KINDS)),
            )
        assert version_mismatch.value.reason_code == dsl.REASON_SCHEMA_VERSION_MISMATCH
        with pytest.raises(dsl.DependencyCompileError) as empty_op:
            dsl.compile_dependencies(dsl.Operation("op", (), (), ()), schema)
        assert empty_op.value.reason_code == dsl.REASON_EMPTY_OPERATION
        with pytest.raises(dsl.DependencyCompileError) as dangling_edge:
            dsl.compile_dependencies(
                dsl.Operation("op", ("medication",), (), (("allergy", "depends_on_current"),)),
                schema,
            )
        assert dangling_edge.value.reason_code == dsl.REASON_UNKNOWN_MUTATION_TARGET


# ---------------------------------------------------------------------------
# 4. Write-skew and policy-epoch race scenarios (RQ2 witnesses)
# ---------------------------------------------------------------------------


class TestWriteSkewAndEpochRaces:
    @pytest.mark.parametrize("flip", [False, True])
    def test_canonical_write_skew_b4_rejects_second_commit_while_b1_b3_admit_both(
        self, flip: bool
    ) -> None:
        first = _tx_medication(v0=1) if not flip else _tx_allergy(v0=1)
        second = _tx_allergy(v0=1) if not flip else _tx_medication(v0=1)
        schedule = _schedule([first, second])
        b4_outcome = _run(B4, schedule)
        assert _committed(b4_outcome) == {str(first["tx_id"])}
        assert _reason_of(b4_outcome, str(second["tx_id"])) in (
            "REQUIRED_READ_EDGE_STALE",
            "WRITE_EDGE_SUPERSEDED",
        )
        for declared_fence_arm in (B1, B3):
            outcome = _run(declared_fence_arm, schedule)
            assert _committed(outcome) == {str(first["tx_id"]), str(second["tx_id"])}
            assert _abort_reasons(outcome) == {}

    def test_consent_epoch_race_b4_rejects_stale_binding_declared_fence_arms_commit(self) -> None:
        """The omitted governance binding (allergy_list) moves to c2; the
        write still declares c1. B4 validates the derived closure edge and
        refuses; B1/B3 never check the omitted entity's epoch — the exact
        RQ2 policy-race gap their declared fence cannot see."""
        schedule = _schedule(
            [_tx_medication(v0=1, consent="c1")],
            consent_map={"allergy_list": "c2"},
        )
        b4_outcome = _run(B4, schedule)
        assert _reason_of(b4_outcome, "t-med") == "CONSENT_EPOCH_STALE"
        assert _committed(b4_outcome) == set()
        for declared_fence_arm in (B0, B1, B3):
            assert _committed(_run(declared_fence_arm, schedule)) == {"t-med"}

    def test_policy_epoch_race_b4_rejects_stale_binding(self) -> None:
        schedule = _schedule(
            [_tx_allergy(v0=1, policy="p1")],
            policy_map={"medication_order": "p2"},
        )
        b4_outcome = _run(B4, schedule)
        assert _reason_of(b4_outcome, "t-allergy") == "POLICY_EPOCH_STALE"
        assert _committed(b4_outcome) == set()
        assert _committed(_run(B1, schedule)) == {"t-allergy"}

    def test_write_at_current_epoch_admits_under_b4(self) -> None:
        """Liveness under the new epoch: a transaction declaring the CURRENT
        consent epoch commits — the epoch fence is not an all-deny."""
        schedule = _schedule(
            [_tx_medication(v0=1, consent="c2")],
            consent_map={"allergy_list": "c2"},
        )
        outcome = _run(B4, schedule)
        assert _committed(outcome) == {"t-med"}
        assert _abort_reasons(outcome) == {}

    @pytest.mark.parametrize("arm", [B0, B1, B3, B4])
    def test_stale_declared_readset_is_justified_abort_on_every_arm(self, arm: str) -> None:
        schedule = _schedule(
            [
                {
                    "tx_id": "t-unrelated",
                    "declared_reads": ["allergy_history"],
                    "declared_writes": ["allergy_history"],
                    "operation_type": "unknown_op",
                    "read_versions": {"allergy_history": 1},
                    "write_values": {"allergy_history": "revised-history"},
                },
                _tx_allergy(v0=1),
            ]
        )
        outcome = _run(arm, schedule)
        assert _committed(outcome) == {"t-unrelated"}
        expected_reason = {
            B0: "GLOBAL_PROFILE_STALE",
            B1: "READSET_VERSION_STALE",
            B3: "READSET_VERSION_STALE",
            B4: "REQUIRED_READ_EDGE_STALE",
        }[arm]
        assert _reason_of(outcome, "t-allergy") == expected_reason


# ---------------------------------------------------------------------------
# 5. Two-step metamorphic relations
# ---------------------------------------------------------------------------

#: Step-2 closure schema for the MR: adding a REQUIRED dependency edge for
#: each synthetic op type, pointing at the OTHER transaction's write target.
ADDED_REQUIRED_EDGES: dict[str, dict[str, tuple[str, ...]]] = {
    "order_write": {"required_reads": ("allergy_list",), "required_writes": ()},
    "list_write": {"required_reads": ("medication_order",), "required_writes": ()},
}


def _mr_pair_schedule(*, flip: bool, v0: int, med_value: str, allergy_value: str) -> dict[str, object]:
    """Two synthetic ops whose only conflict is the (base-omitted) edge."""
    first: dict[str, object] = {
        "tx_id": "t-order",
        "declared_reads": ["medication_history"],
        "declared_writes": ["medication_order"],
        "operation_type": "order_write",
        "read_versions": {"medication_history": v0},
        "write_values": {"medication_order": med_value},
    }
    second: dict[str, object] = {
        "tx_id": "t-list",
        "declared_reads": ["allergy_history"],
        "declared_writes": ["allergy_list"],
        "operation_type": "list_write",
        "read_versions": {"allergy_history": v0},
        "write_values": {"allergy_list": allergy_value},
    }
    pair = [second, first] if flip else [first, second]
    return _schedule(pair, v0=v0)


class TestMetamorphicRelations:
    def test_mr1_adding_required_dependency_edge_only_reduces_commits(self) -> None:
        """Two-step metamorphic relation (manifest): step 1 runs the base
        schedule; step 2 adds a required dependency edge to the frozen
        schema. The commit set can only shrink and the forbidden-commit
        count on the oracle-REJECT-labeled schedule can never increase."""
        schedule = _mr_pair_schedule(flip=False, v0=1, med_value="m", allergy_value="a")
        base_outcome = _run(B4, schedule)
        base_commits = _committed(base_outcome)
        assert base_commits == {"t-order", "t-list"}
        with unittest.mock.patch.object(bl, "REQUIRED_DEPENDENCIES", ADDED_REQUIRED_EDGES):
            derived_outcome = _run(B4, schedule)
        derived_commits = _committed(derived_outcome)
        assert derived_commits <= base_commits, "edge addition admitted a new commit"
        assert derived_commits == {"t-order"}
        assert _reason_of(derived_outcome, "t-list") == "REQUIRED_READ_EDGE_STALE"
        # Forbidden commits (oracle labels this family REJECT) non-increasing.
        assert _oracle_label("omitted_dependency") == "REJECT"
        forbidden = {"t-list"}
        assert len(derived_commits & forbidden) <= len(base_commits & forbidden)

    @pytest.mark.parametrize("v0", [1, 2])
    def test_mr1_edge_addition_monotone_across_seeded_orders(self, v0: int) -> None:
        rng = random.Random(FIXED_SEED + v0)
        for index in range(8):
            flip = rng.randrange(2) == 1
            med_value = rng.choice(VALUE_POOL)
            allergy_value = rng.choice(VALUE_POOL)
            schedule = _mr_pair_schedule(
                flip=flip, v0=v0, med_value=med_value, allergy_value=allergy_value
            )
            base_commits = _committed(_run(B4, schedule))
            with unittest.mock.patch.object(bl, "REQUIRED_DEPENDENCIES", ADDED_REQUIRED_EDGES):
                derived_commits = _committed(_run(B4, schedule))
            assert derived_commits <= base_commits, f"case {index}: commit set grew"
            assert len(derived_commits) <= 1 and len(base_commits) == 2
            survivor = "t-list" if flip else "t-order"
            assert derived_commits == {survivor}

    def test_mr2_declaring_the_omitted_edge_reduces_declared_fence_forbidden_commits(self) -> None:
        """Step 1: B1 admits both skew commits (the omitted edge is outside
        its fence). Step 2: the same workload DECLARES the omitted edge at
        its observed version — the skew becomes a detected stale readset and
        the forbidden commit disappears; B4 stays at zero throughout."""
        skew = _schedule([_tx_medication(v0=1), _tx_allergy(v0=1)])
        declared = _schedule(
            [
                _tx_medication(v0=1, declare_required_at=1),
                _tx_allergy(v0=1, declare_required_at=1),
            ]
        )
        forbidden = {"t-allergy"}
        b1_skew = _committed(_run(B1, skew))
        b1_declared = _committed(_run(B1, declared))
        assert b1_skew == {"t-med", "t-allergy"}
        assert b1_declared <= b1_skew
        assert _reason_of(_run(B1, declared), "t-allergy") == "READSET_VERSION_STALE"
        assert len(b1_declared & forbidden) < len(b1_skew & forbidden)
        b4_forbidden_before = _committed(_run(B4, skew)) & forbidden
        b4_forbidden_after = _committed(_run(B4, declared)) & forbidden
        assert b4_forbidden_before == set() and b4_forbidden_after == set()

    def test_mr3_dsl_closure_monotone_under_added_required_reads(self) -> None:
        """Compile-level MR: adding a required read resource strictly grows
        the closure (superset), and adding a declared edge only refines the
        predicate without changing coverage — no resource is ever dropped."""
        schema = dsl.make_schema(resources=dict(DSL_RESOURCE_KINDS))
        base_op = dsl.Operation("op", ("medication",), ("consent", "allergy"), ())
        base_closure = dsl.compile_dependencies(base_op, schema)
        extended_op = dsl.Operation(
            "op", ("medication",), ("consent", "allergy", "history", "write_lease"), ()
        )
        extended_closure = dsl.compile_dependencies(extended_op, schema)
        assert base_closure <= extended_closure
        assert {d.resource for d in extended_closure} - {d.resource for d in base_closure} == {
            "history",
            "write_lease",
        }
        refined_op = dsl.Operation(
            "op", ("medication",), ("consent", "allergy"), (("medication", "backed_by"),)
        )
        refined_closure = dsl.compile_dependencies(refined_op, schema)
        assert {d.resource for d in refined_closure} == {d.resource for d in base_closure}
        assert {d.resource for d in refined_closure if d.predicate == "backed_by"} == {"medication"}
        dsl.assert_no_wildcard_omission(refined_closure, refined_op)

    def test_mr4_adding_epoch_binding_only_reduces_b4_commits(self) -> None:
        """Governance-dimension MR: adding a consent-epoch binding to the
        schedule can only shrink the commit set; a tx declaring the current
        epoch under the added binding still commits (liveness)."""
        base_schedule = _schedule([_tx_medication(v0=1)])
        assert _committed(_run(B4, base_schedule)) == {"t-med"}
        strengthened = _schedule(
            [_tx_medication(v0=1)], consent_map={"allergy_list": "c2"}
        )
        assert _committed(_run(B4, strengthened)) == set()
        assert _reason_of(_run(B4, strengthened), "t-med") == "CONSENT_EPOCH_STALE"
        current_epoch = _schedule([_tx_medication(v0=1, consent="c2")], consent_map={"allergy_list": "c2"})
        assert _committed(_run(B4, current_epoch)) == {"t-med"}


# ---------------------------------------------------------------------------
# 6. Mutation checks (mutation-adequacy for the pass gate)
# ---------------------------------------------------------------------------


class TestMutationChecks:
    def test_mutation_closure_drop_on_b4_is_killed_by_safety_invariant(self) -> None:
        """Mutant: the dependency-closure derivation is disabled (declared
        sets only). B4 then admits the canonical forbidden write skew, which
        the invariant detects — the suite is sensitive to the mechanism axis
        under study."""
        schedule, forbidden = _build_property_case(
            "omitted_dependency",
            flip=False,
            v0=1,
            med_value="m",
            allergy_value="a",
            unrelated_value="u",
        )
        declared_only = lambda tx: (  # noqa: E731 - explicit mutant, restored by context manager
            frozenset(tx.get("declared_reads", ())),
            frozenset(tx.get("declared_writes", ())),
        )
        with unittest.mock.patch.object(bl, "_dependency_closure", declared_only):
            outcome = _run(B4, schedule)
        bad = _committed(outcome) & set(forbidden)
        assert bad == {"t-allergy"}, "closure-drop mutant survived the safety invariant"

    def test_mutation_epoch_check_drop_on_b4_is_killed_by_safety_invariant(self) -> None:
        """Mutant: every consent/policy epoch check is removed. B4 then
        commits the stale-epoch race write — detected by the invariant."""
        schedule, forbidden = _build_property_case(
            "epoch_race",
            flip=False,
            v0=1,
            med_value="m",
            allergy_value="a",
            unrelated_value="u",
        )
        with unittest.mock.patch.object(bl, "_tx_epoch_ok", lambda *a, **k: (True, "OK")):
            outcome = _run(B4, schedule)
        bad = _committed(outcome) & set(forbidden)
        assert bad == {"t-med"}, "epoch-check-drop mutant survived the safety invariant"

    def test_mutation_all_deny_b4_is_killed_by_liveness_control(self) -> None:
        """An arbitrary all-deny must never pass correctness: the clean
        positive control requires B4 to commit, so an all-deny mutant is
        caught even though it trivially satisfies the safety invariant."""
        clean_schedule = _schedule([_tx_medication(v0=1)])
        with unittest.mock.patch.object(
            bl, "_tx_epoch_ok", lambda *a, **k: (False, "POLICY_EPOCH_STALE")
        ):
            outcome = _run(B4, clean_schedule)
        assert _committed(outcome) == set(), "all-deny mutant passed the liveness control"

    def test_mutation_oracle_rule_flip_is_killed_by_frozen_self_checks(self) -> None:
        with unittest.mock.patch.dict(oracle.CASE_OUTCOME_RULES, {"clean": "REJECT"}):
            with pytest.raises(oracle_kernel.OracleError) as excinfo:
                oracle.run_self_checks()
        assert excinfo.value.reason_code == "SELF_CHECK_MISMATCH"
        # Context exit restored the frozen table: the rule table is intact.
        assert oracle.CASE_OUTCOME_RULES["clean"] == "ADMIT"
        assert [r.outcome for r in oracle.run_self_checks()] == [
            "ADMIT",
            "REJECT",
            "REJECT",
            "REJECT",
        ]

    def test_mutation_oracle_candidate_import_is_killed_by_independence_guard(self) -> None:
        poisoned_forbidden_commit = (
            "from evaluation.venue2027.compsac import baselines\n"
        )
        with pytest.raises(oracle_kernel.OracleError) as forbidden_commit_import:
            oracle.verify_independence(source=poisoned_forbidden_commit)
        assert forbidden_commit_import.value.reason_code == oracle.REASON_CANDIDATE_IMPORT
        poisoned_closure = "from evaluation.venue2027.compsac import dependency_dsl\n"
        with pytest.raises(closure_oracle.OracleError) as closure_import:
            closure_oracle.assert_oracle_independence(source=poisoned_closure)
        assert closure_import.value.reason_code == closure_oracle.REASON_CANDIDATE_IMPORT
        with pytest.raises(closure_oracle.OracleError) as dynamic_import:
            closure_oracle.assert_oracle_independence(source="x = __import__('os')\n")
        assert "__dynamic__" in dynamic_import.value.detail


# ---------------------------------------------------------------------------
# 7. Seeded safety invariant sweep (the falsification rule, mechanically run)
# ---------------------------------------------------------------------------


class TestSeededSafetyInvariant:
    def test_b4_never_commits_oracle_forbidden_transactions_over_seeded_sweep(self) -> None:
        """SAFETY INVARIANT: over the whole seeded, family-balanced sweep,
        B4 never commits a transaction the independent oracle labels
        forbidden; clean families stay live (never all-deny); skew/race
        aborts carry the documented mechanism reason codes."""
        cases = _generated_property_cases(FIXED_SEED)
        assert len(cases) == SWEEP_SIZE
        witnesses = _b4_forbidden_commit_witnesses(cases)
        assert witnesses == [], f"B4 committed oracle-forbidden writes: {witnesses}"
        for index, (family, schedule, forbidden) in enumerate(cases):
            label = _oracle_label(family)
            # Construction <-> oracle consistency: a schedule with a
            # by-construction forbidden tx must be oracle-REJECT-labeled,
            # and an ADMIT-labeled family never carries one.
            assert (label == "REJECT") == bool(forbidden), f"case {index}/{family}"
            outcome = _run(B4, schedule)
            assert outcome.observed_outcome in ("ADMIT", "REJECT")
            if not forbidden:
                assert _committed(outcome), f"case {index}/{family}: liveness violated"
            else:
                assert _committed(outcome) & forbidden == set()
                reasons = set(_abort_reasons(outcome).values())
                expected_codes = {
                    "omitted_dependency": {"REQUIRED_READ_EDGE_STALE", "WRITE_EDGE_SUPERSEDED"},
                    "epoch_race": {"CONSENT_EPOCH_STALE"},
                    "stale_readset": {"REQUIRED_READ_EDGE_STALE"},
                }[family]
                assert reasons & expected_codes, f"case {index}/{family}: {reasons}"

    def test_seeded_sweep_is_replay_identical(self) -> None:
        """Determinism: the seeded generator and the arms are pure; two full
        passes produce byte-identical transcripts."""
        def transcript(seed: int) -> list[tuple[object, ...]]:
            rows: list[tuple[object, ...]] = []
            for family, schedule, forbidden in _generated_property_cases(seed):
                outcome = _run(B4, schedule)
                rows.append(
                    (
                        family,
                        tuple(sorted(forbidden)),
                        outcome.observed_outcome,
                        outcome.detail,
                    )
                )
            return rows

        assert transcript(FIXED_SEED) == transcript(FIXED_SEED)
        assert _generated_property_cases(FIXED_SEED) == _generated_property_cases(FIXED_SEED)
        # A different seed yields a different schedule stream (the sweep is
        # genuinely parameterized, not a fixed fixture replay).
        assert _generated_property_cases(FIXED_SEED) != _generated_property_cases(FIXED_SEED + 1)

    def test_seeded_dsl_closures_complete_wildcard_free_and_stable(self) -> None:
        rng = random.Random(FIXED_SEED + 7)
        schema = dsl.make_schema(resources=dict(DSL_RESOURCE_KINDS))
        universe = sorted(DSL_RESOURCE_KINDS)
        for index in range(DSL_SWEEP_OPS):
            n_writes = rng.randint(1, 3)
            writes = rng.sample(universe, n_writes)
            read_pool = [r for r in universe if r not in writes]
            reads = rng.sample(read_pool, rng.randint(1, min(3, len(read_pool))))
            op = dsl.Operation(
                op_id=f"seeded-op-{index}",
                writes=tuple(writes),
                reads=tuple(reads),
                declared_edges=(
                    (rng.choice(sorted(set(writes) | set(reads))), "depends_on_current"),
                )
                if rng.randrange(2)
                else (),
            )
            closure = dsl.compile_dependencies(op, schema)
            touched = set(op.writes) | set(op.reads)
            assert {d.resource for d in closure} == touched
            assert all(d.kind is DSL_RESOURCE_KINDS[d.resource] for d in closure)
            dsl.assert_no_wildcard_omission(closure, op)
            assert dsl.compile_dependencies(op, schema) == closure
            report = dsl.compile_with_report(op, schema)
            assert report.ok
            assert report.closure_sha256 == dsl.compile_with_report(op, schema).closure_sha256
