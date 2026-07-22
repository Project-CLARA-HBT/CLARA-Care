import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.compliance.service import ComplianceService
from clara_api.compliance.transfer import LLM_PROCESSOR, LLM_PURPOSE
from clara_api.core.attribution import (
    attach_attribution,
    build_attribution,
    normalize_source_errors,
    normalize_source_used,
)
from clara_api.core.config import get_settings
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.flow import get_chat_flow_event_persister
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import User
from clara_api.db.session import get_db
from clara_api.schemas import ChatRequest, ChatResponse, RagFlowConfig

router = APIRouter()
logger = logging.getLogger(__name__)


_SAFE_MODE_NOTICE = (
    "Hệ thống truy xuất chuyên sâu đang bận hoặc tạm thời không kết nối được nguồn RAG. "
    "Tạm thời dùng chế độ an toàn: bạn nên ưu tiên phác đồ chính thống, "
    "đối chiếu tương tác thuốc quan trọng, "
    "và trao đổi bác sĩ khi có bệnh nền hoặc dấu hiệu nặng."
)
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


def _is_general_greeting(message: str) -> bool:
    normalized = " ".join(str(message).lower().split())
    if not normalized:
        return False
    token_count = len([token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]+", normalized) if token])
    if token_count == 0 or token_count > 5:
        return False
    return any(hint in normalized for hint in _GREETING_HINTS)


def _build_chat_attribution(
    ml_response: dict[str, Any],
    rag_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    active_sources: list[dict[str, str]] = []
    for source in rag_sources:
        if not isinstance(source, dict):
            continue
        if source.get("enabled") is False:
            continue
        source_id = str(source.get("id", "")).strip()
        source_name = str(source.get("name", "")).strip()
        if not source_id and not source_name:
            continue
        item: dict[str, str] = {
            "id": source_id or source_name.lower().replace(" ", "_"),
            "name": source_name or source_id,
        }
        raw_category = source.get("category")
        if isinstance(raw_category, str) and raw_category.strip():
            item["category"] = raw_category.strip()
        active_sources.append(item)

    context_debug = ml_response.get("context_debug")
    context_debug_obj = context_debug if isinstance(context_debug, dict) else {}
    retrieval_trace_obj = (
        context_debug_obj.get("retrieval_trace")
        if isinstance(context_debug_obj.get("retrieval_trace"), dict)
        else {}
    )
    search_phase_obj = (
        retrieval_trace_obj.get("search_phase")
        if isinstance(retrieval_trace_obj.get("search_phase"), dict)
        else {}
    )
    raw_source_errors = (
        ml_response.get("source_errors")
        or context_debug_obj.get("source_errors")
        or retrieval_trace_obj.get("source_errors")
        or search_phase_obj.get("source_errors")
        or {}
    )
    source_errors = normalize_source_errors(raw_source_errors)
    source_used = normalize_source_used(
        ml_response.get("source_used")
        or context_debug_obj.get("source_used")
        or retrieval_trace_obj.get("source_used")
        or search_phase_obj.get("source_used")
        or []
    )
    source_attempts = search_phase_obj.get("source_attempts")
    if isinstance(source_attempts, list):
        for attempt in source_attempts:
            if not isinstance(attempt, dict):
                continue
            raw_source_name = (
                attempt.get("source")
                or attempt.get("provider")
                or attempt.get("connector")
                or attempt.get("name")
            )
            if raw_source_name is None:
                continue
            source_name = str(raw_source_name).strip().lower()
            if source_name and source_name not in source_used:
                source_used.append(source_name)
    fallback_used = bool(
        ml_response.get("safe_mode_used")
        or ml_response.get("fallback_used")
        or ml_response.get("fallback_reason")
        or str(ml_response.get("model_used") or "").startswith("api-safe-")
        or str(ml_response.get("model_used") or "").startswith("api-local-synth-")
    )
    mode = "safe_mode" if fallback_used else "evidence_rag"

    return build_attribution(
        channel="chat",
        mode=mode,
        sources=active_sources,
        citations_payload=ml_response.get("citations"),
        source_used=source_used,
        source_errors=source_errors,
        fallback_used=fallback_used,
    )


def _safe_chat_fallback(message: str, role: str, reason: str) -> dict[str, Any]:
    if _is_general_greeting(message):
        return {
            "role": role,
            "intent": "general_guidance",
            "confidence": 0.9,
            "emergency": False,
            "answer": (
                "Chào bạn, CLARA đang sẵn sàng. "
                "Bạn có thể gửi danh sách thuốc hoặc câu hỏi về tương tác thuốc để mình hỗ trợ."
            ),
            "retrieved_ids": [],
            "model_used": "api-safe-smalltalk-v1",
            "fallback_reason": reason,
            "query_echo": message,
        }

    return {
        "role": role,
        "intent": "general_guidance",
        "confidence": 0.35,
        "emergency": False,
        "answer": _SAFE_MODE_NOTICE,
        "retrieved_ids": [],
        "model_used": "api-safe-fallback-v1",
        "fallback_reason": reason,
        "query_echo": message,
    }


_CROSS_BORDER_DEGRADED_NOTICE = (
    "Bạn chưa đồng ý cho phép xử lý dữ liệu xuyên biên giới, nên CLARA tạm thời "
    "dùng chế độ nội địa rút gọn (degraded) và KHÔNG gửi nội dung nhận dạng được "
    "ra mô hình đặt ngoài Việt Nam. Bạn nên ưu tiên phác đồ chính thống, đối chiếu "
    "tương tác thuốc quan trọng, và trao đổi bác sĩ/dược sĩ khi có bệnh nền hoặc dấu "
    "hiệu nặng. Để nhận câu trả lời đầy đủ hơn, bạn có thể bật đồng ý xử lý xuyên "
    "biên giới trong Trung tâm quyền riêng tư."
)


def _resolve_user_id(db: Session, token: TokenPayload) -> int | None:
    """Resolve the numeric user id for the authenticated subject.

    Returns ``None`` when no matching user row exists; the cross-border guard
    treats a missing subject as "no consent" and degrades, which fails closed
    for processing while keeping safety surfaces intact.
    """

    user_id = db.execute(select(User.id).where(User.email == token.sub)).scalar_one_or_none()
    return int(user_id) if user_id is not None else None


def _cross_border_degraded_payload(message: str, role: str, reason: str) -> dict[str, Any]:
    """Local deterministic answer used when cross-border transfer is gated off.

    No identifiable content is transmitted offshore: this payload is built
    entirely in-process. ``model_used`` uses the ``local-synth-*`` sentinel so
    the response-envelope disclosure labels it ``is_fallback=true`` / degraded
    (Req 1.4, 4.2 / Correctness Property 2).
    """

    return {
        "role": role,
        "intent": "general_guidance",
        "confidence": 0.3,
        "emergency": False,
        "answer": _CROSS_BORDER_DEGRADED_NOTICE,
        "retrieved_ids": [],
        "model_used": "local-synth-degraded-v1",
        "fallback_reason": f"cross_border_gated:{reason}",
        "query_echo": message,
        "safe_mode_used": True,
    }


def _decorate_safe_mode_answer(answer: str) -> str:
    cleaned = answer.strip()
    if not cleaned:
        return _SAFE_MODE_NOTICE
    if cleaned.startswith(_SAFE_MODE_NOTICE):
        return cleaned
    return f"{_SAFE_MODE_NOTICE}\n\n{cleaned}"


def _sanitize_chat_reply(answer: str) -> str:
    cleaned = str(answer or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(
        r"hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời\.?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:^|\n)\s*security\s*\n+\s*ma trận quyết định an toàn[\s\S]*?(?=\n##\s|\n#\s|$)",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:^|\n)\s*ai\s*verified[\s\S]*?(?=\n##\s|\n#\s|$)",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:^|\n)\s*\|?\s*claim\s*\|?\s*verdict\s*\|?\s*confidence[^\n]*\n(?:\s*\|?.*?\n){1,30}",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"```mermaid[\s\S]*?```", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _post_to_ml(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    request_kwargs: dict[str, Any] = {"json": payload, "timeout": timeout_seconds}
    if headers:
        request_kwargs["headers"] = headers
    response = httpx.post(url, **request_kwargs)
    if response.status_code >= 500:
        raise httpx.HTTPStatusError(
            f"ML upstream 5xx: {response.status_code}",
            request=response.request,
            response=response,
        )
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"ML upstream 4xx: {response.status_code}",
            request=response.request,
            response=response,
        )
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("ml_unexpected_payload")
    return data


def _safe_mode_payload(
    message: str,
    role: str,
    rag_flow: RagFlowConfig,
    rag_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    base_flow = rag_flow.model_dump()
    base_flow.update(
        {
            "rule_verification_enabled": False,
            "nli_model_enabled": False,
            "rag_reranker_enabled": False,
            "rag_nli_enabled": False,
            "rag_graphrag_enabled": False,
            "deepseek_fallback_enabled": True,
            "scientific_retrieval_enabled": False,
            "web_retrieval_enabled": False,
            "file_retrieval_enabled": True,
            # Force low-context branch to avoid waiting for heavy retrieval branches.
            "low_context_threshold": 1.0,
        }
    )
    return {
        "query": message,
        "role": role,
        "rag_flow": base_flow,
        "rag_sources": rag_sources,
    }


def _call_ml_service(
    message: str,
    role: str,
    rag_flow: RagFlowConfig,
    rag_sources: list[dict[str, Any]],
    *,
    protocol: str = "clinical_answer",
    clinical_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/routed"
    request_payload = {
        "query": message,
        "role": role,
        "rag_flow": rag_flow.model_dump(),
        "rag_sources": rag_sources,
        "protocol": protocol,
        "clinical_context": clinical_context,
    }
    safe_mode_timeout = max(3.0, min(settings.ml_service_timeout_seconds, 12.0))

    primary_reason = ""
    try:
        data = _post_to_ml(url, request_payload, settings.ml_service_timeout_seconds)
        return data
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        primary_reason = f"ml_unavailable:{exc.__class__.__name__}"
    except httpx.HTTPError as exc:
        upstream_status = exc.response.status_code if exc.response is not None else None
        if upstream_status is None:
            primary_reason = f"ml_http_error:{exc.__class__.__name__}"
        elif upstream_status >= 500:
            primary_reason = f"ml_upstream_5xx:{upstream_status}"
        else:
            primary_reason = f"ml_upstream_4xx:{upstream_status}"
    except ValueError as exc:
        primary_reason = f"ml_invalid_json:{exc.__class__.__name__}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        primary_reason = f"ml_unexpected_exception:{exc.__class__.__name__}"

    if settings.deepseek_strict_mode:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"deepseek_required_unavailable:{primary_reason}",
        )

    safe_mode_reason = ""
    try:
        safe_mode_data = _post_to_ml(
            url,
            {
                **_safe_mode_payload(message, role, rag_flow, rag_sources),
                "protocol": protocol,
                "clinical_context": clinical_context,
            },
            safe_mode_timeout,
        )
        answer = safe_mode_data.get("answer")
        if isinstance(answer, str):
            safe_mode_data["answer"] = _decorate_safe_mode_answer(answer)
        safe_mode_data["safe_mode_used"] = True
        safe_mode_data["fallback_reason"] = f"{primary_reason};safe_mode_recovered"
        model_used = safe_mode_data.get("model_used")
        if not isinstance(model_used, str) or not model_used.strip():
            safe_mode_data["model_used"] = "deepseek-v3.2-safe-mode"
        return safe_mode_data
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        safe_mode_reason = f"safe_mode_unavailable:{exc.__class__.__name__}"
    except httpx.HTTPError as exc:
        upstream_status = exc.response.status_code if exc.response is not None else None
        if upstream_status is None:
            safe_mode_reason = f"safe_mode_http_error:{exc.__class__.__name__}"
        elif upstream_status >= 500:
            safe_mode_reason = f"safe_mode_upstream_5xx:{upstream_status}"
        else:
            safe_mode_reason = f"safe_mode_upstream_4xx:{upstream_status}"
    except ValueError as exc:
        safe_mode_reason = f"safe_mode_invalid_json:{exc.__class__.__name__}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        safe_mode_reason = f"safe_mode_unexpected_exception:{exc.__class__.__name__}"

    composed_reason = primary_reason
    if safe_mode_reason:
        composed_reason = f"{primary_reason};{safe_mode_reason}"
    return _safe_chat_fallback(message, role, reason=composed_reason)


def _load_rag_runtime(db: Session) -> tuple[RagFlowConfig, list[dict[str, Any]]]:
    try:
        control_tower = get_control_tower_config_service().load(db)
        rag_flow = control_tower.rag_flow
        rag_sources = [item.model_dump() for item in control_tower.rag_sources]
        return rag_flow, rag_sources
    except Exception as exc:  # pragma: no cover - defensive path for runtime resilience
        logger.exception("Failed to load control tower config")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"control_tower_config_unavailable:{exc.__class__.__name__}",
        ) from exc


def _build_cross_border_degraded_response(
    payload: ChatRequest,
    role: str,
    rag_sources: list[dict[str, Any]],
    db: Session,
    settings: Any,
    reason: str,
) -> dict[str, object]:
    """Assemble the chat response for a cross-border-gated (degraded) turn.

    Mirrors the shape of the normal/fallback response so clients render it
    identically, but the answer is the local deterministic notice and the turn
    is flagged ``fallback=True`` with a ``cross_border_gated:*`` reason. No
    offshore call is made, so no identifiable content leaves the country
    (Req 4.2 / Property P2).
    """

    degraded_ml = _cross_border_degraded_payload(payload.message, role, reason)
    response_payload: dict[str, object] = {
        "message": payload.message,
        "reply": degraded_ml["answer"],
        "role": role,
        "intent": degraded_ml.get("intent"),
        "confidence": degraded_ml.get("confidence"),
        "emergency": degraded_ml.get("emergency"),
        "model_used": degraded_ml.get("model_used"),
        "retrieved_ids": degraded_ml.get("retrieved_ids", []),
        "ml": degraded_ml,
        "fallback": True,
        "fallback_reason": str(degraded_ml.get("fallback_reason")),
    }
    attribution = _build_chat_attribution(degraded_ml, rag_sources)
    disclosure = ComplianceService(db, settings=settings).model_disclosure(
        degraded_ml.get("model_used")
    )
    if disclosure is not None:
        response_payload["ai_disclosure"] = disclosure
    return attach_attribution(response_payload, attribution=attribution)


@router.post("/", response_model=ChatResponse, response_model_exclude_none=True)
@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
def chat_completion(
    payload: ChatRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    rag_flow, rag_sources = _load_rag_runtime(db)

    # Cross-border transfer gate (Req 4.2 / Correctness Property P2): when
    # COMPLIANCE_CROSS_BORDER_GATING_ENABLED is on and the user has not granted
    # cross_border_processing consent, the offshore model MUST NOT receive the
    # user's identifiable query. We consult the guard before any outbound ML
    # call and degrade to a local deterministic answer labeled degraded. The
    # whole block is behind the flag so that with gating off no new code path
    # runs and the request is byte-equivalent to baseline (Property P6).
    if settings.compliance_cross_border_gating_enabled:
        compliance = ComplianceService(db, settings=settings)
        user_id = _resolve_user_id(db, token)
        transfer = compliance.outbound_guard(user_id=user_id)
        # No-PII transfer event (Req 4.4 / Property P5): record the processor
        # identity, purpose, and an opaque user ref for the outbound offshore
        # decision — never the query text. ``allowed`` distinguishes a payload
        # transmitted offshore ("sent") from a consent-blocked degrade
        # ("blocked"). Inside the flag block so flags-off side effects are
        # byte-equivalent to baseline (Property P6).
        compliance.record_transfer(
            user_id=user_id,
            processor=LLM_PROCESSOR,
            purpose=LLM_PURPOSE,
            allowed=transfer.allow_cross_border,
        )
        if not transfer.allow_cross_border:
            return _build_cross_border_degraded_response(
                payload, token.role, rag_sources, db, settings, transfer.reason
            )

    try:
        ml_response = _call_ml_service(
            payload.message,
            token.role,
            rag_flow,
            rag_sources,
            protocol=payload.protocol,
            clinical_context=payload.clinical_context,
        )
        model_used = ml_response.get("model_used")
        if (
            settings.deepseek_strict_mode
            and isinstance(model_used, str)
            and model_used.startswith("local-synth")
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="deepseek_required_unavailable:local_synthesis_blocked",
            )

        if (
            not settings.deepseek_strict_mode
            and isinstance(model_used, str)
            and model_used.startswith("local-synth")
        ):
            ml_response["upstream_model_used"] = model_used
            if _is_general_greeting(payload.message):
                ml_response["answer"] = (
                    "Chào bạn, CLARA đang sẵn sàng. "
                    "Bạn có thể gửi danh sách thuốc hoặc câu hỏi về tương tác thuốc để mình hỗ trợ."
                )
                ml_response["model_used"] = "api-safe-smalltalk-v1"
            else:
                ml_response["answer"] = (
                    "Hệ thống đang ưu tiên chế độ an toàn do phản hồi từ mô hình nền chưa ổn định. "
                    "Bạn vui lòng thử lại sau ít phút. Nếu có dấu hiệu nặng hoặc bệnh nền, "
                    "hãy liên hệ bác sĩ/duợc sĩ ngay."
                )
                ml_response["model_used"] = "api-local-synth-guard-v1"
            ml_response["safe_mode_used"] = True
            ml_response["fallback_reason"] = str(
                ml_response.get("fallback_reason") or "ml_local_synthesis_guard"
            )

        if not isinstance(ml_response.get("citations"), list):
            ml_response["citations"] = []

        reply = ml_response.get("answer")
        if settings.deepseek_strict_mode and (not isinstance(reply, str) or not reply.strip()):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="deepseek_required_unavailable:missing_answer",
            )

        if not isinstance(reply, str):
            reply = _safe_chat_fallback(
                payload.message,
                token.role,
                reason="ml_unexpected_payload:missing_answer",
            )["answer"]
        elif not reply.strip():
            reply = _safe_chat_fallback(
                payload.message,
                token.role,
                reason="ml_unexpected_payload:blank_answer",
            )["answer"]
        reply = _sanitize_chat_reply(reply)
        if not reply:
            reply = _safe_chat_fallback(
                payload.message,
                token.role,
                reason="ml_unexpected_payload:blank_after_sanitize",
            )["answer"]
        ml_response["answer"] = reply

        resolved_role = ml_response.get("role")
        if not isinstance(resolved_role, str) or not resolved_role:
            resolved_role = token.role

        try:
            get_chat_flow_event_persister().persist(
                token=token,
                role=resolved_role,
                ml_response=ml_response,
            )
        except Exception:  # pragma: no cover - do not break answer flow for telemetry writes
            logger.exception("Failed to persist chat flow event")

        attribution = _build_chat_attribution(ml_response, rag_sources)
        retrieved_ids = ml_response.get("retrieved_ids")
        if not isinstance(retrieved_ids, list):
            retrieved_ids = []
        fallback_reason = ml_response.get("fallback_reason")
        fallback_used = bool(attribution.get("fallback_used"))

        response_payload = {
            "message": payload.message,
            "reply": reply,
            "role": resolved_role,
            "intent": ml_response.get("intent"),
            "confidence": ml_response.get("confidence"),
            "emergency": ml_response.get("emergency"),
            "model_used": ml_response.get("model_used"),
            "retrieved_ids": retrieved_ids,
            "ml": ml_response,
            "fallback": fallback_used,
        }
        if isinstance(fallback_reason, str) and fallback_reason.strip():
            response_payload["fallback_reason"] = fallback_reason.strip()
        disclosure = ComplianceService(db, settings=settings).model_disclosure(
            ml_response.get("model_used")
        )
        if disclosure is not None:
            response_payload["ai_disclosure"] = disclosure
        return attach_attribution(response_payload, attribution=attribution)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - final defensive guard
        logger.exception("Chat endpoint failed unexpectedly")
        if settings.deepseek_strict_mode:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"deepseek_required_unavailable:chat_internal_error:{exc.__class__.__name__}",
            ) from exc

        fallback_ml = _safe_chat_fallback(
            payload.message,
            token.role,
            reason=f"chat_internal_error:{exc.__class__.__name__}",
        )
        fallback_reason = fallback_ml.get("fallback_reason")
        response_payload = {
            "message": payload.message,
            "reply": str(fallback_ml.get("answer", "")).strip() or _SAFE_MODE_NOTICE,
            "role": token.role,
            "intent": fallback_ml.get("intent"),
            "confidence": fallback_ml.get("confidence"),
            "emergency": fallback_ml.get("emergency"),
            "model_used": fallback_ml.get("model_used"),
            "retrieved_ids": fallback_ml.get("retrieved_ids", []),
            "ml": fallback_ml,
            "fallback": True,
        }
        if isinstance(fallback_reason, str) and fallback_reason.strip():
            response_payload["fallback_reason"] = fallback_reason.strip()
        attribution = _build_chat_attribution(fallback_ml, rag_sources)
        disclosure = ComplianceService(db, settings=settings).model_disclosure(
            fallback_ml.get("model_used")
        )
        if disclosure is not None:
            response_payload["ai_disclosure"] = disclosure
        return attach_attribution(response_payload, attribution=attribution)


@router.post("/stream")
def chat_completion_stream(
    payload: ChatRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE variant of the chat turn: live pipeline ``step`` events + ``token`` stream.

    Proxies the ML ``/v1/chat/stream`` SSE through to the browser (mirroring the
    research job stream pattern). The non-streaming ``POST /api/v1/chat`` is
    unchanged; clients opt into streaming by calling this route. On any upstream
    failure a terminal ``error`` SSE frame is emitted so the client degrades
    gracefully (it can then retry the non-streaming endpoint).
    """

    settings = get_settings()
    rag_flow, rag_sources = _load_rag_runtime(db)
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/stream"
    request_payload = {
        "query": payload.message,
        "role": token.role,
        "rag_flow": rag_flow.model_dump(),
        "rag_sources": rag_sources,
        "protocol": payload.protocol,
        "clinical_context": payload.clinical_context,
    }
    headers: dict[str, str] = {"Accept": "text/event-stream"}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    # Generous read timeout: the upstream holds the connection open while it
    # synthesizes + streams tokens (no per-chunk write timeout).
    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)

    # Cross-border transfer gate (Req 4.2 / Correctness Property P2): when gating
    # is on and the user has not granted cross_border_processing consent, never
    # open the upstream stream (which would transmit the query offshore). Emit a
    # terminal degraded ``error`` frame so the client falls back to the
    # non-streaming endpoint, which is gated and returns the local degraded
    # answer. Behind the flag ⇒ no new behavior with gating off (Property P6).
    if settings.compliance_cross_border_gating_enabled:
        compliance = ComplianceService(db, settings=settings)
        user_id = _resolve_user_id(db, token)
        transfer = compliance.outbound_guard(user_id=user_id)
        # No-PII transfer event (Req 4.4 / Property P5): record processor,
        # purpose, and opaque user ref for the outbound offshore decision before
        # the upstream stream is (or is not) opened. No query text is logged.
        compliance.record_transfer(
            user_id=user_id,
            processor=LLM_PROCESSOR,
            purpose=LLM_PURPOSE,
            allowed=transfer.allow_cross_border,
        )
        if not transfer.allow_cross_border:

            def degraded_relay():  # noqa: ANN202 - generator of SSE byte chunks
                yield (
                    b'event: error\ndata: {"message":"cross_border_consent_required",'
                    b'"degraded":true,"fallback":"non_streaming"}\n\n'
                )

            return StreamingResponse(
                degraded_relay(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

    def relay():  # noqa: ANN202 - generator of SSE byte chunks
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=request_payload, headers=headers) as upstream:
                    if upstream.status_code >= 400:
                        upstream.read()
                        yield (
                            'event: error\ndata: {"message":"chat stream upstream error",'
                            f'"status":{upstream.status_code}}}\n\n'
                        ).encode()
                        return
                    for chunk in upstream.iter_raw():
                        if chunk:
                            yield chunk
        except Exception as exc:  # noqa: BLE001 - terminal SSE error frame
            yield (
                'event: error\ndata: {"message":"chat stream proxy failed",'
                f'"error":"{exc.__class__.__name__}"}}\n\n'
            ).encode()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
