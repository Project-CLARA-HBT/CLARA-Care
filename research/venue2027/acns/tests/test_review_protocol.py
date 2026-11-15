"""Structural gate for ACNS-X01_review_protocol (systematic-review selection protocol).

Purpose
-------
Machine-checks task ``ACNS-X01_review_protocol`` (venue ``acns``, phase ``P01``)
against its deliverable contract: ``research/venue2027/acns/design/
sok_review_protocol.md`` must be a **reproducible systematic-review selection
protocol** for the SoK corpus, carrying:

- explicit **inclusion criteria** (peer-reviewed attestation, provenance,
  agent tool-use / receipt claims) and **exclusion criteria** (marketing and
  non-peer-reviewed material excluded via a stable reason code);
- the exact **search strings**, at least **two named databases** (the protocol
  registers five), an explicit **date range** and **cutoff date**, and the
  backward/forward **snowballing** procedure with a saturation rule;
- the **screening stages** (title -> abstract -> full text) with a per-stage
  count ledger table;
- the **coding scheme** and **inter-rater conflict resolution** rules;
- the **risk-of-bias / evidence-boundary** coding rubric;
- the explicit **anti-bias rule**: the authors' own CLARA paper may not
  dominate the corpus, and convenience-only sampling is prohibited;
- an honest execution statement that **no live search was executed**, so the
  stage counts are planned zeros, never invented observed results;
- **no placeholder text** such as ``TBD``/``TODO`` anywhere in the document.

The test also asserts the protocol stays aligned with the standing ACNS
declarations (SoK framing in the novelty contract, cross-study firewall) and
that it does not fabricate empirical values (no invented counts or kappa).

Allowed input
-------------
Read-only access to the protocol markdown and the ACNS novelty contract.
No network, no database, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_X01_``; pytest reports the failing check directly. Stdlib-only besides
pytest itself.

Version
-------
``ACNS_X01_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

ACNS_X01_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
PROTOCOL_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "design" / "sok_review_protocol.md"
NOVELTY_CONTRACT_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "novelty_contract.md"

# --- required section anchors (markdown headings) ---------------------------
REQUIRED_SECTIONS = (
    "Population and unit of analysis",
    "Inclusion criteria",
    "Exclusion criteria",
    "Search strategy",
    "Screening stages",
    "Coding scheme",
    "Inter-rater conflict resolution",
    "Risk-of-bias",
    "Corpus anti-bias rules",
    "Execution status",
)

# --- inclusion-criteria content --------------------------------------------
INCLUSION_MARKERS = (
    "I1",  # peer-reviewed attestation criterion id
    "peer-reviewed",
    "I3",  # provenance-relevant topic
    "I4",  # agent tool-use / receipt-claim relevance
    "I5",  # retrievable full text with provenance + retrieval date
)

# --- exclusion-criteria content --------------------------------------------
EXCLUSION_CODE_PATTERN = re.compile(r"EXCL_[A-Z_]+")
REQUIRED_EXCLUSION_CODES = (
    "EXCL_NOT_PEER_REVIEWED",
    "EXCL_OUT_OF_WINDOW",
    "EXCL_OUT_OF_TOPIC",
    "EXCL_DUPLICATE",
    "EXCL_UNAVAILABLE",
)
EXCLUSION_SCOPE_MARKERS = (
    "Marketing",  # marketing material explicitly excluded
    "white paper",  # concrete marketing exemplar
    "blog",  # concrete non-peer-reviewed exemplar
    "preprint",  # arXiv-style non-peer-reviewed material
)

# --- search-strategy content -----------------------------------------------
REQUIRED_DATABASES = (
    "ACM Digital Library",
    "IEEE Xplore",
    "Scopus",
    "DBLP",
    "USENIX",
)
REQUIRED_SEARCH_STRING_IDS = ("S1_", "S2_", "S3_", "S4_", "S5_")
SNOWBALL_MARKERS = ("Backward snowballing", "Forward snowballing", "Saturation rule")

# --- screening ledger -------------------------------------------------------
SCREENING_STAGE_ROWS = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")
SCREENING_STAGE_LABELS = {
    "S2": "Title screening",
    "S3": "Abstract screening",
    "S4": "Full-text screening",
}
LEDGER_HEADER_MARKERS = ("Observed count", "Status")

# --- coding / conflict / bias content ---------------------------------------
CODING_FIELD_PATTERN = re.compile(r"^-\s+\*\*C\d", re.MULTILINE)
CONFLICT_MARKERS = (
    "third-coder adjudication",
    "conservative inclusion",
    "Cohen",
    "Adjudication ledger",
)
BIAS_RUBRIC_PATTERN = re.compile(r"^-\s+\*\*`?BND_[A-Z]+`?\*\*", re.MULTILINE)
REQUIRED_BND_CODES = ("BND_VALID", "BND_OVERREAD", "BND_UNDERREAD", "BND_INDETERMINATE")
RISK_OF_BIAS_PATTERN = re.compile(r"^\|\s*RB\d", re.MULTILINE)
INDETERMINATE_MARKER = "INDETERMINATE"

# --- anti-bias rule ---------------------------------------------------------
ANTI_BIAS_MARKERS = (
    "may not dominate",
    "CLARA",
    "Convenience-only sampling prohibited",
    "EXCL_NOT_TRACEABLE",
)

# --- honest-execution statement --------------------------------------------
NO_LIVE_SEARCH_MARKER = "NO LIVE SEARCH WAS EXECUTED"
PLANNED_ZERO_MARKER = "planned, not executed"

# --- forbidden placeholder text --------------------------------------------
PLACEHOLDER_PATTERN = re.compile(r"\b(TBD|TODO|FIXME|XXX|<placeholder>|LOREM)\b")

# --- forbidden fabricated-empirics patterns ---------------------------------
FABRICATED_EMPIRICS = (
    "kappa = 0.",
    "κ = 0.",
    "agreement of 0.",
    "we screened 1",
    "we included 1",
)


def _protocol_text() -> str:
    assert PROTOCOL_PATH.is_file(), f"ACNS_X01_PROTOCOL_MISSING: {PROTOCOL_PATH}"
    return PROTOCOL_PATH.read_text(encoding="utf-8")


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
    assert start is not None, f"ACNS_X01_SECTION_MISSING: {heading_fragment!r}"
    return "".join(lines[start:] if end is None else lines[start:end])


def _ledger_table(text: str) -> str:
    section = _section(text, "Screening stages")
    lines = [ln for ln in section.splitlines() if ln.strip().startswith("|")]
    assert len(lines) >= 3, "ACNS_X01_LEDGER_TABLE_MISSING"
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Structural completeness
# ---------------------------------------------------------------------------


def test_version_declared() -> None:
    assert ACNS_X01_TEST_VERSION == "1.0.0"


def test_protocol_file_exists() -> None:
    assert PROTOCOL_PATH.is_file(), f"protocol missing: {PROTOCOL_PATH}"


def test_all_required_sections_present() -> None:
    text = _protocol_text()
    for section in REQUIRED_SECTIONS:
        assert re.search(
            rf"^#+\s+.*{re.escape(section)}", text, flags=re.MULTILINE
        ), f"ACNS_X01_SECTION_HEADING_MISSING: {section!r}"


def test_no_placeholder_text_anywhere() -> None:
    match = PLACEHOLDER_PATTERN.search(_protocol_text())
    assert match is None, f"ACNS_X01_PLACEHOLDER_TEXT_FOUND: {match.group(0) if match else ''}"


def test_pre_registered_window_and_cutoff_date_present() -> None:
    text = _protocol_text()
    assert re.search(r"2019-01-01", text), "ACNS_X01_WINDOW_START_MISSING"
    assert re.search(r"cutoff date:\s*2026-12-31", text), "ACNS_X01_CUTOFF_DATE_MISSING"


def test_no_fabricated_empirical_values() -> None:
    lowered = _protocol_text().lower()
    for pattern in FABRICATED_EMPIRICS:
        assert pattern not in lowered, f"ACNS_X01_FABRICATED_EMPIRICS: {pattern!r}"


# ---------------------------------------------------------------------------
# Inclusion / exclusion criteria
# ---------------------------------------------------------------------------


def test_inclusion_criteria_explicit() -> None:
    section = _section(_protocol_text(), "Inclusion criteria")
    for marker in INCLUSION_MARKERS:
        assert marker in section, f"ACNS_X01_INCLUSION_MARKER_MISSING: {marker!r}"
    assert "peer-reviewed" in section.lower(), "ACNS_X01_PEER_REVIEW_ATTESTATION_MISSING"


def test_exclusion_codes_registered() -> None:
    section = _section(_protocol_text(), "Exclusion criteria")
    codes = set(EXCLUSION_CODE_PATTERN.findall(section))
    for code in REQUIRED_EXCLUSION_CODES:
        assert code in codes, f"ACNS_X01_EXCLUSION_CODE_MISSING: {code}"


def test_marketing_and_non_peer_reviewed_excluded() -> None:
    section = _section(_protocol_text(), "Exclusion criteria")
    for marker in EXCLUSION_SCOPE_MARKERS:
        assert (
            marker.lower() in section.lower()
        ), f"ACNS_X01_EXCLUSION_SCOPE_MARKER_MISSING: {marker!r}"


def test_every_exclusion_requires_justification_no_silent_drops() -> None:
    section = _section(_protocol_text(), "Exclusion criteria")
    assert "Silent dropping is forbidden" in section, "ACNS_X01_NO_SILENT_DROP_RULE_MISSING"


# ---------------------------------------------------------------------------
# Search strategy: databases, strings, dates, snowballing
# ---------------------------------------------------------------------------


def test_at_least_two_databases_named() -> None:
    text = _protocol_text()
    named = [db for db in REQUIRED_DATABASES if db in text]
    assert len(named) >= 2, f"ACNS_X01_TOO_FEW_DATABASES: {named}"


def test_all_five_registered_databases_named() -> None:
    text = _protocol_text()
    for db in REQUIRED_DATABASES:
        assert db in text, f"ACNS_X01_DATABASE_MISSING: {db!r}"


def test_exact_search_strings_present() -> None:
    text = _protocol_text()
    for string_id in REQUIRED_SEARCH_STRING_IDS:
        assert string_id in text, f"ACNS_X01_SEARCH_STRING_MISSING: {string_id!r}"
    assert "attestation" in text and "provenance" in text, "ACNS_X01_CORE_SEARCH_TERMS_MISSING"


def test_snowballing_procedure_present() -> None:
    text = _protocol_text()
    for marker in SNOWBALL_MARKERS:
        assert marker in text, f"ACNS_X01_SNOWBALL_MARKER_MISSING: {marker!r}"


# ---------------------------------------------------------------------------
# Screening stages: table with per-stage counts
# ---------------------------------------------------------------------------


def test_screening_stage_table_present_with_header() -> None:
    table = _ledger_table(_protocol_text())
    for header in LEDGER_HEADER_MARKERS:
        assert header in table, f"ACNS_X01_LEDGER_HEADER_MISSING: {header!r}"


def test_screening_stage_rows_cover_full_pipeline() -> None:
    table = _ledger_table(_protocol_text())
    for stage in SCREENING_STAGE_ROWS:
        assert re.search(rf"\|\s*{stage}\s", table), f"ACNS_X01_LEDGER_STAGE_ROW_MISSING: {stage}"


def test_title_abstract_fulltext_stages_named() -> None:
    table = _ledger_table(_protocol_text())
    for stage, label in SCREENING_STAGE_LABELS.items():
        stage_row = next((ln for ln in table.splitlines() if f"| {stage} " in ln), "")
        assert label in stage_row, f"ACNS_X01_STAGE_LABEL_MISSING: {stage} {label!r}"


def test_ledger_counts_are_zero_planned_not_observed() -> None:
    """Pre-execution honesty: every count is 0 and labeled planned, not executed."""
    table = _ledger_table(_protocol_text())
    observed = [ln for ln in table.splitlines() if "| 0 |" in ln and PLANNED_ZERO_MARKER in ln]
    assert observed, "ACNS_X01_LEDGER_ZERO_PLANNED_ROWS_MISSING"
    for ln in table.splitlines():
        if not ln.strip().startswith("|") or "Observed count" in ln or ln.startswith("|--"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        stage = cells[0] if cells else ""
        if not re.fullmatch(r"S\d", stage):
            continue
        count = cells[-2] if len(cells) >= 2 else ""
        assert count == "0", f"ACNS_X01_NONZERO_INVENTED_COUNT: {stage}={count!r}"
        assert PLANNED_ZERO_MARKER in cells[-1], f"ACNS_X01_COUNT_NOT_LABELED_PLANNED: {stage}"


def test_no_live_search_statement_present() -> None:
    text = _protocol_text()
    assert NO_LIVE_SEARCH_MARKER in text, "ACNS_X01_NO_LIVE_SEARCH_STATEMENT_MISSING"


# ---------------------------------------------------------------------------
# Coding scheme and conflict resolution
# ---------------------------------------------------------------------------


def test_coding_scheme_fields_defined() -> None:
    section = _section(_protocol_text(), "Coding scheme")
    fields = CODING_FIELD_PATTERN.findall(section)
    assert len(fields) >= 4, f"ACNS_X01_CODING_FIELDS_TOO_FEW: {len(fields)}"
    for concept in ("evidence class", "lattice level", "observer", "trust"):
        assert concept in section.lower(), f"ACNS_X01_CODING_CONCEPT_MISSING: {concept!r}"


def test_conflict_resolution_rules_present() -> None:
    section = _section(_protocol_text(), "Inter-rater conflict resolution")
    for marker in CONFLICT_MARKERS:
        assert marker in section, f"ACNS_X01_CONFLICT_MARKER_MISSING: {marker!r}"
    assert "14 days" in section, "ACNS_X01_ADJUDICATION_DEADLINE_MISSING"


def test_indeterminate_retained_not_coerced() -> None:
    section = _section(_protocol_text(), "Inter-rater conflict resolution")
    assert INDETERMINATE_MARKER in section, "ACNS_X01_INDETERMINATE_RETENTION_MISSING"
    assert "never coerced" in section or "Coercing" in section, "ACNS_X01_NO_COERCION_RULE_MISSING"


# ---------------------------------------------------------------------------
# Risk-of-bias / evidence-boundary rubric
# ---------------------------------------------------------------------------


def test_risk_of_bias_domains_defined() -> None:
    section = _section(_protocol_text(), "Risk-of-bias and evidence-boundary rubric")
    domains = RISK_OF_BIAS_PATTERN.findall(section)
    assert len(domains) >= 3, f"ACNS_X01_RISK_OF_BIAS_DOMAINS_TOO_FEW: {len(domains)}"
    assert "UNKNOWN" in section, "ACNS_X01_RB_UNKNOWN_CODE_MISSING"
    assert "sensitivity analysis" in section, "ACNS_X01_RB_SENSITIVITY_ANALYSIS_MISSING"


def test_evidence_boundary_codes_defined() -> None:
    section = _section(_protocol_text(), "Risk-of-bias and evidence-boundary rubric")
    codes = BIAS_RUBRIC_PATTERN.findall(section)
    assert codes, "ACNS_X01_BOUNDARY_RUBRIC_ABSENT"
    for code in REQUIRED_BND_CODES:
        assert re.search(rf"\*\*`?{code}`?\*\*", section), f"ACNS_X01_BOUNDARY_CODE_MISSING: {code}"


# ---------------------------------------------------------------------------
# Anti-bias rules: own-paper cap and convenience-sampling prohibition
# ---------------------------------------------------------------------------


def test_own_paper_dominance_prohibited() -> None:
    section = _section(_protocol_text(), "Corpus anti-bias rules")
    for marker in ANTI_BIAS_MARKERS:
        assert marker in section, f"ACNS_X01_ANTI_BIAS_MARKER_MISSING: {marker!r}"
    assert re.search(
        r"at most\s*\**\s*3\**\s+CLARA", section
    ), "ACNS_X01_OWN_PAPER_HARD_CAP_MISSING"
    assert "with and without" in section, "ACNS_X01_WITH_AND_WITHOUT_ANALYSIS_MISSING"
    assert "solely" in section, "ACNS_X01_NO_SOLE_CLARA_ANCHOR_RULE_MISSING"


def test_convenience_sampling_prohibited() -> None:
    section = _section(_protocol_text(), "Corpus anti-bias rules")
    assert (
        "Convenience-only sampling prohibited" in section
    ), "ACNS_X01_CONVENIENCE_PROHIBITION_MISSING"
    channels = ("logged database-search hit", "logged snowball step", "registered seed set")
    for channel in channels:
        assert channel in section, f"ACNS_X01_TRACEABILITY_CHANNEL_MISSING: {channel!r}"


def test_cross_study_firewall_declared() -> None:
    section = _section(_protocol_text(), "Corpus anti-bias rules")
    for firewall in ("E15", "IFIP", "DIMVA"):
        assert firewall in section, f"ACNS_X01_FIREWALL_CLAUSE_MISSING: {firewall}"


def test_competitor_and_negative_finding_retention() -> None:
    section = _section(_protocol_text(), "Corpus anti-bias rules")
    assert "negative" in section.lower(), "ACNS_X01_NEGATIVE_RESULT_RETENTION_MISSING"
    assert "RFC 9334" in section, "ACNS_X01_BASELINE_RETENTION_MISSING"


# ---------------------------------------------------------------------------
# Alignment with standing ACNS declarations
# ---------------------------------------------------------------------------


def test_alignment_with_novelty_contract() -> None:
    assert NOVELTY_CONTRACT_PATH.is_file(), f"ACNS_X01_CONTRACT_MISSING: {NOVELTY_CONTRACT_PATH}"
    contract = NOVELTY_CONTRACT_PATH.read_text(encoding="utf-8")
    assert (
        "2019" in contract and "2026" in contract
    ), "ACNS_X01_CONTRACT_WINDOW_DRIFT: novelty contract no longer declares 2019-2026"
    text = _protocol_text()
    assert "Systematization of Knowledge" in contract, "ACNS_X01_CONTRACT_SOK_DECLARATION_ABSENT"
    assert "systematic" in text.lower(), "ACNS_X01_PROTOCOL_NOT_SYSTEMATIC"


def test_search_strings_are_frozen_with_adaptation_rule() -> None:
    section = _section(_protocol_text(), "Exact search strings", level=3)
    assert "verbatim" in section.lower(), "ACNS_X01_VERBATIM_EXECUTION_RULE_MISSING"
    assert "search log" in section, "ACNS_X01_ADAPTATION_LOGGING_RULE_MISSING"
