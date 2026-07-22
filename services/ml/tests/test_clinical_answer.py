from clara_ml.clinical_answer import build_clinical_answer_package


def test_medical_answer_package_links_real_evidence_and_missing_context() -> None:
    package = build_clinical_answer_package(
        answer="A grounded answer.",
        intent="medication_safety",
        emergency=False,
        policy_action="allow",
        model_used="deepseek-test",
        retrieved_context=[
            {
                "id": "label-1",
                "text": "Official label excerpt",
                "metadata": {
                    "title": "Official label",
                    "url": "https://example.test/label",
                    "trust_tier": 1,
                    "effective_date": "2026-01-01",
                },
            }
        ],
        factcheck={"verdict": "pass", "severity": "low"},
        clinical_context={"medications": ["warfarin"]},
        protocol="medication_review",
    )

    assert package is not None
    assert package["claim_support"]["evidence_ids"] == ["E1"]
    assert package["evidence_ledger"][0]["trust_tier"] == 1
    assert "medications" not in [item["field"] for item in package["missing_information"]]
    assert package["provenance"]["fallback_used"] is False


def test_degraded_answer_never_claims_supported() -> None:
    package = build_clinical_answer_package(
        answer="Safe fallback",
        intent="symptom_triage",
        emergency=False,
        policy_action="warn",
        model_used="local-synth-v1",
        retrieved_context=[],
        factcheck=None,
    )

    assert package is not None
    assert package["claim_support"]["status"] == "degraded"
    assert package["uncertainty"]["level"] == "high"


def test_plain_chat_nonmedical_can_skip_workbench_package() -> None:
    assert (
        build_clinical_answer_package(
            answer="Hello",
            intent="general_guidance",
            emergency=False,
            policy_action="allow",
            model_used="deepseek-test",
            retrieved_context=[],
            factcheck=None,
            protocol="chat",
        )
        is None
    )
