"""Tests for COMPSAC-X05_silo_occ — Silo-style entity read-set OCC comparator.

The arm under test executes the REAL B1 baseline engine
(``evaluation/venue2027/compsac/baselines.py``, registry arm
``silo-style-entity-readset-occ``, fidelity FAITHFUL_PORT) through the task
signature adapter ``silo_readset_port.execute_occ(op, store) -> Outcome``.
The OCC protocol is never re-implemented or stubbed here.

Positive controls (must pass):
- A valid clinical write operation COMMITs through the Silo-style fence and
  installs its write with version + 1 (determined, reproducible detail).
- Commit-time read-set version validation is REAL: an operation whose observed
  read version diverges from the CURRENT store (a concurrent committed write)
  aborts with READSET_VERSION_STALE and its writes are NOT installed — the
  store is untouched by the aborted operation (transaction invalidation).
- An unknown read entity aborts with ENTITY_UNKNOWN; a stale consent/policy
  epoch aborts with the epoch-specific code (version equality alone does not
  admit — the ABA/epoch-cycle guard).

Adversarial / scientific-contrast controls (must hold, with real counts):
- THE RQ2 WRITE-SKEW CONTRAST: on the canonical omitted-dependency write-skew
  schedule, the Silo-style read-set fence (B1) ADMITS both transactions
  (declared read sets stay valid; aborted == 0) while the candidate B4
  (dependency-complete scope-local OCC) REJECTs the second commit on the
  omitted dependency edge (aborted >= 1) — same case, same config; real abort
  counts are read from run_baseline detail and asserted.
- The declared-read-set boundary is the mechanism: closing the read set with
  the derived dependency closure turns the admitted write skew into an abort
  (closure drives the differential, nothing else).
- Tamper surface: an explicit read_versions entry claiming an older observed
  version is caught by the fence.
- Wiring errors fail closed with stable reason codes (OP_MALFORMED,
  STORE_MALFORMED -> EXECUTION_ERROR), never counted as safe rejections.
- Determinism: identical inputs yield byte-identical outcomes.

Version: SILO_READSET_PORT_VERSION 1.0.0 over COMPSAC_BASELINES_VERSION 1.0.0.
"""

from __future__ import annotations

import json

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.compsac import baselines as bl
from evaluation.venue2027.compsac import silo_readset_port as port

B1 = bl.B1_SILO_READSET
B4 = bl.B4_DEPENDENCY_COMPLETE


def _store() -> dict[str, dict[str, object]]:
    """Clinical profile snapshot at v1 with c1/p1 epoch bindings."""
    return {
        "medication_order": {"version": 1, "value": "none", "consent_epoch": "c1"},
        "allergy_list": {"version": 1, "value": "penicillin", "consent_epoch": "c1"},
        "medication_history": {"version": 1, "value": "statins", "consent_epoch": "c1"},
        "allergy_history": {"version": 1, "value": "rash-2025", "consent_epoch": "c1"},
    }


