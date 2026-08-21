from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import FhirIngestError, ingest_bundle


def _bundle(entries: list[dict]) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": item} for item in entries],
    }


def test_r4_ingestion_and_candidate_are_source_grounded() -> None:
    bundle = _bundle(
        [
            {"resourceType": "Patient", "id": "patient-a"},
            {
                "resourceType": "ServiceRequest",
                "id": "request-1",
                "status": "active",
                "subject": {"reference": "Patient/patient-a"},
                "authoredOn": "2026-01-01T00:00:00Z",
                "occurrencePeriod": {"end": "2026-02-01T00:00:00Z"},
                "code": {"coding": [{"system": "http://loinc.org", "code": "example"}]},
            },
        ]
    )
    token, events = ingest_bundle(
        bundle, fhir_version="R4", ingested_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    cases = mine_candidates(token, events)
    assert cases[0].status == "ELIGIBLE"
    assert cases[0].anchor_evidence_id == "ServiceRequest/request-1"
    assert cases[0].target == {"system": "http://loinc.org", "code": "example"}
    assert cases[0].due_time == datetime(2026, 2, 1, tzinfo=UTC)


def test_missing_grounded_code_yields_no_eligible_case() -> None:
    token, events = ingest_bundle(
        _bundle(
            [
                {"resourceType": "Patient", "id": "patient-b"},
                {
                    "resourceType": "ServiceRequest",
                    "id": "request-2",
                    "status": "active",
                    "subject": {"reference": "Patient/patient-b"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                },
            ]
        ),
        fhir_version="R4",
        ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert mine_candidates(token, events)[0].status == "NO_ELIGIBLE_CASE"


def test_stu3_procedure_request_is_source_grounded_without_relabeling_provenance() -> None:
    token, events = ingest_bundle(
        _bundle(
            [
                {"resourceType": "Patient", "id": "patient-stu3"},
                {
                    "resourceType": "ProcedureRequest",
                    "id": "request-stu3",
                    "status": "active",
                    "subject": {"reference": "Patient/patient-stu3"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "scheduledPeriod": {"end": "2026-02-01T00:00:00Z"},
                    "code": {"coding": [{"system": "http://loinc.org", "code": "example-stu3"}]},
                },
            ]
        ),
        fhir_version="STU3",
        ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    cases = mine_candidates(token, events)
    assert events[0].resource_type == "ProcedureRequest"
    assert cases[0].status == "ELIGIBLE"
    assert cases[0].anchor_evidence_id == "ProcedureRequest/request-stu3"
    assert cases[0].target == {"system": "http://loinc.org", "code": "example-stu3"}
    assert cases[0].due_time == datetime(2026, 2, 1, tzinfo=UTC)


def test_version_and_subject_scope_fail_closed() -> None:
    with pytest.raises(FhirIngestError, match="unsupported_fhir_version"):
        ingest_bundle(_bundle([]), fhir_version="R5", ingested_at=datetime.now(UTC))
    with pytest.raises(FhirIngestError, match="timezone_aware_ingested_at_required"):
        ingest_bundle(
            _bundle([]),
            fhir_version="R4",
            ingested_at=datetime(2026, 1, 1),  # noqa: DTZ001 - rejection fixture
        )
    with pytest.raises(FhirIngestError, match="cross_subject_reference"):
        ingest_bundle(
            _bundle(
                [
                    {"resourceType": "Patient", "id": "patient-a"},
                    {
                        "resourceType": "Observation",
                        "id": "obs-1",
                        "subject": {"reference": "Patient/patient-b"},
                    },
                ]
            ),
            fhir_version="STU3",
            ingested_at=datetime.now(UTC),
        )


def test_local_knowledge_time_cannot_predate_bundle_ingestion() -> None:
    ingested_at = datetime(2026, 2, 1, tzinfo=UTC)
    token, events = ingest_bundle(
        _bundle(
            [
                {"resourceType": "Patient", "id": "patient-known-time"},
                {
                    "resourceType": "Observation",
                    "id": "obs-known-time",
                    "status": "final",
                    "subject": {"reference": "Patient/patient-known-time"},
                    "effectiveDateTime": "2026-01-01T00:00:00Z",
                    "meta": {"lastUpdated": "2026-01-02T00:00:00Z"},
                    "code": {"coding": [{"system": "s", "code": "c"}]},
                },
            ]
        ),
        fhir_version="R4",
        ingested_at=ingested_at,
    )
    assert token
    assert events[0].known_at == ingested_at
    assert events[0].source["meta"]["lastUpdated"] == "2026-01-02T00:00:00Z"
