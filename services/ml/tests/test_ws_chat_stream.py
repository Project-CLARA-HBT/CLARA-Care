"""WebSocket chat-stream contracts.

The WebSocket compatibility endpoint must stream the result of the same routed
inference boundary as HTTP/SSE.  In particular it must never echo incoming text
as though it were model output, and upstream failures must stay sanitized.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import clara_ml.main as main


def test_websocket_streams_routed_answer_not_input(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "ml_internal_api_key", "", raising=False)
    seen: list[dict] = []

    def infer(payload: dict) -> dict:
        seen.append(payload)
        return {
            "answer": "Câu trả lời đã qua guardrail.",
            "flow_events": [{"stage": "safety", "status": "pass"}],
        }

    monkeypatch.setattr(main, "routed_chat_infer", infer)
    with TestClient(main.app).websocket_connect("/ws/stream") as websocket:
        websocket.send_text("raw incoming text")
        assert websocket.receive_json() == {"event": "start"}
        assert websocket.receive_json() == {
            "event": "step",
            "index": 0,
            "stage": "safety",
            "status": "pass",
        }
        tokens: list[str] = []
        while True:
            event = websocket.receive_json()
            if event["event"] == "token":
                tokens.append(event["text"])
                continue
            assert event["event"] == "done"
            break

    assert seen == [{"query": "raw incoming text"}]
    assert "".join(tokens) == "Câu trả lời đã qua guardrail."


def test_websocket_rejects_empty_or_non_object_input(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "ml_internal_api_key", "", raising=False)
    with TestClient(main.app).websocket_connect("/ws/stream") as websocket:
        websocket.send_text("[]")
        assert websocket.receive_json() == {"event": "error", "code": "invalid_request"}
