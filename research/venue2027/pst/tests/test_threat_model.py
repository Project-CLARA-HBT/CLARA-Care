"""Tests for the PST-threat threat model.

Purpose
-------
Verify, with the standard library only, that
``research/venue2027/pst/threat_model.md`` passes the shared program contract
validator ``research/venue2027/_shared/tools/threat_model.py``
(``validate_threat()->ThreatCoverage``), that an incomplete threat model is
refused with stable reason codes, and that the PST-specific
forensic-omission family exists in the attack/control matrix with a paired
clean and adversarial case.

Allowed input: the threat-model markdown file read read-only from the
repository. Failure semantics: any missing structure fails an assertion with a
stable message; no network, clock, randomness, or external dependency is used.

Version: 1.0.0
"""

from __future__ import annotations

import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import threat_model as tm  # noqa: E402

THREAT_PATH = pathlib.Path(__file__).resolve().parents[1] / "threat_model.md"

PST_SPECIFIC_FAMILIES = (
    "forensic_omission",
    "selective_omission",
    "record_tampering",
    "linkability_leakage",
    "timestamp_inference",
    "receipt_forgery",
)


def _load_threat_model() -> str:
    if not THREAT_PATH.is_file():
        raise AssertionError(f"threat model missing at {THREAT_PATH}")
    return THREAT_PATH.read_text(encoding="utf-8")


class TestThreatModelPassesSharedValidator(unittest.TestCase):
    """The real file must satisfy the shared validate_threat contract."""

    def setUp(self) -> None:
        self.text = _load_threat_model()
        self.coverage = tm.validate_threat(self.text)

    def test_shared_validator_ok(self) -> None:
        self.assertTrue(
            self.coverage.ok,
            f"validator refused threat model: {self.coverage.reason_codes}",
        )
        self.assertEqual(self.coverage.reason_codes, ())
        self.assertEqual(self.coverage.missing_sections, ())
        self.assertEqual(self.coverage.families_without_pair, ())

    def test_all_canonical_families_covered_with_pairs(self) -> None:
        self.assertEqual(
            self.coverage.families_covered, tuple(sorted(tm.ATTACK_FAMILIES))
        )
        self.assertEqual(set(tm.ATTACK_FAMILIES) & set(PST_SPECIFIC_FAMILIES), set())

    def test_required_sections_present_as_headings(self) -> None:
        for section in tm.REQUIRED_SECTIONS:
            self.assertTrue(
                tm._section_present(self.text, section),
                f"required section heading missing: {section}",
            )


class TestIncompleteModelRefused(unittest.TestCase):
    """Deformations of the model must fail with stable reason codes."""

    def test_missing_section_refused(self) -> None:
        text = "\n".join(
            line
            for line in _load_threat_model().splitlines()
            if "## Trusted components" not in line
        )
        result = tm.validate_threat(text)
        self.assertFalse(result.ok)
        self.assertIn("MISSING_SECTION", result.reason_codes)
        self.assertIn("Trusted components", result.missing_sections)

    def test_family_without_pair_refused(self) -> None:
        text = "\n".join(
            line for line in _load_threat_model().splitlines() if "| replay |" not in line
        )
        result = tm.validate_threat(text)
        self.assertFalse(result.ok)
        self.assertIn("FAMILY_WITHOUT_PAIR", result.reason_codes)
        self.assertIn("replay", result.families_without_pair)

    def test_empty_document_refused(self) -> None:
        result = tm.validate_threat("")
        self.assertFalse(result.ok)
        self.assertIn("MISSING_SECTION", result.reason_codes)
        self.assertEqual(result.families_covered, ())


