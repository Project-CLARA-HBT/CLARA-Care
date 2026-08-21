"""Property-based test for no degraded persistence in production (Property 10).

Feature: rag-knowledge-pipeline, task 3.20 (optional test).

**Validates: Requirements 2.4, 2.5**

Design reference (design.md -> Correctness Properties):
    Property 10: No degraded persistence. In production, a chunk whose embedding
    is degraded is NEVER persisted. The Ingestion_Orchestrator aborts the whole
    document on a degraded embedding (counting it as ``failed``), and the
    Document_Store write boundary rejects any degraded embedding row.

Requirements exercised:
    2.4  IF a degraded embedding is produced during ingestion WHILE
         ``environment`` is ``production``, THEN THE Ingestion_Orchestrator SHALL
         abort the current document and persist no embedding row for it.
    2.5  WHILE ``environment`` is ``production``, THE Document_Store SHALL hold no
         ``kb_chunk_embeddings`` row with ``is_degraded = true``.

The property is proven from two complementary angles, each varying *which* chunk
of a document carries the degraded embedding (Hypothesis, >= 100 iterations):

Part A — orchestrator abort + atomic rollback (Requirement 2.4).
    Drives the REAL :class:`clara_ml.ingestion.orchestrator.IngestionOrchestrator`
    and the REAL :class:`clara_ml.ingestion.embedding_builder.EmbeddingBuilder`
    (pinned to ``environment='production'``) against fully in-memory doubles
    reused from task 3.17: a transactional Document_Store fake whose
    ``transaction()`` faithfully rolls back partial writes on error, a connector
    fake, and an embed-once client fake that marks one chosen chunk per document
    degraded. When a document's batch is degraded the real builder raises
    :class:`~clara_ml.rag.embedder.EmbeddingUnavailableError` (production
    fail-loud), the orchestrator aborts that document (counted as ``failed``),
    the per-document transaction rolls back, and NOTHING for that document is
    persisted -- no document row, no chunks, and no embedding row. Clean
    documents in the same run persist normally, and the corpus holds zero
    degraded embedding rows.

Part B — store boundary rejection (Requirement 2.5).
    Calls the REAL :class:`~clara_ml.rag.store.document_store.DocumentStore`
    write boundary (``write_embeddings``) in ``environment='production'`` with a
    batch in which exactly one (varying) row is degraded, and asserts the write
    is rejected with :class:`~clara_ml.rag.store.schema.DegradedEmbeddingNotAllowedError`
    *before any database access* (the injected session factory is wired to fail
    if ever called), so a degraded row can never reach the table.

No database connection or network request is made anywhere in this module.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.connectors.base import ConnectorContext, FetchWindow, RawRecord
from clara_ml.ingestion.embedding_builder import EmbeddingBuilder
from clara_ml.ingestion.orchestrator import IngestionOrchestrator, SourceResolution
from clara_ml.rag.embedder import EmbedBatchResult
from clara_ml.rag.store.document_store import DocumentStore, EmbeddingRow
from clara_ml.rag.store.schema import (
    DegradedEmbeddingNotAllowedError,
    configured_embedding_dim,
    guard_degraded_row,
)

_SOURCE_KEY = "fake-source"
_SOURCE_ID = 1
_EMB_MODEL_ID = "fake-emb"
# Small dense vector for the in-memory store (the fake store does not validate
# the dimension -- the production fail-loud abort happens before any row is
# emitted, so the vector width is irrelevant to Part A).
_CLIENT_DIM = 8

# A stable, PII-free, non-boilerplate sentence prepended to every generated
# document so the real Cleaner leaves non-whitespace content and the real
# Structure_Aware_Chunker always yields >= 1 chunk. That guarantees the embedding
# builder (hence the embed client) is invoked exactly once per record, in record
# order, so each client call maps unambiguously back to its document.
_STABLE_PARA = "Clinical guideline overview paragraph for ingestion coverage."


# ---------------------------------------------------------------------------
# In-memory doubles (no DB / no network) -- transactional, with rollback
# ---------------------------------------------------------------------------


def _eq_param(params: dict[str, Any], column: str) -> Any:
    """Pull the bound value for ``column`` from a compiled statement's params."""

    for key, value in params.items():
        if key == column or key.startswith(column + "_"):
            return value
    return None


class _FakeResult:
    """Minimal stand-in for a SQLAlchemy ``Result`` (only ``.first()`` is used)."""

    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def first(self) -> tuple[Any, ...] | None:
        return self._row


