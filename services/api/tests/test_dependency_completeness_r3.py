"""Unit and integration tests for GLHS R3 Phase 3 Schema-Derived Dependency Completeness.

Covers:
1. Automatic derivation across all 8 operation families.
2. Hard rejection of entity omissions (M1).
3. Clean admission of conservative supersets (M2).
4. Hard rejection of access mode, version, and key corruptions (M3, M4, M5).
5. Prevention of classical multi-entity write skew (M6).
6. Hard rejection of evidence and governance omissions (M8, M9).
7. Real database session execution of 6-phase OCC commits.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsAppliedTransition,
    GlhsEntityVersionPartition,
    GlhsEvidence,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.glhs.commit_kernel import (
    DependencySpec,
    GlhsCommitContext,
    execute_atomic_glhs_commit,
)
from clara_api.glhs.dependency_contract import (
    CONTRACT_VERSION,
    DependencyGenerationInput,
    GeneratedDependencyVector,
    generate_dependency_vector,
    lookup_operation_rule,
    validate_proposed_dependencies,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.lock_hierarchy import get_or_create_entity_partition


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
        session.rollback()


def _seed_profile(db: Session) -> tuple[User, PhrProfile]:
    user = User(
        email=f"user_{uuid4().hex[:8]}@example.com",
        hashed_password="test_hash_123",
        role="normal",
    )
    db.add(user)
    db.flush()

    profile = PhrProfile(
        user_id=user.id,
        full_name="Test Patient",
    )
    db.add(profile)
    db.flush()
    return user, profile


def _seed_evidence(
    db: Session,
    profile_id: int,
    public_id: str | None = None,
    fingerprint: str = "fp_evidence_default_123",
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
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=365),
    )
    if public_id is not None:
        ev.public_id = public_id
    db.add(ev)
    db.flush()
    return ev


# ---------------------------------------------------------------------------
# 1. Automatic Derivation Across All 8 Operation Families
# ---------------------------------------------------------------------------

OPERATION_FAMILIES = [
    "COMMIT_PROPOSAL",
    "ACTIVATE_ASSERTION",
    "SUPERSEDE_ASSERTION",
    "RESOLVE_CONFLICT",
    "RECONCILE_MEDICATION",
    "IMPORT_FHIR_BUNDLE",
    "RECORD_OBSERVATION",
    "CONSENT_TRANSITION",
]


@pytest.mark.parametrize("op_kind", OPERATION_FAMILIES)
def test_automatic_derivation_across_all_8_operation_families(op_kind: str) -> None:
    """Verify deterministic derivation across all 8 primary operation families."""
    rule = lookup_operation_rule(op_kind)
    assert rule.operation_kind == op_kind

    semantic_keys = ("metformin",) if rule.min_entity_count > 0 else ()
    evidence_ids = ("ev-100",) if rule.requires_evidence else ()

    inp = DependencyGenerationInput(
        operation_kind=op_kind,
        domain="medications" if op_kind != "CONSENT_TRANSITION" else "consent",
        semantic_keys=semantic_keys,
        policy_version="glhs.v1",
        consent_version="disclaimer.v3",
        evidence_ids=evidence_ids,
        observed_entity_versions={"medications:metformin": 1},
    )

    vec = generate_dependency_vector(inp)

    assert vec.contract_version == CONTRACT_VERSION
    assert vec.generation_rule == op_kind
    assert isinstance(vec.dependencies, tuple)

    kinds = [d.dependency_kind for d in vec.dependencies]
    if rule.requires_governance:
        assert "GOVERNANCE" in kinds
    if rule.requires_consent:
        assert any(d.dependency_kind == "GOVERNANCE" and "consent" in d.dependency_key for d in vec.dependencies)
    if rule.requires_evidence:
        assert "EVIDENCE" in kinds
        ev_dep = next(d for d in vec.dependencies if d.dependency_kind == "EVIDENCE")
        assert ev_dep.dependency_key == "evidence:ev-100"

    if rule.min_entity_count > 0:
        ent_deps = [d for d in vec.dependencies if d.dependency_kind == "ENTITY"]
        assert len(ent_deps) >= rule.min_entity_count
        assert ent_deps[0].access_mode == rule.entity_access_mode


# ---------------------------------------------------------------------------
# 2. Hard Rejection of Entity Omissions (M1)
# ---------------------------------------------------------------------------

def test_hard_rejection_entity_omission_m1(db: Session) -> None:
    """Verify missing required entity dependency raises GlhsInvariantError('dependency_contract_omission')."""
    _, profile = _seed_profile(db)
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        policy_version="glhs.v1",
        consent_version="disclaimer.v3",
        evidence_ids=("ev-1",),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Omit the ENTITY dependency from proposed set
    incomplete_proposed = [d for d in minimum.dependencies if d.dependency_kind != "ENTITY"]

    # 1. Direct validation check
    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        validate_proposed_dependencies(minimum, incomplete_proposed, operation_kind="COMMIT_PROPOSAL")

    # 2. Real DB kernel session execution check
    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=incomplete_proposed,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 3. Clean Admission of Conservative Supersets (M2)
# ---------------------------------------------------------------------------

def test_clean_admission_conservative_superset_m2(db: Session) -> None:
    """Verify conservative supersets are admitted cleanly without false-stale aborts."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-superset-1")

    part1 = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")
    part2 = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="lisinopril")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        policy_version="glhs.v1",
        consent_version="not_required",
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part1.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Add extra entity READ dependency (conservative superset)
    extra_dep = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key=f"medications:{part2.semantic_key}",
        access_mode="READ",
        observed_version=part2.state_version,
    )
    superset = list(minimum.dependencies) + [extra_dep]

    validated = validate_proposed_dependencies(minimum, superset, operation_kind="COMMIT_PROPOSAL")
    assert validated.is_superset is True
    assert len(validated.superset_extra_keys) == 1
    assert "ENTITY:medications:lisinopril:READ" in validated.superset_extra_keys

    # Execute inside real DB session under PostgreSQL locks
    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=f"idemp_{uuid4().hex}",
        operation_kind="COMMIT_PROPOSAL",
        policy_domain="medications",
        dependencies=superset,
        required_dependencies=minimum,
    )

    assert result.transition_status == "COMMITTED"
    assert result.idempotent_replay is False

    # Verify write partition metformin incremented, read partition lisinopril remained unchanged
    db.refresh(part1)
    db.refresh(part2)
    assert part1.state_version == 2
    assert part2.state_version == 1


