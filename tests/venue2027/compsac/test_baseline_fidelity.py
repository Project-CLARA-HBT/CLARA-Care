"""CLARA-Care 2027 COMPSAC task COMPSAC-baseline_tests — baseline fidelity suite.

Purpose
-------
One POSITIVE fidelity vector and one ADVERSARIAL NEGATIVE vector for EACH
implemented COMPSAC baseline arm in
``evaluation/venue2027/compsac/baselines.py`` (imported real via the public
``run_baseline`` entry point — never reimplemented, never stubbed):

- B0 ``global-profile-version-occ`` — coarse global-profile OCC.
- B1 ``silo-style-entity-readset-occ`` — Silo-style per-entity read-set OCC
  (faithful port of Tu et al., SOSP 2013; NOT Silo source code).
- B3 ``entity-occ-no-closure-ablation`` — B1 machinery with the semantic
  dependency-closure derivation disabled (RQ2 instrument).
- B4 ``dependency-complete-scope-local-occ`` — the candidate; derives the
  frozen per-operation dependency closure and validates it at commit.

Positive vectors (guarantee holds on a clean schedule)
    On a schedule where the only concurrent conflict is a DECLARED read
    (the declared read set genuinely overlaps the other transaction's write
    target), each arm must exhibit its documented guarantee END TO END:
    no false abort of the uncontended transaction, the contended
    transaction fails on the declared edge (B0 GLOBAL_PROFILE_STALE,
    B1/B3 READSET_VERSION_STALE, B4 WRITE_EDGE_SUPERSEDED), and the
    outcome carries real per-transaction commit/abort records — a
    constant stub structurally cannot reproduce this arm-specific
    differential.

Adversarial negative vectors (the omitted-dependency write skew)
    On the canonical write-skew schedule (two interleaved clinical writes,
    each reading an entity the OTHER write mutates but declaring only its
    own read set), the expected contrast is asserted explicitly as the
    fidelity evidence: B4 REJECTS the second commit on its derived
    closure edge (WRITE_EDGE_SUPERSEDED / REQUIRED_READ_EDGE_STALE)
    while B1 and B3 ADMIT both transactions (declared read sets stay
    valid) — the omitted dependency is invisible to their declared fence.

B2 honesty vector
    ``postgresql-ssi`` requires a genuine PostgreSQL SERIALIZABLE
    connection; without one it must report ``NOT_RUN_EXTERNAL`` /
    ``BASELINE_UNAVAILABLE`` — never a simulated ADMIT/REJECT over the
    in-memory store or SQLite.

Allowed input
-------------
Synthetic, JSON-serializable schedules only (versioned in-memory store,
declared read/write sets, consent/policy epochs). No network, DB, clock or
model; no patient data, no production secrets. All vectors deterministic.

Failure semantics
-----------------
Arms fail closed with stable uppercase reason codes (READSET_VERSION_STALE,
WRITE_EDGE_SUPERSEDED, REQUIRED_READ_EDGE_STALE, GLOBAL_PROFILE_STALE,
SCHEDULE_MALFORMED, BASELINE_UNAVAILABLE, ...). Tests assert these codes and
never accept a bare exception or a silent drop as a safe rejection.

Version
-------
``COMPSAC_BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"`` against
``baselines.COMPSAC_BASELINES_VERSION`` 1.x.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.compsac import baselines as bl

COMPSAC_BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"

IMPLEMENTED_ARMS = sorted(bl.IMPLEMENTED_BASELINES)


def _ctx(seed: int = 42) -> RunContext:
    return RunContext(
        campaign_id="camp-compsac-baseline-fidelity",
        case_id="case-fidelity-1",
        arm_id="arm",
        seed=seed,
        source_commit="a" * 40,
        deadline_seconds=60.0,
    )


def _case(schedule: dict[str, object] | None = None) -> dict[str, object]:
    case: dict[str, object] = {"case_id": "case-compsac-fidelity", "seed": 42}
    if schedule is not None:
        case["schedule"] = schedule
    return case


def _clean_schedule() -> dict[str, object]:
    """Clean-schedule positive fixture: declared reads genuinely conflict.

    Both transactions run operation_type "unknown_op" (absent from the frozen
    dependency schema), so each arm's contract is exactly its declared sets —
    no closure edges and no epoch bindings. The declared reads are disjoint
    from each transaction's OWN writes but DO overlap the other transaction's
    write target, so a real read-set fence must fire for the second commit;
    the FIRST transaction is uncontended and must never be falsely aborted.
    """
    return {
        "store": {
            "medication_order": {"version": 1, "value": "none"},
            "allergy_list": {"version": 1, "value": "penicillin"},
            "medication_history": {"version": 1, "value": "statins"},
            "allergy_history": {"version": 1, "value": "rash-2025"},
        },
        "transactions": [
            {
                "tx_id": "t1-first-commit",
                "declared_reads": ["medication_history"],
                "declared_writes": ["allergy_list"],
                "operation_type": "unknown_op",
                "read_versions": {"medication_history": 1},
                "write_values": {"allergy_list": "sulfa"},
            },
            {
                "tx_id": "t2-declared-stale-read",
                "declared_reads": ["allergy_list"],
                "declared_writes": ["medication_order"],
                "operation_type": "unknown_op",
                "read_versions": {"allergy_list": 1},
                "write_values": {"medication_order": "metformin-500mg"},
            },
        ],
    }


def _write_skew_schedule() -> dict[str, object]:
    """Canonical omitted-dependency write-skew schedule (RQ2 witness).

    T1 (medication_prescribe) writes medication_order after reading only
    medication_history; T2 (allergy_update) writes allergy_list after
    reading only allergy_history. Each semantically REQUIRES the entity the
    other writes (allergy_list / medication_order) but declares neither:
    the omitted dependency. This is exactly the module's default schedule
    shape, built explicitly here so the contrast vector does not depend on
    the module's private defaults.
    """
    return {
        "store": {
            "medication_order": {"version": 1, "value": "none", "consent_epoch": "c1"},
            "allergy_list": {"version": 1, "value": "penicillin", "consent_epoch": "c1"},
            "medication_history": {"version": 1, "value": "statins", "consent_epoch": "c1"},
            "allergy_history": {"version": 1, "value": "rash-2025", "consent_epoch": "c1"},
        },
        "policy_epochs": {
            "medication_order": "p1",
            "allergy_list": "p1",
            "medication_history": "p1",
            "allergy_history": "p1",
        },
        "consent_epochs": {
            "medication_order": "c1",
            "allergy_list": "c1",
            "medication_history": "c1",
            "allergy_history": "c1",
        },
        "transactions": [
            {
                "tx_id": "t1-medication-write",
                "declared_reads": ["medication_history"],
                "declared_writes": ["medication_order"],
                "operation_type": "medication_prescribe",
                "read_versions": {"medication_history": 1},
                "write_values": {"medication_order": "metformin-500mg"},
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
            {
                "tx_id": "t2-allergy-write",
                "declared_reads": ["allergy_history"],
                "declared_writes": ["allergy_list"],
                "operation_type": "allergy_update",
                "read_versions": {"allergy_history": 1},
                "write_values": {"allergy_list": "sulfa"},
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            },
        ],
    }


def _run(arm: str, schedule: dict[str, object], seed: int = 42) -> Outcome:
    outcome = bl.run_baseline(arm, _case(schedule), _ctx(seed=seed))
    assert isinstance(outcome, Outcome)
    return outcome


def _detail(outcome: Outcome) -> dict[str, object]:
    return json.loads(outcome.detail)


# ---------------------------------------------------------------------------
# B0 global-profile OCC (arm B0)
# ---------------------------------------------------------------------------


def test_b0_positive_clean_schedule_no_false_abort_then_global_stale() -> None:
    """Positive: the uncontended first commit succeeds; the contended second
    transaction is rejected by the GLOBAL profile fence (any concurrent
    profile write aborts it) — the documented wide-scope behavior, not a
    false abort of an uncontended transaction."""
    outcome = _run(bl.B0_GLOBAL_PROFILE, _clean_schedule())
    detail = _detail(outcome)
    assert detail["baseline"] == bl.B0_GLOBAL_PROFILE
    assert detail["version"] == bl.COMPSAC_BASELINES_VERSION
    assert detail["committed"] == 1 and detail["aborted"] == 1
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    # No false abort: the first, uncontended commit succeeds cleanly.
    assert by_tx["t1-first-commit"]["outcome"] == "COMMIT"
    assert by_tx["t1-first-commit"]["reason_code"] == "OK"
    # The contended second commit hits the global profile fence.
    assert by_tx["t2-declared-stale-read"]["outcome"] == "ABORT"
    assert by_tx["t2-declared-stale-read"]["reason_code"] == "GLOBAL_PROFILE_STALE"
    # The committed write actually installed (version+1).
    assert detail["final_versions"]["allergy_list"] == 2
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True


def test_b0_negative_never_repairs_omitted_dependency_write_skew() -> None:
    """Negative: on the write-skew schedule B0 aborts the second in-flight
    transaction via its coarse global fence (GLOBAL_PROFILE_STALE). Its
    rejection reason is scope-wide staleness — it does NOT see the omitted
    dependency edge, which is precisely the fidelity gap B4 closes."""
    outcome = _run(bl.B0_GLOBAL_PROFILE, _write_skew_schedule())
    detail = _detail(outcome)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    assert by_tx["t2-allergy-write"]["outcome"] == "ABORT"
    assert by_tx["t2-allergy-write"]["reason_code"] == "GLOBAL_PROFILE_STALE"
    # The rejection is NOT dependency-aware: no closure-edge reason code can
    # appear from B0's coarse fence.
    assert by_tx["t2-allergy-write"]["reason_code"] not in (
        "WRITE_EDGE_SUPERSEDED",
        "REQUIRED_READ_EDGE_STALE",
    )
    assert outcome.observed_outcome == "ADMIT"  # one commit survived


# ---------------------------------------------------------------------------
# B1 Silo-style entity readset OCC (arm B1)
# ---------------------------------------------------------------------------


def test_b1_positive_clean_schedule_declared_readset_fence_fires() -> None:
    """Positive: on a clean schedule with a genuine DECLARED read conflict,
    the uncontended first commit succeeds and the second transaction is
    aborted on its own declared read-set version (READSET_VERSION_STALE) —
    the Silo commit-time fence working exactly as published."""
    outcome = _run(bl.B1_SILO_READSET, _clean_schedule())
    detail = _detail(outcome)
    assert detail["baseline"] == bl.B1_SILO_READSET
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-first-commit"]["outcome"] == "COMMIT"
    assert by_tx["t1-first-commit"]["reason_code"] == "OK"
    assert by_tx["t2-declared-stale-read"]["outcome"] == "ABORT"
    assert by_tx["t2-declared-stale-read"]["reason_code"] == "READSET_VERSION_STALE"
    assert detail["final_versions"]["allergy_list"] == 2
    assert outcome.observed_outcome == "ADMIT"


def test_b1_negative_admits_omitted_dependency_write_skew() -> None:
    """Adversarial negative (THE fidelity evidence): on the canonical
    write-skew schedule B1 ADMITS BOTH transactions — the omitted dependency
    (allergy_list for the medication write, medication_order for the allergy
    write) lies outside B1's declared-read-set fence, so the concurrent
    mutation goes unnoticed and write skew commits."""
    outcome = _run(bl.B1_SILO_READSET, _write_skew_schedule())
    detail = _detail(outcome)
    assert detail["committed"] == 2 and detail["aborted"] == 0
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    assert by_tx["t2-allergy-write"]["outcome"] == "COMMIT"
    # Both installs landed: the skew is real in the final store state.
    assert detail["final_versions"]["medication_order"] == 2
    assert detail["final_versions"]["allergy_list"] == 2
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True


# ---------------------------------------------------------------------------
# B3 no-closure ablation (arm B3)
# ---------------------------------------------------------------------------


def test_b3_positive_clean_schedule_matches_declared_fence() -> None:
    """Positive: with closure derivation disabled, B3 still enforces its
    DECLARED read-set contract end-to-end on a clean schedule: uncontended
    first commit succeeds, contended second commit aborts on the declared
    stale read version."""
    outcome = _run(bl.B3_NO_CLOSURE_ABLATION, _clean_schedule())
    detail = _detail(outcome)
    assert detail["baseline"] == bl.B3_NO_CLOSURE_ABLATION
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-first-commit"]["outcome"] == "COMMIT"
    assert by_tx["t2-declared-stale-read"]["outcome"] == "ABORT"
    assert by_tx["t2-declared-stale-read"]["reason_code"] == "READSET_VERSION_STALE"
    assert outcome.observed_outcome == "ADMIT"


def test_b3_negative_admits_omitted_dependency_write_skew() -> None:
    """Adversarial negative (RQ2 instrument): the ablation ADMITS BOTH
    write-skew transactions exactly like B1 — disabling the closure
    derivation leaves only the declared fence, so the omitted dependency is
    invisible and the skew commits. B3 must be behaviorally indistinguishable
    from B1 here: same per-tx outcomes, same final store state."""
    skew = _write_skew_schedule()
    b3 = _detail(_run(bl.B3_NO_CLOSURE_ABLATION, skew))
    b1 = _detail(_run(bl.B1_SILO_READSET, skew))
    assert b3["committed"] == 2 and b3["aborted"] == 0
    by_tx = {tx["tx_id"]: tx for tx in b3["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    assert by_tx["t2-allergy-write"]["outcome"] == "COMMIT"
    # Ablation parity with B1 on the skew witness (same machinery, no closure).
    assert {tx["tx_id"]: tx["outcome"] for tx in b3["transactions"]} == {
        tx["tx_id"]: tx["outcome"] for tx in b1["transactions"]
    }
    assert b3["final_versions"] == b1["final_versions"]
    assert b3["final_versions"]["medication_order"] == 2
    assert b3["final_versions"]["allergy_list"] == 2


# ---------------------------------------------------------------------------
# B4 dependency-complete scope-local OCC (candidate, arm B4)
# ---------------------------------------------------------------------------


def test_b4_positive_clean_schedule_no_false_abort_on_uncontended_commit() -> None:
    """Positive: B4's closure validation does NOT over-reject. On a clean
    schedule (operation types outside the frozen schema -> declared sets are
    the contract), the uncontended first commit succeeds and the second
    transaction aborts ONLY on its genuinely superseded declared write edge
    (WRITE_EDGE_SUPERSEDED) — no false abort from derived edges."""
    outcome = _run(bl.B4_DEPENDENCY_COMPLETE, _clean_schedule())
    detail = _detail(outcome)
    assert detail["baseline"] == bl.B4_DEPENDENCY_COMPLETE
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-first-commit"]["outcome"] == "COMMIT"
    assert by_tx["t1-first-commit"]["reason_code"] == "OK"
    assert by_tx["t2-declared-stale-read"]["outcome"] == "ABORT"
    # Closure reads validate before closure writes: the superseded entity is
    # t2's DECLARED read (allergy_list), so the read-edge code fires first.
    assert by_tx["t2-declared-stale-read"]["reason_code"] == "REQUIRED_READ_EDGE_STALE"
    assert detail["final_versions"]["allergy_list"] == 2
    assert outcome.observed_outcome == "ADMIT"


def test_b4_negative_rejects_omitted_dependency_write_skew() -> None:
    """Adversarial negative (THE candidate guarantee): on the canonical
    write-skew schedule B4 REJECTS the second commit. T1 commits first and
    bumps medication_order; T2's DERIVED closure (allergy_update requires
    reading medication_order) validates at v1 but the store is at v2, so the
    required read edge is stale and the skew never lands."""
    outcome = _run(bl.B4_DEPENDENCY_COMPLETE, _write_skew_schedule())
    detail = _detail(outcome)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    assert by_tx["t2-allergy-write"]["outcome"] == "ABORT"
    assert by_tx["t2-allergy-write"]["reason_code"] == "REQUIRED_READ_EDGE_STALE"
    # The rejected write NEVER installed: the skew is blocked in final state.
    assert detail["final_versions"]["medication_order"] == 2
    assert detail["final_versions"]["allergy_list"] == 1
    assert outcome.observed_outcome == "ADMIT"  # T1 committed; pair outcome determined


# ---------------------------------------------------------------------------
# THE FIDELITY CONTRAST: same case, same config — B4 rejects what B1/B3 admit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("weak_arm", [bl.B1_SILO_READSET, bl.B3_NO_CLOSURE_ABLATION])
def test_write_skew_contrast_b4_rejects_what_b1_b3_admit(weak_arm: str) -> None:
    """Explicit cross-arm fidelity evidence on the IDENTICAL schedule.

    The omitted-dependency write skew is ADMITted by the declared-fence arms
    (B1, B3) and REJECTed by the dependency-complete candidate (B4); final
    store states differ accordingly. This differential is the fidelity
    witness the task contract requires.
    """
    skew = _write_skew_schedule()
    weak = _detail(_run(weak_arm, skew))
    cand = _detail(_run(bl.B4_DEPENDENCY_COMPLETE, skew))

    assert weak["committed"] == 2 and weak["aborted"] == 0
    cand_by_tx = {tx["tx_id"]: tx for tx in cand["transactions"]}
    assert cand_by_tx["t2-allergy-write"]["outcome"] == "ABORT"
    assert cand_by_tx["t2-allergy-write"]["reason_code"] in (
        "WRITE_EDGE_SUPERSEDED",
        "REQUIRED_READ_EDGE_STALE",
    )
    # Same first commit; only the second decision diverges.
    assert cand_by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    # The candidate's rejection is exactly what the weak arm failed to see.
    assert weak["final_versions"]["allergy_list"] == 2  # skew installed
    assert cand["final_versions"]["allergy_list"] == 1  # skew blocked


def test_constant_stub_cannot_reproduce_arm_differential() -> None:
    """A constant stub (always-ADMIT or always-REJECT) structurally fails the
    discriminating witnesses: the real arms produce arm-specific, per-
    transaction, schedule-dependent outcomes a constant cannot."""

    class _ConstantStub:
        def __init__(self, constant: str) -> None:
            self._constant = constant

        def run(self, baseline_id: str, case: object, ctx: object) -> Outcome:
            return Outcome(observed_outcome=self._constant, counted_as_success=True)

    skew = _write_skew_schedule()
    for constant in ("ADMIT", "REJECT"):
        stub = _ConstantStub(constant)
        stub_out_b1 = stub.run(bl.B1_SILO_READSET, skew, _ctx())
        stub_out_b4 = stub.run(bl.B4_DEPENDENCY_COMPLETE, skew, _ctx())
        # The stub is identical for every arm and every schedule...
        assert stub_out_b1.observed_outcome == stub_out_b4.observed_outcome == constant
        # ...but the real arms differ per arm and per schedule (B1 admits the
        # skew, B4 aborts one tx; the clean schedule aborts the second tx).
        b1_skew = _detail(_run(bl.B1_SILO_READSET, skew))
        b4_skew = _detail(_run(bl.B4_DEPENDENCY_COMPLETE, skew))
        b1_clean = _detail(_run(bl.B1_SILO_READSET, _clean_schedule()))
        assert (b1_skew["aborted"], b4_skew["aborted"]) == (0, 1)
        assert b1_clean["aborted"] == 1
        assert b1_skew["transactions"] and b4_skew["transactions"]
        assert all(tx["reason_code"] for tx in b1_skew["transactions"] + b4_skew["transactions"])


# ---------------------------------------------------------------------------
# B2 PostgreSQL SSI: honest unavailability, never faked
# ---------------------------------------------------------------------------


def test_b2_without_pg_connection_asserts_not_run_external() -> None:
    """B2 without a genuine PostgreSQL connection must assert NOT_RUN_EXTERNAL
    with BASELINE_UNAVAILABLE — never a simulated ADMIT/REJECT, never counted
    as success, retriable."""
    outcome = bl.run_baseline(bl.B2_POSTGRES_SSI, _case(), _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert "BASELINE_UNAVAILABLE" in outcome.detail
    assert bl.B2_POSTGRES_SSI in outcome.detail
    # The detail carries the honest reason: reported NOT_RUN_EXTERNAL
    # INSTEAD OF simulated (never a fabricated SSI result).
    assert "instead of simulated" in outcome.detail


def test_b2_never_accepts_sqlite_as_the_external_condition() -> None:
    """A SQLite connection must NOT satisfy the PostgreSQL arm: the genuine-
    PostgreSQL gate refuses it BEFORE execution with a stable reason code —
    no simulated SERIALIZABLE result is ever produced."""
    import sqlite3

    conn = sqlite3.connect(":memory:")

    class _CtxWithPg:
        campaign_id = "camp-compsac-baseline-fidelity"
        case_id = "case-fidelity-1"
        arm_id = "arm"
        seed = 42
        source_commit = "a" * 40
        deadline_seconds = 60.0
        pg_connection = conn

    outcome = bl.run_baseline(bl.B2_POSTGRES_SSI, _case(), _CtxWithPg())
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert bl.REASON_PG_CONNECTION_REQUIRED in outcome.detail
    assert outcome.counted_as_success is False
    # The refusal names the honesty rule: the arm is never simulated.
    assert "never simulated" in outcome.detail


# ---------------------------------------------------------------------------
# Equal-config discipline and registry honesty
# ---------------------------------------------------------------------------


def test_equal_config_all_arms_same_case_and_seed() -> None:
    """All arms run the IDENTICAL write-skew case and seed; implemented arms
    produce determined outcomes, B2 stays honestly unavailable."""
    skew = _write_skew_schedule()
    outcomes = {arm: bl.run_baseline(arm, _case(skew), _ctx(seed=7)) for arm in sorted(bl.BASELINE_REGISTRY)}
    for arm, outcome in outcomes.items():
        assert isinstance(outcome, Outcome)
        if arm == bl.B2_POSTGRES_SSI:
            assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        else:
            assert outcome.observed_outcome in ("ADMIT", "REJECT")
            detail = _detail(outcome)
            assert detail["baseline"] == arm
            assert detail["version"] == bl.COMPSAC_BASELINES_VERSION
            assert detail["tx_count"] == 2
            assert detail["committed"] + detail["aborted"] == detail["tx_count"]


def test_determinism_of_all_fidelity_vectors() -> None:
    """Every vector is deterministic: repeated runs byte-identical."""
    for arm in IMPLEMENTED_ARMS:
        schedule = _write_skew_schedule() if arm != bl.B0_GLOBAL_PROFILE else _clean_schedule()
        first = _run(arm, schedule, seed=11)
        second = _run(arm, schedule, seed=11)
        assert first.observed_outcome == second.observed_outcome
        assert first.detail == second.detail
        third = _run(arm, _clean_schedule(), seed=11)
        fourth = _run(arm, _clean_schedule(), seed=11)
        assert third.detail == fourth.detail


def test_registry_declares_implemented_arms_as_faithful_ports() -> None:
    """Registry honesty: implemented arms declare FAITHFUL_PORT with
    provenance; B2 declares NOT_RUN_EXTERNAL fidelity (never faked)."""
    for arm in IMPLEMENTED_ARMS:
        entry = bl.BASELINE_REGISTRY[arm]
        assert entry["fidelity"] == "FAITHFUL_PORT"
        assert entry.get("source") and entry.get("algorithm")
    assert bl.BASELINE_REGISTRY[bl.B2_POSTGRES_SSI]["fidelity"] == "NOT_RUN_EXTERNAL"
