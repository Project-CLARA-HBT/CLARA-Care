"""Automated security negative-test suite for CLARA Care (PH03_A09).

Audits and validates comprehensive negative test vectors:
1. Expired JWT tokens (access + refresh)
2. Wrong signature & cryptographic tampering (forged key, payload tampering, 'none' alg, issuer/type mismatch)
3. Malformed authorization header (missing prefix, invalid schemes, truncated segments, transport anti-downgrade)
4. Cross-tenant / cross-user IDOR (object-level isolation: folders, channels, cases, knowledge sources; RBAC vertical checks)
5. Replay of revoked tokens (logout denylist, single-use DB consumption, rotation replay detection, zero-PII telemetry)

Standard: RFC 7519, RFC 7235, OWASP API Security Top 10 (API1:2023, API2:2023).
Invariant: Fail-closed; zero PII leakage; no credential transport downgrade.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clara_api.core.config import get_settings
from clara_api.core.rbac import (
    AuthContextMiddleware,
    _extract_access_token,
    _has_bearer_scheme,
    _reject_if_revoked,
    extract_bearer_token,
    get_current_token,
    has_valid_explicit_bearer_token,
    require_roles,
)
from clara_api.core.redis_security_store import RedisSecurityStore
from clara_api.core.security import (
    TokenPayload,
    _decode_with_keys,
    _signing_keys,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from clara_api.core.session_security import SessionSecurity, session_security
from clara_api.db.models import CouncilCase, KnowledgeSource, WorkspaceChannel, WorkspaceFolder


# ==============================================================================
# In-Memory Security Mock Store for SessionSecurity Isolation
# ==============================================================================

class InMemorySecurityStore:
    """Deterministic in-memory double of RedisSecurityStore for hermetic negative testing."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._ttls: dict[str, float] = {}
        self._counters: dict[str, int] = {}

    def set_lock(self, key: str, *, ttl_seconds: int) -> bool:
        self._store[key] = b"1"
        self._ttls[key] = time.time() + max(1, ttl_seconds)
        return True

    def get_ttl(self, key: str) -> int | None:
        if key not in self._ttls:
            return None
        remaining = int(self._ttls[key] - time.time())
        if remaining <= 0:
            self._store.pop(key, None)
            self._ttls.pop(key, None)
            return 0
        return remaining

    def incr_with_ttl(self, key: str, *, ttl_seconds: int) -> tuple[int, int] | None:
        count = self._counters.get(key, 0) + 1
        self._counters[key] = count
        self._ttls[key] = time.time() + max(1, ttl_seconds)
        return count, max(1, ttl_seconds)

    def available(self) -> bool:
        return True


# ==============================================================================
# Test Suite 1: Expired JWT Vectors (VEC-SEC-EXP-*)
# ==============================================================================

