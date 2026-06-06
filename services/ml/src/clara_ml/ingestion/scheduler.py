"""Incremental ingestion ``Scheduler`` + Source_Registry seed (task 3.21).

This module owns two cooperating pieces of the offline ingestion plane
(design.md → "Offline Ingestion Plane / Scheduler" and the
``kb_source_registry`` data model):

* :class:`Scheduler` — decides *which* sources are due for an incremental run
  (per-source interval vs ``last_run_at`` from the Source_Registry) and triggers
  the injected :class:`IngestionOrchestrator` for each, starting every source
  from its persisted watermark (Requirement 4.6).
* :func:`seed_source_registry` + :data:`DEFAULT_SOURCES` — the data-driven seed
  that idempotently UPSERTs the default source rows (trust tier, license,
  attribution, fetch mode, base URL, connector config) into
  ``kb_source_registry`` (Requirement 6.3).

Design constraints honoured here
--------------------------------
* **Import-safe.** Importing this module opens no socket and no database
  connection and runs no DDL. The :data:`DEFAULT_SOURCES` table is pure data, so
  it (and the pure scheduling predicate :func:`is_due`) is testable without a
  database.
* **DB-injected.** The :class:`Scheduler` reads schedules through an injected
  :class:`ScheduleReader` seam; the default :class:`RegistryScheduleReader` is
  built from a dependency-injected SQLAlchemy session factory, so the scheduler
  never owns engine lifecycle. The seed accepts a
  :class:`~clara_ml.rag.store.document_store.DocumentStore`, a session factory,
  or a live :class:`~sqlalchemy.orm.Session`.
* **No coupling to the orchestrator module.** Like
  :mod:`clara_ml.ingestion.backfill`, the orchestrator is injected via the
  structural :class:`~clara_ml.ingestion.backfill.IngestionOrchestratorLike`
  protocol (reused here) instead of hard-importing
  ``ingestion/orchestrator.py``.
* **Flag-gated.** Every triggering entrypoint is a strict no-op when
  ``RAG_INGESTION_ENABLED`` is false (the default), so the legacy in-memory
  pipeline keeps serving traffic untouched.
* **Parameterized / ORM writes only.** The seed UPSERTs go through the
  SQLAlchemy ORM with bound parameters; no value is interpolated into SQL.

Watermark / interval logic (Requirements 4.6, 6.3)
--------------------------------------------------
``kb_source_registry`` carries ``last_run_at`` (when the source last ran) and
``last_watermark`` (the resumable cursor), but no dedicated interval column. The
per-source incremental cadence is therefore data-driven: it is stored in the
source's ``config_json['schedule_interval_seconds']`` (seeded from each
:class:`SourceSpec`). A source is *due* when it has never run
(``last_run_at IS NULL``) or when ``now - last_run_at >= interval``. When a due
source is run, the :class:`Scheduler` passes that source's persisted watermark
as the ``since`` override so the orchestrator resumes incrementally from where
the last run stopped (Requirement 4.6); the orchestrator itself advances
``last_watermark`` / ``last_run_at`` via its own checkpointing, so the scheduler
performs no registry writes during a run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_ml.config import settings

# Reuse the orchestrator DI seam from the backfill harness rather than importing
# the (heavier) orchestrator module — keeps this module decoupled + import-safe.
from clara_ml.ingestion.backfill import IngestionOrchestratorLike
from clara_ml.rag.normalize.umls_client import LICENSE_ATTRIBUTIONS
from clara_ml.rag.store.schema import KbSourceRegistry, validate_trust_tier

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "SCHEDULE_INTERVAL_KEY",
    "SourceSpec",
    "DEFAULT_SOURCES",
    "SourceSchedule",
    "ScheduleReader",
    "RegistryScheduleReader",
    "Scheduler",
    "is_due",
    "run_incremental_ingestion",
    "seed_source_registry",
]


# ---------------------------------------------------------------------------
# Interval configuration
# ---------------------------------------------------------------------------

# Default incremental cadence when a source row carries no explicit interval.
DEFAULT_INTERVAL_SECONDS = 86_400  # 24h

# The ``config_json`` key under which a source's incremental cadence is stored.
SCHEDULE_INTERVAL_KEY = "schedule_interval_seconds"

# A couple of named cadences for readability in DEFAULT_SOURCES.
_DAILY = 86_400
_WEEKLY = 604_800


# ---------------------------------------------------------------------------
# Default source seed (data-driven; testable without a DB)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSpec:
    """Declarative seed row for one ``kb_source_registry`` entry.

    Pure data: a :class:`SourceSpec` describes the trust tier, license,
    attribution, fetch mode, base URL and connector ``config_json`` for a source
    without touching a database. :func:`seed_source_registry` maps each spec to
    an idempotent UPSERT.

    The incremental cadence (``interval_seconds``) is merged into the persisted
    ``config_json`` under :data:`SCHEDULE_INTERVAL_KEY` so the :class:`Scheduler`
    can read it back from the registry row (see :meth:`registry_config_json`).
    """

    source_key: str
    display_name: str
    trust_tier: int
    license_code: str = ""
    attribution: str = ""
    fetch_mode: str = "api"  # 'api' | 'crawl'
    base_url: str = ""
    robots_respect: bool = True
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    config_json: dict[str, Any] = field(default_factory=dict)

    def registry_config_json(self) -> dict[str, Any]:
        """Return the ``config_json`` to persist, with the interval merged in.

        An explicit ``schedule_interval_seconds`` already present in
        ``config_json`` wins over :attr:`interval_seconds` so a caller can
        override the cadence per source without losing the connector knobs.
        """

        merged = dict(self.config_json)
        merged.setdefault(SCHEDULE_INTERVAL_KEY, int(self.interval_seconds))
        return merged


# Default curated source list (Requirement 6.3). Trust tiers: 1 = regulator /
# drug label (highest authority) .. 4 = lowest. RxNorm carries the NLM RxNorm
# attribution from the shared ``LICENSE_ATTRIBUTIONS`` table (Requirement 15.3).
DEFAULT_SOURCES: list[SourceSpec] = [
    SourceSpec(
        source_key="openfda",
        display_name="openFDA (U.S. FDA drug labels & events)",
        trust_tier=1,
        license_code="openFDA-public",
        attribution=(
            "This product uses publicly available data from the U.S. Food and "
            "Drug Administration (FDA) openFDA API but is not endorsed or "
            "certified by the FDA."
        ),
        fetch_mode="api",
        base_url="https://api.fda.gov",
        interval_seconds=_DAILY,
    ),
    SourceSpec(
        source_key="dailymed",
        display_name="DailyMed (NLM Structured Product Labels)",
        trust_tier=1,
        license_code="DailyMed-public",
        attribution=(
            "Source: DailyMed, U.S. National Library of Medicine (NLM), "
            "National Institutes of Health."
        ),
        fetch_mode="api",
        base_url="https://dailymed.nlm.nih.gov/dailymed/services",
        interval_seconds=_WEEKLY,
    ),
    SourceSpec(
        source_key="rxnorm",
        display_name="RxNorm (NLM normalized drug nomenclature)",
        trust_tier=1,
        license_code="RxNorm",
        # License-aware attribution sourced from the shared UMLS/RxNorm table.
        attribution=LICENSE_ATTRIBUTIONS.get("RXNORM", ""),
        fetch_mode="api",
        base_url="https://rxnav.nlm.nih.gov/REST",
        interval_seconds=_WEEKLY,
    ),
    SourceSpec(
        source_key="pubmed",
        display_name="PubMed / MEDLINE (NCBI E-utilities)",
        trust_tier=3,
        license_code="NCBI-EUtils-public",
        attribution=(
            "Courtesy of the U.S. National Library of Medicine (NLM), "
            "PubMed/MEDLINE via the NCBI E-utilities."
        ),
        fetch_mode="api",
        base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        interval_seconds=_DAILY,
    ),
    SourceSpec(
        source_key="europepmc",
        display_name="Europe PMC (EMBL-EBI literature)",
        trust_tier=3,
        license_code="EuropePMC",
        attribution=(
            "Includes data from Europe PMC (EMBL-EBI), used under the Europe "
            "PMC terms of use."
        ),
        fetch_mode="api",
        base_url="https://www.ebi.ac.uk/europepmc/webservices/rest",
        interval_seconds=_DAILY,
    ),
    SourceSpec(
        source_key="vn_dav",
        display_name="Cục Quản lý Dược Việt Nam (Drug Administration of Vietnam)",
        trust_tier=1,
        license_code="public-vn",
        attribution=(
            "Nguồn: Cục Quản lý Dược, Bộ Y tế Việt Nam (Drug Administration of "
            "Vietnam, Ministry of Health)."
        ),
        fetch_mode="crawl",
        base_url="https://dav.gov.vn",
        robots_respect=True,
        interval_seconds=_WEEKLY,
        config_json={"allowed_domains": ["dav.gov.vn"]},
    ),
    SourceSpec(
        source_key="who",
        display_name="World Health Organization (WHO) guidelines",
        trust_tier=2,
        license_code="WHO",
        attribution=(
            "© World Health Organization (WHO). Reproduced for informational "
            "use under the WHO terms of use."
        ),
        fetch_mode="crawl",
        base_url="https://www.who.int",
        robots_respect=True,
        interval_seconds=_WEEKLY,
        config_json={"allowed_domains": ["who.int"]},
    ),
]


# ---------------------------------------------------------------------------
# Schedule view + reader seam
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSchedule:
    """A per-source scheduling view distilled from a ``kb_source_registry`` row.

    Carries only what the scheduling predicate needs: whether the source is
    ``enabled``, its incremental ``interval_seconds``, when it ``last_run_at``
    (``None`` = never), and the resumable ``watermark`` the orchestrator should
    resume from (Requirement 4.6).
    """

    source_key: str
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    last_run_at: datetime | None = None
    watermark: str = ""


@runtime_checkable
class ScheduleReader(Protocol):
    """Structural seam returning the current per-source schedules.

    Any object exposing ``read_schedules() -> Sequence[SourceSchedule]``
    satisfies the contract, so the :class:`Scheduler` is unit-testable against a
    fake registry (a list of :class:`SourceSchedule`) without a database.
    """

    def read_schedules(self) -> Sequence[SourceSchedule]:  # pragma: no cover - protocol
        ...


class RegistryScheduleReader:
    """Default :class:`ScheduleReader` backed by ``kb_source_registry``.

    Built from a dependency-injected session factory (a
    :class:`~sqlalchemy.orm.sessionmaker` or any zero-arg callable returning a
    :class:`~sqlalchemy.orm.Session`), so importing this module opens no
    connection and the reader stays unit-testable. The per-source interval is
    read from ``config_json[SCHEDULE_INTERVAL_KEY]`` (falling back to
    ``default_interval_seconds`` when absent or invalid).
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        default_interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be a zero-argument callable returning a Session")
        self._session_factory = session_factory
        self._default_interval = _coerce_interval(default_interval_seconds, DEFAULT_INTERVAL_SECONDS)

    def read_schedules(self) -> list[SourceSchedule]:
        session = self._session_factory()
        try:
            rows = (
                session.execute(
                    select(KbSourceRegistry).order_by(KbSourceRegistry.source_key)
                )
                .scalars()
                .all()
            )
            return [self._to_schedule(row) for row in rows]
        finally:
            session.close()

    def _to_schedule(self, row: KbSourceRegistry) -> SourceSchedule:
        config = row.config_json if isinstance(row.config_json, dict) else {}
        interval = _coerce_interval(config.get(SCHEDULE_INTERVAL_KEY), self._default_interval)
        return SourceSchedule(
            source_key=row.source_key,
            enabled=bool(row.enabled),
            interval_seconds=interval,
            last_run_at=row.last_run_at,
            watermark=row.last_watermark or "",
        )


