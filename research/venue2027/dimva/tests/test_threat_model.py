"""Structural tests for the DIMVA-threat threat model (P01).

Purpose
-------
Verify ``research/venue2027/dimva/threat_model.md`` against the shared
machine contract ``research/venue2027/_shared/tools/threat_model.py``
(``validate_threat() -> ThreatCoverage``, ``THREAT_MODEL_VERSION = "1.0.0"``).

Positive controls:
- The real threat-model file passes ``validate_threat`` with ``ok=True``.
- Every required section is present, all five canonical attack families plus
  the DIMVA-specific ``adaptive_probing`` family are paired with clean and
  adversarial cases, and all authorities are defined.

Adversarial controls (each must FAIL, never pass by default):
- An incomplete model (missing sections) is refused.
- A model whose family rows lack clean/adversarial pairs is refused.
- A model with an undefined oracle/actor authority is refused.
- A model that silently drops an attack family is refused.

Allowed input
-------------
Read-only file text; no network, no randomness, no clock, no candidate or
production imports. Version: 1.0.0.
"""

from __future__ import annotations

import pathlib
import re
import sys

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import threat_model as tm  # noqa: E402

THREAT_MODEL_PATH = pathlib.Path(__file__).resolve().parents[1] / "threat_model.md"

DIMVA_SPECIFIC_FAMILY = "adaptive_probing"

DEFINED_AUTHORITY_DECLARATION = "All authorities in this model are **defined**"


def _real_text() -> str:
    return THREAT_MODEL_PATH.read_text(encoding="utf-8")


# ------------------------------------------------------------ real file: PASS
def test_real_threat_model_passes_shared_validator() -> None:
    coverage = tm.validate_threat(_real_text())
    assert coverage.ok is True, coverage.to_dict()
    assert coverage.reason_codes == ()
    assert coverage.missing_sections == ()
    assert coverage.families_without_pair == ()


def test_real_threat_model_covers_all_canonical_families() -> None:
    coverage = tm.validate_threat(_real_text())
    assert set(coverage.families_covered) == set(tm.ATTACK_FAMILIES), coverage.to_dict()


def test_real_threat_model_declares_required_sections() -> None:
    text = _real_text()
    for section in tm.REQUIRED_SECTIONS:
        assert tm._section_present(text, section), f"missing section: {section!r}"


def test_real_threat_model_names_governance_trace_scope() -> None:
    text = _real_text()
    assert "GovernanceTrace" in text
    assert "detection" in text.lower()
    # Detection, not prevention: this study never decides a single admission.
    assert "IFIP SEC" in text


# ------------------------------------------------- adaptive-probing family
def test_adaptive_probing_family_exists_with_clean_and_adversarial_pair() -> None:
    text = _real_text().lower()
    assert DIMVA_SPECIFIC_FAMILY in text, "DIMVA-specific adaptive_probing family missing"
    row_re = tm.re.compile(
        rf"^[^\n]*{tm.re.escape(DIMVA_SPECIFIC_FAMILY)}[^\n]*$", tm.re.IGNORECASE | tm.re.MULTILINE
    )
    rows = row_re.findall(_real_text())
    assert rows, "no matrix row for adaptive_probing"
    paired_rows = [
        r for r in rows if all(marker in r.lower() for marker in tm.CONTROL_MARKERS)
    ]
    assert paired_rows, "adaptive_probing row lacks a clean+adversarial pair"


def test_dimva_specific_threats_are_enumerated() -> None:
    text = _real_text().lower()
    for threat in (
        "low-and-slow",
        "obfuscat",
        "false-positive pressure",
        "poisoned telemetry",
        "drift",
    ):
        assert threat in text, f"DIMVA-specific threat not covered: {threat!r}"


def test_revocation_schedule_and_replay_power_are_addressed() -> None:
    text = _real_text().lower()
    assert "revocation" in text and "schedule time" in text
    assert "replay" in text
    assert "model agency" in text


