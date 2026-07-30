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
                '{"supported_findings":[{"statement":"Chest pain is reported",'
                '"evidence_ids":["symptoms-1"]}],'
                '"evidence_ids":["symptoms-1"],'
                '"supporting_case_fact_ids":["symptoms-1"],'
                '"contradicting_case_fact_ids":[],'
                '"missing_decisive_data":["ECG"],"uncertainties":["No ECG supplied"],'
                '"suggested_questions":["Can an ECG be obtained?"],'
                '"abstain":false,"abstention_reason":"",'
                '"triage":"emergency_escalation",'
                '"safe_next_action_class":"emergency_evaluation"}'
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
    assert all(a["evidence_ids"] == ["symptoms-1"] for a in result["assessments"])
    assert all(a["evidence_status"] == "supported_with_uncertainties" for a in result["assessments"])
    assert all(a["verification"]["self_verification_performed"] is False for a in result["assessments"])
    assert all("confidence" not in a for a in result["assessments"])
    assert all("relevant_observations" not in a for a in result["assessments"])
    assert all("hypotheses" not in a for a in result["assessments"])
    assert all(a["safe_next_action_class"] == "emergency_evaluation" for a in result["assessments"])
    assert result["adjudication"]["status"] == "not_release_eligible"
    assert result["adjudication"]["release_effect"] == "none_shadow_only"
    assert len(client.prompts) == 2
    assert all("CASE_PACKET=" in prompt for prompt in client.prompts)
    assert all("Do not return confidence, probability" in prompt for prompt in client.prompts)


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


def test_model_finding_without_bound_case_fact_fails_closed(monkeypatch) -> None:
    class UnsupportedFindingClient:
        def generate(self, *_args, **_kwargs) -> _Response:
            return _Response(
                content=(
                    '{"supported_findings":[{"statement":"Invented claim",'
                    '"evidence_ids":["not-a-case-fact"]}],'
                    '"evidence_ids":["not-a-case-fact"],"uncertainties":[], '
                    '"suggested_questions":[],"abstain":false,"abstention_reason":"",'
                    '"triage":"routine_follow_up","safe_next_action_class":"clinician_review"}'
                )
            )

    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", True)
    monkeypatch.setattr(council_model, "_client", lambda: UnsupportedFindingClient())

    result = council_model.run_model_council_shadow(
        {"symptoms": ["headache"]}, ["neurology"]
    )

    assert result["status"] == "unavailable"
    assert result["assessments"] == []
    assert result["failures"] == [
        {"specialist": "neurology", "code": "invalid_schema"}
    ]


def test_abstention_requires_an_explicit_evidence_gap(monkeypatch) -> None:
    class AbstainingClient:
        def generate(self, *_args, **_kwargs) -> _Response:
            return _Response(
                content=(
                    '{"supported_findings":[],"evidence_ids":[],"uncertainties":['
                    '"Symptom timing is absent"],"missing_decisive_data":["Onset"],'
                    '"suggested_questions":["When did symptoms begin?"],'
                    '"abstain":true,"abstention_reason":"Timing is required before review",'
                    '"triage":"same_day_review","safe_next_action_class":"same_day_in_person_review"}'
                )
            )

    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", True)
    monkeypatch.setattr(council_model, "_client", lambda: AbstainingClient())

    result = council_model.run_model_council_shadow(
        {"symptoms": ["headache"]}, ["neurology"]
    )

    assessment = result["assessments"][0]
    assert assessment["abstained"] is True
    assert assessment["evidence_status"] == "abstained_insufficient_evidence"
    assert result["adjudication"]["abstention_count"] == 1
    assert result["adjudication"]["requires_human_review"] is True


def test_model_action_class_cannot_undercut_its_triage_vote(monkeypatch) -> None:
    class UnsafeActionClassClient:
        def generate(self, *_args, **_kwargs) -> _Response:
            return _Response(
                content=(
                    '{"supported_findings":[{"statement":"Chest pain is reported",'
                    '"evidence_ids":["symptoms-1"]}],'
                    '"evidence_ids":["symptoms-1"],'
                    '"supporting_case_fact_ids":["symptoms-1"],'
                    '"uncertainties":[],"suggested_questions":[],'
                    '"abstain":false,"abstention_reason":"",'
                    '"triage":"emergency_escalation",'
                    '"safe_next_action_class":"clinician_review"}'
                )
            )

    monkeypatch.setattr(council_model.settings, "council_llm_shadow_enabled", True)
    monkeypatch.setattr(council_model, "_client", lambda: UnsafeActionClassClient())

    result = council_model.run_model_council_shadow(
        {"symptoms": ["chest pain"]}, ["cardiology"]
    )

    assert result["status"] == "unavailable"
    assert result["assessments"] == []
    assert result["failures"] == [{"specialist": "cardiology", "code": "invalid_schema"}]
