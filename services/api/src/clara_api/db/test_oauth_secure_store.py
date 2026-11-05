"""Unit and integration tests for OAuth secure store, refresh token rotation, and lease locking.

Test Matrix:
- Crypto: AES-256-GCM encryption/decryption, AAD integrity, tamper detection, wrong key rejection
- At-rest security: Access and refresh tokens never stored in plaintext
- Storage & Retrieval: store_oauth_tokens, get_active_token, retrieve_decrypted_tokens
- Token Rotation (RFC 6819): Single-use refresh token exchange, sequence counter increment, parent linkage
- Security Negative (Replay/Reuse Attack): Presentation of already-rotated token triggers family-wide cascade revocation,
  connector 'needs_reauth' transition, and audit ledger recording with reuse_detected=True
- Lease Locking: Mutual exclusion, heartbeat renewal, clean release, expired lease takeover, fencing token monotonicity
- Context Manager: lease_scope auto-acquisition and auto-release
- Multi-tenant / Multi-profile isolation
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.base import Base
from clara_api.db.models import ConnectorAccount, PhrProfile, User
from clara_api.db.oauth_secure_models import (
    ConnectorLeaseLock,
    ConnectorOAuthToken,
    ConnectorRefreshTokenRotation,
)
from clara_api.db.oauth_secure_store import (
    LeaseAcquisitionError,
    OAuthTokenNotFoundError,
    OAuthTokenSecurityError,
    RefreshTokenReuseError,
    acquire_lease,
    decrypt_token,
    encrypt_token,
    get_active_token,
    hash_refresh_token,
    lease_scope,
    release_lease,
    renew_lease,
    retrieve_decrypted_tokens,
    revoke_token_family,
    rotate_refresh_token,
    store_oauth_tokens,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh SQLite in-memory database with all models created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed test user, profile, and connector account
    user1 = User(
        email="patient1@clara.local",
        hashed_password="pw_hash_test_123",
        role="normal",
        full_name="Nguyen Van A",
    )
    user2 = User(
        email="patient2@clara.local",
        hashed_password="pw_hash_test_456",
        role="normal",
        full_name="Tran Thi B",
    )
    session.add_all([user1, user2])
    session.flush()

    prof1 = PhrProfile(user_id=user1.id, full_name="Nguyen Van A")
    prof2 = PhrProfile(user_id=user2.id, full_name="Tran Thi B")
    session.add_all([prof1, prof2])
    session.flush()

    conn1 = ConnectorAccount(
        user_id=user1.id,
        profile_id=prof1.id,
        provider="fitbit",
        external_subject_ref="fitbit-sub-001",
        display_label="Nguyen's Fitbit Sense",
        status="available",
    )
    conn2 = ConnectorAccount(
        user_id=user2.id,
        profile_id=prof2.id,
        provider="dexcom",
        external_subject_ref="dexcom-sub-002",
        display_label="Tran's Dexcom G7",
        status="available",
    )
    session.add_all([conn1, conn2])
    session.commit()

    yield session

    session.close()


# ==============================================================================
# Crypto & Security Tests
# ==============================================================================


def test_encrypt_decrypt_roundtrip() -> None:
    """Verifies AES-256-GCM encrypts and decrypts secret cleanly with AAD context."""
    secret = "ya29.a0AfH6SMD_very_secret_oauth_access_token_12345"
    connector_id = 42
    profile_id = 7
    tenant_id = "vn-hospital-central"

    ciphertext, metadata = encrypt_token(
        secret,
        connector_id=connector_id,
        profile_id=profile_id,
        tenant_id=tenant_id,
    )

    assert isinstance(ciphertext, bytes)
    assert secret.encode("utf-8") not in ciphertext
    assert metadata["encryption_algorithm"] == "aes-256-gcm"
    assert metadata["nonce_length"] == 12

    decrypted = decrypt_token(
        ciphertext,
        connector_id=connector_id,
        profile_id=profile_id,
        tenant_id=tenant_id,
    )
    assert decrypted == secret


def test_decrypt_tampered_ciphertext_fails() -> None:
    """Verifies that altering any byte in ciphertext triggers authentication tag failure."""
    secret = "super_confidential_refresh_token_xyz"
    connector_id = 1
    profile_id = 1

    ciphertext, _ = encrypt_token(
        secret,
        connector_id=connector_id,
        profile_id=profile_id,
    )

    # Corrupt one byte in the payload
    tampered = bytearray(ciphertext)
    tampered[-5] ^= 0xFF

    with pytest.raises(OAuthTokenSecurityError, match="authentication failed"):
        decrypt_token(bytes(tampered), connector_id=connector_id, profile_id=profile_id)


def test_decrypt_mismatched_aad_context_fails() -> None:
    """Verifies that ciphertext spliced to another connector or profile cannot be decrypted."""
    secret = "profile_1_secret_token"
    ciphertext, _ = encrypt_token(
        secret,
        connector_id=1,
        profile_id=1,
        tenant_id="default",
    )

    # Attempt to decrypt under profile 2
    with pytest.raises(OAuthTokenSecurityError, match="authentication failed"):
        decrypt_token(ciphertext, connector_id=1, profile_id=2, tenant_id="default")

    # Attempt to decrypt under connector 2
    with pytest.raises(OAuthTokenSecurityError, match="authentication failed"):
        decrypt_token(ciphertext, connector_id=2, profile_id=1, tenant_id="default")

    # Attempt to decrypt under different tenant
    with pytest.raises(OAuthTokenSecurityError, match="authentication failed"):
        decrypt_token(ciphertext, connector_id=1, profile_id=1, tenant_id="tenant-beta")


def test_decrypt_wrong_key_fails() -> None:
    """Verifies that attempting decryption with a different encryption key fails."""
    key1 = b"01234567890123456789012345678901"
    key2 = b"abcdefghijklmnopqrstuvwxyz123456"

    ciphertext, _ = encrypt_token(
        "secret-key-test",
        connector_id=1,
        profile_id=1,
        key=key1,
    )

    with pytest.raises(OAuthTokenSecurityError, match="authentication failed"):
        decrypt_token(ciphertext, connector_id=1, profile_id=1, key=key2)


def test_empty_secret_raises_value_error() -> None:
    """Empty tokens must be rejected at input."""
    with pytest.raises(ValueError, match="cannot be empty"):
        encrypt_token("", connector_id=1, profile_id=1)


# ==============================================================================
# Token Store & Persistence Tests
# ==============================================================================


def test_store_oauth_tokens_at_rest_encryption(db_session: Session) -> None:
    """Verifies access and refresh tokens are encrypted at rest in the database."""
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    access_raw = "raw-access-token-999"
    refresh_raw = "raw-refresh-token-888"

    token_rec = store_oauth_tokens(
        db_session,
        connector_id=conn.id,
        profile_id=conn.profile_id,
        provider="fitbit",
        access_token=access_raw,
        refresh_token=refresh_raw,
        scopes=["activity", "heartrate", "sleep"],
        access_token_expires_in=3600,
        refresh_token_expires_in=2592000,
    )
    db_session.commit()

    assert token_rec.id is not None
    assert token_rec.status == "active"
    assert token_rec.rotation_counter == 0
    assert token_rec.rotation_family_id is not None

    # Raw tokens MUST NOT be stored in plaintext
    assert access_raw.encode() not in token_rec.access_token_ciphertext
    assert refresh_raw.encode() not in token_rec.refresh_token_ciphertext

    # Refresh token hash is indexed
    assert token_rec.refresh_token_hash == hash_refresh_token(refresh_raw)

    # ConnectorAccount status synchronized to 'connected'
    db_session.refresh(conn)
    assert conn.status == "connected"


def test_retrieve_decrypted_tokens(db_session: Session) -> None:
    """Verifies retrieve_decrypted_tokens cleanly recovers plaintext secrets."""
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    access_raw = "fitbit-access-secret-abc"
    refresh_raw = "fitbit-refresh-secret-xyz"

    token_rec = store_oauth_tokens(
        db_session,
        connector_id=conn.id,
        profile_id=conn.profile_id,
        provider="fitbit",
        access_token=access_raw,
        refresh_token=refresh_raw,
        scopes=["activity"],
        access_token_expires_in=7200,
    )
    db_session.commit()

    active = get_active_token(db_session, connector_id=conn.id)
    assert active is not None
    assert active.id == token_rec.id

    decrypted = retrieve_decrypted_tokens(db_session, token_model=active)
    assert decrypted["access_token"] == access_raw
    assert decrypted["refresh_token"] == refresh_raw
    assert decrypted["token_type"] == "Bearer"
    assert decrypted["is_access_expired"] is False
    assert decrypted["rotation_counter"] == 0


# ==============================================================================
# Refresh Token Rotation & Replay Attack Defense Tests
# ==============================================================================


def test_rotate_refresh_token_happy_path(db_session: Session) -> None:
    """Verifies single-use refresh token rotation produces new generation and marks old rotated."""
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    # Generation 0
    t0 = store_oauth_tokens(
        db_session,
        connector_id=conn.id,
        profile_id=conn.profile_id,
        provider="fitbit",
        access_token="access-gen-0",
        refresh_token="refresh-gen-0",
    )
    db_session.commit()
    family_id = t0.rotation_family_id

    # Generation 1 Rotation
    t1 = rotate_refresh_token(
        db_session,
        connector_id=conn.id,
        presented_refresh_token="refresh-gen-0",
        new_access_token="access-gen-1",
        new_refresh_token="refresh-gen-1",
        access_token_expires_in=3600,
        refresh_token_expires_in=2592000,
        client_metadata={"source": "cron_sync_worker"},
    )
    db_session.commit()

    assert t1.rotation_family_id == family_id
    assert t1.rotation_counter == 1
    assert t1.parent_token_id == t0.id
    assert t1.status == "active"

    # Old token t0 is rotated
    db_session.refresh(t0)
    assert t0.status == "rotated"

    # Audit ledger records rotation
    ledger_entries = db_session.execute(
        select(ConnectorRefreshTokenRotation).where(
            ConnectorRefreshTokenRotation.connector_id == conn.id
        )
    ).scalars().all()

    assert len(ledger_entries) == 1
    assert ledger_entries[0].family_id == family_id
    assert ledger_entries[0].old_token_id == t0.id
    assert ledger_entries[0].new_token_id == t1.id
    assert ledger_entries[0].reuse_detected is False

    # Generation 2 Rotation
    t2 = rotate_refresh_token(
        db_session,
        connector_id=conn.id,
        presented_refresh_token="refresh-gen-1",
        new_access_token="access-gen-2",
        new_refresh_token="refresh-gen-2",
    )
    db_session.commit()

    assert t2.rotation_family_id == family_id
    assert t2.rotation_counter == 2
    assert t2.parent_token_id == t1.id
    assert t2.status == "active"

    db_session.refresh(t1)
    assert t1.status == "rotated"


def test_rotate_refresh_token_replay_attack_reuse_detected(db_session: Session) -> None:
    """Security Negative: If a previously rotated refresh token is presented again (replay attack),
    the system MUST revoke the entire token family, mark connector 'needs_reauth', and log reuse_detected.
    """
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    # Initial token: gen 0
    t0 = store_oauth_tokens(
        db_session,
        connector_id=conn.id,
        profile_id=conn.profile_id,
        provider="fitbit",
        access_token="access-0",
        refresh_token="refresh-0",
    )
    db_session.commit()
    family_id = t0.rotation_family_id

    # Normal rotation: gen 0 -> gen 1
    t1 = rotate_refresh_token(
        db_session,
        connector_id=conn.id,
        presented_refresh_token="refresh-0",
        new_access_token="access-1",
        new_refresh_token="refresh-1",
    )
    db_session.commit()
    assert t1.status == "active"

    # ATTACK: Attacker intercepted refresh-0 and attempts to rotate it again!
    with pytest.raises(RefreshTokenReuseError, match="reuse detected"):
        rotate_refresh_token(
            db_session,
            connector_id=conn.id,
            presented_refresh_token="refresh-0",
            new_access_token="attacker-access",
            new_refresh_token="attacker-refresh",
            client_metadata={"ip": "198.51.100.1"},
        )
    db_session.commit()

    # 1. Entire token family is revoked
    all_tokens = db_session.execute(
        select(ConnectorOAuthToken).where(ConnectorOAuthToken.rotation_family_id == family_id)
    ).scalars().all()

    for tok in all_tokens:
        assert tok.status == "revoked"
        assert tok.revocation_reason == "refresh_token_reuse_detected"

    # 2. ConnectorAccount transitioned to needs_reauth
    db_session.refresh(conn)
    assert conn.status == "needs_reauth"

    # 3. Audit ledger records the reuse violation
    reuse_audit = db_session.execute(
        select(ConnectorRefreshTokenRotation).where(
            ConnectorRefreshTokenRotation.connector_id == conn.id,
            ConnectorRefreshTokenRotation.reuse_detected == True,  # noqa: E712
        )
    ).scalar_one_or_none()

    assert reuse_audit is not None
    assert reuse_audit.family_id == family_id
    assert reuse_audit.old_token_hash == hash_refresh_token("refresh-0")


def test_rotate_unknown_refresh_token_raises_not_found(db_session: Session) -> None:
    """Presenting an unknown/fabricated refresh token raises OAuthTokenNotFoundError."""
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    with pytest.raises(OAuthTokenNotFoundError, match="No matching active or known refresh token"):
        rotate_refresh_token(
            db_session,
            connector_id=conn.id,
            presented_refresh_token="totally_unknown_fabricated_token",
            new_access_token="new-acc",
            new_refresh_token="new-ref",
        )


def test_revoke_token_family(db_session: Session) -> None:
    """Verifies manual revocation of a token family."""
    conn = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()

    t0 = store_oauth_tokens(
        db_session,
        connector_id=conn.id,
        profile_id=conn.profile_id,
        provider="fitbit",
        access_token="acc-to-revoke",
        refresh_token="ref-to-revoke",
    )
    db_session.commit()

    revoked_count = revoke_token_family(
        db_session,
        connector_id=conn.id,
        family_id=t0.rotation_family_id,
        reason="user_disconnected",
    )
    db_session.commit()

    assert revoked_count == 1
    db_session.refresh(t0)
    assert t0.status == "revoked"
    assert t0.revocation_reason == "user_disconnected"

    db_session.refresh(conn)
    assert conn.status == "disconnected"


# ==============================================================================
# Lease Locking & Distributed Coordination Tests
# ==============================================================================


def test_acquire_lease_mutual_exclusion(db_session: Session) -> None:
    """Verifies that only one worker can hold a lease at any given time."""
    resource_type = "oauth_token_refresh"
    resource_id = "connector:1"

    # Worker 1 acquires lease
    lease1 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-node-1",
        ttl_seconds=30,
    )
    db_session.commit()

    assert lease1 is not None
    assert lease1.holder_id == "worker-node-1"
    assert lease1.fencing_token == 1

    # Worker 2 attempts concurrent acquisition -> MUST FAIL (return None)
    lease2 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-node-2",
        ttl_seconds=30,
    )
    assert lease2 is None


def test_lease_heartbeat_renewal(db_session: Session) -> None:
    """Verifies that the holding worker can renew lease and extend TTL."""
    resource_type = "connector_sync"
    resource_id = "connector:fitbit:42"

    lease = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-sync-1",
        ttl_seconds=10,
    )
    db_session.commit()
    assert lease is not None

    token = lease.lease_token

    # Heartbeat renewal
    renewed = renew_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        lease_token=token,
        holder_id="worker-sync-1",
        ttl_seconds=20,
    )
    db_session.commit()
    assert renewed is True

    db_session.refresh(lease)
    assert lease.renewed_count == 1

    # Another worker attempting renewal with wrong token fails
    renewed_impostor = renew_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        lease_token="fake-token",
        holder_id="worker-sync-2",
    )
    assert renewed_impostor is False


def test_lease_release_and_takeover(db_session: Session) -> None:
    """Verifies clean release allows another worker to acquire lease with incremented fencing token."""
    resource_type = "observation_ingest"
    resource_id = "profile:1:provider:fitbit"

    lease1 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-A",
        ttl_seconds=30,
    )
    db_session.commit()
    assert lease1 is not None
    assert lease1.fencing_token == 1

    # Worker A releases lease
    released = release_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        lease_token=lease1.lease_token,
        holder_id="worker-A",
    )
    db_session.commit()
    assert released is True

    # Worker B can now acquire immediately
    lease2 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-B",
        ttl_seconds=30,
    )
    db_session.commit()

    assert lease2 is not None
    assert lease2.holder_id == "worker-B"
    # Fencing token must monotonically increase
    assert lease2.fencing_token == 2


def test_lease_expiry_takeover(db_session: Session) -> None:
    """Verifies that an expired lease can be stolen/taken over by another worker."""
    resource_type = "dexcom_token_refresh"
    resource_id = "connector:2"

    # Worker 1 acquires with -5 seconds TTL (already expired)
    lease1 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-crashed",
        ttl_seconds=-5,
    )
    db_session.commit()
    assert lease1 is not None
    assert lease1.fencing_token == 1

    # Worker 2 discovers expired lease and takes over
    lease2 = acquire_lease(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="worker-healthy",
        ttl_seconds=30,
    )
    db_session.commit()

    assert lease2 is not None
    assert lease2.holder_id == "worker-healthy"
    assert lease2.fencing_token == 2


def test_lease_scope_context_manager(db_session: Session) -> None:
    """Verifies lease_scope context manager acquires and releases lease automatically."""
    resource_type = "scheduled_sync"
    resource_id = "tenant:default:cron"

    with lease_scope(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="thread-1",
        ttl_seconds=10,
    ) as lease:
        assert lease.holder_id == "thread-1"

        # Inside scope, competing worker cannot acquire
        with pytest.raises(LeaseAcquisitionError):
            with lease_scope(
                db_session,
                resource_type=resource_type,
                resource_id=resource_id,
                holder_id="thread-2",
                ttl_seconds=10,
            ):
                pass  # pragma: no cover

    # After exiting scope, lease is released; thread-2 can acquire
    with lease_scope(
        db_session,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id="thread-2",
        ttl_seconds=10,
    ) as lease2:
        assert lease2.holder_id == "thread-2"
        assert lease2.fencing_token >= 2


# ==============================================================================
# Multi-Tenant & Multi-Profile Isolation
# ==============================================================================


def test_multi_profile_isolation(db_session: Session) -> None:
    """Tokens stored for Profile 1 cannot be accessed or manipulated by Profile 2."""
    conn1 = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "fitbit")).scalar_one()
    conn2 = db_session.execute(select(ConnectorAccount).where(ConnectorAccount.provider == "dexcom")).scalar_one()

    t1 = store_oauth_tokens(
        db_session,
        connector_id=conn1.id,
        profile_id=conn1.profile_id,
        tenant_id="tenant-alpha",
        provider="fitbit",
        access_token="p1-token",
        refresh_token="p1-ref",
    )
    t2 = store_oauth_tokens(
        db_session,
        connector_id=conn2.id,
        profile_id=conn2.profile_id,
        tenant_id="tenant-beta",
        provider="dexcom",
        access_token="p2-token",
        refresh_token="p2-ref",
    )
    db_session.commit()

    # Profile 1 active token matches
    active1 = get_active_token(db_session, connector_id=conn1.id)
    assert active1 is not None
    assert active1.id == t1.id

    # Profile 2 active token matches
    active2 = get_active_token(db_session, connector_id=conn2.id)
    assert active2 is not None
    assert active2.id == t2.id

    # Attempting to cross-decrypt fails
    with pytest.raises(OAuthTokenSecurityError):
        decrypt_token(
            t1.access_token_ciphertext,
            connector_id=conn2.id,
            profile_id=conn2.profile_id,
            tenant_id="tenant-beta",
        )
