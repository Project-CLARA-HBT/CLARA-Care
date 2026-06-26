"""Tests for the BGE-M3 pipeline shim (rag-knowledge-pipeline, Requirement 2).

``BgeM3Pipeline`` defaults to the legacy non-production 16-dim hash stub, but can
opt into the production :class:`HttpEmbeddingClient` via
``use_real_embeddings=True``. These tests assert:

- the default path still produces the legacy 16-dim stub vectors (back-compat),
- the opt-in path routes through ``HttpEmbeddingClient`` (model-dimensioned,
  fail-loud), and
- a non-production degraded run yields explicit model-dim zero sentinels — never
  the legacy hash.
"""

from __future__ import annotations

import pytest

# Import the store package first to avoid the known rag circular-import quirk.
import clara_ml.rag.store  # noqa: F401
from clara_ml.config import settings
from clara_ml.nlp.bge_adapter import BgeM3Pipeline
from clara_ml.rag.store.schema import configured_embedding_dim

_LEGACY_HASH_DIM = 16


def test_default_uses_legacy_stub_16_dim() -> None:
    pipe = BgeM3Pipeline()
    out = pipe.embed_batch(["a", "b"])
    assert len(out) == 2
    assert all(len(item.vector) == _LEGACY_HASH_DIM for item in out)
    assert out[0].text == "a"


def test_real_embeddings_use_model_dim_not_hash_nonprod_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opt-in real embeddings route through HttpEmbeddingClient.

    In non-production with degraded mode allowed, the legacy in-memory surface
    (``embed_batch``) returns model-dim zero sentinels — distinctly NOT the
    16-dim hash the stub would have produced.
    """

    monkeypatch.setattr(settings, "environment", "development", raising=False)
    monkeypatch.setattr(settings, "rag_embedding_allow_degraded", True, raising=False)
    # No API key -> the client degrades (non-prod) instead of making a network call.
    monkeypatch.setattr(settings, "embedding_api_key", "", raising=False)

    dim = configured_embedding_dim()
    assert dim != _LEGACY_HASH_DIM

    pipe = BgeM3Pipeline(use_real_embeddings=True)
    out = pipe.embed_batch(["aspirin", "warfarin"])

    assert len(out) == 2
    for item in out:
        assert len(item.vector) == dim
        assert len(item.vector) != _LEGACY_HASH_DIM
        assert all(value == 0.0 for value in item.vector)
