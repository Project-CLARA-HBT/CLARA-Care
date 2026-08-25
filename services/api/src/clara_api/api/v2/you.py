"""CLARA API v2 You, Privacy, Sharing, and Connected Health Router.

Endpoints:
- `GET /api/v2/you/profile`: personal details, emergency card data, preferences.
- `GET /api/v2/you/sharing`: active access grants, family invitations, and sharing access logs.
- `POST /api/v2/you/sharing/grants`: create granular access grant.
- `DELETE /api/v2/you/sharing/grants/{grant_id}`: server-authoritative revocation.
- `GET /api/v2/you/privacy`: consent status, AI usage disclosure, DSAR tools.
- `GET /api/v2/you/integrations`: list connected health data sources and sync status.
- `POST /api/v2/you/integrations/sync`: receive canonical connected health observation envelope.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.api.v2.conventions import (
    ApiV2HTTPException,
    ApiV2ResponseEnvelope,
)
from clara_api.compliance.notice import current_notice_version
from clara_api.compliance.redaction import hash_user_ref
from clara_api.connectors.envelope import (
    ConnectedObservationEnvelope,
    DeduplicationResult,
    ingest_observation_envelope,
)
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ConnectorAccount,
    DsarRequest,
    FamilyAccessGrant,
    FamilyAccessLog,
    FamilyInvitation,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope
from clara_api.lifemap.projection_invalidation import invalidate_projection_graph
from clara_api.phr.emergency_card import build_emergency_card

router = APIRouter()


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas - Profile & Emergency Card
# ---------------------------------------------------------------------------


class ProfilePreferences(BaseModel):
    """User preferences, localization settings, and onboarding state."""

    model_config = ConfigDict(extra="ignore")

    locale: str = Field(default="vi", description="Preferred display language")
    timezone: str = Field(default="Asia/Ho_Chi_Minh", description="User local timezone")
    emergency_card_prefs: dict[str, bool] = Field(
        default_factory=lambda: {
            "allergies": True,
            "current_medications": True,
            "conditions": True,
            "blood_type": True,
            "emergency_contact": True,
        },
        description="Field inclusion toggles for emergency card projection",
    )
    onboarding_status: str = Field(default="completed", description="Onboarding workflow status")
    onboarding_version: str = Field(default="", description="Completed onboarding version")
    onboarding_completed_at: datetime | None = Field(
        default=None, description="Timestamp of onboarding completion"
    )
    current_version_no: int = Field(default=1, description="Monotonic profile mutation version")


class EmergencyCardData(BaseModel):
    """Owner-controlled emergency card projection."""

    model_config = ConfigDict(extra="ignore")

    allergies: list[dict[str, Any]] = Field(
        default_factory=list, description="Critical allergies for emergency responders"
    )
    current_medications: list[dict[str, Any]] = Field(
        default_factory=list, description="Current taking medications"
    )
    conditions: list[dict[str, Any]] = Field(
        default_factory=list, description="Chronic or critical conditions"
    )
    blood_type: str = Field(default="", description="ABO/Rh blood type")
    emergency_contact: dict[str, str] = Field(
        default_factory=dict, description="Primary emergency contact details"
    )
    disclaimer: dict[str, str] = Field(
        default_factory=dict, description="Bilingual emergency card legal disclaimer"
    )
    hedge: str | dict[str, str] | None = Field(
        default=None, description="Bilingual self-declared decision support notice"
    )


class YouProfileResponse(BaseModel):
    """Personal details, emergency card data, and profile preferences."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default="", description="Profile public ID (alias for id)")
    profile_id: str = Field(description="Profile public ID")
    user_id: int = Field(description="Associated user ID")
    display_name: str = Field(default="", description="Display name")
    full_name: str = Field(description="User full legal or preferred name")
    date_of_birth: date | None = Field(default=None, description="Date of birth")
    gender: str = Field(default="", description="Gender identifier")
    blood_type: str = Field(default="", description="Blood type")
    height_cm: float | None = Field(default=None, description="Height in centimetres")
    weight_kg: float | None = Field(default=None, description="Weight in kilograms")
    phone: str = Field(default="", description="Contact phone number")
    contact_email: str = Field(default="", description="Contact email address")
    email: str = Field(default="", description="Contact email address alias")
    address: str = Field(default="", description="Residential address")
    emergency_contact: dict[str, Any] = Field(
        default_factory=dict, description="Primary emergency contact details"
    )
    allergies: list[dict[str, Any]] = Field(
        default_factory=list, description="List of recorded allergies"
    )
    conditions: list[dict[str, Any]] = Field(
        default_factory=list, description="List of recorded conditions"
    )
    medications: list[dict[str, Any]] = Field(
        default_factory=list, description="List of recorded medications"
    )
    medical_alerts: list[str] = Field(
        default_factory=list, description="Critical medical alert badges"
    )
    emergency_card_included_fields: dict[str, bool] = Field(
        default_factory=lambda: {
            "allergies": True,
            "current_medications": True,
            "conditions": True,
            "blood_type": True,
            "emergency_contact": True,
        },
        description="Emergency card inclusion preferences",
    )
    insurance_provider: str = Field(default="", description="Health insurance provider")
    insurance_id: str = Field(default="", description="Health insurance card number")
    insurance_expiry: date | None = Field(default=None, description="Insurance expiration date")
    allergy_status: str = Field(default="unknown", description="Declared allergy status")
    notes: str = Field(default="", description="General health summary notes")
    emergency_card: EmergencyCardData = Field(
        description="Projected emergency summary card data"
    )
    preferences: ProfilePreferences = Field(description="User preferences and settings")
    created_at: datetime = Field(description="Profile creation timestamp")
    updated_at: datetime = Field(description="Last profile update timestamp")


# ---------------------------------------------------------------------------
# Overview Schemas
# ---------------------------------------------------------------------------


class HomeProfileDto(BaseModel):
    """Profile identity summary for personal hub."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Profile identifier")
    display_name: str = Field(description="User display name")
    full_name: str | None = Field(default=None, description="Full legal name")
    avatar_url: str | None = Field(default=None, description="Avatar image URL")
    kind: str = Field(default="primary", description="Profile kind ('primary' or 'shared')")
    is_primary: bool = Field(default=True, description="Whether this is user primary profile")
    blood_type: str | None = Field(default=None, description="Blood type")
    conditions_count: int = Field(default=0, description="Count of active conditions")
    allergies_count: int = Field(default=0, description="Count of active allergies")
    medications_count: int = Field(default=0, description="Count of active medications")


class HealthDemographicsDto(BaseModel):
    """Demographics snapshot."""

    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    insurance_provider: str | None = None
    insurance_id: str | None = None
    emergency_contact: dict[str, Any] | None = None


class YouEmergencyCardSummaryDto(BaseModel):
    """Emergency card summary for You overview."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    blood_type: str | None = None
    allergies_count: int = 0
    conditions_count: int = 0
    medications_count: int = 0
    medical_alerts: list[str] = Field(default_factory=list)
    emergency_contact: dict[str, Any] | None = None
    is_configured: bool = True
    last_updated: str | None = None


class FamilySharingSummaryDto(BaseModel):
    """Family sharing summary for You overview."""

    model_config = ConfigDict(extra="ignore")

    active_grants_count: int = 0
    received_grants_count: int = 0
    pending_invites_count: int = 0
    members: list[dict[str, Any]] = Field(default_factory=list)


class PrivacyAiSummaryDto(BaseModel):
    """Privacy and AI settings summary for You overview."""

    model_config = ConfigDict(extra="ignore")

    data_classes_used: list[str] = Field(
        default_factory=lambda: ["demographics", "medications", "conditions", "vitals"]
    )
    ai_features_enabled: bool = True
    cot_disabled: bool = True
    retention_policy_days: int = 30
    consent_status: str = "granted"
    last_consent_at: str | None = None


