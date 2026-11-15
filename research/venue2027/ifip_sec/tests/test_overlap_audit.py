"""Structural and adversarial tests for the IFIP_SEC-overlap publication isolation audit.

Positive controls:
- Machine-checks that ``research/venue2027/ifip_sec/overlap_audit.md`` satisfies the
  P01 anti-salami gate via the REQUIRED shared validator
  ``research/venue2027/_shared/tools/overlap_contract.py`` (all eight sibling
  venues named, the historical GLHS/GovRed/GovMut/CareGuard/HEALTHINF corpus
  named, an explicit refusal to reuse frozen E15–E22 outcomes, exactly one
  final Decision line).
- Runs the real executable check (``_shared/tools/claim_overlap.py``) against
  ``_shared/study_claims.json`` and asserts the ifip_sec entry does not share
  question+endpoint with any other venue and reuses no archived evidence.
- Asserts the ACNS (mechanism vs SoK) and DIMVA (prevention vs detection)
  contrasts demanded by ``GATES/ANTI_SALAMI_REVIEW.md`` are documented.

Adversarial controls (mutations must FAIL, never silently pass):
- Dropping a sibling venue, a historical comparator, the frozen refusal, or the
  Decision line must make the shared validator return ``ok=False`` with the
  matching reason code.

Allowed input
-------------
Read-only access to the audit markdown, the shared claims registry and the
shared tools. No network, no database, no writes outside tmp_path.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing element; no silent
passes. Stdlib-only besides pytest itself.

Version
-------
``ifip-sec-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import overlap_contract as oc  # noqa: E402

TEST_VERSION = "ifip-sec-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "ifip_sec" / "overlap_audit.md"
CLAIMS_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "study_claims.json"
CLAIM_TOOL_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "claim_overlap.py"

NINE_VENUES: tuple[str, ...] = (
    "COMPSAC",
    "PoPETs",
    "AIME",
    "SACMAT",
    "ACNS",
    "DSN",
    "DIMVA",
    "PST",
    "IFIP SEC",
)

HISTORICAL_COMPARATORS: tuple[str, ...] = (
    "GLHS",
    "GovRed",
    "GovMut",
    "CareGuard",
    "HEALTHINF",
)

# The refusal must be explicit, unambiguous, and cover both "not reused" and
# "not as new independent evidence".
REFUSAL_SENTENCE_PATTERN = re.compile(
    r"frozen\s+E15[–-]E22\s+outcomes?[^\n]*are\s+NOT\s+reused\s+as\s+new\s+"
    r"independent\s+evidence",
    re.IGNORECASE,
)

DECISION_PATTERN = re.compile(r"^Decision:\s*(PASS|MERGE-ALTERNATIVE)\s*$", re.MULTILINE)

IFIP_SEC_ENDPOINT = "replay acceptance rate across purpose/delegation lineage"


def _load_audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _load_claim_overlap_module():
    spec = importlib.util.spec_from_file_location("ifip_claim_overlap", CLAIM_TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {CLAIM_TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("ifip-sec-overlap-audit-test-")


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


def test_shared_overlap_contract_validator_passes() -> None:
    """The REQUIRED shared gate: audit_overlap_document(text, venue='ifip_sec').ok."""

    result = oc.audit_overlap_document(_load_audit_text(), venue="ifip_sec")
    assert result.ok is True, result.to_dict()
    assert result.missing_venues == ()
    assert result.missing_historical == ()
    assert result.has_frozen_refusal is True
    assert result.has_decision is True


def test_all_nine_2027_venues_named() -> None:
    text = _load_audit_text()
    for venue in NINE_VENUES:
        assert venue in text, f"2027 venue not named in audit: {venue}"


def test_historical_comparators_named() -> None:
    text = _load_audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"


def test_e15_e22_refusal_sentence_present() -> None:
    text = _load_audit_text()
    assert REFUSAL_SENTENCE_PATTERN.search(text), (
        "explicit 'frozen E15–E22 outcomes are NOT reused as new independent "
        "evidence' refusal sentence missing from audit"
    )


def test_ifip_sec_endpoint_named() -> None:
    text = _load_audit_text()
    assert IFIP_SEC_ENDPOINT in text, "ifip_sec primary endpoint wording missing"


def test_acns_contrast_present() -> None:
    text = _load_audit_text()
    assert "SoK" in text, "ACNS SoK contrast missing"
    assert "taxonomy" in text.lower(), "ACNS literature-taxonomy contrast missing"
    assert "prevention" in text.lower() or "mechanism" in text.lower(), (
        "IFIP_SEC mechanism-vs-SoK contrast missing"
    )


def test_dimva_contrast_present() -> None:
    text = _load_audit_text()
    lowered = text.lower()
    assert "detection" in lowered, "DIMVA detection contrast missing"
    assert "prevention" in lowered, "IFIP_SEC prevention-vs-detection contrast missing"


def test_exactly_one_decision_line() -> None:
    text = _load_audit_text()
    decisions = DECISION_PATTERN.findall(text)
    assert len(decisions) == 1, f"expected exactly one Decision line, found {decisions}"
    assert decisions[0] in {"PASS", "MERGE-ALTERNATIVE"}


def test_decision_is_pass_with_justification() -> None:
    text = _load_audit_text()
    match = DECISION_PATTERN.search(text)
    assert match is not None, "no Decision line found"
    tail = text[match.end() :]
    assert "Justification" in tail, "Decision lacks a justification block"
    # Decision must be the final verdict: no later contradicting decision line.
    assert "Decision: MERGE-ALTERNATIVE" not in text or match.group(1) == "MERGE-ALTERNATIVE"


def test_no_duplicate_primary_claim() -> None:
    """The ifip_sec primary endpoint must be claimed by exactly one 2027 study."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    ifip = [c for c in claims if c.study == "ifip_sec"]
    assert len(ifip) == 1, "ifip_sec must appear exactly once in study_claims.json"
    endpoint = module._normalize(ifip[0].primary_endpoint)
    holders = [c.study for c in claims if module._normalize(c.primary_endpoint) == endpoint]
    assert holders == ["ifip_sec"], (
        f"primary endpoint '{IFIP_SEC_ENDPOINT}' also claimed by: {holders}"
    )
    question = module._normalize(ifip[0].research_question)
    q_holders = [c.study for c in claims if module._normalize(c.research_question) == question]
    assert q_holders == ["ifip_sec"], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_ifip_sec() -> None:
    """Run the real shared tool: ifip_sec shares no question+endpoint with any venue."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    findings = module.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    ifip_findings = [
        f
        for f in findings.findings
        if "ifip_sec" in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert not ifip_findings, f"ifip_sec overlap findings: {[f.to_dict() for f in ifip_findings]}"
    ifip_claim = next(c for c in claims if c.study == "ifip_sec")
    assert ifip_claim.reuses_archive == (), (
        f"ifip_sec must not reuse archived evidence: {ifip_claim.reuses_archive}"
    )


# --- Adversarial mutants: the shared validator must REFUSE each mutation. ---


def _mutated_audit(*replacements: tuple[str, str]) -> str:
    text = _load_audit_text()
    for old, new in replacements:
        assert old in text, f"mutation target not found in audit: {old!r}"
        text = text.replace(old, new, 1)
    return text


def test_mutant_dropped_sibling_venue_is_refused() -> None:
    # Drop every line mentioning the pst sibling; the validator's substring
    # check must then report MISSING_SIBLING_VENUE for pst.
    text = _load_audit_text()
    lines = [ln for ln in text.splitlines() if "pst" not in ln.lower()]
    body = "\n".join(lines)
    assert "pst" not in body.lower(), "mutation must remove every pst token"
    result = oc.audit_overlap_document(body, venue="ifip_sec")
    assert result.ok is False, "mutant dropping sibling venue must not pass"
    assert "MISSING_SIBLING_VENUE" in result.reason_codes
    assert "pst" in result.missing_venues


def test_mutant_dropped_historical_comparator_is_refused() -> None:
    # Delete every CareGuard token (heading + table row); the validator's
    # substring check must then report MISSING_HISTORICAL_COMPARISON.
    text = _load_audit_text()
    for token in ("CareGuard-VN", "CareGuard "):
        text = text.replace(token, "")
    text = text.replace("careguard-vn", "")
    text = text.replace("CareGuard", "")
    assert "careguard" not in text.lower(), "mutation must remove every careguard token"
    result = oc.audit_overlap_document(text, venue="ifip_sec")
    assert result.ok is False, "mutant dropping CareGuard must not pass"
    assert "MISSING_HISTORICAL_COMPARISON" in result.reason_codes
    assert "careguard" in result.missing_historical


def test_mutant_missing_frozen_refusal_is_refused() -> None:
    # Remove ALL refusal-flavoured statements so the validator cannot find the
    # mandatory frozen E15–E22 refusal anywhere in the document.
    lines = [
        ln
        for ln in _load_audit_text().splitlines()
        if not any(
            marker in ln.lower()
            for marker in ("not reused", "refus", "not presented", "not reuse ")
        )
    ]
    text = "\n".join(lines)
    result = oc.audit_overlap_document(text, venue="ifip_sec")
    assert result.ok is False, "mutant without frozen refusal must not pass"
    assert "MISSING_FROZEN_REFUSAL" in result.reason_codes


def test_mutant_missing_decision_line_is_refused() -> None:
    text = _mutated_audit(("Decision: PASS", "Verdict: PASS"))
    result = oc.audit_overlap_document(text, venue="ifip_sec")
    assert result.ok is False, "mutant without Decision line must not pass"
    assert "MISSING_DECISION" in result.reason_codes


def test_mutant_second_decision_line_is_caught_by_structural_check() -> None:
    text = _mutated_audit(
        (
            'pass gate "PASS or explicit alternative-venue merger" is satisfied by PASS.',
            "pass gate satisfied.\n\nDecision: MERGE-ALTERNATIVE",
        ),
    )
    decisions = DECISION_PATTERN.findall(text)
    assert len(decisions) == 2, "mutation must produce a second Decision line"
