"""Machine-checked tests for the PST-funding submission/author check.

Purpose
-------
Verify, with the standard library only, that
``research/venue2027/pst/submission/funding_and_author_check.md`` passes the
shared program contract validator
``research/venue2027/_shared/tools/submission_contract.py``
(``validate_submission_check() -> SubmissionResult``), that every REQUIRED
field is present, that the PST-specific honesty posture holds (``decision:
HOLD``, no submission or fee action taken, human authorization required,
every fee amount UNVERIFIED, no guaranteed waiver, double/simultaneous
submission refused), and that the validator refuses adversarial documents:
CONFIRMED claims without URL+date, guaranteed waivers without a source,
missing required fields, and missing simultaneous-submission policy.

Allowed input
-------------
Read-only access to the funding-check markdown and the shared tools
directory. No network, no DB, no provider calls.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the violated contract element;
no silent passes. The shared validator's verdicts are the authority — this
test never re-implements its logic, so it cannot drift from the program gate.

Version
-------
``pst-funding-check-test-v1``
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS_DIR = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import submission_contract as sc  # noqa: E402

TEST_VERSION = "pst-funding-check-test-v1"

DOC_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "submission" / "funding_and_author_check.md"
)


def _real_doc_text() -> str:
    assert DOC_PATH.is_file(), f"funding check missing at {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def _minimal_body() -> str:
    return (
        "cfp_url: https://venue.org/cfp\n"
        "template: IEEE 2-column\n"
        "page_limit: 10\n"
        "fee_or_registration: UNVERIFIED\n"
        "waiver_path: UNVERIFIED\n"
        "authorship_and_contribution: listed\n"
        "conflicts_policy: declared\n"
        "simultaneous_submission_policy: double submission refused\n"
        "verification_status: UNVERIFIED\n"
        "decision: HOLD\n"
    )


# ------------------------------------------------------------- positive controls
def test_version_declared() -> None:
    assert TEST_VERSION.startswith("pst-funding-check-test-")


def test_real_document_passes_shared_validator() -> None:
    result = sc.validate_submission_check(_real_doc_text())
    assert result.ok is True, (
        f"real funding_and_author_check.md must pass the shared validator; "
        f"reason_codes={result.reason_codes} missing_fields={result.missing_fields} "
        f"violations={result.violations}"
    )
    assert result.missing_fields == ()
    assert result.violations == ()


def test_all_required_fields_present_in_real_document() -> None:
    lower = _real_doc_text().lower()
    for field in sc.REQUIRED_FIELDS:
        assert field in lower, f"required field missing from real document: {field}"


def test_all_required_fields_present_as_labeled_lines() -> None:
    lines = _real_doc_text().splitlines()
    for field in sc.REQUIRED_FIELDS:
        assert any(line.strip().startswith(f"- {field}:") for line in lines), (
            f"missing labeled line for required field: {field}"
        )


def test_verification_status_is_unverified() -> None:
    line = next(
        ln
        for ln in _real_doc_text().splitlines()
        if ln.strip().startswith("- verification_status:")
    )
    assert "UNVERIFIED" in line, "verification_status must be UNVERIFIED"
    assert "live CFP not fetched" in _real_doc_text(), "unverified reason must be stated"
    assert "re-verify at submission" in _real_doc_text(), "re-verification obligation required"


def test_decision_is_hold() -> None:
    line = next(ln for ln in _real_doc_text().splitlines() if ln.strip().startswith("- decision:"))
    assert "HOLD" in line, f"decision must be HOLD while verification is pending: {line.strip()}"
    assert "- decision: go" not in _real_doc_text().lower()


def test_no_submission_or_fee_action_taken_and_human_gate() -> None:
    text = _real_doc_text()
    assert "No submission action was taken" in text, "must state no submission action taken"
    assert "No fee was paid" in text, "must state no fee payment taken"
    assert "Human authorization is required" in text, "human authorization gate missing"


def test_every_fee_amount_marked_unverified() -> None:
    lower = _real_doc_text().lower()
    assert "every fee amount in this document is unverified" in lower
    assert "amounts not yet verified" in lower, "fee row must budget as nonzero/unverified"


def test_no_guaranteed_waiver_claim() -> None:
    text = _real_doc_text()
    assert "No guaranteed waiver" in text, "must state there is no guaranteed waiver"
    result = sc.validate_submission_check(text)
    assert "UNVERIFIED_WAIVER_GUARANTEE" not in result.reason_codes


def test_waiver_may_not_be_presented_as_assured() -> None:
    text = _real_doc_text()
    assert "No waiver" in text and "guaranteed, assured, or automatic" in text, (
        "explicit refusal to treat any waiver as assured must be present"
    )


def test_remote_presentation_path_named_but_unverified() -> None:
    text = _real_doc_text()
    assert "Remote presentation" in text, "PST remote-presentation route must be named"
    assert "does not waive registration" in text, (
        "remote presentation must not be conflated with a fee waiver"
    )


def test_student_status_proof_route_named_but_unverified() -> None:
    text = _real_doc_text()
    assert "Student status proof" in text, "student status proof route must be named"
    assert "enrollment" in text.lower(), "expected proof artifact must be named"


def test_pst_cfp_url_present() -> None:
    text = _real_doc_text()
    assert "https://www.pstnet.ca/pst2027/callforpapers.html" in text, (
        "PST 2027 official CFP URL must be present"
    )


def test_double_submission_refused() -> None:
    lower = _real_doc_text().lower()
    assert "double submission is prohibited" in lower
    assert "simultaneously under review" in lower


def test_popets_overlap_firewall_referenced() -> None:
    lower = _real_doc_text().lower()
    assert "publication_overlap_registry.yaml" in lower, (
        "internal PoPETs/PST overlap firewall must be referenced"
    )
    assert "phase_gate_matrix.md" in lower, "P09 STOP signal source must be referenced"


def test_sponsor_request_packet_present() -> None:
    lower = _real_doc_text().lower()
    assert "sponsor request packet" in lower, "go/no-go sponsor packet must be outlined"
    assert "not an authorization to spend" in lower


# ---------------------------------------------------------- adversarial controls
def test_adversarial_confirmed_without_citation_fails() -> None:
    """A CONFIRMED fee claim with no URL+date on the line must be refused."""
    body = _minimal_body() + "- fee_or_registration: CONFIRMED as 500 USD\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_adversarial_confirmed_with_url_but_no_date_fails() -> None:
    """A CONFIRMED claim carrying a URL but no ISO date must still be refused."""
    body = _minimal_body() + "- fee CONFIRMED at https://www.pstnet.ca/\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_adversarial_confirmed_with_citation_passes() -> None:
    """Sanity: the validator accepts a dated, sourced CONFIRMED line."""
    body = _minimal_body() + "- fee CONFIRMED at https://www.pstnet.ca/ 2026-11-15\n"
    assert sc.validate_submission_check(body).ok is True


def test_adversarial_guaranteed_waiver_without_source_fails() -> None:
    """A guaranteed waiver with no evidence URL must be refused."""
    body = _minimal_body() + "- waiver_path: student waiver guaranteed for all authors\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "UNVERIFIED_WAIVER_GUARANTEE" in result.reason_codes


def test_adversarial_missing_required_field_fails() -> None:
    """Dropping a REQUIRED field must be refused, never silently accepted."""
    body = _minimal_body().replace("template: IEEE 2-column\n", "")
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "template" in result.missing_fields


def test_adversarial_missing_simultaneous_policy_fails() -> None:
    """A document silent on double/simultaneous submission must be refused."""
    body = _minimal_body().replace(
        "simultaneous_submission_policy: double submission refused\n", ""
    )
    result = sc.validate_submission_check(body)
    assert "MISSING_SIMULTANEOUS_POLICY" in result.reason_codes
    assert result.missing_fields == ("simultaneous_submission_policy",)


def test_adversarial_empty_document_fails() -> None:
    result = sc.validate_submission_check("")
    assert result.ok is False
    assert "MISSING_FIELD" in result.reason_codes


def test_adversarial_go_decision_is_not_the_committed_state() -> None:
    """The committed document must never declare GO while facts are UNVERIFIED."""
    assert "decision: GO" not in _real_doc_text().lower()


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__]))
