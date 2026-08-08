"""``Ingestion_Orchestrator`` — idempotent / resumable corpus build (task 3.16).

This module wires the offline ingestion plane end-to-end for a single source
(design.md → "Low-Level Design / 6. Ingestion Orchestrator (idempotent /
resumable)"):

    SourceConnector (ingestion.connectors)
        -> Cleaner       (ingestion.cleaning.clean + content_hash)
        -> EntityLinker  (optional; injected, no-op default for P1)
        -> Structure_Aware_Chunker (ingestion.chunking.chunk_document)
        -> EmbeddingBuilder         (ingestion.embedding_builder)
        -> DocumentStore            (rag.store.document_store)

The orchestrator owns the *control flow* (paging, idempotency check, atomic
per-document persistence, watermark checkpointing, accounting) and delegates all
domain work to the injected collaborators, so it stays small, import-safe, and
unit-testable against fakes.

Design constraints honoured here
--------------------------------
* **Import-safe / DB-injected.** Importing this module opens no socket and runs
  no DDL. The orchestrator receives a :class:`~clara_ml.rag.store.document_store.DocumentStore`
  (constructed with a dependency-injected session factory) and an
  :class:`~clara_ml.ingestion.embedding_builder.EmbeddingBuilder`. Connectors are
  built lazily from the registry via :func:`~clara_ml.ingestion.connectors.registry.build_connector`
  (or a pre-built connector / factory injected for tests).
* **IDEMPOTENT (Requirements 4.1 / 4.2).** A record whose deterministic
  ``content_hash`` already exists for ``(source_id, external_id)`` is skipped, so
  re-running over unchanged upstream data inserts **0** new chunks and yields
  ``skipped == fetched``.
* **RESUMABLE (Requirement 4.3).** After each fetched batch the next cursor is
  persisted via :meth:`DocumentStore.checkpoint` (the per-source watermark in
  ``kb_source_registry``); a crash/restart resumes from that watermark and
  reprocesses nothing already committed.
* **ATOMIC PER DOCUMENT (Requirement 4.4).** Each document's
  document/chunks/embeddings/sparse-terms/(entity-links) are persisted inside a
  single :meth:`DocumentStore.transaction`, so a failure mid-document leaves no
  partial document.
* **NO DEGRADED PERSISTENCE (Requirements 2.4 / 2.5).** In production the
  :class:`EmbeddingBuilder` raises
  :class:`~clara_ml.rag.embedder.EmbeddingUnavailableError` when the embedding
  client returns any degraded vector; the orchestrator catches it, counts the
  document as ``failed``, and the surrounding transaction rolls back — a
  meaningless vector is never persisted.
* **ACCOUNTING IDENTITY (Requirement 4.5).** The emitted :class:`IngestionReport`
  satisfies ``fetched == inserted + updated + skipped + failed`` for every run.

Source resolution
------------------
The Source_Registry row (``source_id``, ``trust_tier``, ``license_code``,
``attribution``, ``base_url``, ``last_watermark``) is read through the injected
``DocumentStore`` session. The default resolver
(:meth:`IngestionOrchestrator._default_resolve_source`) loads the
``kb_source_registry`` row and yields a :class:`SourceResolution` carrying the
``source_id`` plus a :class:`~clara_ml.ingestion.connectors.base.ConnectorContext`
(used to build the connector and to thread provenance into persisted documents).
A custom resolver callable can be injected to override this lookup.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_ml.config import settings
from clara_ml.ingestion.chunking import chunk_document, count_tokens
from clara_ml.ingestion.cleaning import clean as default_clean
from clara_ml.ingestion.cleaning import content_hash as default_content_hash
from clara_ml.ingestion.connectors.base import (
    ConnectorContext,
    FetchWindow,
    RawRecord,
    SourceConnector,
)
from clara_ml.ingestion.connectors.registry import build_connector
from clara_ml.nlp.unicode_utils import normalize_nfc
from clara_ml.rag.embedder import EmbeddingUnavailableError
from clara_ml.rag.store.document_store import (
    ChunkEntityLink,
    ChunkRow,
    DocumentStore,
    IngestDocument,
)
from clara_ml.rag.store.graph_store import EntityInput, GraphStore
from clara_ml.rag.store.schema import KbDocument, KbSourceRegistry

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids any import overhead
    from clara_ml.ingestion.chunking import Chunk
    from clara_ml.ingestion.embedding_builder import EmbeddingBuilder

logger = logging.getLogger(__name__)

__all__ = [
    "IngestionReport",
    "IngestionError",
    "IngestionAccountingError",
    "SourceNotFoundError",
    "SourceDisabledError",
    "SourceResolution",
    "EntityLinker",
    "IngestionOrchestrator",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IngestionError(RuntimeError):
    """Base class for orchestrator-level ingestion failures."""


class SourceNotFoundError(IngestionError):
    """Raised when a ``source_key`` is absent from ``kb_source_registry``."""


class SourceDisabledError(IngestionError):
    """Raised when a resolved source exists but is not enabled for ingestion."""


class IngestionAccountingError(IngestionError):
    """Raised when an :class:`IngestionReport` violates its accounting identity."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class IngestionReport:
    """Per-run counts for one source ingestion (design.md ``IngestionReport``).

    The accounting identity ``fetched == inserted + updated + skipped + failed``
    holds for every successful run (Requirement 4.5). ``inserted`` counts records
    persisted as brand-new documents; ``updated`` counts records whose
    ``(source_id, external_id)`` already existed but whose content changed;
    ``skipped`` counts records whose ``content_hash`` already existed (idempotent
    no-ops); ``failed`` counts records whose per-document transaction was rolled
    back (e.g. a degraded embedding aborted the document in production).
    """

    source_key: str = ""
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def accounted(self) -> int:
        """Sum of the disposition counters (must equal :attr:`fetched`)."""

        return self.inserted + self.updated + self.skipped + self.failed

    def accounting_holds(self) -> bool:
        """Return ``True`` when ``fetched == inserted + updated + skipped + failed``."""

        return self.fetched == self.accounted

    def assert_accounting(self) -> None:
        """Raise :class:`IngestionAccountingError` if the identity is violated.

        A defensive postcondition check the orchestrator runs before returning a
        report; also useful as the assertion target for the idempotency /
        accounting property tests (tasks 3.17–3.20).
        """

        if not self.accounting_holds():
            raise IngestionAccountingError(
                f"ingestion accounting violated for source_key={self.source_key!r}: "
                f"fetched={self.fetched} != inserted+updated+skipped+failed={self.accounted} "
                f"(inserted={self.inserted}, updated={self.updated}, "
                f"skipped={self.skipped}, failed={self.failed})"
            )


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceResolution:
    """Resolved ``kb_source_registry`` view needed to drive one ingestion run.

    Carries the persisted ``source_id`` (the orchestrator's idempotency /
    checkpoint key), the :class:`ConnectorContext` (provenance + connector
    knobs), the resumable ``watermark`` and the ``enabled`` flag.
    """

    source_id: int
    context: ConnectorContext
    watermark: str = ""
    enabled: bool = True
    display_name: str = ""