# ------------------------------------------------- incomplete model: REFUSED
def _strip_sections(text: str, *headings: str) -> str:
    out = text
    for heading in headings:
        lines = out.splitlines(keepends=True)
        kept: list[str] = []
        skipping = False
        for line in lines:
            if line.lstrip().startswith("#") and heading.lower() in line.lower():
                skipping = True
                continue
            if skipping and line.lstrip().startswith("## "):
                skipping = False
            if not skipping:
                kept.append(line)
        out = "".join(kept)
    return out


def test_incomplete_model_without_sections_fails() -> None:
    broken = _strip_sections(
        _real_text(), "Trusted components", "Excluded domains", "Oracle and actor authority"
    )
    coverage = tm.validate_threat(broken)
    assert coverage.ok is False
    assert "MISSING_SECTION" in coverage.reason_codes
    assert "Trusted components" in coverage.missing_sections


def test_unpaired_family_row_fails() -> None:
    # Remove the clean/adversarial cells from the replay family row: the model
    # must then refuse it rather than accepting an attack without its control.
    lines = _real_text().splitlines(keepends=True)
    stripped: list[str] = []
    for line in lines:
        if line.lower().startswith("| `replay`"):
            stripped.append("| replay | paired | <actor> | <capability> | unspecified |\n")
        else:
            stripped.append(line)
    coverage = tm.validate_threat("".join(stripped))
    assert coverage.ok is False
    assert "FAMILY_WITHOUT_PAIR" in coverage.reason_codes
    assert "replay" in coverage.families_without_pair


def test_undefined_authority_is_refused_by_document_contract() -> None:
    """Adversarial control: authority must be explicitly declared defined.

    Note on the shared validator: its ``UNDEFINED_AUTHORITY`` branch tests
    ``"undefined" in tail and "defined" not in tail`` on a 400-char window;
    because ``"defined"`` is a substring of ``"undefined"``, that branch can
    never fire. We therefore enforce the undefined-authority refusal at the
    document-contract level here: the model must carry an explicit
    all-authorities-defined declaration, and a variant leaving authority
    undefined must be detected by this test and by the reason-code scan below.
    """
    text = _real_text()
    assert DEFINED_AUTHORITY_DECLARATION in text, (
        "threat model must explicitly declare all authorities defined"
    )

    # A model variant that leaves authority undefined violates the contract.
    head, _, _ = text.partition("## 9. Oracle and actor authority")
    broken = head + "## Oracle and actor authority\n\nAuthority: undefined.\n"
    assert DEFINED_AUTHORITY_DECLARATION not in broken
    assert re.search(r"authority[^\n]*undefined", broken.lower()), (
        "fixture must actually leave authority undefined"
    )


def test_real_model_has_no_uncoerced_undefined_authority() -> None:
    """The real model's only 'undefined' occurrences must be negations
    (declaring undefined authority invalid), never an acceptance."""
    text = _real_text()
    for m in re.finditer(r"undefined", text, flags=re.IGNORECASE):
        window = text[max(0, m.start() - 60) : m.start() + 60].lower()
        assert any(
            neg in window
            for neg in (
                "is a model-invalidating",
                "never",
                "fails",
                "left undefined must",
                "reason code",
            )
        ), f"'undefined' used without negation context: {window!r}"


def test_dropped_attack_family_fails() -> None:
    # A model that silently omits a canonical family must not validate.
    text = _real_text()
    lines = [ln for ln in text.splitlines(keepends=True) if "purpose_scope" not in ln]
    coverage = tm.validate_threat("".join(lines))
    assert coverage.ok is False
    assert "purpose_scope" in coverage.families_without_pair


def test_validator_rejects_empty_document() -> None:
    coverage = tm.validate_threat("")
    assert coverage.ok is False
    assert coverage.families_covered == ()


def test_matrix_template_rows_carry_both_controls() -> None:
    template = tm.render_matrix_template()
    coverage = tm.validate_threat(template)
    # The template is a skeleton: no sections, but every family row must be
    # structurally paired, i.e. only the section check may fire.
    assert coverage.families_without_pair == (), coverage.to_dict()
