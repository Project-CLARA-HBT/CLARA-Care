import pytest

from clara_ml.agents.careguard import (
    _load_local_ddi_rules,
    _load_vn_drug_dictionary,
    run_careguard_analyze,
)
from clara_ml.clients.drug_sources import DrugSourceClient, ExternalDDIResult


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


# ---- OpenFDA label-derived alerts (tầng 3 nâng cấp) ----


def test_label_match_word_boundary() -> None:
    text = "Concomitant use with ibuprofen may increase bleeding risk."
    assert DrugSourceClient._match_in_label(text, "ibuprofen") is not None
    # "asa" KHÔNG được match substring trong "asacol"
    assert DrugSourceClient._match_in_label("Avoid asacol therapy.", "asa") is None
    # không có text / không có tên → None
    assert DrugSourceClient._match_in_label("", "warfarin") is None


def test_label_severity_inference_conservative() -> None:
    assert DrugSourceClient._infer_label_severity("this combination is contraindicated") == "high"
    assert DrugSourceClient._infer_label_severity("monitor closely for bleeding") == "medium"
    assert DrugSourceClient._infer_label_severity("may be used together") == "medium"
    # KHÔNG bao giờ critical từ free text (cap ở high)
    assert DrugSourceClient._infer_label_severity("severe fatal contraindicated") != "critical"


def test_clone_result_preserves_openfda_alerts_and_rxnav_status() -> None:
    original = ExternalDDIResult(
        openfda_alerts=[
            {
                "type": "drug_drug",
                "severity": "high",
                "medications": ["warfarin", "ibuprofen"],
                "message": "label snippet",
                "source": "openfda",
            }
        ],
        rxnav_status="endpoint_retired",
    )
    cloned = DrugSourceClient._clone_result(original)
    assert cloned.openfda_alerts == original.openfda_alerts
    assert cloned.openfda_alerts is not original.openfda_alerts  # deep copy
    assert cloned.rxnav_status == "endpoint_retired"


def test_openfda_label_alert_flows_to_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        return ExternalDDIResult(
            openfda_alerts=[
                {
                    "type": "drug_drug",
                    "severity": "high",
                    "medications": ["alphaone", "betatwo"],
                    "message": "…avoid concomitant use of alphaone and betatwo…",
                    "source": "openfda",
                }
            ],
            openfda_pairs_checked=1,
            source_used=["openfda"],
            rxnav_status="endpoint_retired",
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {"medications": ["alphaone", "betatwo"], "external_ddi_enabled": True}
    )

    alerts = result["ddi_alerts"]
    assert len(alerts) == 1
    assert "openfda" in alerts[0].get("source", "")
    assert alerts[0].get("severity") == "high"
    assert result["metadata"]["openfda_alert_count"] == 1


def test_openfda_alert_does_not_clobber_local_message(monkeypatch: pytest.MonkeyPatch) -> None:
    # clopidogrel+omeprazole là local rule severity "medium"; openfda alert "high"
    # cho cùng cặp → severity được nâng lên high NHƯNG message vẫn là câu VN của local.
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        return ExternalDDIResult(
            openfda_alerts=[
                {
                    "type": "drug_drug",
                    "severity": "high",
                    "medications": ["clopidogrel", "omeprazole"],
                    "message": "english label snippet should not override curated vi",
                    "source": "openfda",
                }
            ],
            source_used=["openfda"],
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {"medications": ["clopidogrel", "omeprazole"], "external_ddi_enabled": True}
    )

    pair_alert = next(
        a for a in result["ddi_alerts"] if {"clopidogrel", "omeprazole"}.issubset(a["medications"])
    )
    assert pair_alert["severity"] == "high"  # severity được nâng
    assert set(pair_alert["source"].split(",")) == {"local_rules", "openfda"}
    # message KHÔNG bị snippet tiếng Anh ghi đè
    assert "english label snippet" not in pair_alert["message"].lower()


def test_rxnav_status_surfaced_not_in_source_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_fetch_ddi_context(self: object, medications: list[str]) -> ExternalDDIResult:
        return ExternalDDIResult(
            openfda_alerts=[
                {
                    "type": "drug_drug",
                    "severity": "medium",
                    "medications": ["alphaone", "betatwo"],
                    "message": "snippet",
                    "source": "openfda",
                }
            ],
            source_used=["openfda"],
            rxnav_status="endpoint_retired",
        )

    monkeypatch.setattr(
        "clara_ml.agents.careguard.DrugSourceClient.fetch_ddi_context",
        _fake_fetch_ddi_context,
    )

    result = run_careguard_analyze(
        {"medications": ["alphaone", "betatwo"], "external_ddi_enabled": True}
    )

    metadata = result["metadata"]
    assert metadata["rxnav_status"] == "endpoint_retired"
    assert "rxnav" not in metadata["source_errors"]
    # rxnav chết KHÔNG được làm flip fallback_used khi openfda đã có tín hiệu
    assert metadata["fallback_used"] is False
