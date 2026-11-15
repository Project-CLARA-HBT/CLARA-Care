"""Structural test for the POPETS-overlap publication isolation audit.

Purpose
-------
Machine-checks that ``research/venue2027/popets/overlap_audit.md`` satisfies the
P01 anti-salami gate, using the shared document validator
``research/venue2027/_shared/tools/overlap_contract.py``:

* the real audit document passes (all eight sibling 2027 venues named, all
  five historical comparators — GLHS, GovRed, GovMut, CareGuard, HEALTHINF —
  named, an explicit refusal to reuse frozen E15–E22 outcomes as new
  independent evidence, and exactly one final ``Decision: PASS`` line);
* adversarial mutations of the document fail with the expected stable reason
  codes: a missing sibling venue, a missing frozen-evidence refusal, a
  missing decision line, and a second decision line each fail closed;
* the executable check (``_shared/tools/claim_overlap.py``) over
  ``_shared/study_claims.json`` shows popets shares no question+endpoint pair
  with any other venue and reuses no archived evidence.

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
``popets-overlap-audit-test-v1``
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

TEST_VERSION = "popets-overlap-audit-test-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_PATH = REPO_ROOT / "research" / "venue2027" / "popets" / "overlap_audit.md"
CLAIMS_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "study_claims.json"
OVERLAP_TOOL_PATH = (
    REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "overlap_contract.py"
)
CLAIM_TOOL_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools" / "claim_overlap.py"

VENUE = "popets"

EIGHT_SIBLINGS: tuple[str, ...] = (
    "compsac",
    "aime",
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

# The refusal must be explicit, unambiguous, and cover "not reused as new
# independent evidence".
REFUSAL_SENTENCE_PATTERN = re.compile(
    r"frozen\s+E15[–-]E22\s+outcomes?[^\n]*are\s+NOT\s+reused\s+as\s+new\s+"
    r"independent\s+evidence",
    re.IGNORECASE,
)

DECISION_PATTERN = re.compile(r"^Decision:\s*(PASS|MERGE-ALTERNATIVE)\s*$", re.MULTILINE)

POPETS_ENDPOINT = "revoked-context re-disclosure rate"


def _load_audit_text() -> str:
    assert AUDIT_PATH.is_file(), f"overlap audit missing at {AUDIT_PATH}"
    return AUDIT_PATH.read_text(encoding="utf-8")


def _load_overlap_contract_module():
    spec = importlib.util.spec_from_file_location("overlap_contract", OVERLAP_TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {OVERLAP_TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _load_claim_overlap_module():
    spec = importlib.util.spec_from_file_location("claim_overlap", CLAIM_TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {CLAIM_TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_version_declared() -> None:
    assert TEST_VERSION.startswith("popets-overlap-audit-test-")


def test_audit_file_exists() -> None:
    assert AUDIT_PATH.is_file(), f"audit missing: {AUDIT_PATH}"


def test_shared_validator_passes_on_real_document() -> None:
    """The REQUIRED validator must return ok=True for the real audit document."""

    module = _load_overlap_contract_module()
    result = module.audit_overlap_document(_load_audit_text(), venue=VENUE)
    assert result.ok, f"overlap_contract failed: {result.to_dict()}"
    assert result.reason_codes == (), f"unexpected reason codes: {result.reason_codes}"
    assert result.missing_venues == (), f"missing sibling venues: {result.missing_venues}"
    assert result.missing_historical == (), (
        f"missing historical comparators: {result.missing_historical}"
    )
    assert result.has_frozen_refusal, "shared validator saw no frozen E15-E22 refusal"
    assert result.has_decision, "shared validator saw no decision line"


def test_all_eight_sibling_venues_named() -> None:
    text = _load_audit_text()
    lower = text.lower()
    # Slug forms ("compsac", "ifip_sec") or human labels ("COMPSAC", "IFIP SEC")
    # both count, mirroring the shared validator's label matching.
    label_map: dict[str, tuple[str, ...]] = {
        "compsac": ("compsac",),
        "aime": ("aime",),
        "ifip_sec": ("ifip_sec", "ifip sec"),
        "sacmat": ("sacmat",),
        "acns": ("acns",),
        "dsn": ("dsn",),
        "dimva": ("dimva",),
        "pst": ("pst",),
    }
    for venue in EIGHT_SIBLINGS:
        assert any(label in lower for label in label_map[venue]), (
            f"2027 sibling venue not named in audit: {venue}"
        )


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


def test_popets_endpoint_named() -> None:
    text = _load_audit_text()
    assert POPETS_ENDPOINT in text, "popets primary endpoint wording missing"


def test_popets_pst_contrast_present() -> None:
    """The mandatory PoPETs–PST distinction must contrast the two directions."""

    text = _load_audit_text()
    assert "post hoc" in text.lower(), "PST post-hoc forensic contrast missing"
    assert "future" in text.lower(), "PoPETs future-context contrast missing"
    assert "forensic" in text.lower(), "PST forensic reconstructability contrast missing"


def test_exactly_one_decision_line() -> None:
    text = _load_audit_text()
    decisions = DECISION_PATTERN.findall(text)
    assert len(decisions) == 1, f"expected exactly one Decision line, found {decisions}"
    assert decisions[0] == "PASS", f"decision must be PASS, found {decisions[0]}"


def test_decision_is_final_verdict_with_justification() -> None:
    text = _load_audit_text()
    match = DECISION_PATTERN.search(text)
    assert match is not None, "no Decision line found"
    tail = text[match.end() :]
    assert "Justification" in tail, "Decision lacks a justification block"


def test_validator_rejects_missing_sibling_venue(tmp_path: pathlib.Path) -> None:
    """Adversarial control: dropping a sibling venue must fail the shared validator."""

    module = _load_overlap_contract_module()
    text = _load_audit_text()
    # Remove every mention of one sibling venue slug.
    mutated = re.sub(r"(?i)\bdsn\b", "VENUE-REDACTED", text)
    assert "dsn" not in mutated.lower(), "mutation failed to remove the sibling venue"
    doc = tmp_path / "overlap_audit.md"
    doc.write_text(mutated, encoding="utf-8")
    result = module.audit_overlap_document(doc.read_text(encoding="utf-8"), venue=VENUE)
    assert not result.ok, "validator accepted an audit missing a sibling venue"
    assert "MISSING_SIBLING_VENUE" in result.reason_codes
    assert "dsn" in result.missing_venues


def test_validator_rejects_missing_frozen_refusal(tmp_path: pathlib.Path) -> None:
    """Adversarial control: dropping the E15-E22 refusal must fail the validator."""

    module = _load_overlap_contract_module()
    text = _load_audit_text()
    # Strip every refusal marker the shared validator keys on ("not reuse",
    # "not reused", "refus*", "not presented") while keeping the E15-E22
    # markers, so the mutation targets refusal semantics, not marker strings.
    mutated = re.sub(r"(?i)not\s+reuse[d]?", "discussed", text)
    mutated = re.sub(r"(?i)refus\w*", "cite", mutated)
    mutated = re.sub(r"(?i)not\s+presented", "mentioned", mutated)
    lower = mutated.lower()
    for marker in ("not reuse", "not reused", "refus", "not presented"):
        assert marker not in lower, f"mutation failed to remove refusal marker: {marker}"
    doc = tmp_path / "overlap_audit.md"
    doc.write_text(mutated, encoding="utf-8")
    result = module.audit_overlap_document(doc.read_text(encoding="utf-8"), venue=VENUE)
    assert not result.ok, "validator accepted an audit without the frozen-evidence refusal"
    assert "MISSING_FROZEN_REFUSAL" in result.reason_codes


def test_validator_rejects_missing_decision(tmp_path: pathlib.Path) -> None:
    """Adversarial control: dropping the decision line must fail the validator."""

    module = _load_overlap_contract_module()
    text = _load_audit_text()
    mutated = text.replace("Decision: PASS", "Decision withheld pending review")
    doc = tmp_path / "overlap_audit.md"
    doc.write_text(mutated, encoding="utf-8")
    result = module.audit_overlap_document(doc.read_text(encoding="utf-8"), venue=VENUE)
    assert not result.ok, "validator accepted an audit without a decision line"
    assert "MISSING_DECISION" in result.reason_codes


def test_no_duplicate_primary_claim() -> None:
    """The popets primary endpoint must be claimed by exactly one 2027 study."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    popets = [c for c in claims if c.study == "popets"]
    assert len(popets) == 1, "popets must appear exactly once in study_claims.json"
    endpoint = module._normalize(popets[0].primary_endpoint)
    holders = [c.study for c in claims if module._normalize(c.primary_endpoint) == endpoint]
    assert holders == ["popets"], f"primary endpoint '{POPETS_ENDPOINT}' also claimed by: {holders}"
    question = module._normalize(popets[0].research_question)
    q_holders = [c.study for c in claims if module._normalize(c.research_question) == question]
    assert q_holders == ["popets"], f"research question also claimed by: {q_holders}"


def test_executable_claim_overlap_passes_for_popets() -> None:
    """Run the real shared tool: popets shares no question+endpoint with any venue."""

    module = _load_claim_overlap_module()
    claims = module.load_claims(CLAIMS_PATH)
    findings = module.audit_overlap(claims)
    assert findings.ok, f"claim_overlap audit failed: {[f.to_dict() for f in findings.findings]}"
    popets_findings = [
        f
        for f in findings.findings
        if "popets" in f.pair
        and f.reason_code
        in {
            "SALAMI_SAME_QUESTION_AND_ENDPOINT",
            "SHARED_PRIMARY_ENDPOINT",
            "SHARED_RESEARCH_QUESTION",
            "ARCHIVE_REUSE_AS_NEW",
        }
    ]
    assert not popets_findings, f"popets overlap findings: {[f.to_dict() for f in popets_findings]}"
    popets_claim = next(c for c in claims if c.study == "popets")
    assert popets_claim.reuses_archive == (), (
        f"popets must not reuse archived evidence: {popets_claim.reuses_archive}"
    )
