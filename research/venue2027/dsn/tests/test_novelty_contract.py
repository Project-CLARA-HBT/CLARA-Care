"""Machine-checked structure test for the DSN 2027 novelty contract.

Purpose
-------
Enforce the required structure of
``research/venue2027/dsn/novelty_contract.md`` so the signed scope contract
cannot silently rot: every mandated section, all three RQs with all five
required fields, the blueprint baseline arms, the distinct-endpoint sentence,
the frozen-archive reuse refusal, and a go/no-go decision line must be
present. Pure stdlib parsing; no new dependencies.

Allowed input
-------------
The contract markdown file at repository-relative path
``research/venue2027/dsn/novelty_contract.md``, located from this test file's
position on disk.

Failure semantics
-----------------
Each check raises ``AssertionError`` with a stable message identifying the
missing structural element. No random, network, or filesystem writes.

Version
-------
``NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re
import unittest

NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO_ROOT / "research" / "venue2027" / "dsn" / "novelty_contract.md"

REQUIRED_SECTIONS = (
    "## 1. Paper title and target reader",
    "## 2. Claim-to-prior-work falsification matrix",
    "## 3. Research questions",
    "## 4. Scope statement and truly distinct endpoint",
    "## 5. Non-overlap declaration",
    "## 6. Go/no-go decision",
)

REQUIRED_RQ_FIELDS = (
    "Primary endpoint",
    "baseline",
    "oracle",
    "Statistical test",
    "Falsification condition",
)

REQUIRED_BASELINES = (
    "B0",
    "B1",
    "B2",
    "B3",
)

# Registry / literature ids that must appear as real citations in the matrix.
REQUIRED_CITATION_IDS = (
    "elle20",
    "silo13",
    "zanzibar19",
    "glhs-journal",
    "govred-rivf-2026",
    "assurance-soict-2026",
)

DISTINCT_ENDPOINT_PATTERN = re.compile(r"truly distinct endpoint", re.IGNORECASE)
ARCHIVE_REFUSAL_PATTERN = re.compile(r"not\s+reused as new evidence", re.IGNORECASE)
DECISION_PATTERN = re.compile(r"^\*\*Decision:\s*(GO|NO-GO)\*\*", re.MULTILINE)


def load_contract_text() -> str:
    assert CONTRACT_PATH.is_file(), f"contract missing: {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


class TestNoveltyContractStructure(unittest.TestCase):
    """Structural gate for the DSN-scope deliverable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = load_contract_text()

    def test_all_required_section_headings_present(self) -> None:
        for heading in REQUIRED_SECTIONS:
            self.assertIn(heading, self.text, f"missing section: {heading}")

    def test_paper_title_present(self) -> None:
        self.assertIn(
            "Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations",
            self.text,
            "paper title missing",
        )
        self.assertIn("Target reader", self.text, "target reader missing")

    def test_falsification_matrix_has_required_rows(self) -> None:
        matrix = self._section_between(
            "## 2. Claim-to-prior-work falsification matrix",
            "## 3. Research questions",
        )
        rows = [line for line in matrix.splitlines() if line.strip().startswith("| C")]
        self.assertGreaterEqual(len(rows), 3, "falsification matrix needs >= 3 claim rows")
        header = next(
            (line for line in matrix.splitlines() if "Strongest competing explanation" in line),
            "",
        )
        for column in (
            "Claim",
            "Strongest competing explanation",
            "Published prior work",
            "Why the claim survives",
            "What WOULD falsify it",
        ):
            self.assertIn(column, header, f"matrix column missing: {column}")

    def test_matrix_cites_real_registry_ids(self) -> None:
        for cite in REQUIRED_CITATION_IDS:
            self.assertIn(f"`{cite}`", self.text, f"missing citation id: {cite}")

    def test_exactly_three_rqs_with_all_five_fields(self) -> None:
        rq_section = self._section_between("## 3. Research questions", "## 4. Scope statement")
        rq_rows = [line for line in rq_section.splitlines() if re.match(r"^\| RQ[123] \|", line)]
        self.assertEqual(len(rq_rows), 3, f"expected exactly 3 RQ rows, got {len(rq_rows)}")
        for field in REQUIRED_RQ_FIELDS:
            self.assertIn(field, rq_section, f"RQ field missing: {field}")
        for idx in ("RQ1", "RQ2", "RQ3"):
            self.assertTrue(
                any(f"| {idx} |" in row for row in rq_rows),
                f"{idx} row missing",
            )

    def test_baseline_arms_named(self) -> None:
        for arm in REQUIRED_BASELINES:
            self.assertIn(f"**{arm}**", self.text, f"baseline arm missing: {arm}")

    def test_distinct_endpoint_sentence_present(self) -> None:
        scope = self._section_between("## 4. Scope statement", "## 5. Non-overlap declaration")
        self.assertIsNotNone(
            DISTINCT_ENDPOINT_PATTERN.search(scope),
            "scope section lacks an explicit truly-distinct-endpoint sentence",
        )
        for anchor in (
            "GLHS R4",
            "COMPSAC",
            "IFIP",
            "PoPETs",
            "PST",
            "AIME",
            "SACMAT",
            "DIMVA",
            "ACNS",
        ):
            self.assertIn(anchor, scope, f"scope must contrast with: {anchor}")

    def test_archive_reuse_refusal_present(self) -> None:
        non_overlap = self._section_between(
            "## 5. Non-overlap declaration", "## 6. Go/no-go decision"
        )
        self.assertIn("E15", non_overlap, "archive ids missing")
        self.assertIn("E22", non_overlap, "archive ids missing")
        self.assertIsNotNone(
            ARCHIVE_REFUSAL_PATTERN.search(non_overlap),
            "explicit frozen-archive reuse refusal missing",
        )
        self.assertIn("reuses_archive: []", non_overlap)

    def test_decision_line_present(self) -> None:
        match = DECISION_PATTERN.search(self.text)
        self.assertIsNotNone(match, "missing '**Decision: GO|NO-GO**' line")
        self.assertEqual(match.group(1), "GO", "decision must be GO for this contract")

    def test_no_invented_empirical_numbers(self) -> None:
        forbidden = re.compile(
            r"\b(p\s*=\s*0\.\d+|p95\s*=\s*\d+|p99\s*=\s*\d+|"
            r"reduced? by \d+(\.\d+)?%|improved? by \d+(\.\d+)?%)\b",
            re.IGNORECASE,
        )
        self.assertIsNone(
            forbidden.search(self.text),
            "contract must remain a design artifact without empirical results",
        )

    # -- helpers ---------------------------------------------------------

    def _section_between(self, start: str, end: str) -> str:
        begin = self.text.index(start)
        stop = self.text.index(end)
        self.assertLess(begin, stop, f"section order broken: {start!r}")
        return self.text[begin:stop]


if __name__ == "__main__":
    unittest.main()
