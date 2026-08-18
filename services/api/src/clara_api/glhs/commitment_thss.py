"""Task/purpose-bounded THSS compiler for Clinical Commitments.

Freshness (P9)
--------------
Recency uses the domain-versioned freshness clock
(``clara_api.glhs.freshness``): the freshest available observation/knowledge
clock governs, and an old clinical ``valid_from`` never alone marks a
commitment stale when a fresher clock exists.  ``stale_evidence_ids`` report
clock-based reasons.  Domain max-ages come from ``risk.DOMAIN_POLICIES``.

Abstention vocabulary (P10)
---------------------------
``sufficiency["decision"]`` uses the shared ``AbstentionDecision`` codes from
``clara_api.glhs.commitment_projection``, identical to generic
``gateway.compile_thss`` ``risk["decision"]``.

Snapshot expiry (P11)
---------------------
``expires_at`` is bounded by the authorization scope:
``min(now + expires_in, scope.valid_until)``; an already-expired scope is
rejected with ``commitment_snapshot_scope_expired`` before any state query.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import GlhsClinicalCommitment, GlhsEvidence, GlhsSnapshotManifest
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    consistency_fingerprint,
)
from clara_api.glhs.commitment_evidence import select_minimal_evidence
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
    DOMAINS,
    reconstruct_commitments,
)
from clara_api.glhs.commitment_projection import sufficiency_decision
from clara_api.glhs.commitment_selection import select_relevant_commitments
from clara_api.glhs.commitments import DOMAIN_POLICIES
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.freshness import freshness_for_commitment
from clara_api.glhs.gateway import (
    SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    _as_utc,
    _consent_basis,
    _governed_consent_version,
    _manifest_envelope,
    current_state_version,
    validate_thss_pipeline_trace,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _digest(value: object) -> str:
    return consistency_fingerprint(value)


def _commitment_id(commitment: dict[str, Any]) -> str:
    return str(commitment["commitment_id"])


def _evidence_ids(commitment: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(evidence_id) for evidence_id in commitment.get("evidence_ids") or ())


def _fact_coverage(
    *,
    included: tuple[dict[str, Any], ...],
    selection: dict[str, Any],
    target_semantic_key: str | None,
    target: dict[str, Any] | None,
    disclosed_evidence_ids: frozenset[str],
    minimal_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Fact-level coverage (P7) of the required task facts.

    Each fact reports ``{covered, evidence_ids, commitment_ids, missing}``;
    ``target`` reports ``not_specified`` when the caller declared no target.
    """

    target_commitment = selection["target_commitment"]
    target_declared = target_semantic_key is not None or target is not None
    relevant_ids = tuple(_commitment_id(item) for item in included)
    all_evidence = {
        str(evidence_id) for item in included for evidence_id in _evidence_ids(item)
    }

    anchor_evidence: tuple[str, ...]
    anchor_commitment_ids: tuple[str, ...]
    if target_commitment is not None:
        anchor_evidence = tuple(_evidence_ids(target_commitment))
        anchor_commitment_ids = (_commitment_id(target_commitment),)
    elif target_declared:
        anchor_evidence = tuple(sorted(disclosed_evidence_ids))
        anchor_commitment_ids = ()
    else:
        anchor_evidence = tuple(sorted(all_evidence | disclosed_evidence_ids))
        anchor_commitment_ids = relevant_ids

    anchor: dict[str, object] = {
        "covered": bool(anchor_evidence),
        "evidence_ids": list(anchor_evidence),
        "commitment_ids": list(anchor_commitment_ids),
        "missing": not anchor_evidence,
    }

    if not target_declared:
        target_fact: dict[str, object] = {
            "status": "not_specified",
            "covered": False,
            "evidence_ids": [],
            "commitment_ids": [],
            "missing": True,
            "note": "target_not_specified",
        }
    elif target_commitment is not None:
        target_fact = {
            "covered": True,
            "evidence_ids": list(_evidence_ids(target_commitment)),
            "commitment_ids": list(anchor_commitment_ids),
            "missing": False,
        }
    else:
        target_fact = {
            "covered": False,
            "evidence_ids": [],
            "commitment_ids": [],
            "missing": True,
            "note": "target_not_visible",
        }

    predicate_commitments = [
        item
        for item in included
        if any(
            isinstance(item.get(field), dict)
            for field in (
                "fulfillment_predicate",
                "cancellation_predicate",
                "supersession_predicate",
                "partial_predicate",
                "conditional_trigger",
            )
        )
    ]
    predicate_ids = {
        str(evidence_id) for evidence_id in minimal_evidence["predicate_matched_ids"] or ()
    }
    predicate_inputs: dict[str, object] = {
        "covered": all(
            any(evidence_id in predicate_ids for evidence_id in _evidence_ids(item))
            for item in predicate_commitments
        ),
        "evidence_ids": sorted(predicate_ids),
        "commitment_ids": [_commitment_id(item) for item in predicate_commitments],
        "missing": any(
            not any(evidence_id in predicate_ids for evidence_id in _evidence_ids(item))
            for item in predicate_commitments
        ),
    }

    dependency_ids = set(selection["dependency_ids"])
    dependency_commitments = tuple(
        item for item in included if str(item.get("semantic_key")) in dependency_ids
    )
    missing_dependencies = tuple(selection["missing_dependencies"])
    dependencies: dict[str, object] = {
        "covered": not missing_dependencies,
        "evidence_ids": sorted(
            {
                str(evidence_id)
                for item in dependency_commitments
                for evidence_id in _evidence_ids(item)
            }
        ),
        "commitment_ids": [_commitment_id(item) for item in dependency_commitments],
        "missing": bool(missing_dependencies),
    }

    unclassified = tuple(item for item in included if not item.get("authority_class"))
    authority: dict[str, object] = {
        "covered": not unclassified,
        "evidence_ids": [],
        "commitment_ids": list(relevant_ids),
        "missing": bool(unclassified),
    }

    below_minimum = tuple(
        item
        for item in included
        if len(_evidence_ids(item)) < DOMAIN_POLICIES[str(item["domain"])].minimum_evidence
    )
    minimum_evidence: dict[str, object] = {
        "covered": not below_minimum,
        "evidence_ids": sorted(all_evidence),
        "commitment_ids": list(relevant_ids),
        "missing": bool(below_minimum),
    }

    return {
        "anchor": anchor,
        "target": target_fact,
        "predicate_inputs": predicate_inputs,
        "dependencies": dependencies,
        "authority": authority,
        "minimum_evidence": minimum_evidence,
    }


