from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import secrets
from time import perf_counter
import unicodedata

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse

from clara_ml.agents.careguard import run_careguard_analyze
from clara_ml.agents.council import run_council
from clara_ml.agents.council_intake import run_council_intake
from clara_ml.agents.research_tier2 import run_research_tier2
from clara_ml.agents.scribe_soap import run_scribe_soap
from clara_ml.config import settings
from clara_ml.factcheck import run_fides_lite
from clara_ml.nlp.pii_filter import redact_pii
from clara_ml.observability import format_metrics_prometheus, metrics_collector
from clara_ml.prompts.loader import PromptLoader
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.routing import P1RoleIntentRouter
from clara_ml.streaming.ws import token_stream

app = FastAPI(title="CLARA ML Service", version="0.1.0")
logger = logging.getLogger(__name__)

prompt_loader = PromptLoader(Path(__file__).resolve().parent / "prompts" / "templates")
rag_pipeline = RagPipelineP1()
router = P1RoleIntentRouter()

_LEGAL_GUARD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            (
                r"(\bke\s*don\b|\bdon\s*thuoc\b|\btoa\s*thuoc\b|"
                r"\bthuoc\s*tri\b|\bcho\s*toi\s*thuoc\b|"
                r"\bnen\s*(uong|dung)\s*thuoc\s*gi\b|"
                r"\bprescribe\b|\bprescribed\b|\bprescription\b|"
                r"\bwhat\s+medicine\s+should\s+i\s+take\b|\bwhat\s+should\s+i\s+take\b)"
            ),
            flags=re.IGNORECASE,
        ),
        "prescription_request",
    ),
    (
        re.compile(
            (
                r"(\bchan\s*doan\b|\bmac\s*benh\s*gi\b|\bxac\s*dinh\s*benh\b|"
                r"\bbenh\s*gi\b|\bdiagnos(?:e|is|ing)\b|\bdiagnostic\b)"
            ),
            flags=re.IGNORECASE,
        ),
        "diagnosis_request",
    ),
    (
        re.compile(
            (
                r"(\blieu\b|\bdos(?:e|age)\b|\buong\s*may\b|"
                r"\bbao\s*nhieu\s*(vien|mg|g|mcg|ml)\b|\bmay\s*(vien|mg|g|mcg|ml)\b|"
                r"\b\d+(?:[.,]\d+)?\s*(mg|g|mcg|ml|vien)\s*(moi\s*ngay|\/ngay|daily)?\b|"
                r"\bx\s*\d+\s*(vien|mg|g|mcg|ml)\b|"
                r"\bdose\s*for\s*me\b)"
            ),
            flags=re.IGNORECASE,
        ),
        "dosage_request",
    ),
]
_GREETING_HINTS: tuple[str, ...] = (
    "hi",
    "hello",
    "hey",
    "xin chao",
    "chao",
    "alo",
    "good morning",
    "good afternoon",
    "good evening",
)
_VALID_POLICY_ACTIONS = {"allow", "warn", "block", "escalate"}
_PROTECTED_ML_PATH_PREFIXES = ("/v1/",)
_PROTECTED_ML_PATH_EXACT = {"/metrics", "/metrics/json", "/health/details"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flow_event(*, stage: str, status: str, source_count: int, note: str) -> dict[str, object]:
    return {
        "stage": stage,
        "timestamp": _now_iso(),
        "status": status,
        "source_count": max(int(source_count), 0),
        "note": note,
    }


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _as_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


def _as_threshold(value: object, default: float) -> float:
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return default
    else:
        return default
    return max(0.0, min(1.0, parsed))


def _as_text(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    return default


def _resolve_llm_runtime_from_rag_flow(rag_flow: dict[str, object]) -> dict[str, str]:
    if settings.llm_deepseek_only:
        api_key = _as_text(rag_flow.get("llm_api_key"), "") or settings.deepseek_api_key
        base_url = _as_text(rag_flow.get("llm_base_url"), "") or settings.deepseek_base_url
        model = _as_text(rag_flow.get("llm_model"), "") or settings.deepseek_model
        return {
            "provider": "deepseek",
            "api_key": api_key.strip(),
            "base_url": base_url.strip(),
            "model": model.strip(),
        }

    default_provider = (
        "hitechcloud_gpt53_codex_high" if settings.primary_llm_api_key else "deepseek"
    )
    provider = _as_text(rag_flow.get("llm_provider"), default_provider).lower()
    if provider == "hitechcloud_gpt53_codex_high":
        api_key = _as_text(rag_flow.get("llm_api_key"), "") or settings.primary_llm_api_key
        base_url = (
            _as_text(rag_flow.get("llm_base_url"), "")
            or settings.primary_llm_base_url
            or "https://platform.hitechcloud.one/v1"
        )
        model = (
            _as_text(rag_flow.get("llm_model"), "")
            or settings.primary_llm_model
            or "gpt-5.3-codex-high"
        )
        return {
            "provider": "hitechcloud_gpt53_codex_high",
            "api_key": api_key.strip(),
            "base_url": base_url.strip(),
            "model": model.strip(),
        }

    api_key = _as_text(rag_flow.get("llm_api_key"), "") or settings.deepseek_api_key
    base_url = _as_text(rag_flow.get("llm_base_url"), "") or settings.deepseek_base_url
    model = _as_text(rag_flow.get("llm_model"), "") or settings.deepseek_model
    return {
        "provider": "deepseek",
        "api_key": api_key.strip(),
        "base_url": base_url.strip(),
        "model": model.strip(),
    }


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _query_token_count(query: str) -> int:
    return len([token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]+", query) if token])


def _strip_diacritics(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_guard_texts(query: str) -> tuple[str, str]:
    normalized = " ".join(query.strip().lower().split())
    folded = " ".join(_strip_diacritics(normalized).split())
    return normalized, folded


def _is_general_greeting(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    if not normalized:
        return False
    token_count = _query_token_count(normalized)
    if token_count == 0 or token_count > 5:
        return False
    return any(hint in normalized for hint in _GREETING_HINTS)


def _detect_legal_guard_violation(query: str, *, channel: str = "chat") -> str | None:
    _ = channel
    normalized, folded = _normalize_guard_texts(query)
    if not normalized:
        return None
    for pattern, reason in _LEGAL_GUARD_PATTERNS:
        if pattern.search(normalized) or pattern.search(folded):
            return reason
    return None


def _normalize_policy_action(value: object, *, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _VALID_POLICY_ACTIONS:
            return normalized
    return default


def _requires_internal_key(path: str) -> bool:
    if path in _PROTECTED_ML_PATH_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _PROTECTED_ML_PATH_PREFIXES)


def _internal_key_is_valid(provided: str, expected: str) -> bool:
    value = provided.strip()
    if not value or not expected:
        return False
    return secrets.compare_digest(value, expected)


def _ensure_policy_contract(payload: dict[str, object], *, default_action: str) -> dict[str, object]:
    body = dict(payload)
    policy_action = _normalize_policy_action(body.get("policy_action"), default=default_action)
    body["policy_action"] = policy_action
    metadata_raw = body.get("metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    metadata["policy_action"] = policy_action
    body["metadata"] = metadata
    return body


def _legal_guard_refusal(*, role_hint: str | None, reason: str) -> dict[str, object]:
    safe_role = (
        role_hint
        if role_hint in {"normal", "researcher", "doctor", "admin"}
        else "normal"
    )
    return _ensure_policy_contract(
        {
            "role": safe_role,
            "intent": "medical_policy_refusal",
            "confidence": 1.0,
            "emergency": False,
            "answer": (
                "CLARA không có thẩm quyền kê đơn, chẩn đoán, hoặc chỉ định liều dùng. "
                "Tôi chỉ có thể giải thích tương tác thuốc và thông tin an toàn sử dụng "
                "từ nguồn tham khảo. "
                "Vui lòng liên hệ bác sĩ hoặc dược sĩ để được chỉ định phù hợp."
            ),
            "retrieved_ids": [],
            "model_used": "legal-hard-guard-v1",
            "flow_events": [
                _flow_event(
                    stage="legal_guard",
                    status="blocked",
                    source_count=0,
                    note=f"Blocked by hard policy: {reason}",
                )
            ],
            "guard_reason": reason,
        },
        default_action="block",
    )


def _research_emergency_escalation(*, role_hint: str | None) -> dict[str, object]:
    safe_role = (
        role_hint
        if role_hint in {"normal", "researcher", "doctor", "admin"}
        else "normal"
    )
    return _ensure_policy_contract(
        {
            "role": safe_role,
            "intent": "emergency_triage",
            "confidence": 1.0,
            "emergency": True,
            "answer": (
                "CLARA phát hiện mô tả có dấu hiệu cấp cứu. "
                "Research mode không phù hợp cho tình huống này. "
                "Vui lòng gọi cấp cứu hoặc đến cơ sở y tế gần nhất ngay."
            ),
            "retrieved_ids": [],
            "model_used": "research-emergency-guard-v1",
            "flow_events": [
                _flow_event(
                    stage="emergency_guard",
                    status="escalated",
                    source_count=0,
                    note="Emergency symptoms detected in research flow; escalated immediately.",
                )
            ],
        },
        default_action="escalate",
    )


def _sanitize_upstream_reason(reason: str) -> str:
    normalized = reason.strip().lower()
    if "deepseek_generation_failed" in normalized:
        return "deepseek_generation_unavailable"
    if "deepseek_request_failed" in normalized:
        return "deepseek_request_unavailable"
    if "timeout" in normalized:
        return "upstream_timeout"
    if "connection" in normalized or "connecterror" in normalized:
        return "upstream_connectivity_error"
    return "upstream_unavailable"


def _is_retryable_research_error(exc: Exception) -> bool:
    payload = f"{exc.__class__.__name__}:{exc}".strip().lower()
    return any(
        token in payload
        for token in (
            "deepseek_generation_failed",
            "deepseek_request_failed",
            "timeout",
            "connecterror",
        )
    )


@app.middleware("http")
async def instrument_requests(request: Request, call_next):
    started_at = perf_counter()
    path = request.url.path
    try:
        response = await call_next(request)
    except Exception:
        metrics_collector.record(
            path=path,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            status_code=500,
        )
        raise

    metrics_collector.record(
        path=path,
        latency_ms=(perf_counter() - started_at) * 1000.0,
        status_code=response.status_code,
    )
    return response


@app.middleware("http")
async def enforce_internal_api_key(request: Request, call_next):
    path = request.url.path
    if not _requires_internal_key(path):
        return await call_next(request)

    expected_key = settings.ml_internal_api_key.strip()
    if not expected_key:
        if settings.environment.lower() == "production":
            return JSONResponse(
                status_code=503,
                content={"detail": "ML internal auth misconfigured"},
            )
        return await call_next(request)

    provided_key = request.headers.get("X-ML-Internal-Key", "").strip()
    if not _internal_key_is_valid(provided_key, expected_key):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized internal request"},
        )
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clara-ml"}


@app.get("/health/details")
def health_details() -> dict:
    return {
        "status": "ok",
        "service": "clara-ml",
        "environment": settings.environment,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "router_ready": hasattr(router, "route"),
        "rag_ready": hasattr(rag_pipeline, "run") and rag_pipeline.retriever is not None,
        "prompt_loader_ready": hasattr(prompt_loader, "load"),
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    payload = format_metrics_prometheus(metrics_collector.snapshot())
    return PlainTextResponse(content=payload, media_type="text/plain; version=0.0.4")


@app.get("/metrics/json")
def metrics_json() -> dict:
    return metrics_collector.snapshot()


@app.post("/v1/rag/poc")
def rag_poc(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    pii = redact_pii(query)

    scientific_retrieval_enabled = _as_bool(payload.get("scientific_retrieval_enabled"), False)
    web_retrieval_enabled = _as_bool(payload.get("web_retrieval_enabled"), False)
    file_retrieval_enabled = _as_bool(payload.get("file_retrieval_enabled"), True)
    rag_sources = _as_list(payload.get("rag_sources"))
    uploaded_documents = _as_list(payload.get("uploaded_documents"))

    result = rag_pipeline.run(
        pii.redacted_text,
        scientific_retrieval_enabled=scientific_retrieval_enabled,
        web_retrieval_enabled=web_retrieval_enabled,
        file_retrieval_enabled=file_retrieval_enabled,
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
    )
    return {
        "query": query,
        "redacted_query": pii.redacted_text,
        "pii_flags": pii.flags,
        "retrieved_ids": result.retrieved_ids,
        "answer": result.answer,
        "model_used": result.model_used,
        "context_debug": result.context_debug,
        "flow_events": result.flow_events,
    }


@app.post("/v1/chat/routed")
def routed_chat_infer(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    role_hint = str(payload.get("role", "")).strip().lower() or None
    legal_guard_reason = _detect_legal_guard_violation(query, channel="chat")
    if legal_guard_reason:
        return _legal_guard_refusal(role_hint=role_hint, reason=legal_guard_reason)

    rag_flow_payload = payload.get("rag_flow")
    rag_flow = rag_flow_payload if isinstance(rag_flow_payload, dict) else {}
    llm_runtime = _resolve_llm_runtime_from_rag_flow(rag_flow)
    role_router_enabled = _as_bool(rag_flow.get("role_router_enabled"), True)
    intent_router_enabled = _as_bool(rag_flow.get("intent_router_enabled"), True)
    legacy_verification_enabled = _as_bool(
        rag_flow.get("verification_enabled"),
        bool(settings.rule_verification_enabled),
    )
    rule_verification_enabled = (
        _as_bool(rag_flow.get("rule_verification_enabled"), legacy_verification_enabled)
        if "rule_verification_enabled" in rag_flow
        else legacy_verification_enabled
    )
    verification_enabled = rule_verification_enabled
    deepseek_fallback_enabled = _as_bool(rag_flow.get("deepseek_fallback_enabled"), True)
    low_context_threshold = _as_threshold(rag_flow.get("low_context_threshold"), 0.15)
    scientific_retrieval_enabled = _as_bool(rag_flow.get("scientific_retrieval_enabled"), False)
    web_retrieval_enabled = _as_bool(rag_flow.get("web_retrieval_enabled"), False)
    file_retrieval_enabled = _as_bool(rag_flow.get("file_retrieval_enabled"), True)
    nli_model_enabled = _as_bool(rag_flow.get("nli_model_enabled"), True)
    rag_reranker_enabled_override = _as_optional_bool(rag_flow.get("rag_reranker_enabled"))
    rag_nli_enabled_override = _as_optional_bool(rag_flow.get("rag_nli_enabled"))
    rag_graphrag_enabled_override = _as_optional_bool(rag_flow.get("rag_graphrag_enabled"))
    rag_reranker_enabled = bool(
        settings.rag_reranker_enabled
        if rag_reranker_enabled_override is None
        else rag_reranker_enabled_override
    )
    rag_nli_enabled = bool(
        settings.rag_nli_enabled if rag_nli_enabled_override is None else rag_nli_enabled_override
    )
    rag_nli_enabled = bool(nli_model_enabled and rag_nli_enabled)
    rag_graphrag_enabled = bool(
        settings.rag_graphrag_enabled
        if rag_graphrag_enabled_override is None
        else rag_graphrag_enabled_override
    )
    rag_sources = _as_list(
        rag_flow.get("rag_sources") if "rag_sources" in rag_flow else payload.get("rag_sources")
    )
    uploaded_documents = _as_list(
        rag_flow.get("uploaded_documents")
        if "uploaded_documents" in rag_flow
        else payload.get("uploaded_documents")
    )
    pii = redact_pii(query)
    route = router.route(pii.redacted_text, role_hint=role_hint)

    if route.emergency:
        return _ensure_policy_contract(
            {
                "role": route.role,
                "intent": route.intent,
                "confidence": route.confidence,
                "emergency": True,
                "answer": (
                    "Possible emergency detected. Call local emergency services immediately "
                    "or go to the nearest ER."
                ),
                "retrieved_ids": [],
                "model_used": "emergency-fastpath-v1",
                "flow_events": [
                    _flow_event(
                        stage="emergency_fastpath",
                        status="completed",
                        source_count=0,
                        note="Emergency route triggered; retrieval and generation bypassed.",
                    )
                ],
                "flow_applied": {
                    "role_router_enabled": role_router_enabled,
                    "intent_router_enabled": intent_router_enabled,
                    "verification_enabled": verification_enabled,
                    "rule_verification_enabled": rule_verification_enabled,
                    "deepseek_fallback_enabled": deepseek_fallback_enabled,
                    "low_context_threshold": low_context_threshold,
                    "scientific_retrieval_enabled": scientific_retrieval_enabled,
                    "web_retrieval_enabled": web_retrieval_enabled,
                    "file_retrieval_enabled": file_retrieval_enabled,
                    "nli_model_enabled": nli_model_enabled,
                    "rag_reranker_enabled": rag_reranker_enabled,
                    "rag_nli_enabled": rag_nli_enabled,
                    "rag_graphrag_enabled": rag_graphrag_enabled,
                },
            },
            default_action="escalate",
        )

    if not role_router_enabled:
        route.role = (
            role_hint if role_hint in {"normal", "researcher", "doctor", "admin"} else "normal"
        )

    if not intent_router_enabled:
        default_by_role = {
            "normal": "symptom_triage",
            "researcher": "evidence_review",
            "doctor": "doctor_case_review",
            "admin": "evidence_review",
        }
        route.intent = default_by_role.get(route.role, "symptom_triage")
        route.confidence = min(route.confidence, 0.6)

    if (
        route.intent == "general_guidance"
        and _is_general_greeting(pii.redacted_text)
        and not settings.deepseek_required
        and deepseek_fallback_enabled
    ):
        return _ensure_policy_contract(
            {
                "role": route.role,
                "intent": route.intent,
                "confidence": route.confidence,
                "emergency": False,
                "answer": (
                    "Chào bạn, mình là CLARA. "
                    "Bạn có thể gửi danh sách thuốc hoặc câu hỏi về tương tác thuốc "
                    "để mình hỗ trợ an toàn."
                ),
                "retrieved_ids": [],
                "model_used": "smalltalk-fastpath-v1",
                "flow_events": [
                    _flow_event(
                        stage="smalltalk_fastpath",
                        status="completed",
                        source_count=0,
                        note="Greeting intent detected; bypassed retrieval and generation.",
                    )
                ],
                "flow_applied": {
                    "role_router_enabled": role_router_enabled,
                    "intent_router_enabled": intent_router_enabled,
                    "verification_enabled": verification_enabled,
                    "rule_verification_enabled": rule_verification_enabled,
                    "deepseek_fallback_enabled": deepseek_fallback_enabled,
                    "low_context_threshold": low_context_threshold,
                    "scientific_retrieval_enabled": False,
                    "web_retrieval_enabled": False,
                    "file_retrieval_enabled": False,
                    "nli_model_enabled": nli_model_enabled,
                    "rag_reranker_enabled": rag_reranker_enabled,
                    "rag_nli_enabled": rag_nli_enabled,
                    "rag_graphrag_enabled": rag_graphrag_enabled,
                    "rag_sources_count": len(rag_sources),
                    "uploaded_documents_count": len(uploaded_documents),
                    "retrieval_profile": "smalltalk_fastpath",
                    "query_token_count": _query_token_count(pii.redacted_text),
                },
            },
            default_action="allow",
        )

    retrieval_profile = "standard"
    query_token_count = _query_token_count(pii.redacted_text)
    adjusted_scientific_retrieval_enabled = scientific_retrieval_enabled
    adjusted_web_retrieval_enabled = web_retrieval_enabled
    adjusted_file_retrieval_enabled = file_retrieval_enabled

    if route.intent == "general_guidance" and query_token_count <= 5:
        retrieval_profile = "smalltalk_minimal"
        adjusted_scientific_retrieval_enabled = False
        adjusted_web_retrieval_enabled = False
        adjusted_file_retrieval_enabled = bool(uploaded_documents)
    elif route.intent == "lifestyle_guidance" and route.role == "normal":
        retrieval_profile = "lifestyle_grounded"
        adjusted_web_retrieval_enabled = False

    degraded_mode = False
    degraded_reason = ""
    try:
        rag_result = rag_pipeline.run(
            pii.redacted_text,
            low_context_threshold=low_context_threshold,
            deepseek_fallback_enabled=deepseek_fallback_enabled,
            scientific_retrieval_enabled=adjusted_scientific_retrieval_enabled,
            web_retrieval_enabled=adjusted_web_retrieval_enabled,
            file_retrieval_enabled=adjusted_file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
            strict_deepseek_required=settings.deepseek_required,
            rag_reranker_enabled=rag_reranker_enabled_override,
            rag_graphrag_enabled=rag_graphrag_enabled_override,
            llm_runtime=llm_runtime,
        )
    except Exception as exc:
        if settings.deepseek_required or not deepseek_fallback_enabled:
            raise HTTPException(
                status_code=503,
                detail=f"deepseek_required_unavailable:{exc.__class__.__name__}",
            ) from exc
        degraded_mode = True
        degraded_reason = exc.__class__.__name__
        rag_result = rag_pipeline.run(
            pii.redacted_text,
            low_context_threshold=low_context_threshold,
            deepseek_fallback_enabled=True,
            scientific_retrieval_enabled=False,
            web_retrieval_enabled=False,
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
            strict_deepseek_required=False,
            rag_reranker_enabled=rag_reranker_enabled_override,
            rag_graphrag_enabled=rag_graphrag_enabled_override,
            llm_runtime=llm_runtime,
        )
    factcheck = None
    if rule_verification_enabled:
        try:
            factcheck = run_fides_lite(
                answer=rag_result.answer,
                retrieved_context=rag_result.retrieved_context,
                nli_enabled=rag_nli_enabled,
            )
        except TypeError as type_exc:
            if "unexpected keyword argument" not in str(type_exc):
                raise
            factcheck = run_fides_lite(
                answer=rag_result.answer,
                retrieved_context=rag_result.retrieved_context,
            )
    answer = rag_result.answer
    if factcheck and factcheck.severity == "high":
        answer = (
            f"{rag_result.answer}\n\n"
            "Lưu ý an toàn: một số nội dung chưa đủ bằng chứng từ tài liệu truy xuất. "
            "Bạn nên đối chiếu thêm với bác sĩ/dược sĩ trước khi áp dụng."
        )

    flow_events = list(rag_result.flow_events)
    if retrieval_profile != "standard":
        flow_events.insert(
            0,
            _flow_event(
                stage="retrieval_policy",
                status="completed",
                source_count=0,
                note=(
                    f"Applied retrieval profile={retrieval_profile}; "
                    f"scientific={adjusted_scientific_retrieval_enabled}, "
                    f"web={adjusted_web_retrieval_enabled}, "
                    f"file={adjusted_file_retrieval_enabled}."
                ),
            ),
        )

    if degraded_mode:
        flow_events.append(
            _flow_event(
                stage="degraded_recovery",
                status="completed",
                source_count=len(rag_result.retrieved_ids),
                note=(
                    "Recovered from routed pipeline error by disabling external retrieval "
                    f"and verification-heavy path. error={degraded_reason}"
                ),
            )
        )
    if rule_verification_enabled:
        if factcheck is not None:
            flow_events.append(
                _flow_event(
                    stage="verification",
                    status=factcheck.verdict,
                    source_count=factcheck.evidence_count,
                    note=factcheck.note,
                )
            )
        else:
            flow_events.append(
                _flow_event(
                    stage="verification",
                    status="skipped",
                    source_count=0,
                    note="Verification was enabled but no factcheck result was produced.",
                )
            )

    default_action = "allow"
    if degraded_mode or rag_result.model_used.startswith("local-synth"):
        default_action = "warn"
    if factcheck and factcheck.severity == "high":
        default_action = "warn"

    return _ensure_policy_contract(
        {
            "role": route.role,
            "intent": route.intent,
            "confidence": route.confidence,
            "emergency": False,
            "answer": answer,
            "retrieved_ids": rag_result.retrieved_ids,
            "model_used": rag_result.model_used,
            "factcheck": factcheck.as_dict() if factcheck else None,
            "context_debug": rag_result.context_debug,
            "flow_events": flow_events,
            "flow_applied": {
                "role_router_enabled": role_router_enabled,
                "intent_router_enabled": intent_router_enabled,
                "verification_enabled": verification_enabled,
                "rule_verification_enabled": rule_verification_enabled,
                "deepseek_fallback_enabled": deepseek_fallback_enabled,
                "low_context_threshold": low_context_threshold,
                "scientific_retrieval_enabled": adjusted_scientific_retrieval_enabled,
                "web_retrieval_enabled": adjusted_web_retrieval_enabled,
                "file_retrieval_enabled": adjusted_file_retrieval_enabled,
                "nli_model_enabled": nli_model_enabled,
                "rag_reranker_enabled": rag_reranker_enabled,
                "rag_nli_enabled": rag_nli_enabled,
                "rag_graphrag_enabled": rag_graphrag_enabled,
                "rag_sources_count": len(rag_sources),
                "uploaded_documents_count": len(uploaded_documents),
                "retrieval_profile": retrieval_profile,
                "query_token_count": query_token_count,
                "llm_provider": llm_runtime.get("provider", "deepseek"),
                "llm_model": llm_runtime.get("model", ""),
                "llm_base_url": llm_runtime.get("base_url", ""),
            },
        },
        default_action=default_action,
    )


def _labs_rows_to_numeric_map(rows: object) -> dict[str, float]:
    if not isinstance(rows, list):
        return {}
    normalized: dict[str, float] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower()
        value = str(item.get("value", "")).strip()
        if not name or not value:
            continue
        try:
            normalized[name] = float(value)
        except ValueError:
            continue
    return normalized


@app.post("/v1/research/tier2")
def research_tier2(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    role_hint = str(payload.get("role", "")).strip().lower() or None
    route = router.route(query, role_hint=role_hint)
    if route.emergency:
        return _research_emergency_escalation(role_hint=route.role)
    legal_guard_reason = _detect_legal_guard_violation(query, channel="research")
    if legal_guard_reason:
        return _legal_guard_refusal(role_hint=role_hint, reason=legal_guard_reason)
    try:
        result = run_research_tier2(payload)
        if isinstance(result, dict):
            return _ensure_policy_contract(result, default_action="allow")
        return _ensure_policy_contract({"answer": str(result)}, default_action="allow")
    except Exception as exc:  # pragma: no cover - defensive fail-soft guard
        if _is_retryable_research_error(exc):
            try:
                retry_result = run_research_tier2(payload)
                if isinstance(retry_result, dict):
                    return _ensure_policy_contract(retry_result, default_action="allow")
                return _ensure_policy_contract({"answer": str(retry_result)}, default_action="allow")
            except Exception as retry_exc:  # pragma: no cover - defensive retry guard
                exc = retry_exc
        detail = str(exc).strip()
        reason = exc.__class__.__name__
        if detail:
            reason = f"{reason}:{detail[:180]}"
        logger.exception("research_tier2 upstream failure: %s", reason)
        # Do not return local fallback for research tier2.
        # Caller should receive explicit upstream failure and retry.
        raise HTTPException(
            status_code=503,
            detail=f"research_upstream_failed:{_sanitize_upstream_reason(reason)}",
        ) from exc


@app.post("/v1/careguard/analyze")
def careguard_analyze(payload: dict) -> dict:
    return run_careguard_analyze(payload)


@app.post("/v1/scribe/soap")
def scribe_soap(payload: dict) -> dict:
    transcript = str(payload.get("transcript", "")).strip()
    return run_scribe_soap(transcript)


@app.post("/v1/council/run")
def council_run(payload: dict) -> dict:
    return run_council(payload)


@app.post("/v1/council/consult")
def council_consult(payload: dict) -> dict:
    transcript = str(payload.get("transcript", "")).strip()
    specialists = payload.get("specialists")
    specialist_count = payload.get("specialist_count")

    merged_payload: dict[str, object] = {}
    intake_summary: dict[str, object] | None = None

    if transcript:
        intake_summary = run_council_intake(transcript=transcript)
        council_payload = intake_summary.get("council_payload")
        if isinstance(council_payload, dict):
            merged_payload.update(council_payload)
        else:
            merged_payload["symptoms"] = intake_summary.get("symptoms", [])
            labs_value = intake_summary.get("labs", {})
            if isinstance(labs_value, dict):
                merged_payload["labs"] = labs_value
            else:
                merged_payload["labs"] = _labs_rows_to_numeric_map(labs_value)
            merged_payload["medications"] = intake_summary.get("medications", [])
            merged_payload["history"] = intake_summary.get("history", [])

    # User-provided fields override extracted intake if present.
    for key in ("symptoms", "labs", "medications", "history"):
        if key in payload and payload.get(key) not in (None, "", []):
            merged_payload[key] = payload.get(key)

    if specialists is not None:
        merged_payload["specialists"] = specialists
    if specialist_count is not None:
        merged_payload["specialist_count"] = specialist_count

    if not merged_payload:
        raise HTTPException(
            status_code=400,
            detail="Missing consult input. Provide transcript or structured clinical fields.",
        )

    result = run_council(merged_payload)
    if intake_summary is not None:
        result["intake"] = {
            "model_used": intake_summary.get("model_used"),
            "warnings": intake_summary.get("warnings", []),
            "missing_fields": intake_summary.get("missing_fields", []),
            "field_confidence": intake_summary.get("field_confidence", {}),
        }
    return result


@app.get("/v1/prompts/{role}/{intent}")
def get_prompt(role: str, intent: str) -> dict:
    return prompt_loader.load(role, intent)


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket) -> None:
    expected_key = settings.ml_internal_api_key.strip()
    if expected_key:
        provided_key = websocket.headers.get("x-ml-internal-key", "").strip()
        if not _internal_key_is_valid(provided_key, expected_key):
            await websocket.close(code=1008)
            return
    elif settings.environment.lower() == "production":
        await websocket.close(code=1011)
        return

    await websocket.accept()
    incoming = await websocket.receive_text()
    async for token in token_stream(incoming):
        await websocket.send_json({"token": token})
    await websocket.send_json({"event": "done"})
    await websocket.close()


@app.post("/v1/council/intake")
async def council_intake(
    transcript: str = Form(default=""),
    audio_file: UploadFile | None = File(default=None),
) -> dict:
    transcript_text = transcript.strip()
    audio_bytes: bytes | None = None
    audio_filename = "audio-input"
    audio_content_type = "application/octet-stream"

    if audio_file is not None and audio_file.filename:
        audio_bytes = await audio_file.read()
        audio_filename = audio_file.filename or audio_filename
        audio_content_type = audio_file.content_type or audio_content_type

    if not transcript_text and not audio_bytes:
        raise HTTPException(status_code=400, detail="Either transcript or audio_file is required.")

    try:
        return run_council_intake(
            transcript=transcript_text,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            audio_content_type=audio_content_type,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
