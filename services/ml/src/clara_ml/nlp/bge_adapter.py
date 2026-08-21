"""BGE-M3 embedding pipeline shim (non-production by default).

``BgeM3Pipeline`` is the small NLP-layer convenience wrapper for embedding text.
By default it uses :class:`~clara_ml.rag.embedder.BgeM3EmbedderStub`, the LEGACY
non-production 16-dim SHA-256 hash adapter. That stub is a meaningless
placeholder and is NEVER used on the production embedding path
(:class:`~clara_ml.rag.embedder.HttpEmbeddingClient` does its own fail-loud /
degraded-mode handling — see Requirement 2 of the rag-knowledge-pipeline spec).

To use real, model-dimensioned embeddings, construct the pipeline with
``use_real_embeddings=True``. This routes through the production
:class:`HttpEmbeddingClient`, which:

- in production returns only real model-dimensioned vectors and raises
  :class:`~clara_ml.rag.embedder.EmbeddingUnavailableError` on failure (never a
  hash / sentinel vector), and
- in non-production degrades to explicit zero sentinels (never the hash) when
  ``RAG_EMBEDDING_ALLOW_DEGRADED`` is set.

The default is intentionally left as the legacy stub so existing callers and the
non-production shim keep their current behavior; switching to real embeddings is
an explicit, opt-in decision by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EmbeddingResult:
    text: str
    vector: list[float]


class BgeM3Pipeline:
    """Interface pipeline for BGE-M3 embeddings.

    By default this uses the legacy non-production hash stub. Pass
    ``use_real_embeddings=True`` to route through the production
    :class:`~clara_ml.rag.embedder.HttpEmbeddingClient` (real model-dimensioned
    vectors, fail-loud in production). The embedding client is imported lazily so
    the default (stub) path stays import-light and free of HTTP-client setup.
    """

    def __init__(self, *, use_real_embeddings: bool = False) -> None:
        self._use_real_embeddings = bool(use_real_embeddings)
        if self._use_real_embeddings:
            # Lazy import: keep the default stub path from pulling in the
            # embedding client (and, transitively, the rag store wiring).
            from clara_ml.rag.embedder import HttpEmbeddingClient

            self._embedder: Any = HttpEmbeddingClient()
        else:
            from clara_ml.rag.embedder import BgeM3EmbedderStub

            self._embedder = BgeM3EmbedderStub()

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        vectors = self._embedder.embed_batch(list(texts))
        return [
            EmbeddingResult(text=text, vector=[float(value) for value in vector])
            for text, vector in zip(texts, vectors)
        ]