# A resolver maps a ``source_key`` to a :class:`SourceResolution`.
SourceResolver = Callable[[str], SourceResolution]

# A connector factory builds a connector from a ``source_key`` + context.
ConnectorFactory = Callable[[str, ConnectorContext], SourceConnector]

# A cleaner normalizes raw text into deterministic, PII-redacted ``clean_text``.
Cleaner = Callable[..., str]

# A hasher derives the idempotency content hash over ``clean_text``.
Hasher = Callable[[str], str]

# A chunker splits a (record, clean_text) into structure-aware chunks.
Chunker = Callable[[RawRecord, str], "list[Chunk]"]


class EntityLinker(Protocol):
    """Minimal structural contract for an injected entity linker (P3).

    For P1 the orchestrator runs with no linker (``None``); when a linker is
    injected (task 7.6) its :meth:`link` output is mapped to
    :class:`~clara_ml.rag.store.document_store.ChunkEntityLink` rows by the
    configured ``entity_link_mapper`` and persisted inside the document
    transaction.
    """

    def link(self, text: str, *, lang: str) -> Sequence[Any]:  # pragma: no cover - protocol
        ...


# Maps (chunk_ids, chunks, linked_entities) -> chunk<->entity link rows.
EntityLinkMapper = Callable[[list[int], "list[Chunk]", Sequence[Any]], list[ChunkEntityLink]]


