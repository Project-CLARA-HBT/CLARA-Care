"""Development-only PoPETs pilot coverage, provenance, and failure controls."""

import dataclasses
import hashlib
import json

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.popets import generate_dataset
from evaluation.venue2027.popets.pilot_executor import (
    PilotConfig,
    PilotError,
    calculate_power,
    development_records,
    execute_pilot,
    load_pilot_plan,
    pilot,
    record_to_scenario_case,
    run_development,
    summarize,
)


def test_only_dev_indices_materialized(monkeypatch):
    calls = []
    payload = generate_dataset.revocation_payload

    def record(seed, family, idx):
        calls.append(idx)
        return payload(seed, family, idx)

    monkeypatch.setattr(generate_dataset, "revocation_payload", record)
    monkeypatch.setattr(dk, "generate", lambda *a, **kw: pytest.fail("buffered generator used"))
    records = development_records(42, 60)
    assert calls == list(range(36, 48))
    cases = [record_to_scenario_case(r) for r in records]
    assert {c["case_id"] for c in cases} == {c["scenario"]["principal"] for c in cases}
    assert len(set(c["case_id"] for c in cases)) == 12


def test_full_accounting_and_raw_provenance():
    cfg = PilotConfig(n=60, seed=42)
    report, bundle, cases = run_development(cfg)
    assert report.to_dict() == summarize(cfg, cases, bundle).to_dict()
    assert report.coverage["recorded"] == report.planned_pairs == 60
    assert report.coverage["executed"] == report.coverage["comparable"] == 36
    assert report.coverage["outcomes"]["not_run_external"] == 24
    assert report.coverage["missing"] == 0
    assert report.complete is False
    assert report.oracle_disagreements == report.candidate_disagreements == 0
    assert report.disagreement_rate == 0
    assert set(report.runtime_stats["per_arm"]) == {"B1", "B2", "B4"}
    assert report.variance_estimates["admission_indicator_by_arm"]["B0"] is None
    assert report.provenance["raw_sha256"] == hashlib.sha256(bundle.to_jsonl().encode()).hexdigest()
    assert report.provenance["source_commit"] == bundle.source_commit
    assert report.dispatch_metrics["independently_observed_dispatches"] == 0
    assert report.dispatch_metrics["unauthorized_bytes"] is None
    assert report.power_estimates["required_sample_size"] is None
    assert report.feasible_matrix["confirmatory_study_n"] is None
    json.dumps(report.to_dict(), allow_nan=False)


def test_absent_eligible_observations_and_candidate():
    report = pilot(PilotConfig(n=20, arm_ids=("B0",)))
    assert report.coverage["comparable"] == 0
    assert report.disagreement_rate is None
    assert report.candidate_disagreements is None
    assert report.runtime_stats["mean_pair_duration_seconds"] is None


def test_incomplete_duplicate_and_broken_adjudication():
    cfg = PilotConfig(n=20)
    _, bundle, cases = run_development(cfg)
    rows = [dict(r) for r in bundle.records]
    b4 = next(r for r in rows if r["arm_id"] == "B4")
    b4["oracle"] = {"oracle_error": "fault"}
    rows.pop(next(i for i, r in enumerate(rows) if r["arm_id"] == "B2"))
    report = summarize(cfg, cases, dataclasses.replace(bundle, records=rows))
    assert report.coverage["missing"] == 1
    assert report.coverage["oracle_unassessed"] == 1
    assert report.coverage["comparable"] == 10
    assert report.baseline_fairness["balanced_pairing"] is False
    with pytest.raises(PilotError, match="UNEXPECTED_PAIR"):
        summarize(cfg, cases, dataclasses.replace(bundle, records=rows + [rows[0]]))


def test_external_inputs_keep_distinct_unit_ids():
    records = development_records(42, 20)
    duplicate = [records[0], records[0]]
    with pytest.raises(PilotError, match="DUPLICATE_ID"):
        execute_pilot(dev_dataset=duplicate)
    with pytest.raises(PilotError, match="CONFIG_MALFORMED"):
        execute_pilot(dev_dataset=[{"family": "fresh", "split": "dev"}])
    with pytest.raises(PilotError, match="UNKNOWN_FAMILY"):
        execute_pilot(dev_dataset=[dataclasses.replace(records[0], family="wrong")])


@pytest.mark.parametrize("label", ["test", "holdout", " train ", None, ""])
def test_refuse_non_dev_inputs_before_materializing_content(label):
    with pytest.raises(PilotError, match="HOLDOUT_ACCESS_FORBIDDEN"):
        execute_pilot(PilotConfig(split=label))
    with pytest.raises(PilotError, match="HOLDOUT_ACCESS_FORBIDDEN"):
        execute_pilot(dev_dataset=[{"unit_id": "synthetic", "split": label}])
    with pytest.raises(PilotError, match="HOLDOUT_ACCESS_FORBIDDEN"):
        execute_pilot(dev_dataset=[{"unit_id": "unlabeled"}])


def test_plan_and_power_scope():
    assert load_pilot_plan()["power"]["status"] == "BLOCKED"
    result = calculate_power(alpha=0.1, sample_sizes=(60,))
    assert result["zero_event_upper_if_independent"]["60"] == pytest.approx(1 - 0.1 ** (1 / 60))
    assert result["required_sample_size"] is None
    with pytest.raises(PilotError, match="CONFIG_MALFORMED"):
        calculate_power(alpha=0)
    with pytest.raises(PilotError, match="EMPTY_SCOPE"):
        execute_pilot(PilotConfig(arm_ids=()))
    with pytest.raises(PilotError, match="EMPTY_SCOPE"):
        execute_pilot(dev_dataset=[])


def test_real_oracle_disagreement_and_indeterminate_remain_distinct():
    cfg = PilotConfig(n=20)
    _, bundle, cases = run_development(cfg)
    rows = [dict(r) for r in bundle.records]
    row, other = [r for r in rows if r["arm_id"] == "B4"][:2]
    row["outcome"] = {
        **row["outcome"],
        "observed_outcome": (
            "ADMIT" if row["oracle"]["expected_outcome"] == "REJECT" else "REJECT"
        ),
    }
    other["outcome"] = {**other["outcome"], "observed_outcome": "INDETERMINATE"}
    result = summarize(cfg, cases, dataclasses.replace(bundle, records=rows))
    assert result.coverage["outcomes"]["indeterminate"] == 1
    assert result.coverage["comparable"] == 11
    assert result.oracle_disagreements == result.candidate_disagreements == 1
    assert result.disagreement_rate == pytest.approx(1 / 11)


def test_false_sha_is_refused():
    with pytest.raises(PilotError, match="SOURCE_MISMATCH"):
        execute_pilot(PilotConfig(n=20, source_commit="a" * 40))
