"""R4 Governed Read-to-Write Continuity (GRWC) Admission Comparator Policies.

Implements the five-arm comparator architecture evaluating write-admission
preconditions across formal baseline paradigms:
- C0 (CURRENT_STATE_ONLY): Validates ONLY commit-time state version, policy
  epoch, consent version, and actor/role authorization. Ignores inference-time
  context bindings, snapshot identity, projection digests, and evidence containment.
- C1 (OCC_READSET): Classical Optimistic Concurrency Control (Kung-Robinson /
  DynamoDB conditional writes) validating entity read-set versions and write-set
  conflicts against current DB state. Ignores prompt disclosure identity and
  evidence prompt-containment.
- C2 (PROVENANCE_ONLY): Inspects and records retrospective W3C PROV lineage
  metadata, but does NOT enforce exact disclosure or forward context binding
  continuity as an admission precondition.
- C3 (SIGNED_EXACT_DISCLOSURE_TOKEN): Compact capability token validator modeled
  on Macaroons / Proof-Carrying File Systems. Validates HMAC signature over
  <H_proj, purpose, task, actor, R_readset, t_expires>. Includes read-set
  version caveats R_readset so it is NOT a strawman against write-skew.
- C4 (FULL_GRWC): GLHS Governed Read-to-Write Continuity reference verifier
  delegating to Section 15 Steps 1-21 under PostgreSQL locks.

Production Route Safety Guard:
- Production code uses FullGrwcValidator (C4) by default.
- Research comparator policies (C0-C3) are strictly prohibited from execution
  in production routes unless explicitly enabled via execution mode flags or
  GLHS_RESEARCH_COMPARATORS_ENABLED environment configuration.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsClinicalCommitmentProposal,
    GlhsSnapshotManifest,
    PhrProfile,
)
from clara_api.glhs.admission import GrwcAdmissionResult, evaluate_grwc_admission
from clara_api.glhs.canonical_json import (
    canonical_json_bytes,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.reason_codes import (
    ACTOR_MISMATCH,
    BINDING_MISSING,
    CONSENT_REVOKED,
    DEPENDENCY_VERSION_STALE,
    EVIDENCE_UNDISCLOSED,
    MANIFEST_DIGEST_MISMATCH,
    POLICY_STALE,
    PROJECTION_DIGEST_MISMATCH,
    PROVIDER_RECEIPT_INVALID,
    PURPOSE_MISMATCH,
    ROLE_MISMATCH,
    SNAPSHOT_EXPIRED,
    STATE_STALE,
    TASK_MISMATCH,
    canonicalize_reason_code,
)

ENV_GLHS_RESEARCH_COMPARATORS_ENABLED = "GLHS_RESEARCH_COMPARATORS_ENABLED"
DEFAULT_C3_HMAC_SECRET = b"glhs-r4-c3-macaroon-capability-token-secret-20260930"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_research_mode_enabled() -> bool:
    val = os.environ.get(ENV_GLHS_RESEARCH_COMPARATORS_ENABLED, "").strip().lower()
    return val in ("1", "true", "yes", "enabled", "on")


def _extract_context_param(
    param_name: str,
    context: Any,
    kwargs: dict[str, Any],
    default: Any = None,
) -> Any:
    """Extract a context parameter from kwargs, dictionary, or context object."""
    if param_name in kwargs and kwargs[param_name] is not None:
        return kwargs[param_name]
    if isinstance(context, dict):
        val = context.get(param_name)
        if val is not None:
            return val
    if context is not None and hasattr(context, param_name):
        val = getattr(context, param_name, None)
        if val is not None:
            return val
    # ProfileScope-specific resolution
    if context is not None:
        if param_name == "actor_user_id" and hasattr(context, "actor") and hasattr(context.actor, "id"):
            return context.actor.id
        if param_name == "actor_role" and hasattr(context, "actor_role"):
            return context.actor_role
        if param_name == "purpose" and hasattr(context, "purpose"):
            return context.purpose
        if param_name == "profile_id" and hasattr(context, "profile") and hasattr(context.profile, "id"):
            return context.profile.id
    return default


def _resolve_proposal(
    db: Session,
    proposal: GlhsClinicalCommitmentProposal | int | dict[str, Any] | Any,
) -> GlhsClinicalCommitmentProposal | dict[str, Any]:
    """Resolve proposal from DB if an ID is passed."""
    if isinstance(proposal, int):
        proposal_row = db.execute(
            select(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == proposal)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if proposal_row is None:
            raise GlhsInvariantError("commitment_proposal_history_incomplete")
        return proposal_row
    if isinstance(proposal, (GlhsClinicalCommitmentProposal, dict)):
        return proposal
    if proposal is None:
        raise GlhsInvariantError("commitment_proposal_history_incomplete")
    return proposal


def _get_proposal_attr(proposal: Any, attr: str, default: Any = None) -> Any:
    if isinstance(proposal, dict):
        return proposal.get(attr, default)
    return getattr(proposal, attr, default)


@dataclass(frozen=True)
class ComparatorDecision:
    """Standardized decision outcome across all R4 admission comparator policies (C0-C4)."""

    policy_name: str
    admitted: bool
    rejection_reason_code: str | None = None
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    grwc_result: GrwcAdmissionResult | None = None

    @property
    def is_admitted(self) -> bool:
        return self.admitted

    @property
    def rejection_reason(self) -> str | None:
        return self.rejection_reason_code


class AdmissionComparatorPolicy(ABC):
    """Abstract base class defining the unified admission comparator interface."""

    @property
    @abstractmethod
    def policy_name(self) -> str:
        """Canonical arm name (e.g., CURRENT_STATE_ONLY, OCC_READSET, etc.)."""
        ...

    @abstractmethod
    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        """Evaluate admission of a proposal under this policy.

        Args:
            db: Database session for executing queries.
            proposal: Proposal instance, proposal ID, or proposal dict.
            context: Execution context (e.g., ProfileScope, GlhsCommitContext, or dict).
            **kwargs: Policy-specific or contextual override parameters.

        Returns:
            ComparatorDecision indicating whether the proposal was admitted or rejected.
        """
        ...


# =============================================================================
# C0: CURRENT_STATE_ONLY Validator
# =============================================================================


class CurrentStateOnlyValidator(AdmissionComparatorPolicy):
    """C0 Comparator: Evaluates ONLY commit-time state, policy, consent, and actor/role.

    Ignores inference-time context bindings, prompt projection digests (H_proj),
    snapshot identity, transport payload digests, and evidence prompt containment.
    """

    @property
    def policy_name(self) -> str:
        return "CURRENT_STATE_ONLY"

    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        t0 = time.perf_counter_ns()
        try:
            prop = _resolve_proposal(db, proposal)
        except GlhsInvariantError as exc:
            code = canonicalize_reason_code(str(exc))
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=code,
                reason_codes=(code,),
                metadata={"duration_ns": time.perf_counter_ns() - t0, "error": str(exc)},
            )

        target_profile_id = _extract_context_param("profile_id", context, kwargs)
        current_state_version = _extract_context_param("current_state_version", context, kwargs)
        effective_policy_version = _extract_context_param("effective_policy_version", context, kwargs)
        effective_consent_version = _extract_context_param("effective_consent_version", context, kwargs)
        actor_user_id = _extract_context_param("actor_user_id", context, kwargs)
        actor_role = _extract_context_param("actor_role", context, kwargs)

        target_profile_public_id = _get_proposal_attr(prop, "target_profile_public_id")
        base_state_version = _get_proposal_attr(prop, "base_state_version")
        prop_policy_version = _get_proposal_attr(prop, "policy_version")
        prop_consent_version = _get_proposal_attr(prop, "consent_version")
        prop_actor_user_id = _get_proposal_attr(prop, "actor_user_id")
        prop_actor_role = _get_proposal_attr(prop, "actor_role")
        origin = _get_proposal_attr(prop, "origin")

        # 1. Target Profile Matching
        if target_profile_public_id and target_profile_id is not None:
            profile_row = db.execute(
                select(PhrProfile).where(PhrProfile.id == target_profile_id)
            ).scalar_one_or_none()
            if profile_row is not None and target_profile_public_id != profile_row.public_id:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code="commitment_proposal_profile_mismatch",
                    reason_codes=("commitment_proposal_profile_mismatch",),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )

        # 2. Base State Version Revalidation
        if current_state_version is not None and base_state_version is not None:
            if base_state_version < current_state_version:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=STATE_STALE,
                    reason_codes=(STATE_STALE,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )

        # 3. Policy Epoch Revalidation
        if effective_policy_version is not None and prop_policy_version is not None:
            if (
                prop_policy_version != effective_policy_version
                and not (
                    prop_policy_version in ("glhs.v1", "commitloop.v1")
                    and effective_policy_version in ("glhs.v1", "commitloop.v1")
                )
                and not effective_policy_version.startswith("policy_epoch")
            ):
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=POLICY_STALE,
                    reason_codes=(POLICY_STALE,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )

        # 4. Consent Epoch Revalidation
        if effective_consent_version is not None and prop_consent_version is not None:
            if prop_consent_version != effective_consent_version:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=CONSENT_REVOKED,
                    reason_codes=(CONSENT_REVOKED,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )

        # 5. Actor and Role Coordinates
        if actor_user_id is not None:
            if origin == "model" and prop_actor_user_id is not None and prop_actor_user_id != actor_user_id:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=ACTOR_MISMATCH,
                    reason_codes=(ACTOR_MISMATCH,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )
        if actor_role is not None and prop_actor_role and prop_actor_role != actor_role:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=ROLE_MISMATCH,
                reason_codes=(ROLE_MISMATCH,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        return ComparatorDecision(
            policy_name=self.policy_name,
            admitted=True,
            metadata={
                "duration_ns": time.perf_counter_ns() - t0,
                "evaluated_coordinates": {
                    "actor_user_id": actor_user_id or prop_actor_user_id,
                    "actor_role": actor_role or prop_actor_role,
                    "state_version": current_state_version,
                },
            },
        )


# =============================================================================
# C1: OCC_READSET Validator
# =============================================================================


class OccReadSetValidator(AdmissionComparatorPolicy):
    """C1 Comparator: Classical Optimistic Concurrency Control (OCC).

    Validates read-set entity versions and write-set conflicts against database state.
    Ignores prompt disclosure identity (H_proj) and evidence prompt-containment.
    """

    @property
    def policy_name(self) -> str:
        return "OCC_READSET"

    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        t0 = time.perf_counter_ns()
        # 1. Evaluate base state checks (C0 parity)
        c0_validator = CurrentStateOnlyValidator()
        c0_decision = c0_validator.evaluate_admission(db, proposal, context, **kwargs)
        if not c0_decision.admitted:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=c0_decision.rejection_reason_code,
                reason_codes=c0_decision.reason_codes,
                metadata={"duration_ns": time.perf_counter_ns() - t0, "stage": "state_revalidation"},
            )

        # 2. Extract and validate read-set entity versions
        read_set = _extract_context_param("read_set", context, kwargs)
        if read_set is None:
            read_set = _extract_context_param("state_dependencies", context, kwargs)
        if read_set is None:
            read_set = _extract_context_param("dependencies", context, kwargs)

        current_versions_map: dict[str, int] = _extract_context_param(
            "current_entity_versions", context, kwargs, default={}
        )

        locked_map = _extract_context_param("locked_map", context, kwargs)
        if locked_map and isinstance(locked_map, dict):
            for k, part in locked_map.items():
                if hasattr(part, "state_version"):
                    key_str = f"{k[0]}:{k[1]}" if isinstance(k, tuple) else str(k)
                    current_versions_map[key_str] = part.state_version

        if read_set:
            for item in read_set:
                key: str | None = None
                observed_version: int | None = None
                if isinstance(item, dict):
                    key = item.get("key") or item.get("entity_key")
                    observed_version = item.get("observed_version")
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    key = str(item[0])
                    observed_version = int(item[1])
                elif hasattr(item, "key") and hasattr(item, "observed_version"):
                    key = item.key
                    observed_version = item.observed_version
                elif hasattr(item, "dependency_key") and hasattr(item, "observed_version"):
                    key = item.dependency_key
                    observed_version = item.observed_version

                if key is not None and observed_version is not None:
                    curr_ver = current_versions_map.get(key)
                    if curr_ver is not None and curr_ver != observed_version:
                        return ComparatorDecision(
                            policy_name=self.policy_name,
                            admitted=False,
                            rejection_reason_code=STATE_STALE,
                            reason_codes=(STATE_STALE, DEPENDENCY_VERSION_STALE),
                            metadata={
                                "duration_ns": time.perf_counter_ns() - t0,
                                "stale_key": key,
                                "observed_version": observed_version,
                                "current_version": curr_ver,
                            },
                        )

        return ComparatorDecision(
            policy_name=self.policy_name,
            admitted=True,
            metadata={
                "duration_ns": time.perf_counter_ns() - t0,
                "validated_readset_count": len(read_set) if read_set else 0,
            },
        )


# =============================================================================
# C2: PROVENANCE_ONLY Validator
# =============================================================================


class ProvenanceOnlyValidator(AdmissionComparatorPolicy):
    """C2 Comparator: Retrospective W3C PROV Provenance Tracker.

    Records/inspects retrospective provenance metadata, but does NOT enforce
    exact disclosure or forward binding continuity as an admission precondition.
    """

    @property
    def policy_name(self) -> str:
        return "PROVENANCE_ONLY"

    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        t0 = time.perf_counter_ns()
        # 1. Base state verification (C0 parity)
        c0_validator = CurrentStateOnlyValidator()
        c0_decision = c0_validator.evaluate_admission(db, proposal, context, **kwargs)
        if not c0_decision.admitted:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=c0_decision.rejection_reason_code,
                reason_codes=c0_decision.reason_codes,
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        try:
            prop = _resolve_proposal(db, proposal)
        except GlhsInvariantError as exc:
            code = canonicalize_reason_code(str(exc))
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=code,
                reason_codes=(code,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        # 2. Inspect / record retrospective provenance metadata
        observed_raw = _get_proposal_attr(prop, "observed_evidence_ids_json")
        origin = _get_proposal_attr(prop, "origin")
        actor_id = _get_proposal_attr(prop, "actor_user_id")
        policy_ver = _get_proposal_attr(prop, "policy_version")

        # Verify syntactic integrity of provenance records
        if observed_raw is not None and not isinstance(observed_raw, (list, tuple, dict, set)):
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code="provenance_structure_malformed",
                reason_codes=("provenance_structure_malformed",),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        prov_graph = {
            "wasGeneratedBy": origin or "unknown",
            "wasAttributedTo": actor_id,
            "used": observed_raw or [],
            "policyVersion": policy_ver,
            "recordedAt": datetime.now(UTC).isoformat(),
        }

        return ComparatorDecision(
            policy_name=self.policy_name,
            admitted=True,
            metadata={
                "duration_ns": time.perf_counter_ns() - t0,
                "retrospective_provenance": prov_graph,
            },
        )


# =============================================================================
# C3: SIGNED_EXACT_DISCLOSURE_TOKEN Validator
# =============================================================================


def compute_c3_token_signature(
    *,
    projection_digest: str,
    purpose: str,
    task: str,
    actor_user_id: int | str,
    readset_caveats: Sequence[dict[str, Any] | tuple[str, int]] | None = None,
    expires_at: str | datetime,
    secret_key: bytes = DEFAULT_C3_HMAC_SECRET,
) -> str:
    """Compute deterministic HMAC-SHA256 signature over <H_proj, purpose, task, actor, R_readset, t_expires>."""
    exp_str = expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at)
    caveats = []
    if readset_caveats:
        for c in readset_caveats:
            if isinstance(c, dict):
                caveats.append({"key": str(c.get("key", "")), "version": int(c.get("version", 0))})
            elif isinstance(c, (tuple, list)) and len(c) >= 2:
                caveats.append({"key": str(c[0]), "version": int(c[1])})

    canonical_payload = {
        "actor_user_id": str(actor_user_id),
        "expires_at": exp_str,
        "projection_digest": str(projection_digest),
        "purpose": str(purpose),
        "readset_caveats": sorted(caveats, key=lambda x: x["key"]),
        "task": str(task),
    }
    canonical_bytes = canonical_json_bytes(canonical_payload)
    return hmac.new(secret_key, canonical_bytes, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class SignedExactDisclosureToken:
    """Capability token holding exact disclosure digest, read-set caveats, and HMAC signature."""

    projection_digest: str
    purpose: str
    task: str
    actor_user_id: int | str
    expires_at: str
    signature: str
    readset_caveats: tuple[dict[str, Any], ...] = ()
    disclosed_evidence_ids: tuple[str, ...] = ()
    policy_version: str = "commitloop.v1"
    consent_version: str = "not_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_digest": self.projection_digest,
            "purpose": self.purpose,
            "task": self.task,
            "actor_user_id": str(self.actor_user_id),
            "expires_at": self.expires_at,
            "signature": self.signature,
            "readset_caveats": list(self.readset_caveats),
            "disclosed_evidence_ids": list(self.disclosed_evidence_ids),
            "policy_version": self.policy_version,
            "consent_version": self.consent_version,
        }

    @classmethod
    def create(
        cls,
        *,
        projection_digest: str,
        purpose: str,
        task: str,
        actor_user_id: int | str,
        expires_at: str | datetime,
        readset_caveats: Sequence[dict[str, Any] | tuple[str, int]] | None = None,
        disclosed_evidence_ids: Sequence[str] | None = None,
        secret_key: bytes = DEFAULT_C3_HMAC_SECRET,
        policy_version: str = "commitloop.v1",
        consent_version: str = "not_required",
    ) -> SignedExactDisclosureToken:
        exp_str = expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at)
        formatted_caveats: list[dict[str, Any]] = []
        if readset_caveats:
            for c in readset_caveats:
                if isinstance(c, dict):
                    formatted_caveats.append(
                        {"key": str(c.get("key", "")), "version": int(c.get("version", 0))}
                    )
                elif isinstance(c, (tuple, list)) and len(c) >= 2:
                    formatted_caveats.append({"key": str(c[0]), "version": int(c[1])})

        sig = compute_c3_token_signature(
            projection_digest=projection_digest,
            purpose=purpose,
            task=task,
            actor_user_id=actor_user_id,
            readset_caveats=formatted_caveats,
            expires_at=exp_str,
            secret_key=secret_key,
        )
        return cls(
            projection_digest=projection_digest,
            purpose=purpose,
            task=task,
            actor_user_id=actor_user_id,
            expires_at=exp_str,
            signature=sig,
            readset_caveats=tuple(formatted_caveats),
            disclosed_evidence_ids=tuple(disclosed_evidence_ids or ()),
            policy_version=policy_version,
            consent_version=consent_version,
        )


class SignedExactDisclosureTokenValidator(AdmissionComparatorPolicy):
    """C3 Comparator: Compact capability token validator modeled on Macaroons / PCFS.

    Validates HMAC signature over <H_proj, purpose, task, actor, R_readset, t_expires>.
    Includes read-set version caveats R_readset to guard against write-skew.
    """

    def __init__(self, secret_key: bytes = DEFAULT_C3_HMAC_SECRET) -> None:
        self.secret_key = secret_key

    @property
    def policy_name(self) -> str:
        return "SIGNED_EXACT_DISCLOSURE_TOKEN"

    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        t0 = time.perf_counter_ns()
        now = _extract_context_param("now", context, kwargs, default=datetime.now(UTC))
        now_utc = _as_utc(now)

        try:
            prop = _resolve_proposal(db, proposal)
        except GlhsInvariantError as exc:
            code = canonicalize_reason_code(str(exc))
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=code,
                reason_codes=(code,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        token: SignedExactDisclosureToken | dict[str, Any] | None = _extract_context_param(
            "token", context, kwargs
        )
        if token is None:
            token = _extract_context_param("capability_token", context, kwargs)
        if token is None:
            token = _extract_context_param("c3_token", context, kwargs)

        # Reconstruct token from kwargs or proposal if passed directly
        if token is None and "projection_digest" in kwargs and "signature" in kwargs:
            token = SignedExactDisclosureToken.create(
                projection_digest=kwargs["projection_digest"],
                purpose=kwargs.get("purpose", _get_proposal_attr(prop, "purpose", "")),
                task=kwargs.get("task", _get_proposal_attr(prop, "task", "")),
                actor_user_id=kwargs.get(
                    "actor_user_id", _get_proposal_attr(prop, "actor_user_id", 0)
                ),
                expires_at=kwargs.get("expires_at", now_utc.isoformat()),
                readset_caveats=kwargs.get("readset_caveats", ()),
                disclosed_evidence_ids=kwargs.get("disclosed_evidence_ids", ()),
                secret_key=kwargs.get("secret_key", self.secret_key),
            )

        if token is None:
            # If no token provided, check if snapshot manifest exists to evaluate
            snap_id = _get_proposal_attr(prop, "source_snapshot_id")
            if snap_id:
                snap = db.execute(
                    select(GlhsSnapshotManifest).where(GlhsSnapshotManifest.public_id == snap_id)
                ).scalar_one_or_none()
                if snap is not None:
                    # Construct synthetic C3 token from snapshot for comparison
                    token = SignedExactDisclosureToken.create(
                        projection_digest=snap.manifest_digest,
                        purpose=snap.purpose or _get_proposal_attr(prop, "purpose", ""),
                        task=snap.task or _get_proposal_attr(prop, "task", ""),
                        actor_user_id=snap.actor_user_id or _get_proposal_attr(prop, "actor_user_id", 0),
                        expires_at=snap.expires_at or now_utc,
                        disclosed_evidence_ids=snap.provenance_ids_json or (),
                        secret_key=self.secret_key,
                    )

        if token is None:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=BINDING_MISSING,
                reason_codes=(BINDING_MISSING,),
                metadata={"duration_ns": time.perf_counter_ns() - t0, "error": "c3_token_missing"},
            )

        # Unpack token fields
        tok_dict = token.to_dict() if isinstance(token, SignedExactDisclosureToken) else token
        t_proj = tok_dict.get("projection_digest", "")
        t_purpose = tok_dict.get("purpose", "")
        t_task = tok_dict.get("task", "")
        t_actor = str(tok_dict.get("actor_user_id", ""))
        t_expires = tok_dict.get("expires_at", "")
        t_sig = tok_dict.get("signature", "")
        t_caveats = tok_dict.get("readset_caveats", ())
        t_disclosed = tok_dict.get("disclosed_evidence_ids", ())

        # 1. Temporal validity / Expiration check
        try:
            exp_dt = datetime.fromisoformat(str(t_expires))
            if _as_utc(exp_dt) <= now_utc:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=SNAPSHOT_EXPIRED,
                    reason_codes=(SNAPSHOT_EXPIRED,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0, "error": "token_expired"},
                )
        except Exception:
            pass

        # 2. HMAC Signature Verification
        secret = kwargs.get("secret_key", self.secret_key)
        expected_sig = compute_c3_token_signature(
            projection_digest=t_proj,
            purpose=t_purpose,
            task=t_task,
            actor_user_id=t_actor,
            readset_caveats=t_caveats,
            expires_at=t_expires,
            secret_key=secret,
        )
        if not hmac.compare_digest(str(t_sig), expected_sig):
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=PROVIDER_RECEIPT_INVALID,
                reason_codes=(PROVIDER_RECEIPT_INVALID, "proposal_hmac_signature_invalid"),
                metadata={"duration_ns": time.perf_counter_ns() - t0, "error": "hmac_signature_invalid"},
            )

        # 3. Context Coordinate Validation (actor, purpose, task)
        current_actor = _extract_context_param("actor_user_id", context, kwargs)
        current_purpose = _extract_context_param("purpose", context, kwargs)
        current_task = _extract_context_param("task", context, kwargs)

        if current_actor is not None and str(current_actor) != t_actor:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=ACTOR_MISMATCH,
                reason_codes=(ACTOR_MISMATCH,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        if current_purpose is not None and current_purpose != t_purpose:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=PURPOSE_MISMATCH,
                reason_codes=(PURPOSE_MISMATCH,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        if current_task is not None and current_task != t_task:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=TASK_MISMATCH,
                reason_codes=(TASK_MISMATCH,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        # 4. Exact Projection Digest Matching (H_proj)
        prop_digest = _get_proposal_attr(prop, "source_snapshot_digest")
        if prop_digest and prop_digest != t_proj:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=PROJECTION_DIGEST_MISMATCH,
                reason_codes=(PROJECTION_DIGEST_MISMATCH, MANIFEST_DIGEST_MISMATCH),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        # 5. Read-Set Version Caveats Revalidation (OCC Non-Strawman Protection)
        current_versions_map: dict[str, int] = _extract_context_param(
            "current_entity_versions", context, kwargs, default={}
        )
        if t_caveats:
            for cav in t_caveats:
                c_key = cav.get("key") if isinstance(cav, dict) else cav[0]
                c_ver = cav.get("version") if isinstance(cav, dict) else cav[1]
                curr_v = current_versions_map.get(str(c_key))
                if curr_v is not None and curr_v != int(c_ver):
                    return ComparatorDecision(
                        policy_name=self.policy_name,
                        admitted=False,
                        rejection_reason_code=STATE_STALE,
                        reason_codes=(STATE_STALE, DEPENDENCY_VERSION_STALE),
                        metadata={"duration_ns": time.perf_counter_ns() - t0, "stale_caveat": c_key},
                    )

        # 6. Evidence Containment (Undisclosed Evidence Rejection)
        observed_ids_raw = _get_proposal_attr(prop, "observed_evidence_ids_json") or ()
        if isinstance(observed_ids_raw, dict):
            asserted_ids = {str(k) for k in observed_ids_raw.keys()}
        else:
            asserted_ids = {str(k) for k in observed_ids_raw}

        disclosed_set = {str(k) for k in t_disclosed}
        if t_caveats:
            for c in t_caveats:
                c_k = c.get("key") if isinstance(c, dict) else c[0]
                disclosed_set.add(str(c_k))

        if asserted_ids and disclosed_set:
            undisclosed = asserted_ids - disclosed_set
            if undisclosed:
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=EVIDENCE_UNDISCLOSED,
                    reason_codes=(EVIDENCE_UNDISCLOSED,),
                    metadata={
                        "duration_ns": time.perf_counter_ns() - t0,
                        "undisclosed_evidence_ids": sorted(undisclosed),
                    },
                )

        # 7. Same-Transaction Governance Revalidation
        eff_policy = _extract_context_param("effective_policy_version", context, kwargs)
        prop_policy = _get_proposal_attr(prop, "policy_version")
        if eff_policy and prop_policy and prop_policy != eff_policy:
            if not (
                prop_policy in ("glhs.v1", "commitloop.v1")
                and eff_policy in ("glhs.v1", "commitloop.v1")
            ) and not eff_policy.startswith("policy_epoch"):
                return ComparatorDecision(
                    policy_name=self.policy_name,
                    admitted=False,
                    rejection_reason_code=POLICY_STALE,
                    reason_codes=(POLICY_STALE,),
                    metadata={"duration_ns": time.perf_counter_ns() - t0},
                )

        eff_consent = _extract_context_param("effective_consent_version", context, kwargs)
        prop_consent = _get_proposal_attr(prop, "consent_version")
        if eff_consent and prop_consent and prop_consent != eff_consent:
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=CONSENT_REVOKED,
                reason_codes=(CONSENT_REVOKED,),
                metadata={"duration_ns": time.perf_counter_ns() - t0},
            )

        return ComparatorDecision(
            policy_name=self.policy_name,
            admitted=True,
            metadata={
                "duration_ns": time.perf_counter_ns() - t0,
                "token_projection_digest": t_proj,
                "readset_caveats_count": len(t_caveats),
            },
        )


# =============================================================================
# C4: FULL_GRWC Validator (Production Reference)
# =============================================================================


class FullGrwcValidator(AdmissionComparatorPolicy):
    """C4 Comparator: Production Reference Governed Read-to-Write Continuity.

    Delegates to formal Section 15 Steps 1-21 verifier under PostgreSQL locks.
    """

    @property
    def policy_name(self) -> str:
        return "FULL_GRWC"

    def evaluate_admission(
        self,
        db: Session,
        proposal: GlhsClinicalCommitmentProposal | int | Any,
        context: Any = None,
        **kwargs: Any,
    ) -> ComparatorDecision:
        t0 = time.perf_counter_ns()
        profile_id = _extract_context_param("profile_id", context, kwargs)
        scope = context if hasattr(context, "profile") and hasattr(context, "actor") else kwargs.get("scope")
        purpose = _extract_context_param("purpose", context, kwargs)
        task = _extract_context_param("task", context, kwargs)
        actor_user_id = _extract_context_param("actor_user_id", context, kwargs)
        actor_role = _extract_context_param("actor_role", context, kwargs)
        current_state_version = _extract_context_param("current_state_version", context, kwargs)
        effective_policy_version = _extract_context_param("effective_policy_version", context, kwargs)
        effective_consent_version = _extract_context_param("effective_consent_version", context, kwargs)
        now = _extract_context_param("now", context, kwargs)

        proposal_id_val = proposal.id if hasattr(proposal, "id") else proposal

        try:
            grwc_result = evaluate_grwc_admission(
                db,
                proposal=proposal if isinstance(proposal, GlhsClinicalCommitmentProposal) else None,
                proposal_id=proposal_id_val,
                profile_id=profile_id,
                scope=scope,
                purpose=purpose,
                task=task,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                current_state_version=current_state_version,
                effective_policy_version=effective_policy_version,
                effective_consent_version=effective_consent_version,
                observed_model_visible_projection=kwargs.get("observed_model_visible_projection"),
                observed_request_envelope=kwargs.get("observed_request_envelope"),
                observed_transport_payload=kwargs.get("observed_transport_payload"),
                expected_transport_payload_digest=kwargs.get("expected_transport_payload_digest"),
                expected_semantic_envelope_digest=kwargs.get("expected_semantic_envelope_digest"),
                now=now,
            )
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=True,
                grwc_result=grwc_result,
                metadata={
                    "duration_ns": time.perf_counter_ns() - t0,
                    "lineage_depth": grwc_result.lineage_depth,
                    "attestation_level": grwc_result.attestation_level,
                },
            )
        except GlhsInvariantError as exc:
            reason = canonicalize_reason_code(str(exc))
            return ComparatorDecision(
                policy_name=self.policy_name,
                admitted=False,
                rejection_reason_code=reason,
                reason_codes=(reason,),
                metadata={
                    "duration_ns": time.perf_counter_ns() - t0,
                    "error": str(exc),
                },
            )


# =============================================================================
# Production Guard & Comparator Registry
# =============================================================================

RESEARCH_COMPARATOR_REGISTRY: dict[str, type[AdmissionComparatorPolicy]] = {
    "C0": CurrentStateOnlyValidator,
    "CURRENT_STATE_ONLY": CurrentStateOnlyValidator,
    "C1": OccReadSetValidator,
    "OCC_READSET": OccReadSetValidator,
    "C2": ProvenanceOnlyValidator,
    "PROVENANCE_ONLY": ProvenanceOnlyValidator,
    "C3": SignedExactDisclosureTokenValidator,
    "SIGNED_EXACT_DISCLOSURE_TOKEN": SignedExactDisclosureTokenValidator,
}

PRODUCTION_COMPARATOR: type[AdmissionComparatorPolicy] = FullGrwcValidator


def get_admission_comparator(
    policy_name: str = "FULL_GRWC",
    *,
    allow_research_comparators: bool = False,
    secret_key: bytes = DEFAULT_C3_HMAC_SECRET,
) -> AdmissionComparatorPolicy:
    """Retrieve an admission comparator policy instance.

    Production Guard Invariant:
    By default, only FullGrwcValidator (C4) is permitted. Research validators (C0-C3)
    are disallowed in production routes unless allow_research_comparators is explicitly True
    or GLHS_RESEARCH_COMPARATORS_ENABLED is active in environment.

    Raises:
        GlhsInvariantError: If a research comparator is requested in production mode.
    """
    normalized_name = policy_name.strip().upper()

    if normalized_name in ("C4", "FULL_GRWC", "PRODUCTION"):
        return FullGrwcValidator()

    if normalized_name in RESEARCH_COMPARATOR_REGISTRY:
        if not allow_research_comparators and not _is_research_mode_enabled():
            raise GlhsInvariantError(
                f"research_comparator_forbidden_in_production: Research comparator policy '{policy_name}' "
                "cannot be executed in production routes without explicit research enablement."
            )
        cls = RESEARCH_COMPARATOR_REGISTRY[normalized_name]
        if cls is SignedExactDisclosureTokenValidator:
            return SignedExactDisclosureTokenValidator(secret_key=secret_key)
        return cls()

    raise GlhsInvariantError(f"unknown_comparator_policy: {policy_name}")


__all__ = [
    "AdmissionComparatorPolicy",
    "ComparatorDecision",
    "CurrentStateOnlyValidator",
    "DEFAULT_C3_HMAC_SECRET",
    "ENV_GLHS_RESEARCH_COMPARATORS_ENABLED",
    "FullGrwcValidator",
    "OccReadSetValidator",
    "ProvenanceOnlyValidator",
    "SignedExactDisclosureToken",
    "SignedExactDisclosureTokenValidator",
    "compute_c3_token_signature",
    "get_admission_comparator",
]