class _FakeSession:
    """Session double answering the orchestrator's document-existence probe.

    Inside a document transaction the orchestrator runs exactly one read on the
    session: ``_document_exists`` -> ``session.execute(select(...))``. We decode
    the ``(source_id, external_id)`` from the compiled statement and answer from
    the store's committed state, mirroring the real query.
    """

    def __init__(self, store: FakeDocumentStore) -> None:
        self._store = store

    def execute(self, statement: Any) -> _FakeResult:
        try:
            params = dict(statement.compile().params)
        except Exception:  # pragma: no cover - defensive; not expected here
            params = {}
        source_id = _eq_param(params, "source_id")
        external_id = _eq_param(params, "external_id")
        doc = self._store.documents.get((source_id, external_id))
        return _FakeResult((doc["id"],) if doc is not None else None)


class FakeDocumentStore:
    """Transactional in-memory model of the ``DocumentStore`` write contract.

    Implements only the surface the orchestrator calls and, crucially for
    Property 10, models the atomic-per-document boundary (Requirement 4.4): the
    :meth:`transaction` context snapshots the persisted corpus on entry and
    restores it on any exception, so a document aborted mid-persist (e.g. by a
    degraded-embedding fail-loud) leaves NO partial rows behind -- not the
    document, not its chunks, not its embeddings. This is exactly the guarantee
    Requirement 2.4 relies on.
    """

    def __init__(self) -> None:
        self.documents: dict[tuple[int, str], dict[str, Any]] = {}
        self.chunks: dict[int, list[dict[str, Any]]] = {}
        self.embeddings: dict[int, tuple[Any, ...]] = {}
        self.sparse: dict[int, list[tuple[str, float, str]]] = {}
        self.watermarks: dict[int, str] = {}
        self._next_doc_id = 0
        self._next_chunk_id = 0

    # -- transaction with faithful rollback ---------------------------------

    def _capture(self) -> tuple[Any, ...]:
        return (
            copy.deepcopy(self.documents),
            copy.deepcopy(self.chunks),
            copy.deepcopy(self.embeddings),
            copy.deepcopy(self.sparse),
        )

    def _restore(self, snap: tuple[Any, ...]) -> None:
        # Restore the data maps only; the id counters intentionally keep
        # advancing (mirroring a real DB sequence: rolled-back ids leave gaps,
        # never reused), which keeps persisted ids globally unique.
        self.documents, self.chunks, self.embeddings, self.sparse = (
            snap[0],
            snap[1],
            snap[2],
            snap[3],
        )

    @contextmanager
    def transaction(self):
        snapshot = self._capture()
        try:
            yield _FakeSession(self)
        except Exception:
            self._restore(snapshot)  # all-or-nothing per document (Req 4.4)
            raise

    # -- write surface ------------------------------------------------------

    def content_hash_exists(
        self,
        source_id: int,
        external_id: str,
        content_hash: str,
        *,
        session: Any | None = None,
    ) -> bool:
        doc = self.documents.get((source_id, external_id))
        return doc is not None and doc["content_hash"] == content_hash

    def upsert_document(self, doc: Any, *, session: Any | None = None) -> int:
        key = (doc.source_id, doc.external_id)
        existing = self.documents.get(key)
        if existing is not None:
            existing["content_hash"] = doc.content_hash
            existing["trust_tier"] = doc.trust_tier
            return int(existing["id"])
        self._next_doc_id += 1
        doc_id = self._next_doc_id
        self.documents[key] = {
            "id": doc_id,
            "content_hash": doc.content_hash,
            "trust_tier": doc.trust_tier,
        }
        return doc_id

    def upsert_chunks(
        self,
        document_id: int,
        chunks: Any,
        *,
        session: Any | None = None,
    ) -> list[int]:
        stored: list[dict[str, Any]] = []
        ids: list[int] = []
        for c in list(chunks):
            self._next_chunk_id += 1
            cid = self._next_chunk_id
            ids.append(cid)
            stored.append(
                {
                    "chunk_id": cid,
                    "ord": c.ord,
                    "parent_ord": c.parent_ord,
                    "text": c.text,
                    "section_type": c.section_type,
                    "token_count": c.token_count,
                    "trust_tier": c.trust_tier,
                }
            )
        self.chunks[document_id] = stored
        return ids

    def write_embeddings(self, rows: Any, *, session: Any | None = None) -> None:
        for r in rows:
            self.embeddings[r.chunk_id] = (
                r.model_id,
                int(r.dim),
                tuple(float(x) for x in r.embedding),
                bool(r.is_degraded),
            )

    def write_sparse_terms(self, rows: Any, *, session: Any | None = None) -> None:
        staged = list(rows)
        for cid in {r.chunk_id for r in staged}:
            self.sparse[cid] = []
        for r in staged:
            self.sparse.setdefault(r.chunk_id, []).append(
                (r.term, round(float(r.weight), 6), r.model_id)
            )

    def checkpoint(self, source_id: int, cursor: str, *, session: Any | None = None) -> None:
        self.watermarks[source_id] = "" if cursor is None else str(cursor)

    # -- test helpers -------------------------------------------------------

    def total_chunks(self) -> int:
        return sum(len(rows) for rows in self.chunks.values())

    def has_degraded_embeddings(self) -> bool:
        """True if any persisted embedding row carries ``is_degraded == True``."""

        return any(row[3] for row in self.embeddings.values())

    def chunk_ids_for_document(self, doc_id: int) -> list[int]:
        return [ch["chunk_id"] for ch in self.chunks.get(doc_id, [])]


