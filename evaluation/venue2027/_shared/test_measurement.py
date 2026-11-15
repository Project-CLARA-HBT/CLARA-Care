"""Tests for SH-measurement (measurement standard over raw run bundles).

Positive controls (must compute from raw records):
- Mutually exclusive outcome counts partition the planned denominator on a
  synthetic bundle containing every harness bucket, including records an
  earlier task might have been tempted to drop (EXECUTION_ERROR, TIMEOUT,
  INVALID_RESULT, INDETERMINATE, NOT_RUN_EXTERNAL).
- ``assert_denominator_consistency`` returns the recount when counts partition
  the planned total (attempted + missing == planned; manifest agrees).
- Latency p50/p95/p99 are exact nearest-rank order statistics of the raw
  durations (known sleep-style benchmark -> plausible latency, same units).
- Throughput is committed admits / busy seconds (sum of per-record durations),
  computed, not estimated.
- Retry amplification is computed from recorded ``attempt_index`` fields.
- Metrics are refused (listed in ``unavailable`` with a stable reason code)
  rather than invented as zeros when their raw records are absent.

Adversarial controls (must be refused / fail closed):
- Missing records: forbidden-commit rate on a bundle with no oracle verdicts
  -> ORACLE_VERDICT_MISSING; latency on a bundle without durations ->
  MISSING_RECORDS; retry amplification with no attempt fields ->
  MISSING_RECORDS. None of them silently returns 0.
- Denominator mismatch: dropping a planned pair (attempted + missing !=
  planned), a manifest lying about denominator_total, and a duplicate pair
  (bucket sum != record count) all raise DENOMINATOR_MISMATCH.
- Mixed time units: p99 over records declaring different ``duration_unit``
  values is rejected with MIXED_TIME_UNITS (never averaged through); malformed
  durations (negative, non-numeric, NaN) are refused with MALFORMED_DURATION.
- False zero ban: no metric in the payload is fabricated when its evidence is
  missing; the field is None plus an explicit ``unavailable`` entry.
- ``require`` escalation: demanding an unavailable metric raises its stable
  reason code instead of returning a silently-partial payload.
"""

from __future__ import annotations

import json
import math

import pytest

from evaluation.venue2027._shared.harness import Campaign, Outcome, RunContext, execute
from evaluation.venue2027._shared.measurement import (
    MEASUREMENT_VERSION,
    REASON_DENOMINATOR_MISMATCH,
    REASON_MALFORMED_DURATION,
    REASON_MISSING_RECORDS,
    REASON_MIXED_TIME_UNITS,
    REASON_ORACLE_VERDICT_MISSING,
    MeasurementError,
    assert_denominator_consistency,
    compute_denominator,
    compute_false_stale_rate,
    compute_forbidden_commit_rate,
    compute_latency,
    measure,
)

SHA_40 = "573d5369abd2e9d35f8039a99cf647e6ba9b3f32"


# ---------------------------------------------------------------------------
# Synthetic bundle construction (all evidence injected; no clock, no I/O)
# ---------------------------------------------------------------------------


def _oracle_for(expected: dict[str, str]):
    """Injected independent oracle: truth derives from the frozen label table."""

    def adjudicate(case_id, arm_id, observed, detail):
        return {
            "expected_outcome": expected[case_id],
            "decision": "PASS",
            "oracle_id": "test-oracle-v1",
        }

    return adjudicate


