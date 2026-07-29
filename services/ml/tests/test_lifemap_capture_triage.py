"""Closed-schema semantic triage contracts for Universal Capture."""

from __future__ import annotations

import pytest

from clara_ml import main


class _Response:
    model = "deepseek-test"

    def __init__(self, content: str) -> None:
        self.content = content


class _Client:
    model = "deepseek-test"

    def __init__(self, content: str) -> None:
        self._content = content

    def generate(self, *_args, **_kwargs) -> _Response:
        return _Response(self._content)


def test_capture_triage_uses_closed_schema_for_indirect_vietnamese_emergency(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        main,
        "_build_deepseek_client",
        lambda: _Client(
            '{"emergency": true, "confidence": 0.93, '
            '"rationale_code": "active_emergency"}'
        ),
    )

    result = main._classify_lifemap_capture_with_llm(
        "Người bệnh đang tím tái, thở hổn hển và lơ mơ.", locale="vi"
    )

    assert result["emergency"] is True
    assert result["rationale_code"] == "active_emergency"
    assert result["model_used"] == "deepseek-test"


def test_capture_triage_rejects_an_inconsistent_model_verdict(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_build_deepseek_client",
        lambda: _Client(
            '{"emergency": false, "confidence": 0.9, '
            '"rationale_code": "active_emergency"}'
        ),
    )

    with pytest.raises(ValueError, match="inconsistent verdict"):
        main._classify_lifemap_capture_with_llm("đang lơ mơ", locale="vi")
