"""Property-based test for atomic per-document persistence (Property 7).

Feature: rag-knowledge-pipeline, task 3.19 (optional test).

**Validates: Requirements 4.4**

Design reference (design.md -> Correctness Properties):
    Property 7: Atomic per-document persistence. If persisting a document fails
    partway (e.g. the embeddings write raises), NO partial state for that
    document is committed -- its document row, chunks, embeddings and sparse
    terms are all-or-nothing. Other documents in the same run are unaffected and
    the failed document is counted in ``failed``.

Requirements exercised:
    4.4  IF a failure occurs while persisting a document, THEN THE
         Ingestion_Orchestrator SHALL leave either all of that document's
         chunks, embeddings, and entity links committed or none of them.

This drives the REAL
:class:`clara_ml.ingestion.orchestrator.IngestionOrchestrator` (real cleaner,
real ``content_hash``, real Structure_Aware_Chunker) against fully in-memory
doubles, so no database connection or network request is made. It reuses the
in-memory-fakes approach of ``test_ingestion_idempotent_property.py`` (task
3.17) and extends the Document_Store double to faithfully model the real
:meth:`~clara_ml.rag.store.document_store.DocumentStore.transaction` semantics:
writes inside a transaction are *staged* and only promoted to committed state
when the ``with`` block exits cleanly; any exception discards the staged writes
(rollback). A write step (or the embed-once step) is then made to raise mid
document so the test can assert that the rolled-back document leaves zero
persisted state while its neighbours persist fully.
"""

from __future__ import annotations

import copy
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

# The persistence steps at which a single document can be made to fail. Each
# step occurs AFTER the document row has been staged, so triggering it exercises
# a genuine *mid-document* rollback (a prior staged write must be discarded):
#   "chunks"     -> Document_Store.upsert_chunks raises (document already staged)
#   "embeddings" -> Document_Store.write_embeddings raises (document+chunks staged)
#   "sparse"     -> Document_Store.write_sparse_terms raises (doc+chunks+emb staged)
#   "embed"      -> the embed-once step raises (document+chunks staged)
_FAIL_STEPS = ("chunks", "embeddings", "sparse", "embed")


# ---------------------------------------------------------------------------
# Injected, deterministic failure
# ---------------------------------------------------------------------------


class _InjectedWriteError(RuntimeError):
    """Raised by the store/builder doubles to abort one document mid-persist.

    A plain ``RuntimeError`` subclass (NOT ``EmbeddingUnavailableError``) so it
    is caught by the orchestrator's generic per-document failure branch, proving
    the atomicity guarantee holds for arbitrary write failures, not only the
    production degraded-embedding fail-loud path.
    """


# ---------------------------------------------------------------------------
# Compiled-statement param decoding (shared with the idempotency test approach)
# ---------------------------------------------------------------------------


