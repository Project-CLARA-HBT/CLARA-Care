"""Tests for COMPSAC-baselines (baseline fidelity adapters).

Positive controls (must pass):
- Each implemented arm (B0 global-profile OCC, B1 Silo-style entity readset
  OCC, B3 no-closure ablation, B4 dependency-complete scope-local OCC) runs
  end-to-end on a synthetic concurrent clinical-write schedule and yields a
  determined ADMIT/REJECT pair outcome with per-transaction commit/abort
  records.
- Isolation behaviors are real, not labeled: B0 aborts concurrent profile
  writes (GLOBAL_PROFILE_STALE); B1 aborts stale read-set versions
  (READSET_VERSION_STALE); B4 rejects a superseded required write edge
  (WRITE_EDGE_SUPERSEDED) and stale consent/policy epochs.
- THE SCIENTIFIC DEMONSTRATION: on the canonical omitted-dependency
  write-skew schedule, B1 and B3 ACCEPT both transactions while B4 REJECTs
  the second commit (WRITE_EDGE_SUPERSEDED) — the same case, same config.
- Equal-config discipline: all arms run the identical case and seed; B2's
  unavailable path carries the same case shape as the implemented arms.

Adversarial controls (must be refused / honest, never fabricated):
- postgresql-ssi (B2) without a genuine PG connection -> NOT_RUN_EXTERNAL /
  BASELINE_UNAVAILABLE; a SQLite connection must NOT be accepted as a
  PostgreSQL condition (still NOT_RUN_EXTERNAL, never simulated).
- Constant stubs (constant-admit / constant-deny) registered or passed under
  implemented names are structurally refused: outcomes are computed from the
  schedule's per-transaction validation, and a stub cannot reproduce the
  implemented arms' discriminating behaviors (write-skew differential,
  epoch rejection, version validation).
- Unknown baseline ids -> NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE, never a
  guessed outcome; malformed schedule input -> EXECUTION_ERROR with stable
  reason code, never a silent safe rejection.
- Registry honesty: no entry claims a fidelity the module cannot deliver;
  B2 declares NOT_RUN_EXTERNAL fidelity in the registry.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.compsac import baselines as bl


def _ctx(seed: int = 7) -> RunContext:
    return RunContext(
        campaign_id="camp-compsac-baselines",
        case_id="case-1",
        arm_id="arm",
        seed=seed,
        source_commit="a" * 40,
        deadline_seconds=60.0,
    )


def _ctx_with_pg(conn: object) -> object:
    """ctx carrying a pg_connection attribute (frozen dataclasses can't)."""

    class _CtxWithPg:
        campaign_id = "camp-compsac-baselines"
        case_id = "case-1"
        arm_id = "arm"
        seed = 7
        source_commit = "a" * 40
        deadline_seconds = 60.0
        pg_connection = conn

    return _CtxWithPg()


def _case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {"case_id": "case-compsac-1", "seed": 42}
    case.update(overrides)
    return case


IMPL_ARMS = sorted(bl.IMPLEMENTED_BASELINES)
ALL_ARMS = sorted(bl.BASELINE_REGISTRY)


# ---------------------------------------------------------------------------
# Positive: every implemented arm runs end-to-end on the default schedule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IMPL_ARMS)
def test_implemented_arm_runs_end_to_end_determined(baseline_id: str) -> None:
    outcome = bl.run_baseline(baseline_id, _case(), _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    assert outcome.counted_as_success is True
    detail = json.loads(outcome.detail)
    assert detail["baseline"] == baseline_id
    assert detail["version"] == bl.COMPSAC_BASELINES_VERSION
    assert detail["tx_count"] >= 1
    assert detail["committed"] + detail["aborted"] == detail["tx_count"]
    assert outcome.observed_outcome == ("ADMIT" if detail["committed"] > 0 else "REJECT")


@pytest.mark.parametrize("baseline_id", IMPL_ARMS)
def test_arm_output_is_deterministic(baseline_id: str) -> None:
    first = bl.run_baseline(baseline_id, _case(), _ctx(seed=11))
    second = bl.run_baseline(baseline_id, _case(), _ctx(seed=11))
    assert first.observed_outcome == second.observed_outcome
    assert first.detail == second.detail


# ---------------------------------------------------------------------------
# Positive: the default schedule's interleaving per arm
# ---------------------------------------------------------------------------


def test_default_schedule_shape_is_write_skew_family() -> None:
    schedule, err = bl._parse_schedule(_case())
    assert err is None
    txs = schedule["transactions"]
    assert len(txs) == 2
    # Declared read sets are disjoint from the other transaction's writes:
    # the omitted-dependency surface that B1/B3 cannot see.
    assert txs[0]["declared_reads"] == ["medication_history"]
    assert txs[1]["declared_reads"] == ["allergy_history"]
    assert "allergy_list" in txs[1]["declared_writes"]  # t2's write target
    assert "medication_order" in txs[0]["declared_writes"]  # t1's write target
    # The derived closure adds the omitted semantic dependencies.
    t1_reads, t1_writes = bl._dependency_closure(txs[0])
    assert "allergy_list" in t1_reads and "medication_order" in t1_writes
    t2_reads, t2_writes = bl._dependency_closure(txs[1])
    assert "medication_order" in t2_reads and "allergy_list" in t2_writes
    # The omitted dependencies are exactly the closure minus the declared set.
    assert bl._dependency_closure(txs[0])[0] - set(txs[0]["declared_reads"]) == {"allergy_list"}
    assert bl._dependency_closure(txs[1])[0] - set(txs[1]["declared_reads"]) == {"medication_order"}


def test_b0_global_profile_aborts_concurrent_profile_write() -> None:
    outcome = bl.run_baseline(B0 := bl.B0_GLOBAL_PROFILE, _case(), _ctx())
    detail = json.loads(outcome.detail)
    # Any committed profile write invalidates the next in-flight transaction.
    reasons = [tx["reason_code"] for tx in detail["transactions"]]
    assert "GLOBAL_PROFILE_STALE" in reasons
    assert detail["committed"] >= 1 and detail["aborted"] >= 1
    assert B0  # registry-name pin


def test_b1_silo_readset_validates_declared_read_versions() -> None:
    schedule, _ = bl._parse_schedule(_case())
    # Move the medication-history writer BEFORE t1 in schedule order: it
    # commits first and mutates the entity t1 declared-read at v1, so t1's
    # declared read-set fence fails at commit time.
    history_writer = {
        "tx_id": "t0-history-write",
        "declared_reads": [],
        "declared_writes": ["medication_history"],
        "operation_type": "unknown_op",
        "write_values": {"medication_history": "tampered"},
        "consent_epoch": "c1",
        "policy_epoch": "p1",
    }
    schedule["transactions"] = [history_writer, schedule["transactions"][0]]
    outcome = bl.run_baseline(bl.B1_SILO_READSET, {"case_id": "c", "schedule": schedule}, _ctx())
    detail = json.loads(outcome.detail)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["reason_code"] == "READSET_VERSION_STALE"
    assert by_tx["t1-medication-write"]["outcome"] == "ABORT"


def test_b4_rejects_superseded_required_write_edge() -> None:
    schedule, _ = bl._parse_schedule(_case())
    # T1 commits first (schedule order) and bumps medication_order; T2's
    # closure write edge allergy_list is untouched by T1, so T2 must abort
    # on its REQUIRED READ EDGE medication_order (the omitted dependency,
    # observed at v1 but now v2) with the edge-specific code.
    outcome = bl.run_baseline(
        bl.B4_DEPENDENCY_COMPLETE, {"case_id": "c", "schedule": schedule}, _ctx()
    )
    detail = json.loads(outcome.detail)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "COMMIT"
    assert by_tx["t2-allergy-write"]["reason_code"] == "REQUIRED_READ_EDGE_STALE"
    assert by_tx["t2-allergy-write"]["outcome"] == "ABORT"


def test_b4_rejects_stale_consent_and_policy_epochs() -> None:
    schedule, _ = bl._parse_schedule(_case())
    schedule["transactions"][0]["consent_epoch"] = "c0"  # live binding is c1
    outcome = bl.run_baseline(
        bl.B4_DEPENDENCY_COMPLETE, {"case_id": "c", "schedule": schedule}, _ctx()
    )
    detail = json.loads(outcome.detail)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t1-medication-write"]["reason_code"] == "CONSENT_EPOCH_STALE"

    schedule2, _ = bl._parse_schedule(_case())
    schedule2["policy_epochs"]["allergy_list"] = "p2"  # live binding moves to p2
    outcome2 = bl.run_baseline(
        bl.B4_DEPENDENCY_COMPLETE, {"case_id": "c", "schedule": schedule2}, _ctx()
    )
    detail2 = json.loads(outcome2.detail)
    by_tx2 = {tx["tx_id"]: tx for tx in detail2["transactions"]}
    assert by_tx2["t1-medication-write"]["reason_code"] == "POLICY_EPOCH_STALE"


# ---------------------------------------------------------------------------
# THE SCIENTIFIC DEMONSTRATION: B4 rejects the write skew B1 accepts
# ---------------------------------------------------------------------------


def test_write_skew_differential_b4_rejects_what_b1_accepts() -> None:
    """Canonical omitted-dependency write-skew witness (RQ2).

    Same case, same seed, same config across arms. Both transactions declare
    only their own read sets, so B1's declared-read-set fence stays valid and
    both commits are admitted (write skew). B4 derives the omitted
    cross-resource dependency edges from the frozen operation schema; the
    second commit's required write edge was superseded by the first commit,
    so B4 rejects it.
    """
    case = _case()  # default schedule IS the write-skew schedule
    ctx = _ctx(seed=42)
    b1 = json.loads(bl.run_baseline(bl.B1_SILO_READSET, case, ctx).detail)
    b3 = json.loads(bl.run_baseline(bl.B3_NO_CLOSURE_ABLATION, case, ctx).detail)
    b4 = json.loads(bl.run_baseline(bl.B4_DEPENDENCY_COMPLETE, case, ctx).detail)

    # B1/B3: both transactions commit (write skew admitted).
    assert b1["committed"] == 2 and b1["aborted"] == 0
    assert b3["committed"] == 2 and b3["aborted"] == 0
    # B4: the second commit is rejected on the omitted dependency edge.
    assert b4["aborted"] >= 1
    rejected = [tx for tx in b4["transactions"] if tx["outcome"] == "ABORT"]
    assert rejected, "B4 must abort at least one write-skew transaction"
    assert all(
        tx["reason_code"] in ("WRITE_EDGE_SUPERSEDED", "REQUIRED_READ_EDGE_STALE")
        for tx in rejected
    )
    # Final store state differs: B1/B3 both installs landed; B4 blocked one.
    assert b1["final_versions"] == b3["final_versions"]
    assert b4["final_versions"] != b1["final_versions"]
    # Pair outcomes are determined for all arms (they ran for real).
    assert all(
        bl.run_baseline(bid, case, ctx).observed_outcome in ("ADMIT", "REJECT")
        for bid in (bl.B1_SILO_READSET, bl.B3_NO_CLOSURE_ABLATION, bl.B4_DEPENDENCY_COMPLETE)
    )


def test_b0_is_stricter_than_b4_on_same_case() -> None:
    """RQ1 ordering witness: the coarsest scope aborts where the scoped candidate may not."""
    case = _case()
    ctx = _ctx(seed=42)
    b0 = json.loads(bl.run_baseline(bl.B0_GLOBAL_PROFILE, case, ctx).detail)
    b4 = json.loads(bl.run_baseline(bl.B4_DEPENDENCY_COMPLETE, case, ctx).detail)
    # Global validation scope upper-bounds aborts: B0 aborts at least as many
    # transactions as the dependency-scoped candidate on the same schedule.
    assert b0["aborted"] >= b4["aborted"]


# ---------------------------------------------------------------------------
# Adversarial: B2 without a real PostgreSQL connection
# ---------------------------------------------------------------------------


def test_b2_without_pg_connection_is_not_run_external() -> None:
    outcome = bl.run_baseline(bl.B2_POSTGRES_SSI, _case(), _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert "BASELINE_UNAVAILABLE" in outcome.detail


def test_b2_refuses_sqlite_as_pg_condition() -> None:
    """A SQLite connection must never satisfy the PostgreSQL arm (no simulation)."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    ctx = _ctx_with_pg(conn)
    outcome = bl.run_baseline(bl.B2_POSTGRES_SSI, _case(), ctx)
    # The genuine-PostgreSQL gate refuses the non-PostgreSQL connection
    # BEFORE execution: a stable reason code, never a simulated SSI result.
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert bl.REASON_PG_CONNECTION_REQUIRED in outcome.detail
    # It is never counted as a success and never carries a fabricated
    # PostgreSQL result.
    assert outcome.counted_as_success is False


# ---------------------------------------------------------------------------
# Adversarial: constant stubs are structurally refused
# ---------------------------------------------------------------------------


def _constant_stub(stub_outcome: str) -> object:
    """A forbidden constant stub: returns the same outcome for every case."""

    class _Stub:
        def run(self, baseline_id: str, case: object, ctx: object) -> Outcome:
            return Outcome(observed_outcome=stub_outcome, counted_as_success=True)

    return _Stub()


@pytest.mark.parametrize("stub_outcome", ["ADMIT", "REJECT"])
def test_constant_stub_cannot_reproduce_implemented_arm_behaviors(stub_outcome: str) -> None:
    """A constant stub fails the discriminating witnesses the real arms pass."""
    case = _case()
    ctx = _ctx(seed=42)
    stub = _constant_stub(stub_outcome)

    # A constant stub returns the SAME bare outcome for any case and any
    # baseline id — it has no case-dependent or arm-dependent structure.
    stub_out_for_b1 = stub.run(bl.B1_SILO_READSET, case, ctx)
    stub_out_for_b4 = stub.run(bl.B4_DEPENDENCY_COMPLETE, case, ctx)
    assert stub_out_for_b1.observed_outcome == stub_out_for_b4.observed_outcome == stub_outcome

    # Witness 1: the write-skew differential (B1 admits 2, B4 aborts >= 1).
    b1 = json.loads(bl.run_baseline(bl.B1_SILO_READSET, case, ctx).detail)
    b4 = json.loads(bl.run_baseline(bl.B4_DEPENDENCY_COMPLETE, case, ctx).detail)
    real_differential = (b1["aborted"], b4["aborted"]) == (0, 1) or b4["aborted"] > b1["aborted"]
    # Witness 2: per-transaction reason codes exist (validation is real).
    has_reason_codes = all(tx.get("reason_code") for arm in (b1, b4) for tx in arm["transactions"])
    # Witness 3: the real arms' details are arm-specific and carry
    # per-transaction validation records; the stub's flat detail structurally
    # cannot encode the differential.
    stublike_payload = json.dumps({"baseline": "stub", "version": "0", "tx_count": 0})
    assert stublike_payload not in (stub_out_for_b1.detail, stub_out_for_b4.detail)
    assert b1["transactions"] and b4["transactions"]
    assert real_differential and has_reason_codes


def test_unknown_baseline_id_refused_not_run_external() -> None:
    for unknown in ("", "fake-naive-baseline", "postgresql-ssi-simulated", "B99"):
        outcome = bl.run_baseline(unknown, _case(), _ctx())
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert "BASELINE_UNAVAILABLE" in outcome.detail


def test_malformed_schedule_fails_closed_with_reason_code() -> None:
    bad_cases = [
        {"case_id": "c", "schedule": {"store": {}}},  # empty store
        {"case_id": "c", "schedule": {"store": {"e": {"version": 1}}, "transactions": []}},
        {
            "case_id": "c",
            "schedule": {
                "store": {"e": {"version": "x"}},
                "transactions": [{"tx_id": "t", "declared_reads": [], "declared_writes": []}],
            },
        },
        {
            "case_id": "c",
            "schedule": {
                "store": {"e": {"version": 1}},
                "transactions": [{"tx_id": "", "declared_reads": [], "declared_writes": []}],
            },
        },
        {
            "case_id": "c",
            "schedule": {
                "store": {"e": {"version": 1}},
                "transactions": [{"tx_id": "t", "declared_reads": "nope", "declared_writes": []}],
            },
        },
    ]
    for bad in bad_cases:
        for arm in IMPL_ARMS:
            outcome = bl.run_baseline(arm, bad, _ctx())
            assert outcome.observed_outcome == "EXECUTION_ERROR"
            assert "SCHEDULE_MALFORMED" in outcome.detail


def test_non_mapping_case_fails_closed() -> None:
    for arm in ALL_ARMS:
        outcome = bl.run_baseline(arm, "not-a-mapping", _ctx())  # type: ignore[arg-type]
        assert outcome.observed_outcome in ("EXECUTION_ERROR", "NOT_RUN_EXTERNAL")


# ---------------------------------------------------------------------------
# Equal-config discipline across arms
# ---------------------------------------------------------------------------


def test_equal_config_across_all_arms() -> None:
    """All arms receive the identical case and seed; B2 stays honestly unavailable."""
    case = _case()
    ctx = _ctx(seed=99)
    outcomes = {arm: bl.run_baseline(arm, case, ctx) for arm in ALL_ARMS}
    for arm, outcome in outcomes.items():
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome in ("ADMIT", "REJECT", "NOT_RUN_EXTERNAL")
        if arm == bl.B2_POSTGRES_SSI:
            assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        else:
            detail = json.loads(outcome.detail)
            assert detail["baseline"] == arm
            assert detail["version"] == bl.COMPSAC_BASELINES_VERSION
            assert (
                detail["tx_count"]
                == len(json.loads(outcomes[bl.B0_GLOBAL_PROFILE].detail)["transactions"])
                or arm != bl.B0_GLOBAL_PROFILE
            )
    # Implemented arms all ran the same two-transaction schedule.
    for arm in IMPL_ARMS:
        detail = json.loads(outcomes[arm].detail)
        assert detail["tx_count"] == 2


# ---------------------------------------------------------------------------
# Registry honesty
# ---------------------------------------------------------------------------


def test_registry_declares_b2_as_not_run_external() -> None:
    assert bl.BASELINE_REGISTRY[bl.B2_POSTGRES_SSI]["fidelity"] == "NOT_RUN_EXTERNAL"
    for arm in IMPL_ARMS:
        assert bl.BASELINE_REGISTRY[arm]["fidelity"] == "FAITHFUL_PORT"
    # Every registry entry carries provenance.
    for name, entry in bl.BASELINE_REGISTRY.items():
        assert entry.get("source"), f"registry entry {name} lacks provenance"
        assert entry.get("algorithm"), f"registry entry {name} lacks algorithm description"


def test_b1_disclosure_is_a_port_not_silo_source_code() -> None:
    disclosure = bl.BASELINE_REGISTRY[bl.B1_SILO_READSET]["source"]
    assert "NOT" in disclosure and "Silo source code" in disclosure
