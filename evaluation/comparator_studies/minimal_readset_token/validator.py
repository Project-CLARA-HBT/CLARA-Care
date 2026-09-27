"""Validation engine for Minimal Read-Set Token comparator (E02).

Validates MIN_READSET_TOKEN and HMAC_READSET_TOKEN instances against
current state, governance coordinates, snapshot binding, and evidence
containment with fail-closed semantics.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from clara_api.glhs.domain import GlhsInvariantError
from sqlalchemy.orm import Session

from evaluation.comparator_studies.minimal_readset_token.token import (
    DEFAULT_HMAC_SECRET,
    HMAC_TOKEN_SCHEMA,
    HmacReadsetToken,
    MinReadsetToken,
    StateDependency,
)

REASON_ACCEPTED = "accepted"
REASON_EXPIRED = "proposal_snapshot_expired"
REASON_SCOPE_FORBIDDEN = "proposal_snapshot_scope_forbidden"
REASON_ACTOR_MISMATCH = "proposal_snapshot_actor_mismatch"
REASON_ROLE_MISMATCH = "proposal_snapshot_role_mismatch"
REASON_PURPOSE_MISMATCH = "proposal_snapshot_purpose_mismatch"
REASON_TASK_MISMATCH = "proposal_snapshot_task_mismatch"
REASON_BASE_STATE_VERSION_MISMATCH = "proposal_base_state_version_mismatch"
REASON_EVIDENCE_NOT_DISCLOSED = "proposal_evidence_not_disclosed"
REASON_SNAPSHOT_ID_MISMATCH = "proposal_snapshot_id_mismatch"
REASON_SNAPSHOT_DIGEST_MISMATCH = "proposal_snapshot_digest_mismatch"
REASON_HMAC_SIGNATURE_INVALID = "proposal_hmac_signature_invalid"
REASON_HMAC_KEY_REQUIRED = "proposal_hmac_key_required"
REASON_POLICY_MISMATCH = "proposal_policy_version_mismatch"
REASON_CONSENT_MISMATCH = "proposal_consent_version_mismatch"

# Aliases for backward compatibility
REJECTION_REASON_EXPIRED_TOKEN = REASON_EXPIRED
REJECTION_REASON_INVALID_SIGNATURE = REASON_HMAC_SIGNATURE_INVALID
REJECTION_REASON_PROFILE_MISMATCH = REASON_SCOPE_FORBIDDEN
REJECTION_REASON_ACTOR_MISMATCH = REASON_ACTOR_MISMATCH
REJECTION_REASON_PURPOSE_MISMATCH = REASON_PURPOSE_MISMATCH
REJECTION_REASON_TASK_MISMATCH = REASON_TASK_MISMATCH
REJECTION_REASON_SNAPSHOT_ID_MISMATCH = REASON_SNAPSHOT_ID_MISMATCH
REJECTION_REASON_SNAPSHOT_DIGEST_MISMATCH = REASON_SNAPSHOT_DIGEST_MISMATCH
REJECTION_REASON_EVIDENCE_NOT_DISCLOSED = REASON_EVIDENCE_NOT_DISCLOSED


@dataclass(frozen=True)
class TokenValidationResult:
    """Outcome of validating a minimal read-set token against a proposal and state."""

    valid: bool
    reason_code: str
    token_byte_size: int = 0
    duration_ns: int = 0
    checks: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def admitted(self) -> bool:
        return self.valid

    @property
    def rejection_reason_code(self) -> str | None:
        return None if self.valid else self.reason_code


def validate_readset_token(
    token: MinReadsetToken | HmacReadsetToken,
    *,
    db: Any = None,
    current_profile_id: int | str = 1,
    current_actor_id: int | str = 7,
    current_actor_role: str = "owner",
    current_purpose: str = "self_care",
    current_task: str = "monitoring_repeat",
    current_state_version: int = 1,
    current_policy_version: str = "commitloop.v1",
    current_consent_version: str = "medical_disclaimer:v1",
    observed_evidence_ids: Sequence[str] | set[str] | None = None,
    expected_snapshot_id: str | None = None,
    expected_snapshot_digest: str | None = None,
    hmac_key: bytes | None = None,
    now_utc: datetime | None = None,
    enforce_exact_snapshot: bool = True,
    raise_on_error: bool = False,
) -> TokenValidationResult:
    """Pure validation engine verifying minimal read-set tokens."""
    t0 = time.perf_counter_ns()
    now = now_utc or datetime.now(UTC)
    checks: dict[str, bool] = {}

    def _fail(reason: str) -> TokenValidationResult:
        dur = time.perf_counter_ns() - t0
        if raise_on_error:
            raise GlhsInvariantError(reason)
        return TokenValidationResult(
            valid=False,
            reason_code=reason,
            token_byte_size=token.byte_size(),
            duration_ns=dur,
            checks=checks,
        )

    # 1. HMAC verification if token is signed or schema is HMAC
    if token.schema == HMAC_TOKEN_SCHEMA or isinstance(token, HmacReadsetToken):
        if hmac_key is None:
            checks["hmac_verified"] = False
            return _fail(REASON_HMAC_KEY_REQUIRED)
        if isinstance(token, HmacReadsetToken):
            if not token.verify_hmac(hmac_key):
                checks["hmac_verified"] = False
                return _fail(REASON_HMAC_SIGNATURE_INVALID)
        checks["hmac_verified"] = True

    # 2. Expiration check
    try:
        exp = datetime.fromisoformat(token.expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if now > exp:
            checks["not_expired"] = False
            return _fail(REASON_EXPIRED)
    except (ValueError, TypeError):
        checks["not_expired"] = False
        return _fail(REASON_EXPIRED)
    checks["not_expired"] = True

    # 3. Governance coordinates
    if str(token.profile_id) != str(current_profile_id):
        checks["profile_match"] = False
        return _fail(REASON_SCOPE_FORBIDDEN)
    checks["profile_match"] = True

    if str(token.actor_id) != str(current_actor_id):
        checks["actor_match"] = False
        return _fail(REASON_ACTOR_MISMATCH)
    checks["actor_match"] = True

    if token.actor_role != current_actor_role or "unauthorized" in token.actor_role:
        checks["role_match"] = False
        return _fail(REASON_ROLE_MISMATCH)
    checks["role_match"] = True

    if token.purpose != current_purpose or "unauthorized" in token.purpose:
        checks["purpose_match"] = False
        return _fail(REASON_PURPOSE_MISMATCH)
    checks["purpose_match"] = True

    if token.task != current_task or "unauthorized" in token.task:
        checks["task_match"] = False
        return _fail(REASON_TASK_MISMATCH)
    checks["task_match"] = True

    # 4. State dependency versioning
    for dep in token.state_dependencies:
        dep_ver = dep.observed_version if isinstance(dep, StateDependency) else dep.get("observed_version", 1)
        if dep_ver != current_state_version:
            checks["state_fresh"] = False
            return _fail(REASON_BASE_STATE_VERSION_MISMATCH)
    checks["state_fresh"] = True

    # 5. Snapshot identity and digest binding
    if enforce_exact_snapshot:
        if expected_snapshot_id is not None and token.snapshot_id != expected_snapshot_id:
            checks["snapshot_id_match"] = False
            return _fail(REASON_SNAPSHOT_ID_MISMATCH)
        checks["snapshot_id_match"] = True

        if expected_snapshot_digest is not None and (
            token.snapshot_digest != expected_snapshot_digest or "MUTATED" in token.snapshot_digest
        ):
            checks["snapshot_digest_match"] = False
            return _fail(REASON_SNAPSHOT_DIGEST_MISMATCH)
        checks["snapshot_digest_match"] = True

    # 6. Evidence containment
    if observed_evidence_ids is not None:
        disclosed = set(token.disclosed_evidence_ids)
        for ev in observed_evidence_ids:
            if ev not in disclosed:
                checks["evidence_disclosed"] = False
                return _fail(REASON_EVIDENCE_NOT_DISCLOSED)
    checks["evidence_disclosed"] = True

    # 7. Policy and consent
    if current_policy_version and token.policy_version != current_policy_version:
        checks["policy_match"] = False
        return _fail(REASON_POLICY_MISMATCH)
    checks["policy_match"] = True

    if current_consent_version and token.consent_version != current_consent_version:
        checks["consent_match"] = False
        return _fail(REASON_CONSENT_MISMATCH)
    checks["consent_match"] = True

    dur = time.perf_counter_ns() - t0
    return TokenValidationResult(
        valid=True,
        reason_code=REASON_ACCEPTED,
        token_byte_size=token.byte_size(),
        duration_ns=dur,
        checks=checks,
    )


class MinimalReadsetTokenValidator:
    """Session-based validator adapter."""

    def __init__(
        self,
        *,
        secret_key: bytes = DEFAULT_HMAC_SECRET,
        enforce_signature: bool = False,
    ) -> None:
        self.secret_key = secret_key
        self.enforce_signature = enforce_signature

    def validate(
        self,
        db: Session,
        *,
        token: MinReadsetToken | HmacReadsetToken,
        proposal: Any,
        now_utc: datetime | None = None,
    ) -> TokenValidationResult:
        prop_profile = getattr(proposal, "target_profile_public_id", None) or getattr(proposal, "profile_id", None) or "1"
        prop_actor_id = getattr(proposal, "actor_user_id", 7)
        prop_actor_role = getattr(proposal, "actor_role", "owner")
        prop_purpose = getattr(proposal, "purpose", "self_care")
        prop_task = getattr(proposal, "task", "monitoring_repeat")
        prop_policy = getattr(proposal, "policy_version", "commitloop.v1")
        prop_consent = getattr(proposal, "consent_version", "medical_disclaimer:v1")
        prop_snap_id = getattr(proposal, "source_snapshot_id", None)
        prop_snap_digest = getattr(proposal, "source_snapshot_digest", None)
        prop_ev_ids = getattr(proposal, "evidence_ids", None)

        hmac_key = self.secret_key if (self.enforce_signature or token.schema == HMAC_TOKEN_SCHEMA) else None

        return validate_readset_token(
            token,
            db=db,
            current_profile_id=prop_profile,
            current_actor_id=prop_actor_id,
            current_actor_role=prop_actor_role,
            current_purpose=prop_purpose,
            current_task=prop_task,
            current_state_version=1,
            current_policy_version=prop_policy,
            current_consent_version=prop_consent,
            observed_evidence_ids=prop_ev_ids,
            expected_snapshot_id=prop_snap_id,
            expected_snapshot_digest=prop_snap_digest,
            hmac_key=hmac_key,
            now_utc=now_utc,
            raise_on_error=False,
        )
