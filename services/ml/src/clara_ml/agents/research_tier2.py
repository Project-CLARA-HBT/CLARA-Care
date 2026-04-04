from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any
import unicodedata
import urllib.error
import urllib.request
from uuid import uuid4

from clara_ml.config import settings
from clara_ml.factcheck import FactCheckResult, run_fides_lite
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.rag.retrieval.source_router import (
    SourceRouterDecision,
    decide_source_route,
    to_metadata_payload as source_route_metadata_payload,
)
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
    "## Theo dõi & cảnh báo đỏ",
    "## Nguồn tham chiếu",
)

_REQUIRED_DEEP_MARKDOWN_HEADINGS = (
    "## Kết luận nhanh",
    "## Tóm tắt điều hành",
    "## Câu hỏi nghiên cứu (PICO)",
    "## Phương pháp truy xuất & tiêu chí chọn lọc",
    "## Hồ sơ bằng chứng & chất lượng nguồn",
    "## Tổng hợp phát hiện chính",
    "## Phản biện bằng chứng đối nghịch",
    "## Ứng dụng lâm sàng theo nhóm bệnh nhân",
    "## Ma trận quyết định an toàn",
    "## Kế hoạch theo dõi sau tư vấn",
    "## Giới hạn, sai số và rủi ro pháp lý",
    "## Nguồn tham chiếu",
)

_DEFAULT_DEEP_PASS_CAP = 12
_DEEP_BETA_PASS_CAP = 20
_DEEP_BETA_REASONING_STAGE_ORDER = (
    "deep_beta_scope",
    "deep_beta_hypothesis_map",
    "deep_beta_retrieval_budget",
    "deep_beta_multi_pass_retrieval",
    "deep_beta_evidence_audit",
    "deep_beta_claim_graph",
    "deep_beta_counter_evidence_scan",
    "deep_beta_guideline_alignment",
    "deep_beta_risk_stratification",
    "deep_beta_gap_fill",
    "deep_beta_evidence_verification",
    "deep_beta_chain_synthesis",
    "deep_beta_report_synthesis",
    "deep_beta_quality_gate",
    "deep_beta_chain_verification",
)
_ALLOWED_RETRIEVAL_ROUTES = {
    "internal-heavy",
    "scientific-heavy",
    "web-assisted",
    "file-grounded",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "-", text)
    return compact[:160]


def _resolve_trace_identifiers(payload: dict[str, Any]) -> tuple[str, str]:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    trace_obj = payload.get("trace")
    trace = trace_obj if isinstance(trace_obj, dict) else {}

    trace_id = (
        _normalized_identifier(payload.get("trace_id"))
        or _normalized_identifier(metadata.get("trace_id"))
        or _normalized_identifier(trace.get("trace_id"))
    )
    run_id = (
        _normalized_identifier(payload.get("run_id"))
        or _normalized_identifier(metadata.get("run_id"))
        or _normalized_identifier(trace.get("run_id"))
        or _normalized_identifier(payload.get("request_id"))
        or _normalized_identifier(metadata.get("request_id"))
    )

    if trace_id and run_id:
        return trace_id, run_id
    if run_id and not trace_id:
        return f"tier2-trace-{run_id}", run_id
    if trace_id and not run_id:
        return trace_id, f"tier2-run-{trace_id}"

    seed = uuid4().hex
    return f"tier2-trace-{seed}", f"tier2-run-{seed}"


def _parse_event_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def _normalize_retrieval_stack_mode(payload: dict[str, Any]) -> str:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    raw_mode = (
        str(
            payload.get("retrieval_stack_mode")
            or payload.get("stack_mode")
            or metadata.get("retrieval_stack_mode")
            or metadata.get("stack_mode")
            or "auto"
        )
        .strip()
        .lower()
    )
    if raw_mode in {"full", "full_stack", "full-stack"}:
        return "full"
    return "auto"


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return None


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or ""))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_marks.lower()


def _detect_language_hint(text: str) -> tuple[bool, bool, str]:
    lowered = str(text or "").lower()
    has_vietnamese_marks = bool(
        re.search(
            r"[àáạảãâầấậẩẫăằắặẳẵđèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]",
            lowered,
        )
    )
    has_english_markers = bool(
        re.search(
            r"\b(interaction|guideline|evidence|review|trial|safety|contraindication|bleeding)\b",
            lowered,
        )
    )
    if has_vietnamese_marks and has_english_markers:
        return has_vietnamese_marks, has_english_markers, "mixed"
    if has_vietnamese_marks:
        return has_vietnamese_marks, has_english_markers, "vi"
    return has_vietnamese_marks, has_english_markers, "en"


def _normalize_retrieval_route(value: Any) -> str:
    route = str(value or "").strip().lower()
    if route in _ALLOWED_RETRIEVAL_ROUTES:
        return route
    return "internal-heavy"


def _normalize_router_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(numeric, 1.0)), 4)


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


def _build_provider_query_overrides(
    *,
    original_query: str,
    canonical_query: str,
    language_hint: str,
    keywords: list[str],
) -> dict[str, dict[str, str]]:
    cleaned_original = " ".join(str(original_query or "").split()).strip()
    cleaned_canonical = " ".join(str(canonical_query or "").split()).strip()
    keyword_phrase = " ".join(
        item.strip() for item in keywords if isinstance(item, str) and item.strip()
    )
    folded_original = _ascii_fold(cleaned_original)
    vi_focus = cleaned_original or folded_original or cleaned_canonical
    en_focus = cleaned_canonical or folded_original or cleaned_original
    if not en_focus:
        en_focus = keyword_phrase
    if not vi_focus:
        vi_focus = keyword_phrase

    scientific_query = en_focus
    if keyword_phrase:
        scientific_query = " ".join([en_focus, keyword_phrase]).strip()
    scientific_query = scientific_query[:360]

    web_query = vi_focus if language_hint in {"vi", "mixed"} else en_focus
    web_query = web_query[:320]

    regulatory_query = vi_focus if language_hint in {"vi", "mixed"} else cleaned_original or web_query
    regulatory_query = regulatory_query[:320]

    return {
        "scientific": {
            "pubmed": scientific_query,
            "europepmc": scientific_query,
            "semantic_scholar": scientific_query,
            "openalex": scientific_query,
            "crossref": scientific_query,
            "clinicaltrials": scientific_query,
            "openfda": scientific_query,
            "dailymed": scientific_query,
            "rxnorm": scientific_query,
        },
        "web": {
            "searxng": web_query,
        },
        "regulatory": {
            "davidrug": regulatory_query,
            "vn_moh": regulatory_query,
            "vn_kcb": regulatory_query,
            "vn_canhgiacduoc": regulatory_query,
            "vn_vbpl_byt": regulatory_query,
            "vn_dav": regulatory_query,
        },
    }


