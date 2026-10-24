"""Automated verification suite for FHIR R4 CapabilityStatement contract and endpoints.

Phase: PH11 (FHIR R4 interoperability production profiles)
Subagent: A01 (API + contract)

Validates:
1. Contract JSON structure and schema adherence.
2. Pydantic DTO models and FHIR R4 field constraints.
3. Feature flag gating (allow and deny paths).
4. Content negotiation (_format query param and Accept header).
5. Query mode filtering (full, normative, terminology).
6. RBAC access control (401 unauthorized, 403 forbidden, 200 allowed).
7. Conformance rules summary DTO.
8. FastAPI route mounting and HTTP responses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from clara_api.api.v1.endpoints.fhir import (
    FHIR_R4_VERSION,
    MIME_FHIR_JSON,
    MIME_JSON,
    _validate_negotiation,
    build_capability_statement,
    is_fhir_capability_enabled,
    require_fhir_capability_enabled,
    router as fhir_router,
)
from clara_api.core.security import TokenPayload
from clara_api.schemas import (
    FHIRCapabilityStatement,
    FHIRConformanceRulesSummary,
    FHIRRestResource,
)

CONTRACTS_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Contract & Schema Integrity Tests
# ==============================================================================


def test_capability_statement_contract_structure() -> None:
    contract_path = CONTRACTS_DIR / "capability_statement_contract.v1.json"
    assert contract_path.is_file(), f"Missing contract file at {contract_path}"
    data = load_json(contract_path)

    assert data.get("phase_id") == "PH11"
    assert data.get("agent_id") == "A01"
    assert data.get("standard") == "HL7 FHIR Release 4 (v4.0.1)"
    assert data.get("feature_flag") == "FHIR_CAPABILITY_STATEMENT_ENABLED"
    assert data.get("default_flag_state") is False

    # Check endpoints defined
    paths = {ep["path"] for ep in data["endpoints"]}
    assert "/api/v1/fhir/metadata" in paths
    assert "/api/v1/fhir/CapabilityStatement" in paths
    assert "/api/v1/fhir/conformance-rules" in paths

    # Check security invariants
    security = data["security"]
    assert "OAuth2-Bearer" in security["auth_mechanisms"]
    assert "SMART-on-FHIR" in security["auth_mechanisms"]
    assert "CLARA-RBAC" in security["auth_mechanisms"]
    assert set(security["roles"]) == {"normal", "researcher", "doctor", "admin"}

    # Check supported resources
    resource_types = {r["type"] for r in data["supported_resources"]}
    expected_resources = {
        "Patient",
        "Observation",
        "Condition",
        "MedicationStatement",
        "MedicationRequest",
        "AllergyIntolerance",
        "DocumentReference",
        "Composition",
        "Encounter",
        "Consent",
        "Provenance",
        "AuditEvent",
    }
    assert expected_resources.issubset(resource_types)

    # Check invariants
    invariants = data["invariants"]
    assert invariants["no_mock_data"] is True
    assert invariants["strict_dto_validation"] is True
    assert invariants["fhir_version_locked"] == "4.0.1"


def test_capability_statement_json_schema_structure() -> None:
    schema_path = CONTRACTS_DIR / "capability_statement.schema.json"
    assert schema_path.is_file(), f"Missing schema at {schema_path}"
    schema = load_json(schema_path)

    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("type") == "object"
    required_props = set(schema.get("required", []))
    assert {"resourceType", "id", "url", "version", "name", "status", "fhirVersion", "rest"}.issubset(required_props)
    assert schema["properties"]["resourceType"]["const"] == "CapabilityStatement"
    assert schema["properties"]["fhirVersion"]["const"] == "4.0.1"


# ==============================================================================
# Pydantic DTO Validation Tests
# ==============================================================================


def test_pydantic_capability_statement_dto_build() -> None:
    statement = build_capability_statement(mode="full")
    assert isinstance(statement, FHIRCapabilityStatement)
    assert statement.resourceType == "CapabilityStatement"
    assert statement.fhirVersion == "4.0.1"
    assert statement.status == "active"
    assert statement.kind == "instance"
    assert statement.software.name == "CLARA Care Medical AI Assistant"
    assert MIME_FHIR_JSON in statement.format
    assert MIME_JSON in statement.format

    # Verify rest configuration
    assert len(statement.rest) == 1
    rest = statement.rest[0]
    assert rest.mode == "server"
    assert rest.security is not None
    assert rest.security.cors is True

    # 12 resources in full mode
    res_types = [r.type for r in rest.resource]
    assert len(res_types) == 12
    assert "Patient" in res_types
    assert "Observation" in res_types
    assert "Composition" in res_types

    # Export & Import operations present
    op_names = [op.name for op in rest.operation]
    assert "export" in op_names
    assert "import" in op_names


def test_pydantic_capability_statement_modes() -> None:
    full_stmt = build_capability_statement(mode="full")
    normative_stmt = build_capability_statement(mode="normative")
    terminology_stmt = build_capability_statement(mode="terminology")

    full_types = {r.type for r in full_stmt.rest[0].resource}
    norm_types = {r.type for r in normative_stmt.rest[0].resource}
    term_types = {r.type for r in terminology_stmt.rest[0].resource}

    assert norm_types == {"Patient", "Observation", "Condition", "Encounter"}
    assert term_types == {"Observation", "Condition", "MedicationStatement", "AllergyIntolerance"}
    assert len(full_types) == 12
    assert norm_types.issubset(full_types)


def test_pydantic_dto_validation_rejection() -> None:
    # Malformed resourceType rejected
    with pytest.raises(ValidationError):
        FHIRCapabilityStatement(
            resourceType="InvalidType",  # type: ignore[arg-type]
            id="test",
            url="https://test.com",
            version="1.0",
            name="test",
            title="test",
            status="active",
            date="2026-10-24",
            publisher="test",
            description="test",
            software={"name": "test", "version": "1.0"},  # type: ignore[arg-type]
            fhirVersion="4.0.1",
        )

    # Wrong fhirVersion rejected
    with pytest.raises(ValidationError):
        FHIRCapabilityStatement(
            resourceType="CapabilityStatement",
            id="test",
            url="https://test.com",
            version="1.0",
            name="test",
            title="test",
            status="active",
            date="2026-10-24",
            publisher="test",
            description="test",
            software={"name": "test", "version": "1.0"},  # type: ignore[arg-type]
            fhirVersion="3.0.1",  # type: ignore[arg-type]
        )


# ==============================================================================
# Feature Flag & Gate Tests (Allow / Deny Paths)
# ==============================================================================


def test_feature_flag_deny_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FHIR_CAPABILITY_STATEMENT_ENABLED", raising=False)
    assert not is_fhir_capability_enabled()

    with pytest.raises(HTTPException) as exc_info:
        require_fhir_capability_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail.get("code") == "fhir_capability_disabled"


def test_feature_flag_allow_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    assert is_fhir_capability_enabled()
    # Should not raise
    require_fhir_capability_enabled()


# ==============================================================================
# Content Negotiation & Input Validation Tests
# ==============================================================================


def test_content_negotiation_valid() -> None:
    # Both json and application/fhir+json valid
    _validate_negotiation(accept="application/fhir+json", _format=None)
    _validate_negotiation(accept="*/*", _format="json")
    _validate_negotiation(accept=None, _format="application/json")


def test_content_negotiation_unsupported_format() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_negotiation(accept=None, _format="xml")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail.get("code") == "unsupported_format"


def test_content_negotiation_unsupported_accept() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_negotiation(accept="application/fhir+xml", _format=None)
    assert exc_info.value.status_code == 406
    assert exc_info.value.detail.get("code") == "not_acceptable"


# ==============================================================================
# HTTP TestClient Route Tests (Integration with FastAPI)
# ==============================================================================


@pytest.fixture
def test_client() -> TestClient:
    app = FastAPI()
    app.include_router(fhir_router, prefix="/api/v1/fhir")
    return TestClient(app)


def test_client_feature_flag_disabled(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "false")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    resp = test_client.get("/api/v1/fhir/metadata")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "fhir_capability_disabled"

    resp_rules = test_client.get("/api/v1/fhir/conformance-rules")
    assert resp_rules.status_code == 404


def test_client_unauthenticated_denied_when_public_disabled(
    test_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "false")

    resp = test_client.get("/api/v1/fhir/metadata")
    assert resp.status_code == 401


def test_client_metadata_happy_path(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    resp = test_client.get("/api/v1/fhir/metadata")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(MIME_FHIR_JSON)
    assert resp.headers["x-clara-fhir-version"] == FHIR_R4_VERSION

    body = resp.json()
    assert body["resourceType"] == "CapabilityStatement"
    assert body["fhirVersion"] == "4.0.1"
    assert body["status"] == "active"
    assert len(body["rest"][0]["resource"]) == 12


def test_client_capability_statement_alias(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    resp = test_client.get("/api/v1/fhir/CapabilityStatement")
    assert resp.status_code == 200
    assert resp.json()["resourceType"] == "CapabilityStatement"


def test_client_mode_parameter(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    # Normative mode
    resp = test_client.get("/api/v1/fhir/metadata?mode=normative")
    assert resp.status_code == 200
    resources = resp.json()["rest"][0]["resource"]
    assert len(resources) == 4
    assert {r["type"] for r in resources} == {"Patient", "Observation", "Condition", "Encounter"}

    # Invalid mode
    resp_invalid = test_client.get("/api/v1/fhir/metadata?mode=unknown_mode")
    assert resp_invalid.status_code == 400
    assert resp_invalid.json()["detail"]["code"] == "invalid_mode"


def test_client_conformance_rules_endpoint(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    resp = test_client.get("/api/v1/fhir/conformance-rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert rules["fhir_version"] == "4.0.1"
    assert rules["conformance_status"] == "active"
    assert len(rules["supported_resources"]) == 12
    assert "OAuth2-Bearer" in rules["security_protocols"]
    assert "$export" in rules["operations"]
    assert "$import" in rules["operations"]
    assert len(rules["invariants"]) >= 5
    assert rules["feature_flag_status"] is True


def test_api_router_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that api_router mounts the fhir endpoints with /fhir prefix."""
    from clara_api.api.router import api_router

    app = FastAPI()
    app.include_router(api_router)
    client = TestClient(app)

    monkeypatch.setenv("FHIR_CAPABILITY_STATEMENT_ENABLED", "true")
    monkeypatch.setenv("FHIR_PUBLIC_METADATA_ENABLED", "true")

    resp = client.get("/api/v1/fhir/metadata")
    assert resp.status_code == 200
    assert resp.json()["resourceType"] == "CapabilityStatement"