def _eq_param(params: dict[str, Any], column: str) -> Any:
    """Pull the bound value for ``column`` out of a compiled statement's params."""

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

    The orchestrator runs exactly one read on the session inside a document
    transaction (``_document_exists`` -> ``session.execute(select(...))``). We
    decode the ``(source_id, external_id)`` from the compiled statement and
    answer from the store's *active* state (the staging buffer while a
    transaction is open), mirroring the real query under read-your-writes.
    """

    def __init__(self, store: "FakeDocumentStore") -> None:
        self._store = store

    def execute(self, statement: Any) -> _FakeResult:
        try:
            params = dict(statement.compile().params)
        except Exception:  # pragma: no cover - defensive; not expected here
            params = {}
        source_id = _eq_param(params, "source_id")
        external_id = _eq_param(params, "external_id")
        doc = self._store.state.documents.get((source_id, external_id))
        return _FakeResult((doc["id"],) if doc is not None else None)


# ---------------------------------------------------------------------------
# Transactional corpus state (committed vs staged)
# ---------------------------------------------------------------------------


class _CorpusState:
    """A snapshot-able view of the persisted corpus (documents/chunks/etc.).

    The store keeps one *committed* state plus, while a transaction is open, one
    *staging* state that started as a deep copy of committed. Writes mutate the
    active state; commit promotes staging to committed, rollback discards it.
    """

    def __init__(self) -> None:
        self.documents: dict[tuple[int, str], dict[str, Any]] = {}
        self.chunks: dict[int, list[dict[str, Any]]] = {}
        self.embeddings: dict[int, tuple[Any, ...]] = {}
        self.sparse: dict[int, list[tuple[str, float, str]]] = {}
        self.watermarks: dict[int, str] = {}
        self.next_doc_id = 0
        self.next_chunk_id = 0
        # The external_id of the document being persisted in the current
        # transaction (each per-document transaction handles exactly one record),
        # used to decide whether to inject a failure for this document.
        self.current_external_id: str | None = None

    def copy(self) -> "_CorpusState":
        clone = _CorpusState()
        clone.documents = copy.deepcopy(self.documents)
        clone.chunks = copy.deepcopy(self.chunks)
        clone.embeddings = copy.deepcopy(self.embeddings)
        clone.sparse = copy.deepcopy(self.sparse)
        clone.watermarks = copy.deepcopy(self.watermarks)
        clone.next_doc_id = self.next_doc_id
        clone.next_chunk_id = self.next_chunk_id
        clone.current_external_id = None  # fresh per transaction
        return clone


class FakeDocumentStore:
    """In-memory ``DocumentStore`` modelling real transaction atomicity.

    Implements only the surface the orchestrator calls (``transaction``,
    ``content_hash_exists``, ``upsert_document``, ``upsert_chunks``,
    ``write_embeddings``, ``write_sparse_terms``, ``checkpoint``). Crucially,
    writes performed inside :meth:`transaction` are staged and committed only on
    a clean exit; any exception rolls them back -- exactly the all-or-nothing
    contract Requirement 4.4 depends on.

    ``failure_plan`` maps ``external_id -> step`` (one of :data:`_FAIL_STEPS`);
    when the named step runs for that document the store (or builder) raises an
    :class:`_InjectedWriteError`, aborting the document mid-persist.
    """

    def __init__(self, failure_plan: dict[str, str] | None = None) -> None:
        self._committed = _CorpusState()
        self._txn: _CorpusState | None = None
        self.failure_plan: dict[str, str] = dict(failure_plan or {})

    @property
    def state(self) -> _CorpusState:
        """The active state: the staging buffer in a transaction, else committed."""

        return self._txn if self._txn is not None else self._committed

    @property
    def committed(self) -> _CorpusState:
        """The durable, committed corpus (post-rollback / post-commit)."""

        return self._committed

    # -- transaction boundary -----------------------------------------------

    @contextmanager
    def transaction(self):
        # Mirror DocumentStore.transaction: stage writes, commit on success,
        # roll back (discard the staging buffer) on any exception.
        staging = self._committed.copy()
        self._txn = staging
        try:
            yield _FakeSession(self)
        except Exception:
            # Rollback: do not promote staging; committed state is untouched.
            raise
        else:
            self._committed = staging  # commit
        finally:
            self._txn = None

    # -- failure injection ---------------------------------------------------

    def _maybe_fail(self, step: str) -> None:
        ext = self.state.current_external_id
        if ext is not None and self.failure_plan.get(ext) == step:
            raise _InjectedWriteError(f"injected {step} failure for external_id={ext!r}")

    def should_fail_embed(self) -> bool:
        ext = self.state.current_external_id
        return ext is not None and self.failure_plan.get(ext) == "embed"

    # -- idempotency (read committed; called outside any transaction) --------

    def content_hash_exists(
        self,
        source_id: int,
        external_id: str,
        content_hash: str,
        *,
        session: Any | None = None,
    ) -> bool:
        doc = self._committed.documents.get((source_id, external_id))
        return doc is not None and doc["content_hash"] == content_hash

    # -- writes (operate on the active/staging state) ------------------------

    def upsert_document(self, doc: Any, *, session: Any | None = None) -> int:
        state = self.state
        # Mark the document under persist BEFORE any write so later steps know
        # which document may be failed (and so a doc-level read sees the txn).
        state.current_external_id = doc.external_id
        key = (doc.source_id, doc.external_id)
        existing = state.documents.get(key)
        if existing is not None:
            existing["content_hash"] = doc.content_hash
            existing["trust_tier"] = doc.trust_tier
            return int(existing["id"])
        state.next_doc_id += 1
        doc_id = state.next_doc_id
        state.documents[key] = {
            "id": doc_id,
            "content_hash": doc.content_hash,
            "trust_tier": doc.trust_tier,
            "external_id": doc.external_id,
            "source_id": doc.source_id,
        }
        return doc_id

    def upsert_chunks(
        self,
        document_id: int,
        chunks: Any,
        *,
        session: Any | None = None,
    ) -> list[int]:
        self._maybe_fail("chunks")
        state = self.state
        stored: list[dict[str, Any]] = []
        ids: list[int] = []
        for c in chunks:
            state.next_chunk_id += 1
            cid = state.next_chunk_id
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
        state.chunks[document_id] = stored
        return ids

    def write_embeddings(self, rows: Any, *, session: Any | None = None) -> None:
        self._maybe_fail("embeddings")
        state = self.state
        for r in rows:
            state.embeddings[r.chunk_id] = (
                r.model_id,
                int(r.dim),
                tuple(float(x) for x in r.embedding),
                bool(r.is_degraded),
            )

    def write_sparse_terms(self, rows: Any, *, session: Any | None = None) -> None:
        self._maybe_fail("sparse")
        state = self.state
        staged = list(rows)
        for cid in {r.chunk_id for r in staged}:
            state.sparse[cid] = []
        for r in staged:
            state.sparse.setdefault(r.chunk_id, []).append(
                (r.term, round(float(r.weight), 6), r.model_id)
            )

    def checkpoint(self, source_id: int, cursor: str, *, session: Any | None = None) -> None:
        # Watermark checkpointing happens between per-document transactions, so
        # it writes to committed state directly.
        self._committed.watermarks[source_id] = "" if cursor is None else str(cursor)

    # -- test inspection helpers --------------------------------------------

    def committed_doc_keys(self) -> set[tuple[int, str]]:
        return set(self._committed.documents.keys())

    def committed_doc_ids(self) -> dict[str, int]:
        return {doc["external_id"]: doc["id"] for doc in self._committed.documents.values()}

    def chunk_ids_for(self, external_id: str) -> list[int]:
        doc = self._committed.documents.get((_SOURCE_ID, external_id))
        if doc is None:
            return []
        return [c["chunk_id"] for c in self._committed.chunks.get(doc["id"], [])]

    def total_chunks(self) -> int:
        return sum(len(rows) for rows in self._committed.chunks.values())


class FakeConnector:
    """Connector double that re-emits a fixed record set in one cursor-less page."""

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

    Honours the store's failure plan for the ``"embed"`` step so the embed-once
    stage can raise mid-document (document + chunks already staged), exercising
    rollback of a non-store failure.
    """

    def __init__(self, store: FakeDocumentStore) -> None:
        self._store = store

    def build(self, chunk_ids: list[int], chunks: list[Any]):
        if self._store.should_fail_embed():
            ext = self._store.state.current_external_id
            raise _InjectedWriteError(f"injected embed failure for external_id={ext!r}")
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


