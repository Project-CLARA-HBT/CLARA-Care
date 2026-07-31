"""Contracts for registry-bound, review-only LifeMap revision pairs."""

from __future__ import annotations

from types import SimpleNamespace

from clara_ml.lifemap import review_proposals
from clara_ml.llm.model_registry import ModelTask


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class _Client:
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, *_args, **_kwargs) -> _Response:
        return _Response(self.content)


def _facts() -> dict:
    return {
        "facts": [
            {"revision_id": "revision_a", "field_key": "symptom_report", "payload": {"symptom": "đau đầu"}},
            {"revision_id": "revision_b", "field_key": "symptom_report", "payload": {"symptom": "đau đầu dữ dội"}},
        ]
    }


def test_review_proposals_use_the_registered_flash_task_and_only_valid_pairs(monkeypatch) -> None:
    calls: list[ModelTask] = []

    def _client(task: ModelTask, *_args, **_kwargs):
        calls.append(task)
        return (
            _Client(
                '{"proposals":[{"relation":"possible_conflict",'
                '"revision_ids":["revision_b","revision_a"],'
                '"field_key":"symptom_report"}]}'
            ),
            SimpleNamespace(
                model_version="deepseek-v4-flash.task-route.v1",
                prompt_version="lifemap-review-proposals.v1",
            ),
        )

    monkeypatch.setattr(review_proposals, "build_task_client", _client)

    result = review_proposals.propose_review_pairs(_facts(), task_settings=object())

    assert calls == [ModelTask.LIFEMAP_REVIEW_PROPOSALS]
    assert result["degraded"] is False
    assert result["proposals"] == [
        {
            "source": "llm",
            "relation": "possible_conflict",
            "revision_ids": ["revision_a", "revision_b"],
            "field_key": "symptom_report",
        }
    ]


def test_review_proposals_fail_soft_when_model_returns_an_unauthorized_or_cross_field_pair(monkeypatch) -> None:
    monkeypatch.setattr(
        review_proposals,
        "build_task_client",
        lambda *_args, **_kwargs: (
            _Client(
                '{"proposals":[{"relation":"possible_duplicate",'
                '"revision_ids":["revision_a","not_authorized"],'
                '"field_key":"symptom_report"}]}'
            ),
            SimpleNamespace(
                model_version="deepseek-v4-flash.task-route.v1",
                prompt_version="lifemap-review-proposals.v1",
            ),
        ),
    )

    result = review_proposals.propose_review_pairs(_facts(), task_settings=object())

    assert result["degraded"] is True
    assert result["proposals"] == []
