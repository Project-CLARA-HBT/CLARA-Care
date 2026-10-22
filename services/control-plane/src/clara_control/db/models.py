"""Separate Admin Control-Plane Database Models.

Part of Phase PH40/PH41 (Control-Plane Foundational Architecture).
Enforces:
1. Strict separation from end-user clinical / PHI schemas.
2. Zero storage of patient medical records in control-plane database.
3. Audited administration actions and tenant governance attributes.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

ControlBase = declarative_base()


class ControlTenant(ControlBase):
    """B2B Healthcare organization/tenant entity governed by control-plane."""

    __tablename__ = "control_tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tier = Column(String(32), default="standard", nullable=False)  # enterprise, clinic, hospital
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False, index=True)  # ONBOARDING, ACTIVE, SUSPENDED, DECOMMISSIONED
    max_workspaces = Column(Integer, default=5, nullable=False)
    max_users = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    admin_users = relationship("ControlAdminUser", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("ControlAuditLog", back_populates="tenant", cascade="all, delete-orphan")


class ControlAdminUser(ControlBase):
    """Privileged admin user within control-plane boundary."""

    __tablename__ = "control_admin_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="tenant_admin", nullable=False)  # platform_admin, tenant_admin, auditor
    is_active = Column(Boolean, default=True, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    tenant = relationship("ControlTenant", back_populates="admin_users")
    audit_logs = relationship("ControlAuditLog", back_populates="admin_user")
    role_bindings = relationship("ControlRoleBinding", back_populates="admin_user", cascade="all, delete-orphan")


class ControlRoleBinding(ControlBase):
    """Explicit role binding linking admin users to specific tenant organizations with permission scopes."""

    __tablename__ = "control_role_bindings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_id = Column(String(36), ForeignKey("control_admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_name = Column(String(64), nullable=False, index=True)
    permissions_json = Column(Text, nullable=False, default="[]")
    granted_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    tenant = relationship("ControlTenant")
    admin_user = relationship("ControlAdminUser", back_populates="role_bindings")


class ControlAuditLog(ControlBase):
    """Immutable audit ledger for all control-plane operations."""

    __tablename__ = "control_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("control_tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_id = Column(String(36), ForeignKey("control_admin_users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)  # e.g., TENANT_SUSPEND, USER_INVITE, FLAG_UPDATE
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # JSON-encoded parameters without secrets/PHI
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False, index=True)

    tenant = relationship("ControlTenant", back_populates="audit_logs")
    admin_user = relationship("ControlAdminUser", back_populates="audit_logs")


class ControlAdminSession(ControlBase):
    """Privileged admin session with constrained TTL and device binding."""

    __tablename__ = "control_admin_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = Column(String(36), ForeignKey("control_admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String(128), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    mfa_verified = Column(Boolean, default=False, nullable=False)
    step_up_level = Column(String(32), default="STANDARD", nullable=False)  # STANDARD, PRIVILEGED, EMERGENCY
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    admin_user = relationship("ControlAdminUser")


class ControlFeatureFlag(ControlBase):
    """Control-plane governed operational and safety feature flags."""

    __tablename__ = "control_feature_flags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flag_key = Column(String(128), unique=True, nullable=False, index=True)
    default_state = Column(Boolean, default=False, nullable=False)
    is_dark = Column(Boolean, default=False, nullable=False)  # Dark-launch safety gate
    description = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

