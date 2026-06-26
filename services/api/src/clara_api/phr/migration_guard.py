"""Startup/CI guard asserting ``phr_profiles`` is migration-managed (Req 1.2).

Historically ``phr_profiles`` was only ever created by SQLAlchemy
``Base.metadata.create_all`` — there was no Alembic migration that owned it. The
``20260416_0012_phr_enhanced`` migration now creates the table (when absent) and
adds the new structured columns/tables. This guard makes the contract explicit:

* In **production**, the database must already be migration-managed before the
  application starts. That means the Alembic version table exists and
  ``phr_profiles`` is already present (created by the migration, not by a
  runtime ``create_all`` fallback). If either is missing, the app fails fast at
  startup rather than silently letting ``create_all`` invent the schema.
* In non-production environments (dev/test), ``create_all`` remains the
  convenient bootstrap path, so the guard is a no-op there — preserving the
  current local/test behavior (Requirement 18.1).

The core check is a pure function over a set of table names so it can be
exercised directly by unit/CI tests without a live engine; a thin engine-backed
wrapper is what ``main.py`` calls at startup just before ``create_all``.
"""

from __future__ import annotations

from collections.abc import Iterable

# Table that this feature requires to be migration-managed in production.
PHR_PROFILES_TABLE = "phr_profiles"
# Alembic's bookkeeping table — its presence means migrations have been applied.
ALEMBIC_VERSION_TABLE = "alembic_version"
# Environment name that enforces the guard.
PRODUCTION_ENVIRONMENT = "production"


class PhrMigrationGuardError(RuntimeError):
    """Raised when ``phr_profiles`` is not migration-managed in production."""


def assert_phr_profiles_migration_managed(
    *,
    existing_tables: Iterable[str],
    environment: str,
    table_name: str = PHR_PROFILES_TABLE,
    alembic_version_table: str = ALEMBIC_VERSION_TABLE,
) -> None:
    """Assert production does not rely on ``create_all`` for ``phr_profiles``.

    This is meant to run **before** ``Base.metadata.create_all`` so the table
    set reflects the schema as produced by migrations alone.

    Args:
        existing_tables: Names of tables already present in the database (as
            reported by an Alembic/SQLAlchemy inspector before ``create_all``).
        environment: The runtime environment name (e.g. ``"production"``).
        table_name: The PHR table that must be migration-managed.
        alembic_version_table: The Alembic version-tracking table.

    Raises:
        PhrMigrationGuardError: In production, when migrations have not been
            applied (no Alembic version table) or ``phr_profiles`` is absent
            (so only a runtime ``create_all`` could create it).
    """

    if environment.strip().lower() != PRODUCTION_ENVIRONMENT:
        # Dev/test bootstrap via create_all stays untouched (Req 18.1).
        return

    tables = set(existing_tables)

    if alembic_version_table not in tables:
        raise PhrMigrationGuardError(
            "PHR schema is not migration-managed: the Alembic version table "
            f"'{alembic_version_table}' is missing in production. Run "
            "'alembic upgrade head' before starting the API so "
            f"'{table_name}' is created by a migration rather than create_all."
        )

    if table_name not in tables:
        raise PhrMigrationGuardError(
            f"PHR schema is not migration-managed: table '{table_name}' is "
            "absent in production before create_all. It must be created by the "
            "Alembic migration (20260416_0012_phr_enhanced), not by a runtime "
            "create_all fallback. Run 'alembic upgrade head' before startup."
        )


def assert_engine_phr_profiles_migration_managed(engine, *, environment: str) -> None:
    """Engine-backed wrapper used by API startup before ``create_all``.

    Inspects the live database for the current table set and delegates to
    :func:`assert_phr_profiles_migration_managed`.

    Args:
        engine: A SQLAlchemy engine/connectable bound to the application DB.
        environment: The runtime environment name.

    Raises:
        PhrMigrationGuardError: See :func:`assert_phr_profiles_migration_managed`.
    """

    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(engine)
    assert_phr_profiles_migration_managed(
        existing_tables=inspector.get_table_names(),
        environment=environment,
    )
