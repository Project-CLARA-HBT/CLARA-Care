"""SSE council-stream contract tests (per-stage progress + terminal result).

Covers the streaming endpoint added in task 2.1: ordered ``stage`` events (one
per ``reasoning_timeline`` step) terminated by exactly one ``result`` (or
``error``) event, and stream/blocking result equivalence (Req 1.1, 1.4).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_ml.agents.council import run_council
from clara_ml.main import app
from clara_ml.streaming.council_stream import stream_council_sse

client = TestClient(app)


def _no_sleep(_seconds: float) -> None:
    return None


def _kinds(frames: list[str]) -> list[str]:
    return [f.split("\n", 1)[0].removeprefix("event: ") for f in frames]


def _data(frame: str) -> dict:
    line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
    return json.loads(line[len("data: ") :])


_SAMPLE_PAYLOAD = {
    "symptoms": ["fatigue", "palpitations"],
    "labs": {"egfr": 58, "glucose": 210},
    "medications": ["metformin"],
    "history": ["type 2 diabetes"],
    "specialists": ["cardiology", "endocrinology", "nephrology"],
}


def _parse_frames(text: str) -> list[str]:
    # SSE frames are separated by a blank line; keep the trailing separator so
    # each reconstructed frame ends with "\n\n" like sse_event produces.
    return [block + "\n\n" for block in text.split("\n\n") if block.strip()]


def _strip_volatile(result: dict) -> dict:
    """Drop per-call wall-clock fields so equivalence compares content, not time.

    ``run_council`` stamps ``emergency_escalation.metadata.generated_at_utc`` at
    call time, so two separate invocations (stream vs blocking) can differ only
    by that timestamp. Equivalence (Req 1.2) is about result content/shape.
    """

    normalized = json.loads(json.dumps(result))
    metadata = normalized.get("emergency_escalation", {}).get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("generated_at_utc", None)
    return normalized


def test_stream_emits_start_then_stages_then_result() -> None:
    frames = list(
        stream_council_sse(_SAMPLE_PAYLOAD, run=run_council, stage_delay=0, sleep=_no_sleep)
    )
    kinds = _kinds(frames)

    assert kinds[0] == "start"
    assert kinds[-1] == "result"
    # Exactly one terminal event, never both result and error.
    assert kinds.count("result") == 1
    assert kinds.count("error") == 0
    # One stage per reasoning-timeline step (the six pipeline steps).
    assert kinds.count("stage") >= 6


def test_stream_stages_are_strictly_ordered_by_sequence() -> None:
    frames = list(
        stream_council_sse(_SAMPLE_PAYLOAD, run=run_council, stage_delay=0, sleep=_no_sleep)
    )
    stage_frames = [
        _data(f) for f, k in zip(frames, _kinds(frames)) if k == "stage"
    ]
    sequences = [s["sequence"] for s in stage_frames]
    assert sequences == sorted(sequences)
    # The stages cover the six named pipeline steps in order.
    steps = [s["step"] for s in stage_frames]
    assert steps[:6] == [
        "intake_normalized",
        "specialist_assessment",
        "conflict_review",
        "consensus_decision",
        "safety_gate",
        "final_recommendation",
    ]


def test_stream_terminal_result_equals_blocking_run() -> None:
    frames = list(
        stream_council_sse(_SAMPLE_PAYLOAD, run=run_council, stage_delay=0, sleep=_no_sleep)
    )
    terminal = _data(frames[-1])
    assert _strip_volatile(terminal) == _strip_volatile(run_council(dict(_SAMPLE_PAYLOAD)))


def test_stream_emits_terminal_error_on_run_failure() -> None:
    def boom(_p):  # noqa: ANN001, ANN202
        raise RuntimeError("kaboom")

    frames = list(stream_council_sse(_SAMPLE_PAYLOAD, run=boom, sleep=_no_sleep))
    kinds = _kinds(frames)
    assert kinds[0] == "start"
    assert kinds[-1] == "error"
    assert "stage" not in kinds
    assert _data(frames[-1])["error"] == "RuntimeError"


def test_endpoint_streams_text_event_stream_and_matches_blocking() -> None:
    response = client.post("/v1/council/run/stream", json=_SAMPLE_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    frames = _parse_frames(response.text)
    kinds = _kinds(frames)
    assert kinds[0] == "start"
    assert kinds[-1] == "result"
    assert kinds.count("stage") >= 6

    terminal = _data(frames[-1])
    blocking = client.post("/v1/council/run", json=_SAMPLE_PAYLOAD).json()
    assert _strip_volatile(terminal) == _strip_volatile(blocking)
