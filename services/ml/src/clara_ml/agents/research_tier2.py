from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from time import perf_counter
from typing import Any

from clara_ml.config import settings
from clara_ml.factcheck import run_fides_lite
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.rag.retrieval.text_utils import analyze_query_profile, query_terms
from clara_ml.routing import P1RoleIntentRouter

router = P1RoleIntentRouter()


@dataclass(frozen=True)
class PlanStep:
    step: str
    objective: str
    output: str


@dataclass(frozen=True)
class Citation:
    source_id: str
    source: str
    title: str
    url: str
    relevance: str


_REQUIRED_MARKDOWN_HEADINGS = (
    "## Kết luận nhanh",
    "## Phân tích chi tiết",
    "## Khuyến nghị an toàn",
    "## Nguồn tham chiếu",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_topic(payload: dict[str, Any]) -> str:
    query = str(payload.get("query") or payload.get("message") or "").strip()
    if query:
        return query
    return "general medication safety in primary care"


def _normalize_research_mode(payload: dict[str, Any]) -> str:
    raw_mode = (
        str(
            payload.get("research_mode")
            or payload.get("mode")
            or payload.get("reasoning_mode")
            or "fast"
        )
        .strip()
        .lower()
    )
    if raw_mode in {"deep", "deep_research", "long"}:
        return "deep"
    return "fast"


def _build_plan_steps(
    topic: str,
    source_mode: str | None,
    *,
    research_mode: str,
) -> list[PlanStep]:
    source_line = " from uploaded files" if source_mode == "uploaded_files" else ""
    base_steps = [
        PlanStep(
            step="scope_question",
            objective=f"Narrow the exact Tier-2 research question for '{topic}'.",
            output="Framed question and inclusion boundaries.",
        ),
        PlanStep(
            step="collect_evidence",
            objective=f"Prioritize high-signal clinical summaries and guidelines{source_line}.",
            output="Evidence shortlist with source quality notes.",
        ),
        PlanStep(
            step="synthesize_findings",
            objective="Merge findings into agreement/disagreement points.",
            output="Structured synthesis with confidence caveats.",
        ),
        PlanStep(
            step="clinical_translation",
            objective="Translate evidence into practical decision guidance.",
            output="Actionable recommendations with safety notes.",
        ),
    ]
    if research_mode != "deep":
        return base_steps

    return [
        base_steps[0],
        PlanStep(
            step="decompose_research",
            objective=(
                "Break the research topic into sub-queries, evidence hypotheses, "
                "and counter-hypotheses."
            ),
            output="Prioritized sub-query list with expected evidence direction.",
        ),
        PlanStep(
            step="breadth_scan",
            objective=(
                "Run broad retrieval across guideline, trial, review and safety sources "
                "to maximize evidence recall."
            ),
            output="Breadth-first evidence pool with source quality metadata.",
        ),
        base_steps[1],
        PlanStep(
            step="counter_evidence_scan",
            objective=(
                "Search explicitly for contradictory findings, subgroup caveats "
                "and negative outcomes."
            ),
            output="Contradiction candidates and uncertainty notes.",
        ),
        PlanStep(
            step="cross_source_verification",
            objective=(
                "Cross-check consistency across internal docs, " "scientific connectors and web."
            ),
            output="Agreement/disagreement matrix by source.",
        ),
        base_steps[2],
        base_steps[3],
    ]


def _build_planner_hints(
    *,
    topic: str,
    source_mode: str | None,
    route_role: str,
    route_intent: str,
    uploaded_documents: list[dict[str, Any]],
    rag_sources: object,
    research_mode: str,
) -> dict[str, Any]:
    normalized_topic = topic.lower()
    has_uploaded = bool(uploaded_documents)
    has_knowledge_sources = isinstance(rag_sources, list) and len(rag_sources) > 0
    evidence_query = any(
        token in normalized_topic
        for token in {
            "evidence",
            "guideline",
            "meta-analysis",
            "rct",
            "systematic",
            "interaction",
            "drug-drug",
            "ddi",
            "contraindication",
            "polypharmacy",
        }
    )

    reason_codes: list[str] = ["tier2_standard_flow"]
    if research_mode == "deep":
        reason_codes.append("tier2_deep_mode")
    extracted_keywords = query_terms(topic)
    if has_uploaded:
        reason_codes.append("uploaded_documents_present")
    if has_knowledge_sources:
        reason_codes.append("knowledge_sources_present")
    if evidence_query:
        reason_codes.append("evidence_heavy_query")

    internal_top_k = 4 if has_uploaded else 3
    if has_knowledge_sources:
        internal_top_k += 1
    hybrid_top_k = max(internal_top_k + 1, 5 if evidence_query else 4)

    deep_mode = research_mode == "deep"
    if deep_mode:
        internal_top_k = min(12, internal_top_k + 2)
        hybrid_top_k = min(12, hybrid_top_k + 3)
        target_pass_count = 8 if evidence_query else 7
    else:
        target_pass_count = 1

    return {
        "internal_top_k": max(1, min(12, internal_top_k)),
        "hybrid_top_k": max(1, min(12, hybrid_top_k)),
        "query_focus": route_intent or "evidence_review",
        "reason_codes": reason_codes,
        "keywords": extracted_keywords,
        "role": route_role,
        "source_mode": source_mode or "default",
        "low_context_threshold": 0.12 if has_uploaded else 0.15,
        "scientific_retrieval_enabled": True,
        "web_retrieval_enabled": deep_mode,
        "file_retrieval_enabled": True,
        "research_mode": research_mode,
        "deep_pass_count": target_pass_count,
        "reasoning_style": (
            "agentic_deep_research_v2" if deep_mode else "targeted_fast_research_v1"
        ),
    }


def _flow_event(
    *,
    stage: str,
    status: str,
    source_count: int,
    note: str,
    component: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "timestamp": _now_iso(),
        "status": status,
        "source_count": max(int(source_count), 0),
        "note": note,
        "detail": note,
        "component": component,
        "payload": payload or {},
    }


def _first_nonempty_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _safe_url(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("https://") or text.startswith("http://"):
        return text
    return ""


def _compact_snippet(text: Any, *, max_len: int = 120) -> str:
    snippet = " ".join(str(text or "").split()).strip()
    if not snippet:
        return ""
    if len(snippet) <= max_len:
        return snippet
    return f"{snippet[: max_len - 3]}..."


def _context_title(item: dict[str, Any], fallback: str) -> str:
    explicit = _first_nonempty_text(
        item.get("title"),
        item.get("name"),
        item.get("document_title"),
        item.get("filename"),
    )
    if explicit:
        return explicit

    text = _compact_snippet(item.get("text"), max_len=84)
    if text:
        return text

    return fallback


def _build_citations(
    topic: str,
    retrieved_context: list[dict[str, Any]],
    uploaded_documents: list[dict[str, Any]],
) -> list[Citation]:
    citations: list[Citation] = []
    seen_source_ids: set[str] = set()

    for idx, item in enumerate(retrieved_context[:10], start=1):
        if not isinstance(item, dict):
            continue

        source_name = _first_nonempty_text(item.get("source"), "retrieved")
        source_id = _first_nonempty_text(item.get("id"), f"{source_name}-{idx}")
        source_key = source_id.lower()
        if source_key in seen_source_ids:
            continue
        seen_source_ids.add(source_key)

        title = _context_title(item, fallback=f"Retrieved evidence {idx}")
        url = _safe_url(item.get("url"))
        relevance = f"Retrieved context matched query '{topic}' from source '{source_name}'."
        score = item.get("score")
        if isinstance(score, (int, float)):
            relevance = f"{relevance} Score={float(score):.4f}."

        citations.append(
            Citation(
                source_id=source_id,
                source=source_name,
                title=title,
                url=url,
                relevance=relevance,
            )
        )

    for idx, doc in enumerate(uploaded_documents[:8], start=1):
        if not isinstance(doc, dict):
            continue

        source_name = _first_nonempty_text(doc.get("source"), "uploaded")
        file_id = _first_nonempty_text(doc.get("file_id"), doc.get("id"), f"file-{idx}")
        source_id = f"{source_name}-{file_id}"
        source_key = source_id.lower()
        if source_key in seen_source_ids:
            continue
        seen_source_ids.add(source_key)

        title = _first_nonempty_text(
            doc.get("filename"),
            doc.get("name"),
            doc.get("title"),
            f"Uploaded document {idx}",
        )
        url = _safe_url(doc.get("url"))
        preview = _compact_snippet(doc.get("preview") or doc.get("text"), max_len=120)
        relevance = f"Uploaded document context from source '{source_name}'."
        if preview:
            relevance = f"{relevance} Preview: {preview}"

        citations.append(
            Citation(
                source_id=source_id,
                source=source_name,
                title=title,
                url=url,
                relevance=relevance,
            )
        )

    return citations


def _build_planner_trace(
    *,
    topic: str,
    source_mode: str | None,
    route_role: str,
    route_intent: str,
    route_confidence: float,
    route_emergency: bool,
    planner_hints: dict[str, Any],
    plan_steps: list[PlanStep],
) -> dict[str, Any]:
    return {
        "stage": "planner-v1",
        "timestamp": _now_iso(),
        "topic": topic,
        "source_mode": source_mode,
        "routing": {
            "role": route_role,
            "intent": route_intent,
            "confidence": route_confidence,
            "emergency": route_emergency,
        },
        "planner_hints": planner_hints,
        "plan_steps": [asdict(step) for step in plan_steps],
    }


def _build_retrieval_trace(
    *,
    rag_result: Any,
    planner_hints: dict[str, Any],
) -> dict[str, Any]:
    context_debug = rag_result.context_debug if isinstance(rag_result.context_debug, dict) else {}
    retrieval_debug = (
        context_debug.get("retrieval_trace")
        if isinstance(context_debug.get("retrieval_trace"), dict)
        else {}
    )
    return {
        "stage": "retrieval-v2",
        "timestamp": _now_iso(),
        "planner_hints": planner_hints,
        "relevance": context_debug.get("relevance"),
        "low_context_threshold": context_debug.get("low_context_threshold"),
        "external_attempted": context_debug.get("external_attempted"),
        "source_counts": context_debug.get("source_counts"),
        "used_stages": context_debug.get("used_stages"),
        "retrieved_ids": list(rag_result.retrieved_ids),
        "retrieved_count": len(rag_result.retrieved_ids),
        "retriever_debug": retrieval_debug,
        "search_plan": retrieval_debug.get("search_plan")
        if isinstance(retrieval_debug.get("search_plan"), dict)
        else {},
        "source_attempts": retrieval_debug.get("source_attempts")
        if isinstance(retrieval_debug.get("source_attempts"), list)
        else [],
        "index_summary": retrieval_debug.get("index_summary")
        if isinstance(retrieval_debug.get("index_summary"), dict)
        else {},
        "crawl_summary": retrieval_debug.get("crawl_summary")
        if isinstance(retrieval_debug.get("crawl_summary"), dict)
        else {},
        "top_context": rag_result.retrieved_context[:8],
    }


def _build_verifier_trace(
    *,
    factcheck_result: Any,
    policy_action: str,
    verification_state: str,
) -> dict[str, Any]:
    return {
        "stage": "verifier-v1",
        "timestamp": _now_iso(),
        "verifier": factcheck_result.stage,
        "state": verification_state,
        "policy_action": policy_action,
        "verdict": factcheck_result.verdict,
        "severity": factcheck_result.severity,
        "confidence": factcheck_result.confidence,
        "supported_claims": factcheck_result.supported_claims,
        "total_claims": factcheck_result.total_claims,
        "unsupported_claims": factcheck_result.unsupported_claims,
        "evidence_count": factcheck_result.evidence_count,
        "note": factcheck_result.note,
    }


def _normalize_retrieval_events(
    events: list[dict[str, Any]],
    *,
    default_component: str = "retrieval",
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        source_count_raw = item.get("source_count", 0)
        try:
            source_count = int(source_count_raw)
        except (TypeError, ValueError):
            source_count = 0
        payload.setdefault("source_count", max(source_count, 0))
        normalized.append(
            {
                **item,
                "component": str(item.get("component") or default_component),
                "detail": str(item.get("detail") or item.get("note") or ""),
                "payload": payload,
            }
        )
    return normalized


def _build_deep_subqueries(topic: str, keywords: list[str], pass_count: int) -> list[str]:
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    keyword_hint = " ".join(cleaned_keywords[:4]).strip()
    query_profile = analyze_query_profile(topic)
    base = [
        topic,
        f"{topic} guideline recommendations and first-line safety considerations",
        f"{topic} systematic review and meta-analysis clinical outcomes",
        f"{topic} adverse events contraindications interaction risks",
        f"{topic} subgroup analysis older adults CKD liver disease polypharmacy",
        f"{topic} contradictory findings limitations and uncertainty analysis",
        f"{topic} clinical decision criteria patient-centered recommendation framework",
    ]
    if query_profile.get("is_ddi_query"):
        primary = str(query_profile.get("primary_drug") or "index drug").strip()
        co_drugs = query_profile.get("co_drugs", [])
        co_block = (
            ", ".join(str(item) for item in co_drugs[:4])
            if isinstance(co_drugs, list) and co_drugs
            else "common analgesics"
        )
        base.extend(
            [
                f"{primary} interaction with {co_block} bleeding risk INR safety",
                f"{primary} contraindication mechanism management with {co_block}",
                f"{primary} painkiller interaction systematic review meta-analysis",
            ]
        )
    if keyword_hint:
        base.extend(
            [
                f"{topic} evidence profile for {keyword_hint}",
                f"{topic} mechanism and pharmacology context for {keyword_hint}",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for item in base:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= pass_count:
            break
    return deduped


def _deep_research_methodology(*, topic: str, subqueries: list[str]) -> dict[str, Any]:
    return {
        "id": "agentic-deep-research-v2",
        "inspired_patterns": [
            "query_decomposition",
            "breadth_first_retrieval",
            "iterative_multi_pass_search",
            "counter_evidence_scan",
            "cross_source_consensus",
            "citation_first_synthesis",
        ],
        "query": topic,
        "subquery_count": len(subqueries),
        "subqueries": subqueries,
        "stages": [
            {
                "name": "scope_and_hypothesis",
                "goal": "Chuẩn hóa câu hỏi, tách giả thuyết chính/phản biện.",
            },
            {
                "name": "evidence_collection",
                "goal": "Thu thập bằng chứng đa nguồn theo nhiều pass.",
            },
            {
                "name": "contradiction_audit",
                "goal": "Tìm bất đồng, ngoại lệ theo nhóm bệnh nền.",
            },
            {
                "name": "consensus_and_translation",
                "goal": "Tổng hợp điểm đồng thuận và khuyến nghị an toàn có điều kiện.",
            },
        ],
    }


def _resolve_deep_pass_count(payload: dict[str, Any], default_count: int) -> int:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    candidates = [
        payload.get("deep_pass_count"),
        payload.get("deep_passes"),
        payload.get("pass_count"),
        metadata.get("deep_pass_count"),
        metadata.get("deep_passes"),
        metadata.get("pass_count"),
    ]

    for raw in candidates:
        try:
            parsed = int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        return max(1, min(12, parsed))
    return max(1, min(12, int(default_count)))


def _merge_retrieved_context(
    primary: list[dict[str, Any]],
    extras: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append_rows(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or "")
            row_source = str(row.get("source") or "")
            row_title = str(row.get("title") or row.get("filename") or "")[:80]
            key = f"{row_id}|{row_source}|{row_title}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    _append_rows(primary)
    for rows in extras:
        _append_rows(rows)
    return merged


def _is_drug_interaction_query(topic: str) -> bool:
    return bool(analyze_query_profile(topic).get("is_ddi_query"))


def _filter_context_for_topic(topic: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _is_drug_interaction_query(topic):
        return rows

    profile = analyze_query_profile(topic)
    primary = str(profile.get("primary_drug") or "").strip().lower()
    co_drugs = {
        str(item).strip().lower()
        for item in profile.get("co_drugs", [])
        if str(item).strip()
    }
    interaction_terms = {"interaction", "ddi", "bleeding", "inr", "contraindication", "adverse"}
    filtered: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("text") or ""),
                str(row.get("source") or ""),
                str(row.get("id") or ""),
            ]
        ).lower()
        tokens = {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", haystack) if token}
        if primary and primary not in tokens:
            continue

        overlap = 0
        if primary and primary in tokens:
            overlap += 1
        if co_drugs.intersection(tokens):
            overlap += 1
        if interaction_terms.intersection(tokens):
            overlap += 1
        if overlap < 2:
            continue
        filtered.append(row)

    return filtered


def _has_markdown_heading(content: str, heading: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(heading)}\s*$", flags=re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(content))


def _citation_markdown_lines(citations: list[Citation]) -> list[str]:
    if not citations:
        return ["- [1] Chưa có nguồn tham chiếu cụ thể trong phản hồi hiện tại."]

    rows: list[str] = []
    for index, citation in enumerate(citations[:12], start=1):
        title = _first_nonempty_text(citation.title, citation.source, citation.source_id, f"Nguồn {index}")
        url = _safe_url(citation.url)
        if url:
            rows.append(f"- [{index}] {title} ({url})")
        else:
            rows.append(f"- [{index}] {title}")
    return rows


def _ensure_markdown_structure(answer: str, citations: list[Citation]) -> str:
    cleaned = str(answer or "").strip()
    if not cleaned:
        cleaned = "Chưa có nội dung trả lời chuyên sâu."

    if all(_has_markdown_heading(cleaned, heading) for heading in _REQUIRED_MARKDOWN_HEADINGS):
        return cleaned

    analysis_block = cleaned
    if "\n" not in analysis_block:
        analysis_block = f"- {analysis_block}"

    citations_block = "\n".join(_citation_markdown_lines(citations))
    return (
        "## Kết luận nhanh\n"
        f"{cleaned}\n\n"
        "## Phân tích chi tiết\n"
        f"{analysis_block}\n\n"
        "## Khuyến nghị an toàn\n"
        "- Không tự ý kê đơn hoặc điều chỉnh liều nếu chưa có tư vấn chuyên môn.\n"
        "- Ưu tiên xác minh lại thông tin với bác sĩ/dược sĩ khi có bệnh nền hoặc đa thuốc.\n\n"
        "## Nguồn tham chiếu\n"
        f"{citations_block}"
    )


def run_research_tier2(payload: dict[str, Any]) -> dict:
    topic = _normalize_topic(payload)
    research_mode = _normalize_research_mode(payload)
    source_mode = str(payload.get("source_mode") or "").strip().lower() or None
    role_hint = str(payload.get("role") or "").strip().lower() or None
    uploaded_documents_raw = payload.get("uploaded_documents")
    uploaded_documents: list[dict[str, Any]] = (
        uploaded_documents_raw if isinstance(uploaded_documents_raw, list) else []
    )
    rag_sources = payload.get("rag_sources")
    route = router.route(topic, role_hint=role_hint)

    plan_steps = _build_plan_steps(topic, source_mode, research_mode=research_mode)
    planner_hints = _build_planner_hints(
        topic=topic,
        source_mode=source_mode,
        route_role=route.role,
        route_intent=route.intent,
        uploaded_documents=uploaded_documents,
        rag_sources=rag_sources,
        research_mode=research_mode,
    )
    planner_trace = _build_planner_trace(
        topic=topic,
        source_mode=source_mode,
        route_role=route.role,
        route_intent=route.intent,
        route_confidence=route.confidence,
        route_emergency=route.emergency,
        planner_hints=planner_hints,
        plan_steps=plan_steps,
    )

    flow_events: list[dict[str, Any]] = [
        _flow_event(
            stage="planner",
            status="started",
            source_count=0,
            note="Planner started Tier-2 orchestration.",
            component="planner",
            payload={
                "source_mode": source_mode or "default",
                "route_role": route.role,
                "route_intent": route.intent,
                "research_mode": research_mode,
            },
        ),
        _flow_event(
            stage="planner",
            status="completed",
            source_count=0,
            note="Planner produced retrieval and verification strategy.",
            component="planner",
            payload=planner_hints,
        ),
    ]

    pipeline = RagPipelineP1()
    strict_deepseek_required = bool(
        payload.get("strict_deepseek_required", settings.deepseek_required)
    )
    deepseek_fallback_enabled = not strict_deepseek_required
    deep_pass_count = _resolve_deep_pass_count(
        payload,
        int(planner_hints.get("deep_pass_count", 1)),
    )
    planner_hints["deep_pass_count"] = deep_pass_count
    deep_subqueries: list[str] = [topic]
    deep_research_profiles: list[dict[str, Any]] = []
    deep_research_method: dict[str, Any] = {}
    deep_pass_summaries: list[dict[str, Any]] = []
    deep_pass_contexts: list[list[dict[str, Any]]] = []
    deep_pass_flow_events: list[dict[str, Any]] = []

    if research_mode == "deep":
        subqueries = _build_deep_subqueries(
            topic,
            planner_hints.get("keywords", []),
            deep_pass_count,
        )
        deep_subqueries = subqueries
        deep_research_method = _deep_research_methodology(topic=topic, subqueries=subqueries)
        deep_research_profiles = [
            {
                "profile": "hypothesis_decomposition",
                "goal": "Tách giả thuyết chính và giả thuyết phản biện.",
                "subquery": subqueries[0] if len(subqueries) > 0 else topic,
            },
            {
                "profile": "breadth_first_evidence_scan",
                "goal": "Mở rộng recall từ guideline/review/trial/safety notes.",
                "subquery": subqueries[1] if len(subqueries) > 1 else topic,
            },
            {
                "profile": "counter_evidence_search",
                "goal": "Tìm bằng chứng trái chiều và điều kiện ngoại lệ.",
                "subquery": subqueries[2] if len(subqueries) > 2 else topic,
            },
            {
                "profile": "cross_source_consistency",
                "goal": "Đối chiếu mức nhất quán giữa nhiều nguồn.",
                "subquery": subqueries[3] if len(subqueries) > 3 else topic,
            },
            {
                "profile": "clinical_synthesis",
                "goal": "Tổng hợp thành khuyến nghị có điều kiện áp dụng.",
                "subquery": subqueries[4] if len(subqueries) > 4 else topic,
            },
        ]
        flow_events.append(
            _flow_event(
                stage="deep_research",
                status="started",
                source_count=0,
                note=f"Deep research mode started with {len(subqueries)} retrieval pass(es).",
                component="planner",
                payload={
                    "pass_count": len(subqueries),
                    "subqueries": subqueries,
                    "keywords": planner_hints.get("keywords", []),
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )

        for pass_index, subquery in enumerate(subqueries, start=1):
            pass_started = perf_counter()
            deep_pass_flow_events.append(
                _flow_event(
                    stage="deep_retrieval_pass",
                    status="started",
                    source_count=0,
                    note=f"Deep retrieval pass {pass_index} started.",
                    component="retrieval",
                    payload={"pass_index": pass_index, "subquery": subquery},
                )
            )
            pass_result = pipeline.run(
                subquery,
                low_context_threshold=float(planner_hints["low_context_threshold"]),
                deepseek_fallback_enabled=deepseek_fallback_enabled,
                scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                rag_sources=rag_sources,
                uploaded_documents=uploaded_documents,
                planner_hints={
                    **planner_hints,
                    "query_focus": f"deep_pass_{pass_index}",
                    "reason_codes": [
                        *planner_hints.get("reason_codes", []),
                        f"deep_pass_{pass_index}",
                    ],
                },
                generation_enabled=False,
                strict_deepseek_required=strict_deepseek_required,
            )
            pass_trace = (
                pass_result.trace.get("retrieval")
                if isinstance(pass_result.trace.get("retrieval"), dict)
                else {}
            )
            pass_source_attempts = (
                pass_trace.get("source_attempts")
                if isinstance(pass_trace.get("source_attempts"), list)
                else []
            )
            pass_index_summary = (
                pass_trace.get("index_summary")
                if isinstance(pass_trace.get("index_summary"), dict)
                else {}
            )
            pass_crawl_summary = (
                pass_trace.get("crawl_summary")
                if isinstance(pass_trace.get("crawl_summary"), dict)
                else {}
            )
            retriever_debug = (
                pass_trace.get("hybrid")
                if isinstance(pass_trace.get("hybrid"), dict)
                else pass_trace.get("internal")
                if isinstance(pass_trace.get("internal"), dict)
                else {}
            )
            deep_pass_contexts.append(pass_result.retrieved_context)
            deep_pass_summaries.append(
                {
                    "pass_index": pass_index,
                    "subquery": subquery,
                    "retrieved_count": len(pass_result.retrieved_ids),
                    "doc_ids": list(pass_result.retrieved_ids[:8]),
                    "relevance": pass_result.context_debug.get("relevance")
                    if isinstance(pass_result.context_debug, dict)
                    else None,
                    "duration_ms": round((perf_counter() - pass_started) * 1000.0, 3),
                    "source_errors": retriever_debug.get("source_errors", {})
                    if isinstance(retriever_debug, dict)
                    else {},
                    "source_attempts": pass_source_attempts,
                    "index_summary": pass_index_summary,
                    "crawl_summary": pass_crawl_summary,
                }
            )
            source_errors = (
                deep_pass_summaries[-1].get("source_errors")
                if isinstance(deep_pass_summaries[-1].get("source_errors"), dict)
                else {}
            )
            duration_ms = round((perf_counter() - pass_started) * 1000.0, 3)
            deep_pass_flow_events.extend(
                _normalize_retrieval_events(
                    pass_result.flow_events, default_component="deep_retrieval"
                )
            )
            deep_pass_flow_events.append(
                _flow_event(
                    stage="deep_retrieval_pass",
                    status="completed",
                    source_count=len(pass_result.retrieved_ids),
                    note=f"Deep retrieval pass {pass_index} completed.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "docs_found": list(pass_result.retrieved_ids[:8]),
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "duration_ms": duration_ms,
                        "source_errors": source_errors,
                    },
                )
            )

        flow_events.extend(deep_pass_flow_events)
        flow_events.append(
            _flow_event(
                stage="deep_research",
                status="completed",
                source_count=sum(item["retrieved_count"] for item in deep_pass_summaries),
                note="Deep retrieval passes completed; moving to final synthesis.",
                component="planner",
                payload={
                    "pass_count": len(deep_pass_summaries),
                    "keywords": planner_hints.get("keywords", []),
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )

    rag_result = pipeline.run(
        topic,
        low_context_threshold=float(planner_hints["low_context_threshold"]),
        deepseek_fallback_enabled=deepseek_fallback_enabled,
        scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
        web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
        file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
        planner_hints=planner_hints,
        generation_enabled=True,
        strict_deepseek_required=strict_deepseek_required,
    )
    if strict_deepseek_required and (
        rag_result.model_used.startswith("local-synth")
        or "fallback" in rag_result.model_used.lower()
    ):
        raise RuntimeError("tier2_deepseek_required_violation")
    retrieval_trace = _build_retrieval_trace(rag_result=rag_result, planner_hints=planner_hints)
    if research_mode == "deep":
        retrieval_trace["deep_pass_summaries"] = deep_pass_summaries
        retrieval_trace["deep_pass_count"] = len(deep_pass_summaries)
    flow_events.extend(_normalize_retrieval_events(rag_result.flow_events))

    merged_context = _merge_retrieved_context(rag_result.retrieved_context, deep_pass_contexts)
    filtered_context = _filter_context_for_topic(topic, merged_context)
    effective_context = (
        filtered_context if filtered_context or _is_drug_interaction_query(topic) else merged_context
    )
    citations = _build_citations(topic, effective_context, uploaded_documents)
    fallback_used = (
        rag_result.model_used.startswith("local-synth")
        or "fallback" in rag_result.model_used.lower()
    )
    if not citations:
        citations = [
            Citation(
                source_id="fallback-safe-1",
                source="system_fallback",
                title="Safety fallback notice",
                url="",
                relevance="Fallback an toàn khi nguồn truy xuất chưa đủ ổn định.",
            )
        ]

    answer_markdown = _ensure_markdown_structure(rag_result.answer, citations)
    factcheck_result = run_fides_lite(answer=answer_markdown, retrieved_context=effective_context)
    policy_action = "allow" if factcheck_result.verdict == "pass" else "warn"
    verification_state = "verified" if policy_action == "allow" else "warning"
    verifier_trace = _build_verifier_trace(
        factcheck_result=factcheck_result,
        policy_action=policy_action,
        verification_state=verification_state,
    )
    verification_status = {
        "state": verification_state,
        "stage": factcheck_result.stage,
        "verdict": factcheck_result.verdict,
        "severity": factcheck_result.severity,
        "confidence": factcheck_result.confidence,
        "evidence_count": factcheck_result.evidence_count,
        "note": factcheck_result.note,
    }
    flow_events.append(
        _flow_event(
            stage="verification",
            status="started",
            source_count=factcheck_result.evidence_count,
            note="Verifier started evidence consistency checks.",
            component="verifier",
            payload={"verifier": factcheck_result.stage},
        )
    )
    flow_events.append(
        _flow_event(
            stage="verification",
            status=factcheck_result.verdict,
            source_count=factcheck_result.evidence_count,
            note=factcheck_result.note,
            component="verifier",
            payload={
                "confidence": factcheck_result.confidence,
                "severity": factcheck_result.severity,
                "supported_claims": factcheck_result.supported_claims,
                "total_claims": factcheck_result.total_claims,
            },
        )
    )
    flow_events.append(
        _flow_event(
            stage="verification_matrix",
            status="completed",
            source_count=factcheck_result.evidence_count,
            note="Verification matrix generated from supported/unsupported claims.",
            component="verifier",
            payload={
                "supported_claims": factcheck_result.supported_claims,
                "unsupported_claims": len(factcheck_result.unsupported_claims),
                "total_claims": factcheck_result.total_claims,
                "severity": factcheck_result.severity,
                "confidence": factcheck_result.confidence,
            },
        )
    )
    flow_events.append(
        _flow_event(
            stage="citation_selection",
            status="completed",
            source_count=len(citations),
            note=f"Selected {len(citations)} citation(s) for final answer.",
            component="postprocess",
            payload={"citation_count": len(citations)},
        )
    )

    retrieval_status = (
        "warning"
        if any(str(event.get("status", "")).lower() in {"error", "failed"} for event in flow_events)
        else "completed"
    )
    effective_fallback_used = False if strict_deepseek_required else fallback_used
    answer_status = "warning" if effective_fallback_used else "completed"
    trace_bundle = {
        "planner": planner_trace,
        "retrieval": retrieval_trace,
        "verifier": verifier_trace,
    }
    source_reasoning: list[dict[str, Any]] = []
    retriever_debug = (
        retrieval_trace.get("retriever_debug")
        if isinstance(retrieval_trace.get("retriever_debug"), dict)
        else {}
    )
    for score_key in ("score_trace", "final_score_trace"):
        rows = retriever_debug.get(score_key)
        if not isinstance(rows, list):
            continue
        for row in rows[:24]:
            if not isinstance(row, dict):
                continue
            if row.get("selected") is False:
                continue
            source_reasoning.append(
                {
                    "source": str(row.get("source") or "unknown"),
                    "score": row.get("final_score"),
                    "reasoning": (
                        f"base={row.get('base_score')} policy={row.get('policy_weight')} "
                        f"trust={row.get('trust_factor')} tag={row.get('tag_factor')}"
                    ),
                }
            )

    aggregated_errors: dict[str, Any] = {}
    if isinstance(retriever_debug.get("source_errors"), dict):
        aggregated_errors.update(retriever_debug.get("source_errors", {}))
    for summary in deep_pass_summaries:
        source_errors = summary.get("source_errors")
        if not isinstance(source_errors, dict):
            continue
        for source_name, err_value in source_errors.items():
            aggregated_errors[source_name] = err_value

    search_plan = (
        retrieval_trace.get("search_plan")
        if isinstance(retrieval_trace.get("search_plan"), dict)
        else {}
    )
    if not search_plan:
        search_plan = {
            "query": topic,
            "keywords": planner_hints.get("keywords", []),
            "top_k": planner_hints.get("hybrid_top_k"),
            "scientific_retrieval_enabled": planner_hints.get("scientific_retrieval_enabled"),
            "web_retrieval_enabled": planner_hints.get("web_retrieval_enabled"),
            "file_retrieval_enabled": planner_hints.get("file_retrieval_enabled"),
        }

    source_attempts: list[dict[str, Any]] = []
    retrieval_source_attempts = retrieval_trace.get("source_attempts")
    if isinstance(retrieval_source_attempts, list):
        source_attempts.extend(item for item in retrieval_source_attempts if isinstance(item, dict))
    for summary in deep_pass_summaries:
        attempts = summary.get("source_attempts")
        if not isinstance(attempts, list):
            continue
        for item in attempts:
            if not isinstance(item, dict):
                continue
            source_attempts.append(
                {
                    **item,
                    "pass_index": summary.get("pass_index"),
                    "subquery": summary.get("subquery"),
                }
            )

    index_summary = (
        retrieval_trace.get("index_summary")
        if isinstance(retrieval_trace.get("index_summary"), dict)
        else {}
    )
    index_summary = {
        **index_summary,
        "retrieved_count": index_summary.get("retrieved_count", retrieval_trace.get("retrieved_count")),
        "source_counts": index_summary.get("source_counts", retrieval_trace.get("source_counts", {})),
        "before_dedupe_count": index_summary.get(
            "before_dedupe_count",
            index_summary.get("before_dedupe", retrieval_trace.get("retrieved_count")),
        ),
        "after_dedupe_count": index_summary.get(
            "after_dedupe_count",
            index_summary.get("after_dedupe", retrieval_trace.get("retrieved_count")),
        ),
        "before_dedupe": index_summary.get(
            "before_dedupe",
            index_summary.get("before_dedupe_count", retrieval_trace.get("retrieved_count")),
        ),
        "after_dedupe": index_summary.get(
            "after_dedupe",
            index_summary.get("after_dedupe_count", retrieval_trace.get("retrieved_count")),
        ),
        "selected_count": index_summary.get(
            "selected_count",
            retrieval_trace.get("retrieved_count"),
        ),
    }
    crawl_summary = (
        retrieval_trace.get("crawl_summary")
        if isinstance(retrieval_trace.get("crawl_summary"), dict)
        else {}
    )
    if not isinstance(crawl_summary.get("domains"), list):
        crawl_summary["domains"] = []

    telemetry = {
        "keywords": planner_hints.get("keywords", []),
        "search_plan": {
            **search_plan,
            "subqueries": deep_subqueries,
            "research_mode": research_mode,
            "profiles": deep_research_profiles,
        },
        "source_attempts": source_attempts,
        "index_summary": index_summary,
        "crawl_summary": crawl_summary,
        "docs": effective_context,
        "scores": {
            "relevance": rag_result.context_debug.get("relevance")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "low_context_threshold": rag_result.context_debug.get("low_context_threshold")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "pipeline_duration_ms": rag_result.context_debug.get("pipeline_duration_ms")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "deep_pass_count": len(deep_pass_summaries),
        },
        "source_reasoning": source_reasoning,
        "errors": aggregated_errors,
        "deep_pass_summaries": deep_pass_summaries,
        "deep_research_profiles": deep_research_profiles,
        "deep_research_methodology": deep_research_method,
    }

    return {
        "metadata": {
            "response_style": "progressive",
            "pipeline": (
                "p2-research-tier2-deep-v1"
                if research_mode == "deep"
                else "p2-research-tier2-hybrid-v2"
            ),
            "stages": [
                {"name": "plan", "status": "completed"},
                *(
                    [{"name": "deep_research", "status": "completed"}]
                    if research_mode == "deep"
                    else []
                ),
                {"name": "hybrid_retrieval", "status": retrieval_status},
                {"name": "answer_synthesis", "status": answer_status},
                {"name": "verification", "status": verification_state},
                {"name": "citation_selection", "status": "completed"},
            ],
            "fallback_used": effective_fallback_used,
            "source_mode": source_mode,
            "research_mode": research_mode,
            "deep_pass_count": len(deep_pass_summaries),
            "context_debug": rag_result.context_debug,
            "policy_action": policy_action,
            "verification_status": verification_status,
            "planner_trace": planner_trace,
            "retrieval_trace": retrieval_trace,
            "verifier_trace": verifier_trace,
            "trace": trace_bundle,
            "flow_events": flow_events,
            "telemetry": telemetry,
            "deep_research_methodology": deep_research_method,
            "routing": {
                "role": route.role,
                "intent": route.intent,
                "confidence": route.confidence,
                "emergency": route.emergency,
            },
            "answer_format": "markdown",
            "render_hints": {
                "markdown": True,
                "tables": True,
                "mermaid": True,
                "chart_spec_fences": [
                    "chart-spec",
                    "vega-lite",
                    "echarts-option",
                    "json",
                    "yaml",
                ],
            },
        },
        "context_debug": rag_result.context_debug,
        "flow_events": flow_events,
        "planner_trace": planner_trace,
        "retrieval_trace": retrieval_trace,
        "verifier_trace": verifier_trace,
        "trace": trace_bundle,
        "telemetry": telemetry,
        "policy_action": policy_action,
        "verification_status": verification_status,
        "fallback_used": effective_fallback_used,
        "research_mode": research_mode,
        "deep_pass_count": len(deep_pass_summaries),
        "plan_steps": [asdict(step) for step in plan_steps],
        "citations": [asdict(item) for item in citations],
        "answer": answer_markdown,
        "answer_markdown": answer_markdown,
        "answer_format": "markdown",
        "render_hints": {
            "markdown": True,
            "tables": True,
            "mermaid": True,
            "chart_spec_fences": [
                "chart-spec",
                "vega-lite",
                "echarts-option",
                "json",
                "yaml",
            ],
        },
    }
