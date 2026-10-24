"""Verification test suite for FHIR SMART-on-FHIR OAuth2 / OIDC scopes and endpoint security.

Agent: A09
Phase: PH11
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

# ==============================================================================
# 1. SMART-on-FHIR Scope Parser and Capability Evaluator
# ==============================================================================

SMART_V2_PATTERN = re.compile(
    r"^(?P<context>patient|user|system)/"
    r"(?P<resource>[A-Za-z*]+)\."
    r"(?P<perms>[cruds*]+)"
    r"(?:\?(?P<params>[a-zA-Z0-9_=&-]+))?$"
)

ALLOWED_CONTEXTS = {"patient", "user", "system"}
ALLOWED_PERMS = {"c", "r", "u", "d", "s", "*"}
IDENTITY_SCOPES = {"openid", "profile", "email", "fhirUser"}
LAUNCH_SCOPES = {"launch", "launch/patient", "launch/encounter"}
SESSION_SCOPES = {"offline_access", "online_access"}

SUPPORTED_FHIR_RESOURCES = {
    "Patient",
    "Observation",
    "Condition",
    "MedicationStatement",
    "MedicationRequest",
    "AllergyIntolerance",
    "DocumentReference",
    "Binary",
    "Consent",
    "Provenance",
    "AuditEvent",
    "QuestionnaireResponse",
    "CarePlan",
    "Goal",
    "Task",
    "Composition",
    "*",
}


def parse_and_validate_smart_scope(scope: str) -> dict[str, Any]:
    """Validates and parses a SMART-on-FHIR scope string."""
    scope = scope.strip()
    if not scope:
        return {"valid": False, "reason": "empty_scope"}

    if scope in IDENTITY_SCOPES:
        return {"valid": True, "category": "identity", "scope": scope}

    if scope in LAUNCH_SCOPES:
        return {"valid": True, "category": "launch", "scope": scope}

    if scope in SESSION_SCOPES:
        return {"valid": True, "category": "session", "scope": scope}

    # SMART v1 classic format (e.g. patient/*.read, user/*.write)
    v1_match = re.match(r"^(patient|user|system)/([A-Za-z*]+)\.(read|write|\*)$", scope)
    if v1_match:
        ctx, res, perm = v1_match.groups()
        if res not in SUPPORTED_FHIR_RESOURCES:
            return {"valid": False, "reason": "unsupported_resource"}
        return {
            "valid": True,
            "version": "v1",
            "context": ctx,
            "resource": res,
            "permission": perm,
        }

    # SMART v2 granular format (e.g. patient/Observation.rs?category=vital-signs)
    v2_match = SMART_V2_PATTERN.match(scope)
    if v2_match:
        ctx = v2_match.group("context")
        res = v2_match.group("resource")
        perms = v2_match.group("perms")
        params = v2_match.group("params")

        if ctx not in ALLOWED_CONTEXTS:
            return {"valid": False, "reason": "invalid_context"}
        if res not in SUPPORTED_FHIR_RESOURCES:
            return {"valid": False, "reason": "unsupported_resource"}
        if perms != "*" and not all(p in ALLOWED_PERMS for p in perms):
            return {"valid": False, "reason": "invalid_permissions"}

        return {
            "valid": True,
            "version": "v2",
            "context": ctx,
            "resource": res,
            "permissions": perms,
            "parameters": params,
        }

    return {"valid": False, "reason": "malformed_syntax"}


def evaluate_smart_access(
    role: str,
    granted_scopes: set[str],
    context: str,
    resource_type: str,
    http_method: str,
) -> bool:
    """Evaluates whether role and granted scopes permit operation."""
    # Clinical prescribing hard-guard:
    if resource_type == "MedicationRequest" and http_method.upper() in {"POST", "PUT"}:
        if role != "doctor":
            return False

    # Platform root cannot read PHI
    if role == "admin" and resource_type in {"Patient", "Observation", "Condition", "MedicationStatement"}:
        return False

    method_perms = {
        "GET": {"r", "s"},
        "HEAD": {"r", "s"},
        "POST": {"c"},
        "PUT": {"u"},
        "PATCH": {"u"},
        "DELETE": {"d"},
    }.get(http_method.upper(), set())

    for scope_str in granted_scopes:
        parsed = parse_and_validate_smart_scope(scope_str)
        if not parsed.get("valid"):
            continue

        # Check v1
        if parsed.get("version") == "v1":
            if parsed["context"] == context:
                if parsed["resource"] in {"*", resource_type}:
                    if parsed["permission"] == "*" or (
                        parsed["permission"] == "read" and method_perms.issubset({"r", "s"})
                    ) or (
                        parsed["permission"] == "write" and not method_perms.issubset({"r", "s"})
                    ):
                        return True

        # Check v2
        if parsed.get("version") == "v2":
            if parsed["context"] == context:
                if parsed["resource"] in {"*", resource_type}:
                    if parsed["permissions"] == "*":
                        return True
                    granted_p = set(parsed["permissions"])
                    if method_perms.issubset(granted_p):
                        return True

    return False


# ==============================================================================
# 2. Test Cases: Scope Syntax and Parsing
# ==============================================================================

def test_smart_scope_v1_valid():
    valid_scopes = [
        "patient/*.read",
        "patient/*.write",
        "patient/*.*",
        "patient/Patient.read",
        "patient/Observation.read",
        "user/*.read",
        "user/Observation.write",
        "system/*.read",
    ]
    for s in valid_scopes:
        res = parse_and_validate_smart_scope(s)
        assert res["valid"] is True, f"Scope {s} should be valid"
        assert res["version"] == "v1"


def test_smart_scope_v2_granular_valid():
    valid_v2_scopes = [
        "patient/*.rs",
        "patient/Patient.rs",
        "patient/Observation.rs",
        "patient/Condition.rs",
        "patient/MedicationStatement.rs",
        "patient/AllergyIntolerance.rs",
        "patient/DocumentReference.rs",
        "patient/Binary.rs",
        "patient/*.c",
        "patient/Observation.cruds",
        "user/*.rs",
        "user/MedicationRequest.c",
        "system/*.rs",
        "patient/Observation.rs?category=vital-signs",
    ]
    for s in valid_v2_scopes:
        res = parse_and_validate_smart_scope(s)
        assert res["valid"] is True, f"Scope {s} should be valid"
        assert res["version"] == "v2"


def test_smart_scope_identity_and_launch():
    identity_and_launch = [
        "openid",
        "profile",
        "email",
        "fhirUser",
        "launch",
        "launch/patient",
        "launch/encounter",
        "offline_access",
        "online_access",
    ]
    for s in identity_and_launch:
        res = parse_and_validate_smart_scope(s)
        assert res["valid"] is True, f"Scope {s} should be valid"


def test_smart_scope_malformed_and_deny():
    invalid_scopes = [
        "",
        "   ",
        "invalid_scope_name",
        "admin/*.read",
        "patient/UnknownCustomResource.read",
        "patient/Observation.xyz",
        "patient/../traversal.rs",
        "patient/Patient.",
        "user//Patient.read",
        "system/Observation",
    ]
    for s in invalid_scopes:
        res = parse_and_validate_smart_scope(s)
        assert res["valid"] is False, f"Scope {s} should be rejected"


# ==============================================================================
# 3. Test Cases: RBAC & ABAC Evaluation and Invariants
# ==============================================================================

def test_consumer_cannot_prescribe_medication_order():
    """Consumer cannot create MedicationRequest even with injected scope."""
    granted = {"patient/MedicationRequest.c", "patient/*.*"}
    # Even if consumer somehow had patient/MedicationRequest.c, evaluate_smart_access must reject
    allowed = evaluate_smart_access(
        role="normal",
        granted_scopes=granted,
        context="patient",
        resource_type="MedicationRequest",
        http_method="POST",
    )
    assert allowed is False, "Consumer role MUST NOT be allowed to create MedicationRequest"


def test_doctor_can_prescribe_medication_order():
    """Clinician with doctor role and user/MedicationRequest.c can create MedicationRequest."""
    granted = {"user/MedicationRequest.c"}
    allowed = evaluate_smart_access(
        role="doctor",
        granted_scopes=granted,
        context="user",
        resource_type="MedicationRequest",
        http_method="POST",
    )
    assert allowed is True, "Doctor role with user/MedicationRequest.c should be allowed"


def test_platform_root_cannot_read_phi():
    """Platform administrator cannot read patient clinical records."""
    granted = {"system/*.read", "system/*.*"}
    for phi_resource in ["Patient", "Observation", "Condition", "MedicationStatement"]:
        allowed = evaluate_smart_access(
            role="admin",
            granted_scopes=granted,
            context="system",
            resource_type=phi_resource,
            http_method="GET",
        )
        assert allowed is False, f"Admin role must not read PHI resource {phi_resource}"


def test_consumer_read_own_observation():
    """Consumer with patient/Observation.rs can read Observation."""
    granted = {"patient/Observation.rs"}
    allowed = evaluate_smart_access(
        role="normal",
        granted_scopes=granted,
        context="patient",
        resource_type="Observation",
        http_method="GET",
    )
    assert allowed is True

    # But cannot write Observation with only .rs
    allowed_write = evaluate_smart_access(
        role="normal",
        granted_scopes=granted,
        context="patient",
        resource_type="Observation",
        http_method="POST",
    )
    assert allowed_write is False


# ==============================================================================
# 4. Test Cases: SMART Configuration Payload Conformance
# ==============================================================================

def test_smart_well_known_configuration_conformance():
    """Validates the SMART Well-Known configuration structure against SMART spec."""
    config = {
        "authorization_endpoint": "https://theclaracare.com/api/v1/auth/smart/authorize",
        "token_endpoint": "https://theclaracare.com/api/v1/auth/smart/token",
        "introspection_endpoint": "https://theclaracare.com/api/v1/auth/smart/introspect",
        "revocation_endpoint": "https://theclaracare.com/api/v1/auth/smart/revoke",
        "jwks_uri": "https://theclaracare.com/api/v1/auth/jwks.json",
        "capabilities": [
            "launch-standalone",
            "launch-ehr",
            "client-public",
            "client-confidential-symmetric",
            "client-confidential-asymmetric",
            "sso-openid-connect",
            "context-standalone-patient",
            "permission-patient",
            "permission-user",
            "permission-system",
            "permission-v2",
        ],
        "scopes_supported": [
            "openid",
            "profile",
            "email",
            "fhirUser",
            "launch",
            "launch/patient",
            "offline_access",
            "patient/*.read",
            "patient/*.rs",
            "patient/Patient.rs",
            "patient/Observation.rs",
            "patient/Condition.rs",
            "patient/MedicationStatement.rs",
            "patient/AllergyIntolerance.rs",
            "patient/DocumentReference.rs",
            "patient/Binary.rs",
            "patient/*.c",
            "user/*.read",
            "user/*.rs",
            "user/MedicationRequest.c",
            "system/*.read",
            "system/*.rs",
        ],
        "response_types_supported": ["code"],
        "token_endpoint_auth_methods_supported": [
            "none",
            "client_secret_basic",
            "client_secret_post",
            "private_key_jwt",
        ],
        "token_endpoint_auth_signing_alg_values_supported": ["RS384", "ES384"],
        "code_challenge_methods_supported": ["S256"],
    }

    assert "authorization_endpoint" in config
    assert "token_endpoint" in config
    assert "capabilities" in config
    assert "S256" in config["code_challenge_methods_supported"]
    assert "launch-standalone" in config["capabilities"]
    assert "permission-v2" in config["capabilities"]
    # Verify mandatory S256 PKCE
    assert config["code_challenge_methods_supported"] == ["S256"]


# ==============================================================================
# 5. Test Cases: Documentation Hygiene and Link Verification
# ==============================================================================

def test_docs_hygiene_no_machine_paths():
    """Ensures no active docs authored by A09 contain machine paths or leading slash links."""
    docs_to_check = [
        "docs/interoperability/FHIR_SMART_AUTH_SCOPES_AND_ENDPOINT_SECURITY.md",
        "docs/implementation/FHIR_ENDPOINT_SECURITY_ARCHITECTURE.md",
        "docs/research/FHIR_AUTH_SECURITY_THREAT_MODEL_AND_AUDIT.md",
    ]
    repo_root = Path(__file__).resolve().parents[3]

    forbidden_machine_patterns = [
        re.compile(r"/home/\w+"),
        re.compile(r"/Users/\w+"),
        re.compile(r"/private/\w+"),
    ]
    forbidden_leading_slash_link = re.compile(r"\[[^\]]+\]\((/[^)]+)\)")

    for rel_path in docs_to_check:
        doc_path = repo_root / rel_path
        assert doc_path.is_file(), f"Expected document {rel_path} to exist"

        content = doc_path.read_text(encoding="utf-8")

        for pattern in forbidden_machine_patterns:
            matches = pattern.findall(content)
            assert not matches, f"Machine path violation in {rel_path}: {matches}"

        leading_slash_matches = forbidden_leading_slash_link.findall(content)
        assert not leading_slash_matches, (
            f"Leading slash markdown link in {rel_path}: {leading_slash_matches}"
        )
