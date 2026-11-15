"""Tests for COMPSAC-X06_coarse_occ — global profile-version OCC comparator.

Exercise the REAL B0 baseline adapter
(``evaluation/venue2027/compsac/baselines.py``, arm
``global-profile-version-occ``, registry fidelity FAITHFUL_PORT) — never a
re-implementation or stub — on a concurrent clinical-write schedule whose
transactions write DIFFERENT entities of the SAME profile.

What is proven (positive controls):
- B0's commit-time validation scope is the WHOLE profile: after the first
  transaction commits, EVERY subsequent in-flight transaction aborts with
  ``GLOBAL_PROFILE_STALE`` even though its write target is disjoint from
  every earlier write (zero true read/write or write/write conflicts).
- Those aborts are exactly FALSE-STALE aborts: the same schedule, same
  config, run under the strong algorithmic comparator B1 (Silo-style
  entity read-set OCC) and under the candidate B4 (dependency-complete
  scope-local OCC), commits ALL transactions — no aborts at all.
- The REAL false-stale count is computed from B0's own per-transaction
  records (aborts whose reason code is GLOBAL_PROFILE_STALE on a write
  target disjoint from all previously committed writes) and asserted to
  its exact deterministic value (recorded in the proof log).
- Coarse-counter fidelity: the profile epoch moves when ANY entity version
  moves — including an unrelated edit to a LOWER-versioned entity that a
  max-version proxy would miss (regression witness for the counter
  semantics, X06-CASE-07).
- Honest accounting: a genuine same-entity write-write conflict is NOT
  false-stale — the false-stale classifier excludes write targets that
  truly collide with a previously committed write (X06-CASE-06).

Adversarial / fail-closed controls:
- Malformed schedule input fails closed with EXECUTION_ERROR /
  SCHEDULE_MALFORMED (never silently counted as a safe rejection).
- Determinism: identical case + ctx reproduces byte-identical detail.
- Equal-config discipline: B0, B1 and B4 receive the identical schedule,
  case id and seed; per-transaction counts are identical (only admission
  decisions differ).

Version: X06_COARSE_OCC_SPEC_VERSION 1.0.0 over COMPSAC_BASELINES_VERSION 1.0.0.
"""

from __future__ import annotations

import json

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.compsac import baselines as bl

X06_COARSE_OCC_SPEC_VERSION = "1.0.0"

#: Workers on the unrelated-edit schedule (concurrent writes to DIFFERENT
#: entities of the SAME profile).
N_WORKERS = 6


def _ctx(seed: int = 7) -> RunContext:
    return RunContext(
        campaign_id="camp-compsac-x06-coarse-occ",
        case_id="case-x06-coarse-occ",
        arm_id="arm",
        seed=seed,
        source_commit="c" * 40,
        deadline_seconds=60.0,
    )


def _x06_unrelated_write_schedule(
    n_workers: int = N_WORKERS, entities: list[str] | None = None
) -> dict[str, object]:
    """Concurrent clinical writes to DIFFERENT entities of the SAME profile.

    One clinical profile holds ``n_workers`` entities; transaction ``t_i``
    declares reading its own ``<entity>_journal`` register (untouched by the
    others) and writing entity ``e_i`` — every write target is DISTINCT and
    every read is a private journal, so there is no true read/write or
    write/write conflict anywhere in the schedule. All transactions begin at
    the same snapshot (the shared harness interleaving convention) with
    identical consent/policy epochs.

    Under a genuine single coarse profile counter every transaction's
    start-observation is invalidated by the FIRST commit, so B0 must abort
    transactions t2..t_n with GLOBAL_PROFILE_STALE even though nothing they
    touched moved — the false-stale cost of the widest validation scope.
    Two entities start at version 0 (empty ``care_plan`` / ``vitals_panel``
    registers) so the first committed write can target a lower-versioned
    entity: the counter must still move (max-version proxies are not a
    faithful coarse counter — X06-CASE-07 witnesses pass an explicit
    entity list with a v0 entity first).
    """
    base_entities = [
        "medication_order",
        "allergy_list",
        "medication_history",
        "allergy_history",
        "vitals_panel",
        "care_plan",
    ]
    targets = entities if entities is not None else base_entities[:n_workers]
    assert len(set(targets)) == len(targets) and targets
    store: dict[str, dict[str, object]] = {}
    for idx, entity in enumerate(targets):
        store[entity] = {
            "version": 0 if entity in ("care_plan", "vitals_panel") else 1,
            "value": f"initial-{idx}",
            "consent_epoch": "c1",
        }
        store[f"{entity}_journal"] = {
            "version": 1,
            "value": f"journal-{idx}",
            "consent_epoch": "c1",
        }
    transactions: list[dict[str, object]] = []
    for idx, entity in enumerate(targets):
        transactions.append(
            {
                "tx_id": f"t{idx + 1}-write-{entity}",
                "declared_reads": [f"{entity}_journal"],
                "declared_writes": [entity],
                "operation_type": "unknown_op",
                "read_versions": {f"{entity}_journal": 1},
                "write_values": {entity: f"concurrent-write-{idx + 1}"},
                "consent_epoch": "c1",
                "policy_epoch": "p1",
            }
        )
    epoch_entities = [f"{e}_journal" for e in targets] + list(targets)
    return {
        "store": store,
        "policy_epochs": {entity: "p1" for entity in epoch_entities},
        "consent_epochs": {entity: "c1" for entity in epoch_entities},
        "transactions": transactions,
    }