class TestForensicOmissionFamily(unittest.TestCase):
    """PST-specific family: audit minimization erasing needed evidence."""

    def setUp(self) -> None:
        self.text = _load_threat_model()
        section = self._matrix_section()
        self.rows = [line for line in section.splitlines() if line.startswith("| ")]

    def test_forensic_omission_family_exists_with_paired_cases(self) -> None:
        rows = [row for row in self.rows if "forensic_omission" in row]
        self.assertGreaterEqual(len(rows), 1, "forensic_omission family row missing")
        for row in rows:
            self.assertIn("clean", row.lower(), "clean control missing in row")
            self.assertIn("adversarial", row.lower(), "adversarial case missing in row")

    def test_forensic_omission_maps_to_case_matrix_anchors(self) -> None:
        row = next(row for row in self.rows if "forensic_omission" in row)
        self.assertIn("PST-CASE-01", row)
        self.assertIn("PST-CASE-05", row)

    def test_forensic_omission_declares_indeterminate_not_false_success(self) -> None:
        row = next(row for row in self.rows if "forensic_omission" in row)
        self.assertIn("INDETERMINATE", row)
        self.assertIn("RECONSTRUCT", row)

    def test_forensic_omission_reason_code_declared(self) -> None:
        self.assertIn("FORENSIC_OMISSION", self.text)
        # The failure-semantics table must classify it as incompleteness.
        self.assertRegex(
            self.text, r"\| `FORENSIC_OMISSION` \|.*incompleteness", "forensic-omission "
            "reason code must be counted as incompleteness, never a pass",
        )

    def test_all_pst_specific_families_present(self) -> None:
        for family in PST_SPECIFIC_FAMILIES:
            rows = [row for row in self.rows if family in row]
            self.assertGreaterEqual(
                len(rows), 1, f"PST-specific family row missing: {family}"
            )

    def _matrix_section(self) -> str:
        start = self.text.index("## Attack family and control matrix")
        end = self.text.index("## Failure semantics and stable reason codes")
        return self.text[start:end]


class TestDeclaredModelSemantics(unittest.TestCase):
    """Capabilities, excluded domains, time model and authority are explicit."""

    def setUp(self) -> None:
        self.text = _load_threat_model()

    def test_attacker_capabilities_declared_with_boundaries(self) -> None:
        section = self._section("Attacker and observer capabilities")
        for actor in ("P1", "P2", "P4", "P5", "P6"):
            self.assertIn(actor, section, f"actor {actor} not declared")
        self.assertIn("auxiliary", section)
        self.assertIn("read-only", section)

    def test_trusted_components_declare_failure_behavior(self) -> None:
        section = self._section("Trusted components")
        for component in ("T1", "T2", "T3", "T4", "T5"):
            self.assertIn(component, section, f"component {component} not declared")
        self.assertIn("append-only", section)
        self.assertIn("retention", section)
        self.assertIn("fail closed", section)

    def test_excluded_domains_declared_with_residual_risk(self) -> None:
        section = self._section("Excluded domains")
        self.assertIn("full disk", section)
        self.assertIn("backups", section)
        self.assertIn("Residual risk", section)

    def test_revocation_and_schedule_time_declared(self) -> None:
        self.assertIn("Revocation instant", self.text)
        self.assertIn("Retention deadline", self.text)
        self.assertIn("retention deadline", self.text)

    def test_model_agency_and_replay_power_declared(self) -> None:
        self.assertIn("**Model agency.**", self.text)
        self.assertIn("**Resubmission power.**", self.text)

    def test_authority_is_defined_not_undefined(self) -> None:
        section = self._section("Oracle and actor authority")
        self.assertIn("Defined", section)
        self.assertIn("sole ground truth", section)
        self.assertIn("never repaired post hoc", section)

    def test_reason_codes_table_declares_unknown_class(self) -> None:
        self.assertIn("| `UNKNOWN` |", self.text)
        self.assertIn("never coerced", self.text)

    def test_no_measured_results_claimed(self) -> None:
        import re

        forbidden = re.findall(r"\b\d+\.\d+%\b", self.text)
        self.assertEqual(
            forbidden, [], f"threat model must not contain measured percentages: {forbidden}"
        )

    def _section(self, heading: str) -> str:
        start = self.text.index(f"## {heading}")
        rest = self.text[start + len(f"## {heading}") :]
        next_heading = rest.find("\n## ")
        return rest[:next_heading] if next_heading >= 0 else rest


if __name__ == "__main__":
    unittest.main()