class FakeConnector:
    """Connector double that re-emits a fixed record set in one fetch page."""

    def __init__(self, context: ConnectorContext, records: list[RawRecord]) -> None:
        self.context = context
        self._records = list(records)

    def fetch(self, window: FetchWindow, cursor: str | None = None):
        return (list(self._records), None)


class PlannedEmbeddingClient:
    """Embed-once client fake that marks one chosen chunk per document degraded.

    ``plans[i]`` is the degrade selector for the i-th ``embed_documents`` call
    (one call per document, in record order): ``None`` yields an all-clean batch;
    an integer ``j`` degrades the chunk at position ``j % len(texts)`` so *which*
    chunk is degraded varies across Hypothesis examples (the core of Property
    10). Records ``any(degraded)`` per call so the test can map each call back to
    its document and predict the orchestrator's accounting exactly.
    """

    def __init__(self, plans: list[int | None], *, dim: int = _CLIENT_DIM) -> None:
        self._plans = list(plans)
        self._dim = dim
        self.calls = 0
        self.degraded_calls: list[bool] = []

    def embed_documents(self, texts: list[str]) -> EmbedBatchResult:
        idx = self.calls
        self.calls += 1
        plan = self._plans[idx] if idx < len(self._plans) else None
        n = len(texts)
        degraded = [False] * n
        if plan is not None and n > 0:
            degraded[plan % n] = True
        self.degraded_calls.append(any(degraded))
        vectors = [[0.0] * self._dim for _ in range(n)]
        return EmbedBatchResult(vectors=vectors, degraded=degraded)


def _build_orchestrator(
    store: FakeDocumentStore,
    records: list[RawRecord],
    client: PlannedEmbeddingClient,
) -> IngestionOrchestrator:
    context = ConnectorContext(source_key=_SOURCE_KEY, trust_tier=1)
    connector = FakeConnector(context, records)

    def resolver(source_key: str) -> SourceResolution:
        return SourceResolution(
            source_id=_SOURCE_ID,
            context=context,
            watermark="",
            enabled=True,
            display_name="Fake Source",
        )

    # The REAL EmbeddingBuilder pinned to production -- it converts a degraded
    # client batch into EmbeddingUnavailableError (production fail-loud) so the
    # orchestrator's real abort path is exercised end to end.
    builder = EmbeddingBuilder(client, model_id=_EMB_MODEL_ID, environment="production")
    return IngestionOrchestrator(
        store,
        builder,
        connectors={_SOURCE_KEY: connector},
        source_resolver=resolver,
    )


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

# Vietnamese letters so cleaning/hashing/chunking are exercised on combining
# unicode, not just ASCII.
_VIETNAMESE = "ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ"

# Heading-like fragments to trigger SPL / guideline section tiling (so multi-
# chunk documents, not just a single tile, are produced -- giving more than one
# candidate chunk position to degrade).
_HEADINGS = [
    "DRUG INTERACTIONS",
    "CONTRAINDICATIONS",
    "INDICATIONS AND USAGE",
    "BOXED WARNING",
    "DOSAGE AND ADMINISTRATION",
    "WARNINGS",
    "# Heading",
    "1. Introduction",
    "1.2 Dosing",
]

