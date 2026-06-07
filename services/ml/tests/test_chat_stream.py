"""SSE chat-stream contract tests (process steps + token-by-token answer)."""

from __future__ import annotations

import json

from clara_ml.streaming.chat_stream import (
    iter_answer_chunks,
    sse_event,
    stream_chat_sse,
)


def _no_sleep(_seconds: float) -> None:
    return None


def _kinds(frames: list[str]) -> list[str]:
    return [f.split("\n", 1)[0].removeprefix("event: ") for f in frames]


def _data(frame: str) -> dict:
    line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
    return json.loads(line[len("data: ") :])


def test_answer_chunks_reconstruct_exactly() -> None:
    ans = "Warfarin và aspirin tăng nguy cơ chảy máu.\n\n- Theo dõi INR."
    assert "".join(iter_answer_chunks(ans)) == ans
    assert list(iter_answer_chunks("")) == []


def test_sse_event_format() -> None:
    frame = sse_event("token", {"text": "hi"})
    assert frame.startswith("event: token\ndata: ")
    assert frame.endswith("\n\n")
    assert _data(frame) == {"text": "hi"}


def test_stream_sequence_steps_then_tokens_then_done() -> None:
    result = {
        "answer": "hello world",
        "flow_events": [
            {"stage": "route", "status": "completed"},
            {"stage": "synthesis", "status": "completed"},
        ],
        "model_used": "m",
        "retrieved_ids": [1, 2],
    }
    frames = list(stream_chat_sse({"query": "x"}, infer=lambda _p: result, token_delay=0, step_delay=0, sleep=_no_sleep))
    kinds = _kinds(frames)

    assert kinds[0] == "start"
    assert kinds[-1] == "done"
    assert kinds.count("step") == 2
    assert kinds.count("token") >= 2

    # Tokens concatenate back to the answer.
    tokens = [_data(f)["text"] for f, k in zip(frames, kinds) if k == "token"]
    assert "".join(tokens) == "hello world"

    # Done frame carries the full structured result.
    done = _data(frames[-1])
    assert done["model_used"] == "m"
    assert done["retrieved_ids"] == [1, 2]


def test_stream_emits_terminal_error_on_infer_failure() -> None:
    def boom(_p):  # noqa: ANN001, ANN202
        raise RuntimeError("kaboom")

    frames = list(stream_chat_sse({"query": "x"}, infer=boom, sleep=_no_sleep))
    kinds = _kinds(frames)
    assert kinds[0] == "start"
    assert kinds[-1] == "error"
    assert _data(frames[-1])["error"] == "RuntimeError"
