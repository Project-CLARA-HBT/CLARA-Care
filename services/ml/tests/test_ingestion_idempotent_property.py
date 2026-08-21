"""Property-based test for idempotent ingestion (Property 5).

Feature: rag-knowledge-pipeline, task 3.17 (optional test).

**Validates: Requirements 4.1, 4.2**

Design reference (design.md -> Correctness Properties):
    Property 5: Idempotent ingestion. Running ingestion twice over identical
    upstream data results in the same persisted chunk set (second run inserts 0
    new chunks; ``skipped == fetched``).

Requirements exercised:
    4.1  WHEN ingestion runs a second time over identical upstream data, THE
         Ingestion_Orchestrator SHALL insert zero new chunks and SHALL report
         ``skipped`` equal to ``fetched``.
    4.2  WHEN a record's ``content_hash`` already exists for its source and
         external id, THE Ingestion_Orchestrator SHALL skip the record, using a
         ``content_hash`` that is deterministic over the normalized clean text.

This drives the REAL :class:`clara_ml.ingestion.orchestrator.IngestionOrchestrator`
(real cleaner, real ``content_hash``, real Structure_Aware_Chunker) against fully
in-memory doubles for the three injected collaborators it touches at the write
boundary -- the Document_Store, the source connector, and the embedding builder
-- so no database connection or network request is made. The in-memory store
faithfully models the real :class:`~clara_ml.rag.store.document_store.DocumentStore`
idempotency contract: ``content_hash_exists`` is true iff a row already exists
for ``(source_id, external_id)`` carrying that exact content hash, which is the
exact signal the orchestrator's skip path depends on.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from contextlib import contextmanager
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.connectors.base import ConnectorContext, FetchWindow, RawRecord
from clara_ml.ingestion.orchestrator import IngestionOrchestrator, SourceResolution
from clara_ml.rag.store.document_store import EmbeddingRow, SparseTermRow

_SOURCE_KEY = "fake-source"
_SOURCE_ID = 1
_EMB_MODEL_ID = "fake-emb"
_EMB_DIM = 8


# ---------------------------------------------------------------------------
# In-memory doubles (no DB / no network)
# ---------------------------------------------------------------------------


def _eq_param(params: dict[str, Any], column: str) -> Any:
    """Pull the bound value for ``column`` out of a compiled statement's params.

    ``IngestionOrchestrator._document_exists`` issues
    ``select(KbDocument.id).where(source_id == .., external_id == ..)``; the
    bound parameter for an equality filter is named after its column (e.g.
    ``source_id`` or ``source_id_1``). This matches either spelling while
    ignoring unrelated params (such as the ``LIMIT`` value).
    """

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
    """Session double whose only job is to answer the document-existence probe.

    The orchestrator runs exactly one read on the session it is handed inside a
    document transaction: ``_document_exists`` -> ``session.execute(select(...))``.
    We decode the ``(source_id, external_id)`` from the compiled statement and
    answer from the store's committed state, mirroring the real query.
    """

    def __init__(self, store: FakeDocumentStore) -> None:
        self._store = store

    def execute(self, statement: Any) -> _FakeResult:
        try:
            params = dict(statement.compile().params)
        except Exception:  # pragma: no cover - defensive; not expected in this test
            params = {}
        source_id = _eq_param(params, "source_id")
        external_id = _eq_param(params, "external_id")
        doc = self._store.documents.get((source_id, external_id))
        return _FakeResult((doc["id"],) if doc is not None else None)


class FakeDocumentStore:
    """Faithful in-memory model of the ``DocumentStore`` write/idempotency contract.

    Implements only the surface the orchestrator calls (``transaction``,
    ``content_hash_exists``, ``upsert_document``, ``upsert_chunks``,
    ``write_embeddings``, ``write_sparse_terms``, ``checkpoint``) and keeps the
    persisted corpus in plain dicts so a snapshot can be compared across runs.
    """

    def __init__(self) -> None:
        self.documents: dict[tuple[int, str], dict[str, Any]] = {}
        self.chunks: dict[int, list[dict[str, Any]]] = {}
        self.embeddings: dict[int, tuple[Any, ...]] = {}
        self.sparse: dict[int, list[tuple[str, float, str]]] = {}
        self.watermarks: dict[int, str] = {}
        self._next_doc_id = 0
        self._next_chunk_id = 0

    @contextmanager
    def transaction(self):
        # Property 5 exercises only the happy path (no mid-document failures),
        # so writes apply immediately; each record commits before the next one,
        # which is exactly what the real per-document transaction guarantees.
        yield _FakeSession(self)

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
        rows = list(chunks)
        stored: list[dict[str, Any]] = []
        ids: list[int] = []
        for c in rows:
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
        # Replace the chunk set for the document (mirrors the real store).
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

    # -- test helpers --------------------------------------------------------

    def total_chunks(self) -> int:
        return sum(len(rows) for rows in self.chunks.values())

    def snapshot(self) -> dict[tuple[int, str], Any]:
        """An id-stable, deep snapshot of the persisted corpus for equality checks."""

        snap: dict[tuple[int, str], Any] = {}
        for (source_id, external_id), doc in self.documents.items():
            doc_id = doc["id"]
            entries = []
            for ch in self.chunks.get(doc_id, []):
                cid = ch["chunk_id"]
                entries.append(
                    (
                        ch["ord"],
                        ch["parent_ord"],
                        ch["text"],
                        ch["section_type"],
                        ch["token_count"],
                        ch["trust_tier"],
                        self.embeddings.get(cid),
                        tuple(sorted(self.sparse.get(cid, []))),
                    )
                )
            entries.sort(key=lambda e: e[0])
            snap[(source_id, external_id)] = {
                "content_hash": doc["content_hash"],
                "trust_tier": doc["trust_tier"],
                "chunks": tuple(entries),
            }
        return snap


class FakeConnector:
    """Connector double that re-emits a fixed record set (identical upstream data).

    Returns the whole set on the first (cursor-less) fetch with ``next_cursor``
    of ``None`` so the orchestrator processes the set exactly once per ``run``.
    Re-running ``run`` re-emits the identical records -- the "twice over
    identical upstream data" precondition of Property 5.
    """

    def __init__(self, context: ConnectorContext, records: list[RawRecord]) -> None:
        self.context = context
        self._records = list(records)

    def fetch(self, window: FetchWindow, cursor: str | None = None):
        return (list(self._records), None)


def _fake_vector(text: str, dim: int = _EMB_DIM) -> list[float]:
    """Deterministic dense vector derived from chunk text (content-stable)."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(dim)]


