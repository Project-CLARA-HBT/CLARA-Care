"""Status-consistency tests for the W0 evidence-integrity renderer (W0-T09).

Fail conditions covered:
- top-level says SEALED but no seal resolves;
- current result claims a frozen plan but no exact historical bytes exist;
- manuscript/status denominator cannot reproduce a reported rate;
- a claim points to a missing artifact;
- run/source SHA mismatch exists.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from evaluation.evidence_program.render_status import (
    build_status,
    validate_status,
)

ROOT = Path(".")


def _status() -> dict:
    return deepcopy(build_status(ROOT))


def test_live_repository_machine_status_is_clean() -> None:
    status = _status()
    assert status["validation"]["errors"] == []
    assert status["validation"]["passes"] is True
    assert status["top_level"]["sealed"] is True
    assert status["runs"]["rivf_final_003"]["top_level_status"] == "SEALED"
    assert status["runs"]["glhs_final"]["top_level_status"] == "SEALED"
    assert status["runs"]["rivf_final_003"]["seal"]["resolved"] is True
    assert status["runs"]["glhs_final"]["seal"]["resolved"] is True


def test_glhs_machine_status_facts_match_run() -> None:
    status = _status()
    glhs = status["runs"]["glhs_final"]
    assert glhs["run_id"] == "GLHS-POSTGRES-TOCTOU-FINAL-20260817-01"
    assert glhs["source_sha"].startswith("2074f875")
    assert glhs["schedules_executed"] == 5
    assert glhs["rejected"] == 4
    assert glhs["forbidden_commit_observed"] == 0
    assert glhs["toctou03"]["status"] == "INDETERMINATE"
    assert glhs["dual_model_protocol_qa"]["cohens_kappa"] == 1.0
    assert glhs["dual_model_protocol_qa"]["unresolved"] == 0


def test_sealed_top_level_with_unresolving_seal_fails() -> None:
    status = _status()
    status["runs"]["glhs_final"]["top_level_status"] = "SEALED"
    status["runs"]["glhs_final"]["seal"]["resolved"] = False
    status["runs"]["glhs_final"]["seal"]["missing"] = ["result.json"]
    errors = validate_status(status, ROOT)
    assert any("SEALED but seal does not resolve" in error for error in errors)


def test_explicit_seal_failure_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["top_level_status"] = "SEAL_DOES_NOT_RESOLVE"
    errors = validate_status(status, ROOT)
    assert any("explicitly failed to resolve" in error for error in errors)


def test_top_level_sealed_without_all_run_seals_fails() -> None:
    status = _status()
    status["top_level"]["sealed"] = True
    status["runs"]["glhs_final"]["top_level_status"] = "SEAL_DOES_NOT_RESOLVE"
    errors = validate_status(status, ROOT)
    assert any("top_level says SEALED but a run-level seal" in error for error in errors)


def test_claimed_frozen_plan_with_missing_bytes_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["frozen_statistics_plan"]["bytes_exist"] = False
    status["runs"]["rivf_final_003"]["frozen_statistics_plan"][
        "hash_matches_reconciliation"
    ] = False
    errors = validate_status(status, ROOT)
    assert any("no exact historical bytes exist" in error for error in errors)


def test_claimed_frozen_plan_with_hash_mismatch_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["frozen_statistics_plan"][
        "hash_matches_reconciliation"
    ] = False
    errors = validate_status(status, ROOT)
    assert any("no exact historical bytes exist" in error for error in errors)


def test_glhs_frozen_plan_bytes_missing_fails() -> None:
    status = _status()
    status["runs"]["glhs_final"]["frozen_plan"]["status"] = "PLAN_BYTES_MISSING"
    errors = validate_status(status, ROOT)
    assert any("frozen plan claim but plan bytes missing" in error for error in errors)


def test_non_reproducible_rate_fails() -> None:
    status = _status()
    arm = status["runs"]["rivf_final_003"]["analysis_v2"]["arms"]["GLHS_STRICT"]
    arm["primary_rate"] = 0.999
    errors = validate_status(status, ROOT)
    assert any("not reproducible from denominator" in error for error in errors)


def test_claim_pointing_to_missing_artifact_fails() -> None:
    status = _status()
    status["claims"]["sealed_claim_eligible_checks"].append(
        {
            "claim_id": "SYNTHETIC-001",
            "ledger": "synthetic.csv",
            "status": "sealed_claim_eligible",
            "missing_artifacts": ["does/not/exist.json"],
        }
    )
    errors = validate_status(status, ROOT)
    assert any("points to missing artifact" in error for error in errors)


def test_run_source_sha_mismatch_in_manifest_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["manifest"]["code_revision"] = "0" * 40
    errors = validate_status(status, ROOT)
    assert any("run/source SHA mismatch" in error for error in errors)


def test_run_source_sha_mismatch_in_v2_analysis_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["analysis_v2"]["source_sha"] = "0" * 40
    errors = validate_status(status, ROOT)
    assert any("run/source SHA mismatch" in error for error in errors)


def test_run_source_sha_mismatch_in_glhs_analysis_fails() -> None:
    status = _status()
    status["runs"]["glhs_final"]["analysis"]["code_revision"] = "0" * 40
    errors = validate_status(status, ROOT)
    assert any("run/source SHA mismatch" in error for error in errors)


def test_manifest_sha_mismatch_vs_reconciliation_fails() -> None:
    status = _status()
    status["runs"]["rivf_final_003"]["manifest"]["sha256"] = "0" * 64
    errors = validate_status(status, ROOT)
    assert any("manifest SHA mismatch" in error for error in errors)
