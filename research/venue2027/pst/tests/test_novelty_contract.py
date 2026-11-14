"""Structural tests for the PST-scope novelty contract.

Purpose
-------
Verify, with the standard library only, that
``research/venue2027/pst/novelty_contract.md`` contains the frozen scope
structure required by ``VENUES/pst/TASKS/PST-scope.md``: title and target
reader, a claim-to-prior-work falsification matrix with real prior-work ids,
exactly three RQs with the five required fields, at least three baselines, a
distinct reconstructability endpoint, the PoPETs differentiation, the archive
refusal for frozen E15-E22, the access-control boundary, and the decision
line.

Allowed input: the contract markdown file read read-only from the repository.
Failure semantics: any missing structure fails an assertion with a stable
message; no network, clock, randomness, or external dependency is used.

Version: 1.0.0
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "pst" / "novelty_contract.md"

RQ_REQUIRED_FIELDS = (
    "Primary endpoint",
    "Strongest competing baseline",
    "Independent oracle",
    "Statistical test",
    "Falsification condition",
)


def _load_contract() -> str:
    if not CONTRACT_PATH.is_file():
        raise AssertionError(f"novelty contract missing at {CONTRACT_PATH}")
    return CONTRACT_PATH.read_text(encoding="utf-8")


class TestNoveltyContractStructure(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _load_contract()

    # ----------------------------------------------------- title and reader
    def test_title_and_target_reader_present(self) -> None:
        self.assertIn("**Title:** ReceiptMin", self.text)
        self.assertIn("**Target reader:**", self.text)

    # ------------------------------------------------------- falsification matrix
    def test_falsification_matrix_with_real_prior_work_ids(self) -> None:
        section = self._section("Claim-to-prior-work falsification matrix")
        self.assertIn("Prior work (id)", section)
        ledger_ids = [
            "ct9162",
            "macaroons14",
            "fhir5",
            "muse",
            "rats9334",
            "nistabac",
            "zanzibar19",
            "who21",
            "glhs-journal",
        ]
        for rid in ledger_ids:
            self.assertIn(f"`{rid}`", section, f"prior-work id {rid} missing")
        self.assertGreaterEqual(section.count("\n| CL-"), 3)

    def test_falsification_matrix_rows_have_failure_tests(self) -> None:
        section = self._section("Claim-to-prior-work falsification matrix")
        self.assertIn("Falsification test", section)

    # ------------------------------------------------------------------ RQs
    def test_exactly_three_rqs_with_five_fields(self) -> None:
        rq_sections = re.findall(r"^### (RQ\d)", self.text, flags=re.MULTILINE)
        self.assertEqual(rq_sections, ["RQ1", "RQ2", "RQ3"])
        bodies = self.text.split("### RQ")[1:]
        self.assertEqual(len(bodies), 3)
        for body in bodies:
            for field in RQ_REQUIRED_FIELDS:
                self.assertIn(f"**{field}:**", body, f"missing field {field}")

    def test_rq_statistical_tests_are_concrete(self) -> None:
        for body in self.text.split("### RQ")[1:]:
            self.assertRegex(body, r"\*\*Statistical test:\*\*.*(permutation|bootstrap)")

    # -------------------------------------------------------------- baselines
    def test_at_least_three_strong_baselines(self) -> None:
        section = self._section("Baseline arms")
        for arm in ("B1", "B2", "B3"):
            self.assertIn(f"| {arm} |", section, f"baseline {arm} missing")
        self.assertEqual(len(re.findall(r"^\| B\d \|", section, flags=re.MULTILINE)), 5)

    # ------------------------------------------------------ distinct endpoint
    def test_primary_endpoint_is_a_reconstructability_measure(self) -> None:
        self.assertIn("forensic reconstructability score", self.text)
        endpoint_section = self._section("Distinct contribution and primary endpoint")
        self.assertIn("reconstruction-versus-linkability", endpoint_section)
        self.assertIn("reconstructability measure", endpoint_section)
        # The endpoint must quantify forensic reconstruction, not only privacy.
        self.assertRegex(
            endpoint_section,
            r"[Ff]orensic [Rr]econstructability|[Ff]orensic [Qq]uery [Aa]nswerability",
        )

    # ------------------------------------------------------ PoPETs separation
    def test_popets_differentiation(self) -> None:
        section = self._section("Non-overlap with the PoPETs 2027 study")
        self.assertIn("future", section)
        self.assertIn("revoked-context re-disclosure rate", section)
        self.assertIn("post hoc audit-event reconstruction", section)

    # ------------------------------------------------------- archive refusal
    def test_frozen_e15_e22_refused_as_new_evidence(self) -> None:
        section = self._section("Archive refusal")
        self.assertIn("E15", section)
        self.assertIn("are refused as new evidence", section)
        self.assertIn("reuses_archive: []", self.text)

    # ------------------------------------------------- access-control boundary
    def test_no_new_access_control_mechanism_claimed(self) -> None:
        self.assertIn("does not propose a new access-control mechanism", self.text)
        forbidden = re.findall(
            r"we (?:introduce|propose|present) a new access-control"
            r"|novel access-control mechanism"
            r"|new authorization enforcement mechanism",
            self.text,
            flags=re.IGNORECASE,
        )
        # The boundary section may quote the forbidden phrases; those quotes
        # must appear only inside the prohibition context, never as claims.
        boundary = self._section("Access-control boundary")
        quoted = re.findall(
            r"we (?:introduce|propose|present) a new access-control"
            r"|novel access-control mechanism"
            r"|new authorization enforcement mechanism",
            boundary,
            flags=re.IGNORECASE,
        )
        self.assertEqual(forbidden, quoted)
        self.assertTrue(quoted, "boundary section must name the forbidden claim patterns")
        lower_boundary = boundary.lower()
        for phrase in quoted:
            pos = lower_boundary.find(phrase.lower())
            self.assertGreaterEqual(pos, 0)
            before = lower_boundary[max(0, pos - 160) : pos]
            self.assertRegex(
                before,
                r"phrases such as|prohibited claim patterns|forbids presenting",
                f"forbidden pattern {phrase!r} not inside a prohibition",
            )

    # --------------------------------------------------------------- decision
    def test_decision_line_present(self) -> None:
        decision_lines = [
            line.strip() for line in self.text.splitlines() if line.strip().startswith("Decision:")
        ]
        self.assertEqual(len(decision_lines), 1, f"expected one decision line: {decision_lines}")
        self.assertRegex(decision_lines[0], r"^Decision: (GO|NO-GO)$")

    # ------------------------------------------------------------ no numbers
    def test_contract_contains_no_measured_results(self) -> None:
        forbidden = re.findall(r"\b\d+\.\d+%\b", self.text)
        self.assertEqual(
            forbidden, [], f"contract must not contain measured percentages: {forbidden}"
        )

    # ------------------------------------------------------------ helpers
    def _section(self, heading: str) -> str:
        match = re.search(
            rf"^#+ {re.escape(heading)}.*?$(.*?)(?=^#+ |\Z)",
            self.text,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, f"section heading not found: {heading}")
        return match.group(0)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
