from __future__ import annotations

from clara_ml.medical_harness import postprocess_stages, preflight_harness
from clara_ml.routing import P1RoleIntentRouter


def test_preflight_orders_emergency_before_medication_and_bypasses_ddi() -> None:
    result = preflight_harness(
        query="Tôi khó thở và đau ngực dữ dội",
        role_hint="normal",
        clinical_context={"medications": ["warfarin", "ibuprofen"]},
        router=P1RoleIntentRouter(),
    )

    assert result.route.emergency is True
    assert result.red_flags
    assert result.careguard is None
    assert [stage["stage"] for stage in result.stages] == [
        "normalize_redact",
        "intent_acuity",
        "emergency_gate",
        "missing_information",
        "medication_safety",
    ]
    assert result.stages[-1]["status"] == "bypassed_emergency"


def test_preflight_runs_deterministic_medication_gate_and_missing_info() -> None:
    result = preflight_harness(
        query="Kiểm tra tương tác thuốc",
        role_hint="normal",
        clinical_context={"medications": ["warfarin", "ibuprofen"]},
        router=P1RoleIntentRouter(),
    )

    assert result.route.emergency is False
    assert result.careguard is not None
    assert result.stages[-1]["status"] == "checked"
    assert {item["field"] for item in result.missing_information} >= {"age", "allergies"}


def test_semantic_triage_clears_negated_emergency_phrases() -> None:
    result = preflight_harness(
        query=(
            "Huyết áp ở nhà khoảng 150/95 nhưng tôi không đau ngực hay khó thở. "
            "Tôi nên làm gì tiếp theo?"
        ),
        role_hint="normal",
        clinical_context={},
        router=P1RoleIntentRouter(),
        semantic_emergency=False,
    )

    assert result.route.emergency is False
    assert result.route.intent == "symptom_triage"
    assert result.stages[2]["status"] == "clear"
    assert result.stages[2]["retrieval_bypassed"] is False


def test_postprocess_exposes_stage_metadata_without_user_input() -> None:
    result = preflight_harness(
        query="Tôi bị sốt, cần biết nên làm gì",
        role_hint="normal",
        clinical_context={},
        router=P1RoleIntentRouter(),
    )
    stages = postprocess_stages(
        preflight=result,
        evidence_count=0,
        factcheck_verdict="not_run",
        degraded=True,
    )

    assert [stage["stage"] for stage in stages][-3:] == [
        "evidence_claim_verification",
        "repair_abstain",
        "postprocess",
    ]
    assert stages[-2]["status"] == "abstain_or_warn"
    assert all("query" not in stage for stage in stages)
