"""Automated test suite for mobile org switching, deep-link intake, and multi-tenant workspace contracts.

Audits and verifies:
1. Safe mobile deep-link intake, URI parsing, and capability sanitization (non-HTTPS, foreign host, path traversal, oversized token rejection).
2. Invitation acceptance capability contracts: HTTP 410 Gone on URL path tokens, preview without consuming, header and body acceptance, duplicate/replay prevention, and recipient validation.
3. Multi-tenant workspace and organization isolation: folder, channel, note, and conversation privacy between users/tenants.
4. Cross-organization context switching: Cache-Control and Vary security headers, safe fallback with reset_required on stale/invalid headers, and anti-IDOR activation defenses.
5. Mobile API summary and org switching contracts: /api/v1/mobile/summary role scoping, session continuity during context transitions, and separation of UI presentation mode from locked server-side RBAC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyInvitation,
    PhrProfile,
    User,
    WorkspaceChannel,
    WorkspaceFolder,
    WorkspaceNote,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

APPROVED_DEEP_LINK_HOSTS = frozenset({"theclaracare.com", "www.theclaracare.com"})
APPROVED_SCHEMES = frozenset({"https", "clara"})


def _login(email: str, password: str = "secret123", role: str = "normal") -> str:
    """Helper to authenticate or auto-provision a user and return access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]


def _auth(token: str, **extra_headers: str) -> dict[str, str]:
    """Helper to construct Authorization and optional context headers."""
    return {"Authorization": f"Bearer {token}", **extra_headers}


def parse_mobile_deep_link(raw_link: str | None) -> dict[str, str | None] | None:
    """Safely parse and sanitize incoming deep links for mobile and web intake.

    Enforces invariants:
    - Rejects null, empty, or oversized URLs (>2048 chars).
    - Rejects null bytes (%00, \\x00) or carriage return injections.
    - Accepts only approved schemes (https or native clara://).
    - For HTTPS, enforces canonical host allowlist.
    - Rejects path traversal (..) and double slash sequences in path.
    - Extracts token only if length is between 8 and 512 chars.
    - Returns structured metadata dictionary, or None if invalid.
    """
    if not raw_link or len(raw_link) > 2048:
        return None

    if "%00" in raw_link or "\x00" in raw_link or "\r" in raw_link or "\n" in raw_link:
        return None

    try:
        parsed = urlparse(raw_link)
    except Exception:
        return None

    scheme = (parsed.scheme or "").lower()
    if scheme not in APPROVED_SCHEMES:
        return None

    # Host check for web links
    if scheme == "https":
        host = (parsed.netloc.split(":")[0] or "").lower()
        if host not in APPROVED_DEEP_LINK_HOSTS:
            return None

    # Path normalization & traversal defense
    raw_path = parsed.path or ""
    if ".." in raw_path or "//" in raw_path:
        return None

    # In custom schemes like clara://org/join, urlparse sets netloc="org", path="/join"
    combined_path = f"/{parsed.netloc}{raw_path}" if scheme == "clara" and parsed.netloc else raw_path

    # Normalize segments
    segments = [s for s in combined_path.strip("/").split("/") if s]

    query = parse_qs(parsed.query)
    token = None

    # Token extraction from query params
    for key in ("token", "code", "invitation_token"):
        if key in query and query[key]:
            cand = query[key][0].strip()
            if 8 <= len(cand) <= 512 and not any(c in cand for c in "<>\r\n\t\"' "):
                token = cand
                break

    # Public PHR share route shape: /phr/shared/{token}
    is_phr_share = len(segments) >= 3 and segments[0] == "phr" and segments[1] == "shared"
    if is_phr_share and not token:
        cand = segments[2].strip()
        if 8 <= len(cand) <= 512 and not any(c in cand for c in "<>\r\n\t\"' "):
            token = cand

    # Invitation route shapes: /invitations/accept, /family/invitations/accept, /org/join
    is_invitation = any(
        kw in combined_path
        for kw in (
            "invitations",
            "family/invitations",
            "org/join",
            "organization/join",
            "workspace/join",
        )
    )

    return {
        "raw_link": raw_link,
        "scheme": scheme,
        "path": combined_path,
        "is_invitation": is_invitation,
        "is_phr_share": is_phr_share,
        "token": token,
    }


