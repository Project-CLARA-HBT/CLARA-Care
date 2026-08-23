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
    GlhsProposalDependency,
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
from clara_api.glhs.lock_hierarchy import get_or_create_entity_partition


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
