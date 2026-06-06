"""Regression test: the legacy 16-dim SHA-256 hash stub is UNREACHABLE in prod.

Feature: rag-knowledge-pipeline, task 1.9 (optional regression test).

Background
----------
The pre-change embedder silently degraded to a 16-dimension SHA-256 hash vector
(``[b / 255.0 for b in sha256(text).digest()[:16]]``) whenever the embedding API
was unavailable. Task 1.7 replaced that silent fallback in
:mod:`clara_ml.rag.embedder` with explicit fail-loud / degraded-mode behavior:

* In production an embedding API failure raises
  :class:`~clara_ml.rag.embedder.EmbeddingUnavailableError`; the client never
  returns a 16-dim SHA-256 hash vector (or any sentinel) on any code path.
* In non-production with ``RAG_EMBEDDING_ALLOW_DEGRADED`` true, the client
  returns explicit *zero* sentinel vectors of the model dimension flagged
  ``is_degraded=True`` — never the old hash.

This test LOCKS that replacement. It is intentionally distinct from the
Property-9 fail-loud property test (task 1.8): here we target the hash stub
specifically and prove (a) the production path never yields the legacy 16-dim
hash shape, and (b) the :class:`~clara_ml.rag.embedder.BgeM3EmbedderStub` is
never invoked by :class:`~clara_ml.rag.embedder.HttpEmbeddingClient` on any
embedding path. The stub class itself is retained only for the legacy
``nlp.bge_adapter`` shim, so we cannot delete it; instead we prove it is dead
code as far as the production embedding client is concerned.

Validates: Requirement 2.2 (production produces only model-dimensioned vectors
and never a 16-dim SHA-256 hash / sentinel vector on any code path).
"""

from __future__ import annotations

import hashlib

import pytest

# Import the store package first: ``clara_ml.rag.store`` eagerly wires
# hybrid_retriever -> score_engine -> HttpEmbeddingClient, so importing it ahead
# of the embedder keeps the partially-initialized-module cycle from biting in
# the test environment (see the import note in embedder.py).
import clara_ml.rag.store  # noqa: F401
from clara_ml.config import settings
from clara_ml.rag.embedder import (
    BgeM3EmbedderStub,
    EmbeddingUnavailableError,
    HttpEmbeddingClient,
)
from clara_ml.rag.store.schema import configured_embedding_dim

# The exact dimensionality of the legacy hash stub we must never reproduce.
_LEGACY_HASH_DIM = 16

# A spread of representative inputs: ASCII, Vietnamese/unicode, whitespace, and
# a long string. Each must fail loud (never hash) on the production path.
_SAMPLE_TEXTS = [
    "aspirin",
    "paracetamol và ibuprofen",
    "tương tác thuốc nghiêm trọng",
    "   leading and trailing   ",
    "a" * 2048,
    "Đường huyết cao 💊",
]


def _legacy_hash_vector(text: str) -> list[float]:
    """Reproduce the exact vector the removed silent fallback would have returned."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in digest[:_LEGACY_HASH_DIM]]


def _set_env(monkeypatch: pytest.MonkeyPatch, environment: str, *, allow_degraded: bool) -> None:
    monkeypatch.setattr(settings, "environment", environment, raising=False)
    monkeypatch.setattr(settings, "rag_embedding_allow_degraded", allow_degraded, raising=False)


def _make_client(*, api_key: str = "") -> HttpEmbeddingClient:
    # api_key="" forces the "no embedding API key" failure branch; a non-empty
    # key routes through the remote producer (which the caller can monkeypatch
    # to simulate an API failure).
    return HttpEmbeddingClient(api_key=api_key, base_url="https://embed.invalid/v1")


def _arm_stub_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any call into the legacy 16-dim hash stub a hard failure.

    If the production client ever reached the stub, these tripwires would raise
    ``AssertionError`` instead of the expected ``EmbeddingUnavailableError``,
    proving the stub is reachable. They never fire when the stub is dead code.
    """

    def _tripwire(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "BgeM3EmbedderStub (legacy 16-dim SHA-256 hash) was reached on an "
            "embedding path; the silent hash fallback must be unreachable"
        )

    monkeypatch.setattr(BgeM3EmbedderStub, "embed", _tripwire)
    monkeypatch.setattr(BgeM3EmbedderStub, "embed_batch", _tripwire)


