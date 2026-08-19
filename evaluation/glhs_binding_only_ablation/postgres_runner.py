"""Execution runner for the GLHS exact-binding ablation (320 schedules x 2 arms).

Runs the frozen protocol (``protocol.json`` + ``schedules.json``) through the
real production commitment admission path over an isolated PostgreSQL database
in a fresh random schema, reusing the connection approach of
``evaluation/glhs_postgres_toctou/executor_v2.py``.  Each logical schedule is
executed once under each arm (640 executions); the scientific unit is the
logical schedule.

The admission path mirrors ``commitment_gateway.apply_commitment_transition``
step for step (scope, proposal digest, provenance, idempotency, profile state
lock, stale-state recheck, consent re-read, domain validation, append-only
version/transition/state rows, outbox) with exactly ONE arm-dependent step:
the context validation is delegated to the evaluation-only
``adapter.validate_proposal_context`` (workstream C-005).  No production code
is modified; no feature flag exists anywhere.

Fail-closed contract:

- Refuses to run without ``GLHS_BINDING_ABLATION_ISOLATED_RESEARCH=1`` and a
  ``postgresql://`` URL that is not a shared/default database.
- ``--backend sqlite`` is an explicit smoke backend: the same code path on a
  real SQLite database.  SQLite smoke results are NOT the final run and are
  always labeled ``backend=sqlite_smoke`` in the manifest and seal.
- Never fabricates results: every observation comes from actually executing
  the schedule under the arm; the raw stream is append-only and hash-chained
  (``observer.Observer``).
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
from clara_api.glhs.canonical_json import consistency_fingerprint
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
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
    review_model_commitment_proposal,
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

from evaluation.glhs_binding_only_ablation.adapter import (
    FULL_GOVERNANCE_NO_EXACT_BINDING,
    GLHS_EXACT_BINDING,
    binding_check_applied,
    validate_proposal_context,
)
from evaluation.glhs_binding_only_ablation.observer import ExecutionRecord, Observer
from evaluation.glhs_binding_only_ablation.validate import (
    validate_protocol,
    validate_schedule_hash,
    validate_schedules,
)

ISOLATION_ATTESTATION_ENV = "GLHS_BINDING_ABLATION_ISOLATED_RESEARCH"
DATABASE_URL_ENV = "GLHS_BINDING_ABLATION_DATABASE_URL"
BACKENDS = frozenset({"postgres", "sqlite"})
ARMS_ORDER = (FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING)

VALID_AT = datetime(2026, 8, 1, tzinfo=UTC)
VALID_AT2 = datetime(2026, 8, 19, tzinfo=UTC)

TARGET_SYSTEMS = {
    "observations": "http://loinc.org",
    "medications": "http://www.whocc.no/atc",
    "allergies": "http://snomed.info/sct",
    "conditions": "http://snomed.info/sct",
}
TARGET_CODES = {
    "observations": "2339-0",
    "medications": "A10BA02",
    "allergies": "419199007",
    "conditions": "73211009",
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
    return f"glhs_binding_ablation_{uuid4().hex}"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        source_kind="glhs-binding-ablation",
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
            fingerprint=f"ba:{schedule_id}:{label}",
            valid_from=at,
        ),
    )


class RunnerEnv:
    """Duck-typed handles: injectable sessions for tests, real DB in production."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory


class SeedContext:
    """Everything seeded for one execution; keeps real ORM handles."""

    def __init__(self) -> None:
        self.scope: ProfileScope | None = None
        self.commitment: GlhsClinicalCommitment | None = None
        self.evidence_rows: list[GlhsEvidence] = []
        self.snapshot_a: Any = None
        self.snapshot_a2: Any = None
        self.snapshot_b: Any = None
        self.proposal1: GlhsClinicalCommitmentProposal | None = None
        self.candidate: GlhsClinicalCommitmentProposal | None = None
        self.foreign_scope: ProfileScope | None = None
        self.foreign_evidence: GlhsEvidence | None = None
        self.foreign_snapshot: Any = None
        self.extra_rows: dict[str, GlhsEvidence] = {}
        self.base_state_version: int = 1