_fragment = st.one_of(
    st.sampled_from(_HEADINGS),
    st.sampled_from([" ", "  ", "\t", "\n", "\n\n"]),
    st.text(
        alphabet=st.one_of(
            st.sampled_from(list(_VIETNAMESE)),
            st.characters(min_codepoint=0x20, max_codepoint=0x2FF),
        ),
        max_size=24,
    ),
)

_raw_body = st.lists(_fragment, max_size=6).map("\n".join)

_record_spec = st.fixed_dictionaries(
    {
        "raw_body": _raw_body,
        "lang": st.sampled_from(["vi", "en"]),
        "doc_type": st.sampled_from(["spl_label", "guideline", "other", ""]),
        "trust_tier": st.sampled_from([1, 2, 3, 4]),
        "title": st.text(max_size=16),
        "url": st.text(max_size=16),
    }
)


@st.composite
def _records_and_plans(draw: st.DrawFn) -> tuple[list[RawRecord], list[int | None]]:
    """Draw a source record set plus a per-document degrade plan (aligned)."""

    specs = draw(st.lists(_record_spec, min_size=1, max_size=5))
    records: list[RawRecord] = []
    plans: list[int | None] = []
    for i, spec in enumerate(specs):
        raw_text = _STABLE_PARA + "\n" + spec["raw_body"]
        records.append(
            RawRecord(
                source_key=_SOURCE_KEY,
                external_id=f"doc-{i}",
                title=spec["title"],
                url=spec["url"],
                lang=spec["lang"],
                doc_type=spec["doc_type"],
                raw_text=raw_text,
                effective_date=None,
                trust_tier=spec["trust_tier"],
            )
        )
        # None => clean document; int => degrade chunk at (j % n_chunks).
        plans.append(draw(st.one_of(st.none(), st.integers(min_value=0, max_value=11))))
    return records, plans


# ---------------------------------------------------------------------------
# Part A — orchestrator aborts a degraded document; nothing persists (Req 2.4)
# ---------------------------------------------------------------------------


@settings(max_examples=150, deadline=None)
@given(records_and_plans=_records_and_plans())
def test_no_degraded_document_is_ever_persisted_in_production(
    records_and_plans: tuple[list[RawRecord], list[int | None]],
) -> None:
    """Property 10 / Req 2.4, 2.5: a degraded document never persists in prod.

    For every document whose embedding batch contains a degraded vector, the
    orchestrator aborts the document (counts it ``failed``) and the per-document
    transaction rolls back, leaving no document/chunk/embedding rows. Clean
    documents persist normally, and the corpus holds zero degraded embedding
    rows. Which chunk position is degraded varies across examples.
    """

    records, plans = records_and_plans
    store = FakeDocumentStore()
    client = PlannedEmbeddingClient(plans)
    orchestrator = _build_orchestrator(store, records, client)

    report = orchestrator.run(_SOURCE_KEY)

    # The stable paragraph guarantees >= 1 chunk per document, so the embedding
    # builder (hence the client) is invoked exactly once per record, in order.
    assert client.calls == len(records)
    assert len(client.degraded_calls) == len(records)

    expected_failed = sum(client.degraded_calls)
    expected_inserted = len(records) - expected_failed

    # Accounting identity (Req 4.5) and the exact disposition of each record.
    assert report.fetched == len(records)
    assert report.skipped == 0
    assert report.updated == 0
    assert report.failed == expected_failed
    assert report.inserted == expected_inserted
    assert report.accounting_holds()

    # Req 2.5: the persisted corpus holds NO degraded embedding row.
    assert not store.has_degraded_embeddings()

    # No orphan embedding may reference a chunk that is not persisted (a degraded
    # document's chunks + embeddings must vanish together on rollback).
    persisted_chunk_ids = {
        cid for doc in store.documents.values() for cid in store.chunk_ids_for_document(doc["id"])
    }
    assert set(store.embeddings).issubset(persisted_chunk_ids)

    for i, record in enumerate(records):
        key = (_SOURCE_ID, record.external_id)
        if client.degraded_calls[i]:
            # Req 2.4: the aborted document persists nothing at all.
            assert key not in store.documents, "degraded document must not be persisted"
        else:
            # A clean document persists with a non-degraded embedding per chunk.
            assert key in store.documents
            doc_id = store.documents[key]["id"]
            chunk_ids = store.chunk_ids_for_document(doc_id)
            assert chunk_ids, "clean document must persist at least one chunk"
            for cid in chunk_ids:
                emb = store.embeddings.get(cid)
                assert emb is not None, "clean chunk must carry an embedding row"
                assert emb[3] is False, "clean chunk embedding must not be degraded"