def _noop_entity_link_mapper(
    chunk_ids: list[int],
    chunks: list[Chunk],
    entities: Sequence[Any],
) -> list[ChunkEntityLink]:
    """Default link mapper for P1: persists no entity links.

    Entity persistence (``kb_entities`` ids) lands in P3 (task 7.x); until then
    the orchestrator wires the linker seam but emits no links.
    """

    del chunk_ids, chunks, entities
    return []


# --- Entity-link surface matching (pure, network-free) ---------------------
#
# Used by the default graph-backed entity-link mapper (task 7.6) to decide which
# persisted chunks actually mention a linked entity. Token-aligned matching
# (not raw substring) prevents partial-word false positives such as "ace"
# matching inside "acetaminophen".

_ENTITY_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _entity_tokens(text: str) -> list[str]:
    """Normalize (NFC + casefold) and tokenize ``text`` into word tokens."""

    if not text:
        return []
    return _ENTITY_TOKEN_RE.findall(normalize_nfc(str(text)).casefold())


def _phrase_in_tokens(phrase_tokens: list[str], text_tokens: list[str]) -> bool:
    """True if ``phrase_tokens`` appears as a contiguous sublist of tokens."""

    span = len(phrase_tokens)
    if span == 0 or span > len(text_tokens):
        return False
    for start in range(len(text_tokens) - span + 1):
        if text_tokens[start : start + span] == phrase_tokens:
            return True
    return False


def _entity_surface_names(entity: Any) -> list[str]:
    """Order-preserving, de-duplicated canonical + synonym surface names.

    Tolerates both the :class:`LinkedEntity` dataclass shape (``synonyms`` =
    ``list[dict]`` with a ``name`` key) and plain objects, so the mapper can be
    exercised offline with a fake linker.
    """

    names: list[str] = []
    canonical = getattr(entity, "canonical_name", None)
    if isinstance(canonical, str) and canonical.strip():
        names.append(canonical.strip())
    for syn in getattr(entity, "synonyms", None) or []:
        name = syn.get("name") if isinstance(syn, dict) else getattr(syn, "name", None)
        if isinstance(name, str) and name.strip():
            names.append(name.strip())

    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            ordered.append(name)
    return ordered


def _entity_source_vocab(entity: Any) -> str:
    """Best-effort source-vocabulary label for a linked entity (RxNorm/UMLS)."""

    if (getattr(entity, "rxcui", "") or "").strip():
        return "RXNORM"
    if (getattr(entity, "cui", "") or "").strip():
        return "UMLS"
    return ""


