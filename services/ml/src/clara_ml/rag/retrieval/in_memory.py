from __future__ import annotations

from time import perf_counter
from typing import Any

from clara_ml.config import settings
from clara_ml.rag.embedder import EmbeddingUnavailableError, HttpEmbeddingClient

from .document_builder import DocumentBuilder
from .domain import Document
from .external_gateway import ExternalSourceGateway
from .reranker import NeuralReranker
from .score_engine import DocumentScorer
from .text_utils import dedupe_documents, query_terms, safe_weight


class InMemoryRetriever:
    _SCIENTIFIC_PROVIDERS = {
        "pubmed",
        "europepmc",
        "semantic_scholar",
        "openalex",
        "crossref",
        "clinicaltrials",
        "openfda",
        "dailymed",
        "rxnorm",
    }
    _WEB_PROVIDERS = {"searxng", "searxng-crawl", "web_crawl"}

    def __init__(
        self,
        documents: list[Document],
        embedder: HttpEmbeddingClient | None = None,
    ) -> None:
        self.builder = DocumentBuilder()
        self.external_gateway = ExternalSourceGateway()
        self.scorer = DocumentScorer(embedder=embedder)
        self.reranker = NeuralReranker()
        self.documents = [
            self.builder.normalized_document(doc, default_source="internal") for doc in documents
        ]
        self.last_trace: dict[str, Any] = {}

    @staticmethod
    def _trace_top_docs(docs: list[Document], *, limit: int = 5) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in docs[: max(int(limit), 1)]:
            metadata = doc.metadata or {}
            raw_score = metadata.get("score", 0.0)
            try:
                parsed_score = float(raw_score)
            except (TypeError, ValueError):
                parsed_score = 0.0
            rows.append(
                {
                    "id": doc.id,
                    "source": str(metadata.get("source") or "unknown"),
                    "score": parsed_score,
                    "url": str(metadata.get("url") or ""),
                }
            )
        return rows

    @staticmethod
    def _documents_by_source(docs: list[Document]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in docs:
            source = str((doc.metadata or {}).get("source") or "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts

    @staticmethod
    def _with_retrieval_origin(docs: list[Document], *, origin: str) -> list[Document]:
        tagged: list[Document] = []
        for doc in docs:
            metadata = dict(doc.metadata or {})
            metadata["retrieval_origin"] = origin
            tagged.append(Document(id=doc.id, text=doc.text, metadata=metadata))
        return tagged

    @staticmethod
    def _diversified_degraded_pool(
        ranked_rows: list[tuple[float, str, Document, int]],
        *,
        limit: int,
    ) -> list[tuple[float, str, Document, int]]:
        """Interleave the strongest candidates from each source/origin bucket."""

        buckets: dict[str, list[tuple[float, str, Document, int]]] = {}
        for row in ranked_rows:
            metadata = row[2].metadata or {}
            source = str(metadata.get("source") or "unknown")
            origin = str(metadata.get("retrieval_origin") or "existing")
            buckets.setdefault(f"{source}:{origin}", []).append(row)
        selected: list[tuple[float, str, Document, int]] = []
        while len(selected) < max(int(limit), 0) and any(buckets.values()):
            for rows in buckets.values():
                if not rows or len(selected) >= limit:
                    continue
                selected.append(rows.pop(0))
        return selected

    @staticmethod
    def _source_errors_from_provider_events(
        provider_events: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        for event in provider_events:
            if not isinstance(event, dict):
                continue
            status = str(event.get("status") or "").lower()
            if status not in {"error", "timeout"}:
                continue
            source = str(event.get("source") or event.get("provider") or "unknown")
            error_name = str(event.get("error") or "UnknownError")
            errors.setdefault(source, []).append(error_name)
        return errors

    def _resolve_neural_reranker(self, *, enabled_override: bool | None) -> NeuralReranker:
        if not isinstance(enabled_override, bool):
            return self.reranker
        if bool(self.reranker.enabled) == enabled_override:
            return self.reranker
        return NeuralReranker(
            enabled=enabled_override,
            model_name=self.reranker.model_name,
            top_n=self.reranker.top_n,
            timeout_ms=self.reranker.timeout_ms,
            cache_enabled=self.reranker.cache_enabled,
            cache_ttl_seconds=self.reranker.cache_ttl_seconds,
            cache_max_entries=self.reranker.cache_max_entries,
        )

    def _collect_internal_candidates(
        self,
        *,
        file_retrieval_enabled: bool,
        rag_sources: object,
        uploaded_documents: object,
    ) -> tuple[list[Document], dict[str, int]]:
        candidates = list(self.documents)
        uploaded_candidates: list[Document] = []
        source_candidates: list[Document] = []
        if file_retrieval_enabled:
            uploaded_candidates = self.builder.build_uploaded_documents(uploaded_documents)
            source_candidates = self.builder.build_rag_source_documents(rag_sources)
            candidates.extend(uploaded_candidates)
            candidates.extend(source_candidates)
        counts = {
            "seed_documents": len(self.documents),
            "uploaded_documents": len(uploaded_candidates),
            "rag_source_documents": len(source_candidates),
            "total_before_dedupe": len(candidates),
        }
        return candidates, counts

    def _index_candidates(
        self,
        *,
        query: str,
        ranking_query_override: str | None = None,
        candidates: list[Document],
        top_k: int,
        rag_sources: object,
        rag_reranker_enabled: bool | None = None,
    ) -> tuple[list[Document], dict[str, Any]]:
        started = perf_counter()
        ranking_query = str(ranking_query_override or "").strip() or query
        deduped = dedupe_documents(candidates)
        score_trace: list[dict[str, Any]] = []
        source_policies = self.builder.parse_source_policies(rag_sources)
        ranking_degraded = False
        ranking_error: str | None = None
        try:
            ranked = self.scorer.score_documents(
                ranking_query,
                deduped,
                top_k=top_k,
                source_policies=source_policies,
                score_trace=score_trace,
            )
            neural_reranker = self._resolve_neural_reranker(
                enabled_override=rag_reranker_enabled,
            )
            rerank_result = neural_reranker.rerank(ranking_query, ranked, top_k=top_k)
            ranked = rerank_result.documents
            neural_rerank = (
                rerank_result.metadata if isinstance(rerank_result.metadata, dict) else {}
            )
        except EmbeddingUnavailableError:
            # External connectors may already have returned useful, attributable
            # evidence before the dense embedding service fails. Never discard
            # those documents: retain them with the reranker's existing
            # deterministic lexical score and make the degradation explicit.
            ranking_degraded = True
            ranking_error = "EmbeddingUnavailableError"
            ranked_rows: list[tuple[float, str, Document, int]] = []
            for raw_doc in deduped:
                doc = self.scorer._normalize_document(raw_doc)
                source_key = str((doc.metadata or {}).get("source") or "").strip().lower()
                policy = source_policies.get(source_key, {"enabled": True, "weight": 1.0})
                if not bool(policy.get("enabled", True)):
                    continue
                # Stored scores describe an earlier query or ranking pass. Reusing
                # them here lets stale persistent rows dominate fresh provider
                # evidence precisely when the embedding service is unavailable.
                # Preserve attribution metadata, but recompute degraded ranking
                # solely from the current query and configured source weight.
                current_query_metadata = dict(doc.metadata or {})
                current_query_metadata["score"] = 0.0
                current_query_doc = Document(
                    id=doc.id,
                    text=doc.text,
                    metadata=current_query_metadata,
                )
                score = self.reranker._placeholder_score(ranking_query, current_query_doc)
                score *= safe_weight(policy.get("weight", 1.0), default=1.0)
                metadata = dict(doc.metadata or {})
                metadata["score"] = float(score)
                metadata["ranking_degraded"] = True
                metadata["ranking_fallback"] = "deterministic_lexical"
                degraded_doc = Document(id=doc.id, text=doc.text, metadata=metadata)
                score_trace.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "final_score": float(score),
                        "selected": False,
                        "ranking_degraded": True,
                        "ranking_fallback": "deterministic_lexical",
                    }
                )
                ranked_rows.append(
                    (float(score), str(doc.id), degraded_doc, len(score_trace) - 1)
                )
            ranked_rows.sort(key=lambda row: (-row[0], row[1]))
            neural_reranker = self._resolve_neural_reranker(
                enabled_override=rag_reranker_enabled,
            )
            llm_info: dict[str, Any] = {"status": "skipped"}
            llm_scores: dict[str, float] = {}
            llm_latency_ms = 0.0
            llm_rejected_count = 0
            llm_unscored_count = 0
            diversified_pool: list[tuple[float, str, Document, int]] = []
            if neural_reranker.llm_enabled and ranked_rows:
                pool_limit = min(
                    len(ranked_rows),
                    max(int(top_k), min(neural_reranker.llm_top_n, 24)),
                )
                diversified_pool = self._diversified_degraded_pool(
                    ranked_rows,
                    limit=pool_limit,
                )
                llm_started = perf_counter()
                llm_scores, llm_info = neural_reranker._llm_score_documents(
                    query=ranking_query,
                    documents=[row[2] for row in diversified_pool],
                )
                llm_latency_ms = round((perf_counter() - llm_started) * 1000.0, 3)
                if llm_scores:
                    combined_rows: list[tuple[float, str, Document, int]] = []
                    for lexical_score, doc_id, doc, trace_index in ranked_rows:
                        llm_score = llm_scores.get(doc.id)
                        if llm_score is None:
                            llm_unscored_count += 1
                            score_trace[trace_index]["rerank_llm_score"] = None
                            score_trace[trace_index]["rejected_by_llm_not_scored"] = True
                            continue
                        if float(llm_score) < neural_reranker.llm_min_score:
                            llm_rejected_count += 1
                            score_trace[trace_index]["rerank_llm_score"] = float(llm_score)
                            score_trace[trace_index]["rejected_by_llm_relevance_floor"] = True
                            continue
                        normalized_lexical = neural_reranker._squash_score(lexical_score)
                        combined_score = (0.20 * normalized_lexical) + (0.80 * llm_score)
                        metadata = dict(doc.metadata or {})
                        metadata["score"] = float(combined_score)
                        metadata["rerank_llm_score"] = (
                            float(llm_score) if llm_score is not None else None
                        )
                        metadata["ranking_fallback"] = "llm_dominant_degraded"
                        reranked_doc = Document(id=doc.id, text=doc.text, metadata=metadata)
                        score_trace[trace_index]["final_score"] = float(combined_score)
                        score_trace[trace_index]["rerank_llm_score"] = (
                            float(llm_score) if llm_score is not None else None
                        )
                        combined_rows.append(
                            (float(combined_score), doc_id, reranked_doc, trace_index)
                        )
                    ranked_rows = sorted(
                        combined_rows,
                        key=lambda row: (-row[0], row[1]),
                    )
            selected_rows = ranked_rows[: max(int(top_k), 0)]
            for row in selected_rows:
                score_trace[row[3]]["selected"] = True
            ranked = [row[2] for row in selected_rows]
            neural_rerank = {
                "rerank_enabled": bool(llm_scores),
                "rerank_model": (
                    str(llm_info.get("model") or neural_reranker.model_name)
                    if llm_scores
                    else "deterministic-lexical-v1"
                ),
                "rerank_strategy": (
                    "llm_dominant_degraded" if llm_scores else "lexical"
                ),
                "rerank_latency_ms": llm_latency_ms,
                "rerank_topn": len(diversified_pool),
                "rerank_timeout_ms": (
                    neural_reranker.llm_timeout_ms
                    if neural_reranker.llm_enabled
                    else 0
                ),
                "rerank_input_count": len(diversified_pool),
                "rerank_output_count": len(ranked),
                "rerank_applied_count": len(llm_scores),
                "rerank_timed_out": "TimeoutError"
                in str(llm_info.get("error") or ""),
                "rerank_reason": (
                    "embedding_unavailable_llm_rerank"
                    if llm_scores
                    else "embedding_unavailable_lexical_fallback"
                ),
                "rerank_error": ranking_error,
                "rerank_cache_hit": False,
                "rerank_llm_used": bool(llm_scores),
                "rerank_llm_status": llm_info.get("status"),
                "rerank_llm_error": llm_info.get("error"),
                "rerank_llm_min_score": neural_reranker.llm_min_score,
                "rerank_llm_rejected_count": llm_rejected_count,
                "rerank_llm_unscored_count": llm_unscored_count,
            }
        biomedical_rerank = {
            "enabled": bool(settings.rag_biomedical_rerank_enabled),
            "alpha": float(settings.rag_biomedical_rerank_alpha),
            "top_n": int(settings.rag_biomedical_rerank_top_n),
            "applied_count": sum(
                1
                for doc in ranked
                if bool((doc.metadata or {}).get("biomedical_rerank_enabled"))
            ),
        }
        index_trace = {
            "fetch_query": query,
            "ranking_query": ranking_query,
            "before_dedupe_count": len(candidates),
            "after_dedupe_count": len(deduped),
            "selected_count": len(ranked),
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
            "ranking_degraded": ranking_degraded,
            "ranking_error": ranking_error,
            "ranking_fallback": (
                (
                    "llm_dominant_degraded"
                    if bool(neural_rerank.get("rerank_llm_used"))
                    else "deterministic_lexical"
                )
                if ranking_degraded
                else None
            ),
            "rerank": {
                **biomedical_rerank,
                "neural": neural_rerank,
                "rerank_latency_ms": neural_rerank.get("rerank_latency_ms"),
                "rerank_topn": neural_rerank.get("rerank_topn"),
                "rerank_model": neural_rerank.get("rerank_model"),
                "rerank_timed_out": bool(neural_rerank.get("rerank_timed_out")),
                "rerank_reason": neural_rerank.get("rerank_reason"),
                "rerank_cache_hit": bool(neural_rerank.get("rerank_cache_hit")),
                "rerank_cache_age_ms": neural_rerank.get("rerank_cache_age_ms"),
            },
            "score_trace": score_trace,
            "top_documents": self._trace_top_docs(ranked),
        }
        return ranked, index_trace

    def retrieve_external_scientific(
        self,
        query: str,
        top_k: int = 3,
        *,
        ranking_query_override: str | None = None,
        timeout_seconds: float = 1.2,
        rag_sources: object = None,
        allowed_providers: set[str] | None = None,
        provider_query_overrides: dict[str, str] | None = None,
        rag_reranker_enabled: bool | None = None,
    ) -> list[Document]:
        started = perf_counter()
        gateway_trace: dict[str, Any] = {}
        docs = self.external_gateway.retrieve_scientific_with_telemetry(
            query=query,
            top_k=top_k,
            timeout_seconds=timeout_seconds,
            telemetry=gateway_trace,
            allowed_providers=allowed_providers,
            provider_query_overrides=provider_query_overrides,
        )
        docs = self._with_retrieval_origin(docs, origin="live_scientific")
        ranked, index_trace = self._index_candidates(
            query=query,
            ranking_query_override=ranking_query_override,
            candidates=docs,
            top_k=max(top_k, 1),
            rag_sources=rag_sources,
            rag_reranker_enabled=rag_reranker_enabled,
        )
        provider_events = (
            gateway_trace.get("provider_events")
            if isinstance(gateway_trace.get("provider_events"), list)
            else []
        )
        source_errors = self._source_errors_from_provider_events(provider_events)
        if bool(index_trace.get("ranking_degraded")):
            source_errors.setdefault("embedding", []).append(
                str(index_trace.get("ranking_error") or "EmbeddingUnavailableError")
            )
        search_phase = {
            "query_terms": query_terms(query),
            "connectors_attempted": provider_events,
            "documents_by_source": self._documents_by_source(docs),
            "source_errors": source_errors,
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
        }
        self.last_trace = {
            "mode": "external_scientific",
            "query": query,
            "fetch_query": query,
            "ranking_query": str(ranking_query_override or "").strip() or query,
            "requested_top_k": int(top_k),
            "raw_documents_count": len(docs),
            "deduped_documents_count": int(index_trace["after_dedupe_count"]),
            "selected_documents_count": len(ranked),
            "gateway": gateway_trace,
            "source_errors": source_errors,
            "search_phase": search_phase,
            "index_phase": index_trace,
            "search_plan": {
                "query": query,
                "query_terms": search_phase.get("query_terms", []),
                "top_k": int(top_k),
                "phase": "external_scientific",
                "total_candidates": len(docs),
            },
            "source_attempts": provider_events,
            "index_summary": {
                "before_dedupe_count": index_trace.get("before_dedupe_count"),
                "after_dedupe_count": index_trace.get("after_dedupe_count"),
                "selected_count": index_trace.get("selected_count"),
                "duration_ms": index_trace.get("duration_ms"),
                "rerank": index_trace.get("rerank", {}),
            },
            "crawl_summary": {},
            "score_trace": index_trace["score_trace"],
            "top_documents": index_trace["top_documents"],
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
        }
        return ranked

    def retrieve_internal(
        self,
        query: str,
        top_k: int = 3,
        *,
        ranking_query_override: str | None = None,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
        rag_reranker_enabled: bool | None = None,
    ) -> list[Document]:
        started = perf_counter()
        if top_k <= 0:
            self.last_trace = {
                "mode": "internal",
                "query": query,
                "fetch_query": query,
                "ranking_query": str(ranking_query_override or "").strip() or query,
                "requested_top_k": int(top_k),
                "selected_documents_count": 0,
                "search_phase": {
                    "query_terms": query_terms(query),
                    "connectors_attempted": [],
                    "documents_by_source": {},
                    "source_errors": {},
                    "duration_ms": 0.0,
                },
                "index_phase": {
                    "before_dedupe_count": 0,
                    "after_dedupe_count": 0,
                    "selected_count": 0,
                    "duration_ms": 0.0,
                    "score_trace": [],
                    "top_documents": [],
                },
                "duration_ms": round((perf_counter() - started) * 1000.0, 3),
            }
            return []

        search_started = perf_counter()
        candidates, counts = self._collect_internal_candidates(
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
        )
        search_phase = {
            "query_terms": query_terms(query),
            "connectors_attempted": [
                {
                    "provider": "internal_corpus",
                    "status": "completed",
                    "documents": len(candidates),
                    "duration_ms": round((perf_counter() - search_started) * 1000.0, 3),
                }
            ],
            "documents_by_source": self._documents_by_source(candidates),
            "source_errors": {},
            "duration_ms": round((perf_counter() - search_started) * 1000.0, 3),
        }

        ranked, index_phase = self._index_candidates(
            query=query,
            ranking_query_override=ranking_query_override,
            candidates=candidates,
            top_k=top_k,
            rag_sources=rag_sources,
            rag_reranker_enabled=rag_reranker_enabled,
        )
        if bool(index_phase.get("ranking_degraded")):
            internal_source_errors = search_phase.setdefault("source_errors", {})
            internal_source_errors.setdefault("embedding", []).append(
                str(index_phase.get("ranking_error") or "EmbeddingUnavailableError")
            )
        counts["total_after_dedupe"] = int(index_phase["after_dedupe_count"])
        self.last_trace = {
            "mode": "internal",
            "query": query,
            "fetch_query": query,
            "ranking_query": str(ranking_query_override or "").strip() or query,
            "requested_top_k": int(top_k),
            "file_retrieval_enabled": bool(file_retrieval_enabled),
            "candidate_counts": counts,
            "selected_documents_count": len(ranked),
            "search_phase": search_phase,
            "index_phase": index_phase,
            "search_plan": {
                "query": query,
                "query_terms": search_phase.get("query_terms", []),
                "top_k": int(top_k),
                "phase": "internal",
                "total_candidates": counts["total_before_dedupe"],
            },
            "source_attempts": search_phase.get("connectors_attempted", []),
            "index_summary": {
                "before_dedupe_count": index_phase.get("before_dedupe_count"),
                "after_dedupe_count": index_phase.get("after_dedupe_count"),
                "selected_count": index_phase.get("selected_count"),
                "duration_ms": index_phase.get("duration_ms"),
                "rerank": index_phase.get("rerank", {}),
            },
            "crawl_summary": {},
            "score_trace": index_phase["score_trace"],
            "top_documents": index_phase["top_documents"],
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
        }
        return ranked

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        *,
        ranking_query_override: str | None = None,
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
        provider_query_overrides: dict[str, str] | None = None,
        web_query_override: str | None = None,
        rag_reranker_enabled: bool | None = None,
    ) -> list[Document]:
        started = perf_counter()
        if top_k <= 0:
            self.last_trace = {
                "mode": "hybrid",
                "query": query,
                "fetch_query": query,
                "ranking_query": str(ranking_query_override or "").strip() or query,
                "requested_top_k": int(top_k),
                "selected_documents_count": 0,
                "search_phase": {
                    "query_terms": query_terms(query),
                    "connectors_attempted": [],
                    "documents_by_source": {},
                    "source_errors": {},
                    "duration_ms": 0.0,
                },
                "index_phase": {
                    "before_dedupe_count": 0,
                    "after_dedupe_count": 0,
                    "selected_count": 0,
                    "duration_ms": 0.0,
                    "score_trace": [],
                    "top_documents": [],
                },
                "duration_ms": round((perf_counter() - started) * 1000.0, 3),
            }
            return []

        search_started = perf_counter()
        source_errors: dict[str, list[str]] = {}
        connectors_attempted: list[dict[str, Any]] = []
        source_policies = self.builder.parse_source_policies(rag_sources)
        enabled_policy_keys = {
            key
            for key, cfg in source_policies.items()
            if isinstance(cfg, dict) and bool(cfg.get("enabled", True))
        }
        allowed_scientific_providers = (
            {item for item in enabled_policy_keys if item in self._SCIENTIFIC_PROVIDERS}
            if source_policies
            else None
        )
        web_retrieval_effective = bool(web_retrieval_enabled)
        if source_policies:
            web_retrieval_effective = bool(
                web_retrieval_enabled
                and any(item in enabled_policy_keys for item in self._WEB_PROVIDERS)
            )

        staged_docs, internal_counts = self._collect_internal_candidates(
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
        )
        internal_duration_ms = round((perf_counter() - search_started) * 1000.0, 3)
        connectors_attempted.append(
            {
                "provider": "internal_corpus",
                "status": "completed",
                "documents": len(staged_docs),
                "duration_ms": internal_duration_ms,
            }
        )
        internal_trace = {
            "candidate_counts": internal_counts,
            "duration_ms": internal_duration_ms,
        }

        external_scientific_trace: dict[str, Any] = {}
        after_external_scientific_count = len(staged_docs)
        if scientific_retrieval_enabled:
            ext_started = perf_counter()
            try:
                scientific_docs = self.external_gateway.retrieve_scientific_with_telemetry(
                    query=query,
                    top_k=max(
                        top_k,
                        min(settings.pubmed_esearch_max_results, settings.europe_pmc_max_results),
                    ),
                    timeout_seconds=settings.pubmed_connector_timeout_seconds,
                    telemetry=external_scientific_trace,
                    allowed_providers=allowed_scientific_providers,
                    provider_query_overrides=provider_query_overrides,
                )
                scientific_docs = self._with_retrieval_origin(
                    scientific_docs,
                    origin="live_scientific",
                )
                staged_docs.extend(scientific_docs)
                after_external_scientific_count = len(staged_docs)
                provider_events = (
                    external_scientific_trace.get("provider_events")
                    if isinstance(external_scientific_trace.get("provider_events"), list)
                    else []
                )
                connectors_attempted.extend(provider_events)
                external_errors = self._source_errors_from_provider_events(provider_events)
                for source_name, values in external_errors.items():
                    source_errors.setdefault(source_name, []).extend(values)
                external_scientific_trace["duration_ms"] = round(
                    (perf_counter() - ext_started) * 1000.0, 3
                )
            except Exception as exc:
                source_errors.setdefault("external_scientific", []).append(exc.__class__.__name__)
                connectors_attempted.append(
                    {
                        "provider": "external_scientific",
                        "source": "external_scientific",
                        "status": "error",
                        "error": exc.__class__.__name__,
                        "documents": 0,
                        "duration_ms": round((perf_counter() - ext_started) * 1000.0, 3),
                    }
                )
                after_external_scientific_count = len(staged_docs)

        web_trace: dict[str, Any] = {}
        crawl_trace: dict[str, Any] = {}
        if web_retrieval_effective:
            web_started = perf_counter()
            searxng_docs: list[Document] = []
            searxng_trace: dict[str, Any] = {}
            try:
                searxng_docs = self.external_gateway.retrieve_searxng_with_telemetry(
                    query=web_query_override or query,
                    top_k=max(top_k, 1),
                    timeout_seconds=settings.searxng_timeout_seconds,
                    telemetry=searxng_trace,
                    crawl_enabled=settings.searxng_crawl_enabled,
                    crawl_top_k=settings.searxng_crawl_top_k,
                    crawl_timeout_seconds=settings.searxng_crawl_timeout_seconds,
                )
                searxng_docs = self._with_retrieval_origin(
                    searxng_docs,
                    origin="live_web",
                )
                staged_docs.extend(searxng_docs)
                web_trace = {
                    "status": "completed",
                    "documents": len(searxng_docs),
                    "duration_ms": round((perf_counter() - web_started) * 1000.0, 3),
                }
                crawl_trace = (
                    searxng_trace.get("crawl_summary")
                    if isinstance(searxng_trace.get("crawl_summary"), dict)
                    else {}
                )
                source_attempts = (
                    searxng_trace.get("source_attempts")
                    if isinstance(searxng_trace.get("source_attempts"), list)
                    else []
                )
                if source_attempts:
                    connectors_attempted.extend(source_attempts)
                else:
                    connectors_attempted.append({"provider": "searxng", **web_trace})
            except Exception as exc:
                source_errors.setdefault("searxng", []).append(exc.__class__.__name__)
                web_trace = {
                    "status": "error",
                    "documents": 0,
                    "error": exc.__class__.__name__,
                    "duration_ms": round((perf_counter() - web_started) * 1000.0, 3),
                }
                connectors_attempted.append(
                    {
                        "provider": "searxng",
                        "source": "searxng",
                        **web_trace,
                    }
                )

        search_phase = {
            "query_terms": query_terms(query),
            "connectors_attempted": connectors_attempted,
            "documents_by_source": self._documents_by_source(staged_docs),
            "source_errors": source_errors,
            "duration_ms": round((perf_counter() - search_started) * 1000.0, 3),
            "total_candidates": len(staged_docs),
            "crawl_summary": crawl_trace or None,
        }

        ranked, index_phase = self._index_candidates(
            query=query,
            ranking_query_override=ranking_query_override,
            candidates=staged_docs,
            top_k=top_k,
            rag_sources=rag_sources,
            rag_reranker_enabled=rag_reranker_enabled,
        )
        if bool(index_phase.get("ranking_degraded")):
            source_errors.setdefault("embedding", []).append(
                str(index_phase.get("ranking_error") or "EmbeddingUnavailableError")
            )
            search_phase["source_errors"] = source_errors
        candidate_counts = {
            "after_internal": internal_counts["total_before_dedupe"],
            "after_external_scientific": after_external_scientific_count,
            "before_final_dedupe": int(index_phase["before_dedupe_count"]),
            "after_final_dedupe": int(index_phase["after_dedupe_count"]),
            "selected_count": int(index_phase["selected_count"]),
        }
        self.last_trace = {
            "mode": "hybrid",
            "query": query,
            "fetch_query": query,
            "ranking_query": str(ranking_query_override or "").strip() or query,
            "requested_top_k": int(top_k),
            "scientific_retrieval_enabled": bool(scientific_retrieval_enabled),
            "web_retrieval_enabled": bool(web_retrieval_effective),
            "file_retrieval_enabled": bool(file_retrieval_enabled),
            "source_errors": source_errors,
            "search_phase": search_phase,
            "index_phase": index_phase,
            "candidate_counts": candidate_counts,
            "selected_documents_count": len(ranked),
            "final_score_trace": index_phase["score_trace"],
            "top_documents": index_phase["top_documents"],
            "internal_trace": internal_trace,
            "external_scientific_trace": external_scientific_trace,
            "web_trace": web_trace,
            "crawl_trace": crawl_trace,
            "search_plan": {
                "query": query,
                "keywords": query_terms(query),
                "top_k": int(top_k),
                "scientific_retrieval_enabled": bool(scientific_retrieval_enabled),
                "web_retrieval_enabled": bool(web_retrieval_enabled),
                "file_retrieval_enabled": bool(file_retrieval_enabled),
            },
            "source_attempts": connectors_attempted,
            "index_summary": {
                "before_dedupe": int(index_phase["before_dedupe_count"]),
                "before_dedupe_count": int(index_phase["before_dedupe_count"]),
                "after_dedupe": int(index_phase["after_dedupe_count"]),
                "after_dedupe_count": int(index_phase["after_dedupe_count"]),
                "selected_count": int(index_phase["selected_count"]),
                "duration_ms": index_phase.get("duration_ms"),
                "rerank": index_phase.get("rerank", {}),
            },
            "crawl_summary": crawl_trace,
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
        }
        return ranked
