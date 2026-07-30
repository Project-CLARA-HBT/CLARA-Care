from __future__ import annotations

from types import SimpleNamespace

from clara_ml.scribe import correction


def test_correction_is_disabled_without_explicit_feature_flag(monkeypatch) -> None:
    monkeypatch.setattr(correction.settings, "scribe_medical_correction_enabled", False)

    result = correction.propose_medical_asr_corrections("toi uong para", language="vi")

    assert result == {"status": "disabled", "suggestions": [], "applied": False}


def test_correction_returns_source_spanned_review_proposal_without_mutating_text(monkeypatch) -> None:
    class Client:
        def generate(self, *_args, **_kwargs):
            return SimpleNamespace(
                content=(
                    '{"suggestions":[{"source_text":"panado",'
                    '"replacement_text":"Panadol","kind":"medication_term",'
                    '"rationale":"Possible brand spelling."}]}'
                )
            )

    selection = SimpleNamespace(
        task=SimpleNamespace(value="scribe_asr_correction"),
        prompt_version="scribe-asr-correction.v1",
        contract_schema_version="clara.task-contracts.v2",
        rollback_applied=False,
    )
    monkeypatch.setattr(correction.settings, "scribe_medical_correction_enabled", True)
    monkeypatch.setattr(correction, "build_task_client", lambda *_args: (Client(), selection))

    transcript = "Benh nhan noi da uong panado toi qua."
    result = correction.propose_medical_asr_corrections(transcript, language="vi")

    assert result["status"] == "review_required"
    assert result["applied"] is False
    assert transcript == "Benh nhan noi da uong panado toi qua."
    assert result["suggestions"] == [
        {
            "source_text": "panado",
            "replacement_text": "Panadol",
            "kind": "medication_term",
            "rationale": "Possible brand spelling.",
            "start": 22,
            "end": 28,
            "status": "suggested_requires_clinician_review",
        }
    ]


def test_correction_rejects_new_dose_and_unbound_source(monkeypatch) -> None:
    class Client:
        def generate(self, *_args, **_kwargs):
            return SimpleNamespace(
                content=(
                    '{"suggestions":['
                    '{"source_text":"para","replacement_text":"paracetamol 500mg",'
                    '"kind":"medication_term","rationale":"unsafe"},'
                    '{"source_text":"missing","replacement_text":"x",'
                    '"kind":"clinical_term","rationale":"unbound"}]}'
                )
            )

    selection = SimpleNamespace(
        task=SimpleNamespace(value="scribe_asr_correction"),
        prompt_version="scribe-asr-correction.v1",
        contract_schema_version="clara.task-contracts.v2",
        rollback_applied=False,
    )
    monkeypatch.setattr(correction.settings, "scribe_medical_correction_enabled", True)
    monkeypatch.setattr(correction, "build_task_client", lambda *_args: (Client(), selection))

    result = correction.propose_medical_asr_corrections("toi noi para", language="vi")

    assert result["suggestions"] == []
    assert result["applied"] is False