def _case(schedule: dict[str, object] | None = None) -> dict[str, object]:
    case: dict[str, object] = {"case_id": "case-x06-coarse-occ", "seed": 42}
    if schedule is not None:
        case["schedule"] = schedule
    return case


def _run(arm: str, case: dict[str, object], ctx: RunContext | None = None) -> dict[str, object]:
    outcome = bl.run_baseline(arm, case, ctx if ctx is not None else _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    assert outcome.counted_as_success is True
    return json.loads(outcome.detail)


def _false_stale_count(detail: dict[str, object], schedule: dict[str, object]) -> int:
    """Count B0 aborts that are FALSE-STALE under an independent classifier.

    Independent of B0's internal accounting: an abort is false-stale iff its
    reason code is GLOBAL_PROFILE_STALE and its write target is disjoint
    from every previously COMMITTED transaction's write set (i.e. no true
    conflict existed). Same-entity write-write collisions are genuine
    conflicts and are never counted.
    """
    committed_targets: set[str] = set()
    false_stale = 0
    txs = schedule["transactions"]
    assert isinstance(txs, list)
    records = detail["transactions"]
    assert isinstance(records, list)
    for tx, record in zip(txs, records, strict=True):
        assert isinstance(tx, dict)
        assert isinstance(record, dict)
        targets = {str(w) for w in tx["declared_writes"]}
        if record["outcome"] == "ABORT":
            if record["reason_code"] == "GLOBAL_PROFILE_STALE" and not (
                targets & committed_targets
            ):
                false_stale += 1
        else:
            assert record["outcome"] == "COMMIT" and record["reason_code"] == "OK"
            committed_targets |= targets
    return false_stale


# ---------------------------------------------------------------------------
# Positive: false-stale aborts on unrelated same-profile edits
# ---------------------------------------------------------------------------


def test_b0_aborts_unrelated_profile_writes_with_global_profile_stale() -> None:
    """B0's coarse scope: after the first commit, every in-flight tx aborts."""
    schedule = _x06_unrelated_write_schedule()
    detail = _run(bl.B0_GLOBAL_PROFILE, _case(schedule))
    assert detail["baseline"] == bl.B0_GLOBAL_PROFILE
    assert detail["version"] == bl.COMPSAC_BASELINES_VERSION
    assert detail["tx_count"] == N_WORKERS
    records = detail["transactions"]
    assert isinstance(records, list)
    # First transaction commits; ALL later transactions hit the moved
    # profile epoch — despite writing fully disjoint entities.
    first = records[0]
    assert isinstance(first, dict)
    assert first["outcome"] == "COMMIT" and first["reason_code"] == "OK"
    for record in records[1:]:
        assert isinstance(record, dict)
        assert record["outcome"] == "ABORT"
        assert record["reason_code"] == "GLOBAL_PROFILE_STALE"
    assert detail["committed"] == 1
    assert detail["aborted"] == N_WORKERS - 1


def test_b0_false_stale_count_is_real_and_exact() -> None:
    """Record the REAL false-stale count of B0 on the unrelated-edit schedule.

    Every abort after the first commit targets an entity disjoint from all
    previously committed writes, so ALL of them are false-stale: exactly
    ``N_WORKERS - 1`` avoidable rejections on this schedule.
    """
    schedule = _x06_unrelated_write_schedule()
    detail = _run(bl.B0_GLOBAL_PROFILE, _case(schedule))
    false_stale = _false_stale_count(detail, schedule)
    assert false_stale == N_WORKERS - 1, (
        f"REAL B0 false-stale count on {N_WORKERS} unrelated same-profile writes "
        f"must be {N_WORKERS - 1}, got {false_stale}"
    )


def test_b1_and_b4_commit_the_same_schedule_b0_aborts() -> None:
    """Same schedule, same config: B1/B4 admit what B0's coarse scope aborts.

    This is the RQ1 differential witness: the aborts B0 pays are exactly the
    false-stale cost of profile-wide validation — the strong algorithmic
    comparator (B1) and the dependency-complete candidate (B4) avoid them
    entirely because their validation fences cover only the entities each
    transaction actually read or required.
    """
    schedule = _x06_unrelated_write_schedule()
    case = _case(schedule)
    ctx = _ctx(seed=42)
    b0 = _run(bl.B0_GLOBAL_PROFILE, case, ctx)
    b1 = _run(bl.B1_SILO_READSET, case, ctx)
    b4 = _run(bl.B4_DEPENDENCY_COMPLETE, case, ctx)

    # B1/B4: every unrelated write commits (zero false-stale aborts).
    for detail in (b1, b4):
        assert detail["committed"] == N_WORKERS
        assert detail["aborted"] == 0
        records = detail["transactions"]
        assert isinstance(records, list)
        assert all(isinstance(r, dict) and r["reason_code"] == "OK" for r in records)
        assert _false_stale_count(detail, schedule) == 0

    # B0: every abort on this schedule is false-stale (no true conflicts).
    assert b0["aborted"] == N_WORKERS - 1
    assert _false_stale_count(b0, schedule) == N_WORKERS - 1

    # Equal-config discipline: identical transaction counts across arms.
    assert b0["tx_count"] == b1["tx_count"] == b4["tx_count"] == N_WORKERS

    # Store state diverges: B1/B4 land all n writes (each target v0/v1 -> +1),
    # B0 landed only the first.
    assert b1["final_versions"] == b4["final_versions"]
    b1_final = b1["final_versions"]
    b0_final = b0["final_versions"]
    assert isinstance(b1_final, dict) and isinstance(b0_final, dict)
    assert sum(b1_final.values()) - sum(b0_final.values()) >= N_WORKERS - 1


def test_b0_pair_outcome_is_determined_admit_with_full_tx_records() -> None:
    """The public run_baseline entry yields a determined pair-level outcome."""
    schedule = _x06_unrelated_write_schedule()
    outcome = bl.run_baseline(bl.B0_GLOBAL_PROFILE, _case(schedule), _ctx())
    assert outcome.observed_outcome == "ADMIT"  # >=1 commit => determined ADMIT
    assert outcome.counted_as_success is True
    detail = json.loads(outcome.detail)
    assert detail["committed"] + detail["aborted"] == detail["tx_count"] == N_WORKERS
    assert detail["forbidden_commits"] == 0


# ---------------------------------------------------------------------------
# Coarse-counter fidelity: ANY entity version move advances the epoch
# ---------------------------------------------------------------------------


def test_b0_counter_moves_on_lower_versioned_entity_edit() -> None:
    """X06-CASE-07: an unrelated edit to a LOWER-versioned entity aborts too.

    The profile epoch is a single coarse counter, not a max-version proxy:
    t0 commits a write to ``care_plan`` (v0 -> v1) while another entity sits
    at a higher version. The counter moved, so the in-flight transaction
    t1 must abort GLOBAL_PROFILE_STALE — a max() implementation would
    wrongly admit it (the regression this test pins).
    """
    schedule = _x06_unrelated_write_schedule(entities=["care_plan", "medication_order"])
    store = schedule["store"]
    assert isinstance(store, dict)
    # medication_order sits at v1 (the profile max); care_plan at v0.
    assert store["medication_order"]["version"] == 1
    assert store["care_plan"]["version"] == 0
    detail = _run(bl.B0_GLOBAL_PROFILE, _case(schedule))
    records = detail["transactions"]
    assert isinstance(records, list)
    by_tx = {r["tx_id"]: r for r in records if isinstance(r, dict)}
    # t0 writes care_plan (v0->v1): commits, counter moves even though the
    # profile max version is unchanged.
    assert by_tx["t1-write-care_plan"]["outcome"] == "COMMIT"
    # t1 writes medication_order: its start snapshot observed the pre-t0
    # counter; the unrelated lower-versioned edit invalidated it.
    assert by_tx["t2-write-medication_order"]["outcome"] == "ABORT"
    assert by_tx["t2-write-medication_order"]["reason_code"] == "GLOBAL_PROFILE_STALE"
    # And the abort is false-stale (disjoint write targets).
    assert _false_stale_count(detail, schedule) == 1


# ---------------------------------------------------------------------------
# Honest accounting: genuine conflicts are NOT false-stale
# ---------------------------------------------------------------------------


def test_b0_same_entity_write_conflict_is_not_counted_false_stale() -> None:
    """X06-CASE-06: a true write-write collision is a genuine abort.

    Two transactions write the SAME entity (lost-update hazard). B0 aborts
    the second — correctly — and the independent false-stale classifier
    must count ZERO false-stale aborts for this schedule.
    """
    base = _x06_unrelated_write_schedule(entities=["medication_order"])
    store = base["store"]
    assert isinstance(store, dict)
    conflict_tx = {
        "tx_id": "t2-conflicting-write",
        "declared_reads": ["medication_history"],
        "declared_writes": ["medication_order"],  # SAME target as t1
        "operation_type": "unknown_op",
        "read_versions": {"medication_history": 1},
        "write_values": {"medication_order": "conflicting-value"},
        "consent_epoch": "c1",
        "policy_epoch": "p1",
    }
    txs = base["transactions"]
    assert isinstance(txs, list)
    txs.append(conflict_tx)
    detail = _run(bl.B0_GLOBAL_PROFILE, _case(base))
    assert detail["committed"] == 1
    assert detail["aborted"] == 1
    records = detail["transactions"]
    assert isinstance(records, list)
    second = records[1]
    assert isinstance(second, dict)
    assert second["outcome"] == "ABORT"
    assert second["reason_code"] == "GLOBAL_PROFILE_STALE"
    # Honest classification: the abort prevented a real lost update, so the
    # false-stale count for this schedule is 0, not 1.
    assert _false_stale_count(detail, base) == 0


def test_b0_single_transaction_schedule_has_no_false_stale() -> None:
    """One writer alone: the counter cannot have moved; no abort at all."""
    schedule = _x06_unrelated_write_schedule(entities=["medication_order"])
    detail = _run(bl.B0_GLOBAL_PROFILE, _case(schedule))
    assert detail["committed"] == 1 and detail["aborted"] == 0
    assert _false_stale_count(detail, schedule) == 0


# ---------------------------------------------------------------------------
# Adversarial / fail-closed controls
# ---------------------------------------------------------------------------


def test_b0_malformed_schedule_fails_closed() -> None:
    """Malformed schedule input is EXECUTION_ERROR, never a silent rejection."""
    outcome = bl.run_baseline(
        bl.B0_GLOBAL_PROFILE,
        {"case_id": "c", "schedule": {"store": "not-a-store", "transactions": []}},
        _ctx(),
    )
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.detail.startswith(bl.REASON_SCHEDULE_MALFORMED)
    assert outcome.counted_as_success is False


def test_b0_is_deterministic() -> None:
    """Same case + ctx reproduces byte-identical per-transaction records."""
    schedule = _x06_unrelated_write_schedule()
    case = _case(schedule)
    first = json.loads(bl.run_baseline(bl.B0_GLOBAL_PROFILE, case, _ctx()).detail)
    second = json.loads(bl.run_baseline(bl.B0_GLOBAL_PROFILE, case, _ctx()).detail)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_x06_spec_version_pins_baselines_version() -> None:
    """The X06 spec layer pins the baseline layer version it was proven on."""
    assert bl.COMPSAC_BASELINES_VERSION == "1.0.0"
    assert X06_COARSE_OCC_SPEC_VERSION == "1.0.0"
