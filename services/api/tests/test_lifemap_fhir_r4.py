"""FHIR R4 projection, fail-closed import, and draft-only API contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import LifeMapCaptureCandidate, PhrProfile
from clara_api.db.session import SessionLocal
from clara_api.lifemap.fhir_r4 import (
    FhirValidationError,
    build_summary_bundle,
    import_candidates,
    parse_import_bundle,
    validate_bundle,
)
from clara_api.main import app

client = TestClient(app)
FIXTURE = Path(__file__).parent / "fixtures/fhir/lifemap-summary-r4.json"


def _snapshot() -> dict:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    return {
        "profile": {
            "public_id": "11111111-1111-4111-8111-111111111111",
            "full_name": "Nguyễn An",
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "allergies": [
                {
                    "id": "allergy-1",
                    "substance": "Penicillin",
                    "reaction": "Phát ban",
                    "verification_status": "unconfirmed",
                }
            ],
            "conditions": [
                {
                    "id": "condition-1",
                    "name": "Tăng huyết áp do người dùng khai báo",
                    "verification_status": "unconfirmed",
                }
            ],
        },
        "actor_role": "owner",
        "events": [
            {
                "public_id": "22222222-2222-4222-8222-222222222222",
                "event_type": "systolic_blood_pressure",
                "truth_state": "confirmed",
                "occurred_at": now,
                "payload": {
                    "display": "Huyết áp tâm thu",
                    "value": 120,
                    "unit": "mmHg",
                    "ucum_code": "mm[Hg]",
                },
                "source_kind": "reported",
            }
        ],
        "answers": [
            {
                "public_id": "33333333-3333-4333-8333-333333333333",
                "truth_state": "confirmed",
                "occurred_at": now,
                "payload": {"field_key": "symptom", "answer": {"value": "none"}},
            }
        ],
        "episodes": [
            {
                "id": 1,
                "public_id": "44444444-4444-4444-8444-444444444444",
                "title": "Theo dõi huyết áp",
                "goal": "Ghi lại số đo trước buổi khám",
                "status": "open",
            }
        ],
        "tasks": [
            {
                "public_id": "55555555-5555-4555-8555-555555555555",
                "episode_id": 1,
                "title": "Ghi số đo",
                "status": "accepted",
                "created_at": now,
            }
        ],
        "medications": [
            {
                "public_id": "66666666-6666-4666-8666-666666666666",
                "medication_name": "Thuốc do người dùng khai báo",
                "original_text": "Tên trên nhãn",
                "status": "active",
                "dose_text": "1 viên",
                "truth_state": "confirmed",
            }
        ],
        "documents": [
            {
                "public_id": "77777777-7777-4777-8777-777777777777",
                "title": "Kết quả khám",
                "document_kind": "external_user_uploaded",
                "media_type": "application/pdf",
                "status": "external_unverified",
                "created_at": now,
            }
        ],
    }


def _bundle() -> dict:
    return build_summary_bundle(
        _snapshot(),
        export_id="88888888-8888-4888-8888-888888888888",
        generated_at=datetime(2026, 7, 29, tzinfo=UTC),
        purpose="self_download",
        include={
            "demographics",
            "observations",
            "allergies",
            "conditions",
            "medications",
            "care_plan",
            "answers",
            "documents",
            "consent",
            "audit",
        },
    )


def test_mapping_covers_supported_summary_resources_and_validates() -> None:
    bundle = _bundle()
    validate_bundle(
        bundle,
        require_patient_id="11111111-1111-4111-8111-111111111111",
    )
    types = {entry["resource"]["resourceType"] for entry in bundle["entry"]}
    assert {
        "Patient",
        "Observation",
        "AllergyIntolerance",
        "Condition",
        "MedicationStatement",
        "CarePlan",
        "Goal",
        "Task",
        "QuestionnaireResponse",
        "DocumentReference",
        "Provenance",
        "Consent",
        "AuditEvent",
    } <= types
    observation = next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )
    assert observation["valueQuantity"]["system"] == "http://unitsofmeasure.org"
    assert "_clara" not in json.dumps(bundle)


def test_committed_golden_fixture_is_strict_r4_summary_not_ips() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    validate_bundle(
        fixture,
        require_patient_id="11111111-1111-4111-8111-111111111111",
    )
    assert fixture["meta"]["tag"][0]["code"] == "clara-r4-summary-not-ips"
    assert not any(
        "ips" in profile.lower()
        for entry in fixture["entry"]
        for profile in entry["resource"].get("meta", {}).get("profile", [])
    )


def test_import_is_semantically_bounded_and_always_draft_material() -> None:
    bundle = _bundle()
    parsed = parse_import_bundle(json.dumps(bundle).encode())
    candidates = import_candidates(parsed)
    assert candidates
    assert all(
        item["value"]["import_trust"] == "untrusted_external_draft"
        for item in candidates
    )
    assert not any(
        item["candidate_type"] in {"fhir_provenance", "fhir_auditevent"}
        for item in candidates
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda bundle: bundle["entry"][0]["resource"].update(
                {"modifierExtension": [{"url": "https://evil.invalid"}]}
            ),
            "unsafe_modifier_or_contained",
        ),
        (
            lambda bundle: bundle["entry"][1]["resource"].update(
                {"subject": {"reference": "https://evil.invalid/Patient/1"}}
            ),
            "external_reference_forbidden",
        ),
        (
            lambda bundle: bundle["entry"][0]["resource"].update(
                {"text": {"status": "generated", "div": "<script>alert(1)</script>"}}
            ),
            "unknown_element",
        ),
        (
            lambda bundle: bundle["entry"].append(bundle["entry"][0]),
            "fullurl_invalid",
        ),
        (
            lambda bundle: bundle["entry"][1]["resource"].update(
                {"subject": {"reference": "urn:uuid:00000000-0000-4000-8000-000000000000"}}
            ),
            "dangling_reference",
        ),
        (
            lambda bundle: bundle["entry"][1]["resource"]["code"].update(
                {"coding": [{"system": "http://loinc.org"}]}
            ),
            "critical_code_incomplete",
        ),
    ],
)
def test_import_rejects_malicious_or_ambiguous_bundles(mutation, expected) -> None:
    bundle = _bundle()
    mutation(bundle)
    with pytest.raises(FhirValidationError) as captured:
        parse_import_bundle(json.dumps(bundle).encode())
    assert any(expected in item for item in captured.value.errors)


def test_import_rejects_excess_size_depth_and_ambiguous_patient() -> None:
    with pytest.raises(FhirValidationError, match="bundle_too_large"):
        parse_import_bundle(b" " * 1_000_001)

    bundle = _bundle()
    nested: dict = {}
    cursor = nested
    for _ in range(22):
        cursor["child"] = {}
        cursor = cursor["child"]
    bundle["entry"][0]["resource"]["unexpected"] = nested
    with pytest.raises(FhirValidationError, match="maximum_nesting_exceeded"):
        validate_bundle(bundle)

    bundle = _bundle()
    second = json.loads(json.dumps(bundle["entry"][0]))
    second["fullUrl"] = "urn:uuid:00000000-0000-4000-8000-000000000001"
    second["resource"]["id"] = "00000000-0000-4000-8000-000000000002"
    bundle["entry"].append(second)
    with pytest.raises(FhirValidationError, match="exactly_one_patient_required"):
        validate_bundle(bundle)


def _headers(email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _profile_and_consent(headers: dict[str, str], suffix: str) -> str:
    profile = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"FHIR User {suffix}"},
    )
    assert profile.status_code == 200
    consent = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={
            "consent_version": consent["required_version"],
            "accepted": True,
        },
    ).status_code == 200
    with SessionLocal() as db:
        row = db.execute(
            select(PhrProfile).where(PhrProfile.full_name == f"FHIR User {suffix}")
        ).scalar_one()
        return row.public_id


def test_export_is_flagged_minimum_necessary_and_ips_never_overclaimed(
    monkeypatch,
) -> None:
    suffix = uuid4().hex
    headers = _headers(f"fhir-export-{suffix}@normal.clara")
    _profile_and_consent(headers, suffix)
    monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)

    response = client.get(
        "/api/v1/lifemap/v2/export/fhir-r4"
        "?purpose=self_download&include=observations,consent,audit",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["x-clara-conformance"] == "fhir-r4-summary-not-ips"
    patient = next(
        entry["resource"]
        for entry in response.json()["entry"]
        if entry["resource"]["resourceType"] == "Patient"
    )
    assert "name" not in patient
    ips = client.get("/api/v1/lifemap/v2/export/ips", headers=headers)
    assert ips.status_code == 409
    assert ips.json()["detail"]["code"] == "ips_conformance_not_approved"
    statement = client.get(
        "/api/v1/lifemap/v2/fhir/conformance", headers=headers
    )
    assert statement.status_code == 200
    assert statement.json()["general_fhir_server"] is False
    assert statement.json()["conformance"] == "fhir-r4-summary-not-ips"
    assert statement.json()["operations"]["ips_export"]["enabled"] is False


def test_import_creates_only_profile_scoped_drafts_and_replays(monkeypatch) -> None:
    suffix = uuid4().hex
    owner = _headers(f"fhir-import-{suffix}@normal.clara")
    stranger = _headers(f"fhir-stranger-{suffix}@normal.clara")
    owner_profile = _profile_and_consent(owner, suffix)
    _profile_and_consent(stranger, f"stranger-{suffix}")
    monkeypatch.setattr(get_settings(), "lifemap_fhir_import_enabled", True)
    raw = json.dumps(_bundle()).encode()
    headers = {
        **owner,
        "Content-Type": "application/fhir+json",
        "Idempotency-Key": f"fhir-import-{suffix}",
    }
    imported = client.post(
        "/api/v1/lifemap/v2/import/fhir-r4",
        headers=headers,
        content=raw,
    )
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["requires_review"] is True
    assert body["source_trust"] == "untrusted_external_draft"
    assert body["candidate_count"] > 0
    replay = client.post(
        "/api/v1/lifemap/v2/import/fhir-r4",
        headers=headers,
        content=raw,
    )
    assert replay.status_code == 201
    assert replay.json()["idempotent_replay"] is True
    with SessionLocal() as db:
        rows = (
            db.query(LifeMapCaptureCandidate)
            .filter(
                LifeMapCaptureCandidate.public_id.in_(
                    [item["id"] for item in body["candidates"]]
                )
            )
            .all()
        )
        assert rows
        assert all(row.status == "draft" for row in rows)

    # An unrelated profile cannot select the owner's opaque context.
    denied = client.post(
        "/api/v1/lifemap/v2/import/fhir-r4",
        headers={
            **stranger,
            "X-CLARA-Profile-Context": owner_profile,
            "Idempotency-Key": f"fhir-denied-{suffix}",
        },
        content=raw,
    )
    assert denied.status_code == 404