def _selection_payload(selection: dict[str, Any]) -> dict[str, Any]:
    """Sanitized selection summary: identifiers and flags only (no PHR content)."""

    return {
        "relevant_commitment_ids": [_commitment_id(item) for item in selection["relevant"]],
        "blocking_commitment_ids": [_commitment_id(item) for item in selection["blocking"]],
        "blocked": bool(selection["blocked"]),
        "dependency_ids": list(selection["dependency_ids"]),
        "missing_dependencies": list(selection["missing_dependencies"]),
        "dependency_cycles": [list(cycle) for cycle in selection["dependency_cycles"]],
    }


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
    selection: dict[str, Any]
    minimal_evidence: dict[str, Any]
    fact_coverage: dict[str, object]
    visible_conflicts_irrelevant: tuple[str, ...]
    snapshot_digest: str
    manifest_digest: str
    assertion_hashes: tuple[dict[str, str], ...]
    pipeline_trace: tuple[dict[str, object], ...]
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
    disclosed_evidence: tuple[GlhsEvidence, ...] = (),
    target_semantic_key: str | None = None,
    target: dict[str, Any] | None = None,
    dependencies: tuple[str, ...] = (),
) -> CommitmentSnapshot:
    # Stage 1: Authorization. No state/evidence query occurs before these
    # purpose, domain and expiry checks complete.
    if purpose != scope.purpose:
        raise GlhsInvariantError("commitment_snapshot_purpose_mismatch")
    if not allowed_domains or not allowed_domains.issubset(DOMAINS):
        raise GlhsInvariantError("commitment_snapshot_domain_invalid")
    if not allowed_domains.issubset(scope.allowed_data_classes):
        raise GlhsInvariantError("commitment_snapshot_domain_forbidden")
    if scope.valid_until is not None and scope.valid_until <= datetime.now(UTC):
        raise GlhsInvariantError("commitment_snapshot_scope_expired")
    if any(item.profile_id != scope.profile.id for item in disclosed_evidence):
        raise GlhsInvariantError("commitment_snapshot_evidence_scope_forbidden")

    # Stage 2: Temporal/Lifecycle.
    visible = reconstruct_commitments(
        db, profile_id=scope.profile.id, valid_at=valid_at, known_at=known_at
    )

    # Stage 3: Conflict, before relevance and minimization.
    all_conflicts = {
        str(item["commitment_id"]) for item in visible if item["evidence_state"] == "CONFLICTED"
    }
    all_insufficient = {
        str(item["commitment_id"])
        for item in visible
        if item["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    }

    # Stage 4: Relevance/Freshness. Task-bounded selection (P5): only the
    # declared target, target system/code matches, and the dependency closure
    # are relevant; same-domain commitments outside that set are excluded as
    # task_irrelevant and can never block the task.
    selection = select_relevant_commitments(
        visible,
        task=task,
        purpose=purpose,
        allowed_domains=allowed_domains,
        target_semantic_key=target_semantic_key,
        target=target,
        dependencies=dependencies,
    )
    included = selection["relevant"]
    visible_ids = {str(item["commitment_id"]) for item in visible}
    all_rows = list(
        db.execute(
            select(GlhsClinicalCommitment).where(
                GlhsClinicalCommitment.profile_id == scope.profile.id,
                GlhsClinicalCommitment.domain.in_(allowed_domains),
            )
        ).scalars()
    )
    exclusions = tuple(
        sorted(
            [
                *selection["irrelevant_exclusions"],
                *(
                    {
                        "commitment_id": row.public_id,
                        "reason": "not_visible_at_bitemporal_cutoff",
                    }
                    for row in all_rows
                    if row.public_id not in visible_ids
                ),
            ],
            key=lambda item: (str(item["commitment_id"]), str(item["reason"])),
        )
    )
    # Stage 5: Minimization. Only selected commitment state and evidence that
    # earns a supported disclosure role enter the disclosed payload.
    blocking = selection["blocking"]
    conflicts = tuple(
        sorted(
            str(item["commitment_id"])
            for item in blocking
            if item["evidence_state"] == "CONFLICTED"
        )
    )
    insufficient = tuple(
        sorted(
            str(item["commitment_id"])
            for item in blocking
            if item["evidence_state"] == "INSUFFICIENT_EVIDENCE"
        )
    )
    disclosed_evidence_ids = frozenset(str(item.public_id) for item in disclosed_evidence)
    minimal_evidence = select_minimal_evidence(
        relevant=included,
        target_semantic_key=target_semantic_key,
        target=target,
        anchor_commitment=selection["target_commitment"],
        dependency_ids=frozenset(selection["dependency_ids"]),
        blocking=blocking,
        disclosed_evidence=disclosed_evidence,
    )
    evidence_ids = minimal_evidence["evidence_ids"]
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
        str(item["commitment_id"]) for item in included if item["timeliness_state"] == "OVERDUE"
    )
    # Stage 4b: Freshness. The domain-versioned freshness clock governs: a
    # fresher observation/knowledge clock keeps the commitment fresh even when
    # the clinical valid anchor (anchor_valid_time) is old.
    stale_evidence: list[dict[str, str]] = []
    for item in included:
        result = freshness_for_commitment(item, cutoff=valid_at)
        if result.fresh:
            continue
        for evidence_id in item.get("evidence_ids", ()):
            stale_evidence.append(
                {
                    "evidence_id": str(evidence_id),
                    "commitment_id": str(item["commitment_id"]),
                    "freshness_clock": result.freshness_clock,
                    "clock_value": result.clock_value.isoformat(),
                    "stale_reason": result.stale_reason or "stale_evidence",
                }
            )
    stale_commitment_ids = sorted({entry["commitment_id"] for entry in stale_evidence})
    authority: dict[str, object] = {
        "authority_classes": sorted(
            {str(item["authority_class"]) for item in included if item.get("authority_class")}
        ),
        "unclassified_commitment_ids": [
            str(item["commitment_id"]) for item in included if not item.get("authority_class")
        ],
    }
    recency: dict[str, object] = {
        "overdue_commitment_ids": list(overdue),
        "stale_evidence_ids": stale_evidence,
    }
    fact_coverage = _fact_coverage(
        included=included,
        selection=selection,
        target_semantic_key=target_semantic_key,
        target=target,
        disclosed_evidence_ids=disclosed_evidence_ids,
        minimal_evidence=minimal_evidence,
    )
    critical_fact_coverage = fact_coverage
    reasons = [
        *({"code": "commitment_conflict", "commitment_id": item} for item in conflicts),
        *(
            {"code": "commitment_insufficient_evidence", "commitment_id": item}
            for item in insufficient
        ),
        *(
            {"code": "commitment_stale_evidence", "commitment_id": item}
            for item in stale_commitment_ids
        ),
    ]
    # P6: only *blocking* conflicts/insufficiency force abstention; visible but
    # task-irrelevant conflicts are recorded separately and never abstain.
    # Stale-evidence abstention (P9) is preserved.
    must_abstain = strict and bool(conflicts or insufficient or stale_commitment_ids)
    sufficiency: dict[str, object] = {
        "included_count": len(included),
        "evidence_count": len(evidence_ids),
        "conflicted_commitment_ids": list(conflicts),
        "insufficient_commitment_ids": list(insufficient),
        "stale_commitment_ids": stale_commitment_ids,
        "decision": sufficiency_decision(must_abstain=must_abstain),
        "escalation_reasons": reasons,
        "clinical_adjudication": "NOT_RUN",
        "missing_fields": list(missing_fields),
        "critical_fact_coverage": critical_fact_coverage,
        "fact_coverage": fact_coverage,
        "authority": authority,
        "recency": recency,
    }
    state_version = current_state_version(db, profile_id=scope.profile.id)
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=purpose
    )
    consent_basis = _consent_basis(purpose=purpose, consent_version=consent_version)
    expires_at = datetime.now(UTC) + expires_in
    if scope.valid_until is not None:
        expires_at = min(expires_at, _as_utc(scope.valid_until))
    assertion_ids = sorted(str(item["version_id"]) for item in included)
    assertion_hashes = [
        {"assertion_id": str(item["version_id"]), "sha256": _digest(item)}
        for item in sorted(included, key=lambda value: str(value["version_id"]))
    ]
    pipeline_trace: list[dict[str, object]] = [
        {
            "stage": 1,
            "name": "authorization",
            "authorized_domains": sorted(allowed_domains),
        },
        {
            "stage": 2,
            "name": "temporal_lifecycle",
            "visible_count": len(visible),
            "valid_at": valid_at.isoformat(),
            "known_at": known_at.isoformat(),
        },
        {
            "stage": 3,
            "name": "conflict",
            "conflicted_count": len(all_conflicts),
            "insufficient_count": len(all_insufficient),
        },
        {
            "stage": 4,
            "name": "relevance_freshness",
            "relevant_count": len(included),
            "overdue_count": len(overdue),
            "stale_count": len(stale_commitment_ids),
            "blocked": bool(selection["blocked"]),
        },
        {
            "stage": 5,
            "name": "minimization",
            "disclosed_commitment_count": len(included),
            "disclosed_evidence_count": len(evidence_ids),
            "excluded_caller_evidence_count": len(minimal_evidence["excluded_caller_evidence"]),
        },
    ]
    validate_thss_pipeline_trace(pipeline_trace)
    selection_payload = _selection_payload(selection)
    payload = {
        "manifest_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "payload_schema_version": SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "state_version": state_version,
        "policy_version": COMMITMENT_POLICY_VERSION,
        "consent_version": consent_version,
        "consent_basis": consent_basis,
        "profile_id": scope.profile.public_id,
        "actor_user_id": scope.actor.id,
        "actor_role": scope.actor_role,
        "task": task,
        "purpose": purpose,
        "valid_at": valid_at.isoformat(),
        "known_at": known_at.isoformat(),
        "commitments": list(included),
        "evidence_ids": evidence_ids,
        "assertion_ids": assertion_ids,
        "assertion_hashes": assertion_hashes,
        "exclusions": list(exclusions),
        "conflicts": list(conflicts),
        "sufficiency": sufficiency,
        "critical_fact_coverage": critical_fact_coverage,
        "authority": authority,
        "recency": recency,
        "missing_fields": list(missing_fields),
        "selection": selection_payload,
        "minimal_evidence": minimal_evidence,
        "fact_coverage": fact_coverage,
        "visible_conflicts_irrelevant": list(selection["visible_conflicts_irrelevant"]),
        "pipeline_trace": pipeline_trace,
        "expires_at": expires_at.isoformat(),
    }
    digest = _digest(payload)
    manifest = GlhsSnapshotManifest(
        public_id=str(uuid4()),
        profile_id=scope.profile.id,
        state_version=state_version,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        task=task,
        purpose=purpose,
        data_classes_json=sorted(allowed_domains),
        assertion_ids_json=assertion_ids,
        provenance_ids_json=evidence_ids,
        conflict_ids_json=list(conflicts),
        selection_policy="commitment_strict" if strict else "commitment_default",
        manifest_schema_version=SNAPSHOT_SCHEMA_VERSION,
        payload_schema_version=SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
        digest_algorithm=DIGEST_ALGORITHM,
        canonicalization_profile=CANONICALIZATION_PROFILE,
        valid_time_cutoff=valid_at,
        knowledge_time_cutoff=known_at,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        consent_basis=consent_basis,
        assertion_hashes_json=assertion_hashes,
        snapshot_payload_json=payload,
        snapshot_digest=digest,
        expires_at=expires_at,
    )
    manifest.manifest_digest = _digest(_manifest_envelope(manifest))
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
        selection=selection_payload,
        minimal_evidence=minimal_evidence,
        fact_coverage=fact_coverage,
        visible_conflicts_irrelevant=selection["visible_conflicts_irrelevant"],
        snapshot_digest=digest,
        manifest_digest=manifest.manifest_digest,
        assertion_hashes=tuple(assertion_hashes),
        pipeline_trace=tuple(pipeline_trace),
        expires_at=expires_at,
    )