def _sanitize_provider_query_overrides(
    value: Any,
    *,
    fallback: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return fallback

    normalized: dict[str, dict[str, str]] = {}
    for category_raw, provider_map in value.items():
        category = str(category_raw or "").strip().lower()
        if category not in {"scientific", "web", "regulatory"}:
            continue
        if not isinstance(provider_map, dict):
            continue
        row: dict[str, str] = {}
        for provider_raw, query_raw in provider_map.items():
            provider = str(provider_raw or "").strip().lower()
            query_text = " ".join(str(query_raw or "").split()).strip()
            if not provider or not query_text:
                continue
            row[provider] = query_text[:360]
        if row:
            normalized[category] = row

    merged: dict[str, dict[str, str]] = {}
    for category in ("scientific", "web", "regulatory"):
        fallback_row = fallback.get(category, {})
        merged_row = dict(fallback_row)
        if category in normalized:
            merged_row.update(normalized[category])
        if merged_row:
            merged[category] = merged_row
    return merged or fallback


def _build_source_aware_query_plan(
    *,
    topic: str,
    research_mode: str,
    keywords: list[str],
    source_route: SourceRouterDecision | None = None,
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

    _, _, language_hint = _detect_language_hint(original_query)

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
    provider_queries = _build_provider_query_overrides(
        original_query=original_query,
        canonical_query=canonical_query,
        language_hint=language_hint,
        keywords=keyword_terms[:10],
    )

    route_payload = source_route_metadata_payload(source_route)
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
        "provider_queries": provider_queries,
        "research_mode": research_mode,
        "query_terms": keyword_terms[:10],
        "retrieval_route": route_payload.get("retrieval_route"),
        "router_confidence": route_payload.get("router_confidence"),
        "router_reason_codes": route_payload.get("router_reason_codes", []),
    }


def _strip_markdown_fence(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _safe_planner_error_code(exc: Exception) -> str:
    normalized = f"{exc.__class__.__name__}:{exc}".lower()
    if "timeout" in normalized:
        return "timeout"
    if "json" in normalized:
        return "invalid_json"
    if "schema" in normalized or "required" in normalized or "missing" in normalized:
        return "invalid_schema"
    if "deepseek_request_failed" in normalized:
        return "provider_request_failed"
    return "runtime_error"


def _sanitize_required_query_entries(
    value: Any,
    *,
    field_name: str,
    limit: int,
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Missing required list field: {field_name}")
    cleaned = _dedupe_query_list([str(item) for item in value], limit=limit)
    if not cleaned:
        raise ValueError(f"Required list field has no usable values: {field_name}")
    return cleaned


def _sanitize_llm_query_plan_payload(
    payload: Any,
    *,
    base_query_plan: dict[str, Any],
    research_mode: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Planner output must be a JSON object")

    required_keys = {"canonical_query", "language_hint", "keywords", "source_queries", "decomposition"}
    if not required_keys.issubset(set(payload.keys())):
        raise ValueError("Planner output missing required keys")

    canonical_query = " ".join(str(payload.get("canonical_query") or "").split()).strip()
    if not canonical_query:
        raise ValueError("Planner output missing canonical_query")
    canonical_query = canonical_query[:320]

    language_hint_raw = str(payload.get("language_hint") or "").strip().lower()
    language_hint = language_hint_raw if language_hint_raw in {"vi", "en", "mixed"} else "mixed"

    keywords_raw = payload.get("keywords")
    if not isinstance(keywords_raw, list):
        raise ValueError("Planner output keywords must be list")
    keywords = _dedupe_query_list([str(item) for item in keywords_raw], limit=12)
    if not keywords:
        keywords = _dedupe_query_list(query_terms(canonical_query), limit=12)
    if not keywords:
        raise ValueError("Planner output keywords must not be empty")

    source_queries_raw = payload.get("source_queries")
    if not isinstance(source_queries_raw, dict):
        raise ValueError("Planner output source_queries must be object")
    internal_queries = _sanitize_required_query_entries(
        source_queries_raw.get("internal"),
        field_name="source_queries.internal",
        limit=8,
    )
    scientific_queries = _sanitize_required_query_entries(
        source_queries_raw.get("scientific"),
        field_name="source_queries.scientific",
        limit=8,
    )
    web_queries = _sanitize_required_query_entries(
        source_queries_raw.get("web"),
        field_name="source_queries.web",
        limit=8,
    )

    decomposition_raw = payload.get("decomposition")
    if not isinstance(decomposition_raw, dict):
        raise ValueError("Planner output decomposition must be object")
    deep_pass_queries = _sanitize_required_query_entries(
        decomposition_raw.get("deep_pass_queries"),
        field_name="decomposition.deep_pass_queries",
        limit=12,
    )
    deep_beta_limit = _DEEP_BETA_PASS_CAP
    deep_beta_pass_queries = _sanitize_required_query_entries(
        decomposition_raw.get("deep_beta_pass_queries"),
        field_name="decomposition.deep_beta_pass_queries",
        limit=deep_beta_limit,
    )
    fast_pass_queries = _dedupe_query_list(
        [canonical_query, base_query_plan.get("original_query"), " ".join(keywords[:6])],
        limit=4,
    )
    fallback_provider_queries = _build_provider_query_overrides(
        original_query=str(base_query_plan.get("original_query") or canonical_query),
        canonical_query=canonical_query,
        language_hint=language_hint,
        keywords=keywords[:10],
    )
    provider_queries = _sanitize_provider_query_overrides(
        payload.get("provider_queries"),
        fallback=fallback_provider_queries,
    )

    return {
        "original_query": str(base_query_plan.get("original_query") or canonical_query),
        "canonical_query": canonical_query,
        "language_hint": language_hint,
        "is_ddi_query": bool(base_query_plan.get("is_ddi_query")),
        "is_ddi_critical_query": bool(base_query_plan.get("is_ddi_critical_query")),
        "source_queries": {
            "internal": internal_queries,
            "scientific": scientific_queries,
            "web": web_queries,
        },
        "decomposition": {
            "fast_pass_queries": fast_pass_queries,
            "deep_pass_queries": deep_pass_queries,
            "deep_beta_pass_queries": deep_beta_pass_queries,
        },
        "provider_queries": provider_queries,
        "research_mode": research_mode,
        "query_terms": keywords[:10],
    }


def _resolve_runtime_llm_config(
    llm_runtime: dict[str, Any] | None,
) -> tuple[str, str, str, str]:
    runtime = llm_runtime if isinstance(llm_runtime, dict) else {}
    provider = str(runtime.get("provider") or "deepseek").strip().lower()
    if provider == "hitechcloud_gpt53_codex_high":
        api_key = (
            str(runtime.get("api_key") or "").strip()
            or str(settings.primary_llm_api_key or "").strip()
        )
        base_url = (
            str(runtime.get("base_url") or "").strip()
            or str(settings.primary_llm_base_url or "").strip()
            or "https://platform.hitechcloud.one/v1"
        )
        model = (
            str(runtime.get("model") or "").strip()
            or str(settings.primary_llm_model or "").strip()
            or "gpt-5.3-codex-high"
        )
        return provider, api_key, base_url, model

    api_key = str(runtime.get("api_key") or "").strip() or str(settings.deepseek_api_key or "").strip()
    base_url = str(runtime.get("base_url") or "").strip() or str(settings.deepseek_base_url or "").strip()
    model = str(runtime.get("model") or "").strip() or str(settings.deepseek_model or "").strip()
    return "deepseek", api_key, base_url, model


def _build_query_planner_client(
    *, llm_runtime: dict[str, Any] | None = None
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    timeout_seconds = max(1.0, min(float(settings.deepseek_timeout_seconds), 8.0))
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        retries_per_base=0,
        retry_backoff_seconds=0.0,
    )


def _build_reasoning_client(
    *,
    timeout_seconds: float | None = None,
    llm_runtime: dict[str, Any] | None = None,
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    resolved_timeout = float(timeout_seconds or settings.deep_beta_reasoning_llm_timeout_seconds)
    resolved_timeout = max(2.0, min(resolved_timeout, 120.0))
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=resolved_timeout,
        retries_per_base=0,
        retry_backoff_seconds=0.0,
    )


def _parse_json_from_llm(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_markdown_fence(str(raw_text or "").strip())
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("llm_json_not_object")
    return parsed


def _run_deep_beta_llm_reasoning_node(
    *,
    node_name: str,
    objective: str,
    topic: str,
    query_plan: dict[str, Any],
    retrieval_budget: dict[str, Any],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.deep_beta_reasoning_llm_enabled:
        return {
            "node": node_name,
            "status": "skipped",
            "reason": "deep_beta_reasoning_llm_disabled",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "node": node_name,
            "status": "degraded",
            "reason": "api_key_missing",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
        }

    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "duration_ms": item.get("duration_ms"),
            "source_errors": item.get("source_errors", {}),
        }
        for item in deep_pass_summaries[:12]
        if isinstance(item, dict)
    ]
    compact_evidence = [
        {
            "id": item.get("id"),
            "source": item.get("source"),
            "title": item.get("title"),
            "score": item.get("score"),
            "text": _compact_snippet(item.get("text", ""), max_len=220),
        }
        for item in evidence_rows[:20]
        if isinstance(item, dict)
    ]

    system_prompt = (
        "You are a clinical research reasoning worker node in a multi-agent RAG pipeline. "
        "Return STRICT JSON only. No markdown. No extra keys."
    )
    prompt = (
        "Analyze this node objective and produce structured reasoning output.\n"
        "Output EXACT JSON:\n"
        "{\n"
        '  "confidence": 0.0,\n'
        '  "insights": ["short insight"],\n'
        '  "actions": ["next action"],\n'
        '  "watchouts": ["risk/caveat"],\n'
        '  "follow_up_queries": ["targeted retrieval query"],\n'
        '  "evidence_checks": ["specific evidence check"]\n'
        "}\n"
        "Constraints:\n"
        "- confidence must be between 0 and 1\n"
        "- each array size <= 6\n"
        "- focus on evidence quality, contradiction risk, and retrieval gaps\n\n"
        f"node_name={node_name}\n"
        f"objective={objective}\n"
        f"topic={topic}\n"
        f"query_plan={json.dumps(query_plan, ensure_ascii=False)}\n"
        f"retrieval_budget={json.dumps(retrieval_budget, ensure_ascii=False)}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
        f"evidence_rows={json.dumps(compact_evidence, ensure_ascii=False)}\n"
    )

    try:
        client = _build_reasoning_client(llm_runtime=llm_runtime)
        if client is None:
            return {
                "node": node_name,
                "status": "degraded",
                "reason": "runtime_llm_unconfigured",
                "confidence": 0.0,
                "insights": [],
                "actions": [],
                "watchouts": [],
                "follow_up_queries": [],
                "evidence_checks": [],
            }
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
        parsed = _parse_json_from_llm(response.content)
        confidence = _normalize_router_confidence(parsed.get("confidence"))

        def _clean_list(key: str) -> list[str]:
            raw = parsed.get(key)
            if not isinstance(raw, list):
                return []
            cleaned: list[str] = []
            for item in raw[:6]:
                text = " ".join(str(item or "").split()).strip()
                if text:
                    cleaned.append(text)
            return cleaned

        return {
            "node": node_name,
            "status": "completed",
            "reason": "ok",
            "model_used": response.model,
            "confidence": confidence,
            "insights": _clean_list("insights"),
            "actions": _clean_list("actions"),
            "watchouts": _clean_list("watchouts"),
            "follow_up_queries": _clean_list("follow_up_queries"),
            "evidence_checks": _clean_list("evidence_checks"),
        }
    except Exception as exc:  # pragma: no cover - provider/network defensive path
        return {
            "node": node_name,
            "status": "degraded",
            "reason": f"{exc.__class__.__name__}",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
            "follow_up_queries": [],
            "evidence_checks": [],
        }


def _run_deep_beta_parallel_reasoning_nodes(
    *,
    topic: str,
    query_plan: dict[str, Any],
    retrieval_budget: dict[str, Any],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    nodes = [
        (
            "deep_beta_evidence_audit",
            "Audit evidence coverage quality, identify weak sources and unresolved questions.",
        ),
        (
            "deep_beta_claim_graph",
            "Build claim/conflict graph across passes and flag contradiction hypotheses.",
        ),
        (
            "deep_beta_counter_evidence_scan",
            "Find strongest counter-evidence, adverse subgroup exceptions, and unresolved caveats.",
        ),
        (
            "deep_beta_guideline_alignment",
            "Check alignment/misalignment between retrieved evidence and guideline-level recommendations.",
        ),
        (
            "deep_beta_risk_stratification",
            "Stratify risk signals by age/comorbidity/polypharmacy and highlight red-flag trajectories.",
        ),
        (
            "deep_beta_gap_fill",
            "Propose high-yield gap-fill retrieval actions to improve coverage.",
        ),
    ]
    max_nodes = max(1, min(int(settings.deep_beta_reasoning_llm_nodes), len(nodes)))
    selected_nodes = nodes[:max_nodes]
    if not selected_nodes:
        return []

    reasoning_rounds = max(1, int(settings.deep_beta_reasoning_rounds))
    max_workers = max(1, min(int(settings.deep_beta_reasoning_parallel_workers), len(selected_nodes)))
    outputs: list[dict[str, Any]] = []
    for round_index in range(1, reasoning_rounds + 1):
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="deep-beta-llm") as executor:
            futures = {
                executor.submit(
                    _run_deep_beta_llm_reasoning_node,
                    node_name=node_name,
                    objective=(
                        f"{objective} "
                        f"(round {round_index}/{reasoning_rounds}; prioritize unresolved gaps from earlier rounds)"
                        if reasoning_rounds > 1
                        else objective
                    ),
                    topic=topic,
                    query_plan=query_plan,
                    retrieval_budget=retrieval_budget,
                    deep_pass_summaries=deep_pass_summaries,
                    evidence_rows=evidence_rows,
                    llm_runtime=llm_runtime,
                ): node_name
                for node_name, objective in selected_nodes
            }
            for future in as_completed(futures):
                node_name = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive
                    result = {
                        "node": node_name,
                        "status": "degraded",
                        "reason": f"{exc.__class__.__name__}",
                        "confidence": 0.0,
                        "insights": [],
                        "actions": [],
                        "watchouts": [],
                        "follow_up_queries": [],
                        "evidence_checks": [],
                    }
                result["round"] = round_index
                result["rounds_total"] = reasoning_rounds
                outputs.append(result)
    outputs.sort(
        key=lambda item: (
            str(item.get("node")),
            _safe_int(item.get("round"), 0),
        )
    )
    return outputs


def _collect_reasoning_follow_up_queries(
    reasoning_nodes: list[dict[str, Any]],
    *,
    limit: int,
) -> list[str]:
    if limit <= 0:
        return []
    collected: list[str] = []
    for node in reasoning_nodes:
        if not isinstance(node, dict):
            continue
        for key in ("follow_up_queries", "evidence_checks", "actions", "watchouts"):
            raw = node.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                text = " ".join(str(item or "").split()).strip()
                if not text:
                    continue
                collected.append(text)
    return _dedupe_query_list(collected, limit=limit)


def _run_deep_beta_evidence_verification_node(
    *,
    topic: str,
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    reasoning_nodes: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.deep_beta_evidence_verification_enabled:
        return {
            "status": "skipped",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": [],
            "high_risk_flags": [],
            "model_used": "disabled",
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "status": "degraded",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": ["DeepSeek API key missing."],
            "high_risk_flags": [],
            "model_used": "unconfigured",
        }

    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "source_errors": item.get("source_errors", {}),
        }
        for item in deep_pass_summaries[:18]
        if isinstance(item, dict)
    ]
    compact_evidence = [
        {
            "id": item.get("id"),
            "source": item.get("source"),
            "title": item.get("title"),
            "score": item.get("score"),
            "snippet": _compact_snippet(item.get("text"), max_len=180),
        }
        for item in evidence_rows[:28]
        if isinstance(item, dict)
    ]
    compact_nodes = [
        {
            "node": item.get("node"),
            "status": item.get("status"),
            "confidence": item.get("confidence"),
            "insights": item.get("insights", [])[:3] if isinstance(item.get("insights"), list) else [],
            "watchouts": item.get("watchouts", [])[:3] if isinstance(item.get("watchouts"), list) else [],
        }
        for item in reasoning_nodes[:20]
        if isinstance(item, dict)
    ]
    prompt = (
        "Verify evidence support at claim level for this deep research run.\n"
        "Output STRICT JSON only with exact schema:\n"
        "{\n"
        '  "verification_confidence": 0.0,\n'
        '  "supported_claims": ["..."],\n'
        '  "unsupported_claims": ["..."],\n'
        '  "contradicted_claims": ["..."],\n'
        '  "evidence_gaps": ["..."],\n'
        '  "high_risk_flags": ["..."]\n'
        "}\n"
        "Rules:\n"
        "- keep each list <= 8 items\n"
        "- do not prescribe diagnosis/dose\n"
        "- high_risk_flags should prioritize clinical safety issues\n"
        "- if evidence is weak, explicitly add to evidence_gaps\n\n"
        f"topic={topic}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
        f"evidence_rows={json.dumps(compact_evidence, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(compact_nodes, ensure_ascii=False)}\n"
    )
    try:
        client = _build_reasoning_client(
            timeout_seconds=max(float(settings.deep_beta_evidence_verification_timeout_seconds), 2.0),
            llm_runtime=llm_runtime,
        )
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        response = client.generate(
            prompt=prompt,
            system_prompt=(
                "You are CLARA deep evidence verifier. "
                "Be conservative and safety-first. Output strict JSON only."
            ),
        )
        parsed = _parse_json_from_llm(response.content)

        def _clean(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            cleaned: list[str] = []
            for item in value[:8]:
                text = " ".join(str(item or "").split()).strip()
                if text:
                    cleaned.append(text)
            return cleaned

        return {
            "status": "completed",
            "verification_confidence": _normalize_router_confidence(
                parsed.get("verification_confidence")
            ),
            "supported_claims": _clean(parsed.get("supported_claims")),
            "unsupported_claims": _clean(parsed.get("unsupported_claims")),
            "contradicted_claims": _clean(parsed.get("contradicted_claims")),
            "evidence_gaps": _clean(parsed.get("evidence_gaps")),
            "high_risk_flags": _clean(parsed.get("high_risk_flags")),
            "model_used": response.model,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "degraded",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": [f"evidence_verification_error:{exc.__class__.__name__}"],
            "high_risk_flags": [],
            "model_used": "error",
        }


def _run_deep_beta_quality_gate(
    *,
    topic: str,
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    reasoning_nodes: list[dict[str, Any]],
    evidence_verification: dict[str, Any] | None = None,
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.deep_beta_quality_gate_enabled:
        return {
            "status": "skipped",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": [],
            "follow_up_actions": [],
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "status": "degraded",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": ["DeepSeek API key missing for quality gate."],
            "follow_up_actions": [],
        }

    compact_citations = [
        {
            "source_id": item.source_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
        }
        for item in citations[:14]
    ]
    prompt = (
        "Evaluate this medical deep-research markdown answer quality.\n"
        "Return STRICT JSON only.\n"
        "Schema:\n"
        "{\n"
        '  "quality_score": 0.0,\n'
        '  "groundedness_score": 0.0,\n'
        '  "completeness_score": 0.0,\n'
        '  "revision_required": false,\n'
        '  "findings": ["..."],\n'
        '  "follow_up_actions": ["..."]\n'
        "}\n"
        "Rules:\n"
        "- scores in [0,1]\n"
        "- findings/follow_up_actions max 6 each\n"
        "- penalize unsupported clinical claims, missing safety caveats, weak attribution\n\n"
        f"topic={topic}\n"
        f"answer_markdown={answer_markdown}\n"
        f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
        f"verification_matrix={json.dumps(verification_matrix_payload, ensure_ascii=False)}\n"
        f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(reasoning_nodes[:12], ensure_ascii=False)}\n"
    )
    try:
        client = _build_reasoning_client(
            timeout_seconds=max(float(settings.deep_beta_quality_gate_timeout_seconds), 2.0),
            llm_runtime=llm_runtime,
        )
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        response = client.generate(
            prompt=prompt,
            system_prompt=(
                "You are CLARA quality gate evaluator for medical RAG reports. "
                "Be strict and safety-first. Output strict JSON only."
            ),
        )
        parsed = _parse_json_from_llm(response.content)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "degraded",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": [f"quality_gate_error:{exc.__class__.__name__}"],
            "follow_up_actions": [],
        }

    def _clamp(value: Any) -> float:
        return _normalize_router_confidence(value)

    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value[:6]:
            text = " ".join(str(item or "").split()).strip()
            if text:
                cleaned.append(text)
        return cleaned

    return {
        "status": "completed",
        "quality_score": _clamp(parsed.get("quality_score")),
        "groundedness_score": _clamp(parsed.get("groundedness_score")),
        "completeness_score": _clamp(parsed.get("completeness_score")),
        "revision_required": bool(parsed.get("revision_required", False)),
        "findings": _clean_list(parsed.get("findings")),
        "follow_up_actions": _clean_list(parsed.get("follow_up_actions")),
    }


def _normalize_mermaid_block_body(body: str) -> str:
    normalized = str(body or "")
    normalized = re.sub(r"<\s*br\s*/?\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</?[a-z][^>\n]*>", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"&nbsp;", " ", normalized, flags=re.IGNORECASE)
    # Normalize inline citations like " ... [1]" or " ... [pubmed-123]".
    normalized = re.sub(
        r"(?<=\s)\[((?:\d{1,3})|(?:[A-Za-z][A-Za-z0-9_.:-]{2,}))\](?=(?:\s|$|[.,;:\]]))",
        r"(\1)",
        normalized,
    )
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def _strip_html_from_mermaid_blocks(markdown_text: str) -> str:
    text = str(markdown_text or "")
    pattern = re.compile(r"```mermaid\s*(.*?)```", flags=re.DOTALL | re.IGNORECASE)

    def _normalize(block: re.Match[str]) -> str:
        body = _normalize_mermaid_block_body(block.group(1))
        return f"```mermaid\n{body}\n```"

    return pattern.sub(_normalize, text)


def _canonical_h2_key(heading: str) -> str:
    text = str(heading or "")
    if text.startswith("## "):
        text = text[3:]
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return text


def _resolve_required_deep_heading_key(heading: str) -> str:
    key = _canonical_h2_key(heading)
    if not key:
        return ""
    for required in _REQUIRED_DEEP_MARKDOWN_HEADINGS:
        required_key = _canonical_h2_key(required)
        if key == required_key or key.startswith(f"{required_key} "):
            return required_key
    return key


def _dedupe_duplicate_h2_headings(markdown_text: str) -> str:
    lines = [line.rstrip() for line in str(markdown_text or "").splitlines()]
    prelude: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is None:
                if current_lines:
                    prelude.extend(current_lines)
            else:
                sections.append((current_heading, current_lines))
            current_heading = stripped
            current_lines = [line]
            continue
        current_lines.append(line)
    if current_heading is None:
        if current_lines:
            prelude.extend(current_lines)
    else:
        sections.append((current_heading, current_lines))

    required_heading_by_key = {
        _canonical_h2_key(item): item for item in _REQUIRED_DEEP_MARKDOWN_HEADINGS
    }
    singleton_keys = set(required_heading_by_key.keys())
    output: list[str] = [line for line in prelude if line.strip()]
    block_plan: list[tuple[str, str | list[str]]] = []
    singleton_best_blocks: dict[str, list[str]] = {}
    previous_key: str | None = None

    for heading, block_lines in sections:
        key = _resolve_required_deep_heading_key(heading)
        if not key:
            continue
        if key in singleton_keys:
            current_best = singleton_best_blocks.get(key)
            current_len = sum(len(item.strip()) for item in block_lines[1:] if item.strip())
            if current_best is None:
                singleton_best_blocks[key] = block_lines
                block_plan.append(("singleton", key))
            else:
                previous_len = sum(len(item.strip()) for item in current_best[1:] if item.strip())
                if current_len > previous_len:
                    singleton_best_blocks[key] = block_lines
            previous_key = key
            continue
        if key == previous_key:
            continue
        block_plan.append(("block", block_lines))
        previous_key = key

    emitted_singleton: set[str] = set()
    for block_type, payload in block_plan:
        if block_type == "singleton":
            singleton_key = str(payload)
            if singleton_key in emitted_singleton:
                continue
            block_lines = singleton_best_blocks.get(singleton_key)
            if block_lines:
                canonical_heading = required_heading_by_key.get(singleton_key)
                normalized_block = list(block_lines)
                if canonical_heading:
                    normalized_block[0] = canonical_heading
                output.extend(normalized_block)
                emitted_singleton.add(singleton_key)
            continue
        if isinstance(payload, list):
            output.extend(payload)
    return "\n".join(output).strip() + "\n"


def _sanitize_deep_beta_markdown_output(markdown_text: str) -> str:
    return _dedupe_duplicate_h2_headings(_strip_html_from_mermaid_blocks(markdown_text))


def _markdown_word_count(text: str) -> int:
    return len(re.findall(r"\S+", str(text or "").strip()))


def _resolve_deep_beta_target_words() -> int:
    min_words = max(int(settings.deep_beta_report_min_words), 900)
    page_target = max(int(settings.deep_beta_report_target_pages), 1)
    words_per_page = max(int(settings.deep_beta_report_words_per_page), 250)
    return max(min_words, page_target * words_per_page)


def _safe_generate_with_token_budget(
    client: Any,
    *,
    prompt: str,
    system_prompt: str,
    max_tokens: int,
) -> Any:
    try:
        return client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
    except TypeError:
        return client.generate(prompt=prompt, system_prompt=system_prompt)


def _ensure_deep_beta_report_artifacts(
    *,
    markdown_text: str,
    deep_pass_summaries: list[dict[str, Any]],
    evidence_verification: dict[str, Any] | None,
    verification_summary: dict[str, Any] | None,
) -> str:
    output = _sanitize_deep_beta_markdown_output(markdown_text)
    appendix_sections: list[str] = []

    if "| --- |" not in output:
        rows = [
            "| Pass | Subquery | Retrieved | Duration (ms) |",
            "| --- | --- | ---: | ---: |",
        ]
        for item in deep_pass_summaries[:10]:
            if not isinstance(item, dict):
                continue
            rows.append(
                f"| {_safe_int(item.get('pass_index'), 0)} | "
                f"{_escape_markdown_cell(item.get('subquery') or '-')} | "
                f"{_safe_int(item.get('retrieved_count'), 0)} | "
                f"{round(_safe_float(item.get('duration_ms'), 0.0), 2)} |"
            )
        appendix_sections.append("### Bảng bổ sung Deep Beta\n" + "\n".join(rows))

    if "```mermaid" not in output:
        appendix_sections.append(
            "### Decision Flow (Deep Beta)\n"
            "```mermaid\n"
            "flowchart TD\n"
            "    A[Scope Lock] --> B[Multi-pass Retrieval]\n"
            "    B --> C[Parallel Reasoning Nodes]\n"
            "    C --> D[Evidence Verification]\n"
            "    D --> E{High-risk / Contradiction?}\n"
            "    E -- Yes --> F[Warn + Escalate clinician]\n"
            "    E -- No --> G[Long-form synthesis + quality gate]\n"
            "```\n"
        )

    if "```chart-spec" not in output:
        evidence = evidence_verification if isinstance(evidence_verification, dict) else {}
        matrix = verification_summary if isinstance(verification_summary, dict) else {}
        appendix_sections.append(
            "### Chart Spec (Deep Beta Signals)\n"
            "```chart-spec\n"
            "type: bar\n"
            "title: Deep Beta Evidence Signals\n"
            "x: [supported_claims, unsupported_claims, contradicted_claims, support_ratio]\n"
            "y:\n"
            f"  - {len(evidence.get('supported_claims', [])) if isinstance(evidence.get('supported_claims'), list) else 0}\n"
            f"  - {len(evidence.get('unsupported_claims', [])) if isinstance(evidence.get('unsupported_claims'), list) else 0}\n"
            f"  - {len(evidence.get('contradicted_claims', [])) if isinstance(evidence.get('contradicted_claims'), list) else 0}\n"
            f"  - {round(_safe_float(matrix.get('support_ratio'), 0.0), 3)}\n"
            "```\n"
        )

    if appendix_sections:
        output = f"{output.rstrip()}\n\n" + "\n\n".join(appendix_sections).rstrip() + "\n"
    return output


def _synthesize_deep_beta_long_report(
    *,
    topic: str,
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    reasoning_nodes: list[dict[str, Any]],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_verification: dict[str, Any] | None = None,
    llm_runtime: dict[str, Any] | None = None,
) -> str:
    if not settings.deep_beta_report_llm_enabled:
        return answer_markdown
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return answer_markdown

    compact_citations = [
        {
            "source_id": item.source_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "relevance": item.relevance,
        }
        for item in citations[:18]
    ]
    verification_summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    contradiction_summary = (
        verification_matrix_payload.get("contradiction_summary")
        if isinstance(verification_matrix_payload.get("contradiction_summary"), dict)
        else {}
    )
    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "duration_ms": item.get("duration_ms"),
        }
        for item in deep_pass_summaries[:14]
        if isinstance(item, dict)
    ]

    target_words = _resolve_deep_beta_target_words()
    report_timeout_seconds = max(
        float(settings.deep_beta_report_timeout_seconds),
        float(settings.deep_beta_reasoning_llm_timeout_seconds),
        30.0,
    )
    report_max_tokens = max(int(settings.deep_beta_report_max_tokens), 1024)
    prompt = (
        "Rewrite the baseline answer into a long-form clinical research report in Vietnamese.\n"
        "Output valid GitHub-Flavored Markdown only, no HTML.\n"
        "Must include these sections in this exact order:\n"
        "## Kết luận nhanh\n"
        "## Tóm tắt điều hành\n"
        "## Câu hỏi nghiên cứu (PICO)\n"
        "## Phương pháp truy xuất & tiêu chí chọn lọc\n"
        "## Hồ sơ bằng chứng & chất lượng nguồn\n"
        "## Tổng hợp phát hiện chính\n"
        "## Phản biện bằng chứng đối nghịch\n"
        "## Ứng dụng lâm sàng theo nhóm bệnh nhân\n"
        "## Ma trận quyết định an toàn\n"
        "## Kế hoạch theo dõi sau tư vấn\n"
        "## Giới hạn, sai số và rủi ro pháp lý\n"
        "## Nguồn tham chiếu\n"
        "Requirements:\n"
        "- length >= "
        f"{target_words} words\n"
        "- write as a long-form clinical report with high depth (target: ~5-10 pages)\n"
        "- each major section must contain concrete bullet points and paragraph analysis (not placeholder text)\n"
        "- explicitly discuss uncertainty, contradictory evidence, and subgroup caveats\n"
        "- include explicit methods narrative (search strategy, inclusion/exclusion, evidence hierarchy)\n"
        "- include an 'if-then' decision flow in mermaid format\n"
        "- include at least one markdown table in 'Hồ sơ bằng chứng & chất lượng nguồn'\n"
        "- include one mermaid flowchart for decision pathway\n"
        "- mermaid block must not contain HTML tags like <br>, <p>, <div>, <span>\n"
        "- include one fenced code block with language 'chart-spec' summarizing numeric signals\n"
        "- citations must use source_id style [source-id]\n"
        "- do not prescribe dosage, do not diagnose\n\n"
        f"topic={topic}\n"
        f"baseline_answer={answer_markdown}\n"
        f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
        f"verification_summary={json.dumps(verification_summary, ensure_ascii=False)}\n"
        f"contradiction_summary={json.dumps(contradiction_summary, ensure_ascii=False)}\n"
        f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(reasoning_nodes, ensure_ascii=False)}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
    )
    system_prompt = (
        "You are CLARA Deep Beta medical report synthesizer. "
        "Be evidence-grounded, safety-first, and specific. "
        "Use a formal medical research style suitable for clinical briefing."
    )
    try:
        client = _build_reasoning_client(
            timeout_seconds=report_timeout_seconds,
            llm_runtime=llm_runtime,
        )
        if client is None:
            return answer_markdown
        response = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=report_max_tokens,
        )
        content = _sanitize_deep_beta_markdown_output(str(response.content or "").strip())
        if not content:
            return answer_markdown

        expansion_rounds = max(int(settings.deep_beta_report_expansion_rounds), 0)
        for round_idx in range(expansion_rounds):
            current_words = _markdown_word_count(content)
            if current_words >= target_words:
                break

            missing_words = max(target_words - current_words, 0)
            continuation_prompt = (
                "Expand the following Vietnamese medical report by APPENDING new content only.\n"
                "Do NOT rewrite previous sections.\n"
                "Do NOT duplicate any existing H2 section title.\n"
                "Add deeper analysis with practical clinical caveats, subgroup handling, and uncertainty.\n"
                f"Need at least ~{missing_words} additional words.\n"
                "Append supplementary sections using H3/H4 headings and additional tables where useful.\n"
                "Return Markdown only.\n\n"
                f"topic={topic}\n"
                f"existing_report={content}\n"
                f"reasoning_nodes={json.dumps(reasoning_nodes, ensure_ascii=False)}\n"
                f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
                f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
                f"verification_summary={json.dumps(verification_summary, ensure_ascii=False)}\n"
            )
            continuation_response = client.generate(
                prompt=continuation_prompt,
                system_prompt=system_prompt,
                max_tokens=report_max_tokens,
            )
            continuation = _sanitize_deep_beta_markdown_output(
                str(continuation_response.content or "").strip()
            )
            if not continuation or continuation in content:
                break
            content = f"{content.rstrip()}\n\n{continuation.strip()}"

        if _markdown_word_count(content) < target_words:
            pass_rows = [
                "| Pass | Subquery | Retrieved | Duration (ms) |",
                "| --- | --- | ---: | ---: |",
            ]
            for item in compact_passes[:16]:
                pass_rows.append(
                    f"| {item.get('pass_index') or '-'} | "
                    f"{_escape_markdown_cell(item.get('subquery') or '-')} | "
                    f"{_safe_int(item.get('retrieved_count'), 0)} | "
                    f"{round(_safe_float(item.get('duration_ms'), 0.0), 2)} |"
                )

            node_rows = [
                "| Reasoning Node | Status | Confidence | Key Insight | Actions |",
                "| --- | --- | ---: | --- | --- |",
            ]
            for node in reasoning_nodes[:16]:
                insights = node.get("insights")
                actions = node.get("actions")
                top_insight = (
                    _compact_snippet(insights[0], max_len=150)
                    if isinstance(insights, list) and insights
                    else "-"
                )
                top_action = (
                    _compact_snippet(actions[0], max_len=120)
                    if isinstance(actions, list) and actions
                    else "-"
                )
                node_rows.append(
                    f"| {_escape_markdown_cell(node.get('node') or '-')} | "
                    f"{_escape_markdown_cell(node.get('status') or '-')} | "
                    f"{_normalize_router_confidence(node.get('confidence')):.2f} | "
                    f"{_escape_markdown_cell(top_insight)} | "
                    f"{_escape_markdown_cell(top_action)} |"
                )

            fallback_appendix = (
                "\n\n## Phụ lục kỹ thuật Deep Beta (mở rộng)\n"
                "### Nhật ký multi-pass retrieval\n"
                + "\n".join(pass_rows)
                + "\n\n### Ma trận reasoning nodes\n"
                + "\n".join(node_rows)
                + "\n\n### Ghi chú phương pháp\n"
                "- Báo cáo này được mở rộng tự động để đạt độ bao phủ bằng chứng và diễn giải lâm sàng sâu hơn.\n"
                "- Các nội dung chưa đủ bằng chứng được giữ trạng thái cảnh báo và không chuyển thành khuyến nghị điều trị.\n"
            )
            content = f"{content.rstrip()}{fallback_appendix}"

        return _ensure_deep_beta_report_artifacts(
            markdown_text=content,
            deep_pass_summaries=deep_pass_summaries,
            evidence_verification=evidence_verification,
            verification_summary=verification_summary,
        )
    except Exception:
        return _ensure_deep_beta_report_artifacts(
            markdown_text=answer_markdown,
            deep_pass_summaries=deep_pass_summaries,
            evidence_verification=evidence_verification,
            verification_summary=verification_summary,
        )


