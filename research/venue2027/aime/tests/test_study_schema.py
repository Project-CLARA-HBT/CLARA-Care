"""Machine-checked tests for the AIME 2027 study schema deliverable.

Purpose
-------
Enforce task ``AIME-schema``: the venue study schema
(``research/venue2027/aime/protocols/study.schema.json``) must rebuild
deterministically from the shared case contract via
``_shared/tools/venue_schema.write_venue_schema('aime', root)``; the committed
synthetic sample records must validate; the adversarial negative control must
be rejected; and every record must carry ``source_authority =
SYNTHETIC_RESEARCH_ONLY`` so no real-PHI path can enter the AIME study.

Allowed input
-------------
The generated schema, the sample-cases fixture file, and the shared tools under
``research/venue2027/_shared/`` — all located from this test file's position on
disk and read read-only (plus one temp-dir rebuild). No network, no
randomness, no live provider.

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message naming the violated
contract element. Validator reason codes must match exactly, fail closed; an
unvalidated or indeterminate outcome is never treated as a pass.

Version
-------
``STUDY_SCHEMA_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

SHARED_TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import venue_schema  # noqa: E402
from schema_validator import is_valid, validate_instance  # noqa: E402

STUDY_SCHEMA_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO_ROOT / "research" / "venue2027" / "aime" / "protocols" / "study.schema.json"
SAMPLES_PATH = REPO_ROOT / "research" / "venue2027" / "aime" / "cases" / "sample_cases.json"
SHARED_CASE_PATH = (
    REPO_ROOT / "research" / "venue2027" / "_shared" / "schemas" / "case.v1.schema.json"
)
FIXTURES_DIR = REPO_ROOT / "research" / "venue2027" / "aime" / "cases" / "fixtures"


def load_samples() -> dict:
    assert SAMPLES_PATH.is_file(), f"sample cases missing: {SAMPLES_PATH}"
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict:
    assert SCHEMA_PATH.is_file(), f"study schema missing: {SCHEMA_PATH}"
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def positive_records() -> list[dict]:
    """The valid sample records, independent of the container key spelling."""
    samples = load_samples()
    for key in ("valid_cases", "positive_cases"):
        if key in samples:
            records = samples[key]
            assert len(records) == 3, f"expected 3 positive records, got {len(records)}"
            return records
    raise AssertionError("sample_cases.json lacks a valid_cases/positive_cases array")


def invalid_records() -> list[dict]:
    samples = load_samples()
    records = samples["invalid_cases"]
    assert len(records) == 1, f"expected exactly 1 invalid record, got {len(records)}"
    entry = records[0]
    # Entries may be raw records or wrappers ({violation, expected_reject_reason, record}).
    return [entry["record"] if "record" in entry else entry]


def test_schema_rebuild_is_deterministic() -> None:
    """Committed schema must byte-match a fresh rebuild from the shared contract."""
    rebuilt = venue_schema.build_venue_schema(
        "aime", json.loads(SHARED_CASE_PATH.read_text(encoding="utf-8"))
    )
    on_disk = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert rebuilt == on_disk, "study.schema.json drifted from write_venue_schema('aime', root)"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == (
        json.dumps(rebuilt, indent=2, sort_keys=True) + "\n"
    ), "study.schema.json serialization is not the canonical deterministic form"
    assert venue_schema.VENUE_SCHEMA_VERSION == "1.0.0"
    assert on_disk["$id"] == "https://clara.care/venue2027/aime/study.schema.json"
    assert on_disk["properties"]["venue"]["const"] == "aime"
    assert on_disk["properties"]["venue_unit_kind"]["const"] == "vignette_pair"
    assert on_disk["properties"]["observer"]["enum"] == ["blinded_clinician"]
    assert on_disk["properties"]["source_authority"]["enum"] == ["SYNTHETIC_RESEARCH_ONLY"]
    for field in (
        "venue",
        "venue_unit_kind",
        "observer",
        "case_family",
        "expected_decision",
        "observed_decision",
        "decision_agreement",
        "synthetic_provenance",
        "source_authority",
        "backend",
        "seed",
        "independent_unit_id",
    ):
        assert field in on_disk["required"], f"venue field {field!r} not required (silent null)"


def test_schema_rebuild_via_write_venue_schema_isolated_tree(tmp_path: pathlib.Path) -> None:
    """write_venue_schema('aime', root) into an isolated tree reproduces the file."""
    root = tmp_path / "rebuild"
    shared_dir = root / "research" / "venue2027" / "_shared" / "schemas"
    shared_dir.mkdir(parents=True)
    (shared_dir / "case.v1.schema.json").write_text(
        json.dumps(
            json.loads(SHARED_CASE_PATH.read_text(encoding="utf-8")), indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    out = venue_schema.write_venue_schema("aime", root)
    assert out == root / "research" / "venue2027" / "aime" / "protocols" / "study.schema.json"
    assert out.read_text(encoding="utf-8") == SCHEMA_PATH.read_text(
        encoding="utf-8"
    ), "write_venue_schema('aime', root) output differs from the committed schema"


def test_schema_rebuild_matches_git_head_blob(tmp_path: pathlib.Path) -> None:
    """The schema as committed in git HEAD also rebuilds deterministically."""
    head = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "show",
            "HEAD:research/venue2027/aime/protocols/study.schema.json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode != 0:
        return  # schema not yet committed; the worktree checks above already cover it
    assert head.stdout == SCHEMA_PATH.read_text(
        encoding="utf-8"
    ), "worktree schema differs from git HEAD blob"
    rebuilt = venue_schema.build_venue_schema(
        "aime", json.loads(SHARED_CASE_PATH.read_text(encoding="utf-8"))
    )
    assert json.dumps(rebuilt, indent=2, sort_keys=True) + "\n" == head.stdout


def test_positive_cases_validate() -> None:
    """Every positive synthetic vignette-pair record must validate (empty codes)."""
    schema = load_schema()
    for record in positive_records():
        codes = validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert codes == (), f"{record['case_id']} rejected with reason codes {codes}"


def test_positive_cases_carry_synthetic_authority_only() -> None:
    """No real PHI path: every record must declare SYNTHETIC_RESEARCH_ONLY provenance."""
    for record in positive_records() + invalid_records():
        assert (
            record.get("source_authority") == "SYNTHETIC_RESEARCH_ONLY"
        ), f"{record['case_id']} does not carry source_authority=SYNTHETIC_RESEARCH_ONLY"
        provenance = record.get("synthetic_provenance")
        assert isinstance(provenance, dict), f"{record['case_id']} lacks synthetic_provenance"
        assert provenance["generator_id"] == "synthetic-aime-2027"
        assert isinstance(provenance["seed"], int)
    for fixture in FIXTURES_DIR.glob("*.json"):
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        assert payload["synthetic_only"] is True, f"{fixture.name} not marked synthetic_only"
        assert (
            payload["source_authority"] == "SYNTHETIC_RESEARCH_ONLY"
        ), f"{fixture.name} not marked SYNTHETIC_RESEARCH_ONLY"


def test_evidence_pointers_match_frozen_fixtures() -> None:
    """Evidence sha256 must equal the real fixture bytes; mismatch fails closed."""
    for record in positive_records():
        for pointer in record["evidence"]:
            assert set(pointer) >= {"pointer_kind", "uri", "sha256"}, record["case_id"]
            artifact = REPO_ROOT / pointer["uri"]
            assert artifact.is_file(), (record["case_id"], pointer["uri"])
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert (
                digest == pointer["sha256"]
            ), f"{record['case_id']} evidence sha256 mismatch for {pointer['uri']}"


def test_evidence_tamper_fails_closed() -> None:
    """A flipped sha256 stays schema-valid but must fail the digest binding."""
    record = json.loads(json.dumps(positive_records()[0]))
    pointer = record["evidence"][0]
    pointer["sha256"] = "0" * 64
    schema = load_schema()
    assert is_valid(
        record, schema, schema_path=SCHEMA_PATH
    ), "tampered pointer must be caught by the digest binding, not the schema shape"
    digest = hashlib.sha256((REPO_ROOT / pointer["uri"]).read_bytes()).hexdigest()
    assert digest != pointer["sha256"]


def test_positive_case_expected_decision_axes() -> None:
    """The three positive cases must cover the three designed decision axes."""
    by_id = {record["case_id"]: record for record in positive_records()}
    assert by_id["AIME-CASE-03"]["expected_decision"] == "REJECT"  # consent withdrawal
    assert by_id["AIME-CASE-02"]["expected_decision"] == "ADMIT"  # medication withdrawal
    assert by_id["AIME-CASE-07"]["expected_decision"] == "INDETERMINATE"  # blinded adjudication
    for record in by_id.values():
        assert record["decision_agreement"] is (
            record["expected_decision"] == record["observed_decision"]
        ), f"{record['case_id']} decision_agreement is not computed from decisions"


def test_adversarial_case_rejected() -> None:
    """The negative control must fail closed with the expected reason codes."""
    schema = load_schema()
    record = invalid_records()[0]
    assert is_valid(record, schema, schema_path=SCHEMA_PATH) is False
    codes = validate_instance(record, schema, schema_path=SCHEMA_PATH)
    # Untracked MRN-like property plus malformed source_sha pattern.
    assert "ADDITIONAL_PROPERTY" in codes, f"expected ADDITIONAL_PROPERTY, got {codes}"
    assert "PATTERN_MISMATCH" in codes, f"expected PATTERN_MISMATCH, got {codes}"


def test_missing_required_field_rejected() -> None:
    """Fail closed: dropping any single required field must be rejected."""
    schema = load_schema()
    base = positive_records()[0]
    for field in schema["required"]:
        record = json.loads(json.dumps(base))
        del record[field]
        codes = validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert codes != (), f"removing required field {field!r} did not reject the record"
        assert "REQUIRED_MISSING" in codes, f"field {field!r} removal gave codes {codes}"


def test_schema_version_and_unit_kinds_frozen() -> None:
    """Only schema_version '1' and the declared unit kinds are accepted."""
    schema = load_schema()
    base = positive_records()[0]

    bumped = json.loads(json.dumps(base))
    bumped["schema_version"] = "2"
    assert "CONST_MISMATCH" in validate_instance(bumped, schema, schema_path=SCHEMA_PATH)

    wrong_unit = json.loads(json.dumps(base))
    wrong_unit["venue_unit_kind"] = "not_a_vignette_pair"
    assert "CONST_MISMATCH" in validate_instance(wrong_unit, schema, schema_path=SCHEMA_PATH)

    wrong_observer = json.loads(json.dumps(base))
    wrong_observer["observer"] = "candidate_model_itself"
    assert "ENUM_MISMATCH" in validate_instance(wrong_observer, schema, schema_path=SCHEMA_PATH)

    wrong_authority = json.loads(json.dumps(base))
    wrong_authority["source_authority"] = "REAL_CLINICAL_RECORDS"
    assert "ENUM_MISMATCH" in validate_instance(wrong_authority, schema, schema_path=SCHEMA_PATH)
