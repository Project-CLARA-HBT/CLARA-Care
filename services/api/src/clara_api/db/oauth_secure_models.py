"""Secure store data models for Connected Health OAuth credentials and lease locking.

Provides persistence models for:
- ConnectorOAuthToken: AES-256-GCM encrypted OAuth token store with rotation family tracking
- ConnectorRefreshTokenRotation: audit ledger for refresh token rotation and replay/reuse detection
- ConnectorLeaseLock: distributed lease coordinator with TTL, fencing tokens, and owner heartbeats
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


def _public_id() -> str:
    """Return a non-enumerable API identifier."""
    return str(uuid4())


class ConnectorOAuthToken(Base):
    """Encrypted OAuth token storage for external connected health and wearable providers.

    Guarantees:
    - Never stores access or refresh tokens in plaintext.
    - Encrypted via AES-256-GCM authenticated cipher with AAD binding.
    - Tracks rotation family ID and sequence counter for RFC 6819 refresh token rotation.
    - Maintains parent token links to form an immutable token lineage tree.
    """

    __tablename__ = "connector_oauth_tokens"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_connector_oauth_token_public_id"),
        Index("ix_connector_oauth_tokens_conn_status", "connector_id", "status"),
        Index("ix_connector_oauth_tokens_rot_family", "rotation_family_id", "rotation_counter"),
        Index("ix_connector_oauth_tokens_profile_provider", "profile_id", "provider"),
        Index("ix_connector_oauth_tokens_refresh_hash", "refresh_token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(
        String(32), default="Bearer", server_default="Bearer", nullable=False
    )
    scopes_json: Mapped[list[str] | dict | None] = mapped_column(JSON, nullable=True)

    # Cryptographic payload (AES-256-GCM ciphertext = 12-byte nonce + encrypted data + 16-byte tag)
    access_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    encryption_algorithm: Mapped[str] = mapped_column(
        String(32), default="aes-256-gcm", server_default="aes-256-gcm", nullable=False
    )
    key_version: Mapped[str] = mapped_column(
        String(64), default="v1", server_default="v1", nullable=False
    )
    key_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False
    )
    envelope_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Lifecycle and expiration
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="active", server_default="active", nullable=False, index=True
    )  # "active", "rotated", "revoked", "expired"
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Token Rotation Family
    rotation_family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rotation_counter: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    refresh_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # SHA-256 of plaintext refresh token for lookup/reuse detection
    parent_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector_oauth_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    parent_token: Mapped[ConnectorOAuthToken | None] = relationship(
        "ConnectorOAuthToken", remote_side=[id], backref="child_tokens"
    )


class ConnectorRefreshTokenRotation(Base):
    """Audit ledger for refresh token rotation events and replay/reuse attacks.

    Whenever a refresh token is exchanged, a rotation entry is recorded.
    If an already rotated refresh token is presented again (replay attack),
    reuse_detected is set to True, and all tokens in the rotation family are revoked.
    """

    __tablename__ = "connector_refresh_token_rotations"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_connector_rot_public_id"),
        Index("ix_connector_rot_conn_fam", "connector_id", "family_id"),
        Index("ix_connector_rot_old_hash", "old_token_hash"),
        Index("ix_connector_rot_reuse", "reuse_detected"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False, index=True
    )
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    old_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector_oauth_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )
    new_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector_oauth_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )
    old_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    new_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reuse_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa.false(), nullable=False, index=True
    )
    client_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ConnectorLeaseLock(Base):
    """Distributed lease coordinator with TTL, fencing tokens, and heartbeat renewal.

    Guarantees:
    - Mutual exclusion for token refresh and data synchronization operations.
    - Prevents thundering-herd refresh races on single-use refresh tokens.
    - Auto-recovers on worker crash after TTL expiration.
    - Monotonically increasing fencing tokens prevent delayed/zombie worker commits.
    """

    __tablename__ = "connector_lease_locks"
    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", name="uq_connector_lease_resource"),
        Index("ix_connector_lease_locks_res", "resource_type", "resource_id"),
        Index("ix_connector_lease_locks_expires", "expires_at"),
        Index("ix_connector_lease_locks_holder", "holder_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    holder_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    fencing_token: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    renewed_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
