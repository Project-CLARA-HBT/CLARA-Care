"""Structural gate for ACNS-X05_rater_manual (inter-rater coder manual).

Purpose
-------
Machine-checks task ``ACNS-X05_rater_manual`` (venue ``acns``, phase ``P02``)
against its deliverable contract: ``research/venue2027/acns/design/
rater_manual.md`` must be a **pre-registered inter-rater coder manual** for the
SoK's evidence-boundary coding, consistent with the frozen review protocol
(``research/venue2027/acns/design/sok_review_protocol.md`` §6–§8). The manual
must carry:

- every evidence-boundary code (``BND_VALID``, ``BND_OVERREAD``,
  ``BND_UNDERREAD``, ``BND_INDETERMINATE``) with a definition, derivation
  rule and constructed anchor examples;
- the full set of coding dimensions **C1–C8** with definitions and decision
  rules;
- a decision tree deriving the boundary codes from the coded fields;
- the INDETERMINATE retention rules (retained, never coerced);
- the inter-rater agreement protocol: two independent human coders, blind
  allocation, a 20-source pilot frozen before main labels, sealed
  pre-adjudication streams, third-coder adjudication, and the kappa
  computation rules delegating all numeric thresholds to
  ``rq_and_estimands.yaml``/``ACNS-freeze``;
- **no invented empirical values** (no fabricated kappa/agreement numbers,
  no fabricated pilot counts beyond the registered 20-source design, no
  invented rater or reviewer names, no fabricated run/manifest identifiers).

Allowed input
-------------
Read-only access to the manual markdown, the review protocol markdown and the
RQ/estimands registry. No network, no database, no provider calls, no
randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_X05_``; pytest reports the failing check directly. Stdlib-only besides
pytest itself.

Version
-------
``ACNS_X05_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

ACNS_X05_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
MANUAL_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "design" / "rater_manual.md"
PROTOCOL_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "design" / "sok_review_protocol.md"
RQ_REGISTRY_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "rq_and_estimands.yaml"

# --- required section anchors (markdown headings) ---------------------------
REQUIRED_SECTIONS = (
    "Scope declaration",
    "Definitions",
    "Coding dimensions",
    "Evidence-boundary codes",
    "Decision tree",
    "INDETERMINATE rules",
    "Stable reason codes",
    "Coding record",
    "Inter-rater agreement protocol",
    "Falsifying defects",
    "Execution status",
)

# --- BND_* evidence-boundary codes (must match the frozen protocol rubric) --
REQUIRED_BND_CODES = ("BND_VALID", "BND_OVERREAD", "BND_UNDERREAD", "BND_INDETERMINATE")
BND_CODE_PATTERN = re.compile(r"`(BND_[A-Z_]+)`")
BND_HEADER_PATTERN = re.compile(r"^###\s+BND_[A-Z]+\s*$", re.MULTILINE)

# --- C1-C8 coding dimensions ------------------------------------------------
REQUIRED_CODING_DIMENSIONS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
DIMENSION_HEADER_PATTERN = re.compile(r"^###\s+C[1-8]\s+—\s+", re.MULTILINE)
DIMENSION_NAME_MARKERS = {
    "C1": "Claim extraction",
    "C2": "Evidence class",
    "C3": "Lattice level claimed",
    "C4": "Lattice level demonstrated",
    "C5": "Observer axis",
    "C6": "Trust axis",
    "C7": "Claim type",
    "C8": "Ambiguity flag",
}

# --- evidence lattice vocabulary (from the threat model / protocol) ---------
LATTICE_LEVELS = ("L0", "L1", "L1.5", "L2", "L3", "L4")
EVIDENCE_CLASSES = (
    "assembly",
    "egress",
    "transport acknowledgment",
    "provider-attested receipt",
    "execution trace",
    "semantic consumption",
)
OBSERVER_POSITIONS = (
    "agent host",
    "transport stack",
    "provider",
    "TEE",
    "persisting service",
    "harness-internal",
)

# --- agreement protocol markers --------------------------------------------
AGREEMENT_MARKERS = (
    "Cohen",
    "pre-adjudication",
    "first-pass",
    "blind",
    "adjudication",
    "14 days",
    "ADJ_UNAVAILABLE",
)
PILOT_MARKERS = ("20 sources", "frozen before main labels")
INDEPENDENCE_MARKERS = (
    "two independent human coders",
    "no internal LLM agent",
)

# --- INDETERMINATE rules ----------------------------------------------------
INDETERMINATE_MARKER = "INDETERMINATE"
IND_RULE_PATTERN = re.compile(r"^- \*\*IND\d", re.MULTILINE)
NO_COERCION_MARKERS = ("Coercing an unresolvable code", "falsifying defect")

# --- stable reason codes ----------------------------------------------------
REQUIRED_REASON_CODES = (
    "EXTRACT_NO_VERBATIM",
    "EXTRACT_NO_LOCATOR",
    "FIELD_UNDECIDABLE",
    "BOUNDARY_REOPENED",
    "CONFLICT_ADJUDICATION_REQUIRED",
    "ADJ_UNAVAILABLE",
)

# --- coding record ----------------------------------------------------------
CODING_RECORD_FIELDS = (
    "manual_version",
    "corpus_record_id",
    "claim_id",
    "coder_role",
    "c1_quotation",
    "c1_locator",
    "c2_evidence_class",
    "c3_level_claimed",
    "c4_level_demonstrated",
    "c5_observer_axis",
    "c7_claim_type",
    "c8_ambiguity_flag",
    "boundary_code",
    "reason_codes",
)

# --- honest execution statement --------------------------------------------
NO_CODING_RUN_MARKER = "No coding run, pilot session, or adjudication session has been executed"

# --- forbidden placeholder text --------------------------------------------
PLACEHOLDER_PATTERN = re.compile(r"\b(TBD|TODO|FIXME|XXX|LOREM)\b")

# --- forbidden fabricated empirics: any observed kappa/agreement value ------
# Registration honesty: the manual must delegate thresholds and assert no
# observed statistic. A stated "kappa = <digit>.<digit>" style value anywhere
# is fabrication (thresholds live in rq_and_estimands.yaml, not here).
FABRICATED_KAPPA_PATTERN = re.compile(
    r"kappa[^.\n]{0,40}?\b[0-1]\.[0-9]+\b",
    re.IGNORECASE,
)
FABRICATED_KAPPA_SYMBOL_PATTERN = re.compile(r"κ[^.\n]{0,40}?\b[0-1]\.[0-9]+\b")
FABRICATED_AGREEMENT_PATTERN = re.compile(
    r"agreement[^.\n]{0,60}?\b[0-9]{1,3}(\.[0-9]+)?\s*%",
    re.IGNORECASE,
)

# --- invented rater identities ---------------------------------------------
# The manual must carry pseudonymous roles only. Any "reviewer/rater/coder
# <First Last>" style personal name attribution is fabrication.
NAME_INTRO_PATTERN = re.compile(
    r"\b(reviewer|rater|coder|adjudicator)s?\s+[A-Z][a-z]+\s+[A-Z][a-z]+"
)
# Reserved role tokens that never count as invented names.
ROLE_TOKENS = {"C1", "C2", "C3"}
# Fictional-sounding anchor "author" names would also violate the no-invented-
# reviewers rule if used to imply real raters existed; catch common patterns
# where a personal name is attached to a coding decision verb.
NAME_DECISION_PATTERN = re.compile(
    r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\s+(coded|rated|adjudicated|classified|reviewed|labeled)"
)

# --- invented run/manifest identifiers -------------------------------------
RUN_ID_PATTERN = re.compile(r"run[_-]?id[\"'≥:=\s]+[\"']?[A-Za-z0-9][A-Za-z0-9_-]{3,}", re.IGNORECASE)


def _manual_text() -> str:
    assert MANUAL_PATH.is_file(), f"ACNS_X05_MANUAL_MISSING: {MANUAL_PATH}"
    return MANUAL_PATH.read_text(encoding="utf-8")


def _protocol_text() -> str:
    assert PROTOCOL_PATH.is_file(), f"ACNS_X05_PROTOCOL_MISSING: {PROTOCOL_PATH}"
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
    assert start is not None, f"ACNS_X05_SECTION_MISSING: {heading_fragment!r}"
    return "".join(lines[start:] if end is None else lines[start:end])


# ---------------------------------------------------------------------------
# Structural completeness
# ---------------------------------------------------------------------------


def test_version_declared() -> None:
    assert ACNS_X05_TEST_VERSION == "1.0.0"


def test_manual_file_exists() -> None:
    assert MANUAL_PATH.is_file(), f"manual missing: {MANUAL_PATH}"


def test_manual_version_is_stamped() -> None:
    text = _manual_text()
    assert re.search(r"[Mm]ual version.*1\.0\.0|``1\.0\.0``", text) or re.search(
        r"[Mm]anual version", text
    ), "ACNS_X05_MANUAL_VERSION_NOT_STAMPED"
    assert re.search(r"clara\.venue2027\.acns\.rater-manual\.v1", text), (
        "ACNS_X05_MANUAL_CONTRACT_ID_MISSING"
    )


def test_all_required_sections_present() -> None:
    text = _manual_text()
    for section in REQUIRED_SECTIONS:
        assert re.search(
            rf"^#+\s+.*{re.escape(section)}", text, flags=re.MULTILINE
        ), f"ACNS_X05_SECTION_HEADING_MISSING: {section!r}"


def test_no_placeholder_text_anywhere() -> None:
    match = PLACEHOLDER_PATTERN.search(_manual_text())
    assert match is None, f"ACNS_X05_PLACEHOLDER_TEXT_FOUND: {match.group(0) if match else ''}"


# ---------------------------------------------------------------------------
# BND_* codes documented with definitions, derivation and anchors
# ---------------------------------------------------------------------------


def _bnd_section() -> str:
    return _section(_manual_text(), "Evidence-boundary codes")


def test_all_bnd_codes_from_protocol_documented() -> None:
    """Every BND_* code in the frozen protocol rubric is defined in the manual."""
    manual_codes = {m.strip("`") for m in BND_CODE_PATTERN.findall(_manual_text())}
    protocol_codes = set(re.findall(r"`(BND_[A-Z_]+)`", _protocol_text()))
    for code in REQUIRED_BND_CODES:
        assert code in manual_codes, f"ACNS_X05_BND_CODE_MISSING: {code}"
    assert manual_codes == protocol_codes, (
        f"ACNS_X05_BND_CODE_SET_MISMATCH: manual={sorted(manual_codes)} "
        f"protocol={sorted(protocol_codes)}"
    )


def test_each_bnd_code_has_own_subsection() -> None:
    section = _bnd_section()
    headers = BND_HEADER_PATTERN.findall(section)
    for code in REQUIRED_BND_CODES:
        assert any(h.strip().endswith(code) for h in headers), (
            f"ACNS_X05_BND_SUBSECTION_MISSING: {code}"
        )


def test_each_bnd_code_has_definition_and_derivation() -> None:
    section = _bnd_section()
    for code in REQUIRED_BND_CODES:
        sub = _section(section, code, level=3)
        assert "**Definition.**" in sub, f"ACNS_X05_BND_DEFINITION_MISSING: {code}"
        assert "**Derivation.**" in sub or "Derivation" in sub, (
            f"ACNS_X05_BND_DERIVATION_MISSING: {code}"
        )


def test_each_bnd_code_has_anchor_examples() -> None:
    section = _bnd_section()
    for code in REQUIRED_BND_CODES:
        sub = _section(section, code, level=3)
        anchors = re.findall(r"Anchor\s+\S+", sub)
        assert len(anchors) >= 2, f"ACNS_X05_BND_ANCHORS_TOO_FEW: {code}"


# ---------------------------------------------------------------------------
# C1-C8 coding dimensions present with names matching the protocol
# ---------------------------------------------------------------------------


def test_all_coding_dimensions_c1_to_c8_present() -> None:
    text = _manual_text()
    section = _section(text, "Coding dimensions")
    headers = DIMENSION_HEADER_PATTERN.findall(section)
    assert len(headers) >= 8, f"ACNS_X05_CODING_DIMENSION_HEADERS_TOO_FEW: {len(headers)}"
    for dim in REQUIRED_CODING_DIMENSIONS:
        assert re.search(rf"^###\s+{dim}\s+—", section, flags=re.MULTILINE), (
            f"ACNS_X05_CODING_DIMENSION_MISSING: {dim}"
        )


def test_coding_dimension_names_match_protocol() -> None:
    section = _section(_manual_text(), "Coding dimensions")
    for dim, name in DIMENSION_NAME_MARKERS.items():
        dim_sub = _section(section, f"{dim} —", level=3)
        assert name.lower() in dim_sub.lower(), (
            f"ACNS_X05_DIMENSION_NAME_MISMATCH: {dim} expected {name!r}"
        )


def test_coding_dimensions_match_protocol_field_names() -> None:
    protocol = _protocol_text()
    manual = _manual_text()
    for dim, name in DIMENSION_NAME_MARKERS.items():
        assert re.search(rf"\*\*{dim}\s+{re.escape(name)}", protocol), (
            f"ACNS_X05_PROTOCOL_DIMENSION_ABSENT: {dim} {name!r}"
        )
        assert re.search(rf"{dim}\s+—\s+{re.escape(name)}", manual), (
            f"ACNS_X05_MANUAL_DIMENSION_NAME_DRIFT: {dim} {name!r}"
        )


def test_each_coding_dimension_has_decision_rules_and_anchor() -> None:
    section = _section(_manual_text(), "Coding dimensions")
    for dim in REQUIRED_CODING_DIMENSIONS:
        sub = _section(section, f"{dim} —", level=3)
        assert "Decision rules" in sub, f"ACNS_X05_DIMENSION_RULES_MISSING: {dim}"
        assert re.search(r"Anchor\s+\S+", sub), f"ACNS_X05_DIMENSION_ANCHOR_MISSING: {dim}"


# ---------------------------------------------------------------------------
# Lattice vocabulary consistency with the protocol/threat model
# ---------------------------------------------------------------------------


def test_lattice_levels_defined() -> None:
    text = _manual_text()
    for level in LATTICE_LEVELS:
        assert level in text, f"ACNS_X05_LATTICE_LEVEL_MISSING: {level}"


def test_six_evidence_classes_named() -> None:
    section = _section(
        _manual_text(), "Evidence classes and lattice levels", level=3
    )
    for cls in EVIDENCE_CLASSES:
        assert cls.lower() in section.lower(), f"ACNS_X05_EVIDENCE_CLASS_MISSING: {cls!r}"


def test_observer_positions_named() -> None:
    text = _manual_text()
    for pos in OBSERVER_POSITIONS:
        assert pos.lower() in text.lower(), f"ACNS_X05_OBSERVER_POSITION_MISSING: {pos!r}"


# ---------------------------------------------------------------------------
# Decision tree deriving boundary codes
# ---------------------------------------------------------------------------


def test_decision_tree_present_with_ordered_steps() -> None:
    section = _section(_manual_text(), "Decision tree")
    steps = re.findall(r"^- \*\*D(\d+)\s+—", section, flags=re.MULTILINE)
    assert len(steps) >= 7, f"ACNS_X05_DECISION_TREE_STEPS_TOO_FEW: {len(steps)}"
    assert [int(s) for s in steps] == sorted(int(s) for s in steps), (
        "ACNS_X05_DECISION_TREE_STEPS_UNORDERED"
    )


def test_decision_tree_derives_all_bnd_codes() -> None:
    section = _section(_manual_text(), "Decision tree")
    for code in REQUIRED_BND_CODES:
        assert code in section, f"ACNS_X05_DECISION_TREE_CODE_MISSING: {code}"


def test_boundary_code_derivable_from_c1_plus_fields() -> None:
    text = _manual_text()
    assert re.search(r"derivable from .{0,80}C1", text, flags=re.IGNORECASE) or re.search(
        r"trace to its C1 quotation", text
    ), "ACNS_X05_DERIVABILITY_RULE_MISSING"
    assert "BOUNDARY_REOPENED" in text, "ACNS_X05_BOUNDARY_REOPEN_CODE_MISSING"


# ---------------------------------------------------------------------------
# INDETERMINATE rules
# ---------------------------------------------------------------------------


def test_indeterminate_rule_section_present() -> None:
    text = _manual_text()
    assert re.search(r"^#+\s+.*INDETERMINATE rules", text, flags=re.MULTILINE), (
        "ACNS_X05_INDETERMINATE_SECTION_MISSING"
    )


def test_indeterminate_rules_numbered_and_complete() -> None:
    section = _section(_manual_text(), "INDETERMINATE rules")
    rules = IND_RULE_PATTERN.findall(section)
    assert len(rules) >= 5, f"ACNS_X05_INDETERMINATE_RULES_TOO_FEW: {len(rules)}"
    for marker in ("retained", "ambiguous-claim fraction"):
        assert marker in section, f"ACNS_X05_INDETERMINATE_MARKER_MISSING: {marker!r}"


def test_no_coercion_rule_present() -> None:
    section = _section(_manual_text(), "INDETERMINATE rules")
    for marker in NO_COERCION_MARKERS:
        assert marker in section, f"ACNS_X05_NO_COERCION_MARKER_MISSING: {marker!r}"


def test_ambiguity_flag_couples_to_undecidable_fields() -> None:
    section = _section(_manual_text(), "INDETERMINATE rules")
    assert "C8" in section and "AMB" in section, "ACNS_X05_AMB_COUPLING_MISSING"


def test_indeterminate_not_a_doubt_escape_hatch() -> None:
    section = _section(_manual_text(), "Evidence-boundary codes")
    assert re.search(
        r"not a third verdict|reserved for claims whose text under-determines", section
    ), "ACNS_X05_INDETERMINATE_SCOPE_RULE_MISSING"


# ---------------------------------------------------------------------------
# Stable reason codes
# ---------------------------------------------------------------------------


def test_required_reason_codes_registered() -> None:
    section = _section(_manual_text(), "Stable reason codes")
    codes = set(re.findall(r"`([A-Z][A-Z_]{4,})`", section))
    for code in REQUIRED_REASON_CODES:
        assert code in codes, f"ACNS_X05_REASON_CODE_MISSING: {code}"


def test_reason_codes_table_has_condition_and_effect() -> None:
    section = _section(_manual_text(), "Stable reason codes")
    assert "Condition" in section and "Effect" in section, (
        "ACNS_X05_REASON_CODE_TABLE_INCOMPLETE"
    )


# ---------------------------------------------------------------------------
# Coding record schema
# ---------------------------------------------------------------------------


def test_coding_record_fields_present() -> None:
    text = _manual_text()
    for field in CODING_RECORD_FIELDS:
        assert f'"{field}"' in text, f"ACNS_X05_CODING_RECORD_FIELD_MISSING: {field}"


def test_coding_record_schema_id_declared() -> None:
    text = _manual_text()
    assert re.search(r"clara\.venue2027\.acns\.coding-record\.v1", text), (
        "ACNS_X05_CODING_RECORD_SCHEMA_ID_MISSING"
    )


# ---------------------------------------------------------------------------
# Inter-rater agreement protocol
# ---------------------------------------------------------------------------


def test_agreement_protocol_section_complete() -> None:
    section = _section(_manual_text(), "Inter-rater agreement protocol")
    for marker in AGREEMENT_MARKERS:
        assert marker in section, f"ACNS_X05_AGREEMENT_MARKER_MISSING: {marker!r}"


def test_pilot_design_and_freeze_rule_present() -> None:
    text = _manual_text()
    for marker in PILOT_MARKERS:
        assert marker in text, f"ACNS_X05_PILOT_MARKER_MISSING: {marker!r}"


def test_rater_independence_rules_present() -> None:
    text = _manual_text()
    for marker in INDEPENDENCE_MARKERS:
        assert marker.lower() in text.lower(), (
            f"ACNS_X05_RATER_INDEPENDENCE_MARKER_MISSING: {marker!r}"
        )


def test_blind_allocation_rule_present() -> None:
    section = _section(_manual_text(), "Blind allocation", level=3)
    assert "never see each other" in section or "never see" in section, (
        "ACNS_X05_BLIND_ALLOCATION_RULE_MISSING"
    )


def test_kappa_computed_on_pre_adjudication_stream() -> None:
    section = _section(_manual_text(), "Agreement statistics rules", level=3)
    assert "pre-adjudication" in section, "ACNS_X05_KAPPA_STREAM_RULE_MISSING"
    assert "raw coder records" in section, "ACNS_X05_KAPPA_RAW_RECORDS_RULE_MISSING"
    assert re.search(r"adjudicated labels are reported separately", section), (
        "ACNS_X05_ADJUDICATED_LABELS_SEPARATION_MISSING"
    )


def test_thresholds_delegated_not_restated() -> None:
    section = _section(_manual_text(), "Agreement statistics rules", level=3)
    assert "rq_and_estimands.yaml" in section, "ACNS_X05_THRESHOLD_DELEGATION_MISSING"
    assert "manifest.json" in section, "ACNS_X05_MANIFEST_DELEGATION_MISSING"


# ---------------------------------------------------------------------------
# No fabricated empirics: kappa/agreement values, rater names, run ids
# ---------------------------------------------------------------------------


def test_no_fabricated_kappa_values() -> None:
    text = _manual_text()
    match = FABRICATED_KAPPA_PATTERN.search(text)
    assert match is None, f"ACNS_X05_FABRICATED_KAPPA_VALUE: {match.group(0)!r}"
    match = FABRICATED_KAPPA_SYMBOL_PATTERN.search(text)
    assert match is None, f"ACNS_X05_FABRICATED_KAPPA_SYMBOL_VALUE: {match.group(0)!r}"


def test_no_fabricated_agreement_percentages() -> None:
    match = FABRICATED_AGREEMENT_PATTERN.search(_manual_text())
    assert match is None, f"ACNS_X05_FABRICATED_AGREEMENT_PERCENT: {match.group(0)!r}"


def test_no_invented_rater_or_reviewer_names() -> None:
    text = _manual_text()
    match = NAME_INTRO_PATTERN.search(text)
    assert match is None, f"ACNS_X05_INVENTED_RATER_NAME: {match.group(0)!r}"
    match = NAME_DECISION_PATTERN.search(text)
    assert match is None, f"ACNS_X05_INVENTED_NAME_ATTACHED_TO_CODING: {match.group(0)!r}"


def test_rater_roles_are_pseudonymous_only() -> None:
    text = _manual_text()
    for role in ROLE_TOKENS:
        assert re.search(rf"\b{role}\b", text), f"ACNS_X05_ROLE_TOKEN_MISSING: {role}"
    assert re.search(r"pseudonymous roles", text), "ACNS_X05_PSEUDONYMITY_RULE_MISSING"


def test_no_invented_run_ids() -> None:
    """Run identifiers are placeholders in the evidence path only, never invented."""
    text = _manual_text()
    for match in RUN_ID_PATTERN.finditer(text):
        snippet = match.group(0)
        assert "<run_id>" in snippet or "run_id" == snippet.strip().split()[-1], (
            f"ACNS_X05_INVENTED_RUN_ID: {snippet!r}"
        )


def test_execution_honesty_statement_present() -> None:
    text = _manual_text()
    assert NO_CODING_RUN_MARKER in text, "ACNS_X05_NO_CODING_RUN_STATEMENT_MISSING"
    assert "negative result" in text, "ACNS_X05_NEGATIVE_RESULT_DISCLOSURE_MISSING"


# ---------------------------------------------------------------------------
# Alignment with the frozen review protocol and RQ registry
# ---------------------------------------------------------------------------


def test_manual_references_frozen_protocol_sections() -> None:
    text = _manual_text()
    assert "sok_review_protocol.md" in text or "selection protocol" in text, (
        "ACNS_X05_PROTOCOL_REFERENCE_MISSING"
    )
    # The four BND codes must be introduced as fixed by the protocol rubric.
    assert re.search(r"§8\.2|8\.2", text), "ACNS_X05_PROTOCOL_RUBRIC_SECTION_UNREFERENCED"


def test_manual_consistent_with_protocol_bnd_set() -> None:
    protocol_codes = set(re.findall(r"`(BND_[A-Z_]+)`", _protocol_text()))
    manual_codes = {m.strip("`") for m in BND_CODE_PATTERN.findall(_manual_text())}
    assert protocol_codes.issubset(manual_codes), (
        f"ACNS_X05_PROTOCOL_BND_CODES_NOT_COVERED: {sorted(protocol_codes)}"
    )


def test_thresholds_exist_upstream_in_rq_registry() -> None:
    """The delegated authority must actually contain the registered RQ3 rules."""
    assert RQ_REGISTRY_PATH.is_file(), f"rq registry missing: {RQ_REGISTRY_PATH}"
    rq_text = RQ_REGISTRY_PATH.read_text(encoding="utf-8")
    assert "kappa" in rq_text.lower(), "ACNS_X05_RQ_REGISTRY_KAPPA_RULES_ABSENT"
    assert "bootstrap" in rq_text.lower(), "ACNS_X05_RQ_REGISTRY_BOOTSTRAP_ABSENT"


def test_coding_dimensions_cover_all_protocol_fields() -> None:
    """The protocol's C2-C7 coding fields are all mapped into the manual."""
    protocol = _protocol_text()
    coding_section = _section(protocol, "Coding scheme")
    protocol_dims = set(re.findall(r"\*\*(C[1-8])\s", coding_section))
    assert protocol_dims >= {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"}, (
        f"ACNS_X05_PROTOCOL_DIMENSION_SET_UNEXPECTED: {sorted(protocol_dims)}"
    )