def _build_orchestrator(
    store: FakeDocumentStore, records: list[RawRecord]
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

    return IngestionOrchestrator(
        store,
        FakeEmbeddingBuilder(store),
        connectors={_SOURCE_KEY: connector},
        source_resolver=resolver,
    )


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

_VIETNAMESE = "ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ"

# Heading-like fragments to trigger SPL / guideline section tiling so documents
# produce multiple chunks (a richer mid-document rollback surface).
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
        max_size=30,
    ),
)

# Bias toward non-empty content so most documents really do persist chunks,
# making "all-or-nothing" non-trivial; ``min_size=1`` avoids empty bodies.
_raw_text = st.lists(_fragment, min_size=1, max_size=8).map("\n".join)

# Each document carries an optional failure step (``None`` => persists cleanly).
_record_spec = st.fixed_dictionaries(
    {
        "raw_text": _raw_text,
        "lang": st.sampled_from(["vi", "en"]),
        "doc_type": st.sampled_from(["spl_label", "guideline", "other", ""]),
        "trust_tier": st.sampled_from([1, 2, 3, 4]),
        "title": st.text(max_size=20),
        "url": st.text(max_size=20),
        "effective_date": st.one_of(st.none(), st.just("2023-05-01")),
        "fail_step": st.one_of(st.none(), st.sampled_from(_FAIL_STEPS)),
    }
)