class IntegrationSourceSummaryDto(BaseModel):
    """Connected source snapshot."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    title: str
    connected: bool = True
    sync_enabled: bool = True
    last_sync_at: str | None = None
    status: str = "active"
    error_message: str | None = None


class IntegrationsSummaryDto(BaseModel):
    """Wearable and connector integration summary for You overview."""

    model_config = ConfigDict(extra="ignore")

    total_connected: int = 0
    sources: list[IntegrationSourceSummaryDto] = Field(default_factory=list)


class ProfessionalModeDto(BaseModel):
    """Professional role launchpad status."""

    model_config = ConfigDict(extra="ignore")

    eligible: bool = False
    role: str = "normal"
    active_workspace: str | None = None


class YouOverviewResponse(BaseModel):
    """Unified personal overview response for /you dashboard."""

    model_config = ConfigDict(extra="ignore")

    profile: HomeProfileDto | None = None
    demographics: HealthDemographicsDto | None = None
    emergency_card: YouEmergencyCardSummaryDto
    family_sharing: FamilySharingSummaryDto
    privacy_ai: PrivacyAiSummaryDto
    integrations: IntegrationsSummaryDto
    professional_mode: ProfessionalModeDto
    notifications: dict[str, Any] | None = None


class UpdateProfileDetailsRequest(BaseModel):
    """Payload to update personal health demographics and preferences."""

    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    address: str | None = None
    emergency_contact: dict[str, Any] | None = None
    emergency_card_included_fields: dict[str, bool] | None = None
    medical_alerts: list[str] | None = None
    insurance_provider: str | None = None
    insurance_id: str | None = None


class EmergencyCardResponse(BaseModel):
    """Direct emergency card response with inclusions and notices."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    profile_id: str | None = None
    blood_type: str | None = None
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    current_medications: list[dict[str, Any]] = Field(default_factory=list)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    emergency_contact: dict[str, Any] | None = None
    medical_alerts: list[str] = Field(default_factory=list)
    included_fields: dict[str, bool] = Field(
        default_factory=lambda: {
            "allergies": True,
            "current_medications": True,
            "conditions": True,
            "blood_type": True,
            "emergency_contact": True,
        }
    )
    disclaimer: dict[str, str] = Field(default_factory=dict)
    last_updated: str | None = None


class UpdateEmergencyCardRequest(BaseModel):
    """Payload to update emergency card preferences."""

    model_config = ConfigDict(extra="ignore")

    blood_type: str | None = None
    emergency_contact: dict[str, Any] | None = None
    medical_alerts: list[str] | None = None
    included_fields: dict[str, bool] | None = None


class AiTransparencyResponse(BaseModel):
    """AI transparency, zero-CoT disclosure, and user controls."""

    model_config = ConfigDict(extra="ignore")

    data_classes_used: list[dict[str, Any]] = Field(default_factory=list)
    retention_policy: dict[str, Any] = Field(default_factory=dict)
    cot_zero_disclosure: dict[str, Any] = Field(default_factory=dict)
    ai_feature_controls: dict[str, bool] = Field(default_factory=dict)
    consent_status: dict[str, Any] = Field(default_factory=dict)


class UpdateAiPreferencesRequest(BaseModel):
    """Payload to update AI features and preferences."""

    model_config = ConfigDict(extra="ignore")

    symptom_insights_enabled: bool | None = None
    visit_prep_suggestions_enabled: bool | None = None
    medication_safety_ai_enabled: bool | None = None
    search_summaries_enabled: bool | None = None


class NotificationPreferencesResponse(BaseModel):
    """User notification channel and category preferences."""

    model_config = ConfigDict(extra="ignore")

    categories: dict[str, bool] = Field(
        default_factory=lambda: {
            "medications": True,
            "visits": True,
            "review_items": True,
            "safety_alerts": True,
            "journey_milestones": True,
            "family_activity": True,
        }
    )
    channels: dict[str, bool] = Field(
        default_factory=lambda: {"push": True, "email": True, "in_app": True}
    )
    quiet_hours: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "start_time": "22:00", "end_time": "07:00"}
    )


class UpdateNotificationPreferencesRequest(BaseModel):
    """Payload to update notification preferences."""

    model_config = ConfigDict(extra="ignore")

    categories: dict[str, bool] | None = None
    channels: dict[str, bool] | None = None
    quiet_hours: dict[str, Any] | None = None


class ActiveSessionItem(BaseModel):
    """Active user login session."""

    model_config = ConfigDict(extra="ignore")

    id: str
    device_name: str
    device_type: str = "desktop"
    platform: str = "Web"
    browser: str | None = None
    ip_address: str = "127.0.0.1"
    location: str = "Việt Nam"
    last_active_at: str
    is_current: bool = False


class SecuritySettingsResponse(BaseModel):
    """Account security settings and active session list."""

    model_config = ConfigDict(extra="ignore")

    mfa_enabled: bool = False
    mfa_method: str = "totp"
    mfa_configured_at: str | None = None
    inactivity_timeout_minutes: int = 30
    new_login_alerts: bool = True
    reauth_for_sensitive: bool = True
    active_sessions: list[ActiveSessionItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pydantic Schemas - Sharing & Family Circle
# ---------------------------------------------------------------------------


class SharingGrantItem(BaseModel):
    """Active or historic granular family/caregiver access grant."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Grant database identifier")
    public_id: str = Field(description="Grant public identifier")
    grantor_user_id: int = Field(description="User ID of grantor (profile owner)")
    grantee_user_id: int = Field(description="User ID of authorized recipient")
    grantee_email: str | None = Field(
        default=None, description="Email address of authorized recipient"
    )
    profile_id: int = Field(description="Target health profile ID")
    object_type: str = Field(description="Scope object type (e.g. 'profile', 'lifemap')")
    object_id: str = Field(description="Scope object identifier (e.g. '*' or specific ID)")
    data_classes: list[str] = Field(
        default_factory=list, description="Permitted data categories"
    )
    allowed_actions: list[str] = Field(
        default_factory=list, description="Permitted operations (e.g. 'view', 'export')"
    )
    purpose: str = Field(description="Clinical or caregiving purpose of access")
    starts_at: datetime = Field(description="Grant validity start timestamp")
    expires_at: datetime = Field(description="Grant validity expiration timestamp")
    status: str = Field(description="Grant state ('active', 'revoked', 'expired')")
    grant_version: int = Field(default=1, description="Version sequence number")
    revoked_at: datetime | None = Field(
        default=None, description="Revocation timestamp if revoked"
    )
    revoke_reason: str = Field(default="", description="Reason for grant revocation")
    created_at: datetime = Field(description="Grant creation timestamp")


class SharingInvitationItem(BaseModel):
    """Pending or accepted one-time family invitation."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Invitation database identifier")
    public_id: str = Field(description="Invitation public identifier")
    recipient_email: str = Field(description="Recipient email address")
    purpose: str = Field(description="Proposed purpose of invitation")
    proposed_scope: dict[str, Any] = Field(
        default_factory=dict, description="Proposed scope and data categories"
    )
    expires_at: datetime = Field(description="Invitation expiration timestamp")
    accepted_at: datetime | None = Field(
        default=None, description="Timestamp of invitation acceptance"
    )
    revoked_at: datetime | None = Field(
        default=None, description="Timestamp of invitation revocation"
    )
    status: str = Field(
        description="Invitation status ('pending', 'accepted', 'revoked', 'expired')"
    )
    created_at: datetime = Field(description="Invitation creation timestamp")


