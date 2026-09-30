"""Unit tests for GLHS Canonical Failure Reason Codes & HTTP Mapping."""

from __future__ import annotations

from clara_api.glhs.reason_codes import (
    ACTOR_MISMATCH,
    BINDING_MISSING,
    BINDING_NOT_COMPLETED,
    CONSENT_REVOKED,
    CONSENT_STALE,
    DEPENDENCY_ACCESS_MODE_MISMATCH,
    DEPENDENCY_DIGEST_MISMATCH,
    DEPENDENCY_MISSING,
    DEPENDENCY_VERSION_STALE,
    DISPATCH_NOT_ATTESTED,
    EVIDENCE_UNDISCLOSED,
    LINEAGE_BINDING_MISMATCH,
    LINEAGE_BINDING_MISSING,
    LINEAGE_CYCLE,
    LINEAGE_DEPTH_EXCEEDED,
    LINEAGE_DOWNGRADE,
    LINEAGE_SNAPSHOT_MISMATCH,
    MANIFEST_DIGEST_MISMATCH,
    POLICY_STALE,
    PROJECTION_DIGEST_MISMATCH,
    PROVIDER_RECEIPT_INVALID,
    PROVIDER_RECEIPT_REQUEST_MISMATCH,
    PROVIDER_RECEIPT_RESPONSE_MISMATCH,
    PURPOSE_MISMATCH,
    REASON_CODES_CATALOG,
    ROLE_MISMATCH,
    SEMANTIC_ENVELOPE_MISMATCH,
    SNAPSHOT_EXPIRED,
    SNAPSHOT_IDENTITY_MISMATCH,
    SNAPSHOT_MISSING,
    STATE_STALE,
    TASK_MISMATCH,
    TRANSPORT_DIGEST_MISMATCH,
    TRANSPORT_DIGEST_MISSING,
    ReasonCategory,
    canonicalize_reason_code,
    get_http_status_code,
    get_reason_category,
    get_reason_code_metadata,
    is_valid_reason_code,
)

EXPECTED_CANONICAL_CODES: dict[str, tuple[ReasonCategory, int]] = {
    # Binding errors
    BINDING_MISSING: (ReasonCategory.BINDING, 400),
    BINDING_NOT_COMPLETED: (ReasonCategory.BINDING, 412),
    DISPATCH_NOT_ATTESTED: (ReasonCategory.BINDING, 412),
    TRANSPORT_DIGEST_MISSING: (ReasonCategory.BINDING, 400),
    TRANSPORT_DIGEST_MISMATCH: (ReasonCategory.BINDING, 422),
    SEMANTIC_ENVELOPE_MISMATCH: (ReasonCategory.BINDING, 422),
    # Snapshot errors
    SNAPSHOT_MISSING: (ReasonCategory.SNAPSHOT, 404),
    SNAPSHOT_IDENTITY_MISMATCH: (ReasonCategory.SNAPSHOT, 422),
    PROJECTION_DIGEST_MISMATCH: (ReasonCategory.SNAPSHOT, 422),
    MANIFEST_DIGEST_MISMATCH: (ReasonCategory.SNAPSHOT, 422),
    # Coordinate errors
    ACTOR_MISMATCH: (ReasonCategory.COORDINATE, 403),
    ROLE_MISMATCH: (ReasonCategory.COORDINATE, 403),
    PURPOSE_MISMATCH: (ReasonCategory.COORDINATE, 403),
    TASK_MISMATCH: (ReasonCategory.COORDINATE, 403),
    # Evidence errors
    EVIDENCE_UNDISCLOSED: (ReasonCategory.EVIDENCE, 422),
    # Dependency errors
    DEPENDENCY_MISSING: (ReasonCategory.DEPENDENCY, 422),
    DEPENDENCY_ACCESS_MODE_MISMATCH: (ReasonCategory.DEPENDENCY, 422),
    DEPENDENCY_VERSION_STALE: (ReasonCategory.DEPENDENCY, 409),
    DEPENDENCY_DIGEST_MISMATCH: (ReasonCategory.DEPENDENCY, 409),
    # Governance errors
    STATE_STALE: (ReasonCategory.GOVERNANCE, 409),
    POLICY_STALE: (ReasonCategory.GOVERNANCE, 409),
    CONSENT_STALE: (ReasonCategory.GOVERNANCE, 409),
    CONSENT_REVOKED: (ReasonCategory.GOVERNANCE, 403),
    SNAPSHOT_EXPIRED: (ReasonCategory.GOVERNANCE, 410),
    # Lineage errors
    LINEAGE_BINDING_MISSING: (ReasonCategory.LINEAGE, 422),
    LINEAGE_BINDING_MISMATCH: (ReasonCategory.LINEAGE, 422),
    LINEAGE_SNAPSHOT_MISMATCH: (ReasonCategory.LINEAGE, 422),
    LINEAGE_DOWNGRADE: (ReasonCategory.LINEAGE, 403),
    LINEAGE_CYCLE: (ReasonCategory.LINEAGE, 422),
    LINEAGE_DEPTH_EXCEEDED: (ReasonCategory.LINEAGE, 422),
    # Receipt errors
    PROVIDER_RECEIPT_INVALID: (ReasonCategory.RECEIPT, 502),
    PROVIDER_RECEIPT_REQUEST_MISMATCH: (ReasonCategory.RECEIPT, 502),
    PROVIDER_RECEIPT_RESPONSE_MISMATCH: (ReasonCategory.RECEIPT, 502),
}


def test_all_canonical_reason_codes_present() -> None:
    assert len(EXPECTED_CANONICAL_CODES) == 33
    for code, (category, status_code) in EXPECTED_CANONICAL_CODES.items():
        assert code in REASON_CODES_CATALOG, f"Missing code: {code}"
        meta = REASON_CODES_CATALOG[code]
        assert meta.code == code
        assert meta.category == category
        assert meta.http_status == status_code
        assert meta.description != ""


def test_helper_functions() -> None:
    assert is_valid_reason_code("dispatch_not_attested") is True
    assert is_valid_reason_code("unknown_garbage_code") is False

    assert get_http_status_code("lineage_downgrade") == 403
    assert get_http_status_code("state_stale") == 409
    assert get_http_status_code("snapshot_expired") == 410
    assert get_http_status_code("provider_receipt_invalid") == 502
    assert get_http_status_code("unknown", default=418) == 418

    assert get_reason_category("actor_mismatch") == ReasonCategory.COORDINATE
    assert get_reason_category("evidence_undisclosed") == ReasonCategory.EVIDENCE
    assert get_reason_category("unknown") is None

    meta = get_reason_code_metadata("transport_digest_mismatch")
    assert meta is not None
    assert meta.category == ReasonCategory.BINDING
    assert meta.http_status == 422


def test_legacy_reason_code_canonicalization() -> None:
    assert canonicalize_reason_code("commitment_lineage_cycle_detected") == LINEAGE_CYCLE
    assert canonicalize_reason_code("commitment_lineage_base_only_forbidden") == LINEAGE_DOWNGRADE
    assert canonicalize_reason_code("proposal_evidence_not_disclosed") == EVIDENCE_UNDISCLOSED
    assert canonicalize_reason_code("stale_base_state_version") == STATE_STALE
    assert canonicalize_reason_code("assertion_policy_mismatch") == POLICY_STALE

    # Exception string prefix parsing
    assert canonicalize_reason_code("lineage_cycle: detail message") == LINEAGE_CYCLE
    assert get_http_status_code("commitment_lineage_cycle_detected") == 422
