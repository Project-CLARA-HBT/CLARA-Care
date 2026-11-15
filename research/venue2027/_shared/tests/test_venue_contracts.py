"""Tests for the comparator-matrix, overlap-audit and submission contracts."""

from __future__ import annotations

import sys
import pathlib

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import comparator_matrix as cm  # noqa: E402
import overlap_contract as oc  # noqa: E402
import submission_contract as sc  # noqa: E402

HEADER = ",".join(cm.REQUIRED_COLUMNS)
MECH = "The comparator provides a distinct guarantee; mechanism differs because of X."


def _row(cid: str, *, available: str = "no", fidelity: str = "UNAVAILABLE_NOT_RUN", code: str = "", link: str = "https://example.org/p") -> str:
    return f'{cid},Title,Venue,{link},{code},OCC,some-guarantee,limitation,{available},{fidelity},"{MECH}"'


def _good_csv() -> str:
    rows = [
        _row("B0-coarse", available="no"),
        _row("B1-entity", available="yes", fidelity="ORIGINAL_UPSTREAM", code="https://github.com/x/y"),
        _row("silo13", available="no"),
    ]
    return "\n".join([HEADER, *rows]) + "\n"


def test_matrix_good_passes() -> None:
    result = cm.validate_matrix(_good_csv(), known_registry_ids={"silo13"})
    assert result.ok is True, result.to_dict()
    assert result.row_count == 3


def test_matrix_missing_column_fails() -> None:
    result = cm.validate_matrix("comparator_id,title\nB0,x\n")
    assert result.ok is False
    assert result.reason_codes == ("MISSING_COLUMN",)


def test_matrix_unknown_comparator_fails() -> None:
    bad = "\n".join([HEADER, _row("made-up-paper"), _row("B0"), _row("B1")]) + "\n"
    result = cm.validate_matrix(bad, known_registry_ids={"silo13"})
    assert result.ok is False
    assert "UNKNOWN_COMPARATOR_ID" in result.reason_codes


def test_matrix_thin_mechanism_fails() -> None:
    bad = HEADER + '\n' + "B0,T,V,https://e.org,,OCC,g,l,no,UNAVAILABLE_NOT_RUN,weak\n"
    bad += "\n".join([_row("B1"), _row("B2")]) + "\n"
    result = cm.validate_matrix(bad, known_registry_ids={"silo13"})
    assert result.ok is False
    assert "MECHANISM_ANALYSIS_MISSING" in result.reason_codes


def test_matrix_available_without_url_fails() -> None:
    bad = "\n".join([HEADER, _row("B0"), _row("B1"), _row("B2", available="yes")]) + "\n"
    result = cm.validate_matrix(bad, known_registry_ids={"silo13"})
    assert result.ok is False
    assert "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes


def test_matrix_upstream_without_code_fails() -> None:
    bad = "\n".join([HEADER, _row("B0"), _row("B1"), _row("B2", fidelity="ORIGINAL_UPSTREAM", available="no")]) + "\n"
    result = cm.validate_matrix(bad, known_registry_ids={"silo13"})
    assert result.ok is False
    assert "UPSTREAM_WITHOUT_CODE" in result.reason_codes


def _overlap_body(venue: str) -> str:
    others = [v for v in oc.ALL_VENUES if v != venue]
    return (
        "# Overlap\n"
        + " ".join(others)
        + "\nGLHS GovRed GovMut CareGuard HEALTHINF\n"
        "We do not reuse the frozen E15-E22 outcomes as new evidence.\n"
        "Decision: PASS\n"
    )


def test_overlap_good_passes() -> None:
    assert oc.audit_overlap_document(_overlap_body("dsn"), venue="dsn").ok is True


def test_overlap_missing_sibling_fails() -> None:
    body = _overlap_body("dsn").replace("pst", "")
    result = oc.audit_overlap_document(body, venue="dsn")
    assert result.ok is False
    assert "pst" in result.missing_venues


def test_overlap_missing_frozen_refusal_fails() -> None:
    body = _overlap_body("dsn").replace("do not reuse the frozen E15-E22 outcomes as new evidence.", "")
    result = oc.audit_overlap_document(body, venue="dsn")
    assert result.ok is False
    assert "MISSING_FROZEN_REFUSAL" in result.reason_codes


def test_overlap_missing_decision_fails() -> None:
    body = _overlap_body("dsn").replace("Decision: PASS", "")
    result = oc.audit_overlap_document(body, venue="dsn")
    assert result.ok is False
    assert "MISSING_DECISION" in result.reason_codes


def _sub_body() -> str:
    return (
        "cfp_url: https://venue.org/cfp\n"
        "template: ACM\n"
        "page_limit: 10\n"
        "fee_or_registration: UNVERIFIED\n"
        "waiver_path: UNVERIFIED\n"
        "authorship_and_contribution: listed\n"
        "conflicts_policy: declared\n"
        "simultaneous_submission_policy: double submission prohibited\n"
        "verification_status: UNVERIFIED\n"
        "decision: HOLD\n"
    )


def test_submission_good_passes() -> None:
    assert sc.validate_submission_check(_sub_body()).ok is True


def test_submission_confirmed_without_citation_fails() -> None:
    body = _sub_body() + "- fee CONFIRMED as 500 USD\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_submission_confirmed_with_citation_passes() -> None:
    body = _sub_body() + "- fee CONFIRMED at https://venue.org/fees 2026-11-15\n"
    assert sc.validate_submission_check(body).ok is True


def test_submission_waiver_guarantee_without_source_fails() -> None:
    body = _sub_body() + "- waiver will be guaranteed for all students\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "UNVERIFIED_WAIVER_GUARANTEE" in result.reason_codes


def test_submission_missing_field_fails() -> None:
    body = _sub_body().replace("template: ACM\n", "")
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "template" in result.missing_fields
