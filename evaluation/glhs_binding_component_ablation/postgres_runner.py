"""Execution runner for the GLHS 2^3 factorial component-wise exact-binding ablation (E01).

Runs the frozen protocol (protocol.json + schedules.json: 352 schedules x 8 arms = 2,816 executions)
through the real production commitment admission path over an isolated PostgreSQL database
in a fresh random schema, or SQLite smoke backend.

The admission path mirrors production commitment admission step-for-step with context validation
delegated to evaluation-only `adapter.validate_proposal_context`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    required_medical_disclaimer_version,
)
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsClinicalCommitmentTransition,
    GlhsClinicalCommitmentVersion,
    GlhsEvidence,
    GlhsSnapshotManifest,
    GlhsStateVersion,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.canonical_json import consistency_fingerprint, fast_canonical_digest
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
    CommitmentVersionInput,
    _canonical_digest,
    _hash,
    _proposal_envelope,
    _require_live_scope,
    _validate_proposal_digest,
    _validate_proposal_scope_coordinates,
    _validated_version,
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.commitments import (
    derive_lifecycle_predicates,
    policy_for,
    validate_domain_version,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    _as_utc,
    _governed_consent_version,
    _lock_profile_state,
    _manifest_envelope,
    create_inference_context_binding,
    current_state_version,
    record_evidence,
)
from clara_api.glhs.predicate_dsl import validate_predicate
from clara_api.lifemap.commands import add_outbox
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import create_engine, exc, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from evaluation.glhs_binding_component_ablation.adapter import (
    binding_check_applied,
    validate_proposal_context,
)
from evaluation.glhs_binding_component_ablation.binding_mask import ALL_ARMS, B000, B111
from evaluation.glhs_binding_component_ablation.observer import ExecutionRecord, Observer
from evaluation.glhs_binding_component_ablation.validate import (
    validate_protocol,
    validate_schedule_hash,
    validate_schedules,
)

ISOLATION_ATTESTATION_ENV = "GLHS_BINDING_ABLATION_ISOLATED_RESEARCH"
DATABASE_URL_ENV = "GLHS_BINDING_ABLATION_DATABASE_URL"
BACKENDS = frozenset({"postgres", "sqlite"})

VALID_AT = datetime(2026, 8, 1, tzinfo=UTC)
VALID_AT2 = datetime(2026, 8, 19, tzinfo=UTC)

TARGET_SYSTEMS = {
    "observations": "http://loinc.org",
    "medications": "http://www.whocc.no/atc",
    "allergies": "http://snomed.info/sct",
    "conditions": "http://snomed.info/sct",
    "care_plans": "http://snomed.info/sct",
}
TARGET_CODES = {
    "observations": "2339-0",
    "medications": "A10BA02",
    "allergies": "419199007",
    "conditions": "73211009",
    "care_plans": "734163000",
}


def _source_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _full_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _require_isolated_postgres(database_url: str | None) -> str:
    if os.environ.get(ISOLATION_ATTESTATION_ENV) != "1":
        raise RuntimeError("glhs_binding_ablation_requires_isolated_research_attestation")
    url = database_url or os.environ.get(DATABASE_URL_ENV, "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("glhs_binding_ablation_requires_postgresql_database_url")
    if make_url(url).database in {None, "postgres", "template0", "template1"}:
        raise RuntimeError("glhs_binding_ablation_requires_non_default_database")
    return url


def _random_schema_name() -> str:
    return f"glhs_e01_ablation_{uuid4().hex}"


def _version_data(context: dict[str, Any]) -> CommitmentVersionInput:
    domain = str(context["domain"])
    target = {"system": TARGET_SYSTEMS[domain], "code": TARGET_CODES[domain]}
    return CommitmentVersionInput(
        action=str(context["action"]),
        target=target,
        anchor_valid_time=VALID_AT2,
        anchor_known_time=VALID_AT2,
        earliest_valid_time=VALID_AT2,
        due_time=VALID_AT2 + timedelta(days=30),
        grace_end=VALID_AT2 + timedelta(days=37),
        authority_class="patient_report",
        fulfillment_predicate={
            "op": "event",
            "equals": {
                "resource_type": "Observation",
                "system": target["system"],
                "code": target["code"],
                "status": "final",
            },
        },
    )


def _seed_evidence(
    db: Session, *, profile_id: int, schedule_id: str, label: str, at: datetime
) -> GlhsEvidence:
    source = HealthSourceReference(
        profile_id=profile_id,
        source_kind="glhs-binding-component-ablation",
        source_identity=f"{schedule_id}:{label}",
        checksum=f"sha256:{schedule_id}:{label}",
        observed_at=at,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=profile_id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="source_event",
            artifact_type="fhir_resource",
            artifact_public_id=f"{label}",
            fingerprint=f"e01:{schedule_id}:{label}",
            valid_from=at,
        ),
    )


class RunnerEnv:
    """Duck-typed handles: injectable sessions for tests, real DB in production."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory


class SeedContext:
    """Everything seeded for one execution."""

    def __init__(self) -> None:
        self.scope: ProfileScope | None = None
        self.commitment: GlhsClinicalCommitment | None = None
        self.evidence_rows: list[GlhsEvidence] = []
        self.snapshot_a: Any = None
        self.snapshot_a2: Any = None
        self.snapshot_b: Any = None
        self.foreign_evidence: GlhsEvidence | None = None
        self.foreign_snapshot: Any = None
        self.extra_rows: dict[str, GlhsEvidence] = {}


def _seed(db: Session, schedule: dict[str, Any]) -> SeedContext:
    schedule_id = str(schedule["schedule_id"])
    context = dict(schedule["context"])
    domain = str(context["domain"])
    seed = SeedContext()
    user = User(
        email=f"e01-{schedule_id}-{uuid4().hex}@example.test",
        hashed_password="x",
        role="normal",
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    db.add(
        UserConsent(
            user_id=user.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
        )
    )
    db.flush()
    actor_role = str(context.get("actor_role", "owner"))
    origin = {"owner": "user", "clinician": "clinician", "caregiver": "caregiver"}.get(actor_role, "user")
    if origin == "user" and actor_role not in {"owner", "clinician", "caregiver"}:
        actor_role = "owner"

    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role=actor_role,
        purpose=str(context.get("purpose", "self_care")),
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations", "care_plans"}),
    )
    seed.scope = scope
    evidence_count = int(context.get("evidence_count", 1))
    for index in range(1, evidence_count + 1):
        seed.evidence_rows.append(
            _seed_evidence(
                db, profile_id=profile.id, schedule_id=schedule_id, label=f"EVD-{index:03d}", at=VALID_AT
            )
        )
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"e01:{domain}:{schedule_id}:1",
        domain=domain,
        supersession_key=f"e01:{domain}:{schedule_id}",
    )
    seed.commitment = commitment
    snapshot_a = compile_commitment_thss(
        db,
        scope=scope,
        task=str(context["task"]),
        purpose=scope.purpose,
        valid_at=VALID_AT,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({domain}),
        disclosed_evidence=tuple(seed.evidence_rows),
    )
    seed.snapshot_a = snapshot_a
    proposal1 = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=tuple(seed.evidence_rows),
        proposed_transition="OPEN",
        origin=origin,
        observed_base_state_version=snapshot_a.state_version,
        task=snapshot_a.task,
        source_snapshot_id=snapshot_a.snapshot_id,
        source_snapshot_digest=snapshot_a.manifest_digest,
    )
    # Apply initial commitment opening transition
    _attempt_admission(
        db,
        arm=B111,
        scope=scope,
        commitment=commitment,
        proposal=proposal1,
        evidence=tuple(seed.evidence_rows),
        data=_version_data(context),
        expected_state_version=snapshot_a.state_version,
        idempotency_key=f"e01-seed-{schedule_id}-{uuid4().hex}",
        transition_kind="commitment_opened",
        reason_code="binding_ablation_seed",
    )
    snapshot_a2 = compile_commitment_thss(
        db,
        scope=scope,
        task=str(context["task"]),
        purpose=scope.purpose,
        valid_at=VALID_AT2,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({domain}),
        disclosed_evidence=tuple(seed.evidence_rows),
    )
    seed.snapshot_a2 = snapshot_a2
    return seed