def _refine_query_plan_with_llm(
    *,
    topic: str,
    research_mode: str,
    route_role: str,
    route_intent: str,
    base_query_plan: dict[str, Any],
    keywords: list[str],
    llm_runtime: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return base_query_plan, {
            "attempted": False,
            "status": "degraded",
            "reason": "api_key_missing",
            "model_used": "unconfigured",
        }

    system_prompt = (
        "You are a clinical evidence query planner. Return STRICT JSON only. "
        "No markdown, no explanations, no extra keys."
    )
    prompt = (
        "Refine this retrieval query plan for high-recall clinical research.\n"
        "Output EXACT JSON schema:\n"
        "{\n"
        '  "canonical_query": "string",\n'
        '  "language_hint": "vi|en|mixed",\n'
        '  "keywords": ["..."],\n'
        '  "source_queries": {\n'
        '    "internal": ["..."],\n'
        '    "scientific": ["..."],\n'
        '    "web": ["..."]\n'
        "  },\n"
        '  "provider_queries": {\n'
        '    "scientific": {"pubmed": "...", "europepmc": "...", "openfda": "..."},\n'
        '    "web": {"searxng": "..."}\n'
        "  },\n"
        '  "decomposition": {\n'
        '    "deep_pass_queries": ["..."],\n'
        '    "deep_beta_pass_queries": ["..."]\n'
        "  }\n"
        "}\n"
        "Constraints:\n"
        "- keywords length <= 12\n"
        "- keep clinical safety terms when query is medication-related\n"
        "- return at least one query per source and decomposition list\n"
        "- provider_queries is optional; if provided, map each provider to concise query\n"
        "- return valid JSON only\n\n"
        f"topic={topic}\n"
        f"research_mode={research_mode}\n"
        f"route_role={route_role}\n"
        f"route_intent={route_intent}\n"
        f"base_keywords={keywords[:12]}\n"
        f"base_plan={json.dumps(base_query_plan, ensure_ascii=False)}\n"
    )

    try:
        client = _build_query_planner_client(llm_runtime=llm_runtime)
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        llm_response = client.generate(prompt=prompt, system_prompt=system_prompt)
        cleaned = _strip_markdown_fence(llm_response.content)
        parsed_payload = json.loads(cleaned)
        sanitized = _sanitize_llm_query_plan_payload(
            parsed_payload,
            base_query_plan=base_query_plan,
            research_mode=research_mode,
        )
        return sanitized, {
            "attempted": True,
            "status": "completed",
            "reason": "ok",
            "model_used": llm_response.model,
        }
    except Exception as exc:  # pragma: no cover - network/provider defensive path
        return base_query_plan, {
            "attempted": True,
            "status": "degraded",
            "reason": _safe_planner_error_code(exc),
            "error": f"{exc.__class__.__name__}: {exc}",
            "model_used": "planner-fallback-v1",
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
    retrieval_stack_mode: str = "auto",
) -> dict[str, Any]:
    normalized_topic = topic.lower()
    _, _, language_hint = _detect_language_hint(topic)
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
    requested_stack_mode = (
        "full" if str(retrieval_stack_mode).strip().lower() == "full" else "auto"
    )
    stack_mode = requested_stack_mode
    if research_mode == "fast" and requested_stack_mode == "full":
        stack_mode = "auto"
        reason_codes.append("stack_mode_full_downgraded_for_fast_mode")
    reason_codes.append(f"retrieval_stack_mode_{stack_mode}")

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
        target_pass_count = 13 if is_ddi_query else (12 if evidence_query else 11)
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

    graphrag_enabled_override: bool | None = None
    if stack_mode == "full":
        scientific_enabled = True
        web_enabled = True
        graphrag_enabled_override = True
        reason_codes.append("stack_mode_full_force_scientific")
        reason_codes.append("stack_mode_full_force_web")
        reason_codes.append("stack_mode_full_force_graphrag")

    pass_cap = _DEEP_BETA_PASS_CAP if deep_beta_mode else _DEFAULT_DEEP_PASS_CAP
    retrieval_budget = {
        "mode": research_mode,
        "retrieval_stack_mode": stack_mode,
        "target_pass_count": max(1, min(pass_cap, target_pass_count)),
        "pass_cap": pass_cap,
        "internal_top_k": max(1, min(12, internal_top_k)),
        "hybrid_top_k": max(1, min(12, hybrid_top_k)),
        "estimated_max_documents": max(1, min(12, hybrid_top_k))
        * max(1, min(pass_cap, target_pass_count)),
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
        "is_ddi_query": is_ddi_query,
        "is_ddi_critical_query": is_ddi_critical_query,
        "language_hint": language_hint,
        "role": route_role,
        "source_mode": source_mode or "default",
        "low_context_threshold": 0.12 if has_uploaded else 0.15,
        "scientific_retrieval_enabled": scientific_enabled,
        "web_retrieval_enabled": web_enabled,
        "file_retrieval_enabled": True,
        "retrieval_stack_mode": stack_mode,
        "graphrag_enabled_override": graphrag_enabled_override,
        "research_mode": research_mode,
        "deep_pass_count": max(1, min(pass_cap, target_pass_count)),
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
        raw_status = str(row.get("support_status") or "insufficient").strip().lower()
        support_status = "insufficient" if raw_status == "unsupported" else raw_status
        compact_rows.append(
            {
                "claim": _first_nonempty_text(row.get("claim")),
                "claim_type": _first_nonempty_text(row.get("claim_type")) or "general",
                "support_status": support_status or "insufficient",
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
                "rationale": _compact_snippet(row.get("rationale"), max_len=max_snippet_len),
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
    insufficient_count = 0
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
            insufficient_count += 1

    inferred_total = max(_safe_int(total_claims, 0), len(rows))
    inferred_supported = _safe_int(supported_claims, 0)
    if inferred_supported <= 0 and supported_count > 0:
        inferred_supported = supported_count
    inferred_supported = max(0, min(inferred_supported, inferred_total))
    support_ratio = inferred_supported / max(inferred_total, 1) if inferred_total > 0 else 0.0
    return {
        "version": "claim-v2-nli",
        "total_claims": inferred_total,
        "supported_claims": inferred_supported,
        "insufficient_claims": insufficient_count,
        "unsupported_claims": insufficient_count,
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
        "version": "claim-v2-nli",
        "has_contradiction": bool(contradicted_rows),
        "contradiction_count": len(contradicted_rows),
        "claims": [str(item.get("claim") or "") for item in contradicted_rows[:5]],
        "details": [
            {
                "claim": item.get("claim", ""),
                "claim_type": item.get("claim_type", "general"),
                "evidence_ref": item.get("evidence_ref"),
                "evidence_snippet": item.get("evidence_snippet", ""),
                "overlap_score": item.get("overlap_score", 0.0),
                "confidence": item.get("confidence", 0.0),
                "rationale": item.get("rationale", ""),
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


_SAFETY_CRITICAL_CLAIM_TYPES = {"dosage", "contraindication"}
_SAFETY_CRITICAL_RISK_STATUSES = {"insufficient", "unsupported", "contradicted"}


def _evaluate_safety_critical_override(
    *,
    rows: list[dict[str, Any]],
    nli_enabled: bool,
) -> dict[str, Any]:
    if not nli_enabled:
        return {"applied": False, "reason": "nli_disabled"}

    critical_rows: list[dict[str, Any]] = []
    contradicted_rows: list[dict[str, Any]] = []
    insufficient_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_type = str(row.get("claim_type") or "").strip().lower()
        support_status = str(row.get("support_status") or "").strip().lower()
        if claim_type not in _SAFETY_CRITICAL_CLAIM_TYPES:
            continue
        if support_status not in _SAFETY_CRITICAL_RISK_STATUSES:
            continue
        critical_rows.append(row)
        if support_status == "contradicted":
            contradicted_rows.append(row)
        else:
            insufficient_rows.append(row)

    if not critical_rows:
        return {"applied": False, "reason": "no_safety_critical_risk"}

    top_claims = [str(item.get("claim") or "") for item in critical_rows[:5]]
    base_payload = {
        "applied": True,
        "affected_claim_count": len(critical_rows),
        "claims": top_claims,
    }
    if contradicted_rows:
        return {
            **base_payload,
            "policy_action": "block",
            "verification_state": "warning",
            "severity_override": "high",
            "reason": "safety_critical_contradicted",
            "note": "Safety override: claim safety-critical bị contradicted, policy chuyển block.",
            "status": "blocked",
        }
    return {
        **base_payload,
        "policy_action": "warn",
        "verification_state": "warning",
        "severity_override": "high",
        "reason": "safety_critical_insufficient",
        "note": "Safety override: claim safety-critical ở trạng thái insufficient, policy chuyển warn.",
        "status": "warning",
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
        "stack_mode_requested": str(retrieval_debug.get("stack_mode_requested") or "auto"),
        "stack_mode_effective": str(retrieval_debug.get("stack_mode_effective") or "auto"),
        "stack_mode_reason_codes": (
            [str(item).strip() for item in retrieval_debug.get("stack_mode_reason_codes", []) if str(item).strip()]
            if isinstance(retrieval_debug.get("stack_mode_reason_codes"), list)
            else []
        ),
        "stack_coverage": retrieval_debug.get("stack_coverage")
        if isinstance(retrieval_debug.get("stack_coverage"), dict)
        else {},
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

    for item in events:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        source_count_raw = item.get("source_count", 0)
        try:
            source_count = int(source_count_raw)
        except (TypeError, ValueError):
            source_count = 0
        parsed_timestamp = _parse_event_timestamp(item.get("timestamp"))
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


def _build_stage_span_summaries(
    flow_events: list[dict[str, Any]],
    *,
    stage_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not stage_entries:
        return []

    events_by_stage: dict[str, list[dict[str, Any]]] = {}
    retrieval_like_events: list[dict[str, Any]] = []
    for event in flow_events:
        if not isinstance(event, dict):
            continue
        stage = str(event.get("stage") or "").strip()
        if not stage:
            continue
        events_by_stage.setdefault(stage, []).append(event)
        stage_lower = stage.lower()
        component = str(event.get("component") or "").strip().lower()
        if (
            component in {"retrieval", "deep_retrieval", "deep_beta_retrieval"}
            or "retrieval" in stage_lower
            or "search" in stage_lower
            or "index" in stage_lower
        ):
            retrieval_like_events.append(event)

    status_start_markers = {"started", "start", "running", "in_progress"}
    stage_aliases: dict[str, list[str]] = {
        "plan": ["planner"],
        "hybrid_retrieval": [],
    }

    spans: list[dict[str, Any]] = []
    for stage_entry in stage_entries:
        if not isinstance(stage_entry, dict):
            continue
        stage_name = str(stage_entry.get("name") or "").strip()
        if not stage_name:
            continue

        stage_events: list[dict[str, Any]] = []
        if stage_name == "hybrid_retrieval":
            stage_events = retrieval_like_events
        else:
            candidates = stage_aliases.get(stage_name, [stage_name])
            for candidate in candidates:
                stage_events.extend(events_by_stage.get(candidate, []))

        start_at: str | None = None
        end_at: str | None = None
        duration_ms: float | None = None
        event_count = len(stage_events)
        final_status = str(stage_entry.get("status") or "unknown")
        source_count = 0
        first_event_sequence: int | None = None
        last_event_sequence: int | None = None

        if stage_events:
            start_event = next(
                (
                    item
                    for item in stage_events
                    if str(item.get("status") or "").strip().lower() in status_start_markers
                ),
                stage_events[0],
            )
            end_event = next(
                (
                    item
                    for item in reversed(stage_events)
                    if str(item.get("status") or "").strip().lower() not in status_start_markers
                ),
                stage_events[-1],
            )
            start_at_raw = str(start_event.get("timestamp") or "").strip()
            end_at_raw = str(end_event.get("timestamp") or "").strip()
            start_at = start_at_raw or None
            end_at = end_at_raw or None
            start_ts = _parse_event_timestamp(start_at)
            end_ts = _parse_event_timestamp(end_at)
            if start_ts and end_ts:
                duration_ms = round(max((end_ts - start_ts).total_seconds() * 1000.0, 0.0), 3)
            final_status = str(end_event.get("status") or final_status)
            source_count = max(_safe_int(end_event.get("source_count"), 0), 0)
            first_event_sequence = _safe_int(start_event.get("event_sequence"), 0) or None
            last_event_sequence = _safe_int(end_event.get("event_sequence"), 0) or None

        spans.append(
            {
                "stage": stage_name,
                "status": final_status,
                "start_at": start_at,
                "end_at": end_at,
                "duration_ms": duration_ms,
                "event_count": event_count,
                "source_count": source_count,
                "first_event_sequence": first_event_sequence,
                "last_event_sequence": last_event_sequence,
            }
        )
    return spans


def _build_otel_trace_metadata(
    *,
    trace_id: str,
    run_id: str,
    stage_spans: list[dict[str, Any]],
    flow_events: list[dict[str, Any]],
) -> dict[str, Any]:
    span_rows: list[dict[str, Any]] = []
    for row in stage_spans:
        if not isinstance(row, dict):
            continue
        name = str(row.get("stage") or "").strip()
        if not name:
            continue
        span_rows.append(
            {
                "name": name,
                "status": str(row.get("status") or "unknown"),
                "start_at": row.get("start_at"),
                "end_at": row.get("end_at"),
                "duration_ms": row.get("duration_ms"),
                "event_count": row.get("event_count"),
                "source_count": row.get("source_count"),
            }
        )

    return {
        "trace_id": trace_id,
        "run_id": run_id,
        "service_name": "clara-ml",
        "component": "research_tier2",
        "span_count": len(span_rows),
        "event_count": len(flow_events),
        "spans": span_rows,
    }


def _emit_otel_trace_best_effort(
    *,
    otel_trace_metadata: dict[str, Any],
    flow_events: list[dict[str, Any]],
) -> dict[str, Any]:
    endpoint = str(settings.otel_export_endpoint or "").strip()
    enabled = bool(settings.otel_export_enabled) and bool(endpoint)
    status: dict[str, Any] = {
        "enabled": enabled,
        "endpoint": endpoint if enabled else "",
        "sent": False,
    }
    if not enabled:
        return status

    payload = {
        "service_name": "clara-ml",
        "component": "research_tier2",
        "trace": otel_trace_metadata,
        "event_count": len(flow_events),
        "exported_at": _now_iso(),
    }
    request = urllib.request.Request(
        url=endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request,
            timeout=float(settings.otel_export_timeout_seconds),
        ) as response:
            status["sent"] = True
            status["http_status"] = int(response.getcode())
            return status
    except urllib.error.HTTPError as exc:
        status["http_status"] = int(exc.code)
        status["error"] = f"HTTPError:{exc.code}"
        return status
    except Exception as exc:  # noqa: BLE001
        status["error"] = f"{type(exc).__name__}:{exc}"
        return status


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
        "id": "agentic-deep-research-beta-v2",
        "query": topic,
        "retrieval_budget": retrieval_budget,
        "inspired_patterns": [
            *base.get("inspired_patterns", []),
            "retrieval_budgeting",
            "iterative_gap_fill",
            "reasoning_chain_audit",
            "parallel_reasoning_workers",
            "evidence_quality_auditor",
            "longform_report_synthesis",
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
            {
                "name": "beta_parallel_reasoning",
                "goal": "Chạy nhiều node reasoning LLM song song để kiểm evidence/gap/mâu thuẫn.",
            },
            {
                "name": "beta_evidence_verification",
                "goal": "Hợp nhất evidence-check theo claim và gắn cờ mắt xích chưa đủ bằng chứng.",
            },
            {
                "name": "beta_longform_report",
                "goal": "Tổng hợp báo cáo dài dạng markdown với bảng, mermaid, chart-spec.",
            },
        ],
    }


def _build_deep_beta_reasoning_steps(*, topic: str, subqueries: list[str]) -> list[dict[str, Any]]:
    objectives = {
        "deep_beta_scope": "Lock scope, safety boundaries and exclusions for the beta chain.",
        "deep_beta_hypothesis_map": "Map main/counter hypotheses with expected supporting evidence.",
        "deep_beta_retrieval_budget": "Allocate retrieval budgets and quality thresholds across passes.",
        "deep_beta_multi_pass_retrieval": "Run iterative retrieval passes and close evidence gaps.",
        "deep_beta_evidence_audit": "LLM node: audit evidence coverage, quality, and unresolved dimensions.",
        "deep_beta_claim_graph": "LLM node: derive claim/conflict graph and contradiction hypotheses.",
        "deep_beta_counter_evidence_scan": "LLM node: seek strongest counter-evidence and boundary conditions.",
        "deep_beta_guideline_alignment": "LLM node: compare findings against guideline-level recommendations.",
        "deep_beta_risk_stratification": "LLM node: stratify risk by subgroup and red-flag conditions.",
        "deep_beta_gap_fill": "Run targeted retrieval passes to fill evidence gaps from LLM audit.",
        "deep_beta_evidence_verification": "LLM node: verify claim support/contradiction coverage before synthesis.",
        "deep_beta_chain_synthesis": "Generate long-form synthesis chain from pass-level evidence.",
        "deep_beta_chain_verification": "Validate chain consistency, contradictions, and uncertainty.",
        "deep_beta_report_synthesis": "LLM node: synthesize long-form final report with explicit evidence contract.",
        "deep_beta_quality_gate": "LLM node: final quality gate for groundedness/completeness before response.",
    }
    steps: list[dict[str, Any]] = []
    for index, stage in enumerate(_DEEP_BETA_REASONING_STAGE_ORDER):
        steps.append(
            {
                "stage": stage,
                "status": "pending",
                "objective": objectives.get(stage, stage),
                "subquery": subqueries[index] if index < len(subqueries) else topic,
            }
        )
    return steps

def _resolve_deep_pass_count(
    payload: dict[str, Any],
    default_count: int,
    *,
    cap: int = _DEFAULT_DEEP_PASS_CAP,
) -> int:
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
        return max(1, min(max(cap, 1), parsed))
    return max(1, min(max(cap, 1), int(default_count)))


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


def _escape_markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _evidence_table_markdown(
    citations: list[Citation],
    *,
    max_rows: int = 8,
) -> str:
    headers = "| Nguồn | Tiêu đề | Mức liên quan | URL |"
    separator = "| --- | --- | --- | --- |"
    rows: list[str] = [headers, separator]
    if not citations:
        rows.append("| system_fallback | Chưa có nguồn | Cần truy xuất thêm bằng chứng. | - |")
        return "\n".join(rows)

    for citation in citations[:max_rows]:
        url = _safe_url(citation.url) or "-"
        rows.append(
            "| "
            f"{_escape_markdown_cell(citation.source)} | "
            f"{_escape_markdown_cell(citation.title)} | "
            f"{_escape_markdown_cell(_compact_snippet(citation.relevance, max_len=96))} | "
            f"{_escape_markdown_cell(url)} |"
        )
    return "\n".join(rows)


def _extract_answer_digest_points(answer: str, *, limit: int = 3) -> list[str]:
    cleaned = " ".join(str(answer or "").split()).strip()
    if not cleaned:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", cleaned)
    points: list[str] = []
    for chunk in chunks:
        point = chunk.strip(" -")
        if not point:
            continue
        points.append(_compact_snippet(point, max_len=160))
        if len(points) >= max(1, limit):
            break
    return points


def _build_chart_specs(
    *,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    source_counts: dict[str, int] = {}
    for citation in citations:
        source_name = _first_nonempty_text(citation.source, "unknown")
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
    if not source_counts:
        source_counts["system_fallback"] = 1

    source_values = [{"source": key, "count": value} for key, value in source_counts.items()]
    chart_specs: list[dict[str, Any]] = [
        {
            "id": "source_distribution",
            "type": "chart-spec",
            "engine": "vega-lite",
            "title": "Phân bổ nguồn bằng chứng",
            "config": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Distribution of evidence citations by source.",
                "data": {"values": source_values},
                "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                "encoding": {
                    "x": {"field": "source", "type": "nominal", "sort": "-y", "title": "Nguồn"},
                    "y": {"field": "count", "type": "quantitative", "title": "Số bằng chứng"},
                    "tooltip": [
                        {"field": "source", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        }
    ]

    summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    support_values = [
        {
            "status": "supported",
            "count": _safe_int(summary.get("supported_claims"), 0),
        },
        {
            "status": "unsupported",
            "count": _safe_int(summary.get("unsupported_claims"), 0),
        },
        {
            "status": "contradicted",
            "count": _safe_int(summary.get("contradicted_claims"), 0),
        },
    ]
    chart_specs.append(
        {
            "id": "claim_support_matrix",
            "type": "chart-spec",
            "engine": "vega-lite",
            "title": "Ma trận mức độ hậu thuẫn claim",
            "config": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Claim support profile from verification matrix.",
                "data": {"values": support_values},
                "mark": "arc",
                "encoding": {
                    "theta": {"field": "count", "type": "quantitative"},
                    "color": {"field": "status", "type": "nominal"},
                    "tooltip": [
                        {"field": "status", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        }
    )
    return chart_specs


def _build_visual_assets(citations: list[Citation]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for index, citation in enumerate(citations[:12], start=1):
        url = _safe_url(citation.url)
        if not url:
            continue
        assets.append(
            {
                "asset_id": f"citation-asset-{index}",
                "type": "reference_url",
                "source_id": citation.source_id,
                "source": citation.source,
                "title": citation.title,
                "url": url,
                "label": f"Nguồn {index}",
            }
        )
    return assets


def _build_reasoning_digest(
    *,
    topic: str,
    research_mode: str,
    planner_hints: dict[str, Any],
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    flow_events: list[dict[str, Any]],
    deep_pass_count: int,
    parallel_reasoning_nodes: list[dict[str, Any]] | None = None,
    evidence_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    contradiction_summary = (
        verification_matrix_payload.get("contradiction_summary")
        if isinstance(verification_matrix_payload.get("contradiction_summary"), dict)
        else {}
    )
    sources = [citation.source for citation in citations if citation.source]
    top_sources: list[str] = []
    for source in sources:
        if source in top_sources:
            continue
        top_sources.append(source)
        if len(top_sources) >= 4:
            break

    llm_status = "disabled"
    reason_codes = (
        planner_hints.get("reason_codes") if isinstance(planner_hints.get("reason_codes"), list) else []
    )
    if "llm_query_planner_enabled" in reason_codes:
        llm_status = "enabled"
    elif "llm_query_planner_fallback" in reason_codes:
        llm_status = "fallback"

    node_rows = parallel_reasoning_nodes if isinstance(parallel_reasoning_nodes, list) else []
    completed_nodes = sum(
        1
        for item in node_rows
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "completed"
    )
    evidence_verification_payload = (
        evidence_verification if isinstance(evidence_verification, dict) else {}
    )

    return {
        "topic": topic,
        "research_mode": research_mode,
        "llm_query_planner_status": llm_status,
        "highlights": _extract_answer_digest_points(answer_markdown, limit=3),
        "evidence": {
            "citation_count": len(citations),
            "top_sources": top_sources,
            "deep_pass_count": max(1, int(deep_pass_count)),
            "parallel_reasoning_nodes": len(node_rows),
            "parallel_reasoning_nodes_completed": completed_nodes,
            "evidence_verification_confidence": _safe_float(
                evidence_verification_payload.get("verification_confidence"),
                0.0,
            ),
            "evidence_verification_gaps": (
                len(evidence_verification_payload.get("evidence_gaps", []))
                if isinstance(evidence_verification_payload.get("evidence_gaps"), list)
                else 0
            ),
        },
        "verification": {
            "support_ratio": _safe_float(summary.get("support_ratio"), 0.0),
            "supported_claims": _safe_int(summary.get("supported_claims"), 0),
            "total_claims": _safe_int(summary.get("total_claims"), 0),
            "contradiction_count": _safe_int(contradiction_summary.get("contradiction_count"), 0),
        },
        "event_count": len(flow_events),
    }


def _ensure_markdown_structure(
    topic: str,
    answer: str,
    citations: list[Citation],
    *,
    research_mode: str,
) -> str:
    def _estimate_medical_risk_band(text: str) -> tuple[str, str, str]:
        normalized = _ascii_fold(text)
        high_terms = (
            "warfarin",
            "xuất huyết",
            "bleeding",
            "shock",
            "sốc",
            "phản vệ",
            "anaphylaxis",
            "khó thở",
            "đau ngực",
            "ngất",
        )
        moderate_terms = (
            "ddi",
            "tương tác thuốc",
            "ibuprofen",
            "aspirin",
            "kháng viêm",
            "nsaid",
            "suy thận",
            "suy gan",
            "đái tháo đường",
            "tim mạch",
        )
        if any(term in normalized for term in high_terms):
            return ("Cao", "Đỏ", "Cần xử trí sớm và đánh giá y tế trực tiếp.")
        if any(term in normalized for term in moderate_terms):
            return ("Trung bình", "Cam", "Cần theo dõi sát và xác minh với bác sĩ/dược sĩ.")
        return ("Thấp", "Vàng", "Theo dõi định kỳ, tiếp tục kiểm chứng nguồn chính thống.")

    def _build_decision_matrix_markdown(*, risk_level: str, risk_signal: str) -> str:
        return (
            "| Mục đánh giá | Mức hiện tại | Hành động khuyến nghị |\n"
            "| --- | --- | --- |\n"
            f"| Mức rủi ro tổng quát | {risk_level} ({risk_signal}) | Không tự điều chỉnh thuốc, xác minh với bác sĩ/dược sĩ. |\n"
            "| Độ tin cậy bằng chứng | Trung bình - Cao (tùy nguồn) | Ưu tiên guideline, nhãn thuốc chính thức, và dữ liệu DDI có trích dẫn. |\n"
            "| Quyết định tại nhà | Có điều kiện | Chỉ tiếp tục dùng thuốc khi không có dấu hiệu cảnh báo đỏ. |\n"
            "| Cần chuyển tuyến ngay | Khi có red flag | Đau ngực, khó thở, ngất, xuất huyết, lú lẫn, phản vệ. |\n"
        )

    cleaned = str(answer or "").strip()
    if not cleaned:
        cleaned = "Chưa có nội dung trả lời chuyên sâu."

    required_headings = (
        _REQUIRED_DEEP_MARKDOWN_HEADINGS
        if research_mode in {"deep", "deep_beta"}
        else _REQUIRED_MARKDOWN_HEADINGS
    )
    if all(_has_markdown_heading(cleaned, heading) for heading in required_headings):
        return cleaned

    analysis_block = cleaned
    if "\n" not in analysis_block:
        analysis_block = f"- {analysis_block}"

    topic_snippet = _compact_snippet(topic, max_len=210)
    risk_level, risk_signal, risk_note = _estimate_medical_risk_band(f"{topic} {cleaned}")
    citations_block = "\n".join(_citation_markdown_lines(citations))
    if research_mode in {"deep", "deep_beta"}:
        evidence_table = _evidence_table_markdown(citations, max_rows=10)
        executive_summary = _compact_snippet(cleaned, max_len=360)
        matrix_table = _build_decision_matrix_markdown(
            risk_level=risk_level,
            risk_signal=risk_signal,
        )
        return (
            "## Kết luận nhanh\n"
            f"{_compact_snippet(cleaned, max_len=320)}\n\n"
            "## Tóm tắt điều hành\n"
            f"- Câu hỏi chính: {topic_snippet}\n"
            f"- Phạm vi nghiên cứu: {_compact_snippet(cleaned, max_len=180)}\n"
            f"- Mức độ bằng chứng hiện có: {len(citations)} nguồn tham chiếu.\n"
            f"- Tín hiệu rủi ro lâm sàng: {risk_level} ({risk_signal}). {risk_note}\n"
            f"- Điểm chính: {executive_summary}\n\n"
            "## Câu hỏi nghiên cứu (PICO)\n"
            f"- **Population**: Nhóm bệnh nhân liên quan đến chủ đề: {_compact_snippet(topic_snippet, max_len=120)}.\n"
            "- **Intervention/Exposure**: Thuốc/phác đồ/yếu tố can thiệp đang được quan tâm.\n"
            "- **Comparison**: So sánh với phương án chuẩn hoặc nhóm đối chứng nếu có.\n"
            "- **Outcomes**: Hiệu quả lâm sàng, biến cố bất lợi, và chỉ số an toàn quan trọng.\n\n"
            "## Phương pháp truy xuất & tiêu chí chọn lọc\n"
            "- Chiến lược truy xuất đa nguồn (guideline, y văn, nguồn chính thống, dữ liệu nội bộ).\n"
            "- Ưu tiên bằng chứng bậc cao (systematic review/meta-analysis/RCT), sau đó cohort/case-series.\n"
            "- Loại trừ nguồn không rõ xuất xứ hoặc không truy cập được metadata tối thiểu.\n\n"
            "## Hồ sơ bằng chứng & chất lượng nguồn\n"
            f"{evidence_table}\n\n"
            "## Tổng hợp phát hiện chính\n"
            f"{analysis_block}\n\n"
            "## Phản biện bằng chứng đối nghịch\n"
            "- Nêu rõ các điểm bất đồng giữa guideline/nghiên cứu quan sát và thử nghiệm có đối chứng.\n"
            "- Đánh giá nguy cơ sai lệch (selection bias, confounding, publication bias) trước khi kết luận.\n"
            "- Đánh dấu claim chưa đủ hỗ trợ để tránh over-claim.\n\n"
            "## Ứng dụng lâm sàng theo nhóm bệnh nhân\n"
            "- Người cao tuổi/đa trị liệu: ưu tiên kiểm tra DDI và độc tính tích lũy.\n"
            "- Bệnh nền gan-thận/tim mạch/đái tháo đường: cần hiệu chỉnh theo nguy cơ cá thể.\n"
            "- Khi xuất hiện dấu hiệu nặng hoặc bất thường mới, chuyển khám trực tiếp thay vì tự xử lý tại nhà.\n\n"
            "## Ma trận quyết định an toàn\n"
            f"{matrix_table}\n\n"
            "## Kế hoạch theo dõi sau tư vấn\n"
            "- Theo dõi triệu chứng trong 24-72 giờ sau khi áp dụng khuyến nghị an toàn.\n"
            "- Ghi lại thuốc đang dùng, thời điểm dùng, và phản ứng bất thường để đối chiếu với bác sĩ.\n"
            "- Nếu có đa thuốc hoặc bệnh nền phức tạp, ưu tiên lịch tư vấn sớm với cơ sở y tế.\n\n"
            "## Giới hạn, sai số và rủi ro pháp lý\n"
            "- Hệ thống chỉ cung cấp thông tin tham khảo dựa trên bằng chứng truy xuất được.\n"
            "- Có thể tồn tại sai lệch do nguồn dữ liệu chưa đầy đủ hoặc khác biệt theo bối cảnh lâm sàng.\n"
            "- Quyết định điều trị cuối cùng phải do bác sĩ/dược sĩ có thẩm quyền xác nhận.\n\n"
            "## Nguồn tham chiếu\n"
            f"{citations_block}"
        )

    return (
        "## Kết luận nhanh\n"
        f"{cleaned}\n\n"
        "## Phân tích chi tiết\n"
        f"{analysis_block}\n\n"
        "## Khuyến nghị an toàn\n"
        "- Không tự ý kê đơn hoặc điều chỉnh liều nếu chưa có tư vấn chuyên môn.\n"
        "- Ưu tiên xác minh lại thông tin với bác sĩ/dược sĩ khi có bệnh nền hoặc đa thuốc.\n\n"
        "## Theo dõi & cảnh báo đỏ\n"
        "- Theo dõi thay đổi triệu chứng trong 24-48 giờ và ghi chú phản ứng bất thường.\n"
        "- Cần đi khám/cấp cứu ngay khi có đau ngực, khó thở, ngất, xuất huyết hoặc phản vệ.\n\n"
        "## Nguồn tham chiếu\n"
        f"{citations_block}"
    )


def _build_deep_beta_reasoning_client(
    *,
    timeout_cap_seconds: float = 25.0,
    llm_runtime: dict[str, Any] | None = None,
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    timeout_seconds = max(2.0, min(float(settings.deepseek_timeout_seconds), timeout_cap_seconds))
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        retries_per_base=0,
        retry_backoff_seconds=0.0,
    )


def _extract_reasoning_context_rows(
    rows: list[dict[str, Any]],
    *,
    max_items: int = 18,
    max_text_len: int = 260,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": _first_nonempty_text(item.get("id"), item.get("source"), f"ctx-{len(compact)+1}"),
                "source": _first_nonempty_text(item.get("source"), "unknown"),
                "title": _compact_snippet(_first_nonempty_text(item.get("title")), max_len=96),
                "text": _compact_snippet(item.get("text"), max_len=max_text_len),
                "url": _safe_url(item.get("url")) or "",
                "score": _safe_float(item.get("score"), 0.0),
            }
        )
        if len(compact) >= max_items:
            break
    return compact


def _strip_json_fence(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _deep_beta_json_call(
    *,
    client: DeepSeekClient,
    system_prompt: str,
    prompt: str,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
    except Exception:
        return fallback

    try:
        parsed = json.loads(_strip_json_fence(response.content))
    except Exception:
        return fallback
    return parsed if isinstance(parsed, dict) else fallback


def _deep_beta_markdown_call(
    *,
    client: DeepSeekClient,
    system_prompt: str,
    prompt: str,
) -> str:
    try:
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
    except Exception:
        return ""
    return str(response.content or "").strip()


def _coerce_reasoning_queries(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_query_list([str(item) for item in value], limit=limit)


def _ensure_min_deep_beta_report(
    *,
    report_markdown: str,
    topic: str,
    citations: list[Citation],
    deep_pass_summaries: list[dict[str, Any]],
    min_chars: int,
) -> str:
    cleaned = str(report_markdown or "").strip()
    if len(cleaned) >= max(400, int(min_chars)):
        return cleaned

    citations_md = "\n".join(_citation_markdown_lines(citations))
    pass_rows = deep_pass_summaries[:10]
    pass_table_rows = [
        "| Pass | Subquery | Retrieved | Duration (ms) |",
        "| --- | --- | --- | --- |",
    ]
    if pass_rows:
        for item in pass_rows:
            pass_table_rows.append(
                "| "
                f"{_escape_markdown_cell(item.get('pass_index'))} | "
                f"{_escape_markdown_cell(_compact_snippet(item.get('subquery'), max_len=120))} | "
                f"{_escape_markdown_cell(item.get('retrieved_count'))} | "
                f"{_escape_markdown_cell(item.get('duration_ms'))} |"
            )
    else:
        pass_table_rows.append("| 1 | baseline | 0 | 0 |")
    pass_table = "\n".join(pass_table_rows)

    extension = (
        "## Phụ lục Deep Beta (Auto-Expanded)\n"
        f"- Chủ đề: {_compact_snippet(topic, max_len=220)}\n"
        f"- Tổng số pass retrieval: {max(1, len(deep_pass_summaries))}\n"
        f"- Tổng số nguồn trích dẫn: {len(citations)}\n\n"
        "### Nhật ký pass retrieval\n"
        f"{pass_table}\n\n"
        "### Hướng dẫn diễn giải an toàn\n"
        "- Luôn đọc kết quả như thông tin hỗ trợ, không thay thế chỉ định điều trị cá thể hóa.\n"
        "- Ưu tiên xác minh lại điểm mâu thuẫn evidence trước khi ra quyết định.\n"
        "- Khi có bệnh nền/đa thuốc/triệu chứng nặng, cần trao đổi bác sĩ ngay.\n\n"
        "### Nguồn tham chiếu bổ sung\n"
        f"{citations_md}"
    )
    combined = f"{cleaned}\n\n{extension}".strip()
    return combined


def run_research_tier2(payload: dict[str, Any]) -> dict:
    topic = _normalize_topic(payload)
    research_mode = _normalize_research_mode(payload)
    retrieval_stack_mode = _normalize_retrieval_stack_mode(payload)
    trace_id, run_id = _resolve_trace_identifiers(payload)
    source_mode = str(payload.get("source_mode") or "").strip().lower() or None
    role_hint = str(payload.get("role") or "").strip().lower() or None
    uploaded_documents_raw = payload.get("uploaded_documents")
    uploaded_documents: list[dict[str, Any]] = (
        uploaded_documents_raw if isinstance(uploaded_documents_raw, list) else []
    )
    rag_sources = payload.get("rag_sources")
    rag_flow_payload = payload.get("rag_flow")
    rag_flow = rag_flow_payload if isinstance(rag_flow_payload, dict) else {}
    llm_runtime = {
        "provider": rag_flow.get("llm_provider"),
        "api_key": rag_flow.get("llm_api_key"),
        "base_url": rag_flow.get("llm_base_url"),
        "model": rag_flow.get("llm_model"),
    }
    llm_provider, _llm_api_key, llm_base_url, llm_model = _resolve_runtime_llm_config(llm_runtime)
    legacy_verification_enabled = _coerce_bool(
        rag_flow.get("verification_enabled"),
        bool(settings.rule_verification_enabled),
    )
    rule_verification_enabled = (
        _coerce_bool(rag_flow.get("rule_verification_enabled"), legacy_verification_enabled)
        if "rule_verification_enabled" in rag_flow
        else legacy_verification_enabled
    )
    nli_model_enabled = _coerce_bool(rag_flow.get("nli_model_enabled"), True)
    rag_nli_enabled_override = _coerce_optional_bool(rag_flow.get("rag_nli_enabled"))
    rag_nli_enabled_runtime = (
        bool(settings.rag_nli_enabled)
        if rag_nli_enabled_override is None
        else bool(rag_nli_enabled_override)
    )
    rag_nli_enabled_runtime = bool(nli_model_enabled and rag_nli_enabled_runtime)
    rag_reranker_enabled_override = _coerce_optional_bool(rag_flow.get("rag_reranker_enabled"))
    rag_graphrag_enabled_override = _coerce_optional_bool(rag_flow.get("rag_graphrag_enabled"))
    if research_mode == "deep_beta":
        if rag_reranker_enabled_override is None:
            rag_reranker_enabled_override = True
        if rag_graphrag_enabled_override is None:
            rag_graphrag_enabled_override = True
    effective_rag_reranker_enabled = (
        bool(settings.rag_reranker_enabled)
        if rag_reranker_enabled_override is None
        else bool(rag_reranker_enabled_override)
    )
    effective_rag_graphrag_enabled = (
        bool(settings.rag_graphrag_enabled)
        if rag_graphrag_enabled_override is None
        else bool(rag_graphrag_enabled_override)
    )
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
        retrieval_stack_mode=retrieval_stack_mode,
    )
    source_route = decide_source_route(
        query=topic,
        research_mode=research_mode,
        has_uploaded_documents=bool(uploaded_documents),
        is_ddi_query=bool(planner_hints.get("is_ddi_query")),
        is_ddi_critical_query=bool(planner_hints.get("is_ddi_critical_query")),
        language_hint=str(planner_hints.get("language_hint") or "en"),
        web_policy_allowed=bool(planner_hints.get("web_retrieval_enabled")),
    )

    planner_hints["scientific_retrieval_enabled"] = bool(
        planner_hints.get("scientific_retrieval_enabled")
    ) and bool(source_route.enable_scientific)
    planner_hints["web_retrieval_enabled"] = bool(planner_hints.get("web_retrieval_enabled")) and bool(
        source_route.enable_web
    )
    reason_codes = planner_hints.get("reason_codes")
    if not isinstance(reason_codes, list):
        reason_codes = []
    reason_codes.extend(f"source_route:{code}" for code in source_route.reason_codes if code)
    reason_codes.append(f"retrieval_route_{source_route.retrieval_route}")
    planner_hints["reason_codes"] = list(dict.fromkeys([str(item) for item in reason_codes if str(item)]))
    planner_hints["retrieval_route"] = _normalize_retrieval_route(source_route.retrieval_route)
    planner_hints["router_confidence"] = _normalize_router_confidence(source_route.confidence)
    planner_hints["router_reason_codes"] = list(source_route.reason_codes)

    base_query_plan = _build_source_aware_query_plan(
        topic=topic,
        research_mode=research_mode,
        keywords=planner_hints.get("keywords", []),
        source_route=source_route,
    )
    planner_hints["query_plan"] = base_query_plan
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
        event_payload.setdefault("trace_id", trace_id)
        event_payload.setdefault("run_id", run_id)
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
                "retrieval_route": planner_hints.get("retrieval_route", "internal-heavy"),
                "router_confidence": planner_hints.get("router_confidence", 0.0),
                "flow_flags": {
                    "verification_enabled": legacy_verification_enabled,
                    "rule_verification_enabled": rule_verification_enabled,
                    "nli_model_enabled": nli_model_enabled,
                    "rag_nli_enabled": rag_nli_enabled_runtime,
                    "rag_reranker_enabled": effective_rag_reranker_enabled,
                    "rag_graphrag_enabled": effective_rag_graphrag_enabled,
                },
            },
        ),
    ]

    llm_plan, llm_plan_status = _refine_query_plan_with_llm(
        topic=topic,
        research_mode=research_mode,
        route_role=route.role,
        route_intent=route.intent,
        base_query_plan=base_query_plan,
        keywords=planner_hints.get("keywords", []),
        llm_runtime=llm_runtime,
    )
    llm_attempted = bool(llm_plan_status.get("attempted"))
    llm_status = str(llm_plan_status.get("status") or "degraded")
    llm_reason = str(llm_plan_status.get("reason") or "unknown")

    if llm_attempted:
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="started",
                source_count=0,
                note="LLM query planner refinement started.",
                component="planner",
                payload={
                    "base_canonical_query": base_query_plan.get("canonical_query"),
                    "model": llm_model or settings.deepseek_model,
                    "provider": llm_provider,
                    "base_url": llm_base_url,
                },
            )
        )

    if llm_status == "completed":
        planner_hints["query_plan"] = llm_plan
        planner_hints["reason_codes"] = [
            *planner_hints.get("reason_codes", []),
            "llm_query_planner_enabled",
        ]
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="completed",
                source_count=0,
                note="LLM query planner refinement completed.",
                component="planner",
                payload={
                    "model_used": llm_plan_status.get("model_used"),
                    "reason": llm_reason,
                    "canonical_query": llm_plan.get("canonical_query"),
                },
            )
        )
    else:
        planner_hints["query_plan"] = base_query_plan
        if llm_attempted:
            planner_hints["reason_codes"] = [
                *planner_hints.get("reason_codes", []),
                "llm_query_planner_fallback",
            ]
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="degraded",
                source_count=0,
                note=(
                    "LLM query planner degraded; fallback to base query plan."
                    if llm_attempted
                    else "LLM query planner skipped due to missing API key."
                ),
                component="planner",
                payload={
                    "reason": llm_reason,
                    "attempted": llm_attempted,
                    "error": llm_plan_status.get("error"),
                    "canonical_query": planner_hints["query_plan"].get("canonical_query"),
                },
            )
        )

    if isinstance(planner_hints.get("query_plan"), dict):
        planner_hints["query_plan"]["retrieval_route"] = _normalize_retrieval_route(
            planner_hints.get("retrieval_route")
        )
        planner_hints["query_plan"]["router_confidence"] = _normalize_router_confidence(
            planner_hints.get("router_confidence")
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
    planner_trace["trace_id"] = trace_id
    planner_trace["run_id"] = run_id
    flow_events.append(
        _event(
            stage="planner",
            status="completed",
            source_count=0,
            note="Planner produced retrieval and verification strategy.",
            component="planner",
            payload=planner_hints,
        )
    )

    pipeline = RagPipelineP1()
    strict_deepseek_required = bool(
        payload.get("strict_deepseek_required", settings.deepseek_required)
    )
    deepseek_fallback_enabled = not strict_deepseek_required
    deep_beta_cap = max(6, min(int(settings.deep_beta_pass_cap), 64))
    pass_count_cap = deep_beta_cap if research_mode == "deep_beta" else _DEFAULT_DEEP_PASS_CAP
    deep_pass_count = _resolve_deep_pass_count(
        payload,
        int(planner_hints.get("deep_pass_count", 1)),
        cap=pass_count_cap,
    )
    planner_hints["deep_pass_count"] = deep_pass_count
    if isinstance(planner_trace.get("planner_hints"), dict):
        planner_trace["planner_hints"]["deep_pass_count"] = deep_pass_count
    deep_subqueries: list[str] = [topic]
    deep_research_profiles: list[dict[str, Any]] = []
    deep_research_method: dict[str, Any] = {}
    deep_pass_summaries: list[dict[str, Any]] = []
    deep_pass_contexts: list[list[dict[str, Any]]] = []
    deep_pass_flow_events: list[dict[str, Any]] = []
    deep_beta_reasoning_steps: list[dict[str, Any]] = []
    deep_beta_retrieval_budgets: dict[str, Any] = {}
    deep_beta_chain_status: dict[str, Any] = {}
    deep_beta_parallel_reasoning_nodes: list[dict[str, Any]] = []
    deep_beta_gap_fill_queries: list[str] = []
    deep_beta_evidence_verification: dict[str, Any] = {}
    deep_beta_quality_gate: dict[str, Any] = {}

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

    def _refresh_beta_chain_status(*, current_stage: str | None = None, status: str | None = None) -> None:
        if not deep_beta_reasoning_steps:
            return
        total_steps = len(deep_beta_reasoning_steps)
        completed_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() == "completed"
        )
        warning_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() in {"warning", "degraded", "failed"}
        )
        skipped_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() in {"skipped"}
        )
        terminal_steps = completed_steps + warning_steps + skipped_steps
        if not current_stage:
            current_stage = ""
            for item in deep_beta_reasoning_steps:
                state = str(item.get("status") or "").strip().lower()
                if state in {"pending", "started", "running"}:
                    current_stage = str(item.get("stage") or "")
                    break
            if not current_stage and deep_beta_reasoning_steps:
                current_stage = str(deep_beta_reasoning_steps[-1].get("stage") or "")
        if not status:
            if terminal_steps >= total_steps and warning_steps == 0:
                status = "completed"
            elif terminal_steps >= total_steps and warning_steps > 0:
                status = "warning"
            else:
                status = "running"
        deep_beta_chain_status.update(
            {
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "terminal_steps": terminal_steps,
                "current_stage": current_stage,
                "status": status,
                "warning_steps": warning_steps,
                "skipped_steps": skipped_steps,
            }
        )

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
                rag_reranker_enabled=rag_reranker_enabled_override,
                rag_graphrag_enabled=rag_graphrag_enabled_override,
                llm_runtime=llm_runtime,
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
        budget_pass_cap = _safe_int(
            (
                planner_hints.get("retrieval_budget", {}).get("pass_cap")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else None
            ),
            _DEEP_BETA_PASS_CAP,
        )
        deep_beta_retrieval_budgets = {
            **(
                planner_hints.get("retrieval_budget")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else {}
            ),
            "mode": "deep_beta",
            "pass_cap": max(1, budget_pass_cap),
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
        _refresh_beta_chain_status(current_stage="deep_beta_scope", status="running")

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
        _refresh_beta_chain_status(current_stage="deep_beta_hypothesis_map", status="running")
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
        _refresh_beta_chain_status(current_stage="deep_beta_retrieval_budget", status="running")
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
        _refresh_beta_chain_status(current_stage="deep_beta_multi_pass_retrieval", status="running")
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
                rag_reranker_enabled=rag_reranker_enabled_override,
                rag_graphrag_enabled=rag_graphrag_enabled_override,
                llm_runtime=llm_runtime,
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
        _refresh_beta_chain_status(current_stage="deep_beta_evidence_audit", status="running")
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

        parallel_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_parallel_reasoning",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Running parallel Deep Beta LLM reasoning nodes for evidence audit.",
                component="verifier",
                payload={
                    "nodes_target": min(
                        int(settings.deep_beta_reasoning_llm_nodes),
                        6,
                    ),
                    "parallel_workers": int(settings.deep_beta_reasoning_parallel_workers),
                    "reasoning_rounds": int(settings.deep_beta_reasoning_rounds),
                },
            )
        )
        deep_beta_parallel_reasoning_nodes = _run_deep_beta_parallel_reasoning_nodes(
            topic=topic,
            query_plan=query_plan if isinstance(query_plan, dict) else {},
            retrieval_budget=deep_beta_retrieval_budgets,
            deep_pass_summaries=deep_pass_summaries,
            evidence_rows=_merge_retrieved_context([], deep_pass_contexts),
            llm_runtime=llm_runtime,
        )
        completed_parallel_nodes = 0
        for node_result in deep_beta_parallel_reasoning_nodes:
            node_name = str(node_result.get("node") or "deep_beta_parallel_node")
            node_status = str(node_result.get("status") or "degraded").strip().lower()
            mapped_status = "completed" if node_status == "completed" else "warning"
            if mapped_status == "completed":
                completed_parallel_nodes += 1
            node_note = (
                "Reasoning node completed."
                if mapped_status == "completed"
                else f"Reasoning node degraded ({node_result.get('reason') or 'unknown'})."
            )
            _update_beta_reasoning_step(
                stage=node_name,
                status=mapped_status,
                note=node_note,
                payload=node_result,
            )
            flow_events.append(
                _event(
                    stage=node_name,
                    status=mapped_status,
                    source_count=len(deep_pass_summaries),
                    note=node_note,
                    component="verifier",
                    payload=node_result,
                )
            )
        _refresh_beta_chain_status(current_stage="deep_beta_gap_fill", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_parallel_reasoning",
                status="completed" if completed_parallel_nodes else "warning",
                source_count=len(deep_beta_parallel_reasoning_nodes),
                note="Parallel Deep Beta reasoning nodes finished.",
                component="verifier",
                payload={
                    "completed_nodes": completed_parallel_nodes,
                    "total_nodes": len(deep_beta_parallel_reasoning_nodes),
                    "nodes": deep_beta_parallel_reasoning_nodes,
                },
                started_at=parallel_started,
            )
        )

        deep_beta_gap_fill_queries = _collect_reasoning_follow_up_queries(
            deep_beta_parallel_reasoning_nodes,
            limit=max(int(settings.deep_beta_gap_fill_max_queries), 1),
        )
        gap_fill_pass_cap = max(0, int(settings.deep_beta_gap_fill_max_passes))
        if deep_beta_gap_fill_queries and gap_fill_pass_cap > 0:
            gap_fill_started = perf_counter()
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="started",
                note="Targeted gap-fill retrieval started.",
                payload={
                    "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    "pass_cap": gap_fill_pass_cap,
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="started",
                    source_count=0,
                    note="Deep beta targeted gap-fill retrieval started.",
                    component="retrieval",
                    payload={
                        "query_count": len(deep_beta_gap_fill_queries),
                        "pass_cap": gap_fill_pass_cap,
                        "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    },
                )
            )
            executed_gap_fill_passes = 0
            for query_index, gap_query in enumerate(deep_beta_gap_fill_queries[:gap_fill_pass_cap], start=1):
                pass_started = perf_counter()
                flow_events.append(
                    _event(
                        stage="deep_beta_gap_fill_pass",
                        status="started",
                        source_count=0,
                        note=f"Deep beta gap-fill pass {query_index} started.",
                        component="retrieval",
                        payload={"pass_index": query_index, "subquery": gap_query},
                    )
                )
                pass_result = pipeline.run(
                    gap_query,
                    low_context_threshold=float(planner_hints["low_context_threshold"]),
                    deepseek_fallback_enabled=deepseek_fallback_enabled,
                    scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                    web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                    file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                    planner_hints={
                        **planner_hints,
                        "query_focus": f"deep_beta_gap_fill_{query_index}",
                        "reason_codes": [
                            *planner_hints.get("reason_codes", []),
                            f"deep_beta_gap_fill_{query_index}",
                        ],
                    },
                    generation_enabled=False,
                    strict_deepseek_required=strict_deepseek_required,
                    rag_reranker_enabled=rag_reranker_enabled_override,
                    rag_graphrag_enabled=rag_graphrag_enabled_override,
                    llm_runtime=llm_runtime,
                )
                deep_pass_contexts.append(pass_result.retrieved_context)
                deep_pass_summaries.append(
                    {
                        "pass_index": len(deep_pass_summaries) + 1,
                        "subquery": gap_query,
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "doc_ids": list(pass_result.retrieved_ids[:8]),
                        "relevance": pass_result.context_debug.get("relevance")
                        if isinstance(pass_result.context_debug, dict)
                        else None,
                        "duration_ms": round((perf_counter() - pass_started) * 1000.0, 3),
                        "source_errors": {},
                        "source_attempts": [],
                        "index_summary": {},
                        "crawl_summary": {},
                        "reasoning_focus": f"deep_beta_gap_fill_{query_index}",
                        "budget_target_docs": deep_beta_retrieval_budgets.get("per_pass_doc_target"),
                    }
                )
                flow_events.extend(
                    _normalize_retrieval_events(
                        pass_result.flow_events, default_component="deep_beta_retrieval"
                    )
                )
                flow_events.append(
                    _event(
                        stage="deep_beta_gap_fill_pass",
                        status="completed",
                        source_count=len(pass_result.retrieved_ids),
                        note=f"Deep beta gap-fill pass {query_index} completed.",
                        component="retrieval",
                        payload={
                            "pass_index": query_index,
                            "subquery": gap_query,
                            "retrieved_count": len(pass_result.retrieved_ids),
                        },
                        started_at=pass_started,
                    )
                )
                executed_gap_fill_passes += 1
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="completed" if executed_gap_fill_passes else "warning",
                note=(
                    "Targeted gap-fill retrieval completed."
                    if executed_gap_fill_passes
                    else "No effective docs retrieved from gap-fill queries."
                ),
                payload={
                    "executed_passes": executed_gap_fill_passes,
                    "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="completed" if executed_gap_fill_passes else "warning",
                    source_count=executed_gap_fill_passes,
                    note=(
                        "Deep beta targeted gap-fill retrieval completed."
                        if executed_gap_fill_passes
                        else "Deep beta gap-fill did not add strong evidence."
                    ),
                    component="retrieval",
                    payload={
                        "executed_passes": executed_gap_fill_passes,
                        "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    },
                    started_at=gap_fill_started,
                )
            )
        else:
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="skipped",
                note="Gap-fill retrieval skipped (no follow-up queries or pass cap=0).",
                payload={
                    "query_count": len(deep_beta_gap_fill_queries),
                    "pass_cap": gap_fill_pass_cap,
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="skipped",
                    source_count=0,
                    note="Gap-fill retrieval skipped.",
                    component="retrieval",
                    payload={
                        "query_count": len(deep_beta_gap_fill_queries),
                        "pass_cap": gap_fill_pass_cap,
                    },
                )
            )

        _refresh_beta_chain_status(current_stage="deep_beta_evidence_verification", status="running")
        evidence_verify_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_evidence_verification",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta evidence verification node started.",
                component="verifier",
                payload={
                    "reasoning_node_count": len(deep_beta_parallel_reasoning_nodes),
                    "pass_count": len(deep_pass_summaries),
                },
            )
        )
        deep_beta_evidence_verification = _run_deep_beta_evidence_verification_node(
            topic=topic,
            deep_pass_summaries=deep_pass_summaries,
            evidence_rows=_merge_retrieved_context([], deep_pass_contexts),
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            llm_runtime=llm_runtime,
        )
        evidence_verification_status = str(
            deep_beta_evidence_verification.get("status") or "degraded"
        ).strip().lower()
        mapped_evidence_status = (
            "completed" if evidence_verification_status == "completed" else "warning"
        )
        _update_beta_reasoning_step(
            stage="deep_beta_evidence_verification",
            status=mapped_evidence_status,
            note=(
                "Evidence verification completed."
                if mapped_evidence_status == "completed"
                else "Evidence verification degraded."
            ),
            payload=deep_beta_evidence_verification,
        )
        flow_events.append(
            _event(
                stage="deep_beta_evidence_verification",
                status=mapped_evidence_status,
                source_count=len(deep_pass_summaries),
                note=(
                    "Deep beta evidence verification completed."
                    if mapped_evidence_status == "completed"
                    else "Deep beta evidence verification degraded."
                ),
                component="verifier",
                payload=deep_beta_evidence_verification,
                started_at=evidence_verify_started,
            )
        )

        _refresh_beta_chain_status(current_stage="deep_beta_chain_synthesis", status="running")
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
        _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="running")
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
        rag_reranker_enabled=rag_reranker_enabled_override,
        rag_graphrag_enabled=rag_graphrag_enabled_override,
        llm_runtime=llm_runtime,
    )
    if strict_deepseek_required and (
        rag_result.model_used.startswith("local-synth")
        or "fallback" in rag_result.model_used.lower()
    ):
        raise RuntimeError("tier2_deepseek_required_violation")
    retrieval_trace = _build_retrieval_trace(rag_result=rag_result, planner_hints=planner_hints)
    retrieval_trace["trace_id"] = trace_id
    retrieval_trace["run_id"] = run_id
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
    answer_markdown = _ensure_markdown_structure(
        topic,
        rag_result.answer,
        citations,
        research_mode=research_mode,
    )
    if research_mode == "deep_beta":
        deep_beta_report_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_report_synthesis",
                status="started",
                source_count=len(citations),
                note="Deep Beta long-form report synthesis started.",
                component="postprocess",
                payload={
                    "citation_count": len(citations),
                    "reasoning_node_count": len(deep_beta_parallel_reasoning_nodes),
                    "deep_pass_count": len(deep_pass_summaries),
                },
            )
        )
        rewritten_report = _synthesize_deep_beta_long_report(
            topic=topic,
            answer_markdown=answer_markdown,
            citations=citations,
            verification_matrix_payload={},
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            deep_pass_summaries=deep_pass_summaries,
            evidence_verification=deep_beta_evidence_verification,
            llm_runtime=llm_runtime,
        )
        report_changed = bool(
            str(rewritten_report or "").strip()
            and str(rewritten_report).strip() != str(answer_markdown).strip()
        )
        if report_changed:
            answer_markdown = _ensure_markdown_structure(
                topic,
                rewritten_report,
                citations,
                research_mode=research_mode,
            )
            _update_beta_reasoning_step(
                stage="deep_beta_report_synthesis",
                status="completed",
                note="Deep beta report synthesis completed with LLM long-form output.",
                payload={"answer_chars": len(answer_markdown)},
            )
            _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="running")
        else:
            _update_beta_reasoning_step(
                stage="deep_beta_report_synthesis",
                status="warning",
                note="Deep beta report synthesis fell back to baseline answer.",
                payload={"answer_chars": len(answer_markdown)},
            )
            _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="warning")
        flow_events.append(
            _event(
                stage="deep_beta_report_synthesis",
                status="completed" if report_changed else "warning",
                source_count=len(citations),
                note=(
                    "Deep Beta long-form report synthesized."
                    if report_changed
                    else "Deep Beta report synthesis degraded; baseline report retained."
                ),
                component="postprocess",
                payload={
                    "report_changed": report_changed,
                    "answer_chars": len(answer_markdown),
                    "target_min_words": int(settings.deep_beta_report_min_words),
                },
                started_at=deep_beta_report_started,
            )
        )
    if research_mode == "deep_beta":
        answer_markdown = _sanitize_deep_beta_markdown_output(answer_markdown)
        answer_markdown = _ensure_deep_beta_report_artifacts(
            markdown_text=answer_markdown,
            deep_pass_summaries=deep_pass_summaries,
            evidence_verification=deep_beta_evidence_verification,
            verification_summary={},
        )
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
    if rule_verification_enabled:
        try:
            factcheck_result = run_fides_lite(
                answer=answer_markdown,
                retrieved_context=effective_context,
                nli_enabled=rag_nli_enabled_runtime,
            )
        except TypeError as type_exc:
            if "unexpected keyword argument" not in str(type_exc):
                raise
            factcheck_result = run_fides_lite(
                answer=answer_markdown,
                retrieved_context=effective_context,
            )
        policy_action = "allow" if factcheck_result.verdict == "pass" else "warn"
        verification_state = "verified" if policy_action == "allow" else "warning"
    else:
        factcheck_result = FactCheckResult(
            enabled=False,
            stage="verification-skipped-v1",
            verdict="pass",
            confidence=1.0,
            supported_claims=0,
            total_claims=0,
            unsupported_claims=[],
            evidence_count=len(effective_context),
            severity="low",
            note="Rule verification disabled by flow flag.",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v2-nli",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "Verification skipped.",
            },
            fide_report={},
        )
        policy_action = "allow"
        verification_state = "skipped"
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
        "version": str(verification_matrix_summary.get("version") or "claim-v2-nli"),
        "rows": verification_matrix_rows,
        "summary": verification_matrix_summary,
        "contradiction_summary": contradiction_summary,
    }
    if rule_verification_enabled:
        safety_override = _evaluate_safety_critical_override(
            rows=verification_matrix_rows,
            nli_enabled=rag_nli_enabled_runtime,
        )
    else:
        safety_override = {
            "applied": False,
            "status": "skipped",
            "reason": "rule_verification_disabled",
            "note": "Rule verification disabled by flow flag.",
            "policy_action": policy_action,
            "verification_state": verification_state,
            "claims": [],
            "affected_claim_count": 0,
        }
    if bool(safety_override.get("applied")):
        policy_action = str(safety_override.get("policy_action") or policy_action)
        verification_state = str(safety_override.get("verification_state") or verification_state)
        severity_override = str(safety_override.get("severity_override") or "").strip().lower()
        if severity_override:
            factcheck_result.severity = severity_override
        flow_events.append(
            _event(
                stage="safety_override",
                status=str(safety_override.get("status") or "warning"),
                source_count=_safe_int(safety_override.get("affected_claim_count"), 0),
                note=str(safety_override.get("note") or "Safety override applied."),
                component="policy",
                payload={
                    "reason": safety_override.get("reason"),
                    "policy_action": policy_action,
                    "verification_state": verification_state,
                    "claims": safety_override.get("claims", []),
                    "affected_claim_count": _safe_int(
                        safety_override.get("affected_claim_count"),
                        0,
                    ),
                },
            )
        )
    verification_matrix_payload["safety_override"] = safety_override
    if research_mode == "deep_beta":
        quality_gate_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_quality_gate",
                status="started",
                source_count=len(citations),
                note="Deep beta quality gate started.",
                component="verifier",
                payload={
                    "reasoning_nodes": deep_beta_parallel_reasoning_nodes,
                    "citation_count": len(citations),
                    "evidence_verification_status": deep_beta_evidence_verification.get("status"),
                },
            )
        )
        deep_beta_quality_gate = _run_deep_beta_quality_gate(
            topic=topic,
            answer_markdown=answer_markdown,
            citations=citations,
            verification_matrix_payload=verification_matrix_payload,
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            evidence_verification=deep_beta_evidence_verification,
            llm_runtime=llm_runtime,
        )
        gate_status = str(deep_beta_quality_gate.get("status") or "degraded").strip().lower()
        gate_quality_score = _safe_float(deep_beta_quality_gate.get("quality_score"), 0.0)
        if gate_status == "completed" and gate_quality_score >= 0.65:
            gate_event_status = "completed"
        elif gate_status == "completed":
            gate_event_status = "warning"
        elif gate_status == "skipped":
            gate_event_status = "skipped"
        else:
            gate_event_status = "degraded"
        _update_beta_reasoning_step(
            stage="deep_beta_quality_gate",
            status=gate_event_status,
            note=(
                "Deep beta quality gate completed."
                if gate_event_status == "completed"
                else "Deep beta quality gate requires manual review."
            ),
            payload=deep_beta_quality_gate,
        )
        _refresh_beta_chain_status(
            current_stage="deep_beta_chain_verification",
            status="warning" if gate_event_status in {"warning", "degraded"} else "running",
        )
        flow_events.append(
            _event(
                stage="deep_beta_quality_gate",
                status=gate_event_status,
                source_count=len(citations),
                note=(
                    "Deep beta quality gate completed."
                    if gate_event_status == "completed"
                    else "Deep beta quality gate flagged potential quality risks."
                ),
                component="verifier",
                payload=deep_beta_quality_gate,
                started_at=quality_gate_started,
            )
        )
    verifier_trace = _build_verifier_trace(
        factcheck_result=factcheck_result,
        policy_action=policy_action,
        verification_state=verification_state,
        verification_matrix=verification_matrix_payload,
    )
    verifier_trace["trace_id"] = trace_id
    verifier_trace["run_id"] = run_id
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
            "safety_override": safety_override,
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
    if rule_verification_enabled:
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
    else:
        flow_events.append(
            _event(
                stage="verification",
                status="skipped",
                source_count=0,
                note="Rule verification disabled by flow flag.",
                component="verifier",
                payload={"verifier": "disabled"},
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
        _refresh_beta_chain_status(
            current_stage="deep_beta_chain_verification",
            status=chain_verification_status,
        )
        deep_beta_chain_status["verification_status"] = chain_verification_status
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

    def _beta_stage_status(stage_name: str, default: str = "completed") -> str:
        if research_mode != "deep_beta" or not deep_beta_reasoning_steps:
            return default
        for item in deep_beta_reasoning_steps:
            if str(item.get("stage")) != stage_name:
                continue
            raw = str(item.get("status") or "").strip().lower()
            if raw in {"completed", "pass", "ok"}:
                return "completed"
            if raw in {"warning", "degraded", "failed", "error"}:
                return "warning"
            if raw in {"running", "started", "pending"}:
                return "running"
            return default
        return default

    metadata_stage_entries = [
        {"name": "plan", "status": "completed"},
        *(
            [{"name": "deep_research", "status": "completed"}]
            if research_mode == "deep"
            else [
                {"name": "deep_beta_scope", "status": _beta_stage_status("deep_beta_scope")},
                {"name": "deep_beta_hypothesis_map", "status": _beta_stage_status("deep_beta_hypothesis_map")},
                {"name": "deep_beta_retrieval_budget", "status": _beta_stage_status("deep_beta_retrieval_budget")},
                {
                    "name": "deep_beta_multi_pass_retrieval",
                    "status": _beta_stage_status("deep_beta_multi_pass_retrieval", retrieval_status),
                },
                {"name": "deep_beta_evidence_audit", "status": _beta_stage_status("deep_beta_evidence_audit")},
                {"name": "deep_beta_claim_graph", "status": _beta_stage_status("deep_beta_claim_graph")},
                {
                    "name": "deep_beta_counter_evidence_scan",
                    "status": _beta_stage_status("deep_beta_counter_evidence_scan"),
                },
                {
                    "name": "deep_beta_guideline_alignment",
                    "status": _beta_stage_status("deep_beta_guideline_alignment"),
                },
                {
                    "name": "deep_beta_risk_stratification",
                    "status": _beta_stage_status("deep_beta_risk_stratification"),
                },
                {"name": "deep_beta_gap_fill", "status": _beta_stage_status("deep_beta_gap_fill")},
                {
                    "name": "deep_beta_parallel_reasoning",
                    "status": (
                        "completed"
                        if deep_beta_parallel_reasoning_nodes
                        and all(
                            str(item.get("status") or "").strip().lower() == "completed"
                            for item in deep_beta_parallel_reasoning_nodes
                            if isinstance(item, dict)
                        )
                        else "warning"
                        if deep_beta_parallel_reasoning_nodes
                        else "skipped"
                    ),
                },
                {
                    "name": "deep_beta_evidence_verification",
                    "status": _beta_stage_status("deep_beta_evidence_verification"),
                },
                {"name": "deep_beta_chain_synthesis", "status": _beta_stage_status("deep_beta_chain_synthesis")},
                {"name": "deep_beta_report_synthesis", "status": _beta_stage_status("deep_beta_report_synthesis")},
                {"name": "deep_beta_quality_gate", "status": _beta_stage_status("deep_beta_quality_gate")},
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
    ]
    stage_spans = (
        _build_stage_span_summaries(flow_events, stage_entries=metadata_stage_entries)
        if research_mode in {"deep", "deep_beta"}
        else []
    )
    stage_spans_by_stage: dict[str, dict[str, Any]] = {
        str(item.get("stage")): item for item in stage_spans if isinstance(item, dict)
    }
    metadata_stages = [
        {
            **stage_entry,
            "start_at": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("start_at")
                if stage_spans_by_stage
                else None
            ),
            "end_at": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("end_at")
                if stage_spans_by_stage
                else None
            ),
            "duration_ms": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("duration_ms")
                if stage_spans_by_stage
                else None
            ),
        }
        for stage_entry in metadata_stage_entries
    ]
    otel_trace_metadata = _build_otel_trace_metadata(
        trace_id=trace_id,
        run_id=run_id,
        stage_spans=stage_spans,
        flow_events=flow_events,
    )
    otel_export_status = _emit_otel_trace_best_effort(
        otel_trace_metadata=otel_trace_metadata,
        flow_events=flow_events,
    )
    trace_bundle = {
        "trace_id": trace_id,
        "run_id": run_id,
        "planner": planner_trace,
        "retrieval": retrieval_trace,
        "verifier": verifier_trace,
        "stage_spans": stage_spans,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
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

    stack_mode_requested = (
        "full"
        if str(planner_hints.get("retrieval_stack_mode") or "").strip().lower() == "full"
        else "auto"
    )
    stack_coverage_raw = (
        retrieval_trace.get("stack_coverage")
        if isinstance(retrieval_trace.get("stack_coverage"), dict)
        else {}
    )
    if not stack_coverage_raw:
        provider_keys: set[str] = set()
        for attempt in source_attempts:
            if not isinstance(attempt, dict):
                continue
            provider_key = _first_nonempty_text(attempt.get("provider"), attempt.get("source")).lower()
            if provider_key:
                provider_keys.add(provider_key)
        scientific_provider_keys = {
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
        web_provider_keys = {"searxng", "searxng-crawl", "web_crawl"}
        stack_coverage_raw = {
            "vector_internal_used": "internal_corpus" in provider_keys,
            "graph_used": bool(retrieval_trace.get("graphrag_enabled")),
            "graph_expansion_count": _safe_int(retrieval_trace.get("graphrag_expansion_count"), 0),
            "scientific_used": bool(provider_keys.intersection(scientific_provider_keys)),
            "web_used": bool(provider_keys.intersection(web_provider_keys)),
        }
    stack_coverage = {
        "vector_internal_used": bool(stack_coverage_raw.get("vector_internal_used")),
        "graph_used": bool(stack_coverage_raw.get("graph_used")),
        "graph_expansion_count": _safe_int(
            stack_coverage_raw.get("graph_expansion_count"),
            _safe_int(retrieval_trace.get("graphrag_expansion_count"), 0),
        ),
        "scientific_used": bool(stack_coverage_raw.get("scientific_used")),
        "web_used": bool(stack_coverage_raw.get("web_used")),
    }
    missing_stack_components = [
        name
        for name, used in (
            ("vector_internal", stack_coverage["vector_internal_used"]),
            ("graph", stack_coverage["graph_used"]),
            ("scientific", stack_coverage["scientific_used"]),
            ("web", stack_coverage["web_used"]),
        )
        if not used
    ]

    stack_mode_effective_from_trace = str(retrieval_trace.get("stack_mode_effective") or "").strip().lower()
    if stack_mode_effective_from_trace not in {"auto", "full"}:
        stack_mode_effective_from_trace = ""
    computed_stack_mode_effective = (
        "full"
        if stack_mode_requested == "full" and not missing_stack_components
        else "auto"
    )
    # requested=full must degrade to auto if any stack is missing.
    if stack_mode_requested == "full":
        stack_mode_effective = computed_stack_mode_effective
    else:
        stack_mode_effective = stack_mode_effective_from_trace or computed_stack_mode_effective

    stack_mode_reason_codes = (
        [str(item).strip() for item in retrieval_trace.get("stack_mode_reason_codes", []) if str(item).strip()]
        if isinstance(retrieval_trace.get("stack_mode_reason_codes"), list)
        else []
    )
    stack_mode_reason_codes.append(f"stack_mode_requested_{stack_mode_requested}")
    if stack_mode_effective == "full":
        stack_mode_reason_codes.append("stack_mode_effective_full")
    elif stack_mode_requested == "full":
        stack_mode_reason_codes.append("stack_mode_effective_auto_missing_stack")
        stack_mode_reason_codes.extend(
            f"stack_mode_missing_{component}" for component in missing_stack_components
        )
    else:
        stack_mode_reason_codes.append("stack_mode_effective_auto")
    if (
        stack_mode_requested == "full"
        and stack_mode_effective_from_trace == "full"
        and stack_mode_effective == "auto"
    ):
        stack_mode_reason_codes.append("stack_mode_effective_adjusted_from_retrieval_trace")
    stack_mode_reason_codes = list(dict.fromkeys(stack_mode_reason_codes))

    retrieval_trace["stack_mode_effective"] = stack_mode_effective
    retrieval_trace["stack_mode_reason_codes"] = stack_mode_reason_codes
    retrieval_trace["stack_coverage"] = stack_coverage

    target_sources = ["internal"]
    if bool(planner_hints.get("scientific_retrieval_enabled")):
        target_sources.append("scientific")
    if bool(planner_hints.get("web_retrieval_enabled")):
        target_sources.append("web")
    if bool(planner_hints.get("file_retrieval_enabled")):
        target_sources.append("file")

    source_target_objective = {
        "target_sources": target_sources,
        "target_source_count": len(target_sources),
        "target_pass_count": deep_pass_count if research_mode in {"deep", "deep_beta"} else 1,
        "pass_cap": pass_count_cap,
        "target_document_budget": _safe_int(
            (
                planner_hints.get("retrieval_budget", {}).get("estimated_max_documents")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else None
            ),
            max(len(target_sources), 1),
        ),
    }

    achieved_sources: list[str] = []
    for row in effective_context:
        if not isinstance(row, dict):
            continue
        source_name = _first_nonempty_text(row.get("source"))
        if source_name and source_name not in achieved_sources:
            achieved_sources.append(source_name)
    for attempt in source_attempts:
        if not isinstance(attempt, dict):
            continue
        source_name = _first_nonempty_text(attempt.get("provider"), attempt.get("source"))
        if source_name and source_name not in achieved_sources:
            achieved_sources.append(source_name)

    source_target_achieved = {
        "achieved_sources": achieved_sources,
        "achieved_source_count": len(achieved_sources),
        "achieved_document_count": len(effective_context),
        "achieved_pass_count": (
            len(deep_pass_summaries)
            if research_mode in {"deep", "deep_beta"} and deep_pass_summaries
            else 1
        ),
    }

    chart_specs = _build_chart_specs(
        citations=citations,
        verification_matrix_payload=verification_matrix_payload,
    )
    visual_assets = _build_visual_assets(citations)
    reasoning_digest = _build_reasoning_digest(
        topic=topic,
        research_mode=research_mode,
        planner_hints=planner_hints,
        answer_markdown=answer_markdown,
        citations=citations,
        verification_matrix_payload=verification_matrix_payload,
        flow_events=flow_events,
        deep_pass_count=len(deep_pass_summaries) if deep_pass_summaries else 1,
        parallel_reasoning_nodes=deep_beta_parallel_reasoning_nodes,
        evidence_verification=deep_beta_evidence_verification,
    )
    retrieval_route = _normalize_retrieval_route(
        query_plan.get("retrieval_route")
        or planner_hints.get("retrieval_route")
        or "internal-heavy"
    )
    router_confidence = _normalize_router_confidence(
        query_plan.get("router_confidence")
        if isinstance(query_plan.get("router_confidence"), (int, float))
        else planner_hints.get("router_confidence")
        if isinstance(planner_hints.get("router_confidence"), (int, float))
        else 0.0
    )
    degraded_path = bool(
        effective_fallback_used
        or any(
            str(event.get("status") or "").strip().lower() == "degraded"
            for event in flow_events
            if isinstance(event, dict)
        )
    )

    telemetry = {
        "trace_id": trace_id,
        "run_id": run_id,
        "flow_flags": {
            "verification_enabled": legacy_verification_enabled,
            "rule_verification_enabled": rule_verification_enabled,
            "nli_model_enabled": nli_model_enabled,
            "rag_nli_enabled": rag_nli_enabled_runtime,
            "rag_reranker_enabled": effective_rag_reranker_enabled,
            "rag_graphrag_enabled": effective_rag_graphrag_enabled,
        },
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
        "degraded_path": degraded_path,
        "retrieval_route": retrieval_route,
        "router_confidence": router_confidence,
        "index_summary": index_summary,
        "crawl_summary": crawl_summary,
        "stack_mode": {
            "requested": stack_mode_requested,
            "effective": stack_mode_effective,
            "reason_codes": stack_mode_reason_codes,
        },
        "stack_coverage": stack_coverage,
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
        "parallel_reasoning_nodes": (
            deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
        ),
        "evidence_verification": (
            deep_beta_evidence_verification if research_mode == "deep_beta" else {}
        ),
        "retrieval_budgets": deep_beta_retrieval_budgets if research_mode == "deep_beta" else {},
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "source_target_objective": source_target_objective,
        "source_target_achieved": source_target_achieved,
        "chart_specs": chart_specs,
        "visual_assets": visual_assets,
        "reasoning_digest": reasoning_digest,
        "verification_matrix": verification_matrix_payload,
        "stage_spans": stage_spans,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
    }
    citations_payload = [asdict(item) for item in citations]
    compact_context_debug = _compact_context_debug(rag_result.context_debug)

    return {
        "metadata": {
            "trace_id": trace_id,
            "run_id": run_id,
            "response_style": "progressive",
            "pipeline": (
                "p2-research-tier2-deep-v1"
                if research_mode == "deep"
                else "p2-research-tier2-deep-beta-v1"
                if research_mode == "deep_beta"
                else "p2-research-tier2-hybrid-v2"
            ),
            "stages": metadata_stages,
            "stage_spans": stage_spans,
            "fallback_used": effective_fallback_used,
            "fallback_reason": fallback_reason or None,
            "source_mode": source_mode,
            "research_mode": research_mode,
            "deep_pass_count": len(deep_pass_summaries),
            "flow_flags": {
                "verification_enabled": legacy_verification_enabled,
                "rule_verification_enabled": rule_verification_enabled,
                "nli_model_enabled": nli_model_enabled,
                "rag_nli_enabled": rag_nli_enabled_runtime,
                "rag_reranker_enabled": effective_rag_reranker_enabled,
                "rag_graphrag_enabled": effective_rag_graphrag_enabled,
            },
            "source_attempts": source_attempts,
            "source_errors": aggregated_errors,
            "degraded_path": degraded_path,
            "retrieval_route": retrieval_route,
            "router_confidence": router_confidence,
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
            "otel_trace_metadata": otel_trace_metadata,
            "otel_export": otel_export_status,
            "deep_research_methodology": deep_research_method,
            "reasoning_steps": deep_beta_reasoning_steps if research_mode == "deep_beta" else [],
            "parallel_reasoning_nodes": (
                deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
            ),
            "evidence_verification": (
                deep_beta_evidence_verification if research_mode == "deep_beta" else {}
            ),
            "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
            "retrieval_budgets": (
                deep_beta_retrieval_budgets
                if research_mode == "deep_beta"
                else planner_hints.get("retrieval_budget", {})
            ),
            "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
            "source_target_objective": source_target_objective,
            "source_target_achieved": source_target_achieved,
            "visual_assets": visual_assets,
            "chart_specs": chart_specs,
            "reasoning_digest": reasoning_digest,
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
        "trace_id": trace_id,
        "run_id": run_id,
        "flow_events": flow_events,
        "planner_trace": planner_trace,
        "retrieval_trace": retrieval_trace,
        "verifier_trace": verifier_trace,
        "trace": trace_bundle,
        "telemetry": telemetry,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
        "policy_action": policy_action,
        "verification_status": verification_status,
        "verification_matrix": verification_matrix_payload,
        "contradiction_summary": contradiction_summary,
        "fallback_used": effective_fallback_used,
        "fallback_reason": fallback_reason or None,
        "source_attempts": source_attempts,
        "source_errors": aggregated_errors,
        "degraded_path": degraded_path,
        "retrieval_route": retrieval_route,
        "router_confidence": router_confidence,
        "query_plan": query_plan,
        "research_mode": research_mode,
        "deep_pass_count": len(deep_pass_summaries),
        "reasoning_steps": deep_beta_reasoning_steps if research_mode == "deep_beta" else [],
        "parallel_reasoning_nodes": (
            deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
        ),
        "evidence_verification": (
            deep_beta_evidence_verification if research_mode == "deep_beta" else {}
        ),
        "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
        "retrieval_budgets": (
            deep_beta_retrieval_budgets
            if research_mode == "deep_beta"
            else planner_hints.get("retrieval_budget", {})
        ),
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "source_target_objective": source_target_objective,
        "source_target_achieved": source_target_achieved,
        "visual_assets": visual_assets,
        "chart_specs": chart_specs,
        "reasoning_digest": reasoning_digest,
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