def _synthetic_bundle():
    """Two-arm x three-case bundle with one of every non-tail bucket.

    Planned = 6 pairs. Observed: admit, reject, execution_error,
    indeterminate, timeout, invalid_result. Durations are declared in
    seconds; two retries are recorded via attempt_index on arm B1/c2.
    """
    campaign = Campaign(
        campaign_id="camp-meas",
        case_ids=("c1", "c2", "c3"),
        arm_ids=("B0", "B1"),
        seeds=(42, 42),
        source_commit=SHA_40,
    )
    plan = {
        ("B0", "c1"): ("ADMIT", 0.10),
        ("B0", "c2"): ("REJECT", 0.20),
        ("B0", "c3"): ("EXECUTION_ERROR", 0.30),
        ("B1", "c1"): ("INDETERMINATE", 0.40),
        ("B1", "c2"): ("TIMEOUT", 0.50),
        ("B1", "c3"): ("INVALID_RESULT", 0.60),
    }
    truth = {"c1": "ADMIT", "c2": "REJECT", "c3": "REJECT"}

    attempts: dict[tuple[str, str], int] = {}

    def run(case, ctx: RunContext):
        key = (ctx.arm_id, ctx.case_id)
        attempts[key] = attempts.get(key, 0) + 1
        observed, _ = plan[key]
        record_attempt = 2 if key == ("B1", "c2") else 1
        return Outcome(
            observed_outcome=observed,
            counted_as_success=observed in {"ADMIT", "REJECT"},
            detail=f"attempt {record_attempt}",
        )

    bundle = execute(campaign, {"B0": run, "B1": run}, _oracle_for(truth))
    # Deterministic durations for exact order statistics (override raw timing).
    for record in bundle.records:
        key = (record["arm_id"], record["case_id"])
        record["duration_seconds"] = plan[key][1]
        record["attempt_index"] = 2 if key == ("B1", "c2") else 1
    return bundle


@pytest.fixture()
def bundle():
    return _synthetic_bundle()


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


class TestDenominatorPartition:
    def test_counts_partition_planned_total(self, bundle):
        metrics = measure(bundle)
        counts = metrics.outcome_counts
        assert counts["admit"] == 1
        assert counts["reject"] == 1
        assert counts["execution_error"] == 1
        assert counts["indeterminate"] == 1
        assert counts["timeout"] == 1
        assert counts["invalid_result"] == 1
        assert counts["not_run"] == 0  # a *tally* zero is fine: bucket exists, pairs absent
        assert sum(counts.values()) == len(bundle.records) == 6

    def test_assert_denominator_consistency_passes(self, bundle):
        recount = assert_denominator_consistency(bundle)
        assert recount["admit"] == 1 and recount["timeout"] == 1

    def test_denominator_fields(self, bundle):
        denom = compute_denominator(bundle.records, bundle.manifest)
        assert denom["planned"] == 6
        assert denom["attempted"] == 6
        assert denom["missing"] == 0
        assert denom["attempted_total"] == 6

    def test_missing_pair_is_counted_not_shrunk(self, bundle):
        # A planned pair that never produced a record widens `missing`,
        # it must NOT shrink the planned denominator.
        short = type(bundle)(
            campaign_id=bundle.campaign_id,
            source_commit=bundle.source_commit,
            seed=bundle.seed,
            python_version=bundle.python_version,
            harness_version=bundle.harness_version,
            records=bundle.records[:-1],
            manifest=dict(bundle.manifest, missing_pairs=1, denominator_total=5),
        )
        metrics = measure(short)
        assert metrics.denominator["planned"] == 6
        assert metrics.denominator["attempted"] == 5
        assert metrics.denominator["missing"] == 1


