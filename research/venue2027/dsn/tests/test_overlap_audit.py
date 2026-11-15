"""Structural test for the DSN-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/dsn/overlap_audit.md`` satisfies the
P01 anti-salami gate by running the shared validator
(``_shared/tools/overlap_contract.py``) against the real document, and against
three adversarial mutants: one missing a sibling venue, one missing the frozen
E15-E22 reuse refusal, and one missing the final decision line. Each mutant
must fail with its stable reason code, proving the validator actually gates
this venue's audit. Also runs ``_shared/tools/claim_overlap.py`` over
``_shared/study_claims.json`` and asserts the dsn entry shares no
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
``dsn-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "dsn-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "dsn" / "overlap_audit.md"
SHARED = REPO_ROOT / "research" / "venue2027" / "_shared"
CLAIMS_PATH = SHARED / "study_claims.json"
OVERLAP_TOOL_PATH = SHARED / "tools" / "overlap_contract.py"
CLAIM_TOOL_PATH = SHARED / "tools" / "claim_overlap.py"

VENUE = "dsn"

SIBLING_VENUES: tuple[str, ...] = (
    "popets",
    "aime",
    "ifip_sec",
    "sacmat",
    "acns",
    "compsac",
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

DSN_ENDPOINT = "crash-consistency violation rate after fault injection"


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
    assert TEST_VERSION.startswith("dsn-overlap-audit-test-")


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


def test_dsn_endpoint_named() -> None:
    text = _load_audit_text()
    assert DSN_ENDPOINT in text, "dsn primary endpoint wording missing"


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
            "are NOT reused as new\nindependent evidence in the DSN 2027 study, in any section, "
            "table, figure, or statistical\ntest.",
            "are part of this study's own new evidence.",
        ),
        ("## 5. Frozen E15–E22 refusal (mandatory statement)", "## 5. Frozen E15–E22 statement"),
        ("This audit refuses:", "This audit states:"),
        ("This refusal is a binding condition", "This statement is a binding condition"),
        ("DSN does not reuse that frozen evidence", "DSN cites that frozen evidence"),
        ("comparators, not reused results", "comparators; no results reused from them"),
        (
            "Historical background and motivation only (see §5 refusal)",
            "Historical background and motivation only (see §5)",
        ),
        (
            "This audit refuses the merge on endpoint separation",
            "This audit rejects the merge on endpoint separation",
        ),
        (
            "the explicit refusal discipline for INDETERMINATE evidence",
            "the explicit INDETERMINATE-evidence discipline",
        ),
        (
            "merge pair is refused by endpoint separation",
            "merge pair is declined by endpoint separation",
        ),
        (
            "Frozen E15–E22 outcomes are explicitly NOT reused as new independent evidence\n(§5)",
            "Frozen E15–E22 outcomes are treated as background only (§5)",
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


def test_dsn_compsac_contrast_present() -> None:
    text = _load_audit_text().lower()
    assert "crash" in text, "DSN crash-consistency side of the contrast missing"
    assert "benign contention" in text, "COMPSAC benign-contention side missing"
    assert "recovery" in text, "post-crash recovery side of the contrast missing"


def test_no_duplicate_primary_claim() -> None:
    """The dsn primary endpoint must be claimed by exactly one 2027 study."""

    co = _load_module("claim_overlap", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    dsn = [c for c in claims if c.study == VENUE]
    assert len(dsn) == 1, "dsn must appear exactly once in study_claims.json"
    endpoint = co._normalize(dsn[0].primary_endpoint)
    holders = [c.study for c in claims if co._normalize(c.primary_endpoint) == endpoint]
    assert holders == [VENUE], f"primary endpoint '{DSN_ENDPOINT}' also claimed by: {holders}"
    question = co._normalize(dsn[0].research_question)
    q_holders = [c.study for c in claims if co._normalize(c.research_question) == question]
    assert q_holders == [VENUE], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_dsn() -> None:
    """Run the real shared tool: dsn shares no question+endpoint with any venue."""

    co = _load_module("claim_overlap", CLAIM_TOOL_PATH)
    claims = co.load_claims(CLAIMS_PATH)
    findings = co.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    dsn_findings = [
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
    assert not dsn_findings, f"dsn overlap findings: {[f.to_dict() for f in dsn_findings]}"
    dsn_claim = next(c for c in claims if c.study == VENUE)
    assert dsn_claim.reuses_archive == (), (
        f"dsn must not reuse archived evidence: {dsn_claim.reuses_archive}"
    )