# ---------------------------------------------------------------------------
# 4. Hard Rejection of Access Mode Corruption (M3)
# ---------------------------------------------------------------------------

def test_hard_rejection_access_mode_corruption_m3(db: Session) -> None:
    """Verify access mode downgrade (WRITE -> READ) is rejected."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-m3-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Corrupt access mode from WRITE to READ
    corrupted_deps = [
        DependencySpec(
            dependency_kind=d.dependency_kind,
            dependency_key=d.dependency_key,
            access_mode="READ" if d.dependency_kind == "ENTITY" else d.access_mode,
            observed_version=d.observed_version,
            observed_digest=d.observed_digest,
        )
        for d in minimum.dependencies
    ]

    with pytest.raises(GlhsInvariantError, match="access_mode_mismatch|dependency_contract_omission"):
        validate_proposed_dependencies(minimum, corrupted_deps, operation_kind="COMMIT_PROPOSAL")

    with pytest.raises(GlhsInvariantError, match="access_mode_mismatch|dependency_contract_omission"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=corrupted_deps,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 5. Hard Rejection of Version Corruption (M4)
# ---------------------------------------------------------------------------

def test_hard_rejection_version_corruption_m4(db: Session) -> None:
    """Verify proposed observed version mismatch raises GlhsInvariantError."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-m4-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Corrupt entity observed_version from 1 to 99
    corrupted_deps = [
        DependencySpec(
            dependency_kind=d.dependency_kind,
            dependency_key=d.dependency_key,
            access_mode=d.access_mode,
            observed_version=99 if d.dependency_kind == "ENTITY" else d.observed_version,
            observed_digest=d.observed_digest,
        )
        for d in minimum.dependencies
    ]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_version_mismatch"):
        validate_proposed_dependencies(minimum, corrupted_deps, operation_kind="COMMIT_PROPOSAL")

    with pytest.raises(GlhsInvariantError, match="dependency_contract_version_mismatch"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=corrupted_deps,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 6. Hard Rejection of Key Corruption (M5)
# ---------------------------------------------------------------------------

def test_hard_rejection_key_corruption_m5(db: Session) -> None:
    """Verify tampered dependency key raises GlhsInvariantError('dependency_contract_omission')."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-m5-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Tamper entity key name
    corrupted_deps = [
        DependencySpec(
            dependency_kind=d.dependency_kind,
            dependency_key="medications:metformin_tampered" if d.dependency_kind == "ENTITY" else d.dependency_key,
            access_mode=d.access_mode,
            observed_version=d.observed_version,
            observed_digest=d.observed_digest,
        )
        for d in minimum.dependencies
    ]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        validate_proposed_dependencies(minimum, corrupted_deps, operation_kind="COMMIT_PROPOSAL")

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=corrupted_deps,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 7. Prevention of Classical Multi-Entity Write Skew (M6)
# ---------------------------------------------------------------------------

def test_prevention_of_classical_multi_entity_write_skew_m6(db: Session) -> None:
    """Verify multi-entity read/write dependency contracts prevent write skew in real database sessions.

    Scenario:
        Entity 1 (rx1) and Entity 2 (rx2) are both at version 1.
        Op A: reads rx1 (v1), writes rx2 (v1 -> v2).
        Op B: reads rx2 (v1), writes rx1 (v1 -> v2).

    If Op A commits first, rx2 transitions to version 2.
    When Op B attempts to commit observing rx2 at version 1, Phase 3 under locks detects
    stale partition version for rx2 (expected 1, got 2) and raises GlhsInvariantError.
    """
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-skew-1")

    rx1 = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="rx1")
    rx2 = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="rx2")
    assert rx1.state_version == 1
    assert rx2.state_version == 1

    # Op A: minimum contract requires reading rx1 (v1) and writing rx2 (v1)
    deps_op_a = [
        DependencySpec(dependency_kind="GOVERNANCE", dependency_key="policy_epoch:medications", access_mode="READ"),
        DependencySpec(dependency_kind="GOVERNANCE", dependency_key="consent:v1", access_mode="READ"),
        DependencySpec(dependency_kind="EVIDENCE", dependency_key=f"evidence:{ev.public_id}", access_mode="READ"),
        DependencySpec(dependency_kind="ENTITY", dependency_key="medications:rx1", access_mode="READ", observed_version=1),
        DependencySpec(dependency_kind="ENTITY", dependency_key="medications:rx2", access_mode="WRITE", observed_version=1),
    ]

    # Op B: minimum contract requires reading rx2 (v1) and writing rx1 (v1)
    deps_op_b = [
        DependencySpec(dependency_kind="GOVERNANCE", dependency_key="policy_epoch:medications", access_mode="READ"),
        DependencySpec(dependency_kind="GOVERNANCE", dependency_key="consent:v1", access_mode="READ"),
        DependencySpec(dependency_kind="EVIDENCE", dependency_key=f"evidence:{ev.public_id}", access_mode="READ"),
        DependencySpec(dependency_kind="ENTITY", dependency_key="medications:rx2", access_mode="READ", observed_version=1),
        DependencySpec(dependency_kind="ENTITY", dependency_key="medications:rx1", access_mode="WRITE", observed_version=1),
    ]

    # Execute Op A -> succeeds and increments rx2 to version 2
    res_a = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=f"idemp_op_a_{uuid4().hex}",
        operation_kind="COMMIT_PROPOSAL",
        policy_domain="medications",
        dependencies=deps_op_a,
    )
    assert res_a.transition_status == "COMMITTED"

    db.refresh(rx1)
    db.refresh(rx2)
    assert rx1.state_version == 1
    assert rx2.state_version == 2

    # Execute Op B -> fails in Phase 3 because rx2 was modified to version 2
    with pytest.raises(GlhsInvariantError, match="stale_entity_partition"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_op_b_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            policy_domain="medications",
            dependencies=deps_op_b,
        )


# ---------------------------------------------------------------------------
# 8. Hard Rejection of Evidence Omissions (M8)
# ---------------------------------------------------------------------------

def test_hard_rejection_evidence_omission_m8(db: Session) -> None:
    """Verify omission of mandatory evidence raises GlhsInvariantError."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-m8-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Omit evidence dependency
    omitted_deps = [d for d in minimum.dependencies if d.dependency_kind != "EVIDENCE"]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        validate_proposed_dependencies(minimum, omitted_deps, operation_kind="COMMIT_PROPOSAL")

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=omitted_deps,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 9. Hard Rejection of Governance Omissions (M9)
# ---------------------------------------------------------------------------

def test_hard_rejection_governance_omission_m9(db: Session) -> None:
    """Verify omission of policy epoch or consent governance raises GlhsInvariantError."""
    _, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-m9-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    # Omit governance dependency
    omitted_deps = [d for d in minimum.dependencies if d.dependency_kind != "GOVERNANCE"]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        validate_proposed_dependencies(minimum, omitted_deps, operation_kind="COMMIT_PROPOSAL")

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        execute_atomic_glhs_commit(
            db,
            profile_id=profile.id,
            idempotency_key=f"idemp_{uuid4().hex}",
            operation_kind="COMMIT_PROPOSAL",
            dependencies=omitted_deps,
            required_dependencies=minimum,
        )


# ---------------------------------------------------------------------------
# 10. Execution Inside Real Database Sessions
# ---------------------------------------------------------------------------

def test_full_real_database_session_atomic_commit_flow(db: Session) -> None:
    """Verify full end-to-end OCC atomic commit execution with real database session."""
    user, profile = _seed_profile(db)
    ev = _seed_evidence(db, profile.id, public_id="ev-db-flow-1")
    part = get_or_create_entity_partition(db, profile_id=profile.id, domain="medications", semantic_key="metformin")

    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        policy_version="glhs.v1",
        consent_version="not_required",
        evidence_ids=(ev.public_id,),
        observed_entity_versions={"medications:metformin": part.state_version},
    )
    minimum = generate_dependency_vector(inp)

    idemp_key = f"idemp_full_db_{uuid4().hex}"
    callback_ran = False

    def mutation_callback(ctx: GlhsCommitContext) -> dict[str, str]:
        nonlocal callback_ran
        callback_ran = True
        return {"status": "success", "mutated_key": "medications:metformin"}

    # Execute commit inside real DB session
    result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=idemp_key,
        operation_kind="COMMIT_PROPOSAL",
        policy_domain="medications",
        dependencies=list(minimum.dependencies),
        required_dependencies=minimum,
        mutation_callback=mutation_callback,
    )

    assert result.transition_status == "COMMITTED"
    assert result.idempotent_replay is False
    assert result.mutation_result == {"status": "success", "mutated_key": "medications:metformin"}
    assert callback_ran is True

    # Verify GlhsAppliedTransition record persisted
    applied = db.get(GlhsAppliedTransition, result.applied_transition.id)
    assert applied is not None
    assert applied.profile_id == profile.id
    assert applied.operation_kind == "COMMIT_PROPOSAL"
    assert applied.idempotency_key == idemp_key

    # Re-executing with identical idempotency key returns idempotent replay
    callback_ran = False
    replay_result = execute_atomic_glhs_commit(
        db,
        profile_id=profile.id,
        idempotency_key=idemp_key,
        operation_kind="COMMIT_PROPOSAL",
        policy_domain="medications",
        dependencies=list(minimum.dependencies),
        required_dependencies=minimum,
        mutation_callback=mutation_callback,
    )

    assert replay_result.idempotent_replay is True
    assert replay_result.applied_transition.id == applied.id
    assert callback_ran is False  # Mutation callback skipped on replay
