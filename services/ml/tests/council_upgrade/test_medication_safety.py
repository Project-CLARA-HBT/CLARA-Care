from __future__ import annotations

from clara_ml.agents import council
from clara_ml.agents.council_medication_safety import evaluate_council_medication_safety


def _careguard_result(
    *,
    level: str = "high",
    alerts: list[dict[str, object]] | None = None,
    drugbank_state: str = "ready",
    conclusion_available: bool = True,
) -> dict[str, object]:
    return {
        "risk": {"level": level},
        "ddi_alerts": alerts if alerts is not None else [{"drug_a": "hidden", "drug_b": "hidden"}],
        "ddi_status": {"conclusion_available": conclusion_available},
        "metadata": {
            "drugbank": {
                "state": drugbank_state,
                "version": "drugbank-2026-07",
            },
            "source_errors": {"drugbank": ["must-not-leak"]},
        },
    }


def test_council_medication_tool_forces_strict_drugbank_and_sanitizes_output() -> None:
    received: list[dict[str, object]] = []

    def runner(payload: dict[str, object]) -> dict[str, object]:
        received.append(payload)
        return _careguard_result(alerts=[{"drug_a": "warfarin"}, {"drug_b": "aspirin"}])

    result = evaluate_council_medication_safety(["warfarin", "aspirin"], runner=runner)

    assert received == [
        {
            "medications": ["warfarin", "aspirin"],
            "drugbank_required": True,
            "external_ddi_enabled": False,
            "locale": "vi",
        }
    ]
    assert result == {
        "state": "checked",
        "drugbank_state": "ready",
        "drugbank_version": "drugbank-2026-07",
        "alert_ids": ["council-ddi-alert-1", "council-ddi-alert-2"],
        "triage_floor": "same_day_review",
        "review_required": True,
    }
    assert "warfarin" not in str(result)
    assert "source_errors" not in str(result)


def test_council_medication_tool_fails_closed_for_unavailable_drugbank() -> None:
    result = evaluate_council_medication_safety(
        ["warfarin", "aspirin"],
        runner=lambda _payload: _careguard_result(
            level="unknown",
            drugbank_state="unavailable",
            conclusion_available=False,
        ),
    )

    assert result == {
        "state": "unavailable",
        "drugbank_state": "unavailable",
        "drugbank_version": "drugbank-2026-07",
        "alert_ids": [],
        "triage_floor": None,
        "review_required": True,
    }


def test_enabled_council_monotonically_applies_careguard_triage_floor(monkeypatch) -> None:
    monkeypatch.setattr(council.settings, "council_medication_safety_enabled", True)
    monkeypatch.setattr(council.settings, "council_llm_shadow_enabled", False)
    monkeypatch.setattr(
        council,
        "evaluate_council_medication_safety",
        lambda _medications: {
            "state": "checked",
            "drugbank_state": "ready",
            "drugbank_version": "drugbank-2026-07",
            "alert_ids": ["council-ddi-alert-1"],
            "triage_floor": "same_day_review",
            "review_required": True,
        },
    )

    result = council.run_council(
        {
            "symptoms": ["mild fatigue for two days"],
            "medications": ["warfarin", "aspirin"],
            "specialists": ["cardiology", "neurology"],
        }
    )

    assert result["council_consensus"]["baseline_winning_triage"] == "routine_follow_up"
    assert result["council_consensus"]["winning_triage"] == "same_day_review"
    assert result["council_consensus"]["safety_floor_applied"] is True
    assert result["medication_safety"] == {
        "state": "checked",
        "drugbank_state": "ready",
        "drugbank_version": "drugbank-2026-07",
        "alert_ids": ["council-ddi-alert-1"],
        "triage_floor": "same_day_review",
        "review_required": True,
    }
    assert result["analyze"]["medication_safety_review_required"] is True
    assert "Medication safety screening requires same-day review" in result["final_recommendation"]


def test_disabled_council_keeps_legacy_shape_and_does_not_invoke_tool(monkeypatch) -> None:
    monkeypatch.setattr(council.settings, "council_medication_safety_enabled", False)

    def should_not_run(_medications: list[str]) -> dict[str, object]:
        raise AssertionError("disabled medication-safety tool must not run")

    monkeypatch.setattr(council, "evaluate_council_medication_safety", should_not_run)
    result = council.run_council({"symptoms": ["mild fatigue"], "medications": ["warfarin"]})

    assert "medication_safety" not in result
    assert "medication_safety_review_required" not in result["analyze"]
