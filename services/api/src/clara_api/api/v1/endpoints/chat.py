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

    try:
        response = httpx.post(
            url, json=request_payload, timeout=settings.ml_service_timeout_seconds
        )
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        return _safe_chat_fallback(message, role, reason=f"ml_unavailable:{exc.__class__.__name__}")
    except httpx.HTTPError as exc:
        return _safe_chat_fallback(message, role, reason=f"ml_http_error:{exc.__class__.__name__}")

    if response.status_code >= 500:
        return _safe_chat_fallback(message, role, reason=f"ml_upstream_5xx:{response.status_code}")
    if response.status_code >= 400:
        return _safe_chat_fallback(message, role, reason=f"ml_upstream_4xx:{response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        return _safe_chat_fallback(
            message, role, reason=f"ml_invalid_json:{exc.__class__.__name__}"
        )

    if not isinstance(data, dict):
        return _safe_chat_fallback(message, role, reason="ml_unexpected_payload")

    return data


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

    return {
        "message": payload.message,
        "reply": reply,
        "role": resolved_role,
        "intent": ml_response.get("intent"),
        "confidence": ml_response.get("confidence"),
        "emergency": ml_response.get("emergency"),
        "model_used": ml_response.get("model_used"),
        "retrieved_ids": ml_response.get("retrieved_ids", []),
        "attribution": attribution,
        "citations": attribution["citations"],
        "ml": ml_response,
    }
