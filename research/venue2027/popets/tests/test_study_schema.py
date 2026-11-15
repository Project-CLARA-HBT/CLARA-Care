"""Tests for the PoPETs venue study schema (task POPETS-schema).

Purpose
-------
Verify the generated ``research/venue2027/popets/protocols/study.schema.json``:
the schema rebuilds deterministically from the shared case contract via
``venue_schema.write_venue_schema('popets', root)``, the three sample
revocation-episode records validate (with their sha256 evidence pointers
actually binding to on-disk artifacts), the violating record is rejected
fail-closed, a record missing the venue observer is rejected, and a record
belonging to another venue cannot pass the popets schema. Every sample record
expresses an evidence-handling verdict on one independent revocation episode
under the future-dispatch noninterference predicate
``forbidden_label(g,p) ∩ lineage(d) = ∅`` — never a mechanism outcome and
never a claim of retroactive erasure of already-delivered bytes.

Allowed input: the shared case schema, the venue schema builder, the stdlib
validator and the on-disk sample cases, all read-only.

Failure semantics: AssertionError with a stable message per violated
invariant. Version: clara.venue2027.popets.test-study-schema.v1
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
SCHEMA_PATH = REPO / "research" / "venue2027" / "popets" / "protocols" / "study.schema.json"
CASES_PATH = REPO / "research" / "venue2027" / "popets" / "cases" / "sample_cases.json"
SHARED_PATH = REPO / "research" / "venue2027" / "_shared" / "schemas" / "case.v1.schema.json"

# Evidence-handling verdict vocabulary of the noninterference predicate.
VERDICT_DECISIONS = {"ADMIT", "REJECT", "INDETERMINATE"}
MECHANISM_MASQUERADE_TOKENS = ("LEAK_BLOCKED", "BYTES_SENT", "PURGED", "DETECTED", "ERASED")

# One record per episode class: fresh dispatch, revoked-then-dispatch, race.
EPISODE_VERDICTS = {
    "POPETS-CASE-02": "ADMIT",
    "POPETS-CASE-03": "REJECT",
    "POPETS-CASE-08": "INDETERMINATE",
}


def _shared_schema() -> dict:
    return json.loads(SHARED_PATH.read_text(encoding="utf-8"))


def _on_disk_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _cases() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def test_rebuild_is_deterministic_and_matches_on_disk() -> None:
    """Rebuilding via write_venue_schema('popets', root) reproduces the file."""
    rebuilt_a = vs.build_venue_schema("popets", _shared_schema())
    rebuilt_b = vs.build_venue_schema("popets", _shared_schema())
    assert rebuilt_a == rebuilt_b, "venue schema build must be deterministic"
    assert (
        rebuilt_a == _on_disk_schema()
    ), "on-disk study.schema.json must equal a fresh write_venue_schema('popets', root) build"
    assert rebuilt_a["properties"]["venue"] == {"const": "popets"}
    assert rebuilt_a["properties"]["venue_unit_kind"]["const"] == "revocation_episode"
    assert rebuilt_a["properties"]["observer"]["enum"] == ["re_disclosure_observer"]
    assert rebuilt_a["additionalProperties"] is False


def test_valid_sample_cases_validate() -> None:
    """Every record in 'cases' validates against the venue study schema."""
    schema = _on_disk_schema()
    cases = _cases()["cases"]
    assert len(cases) == 3, "task requires exactly three valid revocation-episode records"
    for case in cases:
        errors = sv.validate_instance(case, schema)
        assert not errors, (case["case_id"], errors)


def test_evidence_pointers_bind_to_on_disk_artifacts() -> None:
    """Each evidence pointer's sha256 equals the SHA256 of the pointed-to artifact."""
    cases = _cases()["cases"]
    for case in cases:
        assert case["unit_kind"] == "case", case["case_id"]
        assert case["schema_version"] == "1", case["case_id"]
        assert len(case["evidence"]) >= 1, case["case_id"]
        for pointer in case["evidence"]:
            assert set(("pointer_kind", "uri", "sha256")) <= set(pointer), case["case_id"]
            artifact = REPO / pointer["uri"]
            assert artifact.is_file(), f"{case['case_id']}: missing artifact {pointer['uri']}"
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert (
                actual == pointer["sha256"]
            ), f"{case['case_id']}: evidence hash mismatch for {pointer['uri']}"


