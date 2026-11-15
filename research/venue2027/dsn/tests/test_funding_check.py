"""Machine-checked tests for the DSN 2027 funding/author check deliverable.

Purpose
-------
Enforce the ``research/venue2027/dsn/submission/funding_and_author_check.md``
contract for task ``DSN-funding``: the committed deliverable must pass the
shared submission validator
(``research/venue2027/_shared/tools/submission_contract.py``) with every
REQUIRED field present, an UNVERIFIED verification status and a HOLD decision;
and the validator must refuse the adversarial cases this task explicitly
guards against: a CONFIRMED claim without a verification URL+date, and a
guaranteed waiver asserted without a source.

Allowed input
-------------
The funding/author check markdown file at repository-relative path
``research/venue2027/dsn/submission/funding_and_author_check.md``, located
from this test file's position on disk, plus the shared validator module
(imported read-only).

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message naming the violated
contract element. No random, network, or filesystem writes; no live CFP fetch.

Version
-------
``FUNDING_CHECK_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import sys

SHARED_TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS))

import submission_contract as sc  # noqa: E402

FUNDING_CHECK_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
FUNDING_CHECK_PATH = (
    REPO_ROOT / "research" / "venue2027" / "dsn" / "submission" / "funding_and_author_check.md"
)


def load_funding_check_text() -> str:
    assert FUNDING_CHECK_PATH.is_file(), f"funding check missing: {FUNDING_CHECK_PATH}"
    return FUNDING_CHECK_PATH.read_text(encoding="utf-8")


def test_real_funding_check_passes_shared_validator() -> None:
    """The committed deliverable must satisfy the REQUIRED validator."""
    result = sc.validate_submission_check(load_funding_check_text())
    assert result.ok is True, (
        f"shared validator refused the DSN funding/author check: "
        f"reason_codes={result.reason_codes} "
        f"missing_fields={result.missing_fields} "
        f"violations={result.violations}"
    )
    assert result.missing_fields == ()
    assert result.violations == ()


def test_all_required_fields_present_as_labeled_lines() -> None:
    """Each REQUIRED field must appear as its own labeled line in the doc."""
    lines = load_funding_check_text().splitlines()
    for field in sc.REQUIRED_FIELDS:
        assert any(line.strip().startswith(f"- {field}:") for line in lines), (
            f"missing labeled line for required field: {field}"
        )


def test_verification_status_is_unverified() -> None:
    """Honest state: the deliverable must declare UNVERIFIED, never verified."""
    text = load_funding_check_text()
    line = next(ln for ln in text.splitlines() if ln.strip().startswith("- verification_status:"))
    assert "UNVERIFIED" in line, "verification_status must be UNVERIFIED"
    assert "live CFP not fetched" in text, "unverified reason must be stated"
    assert "re-verify at submission" in text, "re-verification obligation must be stated"


def test_decision_is_hold_not_go() -> None:
    """Verification pending => the only honest decision is HOLD."""
    line = next(
        ln for ln in load_funding_check_text().splitlines() if ln.strip().startswith("- decision:")
    )
    assert "HOLD" in line, (
        f"decision must be HOLD while verification is pending, got: {line.strip()}"
    )
    assert "- decision: GO" not in load_funding_check_text().lower()


def test_no_unjustified_confirmed_claims() -> None:
    """No CONFIRMED line may appear unless it also carries a URL and ISO date."""
    result = sc.validate_submission_check(load_funding_check_text())
    assert "CONFIRMED_WITHOUT_CITATION" not in result.reason_codes


def test_no_guaranteed_waiver_claim() -> None:
    """No waiver may be asserted as guaranteed without an evidence URL."""
    result = sc.validate_submission_check(load_funding_check_text())
    assert "UNVERIFIED_WAIVER_GUARANTEE" not in result.reason_codes
    assert "waiver may be" in load_funding_check_text(), (
        "explicit refusal to treat any waiver as assured must be present"
    )


def test_no_submission_or_fee_action_claimed() -> None:
    """The action ledger must state that nothing external was done."""
    text = load_funding_check_text()
    assert "No submission action was taken" in text
    assert "No fee was paid" in text
    assert "Human authorization is required" in text


# -- adversarial cases: the validator must refuse dishonest documents ---------


def _base_document() -> str:
    return (
        "- cfp_url: https://dsn2027-berlin.github.io/important-dates/\n"
        "- template: IEEE conference template\n"
        "- page_limit: not established\n"
        "- fee_or_registration: UNVERIFIED\n"
        "- waiver_path: UNVERIFIED\n"
        "- authorship_and_contribution: CRediT-style statement\n"
        "- conflicts_policy: declared per official form\n"
        "- simultaneous_submission_policy: double submission refused\n"
        "- verification_status: UNVERIFIED\n"
        "- decision: HOLD\n"
    )


def test_adversarial_confirmed_without_citation_fails() -> None:
    """A CONFIRMED fee claim with no URL+date on the line must be refused."""
    body = _base_document() + "- fee_or_registration: CONFIRMED as 500 USD\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_adversarial_confirmed_with_url_but_no_date_fails() -> None:
    """A CONFIRMED claim carrying a URL but no ISO date must still be refused."""
    body = _base_document() + "- fee CONFIRMED at https://dsn2027-berlin.github.io/\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_adversarial_guaranteed_waiver_without_source_fails() -> None:
    """A guaranteed waiver with no evidence URL must be refused."""
    body = _base_document() + "- waiver_path: student waiver guaranteed for all authors\n"
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "UNVERIFIED_WAIVER_GUARANTEE" in result.reason_codes


def test_adversarial_missing_required_field_fails() -> None:
    """Dropping a REQUIRED field must be refused, never silently accepted."""
    body = _base_document().replace("- decision: HOLD\n", "")
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "decision" in result.missing_fields


def test_adversarial_missing_simultaneous_policy_fails() -> None:
    """A document silent on double submission must be refused."""
    body = _base_document().replace(
        "- simultaneous_submission_policy: double submission refused\n", ""
    )
    result = sc.validate_submission_check(body)
    assert result.ok is False
    assert "MISSING_SIMULTANEOUS_POLICY" in result.reason_codes


def test_confirmed_with_citation_is_accepted_by_validator() -> None:
    """Sanity: the validator accepts a dated, sourced CONFIRMED line."""
    body = _base_document() + "- fee CONFIRMED at https://example.org/fees 2026-11-15\n"
    assert sc.validate_submission_check(body).ok is True


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__]))
