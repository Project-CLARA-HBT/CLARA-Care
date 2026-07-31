"""Tests for the watermark-driven backfill harness (rag-knowledge-pipeline).

Feature: rag-knowledge-pipeline, task 1.12 (+ source-registry wiring, tasks
3.1/3.21). These lock the additive contract:

- ``run_backfill`` is a strict no-op unless both ``RAG_INGESTION_ENABLED`` and
  the independent high-impact ``RAG_BACKFILL_ENABLED`` gate are true.
- When enabled, ``source_keys=None`` resolves "all enabled sources" from the
  injected Source_Registry reader; an explicit list is normalized (blanks
  dropped, duplicates removed, order preserved).
- The ``since`` override is passed through to the orchestrator per source.
- Without an injected orchestrator, the real default wiring is built lazily
  through the existing scheduler composition seam.

Everything is in-process and network-free (the registry/orchestrator seams are
injected fakes), so no DB connection is opened.
"""

from __future__ import annotations

from clara_ml.config import settings as app_settings
from clara_ml.ingestion import backfill as bf


class _FakeRegistry:
    """Source_Registry reader stub returning a fixed enabled-source list."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self.calls = 0

    def list_enabled_source_keys(self) -> list[str]:
        self.calls += 1
        return list(self._keys)


class _RecordingOrchestrator:
    """Ingestion orchestrator stub recording each per-source ``run`` call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def run(self, source_key: str, *, since: str | None = None) -> dict:
        self.calls.append((source_key, since))
        return {"source": source_key, "since": since, "ingested": 1}


def _set_ingestion(value: bool) -> bool:
    previous = app_settings.rag_ingestion_enabled
    app_settings.rag_ingestion_enabled = value
    return previous


def _set_backfill(value: bool) -> bool:
    previous = getattr(app_settings, "rag_backfill_enabled", False)
    app_settings.rag_backfill_enabled = value
    return previous


def _enable_backfill() -> tuple[bool, bool]:
    return _set_ingestion(True), _set_backfill(True)


def _restore_backfill(previous: tuple[bool, bool]) -> None:
    app_settings.rag_ingestion_enabled, app_settings.rag_backfill_enabled = previous


# ---------------------------------------------------------------------------
# Disabled path: strict no-op
# ---------------------------------------------------------------------------


def test_disabled_is_strict_noop_even_with_orchestrator_and_registry() -> None:
    registry = _FakeRegistry(["pubmed", "openfda"])
    orchestrator = _RecordingOrchestrator()
    previous = _set_ingestion(False), _set_backfill(True)
    try:
        report = bf.run_backfill(orchestrator=orchestrator, source_registry=registry)
    finally:
        _restore_backfill(previous)

    assert report.started is False
    assert report.sources == []
    assert report.per_source == {}
    assert "disabled" in report.reason
    # No work delegated at all: registry never read, orchestrator never run.
    assert registry.calls == 0
    assert orchestrator.calls == []


# ---------------------------------------------------------------------------
# Enabled: source resolution from the registry / explicit list
# ---------------------------------------------------------------------------


def test_enabled_resolves_all_enabled_sources_from_registry() -> None:
    registry = _FakeRegistry(["pubmed", "openfda", "dailymed"])
    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(
            source_keys=None,
            orchestrator=orchestrator,
            source_registry=registry,
        )
    finally:
        _restore_backfill(previous)

    assert report.started is True
    assert report.sources == ["pubmed", "openfda", "dailymed"]
    assert registry.calls == 1
    # Each enabled source was delegated to the orchestrator once.
    assert [key for key, _since in orchestrator.calls] == ["pubmed", "openfda", "dailymed"]


def test_enabled_all_sources_without_registry_resolves_empty() -> None:
    """With no registry reader wired, "all sources" resolves to empty (no DB read)."""

    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(source_keys=None, orchestrator=orchestrator)
    finally:
        _restore_backfill(previous)

    assert report.started is True
    assert report.sources == []
    assert orchestrator.calls == []


def test_explicit_source_keys_are_normalized() -> None:
    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(
            source_keys=[" pubmed ", "openfda", "pubmed", "", "  "],
            orchestrator=orchestrator,
        )
    finally:
        _restore_backfill(previous)

    # Blanks dropped, duplicates removed, first-seen order preserved.
    assert report.sources == ["pubmed", "openfda"]
    assert [key for key, _since in orchestrator.calls] == ["pubmed", "openfda"]


