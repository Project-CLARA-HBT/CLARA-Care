"""Tests for the ACNS venue study schema (task ACNS-schema).

Purpose
-------
Verify the generated ``research/venue2027/acns/protocols/study.schema.json``:
the schema rebuilds deterministically from the shared case contract via
``venue_schema.write_venue_schema('acns', root)``, the sample evidence records
validate (with their sha256 evidence pointers actually binding to on-disk
artifacts), the violating record is rejected fail-closed, and every sample
record expresses an *evidence-boundary verdict* (which claim the frozen
evidence supports and where the claimed implication breaks) — a SoK taxonomy
adjudication, never a mechanism/detection outcome.

Allowed input: the shared case schema, the venue schema builder, the stdlib
validator and the on-disk sample cases, all read-only.

Failure semantics: AssertionError with a stable message per violated
invariant. Version: clara.venue2027.acns.test-study-schema.v1
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

TOOLSFOLDER = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLSFOLDER))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO / "research" / "venue2027" / "acns" / "protocols" / "study.schema.json"
CASES_PATH = REPO / "research" / "venue2027" / "acns" / "cases" / "sample_cases.json"
SHARED_PATH = REPO / "research" / "venue2027" / "_shared" / "schemas" / "case.v1.schema.json"

# Evidence-handling verdict vocabulary of the SoK (never a mechanism outcome).
VERDICT_DECISIONS = {"ADMIT", "REJECT", "INDETERMINATE"}
MECHANISM_MASQUERADE_TOKENS = ("TOOL_RAN", "BLOCKED", "ALLOWED", "DETECTED", "PREVENTED")


def _shared_schema() -> dict:
    return json.loads(SHARED_PATH.read_text(encoding="utf-8"))


def _on_disk_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _cases() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def test_rebuild_is_deterministic_and_matches_on_disk() -> None:
    """Rebuilding via write_venue_schema('acns', root) reproduces the file."""
    rebuilt_a = vs.build_venue_schema("acns", _shared_schema())
    rebuilt_b = vs.build_venue_schema("acns", _shared_schema())
    assert rebuilt_a == rebuilt_b, "venue schema build must be deterministic"
    assert (
        rebuilt_a == _on_disk_schema()
    ), "on-disk study.schema.json must equal a fresh write_venue_schema('acns', root) build"
    assert rebuilt_a["properties"]["venue"] == {"const": "acns"}
    assert rebuilt_a["properties"]["venue_unit_kind"]["const"] == "evidence_record"
    assert rebuilt_a["properties"]["observer"]["enum"] == ["evidence_boundary_auditor"]
    assert rebuilt_a["additionalProperties"] is False


def test_valid_sample_cases_validate() -> None:
    """Every record in 'cases' validates against the venue study schema."""
    schema = _on_disk_schema()
    cases = _cases()["cases"]
    assert len(cases) == 3, "task requires exactly three valid evidence-record cases"
    for case in cases:
        errors = sv.validate_instance(case, schema)
        assert not errors, (case["case_id"], errors)


def test_evidence_pointers_bind_to_on_disk_artifacts() -> None:
    """Each evidence pointer's sha256 equals the SHA256 of the pointed-to artifact."""
    cases = _cases()["cases"]
    for case in cases:
        assert case["unit_kind"] == "case", case["case_id"]
        assert case["schema_version"] == "1", case["case_id"]
        for pointer in case["evidence"]:
            assert set(("pointer_kind", "uri", "sha256")) <= set(pointer), case["case_id"]
            artifact = REPO / pointer["uri"]
            assert artifact.is_file(), f"{case['case_id']}: missing artifact {pointer['uri']}"
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert (
                actual == pointer["sha256"]
            ), f"{case['case_id']}: evidence hash mismatch for {pointer['uri']}"


def test_invalid_case_rejected_fail_closed() -> None:
    """The violating record (mechanism masquerade + silent nulls) is rejected."""
    schema = _on_disk_schema()
    invalid = _cases()["invalid_cases"]
    assert len(invalid) == 1, "task requires exactly one violating record"
    entry = invalid[0]
    record = entry["record"]
    errors = sv.validate_instance(record, schema)
    assert errors, "violating record must be rejected, never silently accepted"
    # Mechanism-outcome masquerade (observed_decision outside the verdict enum).
    assert "ENUM_MISMATCH" in errors, errors
    # Silent nulls in required fields (unit_kind/seed/branch/arm_id/backend).
    assert "TYPE_MISMATCH" in errors, errors
    # Evidence array with zero pointers (no binding at all).
    assert "MIN_ITEMS" in errors, errors


