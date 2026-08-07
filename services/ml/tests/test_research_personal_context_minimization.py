from clara_ml.agents.research_tier2 import _build_personal_context_suffix


def test_personal_context_suffix_uses_coarse_context_and_safety_boundary() -> None:
    value = _build_personal_context_suffix(
        {
            "profile": {
                "age_band": "40_64",
                "gender": "female",
                # Old stored payload fields must not be rendered if present.
                "full_name": "Nguyen Van A",
                "date_of_birth": "1980-01-01",
            },
            "allergies": [{"name": "penicillin"}],
            "conditions": [{"name": "hypertension"}],
            "medications": [{"name": "amlodipine", "dose": "5 mg"}],
        },
        answer_language="en",
    )

    assert "Age band: 40_64" in value
    assert "Nguyen Van A" not in value
    assert "1980-01-01" not in value
    assert "Do not infer a diagnosis" in value
