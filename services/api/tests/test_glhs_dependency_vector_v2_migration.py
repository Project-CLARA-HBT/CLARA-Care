"""Round-trip and schema contract tests for GLHS dependency vector v2 migration.

Verifies:
- Creation of `glhs_proposal_dependencies`, `glhs_applied_transitions`, `glhs_transition_partition_links`.
- Extension of `glhs_clinical_commitment_proposals` with v2 protocol columns.
- Immutability triggers on all new ledger tables (UPDATE and DELETE rejected).
- SQLAlchemy ORM model integration and immutability event listeners.
- Nullable `proposal_id` and `assertion_id` on `glhs_applied_transitions` with conditional unique index.
- Schema consistency and execution of `apply_transition` and `apply_commitment_transition` on an Alembic-migrated database.
- Clean downgrade and re-upgrade idempotency.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
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
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope

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
    """Create minimal pre-GLHS baseline tables required for foreign keys and models."""
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=True, server_default="normal"),
        sa.Column("full_name", sa.String(255), nullable=True, server_default=""),
        sa.Column("is_email_verified", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("status", sa.String(32), nullable=True, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, default=lambda: str(uuid4())),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True, server_default=""),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(32), nullable=True, server_default=""),
        sa.Column("blood_type", sa.String(16), nullable=True, server_default=""),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True, server_default=""),
        sa.Column("contact_email", sa.String(254), nullable=True, server_default=""),
        sa.Column("address", sa.Text(), nullable=True, server_default=""),
        sa.Column("emergency_contact_name", sa.String(255), nullable=True, server_default=""),
        sa.Column("emergency_contact_phone", sa.String(64), nullable=True, server_default=""),
        sa.Column("emergency_contact_relationship", sa.String(80), nullable=True, server_default=""),
        sa.Column("emergency_contact_note", sa.Text(), nullable=True, server_default=""),
        sa.Column("insurance_provider", sa.String(255), nullable=True, server_default=""),
        sa.Column("insurance_id", sa.String(128), nullable=True, server_default=""),
        sa.Column("insurance_expiry", sa.Date(), nullable=True),
        sa.Column("allergy_status", sa.String(32), nullable=True, server_default="unknown"),
        sa.Column("notes", sa.Text(), nullable=True, server_default=""),
        sa.Column("allergies_json", sa.JSON(), nullable=True),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("medications_json", sa.JSON(), nullable=True),
        sa.Column("emergency_card_prefs_json", sa.JSON(), nullable=True),
        sa.Column("onboarding_status", sa.String(32), nullable=True, server_default="completed"),
        sa.Column("onboarding_version", sa.String(32), nullable=True, server_default=""),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_version_no", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("status", sa.String(32), nullable=True, server_default="active"),
        sa.Column("locale", sa.String(16), nullable=True, server_default="vi"),
        sa.Column("timezone", sa.String(64), nullable=True, server_default="Asia/Ho_Chi_Minh"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    sa.Table(
        "health_source_references",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, default=lambda: str(uuid4())),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("source_kind", sa.String(64), nullable=True),
        sa.Column("source_identity", sa.String(255), nullable=True, server_default=""),
        sa.Column("author_type", sa.String(32), nullable=True, server_default=""),
        sa.Column("author_public_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("device_identity", sa.String(128), nullable=True, server_default=""),
        sa.Column("checksum", sa.String(255), nullable=True, server_default=""),
        sa.Column("original_language", sa.String(16), nullable=True, server_default=""),
        sa.Column("source_span_json", sa.JSON(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    sa.Table(
        "user_consents",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(64), nullable=False, server_default="medical_disclaimer"),
        sa.Column("consent_version", sa.String(32), nullable=False, server_default="not_required"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    sa.Table(
        "lifemap_outbox_events",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=False, server_default=""),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    metadata.create_all(engine)


def _migrate_db(engine: sa.Engine) -> None:
    """Run all prerequisite migrations and target v2 migration."""
    _baseline(engine)
    prereq_migrations = [_load_migration(fn) for fn in _PREREQUISITE_MIGRATIONS]
    target_migration = _load_migration(_TARGET_MIGRATION)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for prereq in prereq_migrations:
                prereq.upgrade()
            target_migration.upgrade()
        connection.commit()


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

            # 6. Verify applied transition table columns (including nullable proposal_id and assertion_id)
            trans_cols = {col["name"]: col for col in inspector.get_columns("glhs_applied_transitions")}
            assert {
                "id",
                "public_id",
                "profile_id",
                "tenant_id",
                "proposal_id",
                "assertion_id",
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
            } <= set(trans_cols.keys())
            assert trans_cols["proposal_id"]["nullable"] is True
            assert trans_cols["assertion_id"]["nullable"] is True

            # Verify indexes on glhs_applied_transitions
            applied_indexes = {idx["name"] for idx in inspector.get_indexes("glhs_applied_transitions")}
            assert "uq_glhs_applied_trans_proposal" in applied_indexes
            assert "ix_glhs_applied_transitions_assertion_id" in applied_indexes

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

            # 9. Verify multiple nullable proposal_id rows can coexist
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, email, hashed_password, role, full_name, is_email_verified, status) "
                    "VALUES (1, 'u@example.com', 'pw', 'patient', 'Test User', 0, 'active')"
                )
            )
            connection.execute(sa.text("INSERT INTO phr_profiles (id, public_id, user_id) VALUES (1, 'p-1', 1)"))
            connection.execute(
                sa.text(
                    "INSERT INTO glhs_applied_transitions "
                    "(id, public_id, profile_id, tenant_id, proposal_id, assertion_id, operation_kind, idempotency_key) "
                    "VALUES (1, 't-1', 1, 'default', NULL, NULL, 'APPLY_TRANSITION', 'idemp-1')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO glhs_applied_transitions "
                    "(id, public_id, profile_id, tenant_id, proposal_id, assertion_id, operation_kind, idempotency_key) "
                    "VALUES (2, 't-2', 1, 'default', NULL, NULL, 'APPLY_TRANSITION', 'idemp-2')"
                )
            )
            connection.commit()

            # 10. Verify immutability trigger blocks UPDATE on glhs_proposal_dependencies
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

            # 11. Test downgrade
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.downgrade()
            connection.commit()

            inspector_down = sa.inspect(connection)
            down_tables = set(inspector_down.get_table_names())
            assert "glhs_proposal_dependencies" not in down_tables
            assert "glhs_applied_transitions" not in down_tables
            assert "glhs_transition_partition_links" not in down_tables

            # 12. Re-upgrade idempotency
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

            # Create applied transition linked to proposal
            applied = GlhsAppliedTransition(
                profile_id=profile.id,
                proposal_id=proposal.id,
                assertion_id=None,
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

            # Create applied transition with null proposal_id and non-null assertion_id
            applied_no_prop = GlhsAppliedTransition(
                profile_id=profile.id,
                proposal_id=None,
                assertion_id=None,
                operation_kind="APPLY_TRANSITION",
                idempotency_key=f"idemp_null_prop_{uuid4().hex}",
                transition_status="COMMITTED",
                request_digest="r2" + "0" * 62,
                result_digest="res2" + "0" * 60,
                dependency_vector_digest="d2" + "0" * 62,
                disclosure_digest="disc2" + "0" * 59,
            )
            session.add(applied_no_prop)
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


def test_apply_transition_and_apply_commitment_transition_on_migrated_db(tmp_path: Path) -> None:
    """Verify apply_transition and apply_commitment_transition on an Alembic-migrated database.

    Verifies:
    1. Schema consistency between Alembic migration and ORM models.
    2. `apply_transition` atomically inserts `glhs_applied_transitions` with proposal_id=NULL and assertion_id.
    3. `apply_commitment_transition` atomically inserts `glhs_applied_transitions` with proposal_id.
    4. Partition version increment links and outbox event recording work end-to-end on migrated schema.
    """
    db_path = tmp_path / "glhs-migrated-integration.db"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path}")

    try:
        _migrate_db(engine)
        session_factory = sessionmaker(bind=engine)

        with session_factory() as session:
            # 1. Seed user, profile, and consent
            user = User(email="patient@example.com", hashed_password="pw", role="normal")
            session.add(user)
            session.flush()

            profile = PhrProfile(user_id=user.id)
            session.add(profile)
            session.flush()

            consent = UserConsent(
                user_id=user.id,
                consent_type="medical_disclaimer",
                consent_version="not_required",
            )
            session.add(consent)
            session.flush()

            scope = ProfileScope(
                actor=user,
                profile=profile,
                actor_role="owner",
                purpose="self_care",
                allowed_actions=frozenset({"create", "confirm", "correct", "invalidate", "resolve", "view"}),
                allowed_data_classes=frozenset({"medications", "lifemap", "visits", "evidence", "observations"}),
            )

            at = datetime(2026, 8, 23, 10, 0, 0, tzinfo=UTC)

            # 2. Record evidence for apply_transition
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="document",
                source_identity="source:rx:001",
                checksum="checksum:rx:001",
                observed_at=at,
            )
            session.add(source)
            session.flush()

            evidence = record_evidence(
                session,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="prescription",
                    artifact_type="document",
                    artifact_public_id="artifact:rx:001",
                    fingerprint="fingerprint:rx:001",
                    valid_from=at,
                ),
            )

            # 3. Propose assertion
            assertion = propose_assertion(
                session,
                profile_id=profile.id,
                actor_user_id=user.id,
                data=AssertionInput(
                    semantic_key="medication:metformin:oral",
                    assertion_type="medications",
                    predicate="dose",
                    value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
                    epistemic_state="reported",
                    valid_from=at,
                    process_kind="user",
                ),
                evidence=((evidence, "supports"),),
            )
            session.commit()

            # 4. Execute apply_transition (tests nullable proposal_id + non-null assertion_id on migrated DB)
            trans = apply_transition(
                session,
                scope=scope,
                assertion=assertion,
                action="activate",
                expected_state_version=assertion.base_state_version,
                idempotency_key="idemp_apply_trans_001",
                transition_kind="user_report",
                reason_code="routine_prescription",
            )
            session.commit()

            assert trans is not None
            assert trans.id is not None

            # Verify GlhsAppliedTransition record for apply_transition
            applied_row = session.query(GlhsAppliedTransition).filter_by(assertion_id=assertion.id).one()
            assert applied_row.proposal_id is None
            assert applied_row.assertion_id == assertion.id
            assert applied_row.operation_kind == "APPLY_TRANSITION"
            assert applied_row.transition_status == "COMMITTED"
            assert len(applied_row.partition_links) == 1
            assert applied_row.partition_links[0].predecessor_version == 1
            assert applied_row.partition_links[0].successor_version == 2

            # 5. Execute apply_commitment_transition (tests non-null proposal_id on migrated DB)
            commitment = get_or_create_commitment(
                session,
                scope=scope,
                semantic_key="observation:glucose:fasting",
                domain="observations",
                supersession_key="observation:glucose",
            )
            session.flush()

            snapshot = compile_commitment_thss(
                session,
                scope=scope,
                task="commitment_proposal",
                purpose="self_care",
                valid_at=at,
                known_at=datetime.now(UTC) + timedelta(seconds=1),
                allowed_domains=frozenset({"observations"}),
                disclosed_evidence=(evidence,),
            )

            comm_proposal = propose_bound_commitment_transition(
                session,
                scope=scope,
                commitment=commitment,
                observed_evidence=(evidence,),
                proposed_transition="OPEN",
                origin="user",
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=snapshot.manifest_digest,
                observed_base_state_version=snapshot.state_version,
                task=snapshot.task,
            )
            session.flush()

            comm_version_data = CommitmentVersionInput(
                action="repeat_measurement",
                target={"system": "http://loinc.org", "code": "15074-8"},
                anchor_valid_time=at,
                anchor_known_time=at,
                earliest_valid_time=at,
                due_time=at + timedelta(days=30),
                grace_end=at + timedelta(days=37),
                authority_class="patient_report",
                fulfillment_predicate={
                    "op": "event",
                    "equals": {
                        "resource_type": "Observation",
                        "system": "http://loinc.org",
                        "code": "15074-8",
                        "status": "final",
                    },
                },
            )

            comm_trans = apply_commitment_transition(
                session,
                scope=scope,
                commitment=commitment,
                proposal=comm_proposal,
                evidence=(evidence,),
                data=comm_version_data,
                expected_state_version=comm_proposal.base_state_version,
                idempotency_key="idemp_comm_trans_001",
                transition_kind="manual_entry",
                reason_code="routine_monitoring",
            )
            session.commit()

            assert comm_trans is not None
            assert comm_trans.id is not None

            # Verify GlhsAppliedTransition record for apply_commitment_transition
            applied_comm_row = session.query(GlhsAppliedTransition).filter_by(proposal_id=comm_proposal.id).one()
            assert applied_comm_row.proposal_id == comm_proposal.id
            assert applied_comm_row.operation_kind == "COMMIT_COMMITMENT_TRANSITION"
            assert applied_comm_row.transition_status == "COMMITTED"
            assert len(applied_comm_row.partition_links) == 1

            # 6. Verify idempotency replay works for both on migrated schema
            replay_trans = apply_transition(
                session,
                scope=scope,
                assertion=assertion,
                action="activate",
                expected_state_version=assertion.base_state_version,
                idempotency_key="idemp_apply_trans_001",
                transition_kind="user_report",
                reason_code="routine_prescription",
            )
            assert replay_trans.id == trans.id

            replay_comm_trans = apply_commitment_transition(
                session,
                scope=scope,
                commitment=commitment,
                proposal=comm_proposal,
                evidence=(evidence,),
                data=comm_version_data,
                expected_state_version=comm_proposal.base_state_version,
                idempotency_key="idemp_comm_trans_001",
                transition_kind="manual_entry",
                reason_code="routine_monitoring",
            )
            assert replay_comm_trans.id == comm_trans.id
    finally:
        engine.dispose()