class FakeEmbeddingBuilder:
    """Embedding-builder double: deterministic dense + sparse rows, embed-once.

    Mirrors the real builder's call contract -- ``build(chunk_ids, chunks)``
    returns ``(embedding_rows, sparse_rows)`` with ``chunk_ids[i]`` aligned to
    ``chunks[i]`` -- and produces content-derived rows so the persisted corpus is
    deterministic across runs. No network is used.
    """

    def build(self, chunk_ids: list[int], chunks: list[Any]):
        emb_rows: list[EmbeddingRow] = []
        sparse_rows: list[SparseTermRow] = []
        for cid, chunk in zip(chunk_ids, chunks, strict=True):
            emb_rows.append(
                EmbeddingRow(
                    chunk_id=cid,
                    model_id=_EMB_MODEL_ID,
                    dim=_EMB_DIM,
                    embedding=_fake_vector(chunk.text),
                    is_degraded=False,
                )
            )
            tokens = chunk.text.split()
            total = len(tokens) or 1
            for term, count in Counter(t.lower() for t in tokens).items():
                sparse_rows.append(
                    SparseTermRow(
                        chunk_id=cid,
                        term=term,
                        weight=round(count / total, 6),
                        model_id=_EMB_MODEL_ID,
                    )
                )
        return (emb_rows, sparse_rows)


def _build_orchestrator(store: FakeDocumentStore, records: list[RawRecord]) -> IngestionOrchestrator:
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

    return IngestionOrchestrator(
        store,
        FakeEmbeddingBuilder(),
        connectors={_SOURCE_KEY: connector},
        source_resolver=resolver,
    )


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

# Vietnamese letters so cleaning/hashing/chunking are exercised on combining
# unicode, not just ASCII (the content hash must stay stable across runs).
_VIETNAMESE = "ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ"

# Heading-like fragments to trigger SPL / guideline section tiling (so multi-
# chunk documents, not just a single "other" tile, are persisted).
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

# PII-like fragments so the redaction step (which runs last in cleaning) is part
# of the hashed clean_text -- idempotency must hold over redacted content too.
_PII_LIKE = ["call 0987654321 now", "contact me at user@example.com"]

_fragment = st.one_of(
    st.sampled_from(_HEADINGS),
    st.sampled_from(_PII_LIKE),
    st.sampled_from([" ", "  ", "\t", "\n", "\n\n"]),
    st.text(
        alphabet=st.one_of(
            st.sampled_from(list(_VIETNAMESE)),
            st.characters(min_codepoint=0x20, max_codepoint=0x2FF),
        ),
        max_size=30,
    ),
)

_raw_text = st.lists(_fragment, max_size=8).map("\n".join)

