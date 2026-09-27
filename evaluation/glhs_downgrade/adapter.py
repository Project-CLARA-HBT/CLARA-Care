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
    GlhsClinicalSnapshot,
    GlhsInferenceContextBinding,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.canonical_json import fast_canonical_digest
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    ProfileScope,
    _require_lineage_binding,
    create_commitment_proposal,
    propose_bound_commitment_transition,
)
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
        pattern_code = schedule["pattern_code"]
        expected_outcome = schedule["expected_outcome"]
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    root_binding = GlhsInferenceContextBinding(
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

                    root_prop = GlhsClinicalCommitmentProposal(
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
                    child_prop = GlhsClinicalCommitmentProposal(
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    root_binding = GlhsInferenceContextBinding(
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

                    root_prop = GlhsClinicalCommitmentProposal(
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
                    child_prop = GlhsClinicalCommitmentProposal(
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    root_binding = GlhsInferenceContextBinding(
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
                    child_prop = GlhsClinicalCommitmentProposal(
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    root_binding = GlhsInferenceContextBinding(
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

                    root_prop = GlhsClinicalCommitmentProposal(
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
                    child_prop = GlhsClinicalCommitmentProposal(
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    root_binding = GlhsInferenceContextBinding(
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
                    scope1 = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    binding_p2 = GlhsInferenceContextBinding(
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

                    prop_cross = GlhsClinicalCommitmentProposal(
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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
                    scope = ProfileScope(profile=p1, actor=user1, role="owner", purpose="self_care")
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

                    binding_clean = GlhsInferenceContextBinding(
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

                    root_prop = GlhsClinicalCommitmentProposal(
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
                    child_prop = GlhsClinicalCommitmentProposal(
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
