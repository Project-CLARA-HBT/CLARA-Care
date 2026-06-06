"""Write / UPSERT adapter for the persistent ``kb_*`` corpus (task 3.1).

This module is the single shared persistence boundary used by the offline
ingestion plane (``ingestion/orchestrator.py`` — task 3.16) and re-used by the
eval harness (task 5.8). It owns *write* access to the corpus tables defined in
:mod:`clara_ml.rag.store.schema`:

``kb_documents``, ``kb_chunks``, ``kb_chunk_embeddings``,
``kb_chunk_sparse_terms``, ``kb_chunk_entities`` and the
``kb_source_registry`` watermark.

Design constraints honoured here:

* **Import-safe.** Importing this module opens no database connection and runs
  no DDL. The store is constructed with a dependency-injected session factory
  (a :class:`sqlalchemy.orm.sessionmaker` or any zero-arg callable returning a
  :class:`~sqlalchemy.orm.Session`). A live database is required only when a
  write method actually executes, so the adapter is unit-testable against an
  in-memory SQLite engine or a session double.
* **Parameterized only.** Every statement goes through the SQLAlchemy ORM /
  Core expression language with bound parameters. No value is ever interpolated
  into a SQL string.
* **Validators at the boundary.** The schema write-invariants
  (:func:`assert_embedding_dim`, :func:`validate_trust_tier`,
  :func:`guard_degraded_row`, :func:`require_model_id`) are enforced *before*
  any row is staged, so an invalid row is rejected and never persisted.
  Validates: Requirements 1.3, 1.5, 2.5, 15.2.
* **Atomic per document.** :meth:`DocumentStore.transaction` yields a session
  whose unit of work commits on success and rolls back on any exception, giving
  the orchestrator all-or-nothing persistence for one document
  (Requirement 4.4).

pgvector note: the dense ``embedding`` column targets pgvector's ``vector``
type. Writes here stay engine-agnostic — the schema's fallback vector type
round-trips a ``list[float]`` to/from pgvector's text form — so the only
pgvector-specific behaviour (the ANN index, ``<=>`` operators) lives on the
*read* path (``hybrid_retriever.py``) and in the migration runner, not here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clara_ml.rag.store.schema import (
    EmbeddingDimMismatchError,
    KbChunk,
    KbChunkEmbedding,
    KbChunkEntity,
    KbChunkSparseTerm,
    KbDocument,
    KbSourceRegistry,
    assert_embedding_dim,
    guard_degraded_row,
    require_model_id,
    validate_trust_tier,
)

__all__ = [
    "IngestDocument",
    "ChunkRow",
    "EmbeddingRow",
    "SparseTermRow",
    "ChunkEntityLink",
    "DocumentStore",
]


# ---------------------------------------------------------------------------
# Input dataclasses (kept here so tasks 3.16 / 5.8 can import them)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class IngestDocument:
    """A normalized source document ready to persist into ``kb_documents``.

    Identity for idempotency is ``(source_id, external_id)`` (the table's unique
    constraint) plus the deterministic ``content_hash`` over the clean text.
    """

    source_id: int
    content_hash: str
    trust_tier: int
    external_id: str = ""
    title: str = ""
    url: str = ""
    lang: str = "en"
    doc_type: str = ""
    effective_date: date | None = None
    raw_meta: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass(slots=True)
class ChunkRow:
    """A structure-aware chunk destined for ``kb_chunks``.

    Parent/child links are expressed by ``parent_ord`` (the ``ord`` of the
    parent chunk *within the same document batch*); the store resolves it to the
    persisted parent id after the rows are flushed. ``parent_ord=None`` marks a
    parent/root chunk.
    """

    ord: int
    text: str
    trust_tier: int
    parent_ord: int | None = None
    chunk_level: int = 0
    section_path: str = ""
    section_type: str = ""
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0
    lang: str = "en"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingRow:
    """A dense embedding destined for ``kb_chunk_embeddings`` (one per chunk)."""

    chunk_id: int
    model_id: str
    dim: int
    embedding: Sequence[float]
    is_degraded: bool = False


@dataclass(slots=True)
class SparseTermRow:
    """A learned-lexical (bge-m3) term -> weight destined for sparse terms."""

    chunk_id: int
    term: str
    weight: float
    model_id: str


@dataclass(slots=True)
class ChunkEntityLink:
    """A chunk <-> entity mention link destined for ``kb_chunk_entities``."""

    chunk_id: int
    entity_id: int
    mention_text: str = ""
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# DocumentStore
# ---------------------------------------------------------------------------


class DocumentStore:
    """Transactional write/UPSERT adapter over the ``kb_*`` corpus.

    Parameters
    ----------
    session_factory:
        A zero-argument callable returning a new :class:`~sqlalchemy.orm.Session`
        — typically a :class:`~sqlalchemy.orm.sessionmaker` or ``services/api``'s
        ``SessionLocal``. Injected so the store never owns engine lifecycle and
        stays import-safe / unit-testable.
    environment:
        Optional override for the effective environment used by the degraded-row
        guard. ``None`` (default) defers to ``settings.environment`` so the
        production fail-loud rule (Requirement 2.5) applies automatically.

    Each write method accepts an optional ``session`` keyword. When a session is
    supplied (e.g. from :meth:`transaction`) the method participates in that
    caller-owned unit of work and does **not** commit; when omitted, the method
    opens, commits, and closes its own short transaction.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        environment: str | None = None,
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be a zero-argument callable returning a Session")
        self._session_factory = session_factory
        self._environment = environment

    # -- construction helpers ------------------------------------------------

    @classmethod
    def from_engine(cls, engine: Engine, *, environment: str | None = None) -> DocumentStore:
        """Build a store from a SQLAlchemy ``Engine`` (no connection opened)."""

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(factory, environment=environment)

    # -- transaction boundary -----------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Yield a session that commits on success and rolls back on error.

        This is the atomic-per-document boundary (Requirement 4.4): pass the
        yielded session into the write methods so all of a document's chunks,
        embeddings, sparse terms and entity links commit together or not at all.
        """

        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _run(self, session: Session | None, work: Callable[[Session], Any]) -> Any:
        """Execute ``work`` on a supplied session or a self-managed transaction."""

        if session is not None:
            return work(session)
        with self.transaction() as managed:
            return work(managed)

    # -- documents -----------------------------------------------------------

    def upsert_document(self, doc: IngestDocument, *, session: Session | None = None) -> int:
        """Insert or update a document; return its ``document_id``.

        Idempotent on ``(source_id, external_id)``: a matching row with the same
        ``content_hash`` is a no-op (its id is returned unchanged); a matching
        row with a different hash is updated in place. Rejects an out-of-range
        ``trust_tier`` (Requirement 1.5).
        """

        tier = validate_trust_tier(doc.trust_tier)

        def work(s: Session) -> int:
            existing = s.execute(
                select(KbDocument).where(
                    KbDocument.source_id == doc.source_id,
                    KbDocument.external_id == doc.external_id,
                )
            ).scalar_one_or_none()

            if existing is not None:
                if existing.content_hash != doc.content_hash:
                    existing.content_hash = doc.content_hash
                    existing.title = doc.title
                    existing.url = doc.url
                    existing.lang = doc.lang
                    existing.doc_type = doc.doc_type
                    existing.trust_tier = tier
                    existing.effective_date = doc.effective_date
                    existing.raw_meta_json = dict(doc.raw_meta)
                    existing.is_active = doc.is_active
                    s.flush()
                return int(existing.id)

            row = KbDocument(
                source_id=doc.source_id,
                external_id=doc.external_id,
                title=doc.title,
                url=doc.url,
                lang=doc.lang,
                doc_type=doc.doc_type,
                trust_tier=tier,
                effective_date=doc.effective_date,
                content_hash=doc.content_hash,
                raw_meta_json=dict(doc.raw_meta),
                is_active=doc.is_active,
            )
            s.add(row)
            s.flush()
            return int(row.id)

        return self._run(session, work)

    def content_hash_exists(
        self,
        source_id: int,
        external_id: str,
        content_hash: str,
        *,
        session: Session | None = None,
    ) -> bool:
        """Return ``True`` when a current row already has this content hash.

        Supports the orchestrator's idempotency check (Requirement 4.1 / 4.2):
        re-ingesting unchanged content is a no-op.
        """

        def work(s: Session) -> bool:
            found = s.execute(
                select(KbDocument.id)
                .where(
                    KbDocument.source_id == source_id,
                    KbDocument.external_id == external_id,
                    KbDocument.content_hash == content_hash,
                )
                .limit(1)
            ).first()
            return found is not None

        return self._run(session, work)

    # -- chunks --------------------------------------------------------------

    def upsert_chunks(
        self,
        document_id: int,
        chunks: Iterable[ChunkRow],
        *,
        session: Session | None = None,
    ) -> list[int]:
        """Replace the chunk set for ``document_id``; return new chunk ids in order.

        The full chunk set for a document is rewritten (existing chunks for the
        document are removed first, cascading to their embeddings / sparse terms
        / entity links) so a re-chunked, changed document persists cleanly. The
        orchestrator only calls this for new or changed documents, so unchanged
        content is never touched. Rejects any chunk whose ``trust_tier`` is
        outside ``{1,2,3,4}`` (Requirement 1.5) before deleting anything.
        """

        rows = list(chunks)
        # Validate every row up-front so a bad row aborts the whole batch
        # without partially mutating the corpus.
        tiers = [validate_trust_tier(c.trust_tier) for c in rows]
        ords = [c.ord for c in rows]
        if len(set(ords)) != len(ords):
            raise ValueError("ChunkRow.ord values must be unique within a document batch")
        ord_set = set(ords)
        for c in rows:
            if c.parent_ord is not None and c.parent_ord not in ord_set:
                raise ValueError(
                    f"ChunkRow.parent_ord {c.parent_ord} does not match any ord in the batch"
                )

        def work(s: Session) -> list[int]:
            # ORM-load + delete so the relationship cascade fires across engines
            # (DB-level ON DELETE CASCADE is not exercised by SQLite in tests).
            existing = (
                s.execute(select(KbChunk).where(KbChunk.document_id == document_id))
                .scalars()
                .all()
            )
            for stale in existing:
                s.delete(stale)
            if existing:
                s.flush()

            models: list[KbChunk] = []
            for c, tier in zip(rows, tiers, strict=True):
                model = KbChunk(
                    document_id=document_id,
                    parent_id=None,
                    chunk_level=c.chunk_level,
                    ord=c.ord,
                    section_path=c.section_path,
                    section_type=c.section_type,
                    text=c.text,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    token_count=c.token_count,
                    lang=c.lang,
                    trust_tier=tier,
                    meta_json=dict(c.meta),
                )
                s.add(model)
                models.append(model)
            s.flush()  # assign autoincrement ids

            ord_to_id = {c.ord: m.id for c, m in zip(rows, models, strict=True)}
            needs_parent = False
            for c, model in zip(rows, models, strict=True):
                if c.parent_ord is not None:
                    model.parent_id = ord_to_id[c.parent_ord]
                    needs_parent = True
            if needs_parent:
                s.flush()

            return [int(m.id) for m in models]

        return self._run(session, work)

    # -- embeddings ----------------------------------------------------------

    def write_embeddings(
        self,
        rows: Iterable[EmbeddingRow],
        *,
        session: Session | None = None,
    ) -> None:
        """UPSERT dense embedding rows (one per chunk) into ``kb_chunk_embeddings``.

        Enforces, per row and before staging anything:

        * ``dim == RAG_EMBEDDING_DIM`` and ``len(embedding) == dim``
          (Requirement 1.3) — :func:`assert_embedding_dim`;
        * a non-empty ``model_id`` discriminator (Requirement 1.4) —
          :func:`require_model_id`;
        * no ``is_degraded`` row in production (Requirement 2.5) —
          :func:`guard_degraded_row`.
        """

        validated: list[tuple[EmbeddingRow, int, str, bool]] = []
        for row in rows:
            dim = assert_embedding_dim(row.dim)
            vector = list(row.embedding)
            if len(vector) != dim:
                raise EmbeddingDimMismatchError(
                    f"embedding vector length {len(vector)} != declared dim {dim}"
                )
            model_id = require_model_id(row.model_id)
            degraded = guard_degraded_row(row.is_degraded, environment=self._environment)
            validated.append((row, dim, model_id, degraded))

        def work(s: Session) -> None:
            for row, dim, model_id, degraded in validated:
                existing = s.get(KbChunkEmbedding, row.chunk_id)
                vector = list(row.embedding)
                if existing is not None:
                    existing.model_id = model_id
                    existing.dim = dim
                    existing.embedding = vector
                    existing.is_degraded = degraded
                else:
                    s.add(
                        KbChunkEmbedding(
                            chunk_id=row.chunk_id,
                            model_id=model_id,
                            dim=dim,
                            embedding=vector,
                            is_degraded=degraded,
                        )
                    )
            s.flush()

        self._run(session, work)

    # -- sparse terms --------------------------------------------------------

    def write_sparse_terms(
        self,
        rows: Iterable[SparseTermRow],
        *,
        session: Session | None = None,
    ) -> None:
        """Replace the bge-m3 sparse term rows for the affected chunks.

        Existing terms for any chunk referenced in ``rows`` are cleared first so
        re-embedding a chunk is idempotent. Requires a non-empty ``model_id`` on
        every row (Requirement 1.4).
        """

        staged = list(rows)
        for row in staged:
            require_model_id(row.model_id)
        chunk_ids = sorted({row.chunk_id for row in staged})

        def work(s: Session) -> None:
            if chunk_ids:
                s.execute(
                    delete(KbChunkSparseTerm).where(KbChunkSparseTerm.chunk_id.in_(chunk_ids))
                )
            for row in staged:
                s.add(
                    KbChunkSparseTerm(
                        chunk_id=row.chunk_id,
                        term=row.term,
                        weight=float(row.weight),
                        model_id=require_model_id(row.model_id),
                    )
                )
            s.flush()

        self._run(session, work)

    # -- entity links --------------------------------------------------------

    def link_entities(
        self,
        links: Iterable[ChunkEntityLink],
        *,
        session: Session | None = None,
    ) -> None:
        """UPSERT chunk <-> entity mention links into ``kb_chunk_entities``."""

        staged = list(links)

        def work(s: Session) -> None:
            for link in staged:
                existing = s.get(KbChunkEntity, (link.chunk_id, link.entity_id))
                if existing is not None:
                    existing.mention_text = link.mention_text
                    existing.confidence = float(link.confidence)
                else:
                    s.add(
                        KbChunkEntity(
                            chunk_id=link.chunk_id,
                            entity_id=link.entity_id,
                            mention_text=link.mention_text,
                            confidence=float(link.confidence),
                        )
                    )
            s.flush()

        self._run(session, work)

    # -- watermark / resumability -------------------------------------------

    def checkpoint(
        self,
        source_id: int,
        cursor: str,
        *,
        session: Session | None = None,
    ) -> None:
        """Persist the resumable watermark for a source (Requirement 4.3 / 4.6).

        Updates ``kb_source_registry.last_watermark`` and ``last_run_at`` for the
        given source so an interrupted ingestion run resumes from here.
        """

        watermark = "" if cursor is None else str(cursor)

        def work(s: Session) -> None:
            registry = s.get(KbSourceRegistry, source_id)
            if registry is None:
                raise ValueError(f"unknown source_id {source_id!r} in kb_source_registry")
            registry.last_watermark = watermark
            registry.last_run_at = func.now()
            s.flush()

        self._run(session, work)
