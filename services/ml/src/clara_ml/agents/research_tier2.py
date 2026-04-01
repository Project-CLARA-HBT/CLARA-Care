from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from time import perf_counter
from typing import Any
import unicodedata

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
    if raw_mode in {"deep_beta", "deep-beta", "deepbeta", "beta"}:
        return "deep_beta"
    if raw_mode in {"deep", "deep_research", "long"}:
        return "deep"
    return "fast"


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or ""))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_marks.lower()


def _dedupe_query_list(queries: list[str], *, limit: int = 12) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        normalized = " ".join(str(item or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= max(int(limit), 1):
            break
    return deduped


def _is_ddi_critical_topic(topic: str) -> bool:
    lowered = str(topic or "").lower()
    folded = _ascii_fold(topic)
    critical_markers = {
        "critical",
        "major",
        "severe",
        "life-threatening",
        "black box",
        "contraindication",
        "bleeding risk",
        "hemorrhage",
        "nghiem trong",
        "nguy hiem",
        "chong chi dinh",
        "xuat huyet",
    }
    return any(marker in lowered or marker in folded for marker in critical_markers)


def _build_source_aware_query_plan(
    *,
    topic: str,
    research_mode: str,
    keywords: list[str],
) -> dict[str, Any]:
    original_query = " ".join(str(topic or "").split()).strip()
    folded_query = _ascii_fold(original_query)
    profile = analyze_query_profile(original_query)
    keyword_terms = [
        item.strip().lower()
        for item in keywords
        if isinstance(item, str) and item.strip()
    ]
    if not keyword_terms:
        keyword_terms = query_terms(original_query)

    has_vietnamese_marks = bool(
        re.search(r"[àáạảãâầấậẩẫăằắặẳẵđèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]", original_query.lower())
    )
    has_english_markers = bool(
        re.search(
            r"\b(interaction|guideline|evidence|review|trial|safety|contraindication|bleeding)\b",
            original_query.lower(),
        )
    )
    language_hint = "vi" if has_vietnamese_marks else "en"
    if has_vietnamese_marks and has_english_markers:
        language_hint = "mixed"

    primary_drug = str(profile.get("primary_drug") or "").strip().lower()
    co_drugs_raw = profile.get("co_drugs")
    co_drugs = (
        [str(item).strip().lower() for item in co_drugs_raw if str(item).strip()]
        if isinstance(co_drugs_raw, list)
        else []
    )
    co_drug_phrase = ", ".join(co_drugs[:4]) if co_drugs else "common analgesics"
    canonical_query = original_query
    if profile.get("is_ddi_query"):
        canonical_query = (
            f"{primary_drug or 'index drug'} interaction with {co_drug_phrase} "
            "bleeding risk contraindication guidance"
        ).strip()
    elif language_hint == "vi":
        canonical_query = " ".join(keyword_terms[:8]).strip() or folded_query or original_query

    internal_queries = _dedupe_query_list(
        [
            original_query,
            canonical_query,
            folded_query if folded_query != original_query.lower() else "",
            " ".join(keyword_terms[:8]),
        ],
        limit=8,
    )
    scientific_queries = _dedupe_query_list(
        [
            canonical_query,
            " ".join(keyword_terms[:8]),
            (
                f"{primary_drug or 'index drug'} drug-drug interaction with {co_drug_phrase} "
                "clinical evidence"
                if profile.get("is_ddi_query")
                else ""
            ),
            original_query,
        ],
        limit=8,
    )
    web_queries = _dedupe_query_list(
        [
            original_query,
            canonical_query,
            f"{canonical_query} guideline",
            f"{canonical_query} safety warning",
        ],
        limit=8,
    )

    deep_queries = _dedupe_query_list(
        [
            canonical_query,
            f"{canonical_query} guideline recommendations and safety thresholds",
            f"{canonical_query} systematic review meta-analysis outcomes",
            f"{canonical_query} adverse events contraindications interaction risks",
            f"{canonical_query} contradictory findings and subgroup caveats",
            f"{canonical_query} clinical translation and monitoring checklist",
        ],
        limit=12,
    )
    deep_beta_queries = _dedupe_query_list(
        [
            *deep_queries,
            f"{canonical_query} dose-adjusted subgroup evidence chronic kidney disease liver impairment",
            f"{canonical_query} pharmacovigilance post-marketing safety signal trend",
            f"{canonical_query} disagreement analysis by trial design and endpoint definitions",
            f"{canonical_query} guideline divergence and implementation constraints primary care",
            f"{canonical_query} monitoring algorithm threshold escalation and stop criteria",
            f"{canonical_query} unresolved evidence gaps and pragmatic fallback protocol",
        ],
        limit=14,
    )
    fast_queries = _dedupe_query_list([canonical_query, original_query, " ".join(keyword_terms[:6])], limit=4)

    return {
        "original_query": original_query,
        "canonical_query": canonical_query,
        "language_hint": language_hint,
        "is_ddi_query": bool(profile.get("is_ddi_query")),
        "is_ddi_critical_query": bool(profile.get("is_ddi_query")) and _is_ddi_critical_topic(original_query),
        "source_queries": {
            "internal": internal_queries,
            "scientific": scientific_queries,
            "web": web_queries,
        },
        "decomposition": {
            "fast_pass_queries": fast_queries,
            "deep_pass_queries": deep_queries,
            "deep_beta_pass_queries": deep_beta_queries,
        },
        "research_mode": research_mode,
        "query_terms": keyword_terms[:10],
    }


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
    if research_mode == "deep_beta":
        return [
            base_steps[0],
            PlanStep(
                step="decompose_research",
                objective=(
                    "Break the research topic into sub-queries, hypothesis/counter-hypothesis "
                    "pairs and evidence conflict checkpoints."
                ),
                output="Prioritized sub-query graph and expected directional signals.",
            ),
            PlanStep(
                step="retrieval_budgeting",
                objective=(
                    "Allocate explicit retrieval budget by source type, pass index and "
                    "quality threshold."
                ),
                output="Pass-level retrieval budgets and source coverage targets.",
            ),
            PlanStep(
                step="breadth_scan",
                objective=(
                    "Run a broad evidence sweep across guidelines, trials, reviews, "
                    "drug labels and safety bulletins."
                ),
                output="Breadth-first evidence pool with source quality metadata.",
            ),
            base_steps[1],
            PlanStep(
                step="iterative_gap_fill",
                objective=(
                    "Run iterative passes to fill unresolved evidence gaps and "
                    "edge-case caveats."
                ),
                output="Gap-closure notes and augmented pass summaries.",
            ),
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
                    "Cross-check consistency across internal docs, scientific connectors, "
                    "web and source trust hierarchy."
                ),
                output="Agreement/disagreement matrix by source and pass.",
            ),
            PlanStep(
                step="reasoning_chain_audit",
                objective=(
                    "Audit the reasoning chain for unsupported links before synthesis."
                ),
                output="Reasoning-chain status with mitigation notes.",
            ),
            base_steps[2],
            base_steps[3],
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
    query_profile = analyze_query_profile(topic)
    is_ddi_query = bool(query_profile.get("is_ddi_query"))
    is_ddi_critical_query = is_ddi_query and _is_ddi_critical_topic(topic)
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
            "tuong tac",
            "tương tác",
            "da thuoc",
            "đa thuốc",
            "thuoc",
            "thuốc",
        }
    )
    evidence_query = bool(evidence_query or is_ddi_query)

    reason_codes: list[str] = ["tier2_standard_flow"]
    if research_mode == "deep":
        reason_codes.append("tier2_deep_mode")
    if research_mode == "deep_beta":
        reason_codes.append("tier2_deep_beta_mode")
    extracted_keywords = query_terms(topic)
    if has_uploaded:
        reason_codes.append("uploaded_documents_present")
    if has_knowledge_sources:
        reason_codes.append("knowledge_sources_present")
    if evidence_query:
        reason_codes.append("evidence_heavy_query")
    if is_ddi_query:
        reason_codes.append("ddi_query_detected")
    if is_ddi_critical_query:
        reason_codes.append("ddi_critical_query")

    internal_top_k = 4 if has_uploaded else 3
    if has_knowledge_sources:
        internal_top_k += 1
    if is_ddi_query:
        internal_top_k += 1
    if is_ddi_critical_query:
        internal_top_k += 1
    hybrid_top_k = max(internal_top_k + 1, 5 if evidence_query else 4)
    if is_ddi_critical_query:
        hybrid_top_k += 1

    deep_mode = research_mode == "deep"
    deep_beta_mode = research_mode == "deep_beta"
    deep_like_mode = deep_mode or deep_beta_mode
    if deep_mode:
        internal_top_k = min(12, internal_top_k + 2)
        hybrid_top_k = min(12, hybrid_top_k + 3)
        target_pass_count = 9 if is_ddi_query else (8 if evidence_query else 7)
    elif deep_beta_mode:
        internal_top_k = min(12, internal_top_k + 4)
        hybrid_top_k = min(12, hybrid_top_k + 5)
        target_pass_count = 12 if is_ddi_query else (11 if evidence_query else 10)
    else:
        # Fast mode ưu tiên SLA: giới hạn fan-out retrieval để tránh timeout upstream.
        internal_top_k = min(4, max(2, internal_top_k))
        hybrid_top_k = min(5, max(3, hybrid_top_k))
        target_pass_count = 1
    # Web crawl chỉ bật mặc định ở deep/deep_beta để giảm latency dao động ở fast mode.
    web_enabled = bool(deep_like_mode)
    if not deep_like_mode and (evidence_query or is_ddi_query):
        reason_codes.append("fast_mode_latency_guard")

    scientific_enabled = bool(deep_like_mode)
    if not scientific_enabled and evidence_query:
        reason_codes.append("fast_scientific_disabled_for_sla")

    retrieval_budget = {
        "mode": research_mode,
        "target_pass_count": max(1, min(12, target_pass_count)),
        "internal_top_k": max(1, min(12, internal_top_k)),
        "hybrid_top_k": max(1, min(12, hybrid_top_k)),
        "estimated_max_documents": max(1, min(12, hybrid_top_k))
        * max(1, min(12, target_pass_count)),
        "scientific_retrieval_enabled": scientific_enabled,
        "web_retrieval_enabled": web_enabled,
        "file_retrieval_enabled": True,
    }

    return {
        "internal_top_k": max(1, min(12, internal_top_k)),
        "hybrid_top_k": max(1, min(12, hybrid_top_k)),
        "query_focus": route_intent or "evidence_review",
        "reason_codes": reason_codes,
        "keywords": extracted_keywords,
        "role": route_role,
        "source_mode": source_mode or "default",
        "low_context_threshold": 0.12 if has_uploaded else 0.15,
        "scientific_retrieval_enabled": scientific_enabled,
        "web_retrieval_enabled": web_enabled,
        "file_retrieval_enabled": True,
        "research_mode": research_mode,
        "deep_pass_count": target_pass_count,
        "reasoning_style": (
            (
                "agentic_deep_research_beta_v1"
                if deep_beta_mode
                else "agentic_deep_research_v2"
                if deep_mode
                else "targeted_fast_research_v1"
            )
        ),
        "ddi_critical_query": is_ddi_critical_query,
        "retrieval_budget": retrieval_budget,
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


def _compact_context_rows(
    rows: list[dict[str, Any]],
    *,
    max_items: int = 10,
    max_text_len: int = 260,
) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for row in rows[:max_items]:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                "id": row.get("id"),
                "source": row.get("source"),
                "title": _context_title(row, fallback="Retrieved evidence"),
                "url": row.get("url"),
                "score": row.get("score"),
                "snippet": _compact_snippet(row.get("text"), max_len=max_text_len),
            }
        )
    return compacted