_record_specs = st.lists(_record_spec, min_size=1, max_size=6)


def _records_from_specs(specs: list[dict[str, Any]]) -> tuple[list[RawRecord], dict[str, str]]:
    records: list[RawRecord] = []
    failure_plan: dict[str, str] = {}
    for i, spec in enumerate(specs):
        external_id = f"doc-{i}"
        if spec["fail_step"] is not None:
            failure_plan[external_id] = spec["fail_step"]
        records.append(
            RawRecord(
                source_key=_SOURCE_KEY,
                external_id=external_id,
                title=spec["title"],
                url=spec["url"],
                lang=spec["lang"],
                doc_type=spec["doc_type"],
                raw_text=spec["raw_text"],
                effective_date=spec["effective_date"],
                trust_tier=spec["trust_tier"],
            )
        )
    return records, failure_plan


# ---------------------------------------------------------------------------
# Property 7
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(specs=_record_specs)
def test_persistence_is_atomic_per_document(specs: list[dict[str, Any]]) -> None:
    """Property 7 / Req 4.4: a mid-document failure commits NO partial state.

    For a single run over distinct documents where an arbitrary subset fails at
    an arbitrary persistence step:

    * each failed document leaves zero committed state (no document row, hence no
      chunks / embeddings / sparse terms) -- all-or-nothing;
    * each surviving document is fully committed (document row present and an
      embedding exists for every one of its chunks) -- neighbours are unaffected;
    * every failed document is counted in ``failed`` and the report's accounting
      identity ``fetched == inserted + updated + skipped + failed`` holds.
    """

    records, failure_plan = _records_from_specs(specs)
    store = FakeDocumentStore(failure_plan)
    orchestrator = _build_orchestrator(store, records)

    report = orchestrator.run(_SOURCE_KEY)

    failed_ext = set(failure_plan)
    success_ext = {r.external_id for r in records} - failed_ext

    # -- report accounting ---------------------------------------------------
    assert report.fetched == len(records)
    assert report.skipped == 0, "all documents are brand-new identities on a first run"
    assert report.updated == 0
    # Req 4.4 / Property 7: every failed document is counted in ``failed``.
    assert report.failed == len(failed_ext)
    assert report.inserted == len(success_ext)
    assert report.accounting_holds()

    # -- all-or-nothing: failed documents leave NO committed state -----------
    committed_keys = store.committed_doc_keys()
    for ext in failed_ext:
        assert (_SOURCE_ID, ext) not in committed_keys, (
            f"failed document {ext!r} must leave no committed document row"
        )
        assert store.chunk_ids_for(ext) == [], (
            f"failed document {ext!r} must leave no committed chunks"
        )

    # The committed document set is EXACTLY the successful documents: failed docs
    # contributed nothing and successful docs all persisted (neighbour safety).
    assert committed_keys == {(_SOURCE_ID, ext) for ext in success_ext}

    # -- surviving documents are fully persisted (document + chunks + embeddings)
    for ext in success_ext:
        chunk_ids = store.chunk_ids_for(ext)
        for cid in chunk_ids:
            assert cid in store.committed.embeddings, (
                f"surviving document {ext!r} chunk {cid} must have a committed embedding"
            )

    # No committed embedding/sparse row may dangle off a non-committed chunk.
    committed_chunk_ids = {
        c["chunk_id"]
        for rows in store.committed.chunks.values()
        for c in rows
    }
    assert set(store.committed.embeddings).issubset(committed_chunk_ids)
    assert set(store.committed.sparse).issubset(committed_chunk_ids)


