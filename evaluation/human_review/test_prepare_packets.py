from __future__ import annotations

import json
from datetime import UTC, datetime

from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import REVIEWER_MODEL, EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e, seal_artifacts
from evaluation.human_review.prepare_packets import prepare_packets


def test_prepared_packets_are_blinded_and_ready_for_external_adjudication(tmp_path) -> None:
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": [
        {"resource": {"resourceType": "Patient", "id": "packet-subject"}},
        {"resource": {"resourceType": "ServiceRequest", "id": "packet-request", "status": "active", "subject": {"reference": "Patient/packet-subject"}, "authoredOn": "2026-01-01T00:00:00Z", "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"}, "code": {"coding": [{"system": "http://loinc.org", "code": "packet"}]}}},
        {"resource": {"resourceType": "Observation", "id": "packet-obs", "status": "final", "subject": {"reference": "Patient/packet-subject"}, "effectiveDateTime": "2026-01-10T00:00:00Z", "meta": {"lastUpdated": "2026-01-11T00:00:00Z"}, "code": {"coding": [{"system": "http://loinc.org", "code": "packet"}]}}},
    ]}
    run = tmp_path / "run"
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=9)
    client = EvaluationClient(base_url="https://router.invalid/v1", api_key="fixture-secret-not-real", transport=DeterministicFakeTransport(), limits=limits)
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    run_local_e2e(bundles=[(bundle, "R4")], output_dir=run, clients={REVIEWER_MODEL: client}, valid_cutoff=cutoff, known_cutoff=cutoff, limits=limits, primary_model=REVIEWER_MODEL)
    token = next(iter(json.loads((run / "partition_manifest.json").read_text())))
    (run / "partition_manifest.json").write_text(json.dumps({token: "validation"}))
    seal_artifacts(run)
    result = prepare_packets(run_dir=run, output_dir=tmp_path / "packets", split="validation")
    assert result["status"] == "READY_FOR_EXTERNAL_ADJUDICATION"
    manifest = json.loads((tmp_path / "packets" / "review_manifest.json").read_text())
    assert manifest["reviewer_ids"] == []
    packet = json.loads((tmp_path / "packets" / "blinded_packets.jsonl").read_text().splitlines()[0])
    assert packet["arm"].startswith("ARM-")
    assert "antigravity" not in json.dumps(packet)
