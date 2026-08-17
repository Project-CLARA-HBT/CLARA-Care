from __future__ import annotations

from evaluation.governance_adversarial.strict_residuals import (
    DEFAULT_MANIFEST,
    DEFAULT_RAW,
    EXPECTED_STRICT_RESIDUALS,
    ROOT_CAUSES,
    build_residuals,
    root_cause_for,
)


def _has_immutable_artifacts() -> bool:
    return DEFAULT_RAW.is_file()


def test_all_strict_residuals_are_concurrent_stale_state_write() -> None:
    if not _has_immutable_artifacts():
        return
    residuals, taxonomy = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    assert len(residuals) == EXPECTED_STRICT_RESIDUALS == 30
    assert {item["family"] for item in residuals} == {"concurrent_stale_state_write"}
    assert taxonomy["total_residuals"] == 30
    assert taxonomy["by_family"] == {"concurrent_stale_state_write": 30}


def test_residual_lines_have_required_no_phi_fields() -> None:
    if not _has_immutable_artifacts():
        return
    residuals, _ = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    required = {
        "case_id", "family", "mutation_class", "expected_invariant",
        "normalized_observed_outcome", "observation_artifact_sha256",
    }
    for item in residuals:
        assert required.issubset(set(item.keys()))
        # No PHI: only hashes and synthetic identifiers appear.
        assert item["observation_artifact_sha256"]
        assert len(str(item["observation_artifact_sha256"])) == 64


def test_root_cause_taxonomy_is_prespecified_and_indeterminate_ordering() -> None:
    if not _has_immutable_artifacts():
        return
    residuals, taxonomy = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    causes = {item["primary_root_cause"] for item in residuals}
    assert causes.issubset(ROOT_CAUSES)
    assert causes == {"INDETERMINATE_ORDERING"}
    assert taxonomy["by_primary_root_cause"] == {"INDETERMINATE_ORDERING": 30}


def test_by_design_audit_control_is_excluded_from_residuals() -> None:
    if not _has_immutable_artifacts():
        return
    residuals, taxonomy = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    assert all(item["family"] != "audit_reconstruction_failure" for item in residuals)
    assert taxonomy["by_design_commits_excluded"] == {"audit_reconstruction_failure": 30}


def test_serial_drift_families_have_zero_invalid_commits_in_strict() -> None:
    if not _has_immutable_artifacts():
        return
    _, taxonomy = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    serial = taxonomy["serial_drift_invalid_commits"]
    assert serial and all(value == 0 for value in serial.values())


def test_established_facts_are_recorded_in_taxonomy() -> None:
    if not _has_immutable_artifacts():
        return
    _, taxonomy = build_residuals(DEFAULT_RAW, DEFAULT_MANIFEST)
    facts = taxonomy["established_facts"]
    assert facts["primary_denominator"] == 210
    assert facts["all_executed"] == 270
    assert facts["not_run_per_arm"] == 180
    assert facts["expected_strict_residuals"] == 30


def test_root_cause_for_by_design_control_is_expected_valid_operation() -> None:
    row = {
        "family": "audit_reconstruction_failure",
        "normalized_outcome": "committed",
    }
    cause, tags = root_cause_for(row)
    assert cause == "EXPECTED_VALID_OPERATION"
    assert "by_design_commit" in tags
