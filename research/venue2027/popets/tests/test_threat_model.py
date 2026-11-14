"""Test that the POPETS threat model satisfies the shared validator contract.

Purpose
-------
Gate for task ``POPETS-threat``. It binds
``research/venue2027/popets/threat_model.md`` to the machine-checkable contract
``validate_threat() -> ThreatCoverage`` from the shared validator
``research/venue2027/_shared/tools/threat_model.py`` (version ``1.0.0``):

* all five required sections present (capabilities, trusted components,
  excluded domains, attack/control matrix, oracle/actor authority);
* every attack family row carries BOTH a ``clean`` and an ``adversarial``
  case (an incomplete model must fail);
* the real deliverable passes; a deliberately truncated model is refused
  with stable reason codes (``MISSING_SECTION``, ``FAMILY_WITHOUT_PAIR``).

Allowed input: markdown files inside this repository only (the real
deliverable and small synthetic strings for negative controls). The
validator module is imported read-only from the shared tools directory;
the tests never import any candidate research code.

Failure semantics: every check raises ``AssertionError`` with a stable
reason-style message; a missing deliverable file is a hard failure
(``MISSING_THREAT_MODEL``), never silently skipped.

Version: 1.0.0
"""

from __future__ import annotations

import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import threat_model as tm  # noqa: E402

THREAT_MODEL = pathlib.Path(__file__).resolve().parents[1] / "threat_model.md"


def _deliverable_text() -> str:
    """Load the deliverable; MISSING_THREAT_MODEL if absent (never skip)."""

    if not THREAT_MODEL.is_file():
        raise AssertionError(f"MISSING_THREAT_MODEL: expected deliverable at {THREAT_MODEL}")
    return THREAT_MODEL.read_text(encoding="utf-8")


def test_deliverable_passes_shared_validator() -> None:
    result = tm.validate_threat(_deliverable_text())
    assert result.ok, f"THREAT_MODEL_INCOMPLETE:{result.reason_codes}"
    assert result.reason_codes == (), "UNEXPECTED_REASON_CODES"
    assert result.missing_sections == (), "UNEXPECTED_MISSING_SECTIONS"
    assert result.families_without_pair == (), "UNEXPECTED_FAMILIES_WITHOUT_PAIR"


def test_all_five_families_paired_in_deliverable() -> None:
    paired, seen = tm._family_pairs(_deliverable_text())
    assert seen == set(tm.ATTACK_FAMILIES), f"FAMILY_TOKEN_MISSING:{set(tm.ATTACK_FAMILIES) - seen}"
    assert paired == set(
        tm.ATTACK_FAMILIES
    ), f"FAMILY_WITHOUT_PAIR:{set(tm.ATTACK_FAMILIES) - paired}"


def test_deliverable_declares_task_specific_threats() -> None:
    text = _deliverable_text()
    lowered = text.lower()
    for marker in (
        "revocation",
        "retry",
        "fallback",
        "embedding pointer",
        "purpose",
        "consent ledger",
    ):
        assert marker in lowered, f"MISSING_TASK_MARKER:{marker}"
    for code in ("OUT_OF_SCOPE_PAST", "INDETERMINATE"):
        assert code in text, f"MISSING_REASON_CODE:{code}"


def test_no_retroactive_erasure_claim() -> None:
    text = _deliverable_text()
    assert "already-delivered content" in text.lower(), "MISSING_DELIVERED_LIMITATION"
    assert "OUT_OF_SCOPE_PAST" in text, "MISSING_OUT_OF_SCOPE_PAST_CODE"
    assert (
        "no claim of cryptographic retroactive erasure" in text.lower()
    ), "FORBIDDEN_RETROACTIVE_ERASURE_CLAIM"


def test_matrix_template_from_validator_passes() -> None:
    text = (
        "# T\n## Attacker and observer capabilities\n## Trusted components\n"
        "## Excluded domains\n## Attack family and control matrix\n"
        + tm.render_matrix_template()
        + "\n## Oracle and actor authority\nDefined.\n"
    )
    assert tm.validate_threat(text).ok, "VALIDATOR_TEMPLATE_MUST_PASS"


def test_incomplete_model_missing_section_fails() -> None:
    text = "\n".join(
        line for line in _deliverable_text().splitlines() if "Excluded domains" not in line
    )
    result = tm.validate_threat(text)
    assert not result.ok, "INCOMPLETE_MODEL_MUST_FAIL"
    assert "MISSING_SECTION" in result.reason_codes
    assert "Excluded domains" in result.missing_sections


def test_incomplete_model_family_without_pair_fails() -> None:
    text = "\n".join(line for line in _deliverable_text().splitlines() if "| replay |" not in line)
    result = tm.validate_threat(text)
    assert not result.ok, "INCOMPLETE_MODEL_MUST_FAIL"
    assert "FAMILY_WITHOUT_PAIR" in result.reason_codes
    assert "replay" in result.families_without_pair


def test_incomplete_model_single_cell_pair_fails() -> None:
    # Drop the replay row's adversarial cell so the family has a clean case
    # but no paired adversarial case; the validator must refuse it.
    text = "\n".join(
        line.replace(
            "adversarial: POPETS-CASE-02 — the cached pre-revocation context is",
            "control-only: POPETS-CASE-02 — the cached pre-revocation context is",
        )
        if "| replay |" in line
        else line
        for line in _deliverable_text().splitlines()
    )
    result = tm.validate_threat(text)
    assert not result.ok, "SINGLE_CELL_PAIR_MUST_FAIL"
    assert "replay" in result.families_without_pair
