"""GLHS Canonical Failure Reason Codes, Categories, and HTTP Mappings.

Section 16 R4 Master Specification Canonical Machine-Readable Failure Reason Codes.
Enforces standard failure reason codes across GRWC admission verification,
commitment gateway, and commit kernel execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasonCategory(str, Enum):
    """Canonical GLHS Failure Reason Categories."""

    BINDING = "binding"
    SNAPSHOT = "snapshot"
    COORDINATE = "coordinate"
    EVIDENCE = "evidence"
    DEPENDENCY = "dependency"
    GOVERNANCE = "governance"
    LINEAGE = "lineage"
    RECEIPT = "receipt"


@dataclass(frozen=True)
class ReasonCodeMetadata:
    """Metadata for a canonical machine-readable failure reason code."""

    code: str
    category: ReasonCategory
    http_status: int
    description: str


# Canonical Reason Codes Definition Catalog (33 Standard Codes across 8 Categories)
REASON_CODES_CATALOG: dict[str, ReasonCodeMetadata] = {
    # --- Binding Errors ---
    "binding_missing": ReasonCodeMetadata(
        code="binding_missing",
        category=ReasonCategory.BINDING,
        http_status=400,
        description="Inference context binding record is missing or required.",
    ),
    "binding_not_completed": ReasonCodeMetadata(
        code="binding_not_completed",
        category=ReasonCategory.BINDING,
        http_status=412,
        description="Inference context binding status is pending, failed, or incomplete.",
    ),
    "dispatch_not_attested": ReasonCodeMetadata(
        code="dispatch_not_attested",
        category=ReasonCategory.BINDING,
        http_status=412,
        description="Inference transport dispatch was not attested before write admission.",
    ),
    "transport_digest_missing": ReasonCodeMetadata(
        code="transport_digest_missing",
        category=ReasonCategory.BINDING,
        http_status=400,
        description="Transport payload digest (D3 / H_trans) is missing.",
    ),
    "transport_digest_mismatch": ReasonCodeMetadata(
        code="transport_digest_mismatch",
        category=ReasonCategory.BINDING,
        http_status=422,
        description="Transport payload digest (D3 / H_trans) mismatch.",
    ),
    "semantic_envelope_mismatch": ReasonCodeMetadata(
        code="semantic_envelope_mismatch",
        category=ReasonCategory.BINDING,
        http_status=422,
        description="Semantic request envelope digest (D2 / H_sem) mismatch.",
    ),
    # --- Snapshot Errors ---
    "snapshot_missing": ReasonCodeMetadata(
        code="snapshot_missing",
        category=ReasonCategory.SNAPSHOT,
        http_status=404,
        description="Referenced THSS snapshot manifest record is missing.",
    ),
    "snapshot_identity_mismatch": ReasonCodeMetadata(
        code="snapshot_identity_mismatch",
        category=ReasonCategory.SNAPSHOT,
        http_status=422,
        description="Snapshot public identifier mismatch across lineage or binding.",
    ),
    "projection_digest_mismatch": ReasonCodeMetadata(
        code="projection_digest_mismatch",
        category=ReasonCategory.SNAPSHOT,
        http_status=422,
        description="Model-visible health projection digest (D1 / H_proj) mismatch.",
    ),
    "manifest_digest_mismatch": ReasonCodeMetadata(
        code="manifest_digest_mismatch",
        category=ReasonCategory.SNAPSHOT,
        http_status=422,
        description="Snapshot manifest digest mismatch.",
    ),
    # --- Coordinate Errors ---
    "actor_mismatch": ReasonCodeMetadata(
        code="actor_mismatch",
        category=ReasonCategory.COORDINATE,
        http_status=403,
        description="Actor user coordinate mismatch between inference and commit.",
    ),
    "role_mismatch": ReasonCodeMetadata(
        code="role_mismatch",
        category=ReasonCategory.COORDINATE,
        http_status=403,
        description="Actor role coordinate mismatch between inference and commit.",
    ),
    "purpose_mismatch": ReasonCodeMetadata(
        code="purpose_mismatch",
        category=ReasonCategory.COORDINATE,
        http_status=403,
        description="Purpose coordinate mismatch between inference and commit.",
    ),
    "task_mismatch": ReasonCodeMetadata(
        code="task_mismatch",
        category=ReasonCategory.COORDINATE,
        http_status=403,
        description="Task coordinate mismatch between inference and commit.",
    ),
    # --- Evidence Errors ---
    "evidence_undisclosed": ReasonCodeMetadata(
        code="evidence_undisclosed",
        category=ReasonCategory.EVIDENCE,
        http_status=422,
        description="Asserted evidence item was omitted from prompt disclosure snapshot.",
    ),
    # --- Dependency Errors ---
    "dependency_missing": ReasonCodeMetadata(
        code="dependency_missing",
        category=ReasonCategory.DEPENDENCY,
        http_status=422,
        description="Required entity partition or dependency vector coordinate is missing.",
    ),
    "dependency_access_mode_mismatch": ReasonCodeMetadata(
        code="dependency_access_mode_mismatch",
        category=ReasonCategory.DEPENDENCY,
        http_status=422,
        description="Dependency access mode (READ vs WRITE) mismatch.",
    ),
    "dependency_version_stale": ReasonCodeMetadata(
        code="dependency_version_stale",
        category=ReasonCategory.DEPENDENCY,
        http_status=409,
        description="Observed entity partition state version is stale under locks.",
    ),
    "dependency_digest_mismatch": ReasonCodeMetadata(
        code="dependency_digest_mismatch",
        category=ReasonCategory.DEPENDENCY,
        http_status=409,
        description="Observed entity partition content digest mismatch under locks.",
    ),
    # --- Governance Errors ---
    "state_stale": ReasonCodeMetadata(
        code="state_stale",
        category=ReasonCategory.GOVERNANCE,
        http_status=409,
        description="Target profile base state version has advanced since proposal creation.",
    ),
    "policy_stale": ReasonCodeMetadata(
        code="policy_stale",
        category=ReasonCategory.GOVERNANCE,
        http_status=409,
        description="System policy epoch version has advanced since inference snapshot.",
    ),
    "consent_stale": ReasonCodeMetadata(
        code="consent_stale",
        category=ReasonCategory.GOVERNANCE,
        http_status=409,
        description="Subject consent epoch version has advanced since inference snapshot.",
    ),
    "consent_revoked": ReasonCodeMetadata(
        code="consent_revoked",
        category=ReasonCategory.GOVERNANCE,
        http_status=403,
        description="Subject consent for domain/purpose was revoked prior to commit.",
    ),
    "snapshot_expired": ReasonCodeMetadata(
        code="snapshot_expired",
        category=ReasonCategory.GOVERNANCE,
        http_status=410,
        description="THSS snapshot validity window has expired.",
    ),
    # --- Lineage Errors ---
    "lineage_binding_missing": ReasonCodeMetadata(
        code="lineage_binding_missing",
        category=ReasonCategory.LINEAGE,
        http_status=422,
        description="Descendant proposal lacks root inference context binding reference.",
    ),
    "lineage_binding_mismatch": ReasonCodeMetadata(
        code="lineage_binding_mismatch",
        category=ReasonCategory.LINEAGE,
        http_status=422,
        description="Descendant proposal inference binding ID differs from root proposal.",
    ),
    "lineage_snapshot_mismatch": ReasonCodeMetadata(
        code="lineage_snapshot_mismatch",
        category=ReasonCategory.LINEAGE,
        http_status=422,
        description="Descendant proposal snapshot ID differs from root proposal snapshot.",
    ),
    "lineage_downgrade": ReasonCodeMetadata(
        code="lineage_downgrade",
        category=ReasonCategory.LINEAGE,
        http_status=403,
        description="Lineage anti-downgrade violation (e.g. attempting base_version_only path).",
    ),
    "lineage_cycle": ReasonCodeMetadata(
        code="lineage_cycle",
        category=ReasonCategory.LINEAGE,
        http_status=422,
        description="Cyclic parent proposal references detected during lineage traversal.",
    ),
    "lineage_depth_exceeded": ReasonCodeMetadata(
        code="lineage_depth_exceeded",
        category=ReasonCategory.LINEAGE,
        http_status=422,
        description="Proposal lineage traversal depth exceeds maximum limit (depth > 4).",
    ),
    # --- Receipt Errors ---
    "provider_receipt_invalid": ReasonCodeMetadata(
        code="provider_receipt_invalid",
        category=ReasonCategory.RECEIPT,
        http_status=502,
        description="Inference provider receipt verification failed or signature invalid.",
    ),
    "provider_receipt_request_mismatch": ReasonCodeMetadata(
        code="provider_receipt_request_mismatch",
        category=ReasonCategory.RECEIPT,
        http_status=502,
        description="Provider receipt transport payload request digest mismatch.",
    ),
    "provider_receipt_response_mismatch": ReasonCodeMetadata(
        code="provider_receipt_response_mismatch",
        category=ReasonCategory.RECEIPT,
        http_status=502,
        description="Provider receipt response payload digest mismatch.",
    ),
}

# String constants for code completion & direct usage
BINDING_MISSING = "binding_missing"
BINDING_NOT_COMPLETED = "binding_not_completed"
DISPATCH_NOT_ATTESTED = "dispatch_not_attested"
TRANSPORT_DIGEST_MISSING = "transport_digest_missing"
TRANSPORT_DIGEST_MISMATCH = "transport_digest_mismatch"
SEMANTIC_ENVELOPE_MISMATCH = "semantic_envelope_mismatch"

SNAPSHOT_MISSING = "snapshot_missing"
SNAPSHOT_IDENTITY_MISMATCH = "snapshot_identity_mismatch"
PROJECTION_DIGEST_MISMATCH = "projection_digest_mismatch"
MANIFEST_DIGEST_MISMATCH = "manifest_digest_mismatch"

ACTOR_MISMATCH = "actor_mismatch"
ROLE_MISMATCH = "role_mismatch"
PURPOSE_MISMATCH = "purpose_mismatch"
TASK_MISMATCH = "task_mismatch"

EVIDENCE_UNDISCLOSED = "evidence_undisclosed"

DEPENDENCY_MISSING = "dependency_missing"
DEPENDENCY_ACCESS_MODE_MISMATCH = "dependency_access_mode_mismatch"
DEPENDENCY_VERSION_STALE = "dependency_version_stale"
DEPENDENCY_DIGEST_MISMATCH = "dependency_digest_mismatch"

STATE_STALE = "state_stale"
POLICY_STALE = "policy_stale"
CONSENT_STALE = "consent_stale"
CONSENT_REVOKED = "consent_revoked"
SNAPSHOT_EXPIRED = "snapshot_expired"

LINEAGE_BINDING_MISSING = "lineage_binding_missing"
LINEAGE_BINDING_MISMATCH = "lineage_binding_mismatch"
LINEAGE_SNAPSHOT_MISMATCH = "lineage_snapshot_mismatch"
LINEAGE_DOWNGRADE = "lineage_downgrade"
LINEAGE_CYCLE = "lineage_cycle"
LINEAGE_DEPTH_EXCEEDED = "lineage_depth_exceeded"

PROVIDER_RECEIPT_INVALID = "provider_receipt_invalid"
PROVIDER_RECEIPT_REQUEST_MISMATCH = "provider_receipt_request_mismatch"
PROVIDER_RECEIPT_RESPONSE_MISMATCH = "provider_receipt_response_mismatch"

# Legacy or internal exception string mappings to canonical codes
LEGACY_REASON_CODE_MAP: dict[str, str] = {
    "commitment_lineage_base_only_forbidden": "lineage_downgrade",
    "commitment_lineage_binding_missing": "lineage_binding_missing",
    "commitment_lineage_binding_required": "lineage_binding_missing",
    "commitment_lineage_binding_mismatch": "lineage_binding_mismatch",
    "commitment_lineage_snapshot_mismatch": "lineage_snapshot_mismatch",
    "commitment_lineage_manifest_mismatch": "manifest_digest_mismatch",
    "commitment_lineage_manifest_digest_mismatch": "manifest_digest_mismatch",
    "commitment_lineage_cycle_detected": "lineage_cycle",
    "commitment_lineage_depth_exceeded": "lineage_depth_exceeded",
    "commitment_review_downgrade_forbidden": "lineage_downgrade",
    "model_base_proposal_forbidden": "lineage_downgrade",
    "proposal_evidence_not_disclosed": "evidence_undisclosed",
    "proposal_snapshot_scope_forbidden": "snapshot_identity_mismatch",
    "proposal_manifest_digest_mismatch": "manifest_digest_mismatch",
    "proposal_envelope_digest_mismatch": "semantic_envelope_mismatch",
    "transport_payload_digest_mismatch": "transport_digest_mismatch",
    "transport_payload_digest_missing": "transport_digest_missing",
    "stale_base_state_version": "state_stale",
    "stale_consent_version": "consent_stale",
    "assertion_policy_mismatch": "policy_stale",
    "inference_binding_snapshot_expired": "snapshot_expired",
    "proposal_snapshot_expired": "snapshot_expired",
    "attestation_actor_mismatch": "actor_mismatch",
    "binding_actor_mismatch": "actor_mismatch",
    "binding_actor_role_mismatch": "role_mismatch",
    "role_changed": "role_mismatch",
    "proposal_snapshot_actor_role_mismatch": "role_mismatch",
    "attestation_purpose_mismatch": "purpose_mismatch",
    "binding_purpose_mismatch": "purpose_mismatch",
    "attestation_task_mismatch": "task_mismatch",
    "binding_task_mismatch": "task_mismatch",
    "attestation_level_unmet": "dispatch_not_attested",
    "provider_receipt_verification_failed": "provider_receipt_invalid",
    "snapshot_manifest_invalid": "snapshot_missing",
}


def canonicalize_reason_code(raw_code: str) -> str:
    """Resolve raw or legacy exception string to canonical machine-readable reason code."""

    code_str = str(raw_code).strip()
    if ":" in code_str:
        code_str = code_str.split(":")[0].strip()
    if code_str in REASON_CODES_CATALOG:
        return code_str
    return LEGACY_REASON_CODE_MAP.get(code_str, code_str)


def get_reason_code_metadata(code: str) -> ReasonCodeMetadata | None:
    """Retrieve metadata for a canonical failure reason code."""

    canonical = canonicalize_reason_code(code)
    return REASON_CODES_CATALOG.get(canonical)


def get_http_status_code(code: str, default: int = 400) -> int:
    """Return the canonical HTTP status code for a failure reason code."""

    meta = get_reason_code_metadata(code)
    return meta.http_status if meta is not None else default


def get_reason_category(code: str) -> ReasonCategory | None:
    """Return the canonical failure category for a reason code."""

    meta = get_reason_code_metadata(code)
    return meta.category if meta is not None else None


def is_valid_reason_code(code: str) -> bool:
    """Check if a reason code is a known canonical code or legacy alias."""

    canonical = canonicalize_reason_code(code)
    return canonical in REASON_CODES_CATALOG


__all__ = [
    "ACTOR_MISMATCH",
    "BINDING_MISSING",
    "BINDING_NOT_COMPLETED",
    "CONSENT_REVOKED",
    "CONSENT_STALE",
    "DEPENDENCY_ACCESS_MODE_MISMATCH",
    "DEPENDENCY_DIGEST_MISMATCH",
    "DEPENDENCY_MISSING",
    "DEPENDENCY_VERSION_STALE",
    "DISPATCH_NOT_ATTESTED",
    "EVIDENCE_UNDISCLOSED",
    "LEGACY_REASON_CODE_MAP",
    "LINEAGE_BINDING_MISMATCH",
    "LINEAGE_BINDING_MISSING",
    "LINEAGE_CYCLE",
    "LINEAGE_DEPTH_EXCEEDED",
    "LINEAGE_DOWNGRADE",
    "LINEAGE_SNAPSHOT_MISMATCH",
    "MANIFEST_DIGEST_MISMATCH",
    "POLICY_STALE",
    "PROJECTION_DIGEST_MISMATCH",
    "PROVIDER_RECEIPT_INVALID",
    "PROVIDER_RECEIPT_REQUEST_MISMATCH",
    "PROVIDER_RECEIPT_RESPONSE_MISMATCH",
    "PURPOSE_MISMATCH",
    "REASON_CODES_CATALOG",
    "ROLE_MISMATCH",
    "SEMANTIC_ENVELOPE_MISMATCH",
    "SNAPSHOT_EXPIRED",
    "SNAPSHOT_IDENTITY_MISMATCH",
    "SNAPSHOT_MISSING",
    "STATE_STALE",
    "TASK_MISMATCH",
    "TRANSPORT_DIGEST_MISMATCH",
    "TRANSPORT_DIGEST_MISSING",
    "ReasonCategory",
    "ReasonCodeMetadata",
    "canonicalize_reason_code",
    "get_http_status_code",
    "get_reason_category",
    "get_reason_code_metadata",
    "is_valid_reason_code",
]
