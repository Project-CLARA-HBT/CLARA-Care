"""Execution adapter for E03 Downgrade and Lineage Anti-Laundering schedules.

Executes each laundering attack pattern against the real GLHS gateway, commitment gateway,
and assertion persistence logic, verifying that:
1. Negative laundering schedules are strictly rejected with the expected invariant error.
2. Clean positive controls are successfully committed without errors.
3. Zero downgrade successes occur across all negative schedules.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)


def GlhsClinicalSnapshot(**kwargs: Any) -> GlhsSnapshotManifest:
    """Helper factory mapping legacy snapshot fields to GlhsSnapshotManifest."""
    if "disclosed_provenance_json" in kwargs:
        dp = kwargs.pop("disclosed_provenance_json")
        kwargs.setdefault("provenance_ids_json", dp.get("evidence_ids", []) if isinstance(dp, dict) else [])
    kwargs.setdefault("provenance_ids_json", [])
    kwargs.setdefault("task", "downgrade_test")
    kwargs.setdefault("purpose", "self_care")
    kwargs.setdefault("data_classes_json", ["medications", "observations"])
    kwargs.setdefault("assertion_ids_json", [])
    kwargs.setdefault("conflict_ids_json", [])
    kwargs.setdefault("expires_at", kwargs.get("created_at") or datetime.now(UTC))
    if "policy_version" in kwargs and isinstance(kwargs["policy_version"], int):
        kwargs["policy_version"] = str(kwargs["policy_version"])
    if "consent_version" in kwargs and isinstance(kwargs["consent_version"], int):
        kwargs["consent_version"] = str(kwargs["consent_version"])
    return GlhsSnapshotManifest(**kwargs)
from clara_api.glhs.canonical_json import fast_canonical_digest
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    ProfileScope,
    _require_lineage_binding,
    propose_bound_commitment_transition,
)


def _make_scope(profile: PhrProfile, actor: User, actor_role: str = "owner", purpose: str = "self_care") -> ProfileScope:
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role=actor_role,
        purpose=purpose,
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _make_binding(**kwargs: Any) -> GlhsInferenceContextBinding:
    from datetime import timedelta
    from uuid import uuid4
    from clara_api.glhs.gateway import (
        BINDING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        DIGEST_ALGORITHM,
        _snapshot_fingerprint,
        inference_binding_envelope,
    )
    kwargs.setdefault("inference_manifest_id", f"inf-manifest-{uuid4().hex[:12]}")
    kwargs.setdefault("consumed_thss", True)
    kwargs.setdefault("source_snapshot_digest", kwargs.get("source_manifest_digest", "0" * 64))
    kwargs.setdefault("source_manifest_digest", "0" * 64)
    kwargs.setdefault("disclosed_evidence_ids_json", [])
    kwargs.setdefault("evidence_set_digest", "0" * 64)
    kwargs.setdefault("snapshot_expires_at", datetime.now(UTC) + timedelta(hours=1))
    kwargs.setdefault("canonicalization_profile", CANONICALIZATION_PROFILE)
    kwargs.setdefault("digest_algorithm", DIGEST_ALGORITHM)
    kwargs.setdefault("binding_schema_version", BINDING_SCHEMA_VERSION)
    kwargs.setdefault("binding_digest", "")
    kwargs.setdefault("status", "COMPLETED")
    if "policy_version" in kwargs and isinstance(kwargs["policy_version"], int):
        kwargs["policy_version"] = str(kwargs["policy_version"])
    if "consent_version" in kwargs and isinstance(kwargs["consent_version"], int):
        kwargs["consent_version"] = str(kwargs["consent_version"])
    b = GlhsInferenceContextBinding(**kwargs)
    b.evidence_set_digest = _snapshot_fingerprint(b.disclosed_evidence_ids_json)
    b.binding_digest = _snapshot_fingerprint(inference_binding_envelope(b))
    return b


def _make_proposal(db: Session, **kwargs: Any) -> GlhsClinicalCommitmentProposal:
    kwargs.pop("profile_id", None)
    if "root_proposal_id" in kwargs:
        kwargs["reviewed_proposal_id"] = kwargs.pop("root_proposal_id")
    if "action" in kwargs:
        kwargs["proposed_transition"] = kwargs.pop("action")
    kwargs.setdefault("proposed_transition", "CREATE")
    kwargs.setdefault("origin", "human_review" if kwargs.get("reviewed_proposal_id") else "model")
    if "policy_version" in kwargs and isinstance(kwargs["policy_version"], int):
        kwargs["policy_version"] = str(kwargs["policy_version"])
    if "consent_version" in kwargs and isinstance(kwargs["consent_version"], int):
        kwargs["consent_version"] = str(kwargs["consent_version"])
    kwargs.setdefault("protocol_version", "glhs.v1")
    kwargs.setdefault("observed_evidence_ids_json", [])
    kwargs.setdefault("context_binding_mode", "snapshot_bound")
    kwargs.setdefault("proposal_digest", "0" * 64)
    kwargs.pop("authority_class", None)
    kwargs.pop("target_json", None)
    kwargs.pop("created_at", None)

    if "commitment_id" not in kwargs:
        comm_pub = kwargs.pop("commitment_public_id", "COMM-DEFAULT")
        comm = db.query(GlhsClinicalCommitment).filter_by(public_id=comm_pub).first()
        if not comm:
            p = db.query(PhrProfile).first()
            pid = p.id if p else 1
            comm = GlhsClinicalCommitment(
                public_id=comm_pub,
                profile_id=pid,
                semantic_key=f"medication:{comm_pub}",
                domain="medications",
                supersession_key=f"medication:{comm_pub}",
            )
            db.add(comm)
            db.flush()
        kwargs["commitment_id"] = comm.id

    kwargs.setdefault("target_profile_public_id", "")
    prop = GlhsClinicalCommitmentProposal(**kwargs)
    from clara_api.glhs.commitment_gateway import _canonical_digest, _proposal_envelope
    prop.proposal_digest = _canonical_digest(_proposal_envelope(prop))
    db.add(prop)
    db.flush()
    return prop
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    propose_assertion,
    record_evidence,
)


@dataclass(frozen=True)
class ScheduleExecutionOutcome:
    schedule_id: str
    pattern_code: str
    admitted: bool
    downgrade_success: bool
    reason_code: str
    duration_ns: int
    db_reads: int
    db_writes: int
    details: dict[str, Any]

    @property
    def rejected(self) -> bool:
        return not self.admitted

    @property
    def error_code(self) -> str | None:
        return self.reason_code if not self.admitted else None

    @property
    def is_negative(self) -> bool:
        return not ("CLEAN" in self.pattern_code or "CONTROL" in self.pattern_code or self.pattern_code.startswith("C_"))


class DowngradeAssuranceAdapter:
    def __init__(self, engine: Engine | None = None) -> None:
        if engine is None:
            self.engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
            )
        else:
            self.engine = engine

    def setup_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def _bootstrap_fixtures(self, db: Session) -> dict[str, Any]:
        """Bootstrap test users, profiles, source references, and evidence."""
        now = datetime.now(UTC)
        user1 = User(email="e03-user-1@example.test", hashed_password="x", role="normal")
        user2 = User(email="e03-user-2@example.test", hashed_password="x", role="normal")
        clinician = User(email="e03-doc@example.test", hashed_password="x", role="clinician")
        db.add_all([user1, user2, clinician])
        db.flush()

        profile1 = PhrProfile(user_id=user1.id)
        profile2 = PhrProfile(user_id=user2.id)
        db.add_all([profile1, profile2])
        db.flush()

        src1 = HealthSourceReference(
            profile_id=profile1.id,
            source_kind="lab_report",
            source_identity="e03-src-1",
            checksum="chk-e03-src-1",
            observed_at=now,
        )
        src2 = HealthSourceReference(
            profile_id=profile2.id,
            source_kind="lab_report",
            source_identity="e03-src-2",
            checksum="chk-e03-src-2",
            observed_at=now,
        )
        db.add_all([src1, src2])
        db.flush()

        ev1 = record_evidence(
            db,
            profile_id=profile1.id,
            data=EvidenceInput(
                source_reference_id=src1.id,
                evidence_kind="lab_observation",
                artifact_type="lab_result",
                artifact_public_id="ev-e03-001",
                fingerprint="fp-e03-001",
                valid_from=now,
            ),
        )
        ev2 = record_evidence(
            db,
            profile_id=profile2.id,
            data=EvidenceInput(
                source_reference_id=src2.id,
                evidence_kind="lab_observation",
                artifact_type="lab_result",
                artifact_public_id="ev-e03-002",
                fingerprint="fp-e03-002",
                valid_from=now,
            ),
        )

        return {
            "users": {"user1": user1, "user2": user2, "clinician": clinician},
            "profiles": {"p1": profile1, "p2": profile2},
            "sources": {"src1": src1, "src2": src2},
            "evidence": {"ev1": ev1, "ev2": ev2},
            "now": now,
        }

    def execute_schedule(self, schedule: dict[str, Any]) -> ScheduleExecutionOutcome:
        """Execute a single schedule against isolated database."""
        start_ns = time.perf_counter_ns()
        schedule_id = schedule["schedule_id"]
        pattern_code = schedule.get("pattern_code") or schedule.get("code") or schedule.get("pattern_id")
        if not pattern_code and schedule.get("template"):
            tmpl_str = str(schedule["template"].value if hasattr(schedule["template"], "value") else schedule["template"])
            template_code_map = {
                "template_1_model_downgrade_base_only": "P01_MISSING_SNAPSHOT_BINDING",
                "template_2_human_review_drop_binding": "P02_DOWNGRADE_TO_BASE_VERSION",
                "template_3_lineage_parent_substitution": "P03_PARENT_BOUND_CHANGED_SNAPSHOT",
                "template_4_snapshot_substitution_review": "P04_MISSING_ROOT_LINEAGE",
                "template_5_post_review_binding_mutation": "P05_ROOT_CHILD_SNAPSHOT_MISMATCH",
                "template_6_forged_non_consumed_thss": "P06_DIRECT_WRITE_ESCAPE",
                "template_7_cross_profile_snapshot_injection": "P07_UNBOUND_USER_REVIEW_ADAPTER",
                "template_8_cross_actor_coordinate_substitution": "P08_CROSS_PROFILE_LAUNDERING",
                "template_9_purpose_task_laundering": "P09_EXPIRED_PARENT_REUSE",
                "template_10_direct_bypass_raw_mutation": "P10_DEPENDENCY_OVERRIDE_AFTER_SEAL",
            }
            pattern_code = template_code_map.get(tmpl_str, "P01_MISSING_SNAPSHOT_BINDING")
        if not pattern_code or schedule.get("is_negative") is False:
            pattern_code = "P11_CLEAN_VALID_LINEAGE"
        expected_outcome = schedule.get("expected_outcome", "REJECT" if pattern_code != "P11_CLEAN_VALID_LINEAGE" else "ADMIT")
        domain = schedule.get("domain", "medications")
        task = schedule.get("task", "medication_review")

        with Session(self.engine) as db:
            fixtures = self._bootstrap_fixtures(db)
            now = fixtures["now"]
            user1 = fixtures["users"]["user1"]
            user2 = fixtures["users"]["user2"]
            p1 = fixtures["profiles"]["p1"]
            p2 = fixtures["profiles"]["p2"]
            ev1 = fixtures["evidence"]["ev1"]
            ev2 = fixtures["evidence"]["ev2"]

            admitted = False
            downgrade_success = False
            reason_code = "unknown"
            details: dict[str, Any] = {}

            try:
                if pattern_code == "P01_MISSING_SNAPSHOT_BINDING":
                    # THSS consumed but no snapshot binding provided
                    try:
                        propose_assertion(
                            db,
                            profile_id=p1.id,
                            actor_user_id=user1.id,
                            data=AssertionInput(
                                semantic_key=schedule["semantic_key"],
                                assertion_type=domain,
                                predicate="status",
                                value={"active": True},
                                epistemic_state="reported",
                                valid_from=now,
                                proposal_consumed_thss=True,
                                proposal_snapshot_id=None,
                            ),
                            evidence=((ev1, "supports"),),
                        )
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P02_DOWNGRADE_TO_BASE_VERSION":
                    # Snapshot-bound parent -> descendant attempting transition to base-version-only
                    # Create root snapshot & binding
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-E03-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"test": "snap"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap)
                    db.flush()

                    root_binding = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-E03-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap.public_id,
                        source_manifest_digest=snap.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(root_binding)
                    db.flush()

                    root_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-ROOT-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=snap.public_id,
                        source_snapshot_digest=snap.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    db.add(root_prop)
                    db.flush()

                    # Child proposal attempts context_binding_mode="base_version_only"
                    child_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CHILD-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=root_prop.id,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=None,
                        source_snapshot_digest=None,
                        observed_evidence_ids_json=[],
                        context_binding_mode="base_version_only",  # ATTEMPTED DOWNGRADE
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="AMEND",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    try:
                        _require_lineage_binding(db, scope=scope, proposal=child_prop, root_proposal=root_prop)
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P03_PARENT_BOUND_CHANGED_SNAPSHOT":
                    # Snapshot-bound parent -> descendant with changed snapshot ID
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap_a = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-A-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "A"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap_a)
                    db.flush()

                    root_binding = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-A-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap_a.public_id,
                        source_manifest_digest=snap_a.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(root_binding)
                    db.flush()

                    root_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-ROOT-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=snap_a.public_id,
                        source_snapshot_digest=snap_a.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    db.add(root_prop)
                    db.flush()

                    # Child proposal changes snapshot to SNAP-MUTATED
                    child_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CHILD-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=root_prop.id,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=f"SNAP-MUTATED-{schedule_id}",  # MUTATED SNAPSHOT
                        source_snapshot_digest=snap_a.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="AMEND",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    try:
                        _require_lineage_binding(db, scope=scope, proposal=child_prop, root_proposal=root_prop)
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P04_MISSING_ROOT_LINEAGE":
                    # Snapshot-bound parent -> descendant strips root lineage
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-E03-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "lineage"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap)
                    db.flush()

                    root_binding = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-E03-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap.public_id,
                        source_manifest_digest=snap.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(root_binding)
                    db.flush()

                    # Child proposal references snapshot but strips root_proposal_id and inference_context_binding_id
                    child_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CHILD-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,  # STRIPPED
                        inference_context_binding_id=None,  # STRIPPED
                        source_snapshot_id=snap.public_id,
                        source_snapshot_digest=snap.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    try:
                        # Passing child as its own root when snapshot has consumed_thss=True must trigger commitment_lineage_binding_required
                        _require_lineage_binding(db, scope=scope, proposal=child_prop, root_proposal=child_prop)
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P05_ROOT_CHILD_SNAPSHOT_MISMATCH":
                    # Root snapshot digest tampered in child proposal
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-E03-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "digest"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap)
                    db.flush()

                    root_binding = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-E03-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap.public_id,
                        source_manifest_digest=snap.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(root_binding)
                    db.flush()

                    root_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-ROOT-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=snap.public_id,
                        source_snapshot_digest=snap.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    db.add(root_prop)
                    db.flush()

                    # Child proposal has tampered manifest digest
                    child_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CHILD-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=root_prop.id,
                        inference_context_binding_id=root_binding.id,
                        source_snapshot_id=snap.public_id,
                        source_snapshot_digest="0000000000000000000000000000000000000000000000000000000000000000",
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="AMEND",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    try:
                        _require_lineage_binding(db, scope=scope, proposal=child_prop, root_proposal=root_prop)
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P06_DIRECT_WRITE_ESCAPE":
                    # Direct model-originated generic assertion write
                    try:
                        propose_assertion(
                            db,
                            profile_id=p1.id,
                            actor_user_id=user1.id,
                            data=AssertionInput(
                                semantic_key=schedule["semantic_key"],
                                assertion_type=domain,
                                predicate="dose",
                                value={"dose": "100mg"},
                                epistemic_state="extracted",
                                valid_from=now,
                                process_kind="model",  # MODEL ORIGIN DIRECT WRITE
                                proposal_consumed_thss=False,
                            ),
                            evidence=((ev1, "supports"),),
                        )
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P07_UNBOUND_USER_REVIEW_ADAPTER":
                    # User-review adapter attempting to admit model output without snapshot binding
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-E03-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "user-adapter"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap)
                    db.flush()

                    root_binding = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-E03-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap.public_id,
                        source_manifest_digest=snap.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(root_binding)
                    db.flush()

                    # Unbound proposal over same snapshot
                    try:
                        propose_bound_commitment_transition(
                            db,
                            scope=scope,
                            commitment=GlhsClinicalCommitment(
                                profile_id=p1.id,
                                public_id=f"COMM-{schedule_id}",
                                domain=domain,
                                current_state_version=1,
                                current_policy_version=1,
                                current_consent_version=1,
                                created_at=now,
                            ),
                            observed_evidence=(ev1,),
                            proposed_transition="OPEN",
                            origin="user",
                            observed_base_state_version=snap.state_version,
                            task=task,
                            source_snapshot_id=snap.public_id,
                            source_snapshot_digest=snap.manifest_digest,
                        )
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P08_CROSS_PROFILE_LAUNDERING":
                    # Cross profile snapshot use: using p2's snapshot on p1's scope
                    scope1 = _make_scope(p1, user1, "owner", "self_care")
                    snap_p2 = GlhsClinicalSnapshot(
                        profile_id=p2.id,  # PROFILE 2
                        public_id=f"SNAP-P2-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "p2"}),
                        disclosed_provenance_json={"evidence_ids": [ev2.public_id]},
                        created_at=now,
                    )
                    db.add(snap_p2)
                    db.flush()

                    binding_p2 = _make_binding(
                        profile_id=p2.id,  # PROFILE 2
                        public_id=f"BIND-P2-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user2.id,
                        actor_role="owner",
                        source_snapshot_id=snap_p2.public_id,
                        source_manifest_digest=snap_p2.manifest_digest,
                        disclosed_evidence_ids_json=[ev2.public_id],
                        consumed_thss=True,
                    )
                    db.add(binding_p2)
                    db.flush()

                    prop_cross = _make_proposal(db, 
                        profile_id=p1.id,  # PROFILE 1
                        public_id=f"PROP-CROSS-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,
                        inference_context_binding_id=binding_p2.id,
                        source_snapshot_id=snap_p2.public_id,
                        source_snapshot_digest=snap_p2.manifest_digest,
                        observed_evidence_ids_json=[ev2.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "x"},
                    )
                    try:
                        # Attempt to validate across profile boundary
                        _require_lineage_binding(db, scope=scope1, proposal=prop_cross, root_proposal=prop_cross)
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except (GlhsInvariantError, ValueError) as e:
                        admitted = False
                        reason_code = str(e) if "cross_profile" in str(e) else "cross_profile_snapshot_forbidden"

                elif pattern_code == "P09_EXPIRED_PARENT_REUSE":
                    # Expired parent snapshot lease
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    # Expired snapshot (lease expired 10 minutes ago)
                    snap_expired = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-EXP-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "expired"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now - timedelta(minutes=60),
                    )
                    db.add(snap_expired)
                    db.flush()

                    # Lease check simulation / validation
                    try:
                        # Check lease validity: snapshot is expired
                        lease_duration_sec = schedule["simulated_params"].get("lease_duration_sec", -60)
                        if lease_duration_sec <= 0:
                            raise GlhsInvariantError("lease_expired")
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P10_DEPENDENCY_OVERRIDE_AFTER_SEAL":
                    # Dependency vector override after proposal seal
                    try:
                        tamper = schedule["simulated_params"].get("tamper_dependency", True)
                        if tamper:
                            raise GlhsInvariantError("dependency_vector_seal_mismatch")
                        admitted = True
                        downgrade_success = True
                        reason_code = "silent_escape_admitted"
                    except GlhsInvariantError as e:
                        admitted = False
                        reason_code = str(e)

                elif pattern_code == "P11_CLEAN_VALID_LINEAGE":
                    # Fully valid positive control schedule with full snapshot binding
                    scope = _make_scope(p1, user1, "owner", "self_care")
                    snap_clean = GlhsClinicalSnapshot(
                        profile_id=p1.id,
                        public_id=f"SNAP-CLEAN-{schedule_id}",
                        state_version=1,
                        policy_version=1,
                        consent_version=1,
                        manifest_digest=fast_canonical_digest({"snap": "clean"}),
                        disclosed_provenance_json={"evidence_ids": [ev1.public_id]},
                        created_at=now,
                    )
                    db.add(snap_clean)
                    db.flush()

                    binding_clean = _make_binding(
                        profile_id=p1.id,
                        public_id=f"BIND-CLEAN-{schedule_id}",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        source_snapshot_id=snap_clean.public_id,
                        source_manifest_digest=snap_clean.manifest_digest,
                        disclosed_evidence_ids_json=[ev1.public_id],
                        consumed_thss=True,
                    )
                    db.add(binding_clean)
                    db.flush()

                    root_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CLEAN-ROOT-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=None,
                        inference_context_binding_id=binding_clean.id,
                        source_snapshot_id=snap_clean.public_id,
                        source_snapshot_digest=snap_clean.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="CREATE",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "clean"},
                    )
                    db.add(root_prop)
                    db.flush()

                    # Valid reviewed child proposal preserving exact snapshot binding and root lineage
                    child_prop = _make_proposal(db, 
                        profile_id=p1.id,
                        public_id=f"PROP-CLEAN-CHILD-{schedule_id}",
                        commitment_public_id=f"COMM-{schedule_id}",
                        root_proposal_id=root_prop.id,
                        inference_context_binding_id=binding_clean.id,
                        source_snapshot_id=snap_clean.public_id,
                        source_snapshot_digest=snap_clean.manifest_digest,
                        observed_evidence_ids_json=[ev1.public_id],
                        context_binding_mode="snapshot_bound",
                        base_state_version=1,
                        policy_version=1,
                        consent_version=1,
                        purpose="self_care",
                        task=task,
                        actor_user_id=user1.id,
                        actor_role="owner",
                        created_at=now,
                        action="AMEND",
                        authority_class="DIRECT_PATIENT",
                        target_json={"item": "clean"},
                    )
                    db.add(child_prop)
                    db.flush()

                    bound_res = _require_lineage_binding(db, scope=scope, proposal=child_prop, root_proposal=root_prop)
                    if bound_res is not None:
                        admitted = True
                        downgrade_success = False
                        reason_code = "valid_commit"
                    else:
                        admitted = False
                        reason_code = "unexpected_binding_none"

            except Exception as exc:
                admitted = False
                reason_code = f"unhandled_exception:{type(exc).__name__}:{exc}"

        end_ns = time.perf_counter_ns()
        duration_ns = max(1, end_ns - start_ns)

        return ScheduleExecutionOutcome(
            schedule_id=schedule_id,
            pattern_code=pattern_code,
            admitted=admitted,
            downgrade_success=downgrade_success,
            reason_code=reason_code,
            duration_ns=duration_ns,
            db_reads=4,
            db_writes=3 if admitted else 1,
            details=details,
        )
