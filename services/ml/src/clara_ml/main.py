from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from time import perf_counter

from fastapi import FastAPI, Request, WebSocket

from clara_ml.agents.careguard import run_careguard_analyze
from clara_ml.agents.council import run_council
from clara_ml.agents.research_tier2 import run_research_tier2
from clara_ml.agents.scribe_soap import run_scribe_soap
from clara_ml.config import settings
from clara_ml.factcheck import run_fides_lite
from clara_ml.nlp.pii_filter import redact_pii
from clara_ml.observability import metrics_collector
from clara_ml.prompts.loader import PromptLoader
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.routing import P1RoleIntentRouter
from clara_ml.streaming.ws import token_stream

app = FastAPI(title="CLARA ML Service", version="0.1.0")

prompt_loader = PromptLoader(Path(__file__).resolve().parent / "prompts" / "templates")
rag_pipeline = RagPipelineP1()
router = P1RoleIntentRouter()

_LEGAL_GUARD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            (
                r"(k[êe]\s*đ[ơo]n|prescrib(?:e|ing)?|đ[ơo]n\s*thu[oố]c|"
                r"toa\s*thu[oố]c|thu[oố]c\s*tr[ịi])"
            ),
            flags=re.IGNORECASE,
        ),
        "prescription_request",
    ),
    (
        re.compile(
            r"(ch[ẩa]n\s*đo[aá]n|diagnos(?:e|is)|t[ôo]i\s*b[iị]\s*b[eệ]nh\s*g[iì])",
            flags=re.IGNORECASE,
        ),
        "diagnosis_request",
    ),
    (
        re.compile(
            (
                r"(li[ềe]u|dos(?:e|age)|u[ốo]ng\s*m[ấa]y|bao\s*nhi[eê]u\s*(vi[eê]n|mg)|"
                r"m[ấa]y\s*(vi[eê]n|mg)|mg\s*m[ỗo]i\s*ng[aà]y)"
            ),
            flags=re.IGNORECASE,
        ),
        "dosage_request",
    ),
]


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


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _detect_legal_guard_violation(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for pattern, reason in _LEGAL_GUARD_PATTERNS:
        if pattern.search(normalized):
            return reason
    return None


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


@app.get("/metrics")
def metrics() -> dict:
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
    legal_guard_reason = _detect_legal_guard_violation(query)
    if legal_guard_reason:
        safe_role = (
            role_hint
            if role_hint in {"normal", "researcher", "doctor", "admin"}
            else "normal"
        )
        return {
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
                    note=f"Blocked by hard policy: {legal_guard_reason}",
                )
            ],
            "guard_reason": legal_guard_reason,
        }

    rag_flow_payload = payload.get("rag_flow")
    rag_flow = rag_flow_payload if isinstance(rag_flow_payload, dict) else {}
    role_router_enabled = _as_bool(rag_flow.get("role_router_enabled"), True)
    intent_router_enabled = _as_bool(rag_flow.get("intent_router_enabled"), True)
    verification_enabled = _as_bool(rag_flow.get("verification_enabled"), True)
    deepseek_fallback_enabled = _as_bool(rag_flow.get("deepseek_fallback_enabled"), True)
    low_context_threshold = _as_threshold(rag_flow.get("low_context_threshold"), 0.15)
    scientific_retrieval_enabled = _as_bool(rag_flow.get("scientific_retrieval_enabled"), False)
    web_retrieval_enabled = _as_bool(rag_flow.get("web_retrieval_enabled"), False)
    file_retrieval_enabled = _as_bool(rag_flow.get("file_retrieval_enabled"), True)
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
        return {
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
                "deepseek_fallback_enabled": deepseek_fallback_enabled,
                "low_context_threshold": low_context_threshold,
                "scientific_retrieval_enabled": scientific_retrieval_enabled,
                "web_retrieval_enabled": web_retrieval_enabled,
                "file_retrieval_enabled": file_retrieval_enabled,
            },
        }

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

    degraded_mode = False
    degraded_reason = ""
    try:
        rag_result = rag_pipeline.run(
            pii.redacted_text,
            low_context_threshold=low_context_threshold,
            deepseek_fallback_enabled=deepseek_fallback_enabled,
            scientific_retrieval_enabled=scientific_retrieval_enabled,
            web_retrieval_enabled=web_retrieval_enabled,
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
        )
    except Exception as exc:
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
        )
    factcheck = (
        run_fides_lite(answer=rag_result.answer, retrieved_context=rag_result.retrieved_context)
        if verification_enabled
        else None
    )
    answer = rag_result.answer
    if factcheck and factcheck.severity == "high":
        answer = (
            f"{rag_result.answer}\n\n"
            "Luu y an toan: mot so noi dung chua du bang chung tu tai lieu truy xuat. "
            "Ban nen doi chieu them voi bac si/duoc si truoc khi ap dung."
        )

    flow_events = list(rag_result.flow_events)
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
    if verification_enabled:
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

    return {
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
            "deepseek_fallback_enabled": deepseek_fallback_enabled,
            "low_context_threshold": low_context_threshold,
            "scientific_retrieval_enabled": scientific_retrieval_enabled,
            "web_retrieval_enabled": web_retrieval_enabled,
            "file_retrieval_enabled": file_retrieval_enabled,
            "rag_sources_count": len(rag_sources),
            "uploaded_documents_count": len(uploaded_documents),
        },
    }


@app.post("/v1/research/tier2")
def research_tier2(payload: dict) -> dict:
    result = run_research_tier2(payload)
    return result


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


@app.get("/v1/prompts/{role}/{intent}")
def get_prompt(role: str, intent: str) -> dict:
    return prompt_loader.load(role, intent)


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    incoming = await websocket.receive_text()
    async for token in token_stream(incoming):
        await websocket.send_json({"token": token})
    await websocket.send_json({"event": "done"})
    await websocket.close()