def test_invalid_case_rejected_fail_closed() -> None:
    """The violating record (foreign venue/observer + silent nulls) is rejected."""
    schema = _on_disk_schema()
    invalid = _cases()["invalid_cases"]
    assert len(invalid) == 1, "task requires exactly one violating record"
    entry = invalid[0]
    record = entry["record"]
    errors = sv.validate_instance(record, schema)
    assert errors, "violating record must be rejected, never silently accepted"
    # Wrong-venue observer (foreign adjudicator outside the venue enum).
    assert "ENUM_MISMATCH" in errors, errors
    # Wrong venue const (cross-venue record must not pass the popets schema).
    assert "CONST_MISMATCH" in errors, errors
    # Silent nulls in required fields (unit_kind/seed/branch/arm_id/backend).
    assert "TYPE_MISMATCH" in errors, errors
    # Evidence array with zero pointers (no binding at all).
    assert "MIN_ITEMS" in errors, errors


def test_missing_observer_rejected() -> None:
    """A record lacking the venue observer field is rejected fail-closed."""
    schema = _on_disk_schema()
    case = json.loads(json.dumps(_cases()["cases"][0]))
    case.pop("observer")
    errors = sv.validate_instance(case, schema)
    assert "REQUIRED_MISSING" in errors, errors
    case["observer"] = None
    errors = sv.validate_instance(case, schema)
    assert "TYPE_MISMATCH" in errors, errors


def test_wrong_venue_rejected() -> None:
    """A valid popets record relabelled to another venue does not validate."""
    schema = _on_disk_schema()
    case = json.loads(json.dumps(_cases()["cases"][0]))
    case["venue"] = "acns"
    case["venue_unit_kind"] = "evidence_record"
    case["observer"] = "evidence_boundary_auditor"
    errors = sv.validate_instance(case, schema)
    assert "CONST_MISMATCH" in errors, errors
    assert "ENUM_MISMATCH" in errors, errors


def test_records_express_revocation_episode_verdicts() -> None:
    """Decision fields must carry an evidence-handling verdict, not a mechanism outcome.

    Each valid record adjudicates one independent revocation episode under the
    future-dispatch noninterference predicate: a fresh post-revocation dispatch
    with clean lineage ADMITs (POPETS-CASE-02), the revoked-then-dispatch
    re-disclosure witness REJECTs (POPETS-CASE-03, interceptor cancellation,
    never a leak), and the schedule-time race keeps INDETERMINATE
    (POPETS-CASE-08) instead of being counted as a safe rejection. Notes carry
    the machine-parseable episode fields episode_class / lineage_verdict /
    failure_mode / erasure_claim.
    """
    cases = _cases()["cases"]
    for case in cases:
        cid = case["case_id"]
        assert cid in EPISODE_VERDICTS, f"unknown sample case {cid}"
        expected_decision = EPISODE_VERDICTS[cid]
        assert case["expected_decision"] == expected_decision, cid
        assert case["observed_decision"] == expected_decision, cid
        assert case["observed_decision"] in VERDICT_DECISIONS, cid
        assert case["observed_decision"] not in MECHANISM_MASQUERADE_TOKENS, cid
        assert case["decision_agreement"] is True, cid
        assert case["observer"] == "re_disclosure_observer", cid
        assert case["venue_unit_kind"] == "revocation_episode", cid
        notes = case["notes"]
        assert "episode_class=" in notes, f"{cid}: notes must name episode_class"
        assert "lineage_verdict=" in notes, f"{cid}: notes must name lineage_verdict"
        assert "failure_mode=" in notes, f"{cid}: notes must name failure_mode"
        assert "erasure_claim=" in notes, f"{cid}: notes must name erasure_claim"
        lowered = notes.lower()
        assert "retroactive erasure of" not in lowered or "no claim" in lowered, (
            f"{cid}: notes must never assert retroactive erasure"
        )


def test_revoked_then_dispatch_record_rejects_leak() -> None:
    """POPETS-CASE-03 is the revoked-then-dispatch re-disclosure witness.

    A derived cache artifact whose lineage intersects forbidden_label(g,p)
    would leave the process boundary after t_r; the episode REJECTs the
    dispatch (interceptor cancellation) and asserts no retroactive erasure.
    """
    case = next(c for c in _cases()["cases"] if c["case_id"] == "POPETS-CASE-03")
    assert case["case_family"] == "transitive_cache_lineage"
    assert case["expected_decision"] == "REJECT"
    notes = case["notes"]
    assert "episode_class=revoked_then_dispatch" in notes
    assert "lineage_verdict=intersects" in notes
    assert "failure_mode=interceptor_cancellation" in notes
    assert "erasure_claim=none" in notes
    assert "forbidden_label" in notes


def test_indeterminate_race_record_fails_closed() -> None:
    """POPETS-CASE-08 keeps INDETERMINATE for the schedule-time race."""
    case = next(c for c in _cases()["cases"] if c["case_id"] == "POPETS-CASE-08")
    assert case["expected_decision"] == "INDETERMINATE"
    notes = case["notes"]
    assert "episode_class=assembly_overlap_race" in notes
    assert "failure_mode=fail_closed" in notes
    assert "INDETERMINATE" in case["observed_decision"]