def _shrink_payload(value: Any, *, max_list: int = 12, max_str: int = 300) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {"text", "content", "raw", "html"}:
                output[key] = _compact_snippet(item, max_len=max_str)
            else:
                output[key] = _shrink_payload(item, max_list=max_list, max_str=max_str)
        return output
    if isinstance(value, list):
        return [
            _shrink_payload(item, max_list=max_list, max_str=max_str)
            for item in value[:max_list]
        ]
    if isinstance(value, str):
        return _compact_snippet(value, max_len=max_str)
    return value


def _compact_context_debug(value: Any) -> dict[str, Any]:
    context = value if isinstance(value, dict) else {}
    compact = _shrink_payload(context, max_list=12, max_str=300)
    if not isinstance(compact, dict):
        return {}
    retrieval_trace = compact.get("retrieval_trace")
    if isinstance(retrieval_trace, dict):
        top_context = retrieval_trace.get("top_context")
        if isinstance(top_context, list):
            retrieval_trace["top_context"] = _compact_context_rows(
                [item for item in top_context if isinstance(item, dict)],
                max_items=8,
                max_text_len=200,
            )
    return compact


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _compact_verification_matrix_rows(
    rows: Any,
    *,
    max_items: int = 20,
    max_snippet_len: int = 180,
) -> list[dict[str, Any]]:
    compact_rows: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return compact_rows

    for row in rows[:max_items]:
        if not isinstance(row, dict):
            continue
        support_status = str(row.get("support_status") or "unsupported").strip().lower()
        compact_rows.append(
            {
                "claim": _first_nonempty_text(row.get("claim")),
                "support_status": support_status or "unsupported",
                "overlap_score": round(
                    max(0.0, min(1.0, _safe_float(row.get("overlap_score")))),
                    4,
                ),
                "confidence": round(
                    max(0.0, min(1.0, _safe_float(row.get("confidence")))),
                    4,
                ),
                "evidence_ref": _first_nonempty_text(row.get("evidence_ref")) or None,
                "evidence_snippet": _compact_snippet(
                    row.get("evidence_snippet") or row.get("evidence"),
                    max_len=max_snippet_len,
                ),
            }
        )
    return compact_rows