# ---------------------------------------------------------------------------
# Concrete examples (readable companions to the property)
# ---------------------------------------------------------------------------


def _spl_record(external_id: str) -> RawRecord:
    return RawRecord(
        source_key=_SOURCE_KEY,
        external_id=external_id,
        title=f"Label {external_id}",
        url=f"https://example.test/{external_id}",
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
    )


def test_middle_document_embeddings_failure_rolls_back_only_that_document() -> None:
    """A mid-batch document failing at the embeddings write leaves neighbours intact."""

    records = [_spl_record("spl-001"), _spl_record("spl-002"), _spl_record("spl-003")]
    store = FakeDocumentStore({"spl-002": "embeddings"})
    orchestrator = _build_orchestrator(store, records)

    report = orchestrator.run(_SOURCE_KEY)

    assert report.fetched == 3
    assert report.inserted == 2
    assert report.failed == 1
    assert report.skipped == 0
    assert report.accounting_holds()

    # The failed document persisted nothing at all (all-or-nothing).
    assert (_SOURCE_ID, "spl-002") not in store.committed_doc_keys()
    assert store.chunk_ids_for("spl-002") == []

    # Its neighbours persisted fully, with an embedding for every chunk.
    for ext in ("spl-001", "spl-003"):
        assert (_SOURCE_ID, ext) in store.committed_doc_keys()
        chunk_ids = store.chunk_ids_for(ext)
        assert chunk_ids, "surviving document must have committed chunks"
        for cid in chunk_ids:
            assert cid in store.committed.embeddings


def test_chunks_step_failure_commits_no_document_row() -> None:
    """Failing at the chunks write (right after the document row) persists nothing."""

    records = [_spl_record("spl-001")]
    store = FakeDocumentStore({"spl-001": "chunks"})
    orchestrator = _build_orchestrator(store, records)

    report = orchestrator.run(_SOURCE_KEY)

    assert report.fetched == 1
    assert report.failed == 1
    assert report.inserted == 0
    assert report.accounting_holds()
    assert store.committed_doc_keys() == set()
    assert store.total_chunks() == 0
    assert store.committed.embeddings == {}
    assert store.committed.sparse == {}


def test_embed_once_failure_rolls_back_document_and_chunks() -> None:
    """Failing in the embed-once step (document + chunks staged) commits nothing."""

    records = [_spl_record("spl-001")]
    store = FakeDocumentStore({"spl-001": "embed"})
    orchestrator = _build_orchestrator(store, records)

    report = orchestrator.run(_SOURCE_KEY)

    assert report.fetched == 1
    assert report.failed == 1
    assert report.inserted == 0
    assert report.accounting_holds()
    assert store.committed_doc_keys() == set()
    assert store.total_chunks() == 0
    assert store.committed.embeddings == {}


def test_no_failures_persists_every_document() -> None:
    """Sanity: with no injected failures every document persists fully."""

    records = [_spl_record("spl-001"), _spl_record("spl-002")]
    store = FakeDocumentStore()
    orchestrator = _build_orchestrator(store, records)

    report = orchestrator.run(_SOURCE_KEY)

    assert report.fetched == 2
    assert report.inserted == 2
    assert report.failed == 0
    assert report.accounting_holds()
    assert store.committed_doc_keys() == {(_SOURCE_ID, "spl-001"), (_SOURCE_ID, "spl-002")}
    for ext in ("spl-001", "spl-002"):
        for cid in store.chunk_ids_for(ext):
            assert cid in store.committed.embeddings