# ---------------------------------------------------------------------------
# Pure scheduling helpers (no DB / no clock side effects)
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Current UTC time (injectable ``now`` overrides this in the public API)."""

    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC (naive is assumed UTC)."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coerce_interval(value: Any, fallback: int) -> int:
    """Return a positive int interval, falling back when missing / invalid."""

    try:
        if isinstance(value, bool):  # bools are ints in Python — reject them
            raise ValueError
        interval = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return interval if interval > 0 else int(fallback)


def is_due(
    schedule: SourceSchedule,
    now: datetime,
    *,
    default_interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> bool:
    """Return ``True`` when ``schedule`` is due for an incremental run at ``now``.

    A source is due when it is enabled AND either it has never run
    (``last_run_at is None``) or at least ``interval_seconds`` have elapsed since
    its last run. ``interval_seconds <= 0`` falls back to
    ``default_interval_seconds``. Pure and clock-free (``now`` is supplied), so
    the predicate is trivially testable.
    """

    if not schedule.enabled:
        return False
    if schedule.last_run_at is None:
        return True
    interval = _coerce_interval(schedule.interval_seconds, default_interval_seconds)
    elapsed = (_as_utc(now) - _as_utc(schedule.last_run_at)).total_seconds()
    return elapsed >= interval


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class Scheduler:
    """Incremental ingestion scheduler driven by per-source watermarks.

    The scheduler reads schedules through an injected :class:`ScheduleReader`
    seam and decides which sources are due (:meth:`due_sources`), then triggers
    an injected orchestrator for each due source (:meth:`run_due`), resuming
    every source from its persisted watermark (Requirement 4.6).

    Both entrypoints are strict no-ops when ``RAG_INGESTION_ENABLED`` is false.
    """

    def __init__(
        self,
        reader: ScheduleReader,
        *,
        default_interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        if not hasattr(reader, "read_schedules"):
            raise TypeError("reader must expose a read_schedules() method")
        self._reader = reader
        self._default_interval = _coerce_interval(default_interval_seconds, DEFAULT_INTERVAL_SECONDS)

    @classmethod
    def from_session_factory(
        cls,
        session_factory: Callable[[], Session],
        *,
        default_interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> "Scheduler":
        """Build a scheduler whose reader queries ``kb_source_registry``."""

        reader = RegistryScheduleReader(
            session_factory, default_interval_seconds=default_interval_seconds
        )
        return cls(reader, default_interval_seconds=default_interval_seconds)

    # -- decision -----------------------------------------------------------

    def _due_schedules(self, now: datetime) -> list[SourceSchedule]:
        """Return the enabled, due schedules in reader order."""

        return [
            sched
            for sched in self._reader.read_schedules()
            if is_due(sched, now, default_interval_seconds=self._default_interval)
        ]

    def due_sources(self, now: datetime | None = None) -> list[str]:
        """Return the source keys due for an incremental run at ``now``.

        Returns ``[]`` when ``RAG_INGESTION_ENABLED`` is false. ``now`` defaults
        to the current UTC time; pass it explicitly for deterministic tests.
        """

        if not settings.rag_ingestion_enabled:
            return []
        moment = _utcnow() if now is None else now
        return [sched.source_key for sched in self._due_schedules(moment)]

    # -- triggering ---------------------------------------------------------

    def run_due(
        self,
        orchestrator: IngestionOrchestratorLike,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Trigger ``orchestrator`` for every due source; return per-source reports.

        Each due source is run starting from its persisted watermark (the
        ``since`` override, Requirement 4.6); when a source has no watermark yet
        ``since=None`` is passed so the orchestrator starts from the beginning.
        The orchestrator is responsible for advancing ``last_watermark`` /
        ``last_run_at`` (via its own checkpointing), so the scheduler writes
        nothing to the registry here.

        Returns a ``{source_key: report}`` map (the report is whatever the
        orchestrator's ``run`` returns). Returns ``{}`` — without touching the
        orchestrator — when ``RAG_INGESTION_ENABLED`` is false.
        """

        if not settings.rag_ingestion_enabled:
            return {}
        if orchestrator is None or not hasattr(orchestrator, "run"):
            raise TypeError("orchestrator must expose a run(source_key, *, since=None) method")

        moment = _utcnow() if now is None else now
        reports: dict[str, Any] = {}
        for sched in self._due_schedules(moment):
            since = sched.watermark or None
            reports[sched.source_key] = orchestrator.run(sched.source_key, since=since)
        return reports


