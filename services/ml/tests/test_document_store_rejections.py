"""Unit tests for ``DocumentStore`` write rejections at the persistence boundary.

Feature: rag-knowledge-pipeline, task 3.2 (optional unit-test task).

These tests target the write methods of
:class:`clara_ml.rag.store.document_store.DocumentStore` and assert that the
schema write-invariant validators reject an invalid row *before* the store
touches the database at all:

* ``write_embeddings`` rejects a dimension mismatch and a vector-length
  mismatch (Requirement 1.3 — embedding dimension invariant), a missing
  ``model_id`` discriminator (Requirement 1.4), and a degraded row while
  ``environment='production'`` (Requirement 2.5 — no degraded persistence).
* ``upsert_document`` / ``upsert_chunks`` reject an out-of-range ``trust_tier``
  (Requirement 1.5 — trust-tier domain ``{1, 2, 3, 4}``).
* ``write_sparse_terms`` rejects a missing ``model_id`` (Requirement 1.4).

Proof of "rejected before any DB access": the store is constructed with a
``session_factory`` that returns an *exploding* Session double whose
``query`` / ``execute`` / ``add`` / ``flush`` / ``commit`` (and friends) raise
on contact. Because the boundary validators run before
``DocumentStore._run`` ever invokes the factory, a rejected write must (a) never
construct a session (``factory.calls == 0``) and (b) never touch any DB method.

_Requirements: 1.3, 1.5, 2.5_
"""

from __future__ import annotations

import pytest

from clara_ml.rag.store.document_store import (
    ChunkRow,
    DocumentStore,
    EmbeddingRow,
    IngestDocument,
    SparseTermRow,
)
from clara_ml.rag.store.schema import (
    DegradedEmbeddingNotAllowedError,
    EmbeddingDimMismatchError,
    InvalidTrustTierError,
    MissingModelIdError,
    configured_embedding_dim,
)

# ---------------------------------------------------------------------------
# Session double + tracking factory (no real DB; explodes on any DB access)
# ---------------------------------------------------------------------------


class _ExplodingSession:
    """A Session test double that fails loudly on any database access.

    Any attempt to ``query`` / ``execute`` / ``add`` / ``flush`` / ``commit``
    etc. raises, so reaching the database before validation would surface as a
    hard test failure rather than a silent partial write.
    """

    def _explode(self, name: str) -> None:
        raise AssertionError(
            f"DocumentStore touched the database via Session.{name}() "
            f"before the boundary validator rejected the write"
        )

    def query(self, *args: object, **kwargs: object) -> None:
        self._explode("query")

    def execute(self, *args: object, **kwargs: object) -> None:
        self._explode("execute")

    def add(self, *args: object, **kwargs: object) -> None:
        self._explode("add")

    def add_all(self, *args: object, **kwargs: object) -> None:
        self._explode("add_all")

    def get(self, *args: object, **kwargs: object) -> None:
        self._explode("get")

    def delete(self, *args: object, **kwargs: object) -> None:
        self._explode("delete")

    def flush(self, *args: object, **kwargs: object) -> None:
        self._explode("flush")

    def commit(self, *args: object, **kwargs: object) -> None:
        self._explode("commit")

    def rollback(self, *args: object, **kwargs: object) -> None:
        self._explode("rollback")

    def close(self, *args: object, **kwargs: object) -> None:
        self._explode("close")

    def scalar(self, *args: object, **kwargs: object) -> None:
        self._explode("scalar")

    def scalars(self, *args: object, **kwargs: object) -> None:
        self._explode("scalars")


