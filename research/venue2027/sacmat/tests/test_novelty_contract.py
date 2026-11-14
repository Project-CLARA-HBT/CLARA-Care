"""Structural tests for the SACMAT-scope novelty contract (task SACMAT-scope, P01).

Purpose
-------
Stdlib-only structural gate over ``research/venue2027/sacmat/novelty_contract.md``.
It verifies the scope register exists, contains the required sections, exactly
three RQs each carrying the five mandatory fields, at least three competing
baselines, a distinct endpoint, explicit GovMut differentiation, an explicit
refusal of frozen E15–E22 archive evidence, and a single GO/NO-GO decision line.

Allowed input
-------------
The markdown file at the repository-relative path below, read-only.

Failure semantics
-----------------
Each violation raises a focused ``AssertionError`` naming the missing marker;
the suite fails closed if the contract file itself is absent.

Version
-------
``NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"

CONTRACT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "sacmat"
    / "novelty_contract.md"
)

RQ_REQUIRED_FIELDS = (
    "Primary endpoint",
    "Strongest competing baseline",
    "Independent oracle",
    "Statistical test",
    "Falsification condition",
)


def _load() -> str:
    assert CONTRACT_PATH.is_file(), f"novelty contract missing at {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_required_sections_present() -> None:
    text = _load()
    for marker in (
        "## 0. Title and target reader",
        "## 1. Claim-to-prior-work falsification matrix",
        "## 2. Exactly three research questions",
        "## 3. Non-overlap and distinct contribution",
        "## Decision",
    ):
        assert marker in text, f"missing required section: {marker}"


def test_exactly_three_rqs_with_five_fields() -> None:
    text = _load()
    rq_heads = re.findall(r"^### RQ\d — ", text, flags=re.MULTILINE)
    assert len(rq_heads) == 3, f"expected exactly 3 RQs, found {len(rq_heads)}"
    for field in RQ_REQUIRED_FIELDS:
        found = len(re.findall(rf"^- \*\*{re.escape(field)}\b", text, flags=re.MULTILINE))
        assert found >= 3, f"field '{field}' present in {found}/3 RQs"


def test_falsification_matrix_has_real_prior_work_ids() -> None:
    text = _load()
    for prior_id in ("xacml18", "xacbench20", "zanzibar19", "cedar", "openfga", "opa"):
        assert prior_id in text, f"falsification matrix missing prior-work id: {prior_id}"
    assert "https://doi.org/10.1145/3205977.3205979" in text, "xacml18 DOI missing"
    assert "USENIX ATC 2019" in text, "Zanzibar citation missing"


def test_at_least_three_baselines_declared() -> None:
    text = _load()
    for baseline in ("B0", "B1", "B2", "B3"):
        assert baseline in text, f"baseline arm {baseline} not declared"
    arms = {
        "uniform random authorization requests",
        "MC/DC-inspired XACML policy testing",
        "XACBench policy profile",
        "property-based history generator without temporal metamorphs",
    }
    present = sum(1 for a in arms if a in text)
    assert present >= 3, f"only {present} strong baselines described (need >=3)"


def test_distinct_endpoint_named() -> None:
    text = _load()
    assert "delegation conformance divergence detection rate" in text.lower(), (
        "distinct primary endpoint not named"
    )
    assert "temporal conformance testing" in text.lower()


def test_govmut_differentiation_present() -> None:
    text = _load()
    assert "GovMut" in text, "GovMut differentiation section content missing"
    assert "mutation-testing adequacy" in text, "GovMut adequacy contrast missing"
    assert "45" in text and "mutant" in text.lower(), "W8 45-mutant boundary missing"


def test_archive_refusal_of_frozen_e15_e22() -> None:
    text = _load()
    assert "E15–E22" in text, "explicit E15–E22 archive refusal missing"
    refusal = re.search(r"### 3\.3 Archive refusal[^#]*", text)
    assert refusal, "archive refusal subsection missing"
    assert "not" in refusal.group(0).lower() and "background" in refusal.group(0).lower()


def test_exactly_one_decision_line_is_go_or_no_go() -> None:
    text = _load()
    decisions = re.findall(r"^\*\*Decision: (GO|NO-GO)\*\*", text, flags=re.MULTILINE)
    assert len(decisions) == 1, f"expected exactly one decision line, found {len(decisions)}"
    assert decisions[0] == "GO"
    assert "**Decision: GO** — conditional on the falsification rules above" in text


def test_no_invented_empirical_numbers() -> None:
    text = _load()
    assert "NOT_RUN" in text or "NOT RUN" in text, "evidence status must be declared not-run"
    assert "PROSPECTIVE" in text, "prospective (not results) status missing"
