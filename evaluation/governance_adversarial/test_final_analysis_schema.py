from __future__ import annotations

from evaluation.governance_adversarial.final_analysis_schema import (
    STATE_CONFIRMED_INVALID,
    STATE_CONFIRMED_SAFE_OR_REJECTED,
    STATE_INDETERMINATE,
    STATE_OPERATIONAL_FAILURE,
    derive_three_state_primary,
)


def _sealed_analysis_fixture() -> dict:
    def arm(failures: int, residual: dict, availability: int = 0) -> dict:
        return {
            "all_executed_n": 270,
            "audit_reconstruction_complete": 0,
            "endpoint_split": {
                "availability_failure": availability,
                "cache_revocation_failure": 0,
                "invalid_commit_acceptance": failures,
                "unintended_disclosure": 0,
                "wrong_subject_release": 0,
            },
            "not_run_n": 180,
            "primary_endpoint_n": 210,
            "primary_failures": failures,
            "primary_family_residual": residual,
            "primary_rate": failures / 210,
            "wilson_95_ci": [0.1, 0.2],
        }

    return {
        "schema_version": "govred-analysis-v2",
        "run_id": "2026-08-17-rivf-final-003",
        "source_sha": "5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb",
        "arms": {
            "UNBOUND": arm(120, {
                "authorization_consent_toctou": 30,
                "concurrent_stale_state_write": 30,
                "role_mismatch": 30,
                "stale_thss_replay": 30,
            }),
            "STATE_VERSION_ONLY": arm(90, {
                "authorization_consent_toctou": 30,
                "concurrent_stale_state_write": 30,
                "role_mismatch": 30,
            }),
            "SNAPSHOT_BOUND_STATE_ONLY": arm(90, {
                "authorization_consent_toctou": 30,
                "concurrent_stale_state_write": 30,
                "role_mismatch": 30,
            }),
            "GLHS_STRICT": arm(30, {"concurrent_stale_state_write": 30}),
        },
    }


def test_glhs_strict_has_zero_confirmed_invalid() -> None:
    table = derive_three_state_primary(_sealed_analysis_fixture())
    strict = next(row for row in table["rows"] if row["arm"] == "GLHS_STRICT")
    assert strict[STATE_CONFIRMED_INVALID] == 0
    assert strict[STATE_INDETERMINATE] == 30
    assert strict[STATE_CONFIRMED_SAFE_OR_REJECTED] == 180
    assert strict[STATE_OPERATIONAL_FAILURE] == 0
    # The 30 strict residuals are never relabelled as confirmed violations.
    assert [item["family"] for item in strict["indeterminate_breakdown"]] == [
        "concurrent_stale_state_write"
    ]
    assert strict["invalid_breakdown"] == []


def test_rows_sum_to_primary_denominator() -> None:
    table = derive_three_state_primary(_sealed_analysis_fixture())
    for row in table["rows"]:
        total = (
            row[STATE_CONFIRMED_INVALID]
            + row[STATE_INDETERMINATE]
            + row[STATE_CONFIRMED_SAFE_OR_REJECTED]
            + row[STATE_OPERATIONAL_FAILURE]
        )
        assert total == row["primary_endpoint_n"] == 210


def test_weaker_arm_residuals_are_attributed_arm_omission() -> None:
    table = derive_three_state_primary(_sealed_analysis_fixture())
    unbound = next(row for row in table["rows"] if row["arm"] == "UNBOUND")
    assert unbound[STATE_CONFIRMED_INVALID] == 90
    assert all(item["attribution"] == "arm_omitted_coordinate" for item in unbound["invalid_breakdown"])
    assert all(item["arm_omits_coordinate"] for item in unbound["invalid_breakdown"])


def test_secondary_frozen_binary_endpoint_preserved() -> None:
    table = derive_three_state_primary(_sealed_analysis_fixture())
    secondary = table["secondary_frozen_binary_endpoint"]
    assert secondary["GLHS_STRICT"]["primary_failures"] == 30
    assert secondary["UNBOUND"]["primary_failures"] == 120


def test_operational_failure_is_split_out() -> None:
    fixture = _sealed_analysis_fixture()
    fixture["arms"]["GLHS_STRICT"]["endpoint_split"]["availability_failure"] = 5
    table = derive_three_state_primary(fixture)
    strict = next(row for row in table["rows"] if row["arm"] == "GLHS_STRICT")
    assert strict[STATE_OPERATIONAL_FAILURE] == 5
    assert strict[STATE_CONFIRMED_SAFE_OR_REJECTED] == 175


def test_rejects_non_sealed_schema() -> None:
    fixture = _sealed_analysis_fixture()
    fixture["schema_version"] = "govred-analysis-v1"
    try:
        derive_three_state_primary(fixture)
    except ValueError as exc:
        assert "govred_three_state_requires_sealed_v2_analysis" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-sealed schema")