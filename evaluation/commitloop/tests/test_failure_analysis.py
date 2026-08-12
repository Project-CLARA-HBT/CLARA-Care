from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from evaluation.commitloop.failure_analysis import analyze_development_run
from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import REVIEWER_MODEL, EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e


def _bundle() -> dict:
    return {
        "resourceType": "Bundle", "type": "collection", "entry": [
            {"resource": {"resourceType": "Patient", "id": "analysis-subject"}},
            {"resource": {"resourceType": "ServiceRequest", "id": "request-analysis", "status": "active", "subject": {"reference": "Patient/analysis-subject"}, "authoredOn": "2026-01-01T00:00:00Z", "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"}, "code": {"coding": [{"system": "http://loinc.org", "code": "analysis-code"}]}}},
            {"resource": {"resourceType": "Observation", "id": "obs-analysis", "status": "final", "subject": {"reference": "Patient/analysis-subject"}, "effectiveDateTime": "2026-01-10T00:00:00Z", "meta": {"lastUpdated": "2026-01-11T00:00:00Z"}, "code": {"coding": [{"system": "http://loinc.org", "code": "analysis-code"}]}}},
        ],
    }


def test_failure_analysis_is_aggregate_and_refuses_final_holdout(tmp_path) -> None:
    run = tmp_path / "run"
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=9)
    client = EvaluationClient(base_url="https://router.invalid/v1", api_key="fixture-secret-not-real", transport=DeterministicFakeTransport(), limits=limits)
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    run_local_e2e(bundles=[(_bundle(), "R4")], output_dir=run, clients={REVIEWER_MODEL: client}, valid_cutoff=cutoff, known_cutoff=cutoff, limits=limits, primary_model=REVIEWER_MODEL)
    partitions = json.loads((run / "partition_manifest.json").read_text())
    token = next(iter(partitions))
    (run / "partition_manifest.json").write_text(json.dumps({token: "development"}))
    from evaluation.commitloop.run_local import seal_artifacts
    seal_artifacts(run)
    report = analyze_development_run(run_dir=run, output_dir=tmp_path / "analysis")
    assert report["status"] == "DEVELOPMENT_ONLY"
    assert (tmp_path / "analysis" / "failure_taxonomy.csv").is_file()
    assert not list((tmp_path / "analysis").glob("*output*"))
    with pytest.raises(ValueError, match="final_holdout_failure_analysis_forbidden"):
        analyze_development_run(run_dir=run, output_dir=tmp_path / "forbidden", analysis_split="sealed_test")