class _TrackingFactory:
    """Zero-arg session factory that records how many sessions it handed out."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> _ExplodingSession:
        self.calls += 1
        return _ExplodingSession()


def _make_store(environment: str | None = "production") -> tuple[DocumentStore, _TrackingFactory]:
    """Build a DocumentStore wired to an exploding session factory.

    Defaults to ``environment='production'`` so the degraded-row guard
    (Requirement 2.5) is active; the value is irrelevant for the dim /
    trust-tier / model_id rejections.
    """

    factory = _TrackingFactory()
    return DocumentStore(factory, environment=environment), factory


# ---------------------------------------------------------------------------
# write_embeddings — dimension invariant (Requirement 1.3)
# ---------------------------------------------------------------------------


def test_write_embeddings_rejects_dim_mismatch_before_db_access() -> None:
    store, factory = _make_store()
    bad_dim = configured_embedding_dim() + 1  # guaranteed != RAG_EMBEDDING_DIM
    row = EmbeddingRow(
        chunk_id=1,
        model_id="text-embedding-3-large",
        dim=bad_dim,
        embedding=[0.0] * bad_dim,
    )

    with pytest.raises(EmbeddingDimMismatchError):
        store.write_embeddings([row])

    # Rejected at the boundary: the factory was never asked for a session.
    assert factory.calls == 0


def test_write_embeddings_rejects_vector_length_mismatch_before_db_access() -> None:
    store, factory = _make_store()
    dim = configured_embedding_dim()  # declared dim is valid ...
    row = EmbeddingRow(
        chunk_id=1,
        model_id="text-embedding-3-large",
        dim=dim,
        embedding=[0.0] * (dim - 1),  # ... but the vector is one element short
    )

    with pytest.raises(EmbeddingDimMismatchError):
        store.write_embeddings([row])

    assert factory.calls == 0


# ---------------------------------------------------------------------------
# write_embeddings — model_id discriminator (Requirement 1.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_id", ["", "   "])
def test_write_embeddings_rejects_missing_model_id_before_db_access(model_id: str) -> None:
    store, factory = _make_store()
    dim = configured_embedding_dim()
    row = EmbeddingRow(
        chunk_id=1,
        model_id=model_id,
        dim=dim,
        embedding=[0.0] * dim,  # dim + length are valid so model_id is reached
    )

    with pytest.raises(MissingModelIdError):
        store.write_embeddings([row])

    assert factory.calls == 0


# ---------------------------------------------------------------------------
# write_embeddings — no degraded persistence in production (Requirement 2.5)
# ---------------------------------------------------------------------------


def test_write_embeddings_rejects_degraded_row_in_production_before_db_access() -> None:
    store, factory = _make_store(environment="production")
    dim = configured_embedding_dim()
    row = EmbeddingRow(
        chunk_id=1,
        model_id="text-embedding-3-large",
        dim=dim,
        embedding=[0.0] * dim,
        is_degraded=True,
    )

    with pytest.raises(DegradedEmbeddingNotAllowedError):
        store.write_embeddings([row])

    assert factory.calls == 0


def test_write_embeddings_allows_degraded_row_outside_production_reaches_db() -> None:
    # Control: a degraded row is permitted in non-production, so validation
    # passes and the store proceeds to acquire a session (the exploding double
    # then trips on the first real DB access). This proves the production guard
    # is what rejects above, not an unconditional refusal.
    store, factory = _make_store(environment="development")
    dim = configured_embedding_dim()
    row = EmbeddingRow(
        chunk_id=1,
        model_id="text-embedding-3-large",
        dim=dim,
        embedding=[0.0] * dim,
        is_degraded=True,
    )

    with pytest.raises(AssertionError):
        store.write_embeddings([row])

    assert factory.calls == 1


# ---------------------------------------------------------------------------
# upsert_document / upsert_chunks — trust_tier domain (Requirement 1.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("trust_tier", [0, 5, -1, 99])
def test_upsert_document_rejects_out_of_range_trust_tier_before_db_access(
    trust_tier: int,
) -> None:
    store, factory = _make_store()
    doc = IngestDocument(
        source_id=1,
        content_hash="abc123",
        trust_tier=trust_tier,
        external_id="ext-1",
    )

    with pytest.raises(InvalidTrustTierError):
        store.upsert_document(doc)

    assert factory.calls == 0


@pytest.mark.parametrize("trust_tier", [0, 5, -1, 99])
def test_upsert_chunks_rejects_out_of_range_trust_tier_before_db_access(
    trust_tier: int,
) -> None:
    store, factory = _make_store()
    chunks = [ChunkRow(ord=0, text="hello", trust_tier=trust_tier)]

    with pytest.raises(InvalidTrustTierError):
        store.upsert_chunks(document_id=1, chunks=chunks)

    assert factory.calls == 0


# ---------------------------------------------------------------------------
# write_sparse_terms — model_id discriminator (Requirement 1.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_id", ["", "   "])
def test_write_sparse_terms_rejects_missing_model_id_before_db_access(model_id: str) -> None:
    store, factory = _make_store()
    row = SparseTermRow(chunk_id=1, term="aspirin", weight=0.5, model_id=model_id)

    with pytest.raises(MissingModelIdError):
        store.write_sparse_terms([row])

    assert factory.calls == 0
