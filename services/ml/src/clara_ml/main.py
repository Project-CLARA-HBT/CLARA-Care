from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request, WebSocket

from clara_ml.agents.careguard import run_careguard_analyze
from clara_ml.agents.council import run_council
from clara_ml.agents.research_tier2 import run_research_tier2
from clara_ml.agents.scribe_soap import run_scribe_soap
from clara_ml.config import settings
from clara_ml.nlp.pii_filter import redact_pii
from clara_ml.observability import metrics_collector
from clara_ml.prompts.loader import PromptLoader
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.routing import P1RoleIntentRouter
from clara_ml.streaming.ws import token_stream

app = FastAPI(title="CLARA ML Service", version="0.1.0")

prompt_loader = PromptLoader(
    Path(__file__).resolve().parent / "prompts" / "templates"
)
rag_pipeline = RagPipelineP1()
router = P1RoleIntentRouter()


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
    result = rag_pipeline.run(pii.redacted_text)
    return {
        "query": query,
        "redacted_query": pii.redacted_text,
        "pii_flags": pii.flags,
        "retrieved_ids": result.retrieved_ids,
        "answer": result.answer,
        "model_used": result.model_used,
    }


@app.post("/v1/chat/routed")
def routed_chat_infer(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    pii = redact_pii(query)
    route = router.route(pii.redacted_text)

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
        }

    rag_result = rag_pipeline.run(pii.redacted_text)
    return {
        "role": route.role,
        "intent": route.intent,
        "confidence": route.confidence,
        "emergency": False,
        "answer": rag_result.answer,
        "retrieved_ids": rag_result.retrieved_ids,
        "model_used": rag_result.model_used,
    }


@app.post("/v1/research/tier2")
def research_tier2(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    result = run_research_tier2(query)
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
