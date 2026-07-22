from __future__ import annotations

from dataclasses import dataclass

from clara_ml.agents import council_model


@dataclass
class _Response:
    content: str
    model: str = "clinical-test-model"


class _Client:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, **_kwargs) -> _Response:
        self.prompts.append(prompt)
        return _Response(
            content=(
                '{"relevant_observations":["Chest pain is reported"],'
                '"hypotheses":["Acute cause requires exclusion"],'
                '"supporting_case_fact_ids":["symptoms-1"],'
                '"contradicting_case_fact_ids":[],'
                '"missing_decisive_data":["ECG"],'
                '"triage":"emergency_escalation","confidence":0.7,'
                '"safe_next_action_class":"urgent in-person evaluation"}'
            )
        )


def test_shadow_disabled_is_inert(monkeypatch) -> None:
    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", False)
    assert council_model.run_model_council_shadow({}, ["cardiology"]) == {
        "status": "disabled",
        "assessments": [],
        "failures": [],
    }


def test_independent_assessment_cites_stable_case_facts(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", True)
    monkeypatch.setattr(council_model, "_client", lambda: client)

    result = council_model.run_model_council_shadow(
        {
            "symptoms": ["chest pain"],
            "labs": {"troponin": 0.1},
            "medications": ["warfarin"],
            "history": ["atrial fibrillation"],
        },
        ["cardiology", "pharmacology"],
    )

    assert result["status"] == "complete"
    assert result["mode"] == "shadow"
    assert len(result["assessments"]) == 2
    assert all(a["evidence_scope"] == "case_packet_only" for a in result["assessments"])
    assert all(a["supporting_case_fact_ids"] == ["symptoms-1"] for a in result["assessments"])
    assert len(client.prompts) == 2
    assert all("CASE_PACKET=" in prompt for prompt in client.prompts)


def test_invalid_model_payload_fails_closed(monkeypatch) -> None:
    class InvalidClient:
        def generate(self, *_args, **_kwargs) -> _Response:
            return _Response(content="not json")

    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", True)
    monkeypatch.setattr(council_model, "_client", lambda: InvalidClient())
    result = council_model.run_model_council_shadow(
        {"symptoms": ["headache"]}, ["neurology"]
    )
    assert result["status"] == "unavailable"
    assert result["assessments"] == []
    assert result["failures"] == [
        {"specialist": "neurology", "code": "invalid_schema"}
    ]