def _seed(db: Session, schedule: dict[str, Any]) -> SeedContext:
    schedule_id = str(schedule["schedule_id"])
    context = dict(schedule["context"])
    domain = str(context["domain"])
    seed = SeedContext()
    user = User(
        email=f"ba-{schedule_id}-{uuid4().hex}@example.test",
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
    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )
    seed.scope = scope
    evidence_count = int(context["evidence_count"])
    for index in range(1, evidence_count + 1):
        seed.evidence_rows.append(_seed_evidence(db, profile_id=profile.id, schedule_id=schedule_id, label=f"E{index}", at=VALID_AT))
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"ba:{domain}:{schedule_id}:1",
        domain=domain,
        supersession_key=f"ba:{domain}:{schedule_id}",
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
        origin="user",
        observed_base_state_version=snapshot_a.state_version,
        task=snapshot_a.task,
        source_snapshot_id=snapshot_a.snapshot_id,
        source_snapshot_digest=snapshot_a.manifest_digest,
    )
    seed.proposal1 = proposal1
    apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal1,
        evidence=tuple(seed.evidence_rows),
        data=_version_data(context),
        expected_state_version=snapshot_a.state_version,
        idempotency_key=f"ba-seed-{schedule_id}-{uuid4().hex}",
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


def _seed_foreign(db: Session, schedule: dict[str, Any]) -> SeedContext:
    schedule_id = str(schedule["schedule_id"])
    context = dict(schedule["context"])
    domain = str(context["domain"])
    seed = SeedContext()
    user = User(
        email=f"ba-foreign-{schedule_id}-{uuid4().hex}@example.test",
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
    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )
    seed.foreign_scope = scope
    evidence = _seed_evidence(db, profile_id=profile.id, schedule_id=schedule_id, label="Y1", at=VALID_AT)
    seed.foreign_evidence = evidence
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task=str(context["task"]),
        purpose=scope.purpose,
        valid_at=VALID_AT,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({domain}),
        disclosed_evidence=(evidence,),
    )
    seed.foreign_snapshot = snapshot
    return seed


def _compile_substituted_snapshot(
    db: Session, seed: SeedContext, schedule: dict[str, Any], kind: str
) -> Any:
    """Compile a second, fully valid snapshot B of the same profile/state version.

    B shares every governance coordinate with A2 (profile, state version,
    policy, consent, purpose, task, actor) but its *disclosure* differs
    (target-declared compilation with no or different disclosed evidence), so
    a proposal observing A2's evidence fails B's evidence-membership check.
    This is the exact-binding adversarial mechanism for families 5 and 8.
    """
    schedule_id = str(schedule["schedule_id"])
    context = dict(schedule["context"])
    domain = str(context["domain"])
    scope = seed.scope
    assert scope is not None
    disclosed: tuple[GlhsEvidence, ...] = ()
    target_semantic_key: str | None = None
    target: dict[str, Any] | None = None
    if kind == "opening_flow_no_disclosure":
        target_semantic_key = f"ba:missing:{schedule_id}"
    elif kind in {"opening_flow_disclosed_other", "opening_flow_disclosed_extra"}:
        target_semantic_key = f"ba:missing:{schedule_id}"
        disclosed = (seed.extra_rows["X1"],)
    elif kind == "declared_target_mismatch":
        target_semantic_key = f"ba:missing2:{schedule_id}"
        target = {"system": TARGET_SYSTEMS[domain], "code": "other-code"}
    else:
        raise ValueError(f"unknown_substitution_kind:{kind}")
    return compile_commitment_thss(
        db,
        scope=scope,
        task=str(context["task"]),
        purpose=scope.purpose,
        valid_at=VALID_AT2,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({domain}),
        disclosed_evidence=disclosed,
        target_semantic_key=target_semantic_key,
        target=target,
    )