_record_spec = st.fixed_dictionaries(
    {
        "raw_text": _raw_text,
        "lang": st.sampled_from(["vi", "en"]),
        "doc_type": st.sampled_from(["spl_label", "guideline", "other", ""]),
        "trust_tier": st.sampled_from([1, 2, 3, 4]),
        "title": st.text(max_size=20),
        "url": st.text(max_size=20),
        "effective_date": st.one_of(st.none(), st.just("2023-05-01")),
    }
)

# A set of distinct source records. external_id is assigned by index so every
# record has a unique (source_id, external_id) identity, matching the design's
# "PMID / SPL setid / URL hash" uniqueness.
_record_specs = st.lists(_record_spec, min_size=0, max_size=6)


def _records_from_specs(specs: list[dict[str, Any]]) -> list[RawRecord]:
    return [
        RawRecord(
            source_key=_SOURCE_KEY,
            external_id=f"doc-{i}",
            title=spec["title"],
            url=spec["url"],
            lang=spec["lang"],
            doc_type=spec["doc_type"],
            raw_text=spec["raw_text"],
            effective_date=spec["effective_date"],
            trust_tier=spec["trust_tier"],
        )
        for i, spec in enumerate(specs)
    ]


# ---------------------------------------------------------------------------
# Property 5
# ---------------------------------------------------------------------------


@settings(max_examples=150, deadline=None)
@given(specs=_record_specs)
def test_ingestion_is_idempotent_over_identical_upstream_data(specs: list[dict[str, Any]]) -> None:
    """Property 5 / Req 4.1, 4.2: a second run over identical data is a no-op.

    The first run populates the corpus; the second run over the *identical*
    record set must insert zero new documents and zero new chunks, report
    ``skipped == fetched`` (every record recognised via its deterministic
    ``content_hash``), and leave the persisted corpus byte-for-byte unchanged.
    """

    records = _records_from_specs(specs)
    store = FakeDocumentStore()
    orchestrator = _build_orchestrator(store, records)

    # First run: builds the corpus. Every record is a brand-new identity, so it
    # is inserted (never skipped) -- this makes the second run's skip meaningful.
    report1 = orchestrator.run(_SOURCE_KEY)
    assert report1.fetched == len(records)
    assert report1.failed == 0
    assert report1.skipped == 0
    assert report1.updated == 0
    assert report1.inserted == len(records)
    assert report1.accounting_holds()

    chunks_after_first = store.total_chunks()
    snapshot_after_first = store.snapshot()

    # Second run over identical upstream data.
    report2 = orchestrator.run(_SOURCE_KEY)

    # Req 4.1: zero new chunks, skipped == fetched.
    assert report2.inserted == 0, "second run must insert no new documents"
    assert report2.updated == 0, "second run must update no documents"
    assert report2.failed == 0
    assert report2.fetched == len(records)
    assert report2.skipped == report2.fetched, "Req 4.1: skipped must equal fetched"
    assert report2.accounting_holds()

    # Req 4.1 / Property 5: no new chunks were persisted by the second run.
    assert store.total_chunks() == chunks_after_first

    # Property 5: the persisted corpus is identical before and after the re-run.
    assert store.snapshot() == snapshot_after_first


def test_ingestion_idempotent_concrete_example() -> None:
    """Concrete example: a two-document source ingested twice persists once.

    Complements the property test with a deterministic, readable case that pins
    the exact counts and asserts the content hash is reused on the second run.
    """

    records = [
        RawRecord(
            source_key=_SOURCE_KEY,
            external_id="spl-001",
            title="Amoxicillin label",
            url="https://example.test/spl-001",
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
            external_id="vn-guide-002",
            title="Huong dan dieu tri",
            url="https://example.test/guide-002",
            lang="vi",
            doc_type="guideline",
            raw_text="# Tong quan\nThuoc duoc su dung de dieu tri.\n",
            effective_date=None,
            trust_tier=3,
        ),
    ]

    store = FakeDocumentStore()
    orchestrator = _build_orchestrator(store, records)

    report1 = orchestrator.run(_SOURCE_KEY)
    assert report1.fetched == 2
    assert report1.inserted == 2
    assert report1.skipped == 0
    assert store.total_chunks() > 0  # real chunker produced chunks

    persisted_hashes = {key: doc["content_hash"] for key, doc in store.documents.items()}
    chunks_after_first = store.total_chunks()

    report2 = orchestrator.run(_SOURCE_KEY)
    assert report2.fetched == 2
    assert report2.inserted == 0
    assert report2.skipped == 2  # skipped == fetched
    assert store.total_chunks() == chunks_after_first

    # The deterministic content_hash from the first run is what the skip matched.
    assert {key: doc["content_hash"] for key, doc in store.documents.items()} == persisted_hashes
