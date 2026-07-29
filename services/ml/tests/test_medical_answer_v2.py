from __future__ import annotations

import pytest
from pydantic import ValidationError

from clara_ml.medical_answer_v2 import (
    build_medical_answer_v2,
    detect_emergency_red_flags,
    validate_medical_answer_v2,
)


def _build(**overrides):
    inputs = {
        "answer": "This finding needs review.",
        "audience": "normal",
        "intent": "symptom_triage",
        "urgency_level": "clinical_review",
        "emergency_red_flags": [],
        "policy_action": "allow",
        "model_used": "deepseek-test",
        "evidence_ledger": [],
        "factcheck": None,
        "clinical_context": {},
        "missing_information": [],
        "careguard": None,
    }
    inputs.update(overrides)
    return build_medical_answer_v2(**inputs)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Tôi đang khó thở", "breathing_difficulty"),
        ("Sudden face droop and slurred speech", "stroke_signs"),
        ("Tôi đã uống thuốc quá liều", "overdose"),
    ],
)
def test_red_flag_gate_is_bilingual_and_deterministic(query: str, expected: str) -> None:
    assert expected in detect_emergency_red_flags(query)


def test_red_flag_gate_does_not_trigger_simple_negation() -> None:
    assert detect_emergency_red_flags("Tôi không khó thở") == []
    assert detect_emergency_red_flags("No shortness of breath") == []


def test_unsupported_actionable_claim_is_suppressed_from_actions() -> None:
    artifact = _build(answer="Start warfarin today.")

    assert artifact["claims"][0]["status"] == "suppressed"
    assert artifact["claims"][0]["decision_ready"] is False
    assert artifact["actions_today"] == []
    assert artifact["uncertainty"]["level"] == "high"


def test_verified_claim_uses_stable_snapshot_id() -> None:
    evidence = [{"source": "guideline", "title": "Guideline", "excerpt": "Review is advised."}]
    first = _build(
        answer="Review is advised.",
        evidence_ledger=evidence,
        factcheck={"verdict": "pass", "severity": "low"},
    )
    second = _build(
        answer="Review is advised.",
        evidence_ledger=evidence,
        factcheck={"verdict": "pass", "severity": "low"},
    )

    assert first["evidence"][0]["evidence_id"] == second["evidence"][0]["evidence_id"]
    assert first["claims"][0]["status"] == "supported"
    assert first["claims"][0]["evidence_ids"] == [first["evidence"][0]["evidence_id"]]


def test_careguard_critical_finding_survives_verbatim() -> None:
    finding = {
        "type": "drug_drug",
        "severity": "critical",
        "medications": ["a", "b"],
        "message": "Critical DrugBank finding — do not discard this text.",
        "source": "drugbank",
    }
    artifact = _build(
        clinical_context={"medications": ["a", "b"]},
        careguard={
            "risk": {"level": "critical"},
            "ddi_alerts": [finding],
            "recommendation": "Urgent review",
            "metadata": {
                "source_used": ["drugbank"],
                "drugbank": {"state": "ready", "version": "db-v1"},
            },
        },
    )

    assert artifact["medication_safety"]["findings"] == [finding]
    assert artifact["medication_safety"]["drugbank"]["state"] == "ready"


def test_medical_answer_includes_verified_plain_language_rendering() -> None:
    artifact = _build(
        urgency_level="clinical_review",
        evidence_ledger=[{"source": "guideline", "title": "Guideline", "excerpt": "Review."}],
        factcheck={"verdict": "pass"},
    )

    rendered = artifact["rendered_explanation"]
    assert rendered["verifier_passed"] is True
    assert rendered["fallback_used"] is False
    assert rendered["source_labels"] == ["guideline"]
    assert "tư vấn" not in rendered["summary"].lower()


def test_validator_rejects_dangling_claim_evidence() -> None:
    artifact = _build()
    artifact["claims"] = [
        {
            "claim_id": "cl-x",
            "text": "A claim",
            "status": "supported",
            "evidence_ids": ["ev-missing"],
            "actionable": False,
            "decision_ready": False,
        }
    ]

    with pytest.raises(ValidationError, match="evidence absent"):
        validate_medical_answer_v2(artifact)


def test_emergency_contract_requires_and_leads_with_immediate_action() -> None:
    artifact = _build(
        urgency_level="emergency",
        emergency_red_flags=["breathing_difficulty"],
        policy_action="escalate",
        answer="Seek emergency care now.",
    )

    assert artifact["urgency"]["emergency"] is True
    assert artifact["actions_now"]
    assert artifact["red_flags"] == ["breathing_difficulty"]