def _insert_tampered_manifest(
    db: Session, seed: SeedContext, schedule: dict[str, Any], *, mutation: str
) -> Any:
    """Insert a tampered manifest copy with only one broken disclosure dependency.

    GLHS ledger rows are append-only immutable (``before_update`` guard), so a
    tampered manifest is represented as a directly-inserted row that is
    identical to A2 on every coordinate and digest EXCEPT the single
    disclosure-dependency attribute under test:

    - ``payload``: the stored payload is mutated while ``snapshot_digest``
      stays stale -> fingerprint(payload) != snapshot_digest.
    - ``expired``: every digest stays self-consistent, only ``expires_at`` is
      moved into the past -> proposal_snapshot_expired.
    """
    a2 = seed.snapshot_a2
    scope = seed.scope
    assert a2 is not None and scope is not None
    persisted_a2 = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.public_id == a2.snapshot_id,
            GlhsSnapshotManifest.profile_id == scope.profile.id,
        )
    ).scalar_one()
    variant = dict(schedule.get("variant") or {})
    payload = dict(persisted_a2.snapshot_payload_json)
    expires_at = persisted_a2.expires_at
    if mutation == "payload":
        target = str(variant["payload_mutation_target"])
        payload[target] = {"mutated": schedule["schedule_id"], "target": target}
    elif mutation == "expired":
        offset = int(variant["expiry_offset_seconds"])
        expires_at = datetime.now(UTC) - timedelta(seconds=offset)
    else:
        raise ValueError(f"unknown_tamper_mutation:{mutation}")
    row = GlhsSnapshotManifest(
        public_id=str(uuid4()),
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
        snapshot_payload_json=payload,
        snapshot_digest=persisted_a2.snapshot_digest,
        expires_at=expires_at,
    )
    row.manifest_digest = consistency_fingerprint(_manifest_envelope(row))
    db.add(row)
    db.flush()
    return row


def _extra_evidence(db: Session, seed: SeedContext, schedule: dict[str, Any], label: str) -> GlhsEvidence:
    """Create (or reuse) an evidence row outside A2's disclosed provenance."""
    schedule_id = str(schedule["schedule_id"])
    scope = seed.scope
    assert scope is not None
    if label in ("X1", "X2", "X3"):
        if label in seed.extra_rows:
            return seed.extra_rows[label]
        row = _seed_evidence(db, profile_id=scope.profile.id, schedule_id=schedule_id, label=label, at=VALID_AT2)
        seed.extra_rows[label] = row
        return row
    if label == "Y1":
        seed_foreign = _seed_foreign(db, schedule)
        seed.foreign_evidence = seed_foreign.foreign_evidence
        return seed_foreign.foreign_evidence
    raise ValueError(f"unknown_extra_evidence_label:{label}")


def _insert_candidate_proposal(
    db: Session,
    seed: SeedContext,
    schedule: dict[str, Any],
    *,
    source_id: str,
    source_digest: str,
    observed: list[str],
    origin: str = "user",
    model_manifest_ref: str | None = None,
    reviewed_proposal_id: int | None = None,
    inference_context_binding_id: int | None = None,
) -> GlhsClinicalCommitmentProposal:
    """Insert a proposal row with crafted binding fields.

    Used for adversarial schedules: an attacker/tampered lineage input lands in
    the database as a proposal whose binding payload is self-inconsistent (or
    references the wrong manifest).  The row is inserted directly because the
    GLHS proposal ledger is append-only immutable; the commit-time revalidation
    (GLHS-B05) is exactly what must catch it.  The proposal digest is
    recomputed over the crafted envelope, mirroring production.
    """
    context = dict(schedule["context"])
    scope = seed.scope
    commitment = seed.commitment
    assert scope is not None and commitment is not None
    base = current_state_version(db, profile_id=scope.profile.id)
    proposal = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=scope.profile.public_id,
        base_state_version=base,
        observed_evidence_ids_json=sorted(set(observed)),
        proposed_transition="OPEN",
        purpose=scope.purpose,
        task=str(context["task"]),
        origin=origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        inference_context_binding_id=inference_context_binding_id,
        inference_actor_user_id=scope.actor.id if inference_context_binding_id is not None else None,
        inference_actor_role=scope.actor_role if inference_context_binding_id is not None else "",
        context_binding_mode="snapshot_bound",
        model_manifest_ref=model_manifest_ref,
        source_snapshot_id=source_id,
        source_snapshot_digest=source_digest,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version="medical_disclaimer:" + required_medical_disclaimer_version(),
        reviewed_proposal_id=reviewed_proposal_id,
    )
    proposal.proposal_digest = _canonical_digest(_proposal_envelope(proposal))
    db.add(proposal)
    db.flush()
    seed.candidate = proposal
    return proposal