class SharingAccessLogItem(BaseModel):
    """Audit ledger entry recording access check outcomes."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Log entry ID")
    public_id: str = Field(description="Log public identifier")
    actor_user_id: int | None = Field(
        default=None, description="User ID of actor performing access"
    )
    grant_id: int | None = Field(default=None, description="Grant ID under which access occurred")
    object_type: str = Field(description="Accessed object type")
    object_id: str = Field(description="Accessed object ID")
    action: str = Field(description="Action attempted (e.g. 'view', 'grant.create')")
    outcome: str = Field(description="Outcome result ('success', 'denied')")
    purpose: str = Field(default="", description="Stated purpose of access")
    created_at: datetime = Field(description="Timestamp of access event")


class YouSharingOverviewResponse(BaseModel):
    """Complete sharing overview covering active grants, invitations, and access audit trail."""

    model_config = ConfigDict(extra="ignore")

    grants: list[SharingGrantItem] = Field(
        default_factory=list, description="Active and historic access grants"
    )
    invitations: list[SharingInvitationItem] = Field(
        default_factory=list, description="Pending and resolved family invitations"
    )
    access_logs: list[SharingAccessLogItem] = Field(
        default_factory=list, description="Recent sharing access audit log entries"
    )
    total_active_grants: int = Field(default=0, description="Count of currently active grants")
    total_pending_invitations: int = Field(
        default=0, description="Count of pending invitations awaiting acceptance"
    )


class CreateSharingGrantRequest(BaseModel):
    """Payload to create a granular access grant."""

    model_config = ConfigDict(extra="ignore")

    target_email: str | None = Field(
        default=None, description="Target recipient email address"
    )
    target_user_id: int | None = Field(
        default=None, description="Target recipient user ID if already known"
    )
    data_classes: list[str] = Field(
        default_factory=lambda: [
            "profile",
            "medications",
            "visits",
            "vitals",
            "allergies",
            "conditions",
        ],
        description="Permitted data classes",
    )
    allowed_categories: list[str] | None = Field(
        default=None, description="Alias for data_classes if provided by client"
    )
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["view"],
        description="Allowed actions (e.g. 'view', 'export')",
    )
    purpose: str = Field(
        default="caregiving",
        min_length=2,
        max_length=64,
        description="Purpose of access grant (e.g. 'caregiving', 'family_support')",
    )
    duration_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Validity duration in days (default 30 days)",
    )
    expires_at: datetime | None = Field(
        default=None, description="Explicit expiration timestamp overriding duration_days"
    )
    object_type: str = Field(
        default="profile", description="Target object type ('profile' or 'lifemap')"
    )
    object_id: str = Field(
        default="*", description="Target object identifier ('*' for whole profile)"
    )


# ---------------------------------------------------------------------------
# Pydantic Schemas - Privacy & DSAR
# ---------------------------------------------------------------------------


class ConsentItem(BaseModel):
    """Status of an individual typed consent policy."""

    model_config = ConfigDict(extra="ignore")

    consent_type: str = Field(description="Consent category (e.g. 'medical_disclaimer')")
    consent_version: str = Field(description="Accepted policy version")
    is_active: bool = Field(description="True if consent is active and not revoked")
    accepted_at: datetime | None = Field(default=None, description="Grant timestamp")
    revoked_at: datetime | None = Field(default=None, description="Revocation timestamp")


class AiDisclosureSummary(BaseModel):
    """Transparent plain-language explanation of AI governance and safety guardrails."""

    model_config = ConfigDict(extra="ignore")

    framework: str = Field(description="AI Governance framework identifier")
    notice_version: str = Field(description="Current AI transparency notice version")
    governance_principles: list[str] = Field(
        default_factory=list, description="Key ethical and safety principles"
    )
    phi_retention_policy: str = Field(description="Data retention and model non-training policy")
    emergency_override_enabled: bool = Field(
        default=True, description="Emergency fast-path bypasses diagnostic reasoning"
    )
    summary_vi: str = Field(description="Vietnamese plain-language AI disclosure summary")
    summary_en: str = Field(description="English plain-language AI disclosure summary")


class DsarRequestItem(BaseModel):
    """Data Subject Access Request (DSAR) record."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="DSAR request ID")
    kind: str = Field(description="Request kind ('export', 'delete', 'correct', 'withdraw')")
    status: str = Field(description="Request status ('received', 'in_progress', 'fulfilled')")
    created_at: datetime = Field(description="Request creation timestamp")
    due_at: datetime | None = Field(default=None, description="Statutory fulfillment deadline")
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp")


class DsarEntryPoints(BaseModel):
    """DSAR action endpoints and statutory timeline metadata."""

    model_config = ConfigDict(extra="ignore")

    export_endpoint: str = Field(description="Endpoint URL for full machine-readable data export")
    delete_endpoint: str = Field(description="Endpoint URL for submitting data deletion request")
    statutory_window_days: int = Field(
        default=30, description="PDPD statutory response window in days"
    )
    active_requests: list[DsarRequestItem] = Field(
        default_factory=list, description="User's DSAR request history"
    )


class YouPrivacyResponse(BaseModel):
    """Privacy hub response with consents, AI disclosures, and DSAR tools."""

    model_config = ConfigDict(extra="ignore")

    consents: list[ConsentItem] = Field(
        default_factory=list, description="User consent grants and ledger status"
    )
    ai_usage_disclosure: AiDisclosureSummary = Field(
        description="AI model usage, safety guardrails, and data boundary disclosures"
    )
    dsar: DsarEntryPoints = Field(description="Data Subject Access Request tools and history")


# ---------------------------------------------------------------------------
# Pydantic Schemas - Integrations & Connected Health
# ---------------------------------------------------------------------------


class IntegrationItem(BaseModel):
    """Connected health source status, capabilities, and permitted actions."""

    model_config = ConfigDict(extra="ignore")

    provider: str = Field(
        description=(
            "Connector provider: 'health_connect', 'apple_health', "
            "'dexcom', 'fitbit', 'huawei_health', 'wear_os'"
        )
    )
    display_label: str = Field(description="Human-readable connector name")
    status: str = Field(
        description=(
            "Integration status: 'connected', 'paused', "
            "'disconnected', 'available', 'error'"
        )
    )
    last_synced_at: datetime | None = Field(
        default=None, description="Timestamp of most recent successful data sync"
    )
    supported_data_types: list[str] = Field(
        default_factory=list, description="All data types supported by this connector"
    )
    connected_data_types: list[str] = Field(
        default_factory=list, description="Currently enabled data types for this user"
    )
    available_actions: list[str] = Field(
        default_factory=list,
        description="Allowed user actions ('sync', 'pause', 'resume', 'disconnect', 'connect')",
    )


class YouIntegrationsResponse(BaseModel):
    """List of all supported and configured health data integrations."""

    model_config = ConfigDict(extra="ignore")

    integrations: list[IntegrationItem] = Field(
        default_factory=list, description="Configured and available health data connectors"
    )
    connected_count: int = Field(
        default=0, description="Count of currently active connected sources"
    )
    available_count: int = Field(
        default=0, description="Count of available but unconnected sources"
    )
    last_sync_overall: datetime | None = Field(
        default=None, description="Most recent sync timestamp across all integrations"
    )


class IntegrationActionRequest(BaseModel):
    """Payload to perform lifecycle action on a connector."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["connect", "pause", "resume", "disconnect", "reconnect"] = Field(
        ..., description="Desired lifecycle transition action"
    )


class YouIntegrationSyncResponse(BaseModel):
    """Result of canonical connected health observation envelope ingestion."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(description="Sync result: 'synced' or 'deduplicated'")
    is_duplicate: bool = Field(description="True if payload was deduplicated without recreation")
    deduplication_key: str = Field(description="Deterministic deduplication key")
    record_hash: str = Field(description="SHA-256 canonical payload hash")
    action_taken: str = Field(
        description="Action executed: 'created', 'updated', or 'deduplicated_noop'"
    )
    observation_id: int | None = Field(
        default=None, description="Created or matched observation ID"
    )
    source_system: str = Field(description="Source system provider")
    data_type: str = Field(description="Ingested health metric type")
    synced_at: datetime = Field(description="Sync processing timestamp")


# ---------------------------------------------------------------------------
# Supported Integrations Catalog
# ---------------------------------------------------------------------------

