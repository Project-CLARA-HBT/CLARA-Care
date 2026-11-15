"""Structural test for the DIMVA-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/dimva/overlap_audit.md`` satisfies the
P01 anti-salami gate by running the shared validator
(``_shared/tools/overlap_contract.py``) against the real document, and against
three adversarial mutants: one missing a sibling venue, one missing the frozen
E15-E22 reuse refusal, and one missing the final decision line. Each mutant
must fail with its stable reason code, proving the validator actually gates
this venue's audit. Also runs ``_shared/tools/claim_overlap.py`` over
``_shared/study_claims.json`` and asserts the dimva entry shares no
question+endpoint pair with any other venue and reuses no archived evidence.

Allowed input
-------------
Read-only access to the audit markdown, the shared claims registry, the shared
tools and a pytest ``tmp_path`` for mutant files. No network, no database, no
writes outside ``tmp_path``.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing element; no silent
passes. Stdlib-only besides pytest itself.

Version
-------
``dimva-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "dimva-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "dimva" / "overlap_audit.md"
SHARED = REPO_ROOT / "research" / "venue2027" / "_shared"
CLAIMS_PATH = SHARED / "study_claims.json"
OVERLAP_TOOL_PATH = SHARED / "tools" / "overlap_contract.py"
CLAIM_TOOL_PATH = SHARED / "tools" / "claim_overlap.py"

VENUE = "dimva"

SIBLING_VENUES: tuple[str, ...] = (
    "compsac",
    "popets",
    "aime",
    "ifip_sec",
    "sacmat",
    "acns",
    "dsn",
    "pst",
)

HISTORICAL_COMPARATORS: tuple[str, ...] = (
    "GLHS",
    "GovRed",
    "GovMut",
    "CareGuard",
    "HEALTHINF",
)

DIMVA_ENDPOINT = "probing detection AUC at fixed false-positive budget"


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


def _load_audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("dimva-overlap-audit-test-")


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


def test_shared_validator_accepts_real_document() -> None:
    """The required shared overlap validator must accept the real audit."""

    oc = _load_module("overlap_contract", OVERLAP_TOOL_PATH)
    result = oc.audit_overlap_document(_load_audit_text(), venue=VENUE)
    assert result.ok, f"shared validator rejected audit: {result.to_dict()}"
    assert result.missing_venues == (), result.missing_venues
    assert result.missing_historical == (), result.missing_historical
    assert result.has_frozen_refusal is True
    assert result.has_decision is True


def test_all_eight_sibling_venues_named() -> None:
    text = _load_audit_text()
    for venue in SIBLING_VENUES:
        assert venue in text.lower(), f"2027 sibling venue not named in audit: {venue}"


def test_all_five_historical_comparators_named() -> None:
    text = _load_audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"


def test_dimva_endpoint_named() -> None:
    text = _load_audit_text()
    assert DIMVA_ENDPOINT in text, "dimva primary endpoint wording missing"


def test_frozen_refusal_present() -> None:
    text = _load_audit_text()
    assert "E15" in text and "E22" in text, "frozen E15-E22 marker missing"
    assert "NOT reused as new" in text, "explicit frozen-evidence refusal missing"


def test_mutant_missing_sibling_fails(tmp_path: pathlib.Path) -> None:
    """Adversarial control: removing a sibling venue must fail the validator."""

    oc = _load_module("overlap_contract", OVERLAP_TOOL_PATH)
    body = re.sub(r"pst", "", _load_audit_text(), flags=re.IGNORECASE)
    mutant = tmp_path / "mutant_missing_sibling.md"
    mutant.write_text(body, encoding="utf-8")
    result = oc.audit_overlap_document(mutant.read_text(encoding="utf-8"), venue=VENUE)
    assert result.ok is False, "mutant missing a sibling venue must not pass"
    assert result.reason_codes == ("MISSING_SIBLING_VENUE",), result.reason_codes
    assert "pst" in result.missing_venues


def test_mutant_missing_frozen_refusal_fails(tmp_path: pathlib.Path) -> None:
    """Adversarial control: removing the frozen-evidence refusal must fail.

    The shared validator triggers on any refusal stem (``refus``) or reuse
    denial (``not reuse``/``not reused``/``not presented``), so the mutant
    must strip every such phrase, not only the bold refusal sentence.
    """

    oc = _load_module("overlap_contract", OVERLAP_TOOL_PATH)
    body = _load_audit_text()
    replacements = (
        (
            "are NOT reused as new\nindependent evidence in the DIMVA 2027 study, in any section, "
            "table, figure, or statistical\ntest.",
            "are part of this study's own new evidence.",
        ),
        ("## 5. Frozen E15–E22 refusal (mandatory statement)", "## 5. Frozen E15–E22 statement"),
        ("This audit refuses:", "This audit states:"),
        ("This audit refuses the merge", "This audit declines the merge"),
        ("This refusal is a binding condition", "This statement is a binding condition"),
        (
            '(`dimva/novelty_contract.md` §5, "Archive refusal")',
            "(`dimva/novelty_contract.md` §5, archive statement)",
        ),
        ("DIMVA does not reuse that frozen evidence", "DIMVA cites that frozen evidence"),
        (
            "The same probing campaign is never reused as two independent primary studies.",
            "The same probing campaign is cited as shared context of both studies.",
        ),
        (
            "Historical background and motivation only (see §5 statement)",
            "Historical background and motivation only (see §5)",
        ),
        (
            "that frozen evidence is not counted as a DIMVA result",
            "that frozen evidence is cited as background only",
        ),
        (
            "Frozen E15–E22 outcomes are explicitly excluded as new independent\nevidence",
            "Frozen E15–E22 outcomes are treated as background only",
        ),
    )
    for old, new in replacements:
        assert old in body, f"refusal-mutation anchor not found: {old[:60]!r}"
        body = body.replace(old, new)
    lower = body.lower()
    for trigger in ("not reuse", "not reused", "refus", "not presented"):
        assert trigger not in lower, f"refusal trigger still present in mutant: {trigger!r}"
    mutant = tmp_path / "mutant_missing_refusal.md"
    mutant.write_text(body, encoding="utf-8")
    result = oc.audit_overlap_document(mutant.read_text(encoding="utf-8"), venue=VENUE)
    assert result.ok is False, "mutant missing the frozen refusal must not pass"
    assert "MISSING_FROZEN_REFUSAL" in result.reason_codes, result.reason_codes


def test_mutant_missing_decision_fails(tmp_path: pathlib.Path) -> None:
    """Adversarial control: removing the decision line must fail the validator."""

    oc = _load_module("overlap_contract", OVERLAP_TOOL_PATH)
    body = _load_audit_text().replace("Decision: PASS", "Verdict issued in section 7.")
    assert body != _load_audit_text(), "decision-line mutation did not apply"
    mutant = tmp_path / "mutant_missing_decision.md"
    mutant.write_text(body, encoding="utf-8")
    result = oc.audit_overlap_document(mutant.read_text(encoding="utf-8"), venue=VENUE)
    assert result.ok is False, "mutant missing the decision line must not pass"
    assert result.reason_codes == ("MISSING_DECISION",), result.reason_codes


def test_exactly_one_decision_line() -> None:
    text = _load_audit_text()
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("Decision:")]
    assert len(lines) == 1, f"expected exactly one Decision line, found: {lines}"
    assert lines[0].strip() == "Decision: PASS", lines[0]


def test_dimva_ifip_sec_contrast_present() -> None:
    text = _load_audit_text().lower()
    assert "prevention" in text, "IFIP SEC prevention side of the contrast missing"
    assert "detection" in text, "DIMVA detection side of the contrast missing"
    assert "verification" in text, "verification-time distinction missing"
    assert "event stream" in text, "independent event-stream distinction missing"


def test_no_duplicate_primary_claim() -> None:
    """The dimva primary endpoint must be claimed by exactly one 2027 study."""

    co = _load_module("claim_overlap", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    dimva = [c for c in claims if c.study == VENUE]
    assert len(dimva) == 1, "dimva must appear exactly once in study_claims.json"
    endpoint = co._normalize(dimva[0].primary_endpoint)
    holders = [c.study for c in claims if co._normalize(c.primary_endpoint) == endpoint]
    assert holders == [VENUE], f"primary endpoint '{DIMVA_ENDPOINT}' also claimed by: {holders}"
    question = co._normalize(dimva[0].research_question)
    q_holders = [c.study for c in claims if co._normalize(c.research_question) == question]
    assert q_holders == [VENUE], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_dimva() -> None:
    """Run the real shared tool: dimva shares no question+endpoint with any venue."""

    co = _load_module("claim_overlap", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    findings = co.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    dimva_findings = [
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
    assert not dimva_findings, f"dimva overlap findings: {[f.to_dict() for f in dimva_findings]}"
    dimva_claim = next(c for c in claims if c.study == VENUE)
    assert dimva_claim.reuses_archive == (), (
        f"dimva must not reuse archived evidence: {dimva_claim.reuses_archive}"
    )
