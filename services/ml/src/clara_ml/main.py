from __future__ import annotations

from pathlib import Path
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
    }


@app.post("/v1/chat/routed")
def routed_chat_infer(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    role_hint = str(payload.get("role", "")).strip().lower() or None
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
        route.role = role_hint if role_hint in {"normal", "researcher", "doctor"} else "normal"

    if not intent_router_enabled:
        default_by_role = {
            "normal": "symptom_triage",
            "researcher": "evidence_review",
            "doctor": "doctor_case_review",
        }
        route.intent = default_by_role.get(route.role, "symptom_triage")
        route.confidence = min(route.confidence, 0.6)

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
