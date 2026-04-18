from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, List, Protocol
import unicodedata
from uuid import uuid4

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient, DeepSeekResponse
from clara_ml.rag.graphrag import GraphRagSidecar
from clara_ml.rag.retrieval.text_utils import analyze_query_profile, query_terms
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

    _PROMPT_MAX_DOCS = 8
    _PROMPT_MAX_DOC_CHARS = 520
    _PROMPT_RETRY_MAX_DOCS = 5
    _PROMPT_RETRY_MAX_DOC_CHARS = 280
    _LONG_FORM_ORCHESTRATOR_MODES = {
        "deep",
        "deep-beta",
        "deep_beta",
        "deep_research",
        "long",
    }
    _STANDARD_ORCHESTRATOR_MODES = {"fast", "quick", "default", "standard"}
    _SCIENTIFIC_PROVIDER_KEYS = {
        "pubmed",
        "europepmc",
        "semantic_scholar",
        "openalex",
        "crossref",
        "clinicaltrials",
        "openfda",
        "dailymed",
        "rxnorm",
        "external_scientific",
    }
    _WEB_PROVIDER_KEYS = {"searxng", "searxng-crawl", "web_crawl"}

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
                retries_per_base=settings.deepseek_retries_per_base,
                retry_backoff_seconds=settings.deepseek_retry_backoff_seconds,
                max_concurrency=settings.llm_global_max_concurrency,
                min_interval_seconds=settings.llm_global_min_interval_seconds,
                request_jitter_seconds=settings.llm_global_jitter_seconds,
            )
        self._graphrag = GraphRagSidecar()

    @staticmethod
    def _local_synthesis(query: str, docs: List[Document], *, answer_language: str = "vi") -> str:
        def _compact(text: str, max_len: int = 180) -> str:
            clean = " ".join(str(text or "").split()).strip()
            if len(clean) <= max_len:
                return clean
            return f"{clean[: max_len - 3]}..."

        if not docs:
            if answer_language == "en":
                return (
                    "## Quick conclusion\n"
                    "There is not enough strong retrieved evidence yet for a firm conclusion, so the answer is kept cautious and safety-first.\n\n"
                    "## Key points\n"
                    f"- Question under review: `{query}`.\n"
                    "- The current session does not yet provide enough context for a personalized recommendation.\n"
                    "- The next step is to verify against primary sources or add more clinical details before concluding.\n\n"
                    "## Practical application\n"
                    "- If a decision is needed now, narrow the question to treatment goal, comorbidities, active medications, and urgency.\n"
                    "- With stronger guideline or case-specific context, a more tailored answer can be produced.\n\n"
                    "## Important caveats\n"
                    "- Cross-check with primary sources such as official labels, guidelines, or a clinician/pharmacist.\n"
                    "- Do not self-prescribe or adjust dosing without qualified advice.\n\n"
                    "<!-- LOCAL_FALLBACK_V1 -->"
                )
            return (
                "## Kết luận nhanh\n"
                "Hiện chưa có đủ bằng chứng truy xuất mạnh để kết luận dứt khoát, nên câu trả lời được giữ ở mức thận trọng và an toàn.\n\n"
                "## Điểm chính\n"
                f"- Câu hỏi đang xét: `{query}`.\n"
                "- Chưa có ngữ cảnh đủ mạnh trong phiên hiện tại để xác nhận một khuyến nghị cá thể hóa.\n"
                "- Bước phù hợp lúc này là kiểm tra lại nguồn chính thống hoặc bổ sung dữ liệu lâm sàng liên quan trước khi kết luận.\n\n"
                "## Ứng dụng thực tế\n"
                "- Nếu cần quyết định ngay, nên quay về câu hỏi hẹp hơn: mục tiêu điều trị, bệnh nền, thuốc đang dùng và mức độ khẩn cấp.\n"
                "- Khi có thêm dữ liệu lâm sàng hoặc nguồn guideline cụ thể, có thể trả lời sâu hơn và sát tình huống hơn.\n\n"
                "## Lưu ý an toàn\n"
                "- Ưu tiên đối chiếu nguồn chính thống (nhãn thuốc, guideline, bác sĩ/dược sĩ).\n"
                "- Không tự ý kê đơn hoặc chỉnh liều khi chưa có tư vấn chuyên môn.\n\n"
                "<!-- LOCAL_FALLBACK_V1 -->"
            )

        evidence_summary = _compact(" ".join(doc.text for doc in docs[:3]), max_len=280)
        if answer_language == "en":
            return (
                "## Quick conclusion\n"
                "The retrieved evidence supports a cautious answer with context-dependent trade-offs rather than an overconfident universal conclusion.\n\n"
                "## Key points\n"
                f"- Question under review: `{query}`.\n"
                f"- Main retrieved signal: {evidence_summary}.\n"
                "- Interpret the answer around treatment goal, comorbidity burden, concurrent medications, and urgency.\n"
                "- The retrieved signal should guide the next question, not replace direct clinical judgement.\n\n"
                "## Practical application\n"
                "- Use the answer to narrow the decision, compare options, and identify what must be clarified next.\n"
                "- For a patient-specific decision, add age, comorbidities, polypharmacy context, and treatment goals.\n\n"
                "## Important caveats\n"
                "- Cross-check against primary sources before applying anything to care decisions.\n"
                "- If there is comorbidity, polypharmacy, or severe symptoms, escalate to a clinician promptly.\n\n"
                "<!-- LOCAL_FALLBACK_V1 -->"
            )
        return (
            "## Kết luận nhanh\n"
            "Bằng chứng truy xuất hiện có cho thấy nên trả lời theo hướng thận trọng, bám vào tín hiệu mạnh nhất thay vì kết luận quá mức.\n\n"
            "## Điểm chính\n"
            f"- Câu hỏi đang xét: `{query}`.\n"
            f"- Tín hiệu chính đang có: {evidence_summary}.\n"
            "- Cần diễn giải kết luận theo mục tiêu điều trị, bệnh nền, thuốc đang dùng và mức độ khẩn cấp.\n"
            "- Phần truy xuất hiện tại giúp định hướng bước tiếp theo, nhưng chưa thay thế đánh giá lâm sàng trực tiếp.\n\n"
            "## Ứng dụng thực tế\n"
            "- Dùng câu trả lời này để thu hẹp quyết định, so sánh các lựa chọn và xác định điểm cần làm rõ tiếp theo.\n"
            "- Nếu áp dụng cho một ca cụ thể, cần ghép thêm tuổi, bệnh nền, đa thuốc và mục tiêu điều trị.\n\n"
            "## Lưu ý an toàn\n"
            "- Ưu tiên kiểm chứng chéo bằng nguồn chính thống trước khi áp dụng vào quyết định y khoa.\n"
            "- Nếu có bệnh nền/đa thuốc/dấu hiệu nặng, cần trao đổi bác sĩ ngay.\n\n"
            "<!-- LOCAL_FALLBACK_V1 -->"
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", text.lower()) if token}

    @staticmethod
    def _ascii_fold(text: str) -> str:
        normalized = unicodedata.normalize("NFD", str(text or ""))
        without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return without_marks.lower()

    @staticmethod
    def _summarize_llm_exception(exc: Exception) -> str:
        message = str(exc or "").strip().lower()
        if "http_502" in message:
            return "llm_http_502"
        if "http_503" in message:
            return "llm_http_503"
        if "http_504" in message:
            return "llm_http_504"
        if "http_429" in message:
            return "llm_http_429"
        if "timeout" in message:
            return "llm_timeout"
        if "auth" in message or "401" in message or "403" in message:
            return "llm_auth_failed"
        if "connection" in message or "connect" in message:
            return "llm_connection_failed"
        if "deepseek_request_failed" in message:
            return "llm_request_failed"
        return "llm_unavailable_or_failed"

    @staticmethod
    def _dedupe_queries(values: list[str], *, limit: int = 8) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in values:
            cleaned = " ".join(str(item or "").split()).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
            if len(deduped) >= max(int(limit), 1):
                break
        return deduped

    @classmethod
    def _build_query_plan(
        cls,
        query: str,
        *,
        planner_query_plan: object = None,
    ) -> dict[str, Any]:
        if isinstance(planner_query_plan, dict):
            source_queries = planner_query_plan.get("source_queries")
            decomposition = planner_query_plan.get("decomposition")
            if isinstance(source_queries, dict) and isinstance(decomposition, dict):
                return {
                    **planner_query_plan,
                    "original_query": str(planner_query_plan.get("original_query") or query),
                    "canonical_query": str(planner_query_plan.get("canonical_query") or query),
                    "source_queries": {
                        "internal": cls._dedupe_queries(
                            [str(item) for item in source_queries.get("internal", [])],
                            limit=8,
                        )
                        or [query],
                        "scientific": cls._dedupe_queries(
                            [str(item) for item in source_queries.get("scientific", [])],
                            limit=8,
                        )
                        or [query],
                        "web": cls._dedupe_queries(
                            [str(item) for item in source_queries.get("web", [])],
                            limit=8,
                        )
                        or [query],
                    },
                    "decomposition": {
                        "fast_pass_queries": cls._dedupe_queries(
                            [str(item) for item in decomposition.get("fast_pass_queries", [])],
                            limit=6,
                        )
                        or [query],
                        "deep_pass_queries": cls._dedupe_queries(
                            [str(item) for item in decomposition.get("deep_pass_queries", [])],
                            limit=12,
                        )
                        or [query],
                    },
                }

        cleaned_query = " ".join(str(query or "").split()).strip()
        folded_query = cls._ascii_fold(cleaned_query)
        profile = analyze_query_profile(cleaned_query)
        terms = query_terms(cleaned_query)
        primary = str(profile.get("primary_drug") or "").strip().lower()
        co_drugs_raw = profile.get("co_drugs")
        co_drugs = (
            [str(item).strip().lower() for item in co_drugs_raw if str(item).strip()]
            if isinstance(co_drugs_raw, list)
            else []
        )
        co_drug_phrase = ", ".join(co_drugs[:4]) if co_drugs else "common analgesics"
        canonical_query = cleaned_query
        if profile.get("is_ddi_query"):
            canonical_query = (
                f"{primary or 'index drug'} interaction with {co_drug_phrase} "
                "bleeding risk contraindication guidance"
            )
        elif folded_query != cleaned_query.lower():
            canonical_query = " ".join(terms[:8]).strip() or cleaned_query

        internal = cls._dedupe_queries(
            [
                cleaned_query,
                canonical_query,
                folded_query if folded_query != cleaned_query.lower() else "",
                " ".join(terms[:8]),
            ],
            limit=8,
        )
        scientific = cls._dedupe_queries(
            [
                canonical_query,
                " ".join(terms[:8]),
                f"{primary or 'index drug'} drug-drug interaction with {co_drug_phrase}"
                if profile.get("is_ddi_query")
                else "",
                cleaned_query,
            ],
            limit=8,
        )
        web = cls._dedupe_queries(
            [
                cleaned_query,
                canonical_query,
                f"{canonical_query} guideline",
                f"{canonical_query} safety warning",
            ],
            limit=8,
        )
        deep_pass_queries = cls._dedupe_queries(
            [
                canonical_query,
                f"{canonical_query} guideline recommendations",
                f"{canonical_query} systematic review meta-analysis",
                f"{canonical_query} adverse events contraindications",
                f"{canonical_query} contradictory findings subgroup caveats",
            ],
            limit=12,
        )
        return {
            "original_query": cleaned_query,
            "canonical_query": canonical_query,
            "source_queries": {
                "internal": internal or [cleaned_query],
                "scientific": scientific or [cleaned_query],
                "web": web or [cleaned_query],
            },
            "decomposition": {
                "fast_pass_queries": internal[:2] if internal else [cleaned_query],
                "deep_pass_queries": deep_pass_queries or [cleaned_query],
            },
            "query_terms": terms[:10],
            "is_ddi_query": bool(profile.get("is_ddi_query")),
        }

    @staticmethod
    def _source_query(query_plan: dict[str, Any], source_key: str, fallback: str) -> str:
        source_queries = (
            query_plan.get("source_queries") if isinstance(query_plan.get("source_queries"), dict) else {}
        )
        selected = source_queries.get(source_key)
        if isinstance(selected, list):
            for item in selected:
                text = " ".join(str(item or "").split()).strip()
                if text:
                    return text
        return fallback

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

    def _build_index_summary(
        self,
        docs: List[Document],
        *,
        before_dedupe_count: Any = None,
        after_dedupe_count: Any = None,
        selected_count: Any = None,
        duration_ms: Any = None,
        rerank: Any = None,
    ) -> dict[str, Any]:
        def _as_int(value: Any, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        before = _as_int(before_dedupe_count, len(docs))
        after = _as_int(after_dedupe_count, len(docs))
        selected = _as_int(selected_count, len(docs))
        parsed_duration: float | None = None
        try:
            if duration_ms is not None:
                parsed_duration = round(float(duration_ms), 3)
        except (TypeError, ValueError):
            parsed_duration = None

        rerank_payload = dict(rerank) if isinstance(rerank, dict) else {}
        neural_payload = (
            rerank_payload.get("neural") if isinstance(rerank_payload.get("neural"), dict) else {}
        )
        if "rerank_latency_ms" not in rerank_payload:
            rerank_payload["rerank_latency_ms"] = neural_payload.get("rerank_latency_ms")
        if "rerank_topn" not in rerank_payload:
            rerank_payload["rerank_topn"] = neural_payload.get("rerank_topn")
        if "rerank_model" not in rerank_payload:
            rerank_payload["rerank_model"] = neural_payload.get("rerank_model")
        if "rerank_timed_out" not in rerank_payload:
            rerank_payload["rerank_timed_out"] = bool(neural_payload.get("rerank_timed_out"))
        if "rerank_reason" not in rerank_payload:
            rerank_payload["rerank_reason"] = neural_payload.get("rerank_reason")
        if "rerank_cache_hit" not in rerank_payload:
            rerank_payload["rerank_cache_hit"] = bool(neural_payload.get("rerank_cache_hit"))
        if "rerank_cache_age_ms" not in rerank_payload:
            rerank_payload["rerank_cache_age_ms"] = neural_payload.get("rerank_cache_age_ms")
        return {
            "retrieved_count": len(docs),
            "source_counts": self._source_counts(docs),
            "before_dedupe_count": before,
            "after_dedupe_count": after,
            "before_dedupe": before,
            "after_dedupe": after,
            "selected_count": selected,
            "duration_ms": parsed_duration,
            "rerank_latency_ms": rerank_payload.get("rerank_latency_ms"),
            "rerank_topn": rerank_payload.get("rerank_topn"),
            "rerank_model": rerank_payload.get("rerank_model"),
            "rerank_timed_out": rerank_payload.get("rerank_timed_out"),
            "rerank_reason": rerank_payload.get("rerank_reason"),
            "rerank_cache_hit": rerank_payload.get("rerank_cache_hit"),
            "rerank_cache_age_ms": rerank_payload.get("rerank_cache_age_ms"),
            "rerank": rerank_payload,
        }

    def _should_force_external_retrieval(self, query: str, docs: List[Document]) -> bool:
        profile = analyze_query_profile(query)
        if bool(profile.get("is_ddi_query")):
            return True
        if len(docs) < 2:
            return True
        return len(self._source_counts(docs)) <= 1

    @staticmethod
    def _normalize_planner_hints(hints: object) -> dict[str, Any]:
        if not isinstance(hints, dict):
            return {
                "internal_top_k": 3,
                "hybrid_top_k": 3,
                "research_mode": "",
                "answer_language": "vi",
                "mode": "",
                "query_focus": "default",
                "ddi_critical_query": False,
                "reason_codes": [],
                "query_plan": {},
                "retrieval_stack_mode": "auto",
                "retrieval_budget": {},
                "graphrag_enabled_override": None,
                "external_connectors_enabled_override": None,
            }

        def _as_int(value: object, default: int, *, min_value: int = 1, max_value: int = 12) -> int:
            try:
                parsed = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default
            return max(min_value, min(max_value, parsed))

        def _as_optional_bool(value: object) -> bool | None:
            if isinstance(value, bool):
                return value
            text = str(value or "").strip().lower()
            if not text:
                return None
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False
            return None

        raw_stack_mode = str(hints.get("retrieval_stack_mode") or "").strip().lower()
        retrieval_stack_mode = "full" if raw_stack_mode == "full" else "auto"

        reason_codes_raw = hints.get("reason_codes")
        reason_codes: list[str] = []
        if isinstance(reason_codes_raw, list):
            for item in reason_codes_raw[:8]:
                text = str(item).strip()
                if text:
                    reason_codes.append(text)

        research_mode = str(hints.get("research_mode") or "").strip().lower()
        answer_language = str(hints.get("answer_language") or "vi").strip().lower()
        if answer_language != "en":
            answer_language = "vi"
        mode = str(hints.get("mode") or "").strip().lower()
        retrieval_budget_raw = (
            hints.get("retrieval_budget") if isinstance(hints.get("retrieval_budget"), dict) else {}
        )
        retrieval_budget: dict[str, int] = {}
        if retrieval_budget_raw:
            retrieval_budget = {
                "latency_budget_ms": _as_int(
                    retrieval_budget_raw.get("latency_budget_ms"),
                    0,
                    min_value=300,
                    max_value=12000,
                ),
                "max_search_rounds": _as_int(
                    retrieval_budget_raw.get("max_search_rounds"),
                    0,
                    min_value=1,
                    max_value=8,
                ),
                "max_connector_calls": _as_int(
                    retrieval_budget_raw.get("max_connector_calls"),
                    0,
                    min_value=0,
                    max_value=8,
                ),
                "max_documents": _as_int(
                    retrieval_budget_raw.get("max_documents"),
                    0,
                    min_value=1,
                    max_value=24,
                ),
                "top_k_cap": _as_int(
                    retrieval_budget_raw.get("top_k_cap"),
                    0,
                    min_value=1,
                    max_value=12,
                ),
            }
            retrieval_budget = {key: value for key, value in retrieval_budget.items() if value > 0}

        return {
            "internal_top_k": _as_int(hints.get("internal_top_k"), 3),
            "hybrid_top_k": _as_int(hints.get("hybrid_top_k"), 3),
            "research_mode": research_mode,
            "answer_language": answer_language,
            "mode": mode,
            "query_focus": str(hints.get("query_focus") or "default"),
            "ddi_critical_query": bool(hints.get("ddi_critical_query")),
            "reason_codes": reason_codes,
            "query_plan": hints.get("query_plan") if isinstance(hints.get("query_plan"), dict) else {},
            "retrieval_stack_mode": retrieval_stack_mode,
            "retrieval_budget": retrieval_budget,
            "graphrag_enabled_override": _as_optional_bool(hints.get("graphrag_enabled_override")),
            "external_connectors_enabled_override": _as_optional_bool(
                hints.get("external_connectors_enabled_override")
            ),
        }

    @staticmethod
    def _resolve_orchestrator_mode(
        *,
        generation_enabled: bool,
        planner_hints: dict[str, Any],
        query_plan: dict[str, Any],
    ) -> str:
        if not generation_enabled:
            return "retrieval_only"
        candidates = [
            planner_hints.get("research_mode"),
            planner_hints.get("mode"),
            query_plan.get("research_mode"),
        ]
        for value in candidates:
            text = str(value or "").strip().lower()
            if text in RagPipelineP1._LONG_FORM_ORCHESTRATOR_MODES:
                return "deep"
            if text in RagPipelineP1._STANDARD_ORCHESTRATOR_MODES:
                return "fast"
        return "fast"

    @staticmethod
    def _is_long_form_orchestrator_mode(mode: str) -> bool:
        return str(mode or "").strip().lower() in RagPipelineP1._LONG_FORM_ORCHESTRATOR_MODES

    @staticmethod
    def _infer_retrieval_complexity(
        *,
        query_profile: dict[str, Any],
        planner_hints: dict[str, Any],
        query_plan: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        signals: list[str] = []
        score = 0
        is_ddi_query = bool(query_profile.get("is_ddi_query"))
        if is_ddi_query:
            score += 2
            signals.append("ddi_query")

        reason_codes_raw = planner_hints.get("reason_codes")
        reason_codes = (
            {str(item).strip().lower() for item in reason_codes_raw if str(item).strip()}
            if isinstance(reason_codes_raw, list)
            else set()
        )
        is_ddi_critical = bool(planner_hints.get("ddi_critical_query")) or bool(
            query_plan.get("is_ddi_critical_query")
        )
        if "ddi_critical_query" in reason_codes:
            is_ddi_critical = True
        if is_ddi_critical:
            score += 1
            signals.append("ddi_critical")
        if mode == "deep":
            score += 1
            signals.append("deep_mode")

        query_terms_raw = query_profile.get("query_terms")
        query_terms = query_terms_raw if isinstance(query_terms_raw, list) else []
        if len(query_terms) >= 6:
            score += 1
            signals.append("long_query_terms")

        co_drugs_raw = query_profile.get("co_drugs")
        co_drugs = co_drugs_raw if isinstance(co_drugs_raw, list) else []
        if len(co_drugs) >= 2:
            score += 1
            signals.append("multi_codrug_focus")

        if "evidence_heavy_query" in reason_codes:
            score += 1
            signals.append("evidence_heavy_query")

        decomposition = query_plan.get("decomposition") if isinstance(query_plan, dict) else {}
        deep_pass_queries = (
            decomposition.get("deep_pass_queries")
            if isinstance(decomposition, dict)
            else []
        )
        if isinstance(deep_pass_queries, list) and len(deep_pass_queries) >= 6:
            score += 1
            signals.append("multi_pass_decomposition")

        if score >= 5:
            level = "high"
        elif score >= 3:
            level = "medium"
        else:
            level = "low"
        return {
            "level": level,
            "score": score,
            "signals": signals,
            "is_ddi_query": is_ddi_query,
            "is_ddi_critical_query": is_ddi_critical,
        }

    @staticmethod
    def _orchestrator_budgets(*, mode: str, complexity_level: str) -> dict[str, Any]:
        budget_table = {
            "retrieval_only": {
                "low": {
                    "latency_budget_ms": 900,
                    "max_search_rounds": 1,
                    "max_connector_calls": 1,
                    "max_documents": 5,
                    "top_k_cap": 5,
                },
                "medium": {
                    "latency_budget_ms": 1200,
                    "max_search_rounds": 1,
                    "max_connector_calls": 2,
                    "max_documents": 6,
                    "top_k_cap": 6,
                },
                "high": {
                    "latency_budget_ms": 1500,
                    "max_search_rounds": 1,
                    "max_connector_calls": 2,
                    "max_documents": 7,
                    "top_k_cap": 7,
                },
            },
            "fast": {
                "low": {
                    "latency_budget_ms": 1000,
                    "max_search_rounds": 1,
                    "max_connector_calls": 1,
                    "max_documents": 6,
                    "top_k_cap": 6,
                },
                "medium": {
                    "latency_budget_ms": 1500,
                    "max_search_rounds": 2,
                    "max_connector_calls": 2,
                    "max_documents": 8,
                    "top_k_cap": 8,
                },
                "high": {
                    "latency_budget_ms": 1900,
                    "max_search_rounds": 2,
                    "max_connector_calls": 3,
                    "max_documents": 10,
                    "top_k_cap": 9,
                },
            },
            "deep": {
                "low": {
                    "latency_budget_ms": 1800,
                    "max_search_rounds": 2,
                    "max_connector_calls": 2,
                    "max_documents": 8,
                    "top_k_cap": 8,
                },
                "medium": {
                    "latency_budget_ms": 2600,
                    "max_search_rounds": 3,
                    "max_connector_calls": 3,
                    "max_documents": 10,
                    "top_k_cap": 10,
                },
                "high": {
                    "latency_budget_ms": 3400,
                    "max_search_rounds": 4,
                    "max_connector_calls": 4,
                    "max_documents": 12,
                    "top_k_cap": 12,
                },
            },
        }
        mode_key = mode if mode in budget_table else "fast"
        level = complexity_level if complexity_level in {"low", "medium", "high"} else "medium"
        return dict(budget_table[mode_key][level])

    @classmethod
    def _build_retrieval_orchestrator_plan(
        cls,
        *,
        query_profile: dict[str, Any],
        query_plan: dict[str, Any],
        planner_hints: dict[str, Any],
        mode: str,
        requested_internal_top_k: int,
        requested_hybrid_top_k: int,
        scientific_retrieval_enabled: bool,
        web_retrieval_enabled: bool,
        file_retrieval_enabled: bool,
        retrieval_stack_mode: str,
        external_connectors_enabled: bool,
    ) -> dict[str, Any]:
        requested_internal = max(1, min(12, int(requested_internal_top_k)))
        requested_hybrid = max(1, min(12, int(requested_hybrid_top_k)))
        normalized_stack_mode = "full" if str(retrieval_stack_mode).strip().lower() == "full" else "auto"
        complexity = cls._infer_retrieval_complexity(
            query_profile=query_profile,
            planner_hints=planner_hints,
            query_plan=query_plan,
            mode=mode,
        )
        complexity_level = str(complexity.get("level") or "medium")
        budgets = cls._orchestrator_budgets(mode=mode, complexity_level=complexity_level)
        retrieval_budget_override = (
            planner_hints.get("retrieval_budget")
            if isinstance(planner_hints.get("retrieval_budget"), dict)
            else {}
        )
        if retrieval_budget_override:
            for key in (
                "latency_budget_ms",
                "max_search_rounds",
                "max_connector_calls",
                "max_documents",
                "top_k_cap",
            ):
                if key not in retrieval_budget_override:
                    continue
                raw_value = retrieval_budget_override.get(key)
                try:
                    parsed_value = int(raw_value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if key == "latency_budget_ms":
                    budgets[key] = max(300, min(12000, parsed_value))
                elif key == "max_search_rounds":
                    budgets[key] = max(1, min(8, parsed_value))
                elif key == "max_connector_calls":
                    budgets[key] = max(0, min(8, parsed_value))
                elif key == "max_documents":
                    budgets[key] = max(1, min(24, parsed_value))
                elif key == "top_k_cap":
                    budgets[key] = max(1, min(12, parsed_value))
        top_k_cap = max(1, min(12, int(budgets.get("top_k_cap", 8))))

        internal_adjust = 0
        hybrid_adjust = 0
        if mode == "deep":
            internal_adjust += 1
            hybrid_adjust += 1
        if complexity_level == "low":
            if mode != "deep":
                internal_adjust -= 1
                hybrid_adjust -= 1
        elif complexity_level == "medium":
            internal_adjust += 1
            hybrid_adjust += 1
        else:
            internal_adjust += 2
            hybrid_adjust += 2
        if mode == "retrieval_only":
            hybrid_adjust -= 1

        adjusted_internal = max(1, min(top_k_cap, requested_internal + internal_adjust))
        adjusted_hybrid = max(1, min(top_k_cap, requested_hybrid + hybrid_adjust))
        adjusted_hybrid = max(adjusted_hybrid, adjusted_internal)

        external_available = bool(external_connectors_enabled)
        disabled_reasons: list[str] = []
        if normalized_stack_mode == "full":
            resolved_scientific = bool(external_available)
            resolved_web = bool(external_available)
            if not external_available:
                disabled_reasons.append("external_connectors_unavailable_for_full_stack")
        else:
            resolved_scientific = external_available and bool(scientific_retrieval_enabled)
            if scientific_retrieval_enabled and not external_available:
                disabled_reasons.append("external_connectors_globally_disabled")

            resolved_web = external_available and bool(web_retrieval_enabled)
            if web_retrieval_enabled and not external_available:
                disabled_reasons.append("external_connectors_globally_disabled")
            if resolved_web and not resolved_scientific:
                resolved_web = False
                disabled_reasons.append("web_requires_scientific_connectors")
            if resolved_web and mode in {"fast", "retrieval_only"} and complexity_level == "low":
                resolved_web = False
                disabled_reasons.append("fast_low_complexity_web_disabled")
            if resolved_web and mode == "retrieval_only":
                resolved_web = False
                disabled_reasons.append("retrieval_only_mode_web_disabled")

        profile_summary = {
            "is_ddi_query": bool(query_profile.get("is_ddi_query")),
            "primary_drug": str(query_profile.get("primary_drug") or ""),
            "co_drugs": [
                str(item).strip().lower()
                for item in query_profile.get("co_drugs", [])
                if str(item).strip()
            ][:6],
            "interaction_signals": [
                str(item).strip().lower()
                for item in query_profile.get("interaction_signals", [])
                if str(item).strip()
            ][:8],
            "query_terms": [
                str(item).strip().lower()
                for item in query_profile.get("query_terms", [])
                if str(item).strip()
            ][:10],
        }

        decomposition = query_plan.get("decomposition") if isinstance(query_plan, dict) else {}
        source_queries = query_plan.get("source_queries") if isinstance(query_plan, dict) else {}
        query_plan_summary = {
            "canonical_query": str(query_plan.get("canonical_query") or ""),
            "is_ddi_query": bool(query_plan.get("is_ddi_query")),
            "fast_pass_count": len(decomposition.get("fast_pass_queries", []))
            if isinstance(decomposition, dict)
            else 0,
            "deep_pass_count": len(decomposition.get("deep_pass_queries", []))
            if isinstance(decomposition, dict)
            else 0,
            "internal_query_count": len(source_queries.get("internal", []))
            if isinstance(source_queries, dict)
            else 0,
            "scientific_query_count": len(source_queries.get("scientific", []))
            if isinstance(source_queries, dict)
            else 0,
            "web_query_count": len(source_queries.get("web", []))
            if isinstance(source_queries, dict)
            else 0,
        }

        planner_reason_codes_raw = planner_hints.get("reason_codes")
        planner_reason_codes = (
            [str(item).strip() for item in planner_reason_codes_raw if str(item).strip()]
            if isinstance(planner_reason_codes_raw, list)
            else []
        )
        decision_reasons = [*complexity.get("signals", []), *disabled_reasons]
        if internal_adjust != 0 or hybrid_adjust != 0:
            decision_reasons.append("top_k_adjusted_by_mode_and_complexity")
        if normalized_stack_mode == "full":
            decision_reasons.append("retrieval_stack_mode_full_forced")
        if retrieval_budget_override:
            decision_reasons.append("planner_retrieval_budget_override")
        if not decision_reasons:
            decision_reasons.append("default_retrieval_policy")

        return {
            "mode": mode,
            "profile": profile_summary,
            "complexity": complexity,
            "budgets": budgets,
            "top_k": {
                "requested": {
                    "internal": requested_internal,
                    "hybrid": requested_hybrid,
                },
                "adjusted": {
                    "internal": adjusted_internal,
                    "hybrid": adjusted_hybrid,
                },
                "deltas": {
                    "internal": adjusted_internal - requested_internal,
                    "hybrid": adjusted_hybrid - requested_hybrid,
                },
            },
            "connector_toggles": {
                "requested": {
                    "internal": True,
                    "scientific": bool(scientific_retrieval_enabled),
                    "web": bool(web_retrieval_enabled),
                    "file": bool(file_retrieval_enabled),
                    "external_connectors_available": external_available,
                },
                "resolved": {
                    "internal": True,
                    "scientific": resolved_scientific,
                    "web": resolved_web,
                    "file": bool(file_retrieval_enabled),
                },
                "disabled_reasons": list(dict.fromkeys(disabled_reasons)),
            },
            "stack_mode": {
                "requested": normalized_stack_mode,
                "effective": (
                    "full"
                    if (
                        normalized_stack_mode == "full"
                        and resolved_scientific
                        and resolved_web
                    )
                    else "auto"
                ),
            },
            "planner_hints": {
                "query_focus": str(planner_hints.get("query_focus") or "default"),
                "reason_codes": planner_reason_codes,
                "research_mode": str(planner_hints.get("research_mode") or ""),
                "internal_top_k": requested_internal,
                "hybrid_top_k": requested_hybrid,
                "retrieval_stack_mode": normalized_stack_mode,
                "retrieval_budget": dict(retrieval_budget_override),
            },
            "query_plan_summary": query_plan_summary,
            "decision_reasons": list(dict.fromkeys(decision_reasons)),
        }

    @staticmethod
    def _extract_retriever_trace(retriever: object) -> dict[str, Any]:
        raw_trace = getattr(retriever, "last_trace", None)
        if isinstance(raw_trace, dict):
            return dict(raw_trace)
        return {}

    @staticmethod
    def _normalize_source_attempts(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or item.get("source") or "").strip()
            status = str(item.get("status") or "unknown").strip().lower()
            row = dict(item)
            row["provider"] = provider or "unknown"
            row["status"] = status or "unknown"
            normalized.append(row)
        return normalized

    @staticmethod
    def _normalize_source_errors(value: object) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, list[str]] = {}
        for key, raw_errors in value.items():
            source = str(key or "").strip() or "unknown"
            if isinstance(raw_errors, list):
                errors = [str(item).strip() for item in raw_errors if str(item).strip()]
            elif raw_errors is None:
                errors = []
            else:
                text = str(raw_errors).strip()
                errors = [text] if text else []
            if errors:
                normalized[source] = errors
        return normalized

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
        profile = analyze_query_profile(query)
        if bool(profile.get("is_ddi_query")):
            primary = str(profile.get("primary_drug") or "").strip().lower()
            co_drugs = {
                str(item).strip().lower()
                for item in profile.get("co_drugs", [])
                if str(item).strip()
            }
            interaction_terms = {
                "interaction",
                "ddi",
                "contraindication",
                "bleeding",
                "inr",
                "adverse",
                "warning",
                "risk",
            }
            best_score = 0.0
            for doc in docs:
                haystack = " ".join(
                    [
                        doc.text,
                        str((doc.metadata or {}).get("source") or ""),
                        str(doc.id or ""),
                    ]
                )
                doc_tokens = self._tokenize(haystack)
                if not doc_tokens:
                    continue
                has_primary = bool(primary) and primary in doc_tokens
                has_codrug = bool(co_drugs.intersection(doc_tokens))
                has_interaction = bool(interaction_terms.intersection(doc_tokens))
                if has_primary and has_codrug:
                    score = 0.78 + (0.12 if has_interaction else 0.0)
                elif has_primary and has_interaction:
                    score = 0.12
                elif has_primary or has_codrug:
                    score = 0.06
                else:
                    score = 0.0
                best_score = max(best_score, min(score, 1.0))
            return best_score
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
        raw_text = str(doc.text or "").strip()
        text = raw_text
        if len(text) > RagPipelineP1._PROMPT_MAX_DOC_CHARS:
            text = f"{text[:RagPipelineP1._PROMPT_MAX_DOC_CHARS].rstrip()}..."
        return f"- ({doc.id}) [{meta_bits}] {text}"

    @classmethod
    def _build_prompt(
        cls,
        query: str,
        docs: List[Document],
        *,
        report_depth: str = "standard",
        answer_language: str = "vi",
        research_mode: str = "",
    ) -> str:
        context = "\n".join(cls._format_doc_context(doc) for doc in docs[: cls._PROMPT_MAX_DOCS])
        language_label = "English" if answer_language == "en" else "Vietnamese"
        normalized_research_mode = str(research_mode or "").strip().lower()
        preferred_headings = (
            "## Quick conclusion, ## Key points, ## Practical application, ## Important caveats"
            if answer_language == "en"
            else "## Kết luận nhanh, ## Điểm chính, ## Ứng dụng thực tế, ## Lưu ý an toàn"
        )
        if str(report_depth).strip().lower() == "deep":
            if normalized_research_mode == "deep_beta":
                deep_beta_headings = (
                    "## Quick conclusion, ## Executive summary, ## Research question (PICO), "
                    "## Retrieval method & selection criteria, ## Evidence profile & source quality, "
                    "## Main findings synthesis, ## Evidence reasoning chain, "
                    "## Counter-evidence and contradictions, ## Clinical application by patient subgroup, "
                    "## Safety decision matrix, ## Follow-up plan after counseling, "
                    "## Limitations, error bands, and legal risk"
                    if answer_language == "en"
                    else "## Kết luận nhanh, ## Tóm tắt điều hành, ## Câu hỏi nghiên cứu (PICO), "
                    "## Phương pháp truy xuất & tiêu chí chọn lọc, ## Hồ sơ bằng chứng & chất lượng nguồn, "
                    "## Tổng hợp phát hiện chính, ## Chuỗi lập luận bằng chứng, "
                    "## Phản biện bằng chứng đối nghịch, ## Ứng dụng lâm sàng theo nhóm bệnh nhân, "
                    "## Ma trận quyết định an toàn, ## Kế hoạch theo dõi sau tư vấn, "
                    "## Giới hạn, sai số và rủi ro pháp lý"
                )
                return (
                    "You are CLARA Deep Beta clinical evidence assistant.\n"
                    "Use retrieved context as primary evidence and avoid unsupported claims.\n"
                    f"Output MUST be valid GitHub-Flavored Markdown (GFM) in {language_label}, no HTML.\n"
                    "Do not wrap the full response in a single code fence.\n"
                    "Write as a structured clinical dossier / evidence brief, not a reader-summary.\n"
                    f"Preferred headings (in order): {deep_beta_headings}.\n"
                    f"Keep every heading, label, bullet, and sentence in {language_label}; do not mix Vietnamese and English except for drug names, study names, or source titles.\n"
                    "Requirements:\n"
                    "- Open with a decision-oriented conclusion and explicit decision boundary.\n"
                    "- Keep claim-to-evidence linkage explicit and traceable across sections.\n"
                    "- Include contradiction handling: what evidence conflicts, how conflict is resolved, and what uncertainty remains.\n"
                    "- Include subgroup applicability, monitoring/red-flag triggers, and follow-up checkpoints.\n"
                    "- Use tables when they improve evidence comparison or risk stratification clarity.\n"
                    "- Avoid internal telemetry language (pipeline, pass log, reranker, node matrix) in answer body.\n"
                    "- Do not add dedicated references section in answer body.\n"
                    f"User query: {query}\n"
                    f"Retrieved context:\n{context}"
                )
            return (
                "You are CLARA Deep Research medical assistant.\n"
                "Use retrieved context as primary evidence and avoid unsupported claims.\n"
                f"Output MUST be valid GitHub-Flavored Markdown (GFM) in {language_label}, no HTML.\n"
                "Do not wrap the full response in a single code fence.\n"
                "Write in a Perplexity-like research answer style: direct answer first, then key reasoning, then practical application, then short caveats.\n"
                f"Preferred headings: {preferred_headings}.\n"
                f"Keep every heading, label, bullet, and sentence in {language_label}; do not mix Vietnamese and English except for drug names, study names, or source titles.\n"
                "Requirements:\n"
                "- Be detailed, but avoid sounding like an internal dossier or compliance template.\n"
                "- Start with a clear answer in 2-4 sentences before expanding.\n"
                "- Make the opening feel crisp and reader-first, like a strong Perplexity answer, not like a hospital report.\n"
                "- In section bodies, prefer short bullets or tightly edited short paragraphs over long dense blocks.\n"
                "- Use bullet points and tables only when they improve clarity.\n"
                "- Keep narrative natural, clinician-friendly, and avoid repetitive sentence templates.\n"
                "- Avoid internal telemetry language (pipeline, pass log, reranker, node matrix) in answer body.\n"
                "- For each major recommendation, explain: when to prefer it, when not to, and what to monitor next.\n"
                "- If query is comparative, include explicit decision criteria: adherence, effectiveness, safety, feasibility, and cost/access.\n"
                "- Do not add dedicated references section in answer body.\n"
                "- Explicitly state uncertainty, subgroup caveats, and decision boundary conditions.\n"
                f"User query: {query}\n"
                f"Retrieved context:\n{context}"
            )
        return (
            "You are CLARA Deep Research medical assistant.\n"
            "Use retrieved context as primary evidence and avoid unsupported claims.\n"
            "If context is weak, provide a conservative safety-first answer with clear uncertainty.\n"
            "Do not say 'no context'; still provide practical next steps safely.\n"
            f"Output MUST be valid GitHub-Flavored Markdown (GFM) in {language_label}, no HTML.\n"
            "Do not wrap the full response in a single code fence.\n"
            "Response should feel like a concise research answer, not a report template.\n"
            f"Preferred structure: {preferred_headings}.\n"
            f"Keep every heading, label, bullet, and sentence in {language_label}; do not mix Vietnamese and English except for drug names, study names, or source titles.\n"
            "Answer the user directly in the first 2-3 sentences, like a strong Perplexity summary.\n"
            "Keep each section skimmable: short paragraphs, 3-5 bullets when useful, and no meta commentary about retrieval or telemetry.\n"
            "Prefer short bullets for trade-offs, practical implications, and monitoring.\n"
            f"If comparing >=2 options, include a Markdown table with columns: {('Criteria | Option A | Option B | Notes' if answer_language == 'en' else 'Tiêu chí | Phương án A | Phương án B | Ghi chú')}.\n"
            "Write naturally like a senior clinician explaining trade-offs, avoid robotic templates.\n"
            "Do not include PICO/methodology/legal disclaimers unless explicitly requested.\n"
            "Do not add a dedicated citations section in the main answer body.\n"
            f"User query: {query}\n"
            f"Retrieved context:\n{context}"
        )

    @classmethod
    def _build_compact_retry_prompt(
        cls,
        query: str,
        docs: List[Document],
        *,
        answer_language: str = "vi",
    ) -> str:
        context = "\n".join(
            cls._format_doc_context_with_limit(doc, max_chars=cls._PROMPT_RETRY_MAX_DOC_CHARS)
            for doc in docs[: cls._PROMPT_RETRY_MAX_DOCS]
        )
        language_label = "English" if answer_language == "en" else "Vietnamese"
        compact_sections = (
            "1) ## Quick conclusion\n2) ## Key points\n3) ## Important caveats"
            if answer_language == "en"
            else "1) ## Kết luận nhanh\n2) ## Điểm chính\n3) ## Lưu ý an toàn"
        )
        return (
            "You are CLARA medical safety assistant.\n"
            f"Answer in {language_label}, concise, evidence-grounded, no HTML.\n"
            "Focus on practical safety guidance and key risks only.\n"
            "Do not diagnose or prescribe dosage.\n"
            f"Keep every heading, label, bullet, and sentence in {language_label}; do not mix Vietnamese and English except for drug names, study names, or source titles.\n"
            "Output sections in order:\n"
            f"{compact_sections}\n"
            "Open with a crisp direct answer instead of report-style setup.\n"
            "Use short bullets rather than long paragraphs whenever possible.\n"
            "Keep wording natural, concise, and avoid robotic repetition.\n"
            f"User query: {query}\n"
            f"Retrieved context:\n{context}"
        )

    @classmethod
    def _format_doc_context_with_limit(cls, doc: Document, max_chars: int) -> str:
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
        raw_text = str(doc.text or "").strip()
        text = raw_text
        if len(text) > max_chars:
            text = f"{text[:max_chars].rstrip()}..."
        return f"- ({doc.id}) [{meta_bits}] {text}"

    @staticmethod
    def _is_retryable_llm_exception(exc: Exception) -> bool:
        message = str(exc).lower()
        retryable_signals = (
            "timeout",
            "timed out",
            "too many requests",
            "rate limit",
            "http_429",
            "http_408",
            "http_500",
            "http_502",
            "http_503",
            "http_504",
            "connection",
            "temporarily unavailable",
            "deepseek_request_failed",
        )
        return any(signal in message for signal in retryable_signals)

    @staticmethod
    def _build_no_rag_prompt(query: str, *, answer_language: str = "vi") -> str:
        language_label = "English" if answer_language == "en" else "Vietnamese"
        no_rag_sections = (
            "## Quick conclusion, ## Key points, ## Practical application, ## Important caveats"
            if answer_language == "en"
            else "## Kết luận nhanh, ## Điểm chính, ## Ứng dụng thực tế, ## Lưu ý an toàn"
        )
        return (
            "User asks a health/medical question with low/empty retrieved context.\n"
            f"Provide a concise safety-first answer in {language_label}.\n"
            "Do not refuse solely due to missing context.\n"
            "Be explicit about uncertainty and avoid diagnostic/prescription overreach.\n"
            "If comparative question, provide balanced criteria and a Markdown table.\n"
            "Write naturally, answer directly first, and avoid template-heavy legal boilerplate.\n"
            "Keep the body scannable with short bullets for the main trade-offs and next steps.\n"
            "Avoid meta language about retrieval, source routing, or evidence pipeline internals.\n"
            "Output MUST be valid GitHub-Flavored Markdown (GFM), no HTML.\n"
            "Do not wrap the full response in a single code fence.\n"
            f"Response must include headings in this order: {no_rag_sections}.\n"
            f"User query: {query}"
        )

    @staticmethod
    def _safe_helpful_answer(query: str, docs: List[Document], *, answer_language: str = "vi") -> str:
        if docs:
            summary = " ".join(doc.text for doc in docs[:2]).strip()
            summary = " ".join(summary.split())
            summary = summary[:240].rstrip() + ("..." if len(summary) > 240 else "")
            if answer_language == "en":
                return (
                    "## Quick conclusion\n"
                    "The answer should stay cautious and context-based rather than overly specific.\n\n"
                    "## Key points\n"
                    f"- Question under review: `{query}`.\n"
                    f"- Main usable signal: {summary or 'Current evidence remains limited and should be treated as preliminary.'}\n"
                    "- The decision still depends on treatment goal, comorbidities, and active medications.\n\n"
                    "## Practical application\n"
                    "- Use this as a narrow decision-support summary, then verify the main trade-off with a clinician or pharmacist.\n"
                    "- For patient-specific action, add age, urgency, polypharmacy context, and red-flag symptoms.\n\n"
                    "## Important caveats\n"
                    "- Do not self-adjust dose or start treatment based on this answer alone.\n"
                    "- Escalate promptly if symptoms are severe, progressive, or atypical."
                )
            return (
                "## Kết luận nhanh\n"
                "Câu trả lời nên được giữ ở mức thận trọng và phụ thuộc bối cảnh thay vì quá cụ thể.\n\n"
                "## Điểm chính\n"
                f"- Câu hỏi đang xét: `{query}`.\n"
                f"- Tín hiệu chính có thể dùng: {summary or 'Bằng chứng hiện tại còn hạn chế và nên được xem là gợi ý ban đầu.'}\n"
                "- Quyết định vẫn phụ thuộc vào mục tiêu điều trị, bệnh nền và các thuốc đang dùng.\n\n"
                "## Ứng dụng thực tế\n"
                "- Dùng kết quả này như một bản tóm tắt hỗ trợ quyết định, rồi xác minh lại điểm đánh đổi chính với bác sĩ hoặc dược sĩ.\n"
                "- Nếu áp dụng cho một ca cụ thể, cần bổ sung tuổi, mức độ khẩn cấp, bối cảnh đa thuốc và dấu hiệu cảnh báo đỏ.\n\n"
                "## Lưu ý an toàn\n"
                "- Không tự ý chỉnh liều hoặc bắt đầu điều trị chỉ dựa trên câu trả lời này.\n"
                "- Cần đi khám sớm nếu triệu chứng nặng lên, kéo dài, hoặc khác thường."
            )
        if answer_language == "en":
            return (
                "## Quick conclusion\n"
                "Use a cautious, safety-first interpretation until stronger clinical context is available.\n\n"
                "## Key points\n"
                f"- Question under review: `{query}`.\n"
                "- The current context is not yet strong enough for a personalized recommendation.\n"
                "- The next useful step is to clarify treatment goal, comorbidities, and concurrent medications.\n\n"
                "## Practical application\n"
                "- Keep the decision narrow and document what still needs verification.\n"
                "- Bring a clinician or pharmacist in early if there is comorbidity or polypharmacy.\n\n"
                "## Important caveats\n"
                "- Do not self-prescribe or change dose based on limited context.\n"
                "- Seek urgent care now if symptoms are severe or rapidly worsening."
            )
        return (
            "## Kết luận nhanh\n"
            "Nên giữ cách hiểu theo hướng an toàn cho tới khi có thêm bối cảnh lâm sàng rõ hơn.\n\n"
            "## Điểm chính\n"
            f"- Câu hỏi đang xét: `{query}`.\n"
            "- Ngữ cảnh hiện tại chưa đủ mạnh để đưa ra khuyến nghị cá thể hóa.\n"
            "- Bước phù hợp tiếp theo là làm rõ mục tiêu điều trị, bệnh nền và các thuốc đang dùng.\n\n"
            "## Ứng dụng thực tế\n"
            "- Giữ quyết định ở phạm vi hẹp và ghi rõ điều gì còn cần kiểm chứng.\n"
            "- Nên tham vấn sớm bác sĩ hoặc dược sĩ nếu có bệnh nền hay đang dùng nhiều thuốc.\n\n"
            "## Lưu ý an toàn\n"
            "- Không tự ý kê đơn hoặc chỉnh liều chỉ với ngữ cảnh còn hạn chế.\n"
            "- Cần đi khám ngay nếu triệu chứng nặng lên nhanh hoặc có dấu hiệu cảnh báo đỏ."
        )

    @classmethod
    def _postprocess_answer(
        cls,
        answer: str,
        query: str,
        docs: List[Document],
        *,
        answer_language: str = "vi",
    ) -> str:
        cleaned = (answer or "").strip()
        if not cleaned:
            return cls._safe_helpful_answer(query, docs, answer_language=answer_language)
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
            return cls._safe_helpful_answer(query, docs, answer_language=answer_language)
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
        orchestrator_plan: dict[str, Any],
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
            "source_attempts": retrieval_trace.get("source_attempts", []),
            "source_errors": retrieval_trace.get("source_errors", {}),
            "query_plan": retrieval_trace.get("query_plan", {}),
            "orchestrator_plan": orchestrator_plan,
            "graphrag": retrieval_trace.get("graphrag", {}),
            "retrieval_orchestrator": {
                "mode": retrieval_trace.get("orchestrator_mode"),
                "complexity": retrieval_trace.get("orchestrator_complexity"),
                "top_k": (
                    orchestrator_plan.get("top_k")
                    if isinstance(orchestrator_plan.get("top_k"), dict)
                    else {}
                ),
                "connector_toggles": (
                    orchestrator_plan.get("connector_toggles")
                    if isinstance(orchestrator_plan.get("connector_toggles"), dict)
                    else {}
                ),
            },
            "graphrag_enabled": bool(retrieval_trace.get("graphrag_enabled")),
            "graphrag_expansion_count": int(retrieval_trace.get("graphrag_expansion_count") or 0),
            "graphrag_node_count": int(retrieval_trace.get("graphrag_node_count") or 0),
            "graphrag_edge_count": int(retrieval_trace.get("graphrag_edge_count") or 0),
            "stack_mode_requested": str(retrieval_trace.get("stack_mode_requested") or "auto"),
            "stack_mode_effective": str(retrieval_trace.get("stack_mode_effective") or "auto"),
            "stack_mode_reason_codes": (
                [
                    str(item).strip()
                    for item in retrieval_trace.get("stack_mode_reason_codes", [])
                    if str(item).strip()
                ]
                if isinstance(retrieval_trace.get("stack_mode_reason_codes"), list)
                else []
            ),
            "stack_coverage": (
                retrieval_trace.get("stack_coverage")
                if isinstance(retrieval_trace.get("stack_coverage"), dict)
                else {}
            ),
            "fallback_reason": retrieval_trace.get("fallback_reason"),
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

    @staticmethod
    def _merge_documents_by_id(docs: List[Document]) -> List[Document]:
        merged: list[Document] = []
        seen: set[str] = set()
        for doc in docs:
            doc_id = str(doc.id or "").strip()
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            merged.append(doc)
        return merged

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
        strict_deepseek_required: bool = False,
        rag_reranker_enabled: bool | None = None,
        rag_graphrag_enabled: bool | None = None,
        llm_runtime: dict[str, Any] | None = None,
    ) -> RagResult:
        run_started = perf_counter()
        planner_active = isinstance(planner_hints, dict) and bool(planner_hints)
        normalized_hints = self._normalize_planner_hints(planner_hints)
        answer_language = str(normalized_hints.get("answer_language") or "vi").strip().lower()
        if answer_language != "en":
            answer_language = "vi"
        requested_stack_mode = (
            "full"
            if str(normalized_hints.get("retrieval_stack_mode") or "").strip().lower() == "full"
            else "auto"
        )
        graphrag_enabled_override = normalized_hints.get("graphrag_enabled_override")
        rag_reranker_runtime = bool(
            settings.rag_reranker_enabled if rag_reranker_enabled is None else rag_reranker_enabled
        )
        graphrag_enabled_runtime = bool(settings.rag_graphrag_enabled)
        if isinstance(rag_graphrag_enabled, bool):
            graphrag_enabled_runtime = rag_graphrag_enabled
        elif isinstance(graphrag_enabled_override, bool):
            graphrag_enabled_runtime = graphrag_enabled_override
        external_connectors_override = normalized_hints.get("external_connectors_enabled_override")
        external_connectors_runtime_enabled = bool(settings.rag_external_connectors_enabled)
        if isinstance(external_connectors_override, bool):
            external_connectors_runtime_enabled = external_connectors_override
        query_plan = self._build_query_plan(
            query,
            planner_query_plan=normalized_hints.get("query_plan"),
        )
        requested_internal_top_k = int(normalized_hints["internal_top_k"])
        requested_hybrid_top_k = int(normalized_hints["hybrid_top_k"])
        query_profile = analyze_query_profile(query)
        orchestrator_mode = self._resolve_orchestrator_mode(
            generation_enabled=generation_enabled,
            planner_hints=normalized_hints,
            query_plan=query_plan,
        )
        threshold = max(0.0, min(1.0, low_context_threshold))
        used_stages: list[str] = ["retrieval_orchestrator", "internal_retrieval"]
        if planner_active:
            used_stages.insert(0, "planner")
        external_attempted = False
        flow_events: list[dict[str, Any]] = []

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
                        "internal_top_k": requested_internal_top_k,
                        "hybrid_top_k": requested_hybrid_top_k,
                        "retrieval_stack_mode": requested_stack_mode,
                        "query_plan": query_plan,
                    },
                )
            )

        flow_events.append(
            self._flow_event(
                stage="retrieval_orchestrator",
                status="started",
                docs=[],
                note="Retrieval orchestrator evaluating query profile and planner hints.",
                component="orchestrator",
                payload={
                    "mode": orchestrator_mode,
                    "query_profile": query_profile,
                    "query_plan": query_plan,
                    "planner_hints": {
                        "query_focus": normalized_hints.get("query_focus"),
                        "reason_codes": normalized_hints.get("reason_codes"),
                        "internal_top_k": requested_internal_top_k,
                        "hybrid_top_k": requested_hybrid_top_k,
                        "research_mode": normalized_hints.get("research_mode"),
                        "retrieval_stack_mode": requested_stack_mode,
                    },
                    "requested_toggles": {
                        "scientific_retrieval_enabled": bool(scientific_retrieval_enabled),
                        "web_retrieval_enabled": bool(web_retrieval_enabled),
                        "file_retrieval_enabled": bool(file_retrieval_enabled),
                        "graphrag_enabled_override": graphrag_enabled_override,
                        "rag_graphrag_enabled": rag_graphrag_enabled,
                        "rag_reranker_enabled": rag_reranker_enabled,
                    },
                },
            )
        )
        orchestrator_plan = self._build_retrieval_orchestrator_plan(
            query_profile=query_profile,
            query_plan=query_plan,
            planner_hints=normalized_hints,
            mode=orchestrator_mode,
            requested_internal_top_k=requested_internal_top_k,
            requested_hybrid_top_k=requested_hybrid_top_k,
            scientific_retrieval_enabled=scientific_retrieval_enabled,
            web_retrieval_enabled=web_retrieval_enabled,
            file_retrieval_enabled=file_retrieval_enabled,
            retrieval_stack_mode=requested_stack_mode,
            external_connectors_enabled=external_connectors_runtime_enabled,
        )
        internal_top_k = int(
            orchestrator_plan.get("top_k", {}).get("adjusted", {}).get(
                "internal", requested_internal_top_k
            )
        )
        hybrid_top_k = int(
            orchestrator_plan.get("top_k", {}).get("adjusted", {}).get(
                "hybrid", requested_hybrid_top_k
            )
        )
        resolved_toggles = orchestrator_plan.get("connector_toggles", {}).get("resolved", {})
        scientific_retrieval_enabled = bool(resolved_toggles.get("scientific"))
        web_retrieval_enabled = bool(resolved_toggles.get("web"))
        file_retrieval_enabled = bool(resolved_toggles.get("file", file_retrieval_enabled))
        flow_events.append(
            self._flow_event(
                stage="retrieval_orchestrator",
                status="completed",
                docs=[],
                note="Retrieval orchestrator selected retrieval plan and budgets.",
                component="orchestrator",
                payload=orchestrator_plan,
            )
        )

        internal_query = self._source_query(query_plan, "internal", query)
        scientific_query = self._source_query(query_plan, "scientific", query)
        web_query = self._source_query(query_plan, "web", query)
        provider_query_overrides_raw = (
            query_plan.get("provider_queries") if isinstance(query_plan, dict) else {}
        )
        provider_query_overrides = (
            provider_query_overrides_raw
            if isinstance(provider_query_overrides_raw, dict)
            else {}
        )
        scientific_provider_query_overrides = (
            provider_query_overrides.get("scientific")
            if isinstance(provider_query_overrides.get("scientific"), dict)
            else {}
        )
        web_provider_query_overrides = (
            provider_query_overrides.get("web")
            if isinstance(provider_query_overrides.get("web"), dict)
            else {}
        )
        web_query_override = str(web_provider_query_overrides.get("searxng") or web_query).strip()
        retrieval_trace: dict[str, Any] = {
            "planner_hints": normalized_hints,
            "query_profile": query_profile,
            "orchestrator_mode": orchestrator_mode,
            "orchestrator_complexity": orchestrator_plan.get("complexity", {}).get("level"),
            "orchestrator_plan": orchestrator_plan,
            "internal_top_k": internal_top_k,
            "hybrid_top_k": hybrid_top_k,
            "internal_top_k_requested": requested_internal_top_k,
            "hybrid_top_k_requested": requested_hybrid_top_k,
            "connector_toggles": resolved_toggles,
            "evidence_search_enforced": bool(settings.rag_force_search_index),
            "external_attempted": False,
            "relevance": 0.0,
            "documents": [],
            "source_attempts": [],
            "source_errors": {},
            "fallback_reason": None,
            "query_plan": query_plan,
            "provider_query_overrides": {
                "scientific": scientific_provider_query_overrides,
                "web": web_provider_query_overrides,
            },
            "graphrag": {
                "enabled": bool(graphrag_enabled_runtime),
                "node_count": 0,
                "edge_count": 0,
                "expansion_count": 0,
            },
            "graphrag_enabled": bool(graphrag_enabled_runtime),
            "graphrag_expansion_count": 0,
            "graphrag_node_count": 0,
            "graphrag_edge_count": 0,
            "runtime_flags": {
                "rag_reranker_enabled_requested": rag_reranker_enabled,
                "rag_reranker_enabled": rag_reranker_runtime,
                "rag_graphrag_enabled_requested": rag_graphrag_enabled,
                "rag_graphrag_enabled": bool(graphrag_enabled_runtime),
            },
            "stack_mode_requested": requested_stack_mode,
            "stack_mode_effective": "auto",
            "stack_mode_reason_codes": [],
            "stack_coverage": {},
        }

        flow_events.append(
            self._flow_event(
                stage="internal_retrieval",
                status="started",
                docs=[],
                note="Internal retrieval started.",
                component="retrieval",
                payload={
                    "top_k": internal_top_k,
                    "resolved_query": internal_query,
                    "original_query": query,
                },
            )
        )
        flow_events.append(
            self._flow_event(
                stage="evidence_search",
                status="started",
                docs=[],
                note="Evidence search phase started (internal corpus).",
                component="retrieval",
                payload={
                    "phase": "internal",
                    "top_k": internal_top_k,
                    "resolved_query": internal_query,
                    "original_query": query,
                },
            )
        )
        docs: List[Document] = []
        try:
            try:
                docs = self.retriever.retrieve_internal(
                    internal_query,
                    top_k=internal_top_k,
                    file_retrieval_enabled=file_retrieval_enabled,
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                    rag_reranker_enabled=rag_reranker_enabled,
                )
            except TypeError as type_exc:
                if "unexpected keyword argument" not in str(type_exc):
                    raise
                docs = self.retriever.retrieve_internal(
                    internal_query,
                    top_k=internal_top_k,
                    file_retrieval_enabled=file_retrieval_enabled,
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                )
        except Exception as exc:
            retrieval_trace["internal_error"] = exc.__class__.__name__
            retrieval_trace["source_errors"] = {"internal_retrieval": [exc.__class__.__name__]}
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
            "query": internal_query,
            "original_query": query,
            "query_terms": internal_search.get("query_terms", []),
            "top_k": internal_top_k,
            "phase": "internal",
            "total_candidates": internal_search.get("total_candidates", len(docs)),
            "duration_ms": internal_search.get("duration_ms"),
        }
        retrieval_trace["source_attempts"] = self._normalize_source_attempts(
            internal_search.get("connectors_attempted", [])
        )
        retrieval_trace["source_errors"] = self._normalize_source_errors(
            internal_search.get("source_errors", {})
        )
        retrieval_trace["index_summary"] = self._build_index_summary(
            docs,
            before_dedupe_count=internal_index.get("before_dedupe_count"),
            after_dedupe_count=internal_index.get("after_dedupe_count"),
            selected_count=internal_index.get("selected_count"),
            duration_ms=internal_index.get("duration_ms"),
            rerank=internal_index.get("rerank"),
        )
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
        should_force_external = (
            scientific_retrieval_enabled
            and external_connectors_runtime_enabled
            and self._should_force_external_retrieval(query, docs)
        )
        retrieval_trace["should_force_external"] = should_force_external

        if (
            (low_context_before_external or should_force_external)
            and scientific_retrieval_enabled
            and external_connectors_runtime_enabled
        ):
            external_attempted = True
            used_stages.append("external_scientific_retrieval")
            flow_events.append(
                self._flow_event(
                    stage="external_scientific_retrieval",
                    status="started",
                    docs=docs,
                    note=(
                        "Need external corroboration; expanding retrieval via external "
                        "medical connectors."
                    ),
                    component="retrieval",
                payload={
                    "top_k": hybrid_top_k,
                    "web_retrieval_enabled": web_retrieval_enabled,
                    "low_context_before_external": low_context_before_external,
                    "should_force_external": should_force_external,
                    "resolved_query": scientific_query,
                    "web_query_override": web_query_override,
                    "provider_query_overrides": scientific_provider_query_overrides,
                    "original_query": query,
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
                        "resolved_query": scientific_query,
                        "original_query": query,
                    },
                )
            )
            try:
                try:
                    retrieve_kwargs: dict[str, Any] = {
                        "top_k": hybrid_top_k,
                        "scientific_retrieval_enabled": True,
                        "web_retrieval_enabled": web_retrieval_enabled,
                        "file_retrieval_enabled": file_retrieval_enabled,
                        "rag_sources": rag_sources,
                        "uploaded_documents": uploaded_documents,
                        "provider_query_overrides": scientific_provider_query_overrides,
                        "web_query_override": web_query_override,
                        "rag_reranker_enabled": rag_reranker_enabled,
                    }
                    docs = self.retriever.retrieve(
                        scientific_query,
                        **retrieve_kwargs,
                    )
                except TypeError as type_exc:
                    if "unexpected keyword argument" not in str(type_exc):
                        raise
                    retrieve_kwargs = {
                        key: value
                        for key, value in retrieve_kwargs.items()
                        if key
                        not in {"provider_query_overrides", "web_query_override", "rag_reranker_enabled"}
                    }
                    docs = self.retriever.retrieve(
                        scientific_query,
                        **retrieve_kwargs,
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
                    "query": scientific_query,
                    "original_query": query,
                    "query_terms": hybrid_search.get("query_terms", []),
                    "top_k": hybrid_top_k,
                    "phase": "hybrid_external",
                    "total_candidates": hybrid_search.get("total_candidates", len(docs)),
                    "duration_ms": hybrid_search.get("duration_ms"),
                }
                retrieval_trace["source_attempts"] = self._normalize_source_attempts(
                    hybrid_search.get("connectors_attempted", [])
                )
                retrieval_trace["source_errors"] = self._normalize_source_errors(
                    hybrid_search.get("source_errors", {})
                )
                retrieval_trace["index_summary"] = self._build_index_summary(
                    docs,
                    before_dedupe_count=hybrid_index.get("before_dedupe_count"),
                    after_dedupe_count=hybrid_index.get("after_dedupe_count"),
                    selected_count=hybrid_index.get("selected_count"),
                    duration_ms=hybrid_index.get("duration_ms"),
                    rerank=hybrid_index.get("rerank"),
                )
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
                    "query": scientific_query,
                    "original_query": query,
                    "query_terms": [],
                    "top_k": hybrid_top_k,
                    "phase": "hybrid_external",
                    "total_candidates": len(docs),
                }
                retrieval_trace["source_attempts"] = []
                retrieval_trace["source_errors"] = {"external_scientific": [exc.__class__.__name__]}
                retrieval_trace["index_summary"] = self._build_index_summary(
                    docs,
                    before_dedupe_count=len(docs),
                    after_dedupe_count=len(docs),
                    selected_count=len(docs),
                    rerank={},
                )
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

        graphrag_summary: dict[str, Any] = {
            "enabled": bool(graphrag_enabled_runtime),
            "node_count": 0,
            "edge_count": 0,
            "expansion_count": 0,
            "max_neighbors": int(settings.rag_graphrag_max_neighbors),
            "expansion_doc_budget": int(settings.rag_graphrag_expansion_docs),
            "runtime_override": graphrag_enabled_override,
        }
        if graphrag_enabled_runtime:
            used_stages.append("graphrag_sidecar")
            flow_events.append(
                self._flow_event(
                    stage="graphrag_sidecar",
                    status="started",
                    docs=docs,
                    note="GraphRAG sidecar building local evidence graph.",
                    component="retrieval",
                    payload={
                        "max_neighbors": int(settings.rag_graphrag_max_neighbors),
                        "expansion_docs": int(settings.rag_graphrag_expansion_docs),
                    },
                )
            )
            try:
                graph_result = self._graphrag.expand(
                    query=query,
                    documents=docs,
                    max_neighbors=int(settings.rag_graphrag_max_neighbors),
                    expansion_docs=int(settings.rag_graphrag_expansion_docs),
                )
                graphrag_summary = dict(graph_result.summary or graphrag_summary)
                if graph_result.expansion_docs:
                    docs = self._merge_documents_by_id([*docs, *graph_result.expansion_docs])
                graphrag_summary["expansion_count"] = int(
                    graphrag_summary.get("expansion_count") or len(graph_result.expansion_docs)
                )
                flow_events.append(
                    self._flow_event(
                        stage="graphrag_sidecar",
                        status="completed",
                        docs=docs,
                        note=(
                            "GraphRAG sidecar completed with "
                            f"{int(graphrag_summary.get('expansion_count') or 0)} expansion doc(s)."
                        ),
                        component="retrieval",
                        payload=graphrag_summary,
                    )
                )
            except Exception as exc:
                graphrag_summary = {
                    **graphrag_summary,
                    "error": exc.__class__.__name__,
                }
                flow_events.append(
                    self._flow_event(
                        stage="graphrag_sidecar",
                        status="error",
                        docs=docs,
                        note=(
                            "GraphRAG sidecar failed; continue with base context. "
                            f"error={exc.__class__.__name__}"
                        ),
                        component="retrieval",
                        payload={"error": exc.__class__.__name__},
                    )
                )

        retrieval_trace["graphrag"] = graphrag_summary
        retrieval_trace["graphrag_enabled"] = bool(graphrag_summary.get("enabled"))
        retrieval_trace["graphrag_expansion_count"] = int(
            graphrag_summary.get("expansion_count") or 0
        )
        retrieval_trace["graphrag_node_count"] = int(graphrag_summary.get("node_count") or 0)
        retrieval_trace["graphrag_edge_count"] = int(graphrag_summary.get("edge_count") or 0)

        relevance_score = self._context_relevance(query, docs)
        retrieval_trace["relevance"] = round(float(relevance_score), 4)
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
                "query": scientific_query if external_attempted else internal_query,
                "original_query": query,
                "keywords": sorted(self._tokenize(query)),
                "top_k": hybrid_top_k if external_attempted else internal_top_k,
                "scientific_retrieval_enabled": bool(scientific_retrieval_enabled),
                "web_retrieval_enabled": bool(web_retrieval_enabled),
                "file_retrieval_enabled": bool(file_retrieval_enabled),
            }
        )
        if isinstance(retrieval_trace["search_plan"], dict):
            retrieval_trace["search_plan"].setdefault("original_query", query)
        source_attempts = active_trace.get("source_attempts")
        if isinstance(source_attempts, list):
            retrieval_trace["source_attempts"] = self._normalize_source_attempts(source_attempts)
        else:
            search_phase = (
                active_trace.get("search_phase")
                if isinstance(active_trace.get("search_phase"), dict)
                else {}
            )
            retrieval_trace["source_attempts"] = self._normalize_source_attempts(
                search_phase.get("connectors_attempted", [])
            )
            retrieval_trace["source_errors"] = self._normalize_source_errors(
                search_phase.get("source_errors", {})
            )
        if "source_errors" not in retrieval_trace:
            retrieval_trace["source_errors"] = {}
        retrieval_trace["source_errors"] = self._normalize_source_errors(
            retrieval_trace.get("source_errors")
            or active_trace.get("source_errors")
            or (
                active_trace.get("search_phase", {}).get("source_errors")
                if isinstance(active_trace.get("search_phase"), dict)
                else {}
            )
        )
        retrieval_trace["query_plan"] = query_plan

        active_index_summary = (
            active_trace.get("index_summary")
            if isinstance(active_trace.get("index_summary"), dict)
            else {}
        )
        retrieval_trace["index_summary"] = self._build_index_summary(
            docs,
            before_dedupe_count=active_index_summary.get(
                "before_dedupe_count",
                active_index_summary.get("before_dedupe"),
            ),
            after_dedupe_count=active_index_summary.get(
                "after_dedupe_count",
                active_index_summary.get("after_dedupe"),
            ),
            selected_count=active_index_summary.get("selected_count"),
            duration_ms=active_index_summary.get("duration_ms"),
            rerank=active_index_summary.get("rerank"),
        )
        retrieval_trace["crawl_summary"] = (
            active_trace.get("crawl_summary")
            if isinstance(active_trace.get("crawl_summary"), dict)
            else {}
        )
        provider_keys: set[str] = set()
        for attempt in retrieval_trace.get("source_attempts", []):
            if not isinstance(attempt, dict):
                continue
            provider_key = str(attempt.get("provider") or attempt.get("source") or "").strip().lower()
            if provider_key:
                provider_keys.add(provider_key)
        vector_internal_used = bool(retrieval_trace.get("internal")) or ("internal_corpus" in provider_keys)
        scientific_used = bool(provider_keys.intersection(self._SCIENTIFIC_PROVIDER_KEYS))
        web_used = bool(provider_keys.intersection(self._WEB_PROVIDER_KEYS))
        graph_used = bool(retrieval_trace.get("graphrag_enabled"))
        graph_expansion_count = int(retrieval_trace.get("graphrag_expansion_count") or 0)
        stack_coverage = {
            "vector_internal_used": vector_internal_used,
            "graph_used": graph_used,
            "graph_expansion_count": graph_expansion_count,
            "scientific_used": scientific_used,
            "web_used": web_used,
        }
        missing_stack_components = [
            name
            for name, used in (
                ("vector_internal", vector_internal_used),
                ("graph", graph_used),
                ("scientific", scientific_used),
                ("web", web_used),
            )
            if not used
        ]
        stack_mode_effective = (
            "full"
            if (
                requested_stack_mode == "full"
                and not missing_stack_components
            )
            else "auto"
        )
        stack_mode_reason_codes: list[str] = [f"stack_mode_requested_{requested_stack_mode}"]
        if stack_mode_effective == "full":
            stack_mode_reason_codes.append("stack_mode_effective_full")
        elif requested_stack_mode == "full":
            stack_mode_reason_codes.append("stack_mode_effective_auto_missing_stack")
            stack_mode_reason_codes.extend(
                f"stack_mode_missing_{component}" for component in missing_stack_components
            )
        else:
            stack_mode_reason_codes.append("stack_mode_effective_auto")
        retrieval_trace["stack_mode_effective"] = stack_mode_effective
        retrieval_trace["stack_mode_reason_codes"] = list(dict.fromkeys(stack_mode_reason_codes))
        retrieval_trace["stack_coverage"] = stack_coverage

        def _build_result(
            *,
            answer: str,
            model_used: str,
            generation_trace: dict[str, Any],
        ) -> RagResult:
            fallback_reason_raw = generation_trace.get("fallback_reason")
            fallback_reason = (
                str(fallback_reason_raw).strip() if fallback_reason_raw is not None else ""
            )
            retrieval_trace["fallback_reason"] = fallback_reason or None
            generation_trace.setdefault("fallback_reason", fallback_reason or None)
            retrieval_trace["source_attempts"] = self._normalize_source_attempts(
                retrieval_trace.get("source_attempts", [])
            )
            retrieval_trace["source_errors"] = self._normalize_source_errors(
                retrieval_trace.get("source_errors", {})
            )
            retrieval_trace["query_plan"] = query_plan
            retrieval_trace["orchestrator_plan"] = orchestrator_plan
            context_debug = self._build_context_debug(
                relevance=relevance_score,
                threshold=threshold,
                used_stages=used_stages,
                docs=docs,
                low_context_before_external=low_context_before_external,
                external_attempted=external_attempted,
                planner_hints=normalized_hints,
                retrieval_trace=retrieval_trace,
                orchestrator_plan=orchestrator_plan,
            )
            context_debug["pipeline_duration_ms"] = round(
                (perf_counter() - run_started) * 1000.0, 3
            )
            context_debug["fallback_reason"] = fallback_reason or None
            reasoning_events = [
                {
                    "event_id": str(event.get("event_id") or ""),
                    "stage": str(event.get("stage") or ""),
                    "status": str(event.get("status") or ""),
                    "component": str(event.get("component") or ""),
                    "timestamp": str(event.get("timestamp") or ""),
                }
                for event in flow_events
                if isinstance(event, dict)
            ]
            context_debug["reasoning_events"] = reasoning_events
            context_debug["reasoning_event_count"] = len(reasoning_events)
            trace = {
                "planner": {
                    "query_focus": normalized_hints.get("query_focus"),
                    "reason_codes": normalized_hints.get("reason_codes"),
                    "internal_top_k": internal_top_k,
                    "hybrid_top_k": hybrid_top_k,
                },
                "orchestrator": orchestrator_plan,
                "retrieval": retrieval_trace,
                "generation": generation_trace,
                "reasoning": {
                    "events": reasoning_events,
                    "event_count": len(reasoning_events),
                },
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

        runtime_llm_client = self._llm_client
        runtime_llm_api_key = (self._deepseek_api_key or "").strip()
        if isinstance(llm_runtime, dict):
            runtime_llm_api_key = str(llm_runtime.get("api_key") or "").strip()
            runtime_llm_base_url = str(llm_runtime.get("base_url") or "").strip()
            runtime_llm_model = str(llm_runtime.get("model") or "").strip()
            if runtime_llm_api_key and runtime_llm_base_url and runtime_llm_model:
                runtime_timeout_seconds = float(settings.deepseek_timeout_seconds)
                runtime_timeout_seconds = max(2.0, min(runtime_timeout_seconds, 18.0))
                runtime_llm_client = DeepSeekClient(
                    api_key=runtime_llm_api_key,
                    base_url=runtime_llm_base_url,
                    model=runtime_llm_model,
                    timeout_seconds=runtime_timeout_seconds,
                    retries_per_base=0,
                    retry_backoff_seconds=min(
                        max(float(settings.deepseek_retry_backoff_seconds), 0.0),
                        0.25,
                    ),
                    max_concurrency=settings.llm_global_max_concurrency,
                    min_interval_seconds=settings.llm_global_min_interval_seconds,
                    request_jitter_seconds=settings.llm_global_jitter_seconds,
                )
            elif runtime_llm_api_key:
                runtime_llm_client = None

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
                answer=self._safe_helpful_answer(query, docs, answer_language=answer_language),
                model_used="retrieval-only-v1",
                generation_trace={
                    "mode": "retrieval_only",
                    "generation_enabled": False,
                },
            )

        if strict_deepseek_required and (not runtime_llm_client or not runtime_llm_api_key):
            raise RuntimeError("deepseek_required_but_not_configured")

        llm_failure_reason = "llm_unavailable_or_failed"
        if runtime_llm_client and runtime_llm_api_key:
            try:
                if (
                    not has_relevant_context
                    and not deepseek_fallback_enabled
                    and not strict_deepseek_required
                ):
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
                        self._local_synthesis(query, docs, answer_language=answer_language),
                        query,
                        docs,
                        answer_language=answer_language,
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
                long_form_generation = self._is_long_form_orchestrator_mode(orchestrator_mode)
                requested_research_mode = str(
                    normalized_hints.get("research_mode") or query_plan.get("research_mode") or ""
                ).strip().lower()
                prompt = (
                    self._build_prompt(
                        query,
                        docs,
                        report_depth="deep" if long_form_generation else "standard",
                        answer_language=answer_language,
                        research_mode=requested_research_mode,
                    )
                    if has_relevant_context
                    else self._build_no_rag_prompt(query, answer_language=answer_language)
                )
                system_prompt_text = (
                    "You are CLARA clinical assistant. "
                    "Be concise, safe, and citation-grounded. "
                    f"Return GFM markdown in {('English' if answer_language == 'en' else 'Vietnamese')} with a direct answer first, then analysis and safety guidance. "
                    "Use markdown table for comparisons. "
                    "Do not output HTML. "
                    "Do not prescribe dosage or diagnose. "
                    "Avoid robotic or repetitive sentence templates."
                )
                if long_form_generation:
                    if requested_research_mode == "deep_beta":
                        system_prompt_text = (
                            "You are CLARA deep beta clinical dossier synthesizer. "
                            f"Produce a long-form, evidence-brief {('English' if answer_language == 'en' else 'Vietnamese')} answer. "
                            "Use GFM markdown only, no HTML. "
                            "Keep a structured clinical report flow: decision boundary first, then evidence profile, contradiction audit, subgroup applicability, safety matrix, and follow-up plan. "
                            "Keep claim-to-evidence mapping explicit and preserve unresolved uncertainty. "
                            "Do not prescribe dosage or diagnose."
                        )
                    else:
                        system_prompt_text = (
                            "You are CLARA deep research clinical assistant. "
                            f"Produce a long-form, evidence-grounded {('English' if answer_language == 'en' else 'Vietnamese')} answer. "
                            "Use GFM markdown only, no HTML. "
                            "Start with the direct answer, then expand into key points, practical application, and caveats. "
                            "Prefer precise source-linked claims and explicitly note uncertainty. "
                            "Use tables only when they materially improve clarity, and avoid dossier-like boilerplate. "
                            "Do not prescribe dosage or diagnose."
                        )
                response = runtime_llm_client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt_text,
                )
                response_model = response.model or runtime_llm_client.model
                flow_events.append(
                    self._flow_event(
                        stage="llm_generation",
                        status="completed",
                        docs=docs,
                        note="LLM answer generated successfully.",
                        component="generation",
                        payload={"model": response_model, "attempt": "primary"},
                    )
                )
                return _build_result(
                    answer=self._postprocess_answer(
                        response.content,
                        query,
                        docs,
                        answer_language=answer_language,
                    ),
                    model_used=response_model,
                    generation_trace={
                        "mode": "llm",
                        "model": response_model,
                        "has_relevant_context": has_relevant_context,
                        "attempt": "primary",
                    },
                )
            except Exception as exc:
                recovered_from_retry = False
                llm_failure_reason = self._summarize_llm_exception(exc)
                if self._is_retryable_llm_exception(exc):
                    flow_events.append(
                        self._flow_event(
                            stage="llm_generation_retry",
                            status="started",
                            docs=docs,
                            note=(
                                "Primary LLM generation failed with transient error; "
                                "retrying with compact prompt."
                            ),
                            component="generation",
                            payload={"error": exc.__class__.__name__, "strategy": "compact_prompt"},
                        )
                    )
                    try:
                        retry_response = runtime_llm_client.generate(
                            prompt=self._build_compact_retry_prompt(
                                query,
                                docs,
                                answer_language=answer_language,
                            ),
                            system_prompt=(
                                "You are CLARA clinical assistant. "
                                f"Prioritize stable, concise medical-safety output in {('English' if answer_language == 'en' else 'Vietnamese')}. "
                                "No HTML. Do not prescribe dosage or diagnose."
                            ),
                        )
                        retry_model = retry_response.model or runtime_llm_client.model
                        flow_events.append(
                            self._flow_event(
                                stage="llm_generation_retry",
                                status="completed",
                                docs=docs,
                                note="Recovered by retrying LLM generation with compact prompt.",
                                component="generation",
                                payload={"model": retry_model, "attempt": "retry_compact"},
                            )
                        )
                        recovered_from_retry = True
                        return _build_result(
                            answer=self._postprocess_answer(
                                retry_response.content,
                                query,
                                docs,
                                answer_language=answer_language,
                            ),
                            model_used=retry_model,
                            generation_trace={
                                "mode": "llm",
                                "model": retry_model,
                                "has_relevant_context": has_relevant_context,
                                "attempt": "retry_compact",
                            },
                        )
                    except Exception as retry_exc:
                        llm_failure_reason = self._summarize_llm_exception(retry_exc)
                        flow_events.append(
                            self._flow_event(
                                stage="llm_generation_retry",
                                status="error",
                                docs=docs,
                                note=(
                                    "Compact retry failed; switching to deterministic fallback if allowed."
                                ),
                                component="generation",
                                payload={"error": retry_exc.__class__.__name__},
                            )
                        )
                        exc = retry_exc

                if recovered_from_retry:
                    raise RuntimeError("llm_retry_state_inconsistent")
                if strict_deepseek_required or not deepseek_fallback_enabled:
                    raise RuntimeError("deepseek_generation_failed") from exc
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

        if strict_deepseek_required or not deepseek_fallback_enabled:
            raise RuntimeError("deepseek_unavailable_and_fallback_disabled")

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
            answer=self._postprocess_answer(
                self._local_synthesis(query, docs, answer_language=answer_language),
                query,
                docs,
                answer_language=answer_language,
            ),
            model_used="local-synth-v1",
            generation_trace={
                "mode": "local_synthesis",
                "fallback_reason": llm_failure_reason,
            },
        )


RagPipelineP0 = RagPipelineP1
