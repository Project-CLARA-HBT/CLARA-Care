"""Contract schema validation test for Organization & Multi-Tenant standards."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONTRACTS_DIR.parent.parent
API_SRC = REPO_ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_organization_tenant_contract_schema_structure() -> None:
    schema_path = CONTRACTS_DIR / "organization-tenant-contract.schema.json"
    assert schema_path.exists(), f"Missing schema at {schema_path}"
    schema = load_json(schema_path)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "required" in schema
    expected_required = {"schema_version", "entities", "crud_contracts", "rbac_roles"}
    assert expected_required.issubset(set(schema["required"]))

    # Verify entity schemas
    entities = schema["properties"]["entities"]["properties"]
    assert "Organization" in entities
    assert "OrganizationMember" in entities
    assert "TenantWorkspace" in entities

    org_props = entities["Organization"]["properties"]
    assert set(entities["Organization"]["required"]) == {
        "id",
        "name",
        "slug",
        "tier",
        "status",
        "created_at",
        "updated_at",
    }
    assert set(org_props["tier"]["enum"]) == {
        "free",
        "standard",
        "professional",
        "enterprise",
        "research_pilot",
    }
    assert set(org_props["status"]["enum"]) == {
        "active",
        "suspended",
        "maintenance",
        "quarantined",
        "deprovisioned",
    }

    member_props = entities["OrganizationMember"]["properties"]
    assert set(member_props["role"]["enum"]) == {
        "owner",
        "admin",
        "workspace_lead",
        "clinician",
        "researcher",
        "auditor",
        "member",
        "viewer",
    }


def test_multi_tenant_standards_schema_structure() -> None:
    schema_path = CONTRACTS_DIR / "multi-tenant-standards.schema.json"
    assert schema_path.exists(), f"Missing schema at {schema_path}"
    schema = load_json(schema_path)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "required" in schema
    expected_required = {
      "standard_version",
      "isolation_invariants",
      "header_specifications",
      "authorization_boundaries",
      "error_handling_standards",
      "telemetry_and_audit_rules",
    }
    assert expected_required.issubset(set(schema["required"]))

    # Verify anti-IDOR 404 invariant
    err_standards = schema["properties"]["error_handling_standards"]["properties"]
    assert err_standards["non_enumeration_status_code"]["const"] == 404

    # Verify telemetry rule: zero PII/PHI
    telemetry_rules = schema["properties"]["telemetry_and_audit_rules"]["properties"]
    assert telemetry_rules["pii_phi_redaction"]["const"] is True


# ==============================================================================
# End-to-End API Endpoint & Anti-IDOR Isolation Verification Tests
# ==============================================================================

@pytest.fixture(autouse=True)
def setup_test_db():
    from clara_api.db.base import Base
    from clara_api.db.session import engine, SessionLocal
    from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
    from clara_api.core.config import get_settings

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_bootstrap_admin(db, get_settings())
    yield


def test_organization_and_workspace_api_lifecycle_and_idor_protection() -> None:
    from fastapi.testclient import TestClient
    from clara_api.main import app

    client = TestClient(app)

    # 1. Login primary user (doctor role)
    login_res = client.post("/api/v1/auth/login", json={"email": "org-admin@example.com", "password": "secret"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_primary = login_res.json()["access_token"]
    headers_primary = {"Authorization": f"Bearer {token_primary}"}

    # 2. Login secondary isolated user (normal role)
    login_other = client.post("/api/v1/auth/login", json={"email": "stranger@example.com", "password": "secret"})
    assert login_other.status_code == 200
    token_stranger = login_other.json()["access_token"]
    headers_stranger = {"Authorization": f"Bearer {token_stranger}"}

    # 3. Create a new organization
    org_payload = {
        "name": "Bệnh Viện Đa Khoa An Sinh",
        "slug": "ansinh-hospital",
        "description": "Multi-specialty hospital tenant",
        "tier": "professional",
        "contact_email": "contact@ansinh.vn",
    }
    create_res = client.post("/api/v1/organizations", headers=headers_primary, json=org_payload)
    assert create_res.status_code == 201
    org = create_res.json()
    org_id = org["id"]
    assert org["slug"] == "ansinh-hospital"
    assert org["member_count"] == 1
    assert org["workspace_count"] == 1

    # 4. Duplicate slug creation fails with 409 Conflict
    dup_res = client.post("/api/v1/organizations", headers=headers_primary, json=org_payload)
    assert dup_res.status_code == 409

    # 5. Get organization details as member
    get_res = client.get(f"/api/v1/organizations/{org_id}", headers=headers_primary)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Bệnh Viện Đa Khoa An Sinh"

    # 6. Anti-IDOR: Stranger access to organization fails with 404 (non-enumeration)
    stranger_get_res = client.get(f"/api/v1/organizations/{org_id}", headers=headers_stranger)
    assert stranger_get_res.status_code == 404
    assert "không tồn tại" in stranger_get_res.json()["detail"]

    # 7. Update organization settings as owner
    patch_res = client.patch(
        f"/api/v1/organizations/{org_id}",
        headers=headers_primary,
        json={"description": "Updated medical center description", "tier": "enterprise"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["tier"] == "enterprise"

    # 8. List organization members
    members_res = client.get(f"/api/v1/organizations/{org_id}/members", headers=headers_primary)
    assert members_res.status_code == 200
    members = members_res.json()["items"]
    assert len(members) == 1
    assert members[0]["user_email"] == "org-admin@example.com"
    assert members[0]["role"] == "owner"

    # 9. Invite a new member
    invite_res = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=headers_primary,
        json={"user_email": "clinician@ansinh.vn", "role": "clinician"},
    )
    assert invite_res.status_code == 201
    invited_mem = invite_res.json()
    mem_id = invited_mem["id"]
    assert invited_mem["role"] == "clinician"

    # 10. Update member role
    role_update_res = client.patch(
        f"/api/v1/organizations/{org_id}/members/{mem_id}",
        headers=headers_primary,
        json={"role": "workspace_lead"},
    )
    assert role_update_res.status_code == 200
    assert role_update_res.json()["role"] == "workspace_lead"

    # 11. Remove invited member
    del_mem_res = client.delete(f"/api/v1/organizations/{org_id}/members/{mem_id}", headers=headers_primary)
    assert del_mem_res.status_code == 200
    assert del_mem_res.json()["status"] == "removed"

    # 12. Create collaborative tenant workspace
    ws_create_res = client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        headers=headers_primary,
        json={
            "name": "Khoa Hồi Sức Cấp Cứu (ICU)",
            "slug": "icu-ward",
            "description": "Critical care patient workspace",
            "is_restricted": True,
        },
    )
    assert ws_create_res.status_code == 201
    ws = ws_create_res.json()
    ws_id = ws["id"]
    assert ws["slug"] == "icu-ward"
    assert ws["is_restricted"] is True

    # 13. List workspaces
    ws_list_res = client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers_primary)
    assert ws_list_res.status_code == 200
    assert ws_list_res.json()["total"] >= 2  # General + ICU

    # 14. Get workspace details
    ws_get_res = client.get(f"/api/v1/organizations/{org_id}/workspaces/{ws_id}", headers=headers_primary)
    assert ws_get_res.status_code == 200
    assert ws_get_res.json()["name"] == "Khoa Hồi Sức Cấp Cứu (ICU)"

    # 15. Stranger access to workspace returns 404 (non-enumeration)
    stranger_ws_res = client.get(f"/api/v1/organizations/{org_id}/workspaces/{ws_id}", headers=headers_stranger)
    assert stranger_ws_res.status_code == 404

    # 16. Update workspace
    ws_patch_res = client.patch(
        f"/api/v1/organizations/{org_id}/workspaces/{ws_id}",
        headers=headers_primary,
        json={"name": "Khoa Cấp Cứu & Can Thiệp Tim Mạch"},
    )
    assert ws_patch_res.status_code == 200
    assert ws_patch_res.json()["name"] == "Khoa Cấp Cứu & Can Thiệp Tim Mạch"

    # 17. Archive workspace
    ws_archive_res = client.delete(f"/api/v1/organizations/{org_id}/workspaces/{ws_id}", headers=headers_primary)
    assert ws_archive_res.status_code == 200
    assert ws_archive_res.json()["status"] == "archived"

    # 18. Audit log records non-PII events
    audit_res = client.get(f"/api/v1/organizations/{org_id}/audit", headers=headers_primary)
    assert audit_res.status_code == 200
    audit_items = audit_res.json()["items"]
    assert len(audit_items) >= 4
    actions = [item["action"] for item in audit_items]
    assert "organization.create" in actions
    assert "workspace.create" in actions
    assert "workspace.archive" in actions
