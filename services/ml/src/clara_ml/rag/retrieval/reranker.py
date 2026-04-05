from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha1
import json
import math
from threading import Lock
from time import perf_counter
from typing import Any, Sequence
import re

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.rag.embedder import HttpEmbeddingClient

from .domain import Document


@dataclass
class RerankResult:
    documents: list[Document]
    metadata: dict[str, Any]


class NeuralReranker:
    """Neural reranker using embedding cosine similarity with safe fallbacks."""

    _CACHE_LOCK = Lock()
    _CACHE: OrderedDict[str, tuple[float, list[Document], dict[str, Any]]] = OrderedDict()

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        strategy: str | None = None,
        model_name: str | None = None,
        top_n: int | None = None,
        timeout_ms: int | None = None,
        llm_enabled: bool | None = None,
        llm_timeout_ms: int | None = None,
        llm_top_n: int | None = None,
        cache_enabled: bool | None = None,
        cache_ttl_seconds: int | None = None,
        cache_max_entries: int | None = None,
        embedder: HttpEmbeddingClient | None = None,
        llm_client: DeepSeekClient | None = None,
    ) -> None:
        self.enabled = bool(settings.rag_reranker_enabled if enabled is None else enabled)
        self.strategy = str(
            strategy or settings.rag_reranker_strategy or "embedding"
        ).strip().lower()
        self.model_name = str(model_name or settings.rag_reranker_model)
        self.top_n = max(1, int(settings.rag_reranker_top_n if top_n is None else top_n))
        self.timeout_ms = max(
            1,
            int(settings.rag_reranker_timeout_ms if timeout_ms is None else timeout_ms),
        )
        self.llm_enabled = bool(
            settings.rag_reranker_llm_enabled if llm_enabled is None else llm_enabled
        )
        self.llm_timeout_ms = max(
            100,
            int(settings.rag_reranker_llm_timeout_ms if llm_timeout_ms is None else llm_timeout_ms),
        )
        self.llm_top_n = max(
            1,
            int(settings.rag_reranker_llm_top_n if llm_top_n is None else llm_top_n),
        )
        self.cache_enabled = bool(
            settings.rag_reranker_cache_enabled
            if cache_enabled is None
            else cache_enabled
        )
        self.cache_ttl_seconds = max(
            1,
            int(
                settings.rag_reranker_cache_ttl_seconds
                if cache_ttl_seconds is None
                else cache_ttl_seconds
            ),
        )
        self.cache_max_entries = max(
            32,
            int(
                settings.rag_reranker_cache_max_entries
                if cache_max_entries is None
                else cache_max_entries
            ),
        )
        timeout_seconds = max(float(self.timeout_ms) / 1000.0, 0.05)
        self._embedder = embedder or HttpEmbeddingClient(
            timeout_seconds=min(float(settings.embedding_timeout_seconds), timeout_seconds),
        )
        self._llm_client = llm_client

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> RerankResult:
        started = perf_counter()
        candidates = [self._copy_document(doc) for doc in documents]

        if top_k is not None and top_k <= 0:
            latency_ms = round((perf_counter() - started) * 1000.0, 3)
            return RerankResult(
                documents=[],
                metadata={
                    "rerank_enabled": self.enabled,
                    "rerank_model": self.model_name,
                    "rerank_strategy": self.strategy,
                    "rerank_latency_ms": latency_ms,
                    "rerank_topn": 0,
                    "rerank_timeout_ms": self.timeout_ms,
                    "rerank_input_count": len(candidates),
                    "rerank_output_count": 0,
                    "rerank_applied_count": 0,
                    "rerank_reason": "top_k_non_positive",
                    "rerank_cache_hit": False,
                },
            )

        if not self.enabled or not candidates:
            output_docs = candidates
            if top_k is not None:
                output_docs = output_docs[:top_k]
            latency_ms = round((perf_counter() - started) * 1000.0, 3)
            return RerankResult(
                documents=output_docs,
                metadata={
                    "rerank_enabled": self.enabled,
                    "rerank_model": self.model_name,
                    "rerank_strategy": self.strategy,
                    "rerank_latency_ms": latency_ms,
                    "rerank_topn": 0,
                    "rerank_timeout_ms": self.timeout_ms,
                    "rerank_input_count": len(candidates),
                    "rerank_output_count": len(output_docs),
                    "rerank_applied_count": 0,
                    "rerank_reason": "disabled_or_empty",
                    "rerank_cache_hit": False,
                },
            )

        cache_key = ""
        if self.cache_enabled:
            cache_key = self._build_cache_key(query=query, candidates=candidates, top_k=top_k)
            cached_result = self._cache_get(cache_key=cache_key, started=started)
            if cached_result is not None:
                return cached_result

        rerank_topn = min(self.top_n, len(candidates))
        rerank_pool = candidates[:rerank_topn]
        remainder = candidates[rerank_topn:]
        timeout_seconds = max(float(self.timeout_ms) / 1000.0, 0.001)
        timed_out = False
        error_name = ""

        try:
            scored_pool = self._score_documents(
                query=query,
                documents=rerank_pool,
                started=started,
                timeout_seconds=timeout_seconds,
            )
            llm_info: dict[str, Any] | None = None
            llm_scores: dict[str, float] = {}
            if self._should_use_llm():
                llm_scores, llm_info = self._llm_score_documents(
                    query=query,
                    documents=rerank_pool,
                )
                if llm_scores:
                    scored_pool = [
                        (
                            self._combine_scores(
                                base_score=float(score),
                                llm_score=llm_scores.get(doc.id),
                            ),
                            original_index,
                            doc,
                        )
                        for score, original_index, doc in scored_pool
                    ]
            scored_pool.sort(key=lambda row: (float(row[0]), -int(row[1])), reverse=True)

            reranked: list[Document] = []
            for rank, (score, _, doc) in enumerate(scored_pool, start=1):
                metadata = doc.metadata or {}
                metadata["rerank_score"] = float(score)
                metadata["rerank_rank"] = rank
                metadata["rerank_applied"] = True
                metadata["rerank_strategy"] = self.strategy
                if llm_scores:
                    metadata["rerank_llm_score"] = float(llm_scores.get(doc.id, 0.0))
                reranked.append(doc)

            for doc in remainder:
                metadata = doc.metadata or {}
                metadata["rerank_applied"] = False

            output_docs = reranked + remainder
            if top_k is not None:
                output_docs = output_docs[:top_k]

            latency_ms = round((perf_counter() - started) * 1000.0, 3)
            result = RerankResult(
                documents=output_docs,
                metadata={
                    "rerank_enabled": self.enabled,
                    "rerank_model": self.model_name,
                    "rerank_strategy": self.strategy,
                    "rerank_latency_ms": latency_ms,
                    "rerank_topn": rerank_topn,
                    "rerank_timeout_ms": self.timeout_ms,
                    "rerank_input_count": len(candidates),
                    "rerank_output_count": len(output_docs),
                    "rerank_applied_count": len(reranked),
                    "rerank_timed_out": False,
                    "rerank_reason": "ok",
                    "rerank_cache_hit": False,
                    "rerank_llm_used": bool(llm_scores),
                    "rerank_llm_error": (
                        llm_info.get("error")
                        if isinstance(llm_info, dict)
                        else None
                    ),
                },
            )
            if cache_key:
                self._cache_set(
                    cache_key=cache_key,
                    documents=result.documents,
                    metadata=result.metadata,
                )
            return result
        except TimeoutError:
            timed_out = True
            error_name = "TimeoutError"
        except Exception as exc:  # pragma: no cover - defensive fallback
            error_name = type(exc).__name__

        for doc in candidates:
            metadata = doc.metadata or {}
            metadata["rerank_applied"] = False
        output_docs = candidates
        if top_k is not None:
            output_docs = output_docs[:top_k]
        latency_ms = round((perf_counter() - started) * 1000.0, 3)
        return RerankResult(
            documents=output_docs,
            metadata={
                "rerank_enabled": self.enabled,
                "rerank_model": self.model_name,
                "rerank_strategy": self.strategy,
                "rerank_latency_ms": latency_ms,
                "rerank_topn": 0,
                "rerank_timeout_ms": self.timeout_ms,
                "rerank_input_count": len(candidates),
                "rerank_output_count": len(output_docs),
                "rerank_applied_count": 0,
                "rerank_timed_out": timed_out,
                "rerank_reason": "timeout_fallback" if timed_out else "error_fallback",
                "rerank_error": error_name or None,
                "rerank_cache_hit": False,
                "rerank_llm_used": False,
            },
        )

    def _build_cache_key(
        self,
        *,
        query: str,
        candidates: list[Document],
        top_k: int | None,
    ) -> str:
        payload: list[str] = [
            f"q={query.strip().lower()}",
            f"top_k={top_k}",
            f"top_n={self.top_n}",
            f"model={self.model_name}",
            f"strategy={self.strategy}",
            f"llm={self.llm_enabled}",
        ]
        for doc in candidates:
            metadata = doc.metadata or {}
            payload.extend(
                [
                    str(doc.id),
                    str(doc.text),
                    str(metadata.get("score", "")),
                    str(metadata.get("source", "")),
                ]
            )
        digest = sha1("\n".join(payload).encode("utf-8")).hexdigest()
        return f"rerank:{digest}"

    def _cache_get(
        self,
        *,
        cache_key: str,
        started: float,
    ) -> RerankResult | None:
        with self._CACHE_LOCK:
            item = self._CACHE.get(cache_key)
            if item is None:
                return None
            cached_at, cached_docs, cached_metadata = item
            ttl_seconds = max(1.0, float(self.cache_ttl_seconds))
            age_seconds = perf_counter() - cached_at
            if age_seconds > ttl_seconds:
                self._CACHE.pop(cache_key, None)
                return None
            self._CACHE.move_to_end(cache_key, last=True)

        metadata = dict(cached_metadata)
        metadata["rerank_cache_hit"] = True
        metadata["rerank_cache_age_ms"] = round(max(age_seconds, 0.0) * 1000.0, 3)
        metadata["rerank_reason"] = "cache_hit"
        metadata["rerank_latency_ms"] = round((perf_counter() - started) * 1000.0, 3)
        return RerankResult(
            documents=[self._copy_document(item) for item in cached_docs],
            metadata=metadata,
        )

    def _cache_set(
        self,
        *,
        cache_key: str,
        documents: list[Document],
        metadata: dict[str, Any],
    ) -> None:
        with self._CACHE_LOCK:
            self._CACHE[cache_key] = (
                perf_counter(),
                [self._copy_document(item) for item in documents],
                dict(metadata),
            )
            self._CACHE.move_to_end(cache_key, last=True)
            max_entries = max(32, int(self.cache_max_entries))
            while len(self._CACHE) > max_entries:
                self._CACHE.popitem(last=False)

    @staticmethod
    def _copy_document(doc: Document) -> Document:
        return Document(id=doc.id, text=doc.text, metadata=dict(doc.metadata or {}))

    def _score_documents(
        self,
        *,
        query: str,
        documents: Sequence[Document],
        started: float,
        timeout_seconds: float,
    ) -> list[tuple[float, int, Document]]:
        self._ensure_not_timed_out(started=started, timeout_seconds=timeout_seconds)
        vectors = self._embedder.embed_batch([query, *[doc.text for doc in documents]])
        self._ensure_not_timed_out(started=started, timeout_seconds=timeout_seconds)
        if len(vectors) != len(documents) + 1:
            raise ValueError("reranker_embedding_size_mismatch")
        query_vector = vectors[0]
        scored: list[tuple[float, int, Document]] = []
        for original_index, (doc, doc_vector) in enumerate(zip(documents, vectors[1:])):
            self._ensure_not_timed_out(started=started, timeout_seconds=timeout_seconds)
            score = self._embedding_score(
                query=query,
                query_vector=query_vector,
                doc=doc,
                doc_vector=doc_vector,
            )
            scored.append((float(score), original_index, doc))
        return scored

    def _should_use_llm(self) -> bool:
        if not self.llm_enabled:
            return False
        if self.strategy not in {"llm_hybrid", "hybrid_llm"}:
            return False
        if self._llm_client is not None:
            return True
        return bool(str(settings.deepseek_api_key or "").strip())

    def _get_llm_client(self) -> DeepSeekClient:
        if self._llm_client is not None:
            return self._llm_client
        timeout_seconds = max(float(self.llm_timeout_ms) / 1000.0, 0.15)
        self._llm_client = DeepSeekClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=timeout_seconds,
            retries_per_base=0,
            retry_backoff_seconds=0.0,
            max_concurrency=settings.llm_global_max_concurrency,
            min_interval_seconds=settings.llm_global_min_interval_seconds,
            request_jitter_seconds=settings.llm_global_jitter_seconds,
        )
        return self._llm_client

    def _llm_score_documents(
        self,
        *,
        query: str,
        documents: Sequence[Document],
    ) -> tuple[dict[str, float], dict[str, Any]]:
        selected = list(documents[: max(1, min(self.llm_top_n, len(documents)))])
        if not selected:
            return {}, {"status": "skipped"}
        system_prompt = (
            "You are a strict biomedical reranker. Return JSON only without markdown."
        )
        prompt_docs = [
            {
                "doc_id": str(item.id),
                "text": " ".join(str(item.text or "").split())[:700],
                "source": str((item.metadata or {}).get("source") or ""),
            }
            for item in selected
        ]
        prompt = (
            "Score each candidate by relevance to the query.\n"
            "Output EXACT JSON schema:\n"
            "{\n"
            '  "scores": [\n'
            '    {"doc_id":"...", "score": 0.0, "rationale":"short"}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            "- score in [0,1]\n"
            "- prioritize direct medication safety and interaction relevance\n\n"
            f"query={query}\n"
            f"candidates={json.dumps(prompt_docs, ensure_ascii=False)}\n"
        )
        try:
            response = self._get_llm_client().generate(prompt=prompt, system_prompt=system_prompt)
            payload = json.loads(self._strip_markdown_fence(response.content))
            rows = payload.get("scores", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                return {}, {"status": "invalid_payload", "error": "scores_not_list"}
            scores: dict[str, float] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                doc_id = str(row.get("doc_id") or "").strip()
                if not doc_id:
                    continue
                scores[doc_id] = self._clamp_unit(row.get("score"), default=0.5)
            return scores, {"status": "ok", "model": response.model}
        except Exception as exc:
            return {}, {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"}

    @staticmethod
    def _strip_markdown_fence(raw: str) -> str:
        text = str(raw or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    @staticmethod
    def _clamp_unit(value: Any, *, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = float(default)
        return max(0.0, min(1.0, parsed))

    @staticmethod
    def _combine_scores(*, base_score: float, llm_score: float | None) -> float:
        if llm_score is None:
            return float(base_score)
        return (0.78 * float(base_score)) + (0.22 * float(llm_score))

    @staticmethod
    def _ensure_not_timed_out(*, started: float, timeout_seconds: float) -> None:
        if (perf_counter() - started) > max(timeout_seconds, 0.001):
            raise TimeoutError("reranker_timeout")

    @classmethod
    def _embedding_score(
        cls,
        *,
        query: str,
        query_vector: Sequence[float],
        doc: Document,
        doc_vector: Sequence[float],
    ) -> float:
        semantic = cls._cosine_similarity(query_vector, doc_vector)
        heuristic = cls._squash_score(cls._placeholder_score(query, doc))
        return (0.82 * semantic) + (0.18 * heuristic)

    @staticmethod
    def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        dim = min(len(left), len(right))
        if dim <= 0:
            return 0.0
        left_values = [float(value) for value in left[:dim]]
        right_values = [float(value) for value in right[:dim]]
        dot = sum(a * b for a, b in zip(left_values, right_values))
        left_norm = math.sqrt(sum(a * a for a in left_values))
        right_norm = math.sqrt(sum(b * b for b in right_values))
        if left_norm <= 1e-12 or right_norm <= 1e-12:
            return 0.0
        cosine = max(-1.0, min(1.0, dot / (left_norm * right_norm)))
        return max(0.0, min(1.0, (cosine + 1.0) * 0.5))

    @staticmethod
    def _squash_score(value: float) -> float:
        return max(0.0, min(1.0, 0.5 + (0.5 * math.tanh(float(value)))))

    @classmethod
    def _placeholder_score(cls, query: str, doc: Document) -> float:
        metadata = doc.metadata or {}
        base_score = cls._safe_float(metadata.get("score"), default=0.0)
        overlap = cls._lexical_overlap(query, doc.text)
        source_bonus = 0.05 if str(metadata.get("source") or "").strip().lower() else 0.0
        return base_score + overlap + source_bonus

    @staticmethod
    def _safe_float(value: object, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _lexical_overlap(cls, query: str, text: str) -> float:
        query_tokens = cls._tokens(query)
        if not query_tokens:
            return 0.0
        doc_tokens = cls._tokens(text)
        if not doc_tokens:
            return 0.0
        return len(query_tokens.intersection(doc_tokens)) / float(len(query_tokens))

    @staticmethod
    def _tokens(text: str) -> set[str]:
        tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", str(text or "").lower())
        return {token for token in tokens if token}

    @classmethod
    def clear_cache(cls) -> None:
        with cls._CACHE_LOCK:
            cls._CACHE.clear()