def _prepare_candidate(db: Session, seed: SeedContext, schedule: dict[str, Any]) -> GlhsClinicalCommitmentProposal:
    """Create the admission candidate with the schedule's disclosure-delta.

    Controls go through the production proposal path unchanged.  Adversarial
    schedules insert a crafted proposal row whose ONLY divergence is the
    disclosure dependency; current state/governance coordinates stay valid
    (GLHS-A03, C-007).
    """
    schedule_id = str(schedule["schedule_id"])
    context = dict(schedule["context"])
    variant = dict(schedule.get("variant") or {})
    scope = seed.scope
    commitment = seed.commitment
    a2 = seed.snapshot_a2
    assert scope is not None and commitment is not None and a2 is not None
    family_id = int(schedule["family_id"])
    kind = str(schedule["kind"])
    observed = [str(evidence.public_id) for evidence in seed.evidence_rows]
    source_id = str(a2.snapshot_id)
    source_digest = str(a2.manifest_digest)

    if kind == "control":
        proposal = propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=tuple(seed.evidence_rows),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=a2.state_version,
            task=a2.task,
            source_snapshot_id=source_id,
            source_snapshot_digest=source_digest,
        )
        seed.candidate = proposal
        return proposal

    if family_id == 1:
        wrong_id_kind = str(variant["wrong_id_kind"])
        if wrong_id_kind == "absent_well_formed":
            source_id = str(uuid4())
        elif wrong_id_kind == "other_profile_manifest":
            seed_foreign = _seed_foreign(db, schedule)
            seed.foreign_snapshot = seed_foreign.foreign_snapshot
            source_id = str(seed_foreign.foreign_snapshot.snapshot_id)
        elif wrong_id_kind == "non_uuid_string":
            source_id = "not-a-uuid-binding"
        elif wrong_id_kind == "empty_string":
            source_id = ""
        else:
            raise ValueError(f"unknown_wrong_id_kind:{wrong_id_kind}")
    elif family_id == 2:
        wrong_digest_kind = str(variant["wrong_digest_kind"])
        if wrong_digest_kind == "zero_hex_64":
            source_digest = "0" * 64
        elif wrong_digest_kind == "digest_of_unrelated_payload":
            source_digest = consistency_fingerprint({"unrelated": schedule_id})
        elif wrong_digest_kind == "truncated_hex":
            source_digest = "a" * 32
        elif wrong_digest_kind == "uppercase_hex_64":
            source_digest = "A" * 64
        else:
            raise ValueError(f"unknown_wrong_digest_kind:{wrong_digest_kind}")
    elif family_id == 3:
        tampered = _insert_tampered_manifest(db, seed, schedule, mutation="payload")
        seed.snapshot_b = tampered
        source_id = str(tampered.public_id)
        source_digest = str(tampered.manifest_digest)
    elif family_id == 4:
        for label in variant.get("extra_undisclosed") or []:
            extra = _extra_evidence(db, seed, schedule, label)
            seed.extra_rows[label] = extra
            observed.append(str(extra.public_id))
    elif family_id == 5:
        substitution_kind = str(variant["substitution_kind"])
        if substitution_kind != "opening_flow_no_disclosure":
            _extra_evidence(db, seed, schedule, "X1")
        seed.snapshot_b = _compile_substituted_snapshot(db, seed, schedule, substitution_kind)
        source_id = str(seed.snapshot_b.snapshot_id)
        source_digest = str(seed.snapshot_b.manifest_digest)
    elif family_id == 6:
        tampered = _insert_tampered_manifest(db, seed, schedule, mutation="expired")
        seed.snapshot_b = tampered
        source_id = str(tampered.public_id)
        source_digest = str(tampered.manifest_digest)
    elif family_id == 7:
        observed = []
        for label in variant.get("swap") or []:
            if label == "Y1":
                seed_foreign = _seed_foreign(db, schedule)
                seed.foreign_evidence = seed_foreign.foreign_evidence
                observed.append(str(seed_foreign.foreign_evidence.public_id))
            elif label == "Z1":
                get_or_create_commitment(
                    db,
                    scope=scope,
                    semantic_key=f"ba-other:{schedule_id}",
                    domain=str(schedule["context"]["domain"]),
                    supersession_key=f"ba-other:{schedule_id}",
                )
                other_evidence = _seed_evidence(
                    db, profile_id=scope.profile.id, schedule_id=schedule_id, label="Z1", at=VALID_AT2
                )
                seed.extra_rows["Z1"] = other_evidence
                observed.append(str(other_evidence.public_id))
            elif label == "X1":
                observed.append(str(_extra_evidence(db, seed, schedule, "X1").public_id))
            elif label.startswith("E"):
                observed.append(str(seed.evidence_rows[int(label[1:]) - 1].public_id))
            else:
                raise ValueError(f"unknown_swap_evidence_label:{label}")
    elif family_id == 8:
        persisted_a2 = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.public_id == a2.snapshot_id,
                GlhsSnapshotManifest.profile_id == scope.profile.id,
            )
        ).scalar_one()
        binding = create_inference_context_binding(
            db,
            profile_id=scope.profile.id,
            inference_manifest_id=f"ba-model:{schedule_id}",
            snapshot=persisted_a2,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            purpose=scope.purpose,
            task=str(context["task"]),
            disclosed_evidence_ids=observed,
        )
        model_proposal = propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=tuple(seed.evidence_rows),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=a2.state_version,
            task=a2.task,
            source_snapshot_id=source_id,
            source_snapshot_digest=source_digest,
            model_manifest_ref=f"ba-model:{schedule_id}",
            inference_context_binding_id=binding.public_id,
        )
        review_model_commitment_proposal(db, scope=scope, proposal=model_proposal)
        substitution_kind = str(variant["substitution_kind"])
        if substitution_kind != "opening_flow_no_disclosure":
            _extra_evidence(db, seed, schedule, "X1")
        seed.snapshot_b = _compile_substituted_snapshot(db, seed, schedule, substitution_kind)
        return _insert_candidate_proposal(
            db,
            seed,
            schedule,
            source_id=str(seed.snapshot_b.snapshot_id),
            source_digest=str(seed.snapshot_b.manifest_digest),
            observed=observed,
            origin="user",
            model_manifest_ref=f"ba-model:{schedule_id}",
            reviewed_proposal_id=model_proposal.id,
            inference_context_binding_id=model_proposal.inference_context_binding_id,
        )
    else:
        raise ValueError(f"unknown_family_id:{family_id}")

    return _insert_candidate_proposal(
        db,
        seed,
        schedule,
        source_id=source_id,
        source_digest=source_digest,
        observed=observed,
    )


