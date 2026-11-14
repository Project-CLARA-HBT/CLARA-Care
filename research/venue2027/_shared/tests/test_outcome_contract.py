"""Tests for SH-outcome_contract (outcome.v1 schema + contract tool).

Positive controls (must validate):
- Full outcome.v1 record for every observed outcome enum member.
- Independent expected_outcome vs observed_outcome tracked separately, including
  oracle-expected ADMIT but observed REJECT (mismatch surfaced, not collapsed).
- Retriable NOT_RUN_EXTERNAL / TIMEOUT records with counted_as_success=false.
- validate_outcome / assert_no_false_zero contract signatures.
- Real fixture files under _shared/fixtures/outcome/ validate against the schema.

Adversarial controls (must be REJECTED, never counted as safe, never zero-filled):
- THE canonical false zero: NOT_RUN_EXTERNAL with counted_as_success=true
  refused by the schema oneOf pair itself AND by assert_no_false_zero.
- TIMEOUT / EXECUTION_ERROR / INDETERMINATE counted as success -> refused.
- NOT_RUN_EXTERNAL serialized as numeric_outcome 0 -> refused (invented zero).
- NOT_RUN_EXTERNAL / TIMEOUT without an explicit retriable flag -> refused.
- expected_outcome carrying a NOT_RUN/EXECUTION_ERROR value (expectation is
  oracle-labelled only) -> rejected.
- Mismatch between expected and observed collapsed into one field -> impossible:
  both fields are independently required; deleting either is REQUIRED_MISSING.
- Missing observation evidence / unknown outcome value / unknown property.
- A whole record set in which any single false zero hides -> assert_no_false_zero
  raises even when the other records are honest.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent / "tools"
SCHEMAS_DIR = HERE.parent / "schemas"
FIXTURES_DIR = HERE.parent / "fixtures" / "outcome"
REPO_ROOT = HERE.parents[3]
sys.path.insert(0, str(TOOLS_DIR))

import outcome_contract as oc  # noqa: E402
import schema_validator as sv  # noqa: E402

OUTCOME_SCHEMA_PATH = SCHEMAS_DIR / "outcome.v1.schema.json"

SHA_40 = "7ebdbbf0740e87ffebe3538d6893a53eaccf2216"
SHA256_64 = "c" * 64

EXPECTED_ENUM = ("ADMIT", "REJECT", "INDETERMINATE")
OBSERVED_ENUM = (
    "ADMIT",
    "REJECT",
    "INDETERMINATE",
    "NOT_RUN_EXTERNAL",
    "EXECUTION_ERROR",
    "TIMEOUT",
)
NEVER_SUCCESS = ("INDETERMINATE", "NOT_RUN_EXTERNAL", "EXECUTION_ERROR", "TIMEOUT")


def _record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1",
        "independent_unit_id": "unit:2026-11-15:0001",
        "case_id": "case-0001",
        "arm_id": "B1",
        "expected_outcome": "REJECT",
        "observed_outcome": "REJECT",
        "retriable": False,
        "counted_as_success": True,
        "evidence": [
            {
                "pointer_kind": "oracle_label",
                "uri": "oracle/labels/unit-0001.json",
                "sha256": SHA256_64,
            }
        ],
        "source_sha": SHA_40,
        "backend": "postgresql",
        "seed": 42,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------- positive vectors


def test_positive_all_observed_outcomes_validate() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    for observed in OBSERVED_ENUM:
        counted = observed not in NEVER_SUCCESS
        record = _record(
            observed_outcome=observed,
            retriable=observed in {"NOT_RUN_EXTERNAL", "TIMEOUT"},
            counted_as_success=counted,
        )
        assert sv.is_valid(record, schema, schema_path=OUTCOME_SCHEMA_PATH), observed


def test_positive_expected_and_observed_tracked_separately() -> None:
    # The oracle expected ADMIT; the arm rejected. Both fields stay independent
    # and the mismatch is surfaced, never collapsed into a single field.
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    mismatch = _record(expected_outcome="ADMIT", observed_outcome="REJECT")
    assert sv.is_valid(mismatch, schema, schema_path=OUTCOME_SCHEMA_PATH)
    # Mutating observed_outcome cannot rewrite the frozen expectation.
    tampered = dict(mismatch)
    tampered["observed_outcome"] = "ADMIT"
    assert tampered["expected_outcome"] == "ADMIT"  # expectation untouched
    # And the pair is two distinct required keys, not one.
    for field in ("expected_outcome", "observed_outcome"):
        record = _record()
        del record[field]
        codes = sv.validate_instance(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
        assert "REQUIRED_MISSING" in codes, field


def test_positive_expected_indeterminate_matches_never_success_observed() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    for observed in NEVER_SUCCESS:
        record = _record(
            expected_outcome="INDETERMINATE",
            observed_outcome=observed,
            retriable=observed in {"NOT_RUN_EXTERNAL", "TIMEOUT"},
            counted_as_success=False,
        )
        assert sv.is_valid(record, schema, schema_path=OUTCOME_SCHEMA_PATH), observed


def test_positive_retriable_failure_distinguished() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    # Environment block: retriable, honest non-success count.
    not_run = _record(observed_outcome="NOT_RUN_EXTERNAL", retriable=True, counted_as_success=False)
    assert sv.is_valid(not_run, schema, schema_path=OUTCOME_SCHEMA_PATH)
    # Durable failure: explicitly non-retriable.
    exec_error = _record(
        observed_outcome="EXECUTION_ERROR", retriable=False, counted_as_success=False
    )
    assert sv.is_valid(exec_error, schema, schema_path=OUTCOME_SCHEMA_PATH)
    assert not_run["retriable"] != exec_error["retriable"]


def test_positive_contract_signatures() -> None:
    assert oc.validate_outcome(_record()) is True
    assert oc.OUTCOME_CONTRACT_VERSION == "1.0.0"
    oc.assert_no_false_zero(
        [
            _record(),
            _record(observed_outcome="NOT_RUN_EXTERNAL", retriable=True, counted_as_success=False),
        ]
    )


def test_positive_denominator_counts_are_mutually_exclusive() -> None:
    records = [
        _record(),
        _record(independent_unit_id="unit:2026-11-15:0002"),
        _record(
            independent_unit_id="unit:2026-11-15:0003",
            observed_outcome="TIMEOUT",
            retriable=True,
            counted_as_success=False,
        ),
        _record(
            independent_unit_id="unit:2026-11-15:0004",
            observed_outcome="NOT_RUN_EXTERNAL",
            retriable=True,
            counted_as_success=False,
        ),
        _record(
            independent_unit_id="unit:2026-11-15:0005",
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
        ),
    ]
    counts = oc.outcome_denominator(records)
    assert counts["reject"] == 2
    assert counts["timeout"] == 1
    assert counts["not_run_external"] == 1
    assert counts["indeterminate"] == 1
    assert counts["admit"] == 0
    assert counts["execution_error"] == 0
    # The four never-success buckets sum to exactly the non-success records.
    assert (
        counts["timeout"]
        + counts["not_run_external"]
        + counts["indeterminate"]
        + counts["execution_error"]
        == 3
    )


def test_positive_real_fixtures_validate_against_schema() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    records = json.loads((FIXTURES_DIR / "honest_outcomes.json").read_text(encoding="utf-8"))
    assert isinstance(records, list) and records
    for i, record in enumerate(records):
        assert sv.is_valid(record, schema, schema_path=OUTCOME_SCHEMA_PATH), i
    oc.assert_no_false_zero(records)


def test_adversarial_false_zero_fixture_rejected_by_schema_and_cli() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    records = json.loads((FIXTURES_DIR / "false_zero.json").read_text(encoding="utf-8"))
    assert sv.is_valid(records[0], schema, schema_path=OUTCOME_SCHEMA_PATH)
    # record[1] is THE false zero (NOT_RUN_EXTERNAL counted as success): the
    # schema itself rejects it before any downstream tally can see it.
    assert not sv.is_valid(records[1], schema, schema_path=OUTCOME_SCHEMA_PATH)
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "outcome_contract.py"),
            str(FIXTURES_DIR / "false_zero.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["reason_code"] == "FALSE_ZERO_OUTCOME"
    assert "FALSE_ZERO_COUNTED_AS_SUCCESS" in payload["detail"]


def test_positive_cli_honest_fixture_ok() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "outcome_contract.py"),
            str(FIXTURES_DIR / "honest_outcomes.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["denominator"]["not_run_external"] == 1


# --------------------------------------------------------- adversarial vectors


@pytest.mark.parametrize("observed", NEVER_SUCCESS)
def test_adversarial_false_zero_counted_as_success_refused(observed: str) -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    record = _record(observed_outcome=observed, retriable=True, counted_as_success=True)
    # The schema itself rejects the false zero (oneOf constraint pair).
    assert not sv.is_valid(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
    assert "ONEOF_MISMATCH" in sv.validate_instance(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
    # The tool refuses it too, with a stable reason.
    assert oc.validate_outcome(record) is False
    with pytest.raises(oc.FalseZeroOutcomeError) as exc:
        oc.assert_no_false_zero([record])
    assert "FALSE_ZERO_COUNTED_AS_SUCCESS" in exc.value.detail


def test_adversarial_not_run_external_serialized_as_numeric_zero_refused() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    # An environment block invented as a numeric 0 "outcome" (side-channel field
    # is first refused by additionalProperties:false, then by the tool rule).
    record = _record(
        observed_outcome="NOT_RUN_EXTERNAL",
        retriable=True,
        counted_as_success=False,
        numeric_outcome=0,
    )
    assert not sv.is_valid(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
    assert "ADDITIONAL_PROPERTY" in sv.validate_instance(
        record, schema, schema_path=OUTCOME_SCHEMA_PATH
    )
    with pytest.raises(oc.FalseZeroOutcomeError) as exc:
        oc.assert_no_false_zero([record])
    assert "FALSE_ZERO_NUMERIC" in exc.value.detail


def test_adversarial_false_zero_hidden_in_honest_set_refused() -> None:
    honest = _record()
    hidden = _record(
        independent_unit_id="unit:2026-11-15:0002",
        observed_outcome="TIMEOUT",
        retriable=True,
        counted_as_success=True,  # the one false zero among honest records
    )
    with pytest.raises(oc.FalseZeroOutcomeError) as exc:
        oc.assert_no_false_zero([honest, honest.copy(), hidden])
    assert "FALSE_ZERO_COUNTED_AS_SUCCESS" in exc.value.detail


def test_adversarial_expected_outcome_cannot_carry_execution_values() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    for bad in ("NOT_RUN_EXTERNAL", "EXECUTION_ERROR", "TIMEOUT"):
        codes = sv.validate_instance(
            _record(expected_outcome=bad), schema, schema_path=OUTCOME_SCHEMA_PATH
        )
        assert "ENUM_MISMATCH" in codes, bad


def test_adversarial_missing_retriable_flag_refused_for_env_outcomes() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    for observed in ("NOT_RUN_EXTERNAL", "TIMEOUT"):
        record = _record(observed_outcome=observed, counted_as_success=False)
        del record["retriable"]
        codes = sv.validate_instance(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
        assert "REQUIRED_MISSING" in codes, observed
        with pytest.raises(oc.FalseZeroOutcomeError) as exc:
            oc.assert_no_false_zero([record])
        assert "RETRIABLE_FLAG_REQUIRED" in exc.value.detail


def test_adversarial_missing_observation_evidence_refused() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    record = _record()
    record["evidence"] = []  # type: ignore[assignment]
    codes = sv.validate_instance(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
    assert "MIN_ITEMS" in codes
    # An evidence row without the frozen sha256 fails closed as well.
    record = _record(evidence=[{"pointer_kind": "oracle_label", "uri": "oracle/x.json"}])
    codes = sv.validate_instance(record, schema, schema_path=OUTCOME_SCHEMA_PATH)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_unknown_outcome_and_unknown_property_rejected() -> None:
    schema = sv.load_schema(OUTCOME_SCHEMA_PATH)
    codes = sv.validate_instance(
        _record(observed_outcome="SUCCESS"), schema, schema_path=OUTCOME_SCHEMA_PATH
    )
    assert "ENUM_MISMATCH" in codes
    codes = sv.validate_instance(
        _record(clinical_free_text="unvalidated side channel"),
        schema,
        schema_path=OUTCOME_SCHEMA_PATH,
    )
    assert "ADDITIONAL_PROPERTY" in codes


def test_adversarial_validate_outcome_rejects_non_object() -> None:
    assert oc.validate_outcome("REJECT") is False  # type: ignore[arg-type]
    assert oc.validate_outcome(None) is False  # type: ignore[arg-type]
    assert oc.validate_outcome([]) is False  # type: ignore[arg-type]


def test_adversarial_cli_refuses_false_zero_fixture() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "outcome_contract.py"),
            str(FIXTURES_DIR / "false_zero.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["reason_code"] == "FALSE_ZERO_OUTCOME"
    assert "FALSE_ZERO_COUNTED_AS_SUCCESS" in payload["detail"]
    assert payload["detail"].count("FALSE_ZERO_COUNTED_AS_SUCCESS") == 1