class TestComputedMetrics:
    def test_forbidden_commit_rate_from_oracle_truth(self, bundle):
        # Oracle truth c1=ADMIT, c2=REJECT, c3=REJECT; no observed ADMIT
        # contradicts truth, so forbidden commits = 0 over planned=6.
        metrics = measure(bundle)
        assert metrics.forbidden_commit_rate == 0.0
        assert metrics.provenance["metric_sources"]["forbidden_commit_rate"].startswith("oracle")

    def test_forbidden_commit_detected(self, bundle):
        # Forge one forbidden commit: B0/c1 ADMITs while oracle says REJECT.
        truth = {"c1": "REJECT", "c2": "REJECT", "c3": "REJECT"}
        campaign = Campaign(
            campaign_id="camp-forbidden",
            case_ids=("c1",),
            arm_ids=("B0",),
            seeds=(42,),
            source_commit=SHA_40,
        )

        def run(case, ctx):
            return Outcome(observed_outcome="ADMIT", counted_as_success=True)

        forged = execute(campaign, {"B0": run}, _oracle_for(truth))
        metrics = measure(forged)
        assert metrics.forbidden_commit_rate == 1.0

    def test_false_stale_rate(self, bundle):
        # Exactly one REJECT (B0/c2) with oracle truth ADMIT would be a false
        # stale; here truth for c2 is REJECT so the rate is 0.0.
        metrics = measure(bundle)
        assert metrics.false_stale_rate == 0.0

    def test_false_stale_detected(self, bundle):
        truth = {"c1": "ADMIT", "c2": "ADMIT", "c3": "ADMIT"}
        campaign = Campaign(
            campaign_id="camp-stale",
            case_ids=("c1", "c2"),
            arm_ids=("B0",),
            seeds=(42,),
            source_commit=SHA_40,
        )

        def run(case, ctx):
            return Outcome(
                observed_outcome="REJECT" if ctx.case_id == "c2" else "ADMIT",
                counted_as_success=True,
            )

        stale = execute(campaign, {"B0": run}, _oracle_for(truth))
        metrics = measure(stale)
        # 1 false stale (c2 REJECT with truth ADMIT) / 1 stale-check REJECT.
        assert metrics.false_stale_rate == 1.0

    def test_throughput_from_busy_time(self, bundle):
        metrics = measure(bundle)
        # Committed ops = 1 admit; busy time = 0.10s (only the admit's duration
        # counts as SUT-active committed time).
        assert metrics.throughput_ops_per_sec == pytest.approx(1.0 / 0.10)

    def test_latency_exact_order_statistics(self, bundle):
        metrics = measure(bundle)
        lat = metrics.latency_seconds
        assert lat is not None
        assert lat.unit == "s" and lat.n == 6
        # sorted durations: .1 .2 .3 .4 .5 .6 -> nearest-rank p50=rank3, p95=rank6, p99=rank6
        assert lat.p50 == pytest.approx(0.30)
        assert lat.p95 == pytest.approx(0.60)
        assert lat.p99 == pytest.approx(0.60)

    def test_retry_amplification_from_attempt_index(self, bundle):
        metrics = measure(bundle)
        # 7 total attempts across 6 distinct ops -> 7/6.
        assert metrics.retry_amplification == pytest.approx(7 / 6)

    def test_measured_against_live_sleep_benchmark(self):
        # Positive control from the task spec: a known sleep benchmark
        # produces plausible latency in the same units (no hidden clock).
        import time

        campaign = Campaign(
            campaign_id="camp-sleep",
            case_ids=("s1", "s2"),
            arm_ids=("B0",),
            seeds=(42,),
            source_commit=SHA_40,
        )

        def run(case, ctx):
            time.sleep(0.01)
            return Outcome(observed_outcome="ADMIT", counted_as_success=True)

        bundle = execute(campaign, {"B0": run}, _oracle_for({"s1": "ADMIT", "s2": "ADMIT"}))
        metrics = measure(bundle)
        assert metrics.latency_seconds is not None
        assert 0.005 <= metrics.latency_seconds.p50 <= 0.500
        assert metrics.latency_seconds.unit == "s"

    def test_payload_is_json_serializable_and_versioned(self, bundle):
        metrics = measure(bundle)
        payload = json.loads(json.dumps(metrics.to_dict()))
        assert payload["measurement_version"] == MEASUREMENT_VERSION
        assert payload["campaign_id"] == "camp-meas"

    def test_measure_accepts_jsonl_roundtrip(self, bundle):
        text = bundle.to_jsonl()
        metrics = measure(text)
        assert metrics.outcome_counts["admit"] == 1
        assert metrics.denominator["planned"] == 6


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


