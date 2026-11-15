"""Structural gate for AIME-X03_review_rubric (clinical adjudication rubric).

Purpose
-------
Machine-checks task ``AIME-X03_review_rubric`` (venue ``aime``, phase ``P02``)
against its deliverable contract: ``research/venue2027/aime/design/
clinical_annotation_rubric.md`` must be a frozen, pre-registered clinical
adjudication rubric carrying:

- all **five** primary categories with explicit definitions:
  clinical correctness, omission, unsafe suggestion, permission/disclosure
  error, indeterminate;
- the mandatory **two independent qualified clinical reviewers** requirement
  wherever medical correctness is claimed, with concrete independence
  eligibility conditions;
- **blinded arms**: arm/provider/method blinding, locked randomized
  presentation order, cross-reviewer visibility prohibition, and a
  self-review prohibition;
- a documented **conflict adjudication procedure** (third-reviewer path,
  conservative resolution, append-only adjudication ledger, reported
  inter-rater agreement);
- an explicit **prohibition of auto-accepting LLM-as-judge output**
  (no label auto-acceptance, no rationale pre-fill, no model-certified
  oracle);
- the INDETERMINATE preservation rule (never coerced into a pass,
  rejection, or safe rejection);
- **no fabricated reviewer names, credentials, kappa values, or any other
  invented human-subject or empiric data** (annotation not executed).

Allowed input
-------------
Read-only access to the rubric markdown at its repository-relative path,
located from this test file's position on disk. No network, no database,
no provider calls, no randomness, no filesystem writes.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``AIME_X03_``; pytest reports the failing check directly. Stdlib-only
(``pathlib``, ``re``) besides pytest itself.

Version
-------
``AIME_X03_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

AIME_X03_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
RUBRIC_PATH = (
    REPO_ROOT / "research" / "venue2027" / "aime" / "design" / "clinical_annotation_rubric.md"
)

# --- required section anchors (markdown headings) ---------------------------
REQUIRED_SECTIONS = (
    "What is adjudicated and by whom",
    "The five annotation categories",
    "Separate rating dimensions",
    "Blinding protocol",
    "Conflict adjudication procedure",
    "Reviewer output record",
    "Prohibition of LLM-as-judge auto-acceptance",
    "Quality control, failure semantics, and escalation",
    "Denominator, reporting, and falsification discipline",
    "Execution status",
)

# --- the five primary categories (exact target contract) --------------------
REQUIRED_CATEGORIES = (
    "CLINICAL_CORRECTNESS",
    "OMISSION",
    "UNSAFE_SUGGESTION",
    "PERMISSION_ERROR",
    "INDETERMINATE",
)

# Human-readable category names that must appear with a definition marker.
CATEGORY_DEFINITION_MARKERS = {
    "CLINICAL_CORRECTNESS": "Definition.",
    "OMISSION": "Definition.",
    "UNSAFE_SUGGESTION": "Definition.",
    "PERMISSION_ERROR": "Definition.",
    "INDETERMINATE": "Definition.",
}

# Target-contract phrasing from the task/manifest signature line.
CONTRACT_SIGNATURE_PHRASES = (
    "clinical correctness",
    "omission",
    "unsafe suggestion",
    "permission",
    "indeterminate",
)

# --- two-reviewer independence requirement ----------------------------------
TWO_REVIEWER_MARKERS = (
    "TWO (2) independent qualified clinical reviewers",
    "R1",
    "R2",
)

ELIGIBILITY_MARKERS = (
    "Licensed clinician",
    "No role in any arm",
    "No conflict of interest",
    "Independence from the other reviewer",
    "Written consent",
)

MEDICAL_CORRECTNESS_CLAIM_LINK = "medical-correctness claim"
SINGLE_REVIEWER_INSUFFICIENT_MARKERS = (
    "A single reviewer",
    "never sufficient",
)

# --- blinding requirement ---------------------------------------------------
BLINDING_MARKERS = (
    "blinded to model arm",
    "Arm blinding",
    "Provider blinding",
    "Method blinding",
    "Locked and randomized",
    "never see each other's ratings",
    "Self-review prohibition",
)

# --- conflict adjudication --------------------------------------------------
CONFLICT_MARKERS = (
    "Third-reviewer adjudication",
    "Conservative-resolution rule",
    "Append-only adjudication ledger",
    "reported, not assumed",
    "Cohen",
)

# --- LLM-as-judge prohibition ----------------------------------------------
LLM_JUDGE_PROHIBITION_MARKERS = (
    "Auto-accepting LLM-as-judge output is prohibited",
    "never be auto-accepted",
    "never be pre-populated by a model",
    "never certifies its own labels",
)

# --- indeterminate preservation ---------------------------------------------
INDETERMINATE_PRESERVATION_MARKERS = (
    "never coerced into a pass, a rejection, or a safe failure",
    "never counted as a safe rejection",
    "denominator is never silently shrunk",
)

# --- honest execution status ------------------------------------------------
NOT_EXECUTED_MARKERS = ("NO CLINICAL ANNOTATION HAS BEEN EXECUTED",)
PLANNED_NOT_RESULT_MARKER = "method commitment, not a result"

# --- forbidden fabricated human-subject data --------------------------------
# Any concrete reviewer identity, credential string, or observed agreement
# statistic is fabrication: no roster exists at registration time.
FABRICATED_NAME_PATTERNS = (
    re.compile(r"\bDr\.?\s+[A-Z][a-z]+"),
    re.compile(r"\b(MD|DO|MBBS|NP|PA-C)\b\s*[,;–—-]\s*[A-Z][a-z]+"),
    re.compile(r"Reviewer\s+(?:[A-Z][a-z]+)\s+(?:[A-Z][a-z]+)"),
)
FABRICATED_CREDENTIAL_MARKERS = (
    "Board Certified",
    "board-certified in",
    "years of experience",
    "Dr.",
)
FABRICATED_EMPIRICS = (
    "kappa = 0.",
    "κ = 0.",
    "kappa of 0.",
    "agreement of 0.",
    "agreement was 0.",
    "we annotated",
    "we reviewed",
    "reviewers agreed on",
    "R1 and R2 agreed on",
)

# --- forbidden placeholder text ---------------------------------------------
PLACEHOLDER_PATTERN = re.compile(r"\b(TBD|TODO|FIXME|XXX|<placeholder>|LOREM)\b")


def _rubric_text() -> str:
    assert RUBRIC_PATH.is_file(), f"AIME_X03_RUBRIC_MISSING: {RUBRIC_PATH}"
    return RUBRIC_PATH.read_text(encoding="utf-8")


def _section(text: str, heading_fragment: str, *, level: int = 2) -> str:
    """Return one markdown section: from its heading line to the next same-level heading."""
    prefix = rf"^{'#' * level}\s"
    lines = text.splitlines(keepends=True)
    start = end = None
    for index, line in enumerate(lines):
        if start is None:
            if re.match(prefix, line) and heading_fragment in line:
                start = index
        elif re.match(prefix, line):
            end = index
            break
    assert start is not None, f"AIME_X03_SECTION_MISSING: {heading_fragment!r}"
    return "".join(lines[start:] if end is None else lines[start:end])


# ---------------------------------------------------------------------------
# Structural completeness
# ---------------------------------------------------------------------------


def test_version_declared() -> None:
    assert AIME_X03_TEST_VERSION == "1.0.0"


def test_rubric_file_exists() -> None:
    assert RUBRIC_PATH.is_file(), f"rubric missing: {RUBRIC_PATH}"


def test_all_required_sections_present() -> None:
    text = _rubric_text()
    for section in REQUIRED_SECTIONS:
        assert re.search(
            rf"^#+\s+.*{re.escape(section)}", text, flags=re.MULTILINE
        ), f"AIME_X03_SECTION_HEADING_MISSING: {section!r}"


def test_no_placeholder_text_anywhere() -> None:
    match = PLACEHOLDER_PATTERN.search(_rubric_text())
    assert match is None, f"AIME_X03_PLACEHOLDER_TEXT_FOUND: {match.group(0) if match else ''}"


# ---------------------------------------------------------------------------
# The five categories with explicit definitions
# ---------------------------------------------------------------------------


def test_all_five_categories_present() -> None:
    text = _rubric_text()
    for category in REQUIRED_CATEGORIES:
        assert re.search(
            rf"\b{re.escape(category)}\b", text
        ), f"AIME_X03_CATEGORY_MISSING: {category}"


def test_each_category_has_explicit_definition_and_examples() -> None:
    text = _rubric_text()
    for category, definition_marker in CATEGORY_DEFINITION_MARKERS.items():
        # Each category gets its own subsection carrying a Definition marker,
        # positive examples, and an explicit boundary rule.
        section = _section(text, category, level=3)
        assert definition_marker in section, f"AIME_X03_CATEGORY_DEFINITION_MISSING: {category}"
        assert "Positive examples." in section, f"AIME_X03_CATEGORY_EXAMPLES_MISSING: {category}"
        assert "Boundary." in section, f"AIME_X03_CATEGORY_BOUNDARY_MISSING: {category}"


def test_target_contract_signature_phrases_present() -> None:
    text = _rubric_text()
    for phrase in CONTRACT_SIGNATURE_PHRASES:
        assert phrase in text.lower(), f"AIME_X03_CONTRACT_PHRASE_MISSING: {phrase!r}"


# ---------------------------------------------------------------------------
# Two independent qualified clinical reviewers
# ---------------------------------------------------------------------------


def test_two_independent_reviewers_required() -> None:
    text = _rubric_text()
    for marker in TWO_REVIEWER_MARKERS:
        assert marker in text, f"AIME_X03_TWO_REVIEWER_MARKER_MISSING: {marker!r}"


def test_reviewer_requirement_tied_to_medical_correctness_claims() -> None:
    text = _rubric_text()
    assert MEDICAL_CORRECTNESS_CLAIM_LINK in text, "AIME_X03_MEDICAL_CORRECTNESS_LINK_MISSING"
    section = _section(text, "What is adjudicated and by whom")
    for marker in SINGLE_REVIEWER_INSUFFICIENT_MARKERS:
        assert marker in section, f"AIME_X03_SINGLE_REVIEWER_REFUSAL_MISSING: {marker!r}"


def test_reviewer_eligibility_conditions_explicit() -> None:
    section = _section(_rubric_text(), "What is adjudicated and by whom")
    for marker in ELIGIBILITY_MARKERS:
        assert marker in section, f"AIME_X03_ELIGIBILITY_MARKER_MISSING: {marker!r}"


def test_third_reviewer_registered_for_conflicts_only() -> None:
    section = _section(_rubric_text(), "What is adjudicated and by whom")
    assert "third qualified clinician" in section, "AIME_X03_THIRD_REVIEWER_MISSING"
    assert (
        "after both R1 and R2 have locked ratings" in section
    ), "AIME_X03_THIRD_REVIEWER_TIMING_MISSING"


def test_model_agent_never_a_reviewer() -> None:
    text = _rubric_text()
    assert (
        "candidate-model agent is never a reviewer" in text
    ), "AIME_X03_MODEL_AGENT_EXCLUSION_MISSING"


# ---------------------------------------------------------------------------
# Blinding (rule 2, INDEPENDENT_EVIDENCE_PROTOCOL.md)
# ---------------------------------------------------------------------------


def test_blinding_protocol_complete() -> None:
    text = _rubric_text()
    for marker in BLINDING_MARKERS:
        assert marker in text, f"AIME_X03_BLINDING_MARKER_MISSING: {marker!r}"


def test_blinding_rule_2_boundary_cited() -> None:
    text = _rubric_text()
    assert "INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2" in text, "AIME_X03_RULE2_CITATION_MISSING"


# ---------------------------------------------------------------------------
# Conflict adjudication procedure
# ---------------------------------------------------------------------------


def test_conflict_adjudication_documented() -> None:
    text = _rubric_text()
    for marker in CONFLICT_MARKERS:
        assert marker in text, f"AIME_X03_CONFLICT_MARKER_MISSING: {marker!r}"


def test_conservative_resolution_direction_specified() -> None:
    section = _section(_rubric_text(), "Conflict adjudication procedure")
    assert (
        "UNSAFE_SUGGESTION over OMISSION over CLINICAL_CORRECTNESS" in section
    ), "AIME_X03_CONSERVATIVE_DIRECTION_MISSING"


def test_inter_rater_agreement_reported_not_assumed() -> None:
    section = _section(_rubric_text(), "Conflict adjudication procedure")
    assert "kappa" in section.lower(), "AIME_X03_KAPPA_MISSING"
    assert "confidence intervals" in section.lower(), "AIME_X03_KAPPA_CI_MISSING"


# ---------------------------------------------------------------------------
# LLM-as-judge prohibition
# ---------------------------------------------------------------------------


def test_llm_judge_auto_acceptance_prohibited() -> None:
    text = _rubric_text()
    for marker in LLM_JUDGE_PROHIBITION_MARKERS:
        assert marker in text, f"AIME_X03_LLM_JUDGE_PROHIBITION_MISSING: {marker!r}"


def test_no_prefill_of_reviewer_rationales() -> None:
    section = _section(_rubric_text(), "Prohibition of LLM-as-judge auto-acceptance")
    assert "rubber-stamping" in section, "AIME_X03_RUBBER_STAMPING_RULE_MISSING"
    assert "pre-populated" in section, "AIME_X03_PREFILL_RULE_MISSING"


def test_rationale_is_reviewers_own_words() -> None:
    section = _section(_rubric_text(), "Reviewer output record")
    assert (
        "never pre-filled, never model-generated" in section
    ), "AIME_X03_RATIONALE_OWNERSHIP_MISSING"


# ---------------------------------------------------------------------------
# INDETERMINATE preservation
# ---------------------------------------------------------------------------


def test_indeterminate_is_preserved_and_counted() -> None:
    text = _rubric_text()
    for marker in INDETERMINATE_PRESERVATION_MARKERS:
        assert marker in text, f"AIME_X03_INDETERMINATE_PRESERVATION_MISSING: {marker!r}"


def test_indecision_reason_codes_registered() -> None:
    text = _rubric_text()
    for code in (
        "INCOMPLETE_FACT_CHAIN",
        "CONFLICTING_FROZEN_SOURCES",
        "UNSAFE_AMBIGUITY",
        "INSUFFICIENT_CONTEXT",
    ):
        assert code in text, f"AIME_X03_INDECISION_REASON_CODE_MISSING: {code}"


# ---------------------------------------------------------------------------
# No fabricated reviewers, credentials, or empirics
# ---------------------------------------------------------------------------


def test_no_fabricated_reviewer_names() -> None:
    text = _rubric_text()
    for pattern in FABRICATED_NAME_PATTERNS:
        match = pattern.search(text)
        assert (
            match is None
        ), f"AIME_X03_FABRICATED_REVIEWER_NAME: {match.group(0) if match else ''}"


def test_no_fabricated_credentials() -> None:
    lowered = _rubric_text().lower()
    for marker in FABRICATED_CREDENTIAL_MARKERS:
        assert marker.lower() not in lowered, f"AIME_X03_FABRICATED_CREDENTIAL_MARKER: {marker!r}"


def test_no_fabricated_empirical_values() -> None:
    lowered = _rubric_text().lower()
    for pattern in FABRICATED_EMPIRICS:
        assert pattern not in lowered, f"AIME_X03_FABRICATED_EMPIRICS: {pattern!r}"


# ---------------------------------------------------------------------------
# Honest execution status
# ---------------------------------------------------------------------------


def test_annotation_declared_not_executed() -> None:
    text = _rubric_text()
    for marker in NOT_EXECUTED_MARKERS:
        assert marker in text, f"AIME_X03_NOT_EXECUTED_MARKER_MISSING: {marker!r}"
    assert PLANNED_NOT_RESULT_MARKER in text, "AIME_X03_METHOD_COMMITMENT_MARKER_MISSING"


def test_no_clinical_validity_claim_without_execution() -> None:
    text = _rubric_text()
    assert "no clinical validity claim" in text.lower(), "AIME_X03_NO_VALIDITY_CLAIM_RULE_MISSING"
    assert (
        "No clinician reviewer or independent original vignettes" in text
    ), "AIME_X03_FALSIFICATION_RULE_MISSING"


def test_instrument_version_frozen() -> None:
    text = _rubric_text()
    assert (
        'CLINICAL_ANNOTATION_RUBRIC_VERSION = "1.0.0"' in text
    ), "AIME_X03_INSTRUMENT_VERSION_MISSING"
