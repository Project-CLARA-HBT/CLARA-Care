"""Persistent embedding cache + semantic query cache (task 9.6, P5).

This module is the ``Cache_Layer`` component from ``design.md`` / Requirement 12.
It provides two independent, import-safe caches:

* :class:`EmbeddingCache` — a *process-durable* embedding cache keyed by
  ``(model_id, normalized_text)``. Its sole correctness contract is
  **byte-identical re-reads**: a text embedded twice under the same ``model_id``
  returns the *exact same* vector on the second read (Requirement 12.1,
  Property 8). The default backing store is an in-memory ``dict``, but the
  store is reached only through a small :class:`CacheBackend` seam (``get`` /
  ``set``) so a disk- or DB-backed store can be dropped in without touching the
  cache semantics. A simple, atomic :class:`JsonFileCacheBackend` is provided as
  the reference durable backend.

* :class:`SemanticQueryCache` — a query-result cache gated by
  ``settings.rag_semantic_cache_enabled`` (Requirement 12.2). When the flag is
  off, :meth:`SemanticQueryCache.get` always returns ``None`` and
  :meth:`SemanticQueryCache.put` is a no-op, so the legacy path is unchanged.
  When on, an *exact normalized-key* path serves a cached result for a
  byte-equal (whitespace-normalized) query today, plus a documented
  **vector-similarity seam**: when an ``embed_fn`` (or precomputed vectors) is
  supplied, near-duplicate queries are matched by cosine similarity against a
  configurable threshold.

Design constraints honoured here (mirroring ``document_store.py`` /
``sparse_index.py``):

* **Import-safe.** Importing this module opens no database connection, touches
  no file, and makes no network call. The JSON backend only reads/writes its
  file when actually constructed and used.
* **Thread-safe.** Every in-memory mutation is guarded by a :class:`threading.Lock`.
  ``get`` returns a *copy* of the stored vector and ``put``/``set`` store a
  *copy* of the caller's vector, so neither side can mutate cached state and the
  byte-identical guarantee cannot be broken by aliasing.
* **Determinism is explicit.** The cache stores and returns the exact stored
  list of floats. Python's ``float`` is an IEEE-754 double and copying a list of
  floats preserves every bit; the JSON backend relies on Python's
  round-trippable float ``repr`` (``float(repr(x)) == x`` for all finite ``x``),
  so even after a reload from disk the re-read is byte-identical.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable, Sequence
from math import sqrt
from pathlib import Path
from threading import Lock
from typing import Any, Optional, Protocol, runtime_checkable

from clara_ml.config import settings

logger = logging.getLogger(__name__)

# Unit-separator used to compose the ``(model_id, normalized_text)`` cache key.
# It is not whitespace, so it survives :func:`normalize_text`'s ``split()``; it
# is also exceedingly unlikely to occur in a model id or in real query text.
_KEY_SEP = "\x1f"

__all__ = [
    "CacheBackend",
    "InMemoryCacheBackend",
    "JsonFileCacheBackend",
    "EmbeddingCache",
    "SemanticQueryCache",
    "cosine_similarity",
    "normalize_text",
]


def normalize_text(text: str) -> str:
    """Collapse runs of whitespace and trim ends.

    Mirrors ``HttpEmbeddingClient._normalize`` so a cache key computed here lines
    up with the text the embedding client actually sends to the provider. The
    normalization is part of the cache *key*, not the stored *value*.
    """

    return " ".join(str(text or "").split()).strip()


def _embedding_key(model_id: str, text: str) -> str:
    """Compose the deterministic ``(model_id, normalized_text)`` cache key."""

    return f"{str(model_id or '').strip()}{_KEY_SEP}{normalize_text(text)}"


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; ``0.0`` when undefined.

    Returns ``0.0`` for length mismatches or zero-norm inputs so the semantic
    seam degrades safely rather than raising.
    """

    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        xf = float(x)
        yf = float(y)
        dot += xf * yf
        norm_a += xf * xf
        norm_b += yf * yf
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (sqrt(norm_a) * sqrt(norm_b))


# ---------------------------------------------------------------------------
# Pluggable backend seam
# ---------------------------------------------------------------------------


