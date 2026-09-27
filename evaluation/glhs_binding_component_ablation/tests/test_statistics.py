"""Unit tests for E01 component-wise exact-binding ablation statistical engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluation.glhs_binding_component_ablation.binding_mask import ALL_ARMS, BindingMask
from evaluation.glhs_binding_component_ablation.build_schedules import (
    TOTAL_SCHEDULES,
    SCHEDULES_PER_FAMILY,
    build_schedules,
)
from evaluation.glhs_binding_component_ablation.analyze import (
    _wilson_score_ci,
    _mcnemar_exact_two_sided,
    _fit_factorial_logistic_regression,
    analyze,
)

SCHEDULES_PATH = Path("evaluation/glhs_binding_component_ablation/schedules.json")


def test_schedules_generation_counts() -> None:
    schedules = build_schedules()
    assert len(schedules) == TOTAL_SCHEDULES == 352
    
    clean_schedules = [s for s in schedules if s["family_name"] == "CLEAN"]
    assert len(clean_schedules) == 96
    
    adversarial_schedules = [s for s in schedules if s["kind"] == "adversarial"]
    assert len(adversarial_schedules) == 256
    
    for fam_name, expected_count in SCHEDULES_PER_FAMILY.items():
        fam_list = [s for s in schedules if s["family_name"] == fam_name]
        assert len(fam_list) == expected_count


def test_binding_masks_vector_mapping() -> None:
    assert BindingMask.from_arm_name("B000").vector == (0, 0, 0)
    assert BindingMask.from_arm_name("B100").vector == (1, 0, 0)
    assert BindingMask.from_arm_name("B010").vector == (0, 1, 0)
    assert BindingMask.from_arm_name("B001").vector == (0, 0, 1)
    assert BindingMask.from_arm_name("B110").vector == (1, 1, 0)
    assert BindingMask.from_arm_name("B101").vector == (1, 0, 1)
    assert BindingMask.from_arm_name("B011").vector == (0, 1, 1)
    assert BindingMask.from_arm_name("B111").vector == (1, 1, 1)


def test_wilson_score_ci_boundaries() -> None:
    low_0, high_0 = _wilson_score_ci(0, 32)
    assert low_0 == 0.0
    assert 0.0 < high_0 < 0.15

    low_1, high_1 = _wilson_score_ci(32, 32)
    assert 0.85 < low_1 < 1.0
    assert high_1 == 1.0


def test_mcnemar_exact_properties() -> None:
    assert _mcnemar_exact_two_sided(0, 0) == 1.0
    assert _mcnemar_exact_two_sided(32, 0) < 1e-9
    assert _mcnemar_exact_two_sided(16, 16) == 1.0


def test_analyze_synthetic_dataset() -> None:
    schedules = build_schedules()
    schedules_doc = {"schedules": schedules}
    
    # Generate synthetic executions
    # In B111, all adversarial are rejected (admitted=False) and all controls are admitted (admitted=True)
    # In B000, adversarial are accepted (admitted=True) and controls are admitted
    records = []
    for s in schedules:
        is_clean = s["family_name"] == "CLEAN"
        for arm in ALL_ARMS:
            if is_clean:
                admitted = True
                reason = None
            else:
                mask = BindingMask.from_arm_name(arm)
                fam = s["family_name"]
                if fam == "ID-SUB":
                    admitted = not mask.snapshot_identity
                elif fam == "DIGEST-MUT":
                    admitted = not mask.snapshot_digest
                elif fam == "EVIDENCE-OUTSIDE":
                    admitted = not mask.evidence_membership
                elif fam == "EXPIRY-CONTROL":
                    admitted = False  # Always rejected under all arms
                elif fam == "COORD-SUB":
                    admitted = False  # Governance coordinate mismatch rejected under all arms
                else:
                    admitted = not (mask.snapshot_identity and mask.snapshot_digest and mask.evidence_membership)
                reason = None if admitted else "snapshot_validation_failed"

            records.append({
                "schedule_id": s["schedule_id"],
                "arm": arm,
                "admitted": admitted,
                "rejection_reason_code": reason,
            })

    result = analyze(schedules_doc, records, {"freeze_id": "TEST-FREEZE"})
    assert result["claim_eligible"] is True
    assert result["total_schedules"] == 352
    assert result["actual_executions"] == 352 * 8 == 2816
    assert result["factorial_logistic_regression"]["fitted"] is True
    assert result["clean_acceptance_by_arm"]["B111"]["acceptance_rate"] == 1.0
    assert result["aggregate_mcnemar_vs_b111"]["B000"]["mcnemar_p_value"] < 1e-6