# ---------------------------------------------------------------------------
# Scheduled incremental-ingestion entrypoint (task 9.9, Requirement 4.6)
# ---------------------------------------------------------------------------


def _resolve_default_engine() -> Any | None:
    """Resolve the configured SQLAlchemy engine, or ``None`` (defensive).

    Reuses the lazy engine resolver from the persistent-store self-check
    (``rag.store.health``), which reads ``database_url`` / ``DATABASE_URL`` and
    never opens a connection. Returns ``None`` when no URL is configured.
    """

    try:
        from clara_ml.rag.store.health import resolve_default_engine

        return resolve_default_engine(settings)
    except Exception as exc:  # pragma: no cover - defensive import guard
        logger.warning(
            "incremental ingestion: could not resolve database engine (%s)",
            exc.__class__.__name__,
        )
        return None


def _resolve_session_factory(engine: Any | None = None) -> Callable[[], Session] | None:
    """Build a ``Session`` factory from ``engine`` (or the configured default).

    Returns ``None`` when no engine is available so the caller degrades to a
    strict no-op rather than raising.
    """

    try:
        from sqlalchemy.orm import sessionmaker

        active = engine if engine is not None else _resolve_default_engine()
        if active is None:
            return None
        return sessionmaker(bind=active, expire_on_commit=False)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "incremental ingestion: could not build session factory (%s)",
            exc.__class__.__name__,
        )
        return None


