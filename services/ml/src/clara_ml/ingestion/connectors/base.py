"""``Source_Connector`` protocol, ``RawRecord``, and a shared base (task 3.3).

This module defines the *contract* every offline source connector implements,
the immutable record type they emit, and the per-source configuration they
receive from the Source_Registry. Concrete connectors land in later tasks:
API-first connectors (``pubmed_eutils``/``openfda``/``dailymed_spl``/``rxnorm``/
``europepmc`` — task 3.4) and the robots-respecting ``vn_crawl`` gap-fill HTML
connector (task 3.5).

Design constraints honoured here (Requirements 6.1, 6.4, 6.5):

* **Resumable paging.** :meth:`SourceConnector.fetch` returns the records for a
  window together with a *next cursor* — an opaque ``str`` — or ``None`` when
  the source is exhausted. The orchestrator (task 3.16) checkpoints that cursor
  so an interrupted run resumes exactly where it stopped (Requirement 6.5).
* **Provenance carried from the registry.** Every connector receives a
  :class:`ConnectorContext` holding the source's ``trust_tier``,
  ``license_code``, and ``attribution`` (plus ``base_url`` and connector knobs).
  :meth:`BaseSourceConnector.make_record` stamps the registry ``trust_tier``
  into each :class:`RawRecord`, and the license/attribution travel on the
  context so the orchestrator can thread them into document provenance
  (Requirement 6.4).
* **Import-safe / no network at import.** Importing this module opens no socket
  and constructs no HTTP client. The optional :class:`BaseSourceConnector`
  creates its :mod:`httpx` client lazily, only when a subclass first asks for
  it, so importing the connectors package never touches the network.

``RawRecord`` matches the design's *Core Types* shape exactly so it round-trips
through cleaning → chunking → embedding without field drift.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from clara_ml.rag.store.schema import validate_trust_tier

__all__ = [
    "RawRecord",
    "FetchWindow",
    "ConnectorContext",
    "SourceConnector",
    "BaseSourceConnector",
]


# ---------------------------------------------------------------------------
# Emitted record (Core Types — design.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawRecord:
    """One fetched source document, before cleaning/chunking/embedding.

    The shape mirrors the design's *Core Types* exactly. ``trust_tier`` is the
    registry authority tier (1 = regulator/label .. 4 = lowest) stamped by the
    producing connector; ``effective_date`` is an optional recency signal kept
    as an ISO ``str`` (or ``None``) at this stage and normalized to a ``date``
    only when persisted.
    """

    source_key: str
    external_id: str          # PMID / SPL setid / URL hash
    title: str
    url: str
    lang: str                 # 'vi' | 'en'
    doc_type: str             # 'spl_label' | 'guideline' | 'rct' | 'review'
    raw_text: str
    effective_date: str | None
    trust_tier: int           # 1..4


# ---------------------------------------------------------------------------
# Fetch window + per-source context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchWindow:
    """The slice of a source a single ``fetch`` call should cover.

    A window bounds *what* to fetch (by watermark/time and optional query); the
    ``cursor`` argument to :meth:`SourceConnector.fetch` bounds *where within
    the window* to resume. ``since`` is typically the per-source watermark from
    the Source_Registry (inclusive lower bound); ``until`` is an exclusive upper
    bound (``None`` means "up to now"). ``page_size`` is the requested maximum
    number of records per page (a hint connectors clamp to their API limits).
    """

    since: str | None = None
    until: str | None = None
    page_size: int = 100
    query: str = ""


@dataclass(frozen=True)
class ConnectorContext:
    """Per-source configuration handed to a connector from the Source_Registry.

    Carries the provenance/authority a connector must attach to everything it
    produces (Requirement 6.4): ``trust_tier`` is stamped onto each
    :class:`RawRecord`, while ``license_code`` and ``attribution`` travel with
    the context for the orchestrator to record alongside persisted documents.
    ``base_url`` and ``config_json`` provide the connector-specific endpoint and
    knobs (page sizes, API params) without hard-coding them.

    ``trust_tier`` is validated against ``{1, 2, 3, 4}`` at construction so an
    out-of-range registry row is rejected before any fetch runs.
    """

    source_key: str
    trust_tier: int
    license_code: str = ""
    attribution: str = ""
    base_url: str = ""
    config_json: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_trust_tier(self.trust_tier)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SourceConnector(Protocol):
    """Structural contract for every offline source connector.

    Implementations are API-first; ``vn_crawl`` (task 3.5) is the only
    HTML/crawl path and additionally honours ``robots.txt`` and an
    allowed-domains list. A connector exposes the :class:`ConnectorContext` it
    was built with so the orchestrator can read provenance (license/attribution)
    without re-querying the registry.
    """

    context: ConnectorContext

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        """Fetch one page of records for ``window`` starting at ``cursor``.

        Args:
            window: Bounds of the slice to fetch (watermark/time + optional
                query and page-size hint).
            cursor: Opaque resume token returned by a previous ``fetch`` call,
                or ``None`` to start at the beginning of the window.

        Returns:
            A ``(records, next_cursor)`` tuple. ``next_cursor`` is an opaque
            ``str`` to pass to the next call, or ``None`` when the window is
            exhausted (Requirement 6.5). Each record carries the registry
            ``trust_tier`` (Requirement 6.4).
        """
        ...


# ---------------------------------------------------------------------------
# Optional shared base
# ---------------------------------------------------------------------------


class BaseSourceConnector(ABC):
    """Optional base with shared paging math and a lazy HTTP hook.

    Concrete connectors (tasks 3.4 / 3.5) may subclass this to inherit:

    * :meth:`make_record` — builds a :class:`RawRecord` with ``source_key`` and
      ``trust_tier`` taken from the :class:`ConnectorContext`, so provenance is
      stamped consistently (Requirement 6.4).
    * offset-cursor helpers (:meth:`decode_offset_cursor`,
      :meth:`next_offset_cursor`) — the paging-window math for resumable
      cursor-based fetching (Requirement 6.5).
    * :meth:`http_client` — a lazily-constructed :mod:`httpx.Client`. No client
      is created at import or construction time, so importing the package opens
      no network connection.

    Subclasses must implement :meth:`fetch`. The class deliberately does **not**
    perform any fetching itself — concrete network/HTML logic belongs in the
    per-source connectors.
    """

    def __init__(
        self,
        context: ConnectorContext,
        *,
        http_client_factory: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.context = context
        self._http_client_factory = http_client_factory
        self._timeout_seconds = timeout_seconds
        self._client: httpx.Client | None = None

    # -- contract ----------------------------------------------------------

    @abstractmethod
    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        """Fetch one page of records (see :class:`SourceConnector`)."""
        raise NotImplementedError

    # -- record construction ----------------------------------------------

    def make_record(
        self,
        *,
        external_id: str,
        raw_text: str,
        title: str = "",
        url: str = "",
        lang: str = "en",
        doc_type: str = "",
        effective_date: str | None = None,
    ) -> RawRecord:
        """Build a :class:`RawRecord`, stamping registry provenance.

        ``source_key`` and ``trust_tier`` are taken from the connector's
        :class:`ConnectorContext`, guaranteeing every produced record carries
        the authority tier from the Source_Registry (Requirement 6.4).
        """

        return RawRecord(
            source_key=self.context.source_key,
            external_id=external_id,
            title=title,
            url=url,
            lang=lang,
            doc_type=doc_type,
            raw_text=raw_text,
            effective_date=effective_date,
            trust_tier=self.context.trust_tier,
        )

    # -- paging window math ------------------------------------------------

    def resolve_page_size(self, window: FetchWindow) -> int:
        """Clamp the requested page size to a sane, source-aware bound.

        Uses ``config_json['max_page_size']`` as the per-source ceiling when
        present; otherwise the window's own ``page_size``. The result is always
        at least 1 so a fetch never requests an empty page.
        """

        requested = int(window.page_size) if window.page_size else 1
        ceiling = self.context.config_json.get("max_page_size")
        if isinstance(ceiling, int) and ceiling > 0:
            requested = min(requested, ceiling)
        return max(requested, 1)

    @staticmethod
    def decode_offset_cursor(cursor: str | None) -> int:
        """Decode an opaque offset cursor to a non-negative integer offset.

        ``None``/empty/malformed cursors decode to ``0`` (start of window), so a
        fresh run and a corrupted checkpoint both safely begin from the top.
        """

        if not cursor:
            return 0
        try:
            value = int(str(cursor).strip())
        except (TypeError, ValueError):
            return 0
        return max(value, 0)

    @classmethod
    def next_offset_cursor(
        cls,
        *,
        offset: int,
        page_size: int,
        fetched: int,
    ) -> str | None:
        """Compute the next offset cursor for resumable paging.

        Returns ``None`` when the page came back short (``fetched < page_size``),
        signalling the window is exhausted; otherwise returns the encoded offset
        for the following page (Requirement 6.5).
        """

        if page_size <= 0 or fetched < page_size:
            return None
        return str(max(offset, 0) + fetched)

    # -- lazy HTTP hook ----------------------------------------------------

    def http_client(self) -> httpx.Client:
        """Return a lazily-constructed :mod:`httpx` client.

        The client is created on first use (never at import/construction), so
        importing the connectors package performs no network I/O. An injected
        ``http_client_factory`` takes precedence, which keeps connectors easy to
        unit-test without real sockets.
        """

        if self._client is None:
            if self._http_client_factory is not None:
                self._client = self._http_client_factory()
            else:
                self._client = httpx.Client(
                    base_url=self.context.base_url or "",
                    timeout=self._timeout_seconds,
                )
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client if one was created."""

        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> BaseSourceConnector:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
