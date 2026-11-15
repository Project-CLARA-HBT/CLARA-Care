"""Structural test for the ACNS-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/acns/overlap_audit.md`` satisfies the
P01 anti-salami gate via the SHARED validator
(``_shared/tools/overlap_contract.py``): all eight sibling 2027 venues named,
the historical GLHS/GovRed/GovMut/CareGuard/HEALTHINF comparators named, an
explicit refusal to reuse frozen E15–E22 outcomes as new independent evidence,
and exactly one final ``Decision: PASS`` line. Also asserts the SoK framing
(no new-mechanism claim), the IFIP SEC mechanism-vs-SoK and DIMVA
detection-vs-mapping contrasts, the artifact reuse table, and runs the real
executable check (``_shared/tools/claim_overlap.py``) against
``_shared/study_claims.json`` — the acns entry shares no question+endpoint
with any other venue and reuses no archived evidence. Mutant documents
(sibling dropped, refusal dropped, decision moved) must FAIL the shared
validator, so the test cannot pass on a gutted audit.

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
``clara.venue2027.acns.test-overlap-audit.v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "clara.venue2027.acns.test-overlap-audit-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import overlap_contract as oc  # noqa: E402

AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "overlap_audit.md"
CLAIMS_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "study_claims.json"
CLAIM_TOOL_PATH = TOOLS / "claim_overlap.py"

SIBLING_VENUES: tuple[str, ...] = (
    "COMPSAC",
    "PoPETs",
    "AIME",
    "IFIP SEC",
    "SACMAT",
    "DSN",
    "DIMVA",
    "PST",
)

HISTORICAL_COMPARATORS: tuple[str, ...] = (
    "GLHS",
    "GovRed",
    "GovMut",
    "CareGuard",
    "HEALTHINF",
)

REFUSAL_SENTENCE_PATTERN = re.compile(
    r"frozen\s+E15[–-]E22\s+outcomes?[^\n]*are\s+NOT\s+reused\s+as\s+new\s+"
    r"independent\s+evidence",
    re.IGNORECASE,
)

DECISION_PATTERN = re.compile(r"^Decision:\s*(PASS|MERGE-ALTERNATIVE)\s*$", re.MULTILINE)

ACNS_ENDPOINT = "evidence-boundary coverage matrix"

SOK_MARKERS = ("Systematization of Knowledge", "SoK")
NO_NEW_MECHANISM_MARKERS = (
    "no new mechanism",
    "proposes no mechanism",
    "explicitly *no new mechanism*",
)
CONTRAST_MARKERS = {
    "ifip_sec": ("mechanism vs SoK", "replay acceptance rate"),
    "dimva": ("detection", "PR-AUC"),
}


def _audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _load_claim_overlap_module():
    spec = importlib.util.spec_from_file_location("acns_claim_overlap", CLAIM_TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {CLAIM_TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _validate(text: str):
    return oc.audit_overlap_document(text, venue="acns")


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("clara.venue2027.acns.test-overlap-audit-")


def test_shared_validator_version() -> None:
    assert oc.OVERLAP_AUDIT_VERSION == "1.0.0"


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


def test_real_validator_passes_on_audit() -> None:
    result = _validate(_audit_text())
    assert result.ok is True, f"shared validator failed: {result.to_dict()}"
    assert result.reason_codes == ()
    assert result.missing_venues == ()
    assert result.missing_historical == ()
    assert result.has_frozen_refusal is True
    assert result.has_decision is True


def _mutant(text: str, *, drop: str) -> str:
    """Remove every line mentioning ``drop`` (case-insensitive).

    The shared validator matches case-insensitive substrings, so a mutant must
    purge all occurrences of a marker, not just the first one, to simulate a
    genuinely gutted audit.
    """

    lines = [line for line in text.splitlines(keepends=True) if drop.lower() not in line.lower()]
    mutant = "".join(lines)
    assert drop.lower() not in mutant.lower(), f"mutant anchor not purged: {drop!r}"
    return mutant


def test_mutant_missing_sibling_fails_validator() -> None:
    text = _audit_text()
    for sibling in ("DIMVA", "PST", "SACMAT"):
        mutant = _mutant(text, drop=sibling)
        result = _validate(mutant)
        assert result.ok is False, f"gutted audit (no {sibling}) must not pass"
        assert "MISSING_SIBLING_VENUE" in result.reason_codes


def test_mutant_missing_historical_fails_validator() -> None:
    mutant = _mutant(_audit_text(), drop="CareGuard")
    result = _validate(mutant)
    assert result.ok is False, "gutted audit (no CareGuard) must not pass"
    assert "MISSING_HISTORICAL_COMPARISON" in result.reason_codes


def test_mutant_missing_frozen_refusal_fails_validator() -> None:
    """An audit that never mentions the frozen archive must fail the gate.

    The refusal phrase is spread across wrapped lines, so the faithful mutant
    purges every line carrying an E15/E22 marker, leaving no frozen marker for
    the validator's refusal check to bind to.
    """

    text = _audit_text()
    lines = [
        line
        for line in text.splitlines(keepends=True)
        if "e15" not in line.lower() and "e22" not in line.lower()
    ]
    mutant = "".join(lines)
    assert (
        "e15" not in mutant.lower() and "e22" not in mutant.lower()
    ), "mutant must contain no E15/E22 marker at all"
    result = _validate(mutant)
    assert result.ok is False, "gutted audit (no E15-E22 refusal) must not pass"
    assert "MISSING_FROZEN_REFUSAL" in result.reason_codes


def test_mutant_missing_decision_fails_validator() -> None:
    mutant = _mutant(_audit_text(), drop="Decision: PASS")
    result = _validate(mutant)
    assert result.ok is False, "gutted audit (no decision) must not pass"
    assert "MISSING_DECISION" in result.reason_codes


def test_all_eight_sibling_venues_named() -> None:
    text = _audit_text()
    for venue in SIBLING_VENUES:
        assert venue in text, f"2027 sibling venue not named in audit: {venue}"


def test_all_historical_comparators_named() -> None:
    text = _audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"


def test_e15_e22_refusal_sentence_present() -> None:
    text = _audit_text()
    assert REFUSAL_SENTENCE_PATTERN.search(text), (
        "explicit 'frozen E15–E22 outcomes are NOT reused as new independent "
        "evidence' refusal sentence missing from audit"
    )


def test_acns_endpoint_named() -> None:
    text = _audit_text()
    assert ACNS_ENDPOINT in text, "acns primary endpoint wording missing"


def test_sok_framing_no_new_mechanism_claim() -> None:
    """The audit must frame ACNS as a SoK, never as a new mechanism."""

    text = _audit_text()
    for marker in SOK_MARKERS:
        assert marker in text, f"SoK framing marker missing: {marker!r}"
    lower = text.lower()
    assert any(
        marker.lower() in lower for marker in NO_NEW_MECHANISM_MARKERS
    ), "audit must explicitly disclaim a new-mechanism contribution"
    assert (
        "falsification instrument" in lower or "falsification instruments" in lower
    ), "witnesses must be framed as falsification instruments, not defenses"
    for forbidden in ("novel mechanism", "we propose a new mechanism", "new detector"):
        assert forbidden not in lower, f"audit must not claim: {forbidden!r}"


def test_ifip_sec_and_dimva_contrasts_present() -> None:
    text = _audit_text()
    lower = text.lower()
    assert "mechanism vs sok" in lower, "IFIP SEC mechanism-vs-SoK contrast missing"
    assert "replay acceptance rate" in lower, "IFIP SEC endpoint not named in contrast"
    for marker in CONTRAST_MARKERS["dimva"]:
        assert marker.lower() in lower, f"DIMVA detection contrast marker missing: {marker!r}"


def test_artifact_reuse_table_present() -> None:
    text = _audit_text()
    assert "Artifact reuse table" in text, "artifact reuse table section missing"
    for column in ("Raw case IDs reused?", "Labels reused?", "Figures reused?", "Endpoint shared?"):
        assert column in text, f"artifact reuse table column missing: {column}"
    assert "reuses_archive: []" in text, "reuses_archive declaration missing"


def test_exactly_one_decision_line() -> None:
    text = _audit_text()
    decisions = DECISION_PATTERN.findall(text)
    assert len(decisions) == 1, f"expected exactly one Decision line, found {decisions}"
    assert decisions == ["PASS"], f"ACNS-overlap must decide PASS, found {decisions}"


def test_decision_is_final_verdict_with_justification() -> None:
    text = _audit_text()
    matches = list(DECISION_PATTERN.finditer(text))
    assert len(matches) == 1, "exactly one Decision line required"
    tail = text[matches[0].end() :]
    assert "Justification" in tail, "Decision lacks a justification block"
    assert DECISION_PATTERN.search(tail) is None, "a later decision line overrides the verdict"


def test_no_duplicate_primary_claim() -> None:
    """The acns primary endpoint must be claimed by exactly one 2027 study."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    acns = [c for c in claims if c.study == "acns"]
    assert len(acns) == 1, "acns must appear exactly once in study_claims.json"
    endpoint = module._normalize(acns[0].primary_endpoint)
    holders = [c.study for c in claims if module._normalize(c.primary_endpoint) == endpoint]
    assert holders == ["acns"], f"primary endpoint '{ACNS_ENDPOINT}' also claimed by: {holders}"
    question = module._normalize(acns[0].research_question)
    q_holders = [c.study for c in claims if module._normalize(c.research_question) == question]
    assert q_holders == ["acns"], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_acns() -> None:
    """Run the real shared tool: acns shares no question+endpoint with any venue."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    assert len(claims) == 9, "study_claims.json must declare all nine 2027 venues"
    findings = module.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    acns_findings = [
        f
        for f in findings.findings
        if "acns" in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert not acns_findings, f"acns overlap findings: {[f.to_dict() for f in acns_findings]}"
    acns_claim = next(c for c in claims if c.study == "acns")
    assert (
        acns_claim.reuses_archive == ()
    ), f"acns must not reuse archived evidence: {acns_claim.reuses_archive}"
