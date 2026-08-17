"""Tests for the W7 reconciliation round (reconcile_v2.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self

import pytest

from evaluation.model_adjudication.reconcile_v2 import reconcile
from evaluation.model_adjudication.run_v2 import MODELS


def _row(*, case_id: str, left: str, right: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
    evidence_ids = evidence_ids or ["e1", "e2"]

    def _review(label: str) -> dict[str, Any]:
        return {"label": label, "rationale": "r", "evidence_ids": evidence_ids, "confidence": 0.9}

    def _result(reviewer_id: str, label: str) -> dict[str, Any]:
        review = _review(label)
        return {
            "model_id": MODELS[0] if reviewer_id == "reviewer_a" else MODELS[1],
            "reviewer_id": reviewer_id,
            "provider": {
                "router_base_url": "https://router.theclaracare.com/v1",
                "http_status": 200,
                "content_type": "application/json",
                "raw_http_body_sha256": "raw" * 16,
                "parsed_review_sha256": f"parsed-{reviewer_id}-{label}" * 8,
            },
            "review": review,
        }

    return {
        "case_id": case_id,
        "protocol": "safety",
        "allowed_labels": ["PASS", "FAIL"],
        "evidence_ids": evidence_ids,
        "reviews": [_result("reviewer_a", left), _result("reviewer_b", right)],
    }


class _FakeHeaders:
    def get_content_type(self) -> str:
        return "application/json"


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers = _FakeHeaders()
        self.status = 200

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def _payload_with_label(label: str) -> bytes:
    review = {"label": label, "rationale": "revised", "evidence_ids": ["e1", "e2"], "confidence": 0.8}
    return json.dumps({"choices": [{"message": {"content": json.dumps(review)}}]}).encode()


def _write_raw(raw_dir: Path, rows: list[dict[str, Any]]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (raw_dir / f"{row['case_id']}.json").write_text(json.dumps(row, sort_keys=True), encoding="utf-8")


@pytest.fixture(autouse=True)
def _router_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLARA_ROUTER_API_KEY", "test-key-not-committed")


def test_agreed_case_passes_through_without_reconciliation(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    _write_raw(raw_dir, [_row(case_id="c1", left="PASS", right="PASS")])
    summary = reconcile(raw_dir=raw_dir, output_dir=out_dir, urlopen=lambda _req, **_kw: _FakeResponse(_payload_with_label("PASS")))
    assert summary["reconciliation_rounds"] == 1
    result = json.loads((out_dir / "c1.json").read_text())
    assert result["status"] == "AGREED"
    assert "reconciliation_prompts" not in result
    assert "revised_response_hashes" not in result


def test_disagreement_records_separate_prompt_hashes_and_revised_hashes(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    _write_raw(raw_dir, [_row(case_id="c1", left="PASS", right="FAIL")])
    summary = reconcile(raw_dir=raw_dir, output_dir=out_dir, urlopen=lambda _req, **_kw: _FakeResponse(_payload_with_label("PASS")))
    assert summary["case_count"] == 1
    assert summary["unresolved_count"] == 0
    result = json.loads((out_dir / "c1.json").read_text())
    assert result["status"] == "AGREED_AFTER_RECONCILIATION"
    prompts = result["reconciliation_prompts"]
    assert set(prompts) == {"reviewer_a", "reviewer_b"}
    assert prompts["reviewer_a"] != prompts["reviewer_b"]
    hashes = result["revised_response_hashes"]
    assert set(hashes) == {"reviewer_a", "reviewer_b"}
    assert hashes["reviewer_a"] == result["revised_reviews"][0]["provider"]["parsed_review_sha256"]
    assert hashes["reviewer_b"] == result["revised_reviews"][1]["provider"]["parsed_review_sha256"]


def test_remaining_disagreement_is_unresolved(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    _write_raw(raw_dir, [_row(case_id="c1", left="PASS", right="FAIL")])
    state = {"calls": 0}

    def _fake(_request: Any, **_kw: Any) -> _FakeResponse:
        state["calls"] += 1
        label = "FAIL" if state["calls"] == 1 else "PASS"
        return _FakeResponse(_payload_with_label(label))

    summary = reconcile(raw_dir=raw_dir, output_dir=out_dir, urlopen=_fake)
    assert summary["unresolved_count"] == 1
    assert summary["unresolved_rate"] == 1.0
    result = json.loads((out_dir / "c1.json").read_text())
    assert result["status"] == "UNRESOLVED"


def test_mixed_cases_and_duplicate_markers_preserved(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    rows = [
        _row(case_id="c1", left="PASS", right="PASS"),
        _row(case_id="c2", left="PASS", right="FAIL"),
    ]
    dup = _row(case_id="c2__dup1", left="PASS", right="FAIL")
    dup["frozen_duplicate"] = True
    dup["duplicate_of"] = "c2"
    _write_raw(raw_dir, [*rows, dup])
    summary = reconcile(raw_dir=raw_dir, output_dir=out_dir, urlopen=lambda _req, **_kw: _FakeResponse(_payload_with_label("PASS")))
    assert summary["case_count"] == 3
    assert summary["unresolved_count"] == 0
    result = json.loads((out_dir / "c2__dup1.json").read_text())
    assert result["frozen_duplicate"] is True
    assert result["duplicate_of"] == "c2"