class TestMissingRecordsRefused:
    def test_no_oracle_verdicts_forbidden_rate_refused(self, bundle):
        # Strip the independent oracle verdicts: forbidden-commit rate must be
        # refused (stable reason), never defaulted to 0.
        for record in bundle.records:
            record.pop("oracle")
        metrics = measure(bundle)
        assert metrics.forbidden_commit_rate is None
        entries = [u for u in metrics.unavailable if u.metric == "forbidden_commit_rate"]
        assert len(entries) == 1
        assert entries[0].reason_code == REASON_ORACLE_VERDICT_MISSING

    def test_required_forbidden_rate_raises(self, bundle):
        for record in bundle.records:
            record.pop("oracle")
        with pytest.raises(MeasurementError) as excinfo:
            measure(bundle, require=("forbidden_commit_rate",))
        assert excinfo.value.reason_code == REASON_ORACLE_VERDICT_MISSING

    def test_no_durations_latency_refused(self, bundle):
        for record in bundle.records:
            record.pop("duration_seconds")
        metrics = measure(bundle)
        assert metrics.latency_seconds is None
        entries = [u for u in metrics.unavailable if u.metric == "latency_seconds"]
        assert entries[0].reason_code == REASON_MISSING_RECORDS
        # Throughput also loses its duration evidence and is refused.
        assert metrics.throughput_ops_per_sec is None

    def test_no_attempt_fields_retry_refused(self, bundle):
        for record in bundle.records:
            record.pop("attempt_index")
        metrics = measure(bundle)
        assert metrics.retry_amplification is None
        entries = [u for u in metrics.unavailable if u.metric == "retry_amplification"]
        assert entries[0].reason_code == REASON_MISSING_RECORDS

    def test_absent_metric_is_never_invented_zero(self, bundle):
        # The false-zero ban: with no oracle and no attempts, the payload has
        # None (not 0.0) for both, plus explicit unavailable reasons.
        for record in bundle.records:
            record.pop("oracle")
            record.pop("attempt_index")
        metrics = measure(bundle)
        payload = metrics.to_dict()
        assert payload["forbidden_commit_rate"] is None
        assert payload["retry_amplification"] is None
        assert metrics.outcome_counts["admit"] == 1  # tally of present records is intact
        assert {u.metric for u in metrics.unavailable} >= {
            "forbidden_commit_rate",
            "retry_amplification",
        }

    def test_empty_bundle_refused(self):
        with pytest.raises(MeasurementError) as excinfo:
            measure({"campaign_id": "x", "manifest": {}, "records": []})
        assert excinfo.value.reason_code == REASON_MISSING_RECORDS


