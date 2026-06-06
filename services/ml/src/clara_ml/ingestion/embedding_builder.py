"""``EmbeddingBuilder`` — embed a chunk batch ONCE into store rows (task 3.15).

This module is the offline "embed once" seam of the ingestion plane
(design.md → "EmbeddingBuilder (`ingestion/embedding_builder.py`)"). Given a
batch of structure-aware :class:`~clara_ml.ingestion.chunking.Chunk` objects and
their already-persisted chunk ids, it produces the rows the
:class:`~clara_ml.rag.store.document_store.DocumentStore` writes:

* one dense :class:`~clara_ml.rag.store.document_store.EmbeddingRow` per chunk
  (``kb_chunk_embeddings``), and
* the learned-lexical (bge-m3 sparse) term -> weight rows
  (:class:`~clara_ml.rag.store.document_store.SparseTermRow`,
  ``kb_chunk_sparse_terms``).

Design constraints honoured here
--------------------------------
* **Embed once per batch.** The injected embedding client is called exactly
  once via ``embed_documents([c.text for c in chunks])`` — never per chunk and
  never per query. The dense vector for ``chunks[i]`` is ``result.vectors[i]``.
* **Dependency-injected client.** The builder accepts any object exposing
  ``embed_documents(texts) -> EmbedBatchResult`` (the production
  :class:`~clara_ml.rag.embedder.HttpEmbeddingClient`, or a fake in tests). It
  owns no network or database resources, so importing this module performs no
  side effects and the builder is pure aside from the injected client.
* **Production fail-loud (Requirements 2.4 / 2.5).** If the client returns any
  degraded vector while ``settings.environment == 'production'``, the builder
  raises :class:`~clara_ml.rag.embedder.EmbeddingUnavailableError` and emits no
  ``EmbeddingRow`` — a degraded vector is never persisted as a production
  embedding. (In non-production, degraded rows are emitted with
  ``is_degraded=True`` so the orchestrator/store can decide what to do.)
* **Dimension + model discriminator.** Every ``EmbeddingRow`` carries
  ``dim = settings.rag_embedding_dim`` and the configured ``model_id`` so the
  store's write-time dimension invariant (Requirement 1.3) and model
  discriminator (Requirement 1.4) hold.

build() contract — how chunk ids are supplied
----------------------------------------------
``chunk_id`` is unknown until a chunk is persisted (it is the autoincrement id
returned by :meth:`DocumentStore.upsert_chunks`). The orchestrator (task 3.16)
therefore calls :meth:`EmbeddingBuilder.build` *after* ``upsert_chunks`` returns
the ids, passing them positionally aligned with the chunks::

    chunk_ids = store.upsert_chunks(document_id, chunk_rows, session=s)
    emb_rows, sparse_rows = builder.build(chunk_ids, chunks)
    store.write_embeddings(emb_rows, session=s)
    store.write_sparse_terms(sparse_rows, session=s)

``chunk_ids[i]`` MUST be the persisted id of ``chunks[i]`` (same length, same
order). This is the cleaner of the two candidate contracts: it keeps the builder
free of any id-allocation concern and makes the row<->chunk mapping explicit and
unambiguous at the call site. A length mismatch is rejected up front.

bge-m3 sparse seam
------------------
The yescale embedding endpoint returns *dense only*, so a true bge-m3 sparse
(learned-lexical) vector is not yet available. :meth:`sparse_terms_for` is the
single replaceable seam that derives a deterministic lexical sparse signal —
normalized term frequencies over tokenized terms — as a stand-in. When a real
bge-m3 sparse vector becomes available, replace *only* this method (and the
``model_id`` it stamps) with the true term -> weight map; the rest of the
builder and the store contract are unchanged.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING, Protocol

from clara_ml.config import settings
from clara_ml.rag.embedder import EmbeddingUnavailableError
from clara_ml.rag.store.document_store import EmbeddingRow, SparseTermRow

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps this module import-light
    from clara_ml.ingestion.chunking import Chunk
    from clara_ml.rag.embedder import EmbedBatchResult

__all__ = [
    "EmbeddingClient",
    "EmbeddingBuilder",
]

_PRODUCTION_ENV = "production"

# Lexical token = maximal run of unicode word characters (letters/digits/_),
# which covers Vietnamese accented letters under Python's default ``re.UNICODE``.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class EmbeddingClient(Protocol):
    """Minimal structural contract the builder needs from an embedding client.

    Satisfied by :class:`clara_ml.rag.embedder.HttpEmbeddingClient`; any object
    exposing ``embed_documents`` with the same shape can be injected (e.g. a
    fake returning fixed-dimension vectors in tests).
    """

    def embed_documents(self, texts: list[str]) -> EmbedBatchResult:  # pragma: no cover - protocol
        ...


class EmbeddingBuilder:
    """Build dense + sparse store rows for a batch of chunks, embedding once.

    Parameters
    ----------
    embedding_client:
        Dependency-injected client exposing ``embed_documents(texts) ->
        EmbedBatchResult`` (see :class:`EmbeddingClient`). The builder calls it
        exactly once per :meth:`build`.
    model_id:
        Embedding model discriminator stamped on every emitted row. Defaults to
        ``settings.embedding_model`` (``text-embedding-3-large``, labeled
        ``bge-m3`` in product copy).
    environment:
        Optional override for the effective environment used by the production
        fail-loud guard. ``None`` (default) defers to ``settings.environment`` so
        the no-degraded-persistence rule (Requirement 2.5) applies automatically.
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        *,
        model_id: str | None = None,
        environment: str | None = None,
    ) -> None:
        if not hasattr(embedding_client, "embed_documents"):
            raise TypeError("embedding_client must expose an embed_documents(texts) method")
        self._client = embedding_client
        resolved_model = (settings.embedding_model if model_id is None else model_id).strip()
        if not resolved_model:
            raise ValueError("model_id must be a non-empty string")
        self._model_id = resolved_model
        self._environment = environment

    # ------------------------------------------------------------------
    # Environment helper
    # ------------------------------------------------------------------

    def _is_production(self) -> bool:
        env = self._environment if self._environment is not None else getattr(
            settings, "environment", ""
        )
        return str(env or "").strip().lower() == _PRODUCTION_ENV

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        chunk_ids: list[int],
        chunks: list[Chunk],
    ) -> tuple[list[EmbeddingRow], list[SparseTermRow]]:
        """Embed ``chunks`` once and return ``(embedding_rows, sparse_rows)``.

        Args:
            chunk_ids: Persisted ``kb_chunks.id`` values, positionally aligned
                with ``chunks`` (``chunk_ids[i]`` is the id of ``chunks[i]``).
            chunks: Structure-aware chunks for one document, in ``ord`` order.

        Returns:
            A pair ``(embedding_rows, sparse_rows)``. ``embedding_rows`` has one
            :class:`EmbeddingRow` per chunk (``dim = settings.rag_embedding_dim``,
            ``model_id`` set); ``sparse_rows`` holds the deterministic lexical
            term -> weight rows produced by :meth:`sparse_terms_for`.

        Raises:
            ValueError: If ``chunk_ids`` and ``chunks`` differ in length, or the
                embedding client returns a vector count that does not match.
            EmbeddingUnavailableError: If the client returns any degraded vector
                while the effective environment is ``production`` (Requirements
                2.4 / 2.5) — no embedding row is emitted in that case.
        """

        if len(chunk_ids) != len(chunks):
            raise ValueError(
                f"chunk_ids length {len(chunk_ids)} != chunks length {len(chunks)}; "
                "chunk_ids must be positionally aligned with chunks"
            )

        if not chunks:
            return ([], [])

        # Embed ONCE for the whole batch.
        result = self._client.embed_documents([c.text for c in chunks])
        vectors = list(result.vectors)
        degraded = list(result.degraded)

        if len(vectors) != len(chunks):
            raise ValueError(
                f"embedding client returned {len(vectors)} vectors for {len(chunks)} chunks"
            )
        if len(degraded) != len(vectors):
            # Defensive: a well-behaved client keeps these aligned. Treat a
            # missing flag as non-degraded rather than guessing.
            degraded = (degraded + [False] * len(vectors))[: len(vectors)]

        # Production fail-loud: never emit/persist a degraded embedding row.
        if self._is_production() and any(degraded):
            raise EmbeddingUnavailableError(
                "degraded embedding produced during ingestion in production; "
                "refusing to emit embedding rows"
            )

        dim = int(settings.rag_embedding_dim)

        embedding_rows: list[EmbeddingRow] = []
        sparse_rows: list[SparseTermRow] = []
        for chunk_id, chunk, vector, is_degraded in zip(
            chunk_ids, chunks, vectors, degraded, strict=True
        ):
            embedding_rows.append(
                EmbeddingRow(
                    chunk_id=chunk_id,
                    model_id=self._model_id,
                    dim=dim,
                    embedding=list(vector),
                    is_degraded=bool(is_degraded),
                )
            )
            for term, weight in self.sparse_terms_for(chunk.text).items():
                sparse_rows.append(
                    SparseTermRow(
                        chunk_id=chunk_id,
                        term=term,
                        weight=weight,
                        model_id=self._model_id,
                    )
                )

        return (embedding_rows, sparse_rows)

    # ------------------------------------------------------------------
    # bge-m3 sparse seam (replaceable)
    # ------------------------------------------------------------------

    def sparse_terms_for(self, text: str) -> dict[str, float]:
        """Derive a deterministic lexical sparse term -> weight map for ``text``.

        STAND-IN for a true bge-m3 learned-sparse vector. Until the embedding
        endpoint exposes a sparse vector, this computes **normalized term
        frequencies**: each surface term (lowercased unicode word run) maps to
        ``count(term) / total_tokens`` rounded to 6 decimals, so weights are in
        ``(0, 1]`` and sum to ~1.0. The result is:

        * deterministic — identical input always yields the identical map;
        * non-empty whenever ``text`` contains at least one word character.

        Replace ONLY this method (and the stamped ``model_id``) when a real
        bge-m3 sparse vector is available; callers and the store contract are
        unaffected.
        """

        tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")]
        total = len(tokens)
        if total == 0:
            return {}

        counts = Counter(tokens)
        return {term: round(count / total, 6) for term, count in counts.items()}