@runtime_checkable
class CacheBackend(Protocol):
    """Storage seam for :class:`EmbeddingCache`.

    A backend maps an opaque string ``key`` to a vector. Implementations MUST
    return a value that is *byte-identical* to what was stored under the same
    key (Requirement 12.1). The in-memory and JSON-file backends below satisfy
    this; a future Postgres/disk backend can be added by implementing the same
    two methods without changing :class:`EmbeddingCache`.
    """

    def get(self, key: str) -> Optional[list[float]]:
        """Return the stored vector for ``key`` or ``None`` if absent."""
        ...

    def set(self, key: str, vector: list[float]) -> None:
        """Store ``vector`` under ``key`` (overwriting any prior value)."""
        ...


class InMemoryCacheBackend:
    """Default process-durable backend backed by a thread-safe ``dict``.

    Durable for the lifetime of the process. ``get``/``set`` copy the vector so
    callers cannot mutate cached state through a shared list reference.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[list[float]]:
        with self._lock:
            stored = self._store.get(key)
            return list(stored) if stored is not None else None

    def set(self, key: str, vector: list[float]) -> None:
        with self._lock:
            self._store[key] = list(vector)

    def __len__(self) -> int:  # pragma: no cover - convenience for diagnostics
        with self._lock:
            return len(self._store)


class JsonFileCacheBackend:
    """Reference durable backend that persists the cache to a JSON file.

    The whole map is loaded into memory once on construction and re-serialized
    atomically (temp file + ``os.replace``) on every ``set`` so a crash never
    leaves a half-written file. Byte-identical re-reads survive a process
    restart because Python's float ``repr`` round-trips exactly
    (``float(repr(x)) == x`` for all finite doubles).

    This is intentionally simple (no eviction, full-file rewrite per write). It
    documents the durable-backend seam; a high-write deployment would swap in a
    DB-backed :class:`CacheBackend` instead.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._store: dict[str, list[float]] = self._load()

    def _load(self) -> dict[str, list[float]]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as exc:  # unreadable file: start empty rather than crash
            logger.warning("embedding_cache_load_failed", extra={"reason": str(exc)})
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("embedding_cache_parse_failed", extra={"reason": str(exc)})
            return {}
        if not isinstance(data, dict):
            return {}
        store: dict[str, list[float]] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, list):
                try:
                    store[key] = [float(item) for item in value]
                except (TypeError, ValueError):
                    continue
        return store

    def _flush_locked(self) -> None:
        """Atomically write the current map to disk. Caller holds ``self._lock``."""

        parent = self._path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._store, handle, ensure_ascii=False)
                os.replace(tmp_name, self._path)
            except BaseException:
                # Best-effort cleanup of the temp file on any failure.
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError as exc:  # disk full / permission: keep in-memory state
            logger.warning("embedding_cache_flush_failed", extra={"reason": str(exc)})

    def get(self, key: str) -> Optional[list[float]]:
        with self._lock:
            stored = self._store.get(key)
            return list(stored) if stored is not None else None

    def set(self, key: str, vector: list[float]) -> None:
        with self._lock:
            self._store[key] = list(vector)
            self._flush_locked()

    def __len__(self) -> int:  # pragma: no cover - convenience for diagnostics
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Persistent embedding cache (Requirement 12.1 / Property 8)
# ---------------------------------------------------------------------------


class EmbeddingCache:
    """Persistent embedding cache keyed by ``(model_id, normalized_text)``.

    Contract (Requirement 12.1, Property 8): for any text put under a given
    ``model_id``, :meth:`get` returns a vector that is *byte-identical* to the
    stored one on every subsequent read. Determinism is explicit — the cache
    stores the exact list of floats and returns an exact copy of it.

    The default backing store is an in-memory dict (:class:`InMemoryCacheBackend`).
    Pass any :class:`CacheBackend` (for example :class:`JsonFileCacheBackend`, or
    a future DB backend) to make the cache durable across processes without
    changing these semantics.
    """

    def __init__(self, backend: CacheBackend | None = None) -> None:
        self._backend: CacheBackend = backend if backend is not None else InMemoryCacheBackend()

    @property
    def backend(self) -> CacheBackend:
        """The underlying storage backend (for diagnostics / swapping in tests)."""

        return self._backend

    def get(self, model_id: str, text: str) -> list[float] | None:
        """Return the cached vector for ``(model_id, text)`` or ``None``."""

        return self._backend.get(_embedding_key(model_id, text))

    def put(self, model_id: str, text: str, vector: Sequence[float]) -> None:
        """Cache ``vector`` for ``(model_id, text)``.

        The vector is stored as an exact list of floats; a re-read returns the
        same bits. ``float(v)`` on an existing float is the identity, so no
        precision is lost; non-float numerics are coerced once on write.
        """

        self._backend.set(_embedding_key(model_id, text), [float(value) for value in vector])


