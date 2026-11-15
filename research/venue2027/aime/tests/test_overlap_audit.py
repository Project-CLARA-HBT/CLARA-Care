"""Structural test for the AIME-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/aime/overlap_audit.md`` satisfies the
P01 anti-salami gate: all eight sibling venues named, the historical
GLHS/GovRed/GovMut/CareGuard/HEALTHINF comparators named, the AIME-HEALTHINF
contrast (clinical task quality vs governance protocol) made explicit, an
artifact-reuse table with no reused raw case IDs/labels/figures/endpoints, an
explicit refusal to reuse frozen E15-E22 outcomes as new independent evidence,
the mandatory synthetic-only / no-clinical-efficacy language, and exactly one
final ``Decision: PASS`` line. The real shared validator
(``_shared/tools/overlap_contract.py``) must accept the audit, and four derived
mutants (missing sibling, missing historical comparator, missing frozen
refusal, missing decision) must each be rejected with the corresponding reason
code. The executable ``_shared/tools/claim_overlap.py`` check runs against
``_shared/study_claims.json`` and asserts the aime entry does not share
question+endpoint with any other venue and reuses no archived evidence.

Allowed input
-------------
Read-only access to the audit markdown, the shared claims registry and the two
shared tools. No network, no database, no writes outside tmp_path.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing element; no silent
passes. Stdlib-only besides pytest itself.

Version
-------
``aime-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "aime-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "aime" / "overlap_audit.md"
CLAIMS_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "study_claims.json"
OVERLAP_CONTRACT_PATH = (
    REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "overlap_contract.py"
)
CLAIM_OVERLAP_TOOL_PATH = (
    REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "claim_overlap.py"
)

VENUE = "aime"

EIGHT_SIBLINGS: tuple[str, ...] = (
    "compsac",
    "popets",
    "ifip_sec",
    "sacmat",
    "acns",
    "dsn",
    "dimva",
    "pst",
)

HISTORICAL_COMPARATORS: tuple[str, ...] = (
    "GLHS",
    "GovRed",
    "GovMut",
    "CareGuard",
    "HEALTHINF",
)

# The refusal must be explicit, unambiguous, and state non-reuse as new
# independent evidence.
REFUSAL_SENTENCE_PATTERN = re.compile(
    r"frozen\s+E15[–-]E22\s+outcomes?[^\n]*are\s+NOT\s+reused\s+as\s+new\s+"
    r"independent\s+evidence",
    re.IGNORECASE,
)

DECISION_PATTERN = re.compile(r"^Decision:\s*PASS\s*$", re.MULTILINE)

AIME_ENDPOINT = "unsafe clinical action rate under consent/medication history changes"


def _load_audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _load_overlap_contract():
    return _load_module("overlap_contract", OVERLAP_CONTRACT_PATH)


def _load_claim_overlap_module():
    return _load_module("claim_overlap", CLAIM_OVERLAP_TOOL_PATH)


def _drop_lines_containing(text: str, *needles: str) -> str:
    lowered = tuple(n.lower() for n in needles)
    return "\n".join(
        line for line in text.splitlines() if not any(n in line.lower() for n in lowered)
    )


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("aime-overlap-audit-test-")


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


# --------------------------------------------------------------------------
# Shared overlap_contract validator: the real document passes, mutants fail.
# --------------------------------------------------------------------------


def test_shared_validator_accepts_real_audit() -> None:
    module = _load_overlap_contract()
    result = module.audit_overlap_document(_load_audit_text(), venue=VENUE)
    assert result.ok, f"validator rejected real audit: {result.to_dict()}"
    assert result.reason_codes == (), f"unexpected reason codes: {result.reason_codes}"
    assert result.missing_venues == (), f"missing venues: {result.missing_venues}"
    assert result.missing_historical == (), f"missing historical: {result.missing_historical}"
    assert result.has_frozen_refusal is True
    assert result.has_decision is True
    assert module.OVERLAP_AUDIT_VERSION == "1.0.0"


def test_mutant_missing_sibling_venue_fails() -> None:
    module = _load_overlap_contract()
    mutant = _drop_lines_containing(_load_audit_text(), "dimva")
    assert "dimva" not in mutant.lower(), "mutant still names dimva"
    result = module.audit_overlap_document(mutant, venue=VENUE)
    assert not result.ok, "validator accepted an audit missing a sibling venue"
    assert result.reason_codes == ("MISSING_SIBLING_VENUE",), result.to_dict()
    assert result.missing_venues == ("dimva",), result.to_dict()


def test_mutant_missing_historical_comparison_fails() -> None:
    module = _load_overlap_contract()
    mutant = _drop_lines_containing(_load_audit_text(), "careguard")
    assert "careguard" not in mutant.lower(), "mutant still names CareGuard"
    result = module.audit_overlap_document(mutant, venue=VENUE)
    assert not result.ok, "validator accepted an audit missing a historical comparator"
    assert result.reason_codes == ("MISSING_HISTORICAL_COMPARISON",), result.to_dict()
    assert result.missing_historical == ("careguard",), result.to_dict()


def test_mutant_missing_frozen_refusal_fails() -> None:
    module = _load_overlap_contract()
    mutant = _drop_lines_containing(_load_audit_text(), "e15", "e22")
    lowered = mutant.lower()
    assert not any(marker in lowered for marker in module.FROZEN_MARKERS), (
        "mutant still carries an E15-E22 marker"
    )
    result = module.audit_overlap_document(mutant, venue=VENUE)
    assert not result.ok, "validator accepted an audit without the frozen-evidence refusal"
    assert result.reason_codes == ("MISSING_FROZEN_REFUSAL",), result.to_dict()
    assert result.has_frozen_refusal is False


def test_mutant_missing_decision_fails() -> None:
    module = _load_overlap_contract()
    mutant = _drop_lines_containing(_load_audit_text(), "decision: pass")
    result = module.audit_overlap_document(mutant, venue=VENUE)
    assert not result.ok, "validator accepted an audit without a Decision line"
    assert result.reason_codes == ("MISSING_DECISION",), result.to_dict()
    assert result.has_decision is False


def test_mutant_combined_reports_all_reason_codes() -> None:
    module = _load_overlap_contract()
    text = _load_audit_text()
    combined = _drop_lines_containing(text, "dimva", "careguard", "e15", "e22", "decision: pass")
    result = module.audit_overlap_document(combined, venue=VENUE)
    assert not result.ok
    assert set(result.reason_codes) == {
        "MISSING_SIBLING_VENUE",
        "MISSING_HISTORICAL_COMPARISON",
        "MISSING_FROZEN_REFUSAL",
        "MISSING_DECISION",
    }, result.to_dict()


# --------------------------------------------------------------------------
# Document structure beyond the validator's minimum.
# --------------------------------------------------------------------------


def test_all_eight_sibling_venues_named() -> None:
    text = _load_audit_text()
    for venue in EIGHT_SIBLINGS:
        assert venue in text.lower(), f"2027 sibling venue not named in audit: {venue}"


def test_historical_comparators_named() -> None:
    text = _load_audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"


def test_aime_healthinf_contrast_present() -> None:
    text = _load_audit_text()
    assert "governance protocol" in text, "HEALTHINF governance-protocol side missing"
    assert "clinical task quality" in text, "AIME clinical-task-quality side missing"
    assert "refuses the merge" in text, "explicit refusal of the AIME-HEALTHINF merge missing"
    assert "five-part distinction test" in text, "five-part distinction test not invoked"
    # The contrast must be on question, endpoint, and evidence.
    for dimension in ("question", "endpoint", "evidence"):
        assert dimension in text.lower(), f"AIME-HEALTHINF contrast omits {dimension}"


def test_artifact_reuse_table_present() -> None:
    text = _load_audit_text()
    assert "Artifact reuse table" in text, "artifact-reuse table section missing"
    assert "reuses_archive: []" in text, "empty reuses_archive declaration missing"
    assert "No manuscript section text" in text, "no-reuse closing statement missing"
    for column in ("Raw case IDs reused?", "Labels reused?", "Figures reused?", "Endpoint shared?"):
        assert column in text, f"artifact-reuse table column missing: {column}"


def test_e15_e22_refusal_sentence_present() -> None:
    text = _load_audit_text()
    assert REFUSAL_SENTENCE_PATTERN.search(text), (
        "explicit 'frozen E15–E22 outcomes are NOT reused as new independent "
        "evidence' refusal sentence missing from audit"
    )


def test_exactly_one_decision_line_and_it_is_pass() -> None:
    text = _load_audit_text()
    decisions = DECISION_PATTERN.findall(text)
    assert len(decisions) == 1, f"expected exactly one 'Decision: PASS' line, found {decisions}"
    match = DECISION_PATTERN.search(text)
    assert match is not None
    tail = text[match.end() :]
    assert "Justification" in tail, "Decision lacks a justification block"
    # No contradicting verdict line may follow or precede it.
    assert not re.search(r"^\s*Decision:\s*(NO-GO|MERGE-ALTERNATIVE)\s*$", text, re.MULTILINE), (
        "a second, contradicting Decision line exists"
    )


def test_synthetic_only_and_no_clinical_efficacy_language() -> None:
    text = _load_audit_text()
    lowered = text.lower()
    assert "synthetic vignettes only" in lowered, "synthetic-only language missing"
    assert "no real phi" in lowered, "no-real-PHI language missing"
    assert "synthetic action correctness is not clinical efficacy" in lowered, (
        "no-clinical-efficacy statement missing"
    )
    assert "no clinical efficacy claim" in lowered, "efficacy-claim refusal missing"
    assert "blinded independent clinician review" in lowered, "blinded-review requirement missing"
    # Hard negative: the audit must not contain efficacy-style claim language.
    for forbidden in ("clinically effective", "proves clinical efficacy"):
        assert forbidden not in lowered, f"forbidden phrase present: {forbidden}"
    # No invented empirical numbers: no percentage or p-value style results.
    assert not re.search(r"\b\d+(\.\d+)?%", text), "percentage-style number found in audit"
    assert not re.search(r"\bp\s*[<>=]", text, flags=re.IGNORECASE), "p-value style number found"


# --------------------------------------------------------------------------
# Executable claim_overlap check against the shared registry.
# --------------------------------------------------------------------------


def test_executable_claim_overlap_passes_for_aime() -> None:
    """Run the real shared tool: aime shares no question+endpoint with any venue."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    findings = module.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    aime_findings = [
        f
        for f in findings.findings
        if "aime" in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert not aime_findings, f"aime overlap findings: {[f.to_dict() for f in aime_findings]}"
    aime_claims = [c for c in claims if c.study == "aime"]
    assert len(aime_claims) == 1, "aime must appear exactly once in study_claims.json"
    aime_claim = aime_claims[0]
    assert aime_claim.reuses_archive == (), (
        f"aime must not reuse archived evidence: {aime_claim.reuses_archive}"
    )
    endpoint = module._normalize(aime_claim.primary_endpoint)
    holders = [c.study for c in claims if module._normalize(c.primary_endpoint) == endpoint]
    assert holders == ["aime"], f"primary endpoint '{AIME_ENDPOINT}' also claimed by: {holders}"
    question = module._normalize(aime_claim.research_question)
    q_holders = [c.study for c in claims if module._normalize(c.research_question) == question]
    assert q_holders == ["aime"], f"research question also claimed by: {q_holders}"