def _find_transition_by_key(db: Session, *, profile_id: int, key_hash: str) -> GlhsClinicalCommitmentTransition | None:
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
    """Mirror ``apply_commitment_transition`` with the arm-selected validation.

    Every step below follows the production admission path exactly; the only
    arm-dependent step is the context validation delegated to the
    evaluation-only adapter (the production function's
    ``_validate_current_proposal_context`` is never weakened or bypassed).
    """
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
        if not set(evidence_ids).issubset(set(proposal.observed_evidence_ids_json)):
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
            event_id=_canonical_digest({"kind": "commitment.transition", "id": transition.public_id}),
            profile_id=scope.profile.id,
            aggregate_type="glhs_clinical_commitment",
            aggregate_public_id=commitment.public_id,
            event_type="glhs.commitment.transition.applied",
        )
        db.flush()
        db.commit()
        return "admitted", None
    except GlhsInvariantError as exc:
        db.rollback()
        return "rejected", str(exc)


def _evidence_for_admission(seed: SeedContext, schedule: dict[str, Any]) -> tuple[GlhsEvidence, ...]:
    variant = dict(schedule.get("variant") or {})
    if schedule["kind"] != "adversarial":
        return tuple(seed.evidence_rows)
    family_id = int(schedule["family_id"])
    if family_id == 4:
        rows: list[GlhsEvidence] = list(seed.evidence_rows)
        for label in variant.get("extra_undisclosed") or []:
            rows.append(seed.extra_rows[label])
        return tuple(rows)
    if family_id == 7:
        rows = []
        for label in variant.get("swap") or []:
            if label == "Y1":
                assert seed.foreign_evidence is not None
                rows.append(seed.foreign_evidence)
            elif label == "Z1":
                rows.append(seed.extra_rows["Z1"])
            elif label == "X1":
                rows.append(seed.extra_rows["X1"])
            elif label.startswith("E"):
                index = int(label[1:])
                rows.append(seed.evidence_rows[index - 1])
            else:
                raise ValueError(f"unknown_swap_evidence_label:{label}")
        return tuple(rows)
    return tuple(seed.evidence_rows)


