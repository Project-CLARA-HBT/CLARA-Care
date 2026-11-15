"""Structural tests for the SACMAT-overlap publication isolation audit.

Purpose
-------
Gate ``research/venue2027/sacmat/overlap_audit.md`` through the SHARED validator
``research/venue2027/_shared/tools/overlap_contract.py`` (``OVERLAP_AUDIT_VERSION
1.0.0``): the real audit must pass, and adversarial mutants (sibling venue
dropped, historical comparator dropped, frozen E15–E22 refusal dropped, decision
line dropped) must each fail with their stable reason codes — the test suite
cannot pass on a gutted audit. Also asserts the SACMAT-specific content: all
eight sibling 2027 venues, the GLHS/GovRed/GovMut/CareGuard/HEALTHINF
comparators, the artifact reuse table, the SACMAT–GovMut contrast
(authorization semantics vs mutation-testing adequacy), and the executable
``_shared/tools/claim_overlap.py`` check that the sacmat entry shares no
question+endpoint pair with any other venue and reuses no archived evidence.

Allowed input
-------------
Read-only access to the audit markdown, the shared claims registry and the two
shared tools. No network, no database, no writes outside ``tmp_path``.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing element; no silent
passes. Stdlib-only besides pytest itself.

Version
-------
``clara.venue2027.sacmat.test-overlap-audit.v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "clara.venue2027.sacmat.test-overlap-audit-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SHARED = REPO_ROOT / "research" / "venue2027" / "_shared"
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "sacmat" / "overlap_audit.md"
CLAIMS_PATH = SHARED / "study_claims.json"
OVERLAP_TOOL_PATH = SHARED / "tools" / "overlap_contract.py"
CLAIM_TOOL_PATH = SHARED / "tools" / "claim_overlap.py"

VENUE = "sacmat"

SIBLING_VENUES: tuple[str, ...] = (
    "compsac",
    "popets",
    "aime",
    "ifip_sec",
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

SACMAT_ENDPOINT = "delegation conformance divergence detection rate"

GOVMUT_CONTRAST_MARKERS: tuple[str, ...] = (
    "authorization semantics vs mutation-testing adequacy",
    "w8 45-mutant",
    "unit of analysis",
    "direction of inference",
    "no corpus transfer",
)

IFIP_DIMVA_CONTRAST_MARKERS: tuple[str, ...] = (
    "replay acceptance rate",
    "probing detection auc",
)


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


def _audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _validate(text: str):
    oc = _load_module("sacmat_overlap_contract", OVERLAP_TOOL_PATH)
    return oc.audit_overlap_document(text, venue=VENUE)


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("clara.venue2027.sacmat.test-overlap-audit-")


def test_shared_validator_version() -> None:
    oc = _load_module("sacmat_overlap_contract_version", OVERLAP_TOOL_PATH)
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
    for sibling in ("DIMVA", "PST", "AIME"):
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
    assert "e15" not in mutant.lower() and "e22" not in mutant.lower(), (
        "mutant must contain no E15/E22 marker at all"
    )
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
        assert venue in text.lower(), f"2027 sibling venue not named in audit: {venue}"


def test_all_historical_comparators_named() -> None:
    text = _audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"


def test_sacmat_endpoint_named() -> None:
    text = _audit_text()
    assert SACMAT_ENDPOINT in text, "sacmat primary endpoint wording missing"


def test_frozen_refusal_sentence_present() -> None:
    text = _audit_text()
    assert re.search(
        r"frozen\s+E15[–-]E22\s+outcomes?[^\n]*are\s+NOT\s+reused\s+as\s+new\s+"
        r"independent\s+evidence",
        text,
        re.IGNORECASE,
    ), (
        "explicit 'frozen E15–E22 outcomes are NOT reused as new independent evidence' refusal missing"
    )


def test_govmut_contrast_present() -> None:
    """The declared SACMAT–GovMut anti-salami pair must be explicitly resolved."""

    text = _audit_text().lower()
    for marker in GOVMUT_CONTRAST_MARKERS:
        assert marker in text, f"SACMAT–GovMut contrast marker missing: {marker!r}"
    assert "never an input, baseline, or comparandum" in text or (
        "not inputs, baselines, or comparanda" in text
    ), "W8 corpus exclusion statement missing"


def test_ifip_and_dimva_contrasts_present() -> None:
    text = _audit_text().lower()
    assert "prevention" in text, "IFIP SEC prevention contrast missing"
    assert "detection" in text, "DIMVA detection contrast missing"
    for marker in IFIP_DIMVA_CONTRAST_MARKERS:
        assert marker in text, f"IFIP/DIMVA endpoint marker missing: {marker!r}"


def test_artifact_reuse_table_present() -> None:
    text = _audit_text()
    assert "Artifact reuse table" in text, "artifact reuse table section missing"
    for column in ("Raw case IDs reused?", "Labels reused?", "Figures reused?", "Endpoint shared?"):
        assert column in text, f"artifact reuse table column missing: {column}"
    assert "reuses_archive: []" in text, "reuses_archive declaration missing"


def test_exactly_one_decision_line() -> None:
    text = _audit_text()
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("Decision:")]
    assert len(lines) == 1, f"expected exactly one Decision line, found: {lines}"
    assert lines[0].strip() == "Decision: PASS", lines[0]


def test_decision_is_final_verdict_with_justification() -> None:
    text = _audit_text()
    matches = list(re.finditer(r"^\s*Decision:\s*(PASS|MERGE-ALTERNATIVE)\s*$", text, re.MULTILINE))
    assert len(matches) == 1, "exactly one Decision line required"
    tail = text[matches[0].end() :]
    assert "Justification" in tail, "Decision lacks a justification block"
    assert not re.search(r"^\s*Decision:\s*(PASS|MERGE-ALTERNATIVE)\s*$", tail, re.MULTILINE), (
        "a later decision line overrides the verdict"
    )


def test_no_duplicate_primary_claim() -> None:
    """The sacmat primary endpoint must be claimed by exactly one 2027 study."""

    co = _load_module("sacmat_claim_overlap", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    sacmat = [c for c in claims if c.study == VENUE]
    assert len(sacmat) == 1, "sacmat must appear exactly once in study_claims.json"
    endpoint = co._normalize(sacmat[0].primary_endpoint)
    holders = [c.study for c in claims if co._normalize(c.primary_endpoint) == endpoint]
    assert holders == [VENUE], f"primary endpoint '{SACMAT_ENDPOINT}' also claimed by: {holders}"
    question = co._normalize(sacmat[0].research_question)
    q_holders = [c.study for c in claims if co._normalize(c.research_question) == question]
    assert q_holders == [VENUE], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_sacmat() -> None:
    """Run the real shared tool: sacmat shares no question+endpoint with any venue."""

    co = _load_module("sacmat_claim_overlap_exec", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    assert len(claims) == 9, "study_claims.json must declare all nine 2027 venues"
    findings = co.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    sacmat_findings = [
        f
        for f in findings.findings
        if VENUE in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert not sacmat_findings, f"sacmat overlap findings: {[f.to_dict() for f in sacmat_findings]}"
    sacmat_claim = next(c for c in claims if c.study == VENUE)
    assert sacmat_claim.reuses_archive == (), (
        f"sacmat must not reuse archived evidence: {sacmat_claim.reuses_archive}"
    )
