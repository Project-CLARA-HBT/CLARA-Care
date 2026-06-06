from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any, List, Sequence
from urllib.request import Request, urlopen

from clara_ml.config import settings

if TYPE_CHECKING:
    # Type-only imports: ``from __future__ import annotations`` keeps annotations
    # lazy, so nothing here executes at runtime and no import cycle can form.
    #
    # NOTE: ``assert_embedding_dim`` (from ``clara_ml.rag.store.schema``) and the
    # optional ``EmbeddingCache`` (from ``clara_ml.rag.store.cache``) are imported
    # lazily *inside the functions that use them* rather than at module top.
    # ``clara_ml.rag.store`` eagerly pulls in ``hybrid_retriever`` →
    # ``score_engine``, and ``score_engine`` imports ``HttpEmbeddingClient`` from
    # THIS module at top level; importing ``store`` (or any of its submodules) at
    # embedder load time therefore creates a partially-initialized-module cycle.
    # Deferring the store imports to call time keeps ``import clara_ml.rag.embedder``
    # cycle-free regardless of which module is imported first. ``store.cache``
    # itself only depends on ``clara_ml.config`` and is safe either way.
    from clara_ml.rag.store.cache import EmbeddingCache

logger = logging.getLogger(__name__)

_PRODUCTION_ENV = "production"


class EmbeddingUnavailableError(RuntimeError):
    """Raised when embeddings cannot be produced and degraded mode is not allowed.

    Replaces the legacy silent 16-dimension SHA-256 hash fallback. On any
    production code path the client raises this error instead of substituting a
    semantically meaningless vector (Requirements 2.1, 2.2).
    """


@dataclass(frozen=True)
class EmbedBatchResult:
    """Result of an offline document-embedding batch.

    ``vectors[i]`` is the dense embedding for ``texts[i]`` and ``degraded[i]``
    flags whether that vector is an explicit non-production sentinel rather than
    a real model embedding. ``degraded`` is all ``False`` in production
    (Requirement 2.2); callers MUST NOT persist degraded vectors as production
    embeddings (Requirements 2.4, 2.5).
    """

    vectors: list[list[float]]
    degraded: list[bool]


class BgeM3EmbedderStub:
    """LEGACY non-production hash adapter (16-dim).

    This stub is retained ONLY so the non-production ``nlp.bge_adapter`` shim
    keeps working. It is NO LONGER used by :class:`HttpEmbeddingClient` and is
    NEVER reachable on the production embedding path. Do not use it for real
    retrieval or ingestion: it produces a meaningless hash vector, exactly the
    silent fallback that Requirement 2 removes from the production path.
    """

    def embed(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # 16 deterministic dimensions — non-production placeholder only.
        return [b / 255.0 for b in digest[:16]]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(text) for text in texts]