def _governance_coordinates(
    seed: SeedContext, schedule: dict[str, Any], *, base: int, evidence: tuple[GlhsEvidence, ...]
) -> dict[str, Any]:
    context = dict(schedule["context"])
    scope = seed.scope
    assert scope is not None
    return {
        "current_state_version": base,
        "expected_state_version": seed.base_state_version,
        "policy_version": COMMITMENT_POLICY_VERSION,
        "consent_version": "medical_disclaimer:" + required_medical_disclaimer_version(),
        "purpose": scope.purpose,
        "task": str(context["task"]),
        "actor_role": scope.actor_role,
        "domain": str(context["domain"]),
        "action": str(context["action"]),
        "lifecycle_state": "OPEN",
        "authority_class": "patient_report",
        "allowed_actions": sorted(scope.allowed_actions),
        "target": TARGET_SYSTEMS[str(context["domain"])] + "/" + TARGET_CODES[str(context["domain"])],
        "evidence_fingerprints": sorted(row.fingerprint for row in evidence),
    }


def _snapshot_coordinates(seed: SeedContext, schedule: dict[str, Any]) -> dict[str, Any]:
    candidate = seed.candidate
    assert candidate is not None
    manifest = seed.snapshot_b if seed.snapshot_b is not None else seed.snapshot_a2
    assert manifest is not None
    provenance = getattr(manifest, "provenance_ids_json", None)
    if provenance is None:
        minimal = getattr(manifest, "minimal_evidence", None)
        provenance = (minimal or {}).get("evidence_ids", [])
    return {
        "disclosure_delta_type": str(schedule["disclosure_delta_type"]),
        "source_snapshot_id": str(candidate.source_snapshot_id or ""),
        "source_snapshot_digest_sha256": _sha256_hex(str(candidate.source_snapshot_digest or "")),
        "snapshot_state_version": int(manifest.state_version),
        "snapshot_expires_at": manifest.expires_at.isoformat() if manifest.expires_at else None,
        "snapshot_provenance_count": len(provenance or []),
        "observed_evidence_count": len(candidate.observed_evidence_ids_json or []),
    }


def _run_execution(
    env: RunnerEnv,
    schedule: dict[str, Any],
    *,
    arm: str,
    run_id: str,
    sequence: int,
) -> ExecutionRecord:
    db = env.session_factory()
    try:
        seed = _seed(db, schedule)
        assert seed.scope is not None and seed.commitment is not None and seed.snapshot_a2 is not None
        _prepare_candidate(db, seed, schedule)
        base = current_state_version(db, profile_id=seed.scope.profile.id)
        evidence = _evidence_for_admission(seed, schedule)
        idempotency_key = f"ba-{schedule['schedule_id']}-{arm}-{uuid4().hex}"
        outcome, reason_code = _attempt_admission(
            db,
            arm=arm,
            scope=seed.scope,
            commitment=seed.commitment,
            proposal=seed.candidate,
            evidence=evidence,
            data=_version_data(dict(schedule["context"])),
            expected_state_version=base,
            idempotency_key=idempotency_key,
            transition_kind="commitment_continued",
            reason_code="binding_ablation_synthetic",
        )
        txid: int | None = None
        backend_pid: int | None = None
        for query in ("SELECT txid_current()", "SELECT pg_backend_pid()"):
            try:
                value = db.scalar(text(query))
                if query.startswith("SELECT txid_current"):
                    txid = int(value) if value is not None else None
                else:
                    backend_pid = int(value) if value is not None else None
            except exc.SQLAlchemyError:
                pass
        return ExecutionRecord(
            run_id=run_id,
            schedule_id=str(schedule["schedule_id"]),
            arm=arm,
            sequence=sequence,
            admitted=outcome == "admitted",
            rejection_reason_code=reason_code,
            snapshot_coordinates=_snapshot_coordinates(seed, schedule),
            governance_coordinates=_governance_coordinates(seed, schedule, base=base, evidence=evidence),
            binding_check_applied=binding_check_applied(arm),
            expected_admissibility=str(schedule["expected_admissibility"]),
            txid=txid,
            backend_pid=backend_pid,
        )
    finally:
        db.close()


def _postgres_metadata(engine: Engine) -> dict[str, object]:
    with engine.connect() as connection:
        version = connection.scalar(text("select version()"))
        isolation = connection.execute(text("show transaction isolation level")).scalar_one()
        commit_timestamp = connection.execute(text("show track_commit_timestamp")).scalar_one()
    return {
        "version": version,
        "isolation_level": isolation,
        "track_commit_timestamp": commit_timestamp,
        "backend": "postgresql",
    }


