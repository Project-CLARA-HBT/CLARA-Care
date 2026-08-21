"""Tests for the W7 hardened review runner (run_v2.py)."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Self

import pytest

from evaluation.model_adjudication.run_v2 import (
    BASE_URL,
    MODELS,
    _call,
    _load_manifest,
    _parse_review_v2,
    _structured_content_v2,
    run,
)

ALLOWED = ("PASS", "FAIL")


class _FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self._content_type = content_type

    def get_content_type(self) -> str:
        return self._content_type


class _FakeResponse:
    def __init__(
        self, payload: bytes, content_type: str = "application/json", status: int = 200
    ) -> None:
        self._payload = payload
        self.headers = _FakeHeaders(content_type)
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def _json_payload(review: dict[str, Any]) -> bytes:
    return json.dumps({"choices": [{"message": {"content": json.dumps(review)}}]}).encode()


def _sse_payload(content: str, *, complete: bool = True, chunk_size: int = 8) -> bytes:
    parts = [
        f'data: {{"choices":[{{"delta":{{"content":{json.dumps(content[i : i + chunk_size])}}}}}]}}'.encode()
        for i in range(0, len(content), chunk_size)
    ]
    if complete:
        parts.append(b"data: [DONE]")
    return b"\n".join(parts) + b"\n"


def _review(
    *,
    label: str = "PASS",
    rationale: str = "ok",
    evidence_ids: list[str] | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "label": label,
        "rationale": rationale,
        "evidence_ids": evidence_ids or ["e1", "e2"],
        "confidence": confidence,
    }


def _manifest(*, status: str = "frozen") -> dict[str, Any]:
    return {
        "schema_version": "clara-model-review-manifest.v2",
        "status": status,
        "study_id": "w7-hardening",
        "models": list(MODELS),
        "protocols": {"safety": {"allowed_labels": ["PASS", "FAIL"]}},
        "rubric": {"dimensions": ["safety"]},
        "cases": [
            {
                "case_id": "c1",
                "protocol": "safety",
                "evidence": {"e1": {"text": "x"}, "e2": {"text": "y"}},
            }
        ],
    }


def _fake_urlopen(
    *,
    response: _FakeResponse | None = None,
    error: Exception | None = None,
    calls: list[Any] | None = None,
) -> Any:
    def _urlopen(request: Any, **_kwargs: Any) -> Any:
        if calls is not None:
            calls.append(request)
        if error is not None:
            raise error
        if response is None:
            raise AssertionError("fake_urlopen configured with neither response nor error")
        return response

    return _urlopen


@pytest.fixture(autouse=True)
def _router_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLARA_ROUTER_API_KEY", "test-key-not-committed")


def test_json_review_parses_with_full_provenance() -> None:
    review = _review()
    raw = _json_payload(review)
    response = _FakeResponse(raw, content_type="application/json", status=200)
    result = _call(
        model=MODELS[0],
        prompt="prompt",
        allowed_labels=ALLOWED,
        available_evidence_ids=["e1", "e2"],
        urlopen=_fake_urlopen(response=response),
    )
    assert result["model_id"] == MODELS[0]
    assert result["attempts"] == 1
    assert result["decoding"] == {"temperature": 0, "stream": False}
    provider = result["provider"]
    assert provider["router_base_url"] == BASE_URL
    assert provider["http_status"] == 200
    assert provider["content_type"] == "application/json"
    assert provider["raw_http_body_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provider["parsed_review_sha256"]
    assert result["review"] == review


def test_sse_supported_despite_stream_false() -> None:
    content = json.dumps(_review())
    response = _FakeResponse(_sse_payload(content), content_type="text/event-stream", status=200)
    result = _call(
        model=MODELS[0],
        prompt="prompt",
        allowed_labels=ALLOWED,
        available_evidence_ids=["e1", "e2"],
        urlopen=_fake_urlopen(response=response),
    )
    assert result["review"]["label"] == "PASS"
    assert result["provider"]["content_type"] == "text/event-stream"


def test_structured_content_parses_split_sse_json() -> None:
    content = json.dumps(_review())
    assert (
        _parse_review_v2(
            content=_structured_content_v2(
                payload_bytes=_sse_payload(content), content_type="text/event-stream"
            ),
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
        )
        == _review()
    )


def test_truncated_sse_fails_closed() -> None:
    content = json.dumps(_review())
    response = _FakeResponse(
        _sse_payload(content, complete=False), content_type="text/event-stream"
    )
    with pytest.raises(RuntimeError, match="call_failed:ValueError"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_sse_missing_choices_fails_closed() -> None:
    payload = b'data: {"choices": []}\n'
    with pytest.raises(ValueError, match="sse_malformed"):
        _structured_content_v2(payload_bytes=payload, content_type="text/event-stream")


def test_malformed_json_fails_closed() -> None:
    response = _FakeResponse(b"this is not json", content_type="application/json")
    with pytest.raises(RuntimeError, match="call_failed:ValueError"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_empty_response_fails_closed() -> None:
    response = _FakeResponse(
        b'{"choices":[{"message":{"content":""}}]}', content_type="application/json"
    )
    with pytest.raises(RuntimeError, match="call_failed:ValueError"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_http_error_fails_closed() -> None:
    error = urllib.error.HTTPError(
        url=BASE_URL, code=503, msg="Service Unavailable", hdrs={}, fp=io.BytesIO(b"oops")
    )
    with pytest.raises(RuntimeError, match="call_failed:HTTPError"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(error=error),
        )


def test_retry_exhaustion_fails_closed() -> None:
    error = urllib.error.URLError(TimeoutError("boom"))
    with pytest.raises(RuntimeError, match="call_failed:URLError"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=1,
            urlopen=_fake_urlopen(error=error),
        )


def test_retry_succeeds_on_subsequent_attempt_and_records_attempts() -> None:
    state = {"calls": 0}

    def flaky(_request: Any, **_kwargs: Any) -> Any:
        state["calls"] += 1
        if state["calls"] == 1:
            raise urllib.error.URLError(TimeoutError("boom"))
        return _FakeResponse(_json_payload(_review()), content_type="application/json")

    result = _call(
        model=MODELS[0],
        prompt="prompt",
        allowed_labels=ALLOWED,
        available_evidence_ids=["e1", "e2"],
        retries=2,
        urlopen=flaky,
    )
    assert result["attempts"] == 2
    assert result["review"]["label"] == "PASS"


def test_credentials_never_retained_in_result() -> None:
    calls: list[Any] = []
    response = _FakeResponse(_json_payload(_review()), content_type="application/json")
    result = _call(
        model=MODELS[0],
        prompt="prompt",
        allowed_labels=ALLOWED,
        available_evidence_ids=["e1", "e2"],
        urlopen=_fake_urlopen(response=response, calls=calls),
    )
    assert "test-key-not-committed" not in json.dumps(result, sort_keys=True)
    assert calls[0].get_header("Authorization") == "Bearer test-key-not-committed"


def test_review_rejects_unknown_evidence_id() -> None:
    response = _FakeResponse(
        _json_payload(_review(evidence_ids=["nope"])), content_type="application/json"
    )
    with pytest.raises(RuntimeError, match="evidence_ids_unknown"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_review_rejects_unallowed_label() -> None:
    response = _FakeResponse(_json_payload(_review(label="MAYBE")), content_type="application/json")
    with pytest.raises(RuntimeError, match="label_not_allowed"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_review_rejects_out_of_range_confidence() -> None:
    response = _FakeResponse(
        _json_payload(_review(confidence=1.5)), content_type="application/json"
    )
    with pytest.raises(RuntimeError, match="confidence_out_of_range"):
        _call(
            model=MODELS[0],
            prompt="prompt",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            retries=0,
            urlopen=_fake_urlopen(response=response),
        )


def test_manifest_requires_frozen_and_rejects_unexpected_keys(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest(status="draft")))
    with pytest.raises(ValueError, match="not_frozen"):
        _load_manifest(path)
    manifest = _manifest()
    manifest["unexpected"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unexpected_keys:manifest"):
        _load_manifest(path)


def test_run_end_to_end_writes_rows_and_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()))
    calls: list[Any] = []
    response = _FakeResponse(_json_payload(_review()), content_type="application/json")
    summary = run(
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
        urlopen=_fake_urlopen(response=response, calls=calls),
    )
    assert summary["case_count"] == 1
    assert summary["schema_version"] == "clara-model-review-run.v2"
    assert summary["models"] == list(MODELS)
    row = json.loads((tmp_path / "out/raw/c1.json").read_text())
    assert row["protocol"] == "safety"
    assert row["allowed_labels"] == ["PASS", "FAIL"]
    assert row["evidence_ids"] == ["e1", "e2"]
    assert {r["reviewer_id"] for r in row["reviews"]} == {"reviewer_a", "reviewer_b"}
    assert all(r["provider"]["raw_http_body_sha256"] for r in row["reviews"])


def test_run_fails_closed_without_router_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLARA_ROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="router_key_missing"):
        _call(
            model=MODELS[0],
            prompt="{}",
            allowed_labels=ALLOWED,
            available_evidence_ids=["e1", "e2"],
            urlopen=_fake_urlopen(),
        )