def test_degraded_document_abort_concrete_example() -> None:
    """Concrete two-document case: the degraded one aborts, the clean one persists.

    Pins the readable behaviour behind Property 10: with one document degraded
    and one clean, production ingestion reports ``failed == 1`` / ``inserted ==
    1``, persists only the clean document, and stores no degraded embedding row.
    """

    records = [
        RawRecord(
            source_key=_SOURCE_KEY,
            external_id="spl-degraded",
            title="Amoxicillin label",
            url="https://example.test/spl-degraded",
            lang="en",
            doc_type="spl_label",
            raw_text=(
                "INDICATIONS AND USAGE\n"
                "Amoxicillin is indicated for bacterial infections.\n"
                "DRUG INTERACTIONS\n"
                "May interact with probenecid.\n"
            ),
            effective_date="2022-01-01",
            trust_tier=1,
        ),
        RawRecord(
            source_key=_SOURCE_KEY,
            external_id="vn-clean",
            title="Huong dan dieu tri",
            url="https://example.test/guide-clean",
            lang="vi",
            doc_type="guideline",
            raw_text="# Tong quan\nThuoc duoc su dung de dieu tri benh.\n",
            effective_date=None,
            trust_tier=3,
        ),
    ]

    store = FakeDocumentStore()
    # First document degraded (chunk 0), second document clean.
    client = PlannedEmbeddingClient([0, None])
    orchestrator = _build_orchestrator(store, records, client)

    report = orchestrator.run(_SOURCE_KEY)

    assert report.fetched == 2
    assert report.failed == 1
    assert report.inserted == 1
    assert report.skipped == 0
    assert report.accounting_holds()

    # The degraded document persisted nothing; the clean one persisted fully.
    assert (_SOURCE_ID, "spl-degraded") not in store.documents
    assert (_SOURCE_ID, "vn-clean") in store.documents
    assert not store.has_degraded_embeddings()


# ---------------------------------------------------------------------------
# Part B — store boundary rejects any degraded row in production (Req 2.5)
# ---------------------------------------------------------------------------


def _raising_session_factory() -> Any:
    """A session factory that must never be called.

    The degraded-row guard runs at the write boundary *before* any database
    access, so reaching this factory means a degraded row slipped past the
    boundary -- the AssertionError makes that failure unmistakable.
    """

    raise AssertionError(
        "session_factory must not be called: a degraded embedding row must be "
        "rejected at the store boundary before any database access"
    )


@st.composite
def _degraded_batch_shape(draw: st.DrawFn) -> tuple[int, int]:
    """Draw ``(batch_size, degraded_index)`` with the index inside the batch."""

    n = draw(st.integers(min_value=1, max_value=4))
    idx = draw(st.integers(min_value=0, max_value=n - 1))
    return n, idx


@settings(max_examples=120, deadline=None)
@given(shape=_degraded_batch_shape())
def test_store_boundary_rejects_degraded_embedding_row_in_production(
    shape: tuple[int, int],
) -> None:
    """Property 10 / Req 2.5: ``write_embeddings`` rejects any degraded row in prod.

    A batch of otherwise-valid embedding rows with exactly one degraded row (at a
    varying position) is rejected by the real Document_Store boundary with
    :class:`DegradedEmbeddingNotAllowedError`, before any database access.
    """

    batch_size, degraded_idx = shape
    dim = configured_embedding_dim()
    store = DocumentStore(_raising_session_factory, environment="production")

    rows = [
        EmbeddingRow(
            chunk_id=i + 1,
            model_id=_EMB_MODEL_ID,
            dim=dim,
            embedding=[0.0] * dim,
            is_degraded=(i == degraded_idx),
        )
        for i in range(batch_size)
    ]

    with pytest.raises(DegradedEmbeddingNotAllowedError):
        store.write_embeddings(rows)


def test_store_degraded_guard_semantics_concrete() -> None:
    """Concrete guard semantics: degraded rejected only in production.

    Documents the boundary's intent succinctly -- a degraded flag is allowed in
    non-production (explicit degraded mode) but rejected in production
    (Requirements 2.4 / 2.5), while a clean flag is always allowed.
    """

    assert guard_degraded_row(False, environment="production") is False
    assert guard_degraded_row(True, environment="staging") is True
    assert guard_degraded_row(True, environment="development") is True
    with pytest.raises(DegradedEmbeddingNotAllowedError):
        guard_degraded_row(True, environment="production")