def _summarize_verification_matrix(
    rows: list[dict[str, Any]],
    *,
    total_claims: int,
    supported_claims: int,
) -> dict[str, Any]:
    supported_count = 0
    unsupported_count = 0
    contradicted_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("support_status") or "").strip().lower()
        if status == "supported":
            supported_count += 1
        elif status == "contradicted":
            contradicted_count += 1
        else:
            unsupported_count += 1

    inferred_total = max(_safe_int(total_claims, 0), len(rows))
    inferred_supported = _safe_int(supported_claims, 0)
    if inferred_supported <= 0 and supported_count > 0:
        inferred_supported = supported_count
    inferred_supported = max(0, min(inferred_supported, inferred_total))
    support_ratio = inferred_supported / max(inferred_total, 1) if inferred_total > 0 else 0.0
    return {
        "version": "claim-v1",
        "total_claims": inferred_total,
        "supported_claims": inferred_supported,
        "unsupported_claims": unsupported_count,
        "contradicted_claims": contradicted_count,
        "support_ratio": round(float(support_ratio), 4),
    }


def _build_contradiction_summary(
    verification_matrix_rows: list[dict[str, Any]],
    raw_summary: Any,
    *,
    fallback_note: str,
) -> dict[str, Any]:
    contradicted_rows = [
        row
        for row in verification_matrix_rows
        if str(row.get("support_status") or "").strip().lower() == "contradicted"
    ]
    default_note = (
        "Phát hiện claim mâu thuẫn với evidence retrieval."
        if contradicted_rows
        else "Không phát hiện claim mâu thuẫn."
    )
    defaults = {
        "version": "claim-v1",
        "has_contradiction": bool(contradicted_rows),
        "contradiction_count": len(contradicted_rows),
        "claims": [str(item.get("claim") or "") for item in contradicted_rows[:5]],
        "details": [
            {
                "claim": item.get("claim", ""),
                "evidence_ref": item.get("evidence_ref"),
                "evidence_snippet": item.get("evidence_snippet", ""),
                "overlap_score": item.get("overlap_score", 0.0),
                "confidence": item.get("confidence", 0.0),
            }
            for item in contradicted_rows[:5]
        ],
        "note": fallback_note or default_note,
    }
    if not isinstance(raw_summary, dict):
        return defaults

    claims = raw_summary.get("claims")
    details = raw_summary.get("details")
    contradiction_count = max(
        0,
        _safe_int(raw_summary.get("contradiction_count"), defaults["contradiction_count"]),
    )
    return {
        "version": str(raw_summary.get("version") or defaults["version"]),
        "has_contradiction": bool(
            raw_summary.get("has_contradiction", defaults["has_contradiction"])
        ),
        "contradiction_count": contradiction_count,
        "claims": (
            [str(item) for item in claims[:5]]
            if isinstance(claims, list)
            else defaults["claims"]
        ),
        "details": details if isinstance(details, list) else defaults["details"],
        "note": str(raw_summary.get("note") or defaults["note"]),
    }


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
    source_errors = retrieval_debug.get("source_errors")
    if not isinstance(source_errors, dict):
        source_errors = {}
    query_plan = retrieval_debug.get("query_plan")
    if not isinstance(query_plan, dict):
        query_plan = {}
    generation_trace = (
        rag_result.trace.get("generation")
        if isinstance(getattr(rag_result, "trace", None), dict)
        and isinstance(rag_result.trace.get("generation"), dict)
        else {}
    )
    fallback_reason_raw = generation_trace.get("fallback_reason")
    fallback_reason = str(fallback_reason_raw).strip() if fallback_reason_raw is not None else ""
    compact_top_context = _compact_context_rows(
        rag_result.retrieved_context if isinstance(rag_result.retrieved_context, list) else [],
        max_items=8,
        max_text_len=220,
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
        "retriever_debug": _shrink_payload(retrieval_debug, max_list=12, max_str=300),
        "search_plan": retrieval_debug.get("search_plan")
        if isinstance(retrieval_debug.get("search_plan"), dict)
        else {},
        "source_attempts": retrieval_debug.get("source_attempts")
        if isinstance(retrieval_debug.get("source_attempts"), list)
        else [],
        "source_errors": source_errors,
        "fallback_reason": fallback_reason or None,
        "query_plan": query_plan,
        "index_summary": retrieval_debug.get("index_summary")
        if isinstance(retrieval_debug.get("index_summary"), dict)
        else {},
        "crawl_summary": retrieval_debug.get("crawl_summary")
        if isinstance(retrieval_debug.get("crawl_summary"), dict)
        else {},
        "top_context": compact_top_context,
    }