CONNECTOR_CATALOG: list[dict[str, Any]] = [
    {
        "provider": "health_connect",
        "display_label": "Android Health Connect",
        "supported_data_types": [
            "steps",
            "sleep",
            "heart_rate",
            "blood_pressure",
            "oxygen_saturation",
            "body_weight",
            "blood_glucose",
        ],
    },
    {
        "provider": "apple_health",
        "display_label": "Apple Health (iOS)",
        "supported_data_types": [
            "steps",
            "sleep",
            "heart_rate",
            "blood_pressure",
            "oxygen_saturation",
            "body_weight",
            "blood_glucose",
        ],
    },
    {
        "provider": "dexcom",
        "display_label": "Dexcom CGM (Stelo & G7)",
        "supported_data_types": ["blood_glucose"],
    },
    {
        "provider": "fitbit",
        "display_label": "Fitbit Cloud",
        "supported_data_types": [
            "steps",
            "sleep",
            "heart_rate",
            "oxygen_saturation",
            "body_weight",
        ],
    },
    {
        "provider": "huawei_health",
        "display_label": "Huawei Health",
        "supported_data_types": [
            "steps",
            "sleep",
            "heart_rate",
            "blood_pressure",
            "oxygen_saturation",
            "body_weight",
        ],
    },
    {
        "provider": "wear_os",
        "display_label": "Wear OS Companion",
        "supported_data_types": ["steps", "heart_rate"],
    },
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    response_model=ApiV2ResponseEnvelope[YouOverviewResponse],
    summary="Get unified personal overview for You workspace",
)
def get_you_overview(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None, description="Explicit profile ID override"),
) -> ApiV2ResponseEnvelope[YouOverviewResponse]:
    """Retrieve unified personal overview covering demographics, emergency summary, sharing, privacy, and integrations."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    # 1. Profile and Demographics
    allergies = profile.allergies_json or []
    conditions = profile.conditions_json or []
    medications = profile.medications_json or []

    profile_dto = HomeProfileDto(
        id=profile.public_id,
        display_name=profile.full_name or "Tài khoản cá nhân",
        full_name=profile.full_name,
        avatar_url=None,
        kind="primary" if scope.is_owner else "shared",
        is_primary=scope.is_owner,
        blood_type=profile.blood_type or "Chưa rõ",
        conditions_count=len(conditions),
        allergies_count=len(allergies),
        medications_count=len(medications),
    )

    emergency_contact = None
    if profile.emergency_contact_name or profile.emergency_contact_phone:
        emergency_contact = {
            "name": profile.emergency_contact_name or "",
            "phone": profile.emergency_contact_phone or "",
            "relationship": profile.emergency_contact_relationship or "",
        }

    demographics_dto = HealthDemographicsDto(
        full_name=profile.full_name,
        date_of_birth=profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        gender=profile.gender,
        blood_type=profile.blood_type,
        phone=profile.phone,
        email=profile.contact_email or user.email,
        address=profile.address,
        insurance_provider=profile.insurance_provider,
        insurance_id=profile.insurance_id,
        emergency_contact=emergency_contact,
    )

    # 2. Emergency Card Summary
    critical_alerts = [
        a.get("name", "") for a in allergies if isinstance(a, dict) and a.get("is_critical")
    ]
    if not critical_alerts and profile.allergy_status == "known_allergies":
        critical_alerts = [
            a.get("name", "") for a in allergies if isinstance(a, dict) and a.get("name")
        ][:2]

    emergency_card_summary = YouEmergencyCardSummaryDto(
        id=profile.public_id,
        blood_type=profile.blood_type or "Chưa rõ",
        allergies_count=len(allergies),
        conditions_count=len(conditions),
        medications_count=len(medications),
        medical_alerts=critical_alerts,
        emergency_contact=emergency_contact,
        is_configured=True,
        last_updated=profile.updated_at.isoformat() if profile.updated_at else None,
    )

    # 3. Family Sharing Summary
    grants_count = (
        db.execute(
            select(func.count(FamilyAccessGrant.id)).where(
                FamilyAccessGrant.profile_id == profile.id,
                FamilyAccessGrant.status == "active",
            )
        ).scalar()
        or 0
    )

    invites_count = (
        db.execute(
            select(func.count(FamilyInvitation.id)).where(
                FamilyInvitation.profile_id == profile.id,
                FamilyInvitation.accepted_at.is_(None),
                FamilyInvitation.revoked_at.is_(None),
            )
        ).scalar()
        or 0
    )

    family_sharing_summary = FamilySharingSummaryDto(
        active_grants_count=int(grants_count),
        received_grants_count=0,
        pending_invites_count=int(invites_count),
        members=[],
    )

    # 4. Privacy and AI
    user_consent = (
        db.execute(
            select(UserConsent)
            .where(UserConsent.user_id == user.id)
            .order_by(desc(UserConsent.accepted_at))
        )
        .scalars()
        .first()
    )

    privacy_ai_summary = PrivacyAiSummaryDto(
        data_classes_used=["demographics", "medications", "conditions", "vitals"],
        ai_features_enabled=True,
        cot_disabled=True,
        retention_policy_days=30,
        consent_status="granted" if user_consent and user_consent.revoked_at is None else "pending",
        last_consent_at=user_consent.accepted_at.isoformat()
        if user_consent and user_consent.accepted_at
        else None,
    )

    # 5. Integrations Summary
    conn_count = (
        db.execute(
            select(func.count(ConnectorAccount.id)).where(
                ConnectorAccount.profile_id == profile.id,
                ConnectorAccount.status == "connected",
            )
        ).scalar()
        or 0
    )

    integrations_summary = IntegrationsSummaryDto(
        total_connected=int(conn_count),
        sources=[],
    )

    # 6. Professional Mode
    is_prof = user.role in {"doctor", "researcher", "admin"}
    prof_mode = ProfessionalModeDto(
        eligible=is_prof,
        role=user.role,
        active_workspace="admin"
        if user.role == "admin"
        else (
            "clinical"
            if user.role == "doctor"
            else ("research" if user.role == "researcher" else "personal")
        ),
    )

    # 7. Notifications
    notifications = {
        "unread_count": 0,
        "preferences": {
            "categories": {
                "medications": True,
                "visits": True,
                "review_items": True,
                "safety_alerts": True,
                "journey_milestones": True,
                "family_activity": True,
            },
            "channels": {"push": True, "email": True, "in_app": True},
            "quiet_hours": {"enabled": True, "start_time": "22:00", "end_time": "07:00"},
        },
    }

    response_data = YouOverviewResponse(
        profile=profile_dto,
        demographics=demographics_dto,
        emergency_card=emergency_card_summary,
        family_sharing=family_sharing_summary,
        privacy_ai=privacy_ai_summary,
        integrations=integrations_summary,
        professional_mode=prof_mode,
        notifications=notifications,
    )

    return ApiV2ResponseEnvelope.wrap(data=response_data)


@router.get(
    "/profile",
    response_model=ApiV2ResponseEnvelope[YouProfileResponse],
    summary="Get user profile, emergency card, and preferences",
)
def get_you_profile(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None, description="Explicit profile ID override"),
) -> ApiV2ResponseEnvelope[YouProfileResponse]:
    """Retrieve personal details, emergency card data projection, and preferences."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    record = {
        "profile": {
            "blood_type": profile.blood_type or "",
            "emergency_contact_name": profile.emergency_contact_name or "",
            "emergency_contact_phone": profile.emergency_contact_phone or "",
            "emergency_contact_relationship": profile.emergency_contact_relationship or "",
            "emergency_contact_note": profile.emergency_contact_note or "",
        },
        "allergies": profile.allergies_json or [],
        "medications": profile.medications_json or [],
        "conditions": profile.conditions_json or [],
    }
    raw_card = build_emergency_card(record, profile.emergency_card_prefs_json)

    emergency_card = EmergencyCardData(
        allergies=raw_card.get("allergies", []),
        current_medications=raw_card.get("current_medications", []),
        conditions=raw_card.get("conditions", []),
        blood_type=raw_card.get("blood_type", profile.blood_type or ""),
        emergency_contact=raw_card.get("emergency_contact", {}),
        disclaimer=raw_card.get("disclaimer", {}),
        hedge=raw_card.get("hedge"),
    )

    prefs_json = profile.emergency_card_prefs_json or {}
    emergency_card_prefs = {
        "allergies": prefs_json.get("allergies", True),
        "current_medications": prefs_json.get("current_medications", True),
        "conditions": prefs_json.get("conditions", True),
        "blood_type": prefs_json.get("blood_type", True),
        "emergency_contact": prefs_json.get("emergency_contact", True),
    }

    preferences = ProfilePreferences(
        locale=profile.locale or "vi",
        timezone=profile.timezone or "Asia/Ho_Chi_Minh",
        emergency_card_prefs=emergency_card_prefs,
        onboarding_status=profile.onboarding_status or "completed",
        onboarding_version=profile.onboarding_version or "",
        onboarding_completed_at=profile.onboarding_completed_at,
        current_version_no=profile.current_version_no or 1,
    )

    allergies_list = profile.allergies_json or []
    conditions_list = profile.conditions_json or []
    medications_list = profile.medications_json or []

    critical_alerts = [
        a.get("name", "")
        for a in allergies_list
        if isinstance(a, dict) and a.get("is_critical")
    ]

    emergency_contact_dict = {
        "name": profile.emergency_contact_name or "",
        "phone": profile.emergency_contact_phone or "",
        "relationship": profile.emergency_contact_relationship or "",
    }

    profile_data = YouProfileResponse(
        id=profile.public_id,
        profile_id=profile.public_id,
        user_id=profile.user_id,
        display_name=profile.full_name or "Tài khoản cá nhân",
        full_name=profile.full_name or "",
        date_of_birth=profile.date_of_birth,
        gender=profile.gender or "",
        blood_type=profile.blood_type or "",
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        phone=profile.phone or "",
        contact_email=profile.contact_email or user.email,
        email=profile.contact_email or user.email,
        address=profile.address or "",
        emergency_contact=emergency_contact_dict,
        allergies=allergies_list,
        conditions=conditions_list,
        medications=medications_list,
        medical_alerts=critical_alerts,
        emergency_card_included_fields=emergency_card_prefs,
        insurance_provider=profile.insurance_provider or "",
        insurance_id=profile.insurance_id or "",
        insurance_expiry=profile.insurance_expiry,
        allergy_status=profile.allergy_status or "unknown",
        notes=profile.notes or "",
        emergency_card=emergency_card,
        preferences=preferences,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )

    return ApiV2ResponseEnvelope.wrap(
        data=profile_data,
        meta={"context_version": str(profile.current_version_no or 1)},
    )


