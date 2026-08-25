"""Unit and regression tests for GLHS Linearizable OCC Commit Kernel (commit_kernel.py).

Verifies the 6-phase atomic commit sequence:
    Phase 1: Fast idempotency pre-check with `GlhsAppliedTransition`.
    Phase 2: Canonical lock acquisition (SHARED anchors & lexicographical entity partition locks).
    Phase 3: Freshness & per-partition dependency revalidation under locks.
    Phase 4: Domain mutation callback execution with GlhsCommitContext.
    Phase 5: CAS-increment only WRITE partitions (successor_version = predecessor_version + 1),
             record `GlhsTransitionPartitionLink` rows.
    Phase 6: Insert `GlhsAppliedTransition` record and transactional outbox event.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAppliedTransition,
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsEntityVersionPartition,
    GlhsEvidence,
    GlhsProposalDependency,
    HealthSourceReference,
    LifeMapOutboxEvent,
    PhrProfile,
    User,
)
from clara_api.glhs.commit_kernel import (
    DependencySpec,
    GlhsCommitContext,
    compute_dependency_vector_digest,
    execute_atomic_glhs_commit,
    parse_entity_partition_key,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.lock_hierarchy import (
    LockClass,
    build_lock_plan,
    get_or_create_entity_partition,
)


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_profile(db: Session, email_prefix: str = "kernel_test") -> tuple[User, PhrProfile]:
    user = User(email=f"{email_prefix}_{uuid4().hex[:8]}@example.test", hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Kernel Test Subject")
    db.add(profile)
    db.flush()
    return user, profile


def _seed_proposal(
    db: Session,
    profile_id: int,
    domain: str = "medications",
    semantic_key: str = "metformin",
    dependency_vector_digest: str | None = None,
) -> tuple[GlhsClinicalCommitment, GlhsClinicalCommitmentProposal]:
    commitment = GlhsClinicalCommitment(
        profile_id=profile_id,
        domain=domain,
        semantic_key=semantic_key,
        supersession_key=f"{domain}:{semantic_key}",
    )
    db.add(commitment)
    db.flush()

    proposal = GlhsClinicalCommitmentProposal(
        commitment_id=commitment.id,
        base_state_version=1,
        observed_evidence_ids_json=[],
        proposed_transition="INITIATE",
        purpose="self_care",
        origin="clinician",
        protocol_version="glhs.v2",
        dependency_vector_digest=dependency_vector_digest,
    )
    db.add(proposal)
    db.flush()
    return commitment, proposal


def test_parse_entity_partition_key() -> None:
    assert parse_entity_partition_key("medications:metformin") == ("medications", "metformin")
    assert parse_entity_partition_key("metformin", default_domain="medications") == ("medications", "metformin")
    assert parse_entity_partition_key("allergies:penicillin", default_domain="general") == ("allergies", "penicillin")
    assert parse_entity_partition_key("vital_signs") == ("general", "vital_signs")


def test_compute_dependency_vector_digest_canonical_sort() -> None:
    dep1 = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="medications:metformin",
        access_mode="WRITE",
        observed_version=1,
    )
    dep2 = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="allergies:penicillin",
        access_mode="READ",
        observed_version=2,
    )
    dep3 = DependencySpec(
        dependency_kind="GOVERNANCE",
        dependency_key="policy_epoch:medications",
        access_mode="READ",
        observed_version=1,
    )

    # Order 1
    digest1 = compute_dependency_vector_digest([dep1, dep2, dep3])
    # Order 2 (reversed)
    digest2 = compute_dependency_vector_digest([dep3, dep2, dep1])

    assert len(digest1) == 64
    assert digest1 == digest2


def test_phase1_fast_idempotency_precheck(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    idempotency_key = f"idemp_{uuid4().hex}"
    req_digest = "req_" + "a" * 60

    callback_called = [False]

    def mutation(ctx: GlhsCommitContext) -> dict[str, str]:
        callback_called[0] = True
        return {"status": "ok"}

    # First execution - successfully commits
    result1 = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=idempotency_key,
        operation_kind="COMMIT_PROPOSAL",
        request_digest=req_digest,
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:metformin",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
        mutation_callback=mutation,
    )

    assert result1.idempotent_replay is False
    assert result1.transition_status == "COMMITTED"
    assert callback_called[0] is True
    assert len(result1.partition_links) == 1

    # Second execution with same idempotency key - fast pre-check hits
    callback_called[0] = False
    result2 = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=idempotency_key,
        operation_kind="COMMIT_PROPOSAL",
        request_digest=req_digest,
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:metformin",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
        mutation_callback=mutation,
    )

    assert result2.idempotent_replay is True
    assert result2.applied_transition.id == result1.applied_transition.id
    assert result2.transition_status == "COMMITTED"
    assert callback_called[0] is False  # Mutation callback was skipped


def test_phase1_idempotency_key_reused_with_mismatch(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    idempotency_key = f"idemp_{uuid4().hex}"

    execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=idempotency_key,
        operation_kind="COMMIT_PROPOSAL",
        request_digest="digest_original_" + "0" * 48,
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:metformin",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
    )

    # Attempt with same idempotency key but different request digest
    with pytest.raises(GlhsInvariantError, match="idempotency_key_reused"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=idempotency_key,
            operation_kind="COMMIT_PROPOSAL",
            request_digest="digest_DIFFERENT_" + "0" * 47,
        )


def test_phase3_stale_entity_partition_rejection(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    # Initialize partition at version 1
    part = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="metformin"
    )
    assert part.state_version == 1

    # Attempt commit with stale observed_version = 0 (or 5)
    with pytest.raises(GlhsInvariantError, match="stale_entity_partition"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            dependencies=[
                DependencySpec(
                    dependency_kind="ENTITY",
                    dependency_key="medications:metformin",
                    access_mode="WRITE",
                    observed_version=5,  # Stale! Current is 1
                )
            ],
        )


def test_phase3_stale_governance_policy_rejection(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    with pytest.raises(GlhsInvariantError, match="stale_governance_policy"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            dependencies=[
                DependencySpec(
                    dependency_kind="GOVERNANCE",
                    dependency_key="policy_epoch:medications",
                    access_mode="READ",
                    observed_version=1,
                    observed_digest="glhs.v999.nonexistent",  # Stale policy version!
                )
            ],
        )


def test_phase3_stale_expected_versions(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    with pytest.raises(GlhsInvariantError, match="stale_base_state_version"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            expected_base_state_version=999,
        )

    with pytest.raises(GlhsInvariantError, match="stale_policy_version"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            expected_policy_version="nonexistent.v99",
        )


def test_phase4_mutation_callback_and_context(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    context_captured: list[GlhsCommitContext] = []

    def mutation(ctx: GlhsCommitContext) -> dict[str, Any]:
        context_captured.append(ctx)
        return {"action": "activated", "patient": ctx.profile_id}

    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        operation_kind="COMMIT_PROPOSAL",
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:lisinopril",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
        mutation_callback=mutation,
        custom_payload={"source": "test"},
    )

    assert len(context_captured) == 1
    ctx = context_captured[0]
    assert ctx.profile_id == profile.id
    assert ctx.proposal_id == proposal.id
    assert ctx.custom_payload == {"source": "test"}
    assert ("medications", "lisinopril") in ctx.locked_partitions
    assert result.mutation_result == {"action": "activated", "patient": profile.id}


def test_phase5_cas_increment_only_write_partitions(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    # Create two partitions: one READ, one WRITE
    read_part = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="conditions", semantic_key="hypertension"
    )
    write_part = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="amlodipine"
    )

    assert read_part.state_version == 1
    assert write_part.state_version == 1

    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="conditions:hypertension",
                access_mode="READ",
                observed_version=1,
            ),
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:amlodipine",
                access_mode="WRITE",
                observed_version=1,
            ),
        ],
    )

    # Re-fetch partitions from DB
    db.refresh(read_part)
    db.refresh(write_part)

    # READ partition must NOT increment
    assert read_part.state_version == 1
    # WRITE partition MUST increment from 1 to 2
    assert write_part.state_version == 2

    # Partition link recorded only for the WRITE partition
    assert len(result.partition_links) == 1
    link = result.partition_links[0]
    assert link.partition_id == write_part.id
    assert link.predecessor_version == 1
    assert link.successor_version == 2
    assert link.successor_version == link.predecessor_version + 1


def test_phase6_applied_transition_and_outbox_event(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    idempotency_key = f"idemp_{uuid4().hex}"

    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=idempotency_key,
        operation_kind="COMMIT_PROPOSAL",
        request_digest="req_digest_123",
        disclosure_digest="disc_digest_456",
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:atorvastatin",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
        aggregate_type="glhs_clinical_commitment",
        event_type="glhs.commitment.transition.applied",
    )

    # Verify GlhsAppliedTransition row in database
    applied = db.get(GlhsAppliedTransition, result.applied_transition.id)
    assert applied is not None
    assert applied.profile_id == profile.id
    assert applied.proposal_id == proposal.id
    assert applied.idempotency_key == idempotency_key
    assert applied.transition_status == "COMMITTED"
    assert applied.request_digest == "req_digest_123"
    assert applied.disclosure_digest == "disc_digest_456"
    assert len(applied.dependency_vector_digest) == 64

    # Verify LifeMapOutboxEvent row in database
    outbox_events = list(
        db.execute(
            select(LifeMapOutboxEvent).where(
                LifeMapOutboxEvent.profile_id == profile.id,
                LifeMapOutboxEvent.event_type == "glhs.commitment.transition.applied",
            )
        ).scalars()
    )
    assert len(outbox_events) == 1
    outbox = outbox_events[0]
    assert outbox.aggregate_type == "glhs_clinical_commitment"
    assert outbox.aggregate_id == applied.public_id
    assert outbox.payload_json["event_type"] == "glhs.commitment.transition.applied"


def _seed_evidence(
    db: Session,
    profile_id: int,
    fingerprint: str = "fp_abc123",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> GlhsEvidence:
    src = HealthSourceReference(profile_id=profile_id, source_kind="visit")
    db.add(src)
    db.flush()
    now = datetime.now(UTC)
    ev = GlhsEvidence(
        profile_id=profile_id,
        source_reference_id=src.id,
        evidence_kind="lab",
        fingerprint=fingerprint,
        valid_from=valid_from or (now - timedelta(days=1)),
        valid_to=valid_to or (now + timedelta(days=30)),
    )
    db.add(ev)
    db.flush()
    return ev


def test_load_dependencies_from_proposal_in_db(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    # Insert proposal dependencies directly into DB
    dep1 = GlhsProposalDependency(
        proposal_id=proposal.id,
        dependency_kind="ENTITY",
        dependency_key="medications:losartan",
        access_mode="WRITE",
        observed_version=1,
    )
    dep2 = GlhsProposalDependency(
        proposal_id=proposal.id,
        dependency_kind="GOVERNANCE",
        dependency_key="policy_epoch:medications",
        access_mode="READ",
        observed_version=1,
    )
    db.add_all([dep1, dep2])
    db.flush()

    # Call execute_atomic_glhs_commit without explicit dependencies parameter
    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        proposal_id=proposal.id,
        idempotency_key=f"idemp_{uuid4().hex}",
    )

    assert result.transition_status == "COMMITTED"
    assert len(result.partition_links) == 1
    assert result.partition_links[0].successor_version == 2


def test_sealed_proposal_disallows_caller_dependencies_override(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    dep1 = GlhsProposalDependency(
        proposal_id=proposal.id,
        dependency_kind="ENTITY",
        dependency_key="medications:losartan",
        access_mode="WRITE",
        observed_version=1,
    )
    db.add(dep1)
    db.flush()

    # Supplying dependencies when proposal_id is provided must raise GlhsInvariantError
    with pytest.raises(
        GlhsInvariantError, match="sealed_proposal_dependencies_override_forbidden"
    ):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            dependencies=[
                DependencySpec(
                    dependency_kind="ENTITY",
                    dependency_key="medications:losartan",
                    access_mode="WRITE",
                    observed_version=1,
                )
            ],
        )


def test_sealed_proposal_disallows_caller_write_partitions_override(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(db, profile.id)

    dep1 = GlhsProposalDependency(
        proposal_id=proposal.id,
        dependency_kind="ENTITY",
        dependency_key="medications:losartan",
        access_mode="WRITE",
        observed_version=1,
    )
    db.add(dep1)
    db.flush()

    # Supplying write_partitions when proposal_id is provided must raise GlhsInvariantError
    with pytest.raises(
        GlhsInvariantError, match="sealed_proposal_write_partitions_override_forbidden"
    ):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            write_partitions=[("medications", "losartan")],
        )


def test_sealed_proposal_dependency_vector_digest_mismatch_fails(db: Session) -> None:
    _, profile = _seed_profile(db)
    _, proposal = _seed_proposal(
        db,
        profile.id,
        dependency_vector_digest="sha256_wrong_digest_" + "0" * 44,
    )

    dep1 = GlhsProposalDependency(
        proposal_id=proposal.id,
        dependency_kind="ENTITY",
        dependency_key="medications:losartan",
        access_mode="WRITE",
        observed_version=1,
    )
    db.add(dep1)
    db.flush()

    with pytest.raises(
        GlhsInvariantError, match="proposal_dependency_vector_digest_mismatch"
    ):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            proposal_id=proposal.id,
            idempotency_key=f"idemp_{uuid4().hex}",
        )


def test_phase3_evidence_dependency_validation(db: Session) -> None:
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, fingerprint="fp_valid_999")

    # 1. Valid evidence commit succeeds
    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        operation_kind="APPLY_TRANSITION",
        dependencies=[
            DependencySpec(
                dependency_kind="EVIDENCE",
                dependency_key=f"evidence:{ev.public_id}",
                access_mode="READ",
                observed_version=1,
                observed_digest=ev.fingerprint,
                valid_from=ev.valid_from,
                valid_to=ev.valid_to,
            )
        ],
    )
    assert result.transition_status == "COMMITTED"

    # 2. Missing evidence row
    with pytest.raises(GlhsInvariantError, match="missing_evidence"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="EVIDENCE",
                    dependency_key="evidence:nonexistent-public-id",
                    access_mode="READ",
                )
            ],
        )

    # 3. Fingerprint mismatch
    with pytest.raises(GlhsInvariantError, match="stale_evidence_fingerprint"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="EVIDENCE",
                    dependency_key=f"evidence:{ev.public_id}",
                    access_mode="READ",
                    observed_digest="fp_wrong_tampered_fingerprint",
                )
            ],
        )

    # 4. Expired evidence
    ev_expired = _seed_evidence(
        db,
        profile.id,
        fingerprint="fp_expired",
        valid_to=datetime.now(UTC) - timedelta(days=1),
    )

    with pytest.raises(GlhsInvariantError, match="evidence_expired"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="EVIDENCE",
                    dependency_key=f"evidence:{ev_expired.public_id}",
                    access_mode="READ",
                    observed_digest=ev_expired.fingerprint,
                )
            ],
        )


def test_phase3_lease_dependency_validation(db: Session) -> None:
    _, profile = _seed_profile(db)

    # Expired lease dependency
    with pytest.raises(GlhsInvariantError, match="lease_expired"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="LEASE",
                    dependency_key="lease:agent_reasoning_123",
                    access_mode="READ",
                    valid_to=datetime.now(UTC) - timedelta(seconds=10),
                )
            ],
        )

    # Not-yet-valid lease dependency
    with pytest.raises(GlhsInvariantError, match="lease_not_yet_valid"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="LEASE",
                    dependency_key="lease:agent_future_123",
                    access_mode="READ",
                    valid_from=datetime.now(UTC) + timedelta(minutes=10),
                )
            ],
        )

    # Wounded lease fails closed under INV-001
    from clara_api.glhs.commitment_gateway import get_dag_lock_manager, reset_dag_lock_manager
    reset_dag_lock_manager()
    lock_mgr = get_dag_lock_manager()
    txn = lock_mgr.begin_transaction(profile_id=profile.id, txn_id="wounded_lease_test")
    txn.mark_wounded("preempted_by_higher_priority")

    with pytest.raises(GlhsInvariantError, match="lease_invalid_or_wounded"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="LEASE",
                    dependency_key="lease:wounded_lease_test",
                    access_mode="READ",
                )
            ],
        )


def test_disjoint_partition_writes_no_global_version_conflict(db: Session) -> None:
    """Disjoint partition writes must NEVER fail due to global base_state_version."""
    _, profile = _seed_profile(db)

    # Partition 1: medications:rx1
    result1 = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        operation_kind="APPLY_TRANSITION",
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="medications:rx1",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
    )
    assert result1.transition_status == "COMMITTED"

    # Partition 2: allergies:penicillin (disjoint from medications:rx1)
    # Even after partition 1 incremented, partition 2 is at version 1 and commits cleanly
    result2 = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        operation_kind="APPLY_TRANSITION",
        dependencies=[
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="allergies:penicillin",
                access_mode="WRITE",
                observed_version=1,
            )
        ],
    )
    assert result2.transition_status == "COMMITTED"


def test_phase5_database_cas_version_conflict(db: Session) -> None:
    _, profile = _seed_profile(db)

    # Seed partition at version 1
    part = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="metformin"
    )
    assert part.state_version == 1

    # Simulate a concurrent writer that increments the partition row behind the scenes during callback
    def malicious_mutation(ctx: GlhsCommitContext) -> None:
        # Directly modify database partition version behind the kernel's back
        db.execute(
            GlhsEntityVersionPartition.__table__.update()
            .where(GlhsEntityVersionPartition.id == part.id)
            .values(state_version=99)
        )
        db.flush()

    with pytest.raises(GlhsInvariantError, match="cas_version_conflict"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="APPLY_TRANSITION",
            dependencies=[
                DependencySpec(
                    dependency_kind="ENTITY",
                    dependency_key="medications:metformin",
                    access_mode="WRITE",
                    observed_version=1,
                )
            ],
            mutation_callback=malicious_mutation,
        )


def test_7_class_canonical_lock_plan_integration() -> None:
    deps = [
        DependencySpec(dependency_kind="LEASE", dependency_key="lease_01"),
        DependencySpec(dependency_kind="EVIDENCE", dependency_key="evidence:ev_01"),
        DependencySpec(dependency_kind="ENTITY", dependency_key="medications:warfarin", access_mode="WRITE"),
        DependencySpec(dependency_kind="GOVERNANCE", dependency_key="policy:medications"),
    ]
    lock_items = [
        ("tenant_global_policy", "policy_epoch:__global__", "SHARED"),
        ("domain_policy", "policy_epoch:medications", "SHARED"),
        ("subject_consent", "user_consent:10", "SHARED"),
        ("idempotency_key", "idempotency:default:test:key1", "EXCLUSIVE"),
    ]
    for d in deps:
        if d.dependency_kind == "ENTITY":
            lock_items.append(("entity_partition", d.dependency_key, d.access_mode))
        elif d.dependency_kind == "EVIDENCE":
            lock_items.append(("evidence", d.dependency_key, d.access_mode))
        elif d.dependency_kind == "LEASE":
            lock_items.append(("lease", d.dependency_key, d.access_mode))
        elif d.dependency_kind == "GOVERNANCE":
            lock_items.append(("domain_policy", d.dependency_key, d.access_mode))

    plan = build_lock_plan(lock_items)
    classes = [item.lock_class for item in plan]
    # Verify strict ascending LockClass order 1 through 7
    assert classes == sorted(classes)
    assert classes[0] == LockClass.TENANT_GLOBAL_POLICY
    assert classes[-1] == LockClass.IDEMPOTENCY_KEY
