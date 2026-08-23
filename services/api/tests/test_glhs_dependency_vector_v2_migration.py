"""Round-trip and schema contract tests for GLHS dependency vector v2 migration.

Verifies:
- Creation of `glhs_proposal_dependencies`, `glhs_applied_transitions`, `glhs_transition_partition_links`.
- Extension of `glhs_clinical_commitment_proposals` with v2 protocol columns.
- Immutability triggers on all new ledger tables (UPDATE and DELETE rejected).
- SQLAlchemy ORM model integration and immutability event listeners.
- Clean downgrade and re-upgrade idempotency.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker

from clara_api.db.models import (
    Base,
    GlhsAppliedTransition,
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsEntityVersionPartition,
    GlhsProposalDependency,
    GlhsTransitionPartitionLink,
    PhrProfile,
    User,
)

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

_PREREQUISITE_MIGRATIONS = (
    "20260808_0050_glhs_foundation.py",
    "20260810_0051_glhs_co_versioned_governance.py",
    "20260810_0052_glhs_snapshot_reconstruction.py",
    "20260810_0053_glhs_proposal_snapshot_link.py",
    "20260810_0054_commitloop_commitments.py",
    "20260811_0055_glhs_manifest_binding.py",
    "20260818_0056_governance_policy_epochs.py",
    "20260818_0057_commitment_effective_time.py",
    "20260819_0058_glhs_inference_context_binding.py",
    "20260820_0059_glhs_entity_partition.py",
)

_TARGET_MIGRATION = "20260823_0060_glhs_dependency_vector_v2.py"


def _load_migration(filename: str):
    path = _VERSIONS / filename
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    assert spec and spec.loader, f"Failed to load migration spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    """Create minimal pre-GLHS baseline tables required for foreign keys."""
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
    )
    sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    sa.Table(
        "health_source_references",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)


def test_dependency_vector_v2_migration_metadata() -> None:
    """Verify migration metadata: valid revision ID, down_revision, and entrypoints."""
    migration = _load_migration(_TARGET_MIGRATION)
    assert migration.revision == "20260823_0060"
    assert migration.down_revision == "20260820_0059"
    assert callable(getattr(migration, "upgrade", None))
    assert callable(getattr(migration, "downgrade", None))


def test_dependency_vector_v2_upgrade_downgrade_roundtrip(tmp_path: Path) -> None:
    """Verify end-to-end upgrade, schema verification, immutability, and downgrade."""
    db_path = tmp_path / "glhs-dep-vector-v2-roundtrip.db"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path}")

    try:
        _baseline(engine)

        prereq_migrations = [_load_migration(fn) for fn in _PREREQUISITE_MIGRATIONS]
        target_migration = _load_migration(_TARGET_MIGRATION)

        with engine.connect() as connection:
            # 1. Upgrade prerequisite chain
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                for prereq in prereq_migrations:
                    prereq.upgrade()
            connection.commit()

            # 2. Upgrade target v2 migration
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.upgrade()
            connection.commit()

            # 3. Verify table existence
            inspector = sa.inspect(connection)
            tables = set(inspector.get_table_names())
            assert "glhs_proposal_dependencies" in tables
            assert "glhs_applied_transitions" in tables
            assert "glhs_transition_partition_links" in tables

            # 4. Verify proposal v2 columns
            prop_cols = {col["name"] for col in inspector.get_columns("glhs_clinical_commitment_proposals")}
            assert {
                "protocol_version",
                "dependency_vector_digest",
                "disclosure_manifest_id",
                "canonicalization_profile",
                "inference_run_digest",
                "sealed_at",
            } <= prop_cols

            # 5. Verify dependency table columns
            dep_cols = {col["name"] for col in inspector.get_columns("glhs_proposal_dependencies")}
            assert {
                "id",
                "public_id",
                "proposal_id",
                "dependency_kind",
                "dependency_key",
                "access_mode",
                "observed_version",
                "observed_digest",
                "valid_from",
                "valid_to",
                "transaction_observed_at",
                "canonicalization_profile",
                "created_at",
            } <= dep_cols

            # 6. Verify applied transition table columns
            trans_cols = {col["name"] for col in inspector.get_columns("glhs_applied_transitions")}
            assert {
                "id",
                "public_id",
                "profile_id",
                "tenant_id",
                "proposal_id",
                "operation_kind",
                "idempotency_key",
                "transition_status",
                "request_digest",
                "result_digest",
                "dependency_vector_digest",
                "disclosure_digest",
                "audit_event_id",
                "committed_at",
                "recorded_at",
            } <= trans_cols

            # 7. Verify partition link table columns
            link_cols = {col["name"] for col in inspector.get_columns("glhs_transition_partition_links")}
            assert {
                "id",
                "public_id",
                "transition_id",
                "partition_id",
                "predecessor_version",
                "successor_version",
                "predecessor_digest",
                "successor_digest",
                "write_digest",
                "recorded_at",
            } <= link_cols

            # 8. Verify SQLite triggers exist
            triggers = {
                str(row[0])
                for row in connection.execute(
                    sa.text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
                )
            }
            assert "trg_glhs_proposal_dependencies_no_update" in triggers
            assert "trg_glhs_proposal_dependencies_no_delete" in triggers
            assert "trg_glhs_applied_transitions_no_update" in triggers
            assert "trg_glhs_applied_transitions_no_delete" in triggers
            assert "trg_glhs_transition_partition_links_no_update" in triggers
            assert "trg_glhs_transition_partition_links_no_delete" in triggers

            # 9. Verify immutability trigger blocks UPDATE on glhs_proposal_dependencies
            connection.execute(sa.text("INSERT INTO phr_profiles (id) VALUES (1)"))
            connection.execute(
                sa.text(
                    "INSERT INTO glhs_clinical_commitments (id, public_id, profile_id, semantic_key, domain, supersession_key) "
                    "VALUES (1, 'c1', 1, 'med:metformin', 'medications', 'med:metformin')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO glhs_clinical_commitment_proposals "
                    "(id, public_id, commitment_id, base_state_version, observed_evidence_ids_json, "
                    "proposed_transition, purpose, origin, protocol_version) "
                    "VALUES (1, 'p1', 1, 1, '[]', 'INITIATE', 'clinical_care', 'clinician', 'glhs.v2')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO glhs_proposal_dependencies "
                    "(id, public_id, proposal_id, dependency_kind, dependency_key, access_mode, observed_version) "
                    "VALUES (1, 'dep1', 1, 'GOVERNANCE', 'gov:policy:v1', 'READ', 1)"
                )
            )
            connection.commit()

            with pytest.raises((sa.exc.IntegrityError, sa.exc.DatabaseError), match="glhs_ledger_immutable"):
                connection.execute(
                    sa.text("UPDATE glhs_proposal_dependencies SET observed_version = 2 WHERE id = 1")
                )
            connection.rollback()

            with pytest.raises((sa.exc.IntegrityError, sa.exc.DatabaseError), match="glhs_ledger_immutable"):
                connection.execute(
                    sa.text("DELETE FROM glhs_proposal_dependencies WHERE id = 1")
                )
            connection.rollback()

            # 10. Test downgrade
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.downgrade()
            connection.commit()

            inspector_down = sa.inspect(connection)
            down_tables = set(inspector_down.get_table_names())
            assert "glhs_proposal_dependencies" not in down_tables
            assert "glhs_applied_transitions" not in down_tables
            assert "glhs_transition_partition_links" not in down_tables

            # 11. Re-upgrade idempotency
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.upgrade()
            connection.commit()

            re_tables = set(sa.inspect(connection).get_table_names())
            assert "glhs_proposal_dependencies" in re_tables
            assert "glhs_applied_transitions" in re_tables
            assert "glhs_transition_partition_links" in re_tables
    finally:
        engine.dispose()


def test_orm_models_and_immutability_listeners(tmp_path: Path) -> None:
    """Verify ORM models: creation, relationships, and Python-level immutability listeners."""
    db_path = tmp_path / "glhs-orm-test.db"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path}")

    try:
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)

        with session_factory() as session:
            # Seed profile and commitment
            user = User(email="doctor@example.com", hashed_password="pw")
            session.add(user)
            session.flush()

            profile = PhrProfile(user_id=user.id)
            session.add(profile)
            session.flush()

            commitment = GlhsClinicalCommitment(
                profile_id=profile.id,
                semantic_key="medication:metformin",
                domain="medications",
                supersession_key="medication:metformin",
            )
            session.add(commitment)
            session.flush()

            # Create partition
            partition = GlhsEntityVersionPartition(
                profile_id=profile.id,
                domain="medications",
                semantic_key="medication:metformin",
                state_version=1,
            )
            session.add(partition)
            session.flush()

            # Create proposal with v2 fields
            proposal = GlhsClinicalCommitmentProposal(
                commitment_id=commitment.id,
                base_state_version=1,
                observed_evidence_ids_json=[],
                proposed_transition="INITIATE",
                purpose="treatment",
                origin="clinician",
                protocol_version="glhs.v2",
                dependency_vector_digest="d" * 64,
                canonicalization_profile="glhs.canonical.v2",
                inference_run_digest="i" * 64,
                sealed_at=datetime.now(UTC),
            )
            session.add(proposal)
            session.flush()

            # Create proposal dependency
            dep = GlhsProposalDependency(
                proposal_id=proposal.id,
                dependency_kind="ENTITY",
                dependency_key="medications:metformin",
                access_mode="WRITE",
                observed_version=1,
                observed_digest="e" * 64,
            )
            session.add(dep)
            session.flush()

            # Create applied transition
            applied = GlhsAppliedTransition(
                profile_id=profile.id,
                proposal_id=proposal.id,
                operation_kind="COMMIT_PROPOSAL",
                idempotency_key=f"idemp_{uuid4().hex}",
                transition_status="COMMITTED",
                request_digest="r" * 64,
                result_digest="res" + "0" * 61,
                dependency_vector_digest="d" * 64,
                disclosure_digest="disc" + "0" * 60,
            )
            session.add(applied)
            session.flush()

            # Create partition link
            link = GlhsTransitionPartitionLink(
                transition_id=applied.id,
                partition_id=partition.id,
                predecessor_version=1,
                successor_version=2,
                predecessor_digest="p" * 64,
                successor_digest="s" * 64,
                write_digest="w" * 64,
            )
            session.add(link)
            session.commit()

            # Verify relationships navigation
            re_prop = session.get(GlhsClinicalCommitmentProposal, proposal.id)
            assert re_prop is not None
            assert len(re_prop.dependencies) == 1
            assert re_prop.dependencies[0].dependency_key == "medications:metformin"
            assert re_prop.applied_transition is not None
            assert re_prop.applied_transition.idempotency_key == applied.idempotency_key
            assert len(re_prop.applied_transition.partition_links) == 1
            assert re_prop.applied_transition.partition_links[0].successor_version == 2

            # Verify ORM immutability listener on GlhsProposalDependency
            with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
                dep.observed_version = 99
                session.commit()
            session.rollback()

            with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
                session.delete(dep)
                session.commit()
            session.rollback()

            # Verify ORM immutability listener on GlhsAppliedTransition
            with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
                applied.transition_status = "ABORTED"
                session.commit()
            session.rollback()

            # Verify ORM immutability listener on GlhsTransitionPartitionLink
            with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
                link.successor_version = 10
                session.commit()
            session.rollback()
    finally:
        engine.dispose()