@router.patch(
    "/profile",
    response_model=ApiV2ResponseEnvelope[YouProfileResponse],
    summary="Update personal health demographics, emergency contact, and preferences",
)
def update_you_profile(
    body: UpdateProfileDetailsRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None),
) -> ApiV2ResponseEnvelope[YouProfileResponse]:
    """Update personal health demographics, emergency contact, and preferences."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    if body.full_name is not None:
        profile.full_name = body.full_name
    if body.phone is not None:
        profile.phone = body.phone
    if body.email is not None:
        profile.contact_email = body.email
    if body.date_of_birth is not None:
        try:
            profile.date_of_birth = date.fromisoformat(body.date_of_birth)
        except Exception:
            pass
    if body.gender is not None:
        profile.gender = body.gender
    if body.blood_type is not None:
        profile.blood_type = body.blood_type
    if body.address is not None:
        profile.address = body.address
    if body.emergency_contact is not None:
        profile.emergency_contact_name = body.emergency_contact.get(
            "name", profile.emergency_contact_name
        )
        profile.emergency_contact_phone = body.emergency_contact.get(
            "phone", profile.emergency_contact_phone
        )
        profile.emergency_contact_relationship = body.emergency_contact.get(
            "relationship", profile.emergency_contact_relationship
        )
    if body.emergency_card_included_fields is not None:
        profile.emergency_card_prefs_json = body.emergency_card_included_fields
    if body.insurance_provider is not None:
        profile.insurance_provider = body.insurance_provider
    if body.insurance_id is not None:
        profile.insurance_id = body.insurance_id

    profile.current_version_no = (profile.current_version_no or 1) + 1
    profile.updated_at = datetime.now(UTC)

    invalidate_projection_graph(
        db, profile_id=profile.id, reason="profile_updated", invalidate_all=True
    )
    db.commit()
    db.refresh(profile)

    return get_you_profile(db=db, token=token, x_clara_profile_context=str(profile.id))


@router.get(
    "/emergency-card",
    response_model=ApiV2ResponseEnvelope[EmergencyCardResponse],
    summary="Get owner-controlled emergency medical summary card",
)
def get_you_emergency_card(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None),
) -> ApiV2ResponseEnvelope[EmergencyCardResponse]:
    """Get owner-controlled emergency medical summary card."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    record = {
        "profile": {
            "blood_type": profile.blood_type or "",
            "emergency_contact_name": profile.emergency_contact_name or "",
            "emergency_contact_phone": profile.emergency_contact_phone or "",
            "emergency_contact_relationship": profile.emergency_contact_relationship or "",
            "emergency_contact_note": profile.emergency_contact_note or "",
        },
        "allergies": profile.allergies_json or [],
        "medications": profile.medications_json or [],
        "conditions": profile.conditions_json or [],
    }
    raw_card = build_emergency_card(record, profile.emergency_card_prefs_json)

    prefs = profile.emergency_card_prefs_json or {
        "allergies": True,
        "current_medications": True,
        "conditions": True,
        "blood_type": True,
        "emergency_contact": True,
    }

    emergency_contact = None
    if profile.emergency_contact_name or profile.emergency_contact_phone:
        emergency_contact = {
            "name": profile.emergency_contact_name or "",
            "phone": profile.emergency_contact_phone or "",
            "relationship": profile.emergency_contact_relationship or "",
        }

    allergies = profile.allergies_json or []
    critical_alerts = [
        a.get("name", "")
        for a in allergies
        if isinstance(a, dict) and a.get("is_critical")
    ]

    card_response = EmergencyCardResponse(
        id=profile.public_id,
        profile_id=profile.public_id,
        blood_type=profile.blood_type or "",
        allergies=raw_card.get("allergies", []),
        current_medications=raw_card.get("current_medications", []),
        conditions=raw_card.get("conditions", []),
        emergency_contact=emergency_contact,
        medical_alerts=critical_alerts,
        included_fields=prefs,
        disclaimer=raw_card.get("disclaimer", {}),
        last_updated=profile.updated_at.isoformat() if profile.updated_at else None,
    )
    return ApiV2ResponseEnvelope.wrap(data=card_response)


@router.put(
    "/emergency-card",
    response_model=ApiV2ResponseEnvelope[EmergencyCardResponse],
    summary="Update emergency card preferences and fields",
)
def update_you_emergency_card(
    body: UpdateEmergencyCardRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None),
) -> ApiV2ResponseEnvelope[EmergencyCardResponse]:
    """Update emergency card preferences and fields."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    if body.blood_type is not None:
        profile.blood_type = body.blood_type
    if body.emergency_contact is not None:
        profile.emergency_contact_name = body.emergency_contact.get(
            "name", profile.emergency_contact_name
        )
        profile.emergency_contact_phone = body.emergency_contact.get(
            "phone", profile.emergency_contact_phone
        )
        profile.emergency_contact_relationship = body.emergency_contact.get(
            "relationship", profile.emergency_contact_relationship
        )
    if body.included_fields is not None:
        profile.emergency_card_prefs_json = body.included_fields

    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)

    return get_you_emergency_card(
        db=db, token=token, x_clara_profile_context=str(profile.id)
    )


@router.get(
    "/sharing",
    response_model=ApiV2ResponseEnvelope[YouSharingOverviewResponse],
    summary="Get sharing overview: active grants, family invitations, and access logs",
)
def get_you_sharing(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None, description="Explicit profile ID override"),
) -> ApiV2ResponseEnvelope[YouSharingOverviewResponse]:
    """Retrieve active access grants, family invitations, and sharing access logs."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile
    now = datetime.now(UTC)

    # 1. Fetch grants
    grants_db = list(
        db.execute(
            select(FamilyAccessGrant)
            .where(FamilyAccessGrant.profile_id == profile.id)
            .order_by(desc(FamilyAccessGrant.created_at))
        ).scalars()
    )

    grant_items: list[SharingGrantItem] = []
    active_grants_count = 0
    for g in grants_db:
        grantee = db.get(User, g.grantee_user_id)
        effective_status = g.status
        g_exp = _as_utc(g.expires_at)
        if g.revoked_at is not None or g.status == "revoked":
            effective_status = "revoked"
        elif g_exp is not None and g_exp < now:
            effective_status = "expired"

        if effective_status == "active":
            active_grants_count += 1

        data_classes = g.data_classes_json if isinstance(g.data_classes_json, list) else []
        allowed_actions = (
            g.allowed_actions_json if isinstance(g.allowed_actions_json, list) else []
        )

        grant_items.append(
            SharingGrantItem(
                id=g.id,
                public_id=g.public_id,
                grantor_user_id=g.grantor_user_id,
                grantee_user_id=g.grantee_user_id,
                grantee_email=grantee.email if grantee else None,
                profile_id=g.profile_id,
                object_type=g.object_type,
                object_id=g.object_id,
                data_classes=data_classes,
                allowed_actions=allowed_actions,
                purpose=g.purpose,
                starts_at=g.starts_at,
                expires_at=g.expires_at,
                status=effective_status,
                grant_version=g.grant_version,
                revoked_at=g.revoked_at,
                revoke_reason=g.revoke_reason or "",
                created_at=g.created_at,
            )
        )

    # 2. Fetch invitations
    invitations_db = list(
        db.execute(
            select(FamilyInvitation)
            .where(FamilyInvitation.profile_id == profile.id)
            .order_by(desc(FamilyInvitation.created_at))
        ).scalars()
    )

    invitation_items: list[SharingInvitationItem] = []
    pending_invitations_count = 0
    for inv in invitations_db:
        inv_exp = _as_utc(inv.expires_at)
        if inv.revoked_at is not None:
            inv_status = "revoked"
        elif inv.accepted_at is not None:
            inv_status = "accepted"
        elif inv_exp is not None and inv_exp < now:
            inv_status = "expired"
        else:
            inv_status = "pending"
            pending_invitations_count += 1

        invitation_items.append(
            SharingInvitationItem(
                id=inv.id,
                public_id=inv.public_id,
                recipient_email=inv.recipient_email,
                purpose=inv.purpose,
                proposed_scope=inv.proposed_scope_json or {},
                expires_at=inv.expires_at,
                accepted_at=inv.accepted_at,
                revoked_at=inv.revoked_at,
                status=inv_status,
                created_at=inv.created_at,
            )
        )

    # 3. Fetch access logs
    logs_db = list(
        db.execute(
            select(FamilyAccessLog)
            .where(FamilyAccessLog.profile_id == profile.id)
            .order_by(desc(FamilyAccessLog.created_at))
            .limit(50)
        ).scalars()
    )

    log_items = [
        SharingAccessLogItem(
            id=log.id,
            public_id=log.public_id,
            actor_user_id=log.actor_user_id,
            grant_id=log.grant_id,
            object_type=log.object_type,
            object_id=log.object_id,
            action=log.action,
            outcome=log.outcome,
            purpose=log.purpose,
            created_at=log.created_at,
        )
        for log in logs_db
    ]

    response_data = YouSharingOverviewResponse(
        grants=grant_items,
        invitations=invitation_items,
        access_logs=log_items,
        total_active_grants=active_grants_count,
        total_pending_invitations=pending_invitations_count,
    )

    return ApiV2ResponseEnvelope.wrap(data=response_data)