def _build_verifier_trace(
    *,
    factcheck_result: Any,
    policy_action: str,
    verification_state: str,
    verification_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = {
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
    if isinstance(verification_matrix, dict):
        trace["verification_matrix"] = verification_matrix
    return trace


def _normalize_retrieval_events(
    events: list[dict[str, Any]],
    *,
    default_component: str = "retrieval",
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    first_timestamp: datetime | None = None

    def _parse_timestamp(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    for item in events:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        source_count_raw = item.get("source_count", 0)
        try:
            source_count = int(source_count_raw)
        except (TypeError, ValueError):
            source_count = 0
        parsed_timestamp = _parse_timestamp(item.get("timestamp"))
        if parsed_timestamp and first_timestamp is None:
            first_timestamp = parsed_timestamp
        elapsed_ms = (
            round((parsed_timestamp - first_timestamp).total_seconds() * 1000.0, 3)
            if parsed_timestamp and first_timestamp
            else None
        )
        sequence = len(normalized) + 1
        payload.setdefault("source_count", max(source_count, 0))
        payload.setdefault("event_sequence", sequence)
        if elapsed_ms is not None:
            payload.setdefault("elapsed_ms", elapsed_ms)
        normalized.append(
            {
                **item,
                "component": str(item.get("component") or default_component),
                "detail": str(item.get("detail") or item.get("note") or ""),
                "payload": payload,
                "event_sequence": sequence,
                **({"elapsed_ms": elapsed_ms} if elapsed_ms is not None else {}),
            }
        )
    return normalized


def _build_deep_subqueries(
    topic: str,
    keywords: list[str],
    pass_count: int,
    *,
    seed_queries: list[str] | None = None,
) -> list[str]:
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    keyword_hint = " ".join(cleaned_keywords[:4]).strip()
    query_profile = analyze_query_profile(topic)
    base = [
        *(seed_queries or []),
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


def _deep_beta_research_methodology(
    *,
    topic: str,
    subqueries: list[str],
    retrieval_budget: dict[str, Any],
) -> dict[str, Any]:
    base = _deep_research_methodology(topic=topic, subqueries=subqueries)
    return {
        **base,
        "id": "agentic-deep-research-beta-v1",
        "query": topic,
        "retrieval_budget": retrieval_budget,
        "inspired_patterns": [
            *base.get("inspired_patterns", []),
            "retrieval_budgeting",
            "iterative_gap_fill",
            "reasoning_chain_audit",
        ],
        "stages": [
            {
                "name": "beta_scope_lock",
                "goal": "Khoá phạm vi lâm sàng, giả định và tiêu chí loại trừ ngay từ đầu.",
            },
            {
                "name": "beta_hypothesis_map",
                "goal": "Tạo bản đồ giả thuyết/chống giả thuyết kèm bằng chứng kỳ vọng.",
            },
            {
                "name": "beta_budgeted_retrieval",
                "goal": "Phân bổ ngân sách retrieval theo pass/source và chạy multi-pass.",
            },
            {
                "name": "beta_reasoning_chain",
                "goal": "Liên kết bằng chứng-pass thành chuỗi lập luận có kiểm lỗi.",
            },
            {
                "name": "beta_chain_verification",
                "goal": "Đánh dấu mắt xích yếu, mâu thuẫn và mức tự tin cuối.",
            },
        ],
    }


def _build_deep_beta_reasoning_steps(*, topic: str, subqueries: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "stage": "deep_beta_scope",
            "status": "pending",
            "objective": "Lock scope, safety boundaries and exclusions for the beta chain.",
            "subquery": subqueries[0] if subqueries else topic,
        },
        {
            "stage": "deep_beta_hypothesis_map",
            "status": "pending",
            "objective": "Map main/counter hypotheses with expected supporting evidence.",
            "subquery": subqueries[1] if len(subqueries) > 1 else topic,
        },
        {
            "stage": "deep_beta_retrieval_budget",
            "status": "pending",
            "objective": "Allocate retrieval budgets and quality thresholds across passes.",
            "subquery": subqueries[2] if len(subqueries) > 2 else topic,
        },
        {
            "stage": "deep_beta_multi_pass_retrieval",
            "status": "pending",
            "objective": "Run iterative retrieval passes and close evidence gaps.",
            "subquery": subqueries[3] if len(subqueries) > 3 else topic,
        },
        {
            "stage": "deep_beta_chain_synthesis",
            "status": "pending",
            "objective": "Build synthesis chain from pass-level evidence summaries.",
            "subquery": subqueries[4] if len(subqueries) > 4 else topic,
        },
        {
            "stage": "deep_beta_chain_verification",
            "status": "pending",
            "objective": "Validate chain consistency, contradictions and uncertainty.",
            "subquery": subqueries[5] if len(subqueries) > 5 else topic,
        },
    ]

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
    primary_aliases = {
        str(item).strip().lower()
        for item in profile.get("primary_aliases", [])
        if str(item).strip()
    }
    if primary:
        primary_aliases.add(primary)
    co_drugs = {
        str(item).strip().lower()
        for item in profile.get("co_drugs", [])
        if str(item).strip()
    }
    co_drug_aliases = set(co_drugs)
    co_drug_aliases_raw = profile.get("co_drug_aliases")
    if isinstance(co_drug_aliases_raw, dict):
        for aliases in co_drug_aliases_raw.values():
            if not isinstance(aliases, list):
                continue
            for item in aliases:
                alias = str(item).strip().lower()
                if alias:
                    co_drug_aliases.add(alias)
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
        if primary_aliases and not primary_aliases.intersection(tokens):
            continue

        source_name = str(row.get("source") or "").strip().lower()
        has_primary = bool(primary_aliases.intersection(tokens))
        has_codrug = bool(co_drug_aliases.intersection(tokens))
        has_interaction = bool(interaction_terms.intersection(tokens))
        trusted_label_source = source_name in {"openfda", "dailymed", "rxnorm", "rxnav"}

        # Keep strong DDI rows (primary + co-drug or interaction).
        if has_primary and (has_codrug or has_interaction):
            filtered.append(row)
            continue

        # Keep authoritative drug-label rows mentioning primary drug,
        # so we do not zero out evidence when query is specific but corpus is sparse.
        if has_primary and trusted_label_source:
            filtered.append(row)

    return filtered


def _infer_fallback_used(rag_result: Any) -> bool:
    trace = rag_result.trace if isinstance(getattr(rag_result, "trace", None), dict) else {}
    generation = trace.get("generation") if isinstance(trace.get("generation"), dict) else {}
    generation_mode = str(generation.get("mode") or "").strip().lower()
    if generation_mode in {"llm", "retrieval_only"}:
        return False
    if generation_mode == "local_synthesis":
        return True

    model_used = str(getattr(rag_result, "model_used", "") or "").strip().lower()
    if model_used.startswith("local-synth"):
        return True
    return "fallback" in model_used


def _trace_rows_for_citation(retrieval_trace: dict[str, Any]) -> list[dict[str, Any]]:
    retriever_debug = (
        retrieval_trace.get("retriever_debug")
        if isinstance(retrieval_trace.get("retriever_debug"), dict)
        else {}
    )
    top_documents = retriever_debug.get("top_documents")
    if not isinstance(top_documents, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in top_documents[:10]:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "retrieved")
        doc_id = str(item.get("id") or "")
        url = _safe_url(item.get("url"))
        score = item.get("score")
        rows.append(
            {
                "id": doc_id or f"{source}-{len(rows) + 1}",
                "source": source,
                "title": doc_id or f"{source} evidence",
                "text": "",
                "url": url,
                "score": score,
            }
        )
    return rows


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
    planner_hints["query_plan"] = _build_source_aware_query_plan(
        topic=topic,
        research_mode=research_mode,
        keywords=planner_hints.get("keywords", []),
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
    run_started_at = perf_counter()

    def _event(
        *,
        stage: str,
        status: str,
        source_count: int,
        note: str,
        component: str,
        payload: dict[str, Any] | None = None,
        started_at: float | None = None,
    ) -> dict[str, Any]:
        now = perf_counter()
        event_payload = dict(payload or {})
        event_payload.setdefault("elapsed_ms", round((now - run_started_at) * 1000.0, 3))
        if started_at is not None:
            event_payload.setdefault("duration_ms", round((now - started_at) * 1000.0, 3))
        return _flow_event(
            stage=stage,
            status=status,
            source_count=source_count,
            note=note,
            component=component,
            payload=event_payload,
        )

    flow_events: list[dict[str, Any]] = [
        _event(
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
        _event(
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
    deep_beta_reasoning_steps: list[dict[str, Any]] = []
    deep_beta_retrieval_budgets: dict[str, Any] = {}
    deep_beta_chain_status: dict[str, Any] = {}

    def _update_beta_reasoning_step(
        *,
        stage: str,
        status: str,
        note: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not deep_beta_reasoning_steps:
            return
        for item in deep_beta_reasoning_steps:
            if str(item.get("stage")) != stage:
                continue
            item["status"] = status
            item["note"] = note
            if isinstance(payload, dict) and payload:
                item["payload"] = payload
            break

    if research_mode == "deep":
        query_plan = (
            planner_hints.get("query_plan")
            if isinstance(planner_hints.get("query_plan"), dict)
            else {}
        )
        decomposition = (
            query_plan.get("decomposition") if isinstance(query_plan.get("decomposition"), dict) else {}
        )
        deep_seed_queries = (
            decomposition.get("deep_pass_queries")
            if isinstance(decomposition.get("deep_pass_queries"), list)
            else []
        )
        subqueries = _build_deep_subqueries(
            str(query_plan.get("canonical_query") or topic),
            planner_hints.get("keywords", []),
            deep_pass_count,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
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
            _event(
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
                _event(
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
                _event(
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
                    started_at=pass_started,
                )
            )

        flow_events.extend(deep_pass_flow_events)
        flow_events.append(
            _event(
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
    elif research_mode == "deep_beta":
        query_plan = (
            planner_hints.get("query_plan")
            if isinstance(planner_hints.get("query_plan"), dict)
            else {}
        )
        decomposition = (
            query_plan.get("decomposition") if isinstance(query_plan.get("decomposition"), dict) else {}
        )
        deep_seed_queries = (
            decomposition.get("deep_beta_pass_queries")
            if isinstance(decomposition.get("deep_beta_pass_queries"), list)
            else decomposition.get("deep_pass_queries")
            if isinstance(decomposition.get("deep_pass_queries"), list)
            else []
        )
        subqueries = _build_deep_subqueries(
            str(query_plan.get("canonical_query") or topic),
            planner_hints.get("keywords", []),
            deep_pass_count,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
        )
        deep_subqueries = subqueries
        deep_beta_retrieval_budgets = {
            **(
                planner_hints.get("retrieval_budget")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else {}
            ),
            "mode": "deep_beta",
            "target_pass_count": len(subqueries),
            "allocated_pass_count": len(subqueries),
            "per_pass_doc_target": max(4, min(12, _safe_int(planner_hints.get("hybrid_top_k"), 8))),
            "max_total_docs": max(4, min(12, _safe_int(planner_hints.get("hybrid_top_k"), 8)))
            * max(len(subqueries), 1),
        }
        deep_research_method = _deep_beta_research_methodology(
            topic=topic,
            subqueries=subqueries,
            retrieval_budget=deep_beta_retrieval_budgets,
        )
        deep_research_profiles = [
            {
                "profile": "beta_scope_lock",
                "goal": "Khoá phạm vi và điều kiện loại trừ ngay từ đầu.",
                "subquery": subqueries[0] if len(subqueries) > 0 else topic,
            },
            {
                "profile": "beta_hypothesis_map",
                "goal": "Lập bản đồ giả thuyết/chống giả thuyết theo hướng bằng chứng.",
                "subquery": subqueries[1] if len(subqueries) > 1 else topic,
            },
            {
                "profile": "beta_budgeted_recall",
                "goal": "Mở rộng retrieval theo ngân sách pass/source.",
                "subquery": subqueries[2] if len(subqueries) > 2 else topic,
            },
            {
                "profile": "beta_gap_fill",
                "goal": "Lấp khoảng trống bằng chứng sau mỗi pass.",
                "subquery": subqueries[3] if len(subqueries) > 3 else topic,
            },
            {
                "profile": "beta_counter_evidence",
                "goal": "Tập trung tìm bằng chứng trái chiều và ngoại lệ.",
                "subquery": subqueries[4] if len(subqueries) > 4 else topic,
            },
            {
                "profile": "beta_chain_synthesis",
                "goal": "Xây chuỗi lập luận từ bằng chứng đa pass.",
                "subquery": subqueries[5] if len(subqueries) > 5 else topic,
            },
            {
                "profile": "beta_chain_validation",
                "goal": "Đánh dấu mắt xích yếu và mức độ chắc chắn.",
                "subquery": subqueries[6] if len(subqueries) > 6 else topic,
            },
        ]
        deep_beta_reasoning_steps = _build_deep_beta_reasoning_steps(topic=topic, subqueries=subqueries)
        deep_beta_chain_status = {
            "mode": "deep_beta",
            "status": "running",
            "completed_steps": 0,
            "total_steps": len(deep_beta_reasoning_steps),
            "current_stage": "deep_beta_scope",
        }

        flow_events.append(
            _event(
                stage="deep_beta_scope",
                status="started",
                source_count=0,
                note="Deep beta stage started: scope lock.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_scope",
            status="completed",
            note="Scope lock completed.",
            payload={"topic": topic},
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": 1,
                "current_stage": "deep_beta_hypothesis_map",
            }
        )
        flow_events.append(
            _event(
                stage="deep_beta_scope",
                status="completed",
                source_count=0,
                note="Deep beta scope locked.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

        flow_events.append(
            _event(
                stage="deep_beta_hypothesis_map",
                status="started",
                source_count=0,
                note="Deep beta stage started: hypothesis map.",
                component="planner",
                payload={
                    "profiles": deep_research_profiles,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_hypothesis_map",
            status="completed",
            note="Hypothesis map completed.",
            payload={"profiles": deep_research_profiles},
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": 2,
                "current_stage": "deep_beta_retrieval_budget",
            }
        )
        flow_events.append(
            _event(
                stage="deep_beta_hypothesis_map",
                status="completed",
                source_count=0,
                note="Deep beta hypothesis map completed.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "profiles": deep_research_profiles,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

        flow_events.append(
            _event(
                stage="deep_beta_retrieval_budget",
                status="started",
                source_count=0,
                note="Deep beta stage started: retrieval budgeting.",
                component="planner",
                payload={"retrieval_budgets": deep_beta_retrieval_budgets},
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_retrieval_budget",
            status="completed",
            note="Retrieval budget allocated.",
            payload=deep_beta_retrieval_budgets,
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": 3,
                "current_stage": "deep_beta_multi_pass_retrieval",
            }
        )
        flow_events.append(
            _event(
                stage="deep_beta_retrieval_budget",
                status="completed",
                source_count=0,
                note="Deep beta retrieval budget allocated.",
                component="planner",
                payload={
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )
        flow_events.append(
            _event(
                stage="deep_beta_multi_pass_retrieval",
                status="started",
                source_count=0,
                note=f"Deep beta multi-pass retrieval started ({len(subqueries)} pass(es)).",
                component="retrieval",
                payload={
                    "pass_count": len(subqueries),
                    "subqueries": subqueries,
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )

        for pass_index, subquery in enumerate(subqueries, start=1):
            pass_started = perf_counter()
            deep_pass_flow_events.append(
                _event(
                    stage="deep_beta_retrieval_pass",
                    status="started",
                    source_count=0,
                    note=f"Deep beta retrieval pass {pass_index} started.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "retrieval_budgets": deep_beta_retrieval_budgets,
                    },
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
                    "query_focus": f"deep_beta_pass_{pass_index}",
                    "reason_codes": [
                        *planner_hints.get("reason_codes", []),
                        f"deep_beta_pass_{pass_index}",
                    ],
                    "retrieval_budget": deep_beta_retrieval_budgets,
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
                    "reasoning_focus": f"deep_beta_pass_{pass_index}",
                    "budget_target_docs": deep_beta_retrieval_budgets.get("per_pass_doc_target"),
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
                    pass_result.flow_events, default_component="deep_beta_retrieval"
                )
            )
            deep_pass_flow_events.append(
                _event(
                    stage="deep_beta_retrieval_pass",
                    status="completed",
                    source_count=len(pass_result.retrieved_ids),
                    note=f"Deep beta retrieval pass {pass_index} completed.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "docs_found": list(pass_result.retrieved_ids[:8]),
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "duration_ms": duration_ms,
                        "source_errors": source_errors,
                        "pass_summary": deep_pass_summaries[-1],
                    },
                    started_at=pass_started,
                )
            )

        _update_beta_reasoning_step(
            stage="deep_beta_multi_pass_retrieval",
            status="completed",
            note="All deep beta retrieval passes completed.",
            payload={
                "pass_count": len(deep_pass_summaries),
                "pass_summaries": deep_pass_summaries,
            },
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": 4,
                "current_stage": "deep_beta_chain_synthesis",
            }
        )
        flow_events.extend(deep_pass_flow_events)
        flow_events.append(
            _event(
                stage="deep_beta_multi_pass_retrieval",
                status="completed",
                source_count=sum(item["retrieved_count"] for item in deep_pass_summaries),
                note="Deep beta multi-pass retrieval completed.",
                component="retrieval",
                payload={
                    "pass_count": len(deep_pass_summaries),
                    "pass_summaries": deep_pass_summaries,
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )
        flow_events.append(
            _event(
                stage="deep_beta_chain_synthesis",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain synthesis started.",
                component="planner",
                payload={
                    "pass_summaries": deep_pass_summaries,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_chain_synthesis",
            status="completed",
            note="Deep beta chain synthesis prepared for final answer generation.",
            payload={"pass_summaries": deep_pass_summaries},
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": 5,
                "current_stage": "deep_beta_chain_verification",
            }
        )
        flow_events.append(
            _event(
                stage="deep_beta_chain_synthesis",
                status="completed",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain synthesis completed.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
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
    if research_mode in {"deep", "deep_beta"}:
        retrieval_trace["deep_pass_summaries"] = deep_pass_summaries
        retrieval_trace["deep_pass_count"] = len(deep_pass_summaries)
    if research_mode == "deep_beta":
        retrieval_trace["reasoning_steps"] = deep_beta_reasoning_steps
        retrieval_trace["retrieval_budgets"] = deep_beta_retrieval_budgets
        retrieval_trace["chain_status"] = deep_beta_chain_status
    flow_events.extend(_normalize_retrieval_events(rag_result.flow_events))

    merged_context = _merge_retrieved_context(rag_result.retrieved_context, deep_pass_contexts)
    filtered_context = _filter_context_for_topic(topic, merged_context)
    if filtered_context:
        effective_context = filtered_context
    elif _is_drug_interaction_query(topic):
        # For DDI queries, prefer filtered rows; if filter is too strict and returns empty,
        # gracefully fall back to merged retrieval evidence instead of an empty context.
        effective_context = merged_context[:10]
    else:
        effective_context = merged_context
    citations = _build_citations(topic, effective_context, uploaded_documents)
    if not citations and merged_context:
        citations = _build_citations(topic, merged_context[:10], uploaded_documents)
    if not citations:
        trace_rows = _trace_rows_for_citation(retrieval_trace)
        if trace_rows:
            citations = _build_citations(topic, trace_rows, uploaded_documents)
    fallback_used = _infer_fallback_used(rag_result)
    generation_trace = (
        rag_result.trace.get("generation")
        if isinstance(getattr(rag_result, "trace", None), dict)
        and isinstance(rag_result.trace.get("generation"), dict)
        else {}
    )
    fallback_reason_raw = generation_trace.get("fallback_reason")
    fallback_reason = str(fallback_reason_raw).strip() if fallback_reason_raw is not None else ""
    if fallback_used and not fallback_reason:
        fallback_reason = "llm_unavailable_or_failed"
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

    synthesis_started = perf_counter()
    flow_events.append(
        _event(
            stage="answer_synthesis",
            status="started",
            source_count=len(effective_context),
            note="Preparing final markdown answer from retrieved evidence.",
            component="postprocess",
            payload={
                "retrieved_count": len(rag_result.retrieved_ids),
                "citation_count": len(citations),
                "model_used": rag_result.model_used,
            },
        )
    )
    answer_markdown = _ensure_markdown_structure(rag_result.answer, citations)
    answer_status = "warning" if fallback_used else "completed"
    flow_events.append(
        _event(
            stage="answer_synthesis",
            status=answer_status,
            source_count=len(citations),
            note="Final markdown answer assembled.",
            component="postprocess",
            payload={
                "citation_count": len(citations),
                "fallback_used": fallback_used,
                "answer_chars": len(answer_markdown),
            },
            started_at=synthesis_started,
        )
    )
    factcheck_result = run_fides_lite(answer=answer_markdown, retrieved_context=effective_context)
    policy_action = "allow" if factcheck_result.verdict == "pass" else "warn"
    verification_state = "verified" if policy_action == "allow" else "warning"
    verification_matrix_rows = _compact_verification_matrix_rows(
        getattr(factcheck_result, "verification_matrix", []),
        max_items=20,
        max_snippet_len=180,
    )
    verification_matrix_summary = _summarize_verification_matrix(
        verification_matrix_rows,
        total_claims=factcheck_result.total_claims,
        supported_claims=factcheck_result.supported_claims,
    )
    contradiction_summary = _build_contradiction_summary(
        verification_matrix_rows,
        getattr(factcheck_result, "contradiction_summary", {}),
        fallback_note=factcheck_result.note if factcheck_result.verdict == "fail" else "",
    )
    verification_matrix_payload = {
        "version": "claim-v1",
        "rows": verification_matrix_rows,
        "summary": verification_matrix_summary,
        "contradiction_summary": contradiction_summary,
    }
    verifier_trace = _build_verifier_trace(
        factcheck_result=factcheck_result,
        policy_action=policy_action,
        verification_state=verification_state,
        verification_matrix=verification_matrix_payload,
    )
    verification_status = {
        "state": verification_state,
        "stage": factcheck_result.stage,
        "verdict": factcheck_result.verdict,
        "severity": factcheck_result.severity,
        "confidence": factcheck_result.confidence,
        "evidence_count": factcheck_result.evidence_count,
        "note": factcheck_result.note,
        "verification_matrix": {
            "summary": verification_matrix_summary,
            "contradiction_summary": contradiction_summary,
        },
    }
    if research_mode == "deep_beta":
        flow_events.append(
            _event(
                stage="deep_beta_chain_verification",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain verification started.",
                component="verifier",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                    "pass_summaries": deep_pass_summaries,
                },
            )
        )
    flow_events.append(
        _event(
            stage="verification",
            status="started",
            source_count=factcheck_result.evidence_count,
            note="Verifier started evidence consistency checks.",
            component="verifier",
            payload={"verifier": factcheck_result.stage},
        )
    )
    flow_events.append(
        _event(
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
    contradiction_stage_status = (
        "warning" if bool(contradiction_summary.get("has_contradiction")) else "completed"
    )
    flow_events.append(
        _event(
            stage="contradiction_miner",
            status=contradiction_stage_status,
            source_count=_safe_int(contradiction_summary.get("contradiction_count"), 0),
            note=str(contradiction_summary.get("note") or "Contradiction miner completed."),
            component="verifier",
            payload={
                "has_contradiction": bool(contradiction_summary.get("has_contradiction")),
                "contradiction_count": _safe_int(
                    contradiction_summary.get("contradiction_count"),
                    0,
                ),
                "claims": contradiction_summary.get("claims", []),
                "details": contradiction_summary.get("details", []),
                "summary": contradiction_summary,
            },
        )
    )
    flow_events.append(
        _event(
            stage="verification_matrix",
            status="completed",
            source_count=factcheck_result.evidence_count,
            note="Verification matrix generated from claim-level factcheck outputs.",
            component="verifier",
            payload={
                "supported_claims": factcheck_result.supported_claims,
                "unsupported_claims": len(factcheck_result.unsupported_claims),
                "total_claims": factcheck_result.total_claims,
                "severity": factcheck_result.severity,
                "confidence": factcheck_result.confidence,
                "summary": verification_matrix_summary,
                "rows": verification_matrix_rows,
                "contradiction_summary": contradiction_summary,
            },
        )
    )
    if research_mode == "deep_beta":
        chain_verification_status = (
            "warning"
            if contradiction_summary.get("has_contradiction") or factcheck_result.verdict != "pass"
            else "completed"
        )
        deep_beta_chain_status.update(
            {
                "completed_steps": len(deep_beta_reasoning_steps),
                "current_stage": "deep_beta_chain_verification",
                "status": "completed",
                "verification_status": chain_verification_status,
            }
        )
        _update_beta_reasoning_step(
            stage="deep_beta_chain_verification",
            status=chain_verification_status,
            note="Deep beta chain verification completed.",
            payload={
                "verdict": factcheck_result.verdict,
                "support_ratio": verification_matrix_summary.get("support_ratio"),
                "contradiction_count": contradiction_summary.get("contradiction_count"),
            },
        )
        flow_events.append(
            _event(
                stage="deep_beta_chain_verification",
                status=chain_verification_status,
                source_count=factcheck_result.evidence_count,
                note="Deep beta chain verification completed.",
                component="verifier",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                    "summary": verification_matrix_summary,
                    "contradiction_summary": contradiction_summary,
                },
            )
        )
    flow_events.append(
        _event(
            stage="citation_selection",
            status="completed",
            source_count=len(citations),
            note=f"Selected {len(citations)} citation(s) for final answer.",
            component="postprocess",
            payload={"citation_count": len(citations)},
        )
    )
    flow_events = _normalize_retrieval_events(flow_events, default_component="tier2_orchestrator")

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
    elif isinstance(retrieval_trace.get("source_errors"), dict):
        aggregated_errors.update(retrieval_trace.get("source_errors", {}))
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

    query_plan = (
        retrieval_trace.get("query_plan")
        if isinstance(retrieval_trace.get("query_plan"), dict)
        else {}
    )
    if not query_plan and isinstance(planner_hints.get("query_plan"), dict):
        query_plan = dict(planner_hints.get("query_plan", {}))
    if not query_plan:
        query_plan = {
            "original_query": topic,
            "canonical_query": topic,
            "source_queries": {"internal": [topic], "scientific": [topic], "web": [topic]},
            "decomposition": {
                "fast_pass_queries": [topic],
                "deep_pass_queries": [topic],
                "deep_beta_pass_queries": [topic],
            },
            "research_mode": research_mode,
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
        "query_plan": query_plan,
        "search_plan": {
            **search_plan,
            "subqueries": deep_subqueries,
            "research_mode": research_mode,
            "profiles": deep_research_profiles,
            "retrieval_budgets": deep_beta_retrieval_budgets
            if research_mode == "deep_beta"
            else planner_hints.get("retrieval_budget", {}),
        },
        "source_attempts": source_attempts,
        "source_errors": aggregated_errors,
        "fallback_reason": fallback_reason or None,
        "index_summary": index_summary,
        "crawl_summary": crawl_summary,
        "docs": _compact_context_rows(effective_context, max_items=10, max_text_len=240),
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
        "pass_summaries": deep_pass_summaries,
        "deep_research_profiles": deep_research_profiles,
        "deep_research_methodology": deep_research_method,
        "reasoning_steps": deep_beta_reasoning_steps if research_mode == "deep_beta" else [],
        "retrieval_budgets": deep_beta_retrieval_budgets if research_mode == "deep_beta" else {},
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "verification_matrix": verification_matrix_payload,
    }
    citations_payload = [asdict(item) for item in citations]
    compact_context_debug = _compact_context_debug(rag_result.context_debug)

    return {
        "metadata": {
            "response_style": "progressive",
            "pipeline": (
                "p2-research-tier2-deep-v1"
                if research_mode == "deep"
                else "p2-research-tier2-deep-beta-v1"
                if research_mode == "deep_beta"
                else "p2-research-tier2-hybrid-v2"
            ),
            "stages": [
                {"name": "plan", "status": "completed"},
                *(
                    [{"name": "deep_research", "status": "completed"}]
                    if research_mode == "deep"
                    else [
                        {"name": "deep_beta_scope", "status": "completed"},
                        {"name": "deep_beta_hypothesis_map", "status": "completed"},
                        {"name": "deep_beta_retrieval_budget", "status": "completed"},
                        {"name": "deep_beta_multi_pass_retrieval", "status": retrieval_status},
                        {"name": "deep_beta_chain_synthesis", "status": "completed"},
                        {
                            "name": "deep_beta_chain_verification",
                            "status": (
                                deep_beta_chain_status.get("verification_status", "completed")
                                if isinstance(deep_beta_chain_status, dict)
                                else "completed"
                            ),
                        },
                    ]
                    if research_mode == "deep_beta"
                    else []
                ),
                {"name": "hybrid_retrieval", "status": retrieval_status},
                {"name": "answer_synthesis", "status": answer_status},
                {"name": "verification", "status": verification_state},
                {"name": "contradiction_miner", "status": contradiction_stage_status},
                {"name": "verification_matrix", "status": "completed"},
                {"name": "citation_selection", "status": "completed"},
            ],
            "fallback_used": effective_fallback_used,
            "fallback_reason": fallback_reason or None,
            "source_mode": source_mode,
            "research_mode": research_mode,
            "deep_pass_count": len(deep_pass_summaries),
            "source_attempts": source_attempts,
            "source_errors": aggregated_errors,
            "query_plan": query_plan,
            "context_debug": compact_context_debug,
            "policy_action": policy_action,
            "verification_status": verification_status,
            "verification_matrix": verification_matrix_payload,
            "planner_trace": planner_trace,
            "retrieval_trace": retrieval_trace,
            "verifier_trace": verifier_trace,
            "trace": trace_bundle,
            "flow_events": flow_events,
            "telemetry": telemetry,
            "deep_research_methodology": deep_research_method,
            "reasoning_steps": deep_beta_reasoning_steps if research_mode == "deep_beta" else [],
            "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
            "retrieval_budgets": (
                deep_beta_retrieval_budgets
                if research_mode == "deep_beta"
                else planner_hints.get("retrieval_budget", {})
            ),
            "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
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
        "context_debug": compact_context_debug,
        "flow_events": flow_events,
        "planner_trace": planner_trace,
        "retrieval_trace": retrieval_trace,
        "verifier_trace": verifier_trace,
        "trace": trace_bundle,
        "telemetry": telemetry,
        "policy_action": policy_action,
        "verification_status": verification_status,
        "verification_matrix": verification_matrix_payload,
        "contradiction_summary": contradiction_summary,
        "fallback_used": effective_fallback_used,
        "fallback_reason": fallback_reason or None,
        "source_attempts": source_attempts,
        "source_errors": aggregated_errors,
        "query_plan": query_plan,
        "research_mode": research_mode,
        "deep_pass_count": len(deep_pass_summaries),
        "reasoning_steps": deep_beta_reasoning_steps if research_mode == "deep_beta" else [],
        "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
        "retrieval_budgets": (
            deep_beta_retrieval_budgets
            if research_mode == "deep_beta"
            else planner_hints.get("retrieval_budget", {})
        ),
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "plan_steps": [asdict(step) for step in plan_steps],
        "citations": citations_payload,
        # Backward-compat alias for clients still expecting `sources`.
        "sources": citations_payload,
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
