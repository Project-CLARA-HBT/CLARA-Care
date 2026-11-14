"""Structural tests for the ACNS threat model (task ACNS-threat).

Purpose
-------
Validate that ``research/venue2027/acns/threat_model.md`` is a structurally
complete, machine-checkable threat chapter for the ACNS SoK: it must pass the
shared coverage validator (``_shared/tools/threat_model.py``), declare SoK
scope with an explicit no-new-mechanism boundary, cover the mandated attack
families with paired clean+adversarial matrix rows, name trusted components
and excluded domains, define revocation/schedule-time semantics, model agency
and artifact re-use power, an evidence-boundary gap register, and defined
oracle/actor authority (undefined authority must be refused, never defaulted).

Allowed input: the threat-model markdown file and the shared validator module,
read-only. No candidate implementation is imported; the validator is shared
infrastructure, not the system under study.

Failure semantics: AssertionError with a stable message per violated section.
Version: clara.venue2027.acns.test-threat-model.v1
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import threat_model as tm  # noqa: E402

THREAT_PATH = pathlib.Path(__file__).resolve().parents[1] / "threat_model.md"

SOK_MARKERS = ("Systematization of Knowledge", "SoK")
ATTACK_SURFACE_MARKERS = (
    "forged provider receipts",
    "attestation-level downgrade",
    "evidence-boundary gap",
    "unsupported trust transitivity",
    "timestamp-only",
    "incomplete disclosure",
)
CAPABILITY_MARKERS = ("A1", "A4", "A5", "A7")
TRUSTED_COMPONENT_MARKERS = ("TC1", "TC3", "TC5")
EXCLUDED_DOMAIN_MARKERS = ("ED1", "ED6")
SIBLING_DECLARATIONS = ("IFIP SEC", "DIMVA")


def _threat_text() -> str:
    return THREAT_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+.*{re.escape(heading)}.*?(?=^##\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"section {heading!r} not found"
    return match.group(0)


def test_threat_model_exists_and_passes_shared_validator() -> None:
    text = _threat_text()
    assert THREAT_PATH.is_file(), "threat_model.md missing"
    result = tm.validate_threat(text)
    assert result.ok is True, f"shared validator refused model: {result.reason_codes}"
    assert set(result.families_covered) == set(tm.ATTACK_FAMILIES), (
        f"every registered family must carry a paired row, missing: "
        f"{set(tm.ATTACK_FAMILIES) - set(result.families_covered)}"
    )


def test_declares_sok_scope_and_no_new_mechanism() -> None:
    text = _threat_text()
    assert all(m in text for m in SOK_MARKERS), "SoK scope not declared"
    assert (
        "no new mechanism" in text.lower()
    ), "SoK scope must explicitly disclaim a new mechanism"
    for marker in ATTACK_SURFACE_MARKERS:
        assert marker in text, f"attestation-evidence attack surface {marker!r} absent"


def test_attacker_and_observer_capabilities_declared() -> None:
    text = _threat_text()
    section = _section(text, "Attacker and observer capabilities")
    for marker in CAPABILITY_MARKERS:
        assert re.search(rf"\*\*{marker}\b", section), f"capability axis {marker} missing"
    assert "model agency" in section.lower(), "model-agency capability missing"
    assert "capture-and-reuse" in section.lower(), "artifact re-use (replay) power missing"
    assert "Observer positions" in section, "observer-position table missing"
    for evidence_class in (
        "Assembly",
        "Egress",
        "Transport acknowledgment",
        "receipt",
        "Execution trace",
        "Semantic consumption",
    ):
        assert evidence_class in section, f"evidence class {evidence_class!r} not observed"


def test_paired_matrix_covers_clean_and_adversarial_per_family() -> None:
    text = _threat_text()
    section = _section(text, "Attack family and control matrix")
    for family in tm.ATTACK_FAMILIES:
        row_matches = [
            line for line in section.splitlines() if family in line.lower() and "|" in line
        ]
        assert row_matches, f"matrix row for {family} missing"
        row = row_matches[0].lower()
        assert "clean:" in row, f"{family}: clean control cell missing"
        assert "adversarial:" in row, f"{family}: adversarial case cell missing"
        assert "reject" in row, f"{family}: adversarial cell must expect a REJECT verdict"


def test_downgrade_family_has_witness_boundaries() -> None:
    text = _threat_text()
    assert (
        "attestation-level downgrade" in text.lower()
    ), "attestation-level downgrade family absent"
    downgrade = re.findall(r"^\| G\d+ \|(?:.*\|){3}", text, flags=re.MULTILINE)
    assert len(downgrade) >= 9, f"evidence-boundary gap register too small: {len(downgrade)}"
    for gap_id in ("G1", "G2", "G5", "G9"):
        assert re.search(rf"^\| {gap_id} \|", text, flags=re.MULTILINE), f"gap {gap_id} missing"


def test_trusted_components_and_excluded_domains_declared() -> None:
    text = _threat_text()
    trusted = _section(text, "Trusted components")
    for marker in TRUSTED_COMPONENT_MARKERS:
        assert marker in trusted, f"trusted component {marker} missing"
    assert "pinned" in trusted.lower(), "attestation roots must be pinned"
    excluded = _section(text, "Excluded domains")
    for marker in EXCLUDED_DOMAIN_MARKERS:
        assert marker in excluded, f"excluded domain {marker} missing"
    assert (
        "hardware root" in excluded.lower()
    ), "hardware root-of-trust compromise must be explicitly excluded"


def test_revocation_and_schedule_time_defined() -> None:
    text = _threat_text()
    section = _section(text, "Revocation and schedule time")
    for concept in ("mint time", "verification time", "revocation lag", "schedule boundar"):
        assert concept in section.lower(), f"schedule concept {concept!r} missing"
    assert re.search(r"revocation_timing", text), "revocation_timing family absent"


def test_oracle_and_actor_authority_defined_not_undefined() -> None:
    text = _threat_text()
    section = _section(text, "Oracle and actor authority")
    assert "UNDEFINED_AUTHORITY" in text, "undefined-authority handling must be named"
    assert "defined explicitly" in section.lower(), "authority map must be declared as defined"
    assert "fails closed" in section.lower() or "fail" in section.lower(), (
        "undefined authority must never default to a safe-looking outcome"
    )
    verdicts = re.findall(r"\b(REJECT|PASS|INDETERMINATE|BLOCKED)\b", section)
    assert "BLOCKED" in verdicts, "undefined-authority outcome must route to BLOCKED"


def test_empirical_outcomes_routed_through_run_manifest() -> None:
    text = _threat_text()
    assert (
        "artifacts/venue2027/acns/<run_id>/manifest.json" in text
    ), "empirical values must route through the run manifest"
    kappa_claims = re.findall(r"[Kk]appa[^\n]*?(\d+\.\d+)", text)
    assert not kappa_claims, f"design-time document must not assert kappa values: {kappa_claims}"


def test_scope_guard_against_sibling_studies_intact() -> None:
    text = _threat_text()
    for sibling in SIBLING_DECLARATIONS:
        assert sibling in text, f"sibling study {sibling} not disclosed"
    assert "no detection/prevention rate" in text.lower(), (
        "witnesses must not be presented as a detection/prevention mechanism"
    )
    assert "instruments of falsification" in text, "witnesses must be declared as SoK instruments"
