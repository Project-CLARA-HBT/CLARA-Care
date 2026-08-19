"""Tests for the governance policy epoch migration, model and gateway read.

Covers GC-006 migration (additive ``governance_policy_epochs`` table), the ORM
model parity with the migration, ``read_current_policy_epoch`` semantics with
fake rows, and the isolated-attestation epoch precedence in
``_effective_policy_version`` while the default strict path stays unchanged.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import clara_api.glhs.gateway as gateway_module
from clara_api.db.base import Base
from clara_api.db.models import GovernancePolicyEpoch

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260818_0056_governance_policy_epochs.py"
)


def _migration() -> object:
    spec = importlib.util.spec_from_file_location("migration_20260818_0056", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _epoch(
    *,
    policy_domain: str,
    version: str,
    active_from: datetime,
    canonical_digest: str = "d" * 64,
) -> GovernancePolicyEpoch:
    return GovernancePolicyEpoch(
        policy_domain=policy_domain,
        version=version,
        active_from=active_from,
        canonical_digest=canonical_digest,
    )


# --- GC-006 migration ---------------------------------------------------------

def test_migration_creates_governance_policy_epochs_table() -> None:
    engine = create_engine("sqlite://")
    migration = _migration()
    assert migration.revision == "20260818_0056"
    assert migration.down_revision == "20260811_0055"
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        connection.commit()

    inspector = inspect(engine)
    assert "governance_policy_epochs" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("governance_policy_epochs")}
    assert columns == {
        "id",
        "policy_domain",
        "version",
        "active_from",
        "canonical_digest",
        "created_at",
    }
    indexes = {index["name"] for index in inspector.get_indexes("governance_policy_epochs")}
    assert "ix_governance_policy_epochs_policy_domain" in indexes
    assert "ix_governance_policy_epochs_version" in indexes
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("governance_policy_epochs")
    }
    assert "uq_governance_policy_epochs_domain_version" in constraints
    engine.dispose()


def test_migration_downgrade_drops_only_the_epoch_table() -> None:
    engine = create_engine("sqlite://")
    migration = _migration()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        connection.commit()
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.downgrade()
        connection.commit()
    assert "governance_policy_epochs" not in inspect(engine).get_table_names()
    engine.dispose()


def test_orm_model_matches_migration_schema() -> None:
    """The ORM model and the migration declare the same columns/constraints."""
    engine = create_engine("sqlite://")
    migration = _migration()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        connection.commit()
    model_table = Base.metadata.tables["governance_policy_epochs"]
    model_columns = {column.name for column in model_table.columns}
    model_constraints = {
        constraint.name
        for constraint in model_table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    inspector = inspect(engine)
    migration_columns = {
        column["name"] for column in inspector.get_columns("governance_policy_epochs")
    }
    migration_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("governance_policy_epochs")
    }
    assert model_columns == migration_columns
    assert "uq_governance_policy_epochs_domain_version" in model_constraints
    assert model_constraints == migration_constraints
    engine.dispose()


def test_model_enforces_unique_policy_domain_version(db: Session) -> None:
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-v2",
            active_from=datetime.now(UTC),
        )
    )
    db.flush()
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-v2",
            active_from=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# --- read_current_policy_epoch ------------------------------------------------

def test_epoch_lookup_returns_none_without_rows(db: Session) -> None:
    assert gateway_module.read_current_policy_epoch(db) is None


def test_epoch_lookup_returns_highest_version_active_epoch(db: Session) -> None:
    now = datetime.now(UTC)
    db.add_all(
        [
            _epoch(
                policy_domain="medications",
                version="policy-v1",
                active_from=now - timedelta(days=1),
            ),
            _epoch(
                policy_domain="medications",
                version="policy-v2",
                active_from=now - timedelta(minutes=5),
            ),
        ]
    )
    db.commit()
    epoch = gateway_module.read_current_policy_epoch(db)
    assert epoch is not None
    assert epoch.version == "policy-v2"


def test_epoch_lookup_excludes_future_epochs(db: Session) -> None:
    now = datetime.now(UTC)
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-future",
            active_from=now + timedelta(hours=1),
        )
    )
    db.commit()
    assert gateway_module.read_current_policy_epoch(db) is None


def test_epoch_lookup_filters_by_policy_domain(db: Session) -> None:
    now = datetime.now(UTC)
    db.add_all(
        [
            _epoch(
                policy_domain="medications",
                version="policy-v2",
                active_from=now - timedelta(minutes=5),
            ),
            _epoch(
                policy_domain="lab_results",
                version="policy-v9",
                active_from=now - timedelta(minutes=5),
            ),
        ]
    )
    db.commit()
    epoch = gateway_module.read_current_policy_epoch(db, policy_domain="medications")
    assert epoch is not None
    assert epoch.version == "policy-v2"
    # Without a domain the highest active version across domains wins.
    global_epoch = gateway_module.read_current_policy_epoch(db)
    assert global_epoch is not None
    assert global_epoch.version == "policy-v9"


def test_epoch_lookup_prefers_highest_version_over_newest_row(db: Session) -> None:
    now = datetime.now(UTC)
    db.add_all(
        [
            _epoch(
                policy_domain="medications",
                version="policy-v3",
                active_from=now - timedelta(minutes=10),
            ),
            _epoch(
                policy_domain="medications",
                version="policy-v2",
                active_from=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()
    epoch = gateway_module.read_current_policy_epoch(db)
    assert epoch is not None
    assert epoch.version == "policy-v3"


# --- _effective_policy_version precedence --------------------------------------

def test_default_strict_path_ignores_epoch_rows(db: Session) -> None:
    """Without isolated attestation the persisted epoch must never be read:
    production default behavior is unchanged even when rows exist."""
    now = datetime.now(UTC)
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-v2",
            active_from=now - timedelta(minutes=5),
        )
    )
    db.commit()
    assert gateway_module._effective_policy_version(db) == "glhs.v1"
    assert gateway_module._effective_policy_version() == "glhs.v1"


def test_isolated_attestation_prefers_persisted_epoch_over_env_override(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-v2",
            active_from=now - timedelta(minutes=5),
        )
    )
    db.commit()
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "env-override-v1")
    monkeypatch.setenv("ENV", "development")
    assert gateway_module._effective_policy_version(db) == "policy-v2"


def test_isolated_attestation_falls_back_to_env_override_without_epoch(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "env-override-v1")
    monkeypatch.setenv("ENV", "development")
    assert gateway_module._effective_policy_version(db) == "env-override-v1"


def test_isolated_attestation_without_epoch_or_override_keeps_constant(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.delenv("GOVRED_RESEARCH_POLICY_VERSION", raising=False)
    monkeypatch.setenv("ENV", "development")
    assert gateway_module._effective_policy_version(db) == "glhs.v1"


def test_future_persisted_epoch_is_not_active_under_attestation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.add(
        _epoch(
            policy_domain="medications",
            version="policy-v2",
            active_from=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "env-override-v1")
    monkeypatch.setenv("ENV", "development")
    assert gateway_module._effective_policy_version(db) == "env-override-v1"
