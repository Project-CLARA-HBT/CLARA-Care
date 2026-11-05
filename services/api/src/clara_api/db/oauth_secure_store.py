"""OAuth callback and refresh secure store with lease locking services.

Provides:
- AES-256-GCM authenticated encryption for OAuth access and refresh tokens
- Tenant and profile Additional Authenticated Data (AAD) cryptographic binding
- RFC 6819 refresh token rotation with single-use enforcement and replay/reuse detection
- Cascade revocation of token families upon reuse attack detection
- Distributed lease locking with fencing tokens and TTL heartbeats for concurrent sync/refresh
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import os
from secrets import token_bytes
from typing import Any, Generator
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from clara_api.db.models import ConnectorAccount
from clara_api.db.oauth_secure_models import (
    ConnectorLeaseLock,
    ConnectorOAuthToken,
    ConnectorRefreshTokenRotation,
)


class OAuthSecureStoreError(Exception):
    """Base exception for OAuth secure store errors."""


class OAuthTokenSecurityError(OAuthSecureStoreError):
    """Raised when token decryption, AAD authentication, or integrity checks fail."""


class RefreshTokenReuseError(OAuthSecureStoreError):
    """Raised when a previously rotated refresh token is presented (replay attack)."""


class OAuthTokenNotFoundError(OAuthSecureStoreError):
    """Raised when an expected token record cannot be found."""


class LeaseAcquisitionError(OAuthSecureStoreError):
    """Raised when lease locking fails or times out."""


class LeaseExpiredError(OAuthSecureStoreError):
    """Raised when attempting an operation under an expired lease."""


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalize datetime to timezone-aware UTC datetime."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _resolve_key(key: bytes | str | None = None) -> bytes:
    """Resolve a 32-byte key for AES-256-GCM operations."""
    if key is not None:
        if isinstance(key, bytes):
            if len(key) == 32:
                return key
            if len(key) == 44:  # Base64 encoded 32 bytes
                try:
                    decoded = base64.urlsafe_b64decode(key)
                    if len(decoded) == 32:
                        return decoded
                except Exception:
                    pass
            # Deterministically hash to 32 bytes if not exactly 32 bytes
            return hashlib.sha256(key).digest()
        elif isinstance(key, str):
            clean = key.strip()
            try:
                decoded = base64.urlsafe_b64decode(clean.encode("utf-8"))
                if len(decoded) == 32:
                    return decoded
            except Exception:
                pass
            return hashlib.sha256(clean.encode("utf-8")).digest()

    # Fallback to application settings or environment
    env_key = os.environ.get("OAUTH_TOKEN_ENCRYPTION_KEY")
    if env_key and env_key.strip():
        return _resolve_key(env_key.strip())

    try:
        from clara_api.core.config import get_settings

        settings = get_settings()
        cfg_key = getattr(settings, "lifemap_capture_encryption_key", None)
        if cfg_key and cfg_key.strip():
            return _resolve_key(cfg_key.strip())
    except Exception:
        pass

    # Safe deterministic internal fallback for development and isolated unit test environments
    return hashlib.sha256(b"clara-dev-oauth-token-encryption-master-key-v1").digest()


def build_aad(*, tenant_id: str, profile_id: int, connector_id: int) -> bytes:
    """Construct Additional Authenticated Data binding to prevent ciphertext splicing across tenants or profiles."""
    return f"clara:oauth:{tenant_id}:{profile_id}:{connector_id}".encode("utf-8")


def hash_refresh_token(token: str) -> str:
    """Compute deterministic SHA-256 digest of refresh token for safe indexing."""
    if not token:
        raise ValueError("Refresh token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encrypt_token(
    secret: str,
    *,
    connector_id: int,
    profile_id: int,
    tenant_id: str = "default",
    key: bytes | str | None = None,
    key_version: str = "v1",
) -> tuple[bytes, dict[str, Any]]:
    """Encrypt a secret using AES-256-GCM with 12-byte random nonce and AAD binding.

    Returns:
        tuple of (ciphertext_with_nonce, envelope_metadata)
    """
    if not secret:
        raise ValueError("Secret text cannot be empty")

    raw_key = _resolve_key(key)
    aes = AESGCM(raw_key)
    nonce = token_bytes(12)
    aad = build_aad(tenant_id=tenant_id, profile_id=profile_id, connector_id=connector_id)

    raw_data = secret.encode("utf-8")
    encrypted_body = aes.encrypt(nonce, raw_data, aad)
    ciphertext = nonce + encrypted_body

    envelope_metadata = {
        "encryption_algorithm": "aes-256-gcm",
        "key_version": key_version,
        "nonce_length": 12,
        "aad_digest": hashlib.sha256(aad).hexdigest()[:16],
        "created_at": datetime.now(UTC).isoformat(),
    }
    return ciphertext, envelope_metadata


def decrypt_token(
    ciphertext: bytes,
    *,
    connector_id: int,
    profile_id: int,
    tenant_id: str = "default",
    key: bytes | str | None = None,
) -> str:
    """Decrypt an AES-256-GCM ciphertext, validating authentication tag and AAD binding."""
    if not ciphertext or len(ciphertext) < 28:  # 12 nonce + 16 auth tag
        raise OAuthTokenSecurityError("Encrypted payload is missing or too short")

    raw_key = _resolve_key(key)
    aes = AESGCM(raw_key)
    nonce, encrypted_body = ciphertext[:12], ciphertext[12:]
    aad = build_aad(tenant_id=tenant_id, profile_id=profile_id, connector_id=connector_id)

    try:
        decrypted_bytes = aes.decrypt(nonce, encrypted_body, aad)
        return decrypted_bytes.decode("utf-8")
    except InvalidTag as err:
        raise OAuthTokenSecurityError(
            "OAuth token authentication failed: ciphertext was corrupted, tampered with, "
            "or decrypted with mismatched tenant/profile/connector AAD context."
        ) from err
    except Exception as err:
        raise OAuthTokenSecurityError("Failed to decrypt OAuth token payload") from err


# ==============================================================================
# Token Store Operations
# ==============================================================================


def store_oauth_tokens(
    db: Session,
    *,
    connector_id: int,
    profile_id: int,
    tenant_id: str = "default",
    provider: str,
    access_token: str,
    refresh_token: str | None = None,
    token_type: str = "Bearer",
    scopes: list[str] | dict | None = None,
    access_token_expires_in: int | None = None,
    refresh_token_expires_in: int | None = None,
    key: bytes | str | None = None,
    key_version: str = "v1",
    key_id: str = "default",
    family_id: str | None = None,
) -> ConnectorOAuthToken:
    """Store encrypted access and refresh tokens, superseding any prior active tokens."""
    now = datetime.now(UTC)

    access_expires_at = (
        now + timedelta(seconds=access_token_expires_in)
        if access_token_expires_in is not None
        else None
    )
    refresh_expires_at = (
        now + timedelta(seconds=refresh_token_expires_in)
        if refresh_token_expires_in is not None
        else None
    )

    access_ciphertext, envelope_metadata = encrypt_token(
        access_token,
        connector_id=connector_id,
        profile_id=profile_id,
        tenant_id=tenant_id,
        key=key,
        key_version=key_version,
    )

    refresh_ciphertext: bytes | None = None
    refresh_hash: str | None = None
    if refresh_token:
        refresh_ciphertext, _ = encrypt_token(
            refresh_token,
            connector_id=connector_id,
            profile_id=profile_id,
            tenant_id=tenant_id,
            key=key,
            key_version=key_version,
        )
        refresh_hash = hash_refresh_token(refresh_token)

    # Deactivate existing active tokens for this connector
    active_tokens = (
        db.execute(
            select(ConnectorOAuthToken).where(
                ConnectorOAuthToken.connector_id == connector_id,
                ConnectorOAuthToken.status == "active",
            )
        )
        .scalars()
        .all()
    )
    for tok in active_tokens:
        tok.status = "rotated"
        tok.updated_at = now

    token_family = family_id or str(uuid4())

    new_token = ConnectorOAuthToken(
        connector_id=connector_id,
        profile_id=profile_id,
        tenant_id=tenant_id,
        provider=provider,
        token_type=token_type,
        scopes_json=scopes,
        access_token_ciphertext=access_ciphertext,
        refresh_token_ciphertext=refresh_ciphertext,
        encryption_algorithm="aes-256-gcm",
        key_version=key_version,
        key_id=key_id,
        envelope_metadata_json=envelope_metadata,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        status="active",
        rotation_family_id=token_family,
        rotation_counter=0,
        refresh_token_hash=refresh_hash,
    )
    db.add(new_token)

    # Synchronize ConnectorAccount status
    account = db.execute(
        select(ConnectorAccount).where(ConnectorAccount.id == connector_id)
    ).scalar_one_or_none()
    if account:
        account.status = "connected"
        account.token_ciphertext = access_ciphertext
        account.token_key_version = key_version
        account.updated_at = now

    db.flush()
    return new_token


def get_active_token(db: Session, *, connector_id: int) -> ConnectorOAuthToken | None:
    """Retrieve current active token record for a connector."""
    return db.execute(
        select(ConnectorOAuthToken).where(
            ConnectorOAuthToken.connector_id == connector_id,
            ConnectorOAuthToken.status == "active",
        )
    ).scalar_one_or_none()


def retrieve_decrypted_tokens(
    db: Session,
    *,
    token_model: ConnectorOAuthToken,
    key: bytes | str | None = None,
) -> dict[str, Any]:
    """Decrypt and return access and refresh tokens without persisting plaintext."""
    access_token = decrypt_token(
        token_model.access_token_ciphertext,
        connector_id=token_model.connector_id,
        profile_id=token_model.profile_id,
        tenant_id=token_model.tenant_id,
        key=key,
    )
    refresh_token = None
    if token_model.refresh_token_ciphertext:
        refresh_token = decrypt_token(
            token_model.refresh_token_ciphertext,
            connector_id=token_model.connector_id,
            profile_id=token_model.profile_id,
            tenant_id=token_model.tenant_id,
            key=key,
        )

    now = datetime.now(UTC)
    is_access_expired = False
    if token_model.access_token_expires_at:
        is_access_expired = _ensure_utc(token_model.access_token_expires_at) <= now

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": token_model.token_type,
        "scopes": token_model.scopes_json,
        "access_token_expires_at": token_model.access_token_expires_at,
        "refresh_token_expires_at": token_model.refresh_token_expires_at,
        "is_access_expired": is_access_expired,
        "rotation_family_id": token_model.rotation_family_id,
        "rotation_counter": token_model.rotation_counter,
        "status": token_model.status,
    }


def rotate_refresh_token(
    db: Session,
    *,
    connector_id: int,
    presented_refresh_token: str,
    new_access_token: str,
    new_refresh_token: str,
    access_token_expires_in: int | None = None,
    refresh_token_expires_in: int | None = None,
    client_metadata: dict[str, Any] | None = None,
    key: bytes | str | None = None,
    key_version: str = "v1",
) -> ConnectorOAuthToken:
    """Perform atomic RFC 6819 Refresh Token Rotation.

    Security Invariant:
    If an already rotated refresh token is presented again (replay attack):
    1. Entire token family is immediately revoked.
    2. Connector account status transitions to 'needs_reauth'.
    3. Audit ledger logs reuse_detected = True.
    4. RefreshTokenReuseError is raised.
    """
    now = datetime.now(UTC)
    presented_hash = hash_refresh_token(presented_refresh_token)

    # 1. Check for active token matching this refresh token hash
    active_token = db.execute(
        select(ConnectorOAuthToken).where(
            ConnectorOAuthToken.connector_id == connector_id,
            ConnectorOAuthToken.refresh_token_hash == presented_hash,
            ConnectorOAuthToken.status == "active",
        )
    ).scalar_one_or_none()

    if active_token is None:
        # Check if this token hash was already rotated in this connector or family
        prior_rotation = db.execute(
            select(ConnectorRefreshTokenRotation).where(
                ConnectorRefreshTokenRotation.connector_id == connector_id,
                ConnectorRefreshTokenRotation.old_token_hash == presented_hash,
            )
        ).scalar_one_or_none()

        stale_token = db.execute(
            select(ConnectorOAuthToken).where(
                ConnectorOAuthToken.connector_id == connector_id,
                ConnectorOAuthToken.refresh_token_hash == presented_hash,
                ConnectorOAuthToken.status.in_(["rotated", "revoked"]),
            )
        ).scalar_one_or_none()

        if prior_rotation is not None or stale_token is not None:
            # REPLAY ATTACK DETECTED!
            family_id = (
                prior_rotation.family_id
                if prior_rotation
                else (stale_token.rotation_family_id if stale_token else "unknown")
            )
            # Revoke entire token family
            db.execute(
                update(ConnectorOAuthToken)
                .where(
                    ConnectorOAuthToken.connector_id == connector_id,
                    ConnectorOAuthToken.rotation_family_id == family_id,
                )
                .values(
                    status="revoked",
                    revocation_reason="refresh_token_reuse_detected",
                    revoked_at=now,
                    updated_at=now,
                )
            )

            # Mark connector account as needing reauthorization
            account = db.execute(
                select(ConnectorAccount).where(ConnectorAccount.id == connector_id)
            ).scalar_one_or_none()
            if account:
                account.status = "needs_reauth"
                account.updated_at = now

            # Record audit entry with reuse_detected = True
            audit_entry = ConnectorRefreshTokenRotation(
                connector_id=connector_id,
                profile_id=account.profile_id if account else (stale_token.profile_id if stale_token else 0),
                tenant_id=stale_token.tenant_id if stale_token else "default",
                family_id=family_id,
                old_token_id=stale_token.id if stale_token else None,
                new_token_id=None,
                old_token_hash=presented_hash,
                new_token_hash=hash_refresh_token(new_refresh_token),
                reuse_detected=True,
                client_metadata_json={
                    **(client_metadata or {}),
                    "violation": "replay_attack",
                    "reason": "previously_rotated_token_presented",
                },
            )
            db.add(audit_entry)
            db.flush()

            raise RefreshTokenReuseError(
                f"Refresh token reuse detected for connector {connector_id}. "
                f"Token family '{family_id}' has been permanently revoked for security."
            )

        raise OAuthTokenNotFoundError(
            f"No matching active or known refresh token found for connector {connector_id}."
        )

    # 2. Legitimate rotation: mark current active token as rotated
    active_token.status = "rotated"
    active_token.updated_at = now

    new_refresh_hash = hash_refresh_token(new_refresh_token)

    new_access_ciphertext, envelope_metadata = encrypt_token(
        new_access_token,
        connector_id=connector_id,
        profile_id=active_token.profile_id,
        tenant_id=active_token.tenant_id,
        key=key,
        key_version=key_version,
    )
    new_refresh_ciphertext, _ = encrypt_token(
        new_refresh_token,
        connector_id=connector_id,
        profile_id=active_token.profile_id,
        tenant_id=active_token.tenant_id,
        key=key,
        key_version=key_version,
    )

    access_expires_at = (
        now + timedelta(seconds=access_token_expires_in)
        if access_token_expires_in is not None
        else None
    )
    refresh_expires_at = (
        now + timedelta(seconds=refresh_token_expires_in)
        if refresh_token_expires_in is not None
        else None
    )

    new_token = ConnectorOAuthToken(
        connector_id=connector_id,
        profile_id=active_token.profile_id,
        tenant_id=active_token.tenant_id,
        provider=active_token.provider,
        token_type=active_token.token_type,
        scopes_json=active_token.scopes_json,
        access_token_ciphertext=new_access_ciphertext,
        refresh_token_ciphertext=new_refresh_ciphertext,
        encryption_algorithm="aes-256-gcm",
        key_version=key_version,
        key_id=active_token.key_id,
        envelope_metadata_json=envelope_metadata,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        status="active",
        rotation_family_id=active_token.rotation_family_id,
        rotation_counter=active_token.rotation_counter + 1,
        refresh_token_hash=new_refresh_hash,
        parent_token_id=active_token.id,
    )
    db.add(new_token)
    db.flush()

    # Record rotation audit
    rotation_audit = ConnectorRefreshTokenRotation(
        connector_id=connector_id,
        profile_id=active_token.profile_id,
        tenant_id=active_token.tenant_id,
        family_id=active_token.rotation_family_id,
        old_token_id=active_token.id,
        new_token_id=new_token.id,
        old_token_hash=presented_hash,
        new_token_hash=new_refresh_hash,
        reuse_detected=False,
        client_metadata_json=client_metadata,
    )
    db.add(rotation_audit)

    # Update connector account
    account = db.execute(
        select(ConnectorAccount).where(ConnectorAccount.id == connector_id)
    ).scalar_one_or_none()
    if account:
        account.status = "connected"
        account.token_ciphertext = new_access_ciphertext
        account.token_key_version = key_version
        account.updated_at = now

    db.flush()
    return new_token


def revoke_token_family(
    db: Session,
    *,
    connector_id: int,
    family_id: str,
    reason: str = "user_revoked",
) -> int:
    """Revoke all tokens belonging to a specific rotation family."""
    now = datetime.now(UTC)
    result = db.execute(
        update(ConnectorOAuthToken)
        .where(
            ConnectorOAuthToken.connector_id == connector_id,
            ConnectorOAuthToken.rotation_family_id == family_id,
            ConnectorOAuthToken.status != "revoked",
        )
        .values(
            status="revoked",
            revocation_reason=reason,
            revoked_at=now,
            updated_at=now,
        )
    )
    account = db.execute(
        select(ConnectorAccount).where(ConnectorAccount.id == connector_id)
    ).scalar_one_or_none()
    if account:
        account.status = "needs_reauth" if reason != "user_disconnected" else "disconnected"
        account.updated_at = now
    db.flush()
    return result.rowcount


# ==============================================================================
# Distributed Lease Locking Operations
# ==============================================================================


def acquire_lease(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
    holder_id: str,
    ttl_seconds: int = 30,
    metadata: dict[str, Any] | None = None,
) -> ConnectorLeaseLock | None:
    """Attempt to acquire a mutual exclusion distributed lease.

    Returns:
        ConnectorLeaseLock if lease was acquired, or None if currently held by another worker.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)

    existing = db.execute(
        select(ConnectorLeaseLock).where(
            ConnectorLeaseLock.resource_type == resource_type,
            ConnectorLeaseLock.resource_id == resource_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        # Create brand-new lease
        lease_token = str(uuid4())
        new_lease = ConnectorLeaseLock(
            resource_type=resource_type,
            resource_id=resource_id,
            lease_token=lease_token,
            holder_id=holder_id,
            fencing_token=1,
            acquired_at=now,
            expires_at=expires_at,
            released_at=None,
            renewed_count=0,
            metadata_json=metadata,
        )
        db.add(new_lease)
        try:
            db.flush()
            return new_lease
        except Exception:
            db.rollback()
            return None

    # Lease exists: check if it's currently held and unexpired
    is_held = existing.released_at is None and _ensure_utc(existing.expires_at) > now
    if is_held:
        if existing.holder_id == holder_id:
            # Re-entrant acquisition / heartbeat extension by same holder
            existing.expires_at = expires_at
            existing.renewed_count += 1
            existing.updated_at = now
            if metadata:
                existing.metadata_json = metadata
            db.flush()
            return existing
        # Held by another active worker
        return None

    # Lease was released or has expired: take over lease with incremented fencing token
    existing.holder_id = holder_id
    existing.lease_token = str(uuid4())
    existing.fencing_token += 1
    existing.acquired_at = now
    existing.expires_at = expires_at
    existing.released_at = None
    existing.renewed_count = 0
    existing.metadata_json = metadata
    existing.updated_at = now
    db.flush()
    return existing


def renew_lease(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
    lease_token: str,
    holder_id: str,
    ttl_seconds: int = 30,
) -> bool:
    """Renew an active lease before expiration (heartbeat).

    Returns:
        True if lease was renewed, False if expired or stolen.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)

    existing = db.execute(
        select(ConnectorLeaseLock).where(
            ConnectorLeaseLock.resource_type == resource_type,
            ConnectorLeaseLock.resource_id == resource_id,
            ConnectorLeaseLock.lease_token == lease_token,
            ConnectorLeaseLock.holder_id == holder_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        return False

    if existing.released_at is not None or _ensure_utc(existing.expires_at) <= now:
        return False

    existing.expires_at = expires_at
    existing.renewed_count += 1
    existing.updated_at = now
    db.flush()
    return True


def release_lease(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
    lease_token: str,
    holder_id: str,
) -> bool:
    """Release an active lease so other workers can acquire it immediately."""
    now = datetime.now(UTC)
    existing = db.execute(
        select(ConnectorLeaseLock).where(
            ConnectorLeaseLock.resource_type == resource_type,
            ConnectorLeaseLock.resource_id == resource_id,
            ConnectorLeaseLock.lease_token == lease_token,
            ConnectorLeaseLock.holder_id == holder_id,
        )
    ).scalar_one_or_none()

    if existing is None or existing.released_at is not None:
        return False

    existing.released_at = now
    existing.updated_at = now
    db.flush()
    return True


@contextmanager
def lease_scope(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
    holder_id: str,
    ttl_seconds: int = 30,
    metadata: dict[str, Any] | None = None,
) -> Generator[ConnectorLeaseLock, None, None]:
    """Context manager for distributed lease locking.

    Raises:
        LeaseAcquisitionError if lease is held by another worker.
    """
    lease = acquire_lease(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        holder_id=holder_id,
        ttl_seconds=ttl_seconds,
        metadata=metadata,
    )
    if lease is None:
        raise LeaseAcquisitionError(
            f"Could not acquire lease on {resource_type}:{resource_id} (held by another worker)"
        )

    try:
        yield lease
    finally:
        release_lease(
            db,
            resource_type=resource_type,
            resource_id=resource_id,
            lease_token=lease.lease_token,
            holder_id=holder_id,
        )