class HttpEmbeddingClient:
    """HTTP embedding client with fail-loud / explicit degraded-mode behavior.

    Production (``settings.environment == 'production'``): real model-dimensioned
    vectors only. If the embedding API is unavailable or fails, the client
    raises :class:`EmbeddingUnavailableError`; it never returns a 16-dim
    SHA-256 hash vector or any sentinel vector on any code path
    (Requirements 2.1, 2.2).

    Non-production: when ``settings.rag_embedding_allow_degraded`` is true, the
    canonical offline/online API (:meth:`embed_documents` / :meth:`embed_query`)
    returns explicit zero sentinel vectors of dimension
    ``settings.rag_embedding_dim`` flagged ``degraded=True`` instead of failing
    (Requirement 2.3). When degraded mode is not allowed those methods fail loud
    just like production.

    The legacy :meth:`embed_batch` / :meth:`embed` methods are preserved for the
    existing in-memory retrieval callers (``DocumentScorer``, ``NeuralReranker``,
    ``InMemoryRetriever``). They route through the same production fail-loud
    logic, but in non-production they degrade gracefully (explicit, logged zero
    sentinels — never the old silent hash) so the legacy path keeps serving.

    An optional persistent :class:`~clara_ml.rag.store.cache.EmbeddingCache` may
    be injected (``embedding_cache``). When present it is an ADDITIONAL,
    process-durable layer that :meth:`embed_query` consults before issuing a live
    embedding request (Requirement 12.3); the in-process cache is unchanged.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        embedding_cache: "EmbeddingCache | None" = None,
    ) -> None:
        self._api_key = (settings.embedding_api_key if api_key is None else api_key).strip()
        self._base_url = (settings.embedding_base_url if base_url is None else base_url).strip()
        self._model = (settings.embedding_model if model is None else model).strip()
        self._timeout_seconds = (
            settings.embedding_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        self._cache: dict[str, list[float]] = {}
        # Optional persistent embedding cache (task 9.8 / Requirement 12.3). When
        # supplied it is an ADDITIONAL, process-durable layer consulted before
        # the live embedding request; the in-process ``self._cache`` keeps
        # working unchanged as a fast first-level cache.
        self._embedding_cache = embedding_cache
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Environment / configuration helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_production() -> bool:
        return str(getattr(settings, "environment", "") or "").strip().lower() == _PRODUCTION_ENV

    @staticmethod
    def _degraded_allowed() -> bool:
        return bool(getattr(settings, "rag_embedding_allow_degraded", False))

    @staticmethod
    def _expected_dim() -> int:
        try:
            return int(getattr(settings, "rag_embedding_dim", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _degraded_sentinel(self, count: int) -> list[list[float]]:
        """Return ``count`` explicit zero sentinel vectors of the model dimension."""

        dim = max(self._expected_dim(), 0)
        return [[0.0] * dim for _ in range(count)]

    # ------------------------------------------------------------------
    # Endpoint / payload helpers
    # ------------------------------------------------------------------

    def _endpoint(self) -> str:
        base = self._base_url.rstrip("/")
        return f"{base}/embeddings"

    def _normalize(self, text: str) -> str:
        return " ".join(str(text or "").split()).strip()

    def _extract_vectors(self, payload: Any) -> list[list[float]]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid embedding response payload")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("Embedding response missing data")

        vectors: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Embedding item is not an object")
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise ValueError("Embedding vector missing")
            vector: list[float] = []
            for value in embedding:
                try:
                    vector.append(float(value))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Embedding vector contains non-numeric value") from exc
            vectors.append(vector)
        return vectors

    def _request_remote_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        body: dict[str, Any] = {"model": self._model, "input": list(texts)}
        # Request a specific output dimensionality when configured. text-embedding-3-*
        # supports native (normalized) dimension reduction, letting the corpus stay
        # within pgvector's 2000-dim HNSW/IVFFlat index limit (e.g. 1536). Only sent
        # when a positive RAG_EMBEDDING_DIM is configured; omitted otherwise so the
        # model's native dimensionality is used (and providers that ignore the field
        # are unaffected).
        expected_dim = int(getattr(settings, "rag_embedding_dim", 0) or 0)
        if expected_dim > 0:
            body["dimensions"] = expected_dim
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CLARA-ML/0.1",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = Request(self._endpoint(), data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=max(float(self._timeout_seconds), 0.2)) as response:
            raw = response.read().decode("utf-8", errors="ignore")
        parsed = json.loads(raw)
        vectors = self._extract_vectors(parsed)
        if len(vectors) != len(texts):
            raise ValueError("Embedding response size mismatch")
        # Dimension invariant: every returned vector must match RAG_EMBEDDING_DIM
        # (Requirement 1.3 via the schema helper). Imported lazily to avoid a
        # module-load import cycle (see the TYPE_CHECKING note at the top).
        from clara_ml.rag.store.schema import assert_embedding_dim

        for vector in vectors:
            assert_embedding_dim(len(vector))
        return vectors

    # ------------------------------------------------------------------
    # Core fail-loud / degraded producer
    # ------------------------------------------------------------------

    def _handle_unavailable(
        self,
        count: int,
        *,
        reason: BaseException | None,
        lenient: bool,
    ) -> EmbedBatchResult:
        """Apply the fail-loud / degraded policy when real embeddings are absent.

        * Production: always raise :class:`EmbeddingUnavailableError`; never
          return a sentinel or hash vector (Requirements 2.1, 2.2).
        * Non-production + degraded allowed (or ``lenient`` legacy callers):
          return explicit zero sentinel vectors flagged ``degraded=True``
          (Requirement 2.3) — explicit and logged, never the silent hash.
        * Non-production + degraded not allowed (strict callers): raise.
        """

        detail = "no embedding API key configured" if reason is None else str(reason)
        if self._is_production():
            raise EmbeddingUnavailableError(
                f"embedding API unavailable in production: {detail}"
            ) from reason

        if lenient or self._degraded_allowed():
            logger.warning(
                "embedding_degraded_mode",
                extra={
                    "reason": type(reason).__name__ if reason is not None else "no_api_key",
                    "lenient": lenient,
                    "count": count,
                },
            )
            return EmbedBatchResult(
                vectors=self._degraded_sentinel(count),
                degraded=[True] * count,
            )

        raise EmbeddingUnavailableError(
            f"embedding API unavailable and degraded mode disabled: {detail}"
        ) from reason

    def _produce(self, normalized: Sequence[str], *, lenient: bool) -> EmbedBatchResult:
        """Produce embeddings for already-normalized texts under the fail-loud policy."""

        texts = list(normalized)
        if not texts:
            return EmbedBatchResult(vectors=[], degraded=[])

        if self._api_key:
            last_exc: Exception | None = None
            # Bounded retry: the provider's latency is bimodal (fast success or a
            # request that hangs to the read timeout). A fresh attempt usually
            # succeeds, so retrying recovers most transient failures WITHOUT ever
            # persisting a degraded vector (each attempt still fully validates the
            # response dimension). ``max(0, ...)`` => at least one attempt.
            attempts = max(0, self._max_retries()) + 1
            for attempt in range(attempts):
                try:
                    vectors = self._request_remote_embeddings(texts)
                    return EmbedBatchResult(vectors=vectors, degraded=[False] * len(vectors))
                except Exception as exc:  # remote failure (network, payload, dim mismatch)
                    last_exc = exc
                    if attempt + 1 < attempts:
                        logger.warning(
                            "embedding_retry",
                            extra={
                                "attempt": attempt + 1,
                                "attempts": attempts,
                                "reason": type(exc).__name__,
                            },
                        )
            return self._handle_unavailable(len(texts), reason=last_exc, lenient=lenient)

        # No API key configured: cannot produce real embeddings.
        return self._handle_unavailable(len(texts), reason=None, lenient=lenient)

    @staticmethod
    def _max_retries() -> int:
        """Configured bounded retry count for a single embedding request (>= 0)."""

        try:
            return max(0, int(getattr(settings, "embedding_max_retries", 0) or 0))
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------
    # Canonical fail-loud API (offline + online paths)
    # ------------------------------------------------------------------

    def embed_documents(self, texts: Sequence[str]) -> EmbedBatchResult:
        """Embed multiple documents (OFFLINE path) with the strict fail-loud contract.

        Returns an :class:`EmbedBatchResult` whose ``vectors`` each have
        dimension ``settings.rag_embedding_dim``. In production a failure raises
        :class:`EmbeddingUnavailableError`; in non-production a sentinel batch is
        returned only when ``settings.rag_embedding_allow_degraded`` is true.
        """

        normalized = [self._normalize(text) for text in texts]
        if not normalized:
            return EmbedBatchResult(vectors=[], degraded=[])
        return self._produce(normalized, lenient=False)

    def embed_query(self, text: str) -> list[float]:
        """Embed ONLY the query (ONLINE path). Same fail-loud contract; cache-first.

        Cache precedence (Requirement 12.3): the optional persistent
        :class:`EmbeddingCache` is consulted FIRST — on a hit its byte-identical
        vector is returned without any live embedding request. On a miss the
        existing path runs (fast in-process cache, then the remote producer) and
        the resulting real vector is written back to BOTH cache layers. Degraded
        / production-failed results are NEVER cached.
        """

        normalized = self._normalize(text)

        # (1) Persistent cache layer (optional) — consulted before any live call.
        if self._embedding_cache is not None:
            persisted = self._embedding_cache.get(model_id=self._model, text=text)
            if persisted is not None:
                return list(persisted)

        # (2) Fast in-process cache (existing behavior, preserved).
        with self._lock:
            cached = self._cache.get(normalized)
        if cached is not None:
            vector = list(cached)
            # Backfill the persistent layer so it stays warm and consistent.
            if self._embedding_cache is not None:
                self._embedding_cache.put(self._model, text, vector)
            return vector

        # (3) Cache miss — compute via the live embedding path.
        result = self._produce([normalized], lenient=False)
        if result.degraded and result.degraded[0] and self._is_production():
            # Defensive: never serve a degraded query embedding in production.
            raise EmbeddingUnavailableError("degraded query embedding in production")

        vector = [float(value) for value in result.vectors[0]]
        # Only cache real (non-degraded) vectors — never poison either layer.
        if not (result.degraded and result.degraded[0]):
            with self._lock:
                self._cache[normalized] = list(vector)
            if self._embedding_cache is not None:
                self._embedding_cache.put(self._model, text, vector)
        return vector

    # ------------------------------------------------------------------
    # Legacy public surface (preserved for existing in-memory callers)
    # ------------------------------------------------------------------

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch and return plain vectors (legacy contract).

        Routes through the production fail-loud logic (never the silent hash). In
        non-production this method degrades gracefully so existing in-memory
        retrieval callers keep functioning when the embedding API is unavailable.
        """

        if not texts:
            return []

        normalized = [self._normalize(text) for text in texts]
        pending_indices: list[int] = []
        pending_values: list[str] = []
        vectors: list[list[float] | None] = [None] * len(normalized)

        with self._lock:
            for idx, text in enumerate(normalized):
                cached = self._cache.get(text)
                if cached is not None:
                    vectors[idx] = list(cached)
                else:
                    pending_indices.append(idx)
                    pending_values.append(text)

        if pending_values:
            result = self._produce(pending_values, lenient=True)
            with self._lock:
                for idx, text, vector, degraded in zip(
                    pending_indices, pending_values, result.vectors, result.degraded
                ):
                    safe_vector = [float(item) for item in vector]
                    # Only cache real embeddings; never poison the cache with sentinels.
                    if not degraded:
                        self._cache[text] = safe_vector
                    vectors[idx] = list(safe_vector)

        return [vector if vector is not None else [] for vector in vectors]

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]
