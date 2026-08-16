from __future__ import annotations

import hashlib

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.analyze import _holm_adjust
from evaluation.governance_adversarial.protocol import (
    FAMILIES,
    PRIMARY_FAMILIES,
    build_development_manifest,
    validate_manifest,
)


def _manifest() -> dict[str, object]:
    return build_development_manifest(
        seed=20260816,
        statistics_plan_sha256=hashlib.sha256(b"statistics-plan").hexdigest(),
        repetitions=1,
    )


def test_development_manifest_is_complete_and_synthetic() -> None:
    manifest = _manifest()
    validated = validate_manifest(manifest, require_frozen=False)
    assert {case["family"] for case in validated["cases"]} == set(FAMILIES)
    assert validated["primary_family_ids"] == list(PRIMARY_FAMILIES)
    assert all(case["subject"].startswith("synthetic-sentinel-") for case in validated["cases"])


def test_manifest_rejects_missing_attack_family() -> None:
    manifest = _manifest()
    manifest["cases"] = [case for case in manifest["cases"] if case["family"] != FAMILIES[0]]
    with pytest.raises(FreezeError, match="govred_families_incomplete"):
        validate_manifest(manifest, require_frozen=False)


def test_manifest_rejects_duplicate_case_id() -> None:
    manifest = _manifest()
    manifest["cases"].append(dict(manifest["cases"][0]))
    with pytest.raises(FreezeError, match="govred_case_id_invalid_or_duplicate"):
        validate_manifest(manifest, require_frozen=False)


def test_holm_adjustment_is_separate_for_primary_and_secondary_scopes() -> None:
    comparisons = [
        {"reporting_scope": "primary_authorization_drift", "exact_mcnemar_p_unadjusted": 0.01},
        {"reporting_scope": "primary_authorization_drift", "exact_mcnemar_p_unadjusted": 0.04},
        {"reporting_scope": "secondary_robustness_stress", "exact_mcnemar_p_unadjusted": 0.04},
    ]
    adjusted = _holm_adjust(comparisons)
    assert adjusted[0]["exact_mcnemar_p_holm"] == 0.02
    assert adjusted[1]["exact_mcnemar_p_holm"] == 0.04
    assert adjusted[2]["exact_mcnemar_p_holm"] == 0.04
