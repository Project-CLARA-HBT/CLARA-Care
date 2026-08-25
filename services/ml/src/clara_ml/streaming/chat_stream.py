"""Server-Sent Events (SSE) streaming for the plain chat path.

This module wraps the existing routed-chat inference so the web frontend can
render, in real time:

* the **pipeline process** — each ``flow_event`` the router/RAG pipeline emits
  (routing, safety, retrieval, synthesis, verification, ...) is forwarded as a
  ``step`` SSE event so the UI can light up a live "process" panel; and
* the **answer token-by-token** — the synthesized answer is streamed as a
  sequence of small ``token`` events so the bubble types out progressively.

Design constraints:

* **Additive / non-invasive.** It reuses the unchanged ``routed_chat_infer``
  result (``answer`` + ``flow_events`` + provenance) rather than refactoring the
  core pipeline, so the existing ``POST /v1/chat`` (non-streaming) path is
  untouched. (Truly per-stage-live emission would require a pipeline callback;
  this v1 emits the real steps in order, then streams the real answer tokens.)
* **Total / fail-soft.** Any error is surfaced as a terminal ``error`` SSE event
  instead of breaking the stream; the generator always ends with a single
  terminal event (``done`` or ``error``).
* **Import-safe.** Importing this module opens no socket; ``routed_chat_infer``
  is injected by the caller (``main.py``) to avoid an import cycle.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from typing import Any

__all__ = ["sse_event", "stream_chat_sse", "iter_answer_chunks"]


# Token granularity for the typewriter effect: emit word-plus-trailing-space
# chunks so markdown / Vietnamese diacritics stay intact and rendering is smooth.
_CHUNK_RE = re.compile(r"\S+\s*|\s+")

# Default inter-chunk / inter-step delay (seconds). Small enough to feel live,
# large enough to be visible. Overridable per request.
_DEFAULT_TOKEN_DELAY = 0.018
_DEFAULT_STEP_DELAY = 0.04


def sanitize_cot_content(raw_content: str, existing_reasoning: str = "") -> tuple[str, str]:
    """Strip <think>...</think> tags and extract reasoning_content."""
    if not raw_content:
        return "", existing_reasoning

    think_pattern = re.compile(r"<think>(.*?)(?:</think>|$)", flags=re.DOTALL)
    extracted_reasoning = [
        m.group(1).strip()
        for m in think_pattern.finditer(raw_content)
        if m.group(1).strip()
    ]
    clean_content = think_pattern.sub("", raw_content).strip()

    combined_reasoning = existing_reasoning
    if extracted_reasoning:
        cot_text = "\n\n".join(extracted_reasoning)
        if combined_reasoning:
            combined_reasoning = f"{combined_reasoning}\n\n{cot_text}"
        else:
            combined_reasoning = cot_text

    return clean_content, combined_reasoning


def sse_event(event: str, data: Any) -> str:
    """Format one SSE frame: ``event: <name>\\ndata: <json>\\n\\n``."""

    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def iter_answer_chunks(answer: str) -> Iterator[str]:
    """Yield small word-plus-whitespace chunks of ``answer`` (order-preserving).

    Concatenating every yielded chunk reproduces ``answer`` byte-for-byte, so no
    content is lost or reordered by the typewriter stream.
    """

    if not answer:
        return
    clean_answer, _ = sanitize_cot_content(answer)
    if not clean_answer:
        return
    for match in _CHUNK_RE.finditer(clean_answer):
        chunk = match.group(0)
        if chunk:
            yield chunk


def stream_chat_sse(
    payload: dict[str, Any],
    *,
    infer: Callable[[dict[str, Any]], dict[str, Any]],
    token_delay: float = _DEFAULT_TOKEN_DELAY,
    step_delay: float = _DEFAULT_STEP_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """Yield the SSE frames for one streamed chat turn.

    Event sequence:

    1. ``start``  — ``{}`` (lets the client open the live panel immediately).
    2. ``step``   — one per ``flow_event`` (the live pipeline process).
    3. ``token``  — many; each carries ``{"text": <chunk>}`` of the answer.
    4. ``done``   — the full structured result (answer, retrieved_ids, model_used,
       flow_events, ...) so the client can finalize/persist the turn.

    On any failure a single terminal ``error`` event is emitted instead of
    ``done``. ``infer`` is the (injected) routed-chat inference function.
    """

    yield sse_event("start", {})
    try:
        result = infer(payload)
        if not isinstance(result, dict):
            result = {"answer": str(result)}
    except Exception as exc:  # noqa: BLE001 - surface as a terminal SSE error
        yield sse_event(
            "error",
            {"message": "chat stream failed", "error": exc.__class__.__name__},
        )
        return

    # (2) Pipeline process — replay the real flow events as ordered steps.
    flow_events = result.get("flow_events")
    if isinstance(flow_events, list):
        for index, event in enumerate(flow_events):
            if not isinstance(event, dict):
                continue
            yield sse_event("step", {"index": index, **event})
            if step_delay > 0:
                sleep(step_delay)

    # (3) Answer — typewriter token stream.
    answer = result.get("answer")
    answer_text = answer if isinstance(answer, str) else ""
    clean_answer, extracted_reasoning = sanitize_cot_content(
        answer_text,
        existing_reasoning=str(result.get("reasoning_content") or ""),
    )
    result["answer"] = clean_answer
    if extracted_reasoning:
        result["reasoning_content"] = extracted_reasoning
    for chunk in iter_answer_chunks(clean_answer):
        yield sse_event("token", {"text": chunk})
        if token_delay > 0:
            sleep(token_delay)

    # (4) Terminal frame with the full structured result.
    yield sse_event("done", result)
