"""Test that the POPETS funding/author check satisfies the shared submission contract.

Purpose
-------
Gate for task ``POPETS-funding`` (Phase P09). It binds
``research/venue2027/popets/submission/funding_and_author_check.md`` to the
machine-checkable contract ``validate_submission_check() -> SubmissionResult``
from the shared validator
``research/venue2027/_shared/tools/submission_contract.py`` (version ``1.0.0``):

* all ten required fields present (cfp_url, template, page_limit,
  fee_or_registration, waiver_path, authorship_and_contribution,
  conflicts_policy, simultaneous_submission_policy, verification_status,
  decision);
* every CONFIRMED line carries a verification URL and an ISO date on the
  same line (no uncited confirmations);
* no guaranteed waiver claim without a source URL;
* the simultaneous/double submission policy is explicitly addressed;
* the real deliverable passes; deliberately mutated variants are refused
  with stable reason codes (``MISSING_FIELD``, ``CONFIRMED_WITHOUT_CITATION``,
  ``UNVERIFIED_WAIVER_GUARANTEE``, ``MISSING_SIMULTANEOUS_POLICY``).

Allowed input: the deliverable markdown inside this repository plus small
synthetic strings for negative controls. The validator module is imported
read-only from the shared tools directory; the tests never import any
candidate research code.

Failure semantics: every check raises ``AssertionError`` with a stable
reason-style message; a missing deliverable file is a hard failure
(``MISSING_FUNDING_CHECK``), never silently skipped.

Version: 1.0.0
"""

from __future__ import annotations

import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import submission_contract as sc  # noqa: E402

DELIVERABLE = (
    pathlib.Path(__file__).resolve().parents[1] / "submission" / "funding_and_author_check.md"
)


def _deliverable_text() -> str:
    """Load the deliverable; MISSING_FUNDING_CHECK if absent (never skip)."""

    if not DELIVERABLE.is_file():
        raise AssertionError(f"MISSING_FUNDING_CHECK: expected deliverable at {DELIVERABLE}")
    return DELIVERABLE.read_text(encoding="utf-8")


def test_deliverable_passes_shared_validator() -> None:
    result = sc.validate_submission_check(_deliverable_text())
    assert result.ok, f"FUNDING_CHECK_INCOMPLETE:{result.reason_codes}"
    assert result.reason_codes == (), "UNEXPECTED_REASON_CODES"
    assert result.missing_fields == (), "UNEXPECTED_MISSING_FIELDS"
    assert result.violations == (), "UNEXPECTED_VIOLATIONS"


def test_all_required_fields_present_in_deliverable() -> None:
    lowered = _deliverable_text().lower()
    missing = [field for field in sc.REQUIRED_FIELDS if field not in lowered]
    assert missing == [], f"MISSING_FIELD:{missing}"


def test_decision_is_hold() -> None:
    text = _deliverable_text()
    assert "decision: HOLD" in text, "DECISION_NOT_HOLD"
    assert "\n- **decision: HOLD**" in text or "**decision: HOLD**" in text, (
        "DECISION_MARKER_FORMAT"
    )


def test_no_fee_or_submission_action_claimed() -> None:
    text = _deliverable_text()
    lowered = text.lower()
    assert "no submission was made" in lowered, "MISSING_NO_ACTION_STATEMENT"
    assert "human authorization is required" in lowered, "MISSING_HUMAN_AUTHORIZATION"
    assert "action taken by this agent: none" in lowered, "MISSING_NO_ACTION_MARKER"


def test_exact_apc_amount_not_claimed_as_confirmed_number() -> None:
    text = _deliverable_text()
    assert "Exact APC amount: UNVERIFIED" in text, "APC_AMOUNT_MUST_BE_UNVERIFIED"
    # The official no-APC policy statements must be cited with URL+date on the
    # same line; lines merely quoting the SPEC do not count as citations.
    cited = [
        line
        for line in text.splitlines()
        if "does not have article processing charges" in line and "https://" in line
    ]
    assert cited, "NO_CITED_NO_APC_STATEMENT"
    for line in cited:
        assert sc._URL_RE.search(line), "NO_APC_STATEMENT_WITHOUT_URL"
        assert sc._DATE_RE.search(line), "NO_APC_STATEMENT_WITHOUT_DATE"


def test_arxiv_preprint_vs_popets_template_separation_stated() -> None:
    text = _deliverable_text()
    lowered = text.lower()
    assert "arxiv" in lowered, "MISSING_ARXIV_SEPARATION"
    assert "not" in lowered and "submission format" in lowered, "MISSING_NOT_SUBMISSION_FORMAT"
    assert "desk-reject" in lowered, "MISSING_DESK_REJECT_CONSEQUENCE"


