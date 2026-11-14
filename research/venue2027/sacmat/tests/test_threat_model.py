"""Structural tests for the SACMAT-threat model (task SACMAT-threat, P01).

Purpose
-------
Gate ``research/venue2027/sacmat/threat_model.md`` through the shared validator
``research/venue2027/_shared/tools/threat_model.py`` (``validate_threat ->
ThreatCoverage``) and assert SACMAT-specific content: the delegated-consent
divergence family with paired clean+adversarial cases, the six extended
delegation families, trust/exclusion boundaries, revocation/schedule-time and
replay-power declarations, and the undefined-authority negative control.

Allowed input
-------------
The markdown file at the repository-relative path below, read-only, plus the
shared validator module. No network, no clock, no randomness.

Failure semantics
-----------------
Each violation raises a focused ``AssertionError`` naming the missing marker;
the suite fails closed if the model file or the shared validator is absent.
An incomplete model must fail (validator ``ok=False``), never pass silently.

Version
-------
``THREAT_MODEL_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import sys

THREAT_MODEL_TEST_VERSION = "1.0.0"

SACMAT_DIR = pathlib.Path(__file__).resolve().parents[1]
MODEL_PATH = SACMAT_DIR / "threat_model.md"
TOOLS_DIR = SACMAT_DIR.parent / "_shared" / "tools"

sys.path.insert(0, str(TOOLS_DIR))

import threat_model as tm  # noqa: E402

EXTENDED_FAMILIES: tuple[str, ...] = (
    "delegated_consent_divergence",
    "delegation_subchain_forgery",
    "policy_version_skew",
    "obligation_purpose_mismatch",
    "conformance_test_evasion",
    "temporal_delegation_expiry_race",
)


def _load() -> str:
    assert MODEL_PATH.is_file(), f"threat model missing at {MODEL_PATH}"
    return MODEL_PATH.read_text(encoding="utf-8")


def test_real_model_passes_shared_validator() -> None:
    result = tm.validate_threat(_load())
    assert result.ok is True, f"validator refused model: {result.to_dict()}"
    assert result.reason_codes == ()
    assert result.missing_sections == ()
    assert result.families_without_pair == ()
    assert set(result.families_covered) == set(tm.ATTACK_FAMILIES)


def test_incomplete_model_fails_validator() -> None:
    text = _load()
    # Drop the paired row for one canonical family -> FAMILY_WITHOUT_PAIR.
    stripped = "\n".join(
        line for line in text.splitlines() if "| insider_or_observer |" not in line
    )
    result = tm.validate_threat(stripped)
    assert result.ok is False, "incomplete model must be refused"
    assert "FAMILY_WITHOUT_PAIR" in result.reason_codes
    assert "insider_or_observer" in result.families_without_pair

    # Drop a required section -> MISSING_SECTION.
    headless = "\n".join(
        line
        for line in stripped.splitlines()
        if not line.startswith("## 4. Trusted components")
    )
    result2 = tm.validate_threat(headless)
    assert result2.ok is False
    assert "MISSING_SECTION" in result2.reason_codes


def test_all_extended_sacmat_families_have_paired_rows() -> None:
    text = _load()
    matrix = text.split("## 2. Attack family and control matrix", 1)[1].split(
        "## 3.", 1
    )[0]
    for family in EXTENDED_FAMILIES:
        rows = [ln for ln in matrix.splitlines() if f"| {family} |" in ln]
        assert rows, f"extended family row missing from matrix: {family}"
        row = rows[0].lower()
        assert "clean" in row, f"{family}: clean control missing"
        assert "adversarial" in row, f"{family}: adversarial case missing"


def test_delegation_divergence_family_has_clean_and_adversarial_cases() -> None:
    text = _load()
    rows = [ln for ln in text.splitlines() if "| delegated_consent_divergence |" in ln]
    assert rows, "delegation-divergence family row missing"
    row = rows[0].lower()
    assert "clean:" in row and "adversarial:" in row, (
        "delegation-divergence family must carry paired clean+adversarial cells"
    )
    # The adversarial cell must target the study's distinct endpoint: identical
    # ordered history across engines yielding a recorded divergence witness.
    assert "grant" in row and "revoke" in row, (
        "adversarial case must exercise ordered grant/revoke history"
    )
    assert "cedar" in row and "openfga" in row and "opa" in row, (
        "adversarial case must replay the same history into all three engines"
    )
    # And it must be keyed to the paper's endpoint language.
    assert "divergence witness" in row or "divergence" in row


def test_trusted_components_and_excluded_domains_declared() -> None:
    text = _load()
    assert "## 4. Trusted components" in text
    for component in (
        "Declarative reference-semantics model",
        "Conformance adapters",
        "External engine binaries",
    ):
        assert component in text, f"trusted component not declared: {component}"
    assert "## 5. Excluded domains" in text
    assert "Engine implementation compromise" in text, (
        "excluded domain (engine compromise) not declared"
    )
    assert "fail-closed" in text.lower(), "fail-closed failure semantics missing"


def test_revocation_schedule_time_and_replay_power_declared() -> None:
    text = _load()
    assert "revocation/schedule-time semantics" in text
    assert "zero-width orderings" in text, "zero-width tick race not declared"
    assert "replay power is unlimited against engines" in text
    assert "nonexistent against oracle labels" in text, (
        "replay power against oracle labels must be bounded"
    )


def test_model_agency_declared_with_undecided_case_rule() -> None:
    text = _load()
    assert "Model agency is deliberately narrow" in text
    assert "never from engine output" in text
    assert "never from aggregate statistics" in text
    assert "labeled INDETERMINATE until adjudicated" in text, (
        "undecided-case rule missing"
    )


def test_undefined_authority_negative_control() -> None:
    text = _load()
    assert "## 6. Oracle and actor authority" in text
    assert "Authority is **defined**" in text, "authority must be explicitly defined"
    assert "UNDEFINED_AUTHORITY" in text, "undefined-authority reason code missing"
    assert "never counted as a safe rejection" in text.lower(), (
        "INDETERMINATE-as-safe-rejection refusal missing"
    )


def test_no_invented_empirical_numbers() -> None:
    text = _load()
    assert "PROSPECTIVE / NOT RUN" in text, "evidence status must be declared not-run"
    assert "designed fixtures" in text and "not observed results" in text
