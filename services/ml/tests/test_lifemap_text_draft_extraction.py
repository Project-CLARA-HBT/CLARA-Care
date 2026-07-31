"""Exact-span contracts for the optional LifeMap free-text LLM route."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from clara_ml import main


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class _Client:
    def __init__(self, content: str) -> None:
        self._content = content

    def generate(self, *_args, **_kwargs) -> _Response:
        return _Response(self._content)


def test_text_draft_extraction_reconstructs_only_exact_source_spans(monkeypatch) -> None:
    source = "Tối qua tôi ngủ khoảng 7 giờ và sáng nay chóng mặt."
    checksum = hashlib.sha256(source.encode()).hexdigest()
    start = source.index("Tối qua")
    end = source.index("và") - 1
    monkeypatch.setattr(
        main,
        "build_task_client",
        lambda *_args, **_kwargs: (
            _Client(
                '{"source_text_checksum": "'
                + checksum
                + '", "candidates": [{"category": "sleep", "start": '
                + str(start)
                + ', "end": '
                + str(end)
                + "}]}"
            ),
            SimpleNamespace(
                model_version="deepseek-v4-flash.task-route.v1",
                prompt_version="lifemap-text-draft-extraction.v1",
            ),
        ),
    )

    result = main._extract_lifemap_text_drafts_with_llm(
        source,
        source_text_checksum=checksum,
        locale="vi",
    )

    assert result["validated_boundary"] == "lifemap-text-draft-v1"
    assert result["draft_only"] is True
    assert result["candidates"] == [
        {"category": "sleep", "start": start, "end": end}
    ]


def test_text_draft_extraction_rejects_model_text_or_overlapping_spans(monkeypatch) -> None:
    source = "Tôi đang thấy mệt và khó ngủ."
    checksum = hashlib.sha256(source.encode()).hexdigest()
    monkeypatch.setattr(
        main,
        "build_task_client",
        lambda *_args, **_kwargs: (
            _Client(
                '{"source_text_checksum": "'
                + checksum
                + '", "candidates": [{"category": "symptom", "start": 0, '
                '"end": 10, "text": "bịa"}]}'
            ),
            SimpleNamespace(
                model_version="deepseek-v4-flash.task-route.v1",
                prompt_version="lifemap-text-draft-extraction.v1",
            ),
        ),
    )

    with pytest.raises(ValueError, match="candidate_invalid"):
        main._extract_lifemap_text_drafts_with_llm(
            source,
            source_text_checksum=checksum,
            locale="vi",
        )
