from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, List, Protocol
from uuid import uuid4

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient, DeepSeekResponse
from clara_ml.rag.retriever import Document, InMemoryRetriever
from clara_ml.rag.seed_documents import base_documents, load_seed_documents


@dataclass
class RagResult:
    query: str
    retrieved_ids: List[str]
    answer: str
    model_used: str
    retrieved_context: List[dict[str, Any]] = field(default_factory=list)
    context_debug: dict[str, Any] = field(default_factory=dict)
    flow_events: List[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)


class LlmGenerator(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse: ...


class RagPipelineP1:
    """P1 pipeline: retrieve -> LLM answer (if available) -> deterministic fallback."""

    def __init__(
        self,
        retriever: InMemoryRetriever | None = None,
        llm_client: LlmGenerator | None = None,
        deepseek_api_key: str | None = None,
        deepseek_base_url: str | None = None,
        deepseek_model: str | None = None,
        deepseek_timeout_seconds: float | None = None,
    ) -> None:
        seed_documents = load_seed_documents()
        seed_by_id: dict[str, Document] = {doc.id: doc for doc in base_documents()}
        for item in seed_documents:
            seed_by_id[item.id] = item

        self.retriever = retriever or InMemoryRetriever(documents=list(seed_by_id.values()))
        self._deepseek_api_key = (
            settings.deepseek_api_key if deepseek_api_key is None else deepseek_api_key
        )
        self._llm_client = llm_client
        if self._llm_client is None and self._deepseek_api_key:
            self._llm_client = DeepSeekClient(
                api_key=self._deepseek_api_key,
                base_url=deepseek_base_url or settings.deepseek_base_url,
                model=deepseek_model or settings.deepseek_model,
                timeout_seconds=(
                    settings.deepseek_timeout_seconds
                    if deepseek_timeout_seconds is None
                    else deepseek_timeout_seconds
                ),
            )

    @staticmethod
    def _local_synthesis(query: str, docs: List[Document]) -> str:
        sources = ", ".join(doc.id for doc in docs) if docs else "none"
        snippets = " | ".join(f"{doc.id}: {doc.text}" for doc in docs)
        return f"Tra loi tam thoi (local): query='{query}'. Sources=[{sources}]. Summary={snippets}"

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", text.lower()) if token}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _source_counts(docs: List[Document]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in docs:
            source = str((doc.metadata or {}).get("source") or "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts

    @staticmethod
    def _trace_doc_rows(docs: List[Document], *, limit: int = 5) -> list[dict[str, Any]]:
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
    def _normalize_planner_hints(hints: object) -> dict[str, Any]:
        if not isinstance(hints, dict):
            return {
                "internal_top_k": 3,
                "hybrid_top_k": 3,
                "query_focus": "default",
                "reason_codes": [],
            }

        def _as_int(value: object, default: int, *, min_value: int = 1, max_value: int = 12) -> int:
            try:
                parsed = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default
            return max(min_value, min(max_value, parsed))

        reason_codes_raw = hints.get("reason_codes")
        reason_codes: list[str] = []
        if isinstance(reason_codes_raw, list):
            for item in reason_codes_raw[:8]:
                text = str(item).strip()
                if text:
                    reason_codes.append(text)

        return {
            "internal_top_k": _as_int(hints.get("internal_top_k"), 3),
            "hybrid_top_k": _as_int(hints.get("hybrid_top_k"), 3),
            "query_focus": str(hints.get("query_focus") or "default"),
            "reason_codes": reason_codes,
        }

    @staticmethod
    def _extract_retriever_trace(retriever: object) -> dict[str, Any]:
        raw_trace = getattr(retriever, "last_trace", None)
        if isinstance(raw_trace, dict):
            return dict(raw_trace)
        return {}

    def _flow_event(
        self,
        *,
        stage: str,
        status: str,
        docs: List[Document],
        note: str,
        component: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        enriched_payload = {
            "document_count": len(docs),
            "source_counts": self._source_counts(docs),
            "retrieved_ids": [doc.id for doc in docs[:8]],
        }
        if isinstance(payload, dict):
            enriched_payload.update(payload)
        return {
            "event_id": f"evt-{uuid4().hex[:10]}",
            "stage": stage,
            "timestamp": self._now_iso(),
            "status": status,
            "source_count": len(self._source_counts(docs)),
            "note": note,
            "detail": note,
            "component": component or "rag_pipeline",
            "payload": enriched_payload,
        }

    def _context_relevance(self, query: str, docs: List[Document]) -> float:
        query_tokens = self._tokenize(query)
        if not query_tokens or not docs:
            return 0.0
        best_score = 0.0
        for doc in docs:
            doc_tokens = self._tokenize(doc.text)
            if not doc_tokens:
                continue
            overlap = len(query_tokens.intersection(doc_tokens))
            score = overlap / max(len(query_tokens), 1)
            if score > best_score:
                best_score = score
        return best_score

    @staticmethod
    def _format_doc_context(doc: Document) -> str:
        metadata = doc.metadata or {}
        source = str(metadata.get("source") or "unknown")
        url = str(metadata.get("url") or "")
        score = metadata.get("score", 0.0)
        try:
            score_txt = f"{float(score):.4f}"
        except (TypeError, ValueError):
            score_txt = "0.0000"
        meta_bits = f"source={source}; score={score_txt}"
        if url:
            meta_bits = f"{meta_bits}; url={url}"
        return f"- ({doc.id}) [{meta_bits}] {doc.text}"

    @classmethod
    def _build_prompt(cls, query: str, docs: List[Document]) -> str:
        context = "\n".join(cls._format_doc_context(doc) for doc in docs)
        return (
            "Answer using only retrieved context.\n"
            "If context is insufficient, still provide a concise safe answer "
            "using general medical knowledge.\n"
            "Do not answer that there is no context; provide useful next steps safely.\n"
            f"User query: {query}\n"
            f"Retrieved context:\n{context}"
        )

    @staticmethod
    def _build_no_rag_prompt(query: str) -> str:
        return (
            "User asks a health/medical question.\n"
            "Retrieved context is empty or irrelevant.\n"
            "Provide a useful, concise, safety-first answer in Vietnamese.\n"
            "Do not claim you cannot answer due to missing context.\n"
            "If the query is comparative (e.g., compares diets/treatments), "
            "provide a balanced comparison and practical decision criteria.\n"
            "Only include urgent warning signs when the query is about symptoms or acute risk.\n"
            "Suggest consulting a clinician when needed.\n"
            f"User query: {query}"
        )

    @staticmethod
    def _safe_helpful_answer(query: str, docs: List[Document]) -> str:
        if docs:
            source_ids = ", ".join(doc.id for doc in docs[:3])
            return (
                "Thong tin hien co cho thay can danh gia theo muc tieu dieu tri, "
                "benh nen va thuoc dang dung. "
                f"Nguon tham chieu gan nhat: {source_ids}. "
                "Ban nen theo doi trieu chung bat thuong, tranh tu y tang lieu, "
                "va trao doi bac si/duoc si de ca nhan hoa khuyen nghi."
            )
        return (
            "Voi cau hoi nay, ban co the ap dung nguyen tac an toan: "
            "dung thuoc dung lieu, theo doi trieu chung bat thuong, "
            "va uu tien tham van bac si neu co benh nen hoac dang dung nhieu thuoc."
        )

    @classmethod
    def _postprocess_answer(cls, answer: str, query: str, docs: List[Document]) -> str:
        cleaned = (answer or "").strip()
        if not cleaned:
            return cls._safe_helpful_answer(query, docs)
        blocked_phrases = {
            "khong co thong tin tu ngu canh",
            "không có thông tin từ ngữ cảnh",
            "khong du thong tin tu ngu canh",
            "insufficient context",
            "no context",
            "cannot answer due to missing context",
        }
        lowered = cleaned.lower()
        if any(phrase in lowered for phrase in blocked_phrases):
            return cls._safe_helpful_answer(query, docs)
        return cleaned

    def _build_context_debug(
        self,
        *,
        relevance: float,
        threshold: float,
        used_stages: List[str],
        docs: List[Document],
        low_context_before_external: bool,
        external_attempted: bool,
        planner_hints: dict[str, Any],
        retrieval_trace: dict[str, Any],
    ) -> dict[str, Any]:
        context_debug = {
            "relevance": round(float(relevance), 4),
            "low_context_threshold": round(float(threshold), 4),
            "used_stages": used_stages,
            "source_counts": self._source_counts(docs),
            "low_context_before_external": low_context_before_external,
            "external_attempted": external_attempted,
            "planner_hints": planner_hints,
            "retrieval_trace": retrieval_trace,
            "trace_version": "rag-v2",
        }
        return context_debug

    @staticmethod
    def _serialize_context(docs: List[Document]) -> List[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for doc in docs:
            metadata = doc.metadata or {}
            serialized.append(
                {
                    "id": doc.id,
                    "text": doc.text,
                    "source": str(metadata.get("source") or "unknown"),
                    "url": str(metadata.get("url") or ""),
                    "score": metadata.get("score"),
                }
            )
        return serialized

    def run(
        self,
        query: str,
        *,
        low_context_threshold: float = 0.15,
        deepseek_fallback_enabled: bool = True,
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
        planner_hints: dict[str, Any] | None = None,
        generation_enabled: bool = True,
    ) -> RagResult:
        run_started = perf_counter()
        planner_active = isinstance(planner_hints, dict) and bool(planner_hints)
        normalized_hints = self._normalize_planner_hints(planner_hints)
        internal_top_k = int(normalized_hints["internal_top_k"])
        hybrid_top_k = int(normalized_hints["hybrid_top_k"])
        threshold = max(0.0, min(1.0, low_context_threshold))
        used_stages: list[str] = ["internal_retrieval"]
        if planner_active:
            used_stages.insert(0, "planner")
        external_attempted = False
        flow_events: list[dict[str, Any]] = []
        retrieval_trace: dict[str, Any] = {
            "planner_hints": normalized_hints,
            "internal_top_k": internal_top_k,
            "hybrid_top_k": hybrid_top_k,
            "evidence_search_enforced": bool(settings.rag_force_search_index),
            "external_attempted": False,
            "relevance": 0.0,
            "documents": [],
        }

        if planner_active:
            flow_events.append(
                self._flow_event(
                    stage="planner",
                    status="completed",
                    docs=[],
                    note="Planner selected retrieval strategy.",
                    component="planner",
                    payload={
                        "query_focus": normalized_hints.get("query_focus"),
                        "reason_codes": normalized_hints.get("reason_codes"),
                        "internal_top_k": internal_top_k,
                        "hybrid_top_k": hybrid_top_k,
                    },
                )
            )

        flow_events.append(
            self._flow_event(
                stage="internal_retrieval",
                status="started",
                docs=[],
                note="Internal retrieval started.",
                component="retrieval",
                payload={"top_k": internal_top_k},
            )
        )
        flow_events.append(
            self._flow_event(
                stage="evidence_search",
                status="started",
                docs=[],
                note="Evidence search phase started (internal corpus).",
                component="retrieval",
                payload={"phase": "internal", "top_k": internal_top_k},
            )
        )
        docs: List[Document] = []
        try:
            docs = self.retriever.retrieve_internal(
                query,
                top_k=internal_top_k,
                file_retrieval_enabled=file_retrieval_enabled,
                rag_sources=rag_sources,
                uploaded_documents=uploaded_documents,
            )
        except Exception as exc:
            retrieval_trace["internal_error"] = exc.__class__.__name__
            flow_events.append(
                self._flow_event(
                    stage="internal_retrieval",
                    status="error",
                    docs=[],
                    note=f"Internal retrieval failed: {exc.__class__.__name__}.",
                    component="retrieval",
                    payload={"error": exc.__class__.__name__},
                )
            )
            flow_events.append(
                self._flow_event(
                    stage="evidence_search",
                    status="warning",
                    docs=[],
                    note="Evidence search degraded; no internal context available.",
                    component="retrieval",
                    payload={"phase": "internal", "error": exc.__class__.__name__},
                )
            )
            flow_events.append(
                self._flow_event(
                    stage="evidence_index",
                    status="completed",
                    docs=[],
                    note="Evidence index completed with zero candidate documents.",
                    component="retrieval",
                    payload={"phase": "internal", "selected_count": 0},
                )
            )
        retrieval_trace["internal"] = self._extract_retriever_trace(self.retriever)
        internal_trace = (
            retrieval_trace["internal"] if isinstance(retrieval_trace["internal"], dict) else {}
        )
        internal_search = (
            internal_trace.get("search_phase")
            if isinstance(internal_trace.get("search_phase"), dict)
            else {}
        )
        internal_index = (
            internal_trace.get("index_phase")
            if isinstance(internal_trace.get("index_phase"), dict)
            else {}
        )
        retrieval_trace["search_phase"] = internal_search
        retrieval_trace["index_phase"] = internal_index
        retrieval_trace["search_plan"] = {
            "query": query,
            "query_terms": internal_search.get("query_terms", []),
            "top_k": internal_top_k,
            "phase": "internal",
            "total_candidates": internal_search.get("total_candidates", len(docs)),
            "duration_ms": internal_search.get("duration_ms"),
        }
        retrieval_trace["source_attempts"] = internal_search.get("connectors_attempted", [])
        retrieval_trace["index_summary"] = {
            "before_dedupe_count": internal_index.get("before_dedupe_count"),
            "after_dedupe_count": internal_index.get("after_dedupe_count"),
            "selected_count": internal_index.get("selected_count"),
            "duration_ms": internal_index.get("duration_ms"),
        }
        retrieval_trace["crawl_summary"] = {}
        flow_events.append(
            self._flow_event(
                stage="evidence_search",
                status="completed",
                docs=docs,
                note=(
                    f"Evidence search completed with "
                    f"{int(internal_search.get('total_candidates') or len(docs))} candidate(s)."
                ),
                component="retrieval",
                payload={"phase": "internal", **internal_search},
            )
        )
        flow_events.append(
            self._flow_event(
                stage="evidence_index",
                status="started",
                docs=docs,
                note="Evidence index/rerank started.",
                component="retrieval",
                payload={"phase": "internal", "top_k": internal_top_k},
            )
        )
        flow_events.append(
            self._flow_event(
                stage="evidence_index",
                status="completed",
                docs=docs,
                note=(
                    "Evidence index completed with "
                    f"{int(internal_index.get('selected_count') or len(docs))} "
                    "selected document(s)."
                ),
                component="retrieval",
                payload={"phase": "internal", **internal_index},
            )
        )
        flow_events.append(
            self._flow_event(
                stage="internal_retrieval",
                status="completed",
                docs=docs,
                note=f"Retrieved {len(docs)} internal document(s).",
                component="retrieval",
                payload={"top_docs": self._trace_doc_rows(docs)},
            )
        )

        relevance_score = self._context_relevance(query, docs)
        retrieval_trace["relevance"] = round(float(relevance_score), 4)
        low_context_before_external = relevance_score < threshold
        retrieval_trace["low_context_before_external"] = low_context_before_external

        if (
            low_context_before_external
            and scientific_retrieval_enabled
            and settings.rag_external_connectors_enabled
        ):
            external_attempted = True
            used_stages.append("external_scientific_retrieval")
            flow_events.append(
                self._flow_event(
                    stage="external_scientific_retrieval",
                    status="started",
                    docs=docs,
                    note=(
                        "Low context detected; expanding retrieval via external "
                        "medical connectors."
                    ),
                    component="retrieval",
                    payload={
                        "top_k": hybrid_top_k,
                        "web_retrieval_enabled": web_retrieval_enabled,
                    },
                )
            )
            flow_events.append(
                self._flow_event(
                    stage="evidence_search",
                    status="started",
                    docs=docs,
                    note="Evidence search phase started (hybrid external connectors).",
                    component="retrieval",
                    payload={
                        "phase": "hybrid_external",
                        "top_k": hybrid_top_k,
                        "scientific_retrieval_enabled": True,
                        "web_retrieval_enabled": web_retrieval_enabled,
                    },
                )
            )
            try:
                docs = self.retriever.retrieve(
                    query,
                    top_k=hybrid_top_k,
                    scientific_retrieval_enabled=True,
                    web_retrieval_enabled=web_retrieval_enabled,
                    file_retrieval_enabled=file_retrieval_enabled,
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                )
                retrieval_trace["hybrid"] = self._extract_retriever_trace(self.retriever)
                hybrid_trace = (
                    retrieval_trace["hybrid"] if isinstance(retrieval_trace["hybrid"], dict) else {}
                )
                hybrid_search = (
                    hybrid_trace.get("search_phase")
                    if isinstance(hybrid_trace.get("search_phase"), dict)
                    else {}
                )
                hybrid_index = (
                    hybrid_trace.get("index_phase")
                    if isinstance(hybrid_trace.get("index_phase"), dict)
                    else {}
                )
                retrieval_trace["search_phase"] = hybrid_search
                retrieval_trace["index_phase"] = hybrid_index
                retrieval_trace["search_plan"] = {
                    "query": query,
                    "query_terms": hybrid_search.get("query_terms", []),
                    "top_k": hybrid_top_k,
                    "phase": "hybrid_external",
                    "total_candidates": hybrid_search.get("total_candidates", len(docs)),
                    "duration_ms": hybrid_search.get("duration_ms"),
                }
                retrieval_trace["source_attempts"] = hybrid_search.get("connectors_attempted", [])
                retrieval_trace["index_summary"] = {
                    "before_dedupe_count": hybrid_index.get("before_dedupe_count"),
                    "after_dedupe_count": hybrid_index.get("after_dedupe_count"),
                    "selected_count": hybrid_index.get("selected_count"),
                    "duration_ms": hybrid_index.get("duration_ms"),
                }
                retrieval_trace["crawl_summary"] = (
                    hybrid_search.get("crawl_summary")
                    if isinstance(hybrid_search.get("crawl_summary"), dict)
                    else {}
                )
                relevance_score = self._context_relevance(query, docs)
                retrieval_trace["relevance"] = round(float(relevance_score), 4)
                hybrid_candidate_count = int(
                    hybrid_search.get("total_candidates") or len(docs)
                )
                flow_events.append(
                    self._flow_event(
                        stage="evidence_search",
                        status="completed",
                        docs=docs,
                        note=f"Hybrid evidence search completed with {hybrid_candidate_count} candidate(s).",
                        component="retrieval",
                        payload={"phase": "hybrid_external", **hybrid_search},
                    )
                )
                flow_events.append(
                    self._flow_event(
                        stage="evidence_index",
                        status="started",
                        docs=docs,
                        note="Hybrid evidence index/rerank started.",
                        component="retrieval",
                        payload={"phase": "hybrid_external", "top_k": hybrid_top_k},
                    )
                )
                flow_events.append(
                    self._flow_event(
                        stage="evidence_index",
                        status="completed",
                        docs=docs,
                        note=(
                            "Hybrid evidence index completed with "
                            f"{int(hybrid_index.get('selected_count') or len(docs))} "
                            "selected document(s)."
                        ),
                        component="retrieval",
                        payload={"phase": "hybrid_external", **hybrid_index},
                    )
                )
                flow_events.append(
                    self._flow_event(
                        stage="external_scientific_retrieval",
                        status="completed",
                        docs=docs,
                        note=(
                            "External retrieval merged; "
                            f"{len(docs)} document(s) retained after re-ranking."
                        ),
                        component="retrieval",
                        payload={"top_docs": self._trace_doc_rows(docs)},
                    )
                )
            except Exception as exc:
                used_stages.append("external_scientific_retrieval_error")
                retrieval_trace["hybrid"] = self._extract_retriever_trace(self.retriever)
                retrieval_trace["hybrid_error"] = exc.__class__.__name__
                hybrid_trace = (
                    retrieval_trace["hybrid"] if isinstance(retrieval_trace["hybrid"], dict) else {}
                )
                retrieval_trace["search_phase"] = (
                    hybrid_trace.get("search_phase")
                    if isinstance(hybrid_trace.get("search_phase"), dict)
                    else {}
                )
                retrieval_trace["index_phase"] = (
                    hybrid_trace.get("index_phase")
                    if isinstance(hybrid_trace.get("index_phase"), dict)
                    else {}
                )
                retrieval_trace["search_plan"] = {
                    "query": query,
                    "query_terms": [],
                    "top_k": hybrid_top_k,
                    "phase": "hybrid_external",
                    "total_candidates": len(docs),
                }
                retrieval_trace["source_attempts"] = []
                retrieval_trace["index_summary"] = {
                    "before_dedupe_count": len(docs),
                    "after_dedupe_count": len(docs),
                    "selected_count": len(docs),
                }
                retrieval_trace["crawl_summary"] = {}
                flow_events.append(
                    self._flow_event(
                        stage="evidence_search",
                        status="warning",
                        docs=docs,
                        note=(
                            "Hybrid evidence search degraded due to retrieval error. "
                            f"error={exc.__class__.__name__}"
                        ),
                        component="retrieval",
                        payload={"phase": "hybrid_external", "error": exc.__class__.__name__},
                    )
                )
                flow_events.append(
                    self._flow_event(
                        stage="evidence_index",
                        status="completed",
                        docs=docs,
                        note="Evidence index completed with currently available context.",
                        component="retrieval",
                        payload={"phase": "hybrid_external", "selected_count": len(docs)},
                    )
                )
                flow_events.append(
                    self._flow_event(
                        stage="external_scientific_retrieval",
                        status="error",
                        docs=docs,
                        note=(
                            "External retrieval failed; falling back to available context. "
                            f"error={exc.__class__.__name__}"
                        ),
                        component="retrieval",
                        payload={"error": exc.__class__.__name__},
                    )
                )

        has_relevant_context = relevance_score >= threshold
        ids = [d.id for d in docs]
        retrieval_trace["external_attempted"] = external_attempted
        retrieval_trace["documents"] = self._trace_doc_rows(docs, limit=8)
        retrieval_trace["document_count"] = len(docs)
        active_trace = (
            retrieval_trace.get("hybrid")
            if isinstance(retrieval_trace.get("hybrid"), dict)
            else retrieval_trace.get("internal")
        )
        active_trace = active_trace if isinstance(active_trace, dict) else {}
        retrieval_trace["search_plan"] = (
            active_trace.get("search_plan")
            if isinstance(active_trace.get("search_plan"), dict)
            else {
                "query": query,
                "keywords": sorted(self._tokenize(query)),
                "top_k": hybrid_top_k if external_attempted else internal_top_k,
                "scientific_retrieval_enabled": bool(scientific_retrieval_enabled),
                "web_retrieval_enabled": bool(web_retrieval_enabled),
                "file_retrieval_enabled": bool(file_retrieval_enabled),
            }
        )
        source_attempts = active_trace.get("source_attempts")
        if isinstance(source_attempts, list):
            retrieval_trace["source_attempts"] = source_attempts
        else:
            search_phase = (
                active_trace.get("search_phase")
                if isinstance(active_trace.get("search_phase"), dict)
                else {}
            )
            retrieval_trace["source_attempts"] = search_phase.get("connectors_attempted", [])

        retrieval_trace["index_summary"] = (
            active_trace.get("index_summary")
            if isinstance(active_trace.get("index_summary"), dict)
            else {
                "before_dedupe": len(docs),
                "after_dedupe": len(docs),
                "selected_count": len(docs),
            }
        )
        retrieval_trace["crawl_summary"] = (
            active_trace.get("crawl_summary")
            if isinstance(active_trace.get("crawl_summary"), dict)
            else {}
        )

        def _build_result(
            *,
            answer: str,
            model_used: str,
            generation_trace: dict[str, Any],
        ) -> RagResult:
            context_debug = self._build_context_debug(
                relevance=relevance_score,
                threshold=threshold,
                used_stages=used_stages,
                docs=docs,
                low_context_before_external=low_context_before_external,
                external_attempted=external_attempted,
                planner_hints=normalized_hints,
                retrieval_trace=retrieval_trace,
            )
            context_debug["pipeline_duration_ms"] = round(
                (perf_counter() - run_started) * 1000.0, 3
            )
            trace = {
                "planner": {
                    "query_focus": normalized_hints.get("query_focus"),
                    "reason_codes": normalized_hints.get("reason_codes"),
                    "internal_top_k": internal_top_k,
                    "hybrid_top_k": hybrid_top_k,
                },
                "retrieval": retrieval_trace,
                "generation": generation_trace,
            }
            return RagResult(
                query=query,
                retrieved_ids=ids,
                answer=answer,
                model_used=model_used,
                retrieved_context=self._serialize_context(docs),
                context_debug=context_debug,
                flow_events=flow_events,
                trace=trace,
            )

        if not generation_enabled:
            used_stages.append("retrieval_only")
            flow_events.append(
                self._flow_event(
                    stage="llm_generation",
                    status="skipped",
                    docs=docs,
                    note="Generation disabled for retrieval-only pass.",
                    component="generation",
                    payload={"generation_enabled": False},
                )
            )
            return _build_result(
                answer=self._safe_helpful_answer(query, docs),
                model_used="retrieval-only-v1",
                generation_trace={
                    "mode": "retrieval_only",
                    "generation_enabled": False,
                },
            )

        if self._llm_client and self._deepseek_api_key:
            try:
                if not has_relevant_context and not deepseek_fallback_enabled:
                    used_stages.append("local_synthesis_no_fallback")
                    flow_events.append(
                        self._flow_event(
                            stage="answer_synthesis",
                            status="completed",
                            docs=docs,
                            note=(
                                "Low-context fallback disabled; returned "
                                "deterministic local synthesis."
                            ),
                            component="generation",
                            payload={
                                "fallback_mode": "forced_local",
                                "has_relevant_context": False,
                            },
                        )
                    )
                    answer = self._postprocess_answer(
                        self._local_synthesis(query, docs), query, docs
                    )
                    return _build_result(
                        answer=answer,
                        model_used="local-synth-v1-no-fallback",
                        generation_trace={
                            "mode": "local_synthesis",
                            "fallback_reason": "deepseek_fallback_disabled",
                        },
                    )

                used_stages.append("llm_generation")
                flow_events.append(
                    self._flow_event(
                        stage="llm_generation",
                        status="started",
                        docs=docs,
                        note="Generating answer with LLM.",
                        component="generation",
                        payload={
                            "has_relevant_context": has_relevant_context,
                            "prompt_mode": "retrieval" if has_relevant_context else "no_rag",
                        },
                    )
                )
                prompt = (
                    self._build_prompt(query, docs)
                    if has_relevant_context
                    else self._build_no_rag_prompt(query)
                )
                response = self._llm_client.generate(
                    prompt=prompt,
                    system_prompt=(
                        "You are CLARA clinical assistant. Be concise, safe, and cite source ids."
                    ),
                )
                flow_events.append(
                    self._flow_event(
                        stage="llm_generation",
                        status="completed",
                        docs=docs,
                        note="LLM answer generated successfully.",
                        component="generation",
                        payload={"model": response.model or self._llm_client.model},
                    )
                )
                return _build_result(
                    answer=self._postprocess_answer(response.content, query, docs),
                    model_used=response.model or self._llm_client.model,
                    generation_trace={
                        "mode": "llm",
                        "model": response.model or self._llm_client.model,
                        "has_relevant_context": has_relevant_context,
                    },
                )
            except Exception as exc:
                used_stages.append("llm_error_fallback")
                flow_events.append(
                    self._flow_event(
                        stage="llm_generation",
                        status="error",
                        docs=docs,
                        note="LLM generation failed; switching to deterministic fallback.",
                        component="generation",
                        payload={"error": exc.__class__.__name__},
                    )
                )

        used_stages.append("local_synthesis")
        flow_events.append(
            self._flow_event(
                stage="answer_synthesis",
                status="completed",
                docs=docs,
                note="Returned deterministic local synthesis.",
                component="generation",
                payload={"fallback_mode": "local_synth"},
            )
        )
        return _build_result(
            answer=self._postprocess_answer(self._local_synthesis(query, docs), query, docs),
            model_used="local-synth-v1",
            generation_trace={
                "mode": "local_synthesis",
                "fallback_reason": "llm_unavailable_or_failed",
            },
        )


RagPipelineP0 = RagPipelineP1