def _sqlite_metadata(engine: Engine) -> dict[str, object]:
    with engine.connect() as connection:
        version = connection.scalar(text("select sqlite_version()"))
    return {"version": version, "backend": "sqlite", "smoke_note": "NOT the final run"}


def _engine_for(backend: str, database_url: str | None, results_dir: Path) -> tuple[Engine, dict[str, object], Callable[[], None], str | None]:
    if backend == "postgres":
        url = _require_isolated_postgres(database_url)
        schema = _random_schema_name()
        admin = create_engine(url, pool_pre_ping=True)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(engine)
        metadata = _postgres_metadata(engine)

        def cleanup() -> None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin.dispose()

        return engine, metadata, cleanup, schema
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, _sqlite_metadata(engine), lambda: None, None


def execute(
    protocol_path: Path,
    schedules_path: Path,
    results_dir: Path,
    *,
    backend: str = "postgres",
    database_url: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Execute the frozen protocol under both arms and append raw observations."""
    if backend not in BACKENDS:
        raise ValueError(f"unknown_backend:{backend}")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    validate_schedule_hash(
        schedules_path.read_bytes(),
        str((protocol.get("schedule_inventory") or {}).get("schedules_sha256")),
    )
    schedules_document = json.loads(schedules_path.read_text(encoding="utf-8"))
    validate_schedules(schedules_document)
    schedules = schedules_document["schedules"]
    if run_id is None:
        run_id = f"GLHS-BA-{backend.upper()}-{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    results_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"executions_{run_id}.jsonl"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        raise RuntimeError(f"glhs_binding_ablation_raw_stream_exists:{raw_path}")

    engine, metadata, cleanup, _schema = _engine_for(backend, database_url, results_dir)
    env = RunnerEnv(session_factory=lambda: Session(engine, expire_on_commit=False))
    observer = Observer(raw_path)
    sequence = 1
    executed = 0
    started = datetime.now(UTC)
    try:
        for schedule in schedules:
            if limit is not None and executed >= limit:
                break
            for arm in ARMS_ORDER:
                record = _run_execution(env, schedule, arm=arm, run_id=run_id, sequence=sequence)
                observer.append(record)
                sequence += 1
                executed += 1
        finished = datetime.now(UTC)
        manifest = {
            "run_id": run_id,
            "freeze_id": str(protocol.get("freeze_id")),
            "backend": "isolated_postgresql_random_schema" if backend == "postgres" else "sqlite_smoke",
            "backend_detail": metadata,
            "schema_retained": False,
            "executed_executions": executed,
            "expected_executions": len(schedules) * 2,
            "schedule_count": len(schedules),
            "arm_order": list(ARMS_ORDER),
            "protocol_path": str(protocol_path),
            "schedules_path": str(schedules_path),
            "protocol_sha256": _sha256_hex(protocol_path.read_text(encoding="utf-8")),
            "schedules_sha256": _sha256_hex(schedules_path.read_text(encoding="utf-8")),
            "freeze_hashes": {
                "protocol_sha256": _sha256_hex(protocol_path.read_text(encoding="utf-8")),
                "schedules_sha256": _sha256_hex(schedules_path.read_text(encoding="utf-8")),
            },
            "source_revision": _source_revision(),
            "source_sha256": _full_git_sha(),
            "started_utc": started.isoformat(),
            "finished_utc": finished.isoformat(),
            "raw_stream": str(raw_path.relative_to(results_dir)),
            "note": (
                "SQLite smoke run: real production code paths on SQLite; NOT the "
                "final frozen PostgreSQL run."
                if backend == "sqlite"
                else "Isolated PostgreSQL random schema; final run candidate."
            ),
        }
        manifest_path = results_dir / f"manifest_{run_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    finally:
        engine.dispose()
        cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path("evaluation/glhs_binding_only_ablation/protocol.json"))
    parser.add_argument("--schedules", type=Path, default=Path("evaluation/glhs_binding_only_ablation/schedules.json"))
    parser.add_argument("--results-dir", type=Path, default=Path("research/glhs_journal/binding_only_ablation/results"))
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="postgres")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    manifest = execute(
        args.protocol,
        args.schedules,
        args.results_dir,
        backend=args.backend,
        database_url=args.database_url,
        run_id=args.run_id,
        limit=args.limit,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