def _seed_expired_snapshot(db: Session, seed: SeedContext, offset: int = 300) -> GlhsSnapshotManifest:
    a2 = seed.snapshot_a2
    scope = seed.scope
    assert a2 is not None and scope is not None
    persisted_a2 = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.public_id == a2.snapshot_id,
            GlhsSnapshotManifest.profile_id == scope.profile.id,
        )
    ).scalar_one()
    row = GlhsSnapshotManifest(
        public_id=f"SNAP-EXPIRED-{uuid4().hex[:8]}",
        profile_id=persisted_a2.profile_id,
        state_version=persisted_a2.state_version,
        actor_user_id=persisted_a2.actor_user_id,
        actor_role=persisted_a2.actor_role,
        task=persisted_a2.task,
        purpose=persisted_a2.purpose,
        data_classes_json=persisted_a2.data_classes_json,
        assertion_ids_json=persisted_a2.assertion_ids_json,
        provenance_ids_json=persisted_a2.provenance_ids_json,
        conflict_ids_json=persisted_a2.conflict_ids_json,
        selection_policy=persisted_a2.selection_policy,
        manifest_schema_version=persisted_a2.manifest_schema_version,
        payload_schema_version=persisted_a2.payload_schema_version,
        digest_algorithm=persisted_a2.digest_algorithm,
        canonicalization_profile=persisted_a2.canonicalization_profile,
        valid_time_cutoff=persisted_a2.valid_time_cutoff,
        knowledge_time_cutoff=persisted_a2.knowledge_time_cutoff,
        policy_version=persisted_a2.policy_version,
        consent_version=persisted_a2.consent_version,
        consent_basis=persisted_a2.consent_basis,
        assertion_hashes_json=persisted_a2.assertion_hashes_json,
        snapshot_payload_json=persisted_a2.snapshot_payload_json,
        snapshot_digest=persisted_a2.snapshot_digest,
        expires_at=datetime.now(UTC) - timedelta(seconds=offset),
    )
    row.manifest_digest = consistency_fingerprint(_manifest_envelope(row))
    db.add(row)
    db.flush()
    return row


def _insert_candidate_proposal(
    db: Session,
    seed: SeedContext,
    schedule: dict[str, Any],
    *,
    source_id: str,
    source_digest: str,
    observed: list[str],
    purpose: str | None = None,
    origin: str = "user",
) -> GlhsClinicalCommitmentProposal:
    context = dict(schedule["context"])
    scope = seed.scope
    commitment = seed.commitment
    a2 = seed.snapshot_a2
    assert scope is not None and commitment is not None and a2 is not None
    base = current_state_version(db, profile_id=scope.profile.id)
    effective_purpose = purpose or scope.purpose
    proposal = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=scope.profile.public_id,
        base_state_version=base,
        observed_evidence_ids_json=sorted(set(observed)),
        proposed_transition="OPEN",
        purpose=effective_purpose,
        task=str(context["task"]),
        origin=origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        context_binding_mode="snapshot_bound",
        source_snapshot_id=source_id,
        source_snapshot_digest=source_digest,
        policy_version=a2.policy_version,
        consent_version=a2.consent_version,
    )
    proposal.proposal_digest = consistency_fingerprint(_proposal_envelope(proposal))
    db.add(proposal)
    db.flush()
    return proposal