class TestExpiredJWTVectors:
    """Rejection coverage for expired access and refresh tokens."""

    def test_vec_sec_exp_01_access_token_expired_in_past(self) -> None:
        """Access token with exp timestamp in the past is rejected with 401."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=2)
        payload = {
            "sub": "victim@example.com",
            "role": "normal",
            "exp": past,
            "iat": past - timedelta(minutes=15),
            "iss": settings.jwt_issuer,
            "jti": "exp-test-jti-01",
            "typ": "access",
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "hết hạn" in exc_info.value.detail

    def test_vec_sec_exp_02_access_token_expired_one_second_ago(self) -> None:
        """Zero-tolerance expiration: token expired by 1 second is strictly rejected."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        past = now - timedelta(seconds=1)
        payload = {
            "sub": "victim@example.com",
            "role": "normal",
            "exp": past,
            "iat": past - timedelta(minutes=15),
            "iss": settings.jwt_issuer,
            "jti": "exp-test-jti-02",
            "typ": "access",
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_exp_03_refresh_token_expired(self) -> None:
        """Refresh token with past exp claim is rejected with 401."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        past = now - timedelta(days=1)
        payload = {
            "sub": "victim@example.com",
            "role": "normal",
            "exp": past,
            "iat": past - timedelta(days=7),
            "iss": settings.jwt_issuer,
            "jti": "exp-test-jti-03",
            "typ": "refresh",
        }
        expired_refresh = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(expired_refresh)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Refresh token không hợp lệ hoặc đã hết hạn" in exc_info.value.detail

    def test_vec_sec_exp_04_positive_control_valid_token_succeeds(self) -> None:
        """Control: unexpired token resolves cleanly with sub and role."""
        token = create_access_token("alice@example.com", "doctor")
        decoded = decode_access_token(token)
        assert decoded.sub == "alice@example.com"
        assert decoded.role == "doctor"
        assert decoded.get("typ") == "access"


# ==============================================================================
# Test Suite 2: Wrong Signature & Cryptographic Tampering (VEC-SEC-SIG-*)
# ==============================================================================

class TestWrongSignatureVectors:
    """Rejection coverage for cryptographic tampering, key mismatch, and alg confusion."""

    def test_vec_sec_sig_01_forged_secret_key(self) -> None:
        """Token signed with attacker-controlled HMAC secret is rejected."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        payload = {
            "sub": "admin@clara.local",
            "role": "admin",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "iss": settings.jwt_issuer,
            "jti": "sig-forged-01",
            "typ": "access",
        }
        forged_token = jwt.encode(payload, "malicious-attacker-secret-key-32b", algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(forged_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_sig_02_payload_tampering_role_escalation(self) -> None:
        """Modifying payload bytes while keeping signature yields invalid signature error."""
        token = create_access_token("normal@example.com", "normal")
        header_b64, payload_b64, sig_b64 = token.split(".")

        # Tamper payload: change role from normal to admin
        import base64
        rem = len(payload_b64) % 4
        padded = payload_b64 + ("=" * (4 - rem) if rem else "")
        raw_json = base64.urlsafe_b64decode(padded.encode()).decode()
        data = json.loads(raw_json)
        data["role"] = "admin"
        tampered_json = json.dumps(data, separators=(",", ":"))
        tampered_b64 = base64.urlsafe_b64encode(tampered_json.encode()).decode().rstrip("=")

        tampered_token = f"{header_b64}.{tampered_b64}.{sig_b64}"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(tampered_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_sig_03_none_algorithm_attack(self) -> None:
        """Token with alg='none' header must be strictly rejected (CVE-2015-9235 defense)."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        payload = {
            "sub": "admin@clara.local",
            "role": "admin",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp()),
            "iss": settings.jwt_issuer,
            "jti": "none-alg-01",
            "typ": "access",
        }
        import base64
        header_json = json.dumps({"alg": "none", "typ": "JWT"}).encode()
        payload_json = json.dumps(payload).encode()
        h_b64 = base64.urlsafe_b64encode(header_json).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(payload_json).decode().rstrip("=")
        none_token = f"{h_b64}.{p_b64}."

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(none_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_sig_04_issuer_mismatch(self) -> None:
        """Token with unauthorized issuer is rejected even with valid signature."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        payload = {
            "sub": "alice@example.com",
            "role": "normal",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "iss": "rogue-auth-server.example.org",
            "jti": "iss-mismatch-01",
            "typ": "access",
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_sig_05_token_type_confusion_cross_surface(self) -> None:
        """Presenting refresh token to access-token endpoint or vice-versa is rejected."""
        refresh_token = create_refresh_token("alice@example.com", "normal")
        access_token = create_access_token("alice@example.com", "normal")

        # 1. Refresh token passed to access-token decoder
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(refresh_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

        # 2. Access token passed to refresh-token decoder
        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(access_token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_sig_06_retired_signing_key_rejection(self) -> None:
        """Token signed with old key after retirement window closes is rejected."""
        settings = get_settings()
        now = datetime.now(tz=UTC)
        retired_secret = "retired-previous-key-123456789012"
        payload = {
            "sub": "alice@example.com",
            "role": "normal",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "iss": settings.jwt_issuer,
            "jti": "retired-key-01",
            "typ": "access",
        }
        token = jwt.encode(payload, retired_secret, algorithm=settings.jwt_algorithm)

        # Verification fails because retired_secret is not in candidate signing keys
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# Test Suite 3: Malformed Authorization Header & Transport Security (VEC-SEC-HDR-*)
# ==============================================================================

class TestMalformedHeaderVectors:
    """Header parsing, scheme compliance, and anti-downgrade transport invariants."""

    def test_vec_sec_hdr_01_missing_authorization_header(self) -> None:
        """Request without Authorization header returns None and fails scheme test."""
        scope = {"type": "http", "headers": []}
        request = Request(scope)
        assert _has_bearer_scheme(request) is False
        assert extract_bearer_token(request) is None

    def test_vec_sec_hdr_02_empty_or_whitespace_header(self) -> None:
        """Empty or whitespace Authorization header is rejected."""
        for raw in [b"", b"   ", b"\t"]:
            scope = {"type": "http", "headers": [(b"authorization", raw)]}
            request = Request(scope)
            assert _has_bearer_scheme(request) is False
            assert extract_bearer_token(request) is None

    def test_vec_sec_hdr_03_missing_bearer_scheme_prefix(self) -> None:
        """Raw JWT without 'Bearer ' scheme prefix fails scheme extraction."""
        token = create_access_token("alice@example.com", "normal")
        scope = {"type": "http", "headers": [(b"authorization", token.encode())]}
        request = Request(scope)
        assert _has_bearer_scheme(request) is False
        assert extract_bearer_token(request) is None

    def test_vec_sec_hdr_04_unsupported_auth_schemes(self) -> None:
        """Schemes like Basic, Digest, or Token are strictly rejected."""
        for scheme in ["Basic", "Token", "OAuth", "BearerXYZ"]:
            header_val = f"{scheme} some-credentials".encode()
            scope = {"type": "http", "headers": [(b"authorization", header_val)]}
            request = Request(scope)
            assert _has_bearer_scheme(request) is False
            assert extract_bearer_token(request) is None

    def test_vec_sec_hdr_05_case_insensitive_bearer_scheme_rfc7235(self) -> None:
        """RFC 7235: 'bearer', 'BEARER', 'Bearer' are recognized by parser."""
        token = "valid-token-string"
        for scheme in ["bearer", "BEARER", "Bearer", "bEaReR"]:
            header_val = f"{scheme} {token}".encode()
            scope = {"type": "http", "headers": [(b"authorization", header_val)]}
            request = Request(scope)
            assert _has_bearer_scheme(request) is True
            assert extract_bearer_token(request) == token

    def test_vec_sec_hdr_06_truncated_jwt_segments(self) -> None:
        """JWT with 1 or 2 segments fails fast during decode."""
        for malformed in ["onlyonepart", "partone.parttwo", "a.b.c.d.e"]:
            with pytest.raises(HTTPException) as exc_info:
                decode_access_token(malformed)
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_hdr_07_corrupted_base64_payload(self) -> None:
        """JWT containing invalid base64 characters fails decoding."""
        malformed = "eyJhbGciOiJIUzI1NiJ9.!!!NOT-BASE-64!!!.invalid-signature"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(malformed)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_vec_sec_hdr_08_transport_anti_downgrade_invariant(self) -> None:
        """CRITICAL INVARIANT: Explicit Bearer header owns authentication.

        If a request carries both a valid cookie session AND a malformed or
        invalid Bearer header, the server must NEVER downgrade to the cookie session.
        Authentication MUST fail closed with 401, and CSRF exemption must be False.
        """
        valid_token = create_access_token("alice@example.com", "normal")
        settings = get_settings()
        cookie_header = f"{settings.auth_cookie_access_name}={valid_token}".encode()

        # Adversary sends valid cookie session + malformed Bearer
        scope = {
            "type": "http",
            "headers": [
                (b"cookie", cookie_header),
                (b"authorization", b"Bearer malformed-invalid-jwt"),
            ],
        }
        request = Request(scope)

        # 1. Bearer scheme is explicitly detected
        assert _has_bearer_scheme(request) is True

        # 2. _extract_access_token chooses the explicit Bearer header, NOT the cookie
        extracted = _extract_access_token(request)
        assert extracted == "malformed-invalid-jwt"

        # 3. has_valid_explicit_bearer_token is False (cannot bypass CSRF)
        assert has_valid_explicit_bearer_token(request) is False


# ==============================================================================
# Test Suite 4: Cross-Tenant & Object-Level IDOR Vectors (VEC-SEC-IDR-*)
# ==============================================================================

class TestCrossTenantIDORVectors:
    """Rejection coverage for horizontal and vertical IDOR vulnerabilities."""

    @pytest.fixture
    def db_session(self) -> Session:
        """In-memory SQLite session with owner-scoped entity tables."""
        engine = create_engine("sqlite:///:memory:")
        WorkspaceFolder.__table__.create(engine)
        WorkspaceChannel.__table__.create(engine)
        CouncilCase.__table__.create(engine)
        KnowledgeSource.__table__.create(engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        yield session
        session.close()

    def test_vec_sec_idr_01_workspace_folder_horizontal_idor_prevention(self, db_session: Session) -> None:
        """User B (same role 'normal') cannot access User A's workspace folder (404 Not Found)."""
        from clara_api.api.v1.endpoints.workspace import _get_owned_folder

        user_a_id = 101
        user_b_id = 102

        folder_a = WorkspaceFolder(
            user_id=user_a_id,
            name="Confidential Medical Records A",
            slug="confidential-a",
            description="Patient A private notes",
            color="red",
            icon="lock",
            sort_order=0,
        )
        db_session.add(folder_a)
        db_session.commit()
        db_session.refresh(folder_a)

        # Positive control: Owner user A accesses folder
        owned = _get_owned_folder(db_session, user_id=user_a_id, folder_id=folder_a.id)
        assert owned.id == folder_a.id

        # Negative vector: User B attempts to access User A's folder
        with pytest.raises(HTTPException) as exc_info:
            _get_owned_folder(db_session, user_id=user_b_id, folder_id=folder_a.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Folder không tồn tại" in exc_info.value.detail

    def test_vec_sec_idr_02_workspace_channel_horizontal_idor_prevention(self, db_session: Session) -> None:
        """User B cannot access User A's workspace channel (404 Not Found)."""
        from clara_api.api.v1.endpoints.workspace import _get_owned_channel

        user_a_id = 201
        user_b_id = 202

        channel_a = WorkspaceChannel(
            user_id=user_a_id,
            name="Private Clinical Channel",
            slug="private-channel",
            description="",
            color="blue",
            icon="chat",
            sort_order=0,
        )
        db_session.add(channel_a)
        db_session.commit()
        db_session.refresh(channel_a)

        # Positive control
        assert _get_owned_channel(db_session, user_id=user_a_id, channel_id=channel_a.id).id == channel_a.id

        # Negative vector
        with pytest.raises(HTTPException) as exc_info:
            _get_owned_channel(db_session, user_id=user_b_id, channel_id=channel_a.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_vec_sec_idr_03_council_case_clinician_cross_access_prevention(self, db_session: Session) -> None:
        """Doctor B (same role 'doctor') cannot access Doctor A's council case (404 Not Found)."""
        from clara_api.api.v1.endpoints.council import _get_owned_case

        doctor_a_id = 301
        doctor_b_id = 302

        case_a = CouncilCase(
            user_id=doctor_a_id,
            title="Complex Oncology Review",
            status="draft",
            transcript="Patient biopsy findings",
        )
        db_session.add(case_a)
        db_session.commit()
        db_session.refresh(case_a)

        # Positive control
        assert _get_owned_case(db_session, user_id=doctor_a_id, case_id=case_a.id).id == case_a.id

        # Negative vector: Doctor B tries to access Doctor A's case
        with pytest.raises(HTTPException) as exc_info:
            _get_owned_case(db_session, user_id=doctor_b_id, case_id=case_a.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_vec_sec_idr_04_research_knowledge_source_isolation(self, db_session: Session) -> None:
        """Researcher B cannot access Researcher A's knowledge source (404 Not Found)."""
        from clara_api.api.v1.endpoints.research import _get_owned_source

        researcher_a_id = 401
        researcher_b_id = 402

        source_a = KnowledgeSource(
            owner_user_id=researcher_a_id,
            name="Proprietary Drug Trial Data",
            description="Phase III clinical data",
        )
        db_session.add(source_a)
        db_session.commit()
        db_session.refresh(source_a)

        # Positive control
        assert _get_owned_source(db_session, source_id=source_a.id, owner_user_id=researcher_a_id).id == source_a.id

        # Negative vector
        with pytest.raises(HTTPException) as exc_info:
            _get_owned_source(db_session, source_id=source_a.id, owner_user_id=researcher_b_id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_vec_sec_idr_05_vertical_privilege_escalation_normal_to_doctor(self) -> None:
        """Role gate: 'normal' role caller on clinician surface raises 403 Forbidden."""
        checker = require_roles("doctor")
        normal_payload = TokenPayload({"sub": "patient@clara.local", "role": "normal"})

        with pytest.raises(HTTPException) as exc_info:
            await checker(normal_payload)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Không đủ quyền truy cập" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_vec_sec_idr_06_vertical_privilege_escalation_doctor_to_admin(self) -> None:
        """Role gate: 'doctor' role caller on admin surface raises 403 Forbidden."""
        checker = require_roles("admin")
        doctor_payload = TokenPayload({"sub": "dr.smith@clara.local", "role": "doctor"})

        with pytest.raises(HTTPException) as exc_info:
            await checker(doctor_payload)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_vec_sec_idr_07_admin_implicit_access_invariant(self) -> None:
        """Admin has implicit access to all role-gated surfaces."""
        checker = require_roles("doctor", "researcher")
        admin_payload = TokenPayload({"sub": "admin@clara.local", "role": "admin"})

        result = await checker(admin_payload)
        assert result.role == "admin"


# ==============================================================================
# Test Suite 5: Replay of Revoked Tokens & Zero-PII Telemetry (VEC-SEC-REV-*)
# ==============================================================================

class TestRevokedTokenReplayVectors:
    """Rejection coverage for replayed access and refresh tokens, plus no-PII telemetry."""

    @pytest.fixture
    def mock_security(self, monkeypatch) -> SessionSecurity:
        """Instantiate SessionSecurity backed by in-memory mock store with hardening enabled."""
        store = InMemorySecurityStore()
        sec = SessionSecurity(store=store)  # type: ignore[arg-type]
        monkeypatch.setenv("HARDENING_TOKEN_DENYLIST_ENABLED", "true")
        monkeypatch.setenv("HARDENING_REFRESH_ROTATION_ENABLED", "true")
        get_settings.cache_clear()
        return sec

    def test_vec_sec_rev_01_replay_of_logged_out_access_token(self, mock_security: SessionSecurity, monkeypatch) -> None:
        """Access token revoked at logout is rejected on subsequent requests (401 Unauthorized)."""
        monkeypatch.setattr("clara_api.core.rbac.session_security", mock_security)

        token = create_access_token("alice@example.com", "normal")
        payload = decode_access_token(token)
        jti = payload.get("jti")
        assert jti

        # Positive control: before revocation, token is valid
        assert _reject_if_revoked(payload).sub == "alice@example.com"

        # Simulate logout revocation
        mock_security.revoke(jti, ttl_seconds=3600)
        assert mock_security.is_revoked(jti) is True

        # Negative vector: replay of revoked token
        with pytest.raises(HTTPException) as exc_info:
            _reject_if_revoked(payload)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token đã bị thu hồi" in exc_info.value.detail

    def test_vec_sec_rev_02_refresh_rotation_replay_detection(self, mock_security: SessionSecurity) -> None:
        """Replay of an already-rotated refresh token is detected and blocked."""
        old_jti = "initial-refresh-jti-01"
        subject = "alice@example.com"
        role = "normal"

        # Rotate token
        new_token, new_jti = mock_security.rotate_refresh(old_jti, subject, role)
        assert new_jti != old_jti

        # Invariant 1: Old jti is marked as rotated
        assert mock_security.is_refresh_reused(old_jti) is True

        # Invariant 2: Old jti is also denylisted
        assert mock_security.is_revoked(old_jti) is True

        # Invariant 3: New jti is clean (not reused, not revoked)
        assert mock_security.is_refresh_reused(new_jti) is False
        assert mock_security.is_revoked(new_jti) is False

    def test_vec_sec_rev_03_zero_pii_security_telemetry_invariant(
        self, mock_security: SessionSecurity, caplog: pytest.LogCaptureFixture
    ) -> None:
        """NO-PII INVARIANT: Replay events log ONLY sha256 digests and counters.

        Zero usernames, emails, patient IDs, or raw tokens in logs or Redis keys.
        """
        raw_jti = "sensitive-token-id-12345"
        expected_digest = hashlib.sha256(raw_jti.encode("utf-8")).hexdigest()

        with caplog.at_level(logging.WARNING):
            mock_security.record_reuse(raw_jti)

        # 1. Verify internal Redis key contains ONLY hashed digest
        key = mock_security._key("jti:deny", raw_jti)
        assert expected_digest in key
        assert raw_jti not in key

        # 2. Verify log records contains no PII
        assert len(caplog.records) > 0
        record = caplog.records[-1]
        extra = getattr(record, "extra", {}) or record.__dict__
        assert extra.get("jti_digest") == expected_digest
        assert "alice" not in record.message
        assert raw_jti not in record.message


# ==============================================================================
# Test Suite 6: End-to-End HTTP Middleware Pipeline Integration
# ==============================================================================

class TestHTTPPipelineIntegration:
    """Full HTTP pipeline tests combining AuthContextMiddleware and FastAPI dependencies."""

    @pytest.fixture
    def test_app(self) -> FastAPI:
        app = FastAPI(title="Negative Security Pipeline Test App")
        app.add_middleware(AuthContextMiddleware)

        @app.get("/api/v1/user/profile")
        def user_profile(token: TokenPayload = Depends(get_current_token)):
            return {"user": token.sub, "role": token.role}

        @app.get("/api/v1/doctor/clinical-notes")
        def clinical_notes(token: TokenPayload = Depends(require_roles("doctor"))):
            return {"notes": ["patient_a_stable"]}

        @app.get("/api/v1/admin/audit-logs")
        def admin_audit(token: TokenPayload = Depends(require_roles("admin"))):
            return {"audit": "secure"}

        return app

    def test_http_01_missing_auth_header_yields_401(self, test_app: FastAPI) -> None:
        client = TestClient(test_app)
        res = client.get("/api/v1/user/profile")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.json()["detail"] == "Thiếu token"

    def test_http_02_garbage_token_yields_401(self, test_app: FastAPI) -> None:
        client = TestClient(test_app)
        res = client.get(
            "/api/v1/user/profile",
            headers={"Authorization": "Bearer this-is-not-a-valid-jwt-token"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token không hợp lệ" in res.json()["detail"]

    def test_http_03_expired_token_yields_401(self, test_app: FastAPI) -> None:
        settings = get_settings()
        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=24)
        payload = {
            "sub": "expired@clara.local",
            "role": "normal",
            "exp": past,
            "iat": past - timedelta(minutes=15),
            "iss": settings.jwt_issuer,
            "jti": "e2e-exp-01",
            "typ": "access",
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        client = TestClient(test_app)
        res = client.get(
            "/api/v1/user/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "hết hạn" in res.json()["detail"]

    def test_http_04_tampered_token_yields_401(self, test_app: FastAPI) -> None:
        token = create_access_token("attacker@clara.local", "normal")
        h, p, s = token.split(".")
        tampered = f"{h}.{p}.invalidsignature123"

        client = TestClient(test_app)
        res = client.get(
            "/api/v1/user/profile",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_http_05_role_gate_rejection_normal_on_doctor_surface(self, test_app: FastAPI) -> None:
        normal_token = create_access_token("user@clara.local", "normal")

        client = TestClient(test_app)
        res = client.get(
            "/api/v1/doctor/clinical-notes",
            headers={"Authorization": f"Bearer {normal_token}"},
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert "Không đủ quyền truy cập" in res.json()["detail"]

    def test_http_06_role_gate_success_doctor_on_doctor_surface(self, test_app: FastAPI) -> None:
        doctor_token = create_access_token("doctor@clara.local", "doctor")

        client = TestClient(test_app)
        res = client.get(
            "/api/v1/doctor/clinical-notes",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["notes"] == ["patient_a_stable"]

    def test_http_07_admin_implicit_access_on_doctor_surface(self, test_app: FastAPI) -> None:
        admin_token = create_access_token("admin@clara.local", "admin")

        client = TestClient(test_app)
        res = client.get(
            "/api/v1/doctor/clinical-notes",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == status.HTTP_200_OK

    def test_http_08_revoked_token_via_denylist_yields_401(
        self, test_app: FastAPI, monkeypatch
    ) -> None:
        store = InMemorySecurityStore()
        sec = SessionSecurity(store=store)  # type: ignore[arg-type]
        monkeypatch.setattr("clara_api.core.rbac.session_security", sec)
        monkeypatch.setenv("HARDENING_TOKEN_DENYLIST_ENABLED", "true")
        get_settings.cache_clear()

        token = create_access_token("alice@clara.local", "normal")
        jti = decode_access_token(token).get("jti")
        assert jti

        # Pre-revocation check
        client = TestClient(test_app)
        res = client.get("/api/v1/user/profile", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == status.HTTP_200_OK

        # Revoke token
        sec.revoke(jti, ttl_seconds=3600)

        # Replay attempt: rejected with 401
        res2 = client.get("/api/v1/user/profile", headers={"Authorization": f"Bearer {token}"})
        assert res2.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token đã bị thu hồi" in res2.json()["detail"]
