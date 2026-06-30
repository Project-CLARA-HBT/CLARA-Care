"""Unit tests for the PHR migration-management guard (Requirement 1.2).

These lock the guard that asserts ``phr_profiles`` is created by an Alembic
migration in production rather than relying on the runtime ``create_all``
fallback. Outside production the guard is a no-op so the dev/test bootstrap via
``create_all`` keeps working unchanged (Requirement 18.1).
"""

from __future__ import annotations

import pytest

from clara_api.phr.migration_guard import (
    ALEMBIC_VERSION_TABLE,
    PHR_PROFILES_TABLE,
    PhrMigrationGuardError,
    assert_phr_profiles_migration_managed,
)

_MIGRATED_TABLES = {ALEMBIC_VERSION_TABLE, PHR_PROFILES_TABLE, "users"}


def test_production_passes_when_migration_managed() -> None:
    # Alembic version table + phr_profiles already present ⇒ migration-managed.
    assert_phr_profiles_migration_managed(
        existing_tables=_MIGRATED_TABLES,
        environment="production",
    )


def test_production_rejects_missing_alembic_version_table() -> None:
    # No alembic_version ⇒ migrations never ran; create_all would be the source.
    with pytest.raises(PhrMigrationGuardError):
        assert_phr_profiles_migration_managed(
            existing_tables={PHR_PROFILES_TABLE, "users"},
            environment="production",
        )


def test_production_rejects_missing_phr_profiles_table() -> None:
    # Migrations ran but phr_profiles absent ⇒ would be created by create_all.
    with pytest.raises(PhrMigrationGuardError):
        assert_phr_profiles_migration_managed(
            existing_tables={ALEMBIC_VERSION_TABLE, "users"},
            environment="production",
        )


@pytest.mark.parametrize("environment", ["development", "test", "staging", "local"])
def test_non_production_is_noop(environment: str) -> None:
    # Outside production the guard never raises, even on an empty database.
    assert_phr_profiles_migration_managed(
        existing_tables=set(),
        environment=environment,
    )


@pytest.mark.parametrize("environment", ["Production", "PRODUCTION", " production "])
def test_production_detection_is_case_and_whitespace_insensitive(environment: str) -> None:
    # Any casing/whitespace variant of "production" still enforces the guard.
    with pytest.raises(PhrMigrationGuardError):
        assert_phr_profiles_migration_managed(
            existing_tables=set(),
            environment=environment,
        )
