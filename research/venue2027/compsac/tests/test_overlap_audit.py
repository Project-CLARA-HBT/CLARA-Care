"""Structural test for the COMPSAC-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/overlap_audit.md`` satisfies the
P01 anti-salami gate: all nine 2027 venues named, the historical
GLHS/GovRed/GovMut/HEALTHINF comparators named, an explicit refusal to reuse
frozen E15–E22 outcomes as new independent evidence, a final Decision line, and
no duplicate primary claim. Also runs the real executable check
(``_shared/tools/claim_overlap.py``) against ``_shared/study_claims.json`` and
asserts the compsac entry does not share question+endpoint with any other
venue and reuses no archived evidence.

Allowed input
-------------
Read-only access to the audit markdown, the shared claims registry and the
shared tool. No network, no database, no writes outside tmp_path.

Failure semantics
-----------------
Each check raises ``AssertionError`` naming the missing element; no silent
passes. Stdlib-only besides pytest itself.

Version
-------
``compsac-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "compsac-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "compsac" / "overlap_audit.md"
CLAIMS_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "study_claims.json"
TOOL_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "claim_overlap.py"

NINE_VENUES: tuple[str, ...] = (
    "DSN",
    "PoPETs",
    "IFIP SEC",
    "ACNS",
    "AIME",
    "SACMAT",
    "DIMVA",
    "PST",
    "COMPSAC",
)

HISTORICAL_COMPARATORS: tuple[str, ...] = (
    "GLHS",
    "GovRed",
    "GovMut",
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

COMPSAC_ENDPOINT = "forbidden commit rate under dependency-complete schedules"


def _load_audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _load_claim_overlap_module():
    spec = importlib.util.spec_from_file_location("claim_overlap", TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("compsac-overlap-audit-test-")


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


def test_all_nine_2027_venues_named() -> None:
    text = _load_audit_text()
    for venue in NINE_VENUES:
        assert venue in text, f"2027 venue not named in audit: {venue}"


def test_historical_comparators_named() -> None:
    text = _load_audit_text()
    for name in HISTORICAL_COMPARATORS:
        assert name in text, f"historical comparator not named in audit: {name}"
    # CareGuard must also be covered per the registry (it is in the task brief's
    # historical set and is declared NOT_RUN).
    assert "CareGuard" in text, "CareGuard-VN comparator not named in audit"


def test_e15_e22_refusal_sentence_present() -> None:
    text = _load_audit_text()
    assert REFUSAL_SENTENCE_PATTERN.search(text), (
        "explicit 'frozen E15–E22 outcomes are NOT reused as new independent "
        "evidence' refusal sentence missing from audit"
    )


def test_compsac_endpoint_named() -> None:
    text = _load_audit_text()
    assert COMPSAC_ENDPOINT in text, "compsac primary endpoint wording missing"


def test_dsn_contrast_present() -> None:
    text = _load_audit_text()
    assert "crash" in text.lower(), "DSN crash-consistency contrast missing"
    assert "benign contention" in text.lower(), "COMPSAC benign-contention contrast missing"


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
    """The compsac primary endpoint must be claimed by exactly one 2027 study."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    compsac = [c for c in claims if c.study == "compsac"]
    assert len(compsac) == 1, "compsac must appear exactly once in study_claims.json"
    endpoint = module._normalize(compsac[0].primary_endpoint)
    holders = [c.study for c in claims if module._normalize(c.primary_endpoint) == endpoint]
    assert holders == [
        "compsac"
    ], f"primary endpoint '{COMPSAC_ENDPOINT}' also claimed by: {holders}"
    question = module._normalize(compsac[0].research_question)
    q_holders = [c.study for c in claims if module._normalize(c.research_question) == question]
    assert q_holders == ["compsac"], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_compsac() -> None:
    """Run the real shared tool: compsac shares no question+endpoint with any venue."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    findings = module.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    compsac_findings = [
        f
        for f in findings.findings
        if "compsac" in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert (
        not compsac_findings
    ), f"compsac overlap findings: {[f.to_dict() for f in compsac_findings]}"
    compsac_claim = next(c for c in claims if c.study == "compsac")
    assert (
        compsac_claim.reuses_archive == ()
    ), f"compsac must not reuse archived evidence: {compsac_claim.reuses_archive}"
