import pytest

from clara_ml.agents.careguard import (
    _load_local_ddi_rules,
    _load_vn_drug_dictionary,
    run_careguard_analyze,
)
from clara_ml.clients.drug_sources import ExternalDDIResult


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


def test_medium_risk_pair_no_longer_collapses_to_low() -> None:
    result = run_careguard_analyze(
        {
            "medications": ["clopidogrel", "omeprazole"],
            "external_ddi_enabled": False,
        }
    )

    assert any(alert.get("severity") == "medium" for alert in result["ddi_alerts"])
    assert result["risk"]["level"] == "medium"
    assert result["risk"]["score"] >= 1


def test_low_risk_pair_stays_low() -> None:
    result = run_careguard_analyze(
        {
            "medications": ["cetirizine", "diazepam"],
            "external_ddi_enabled": False,
        }
    )

    assert any(alert.get("severity") == "low" for alert in result["ddi_alerts"])
    assert result["risk"]["level"] == "low"


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


def test_openfda_only_evidence_does_not_create_synthetic_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        assert len(medications) >= 2
        return ExternalDDIResult(
            openfda_evidence={
                tuple(sorted(("alphaone", "betatwo"))): {
                    "label_mentions": 2,
                    "event_reports": 12,
                }
            },
            openfda_pairs_checked=1,
            source_used=["openfda"],
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {
            "medications": ["alphaone", "betatwo"],
            "external_ddi_enabled": True,
        }
    )

    assert result["ddi_alerts"] == []
    assert result["risk"]["level"] == "low"


def test_openfda_evidence_enriches_existing_rxnav_alert_without_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        assert len(medications) >= 2
        return ExternalDDIResult(
            rxnav_alerts=[
                {
                    "type": "drug_drug",
                    "severity": "medium",
                    "medications": ["alphaone", "betatwo"],
                    "message": "RxNav interaction alert.",
                    "source": "rxnav",
                }
            ],
            openfda_evidence={
                tuple(sorted(("alphaone", "betatwo"))): {
                    "label_mentions": 3,
                    "event_reports": 25,
                }
            },
            openfda_pairs_checked=1,
            source_used=["rxnav", "openfda"],
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {
            "medications": ["alphaone", "betatwo"],
            "external_ddi_enabled": True,
        }
    )

    ddi_alerts = result["ddi_alerts"]
    assert len(ddi_alerts) == 1
    alert = ddi_alerts[0]
    assert set(alert.get("source", "").split(",")) == {"openfda", "rxnav"}
    assert "tương tác" in str(alert.get("message", "")).lower()
    assert alert.get("evidence", {}).get("openfda_label_mentions") == 3
    assert alert.get("evidence", {}).get("openfda_event_reports") == 25


def test_openfda_http_400_is_suppressed_when_rxnav_has_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        assert len(medications) >= 2
        return ExternalDDIResult(
            rxnav_alerts=[
                {
                    "type": "drug_drug",
                    "severity": "low",
                    "medications": ["alphaone", "betatwo"],
                    "message": "Potential interaction identified by RxNav.",
                    "source": "rxnav",
                }
            ],
            openfda_pairs_checked=1,
            source_used=["rxnav"],
            source_errors={"openfda": ["http_400:bad_request"]},
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {
            "medications": ["alphaone", "betatwo"],
            "external_ddi_enabled": True,
        }
    )

    metadata = result["metadata"]
    assert "openfda" not in metadata["source_errors"]
    assert metadata["fallback_used"] is False


def test_openfda_http_400_kept_when_no_other_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        assert len(medications) >= 2
        return ExternalDDIResult(
            openfda_pairs_checked=1,
            source_errors={"openfda": ["http_400:bad_request"]},
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {
            "medications": ["alphaone", "betatwo"],
            "external_ddi_enabled": True,
        }
    )

    metadata = result["metadata"]
    assert metadata["source_errors"].get("openfda") == ["http_400:bad_request"]
    assert metadata["fallback_used"] is True
