"""Regression coverage for CareGuard's additive wording projection."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from clara_ml.agents import careguard
from clara_ml.llm.model_registry import ModelTask


def test_consumer_wording_is_absent_until_release_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", False)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    assert "consumer_explanation" not in result


def test_consumer_wording_preserves_final_drugbank_result_and_uses_safe_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    assert result["risk"]["level"] in {"high", "critical"}
    assert rendered["headline"] == "Nên được nhân viên y tế đánh giá sớm"
    assert rendered["verifier_passed"] is True
    assert rendered["fallback_used"] is False
    assert (
        "warfarin"
        not in " ".join(
            [rendered["headline"], rendered["summary"], *rendered["next_steps"]]
        ).lower()
    )
    # The existing DrugBank/curated alert and recommendation remain untouched.
    assert result["ddi_alerts"]
    assert result["recommendation"]


def test_unavailable_required_drugbank_wording_never_reassures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_required", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", False)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    assert result["ddi_status"]["conclusion_available"] is False
    assert rendered["verifier_passed"] is True
    assert "không có cảnh báo không đồng nghĩa là an toàn" in str(rendered["safety_text"]).lower()
    assert rendered["fallback_used"] is False


def test_flash_draft_receives_only_closed_facts_and_keeps_final_ddi_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_wording_model_draft_enabled", False)
    baseline = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    monkeypatch.setattr(careguard.settings, "careguard_wording_model_draft_enabled", True)
    captured: dict[str, object] = {}

    class _FakeClient:
        def generate(self, prompt: str, system_prompt: str, *, max_tokens: int):
            captured["prompt"] = prompt
            captured["system_prompt"] = system_prompt
            captured["max_tokens"] = max_tokens
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "headline": "Cần được nhân viên y tế xem lại sớm",
                        "summary": "Kết quả hiện có cần được xem xét cẩn thận.",
                        "why_it_matters": ["Mức độ lưu ý hiện tại cần được đánh giá phù hợp."],
                    }
                )
            )

    def _client(task: ModelTask, *_args: object, **_kwargs: object):
        captured["task"] = task
        return _FakeClient(), SimpleNamespace()

    monkeypatch.setattr(
        "clara_ml.language_renderer.careguard_draft.build_task_client",
        _client,
    )

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    model_input = str(captured["prompt"]).lower()
    assert captured["task"] is ModelTask.CAREGUARD_WORDING_DRAFT
    assert captured["max_tokens"] == 420
    assert "warfarin" not in model_input
    assert "ibuprofen" not in model_input
    assert "drugbank" not in model_input
    assert rendered["headline"] == "Cần được nhân viên y tế xem lại sớm"
    assert rendered["fallback_used"] is False
    assert result["risk"] == baseline["risk"]
    assert result["ddi_alerts"] == baseline["ddi_alerts"]
    assert result["recommendation"] == baseline["recommendation"]
    assert result["risk"]["level"] in {"high", "critical"}


@pytest.mark.parametrize(
    "draft",
    [
        "not-json",
        json.dumps(
            {
                "headline": "Có thể an toàn",
                "summary": "Bạn có thể uống 500 mg ngay.",
                "why_it_matters": ["Không cần hỏi thêm."],
            }
        ),
        json.dumps(
            {
                "headline": "Warfarin cần được xem lại",
                "summary": "Kết quả hiện có cần được xem xét.",
                "why_it_matters": ["Mức độ lưu ý hiện tại cần được đánh giá."],
            }
        ),
    ],
)
def test_flash_draft_malformed_or_unsafe_output_falls_back_to_template(
    monkeypatch: pytest.MonkeyPatch,
    draft: str,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_wording_model_draft_enabled", True)

    class _FakeClient:
        def generate(self, *_args: object, **_kwargs: object):
            return SimpleNamespace(content=draft)

    monkeypatch.setattr(
        "clara_ml.language_renderer.careguard_draft.build_task_client",
        lambda *_args, **_kwargs: (_FakeClient(), SimpleNamespace()),
    )

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    assert rendered["headline"] == "Nên được nhân viên y tế đánh giá sớm"
    assert rendered["fallback_used"] is True
    assert "warfarin" not in " ".join(
        [rendered["headline"], rendered["summary"], *rendered["why_it_matters"]]
    ).lower()