# ---------------------------------------------------------------------------
# Semantic query cache (Requirement 12.2)
# ---------------------------------------------------------------------------


class SemanticQueryCache:
    """Query-result cache gated by ``settings.rag_semantic_cache_enabled``.

    Behaviour:

    * **Flag off (default):** :meth:`get` always returns ``None`` and :meth:`put`
      is a no-op — the system behaves exactly as it does today.
    * **Flag on, exact path:** a whitespace-normalized, byte-equal query returns
      the cached result.
    * **Flag on, vector-similarity seam:** when an ``embed_fn`` is supplied (per
      call, or at construction) and entries were stored with a vector, a
      near-duplicate query whose cosine similarity to a stored query vector meets
      ``similarity_threshold`` is treated as semantically equivalent
      (Requirement 12.2). Without an ``embed_fn``/vectors only the exact path is
      active; the seam is fully wired and documented for when query vectors are
      available online.

    The enabled state is read dynamically from ``settings`` (unless overridden in
    the constructor) so toggling the flag at runtime takes effect immediately.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        embed_fn: Callable[[str], Sequence[float]] | None = None,
        similarity_threshold: float = 0.97,
    ) -> None:
        self._enabled_override = enabled
        self._embed_fn = embed_fn
        self._similarity_threshold = float(similarity_threshold)
        self._exact: dict[str, Any] = {}
        # Vector-similarity seam: parallel list of (query_vector, result).
        self._vector_entries: list[tuple[list[float], Any]] = []
        self._lock = Lock()

    def _is_enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return bool(getattr(settings, "rag_semantic_cache_enabled", False))

    def get(
        self,
        query: str,
        embed_fn: Callable[[str], Sequence[float]] | None = None,
    ) -> Any | None:
        """Return a cached result for ``query`` or ``None``.

        Always ``None`` when the semantic-cache flag is off. Tries the exact
        normalized-key path first, then the cosine-similarity seam when an
        ``embed_fn`` (argument or constructor default) and stored vectors exist.
        """

        if not self._is_enabled():
            return None

        norm = normalize_text(query)
        with self._lock:
            if norm in self._exact:
                return self._exact[norm]
            fn = embed_fn or self._embed_fn
            if fn is None or not self._vector_entries:
                return None
            # Snapshot under lock; embed and compare without holding it.
            candidates = list(self._vector_entries)

        try:
            query_vector = list(fn(query))
        except Exception as exc:  # embedding unavailable: fall back to a miss
            logger.warning("semantic_cache_embed_failed", extra={"reason": str(exc)})
            return None

        best_result: Any | None = None
        best_score = self._similarity_threshold
        for vector, result in candidates:
            score = cosine_similarity(query_vector, vector)
            if score >= best_score:
                best_score = score
                best_result = result
        return best_result

    def put(
        self,
        query: str,
        result: Any,
        *,
        vector: Sequence[float] | None = None,
        embed_fn: Callable[[str], Sequence[float]] | None = None,
    ) -> None:
        """Cache ``result`` for ``query``; a no-op when the flag is off.

        Stores the exact normalized-key entry. If a ``vector`` is provided (or an
        ``embed_fn`` can produce one) the entry is also indexed for the
        cosine-similarity seam.
        """

        if not self._is_enabled():
            return

        norm = normalize_text(query)
        vec = list(vector) if vector is not None else None
        if vec is None:
            fn = embed_fn or self._embed_fn
            if fn is not None:
                try:
                    vec = list(fn(query))
                except Exception as exc:  # embedding unavailable: exact path only
                    logger.warning("semantic_cache_embed_failed", extra={"reason": str(exc)})
                    vec = None

        with self._lock:
            self._exact[norm] = result
            if vec is not None:
                self._vector_entries.append(([float(value) for value in vec], result))
