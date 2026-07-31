"""Server-Sent Events (SSE) streaming for the Council progress path.

This module wraps the existing deterministic ``run_council`` computation so the
web frontend can render the deliberation **stage-by-stage** instead of waiting
for a single blocking response:

* the **processing progress** — each non-clinical stage label of the existing
  processing timeline (``intake_normalized`` → ``specialist_assessment`` →
  ``conflict_review`` → ``consensus_decision`` → ``safety_gate`` →
  ``final_recommendation``) is forwarded, in order, as a ``stage`` SSE event so
  the UI can light up a live progress panel; then
* the **final result** — the full ``run_council`` envelope is streamed as a
  single terminal ``result`` event so the client can finalize/persist the run.

Design constraints (mirroring ``streaming.chat_stream``):

* **Additive / non-invasive.** It reuses the unchanged ``run_council`` result
  rather than refactoring the deterministic engine, so the existing
  ``POST /v1/council/run`` (non-streaming) path is untouched. Because
  ``run_council`` is synchronous and deterministic, the terminal ``result``
  event is *the same object* the blocking endpoint returns — stream/blocking
  result equivalence holds by construction (Requirement 1.1, 1.2).
* **Total / fail-soft.** Any error is surfaced as a single terminal ``error``
  SSE event instead of breaking the stream; the generator always ends with
  exactly one terminal event (``result`` or ``error``), never both
  (Requirement 1.4).
* **Import-safe.** Importing this module opens no socket; ``run_council`` is
  injected by the caller (``main.py``) to keep the seam testable.
* **No reasoning trace or PII surface.** Stage events carry only the stable
  ``sequence`` and ``step`` progress labels.  Clinical text, metadata, model
  rationale, and chain-of-thought-like content stay out of the stream.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

from clara_ml.streaming.chat_stream import sse_event

__all__ = ["stream_council_sse"]


# Default inter-stage delay (seconds). Small enough to feel live, large enough
# to be visible. Overridable per request (set to 0 in tests).
_DEFAULT_STAGE_DELAY = 0.04


def stream_council_sse(
    payload: dict[str, Any],
    *,
    run: Callable[[dict[str, Any]], dict[str, Any]],
    stage_delay: float = _DEFAULT_STAGE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """Yield the SSE frames for one streamed Council run.

    Event sequence:

    1. ``start``  — ``{}`` (lets the client open the live panel immediately).
    2. ``stage``  — one per processing step, in timeline order, carrying only
       ``{"index": <i>, "sequence": <n>, "step": <label>}``.
    3. ``result`` — the full ``run_council`` envelope so the client can
       finalize/persist the run.

    On any failure a single terminal ``error`` event is emitted instead of
    ``result``. ``run`` is the (injected) ``run_council`` function.
    """

    yield sse_event("start", {})
    try:
        result = run(payload)
        if not isinstance(result, dict):
            raise TypeError("run_council must return a dict result")
    except Exception as exc:  # noqa: BLE001 - surface as a terminal SSE error
        yield sse_event(
            "error",
            {"message": "council stream failed", "error": exc.__class__.__name__},
        )
        return

    # (2) Progress states only — never relay a reasoning trace, metadata, or
    # clinical text to the browser while the Council is running.
    timeline = result.get("reasoning_timeline")
    if isinstance(timeline, list):
        for index, step in enumerate(timeline):
            if not isinstance(step, dict):
                continue
            sequence = step.get("sequence")
            label = step.get("step")
            if not isinstance(sequence, int) or not isinstance(label, str) or not label:
                continue
            yield sse_event("stage", {"index": index, "sequence": sequence, "step": label})
            if stage_delay > 0:
                sleep(stage_delay)

    # (3) Terminal frame with the full structured result. Identical to what the
    # blocking ``POST /v1/council/run`` returns for the same payload.
    yield sse_event("result", result)
