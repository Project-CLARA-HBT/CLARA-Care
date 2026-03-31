from __future__ import annotations

from time import perf_counter
from typing import Any

from clara_ml.config import settings
from clara_ml.rag.embedder import HttpEmbeddingClient

from .document_builder import DocumentBuilder
from .domain import Document
from .external_gateway import ExternalSourceGateway
from .score_engine import DocumentScorer
from .text_utils import dedupe_documents, query_terms


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
        candidates: list[Document],
        top_k: int,
        rag_sources: object,
    ) -> tuple[list[Document], dict[str, Any]]:
        started = perf_counter()
        deduped = dedupe_documents(candidates)
        score_trace: list[dict[str, Any]] = []
        ranked = self.scorer.score_documents(
            query,
            deduped,
            top_k=top_k,
            source_policies=self.builder.parse_source_policies(rag_sources),
            score_trace=score_trace,
        )
        index_trace = {
            "before_dedupe_count": len(candidates),
            "after_dedupe_count": len(deduped),
            "selected_count": len(ranked),
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
            "score_trace": score_trace,
            "top_documents": self._trace_top_docs(ranked),
        }
        return ranked, index_trace

    def retrieve_external_scientific(
        self,
        query: str,
        top_k: int = 3,
        *,
        timeout_seconds: float = 1.2,
        rag_sources: object = None,
        allowed_providers: set[str] | None = None,
    ) -> list[Document]:
        started = perf_counter()
        gateway_trace: dict[str, Any] = {}
        docs = self.external_gateway.retrieve_scientific_with_telemetry(
            query=query,
            top_k=top_k,
            timeout_seconds=timeout_seconds,
            telemetry=gateway_trace,
            allowed_providers=allowed_providers,
        )
        ranked, index_trace = self._index_candidates(
            query=query,
            candidates=docs,
            top_k=max(top_k, 1),
            rag_sources=rag_sources,
        )
        provider_events = (
            gateway_trace.get("provider_events")
            if isinstance(gateway_trace.get("provider_events"), list)
            else []
        )
        source_errors = self._source_errors_from_provider_events(provider_events)
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
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> list[Document]:
        started = perf_counter()
        if top_k <= 0:
            self.last_trace = {
                "mode": "internal",
                "query": query,
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
            candidates=candidates,
            top_k=top_k,
            rag_sources=rag_sources,
        )
        counts["total_after_dedupe"] = int(index_phase["after_dedupe_count"])
        self.last_trace = {
            "mode": "internal",
            "query": query,
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
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> list[Document]:
        started = perf_counter()
        if top_k <= 0:
            self.last_trace = {
                "mode": "hybrid",
                "query": query,
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
                    query=query,
                    top_k=max(top_k, 1),
                    timeout_seconds=settings.searxng_timeout_seconds,
                    telemetry=searxng_trace,
                    crawl_enabled=settings.searxng_crawl_enabled,
                    crawl_top_k=settings.searxng_crawl_top_k,
                    crawl_timeout_seconds=settings.searxng_crawl_timeout_seconds,
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
            candidates=staged_docs,
            top_k=top_k,
            rag_sources=rag_sources,
        )
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
            },
            "crawl_summary": crawl_trace,
            "duration_ms": round((perf_counter() - started) * 1000.0, 3),
        }
        return ranked