def _build_default_orchestrator(
    session_factory: Callable[[], Session] | None = None,
    *,
    engine: Any | None = None,
) -> IngestionOrchestratorLike | None:
    """Lazily build the default :class:`IngestionOrchestrator`, or ``None``.

    Composes the existing offline-ingestion collaborators — a
    :class:`~clara_ml.rag.store.document_store.DocumentStore` (write boundary)
    and an :class:`~clara_ml.ingestion.embedding_builder.EmbeddingBuilder` (embed
    once) backed by the production :class:`~clara_ml.rag.embedder.HttpEmbeddingClient`.
    The heavy ``ingestion.orchestrator`` import is performed here (lazily) so the
    scheduler module stays import-safe and decoupled. Any failure resolves to
    ``None`` so the entrypoint degrades to a no-op instead of crashing.
    """

    try:
        from clara_ml.ingestion.embedding_builder import EmbeddingBuilder
        from clara_ml.ingestion.orchestrator import IngestionOrchestrator
        from clara_ml.rag.embedder import HttpEmbeddingClient
        from clara_ml.rag.store.document_store import DocumentStore

        factory = session_factory if session_factory is not None else _resolve_session_factory(engine)
        if factory is None:
            return None
        store = DocumentStore(factory)
        builder = EmbeddingBuilder(HttpEmbeddingClient())
        return IngestionOrchestrator(store, builder)
    except Exception as exc:  # pragma: no cover - defensive: never crash a run
        logger.warning(
            "incremental ingestion: default orchestrator unavailable (%s)",
            exc.__class__.__name__,
        )
        return None