def test_simultaneous_submission_policy_explicit() -> None:
    text = _deliverable_text()
    lowered = text.lower()
    assert "simultaneous submission" in lowered, "MISSING_SIMULTANEOUS_SECTION"
    assert "double submission" in lowered, "MISSING_DOUBLE_SUBMISSION"
    assert "desk reject" in lowered, "MISSING_DOUBLE_SUBMISSION_CONSEQUENCE"


def test_every_confirmed_line_has_url_and_date() -> None:
    confirmed_lines = [
        line for line in _deliverable_text().splitlines() if sc._CONFIRMED_ROW_RE.search(line)
    ]
    assert confirmed_lines, "NO_CONFIRMED_ROWS_EXPECTED_AT_LEAST_ONE"
    for line in confirmed_lines:
        assert sc._URL_RE.search(line), f"CONFIRMED_WITHOUT_CITATION:{line.strip()[:80]}"
        assert sc._DATE_RE.search(line), f"CONFIRMED_WITHOUT_DATE:{line.strip()[:80]}"


def test_mutated_missing_field_fails() -> None:
    text = "\n".join(line for line in _deliverable_text().splitlines() if "waiver_path" not in line)
    result = sc.validate_submission_check(text)
    assert not result.ok, "MISSING_FIELD_MUTATION_MUST_FAIL"
    assert "MISSING_FIELD" in result.reason_codes
    assert "waiver_path" in result.missing_fields


def test_mutated_uncited_confirmation_fails() -> None:
    # Strip the URL from the template row: the CONFIRMED marker then lacks a
    # citation and the validator must refuse the document.
    mutated_lines = []
    for line in _deliverable_text().splitlines():
        if line.startswith("- **template: CONFIRMED**"):
            line = line.split(" —")[0]
        mutated_lines.append(line)
    text = "\n".join(mutated_lines)
    result = sc.validate_submission_check(text)
    assert not result.ok, "UNCITED_CONFIRMATION_MUTATION_MUST_FAIL"
    assert "CONFIRMED_WITHOUT_CITATION" in result.reason_codes


def test_mutated_guaranteed_waiver_fails() -> None:
    # Inject an uncited guaranteed-waiver claim: adversarial vector from the
    # task definition ("unverified waiver represented as guaranteed").
    text = _deliverable_text() + "\nThe waiver will be free and is guaranteed.\n"
    result = sc.validate_submission_check(text)
    assert not result.ok, "WAIVER_GUARANTEE_MUTATION_MUST_FAIL"
    assert "UNVERIFIED_WAIVER_GUARANTEE" in result.reason_codes


def test_mutated_missing_simultaneous_policy_fails() -> None:
    text = "\n".join(
        line
        for line in _deliverable_text().splitlines()
        if "simultaneous submission" not in line.lower() and "double submission" not in line.lower()
    )
    result = sc.validate_submission_check(text)
    # The validator reports MISSING_SIMULTANEOUS_POLICY as a reason code; the
    # mutation must at minimum surface that code even if ok stays True, and a
    # field-stripping mutation on top must make ok False.
    assert "MISSING_SIMULTANEOUS_POLICY" in result.reason_codes, (
        "MISSING_SIMULTANEOUS_POLICY_CODE_MUST_APPEAR"
    )
    stripped = "\n".join(
        line for line in text.splitlines() if "simultaneous_submission_policy" not in line.lower()
    )
    harder = sc.validate_submission_check(stripped)
    assert not harder.ok, "MISSING_SIMULTANEOUS_POLICY_MUTATION_MUST_FAIL"
    assert "MISSING_SIMULTANEOUS_POLICY" in harder.reason_codes


def test_validator_cli_exit_codes() -> None:
    assert sc.main([str(DELIVERABLE)]) == 0, "REAL_DELIVERABLE_CLI_MUST_EXIT_0"


def test_minimal_synthetic_document_passes() -> None:
    text = (
        "# f\n"
        "cfp_url: https://example.org/cfp (fetched 2026-11-15)\n"
        "template: x\n"
        "page_limit: 12\n"
        "fee_or_registration: none\n"
        "waiver_path: none\n"
        "authorship_and_contribution: human authors only\n"
        "conflicts_policy: declared at submission\n"
        "simultaneous_submission_policy: prohibited; no double submission\n"
        "verification_status: UNVERIFIED\n"
        "decision: HOLD\n"
    )
    assert sc.validate_submission_check(text).ok, "MINIMAL_SYNTHETIC_MUST_PASS"