def _prescribe(store: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    """medication_prescribe: reads medication_history at v1, writes medication_order."""
    return {
        "tx_id": "t1-medication-write",
        "declared_reads": ["medication_history"],
        "declared_writes": ["medication_order"],
        "operation_type": "medication_prescribe",
        "read_versions": {"medication_history": 1},
        "write_values": {"medication_order": "metformin-500mg"},
        "consent_epoch": "c1",
        "policy_epoch": "p1",
    }


def _write_skew_case() -> dict[str, object]:
    """Canonical omitted-dependency write-skew schedule (the default B1 case)."""
    return {"case_id": "case-x05-silo-occ", "seed": 42}


def _detail(outcome: Outcome) -> dict[str, object]:
    assert isinstance(outcome, Outcome)
    return json.loads(outcome.detail)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Positive: a valid operation commits and installs version + 1
# ---------------------------------------------------------------------------


def test_valid_operation_commits_and_installs_version_plus_one() -> None:
    outcome = port.execute_occ(_prescribe(), _store())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    detail = _detail(outcome)
    assert detail["baseline"] == B1
    assert detail["tx_count"] == 1
    assert detail["committed"] == 1 and detail["aborted"] == 0
    tx = detail["transactions"][0]
    assert tx["outcome"] == "COMMIT" and tx["reason_code"] == "OK"
    # Writes install with version + 1 exactly (Silo write-install rule).
    assert detail["final_versions"]["medication_order"] == 2
    # Untouched entities keep their versions.
    assert detail["final_versions"]["medication_history"] == 1


def test_execute_occ_is_deterministic_and_json_serializable() -> None:
    first = port.execute_occ(_prescribe(), _store())
    second = port.execute_occ(_prescribe(), _store())
    assert first.observed_outcome == second.observed_outcome
    assert first.detail == second.detail
    detail = _detail(first)
    json.dumps(detail, sort_keys=True)  # must not raise
    assert port.SILO_READSET_PORT_VERSION == "1.0.0"
    assert "NOT Silo source code" in port.PORT_DISCLOSURE


def test_silo_operation_dataclass_round_trips_through_execute_occ() -> None:
    op = port.SiloOperation(
        tx_id="t1-medication-write",
        declared_reads=("medication_history",),
        declared_writes=("medication_order",),
        read_versions={"medication_history": 1},
        write_values={"medication_order": "metformin-500mg"},
        operation_type="medication_prescribe",
        consent_epoch="c1",
        policy_epoch="p1",
    )
    via_dataclass = port.execute_occ(op, _store())
    via_dict = port.execute_occ(_prescribe(), _store())
    assert via_dataclass.observed_outcome == via_dict.observed_outcome == "ADMIT"
    assert via_dataclass.detail == via_dict.detail


# ---------------------------------------------------------------------------
# Positive: commit-time read-set version validation (stale read set aborts)
# ---------------------------------------------------------------------------


def test_stale_read_set_aborts_and_writes_are_never_installed() -> None:
    """A concurrent committed write invalidates the declared read set at commit."""
    store = _store()
    # The concurrent writer commits FIRST (schedule order) and bumps the
    # entity t1 declared-read; t1 then presents its stale observed version.
    history_writer = {
        "tx_id": "t0-history-write",
        "declared_reads": [],
        "declared_writes": ["medication_history"],
        "operation_type": "unknown_op",
        "write_values": {"medication_history": "tampered"},
        "consent_epoch": "c1",
        "policy_epoch": "p1",
    }
    # Run the writer through the same real engine to advance the store, then
    # re-validate t1's fence against the CURRENT store snapshot.
    writer_outcome = port.execute_occ(history_writer, store)
    assert writer_outcome.observed_outcome == "ADMIT"
    store["medication_history"]["version"] = 2  # writer installed version+1
    outcome = port.execute_occ(_prescribe(store), store)
    assert outcome.observed_outcome == "REJECT"
    detail = _detail(outcome)
    tx = detail["transactions"][0]
    assert tx["outcome"] == "ABORT"
    assert tx["reason_code"] == "READSET_VERSION_STALE"
    assert detail["aborted"] == 1 and detail["committed"] == 0
    # Transaction invalidation: the aborted operation's writes are NOT
    # installed — medication_order stays at v1 with its prior value.
    assert detail["final_versions"]["medication_order"] == 1


def test_real_engine_aborts_stale_declared_read_in_schedule_order() -> None:
    """Same fence proven end-to-end through the real B1 baseline adapter."""
    schedule, _ = bl._parse_schedule(_write_skew_case())
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
    outcome = bl.run_baseline(B1, {"case_id": "c", "schedule": schedule}, None)
    detail = _detail(outcome)
    by_tx = {tx["tx_id"]: tx for tx in detail["transactions"]}
    assert by_tx["t0-history-write"]["outcome"] == "COMMIT"
    assert by_tx["t1-medication-write"]["outcome"] == "ABORT"
    assert by_tx["t1-medication-write"]["reason_code"] == "READSET_VERSION_STALE"
    assert detail["aborted"] == 1


def test_unknown_read_entity_aborts_with_entity_unknown() -> None:
    op = _prescribe()
    op["declared_reads"] = ["nonexistent_entity"]
    outcome = port.execute_occ(op, _store())
    assert outcome.observed_outcome == "REJECT"
    tx = _detail(outcome)["transactions"][0]
    assert tx["outcome"] == "ABORT" and tx["reason_code"] == "ENTITY_UNKNOWN"


def test_stale_consent_epoch_aborts_even_when_versions_match() -> None:
    """ABA/epoch cycle: version equality alone does not admit."""
    op = _prescribe()
    op["consent_epoch"] = "c0"  # live binding is c1
    outcome = port.execute_occ(op, _store())
    assert outcome.observed_outcome == "REJECT"
    tx = _detail(outcome)["transactions"][0]
    assert tx["reason_code"] == "CONSENT_EPOCH_STALE"


def test_stale_policy_epoch_aborts_even_when_versions_match() -> None:
    store = _store()
    store["allergy_list"]["policy_epoch"] = "p2"  # live binding moved to p2
    op = _prescribe(store)
    op["declared_reads"] = ["allergy_list"]
    op["read_versions"] = {"allergy_list": 1}
    op["declared_writes"] = ["medication_order"]
    outcome = port.execute_occ(op, store)
    assert outcome.observed_outcome == "REJECT"
    tx = _detail(outcome)["transactions"][0]
    assert tx["reason_code"] == "POLICY_EPOCH_STALE"


# ---------------------------------------------------------------------------
# Scientific contrast: the fence ADMITS the omitted-dependency write skew
# that B4 REJECTs (RQ2), with real abort counts
# ---------------------------------------------------------------------------


def test_silo_fence_admits_write_skew_that_b4_rejects() -> None:
    """Canonical omitted-dependency write-skew witness (same case, same config).

    Both transactions declare only their own read sets — disjoint from the
    other's write targets — so B1's declared-read-set fence stays valid and
    BOTH commit (write skew over the omitted dependencies). B4 derives the
    required cross-resource edges from the frozen operation schema and rejects
    the second commit because T1's committed write superseded T2's required
    read edge (medication_order). Real abort counts are asserted, not assumed.
    """
    case = _write_skew_case()
    b1_detail = _detail(bl.run_baseline(B1, dict(case), None))
    b4_detail = _detail(bl.run_baseline(B4, dict(case), None))

    # B1: the omitted-dependency write skew is ADMITTED — both commit, zero
    # aborts (real count from the engine detail).
    assert b1_detail["aborted"] == 0
    assert b1_detail["committed"] == 2
    assert all(tx["outcome"] == "COMMIT" for tx in b1_detail["transactions"])

    # B4: the candidate REJECTs on the omitted dependency edge.
    assert b4_detail["aborted"] >= 1
    rejected = [tx for tx in b4_detail["transactions"] if tx["outcome"] == "ABORT"]
    assert rejected, "B4 must abort at least one write-skew transaction"
    assert all(
        tx["reason_code"] in ("WRITE_EDGE_SUPERSEDED", "REQUIRED_READ_EDGE_STALE")
        for tx in rejected
    )
    # Real differential recorded on the identical schedule.
    assert b4_detail["aborted"] > b1_detail["aborted"]
    # Final store states differ: both B1 installs landed; B4 blocked one.
    assert b4_detail["final_versions"] != b1_detail["final_versions"]


def test_closing_the_declared_read_set_turns_the_skew_into_an_abort() -> None:
    """The declared-read-set boundary is the mechanism, nothing else.

    Re-running the SAME schedule through the real engine with the derived
    dependency closure added to the validated read set (the B4 machinery on
    B1's fence) aborts the skew transaction — proving the differential is
    caused by the omitted dependency edge, not by any other arm difference.
    """
    schedule, _ = bl._parse_schedule(_write_skew_case())
    b1_detail = _detail(bl.run_baseline(B1, {"case_id": "c", "schedule": schedule}, None))
    assert b1_detail["aborted"] == 0 and b1_detail["committed"] == 2

    # Add the omitted semantic dependency to T2's DECLARED read set (the only
    # change): T2 now reads medication_order at its observed version v1, which
    # T1's committed write already superseded — the fence must fire.
    t2 = schedule["transactions"][1]
    t2["declared_reads"] = sorted(set(t2["declared_reads"]) | {"medication_order"})
    t2["read_versions"] = {**t2.get("read_versions", {}), "medication_order": 1}
    closed_detail = _detail(bl.run_baseline(B1, {"case_id": "c", "schedule": schedule}, None))
    by_tx = {tx["tx_id"]: tx for tx in closed_detail["transactions"]}
    assert by_tx["t2-allergy-write"]["outcome"] == "ABORT"
    assert by_tx["t2-allergy-write"]["reason_code"] == "READSET_VERSION_STALE"
    assert closed_detail["aborted"] == 1 and closed_detail["committed"] == 1


def test_tampered_read_version_claim_is_caught_by_the_fence() -> None:
    """An operation claiming an older observed version is rejected (tamper)."""
    schedule, _ = bl._parse_schedule(_write_skew_case())
    t1 = schedule["transactions"][0]
    t1["read_versions"] = {"medication_history": 0}  # observed version falsified
    outcome = bl.run_baseline(B1, {"case_id": "c", "schedule": schedule}, None)
    by_tx = {tx["tx_id"]: tx for tx in _detail(outcome)["transactions"]}
    assert by_tx["t1-medication-write"]["outcome"] == "ABORT"
    assert by_tx["t1-medication-write"]["reason_code"] == "READSET_VERSION_STALE"


# ---------------------------------------------------------------------------
# Wiring: fail-closed input handling, never silent safe rejections
# ---------------------------------------------------------------------------


def test_malformed_op_fails_closed_with_op_malformed() -> None:
    bad_ops: list[object] = [
        {"tx_id": "", "declared_reads": [], "declared_writes": []},
        {"declared_reads": [], "declared_writes": []},  # no tx_id
        {"tx_id": "t", "declared_reads": "nope", "declared_writes": []},
        {"tx_id": "t", "declared_reads": [], "declared_writes": [], "surprise": 1},
        {
            "tx_id": "t",
            "declared_reads": [],
            "declared_writes": [],
            "read_versions": {"e": "x"},
        },
        "not-a-mapping",
    ]
    for bad in bad_ops:
        outcome = port.execute_occ(bad, _store())  # type: ignore[arg-type]
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "EXECUTION_ERROR", bad
        assert outcome.detail.startswith(port.RC_OP_MALFORMED), bad
        assert outcome.counted_as_success is False


def test_malformed_store_fails_closed_with_store_malformed() -> None:
    bad_stores: list[object] = [
        {},
        "not-a-mapping",
        {"e": {"version": "x"}},
        {"e": {"version": -1}},
        {"e": "not-a-record"},
    ]
    for bad in bad_stores:
        outcome = port.execute_occ(_prescribe(), bad)  # type: ignore[arg-type]
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "EXECUTION_ERROR", bad
        assert outcome.detail.startswith(port.RC_STORE_MALFORMED), bad
        assert outcome.counted_as_success is False


def test_degenerate_noop_op_follows_engine_semantics_not_adapter_opinion() -> None:
    """A well-formed no-op (empty reads/writes) is the ENGINE's call to make.

    The B1 engine commits an empty transaction trivially (vacuous fence); the
    adapter must not reclassify engine-legal input as an input error. Adapter
    rejections are reserved for structural malformation (OP_MALFORMED /
    STORE_MALFORMED); OCC verdicts come from the engine alone.
    """
    outcome = port.execute_occ(
        {"tx_id": "t", "declared_reads": [], "declared_writes": []}, _store()
    )
    assert outcome.observed_outcome == "ADMIT"
    tx = _detail(outcome)["transactions"][0]
    assert tx["outcome"] == "COMMIT" and tx["reason_code"] == "OK"


def test_engine_entity_unknown_reason_passes_through() -> None:
    store = {"e": {"version": 1}}
    op = {"tx_id": "t", "declared_reads": ["missing"], "declared_writes": ["e"]}
    # declared read references an entity absent from the store -> ENTITY_UNKNOWN
    # is the engine's rejection; the adapter must not reclassify it.
    outcome = port.execute_occ(op, store)
    assert outcome.observed_outcome == "REJECT"
    assert _detail(outcome)["transactions"][0]["reason_code"] == "ENTITY_UNKNOWN"
