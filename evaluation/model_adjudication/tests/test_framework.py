from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.model_adjudication.analyze import analyze
from evaluation.model_adjudication.run import (
    _call,
    _load,
    _parse_review,
    _structured_content,
)


def test_run_fails_closed_without_router_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLARA_ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("CLARA_UNOFFICIAL_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="router_key_missing"):
        _call(model="gemini-3.6-flash-high", prompt="{}")


def test_analyze_uses_cases_not_calls(tmp_path: Path) -> None:
    for case_id, left, right in (("a", "PASS", "PASS"), ("b", "FAIL", "PASS")):
        (tmp_path / f"{case_id}.json").write_text(
            json.dumps({"reviews": [{"review": {"label": left}}, {"review": {"label": right}}]})
        )
    result = analyze(tmp_path)
    assert result["case_count"] == 2
    assert result["pre_reconciliation_agreement"] == 0.5


def test_manifest_requires_frozen_contract(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "clara-model-review-manifest.v1",
                "status": "draft",
                "rubric": {},
                "cases": [],
            }
        )
    )
    with pytest.raises(ValueError, match="not_frozen"):
        _load(path)


def test_transport_parses_json_fence_and_complete_sse() -> None:
    assert _parse_review('```json\n{"label": "PASS", "rationale": "ok"}\n```')["label"] == "PASS"
    sse = b'data: {"choices":[{"delta":{"content":"{\\"label\\":\\"PASS\\","}}]}\ndata: {"choices":[{"delta":{"content":"\\"rationale\\":\\"ok\\"}"}}]}\ndata: [DONE]\n'
    assert (
        _parse_review(_structured_content(payload_bytes=sse, content_type="text/event-stream"))[
            "label"
        ]
        == "PASS"
    )


def test_transport_rejects_interrupted_or_empty_response() -> None:
    with pytest.raises(ValueError, match="sse_malformed"):
        _structured_content(
            payload_bytes=b'data: {"choices": []}\n', content_type="text/event-stream"
        )
    with pytest.raises(ValueError, match="response_empty"):
        _structured_content(
            payload_bytes=b'{"choices":[{"message":{"content":""}}]}',
            content_type="application/json",
        )
