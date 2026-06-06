"""Regression tests for the persistent-store startup self-check (task 1.11).

Validates Requirement 3.4:

    IF a persistent-path flag is enabled WHILE the ``vector`` extension or
    ``kb_*`` tables are absent, THEN THE Knowledge_Pipeline SHALL force the
    legacy in-memory path and log a descriptive error rather than failing the
    request.

These tests exercise the *real* self-check API in
``clara_ml.rag.store.health`` together with its integration point in
``clara_ml.rag.pipeline`` (``RagPipelineP1._persistent_retrieval_active``).
No real Postgres is required: the "infrastructure missing" condition is
simulated either with ``engine=None`` (no DB at all) or with a throwaway
in-memory SQLite engine (a DB that exists but has neither the pgvector
``vector`` extension nor any ``kb_*`` table).

The core guarantee under test: with ``RAG_PERSISTENT_RETRIEVAL_ENABLED`` true
but the persistent infrastructure absent, the self-check resolves
``forced_legacy=True``, ``persistent_retrieval_enabled=False``, and the request
path (``_persistent_retrieval_active``) returns ``False`` and never crashes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

# Import the store package first to avoid the documented circular-import quirk
# (pipeline.py relies on the same ordering).
import clara_ml.rag.store  # noqa: F401
from clara_ml.rag.store import health
from clara_ml.rag.store.health import (
    PersistentStoreStatus,
    check_persistent_store_ready,
    get_resolved_persistent_flags,
    resolve_effective_persistent_flags,
    run_startup_self_check,
    set_resolved_persistent_flags,
)
from clara_ml.rag.pipeline import RagPipelineP1


def _settings(*, store: bool = False, retrieval: bool = False, database_url: str = ""):
    """Build a minimal settings stand-in the health helpers can read via getattr."""

    return SimpleNamespace(
        rag_persistent_store_enabled=store,
        rag_persistent_retrieval_enabled=retrieval,
        database_url=database_url,
    )


def _pipeline_instance() -> RagPipelineP1:
    """A bare ``RagPipelineP1`` whose ``_persistent_retrieval_active`` we test.

    ``_persistent_retrieval_active`` reads no instance state (only the resolved
    self-check flags and module settings), so we bypass the heavy constructor.
    """

    return RagPipelineP1.__new__(RagPipelineP1)


@pytest.fixture(autouse=True)
def _restore_resolved_flags():
    """Snapshot/restore the module-level resolved-flags holder around each test."""

    previous = get_resolved_persistent_flags()
    try:
        yield
    finally:
        if previous is None:
            # Reset back to ``None`` when nothing was set before this test ran.
            health._RESOLVED_FLAGS = None
        else:
            set_resolved_persistent_flags(previous)


# ---------------------------------------------------------------------------
# Readiness self-check: infrastructure absent -> not ready
# ---------------------------------------------------------------------------


def test_check_ready_returns_not_ready_when_no_engine():
    """No database engine at all -> store reported as not ready (never raises)."""

    status = check_persistent_store_ready(None)

    assert status.ready is False
    assert status.missing  # describes what is missing
    assert "vector" in status.missing
    assert status.reason


def test_check_ready_not_ready_when_extension_and_tables_absent():
    """A live DB without the vector extension or kb_* tables is not ready."""

    engine = create_engine("sqlite://")  # in-memory, empty schema
    try:
        status = check_persistent_store_ready(engine)
    finally:
        engine.dispose()

    assert status.ready is False
    # Missing extension is reported, plus the kb_* tables that don't exist.
    assert "extension:vector" in status.missing
    assert any(name.startswith("kb_") for name in status.missing)


# ---------------------------------------------------------------------------
# Effective-flag resolution: not-ready + flag on -> forced legacy
# ---------------------------------------------------------------------------


def test_resolve_forces_legacy_when_retrieval_flag_on_but_not_ready():
    """Requirement 3.4: persistent retrieval requested + infra missing -> legacy."""

    not_ready = PersistentStoreStatus(
        ready=False, missing=["extension:vector"], reason="missing infra"
    )

    resolved = resolve_effective_persistent_flags(
        _settings(retrieval=True), not_ready
    )

    assert resolved.forced_legacy is True
    assert resolved.persistent_retrieval_enabled is False
    assert resolved.persistent_store_enabled is False


def test_resolve_honors_flags_when_store_ready():
    """Sanity: when the store IS ready the configured flags are honored as-is."""

    ready = PersistentStoreStatus(ready=True, missing=[], reason="ready")

    resolved = resolve_effective_persistent_flags(
        _settings(store=True, retrieval=True), ready
    )

    assert resolved.forced_legacy is False
    assert resolved.persistent_retrieval_enabled is True
    assert resolved.persistent_store_enabled is True


def test_resolve_no_force_when_no_flag_requested_and_not_ready():
    """Not ready but nothing requested -> legacy path with forced_legacy False."""

    not_ready = PersistentStoreStatus(ready=False, missing=["kb_chunks"], reason="x")

    resolved = resolve_effective_persistent_flags(_settings(), not_ready)

    assert resolved.persistent_retrieval_enabled is False
    assert resolved.forced_legacy is False


# ---------------------------------------------------------------------------
# End-to-end: self-check + pipeline routing
# ---------------------------------------------------------------------------


def test_run_startup_self_check_forces_legacy_and_pipeline_uses_legacy():
    """Flag ON + missing infra: self-check forces legacy and pipeline routes legacy."""

    engine = create_engine("sqlite://")  # DB exists, no vector ext / kb_* tables
    try:
        resolved = run_startup_self_check(
            _settings(retrieval=True, store=True), engine=engine
        )
    finally:
        engine.dispose()

    # Self-check resolved forced_legacy.
    assert resolved.forced_legacy is True
    assert resolved.persistent_retrieval_enabled is False

    # Stashed for the pipeline to consult.
    stashed = get_resolved_persistent_flags()
    assert stashed is not None
    assert stashed.forced_legacy is True

    # The request path consults the resolved flags and uses the legacy retriever.
    pipe = _pipeline_instance()
    assert pipe._persistent_retrieval_active() is False


def test_run_startup_self_check_with_no_engine_forces_legacy():
    """No DB engine available at all also forces the legacy path (no crash)."""

    resolved = run_startup_self_check(_settings(retrieval=True), engine=None)

    assert resolved.forced_legacy is True
    assert resolved.persistent_retrieval_enabled is False
    assert get_resolved_persistent_flags().forced_legacy is True

    pipe = _pipeline_instance()
    assert pipe._persistent_retrieval_active() is False


def test_pipeline_persistent_active_false_on_forced_legacy_resolution():
    """``_persistent_retrieval_active`` honors a stashed forced-legacy outcome."""

    set_resolved_persistent_flags(
        health.EffectivePersistentFlags(
            persistent_store_enabled=False,
            persistent_retrieval_enabled=False,
            forced_legacy=True,
            reason="forced legacy for test",
            status=None,
        )
    )

    pipe = _pipeline_instance()
    assert pipe._persistent_retrieval_active() is False


def test_self_check_never_raises_on_missing_infra():
    """The self-check must never raise on the request/startup path (Req 3.4)."""

    engine = create_engine("sqlite://")
    try:
        # None of these should raise even though the infra is absent.
        status = check_persistent_store_ready(engine)
        resolve_effective_persistent_flags(_settings(retrieval=True), status)
        run_startup_self_check(_settings(retrieval=True), engine=engine)
    finally:
        engine.dispose()
