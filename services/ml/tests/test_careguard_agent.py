from clara_ml.agents.careguard import (
    _load_local_ddi_rules,
    _load_vn_drug_dictionary,
    run_careguard_analyze,
)


def test_high_risk_pair_escalates_to_high() -> None:
    payload = {
        "symptoms": ["nausea"],
        "medications": ["warfarin", "ibuprofen"],
        "allergies": [],
        "labs": {},
    }
    result = run_careguard_analyze(payload)

    assert result["risk"]["level"] in {"high", "critical"}
    assert result["metadata"]["pipeline"] == "p2-careguard-ddi-standard-v2"
    assert isinstance(result["ddi_alerts"], list)
    assert len(result["ddi_alerts"]) >= 1


def test_local_ddi_rules_loaded_from_versioned_seed_file() -> None:
    rules, version = _load_local_ddi_rules()

    assert version == "v1"
    assert len(rules) >= 50


def test_external_ddi_flag_source_metadata_runtime_vs_env() -> None:
    env_result = run_careguard_analyze({"medications": ["warfarin"]})
    runtime_result = run_careguard_analyze(
        {"medications": ["warfarin"], "external_ddi_enabled": True}
    )

    assert env_result["metadata"]["external_ddi_flag_source"] == "env"
    assert runtime_result["metadata"]["external_ddi_flag_source"] == "runtime"


def test_vn_drug_dictionary_seed_has_minimum_coverage() -> None:
    version, record_count = _load_vn_drug_dictionary()

    assert version.startswith("vn-drug-dictionary")
    assert record_count >= 100


def test_vn_drug_dictionary_maps_panadol_extra_to_active_ingredients() -> None:
    result = run_careguard_analyze(
        {
            "medications": ["Panadol Extra", "Warfarin"],
            "external_ddi_enabled": False,
        }
    )

    metadata = result["metadata"]
    assert metadata["vn_dictionary_mapped_count"] >= 1
    mapped_inputs = [item["input"] for item in metadata["vn_dictionary_mapped_items"]]
    assert "panadol extra" in mapped_inputs

    ddi_pairs = [set(alert.get("medications", [])) for alert in result["ddi_alerts"]]
    assert any({"warfarin", "paracetamol"}.issubset(pair) for pair in ddi_pairs)


def test_decorated_medication_names_still_match_local_ddi_rules() -> None:
    result = run_careguard_analyze(
        {
            "medications": ["Warfarin 5mg", "Ibuprofen 400mg tablet"],
            "external_ddi_enabled": False,
        }
    )

    ddi_pairs = [set(alert.get("medications", [])) for alert in result["ddi_alerts"]]
    assert any({"warfarin", "ibuprofen"}.issubset(pair) for pair in ddi_pairs)
    assert result["metadata"]["normalization_pair_coverage_low"] is False
    assert result["metadata"]["normalized_medication_count"] >= 2
