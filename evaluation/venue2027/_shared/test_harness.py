"""Tests for SH-run_harness (deterministic resumable multi-arm execution).

Positive controls (must pass):
- Every planned arm x case pair is recorded exactly once, in preregistration
  order, including pairs whose adapter returns INDETERMINATE.
- Interruption + resumption: journal carries completed pairs; re-run executes
  only missing pairs; final record set has no duplicates and covers the plan.
- Re-running a fully completed campaign performs ZERO adapter calls
  (idempotent) and returns identical records.
- Records carry source_commit, python_version, harness_version, duration and
  mutually exclusive outcome counts summing to the planned denominator.
- Deterministic same-config runs produce identical pair digests.

Adversarial controls (must be refused / recorded, never dropped):
- Adapter raising an exception -> recorded EXECUTION_ERROR row (not dropped,
  not an uncounted crash), denominator still complete.
- Seed drift between arms -> SEED_DRIFT refusal before any adapter call.
- Missing arm adapter -> MISSING_ARM; unknown arm -> UNKNOWN_ARM;
  non-callable adapter -> ARM_NOT_CALLABLE; non-callable oracle ->
  ORACLE_NOT_CALLABLE.
- Journal written by a different source_commit -> JOURNAL_SOURCE_MISMATCH
  (never resumed across a moving code SHA).
- Corrupt journal line -> JOURNAL_CORRUPT.
- Adapter returning a dict without observed_outcome -> recorded
  INVALID_RESULT row (fail closed, still counted in the denominator).
- False zero: Outcome(TIMEOUT, counted_as_success=True) is rejected at
  construction time.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import (
    HARNESS_VERSION,
    Campaign,
    HarnessError,
    Outcome,
    RunContext,
    completed_pairs,
    execute,
    expected_pair_ids,
    summarize_counts,
)

SHA_40 = "573d5369abd2e9d35f8039a99cf647e6ba9b3f32"


def _campaign(
    case_ids: tuple[str, ...] = ("c1", "c2", "c3"),
    arm_ids: tuple[str, ...] = ("B0", "B1"),
    seed: int = 42,
) -> Campaign:
    return Campaign(
        campaign_id="camp-test",
        case_ids=case_ids,
        arm_ids=arm_ids,
        seeds=tuple(seed for _ in arm_ids),
        source_commit=SHA_40,
    )


def _ok_arm(outcome: str = "ADMIT"):
    def run(case, ctx: RunContext):
        assert ctx.seed == 42 and ctx.source_commit == SHA_40
        return Outcome(observed_outcome=outcome, counted_as_success=outcome in {"ADMIT", "REJECT"})

    return run


def _independent_oracle():
    """Injected oracle: derives expectations ONLY from the case id, never from
    candidate code paths; records candidate reason code as ignored."""
    calls: list[tuple[str, str]] = []

    def adjudicate(case_id, arm_id, observed, detail):
        calls.append((case_id, arm_id))
        expected = "ADMIT" if case_id.endswith("1") else "REJECT"
        return {
            "oracle_id": "independent-oracle-v1",
            "expected_outcome": expected,
            "candidate_reason_code_ignored": True,
            "decision": "PASS" if expected == observed else "FAIL",
        }

    adjudicate.calls = calls  # type: ignore[attr-defined]
    return adjudicate


# ----------------------------------------------------------- positive vectors


def test_all_planned_pairs_recorded_exactly_once() -> None:
    campaign = _campaign()
    calls: list[str] = []

    def counting_arm(case, ctx):
        calls.append(f"{ctx.arm_id}/{case['case_id']}")
        return Outcome("ADMIT", counted_as_success=True)

    bundle = execute(campaign, {"B0": counting_arm, "B1": counting_arm}, _independent_oracle())
    assert len(bundle.records) == 6  # 2 arms x 3 cases
    assert len(calls) == 6
    assert {(r["arm_id"], r["case_id"]) for r in bundle.records} == expected_pair_ids(campaign)
    # preregistration order preserved
    assert [(r["arm_id"], r["case_id"]) for r in bundle.records] == list(campaign.planned_pairs)


def test_provenance_fields_present_and_counts_exclusive() -> None:
    bundle = execute(_campaign(), {"B0": _ok_arm(), "B1": _ok_arm("REJECT")}, _independent_oracle())
    for record in bundle.records:
        assert record["source_commit"] == SHA_40
        assert record["python_version"]
        assert record["harness_version"] == HARNESS_VERSION
        assert record["duration_seconds"] >= 0
        assert record["seed"] == 42
        assert record["oracle"]["oracle_id"] == "independent-oracle-v1"
        assert len(record["pair_digest"]) == 64
    counts = bundle.outcome_counts()
    assert counts["admit"] == 3 and counts["reject"] == 3
    assert sum(counts.values()) == 6 == bundle.manifest["planned_pairs"]
    assert bundle.manifest["complete"] is True
    assert bundle.manifest["missing_pairs"] == 0
    # mutually exclusive: one observed_outcome per record, buckets sum to total
    assert bundle.manifest["denominator_total"] == len(bundle.records)


def test_interruption_resumption_completes_missing_pairs_without_duplicates(tmp_path) -> None:
    journal = tmp_path / "journal.jsonl"
    campaign = _campaign(case_ids=("c1", "c2", "c3"), arm_ids=("B0", "B1"))
    executed: list[tuple[str, str]] = []

    def flaky_arm(case, ctx):
        executed.append((ctx.arm_id, case["case_id"]))
        # First (interrupted) run: fail after 2 pairs; resumption: succeed.
        if len(executed) <= 2:
            raise RuntimeError("simulated interruption")
        return Outcome("ADMIT", counted_as_success=True)

    arms = {"B0": flaky_arm, "B1": flaky_arm}

    # "Interrupted" pass: only 2 pairs attempt before the simulated crash loop
    # ends (each raise is recorded, so the first pass actually completes with
    # errors -- simulate a hard kill by journaling just one pair manually).
    bundle1 = execute(campaign, arms, _independent_oracle(), journal_path=journal)
    assert bundle1.manifest["complete"] is True  # errors are outcomes, not drops
    first_digests = [r["pair_digest"] for r in bundle1.records]

    # Simulate interruption: truncate journal to its first 4 lines (4 pairs).
    lines = journal.read_text(encoding="utf-8").splitlines()
    journal.write_text("\n".join(lines[:4]) + "\n", encoding="utf-8")
    executed.clear()

    # Resumption: only the 2 missing pairs execute; 4 are resumed.
    bundle2 = execute(campaign, arms, _independent_oracle(), journal_path=journal)
    assert bundle2.manifest["resumed_pairs"] == 4
    assert bundle2.manifest["executed_pairs"] == 2
    assert len(executed) == 2
    keys = [(r["arm_id"], r["case_id"]) for r in bundle2.records]
    assert len(keys) == len(set(keys)) == 6  # no duplicates, full plan
    assert set(keys) == expected_pair_ids(campaign)
    assert completed_pairs(journal) == expected_pair_ids(campaign)
    # Resumed records are byte-identical to the first pass (idempotent).
    assert [r["pair_digest"] for r in bundle2.records][:4] == first_digests[:4]


def test_fully_completed_rerun_performs_zero_adapter_calls(tmp_path) -> None:
    journal = tmp_path / "journal.jsonl"
    campaign = _campaign()
    calls: list[str] = []

    def counting_arm(case, ctx):
        calls.append(case["case_id"])
        return Outcome("ADMIT", counted_as_success=True)

    execute(campaign, {"B0": counting_arm, "B1": counting_arm}, _independent_oracle(), journal_path=journal)
    first = journal.read_text(encoding="utf-8")
    assert len(calls) == 6

    rerun = execute(
        campaign, {"B0": counting_arm, "B1": counting_arm}, _independent_oracle(), journal_path=journal
    )
    assert len(calls) == 6  # zero new adapter calls
    assert rerun.manifest["resumed_pairs"] == 6
    assert rerun.manifest["executed_pairs"] == 0
    assert journal.read_text(encoding="utf-8") == first  # journal append-only stable


def test_deterministic_digests_across_identical_runs() -> None:
    campaign = _campaign()
    b1 = execute(campaign, {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle())
    b2 = execute(campaign, {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle())
    assert [r["pair_digest"] for r in b1.records] == [r["pair_digest"] for r in b2.records]


def test_to_jsonl_roundtrip() -> None:
    bundle = execute(
        _campaign(arm_ids=("B0",)), {"B0": _ok_arm()}, _independent_oracle()
    )
    lines = [json.loads(line) for line in bundle.to_jsonl().splitlines()]
    assert lines[-1]["record_kind"] == "run_manifest"
    assert all(line["record_kind"] == "pair_result" for line in lines[:-1])
    assert summarize_counts(bundle.records)["admit"] == 3


def test_workers_greater_than_one_records_all_pairs() -> None:
    campaign = _campaign()
    bundle = execute(
        campaign, {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle(), workers=3
    )
    assert {(r["arm_id"], r["case_id"]) for r in bundle.records} == expected_pair_ids(campaign)
    assert len(bundle.records) == 6


# ------------------------------------------------------- adversarial vectors


def test_adapter_exception_recorded_as_execution_error_not_dropped() -> None:
    def exploding_arm(case, ctx):
        if case["case_id"] == "c2":
            raise RuntimeError("provider 500")
        return Outcome("ADMIT", counted_as_success=True)

    bundle = execute(_campaign(), {"B0": exploding_arm, "B1": _ok_arm()}, _independent_oracle())
    assert len(bundle.records) == 6  # nothing dropped
    errors = [r for r in bundle.records if r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"]
    assert len(errors) == 1
    assert errors[0]["outcome"]["detail"] == "RuntimeError"
    assert errors[0]["arm_id"] == "B0" and errors[0]["case_id"] == "c2"
    # The error row is NOT counted as success (no invented false zero).
    assert errors[0]["outcome"]["counted_as_success"] is False
    counts = bundle.outcome_counts()
    assert counts["execution_error"] == 1 and counts["admit"] == 5
    assert sum(counts.values()) == 6


def test_seed_drift_refused_before_any_execution() -> None:
    calls: list[str] = []

    def spy_arm(case, ctx):
        calls.append(case["case_id"])
        return Outcome("ADMIT", counted_as_success=True)

    drifted = Campaign(
        campaign_id="camp-drift",
        case_ids=("c1",),
        arm_ids=("B0", "B1"),
        seeds=(42, 43),
        source_commit=SHA_40,
    )
    with pytest.raises(HarnessError) as exc:
        execute(drifted, {"B0": spy_arm, "B1": spy_arm}, _independent_oracle())
    assert exc.value.reason_code == "SEED_DRIFT"
    assert calls == []  # refused before any adapter ran


def test_wiring_errors_fail_closed() -> None:
    campaign = _campaign()
    with pytest.raises(HarnessError) as exc:
        execute(campaign, {"B0": _ok_arm()}, _independent_oracle())  # B1 missing
    assert exc.value.reason_code == "MISSING_ARM"

    with pytest.raises(HarnessError) as exc:
        execute(campaign, {"B0": _ok_arm(), "B1": _ok_arm(), "B9": _ok_arm()}, _independent_oracle())
    assert exc.value.reason_code == "UNKNOWN_ARM"

    with pytest.raises(HarnessError) as exc:
        execute(campaign, {"B0": _ok_arm(), "B1": "not callable"}, _independent_oracle())
    assert exc.value.reason_code == "ARM_NOT_CALLABLE"

    with pytest.raises(HarnessError) as exc:
        execute(campaign, {"B0": _ok_arm(), "B1": _ok_arm()}, "not an oracle")
    assert exc.value.reason_code == "ORACLE_NOT_CALLABLE"

    with pytest.raises(HarnessError) as exc:
        execute(campaign, {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle(), workers=0)
    assert exc.value.reason_code == "INVALID_WORKERS"


def test_journal_source_mismatch_refused(tmp_path) -> None:
    journal = tmp_path / "journal.jsonl"
    execute(_campaign(), {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle(), journal_path=journal)
    moved = Campaign(
        campaign_id="camp-test",
        case_ids=("c1", "c2", "c3"),
        arm_ids=("B0", "B1"),
        seeds=(42, 42),
        source_commit="a" * 40,  # different frozen SHA
    )
    with pytest.raises(HarnessError) as exc:
        execute(moved, {"B0": _ok_arm(), "B1": _ok_arm()}, _independent_oracle(), journal_path=journal)
    assert exc.value.reason_code == "JOURNAL_SOURCE_MISMATCH"


def test_corrupt_journal_refused(tmp_path) -> None:
    journal = tmp_path / "journal.jsonl"
    journal.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(HarnessError) as exc:
        execute(
            _campaign(),
            {"B0": _ok_arm(), "B1": _ok_arm()},
            _independent_oracle(),
            journal_path=journal,
        )
    assert exc.value.reason_code == "JOURNAL_CORRUPT"


def test_invalid_adapter_result_recorded_not_dropped() -> None:
    def broken_arm(case, ctx):
        return {"detail": "forgot observed_outcome"}

    bundle = execute(_campaign(), {"B0": broken_arm, "B1": _ok_arm()}, _independent_oracle())
    invalid = [
        r for r in bundle.records if r["outcome"]["observed_outcome"] == "INVALID_RESULT"
    ]
    assert len(invalid) == 3
    assert all(r["arm_id"] == "B0" for r in invalid)
    assert len(bundle.records) == 6


def test_false_zero_outcome_refused_at_construction() -> None:
    with pytest.raises(HarnessError) as exc:
        Outcome("TIMEOUT", counted_as_success=True)
    assert exc.value.reason_code == "FALSE_ZERO_OUTCOME"
    with pytest.raises(HarnessError) as exc:
        Outcome("NOT_A_BUCKET")
    assert exc.value.reason_code == "OBSERVED_OUTCOME_UNKNOWN"


def test_campaign_validation_refuses_bad_preregistrations() -> None:
    with pytest.raises(HarnessError) as exc:
        Campaign("camp", (), ("B0",), (42,), SHA_40).validate()
    assert exc.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(HarnessError) as exc:
        Campaign("camp", ("c1", "c1"), ("B0",), (42,), SHA_40).validate()
    assert exc.value.reason_code == "DUPLICATE_ID"

    with pytest.raises(HarnessError) as exc:
        Campaign("camp", ("c1",), ("B0", "B1"), (42,), SHA_40).validate()
    assert exc.value.reason_code == "SEED_DRIFT"

    with pytest.raises(HarnessError) as exc:
        Campaign("camp", ("c1",), ("B0",), (42,), "short-sha").validate()
    assert exc.value.reason_code == "MISSING_SOURCE_SHA"