def test_records_express_evidence_boundary_verdicts() -> None:
    """Decision fields must carry a SoK evidence-boundary verdict, not a mechanism outcome.

    Each valid record adjudicates which attestation lattice level its frozen
    evidence supports: bound evidence admitted at its exact level (ACNS-CASE-03,
    ADMIT at L2), the G2 attestation-downgrade implication refused
    (ACNS-CASE-02, REJECT), and ambiguous disclosure retained as INDETERMINATE
    (ACNS-CASE-05) rather than coerced to a pass. Notes carry the
    machine-parseable verdict fields granted_level / refused_claim /
    boundary_condition / gap_code (G1-G9 of the threat-model register).
    """
    cases = _cases()["cases"]
    verdicts = {
        "ACNS-CASE-03": "ADMIT",
        "ACNS-CASE-02": "REJECT",
        "ACNS-CASE-05": "INDETERMINATE",
    }
    forbidden_mechanism_terms = (
        "detection rate",
        "prevention rate",
        "attack success rate",
    )
    for case in cases:
        cid = case["case_id"]
        assert cid in verdicts, f"unknown sample case {cid}"
        expected_decision = verdicts[cid]
        assert case["expected_decision"] == expected_decision, cid
        assert case["observed_decision"] == expected_decision, cid
        assert case["observed_decision"] in VERDICT_DECISIONS, cid
        assert case["observed_decision"] not in MECHANISM_MASQUERADE_TOKENS, cid
        assert case["decision_agreement"] is True, cid
        assert case["observer"] == "evidence_boundary_auditor", cid
        notes = case["notes"]
        assert "granted_level=" in notes, f"{cid}: notes must name granted_level"
        assert "refused_claim=" in notes, f"{cid}: notes must name refused_claim"
        assert "boundary_condition=" in notes, f"{cid}: notes must name boundary_condition"
        assert "gap_code=" in notes, f"{cid}: notes must name gap_code"
        lowered = notes.lower()
        for term in forbidden_mechanism_terms:
            assert term not in lowered, f"{cid}: mechanism outcome term {term!r} in notes"


def test_downgrade_gap_record_refutes_l2_to_l3() -> None:
    """ACNS-CASE-02 is the G2 attestation-downgrade witness, a SoK result.

    The receipt (L2) is quoted as execution proof; the record refuses the
    L2->L3 implication absent TC3 TEE attestation and caps the granted level
    at L2. This is a falsification verdict on a claimed implication pair.
    """
    case = next(c for c in _cases()["cases"] if c["case_id"] == "ACNS-CASE-02")
    assert case["case_family"] == "model_agency"
    assert case["expected_decision"] == "REJECT"
    notes = case["notes"]
    assert "gap_code=G2" in notes, "downgrade witness must cite register entry G2"
    assert "granted_level=L2_ACKNOWLEDGED" in notes, "granted level must stay at L2"
    assert "refused_claim=the model executed the tool" in notes
    assert "TC3" in notes, "refusal must name the absent trust assumption (TC3)"


def test_bound_evidence_record_admits_exactly_supported_level() -> None:
    """ACNS-CASE-03 admits the bound receipt at L2 and refuses the L2->L4 leap."""
    case = next(c for c in _cases()["cases"] if c["case_id"] == "ACNS-CASE-03")
    assert case["expected_decision"] == "ADMIT"
    notes = case["notes"]
    assert "granted_level=L2_ACKNOWLEDGED" in notes
    assert "refused_claim=the model executed the tool" in notes
    assert "gap_code=none" in notes


def test_ambiguous_record_keeps_indeterminate() -> None:
    """ACNS-CASE-05 retains INDETERMINATE instead of coercing a pass."""
    case = next(c for c in _cases()["cases"] if c["case_id"] == "ACNS-CASE-05")
    assert case["expected_decision"] == "INDETERMINATE"
    notes = case["notes"]
    assert "granted_level=INDETERMINATE_PENDING_ADJUDICATION" in notes
    assert "INDETERMINATE" in case["observed_decision"]
