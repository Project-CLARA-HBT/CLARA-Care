import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.flow import get_chat_flow_event_persister
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.session import get_db
from clara_api.schemas import RagFlowConfig

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


_SAFE_MODE_NOTICE = (
    "Hệ thống truy xuất chuyên sâu đang bận hoặc tạm thời không kết nối được nguồn RAG. "
    "Tạm thời dùng chế độ an toàn để phản hồi nhanh."
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


def _normalize_citation_rows(citations_payload: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(citations_payload, list):
        return rows

    for idx, item in enumerate(citations_payload, start=1):
        if isinstance(item, str):
            source = item.strip()
            if source:
                rows.append({"source": source})
            continue

        if not isinstance(item, dict):
            continue

        raw_source = item.get("source") or item.get("title") or item.get("id")
        source = str(raw_source).strip() if raw_source is not None else ""
        if not source:
            source = f"reference-{idx}"
        citation: dict[str, str] = {"source": source}

        raw_url = item.get("url") or item.get("link")
        if raw_url is not None:
            url = str(raw_url).strip()
            if url:
                citation["url"] = url

        rows.append(citation)
    return rows


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

    citations = _normalize_citation_rows(ml_response.get("citations"))
    return {
        "channel": "chat",
        "source_count": len(active_sources),
        "citation_count": len(citations),
        "sources": active_sources,
        "citations": citations,
    }


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
        "answer": (
            "Hệ thống đang quá tải tạm thời nên câu trả lời chi tiết chưa sẵn sàng. "
            "Bạn có thể thử lại sau ít phút. Trong thời gian chờ, hãy ưu tiên nguồn chính thống "
            "và liên hệ chuyên gia y tế nếu có dấu hiệu nặng hoặc bất thường."
        ),
        "retrieved_ids": [],
        "model_used": "api-safe-fallback-v1",
        "fallback_reason": reason,
        "query_echo": message,
    }


def _decorate_safe_mode_answer(answer: str) -> str:
    cleaned = answer.strip()
    if not cleaned:
        return _SAFE_MODE_NOTICE
    return f"{_SAFE_MODE_NOTICE}\n\n{cleaned}"


def _post_to_ml(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    response = httpx.post(url, json=payload, timeout=timeout_seconds)
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
            "verification_enabled": False,
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
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/routed"
    request_payload = {
        "query": message,
        "role": role,
        "rag_flow": rag_flow.model_dump(),
        "rag_sources": rag_sources,
    }
    safe_mode_timeout = max(3.0, min(settings.ml_service_timeout_seconds, 12.0))

    primary_reason = ""
    try:
        data = _post_to_ml(url, request_payload, settings.ml_service_timeout_seconds)
        return data
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        primary_reason = f"ml_unavailable:{exc.__class__.__name__}"
    except httpx.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status is None:
            primary_reason = f"ml_http_error:{exc.__class__.__name__}"
        elif status >= 500:
            primary_reason = f"ml_upstream_5xx:{status}"
        else:
            primary_reason = f"ml_upstream_4xx:{status}"
    except ValueError as exc:
        primary_reason = f"ml_invalid_json:{exc.__class__.__name__}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        primary_reason = f"ml_unexpected_exception:{exc.__class__.__name__}"

    safe_mode_reason = ""
    try:
        safe_mode_data = _post_to_ml(
            url,
            _safe_mode_payload(message, role, rag_flow, rag_sources),
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
        status = exc.response.status_code if exc.response is not None else None
        if status is None:
            safe_mode_reason = f"safe_mode_http_error:{exc.__class__.__name__}"
        elif status >= 500:
            safe_mode_reason = f"safe_mode_upstream_5xx:{status}"
        else:
            safe_mode_reason = f"safe_mode_upstream_4xx:{status}"
    except ValueError as exc:
        safe_mode_reason = f"safe_mode_invalid_json:{exc.__class__.__name__}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        safe_mode_reason = f"safe_mode_unexpected_exception:{exc.__class__.__name__}"

    composed_reason = primary_reason
    if safe_mode_reason:
        composed_reason = f"{primary_reason};{safe_mode_reason}"
    return _safe_chat_fallback(message, role, reason=composed_reason)


@router.post("/")
@router.post("")
def chat_placeholder(
    payload: ChatRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    control_tower = get_control_tower_config_service().load(db)
    rag_flow = control_tower.rag_flow
    rag_sources = [item.model_dump() for item in control_tower.rag_sources]
    ml_response = _call_ml_service(payload.message, token.role, rag_flow, rag_sources)
    model_used = ml_response.get("model_used")
    if isinstance(model_used, str) and model_used.startswith("local-synth"):
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

    resolved_role = ml_response.get("role")
    if not isinstance(resolved_role, str) or not resolved_role:
        resolved_role = token.role

    get_chat_flow_event_persister().persist(
        token=token,
        role=resolved_role,
        ml_response=ml_response,
    )
    attribution = _build_chat_attribution(ml_response, rag_sources)
    attributions = [attribution]

    return {
        "message": payload.message,
        "reply": reply,
        "role": resolved_role,
        "intent": ml_response.get("intent"),
        "confidence": ml_response.get("confidence"),
        "emergency": ml_response.get("emergency"),
        "model_used": ml_response.get("model_used"),
        "retrieved_ids": ml_response.get("retrieved_ids", []),
        "attributions": attributions,
        "attribution": attribution,
        "citations": attribution["citations"],
        "ml": ml_response,
    }