# ---------------------------------------------------------------------------
# Production: every public method fails loud and never returns the hash vector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_production_no_api_key_fails_loud_never_hash(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """No API key in production: every entry point raises, never a 16-dim hash."""

    _set_env(monkeypatch, "production", allow_degraded=False)
    client = _make_client(api_key="")

    with pytest.raises(EmbeddingUnavailableError):
        client.embed_documents([text])
    with pytest.raises(EmbeddingUnavailableError):
        client.embed_query(text)
    with pytest.raises(EmbeddingUnavailableError):
        client.embed_batch([text])
    with pytest.raises(EmbeddingUnavailableError):
        client.embed(text)


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_production_api_failure_fails_loud_never_hash(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """A live embedding API failure in production raises rather than hashing."""

    _set_env(monkeypatch, "production", allow_degraded=False)
    client = _make_client(api_key="real-key")

    def _boom(_texts: object) -> list[list[float]]:
        raise ConnectionError("simulated embedding API outage")

    # Force the remote producer to fail so we hit the unavailable handler.
    monkeypatch.setattr(client, "_request_remote_embeddings", _boom)

    with pytest.raises(EmbeddingUnavailableError):
        client.embed_documents([text])
    with pytest.raises(EmbeddingUnavailableError):
        client.embed_query(text)
    with pytest.raises(EmbeddingUnavailableError):
        client.embed_batch([text])
    with pytest.raises(EmbeddingUnavailableError):
        client.embed(text)


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_production_even_when_degraded_allowed_still_fails_loud(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """Production ignores RAG_EMBEDDING_ALLOW_DEGRADED: no sentinel/hash, just raise."""

    # Degraded mode is "allowed" but production must override and fail loud.
    _set_env(monkeypatch, "production", allow_degraded=True)
    client = _make_client(api_key="")

    for call in (
        lambda: client.embed_documents([text]),
        lambda: client.embed_query(text),
        lambda: client.embed_batch([text]),
        lambda: client.embed(text),
    ):
        with pytest.raises(EmbeddingUnavailableError):
            call()


# ---------------------------------------------------------------------------
# The legacy 16-dim SHA-256 hash shape is never produced on the production path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_production_failure_never_returns_legacy_hash_vector(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """On failure, no production entry point returns the legacy 16-dim hash vector.

    We compute the exact vector the removed fallback would have returned and
    assert that, if any method somehow returns instead of raising, the result is
    neither 16-dimensional nor equal to that hash. In practice every call raises,
    which is the stronger guarantee.
    """

    _set_env(monkeypatch, "production", allow_degraded=False)
    client = _make_client(api_key="")
    legacy = _legacy_hash_vector(text)
    assert len(legacy) == _LEGACY_HASH_DIM  # sanity: the shape we are banning

    def _assert_not_hash(producer) -> None:
        try:
            result = producer()
        except EmbeddingUnavailableError:
            return  # fail-loud: nothing returned, hash impossible
        # Defensive: if a vector ever comes back it must NOT be the legacy hash.
        vectors = result.vectors if hasattr(result, "vectors") else result
        flat = vectors if vectors and isinstance(vectors[0], (int, float)) else None
        candidates = [flat] if flat is not None else list(vectors)
        for vector in candidates:
            assert len(vector) != _LEGACY_HASH_DIM
            assert list(vector) != legacy

    _assert_not_hash(lambda: client.embed_documents([text]))
    _assert_not_hash(lambda: client.embed_query(text))
    _assert_not_hash(lambda: client.embed_batch([text]))
    _assert_not_hash(lambda: client.embed(text))


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_production_success_returns_model_dim_not_16(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """The healthy production path yields model-dimensioned vectors, never 16-dim."""

    _set_env(monkeypatch, "production", allow_degraded=False)
    dim = configured_embedding_dim()
    assert dim != _LEGACY_HASH_DIM  # the model dim must not collide with the stub

    client = _make_client(api_key="real-key")

    def _ok(texts: list[str]) -> list[list[float]]:
        return [[0.01] * dim for _ in texts]

    monkeypatch.setattr(client, "_request_remote_embeddings", _ok)

    batch = client.embed_documents([text])
    assert all(len(vector) == dim for vector in batch.vectors)
    assert all(not flag for flag in batch.degraded)
    assert all(len(vector) != _LEGACY_HASH_DIM for vector in batch.vectors)

    query_vector = client.embed_query(text)
    assert len(query_vector) == dim
    assert len(query_vector) != _LEGACY_HASH_DIM


# ---------------------------------------------------------------------------
# Non-production degraded mode uses zero sentinels, NOT the SHA-256 hash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_nonprod_degraded_uses_zero_sentinel_not_hash(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """Dev degraded fallback is an explicit model-dim zero sentinel, never the hash."""

    _set_env(monkeypatch, "development", allow_degraded=True)
    dim = configured_embedding_dim()
    client = _make_client(api_key="")
    legacy = _legacy_hash_vector(text)

    batch = client.embed_documents([text])
    assert batch.degraded == [True]
    sentinel = batch.vectors[0]
    # Model-dimensioned, all-zero sentinel — distinctly NOT the 16-dim hash.
    assert len(sentinel) == dim
    assert len(sentinel) != _LEGACY_HASH_DIM
    assert all(value == 0.0 for value in sentinel)
    assert sentinel != legacy

    # The legacy in-memory surface (lenient) also degrades to a zero sentinel.
    legacy_surface = client.embed_batch([text])[0]
    assert len(legacy_surface) == dim
    assert len(legacy_surface) != _LEGACY_HASH_DIM
    assert all(value == 0.0 for value in legacy_surface)
    assert legacy_surface != legacy


# ---------------------------------------------------------------------------
# The BgeM3EmbedderStub is never invoked by the client on any embedding path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", _SAMPLE_TEXTS)
def test_hash_stub_is_unreachable_from_http_client(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """Arming a tripwire on the stub proves it is dead code for HttpEmbeddingClient.

    We exercise the production failure paths AND the non-production degraded path
    with the stub's methods rigged to raise. The expected outcomes
    (``EmbeddingUnavailableError`` in prod, a clean zero-sentinel in dev) prove
    the client never delegates to the legacy 16-dim hash stub.
    """

    _arm_stub_tripwire(monkeypatch)

    # Production failure paths: must raise the unavailable error, never trip the
    # stub tripwire (which would surface as AssertionError).
    _set_env(monkeypatch, "production", allow_degraded=False)
    prod_client = _make_client(api_key="")
    for call in (
        lambda: prod_client.embed_documents([text]),
        lambda: prod_client.embed_query(text),
        lambda: prod_client.embed_batch([text]),
        lambda: prod_client.embed(text),
    ):
        with pytest.raises(EmbeddingUnavailableError):
            call()

    # Non-production degraded path: returns a zero sentinel without touching the
    # stub. If the stub were reached the tripwire AssertionError would escape.
    _set_env(monkeypatch, "development", allow_degraded=True)
    dev_client = _make_client(api_key="")
    dim = configured_embedding_dim()
    batch = dev_client.embed_documents([text])
    assert batch.vectors[0] == [0.0] * dim
    assert dev_client.embed_batch([text])[0] == [0.0] * dim