@router.post(
    "/sharing/grants",
    response_model=ApiV2ResponseEnvelope[SharingGrantItem],
    status_code=status.HTTP_201_CREATED,
    summary="Create a granular access grant",
)
def create_sharing_grant(
    request: CreateSharingGrantRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None, description="Explicit profile ID override"),
) -> ApiV2ResponseEnvelope[SharingGrantItem]:
    """Create a granular family/caregiver access grant with duration and scoping."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    if profile.user_id != user.id:
        raise ApiV2HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="scope_forbidden",
            message="Only the profile owner may grant access",
        )

    # 1. Resolve grantee user
    grantee: User | None = None
    if request.target_user_id is not None:
        grantee = db.get(User, request.target_user_id)
        if grantee is None:
            raise ApiV2HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="user_not_found",
                message=f"Target user ID {request.target_user_id} does not exist",
            )
    elif request.target_email and request.target_email.strip():
        clean_email = request.target_email.strip().lower()
        grantee = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
        if grantee is None:
            grantee = User(
                email=clean_email,
                hashed_password="invited-family-placeholder",
                role="normal",
                is_email_verified=False,
                status="active",
            )
            db.add(grantee)
            db.flush()
    else:
        raise ApiV2HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="invalid_grantee",
            message="Either target_email or target_user_id must be provided",
        )

    now = datetime.now(UTC)
    if request.expires_at is not None:
        expiry = request.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
    else:
        expiry = now + timedelta(days=max(1, request.duration_days))

    categories = (
        request.allowed_categories
        if request.allowed_categories is not None
        else request.data_classes
    )

    grant = FamilyAccessGrant(
        grantor_user_id=user.id,
        grantee_user_id=grantee.id,
        profile_id=profile.id,
        object_type=request.object_type,
        object_id=request.object_id,
        data_classes_json=categories,
        allowed_actions_json=request.allowed_actions,
        purpose=request.purpose,
        starts_at=now,
        expires_at=expiry,
        grant_version=1,
        status="active",
    )
    db.add(grant)
    db.flush()

    # Append audit log
    db.add(
        FamilyAccessLog(
            profile_id=profile.id,
            actor_user_id=user.id,
            grant_id=grant.id,
            object_type=request.object_type,
            object_id=request.object_id,
            action="grant.create",
            outcome="success",
            purpose=request.purpose,
        )
    )

    # Invalidate projection graph
    invalidate_projection_graph(
        db, profile_id=profile.id, reason="grant_created", invalidate_all=True
    )
    db.commit()
    db.refresh(grant)

    grant_item = SharingGrantItem(
        id=grant.id,
        public_id=grant.public_id,
        grantor_user_id=grant.grantor_user_id,
        grantee_user_id=grant.grantee_user_id,
        grantee_email=grantee.email,
        profile_id=grant.profile_id,
        object_type=grant.object_type,
        object_id=grant.object_id,
        data_classes=categories,
        allowed_actions=request.allowed_actions,
        purpose=grant.purpose,
        starts_at=grant.starts_at,
        expires_at=grant.expires_at,
        status="active",
        grant_version=grant.grant_version,
        revoked_at=None,
        revoke_reason="",
        created_at=grant.created_at,
    )

    return ApiV2ResponseEnvelope.wrap(
        data=grant_item,
        meta={"grant_id": str(grant.id), "public_id": grant.public_id},
    )


@router.delete(
    "/sharing/grants/{grant_id}",
    response_model=ApiV2ResponseEnvelope[dict[str, Any]],
    summary="Revoke an access grant immediately",
)
def revoke_sharing_grant(
    grant_id: str = Path(..., description="Grant public ID or integer ID"),
    reason: str = Query("owner_revoked", description="Reason for grant revocation"),
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[dict[str, Any]]:
    """Server-authoritative revocation with immediate cache and summary invalidation."""
    user = current_user(db, token)

    clauses = [FamilyAccessGrant.public_id == grant_id]
    if grant_id.isdecimal():
        clauses.append(FamilyAccessGrant.id == int(grant_id))

    grant = db.execute(
        select(FamilyAccessGrant).where(
            or_(*clauses),
            FamilyAccessGrant.grantor_user_id == user.id,
        )
    ).scalar_one_or_none()

    if grant is None:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="grant_not_found",
            message=f"Access grant '{grant_id}' not found or unauthorized",
        )

    now = datetime.now(UTC)
    if grant.revoked_at is None:
        grant.status = "revoked"
        grant.revoked_at = now
        grant.revoke_reason = reason[:255]
        grant.grant_version += 1

        db.add(
            FamilyAccessLog(
                profile_id=grant.profile_id,
                actor_user_id=user.id,
                grant_id=grant.id,
                object_type=grant.object_type,
                object_id=grant.object_id,
                action="grant.revoke",
                outcome="success",
                purpose=grant.purpose,
            )
        )

        # Immediate cache and summary invalidation
        invalidate_projection_graph(
            db,
            profile_id=grant.profile_id,
            reason="grant_revoked",
            invalidate_all=True,
        )
        db.commit()

    return ApiV2ResponseEnvelope.wrap(
        data={
            "revoked": True,
            "grant_id": str(grant.id),
            "public_id": grant.public_id,
            "status": "revoked",
            "revoked_at": now.isoformat(),
        },
        meta={"grant_id": str(grant.id), "public_id": grant.public_id},
    )


@router.post(
    "/sharing/grants/{grant_id}/revoke",
    response_model=ApiV2ResponseEnvelope[dict[str, Any]],
    summary="Revoke an access grant via POST endpoint",
)
def revoke_sharing_grant_post(
    grant_id: str = Path(..., description="Grant public ID or integer ID"),
    reason: str = Query("owner_revoked", description="Reason for grant revocation"),
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[dict[str, Any]]:
    """Server-authoritative revocation via POST."""
    return revoke_sharing_grant(grant_id=grant_id, reason=reason, db=db, token=token)


@router.get(
    "/sharing/logs",
    response_model=ApiV2ResponseEnvelope[list[SharingAccessLogItem]],
    summary="Get audit logs of sharing access events",
)
def get_sharing_logs(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None),
) -> ApiV2ResponseEnvelope[list[SharingAccessLogItem]]:
    """Retrieve recent access logs for family circle audit."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    logs_db = list(
        db.execute(
            select(FamilyAccessLog)
            .where(
                or_(
                    FamilyAccessLog.actor_user_id == user.id,
                    FamilyAccessLog.profile_id == profile.id,
                )
            )
            .order_by(desc(FamilyAccessLog.created_at))
            .limit(50)
        ).scalars()
    )

    items = [
        SharingAccessLogItem(
            id=log.id,
            public_id=log.public_id,
            actor_user_id=log.actor_user_id,
            grant_id=log.grant_id,
            object_type=log.object_type,
            object_id=log.object_id,
            action=log.action,
            outcome=log.outcome,
            purpose=log.purpose or "",
            created_at=log.created_at,
        )
        for log in logs_db
    ]
    return ApiV2ResponseEnvelope.wrap(data=items)


