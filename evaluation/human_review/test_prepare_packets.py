from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import REVIEWER_MODEL, EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e, seal_artifacts
from evaluation.human_review.prepare_packets import prepare_packets


def test_prepared_packets_use_unique_blinded_ids_and_common_reference_context(tmp_path) -> None:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "packet-subject"}},
            {
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": "packet-request",
                    "status": "active",
                    "subject": {"reference": "Patient/packet-subject"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"},
                    "code": {"coding": [{"system": "http://loinc.org", "code": "packet"}]},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "packet-obs",
                    "status": "final",
                    "subject": {"reference": "Patient/packet-subject"},
                    "effectiveDateTime": "2026-01-10T00:00:00Z",
                    "meta": {"lastUpdated": "2026-01-11T00:00:00Z"},
                    "code": {"coding": [{"system": "http://loinc.org", "code": "packet"}]},
                }
            },
        ],
    }
    run = tmp_path / "run"
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=9)
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=DeterministicFakeTransport(),
        limits=limits,
    )
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    manifest = run_local_e2e(
        bundles=[(bundle, "R4")],
        output_dir=run,
        clients={REVIEWER_MODEL: client},
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
        primary_model=REVIEWER_MODEL,
    )
    assert manifest["run_status"] == "COMPLETE"
    token = next(iter(json.loads((run / "partition_manifest.json").read_text())))
    (run / "partition_manifest.json").write_text(json.dumps({token: "validation"}))
    seal_artifacts(run)

    output = tmp_path / "packets"
    result = prepare_packets(
        run_dir=run,
        output_dir=output,
        split="validation",
        randomization_seed="fixed-test-seed",
    )
    assert result["status"] == "READY_FOR_EXTERNAL_ADJUDICATION"
    packets = [json.loads(line) for line in (output / "blinded_packets.jsonl").read_text().splitlines()]
    assert len(packets) == 9
    assert len({packet["packet_id"] for packet in packets}) == len(packets)
    assert len({json.dumps(packet["source_context"], sort_keys=True) for packet in packets}) == 1
    serialized = json.dumps(packets)
    assert "antigravity" not in serialized
    assert '"condition"' not in serialized
    assert '"arm"' not in serialized
    assert '"requested_model_id"' not in serialized

    with (output / "reviewer_import_template.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["packet_id"] for row in rows] == [packet["packet_id"] for packet in packets]

    coordinator = json.loads((output / "coordinator_only" / "coordinator_mapping.json").read_text())
    assert len(coordinator["packet_mapping"]) == len(packets)
    assert set(coordinator["packet_mapping"]) == {packet["packet_id"] for packet in packets}

    review_manifest = json.loads((output / "review_manifest.json").read_text())
    assert review_manifest["clinical_adjudication"] == "NOT_RUN"
    assert review_manifest["adjudication_scope"] == "structural_state_review_not_clinical_validity"