class TestDenominatorMismatchRefused:
    def test_dropped_pair_refused(self, bundle):
        broken = type(bundle)(
            campaign_id=bundle.campaign_id,
            source_commit=bundle.source_commit,
            seed=bundle.seed,
            python_version=bundle.python_version,
            harness_version=bundle.harness_version,
            records=bundle.records[:-1],
            # Manifest still claims nothing is missing -> mismatch.
            manifest=dict(bundle.manifest, missing_pairs=0),
        )
        with pytest.raises(MeasurementError) as excinfo:
            measure(broken)
        assert excinfo.value.reason_code == REASON_DENOMINATOR_MISMATCH

    def test_lying_manifest_total_refused(self, bundle):
        broken = type(bundle)(
            campaign_id=bundle.campaign_id,
            source_commit=bundle.source_commit,
            seed=bundle.seed,
            python_version=bundle.python_version,
            harness_version=bundle.harness_version,
            records=bundle.records,
            manifest=dict(bundle.manifest, denominator_total=99),
        )
        with pytest.raises(MeasurementError) as excinfo:
            assert_denominator_consistency(broken)
        assert excinfo.value.reason_code == REASON_DENOMINATOR_MISMATCH

    def test_duplicate_pair_refused(self, bundle):
        # One pair counted twice: bucket sum (7) != record count (7)? No — the
        # duplicate IS a seventh record, so the partition check that fails is
        # attempted+missing != planned via measure(); the bucket-sum invariant
        # itself needs a malformed record whose outcome does not tally once.
        duplicate = type(bundle)(
            campaign_id=bundle.campaign_id,
            source_commit=bundle.source_commit,
            seed=bundle.seed,
            python_version=bundle.python_version,
            harness_version=bundle.harness_version,
            records=bundle.records + [dict(bundle.records[0])],
            manifest=dict(bundle.manifest, planned_pairs=7, missing_pairs=0),
        )
        with pytest.raises(MeasurementError) as excinfo:
            assert_denominator_consistency(duplicate)
        assert excinfo.value.reason_code == REASON_DENOMINATOR_MISMATCH

    def test_malformed_outcome_refused(self, bundle):
        broken = dict(bundle.records[0])
        broken["outcome"] = {"observed_outcome": "SPARKLE"}
        malformed = type(bundle)(
            campaign_id=bundle.campaign_id,
            source_commit=bundle.source_commit,
            seed=bundle.seed,
            python_version=bundle.python_version,
            harness_version=bundle.harness_version,
            records=[broken, *bundle.records[1:]],
            manifest=bundle.manifest,
        )
        with pytest.raises(MeasurementError) as excinfo:
            measure(malformed)
        assert "MALFORMED_RECORD" in str(excinfo.value)


class TestMixedTimeUnitsAndMalformedDurations:
    def test_mixed_units_rejected_for_latency(self, bundle):
        mixed = [
            dict(r, duration_unit="s" if i % 2 == 0 else "ms")
            for i, r in enumerate(bundle.records)
        ]
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(mixed, unit="s")
        assert excinfo.value.reason_code == REASON_MIXED_TIME_UNITS

    def test_p99_never_averages_through_mixed_units(self, bundle):
        # The task spec adversarial vector: "p99 computed on malformed mixed
        # time units rejected" — measure() must not produce a p99 either.
        mixed = [dict(r, duration_unit="ms") for r in bundle.records[:3]]
        mixed += [dict(r, duration_unit="s") for r in bundle.records[3:]]
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(mixed, unit="s")
        assert excinfo.value.reason_code == REASON_MIXED_TIME_UNITS

    def test_negative_duration_refused(self, bundle):
        bad = [dict(bundle.records[0], duration_seconds=-1.0), *bundle.records[1:]]
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(bad, unit="s")
        assert excinfo.value.reason_code == REASON_MALFORMED_DURATION

    def test_non_numeric_duration_refused(self, bundle):
        bad = [dict(bundle.records[0], duration_seconds="fast"), *bundle.records[1:]]
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(bad, unit="s")
        assert excinfo.value.reason_code == REASON_MALFORMED_DURATION

    def test_nan_duration_refused(self, bundle):
        bad = [dict(bundle.records[0], duration_seconds=math.nan), *bundle.records[1:]]
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(bad, unit="s")
        assert excinfo.value.reason_code == REASON_MALFORMED_DURATION

    def test_unknown_unit_refused(self, bundle):
        with pytest.raises(MeasurementError) as excinfo:
            compute_latency(bundle.records, unit="furlongs")
        assert excinfo.value.reason_code == REASON_MIXED_TIME_UNITS


class TestRateDenominators:
    def test_forbidden_rate_without_denominator_refused(self, bundle):
        value, reason = compute_forbidden_commit_rate(bundle.records, denominator=0)
        assert value is None and reason == "NO_DENOMINATOR"

    def test_false_stale_without_checks_refused(self):
        # No oracle verdicts at all -> no stale checks -> refused, not zero.
        value, reason = compute_false_stale_rate(
            [{"outcome": {"observed_outcome": "REJECT"}}]
        )
        assert value is None and reason == REASON_MISSING_RECORDS
