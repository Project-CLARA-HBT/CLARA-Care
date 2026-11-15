"""Structural test for the COMPSAC-funding submission/author check.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/submission/funding_and_author_check.md``
satisfies the shared program contract via the REQUIRED validator
``research/venue2027/_shared/tools/submission_contract.py``
(``validate_submission_check() -> SubmissionResult``): every required field
present, no fee/row marked verified without a citation URL and date, no
assured-waiver claim without a source, and an explicit double/simultaneous
submission refusal. Also verifies COMPSAC-specific honesty requirements that
the generic validator cannot express: ``decision: HOLD``, no submission or fee
action taken, human authorization required, every fee amount UNVERIFIED, no
guaranteed waiver, IEEE Computer Society member/non-member/student tier and
membership-discount path named, student travel support possibilities named,
and the IEEE dual-submission policy stated.

Adversarial controls (each must FAIL, never silently pass):
- A document whose fee row claims a verified amount without URL+date is
  refused with ``CONFIRMED_WITHOUT_CITATION``.
- A document promising an assured fee waiver without a source is refused with
  ``UNVERIFIED_WAIVER_GUARANTEE``.
- A document missing a required field (or the double/simultaneous policy) is
  refused.
- An empty document is refused.

Allowed input
-------------
Read-only access to the funding-check markdown and the shared tools directory.
No network, no DB, no provider calls.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing contract element; no
silent passes. The shared validator's verdicts are the authority here — this
test never re-implements its logic, so it cannot drift from the program gate.

Version
-------
``compsac-funding-check-test-v1``
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS_DIR = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import submission_contract as sc  # noqa: E402

TEST_VERSION = "compsac-funding-check-test-v1"

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
        "simultaneous_submission_policy: double submission prohibited\n"
        "verification_status: UNVERIFIED\n"
        "decision: HOLD\n"
    )


# ------------------------------------------------------------- positive controls
def test_version_declared() -> None:
    assert TEST_VERSION.startswith("compsac-funding-check-test-")


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


def test_decision_is_hold() -> None:
    text = _real_doc_text()
    assert "decision: HOLD" in text.lower() or "Decision: HOLD" in text


def test_no_submission_or_fee_action_taken_and_human_gate() -> None:
    lower = _real_doc_text().lower()
    assert "no submission action" in lower, "must state no submission action taken"
    assert "fee payment" in lower, "must state no fee payment taken"
    assert "human authorization is required" in lower, "human authorization gate missing"


def test_every_fee_amount_marked_unverified() -> None:
    lower = _real_doc_text().lower()
    assert "all amounts unverified" in lower, "fee row must mark amounts UNVERIFIED"
    assert "every fee amount in this document is unverified" in lower


def test_no_guaranteed_waiver_claim() -> None:
    lower = _real_doc_text().lower()
    assert "no guaranteed waiver" in lower, "must state there is no guaranteed waiver"


def test_compsac_cost_paths_named() -> None:
    lower = _real_doc_text().lower()
    for token in (
        "ieee computer society member",
        "non-member",
        "student tier",
        "membership discount",
        "student travel support",
        "open-access apc",
    ):
        assert token in lower, f"COMPSAC cost path not named: {token}"


def test_ieee_dual_submission_policy_stated() -> None:
    lower = _real_doc_text().lower()
    assert "double submission is prohibited" in lower
    assert "simultaneously under review" in lower


def test_live_cfp_not_fetched_declared() -> None:
    lower = _real_doc_text().lower()
    assert "live cfp not fetched" in lower, "must state the live CFP was not fetched"
    assert "unverified" in lower


# ---------------------------------------------------------- adversarial controls
def test_verified_fee_without_citation_fails() -> None:
    body = _minimal_body() + "- fee CONFIRMED as 500 USD\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_waiver_guarantee_without_source_fails() -> None:
    body = _minimal_body() + "- waiver will be guaranteed for all students\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "UNVERIFIED_WAIVER_GUARANTEE" in result.reason_codes


def test_missing_required_field_fails() -> None:
    body = _minimal_body().replace("template: IEEE 2-column\n", "")
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "template" in result.missing_fields


def test_missing_simultaneous_policy_flags() -> None:
    # The shared validator surfaces the missing policy as a reason_code; a body
    # that never mentions double/simultaneous submission must be flagged even
    # when no other violation exists.
    body = _minimal_body().replace(
        "simultaneous_submission_policy: double submission prohibited\n", ""
    )
    result = sc.validate_submission_check(body)
    assert "MISSING_SIMULTANEOUS_POLICY" in result.reason_codes
    assert result.missing_fields == ("simultaneous_submission_policy",)


def test_empty_document_fails() -> None:
    result = sc.validate_submission_check("")
    assert result.ok is False
    assert "MISSING_FIELD" in result.reason_codes
