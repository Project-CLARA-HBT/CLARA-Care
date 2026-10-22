"""Audit schemas and domain contracts for multi-tenant billing boundary privacy.

Defines Pydantic models, enums, and validators enforcing:
1. Strict tenant isolation by tenant_id
2. Zero-PII/PHI financial metering invariant
3. Cryptographic scope digests and privacy audit receipts
4. Safe invoice representations with allowlisted accounting attributes
"""

from __future__ import annotations

import enum
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class MeterKind(str, enum.Enum):
    """Allowlisted billable meter dimensions in CLARA Care."""

    LLM_PROMPT_TOKENS = "llm_prompt_tokens"
    LLM_COMPLETION_TOKENS = "llm_completion_tokens"
    ASR_AUDIO_SECONDS = "asr_audio_seconds"
    OCR_DOCUMENT_PAGES = "ocr_document_pages"
    CAREGUARD_CHECKS = "careguard_checks"
    COUNCIL_CASES = "council_cases"
    STORAGE_GB_HOURS = "storage_gb_hours"
    API_REQUESTS = "api_requests"


class SurfaceKind(str, enum.Enum):
    """Subsystem surfaces producing billable meter events."""

    CHAT = "chat"
    RESEARCH = "research"
    SCRIBE = "scribe"
    CAREGUARD = "careguard"
    COUNCIL = "council"
    SELFMED = "selfmed"
    STORAGE = "storage"
    PLATFORM = "platform"


# Forbidden PII and PHI field names in billing metadata
FORBIDDEN_PHI_KEYS: frozenset[str] = frozenset(
    {
        "patient",
        "patient_id",
        "patient_name",
        "name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "phone_number",
        "address",
        "dob",
        "date_of_birth",
        "birth_date",
        "ssn",
        "citizen_id",
        "cccd",
        "cmnd",
        "query",
        "query_text",
        "prompt",
        "transcript",
        "transcription",
        "audio_raw",
        "diagnosis",
        "diagnoses",
        "symptom",
        "symptoms",
        "condition",
        "conditions",
        "medication",
        "medications",
        "drug",
        "drugs",
        "dosage",
        "allergy",
        "allergies",
        "lab_result",
        "lab_results",
        "vital_signs",
        "vitals",
        "notes",
        "clinical_notes",
    }
)


def _validate_phi_free_dict(d: dict[str, Any], path: str = "") -> None:
    """Recursively verify that no forbidden PHI/PII keys or clinical values appear."""
    for key, value in d.items():
        key_lower = str(key).strip().lower()
        current_path = f"{path}.{key}" if path else key
        if key_lower in FORBIDDEN_PHI_KEYS:
            raise ValueError(f"PHI/PII violation: forbidden key '{current_path}' in billing payload")
        if isinstance(value, dict):
            _validate_phi_free_dict(value, current_path)
        elif isinstance(value, (list, tuple, set)):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    _validate_phi_free_dict(item, f"{current_path}[{idx}]")
                elif isinstance(item, str):
                    _validate_phi_free_string(item, f"{current_path}[{idx}]")
        elif isinstance(value, str):
            _validate_phi_free_string(value, current_path)


def _validate_phi_free_string(text: str, field_name: str) -> None:
    """Detect obvious clinical leakage patterns in string values."""
    email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    if email_regex.search(text):
        raise ValueError(f"PII violation: email address detected in billing metadata '{field_name}'")


class TenantUsageEvent(BaseModel):
    """An immutable usage meter event emitted by subsystem surfaces."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = Field(..., min_length=3, max_length=64)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    surface: SurfaceKind
    meter_kind: MeterKind
    quantity: float = Field(..., ge=0.0)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    tier: str = Field(default="standard", max_length=32)
    metadata_tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("tenant_id cannot be empty or whitespace")
        if not re.match(r"^[a-zA-Z0-9_-]+$", cleaned):
            raise ValueError("tenant_id contains invalid characters")
        return cleaned

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        import math

        if math.isnan(v) or math.isinf(v) or v < 0.0:
            raise ValueError("quantity must be a finite non-negative number")
        return round(v, 4)

    @model_validator(mode="after")
    def check_metadata_for_phi(self) -> TenantUsageEvent:
        if self.metadata_tags:
            _validate_phi_free_dict(self.metadata_tags)
        return self


class MeterAggregationSummary(BaseModel):
    """Sub-total for a specific meter category within a tenant's billing window."""

    meter_kind: MeterKind
    total_units: float = 0.0
    unit_name: str
    unit_price_cents: int = 0
    subtotal_cents: int = 0


class TenantUsageAggregation(BaseModel):
    """Aggregated usage and billing metrics for a specific tenant and time window."""

    tenant_id: str
    range_start: datetime
    range_end: datetime
    meters: dict[str, MeterAggregationSummary] = Field(default_factory=dict)
    surface_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_cost_cents: int = 0
    currency: str = "VND"
    has_data: bool = False
    event_count: int = 0
    scope_digest: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @staticmethod
    def compute_scope_digest(tenant_id: str, start: datetime, end: datetime, event_count: int, total_cents: int) -> str:
        """Compute tamper-evident SHA-256 digest of aggregation boundary parameters."""
        raw = f"{tenant_id}:{start.isoformat()}:{end.isoformat()}:{event_count}:{total_cents}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InvoiceLineItem(BaseModel):
    """PII-free line item in a tenant billing invoice."""

    meter_kind: str
    surface: str
    units: float
    unit_price_cents: int
    line_total_cents: int


class TenantInvoice(BaseModel):
    """Formal invoice representation for organization billing."""

    invoice_id: str
    tenant_id: str
    billing_period: str  # YYYY-MM
    issued_at: datetime
    due_at: datetime
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str = "VND"
    status: str = "issued"  # issued, paid, overdue
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    cryptographic_seal: str


class PrivacyAuditReceipt(BaseModel):
    """Cryptographic audit record proving tenant boundary enforcement."""

    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:16]}")
    scanner_version: str = "1.0.0-ph04"
    tenant_id: str
    scope_digest: str
    result: str = "pass"
    finding_count: int = 0
    artifact_digest: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    verified_invariants: list[str] = Field(default_factory=list)


class ComplianceBoundaryEvent(BaseModel):
    """Security/compliance audit event for tenant boundary violations."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "TENANT_BOUNDARY_PROBE"
    attempted_tenant_id: str
    authenticated_tenant_id: str
    caller_role: str
    endpoint: str
    severity: str = "CRITICAL"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    subject_digest: str  # SHA-256 of user identifier, zero plaintext PII