# ============================================================================
# 1. Mobile Deep Link Intake and URI Sanitization Tests
# ============================================================================


class TestDeepLinkIntakeAndSanitization:
    """Verifies intake validation, parsing security, and sanitization of deep links."""

    def test_canonical_https_invitation_links_pass_validation(self) -> None:
        valid_urls = [
            "https://theclaracare.com/invitations/accept?token=inv_valid_token_12345",
            "https://www.theclaracare.com/family/invitations/accept?code=family_secret_67890",
            "https://theclaracare.com/org/join?token=org_secret_token_112233",
            "https://theclaracare.com/workspace/join?invitation_token=workspace_token_445566",
        ]
        for url in valid_urls:
            res = parse_mobile_deep_link(url)
            assert res is not None, f"Failed to parse valid URL: {url}"
            assert res["is_invitation"] is True
            assert res["token"] is not None
            assert len(res["token"]) >= 8

    def test_native_app_scheme_deep_links_pass_validation(self) -> None:
        native_urls = [
            "clara://invitations/accept?token=native_token_12345678",
            "clara://family/invitations/accept?code=native_family_code_99",
            "clara://org/join?token=native_org_join_secret",
        ]
        for url in native_urls:
            res = parse_mobile_deep_link(url)
            assert res is not None, f"Failed to parse native app link: {url}"
            assert res["scheme"] == "clara"
            assert res["is_invitation"] is True
            assert res["token"] is not None

    def test_public_phr_share_link_extraction(self) -> None:
        url = "https://theclaracare.com/phr/shared/secure_capability_share_token_887766"
        res = parse_mobile_deep_link(url)
        assert res is not None
        assert res["is_phr_share"] is True
        assert res["token"] == "secure_capability_share_token_887766"

    def test_reject_insecure_or_unapproved_schemes(self) -> None:
        insecure_urls = [
            "http://theclaracare.com/invitations/accept?token=plain_http_token",
            "javascript:alert(document.cookie)",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "file:///etc/passwd",
            "ftp://theclaracare.com/invitations/accept",
        ]
        for url in insecure_urls:
            assert parse_mobile_deep_link(url) is None, f"Should reject insecure scheme: {url}"

    def test_reject_untrusted_foreign_hosts(self) -> None:
        foreign_urls = [
            "https://evil-theclaracare.com/invitations/accept?token=phish_token_1234",
            "https://theclaracare.com.attacker.org/invitations/accept?token=spoof_token_1234",
            "https://phishing.site/org/join?token=fake_token_1234",
            "https://google.com/search?q=clara",
        ]
        for url in foreign_urls:
            assert parse_mobile_deep_link(url) is None, f"Should reject foreign host: {url}"

    def test_reject_path_traversal_and_malformed_uris(self) -> None:
        malformed = [
            "https://theclaracare.com/invitations/../../etc/passwd?token=traversal_tok",
            "https://theclaracare.com//admin/secret?token=double_slash_tok",
            "https://theclaracare.com/invitations/accept?token=%00nullbyte_injection",
            "",
            "   ",
            "not a url at all",
            "https://theclaracare.com/" + ("a" * 2100),
        ]
        for url in malformed:
            assert parse_mobile_deep_link(url) is None, f"Should reject malformed link: {url}"

    def test_reject_oversized_and_empty_tokens(self) -> None:
        too_short = "https://theclaracare.com/invitations/accept?token=short"
        res_short = parse_mobile_deep_link(too_short)
        assert res_short is not None
        assert res_short["token"] is None

        too_long = "https://theclaracare.com/invitations/accept?token=" + ("x" * 513)
        res_long = parse_mobile_deep_link(too_long)
        assert res_long is not None
        assert res_long["token"] is None


# ============================================================================
# 2. Invitation Acceptance Capability Security Contracts
# ============================================================================


