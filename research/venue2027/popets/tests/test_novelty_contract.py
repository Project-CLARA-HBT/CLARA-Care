"""Test that the POPETS novelty contract contains all required sections.

Purpose
-------
Stdlib-only structural gate for task ``POPETS-scope``. It enforces the
deliverable contract of ``research/venue2027/VENUES/popets/TASKS/POPETS-scope.md``
against ``research/venue2027/popets/novelty_contract.md``:

required sections (paper title + target reader, claim-to-prior-work
falsification matrix with real prior-work ids, >=3 RQs each with 5 fields,
>=3 named baselines, distinct-endpoint sentence vs GLHS R4 and the other
eight venues, archive-reuse refusal, and a Decision line).

Allowed input: the contract markdown file in this repository only.

Failure semantics: every check raises ``AssertionError`` with a stable
reason-style message; a missing contract file is a hard failure
(MISSING_CONTRACT), never silently skipped.

Version: 1.0.0
"""

from __future__ import annotations

import pathlib
import re

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "novelty_contract.md"

EXPECTED_RQ_IDS = ("RQ1", "RQ2", "RQ3")
RQ_FIELD_PATTERNS = (
    "Primary endpoint",
    "Strongest competing baseline",
    "Independent oracle",
    "Statistical test",
    "Falsification condition",
)
REQUIRED_BASELINES = (
    "always-recompute authorized projection",
    "Zanzibar-like consistency-token authorization",
    "coarse cache purge",
)
OTHER_VENUES = (
    "DSN",
    "IFIP SEC",
    "ACNS",
    "COMPSAC",
    "AIME",
    "SACMAT",
    "DIMVA",
    "PST",
)
REQUIRED_PRIOR_IDS = (
    "zanzibar19",
    "macaroons14",
    "muse",
    "openfga",
    "fhir5",
)


def _contract_text() -> str:
    """Load the contract; MISSING_CONTRACT if absent (never skip)."""
    if not CONTRACT.is_file():
        raise AssertionError(f"MISSING_CONTRACT: expected contract at {CONTRACT}")
    return CONTRACT.read_text(encoding="utf-8")


def test_paper_title_and_target_reader() -> None:
    text = _contract_text()
    assert "Revocation-Complete Future Disclosure" in text, "MISSING_PAPER_TITLE"
    assert re.search(r"\*\*Target reader:\*\*", text) is not None, "MISSING_TARGET_READER"


def test_falsification_matrix_with_real_prior_work_ids() -> None:
    text = _contract_text()
    assert "Claim-to-prior-work falsification matrix" in text, "MISSING_FALSIFICATION_MATRIX"
    table_rows = [line for line in text.splitlines() if line.strip().startswith("| C")]
    assert len(table_rows) >= 5, "FALSIFICATION_MATRIX_TOO_FEW_CLAIMS"
    for prior_id in REQUIRED_PRIOR_IDS:
        assert prior_id in text, f"MISSING_PRIOR_WORK_ID:{prior_id}"


def test_three_rqs_with_five_fields_each() -> None:
    text = _contract_text()
    rq_sections = {
        rq: len(re.findall(rf"^### {rq} —", text, flags=re.MULTILINE)) for rq in EXPECTED_RQ_IDS
    }
    for rq, count in rq_sections.items():
        assert count == 1, f"RQ_SECTION_MISSING_OR_DUPLICATED:{rq}"
    rq_blocks = re.split(r"^### RQ", text, flags=re.MULTILINE)[1:]
    rq_blocks = rq_blocks[:3]
    assert len(rq_blocks) == 3, "RQ_COUNT_MUST_BE_EXACTLY_THREE"
    for block in rq_blocks:
        for field in RQ_FIELD_PATTERNS:
            assert re.search(rf"\*\*{field}:\*\*", block) is not None, f"RQ_FIELD_MISSING:{field}"


def test_at_least_three_named_baselines() -> None:
    text = _contract_text()
    found = [b for b in REQUIRED_BASELINES if b in text]
    assert len(found) >= 3, f"BASELINES_TOO_FEW: found {len(found)} of {len(REQUIRED_BASELINES)}"
    for label in ("B1", "B2", "B3", "B4"):
        assert label in text, f"MISSING_BASELINE_ARM_LABEL:{label}"


def test_distinct_endpoint_sentence_vs_glhs_r4_and_other_venues() -> None:
    text = _contract_text()
    assert "truly distinct primary endpoint" in text, "MISSING_DISTINCT_ENDPOINT_SENTENCE"
    assert "governed_read_to_proposal_to_write_correctness" in text, (
        "MISSING_GLSH_R4_ENDPOINT_CONTRAST"
    )
    assert "revoked-context re-disclosure rate" in text, "MISSING_TRULY_DISTINCT_ENDPOINT_NAME"
    for venue in OTHER_VENUES:
        assert venue in text, f"MISSING_VENUE_CONTRAST:{venue}"


def test_archive_reuse_refusal() -> None:
    text = _contract_text()
    assert "Frozen E15–E22" in text, "MISSING_E15_E22_REFUSAL"
    assert "not new evidence" in text, "MISSING_ARCHIVE_REFUSAL_STATEMENT"
    assert "reuses_archive: []" in text, "MISSING_REUSE_ARCHIVE_DECLARATION"


def test_decision_line_is_go() -> None:
    text = _contract_text()
    decisions = re.findall(r"^\*\*Decision:\s*(GO|NO-GO)\*\*", text, flags=re.MULTILINE)
    assert len(decisions) >= 1, "MISSING_DECISION_LINE"
    assert decisions[0] == "GO", f"DECISION_NOT_GO:{decisions[0]}"


def test_no_invented_empirical_numbers() -> None:
    text = _contract_text()
    invented = re.findall(r"(?:rate|score|p95|latency)\s*[=:]\s*\d+(?:\.\d+)?%?", text)
    assert not invented, f"INVENTED_EMPIRICAL_NUMBERS:{invented}"