def test_explicit_keys_take_precedence_over_registry() -> None:
    registry = _FakeRegistry(["should-not-be-used"])
    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(
            source_keys=["pubmed"],
            orchestrator=orchestrator,
            source_registry=registry,
        )
    finally:
        _restore_backfill(previous)

    assert report.sources == ["pubmed"]
    # The registry is not consulted when an explicit list is given.
    assert registry.calls == 0


# ---------------------------------------------------------------------------
# since override + not-yet-wired path
# ---------------------------------------------------------------------------


def test_since_override_is_passed_through_per_source() -> None:
    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(
            source_keys=["pubmed", "openfda"],
            since="2026-01-01",
            orchestrator=orchestrator,
        )
    finally:
        _restore_backfill(previous)

    assert report.started is True
    assert orchestrator.calls == [("pubmed", "2026-01-01"), ("openfda", "2026-01-01")]
    assert report.per_source["pubmed"]["since"] == "2026-01-01"


def test_backfill_gate_is_strict_noop_even_when_ingestion_is_enabled() -> None:
    registry = _FakeRegistry(["pubmed"])
    orchestrator = _RecordingOrchestrator()
    previous = _set_ingestion(True), _set_backfill(False)
    try:
        report = bf.run_backfill(
            source_keys=None,
            orchestrator=orchestrator,
            source_registry=registry,
        )
    finally:
        _restore_backfill(previous)

    assert report.sources == []
    assert report.started is False
    assert "RAG_BACKFILL_ENABLED" in report.reason
    assert report.per_source == {}
    assert registry.calls == 0
    assert orchestrator.calls == []


def test_default_wiring_is_lazy_and_uses_existing_scheduler_composition(monkeypatch) -> None:
    orchestrator = _RecordingOrchestrator()
    previous = _enable_backfill()
    try:
        import clara_ml.ingestion.scheduler as scheduler

        sentinel_factory = object()
        monkeypatch.setattr(scheduler, "_resolve_session_factory", lambda: sentinel_factory)
        monkeypatch.setattr(
            scheduler,
            "_build_default_orchestrator",
            lambda factory: orchestrator if factory is sentinel_factory else None,
        )
        report = bf.run_backfill(source_keys=["pubmed"])
    finally:
        _restore_backfill(previous)

    assert report.started is True
    assert report.reason == "completed"
    assert orchestrator.calls == [("pubmed", None)]


def test_default_registry_adapter_filters_disabled_sources(monkeypatch) -> None:
    class _Schedule:
        def __init__(self, source_key: str, enabled: bool) -> None:
            self.source_key = source_key
            self.enabled = enabled

    class _Reader:
        def __init__(self, session_factory) -> None:
            assert session_factory is sentinel_factory

        def read_schedules(self) -> list[_Schedule]:
            return [_Schedule("pubmed", True), _Schedule("disabled-source", False)]

    import clara_ml.ingestion.scheduler as scheduler

    sentinel_factory = object()
    monkeypatch.setattr(scheduler, "RegistryScheduleReader", _Reader)

    registry = bf._DefaultSourceRegistry(sentinel_factory)
    assert registry.list_enabled_source_keys() == ["pubmed"]


def test_one_source_failure_is_typed_and_does_not_stop_siblings() -> None:
    class _PartiallyFailingOrchestrator(_RecordingOrchestrator):
        def run(self, source_key: str, *, since: str | None = None) -> dict:
            self.calls.append((source_key, since))
            if source_key == "bad-source":
                raise RuntimeError("upstream detail must not leak")
            return {"source": source_key}

    orchestrator = _PartiallyFailingOrchestrator()
    previous = _enable_backfill()
    try:
        report = bf.run_backfill(
            source_keys=["bad-source", "good-source"],
            orchestrator=orchestrator,
        )
    finally:
        _restore_backfill(previous)

    assert report.started is True
    assert report.reason == "completed_with_failures"
    assert report.per_source["bad-source"] == {
        "status": "failed",
        "reason": "orchestrator_run_failed:RuntimeError",
    }
    assert report.per_source["good-source"] == {"source": "good-source"}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_fakes_satisfy_the_structural_protocols() -> None:
    assert isinstance(_RecordingOrchestrator(), bf.IngestionOrchestratorLike)
    assert isinstance(_FakeRegistry([]), bf.SourceRegistryLike)
