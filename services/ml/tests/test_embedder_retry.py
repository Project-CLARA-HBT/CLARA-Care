"""Bounded-retry behaviour for the embedding HTTP producer.

The upstream embedding provider exhibits bimodal latency (fast success or a
request that hangs until the read timeout). ``HttpEmbeddingClient._produce``
therefore retries a failed single request up to ``settings.embedding_max_retries``
times before applying the fail-loud / degraded policy. These tests pin that
contract:

* a transient failure that clears on a later attempt is recovered (no
  degraded vector, real embedding returned);
* a persistent failure still fails loud, and the number of attempts equals
  ``max_retries + 1``;
* ``max_retries = 0`` means exactly one attempt (retries disabled).

A real degraded vector is NEVER persisted by any of these paths.
"""

from __future__ import annotations

from unittest import mock

import pytest

# Import the store package first to avoid the known partially-initialized-module
# import cycle (see the import note in embedder.py).
import clara_ml.rag.store  # noqa: F401
from clara_ml.config import settings
from clara_ml.rag.embedder import EmbeddingUnavailableError, HttpEmbeddingClient

_TEST_DIM = 8


def _client() -> HttpEmbeddingClient:
    return HttpEmbeddingClient(
        api_key="test-key", base_url="https://example.invalid/v1", model="m"
    )


def _force(monkeypatch: pytest.MonkeyPatch, *, retries: int, environment: str = "production") -> None:
    monkeypatch.setattr(settings, "environment", environment, raising=False)
    monkeypatch.setattr(settings, "embedding_max_retries", retries, raising=False)
    monkeypatch.setattr(settings, "rag_embedding_dim", _TEST_DIM, raising=False)


def test_transient_failure_is_recovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two timeouts then a success → real vector returned, not degraded."""

    _force(monkeypatch, retries=3)
    client = _client()
    good = [[0.1] * _TEST_DIM]
    side = [TimeoutError("hang"), TimeoutError("hang"), good]

    def fake(texts):  # noqa: ANN001 - test stub
        item = side.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with mock.patch.object(client, "_request_remote_embeddings", side_effect=fake):
        result = client.embed_documents(["ibuprofen 200 mg"])

    assert result.degraded == [False]
    assert result.vectors == good


def test_persistent_failure_exhausts_retries_then_fails_loud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All attempts fail → EmbeddingUnavailableError after exactly retries+1 calls."""

    _force(monkeypatch, retries=3)
    client = _client()
    spy = mock.Mock(side_effect=TimeoutError("hang"))

    with mock.patch.object(client, "_request_remote_embeddings", spy):
        with pytest.raises(EmbeddingUnavailableError):
            client.embed_documents(["ibuprofen 200 mg"])

    assert spy.call_count == 4  # 3 retries + 1 initial attempt


def test_zero_retries_means_single_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """retries=0 → exactly one attempt before failing loud."""

    _force(monkeypatch, retries=0)
    client = _client()
    spy = mock.Mock(side_effect=TimeoutError("hang"))

    with mock.patch.object(client, "_request_remote_embeddings", spy):
        with pytest.raises(EmbeddingUnavailableError):
            client.embed_documents(["ibuprofen 200 mg"])

    assert spy.call_count == 1