class TestInvitationAcceptanceCapabilityContracts:
    """Verifies that invitation tokens are handled strictly as opaque capabilities."""

    def test_invitation_capability_never_processed_from_url_path(self) -> None:
        email = f"legacy-url-test-{uuid4().hex[:8]}@example.com"
        token = _login(email)
        headers = _auth(token)
        secret = "x" * 43

        response = client.post(
            f"/api/v1/family/invitations/{secret}/accept",
            headers=headers,
        )
        assert response.status_code == 410, f"Expected 410 Gone, got: {response.status_code}"
        assert secret not in response.text, "Secret token must NEVER be reflected in error message"
        assert "detail" in response.json()
        assert "JSON" in response.json()["detail"] or "header" in response.json()["detail"]

    def test_invitation_preview_contract_does_not_consume_or_modify_state(self) -> None:
        inviter_email = f"preview-inviter-{uuid4().hex[:8]}@example.com"
        recipient_email = f"preview-recipient-{uuid4().hex[:8]}@example.com"

        inviter_token = _login(inviter_email)
        recipient_token = _login(recipient_email)

        inviter_headers = _auth(inviter_token)
        recipient_headers = _auth(recipient_token)

        client.put(
            "/api/v1/phr/record",
            headers=inviter_headers,
            json={"full_name": "Dr. Inviter"},
        )
        client.put(
            "/api/v1/phr/record",
            headers=recipient_headers,
            json={"full_name": "Patient Recipient"},
        )

        episode = client.post(
            "/api/v1/lifemap/episodes",
            headers={**inviter_headers, "Idempotency-Key": uuid4().hex},
            json={"title": "Phục hồi"},
        )
        assert episode.status_code == 201
        episode_id = episode.json()["id"]

        create_res = client.post(
            "/api/v1/family/invitations",
            headers=inviter_headers,
            json={
                "recipient_email": recipient_email,
                "scope": {
                    "object_type": "episode",
                    "object_id": episode_id,
                    "allowed_actions": ["view"],
                },
                "purpose": "care_coordination",
                "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
        )
        assert create_res.status_code == 201, create_res.text
        invitation_data = create_res.json()
        raw_token = invitation_data["token"]
        invitation_id = invitation_data["id"]

        preview_body_res = client.post(
            "/api/v1/family/invitations/preview",
            headers=recipient_headers,
            json={"token": raw_token},
        )
        assert preview_body_res.status_code == 200, preview_body_res.text
        preview_body = preview_body_res.json()
        assert preview_body["object_type"] == "episode"
        assert preview_body["allowed_actions"] == ["view"]
        assert preview_body["purpose"] == "care_coordination"

        preview_header_res = client.post(
            "/api/v1/family/invitations/preview",
            headers=_auth(recipient_token, **{"X-Family-Invitation-Token": raw_token}),
        )
        assert preview_header_res.status_code == 200, preview_header_res.text

        with SessionLocal() as db:
            inv = db.execute(
                select(FamilyInvitation).where(FamilyInvitation.public_id == invitation_id)
            ).scalar_one()
            assert inv.accepted_at is None
            assert inv.revoked_at is None

    def test_invitation_acceptance_and_replay_prevention(self) -> None:
        inviter_email = f"accept-inviter-{uuid4().hex[:8]}@example.com"
        recipient_email = f"accept-recipient-{uuid4().hex[:8]}@example.com"

        inviter_token = _login(inviter_email)
        recipient_token = _login(recipient_email)

        inviter_headers = _auth(inviter_token)
        recipient_headers = _auth(recipient_token)

        client.put(
            "/api/v1/phr/record",
            headers=inviter_headers,
            json={"full_name": "Inviter A"},
        )
        client.put(
            "/api/v1/phr/record",
            headers=recipient_headers,
            json={"full_name": "Recipient B"},
        )

        episode = client.post(
            "/api/v1/lifemap/episodes",
            headers={**inviter_headers, "Idempotency-Key": uuid4().hex},
            json={"title": "Theo dõi điều trị"},
        )
        assert episode.status_code == 201
        episode_id = episode.json()["id"]

        create_res = client.post(
            "/api/v1/family/invitations",
            headers=inviter_headers,
            json={
                "recipient_email": recipient_email,
                "scope": {
                    "object_type": "episode",
                    "object_id": episode_id,
                    "allowed_actions": ["view"],
                },
                "purpose": "care_coordination",
                "expires_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            },
        )
        assert create_res.status_code == 201
        raw_token = create_res.json()["token"]

        accept_res = client.post(
            "/api/v1/family/invitations/accept",
            headers=recipient_headers,
            json={"token": raw_token},
        )
        assert accept_res.status_code == 201, accept_res.text
        grant = accept_res.json()
        assert "id" in grant
        assert grant["purpose"] == "care_coordination"
        assert grant["object_type"] == "episode"
        assert grant["allowed_actions"] == ["view"]

        # Re-accepting with the same recipient returns the existing grant (idempotent, no duplicates)
        repeat_res = client.post(
            "/api/v1/family/invitations/accept",
            headers=recipient_headers,
            json={"token": raw_token},
        )
        assert repeat_res.status_code == 201
        assert repeat_res.json()["id"] == grant["id"]

    def test_invitation_wrong_recipient_fails_closed(self) -> None:
        inviter_email = f"bound-inviter-{uuid4().hex[:8]}@example.com"
        intended_email = f"intended-recipient-{uuid4().hex[:8]}@example.com"
        impostor_email = f"impostor-{uuid4().hex[:8]}@example.com"

        inviter_token = _login(inviter_email)
        _login(intended_email)
        impostor_token = _login(impostor_email)

        inviter_headers = _auth(inviter_token)
        impostor_headers = _auth(impostor_token)

        client.put(
            "/api/v1/phr/record",
            headers=inviter_headers,
            json={"full_name": "Bound Inviter"},
        )

        episode = client.post(
            "/api/v1/lifemap/episodes",
            headers={**inviter_headers, "Idempotency-Key": uuid4().hex},
            json={"title": "Chăm sóc gia đình"},
        )
        assert episode.status_code == 201
        episode_id = episode.json()["id"]

        create_res = client.post(
            "/api/v1/family/invitations",
            headers=inviter_headers,
            json={
                "recipient_email": intended_email,
                "scope": {
                    "object_type": "episode",
                    "object_id": episode_id,
                    "allowed_actions": ["view"],
                },
                "purpose": "care_coordination",
                "expires_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            },
        )
        assert create_res.status_code == 201
        raw_token = create_res.json()["token"]

        impostor_res = client.post(
            "/api/v1/family/invitations/accept",
            headers=impostor_headers,
            json={"token": raw_token},
        )
        assert impostor_res.status_code in (404, 403, 400), (
            f"Mismatched recipient should be rejected, got: {impostor_res.status_code}"
        )

        impostor_preview = client.post(
            "/api/v1/family/invitations/preview",
            headers=impostor_headers,
            json={"token": raw_token},
        )
        assert impostor_preview.status_code in (404, 403, 400)


# ============================================================================
# 3. Multi-Tenant Workspace and Organization Isolation Tests
# ============================================================================


class TestMultiTenantWorkspaceAndOrgIsolation:
    """Verifies that workspace entities and organization resources are strictly isolated."""

    def test_workspace_folders_and_channels_isolated_per_tenant_user(self) -> None:
        user_a = f"workspace-tenant-a-{uuid4().hex[:8]}@example.com"
        user_b = f"workspace-tenant-b-{uuid4().hex[:8]}@example.com"

        token_a = _login(user_a)
        token_b = _login(user_b)

        headers_a = _auth(token_a)
        headers_b = _auth(token_b)

        create_folder_res = client.post(
            "/api/v1/workspace/folders",
            headers=headers_a,
            json={"name": "Org A Confidential Cases", "description": "Strictly tenant A"},
        )
        assert create_folder_res.status_code == 200
        folder_id = create_folder_res.json()["id"]

        create_channel_res = client.post(
            "/api/v1/workspace/channels",
            headers=headers_a,
            json={"name": "Org A Internal Discussion"},
        )
        assert create_channel_res.status_code == 200
        channel_id = create_channel_res.json()["id"]

        list_b_folders = client.get("/api/v1/workspace/folders", headers=headers_b)
        assert list_b_folders.status_code == 200
        assert all(f["id"] != folder_id for f in list_b_folders.json())

        list_b_channels = client.get("/api/v1/workspace/channels", headers=headers_b)
        assert list_b_channels.status_code == 200
        assert all(c["id"] != channel_id for c in list_b_channels.json())

        patch_res = client.patch(
            f"/api/v1/workspace/folders/{folder_id}",
            headers=headers_b,
            json={"name": "Hacked Folder"},
        )
        assert patch_res.status_code == 404, (
            f"Cross-tenant folder patch must 404, got: {patch_res.status_code}"
        )

        del_res = client.delete(
            f"/api/v1/workspace/channels/{channel_id}",
            headers=headers_b,
        )
        assert del_res.status_code == 404, (
            f"Cross-tenant channel delete must 404, got: {del_res.status_code}"
        )

    def test_workspace_notes_cross_tenant_isolation(self) -> None:
        user_a = f"notes-tenant-a-{uuid4().hex[:8]}@example.com"
        user_b = f"notes-tenant-b-{uuid4().hex[:8]}@example.com"

        token_a = _login(user_a)
        token_b = _login(user_b)

        headers_a = _auth(token_a)
        headers_b = _auth(token_b)

        create_note = client.post(
            "/api/v1/workspace/notes",
            headers=headers_a,
            json={
                "title": "Private Clinical Protocol",
                "content": "Secret patient guidance",
                "tags": ["clinical", "tenant_a"],
            },
        )
        assert create_note.status_code == 200
        note_id = create_note.json()["id"]

        list_b = client.get("/api/v1/workspace/notes", headers=headers_b)
        assert list_b.status_code == 200
        assert all(n["id"] != note_id for n in list_b.json())

        patch_b = client.patch(
            f"/api/v1/workspace/notes/{note_id}",
            headers=headers_b,
            json={"title": "Unauthorized Overwrite"},
        )
        assert patch_b.status_code == 404

        del_b = client.delete(f"/api/v1/workspace/notes/{note_id}", headers=headers_b)
        assert del_b.status_code == 404

    def test_workspace_conversation_share_revocation_requires_owner(self) -> None:
        user_a = f"share-owner-{uuid4().hex[:8]}@example.com"
        user_b = f"share-attacker-{uuid4().hex[:8]}@example.com"

        token_a = _login(user_a)
        token_b = _login(user_b)

        headers_a = _auth(token_a)
        headers_b = _auth(token_b)

        revoke_unowned = client.delete(
            "/api/v1/workspace/conversations/999999/share",
            headers=headers_b,
        )
        assert revoke_unowned.status_code in (404, 403)


# ============================================================================
# 4. Cross-Organization Context and Switching Tests
# ============================================================================


class TestCrossOrganizationContextAndSwitching:
    """Verifies organization/profile context header handling, cache poisoning defenses, and IDOR prevention."""

    def test_context_resolution_security_and_cache_headers(self) -> None:
        email = f"context-user-{uuid4().hex[:8]}@example.com"
        token = _login(email)
        headers = _auth(token)

        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Context Testing User"},
        )

        res = client.get("/api/v1/profiles/context", headers=headers)
        assert res.status_code == 200

        # Anti-cache-poisoning headers are mandatory for multi-tenant and context switching
        cache_control = res.headers.get("cache-control", "").lower()
        assert "no-store" in cache_control, f"Expected no-store in Cache-Control: {cache_control}"
        assert "private" in cache_control, f"Expected private in Cache-Control: {cache_control}"

        vary = res.headers.get("vary", "")
        assert "Authorization" in vary, f"Expected Authorization in Vary header: {vary}"
        assert "X-CLARA-Profile-Context" in vary or "Context" in vary

    def test_stale_or_invalid_context_header_resets_safely(self) -> None:
        email = f"stale-context-{uuid4().hex[:8]}@example.com"
        token = _login(email)
        headers = _auth(token)

        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Stale Context User"},
        )

        stale_headers = _auth(token, **{"X-CLARA-Profile-Context": "non-existent-or-foreign-org"})
        res = client.get("/api/v1/profiles/context", headers=stale_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["reset_required"] is True
        assert body["active_kind"] == "self"
        assert body["active_profile_id"] is not None

    def test_unauthorized_context_activation_idor_blocked(self) -> None:
        user_a = f"idor-target-{uuid4().hex[:8]}@example.com"
        user_b = f"idor-attacker-{uuid4().hex[:8]}@example.com"

        token_a = _login(user_a)
        token_b = _login(user_b)

        headers_a = _auth(token_a)
        headers_b = _auth(token_b)

        client.put(
            "/api/v1/phr/record",
            headers=headers_a,
            json={"full_name": "Target Org Account"},
        )
        context_a = client.get("/api/v1/profiles/context", headers=headers_a).json()
        target_profile_id = context_a["active_profile_id"]

        idor_res = client.post(
            f"/api/v1/profiles/{target_profile_id}/activate",
            headers=headers_b,
        )
        assert idor_res.status_code == 404, (
            f"Unauthorized profile activation must return 404, got: {idor_res.status_code}"
        )


# ============================================================================
# 5. Mobile API Summary and Organization Switching Contracts
# ============================================================================


class TestMobileOrgSwitchingAndSummaryContracts:
    """Verifies mobile API summary contracts, role scoping, and presentation mode separation."""

    def test_mobile_summary_authenticated_structure(self) -> None:
        email = f"mobile-normal-{uuid4().hex[:8]}@example.com"
        token = _login(email, role="normal")
        headers = _auth(token)

        res = client.get("/api/v1/mobile/summary", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["role"] == "normal"
        assert data["api_health"]["status"] == "ok"
        assert data["api_health"]["endpoint"] == "/api/v1/health"
        assert isinstance(data["quick_links"], dict)
        assert isinstance(data["feature_flags"], dict)
        assert datetime.fromisoformat(data["last_updated"]).tzinfo is not None

    def test_mobile_summary_unauthenticated_fails_closed(self) -> None:
        client.cookies.clear()
        res = client.get("/api/v1/mobile/summary")
        assert res.status_code == 401, f"Expected 401 for missing auth, got: {res.status_code}"

    def test_presentation_mode_does_not_mutate_backend_rbac(self) -> None:
        """Verify safety invariant: presentation modes modify only UI layout and never bypass server RBAC."""
        normal_email = f"normal-user-rbac-{uuid4().hex[:8]}@example.com"
        normal_token = _login(normal_email, role="normal")

        # Attempt to access doctor/researcher/admin routes while passing clinical presentation context
        pretend_headers = _auth(
            normal_token,
            **{
                "X-CLARA-Presentation-Mode": "clinical",
                "X-CLARA-Org-Context": "hospital-bach-mai",
            },
        )

        res_control = client.get("/api/v1/system/control-tower/config", headers=pretend_headers)
        assert res_control.status_code == 403, (
            f"Normal user accessing doctor route must 403, got: {res_control.status_code}"
        )

        res_compliance = client.get("/api/v1/compliance/records", headers=pretend_headers)
        assert res_compliance.status_code == 403, (
            f"Normal user accessing admin compliance records must 403, got: {res_compliance.status_code}"
        )

        res_metrics = client.get("/api/v1/system/metrics", headers=pretend_headers)
        assert res_metrics.status_code == 403, (
            f"Normal user accessing system metrics must 403, got: {res_metrics.status_code}"
        )

    def test_mobile_session_continuity_during_context_switch(self) -> None:
        email = f"session-continuity-{uuid4().hex[:8]}@example.com"
        token = _login(email)
        headers = _auth(token)

        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Continuity User"},
        )

        ctx_res1 = client.get("/api/v1/profiles/context", headers=headers)
        assert ctx_res1.status_code == 200
        profile_id = ctx_res1.json()["active_profile_id"]

        act_res = client.post(f"/api/v1/profiles/{profile_id}/activate", headers=headers)
        assert act_res.status_code == 200

        # Existing access token must remain fully valid
        summary_res = client.get("/api/v1/mobile/summary", headers=headers)
        assert summary_res.status_code == 200
        assert summary_res.json()["role"] == "normal"
