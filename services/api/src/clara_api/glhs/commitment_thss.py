"""Task/purpose-bounded THSS compiler for Clinical Commitments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import GlhsClinicalCommitment, GlhsSnapshotManifest
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
    DOMAINS,
    reconstruct_commitments,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import _governed_consent_version, current_state_version
from clara_api.lifemap.profile_scope import ProfileScope


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class CommitmentSnapshot:
    snapshot_id: str
    state_version: int
    policy_version: str
    consent_version: str
    task: str
    purpose: str
    valid_at: datetime
    known_at: datetime
    commitments: tuple[dict[str, Any], ...]
    exclusions: tuple[dict[str, str], ...]
    conflicts: tuple[str, ...]
    sufficiency: dict[str, object]
    critical_fact_coverage: dict[str, object]
    authority: dict[str, object]
    recency: dict[str, object]
    missing_fields: tuple[dict[str, str], ...]
    snapshot_digest: str
    expires_at: datetime


def compile_commitment_thss(
    db: Session,
    *,
    scope: ProfileScope,
    task: str,
    purpose: str,
    valid_at: datetime,
    known_at: datetime,
    allowed_domains: frozenset[str],
    strict: bool = True,
    expires_in: timedelta = timedelta(minutes=5),
) -> CommitmentSnapshot:
    if purpose != scope.purpose:
        raise GlhsInvariantError("commitment_snapshot_purpose_mismatch")
    if not allowed_domains or not allowed_domains.issubset(DOMAINS):
        raise GlhsInvariantError("commitment_snapshot_domain_invalid")
    if not allowed_domains.issubset(scope.allowed_data_classes):
        raise GlhsInvariantError("commitment_snapshot_domain_forbidden")
    if scope.valid_until is not None and scope.valid_until <= datetime.now(UTC):
        raise GlhsInvariantError("commitment_snapshot_scope_expired")
    visible = reconstruct_commitments(
        db, profile_id=scope.profile.id, valid_at=valid_at, known_at=known_at
    )
    included = tuple(item for item in visible if item["domain"] in allowed_domains)
    included_ids = {str(item["commitment_id"]) for item in included}
    all_rows = list(
        db.execute(
            select(GlhsClinicalCommitment).where(
                GlhsClinicalCommitment.profile_id == scope.profile.id
            )
        ).scalars()
    )
    exclusions = tuple(
        {
            "commitment_id": row.public_id,
            "reason": (
                "domain_not_authorized"
                if row.domain not in allowed_domains
                else "not_visible_at_bitemporal_cutoff"
            ),
        }
        for row in all_rows
        if row.public_id not in included_ids
    )
    conflicts = tuple(
        str(item["commitment_id"])
        for item in included
        if item["evidence_state"] == "CONFLICTED"
    )
    insufficient = tuple(
        str(item["commitment_id"])
        for item in included
        if item["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    )
    evidence_ids = sorted(
        {str(evidence_id) for item in included for evidence_id in item["evidence_ids"]}
    )
    missing_fields = tuple(
        {
            "commitment_id": str(item["commitment_id"]),
            "field": field,
        }
        for item in included
        for field in ("system", "code")
        if not isinstance(item.get("target"), dict)
        or not isinstance(item["target"].get(field), str)
        or not item["target"][field]
    )
    overdue = tuple(
        str(item["commitment_id"])
        for item in included
        if item["timeliness_state"] == "OVERDUE"
    )
    authority: dict[str, object] = {
        "authority_classes": sorted(
            {str(item["authority_class"]) for item in included if item.get("authority_class")}
        ),
        "unclassified_commitment_ids": [
            str(item["commitment_id"])
            for item in included
            if not item.get("authority_class")
        ],
    }
    recency: dict[str, object] = {"overdue_commitment_ids": list(overdue)}
    critical_fact_coverage: dict[str, object] = {
        "authorized_domains": sorted(allowed_domains),
        "covered_domains": sorted({str(item["domain"]) for item in included}),
        "missing_authorized_domains": sorted(
            allowed_domains - {str(item["domain"]) for item in included}
        ),
    }
    reasons = [
        *({"code": "commitment_conflict", "commitment_id": item} for item in conflicts),
        *(
            {"code": "commitment_insufficient_evidence", "commitment_id": item}
            for item in insufficient
        ),
    ]
    must_abstain = strict and bool(conflicts or insufficient)
    sufficiency: dict[str, object] = {
        "included_count": len(included),
        "evidence_count": len(evidence_ids),
        "conflicted_commitment_ids": list(conflicts),
        "insufficient_commitment_ids": list(insufficient),
        "decision": "ABSTAIN_ESCALATE" if must_abstain else "USABLE",
        "escalation_reasons": reasons,
        "clinical_adjudication": "NOT_RUN",
        "missing_fields": list(missing_fields),
        "critical_fact_coverage": critical_fact_coverage,
        "authority": authority,
        "recency": recency,
    }
    state_version = current_state_version(db, profile_id=scope.profile.id)
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=purpose
    )
    expires_at = datetime.now(UTC) + expires_in
    payload = {
        "state_version": state_version,
        "policy_version": COMMITMENT_POLICY_VERSION,
        "consent_version": consent_version,
        "profile_id": scope.profile.public_id,
        "actor_role": scope.actor_role,
        "task": task,
        "purpose": purpose,
        "valid_at": valid_at.isoformat(),
        "known_at": known_at.isoformat(),
        "commitments": list(included),
        "evidence_ids": evidence_ids,
        "assertion_ids": [],
        "exclusions": list(exclusions),
        "conflicts": list(conflicts),
        "sufficiency": sufficiency,
        "critical_fact_coverage": critical_fact_coverage,
        "authority": authority,
        "recency": recency,
        "missing_fields": list(missing_fields),
        "expires_at": expires_at.isoformat(),
    }
    digest = _digest(payload)
    manifest = GlhsSnapshotManifest(
        profile_id=scope.profile.id,
        state_version=state_version,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        task=f"commitment:{task}",
        purpose=purpose,
        data_classes_json=sorted(allowed_domains),
        assertion_ids_json=[],
        provenance_ids_json=evidence_ids,
        conflict_ids_json=list(conflicts),
        selection_policy="commitment_strict" if strict else "commitment_default",
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        snapshot_payload_json=payload,
        snapshot_digest=digest,
        expires_at=expires_at,
    )
    db.add(manifest)
    db.flush()
    return CommitmentSnapshot(
        snapshot_id=manifest.public_id,
        state_version=state_version,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        task=task,
        purpose=purpose,
        valid_at=valid_at,
        known_at=known_at,
        commitments=included,
        exclusions=exclusions,
        conflicts=conflicts,
        sufficiency=sufficiency,
        critical_fact_coverage=critical_fact_coverage,
        authority=authority,
        recency=recency,
        missing_fields=missing_fields,
        snapshot_digest=digest,
        expires_at=expires_at,
    )