def run_incremental_ingestion(
    *,
    orchestrator: IngestionOrchestratorLike | None = None,
    scheduler: Scheduler | None = None,
    session_factory: Callable[[], Session] | None = None,
    engine: Any | None = None,
    now: datetime | None = None,
    default_interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Scheduled incremental-ingestion entrypoint (Requirement 4.6).

    Triggers an incremental ingestion run for every source that is *due*
    (per-source interval vs ``last_run_at``), resuming each due source from its
    persisted ``last_watermark`` in the Source_Registry (the watermarks seeded in
    task 3.21). It composes the :class:`Scheduler` (which decides what is due and
    supplies each source's watermark as the ``since`` override) with the existing
    :class:`~clara_ml.ingestion.orchestrator.IngestionOrchestrator` (which performs
    the idempotent, resumable, atomic-per-document ingestion).

    Strict no-op contract: returns ``{}`` WITHOUT touching the database, building
    an orchestrator, or reading the registry when ``RAG_INGESTION_ENABLED`` is
    false (the default), so the legacy in-memory pipeline is untouched.

    Every collaborator is injectable (DI / tests). When not injected they are
    built lazily and defensively from the configured database engine; if no
    database URL is configured or construction fails, the function returns ``{}``
    rather than raising.

    Args:
        orchestrator: The ingestion orchestrator to drive. Defaults to a
            lazily-built :class:`IngestionOrchestrator`.
        scheduler: The :class:`Scheduler` deciding which sources are due.
            Defaults to one reading ``kb_source_registry`` via ``session_factory``.
        session_factory: Zero-arg callable returning a :class:`Session`. Derived
            from ``engine`` (or the configured default engine) when omitted.
        engine: A SQLAlchemy ``Engine`` to derive a session factory from when
            neither ``session_factory`` nor ``scheduler`` is injected.
        now: Injected clock for deterministic tests; defaults to current UTC.
        default_interval_seconds: Fallback cadence when a source row carries no
            explicit ``schedule_interval_seconds``.

    Returns:
        A ``{source_key: report}`` map (the orchestrator's per-source result),
        or ``{}`` when disabled / no source is due / collaborators unavailable.
    """

    if not settings.rag_ingestion_enabled:
        return {}

    if scheduler is None:
        factory = session_factory if session_factory is not None else _resolve_session_factory(engine)
        if factory is None:
            logger.info("incremental ingestion skipped: no database engine configured")
            return {}
        session_factory = factory
        scheduler = Scheduler.from_session_factory(
            session_factory, default_interval_seconds=default_interval_seconds
        )

    if orchestrator is None:
        orchestrator = _build_default_orchestrator(session_factory, engine=engine)
        if orchestrator is None:
            logger.info("incremental ingestion skipped: ingestion orchestrator unavailable")
            return {}

    return scheduler.run_due(orchestrator, now=now)


# ---------------------------------------------------------------------------
# Source_Registry seed (idempotent UPSERT on source_key)
# ---------------------------------------------------------------------------


def _upsert_sources(session: Session, sources: Sequence[SourceSpec]) -> list[str]:
    """UPSERT each :class:`SourceSpec` into ``kb_source_registry`` on ``session``.

    Idempotent on ``source_key``: an existing row has its descriptive columns
    (display name, tier, license, attribution, fetch mode, base URL, robots
    flag, enabled flag, config) refreshed in place, while its ingestion progress
    columns (``last_watermark`` / ``last_run_at``) are deliberately left
    untouched so re-seeding never rewinds an in-flight ingestion. Flushes (does
    not commit) so it composes inside a caller-owned transaction.
    """

    seeded: list[str] = []
    for spec in sources:
        tier = validate_trust_tier(spec.trust_tier)
        config = spec.registry_config_json()
        existing = session.execute(
            select(KbSourceRegistry).where(KbSourceRegistry.source_key == spec.source_key)
        ).scalar_one_or_none()

        if existing is not None:
            existing.display_name = spec.display_name
            existing.trust_tier = tier
            existing.base_url = spec.base_url
            existing.fetch_mode = spec.fetch_mode
            existing.license_code = spec.license_code
            existing.attribution = spec.attribution
            existing.robots_respect = bool(spec.robots_respect)
            existing.enabled = bool(spec.enabled)
            existing.config_json = config
        else:
            session.add(
                KbSourceRegistry(
                    source_key=spec.source_key,
                    display_name=spec.display_name,
                    trust_tier=tier,
                    base_url=spec.base_url,
                    fetch_mode=spec.fetch_mode,
                    license_code=spec.license_code,
                    attribution=spec.attribution,
                    robots_respect=bool(spec.robots_respect),
                    enabled=bool(spec.enabled),
                    config_json=config,
                )
            )
        seeded.append(spec.source_key)

    session.flush()
    return seeded


def seed_source_registry(
    store_or_session: Any,
    *,
    sources: Sequence[SourceSpec] | None = None,
) -> list[str]:
    """Idempotently UPSERT the default sources into ``kb_source_registry``.

    Args:
        store_or_session: One of —
            * a :class:`~clara_ml.rag.store.document_store.DocumentStore`-like
              object exposing ``transaction()`` (preferred; commits on success);
            * a zero-arg session factory (a ``sessionmaker`` / callable returning
              a :class:`~sqlalchemy.orm.Session`) — a session is opened, the
              UPSERTs committed, and the session closed; or
            * a live :class:`~sqlalchemy.orm.Session` — the UPSERTs run and are
              committed on the supplied session.
        sources: Source specs to seed; defaults to :data:`DEFAULT_SOURCES`.

    Returns:
        The list of seeded ``source_key`` values (order-preserving).

    Raises:
        TypeError: If ``store_or_session`` is none of the supported shapes.
    """

    specs = list(DEFAULT_SOURCES if sources is None else sources)

    # 1) DocumentStore-like: reuse its transactional boundary (commits/rolls back).
    transaction = getattr(store_or_session, "transaction", None)
    if callable(transaction) and not isinstance(store_or_session, Session):
        with transaction() as session:
            return _upsert_sources(session, specs)

    # 2) Live Session: operate on it and commit.
    if isinstance(store_or_session, Session):
        seeded = _upsert_sources(store_or_session, specs)
        store_or_session.commit()
        return seeded

    # 3) Session factory: open / commit / close our own short transaction.
    if callable(store_or_session):
        session = store_or_session()
        try:
            seeded = _upsert_sources(session, specs)
            session.commit()
            return seeded
        finally:
            session.close()

    raise TypeError(
        "seed_source_registry expects a DocumentStore-like object, a session "
        "factory, or a SQLAlchemy Session"
    )
