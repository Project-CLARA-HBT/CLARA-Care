"""Machine-checked tests for the DSN 2027 study schema deliverable.

Purpose
-------
Enforce the ``research/venue2027/dsn/protocols/study.schema.json`` contract for
task ``DSN-schema``: the committed schema must be a deterministic rebuild via
``venue_schema.write_venue_schema('dsn', ...)``, the sample cases in
``research/venue2027/dsn/cases/sample_cases.json`` must validate, the declared
invalid record must be rejected, and the fail-closed properties (missing venue
observer, wrong venue) must hold.

Allowed input
-------------
The committed study schema, the shared case schema and the sample-cases file at
repository-relative paths, located from this test file's position on disk, plus
the shared tool modules (imported read-only).

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message naming the violated
contract element. No random, network, or repository-mutating operations; the
deterministic-rebuild check writes only to a temporary directory.

Version
-------
``STUDY_SCHEMA_TEST_VERSION = "1.0.0"`"
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

SHARED_TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import venue_schema  # noqa: E402
from schema_validator import SchemaError, validate_instance  # noqa: E402

STUDY_SCHEMA_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SHARED_CASE_SCHEMA_PATH = (
    REPO_ROOT / "research" / "venue2027" / "_shared" / "schemas" / "case.v1.schema.json"
)
STUDY_SCHEMA_PATH = (
    REPO_ROOT / "research" / "venue2027" / "dsn" / "protocols" / "study.schema.json"
)
SAMPLE_CASES_PATH = (
    REPO_ROOT / "research" / "venue2027" / "dsn" / "cases" / "sample_cases.json"
)


def load_study_schema() -> dict:
    assert STUDY_SCHEMA_PATH.is_file(), f"study schema missing: {STUDY_SCHEMA_PATH}"
    return json.loads(STUDY_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sample_cases() -> dict:
    assert SAMPLE_CASES_PATH.is_file(), f"sample cases missing: {SAMPLE_CASES_PATH}"
    return json.loads(SAMPLE_CASES_PATH.read_text(encoding="utf-8"))


def test_study_schema_is_deterministic_rebuild() -> None:
    """Regenerating the venue schema must reproduce the committed file byte-for-byte."""
    committed = STUDY_SCHEMA_PATH.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        rebuild_root = pathlib.Path(tmp)
        (rebuild_root / "research" / "venue2027" / "_shared").mkdir(parents=True)
        shared_copy = rebuild_root / "research" / "venue2027" / "_shared" / "schemas"
        shared_copy.mkdir()
        (
            shared_copy / "case.v1.schema.json"
        ).write_text(SHARED_CASE_SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        out = venue_schema.write_venue_schema("dsn", rebuild_root)
        rebuilt = out.read_text(encoding="utf-8")
    assert rebuilt == committed, (
        "study.schema.json is not a deterministic write_venue_schema('dsn') rebuild"
    )


def test_sample_case_records_validate() -> None:
    """All three positive sample records must validate with no reason codes."""
    schema = load_study_schema()
    cases = load_sample_cases()
    assert isinstance(cases.get("records"), list) and len(cases["records"]) == 3, (
        "sample_cases.json must carry exactly 3 valid records"
    )
    for record in cases["records"]:
        codes = validate_instance(record, schema, schema_path=STUDY_SCHEMA_PATH)
        assert codes == (), f"valid record {record.get('case_id')!r} rejected: {codes}"


def test_declared_invalid_record_rejected() -> None:
    """The declared invalid_cases record must fail validation, not slip through."""
    schema = load_study_schema()
    cases = load_sample_cases()
    invalid = cases.get("invalid_cases")
    assert isinstance(invalid, list) and len(invalid) == 1, (
        "sample_cases.json must declare exactly 1 invalid record"
    )
    codes = validate_instance(invalid[0], schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "invalid record must be rejected by the study schema"
    assert "REQUIRED_MISSING" in codes, (
        f"invalid record must fail as REQUIRED_MISSING, got {codes}"
    )


def test_missing_observer_rejected() -> None:
    """Fail closed: a record without the venue observer field is rejected."""
    schema = load_study_schema()
    cases = load_sample_cases()
    record = json.loads(json.dumps(cases["records"][0]))
    record.pop("observer")
    codes = validate_instance(record, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "record missing 'observer' must be rejected"
    assert "REQUIRED_MISSING" in codes, (
        f"missing observer must yield REQUIRED_MISSING, got {codes}"
    )


def test_wrong_venue_rejected() -> None:
    """Fail closed: venue is a const ('dsn'); any other venue label is rejected."""
    schema = load_study_schema()
    cases = load_sample_cases()

    mutated = json.loads(json.dumps(cases["records"][0]))
    mutated["venue"] = "compsac"
    codes = validate_instance(mutated, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "record with wrong venue const must be rejected"
    assert "CONST_MISMATCH" in codes, f"wrong venue must yield CONST_MISMATCH, got {codes}"

    forged = json.loads(json.dumps(cases["records"][0]))
    forged["venue"] = "sacmat"
    forged["venue_unit_kind"] = "delegated_consent_case"
    forged["observer"] = "policy_engine_differential"
    codes = validate_instance(forged, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "fully forged foreign-venue record must be rejected"
    assert "CONST_MISMATCH" in codes, f"forged venue must yield CONST_MISMATCH, got {codes}"


def test_venue_schema_builder_refuses_unknown_venue() -> None:
    """The shared builder fails closed for unknown venues."""
    try:
        venue_schema.build_venue_schema("not_a_venue", {"properties": {}})
    except venue_schema.VenueSchemaError as exc:
        assert exc.reason_code == "UNKNOWN_VENUE", f"unexpected reason code: {exc.reason_code}"
    else:
        raise AssertionError("unknown venue must raise VenueSchemaError(UNKNOWN_VENUE)")


def test_validator_fails_closed_on_unresolvable_ref() -> None:
    """The shared validator must raise, never silently pass, on a broken schema."""
    broken = {"$ref": "#/$defs/does_not_exist", "type": "object"}
    try:
        validate_instance({}, broken)
    except SchemaError as exc:
        assert exc.reason_code == "REF_UNRESOLVED", f"unexpected reason code: {exc.reason_code}"
    else:
        raise AssertionError("unresolvable $ref must raise SchemaError(REF_UNRESOLVED)")


def test_adversarial_records_rejected() -> None:
    """Adversarial mutations of a valid record must be rejected, fail closed."""
    schema = load_study_schema()
    cases = load_sample_cases()

    # Outcome label smuggled from the CASE_MATRIX oracle vocabulary instead of
    # the schema's decision enum.
    smuggled = json.loads(json.dumps(cases["records"][0]))
    smuggled["observed_decision"] = "COMMITTED_BUT_PENDING_DELIVERY"
    codes = validate_instance(smuggled, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "non-enum observed_decision must be rejected"
    assert "ENUM_MISMATCH" in codes, f"expected ENUM_MISMATCH, got {codes}"

    # Unknown property smuggled past the closed-world contract.
    extra = json.loads(json.dumps(cases["records"][0]))
    extra["oracle_bypass"] = True
    codes = validate_instance(extra, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "unexpected additional property must be rejected"
    assert "ADDITIONAL_PROPERTY" in codes, f"expected ADDITIONAL_PROPERTY, got {codes}"

    # Untracked randomness: seed outside the shared integer domain.
    bad_seed = json.loads(json.dumps(cases["records"][0]))
    bad_seed["seed"] = -1
    codes = validate_instance(bad_seed, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "negative seed must be rejected"
    assert "MINIMUM" in codes, f"expected MINIMUM, got {codes}"


def test_silent_unit_kind_extension_forbidden() -> None:
    """The venue builder may not silently extend the shared unit_kind enum."""
    shared = json.loads(SHARED_CASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema = load_study_schema()
    assert schema["properties"]["unit_kind"]["enum"] == shared["properties"]["unit_kind"]["enum"], (
        "unit_kind enum must stay byte-identical to the shared case contract"
    )
    # A record claiming the venue's own label as a unit_kind is rejected: the
    # venue-specific name lives only in venue_unit_kind.
    cases = load_sample_cases()
    record = json.loads(json.dumps(cases["records"][0]))
    record["unit_kind"] = "crash_recovery_episode"
    codes = validate_instance(record, schema, schema_path=STUDY_SCHEMA_PATH)
    assert codes != (), "unit_kind extension attempt must be rejected"
    assert "ENUM_MISMATCH" in codes, f"expected ENUM_MISMATCH, got {codes}"
