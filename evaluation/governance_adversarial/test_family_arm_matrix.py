from __future__ import annotations

from evaluation.governance_adversarial.family_arm_matrix import (
    ALL_EXECUTED,
    DEFAULT_MANIFEST,
    DEFAULT_RAW_ROOT,
    NOT_RUN_PER_ARM,
    PRIMARY_DENOMINATOR,
    PRIMARY_ENDPOINT_FAMILIES,
    build_family_arm_matrix,
)


def _has_immutable_artifacts() -> bool:
    return (DEFAULT_RAW_ROOT / "GLHS_STRICT" / "raw_results.csv").is_file()


def test_matrix_covers_all_families_and_arms() -> None:
    if not _has_immutable_artifacts():
        return
    rows, _checks = build_family_arm_matrix(DEFAULT_RAW_ROOT, DEFAULT_MANIFEST)
    assert len(rows) == 15 * 4
    assert {row["arm"] for row in rows} == {
        "UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT",
    }
    assert len({row["family"] for row in rows}) == 15


def test_matrix_columns_and_counts() -> None:
    if not _has_immutable_artifacts():
        return
    rows, _checks = build_family_arm_matrix(DEFAULT_RAW_ROOT, DEFAULT_MANIFEST)
    expected = {
        "family", "reporting_scope", "arm", "eligible_n", "executed_n", "not_run_n",
        "invalid_commit_acceptance", "unintended_disclosure", "wrong_subject_exposure",
        "cache_revocation_failure", "availability_error", "committed_count",
        "rejected_count", "rejection_auditability", "committed_reconstructability",
        "latency_ms",
    }
    assert expected.issubset(set(rows[0].keys()))
    for row in rows:
        assert int(row["eligible_n"]) == 30
        assert int(row["executed_n"]) + int(row["not_run_n"]) == 30


def test_endpoint_facts_are_encoded_in_matrix_checks() -> None:
    if not _has_immutable_artifacts():
        return
    _rows, checks = build_family_arm_matrix(DEFAULT_RAW_ROOT, DEFAULT_MANIFEST)
    assert checks["primary_denominator"] == PRIMARY_DENOMINATOR == 210
    assert checks["all_executed"] == ALL_EXECUTED == 270
    assert checks["not_run_per_arm"] == NOT_RUN_PER_ARM == 180
    assert checks["strict_residual_families"] == 1
    assert checks["audit_by_design_commits"] == 30
    # GLHS_STRICT invalid-commit acceptance = concurrent (30) + by-design audit (30).
    assert checks["strict_invalid_commit_acceptance"] == 60


def test_primary_endpoint_families_execute_in_strict_arm() -> None:
    if not _has_immutable_artifacts():
        return
    rows, _ = build_family_arm_matrix(DEFAULT_RAW_ROOT, DEFAULT_MANIFEST)
    strict = [row for row in rows if row["arm"] == "GLHS_STRICT"]
    executed_primary = {
        row["family"]
        for row in strict
        if row["family"] in PRIMARY_ENDPOINT_FAMILIES and int(row["executed_n"]) == 30
    }
    assert executed_primary == PRIMARY_ENDPOINT_FAMILIES


def test_all_serial_drift_families_have_zero_invalid_commits_in_strict() -> None:
    if not _has_immutable_artifacts():
        return
    rows, _ = build_family_arm_matrix(DEFAULT_RAW_ROOT, DEFAULT_MANIFEST)
    serial = {
        "revoked_consent_cache_index_reuse",
        "policy_version_change",
        "role_mismatch",
        "stale_thss_replay",
        "digest_expiry_tamper_replay",
        "cross_subject_proposal_write",
        "derived_cache_persistence_after_revocation",
    }
    for row in rows:
        if row["arm"] == "GLHS_STRICT" and row["family"] in serial:
            assert int(row["invalid_commit_acceptance"]) == 0, row