def _find_transition_by_key(
    db: Session, *, profile_id: int, key_hash: str
) -> GlhsClinicalCommitmentTransition | None:
    return db.execute(
        select(GlhsClinicalCommitmentTransition).where(
            GlhsClinicalCommitmentTransition.profile_id == profile_id,
            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()


def _attempt_admission(
    db: Session,
    *,
    arm: str,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    proposal: GlhsClinicalCommitmentProposal,
    evidence: tuple[GlhsEvidence, ...],
    data: CommitmentVersionInput,
    expected_state_version: int,
    idempotency_key: str,
    transition_kind: str,
    reason_code: str,
) -> tuple[str, str | None]:
    """Mirror production admission path with evaluation-only adapter validation."""
    try:
        _require_live_scope(scope)
        if commitment.profile_id != scope.profile.id or proposal.commitment_id != commitment.id:
            raise GlhsInvariantError("commitment_scope_forbidden")
        _validate_proposal_digest(proposal)
        if proposal.origin == "model":
            raise GlhsInvariantError("model_cannot_commit_commitment")
        _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)
        if proposal.proposed_transition != data.lifecycle_state:
            raise GlhsInvariantError("commitment_proposal_transition_mismatch")
        required_action = "create" if data.lifecycle_state == "OPEN" else "correct"
        if required_action not in scope.allowed_actions:
            raise GlhsInvariantError("commitment_action_forbidden")
        if not evidence or any(item.profile_id != scope.profile.id for item in evidence):
            raise GlhsInvariantError("commitment_provenance_required")
        evidence_ids = sorted({item.public_id for item in evidence})
        if not set(evidence_ids).issubset(set(proposal.observed_evidence_ids_json or ())):
            raise GlhsInvariantError("commitment_proposal_evidence_mismatch")
        predicates = _validated_version(data)
        key_hash = _hash(idempotency_key)
        request_digest = _canonical_digest(
            {
                "commitment_id": commitment.public_id,
                "proposal_id": proposal.public_id,
                "proposal_digest": proposal.proposal_digest,
                "source_snapshot_id": proposal.source_snapshot_id,
                "source_snapshot_digest": proposal.source_snapshot_digest,
                "evidence_ids": evidence_ids,
                "data": asdict(data),
                "expected_state_version": expected_state_version,
                "transition_kind": transition_kind,
                "reason_code": reason_code,
            }
        )
        existing = _find_transition_by_key(db, profile_id=scope.profile.id, key_hash=key_hash)
        if existing is not None:
            if existing.request_digest != request_digest:
                raise GlhsInvariantError("commitment_idempotency_reuse_mismatch")
            db.rollback()
            return "admitted", None
        base = _lock_profile_state(db, profile_id=scope.profile.id)
        existing = _find_transition_by_key(db, profile_id=scope.profile.id, key_hash=key_hash)
        if existing is not None:
            if existing.request_digest != request_digest:
                raise GlhsInvariantError("commitment_idempotency_reuse_mismatch")
            db.rollback()
            return "admitted", None
        if base != expected_state_version or proposal.base_state_version != base:
            raise GlhsInvariantError("stale_commitment_proposal")
        consent_version = _governed_consent_version(
            db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
        )
        validate_proposal_context(
            db,
            arm=arm,
            scope=scope,
            proposal=proposal,
            evidence_ids=evidence_ids,
            current_version=base,
            consent_version=consent_version,
        )
        prior = db.execute(
            select(GlhsClinicalCommitmentVersion)
            .where(GlhsClinicalCommitmentVersion.commitment_id == commitment.id)
            .order_by(GlhsClinicalCommitmentVersion.version_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        policy = policy_for(commitment.domain)
        derived = derive_lifecycle_predicates(
            policy, action=data.action, target=data.target, due_time=data.due_time
        )
        for name, clause in (
            ("fulfillment", "fulfillment_predicate"),
            ("cancellation", "cancellation_predicate"),
            ("supersession", "supersession_predicate"),
            ("partial", "partial_predicate"),
        ):
            if predicates[clause] is None and name in derived:
                predicates[clause] = validate_predicate(derived[name])
        validate_domain_version(
            policy=policy,
            action=data.action,
            target=data.target,
            authority_class=data.authority_class,
            actor_role=scope.actor_role,
            prior_lifecycle=prior.lifecycle_state if prior is not None else None,
            lifecycle_state=data.lifecycle_state,
            due_time=data.due_time,
            grace_end=data.grace_end,
            has_fulfillment_predicate=predicates["fulfillment_predicate"] is not None,
            has_cancellation_predicate=predicates["cancellation_predicate"] is not None,
            has_supersession_predicate=predicates["supersession_predicate"] is not None,
            has_partial_predicate=predicates["partial_predicate"] is not None,
        )
        version_no = 1 if prior is None else prior.version_no + 1
        version = GlhsClinicalCommitmentVersion(
            commitment_id=commitment.id,
            base_state_version=base,
            version_no=version_no,
            lifecycle_state=data.lifecycle_state,
            evidence_state=data.evidence_state,
            timeliness_state=data.timeliness_state,
            action=data.action,
            target_json=data.target,
            dependencies_json=list(data.dependencies),
            conditional_trigger_json=predicates["conditional_trigger"],
            fulfillment_predicate_json=predicates["fulfillment_predicate"],
            cancellation_predicate_json=predicates["cancellation_predicate"],
            supersession_predicate_json=predicates["supersession_predicate"],
            partial_predicate_json=predicates["partial_predicate"],
            conflict_rules_json={"rule": policy.conflict_rule},
            abstention_rules_json={"rule": policy.abstention_rule},
            anchor_valid_time=data.anchor_valid_time,
            anchor_known_time=data.anchor_known_time,
            state_effective_at=(
                data.state_effective_at
                if data.state_effective_at is not None
                else data.anchor_valid_time
            ),
            earliest_valid_time=data.earliest_valid_time,
            due_time=data.due_time,
            grace_end=data.grace_end,
            authority_class=data.authority_class,
            schema_version="commitloop.commitment.v1",
            policy_version=COMMITMENT_POLICY_VERSION,
            consent_version=consent_version,
        )
        db.add(version)
        db.flush()
        now = datetime.now(UTC)
        transition = GlhsClinicalCommitmentTransition(
            public_id=str(uuid4()),
            profile_id=scope.profile.id,
            commitment_id=commitment.id,
            prior_version_id=prior.id if prior else None,
            result_version_id=version.id,
            base_state_version=base,
            resulting_state_version=base + 1,
            valid_at=data.anchor_valid_time,
            known_at=now,
            transition_kind=transition_kind,
            reason_code=reason_code,
            evidence_ids_json=evidence_ids,
            predicate_clause_json=predicates,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            origin=proposal.origin,
            policy_version=COMMITMENT_POLICY_VERSION,
            consent_version=consent_version,
            proposal_id=proposal.id,
            source_snapshot_id=proposal.source_snapshot_id,
            source_snapshot_digest=proposal.source_snapshot_digest,
            request_digest=request_digest,
            idempotency_key_hash=key_hash,
        )
        db.add(transition)
        db.add(
            GlhsStateVersion(
                profile_id=scope.profile.id,
                state_version=base + 1,
                valid_at=data.anchor_valid_time,
                policy_version=COMMITMENT_POLICY_VERSION,
            )
        )
        add_outbox(
            db,
            event_id=_canonical_digest(
                {"kind": "commitment.transition", "id": transition.public_id}
            ),
            profile_id=scope.profile.id,
            aggregate_type="glhs_clinical_commitment",
            aggregate_public_id=commitment.public_id,
            event_type="glhs.commitment.transition.applied",
        )
        db.flush()
        db.commit()
        return "admitted", None
    except (GlhsInvariantError, Exception) as exc_info:
        db.rollback()
        return "rejected", str(exc_info)


def _run_execution(
    db: Session,
    *,
    schedule: dict[str, Any],
    arm: str,
    run_id: str,
    sequence: int,
) -> ExecutionRecord:
    family_name = str(schedule["family_name"])
    seed = _seed(db, schedule)
    scope = seed.scope
    commitment = seed.commitment
    a2 = seed.snapshot_a2
    assert scope is not None and commitment is not None and a2 is not None

    disclosed_ids = [e.public_id for e in seed.evidence_rows]
    observed_ids = list(disclosed_ids)
    source_id = a2.snapshot_id
    source_digest = a2.manifest_digest
    evidence_to_pass = list(seed.evidence_rows)
    proposal_purpose: str | None = None

    # Apply family-specific variations
    if family_name == "ID-SUB":
        source_id = f"SNAP-SUBSTITUTED-{uuid4().hex[:8]}"
    elif family_name == "DIGEST-MUT":
        source_digest = f"DIGEST-MUTATED-CORRUPTED-{uuid4().hex[:8]}"
    elif family_name == "EVIDENCE-OUTSIDE":
        extra_e = _seed_evidence(
            db, profile_id=scope.profile.id, schedule_id=schedule["schedule_id"], label="EVD-EXTRA-999", at=VALID_AT2
        )
        observed_ids.append(extra_e.public_id)
        evidence_to_pass.append(extra_e)
    elif family_name == "MIN-SET-SWAP":
        swap_e = _seed_evidence(
            db, profile_id=scope.profile.id, schedule_id=schedule["schedule_id"], label="EVD-SWAP-888", at=VALID_AT2
        )
        observed_ids = [swap_e.public_id]
        evidence_to_pass = [swap_e]
    elif family_name == "CROSS-SNAPSHOT-SAME-VERSION":
        source_id = f"SNAP-CROSS-{uuid4().hex[:8]}"
        source_digest = f"DIGEST-CROSS-{uuid4().hex[:8]}"
    elif family_name == "COORD-SUB":
        # Mutate purpose in proposal context to trigger governance rejection
        proposal_purpose = "research" if scope.purpose != "research" else "clinical_review"
    elif family_name == "LINEAGE-ROOT-SUB":
        source_id = f"SNAP-ROOT-SUB-{uuid4().hex[:8]}"
        source_digest = f"DIGEST-ROOT-SUB-{uuid4().hex[:8]}"
    elif family_name == "EXPIRY-CONTROL":
        expired_row = _seed_expired_snapshot(db, seed)
        source_id = expired_row.public_id
        source_digest = expired_row.manifest_digest
    elif family_name == "CLEAN":
        pass

    origin = "clinician" if scope.actor_role == "clinician" else ("caregiver" if scope.actor_role == "caregiver" else "user")
    proposal = _insert_candidate_proposal(
        db,
        seed,
        schedule,
        source_id=source_id,
        source_digest=source_digest,
        observed=observed_ids,
        purpose=proposal_purpose,
        origin=origin,
    )

    current_version = current_state_version(db, profile_id=scope.profile.id)
    status, reason = _attempt_admission(
        db,
        arm=arm,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=tuple(evidence_to_pass),
        data=_version_data(schedule["context"]),
        expected_state_version=current_version,
        idempotency_key=f"e01-exec-{schedule['schedule_id']}-{arm}-{uuid4().hex}",
        transition_kind="commitment_opened",
        reason_code="binding_ablation_eval",
    )

    return ExecutionRecord(
        run_id=run_id,
        schedule_id=schedule["schedule_id"],
        arm=arm,
        sequence=sequence,
        admitted=(status == "admitted"),
        rejection_reason_code=reason,
        snapshot_coordinates={"source_snapshot_id": source_id, "source_digest": source_digest},
        governance_coordinates=dict(schedule["context"]),
        binding_check_applied=binding_check_applied(arm),
        expected_admissibility=schedule["expected_admissibility"],
    )


def run_ablation(
    engine: Engine,
    *,
    schedules: list[dict[str, Any]],
    protocol: dict[str, Any],
    observer: Observer,
    run_id: str,
) -> dict[str, Any]:
    """Execute all schedules across all 8 arms."""
    sequence = 0
    total_execs = len(schedules) * len(ALL_ARMS)
    print(f"Starting E01 ablation execution: {len(schedules)} schedules x 8 arms = {total_execs} runs")

    for schedule in schedules:
        for arm in ALL_ARMS:
            sequence += 1
            with Session(engine) as db:
                record = _run_execution(
                    db,
                    schedule=schedule,
                    arm=arm,
                    run_id=run_id,
                    sequence=sequence,
                )
                observer.append(record)

    return {
        "run_id": run_id,
        "total_executions": sequence,
        "schedules_count": len(schedules),
        "arms_count": len(ALL_ARMS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run E01 2^3 Factorial Component Ablation")
    parser.add_argument("--backend", choices=["postgres", "sqlite"], default="sqlite")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/E01/results"),
    )
    args = parser.parse_args()

    pkg_dir = Path(__file__).resolve().parent
    schedules_path = pkg_dir / "schedules.json"
    protocol_path = pkg_dir / "protocol.json"

    schedules_doc = json.loads(schedules_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    validate_schedules(schedules_doc)
    validate_protocol(protocol)
    validate_schedule_hash(schedules_path.read_bytes(), protocol["schedule_inventory"]["schedules_sha256"])

    run_id = args.run_id or f"GLHS-E01-{args.backend.upper()}-{uuid4().hex[:8]}"
    raw_path = args.output_dir / "raw" / f"executions_{run_id}.jsonl"
    observer = Observer(raw_path)

    if args.backend == "postgres":
        url = _require_isolated_postgres(args.database_url)
        schema = _random_schema_name()
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.commit()
        schema_engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema},public"},
        )
        Base.metadata.create_all(schema_engine)
        try:
            summary = run_ablation(
                schema_engine,
                schedules=schedules_doc["schedules"],
                protocol=protocol,
                observer=observer,
                run_id=run_id,
            )
        finally:
            schema_engine.dispose()
            with engine.connect() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                conn.commit()
            engine.dispose()
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        summary = run_ablation(
            engine,
            schedules=schedules_doc["schedules"],
            protocol=protocol,
            observer=observer,
            run_id=run_id,
        )
        engine.dispose()

    manifest = {
        "run_id": run_id,
        "backend": "postgres" if args.backend == "postgres" else "sqlite_smoke",
        "freeze_id": protocol["freeze_id"],
        "git_sha": _full_git_sha(),
        "created_utc": datetime.now(UTC).isoformat(),
        "summary": summary,
    }
    manifest_path = args.output_dir / f"manifest_{run_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Run completed successfully: manifest -> {manifest_path}")


if __name__ == "__main__":
    main()