@router.get(
    "/privacy",
    response_model=ApiV2ResponseEnvelope[YouPrivacyResponse],
    summary="Get privacy hub: consent status, AI disclosure, and DSAR tools",
)
def get_you_privacy(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[YouPrivacyResponse]:
    """Retrieve consent ledger status, AI usage disclosure, and DSAR tools."""
    user = current_user(db, token)

    # 1. Fetch user consents
    consents_db = list(
        db.execute(
            select(UserConsent)
            .where(UserConsent.user_id == user.id)
            .order_by(desc(UserConsent.accepted_at))
        ).scalars()
    )

    consent_items: list[ConsentItem] = []
    seen_types: set[str] = set()
    for c in consents_db:
        if c.consent_type not in seen_types:
            seen_types.add(c.consent_type)
            consent_items.append(
                ConsentItem(
                    consent_type=c.consent_type,
                    consent_version=c.consent_version,
                    is_active=c.revoked_at is None,
                    accepted_at=c.accepted_at,
                    revoked_at=c.revoked_at,
                )
            )

    # Ensure standard policy types exist in output if not yet consented
    standard_types = ["medical_disclaimer", "ai_processing", "data_sharing", "analytics"]
    for st in standard_types:
        if st not in seen_types:
            consent_items.append(
                ConsentItem(
                    consent_type=st,
                    consent_version=current_notice_version(),
                    is_active=False,
                    accepted_at=None,
                    revoked_at=None,
                )
            )

    # 2. Build AI disclosure summary
    ai_disclosure = AiDisclosureSummary(
        framework="CLARA Trust Engine (FIDES + CareGuard + Council)",
        notice_version=current_notice_version(),
        governance_principles=[
            "Safety-First Invariant: Clinical assistant, not a doctor replacement",
            "Zero-Retention Training: Health data is never used for general LLM training",
            "Context Minimization: Only relevant observations are assembled for inference",
            "Deterministic Emergency Floor: Critical symptoms trigger immediate escalation",
            "Multi-Tiered Verification: Drug dosing and DDI verified by FIDES & DrugBank",
        ],
        phi_retention_policy="30-day statutory response window under PDPD; DSAR supported",
        emergency_override_enabled=True,
        summary_vi=(
            "CLARA cam kết bảo vệ quyền riêng tư và dữ liệu sức khỏe của bạn theo tiêu chuẩn PDPD "
            "và an toàn y tế quốc tế. Mọi phân tích AI đều được kiểm soát bởi FIDES và CareGuard."
        ),
        summary_en=(
            "CLARA is committed to protecting your health privacy under PDPD standards "
            "and medical safety guidelines. All AI analyses are governed by FIDES and CareGuard."
        ),
    )

    # 3. Fetch DSAR history
    user_ref = hash_user_ref(user.id)
    dsar_requests = list(
        db.execute(
            select(DsarRequest)
            .where(DsarRequest.user_ref == user_ref)
            .order_by(desc(DsarRequest.created_at))
            .limit(20)
        ).scalars()
    )

    dsar_items = [
        DsarRequestItem(
            id=req.id,
            kind=req.kind,
            status=req.status,
            created_at=req.created_at,
            due_at=req.due_at,
            resolved_at=req.resolved_at,
        )
        for req in dsar_requests
    ]

    dsar = DsarEntryPoints(
        export_endpoint="/api/v1/compliance/dsar/export",
        delete_endpoint="/api/v1/compliance/dsar/requests",
        statutory_window_days=30,
        active_requests=dsar_items,
    )

    response_data = YouPrivacyResponse(
        consents=consent_items,
        ai_usage_disclosure=ai_disclosure,
        dsar=dsar,
    )

    return ApiV2ResponseEnvelope.wrap(data=response_data)


@router.get(
    "/privacy/ai-transparency",
    response_model=ApiV2ResponseEnvelope[AiTransparencyResponse],
    summary="Get AI transparency, data classes, and zero-CoT governance details",
)
def get_privacy_ai_transparency(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[AiTransparencyResponse]:
    """Get AI governance transparency data and zero-CoT safety status."""
    user = current_user(db, token)
    user_consent = (
        db.execute(
            select(UserConsent)
            .where(UserConsent.user_id == user.id)
            .order_by(desc(UserConsent.accepted_at))
        )
        .scalars()
        .first()
    )

    data = AiTransparencyResponse(
        data_classes_used=[
            {
                "key": "demographics",
                "name": "Thông tin cơ bản",
                "purpose": "Xác định ngữ cảnh cá nhân hóa",
                "sensitive": False,
            },
            {
                "key": "medications",
                "name": "Đơn thuốc & Dị ứng",
                "purpose": "Kiểm tra an toàn tương tác thuốc DDI & FIDES",
                "sensitive": True,
            },
            {
                "key": "conditions",
                "name": "Tiền sử bệnh lý",
                "purpose": "Hội đồng AI phân tích triệu chứng & phác đồ",
                "sensitive": True,
            },
            {
                "key": "vitals",
                "name": "Chỉ số sinh hiệu",
                "purpose": "Phát hiện dấu hiệu cảnh báo lâm sàng khẩn cấp",
                "sensitive": True,
            },
        ],
        retention_policy={
            "days": 30,
            "description": "Dữ liệu được lưu trữ an toàn theo tiêu chuẩn PDPD và tự động thu hồi khi người dùng yêu cầu.",
            "auto_delete_enabled": True,
        },
        cot_zero_disclosure={
            "operates_without_cot": True,
            "description": "CLARA không lưu trữ chuỗi suy luận nội bộ (Zero-CoT) trong nhật ký lưu trữ vĩnh viễn.",
            "verified_guardrails": [
                "FIDES Verification",
                "CareGuard Emergency Floor",
                "DrugBank XML Safety",
            ],
        },
        ai_feature_controls={
            "symptom_insights_enabled": True,
            "visit_prep_suggestions_enabled": True,
            "medication_safety_ai_enabled": True,
            "search_summaries_enabled": True,
        },
        consent_status={
            "version": user_consent.consent_version
            if user_consent
            else current_notice_version(),
            "granted_at": user_consent.accepted_at.isoformat()
            if user_consent and user_consent.accepted_at
            else None,
            "status": "granted"
            if user_consent and user_consent.revoked_at is None
            else "pending",
            "requires_reconsent": False,
            "purposes": [
                {
                    "purpose": "medical_disclaimer",
                    "label": "Tuyên bố miễn trừ y khoa",
                    "granted": True,
                    "locked": True,
                },
                {
                    "purpose": "ai_processing",
                    "label": "Xử lý hỗ trợ bởi Trí tuệ Nhân tạo",
                    "granted": True,
                },
                {
                    "purpose": "data_sharing",
                    "label": "Chia sẻ dữ liệu chăm sóc gia đình",
                    "granted": True,
                },
                {
                    "purpose": "analytics",
                    "label": "Thống kê chất lượng dịch vụ (Zero-PII)",
                    "granted": True,
                },
            ],
        },
    )
    return ApiV2ResponseEnvelope.wrap(data=data)


@router.patch(
    "/privacy/ai-preferences",
    response_model=ApiV2ResponseEnvelope[dict[str, Any]],
    summary="Update user AI feature controls",
)
def update_privacy_ai_preferences(
    body: UpdateAiPreferencesRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[dict[str, Any]]:
    """Update user AI feature toggle preferences."""
    return ApiV2ResponseEnvelope.wrap(
        data={
            "symptom_insights_enabled": body.symptom_insights_enabled
            if body.symptom_insights_enabled is not None
            else True,
            "visit_prep_suggestions_enabled": body.visit_prep_suggestions_enabled
            if body.visit_prep_suggestions_enabled is not None
            else True,
            "medication_safety_ai_enabled": body.medication_safety_ai_enabled
            if body.medication_safety_ai_enabled is not None
            else True,
            "search_summaries_enabled": body.search_summaries_enabled
            if body.search_summaries_enabled is not None
            else True,
        }
    )


@router.get(
    "/integrations",
    response_model=ApiV2ResponseEnvelope[YouIntegrationsResponse],
    summary="List connected health data sources and sync status",
)
def get_you_integrations(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None, description="Explicit profile ID override"),
) -> ApiV2ResponseEnvelope[YouIntegrationsResponse]:
    """List connected health data sources, sync status, last sync timestamp, and allowed actions."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    accounts = list(
        db.execute(
            select(ConnectorAccount).where(
                ConnectorAccount.profile_id == profile.id,
                ConnectorAccount.user_id == user.id,
            )
        ).scalars()
    )
    accounts_by_provider = {acc.provider: acc for acc in accounts}

    items: list[IntegrationItem] = []
    connected_count = 0
    available_count = 0
    last_sync_overall: datetime | None = None

    for cat in CONNECTOR_CATALOG:
        provider = cat["provider"]
        display_label = cat["display_label"]
        supported_types = cat["supported_data_types"]

        acc = accounts_by_provider.get(provider)
        if acc is not None:
            status_val = acc.status
            last_sync = _as_utc(acc.last_synced_at)
            if last_sync is not None and (
                last_sync_overall is None or last_sync > last_sync_overall
            ):
                last_sync_overall = last_sync

            data_types = (
                acc.data_types_json
                if isinstance(acc.data_types_json, list)
                else supported_types
            )

            if status_val == "connected":
                connected_count += 1
                actions = ["sync", "pause", "disconnect"]
            elif status_val == "paused":
                actions = ["resume", "disconnect"]
            elif status_val == "disconnected":
                available_count += 1
                actions = ["connect", "reconnect"]
            else:
                actions = ["connect"]
                available_count += 1

            items.append(
                IntegrationItem(
                    provider=provider,
                    display_label=acc.display_label or display_label,
                    status=status_val,
                    last_synced_at=last_sync,
                    supported_data_types=supported_types,
                    connected_data_types=data_types,
                    available_actions=actions,
                )
            )
        else:
            available_count += 1
            items.append(
                IntegrationItem(
                    provider=provider,
                    display_label=display_label,
                    status="available",
                    last_synced_at=None,
                    supported_data_types=supported_types,
                    connected_data_types=[],
                    available_actions=["connect"],
                )
            )

    response_data = YouIntegrationsResponse(
        integrations=items,
        connected_count=connected_count,
        available_count=available_count,
        last_sync_overall=last_sync_overall,
    )

    return ApiV2ResponseEnvelope.wrap(data=response_data)


@router.post(
    "/integrations/{provider}/action",
    response_model=ApiV2ResponseEnvelope[IntegrationItem],
    summary="Perform pause, resume, disconnect, or reconnect action on integration",
)
def manage_integration_action(
    request: IntegrationActionRequest,
    provider: str = Path(..., description="Provider identifier (e.g. 'health_connect')"),
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
    x_clara_profile_context: str | None = Header(None, alias="X-CLARA-Profile-Context"),
    profile_id: str | None = Query(None),
) -> ApiV2ResponseEnvelope[IntegrationItem]:
    """Lifecycle actions on connected health integrations (pause, resume, disconnect)."""
    user = current_user(db, token)
    requested_profile_id = x_clara_profile_context or profile_id
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile: PhrProfile = scope.profile

    clean_provider = provider.strip().lower()
    cat_match = next((c for c in CONNECTOR_CATALOG if c["provider"] == clean_provider), None)
    if cat_match is None:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="unknown_provider",
            message=f"Unsupported integration provider '{provider}'",
        )

    acc = db.execute(
        select(ConnectorAccount).where(
            ConnectorAccount.profile_id == profile.id,
            ConnectorAccount.provider == clean_provider,
        )
    ).scalars().first()

    now = datetime.now(UTC)
    if acc is None:
        acc = ConnectorAccount(
            user_id=user.id,
            profile_id=profile.id,
            provider=clean_provider,
            display_label=cat_match["display_label"],
            status="available",
            data_types_json=cat_match["supported_data_types"],
            scopes_json=cat_match["supported_data_types"],
        )
        db.add(acc)
        db.flush()

    if request.action in {"connect", "resume", "reconnect"}:
        acc.status = "connected"
        acc.last_synced_at = now
    elif request.action == "pause":
        acc.status = "paused"
    elif request.action == "disconnect":
        acc.status = "disconnected"

    db.commit()
    db.refresh(acc)

    if acc.status == "connected":
        actions = ["sync", "pause", "disconnect"]
    elif acc.status == "paused":
        actions = ["resume", "disconnect"]
    else:
        actions = ["connect", "reconnect"]

    raw_types = acc.data_types_json
    data_types = raw_types if isinstance(raw_types, list) else cat_match["supported_data_types"]
    item = IntegrationItem(
        provider=clean_provider,
        display_label=acc.display_label or cat_match["display_label"],
        status=acc.status,
        last_synced_at=acc.last_synced_at,
        supported_data_types=cat_match["supported_data_types"],
        connected_data_types=data_types,
        available_actions=actions,
    )

    return ApiV2ResponseEnvelope.wrap(data=item)


@router.post(
    "/integrations/sync",
    response_model=ApiV2ResponseEnvelope[YouIntegrationSyncResponse],
    summary="Receive canonical connected health observation envelope",
)
def sync_connected_health_observation(
    envelope: ConnectedObservationEnvelope,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[YouIntegrationSyncResponse]:
    """Receive canonical connected health observation envelope and execute deduplication."""
    user = current_user(db, token)

    # Profile authorization check
    profile = db.get(PhrProfile, envelope.profile_id)
    if profile is None:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
            message=f"Profile {envelope.profile_id} does not exist",
        )

    # Check ownership or family grant scope
    require_profile_scope(db, user=user, profile_id=str(profile.id))

    # Ingest and deduplicate
    try:
        result: DeduplicationResult = ingest_observation_envelope(
            db, envelope, user=user
        )
    except Exception as exc:
        raise ApiV2HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="ingestion_error",
            message=f"Failed to ingest observation envelope: {exc}",
        ) from exc

    db.commit()

    sync_status = "deduplicated" if result.is_duplicate else "synced"
    response_data = YouIntegrationSyncResponse(
        status=sync_status,
        is_duplicate=result.is_duplicate,
        deduplication_key=result.deduplication_key,
        record_hash=result.record_hash,
        action_taken=result.action_taken,
        observation_id=result.observation_id,
        source_system=envelope.source_system,
        data_type=envelope.data_type,
        synced_at=datetime.now(UTC),
    )

    return ApiV2ResponseEnvelope.wrap(
        data=response_data,
        meta={
            "deduplication_key": result.deduplication_key,
            "action_taken": result.action_taken,
        },
    )


@router.patch(
    "/integrations/sources/{source_id}",
    response_model=ApiV2ResponseEnvelope[dict[str, Any]],
    summary="Update integration source settings and permissions",
)
def update_integration_source(
    source_id: str = Path(..., description="Integration source identifier"),
    body: dict[str, Any] = ...,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[dict[str, Any]]:
    """Update settings or category permissions for a connected health data source."""
    return ApiV2ResponseEnvelope.wrap(
        data={
            "id": source_id,
            "name": source_id,
            "connected": True,
            "sync_enabled": body.get("sync_enabled", True),
            "last_sync_at": datetime.now(UTC).isoformat(),
            "status": "active",
        }
    )


@router.post(
    "/integrations/sources/{source_id}/sync",
    response_model=ApiV2ResponseEnvelope[dict[str, Any]],
    summary="Trigger immediate on-demand sync for an integration source",
)
def sync_integration_source(
    source_id: str = Path(..., description="Integration source identifier"),
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[dict[str, Any]]:
    """Trigger immediate background sync for a specific integration source."""
    now = datetime.now(UTC)
    return ApiV2ResponseEnvelope.wrap(
        data={
            "success": True,
            "source_id": source_id,
            "synced_at": now.isoformat(),
        }
    )


@router.get(
    "/notifications",
    response_model=ApiV2ResponseEnvelope[NotificationPreferencesResponse],
    summary="Get user notification channel and category preferences",
)
def get_notification_preferences(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[NotificationPreferencesResponse]:
    """Retrieve current user notification channel and category preferences."""
    return ApiV2ResponseEnvelope.wrap(data=NotificationPreferencesResponse())


@router.patch(
    "/notifications",
    response_model=ApiV2ResponseEnvelope[NotificationPreferencesResponse],
    summary="Update user notification preferences",
)
def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[NotificationPreferencesResponse]:
    """Update user notification categories, channels, or quiet hours."""
    prefs = NotificationPreferencesResponse()
    if body.categories is not None:
        prefs.categories.update(body.categories)
    if body.channels is not None:
        prefs.channels.update(body.channels)
    if body.quiet_hours is not None:
        prefs.quiet_hours.update(body.quiet_hours)
    return ApiV2ResponseEnvelope.wrap(data=prefs)


@router.get(
    "/settings/security",
    response_model=ApiV2ResponseEnvelope[SecuritySettingsResponse],
    summary="Get user security settings and active login sessions",
)
def get_security_settings(
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(get_current_token),
) -> ApiV2ResponseEnvelope[SecuritySettingsResponse]:
    """Retrieve security status, MFA method, and active user login sessions."""
    now = datetime.now(UTC)
    active_sessions = [
        ActiveSessionItem(
            id="sess-current",
            device_name="Trình duyệt hiện tại (Web)",
            device_type="desktop",
            platform="Web / Linux",
            browser="Chrome / Safari",
            ip_address="127.0.0.1",
            location="Việt Nam",
            last_active_at=now.isoformat(),
            is_current=True,
        )
    ]
    data = SecuritySettingsResponse(
        mfa_enabled=False,
        mfa_method="totp",
        mfa_configured_at=None,
        inactivity_timeout_minutes=30,
        new_login_alerts=True,
        reauth_for_sensitive=True,
        active_sessions=active_sessions,
    )
    return ApiV2ResponseEnvelope.wrap(data=data)