def _parse_iso_date(value: Any) -> date | None:
    """Best-effort convert an ISO date string to a :class:`datetime.date`.

    ``RawRecord.effective_date`` is an optional ISO ``str`` (``YYYY-MM-DD`` or a
    longer ISO timestamp); only the date head is used. Returns ``None`` for an
    empty or unparseable value.
    """

    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class IngestionOrchestrator:
    """Drive fetch → clean → link → chunk → embed-once → persist for one source.

    Parameters
    ----------
    store:
        The :class:`DocumentStore` write boundary (idempotency check, atomic
        per-document transaction, checkpoint). Constructed with a
        dependency-injected session factory so the orchestrator stays import-safe.
    embedding_builder:
        The :class:`EmbeddingBuilder` that embeds a chunk batch **once** and
        returns the dense + sparse store rows. It enforces the production
        fail-loud rule, raising :class:`EmbeddingUnavailableError` on a degraded
        batch.
    linker:
        Optional :class:`EntityLinker`. ``None`` (the P1 default) runs no entity
        linking. When provided, its output is mapped via ``entity_link_mapper``.
    connectors:
        Optional mapping of ``source_key`` -> pre-built :class:`SourceConnector`
        (handy for tests / injection). Takes precedence over ``connector_factory``.
    connector_factory:
        Optional callable ``(source_key, context) -> SourceConnector``. Defaults
        to a thin wrapper over :func:`build_connector` (forwarding
        ``connector_kwargs``).
    connector_kwargs:
        Extra kwargs forwarded to the default :func:`build_connector` factory
        (e.g. an injected ``http_client_factory``).
    source_resolver:
        Optional callable ``source_key -> SourceResolution``. Defaults to a
        registry lookup through ``store`` (:meth:`_default_resolve_source`).
    cleaner / hasher / chunker:
        Injectable overrides for the pure transforms; default to
        :func:`clean`, :func:`content_hash` and :func:`chunk_document`.
    entity_link_mapper:
        Maps linker output to :class:`ChunkEntityLink` rows. Defaults to a no-op
        seam; when no mapper is injected and a linker is active the orchestrator
        resolves entity ids itself via :meth:`GraphStore.upsert_entity`.
    graph_store:
        Optional injected :class:`~clara_ml.rag.store.graph_store.GraphStore`
        used to UPSERT linked entities into ``kb_entities`` (so each link gets a
        stable ``entity_id``). Defaults to one lazily built from ``store``'s
        session factory; entity upserts participate in the per-document
        transaction.
    max_child_tokens / overlap_tokens:
        Token-window knobs forwarded to the chunker.
    """

    def __init__(
        self,
        store: DocumentStore,
        embedding_builder: EmbeddingBuilder,
        *,
        linker: EntityLinker | None = None,
        connectors: Mapping[str, SourceConnector] | None = None,
        connector_factory: ConnectorFactory | None = None,
        connector_kwargs: dict[str, Any] | None = None,
        source_resolver: SourceResolver | None = None,
        cleaner: Cleaner | None = None,
        hasher: Hasher | None = None,
        chunker: Chunker | None = None,
        entity_link_mapper: EntityLinkMapper | None = None,
        graph_store: GraphStore | None = None,
        max_child_tokens: int = 380,
        overlap_tokens: int = 48,
    ) -> None:
        if not hasattr(store, "transaction"):
            raise TypeError("store must be a DocumentStore-like object exposing transaction()")
        if not hasattr(embedding_builder, "build"):
            raise TypeError("embedding_builder must expose a build(chunk_ids, chunks) method")

        self._store = store
        self._embedding_builder = embedding_builder
        # Entity-normalization wiring (task 7.6). An explicitly injected linker
        # always wins (DI / tests). Otherwise a default RxNorm/UMLS linker is
        # built ONLY when ``settings.rag_entity_normalization_enabled`` is true;
        # when the flag is off the linker stays ``None`` (no entity linking, the
        # P1 behaviour is unchanged). Construction is defensive: any failure
        # leaves the linker ``None`` so ingestion still runs without links.
        if linker is None and bool(getattr(settings, "rag_entity_normalization_enabled", False)):
            linker = self._build_default_entity_linker()
        self._linker = linker
        self._connectors = dict(connectors) if connectors else None
        self._connector_factory = connector_factory
        self._connector_kwargs = dict(connector_kwargs or {})
        self._source_resolver = source_resolver
        self._clean = cleaner or default_clean
        self._hash = hasher or default_content_hash
        self._chunk = chunker or chunk_document
        # An injected mapper overrides the default graph-backed resolution and
        # is used verbatim (stateless seam). When no mapper is injected the
        # orchestrator resolves entity ids itself via ``GraphStore.upsert_entity``.
        self._custom_link_mapper = entity_link_mapper is not None
        self._entity_link_mapper = entity_link_mapper or _noop_entity_link_mapper
        self._graph_store = graph_store
        self._graph_store_unavailable = False
        self._max_child_tokens = max_child_tokens
        self._overlap_tokens = overlap_tokens

    @staticmethod
    def _build_default_entity_linker() -> EntityLinker | None:
        """Build the default RxNorm/UMLS ``EntityLinker`` (defensive, may be None).

        Constructs a :class:`~clara_ml.rag.normalize.entity_linker.EntityLinker`
        backed by a lazy :class:`~clara_ml.rag.normalize.umls_client.UmlsClient`.
        Neither opens a socket at construction time. Any import/construction
        failure degrades to ``None`` so ingestion proceeds without entity links
        rather than crashing.
        """

        try:
            from clara_ml.rag.normalize.entity_linker import EntityLinker as _RealEntityLinker
            from clara_ml.rag.normalize.umls_client import UmlsClient

            return _RealEntityLinker(UmlsClient(), max_network_lookups=0)
        except Exception as exc:  # pragma: no cover - defensive import guard
            logger.warning(
                "default entity linker unavailable (%s); ingestion runs without entity linking",
                exc.__class__.__name__,
            )
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        source_key: str,
        *,
        since: str | None = None,
        batch_size: int = 100,
    ) -> IngestionReport:
        """Ingest one source: fetch → clean → chunk → embed once → persist.

        Args:
            source_key: The ``kb_source_registry.source_key`` to ingest.
            since: Optional watermark override; when ``None`` the persisted
                per-source ``last_watermark`` is used (resumable).
            batch_size: Records requested per fetch page.

        Returns:
            An :class:`IngestionReport` whose counts satisfy
            ``fetched == inserted + updated + skipped + failed``.

        Raises:
            ValueError: If ``batch_size`` is not positive.
            SourceNotFoundError / SourceDisabledError: From source resolution.
        """

        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        resolution = self._resolve_source(source_key)
        if not resolution.enabled:
            raise SourceDisabledError(f"source_key {source_key!r} is not enabled for ingestion")

        connector = self._build_connector(source_key, resolution.context)
        report = IngestionReport(source_key=source_key)

        # The per-source watermark doubles as the resumable paging cursor and the
        # window lower bound (design.md overloads ``last_watermark`` for both).
        effective_since = since if since is not None else (resolution.watermark or None)
        window = FetchWindow(since=effective_since, page_size=batch_size)
        cursor = effective_since

        while True:
            records, next_cursor = connector.fetch(window, cursor)
            if not records:
                break
            for record in records:
                # Loop invariant: ``fetched`` counts every record exactly once and
                # the store holds a consistent (non-partial) view of prior records.
                report.fetched += 1
                self._process_record(resolution, record, report)

            cursor = next_cursor
            # Resumable checkpoint after each committed batch (Requirement 4.3).
            self._store.checkpoint(resolution.source_id, cursor or "")
            if next_cursor is None:
                break

        report.assert_accounting()
        return report

    def ingest_records(
        self,
        source_key: str,
        records: Sequence[RawRecord],
    ) -> IngestionReport:
        """Persist already-fetched, provenance-checked records without fetching.

        This is the narrow write boundary for trusted live retrieval gap-fill.
        It deliberately does **not** create a connector, advance a source
        watermark, or retain the triggering user query.  Each record still
        takes the same cleaner → chunker → embedding → atomic-store path as
        offline ingestion, including fail-loud handling for degraded vectors.

        Callers must group records by their registry ``source_key``.  Records
        claiming a different source are rejected rather than allowing a live
        provider to smuggle content under another source's authority tier.
        """

        resolution = self._resolve_source(source_key)
        if not resolution.enabled:
            raise SourceDisabledError(f"source_key {source_key!r} is not enabled for ingestion")

        report = IngestionReport(source_key=source_key)
        for record in records:
            if record.source_key != source_key:
                raise ValueError(
                    "live ingestion record source_key does not match the resolved source"
                )
            report.fetched += 1
            self._process_record(resolution, record, report)

        report.assert_accounting()
        return report

    # ------------------------------------------------------------------
    # Per-record processing
    # ------------------------------------------------------------------

    def _process_record(
        self,
        resolution: SourceResolution,
        record: RawRecord,
        report: IngestionReport,
    ) -> None:
        """Clean, idempotency-check, then atomically persist one record."""

        clean_text = self._clean(record.raw_text, lang=record.lang)
        content_hash = self._hash(clean_text)

        # Idempotency: an unchanged record (same content hash) is a no-op.
        if self._store.content_hash_exists(
            resolution.source_id, record.external_id, content_hash
        ):
            report.skipped += 1
            return

        try:
            with self._store.transaction() as session:
                was_existing = self._document_exists(
                    session, resolution.source_id, record.external_id
                )
                self._persist_document(session, resolution, record, clean_text, content_hash)
        except EmbeddingUnavailableError:
            # Production degraded embedding: abort the whole document (fail-loud);
            # the transaction has already rolled back, so no partial doc persists.
            report.failed += 1
            logger.error(
                "ingestion_doc_degraded_abort",
                extra={"source_key": record.source_key, "external_id": record.external_id},
            )
            return
        except Exception as exc:  # noqa: BLE001 - record + continue with the next doc
            report.failed += 1
            logger.error(
                "ingestion_doc_failed",
                extra={
                    "source_key": record.source_key,
                    "external_id": record.external_id,
                    "error": type(exc).__name__,
                },
            )
            return

        if was_existing:
            report.updated += 1
        else:
            report.inserted += 1

    def _persist_document(
        self,
        session: Session,
        resolution: SourceResolution,
        record: RawRecord,
        clean_text: str,
        content_hash: str,
    ) -> None:
        """Persist one document atomically within ``session`` (Requirement 4.4)."""

        chunks = self._chunk(
            record,
            clean_text,
            max_child_tokens=self._max_child_tokens,
            overlap_tokens=self._overlap_tokens,
        )

        document_id = self._store.upsert_document(
            self._to_ingest_doc(resolution, record, content_hash), session=session
        )

        chunk_rows = [self._to_chunk_row(resolution, record, chunk) for chunk in chunks]
        chunk_ids = self._store.upsert_chunks(document_id, chunk_rows, session=session)

        # Embed the whole chunk batch ONCE; the builder raises
        # EmbeddingUnavailableError on a degraded production batch (fail-loud).
        embedding_rows, sparse_rows = self._embedding_builder.build(chunk_ids, chunks)
        self._store.write_embeddings(embedding_rows, session=session)
        self._store.write_sparse_terms(sparse_rows, session=session)

        # Entity linking is wired but no-op by default in P1 (linker is None).
        # When a linker is active (P3, ``RAG_ENTITY_NORMALIZATION_ENABLED``), it
        # runs inside an isolated SAVEPOINT so a linking failure can NEVER abort
        # persistence of this document's chunks (defensive — task 7.6).
        self._maybe_link_entities(session, record, clean_text, chunk_ids, chunks)

    def _maybe_link_entities(
        self,
        session: Session,
        record: RawRecord,
        clean_text: str,
        chunk_ids: list[int],
        chunks: list[Chunk],
    ) -> None:
        """Link + persist entity mentions for a document (defensive, isolated).

        The whole step is wrapped in a nested SAVEPOINT and a broad ``except``:
        if entity linking, entity UPSERT, or link persistence fails, only the
        savepoint is rolled back and the document's already-persisted chunks /
        embeddings remain committed (Requirements 9.1 / 9.4 wiring — a missing
        entity-normalization layer must never lose corpus content).
        """

        if self._linker is None:
            return

        try:
            with session.begin_nested():  # SAVEPOINT: isolate link failures
                entities = list(self._linker.link(clean_text, lang=record.lang) or [])
                if not entities:
                    return
                if self._custom_link_mapper:
                    links = list(self._entity_link_mapper(chunk_ids, chunks, entities))
                else:
                    links = self._graph_backed_links(session, chunk_ids, chunks, entities)
                if links:
                    self._store.link_entities(links, session=session)
        except Exception as exc:  # noqa: BLE001 - links are best-effort; never abort the doc
            logger.warning(
                "ingestion_entity_link_failed",
                extra={
                    "source_key": record.source_key,
                    "external_id": record.external_id,
                    "error": exc.__class__.__name__,
                },
            )

    def _graph_backed_links(
        self,
        session: Session,
        chunk_ids: list[int],
        chunks: list[Chunk],
        entities: Sequence[Any],
    ) -> list[ChunkEntityLink]:
        """Resolve linked entities to ``kb_entities`` ids and map chunk mentions.

        For each :class:`LinkedEntity` the entity is UPSERTed via
        :meth:`GraphStore.upsert_entity` (within the document transaction) to
        obtain a stable ``entity_id``; then every persisted chunk whose text
        token-contains one of the entity's surface names is linked to it. Returns
        an empty list when no graph store is available (links are best-effort).
        """

        graph_store = self._get_graph_store()
        if graph_store is None:
            return []

        # Tokenize each chunk once (chunk_ids align with chunks by order).
        normalized_chunks = [
            (chunk_id, _entity_tokens(chunk.text))
            for chunk_id, chunk in zip(chunk_ids, chunks)
        ]

        links: list[ChunkEntityLink] = []
        for entity in entities:
            names = _entity_surface_names(entity)
            if not names:
                continue
            name_tokens = [(name, _entity_tokens(name)) for name in names]
            name_tokens = [(name, toks) for name, toks in name_tokens if toks]
            if not name_tokens:
                continue

            entity_id = graph_store.upsert_entity(
                EntityInput(
                    canonical_name=(getattr(entity, "canonical_name", None) or None),
                    entity_type=(getattr(entity, "entity_type", "drug") or "drug"),
                    cui=(getattr(entity, "cui", "") or ""),
                    rxcui=(getattr(entity, "rxcui", "") or ""),
                    synonyms=list(getattr(entity, "synonyms", []) or []),
                    source_vocab=_entity_source_vocab(entity),
                ),
                session=session,
            )
            confidence = float(getattr(entity, "confidence", 1.0) or 0.0)

            for chunk_id, chunk_tokens in normalized_chunks:
                if not chunk_tokens:
                    continue
                mention = next(
                    (name for name, toks in name_tokens if _phrase_in_tokens(toks, chunk_tokens)),
                    None,
                )
                if mention is not None:
                    links.append(
                        ChunkEntityLink(
                            chunk_id=chunk_id,
                            entity_id=entity_id,
                            mention_text=mention,
                            confidence=confidence,
                        )
                    )
        return links

    def _get_graph_store(self) -> GraphStore | None:
        """Return the (lazily built, memoized) :class:`GraphStore` or ``None``.

        Reuses the injected graph store when provided; otherwise builds one from
        the document store's session factory so entity UPSERTs share the
        per-document transaction. Any failure (or a store that does not expose a
        session factory) degrades to ``None`` — links are then skipped, never
        crashing ingestion.
        """

        if self._graph_store is not None:
            return self._graph_store
        if self._graph_store_unavailable:
            return None

        factory = getattr(self._store, "_session_factory", None)
        if not callable(factory):
            self._graph_store_unavailable = True
            return None
        try:
            self._graph_store = GraphStore(factory)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "graph store unavailable for entity linking (%s)", exc.__class__.__name__
            )
            self._graph_store_unavailable = True
            return None
        return self._graph_store

    # ------------------------------------------------------------------
    # Mapping helpers (chunking.Chunk / RawRecord -> store rows)
    # ------------------------------------------------------------------

    def _to_ingest_doc(
        self,
        resolution: SourceResolution,
        record: RawRecord,
        content_hash: str,
    ) -> IngestDocument:
        """Map a :class:`RawRecord` + content hash to an :class:`IngestDocument`."""

        context = resolution.context
        return IngestDocument(
            source_id=resolution.source_id,
            content_hash=content_hash,
            trust_tier=record.trust_tier,
            external_id=record.external_id,
            title=record.title,
            url=record.url,
            lang=record.lang,
            doc_type=record.doc_type,
            effective_date=_parse_iso_date(record.effective_date),
            raw_meta={
                "source": context.source_key,
                "source_key": context.source_key,
                "url": record.url,
                "effective_date": record.effective_date,
                "lang": record.lang,
                "license_code": context.license_code,
                "attribution": context.attribution,
                "base_url": context.base_url,
            },
            is_active=True,
        )

    def _to_chunk_row(
        self,
        resolution: SourceResolution,
        record: RawRecord,
        chunk: Chunk,
    ) -> ChunkRow:
        """Map a :class:`~clara_ml.ingestion.chunking.Chunk` to a :class:`ChunkRow`.

        ``chunk_level`` is derived from the parent link (0 for a parent/section
        chunk, 1 for a child window); ``token_count`` is computed with the
        chunker's own deterministic :func:`count_tokens`; ``trust_tier`` comes
        from the record (registry-stamped); ``meta`` threads source provenance.
        """

        return ChunkRow(
            ord=chunk.ord,
            text=chunk.text,
            trust_tier=record.trust_tier,
            parent_ord=chunk.parent_ord,
            chunk_level=0 if chunk.parent_ord is None else 1,
            section_path=chunk.section_path,
            section_type=chunk.section_type,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            token_count=count_tokens(chunk.text),
            lang=chunk.lang,
            meta={
                "source": resolution.context.source_key,
                "external_id": record.external_id,
                "url": record.url,
                "effective_date": record.effective_date,
                "lang": record.lang,
            },
        )

    @staticmethod
    def _document_exists(session: Session, source_id: int, external_id: str) -> bool:
        """Return ``True`` when a document already exists for ``(source_id, external_id)``.

        Used inside the per-document transaction to classify a non-skipped record
        as an ``insert`` (new identity) vs an ``update`` (changed content for an
        existing identity), keeping the report's accounting identity exact.
        """

        found = session.execute(
            select(KbDocument.id)
            .where(
                KbDocument.source_id == source_id,
                KbDocument.external_id == external_id,
            )
            .limit(1)
        ).first()
        return found is not None

    # ------------------------------------------------------------------
    # Source resolution + connector construction
    # ------------------------------------------------------------------

    def _resolve_source(self, source_key: str) -> SourceResolution:
        """Resolve ``source_key`` via the injected resolver or the registry."""

        if self._source_resolver is not None:
            return self._source_resolver(source_key)
        return self._default_resolve_source(source_key)

    def _default_resolve_source(self, source_key: str) -> SourceResolution:
        """Load the ``kb_source_registry`` row through the store's session."""

        with self._store.transaction() as session:
            row = session.execute(
                select(KbSourceRegistry).where(KbSourceRegistry.source_key == source_key)
            ).scalar_one_or_none()
            if row is None:
                raise SourceNotFoundError(
                    f"source_key {source_key!r} not found in kb_source_registry"
                )
            context = ConnectorContext(
                source_key=row.source_key,
                trust_tier=int(row.trust_tier),
                license_code=row.license_code or "",
                attribution=row.attribution or "",
                base_url=row.base_url or "",
                config_json=dict(row.config_json or {}),
            )
            return SourceResolution(
                source_id=int(row.id),
                context=context,
                watermark=row.last_watermark or "",
                enabled=bool(row.enabled),
                display_name=row.display_name or "",
            )

    def _build_connector(
        self,
        source_key: str,
        context: ConnectorContext,
    ) -> SourceConnector:
        """Return the connector for ``source_key`` (injected, factory, or registry)."""

        if self._connectors is not None and source_key in self._connectors:
            return self._connectors[source_key]
        if self._connector_factory is not None:
            return self._connector_factory(source_key, context)
        return build_connector(source_key, context, **self._connector_kwargs)
