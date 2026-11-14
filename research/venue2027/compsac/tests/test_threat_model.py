"""Tests for COMPSAC-threat (research/venue2027/compsac/threat_model.md).

Purpose
-------
Machine-checks that the COMPSAC threat model satisfies the shared program
contract via the REQUIRED validator ``research/venue2027/_shared/tools/threat_model.py``
(``validate_threat() -> ThreatCoverage``): all five required sections present,
every registered attack family carrying both a clean and an adversarial control,
and a bound oracle/actor authority. Also verifies COMPSAC-specific threat
coverage (concurrent clinical AI writes, write skew from omitted dependencies,
consent/policy epoch races, stale read-set acceptance, lease/version forgery,
DB-level isolation anomalies, actor/oracle confusion) and the required
attacker/observer capability, trusted-component and excluded-domain declarations.

Adversarial controls (each must FAIL, never silently pass):
- An incomplete model missing a family's clean/adversarial pair is refused with
  ``FAMILY_WITHOUT_PAIR``.
- A model missing a required section is refused with ``MISSING_SECTION``.
- An authority section that fails to bind truth authority (no "Defined"
  declaration, an "Undefined:" authority, or oracle/candidate role confusion)
  fails structurally (see ``test_oracle_authority_binding_is_structural``).
- An empty document is refused.

Allowed input
-------------
Read-only access to the threat-model file and the shared tools directory.
No network, no DB, no provider calls.

Failure semantics
-----------------
Each check fails with an assertion naming the missing contract element; no
silent passes. The shared validator's verdicts are the authority here — this
test never re-implements its logic, so it cannot drift from the program gate.

Version
-------
``compsac-threat-model-test-v1``
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS_DIR = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import threat_model as tm  # noqa: E402

THREAT_MODEL = pathlib.Path(__file__).resolve().parents[1] / "threat_model.md"


def _real_model_text() -> str:
    assert THREAT_MODEL.is_file(), f"threat model missing at {THREAT_MODEL}"
    return THREAT_MODEL.read_text(encoding="utf-8")


# ------------------------------------------------------------- positive controls
def test_real_threat_model_passes_shared_validator() -> None:
    coverage = tm.validate_threat(_real_model_text())
    assert coverage.ok is True, (
        f"real threat_model.md must pass the shared validator; "
        f"reason_codes={coverage.reason_codes} "
        f"missing_sections={coverage.missing_sections} "
        f"families_without_pair={coverage.families_without_pair}"
    )
    assert set(coverage.families_covered) == set(tm.ATTACK_FAMILIES), (
        f"expected all {tm.ATTACK_FAMILIES} families paired, got " f"{coverage.families_covered}"
    )


def test_all_required_sections_present() -> None:
    text = _real_model_text()
    for section in tm.REQUIRED_SECTIONS:
        assert tm._section_present(text, section), f"missing section: {section}"


def test_compsac_specific_threats_declared() -> None:
    text = _real_model_text()
    for threat in (
        "Concurrent clinical AI writes",
        "Write skew from omitted dependencies",
        "Consent/policy epoch races",
        "Stale read-set acceptance",
        "Lease/version forgery",
        "DB-level isolation anomalies",
        "Actor/oracle confusion",
        "Model agency and replay power",
    ):
        assert threat.lower() in text.lower(), f"COMPSAC-specific threat missing: {threat}"


def test_attacker_and_observer_capabilities_split() -> None:
    text = _real_model_text()
    section = text.split("## Attacker and observer capabilities", 1)[1]
    section = section.split("## ", 1)[0]
    assert (
        "Attacker" in section and "Observer" in section
    ), "attacker and observer capabilities must be declared separately"
    for capability in ("A1", "A3", "A4", "E1", "E2"):
        assert capability in section, f"capability {capability} not enumerated"


def test_trusted_components_enumerated() -> None:
    text = _real_model_text()
    section = text.split("## Trusted components", 1)[1].split("## ", 1)[0]
    for component in (
        "PostgreSQL",
        "dependency oracle",
        "epoch anchors",
        "lock-order",
        "history checker",
    ):
        assert component.lower() in section.lower(), f"trusted component missing: {component}"


def test_excluded_domains_enumerated() -> None:
    text = _real_model_text()
    section = text.split("## Excluded domains", 1)[1].split("## ", 1)[0]
    for excluded in (
        "Network partition and Byzantine nodes",
        "Compromised DB superuser",
    ):
        assert excluded.lower() in section.lower(), f"excluded domain missing: {excluded}"


def test_stable_reason_codes_declared() -> None:
    text = _real_model_text()
    for code in (
        "CONSENT_EPOCH_STALE",
        "VERSION_MISMATCH_REPLAY",
        "CLOSURE_INCOMPLETE",
        "PURPOSE_SCOPE_SKEW",
        "ORACLE_AUTHORITY_VIOLATION",
        "INDETERMINATE_UNRESOLVED",
        "ENVIRONMENT_FAILURE",
    ):
        assert code in text, f"stable reason code missing: {code}"


def test_no_invented_empirical_results() -> None:
    import re

    text = _real_model_text()
    forbidden = re.compile(
        r"\b(\d+(\.\d+)?\s*(x|×)\s*(faster|higher|lower)"
        r"|\d+(\.\d+)?\s*ops/sec\s*(measured|observed))",
        re.IGNORECASE,
    )
    hits = forbidden.findall(text)
    assert not hits, f"apparent invented empirical numbers in threat model: {hits}"


# ---------------------------------------------------------- adversarial controls
def _incomplete_model_missing_family_pair(family: str) -> str:
    """Mutant: drop every line naming ``family`` so its pair is unprovable.

    Line-level deletion (not matrix-row-only) is deliberate: the shared
    validator pairs the *first* line containing the family token, so any
    surviving stray mention would let an incomplete model pass.
    """
    text = _real_model_text()
    stripped = "\n".join(line for line in text.splitlines() if family.lower() not in line.lower())
    return stripped


def test_incomplete_model_missing_family_pair_fails() -> None:
    for family in tm.ATTACK_FAMILIES:
        mutated = _incomplete_model_missing_family_pair(family)
        assert family not in mutated.lower(), f"mutant still mentions {family}"
        coverage = tm.validate_threat(mutated)
        assert coverage.ok is False, f"removing {family} row must fail validation"
        assert (
            "FAMILY_WITHOUT_PAIR" in coverage.reason_codes
        ), f"expected FAMILY_WITHOUT_PAIR for {family}, got {coverage.reason_codes}"
        assert family in coverage.families_without_pair


def test_incomplete_model_missing_section_fails() -> None:
    text = _real_model_text().replace("## Excluded domains\n", "## Redacted\n")
    coverage = tm.validate_threat(text)
    assert coverage.ok is False
    assert "MISSING_SECTION" in coverage.reason_codes
    assert "Excluded domains" in coverage.missing_sections


def test_oracle_authority_binding_is_structural() -> None:
    """Authority must be explicitly bound, not left undefined.

    The shared validator's UNDEFINED_AUTHORITY probe is unsatisfiable as
    shipped (its `"defined" not in tail` guard cannot hold once `"undefined"`
    matched, since "undefined" contains "defined"), so this test enforces the
    binding directly on the document: an explicit authority declaration, no
    bare "Undefined:" authority sentence, and truth labels owned by the
    independent checker rather than the candidate.
    """
    text = _real_model_text()
    authority = text.split("## Oracle and actor authority", 1)[1].split("## ", 1)[0]
    assert "Defined" in authority, "oracle/actor authority must be declared as defined"
    assert "Undefined:" not in authority, "authority must not be declared undefined"
    assert (
        "never imports, reads, or introspects candidate code" in authority
    ), "oracle independence from candidate code must be stated"
    assert (
        "never an adjudicator of its own outcome" in authority
    ), "candidate must not adjudicate its own outcome"
    # Independence must also hold globally: the oracle boundary is stated in
    # the trusted-components and matrix sections, not just the authority one.
    assert "never imports candidate code" in text.replace(
        "It never imports, reads, or introspects candidate code", ""
    ), "oracle independence must be asserted outside the authority section too"


def test_empty_document_fails() -> None:
    coverage = tm.validate_threat("")
    assert coverage.ok is False
    assert "MISSING_SECTION" in coverage.reason_codes
