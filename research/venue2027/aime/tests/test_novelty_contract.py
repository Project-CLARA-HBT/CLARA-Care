"""Structural tests for the AIME 2027 novelty contract (task AIME-scope).

Purpose
-------
Stdlib-only structural gate for ``research/venue2027/aime/novelty_contract.md``.
It checks the required sections, exactly three RQs with five fields each, the
baseline set, the distinct primary endpoint, HEALTHINF differentiation, refusal
of the frozen E15-E22 archive, the GO/NO-GO decision line, and the mandatory
clinical-venue language (synthetic-only, no real PHI, blinded independent
clinician review, and "synthetic action correctness is NOT clinical efficacy").

Allowed input
-------------
The contract markdown file at repository path
``research/venue2027/aime/novelty_contract.md``.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``NOVELTY_CONTRACT_``; pytest reports the failing check directly.

Version
-------
``NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

NOVELTY_CONTRACT_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO_ROOT / "research" / "venue2027" / "aime" / "novelty_contract.md"


def _load_contract() -> str:
    assert CONTRACT_PATH.is_file(), f"NOVELTY_CONTRACT_MISSING: {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_required_sections_present() -> None:
    text = _load_contract()
    for heading in (
        "Title and target reader",
        "Claim-to-prior-work falsification matrix",
        "Distinct contribution and distinct primary endpoint",
        "Research questions and estimands",
        "Non-overlap firewall",
        "Decision",
    ):
        assert heading in text, f"NOVELTY_CONTRACT_MISSING_SECTION: {heading}"


def test_exactly_three_rqs_with_five_fields() -> None:
    text = _load_contract()
    rq_ids = re.findall(r"^### RQ(\d) —", text, flags=re.MULTILINE)
    assert rq_ids == ["1", "2", "3"], f"NOVELTY_CONTRACT_RQ_SET: {rq_ids}"

    rq_bodies = re.split(r"^### RQ\d —", text, flags=re.MULTILINE)[1:]
    assert len(rq_bodies) == 3, "NOVELTY_CONTRACT_RQ_BODIES"
    for body in rq_bodies:
        body = body.split("### ", 1)[0]
        for field in (
            "Primary endpoint:",
            "Strongest competing baseline:",
            "Independent oracle:",
            "Statistical test:",
            "Falsification condition:",
        ):
            assert field in body, f"NOVELTY_CONTRACT_RQ_FIELD_MISSING: {field}"


def test_at_least_three_baselines_present() -> None:
    text = _load_contract()
    baseline_section = text.split("## 6. Baseline arms", 1)[1]
    baseline_section = baseline_section.split("## 7.", 1)[0]
    arms = re.findall(r"^- \*\*(B\d)\*\* —", baseline_section, flags=re.MULTILINE)
    assert len(set(arms)) >= 3, f"NOVELTY_CONTRACT_BASELINES: {arms}"
    for arm in ("B0", "B1", "B3", "B4"):
        assert arm in arms, f"NOVELTY_CONTRACT_BASELINE_MISSING: {arm}"


def test_distinct_endpoint_declared() -> None:
    text = _load_contract()
    assert "unsafe clinical action rate under consent/medication history changes" in text, (
        "NOVELTY_CONTRACT_ENDPOINT_MISSING"
    )
    # Must be explicitly distinguished from every sibling venue endpoint.
    for sibling in (
        "forbidden commit rate under dependency-complete schedules",
        "revoked-context re-disclosure rate",
        "replay acceptance rate across purpose/delegation lineage",
        "delegation conformance divergence detection rate",
        "evidence-boundary coverage matrix",
        "crash-consistency violation rate after fault injection",
        "probing detection AUC at fixed false-positive budget",
        "forensic reconstructability score",
    ):
        assert sibling in text, f"NOVELTY_CONTRACT_ENDPOINT_DISTINCTION: {sibling}"


def test_healthinf_differentiation() -> None:
    text = _load_contract()
    assert "HEALTHINF" in text, "NOVELTY_CONTRACT_HEALTHINF_ABSENT"
    # Clinical task quality vs governance protocol distinction must be explicit.
    assert "governance protocol" in text, "NOVELTY_CONTRACT_HEALTHINF_PROTOCOL"
    assert "clinical task quality" in text, "NOVELTY_CONTRACT_HEALTHINF_TASK_QUALITY"
    assert "not re-evaluated here" in text, "NOVELTY_CONTRACT_HEALTHINF_NOT_REUSED"


def test_archive_refusal_e15_e22() -> None:
    text = _load_contract()
    assert "E15" in text and "E22" in text, "NOVELTY_CONTRACT_ARCHIVE_IDS"
    assert re.search(r"E15[–-]E22", text), "NOVELTY_CONTRACT_ARCHIVE_RANGE"
    assert "are refused as new evidence" in text, "NOVELTY_CONTRACT_ARCHIVE_REFUSAL"
    assert "background only" in text.lower(), "NOVELTY_CONTRACT_ARCHIVE_BACKGROUND"
    # No AIME sentence may lean on the frozen archive.
    assert "reuses_archive` remains empty" in text, "NOVELTY_CONTRACT_ARCHIVE_EMPTY"


def test_decision_line_go_or_no_go() -> None:
    text = _load_contract()
    match = re.search(r"^\*\*Decision: (GO|NO-GO)\*\*", text, flags=re.MULTILINE)
    assert match is not None, "NOVELTY_CONTRACT_DECISION_LINE"
    assert match.group(1) == "GO", "NOVELTY_CONTRACT_DECISION_NOT_GO"


def test_synthetic_only_and_no_clinical_efficacy_language() -> None:
    text = _load_contract()
    lowered = text.lower()
    assert "no real phi" in lowered, "NOVELTY_CONTRACT_NO_REAL_PHI"
    assert "synthetic vignettes only" in lowered, "NOVELTY_CONTRACT_SYNTHETIC_ONLY"
    assert "blinded independent clinician review" in lowered, "NOVELTY_CONTRACT_BLINDED_REVIEW"
    assert "synthetic action correctness is not clinical efficacy" in lowered, (
        "NOVELTY_CONTRACT_NO_EFFICACY_CLAIM"
    )
    # Hard negative: the contract must not contain efficacy-style claim language.
    for forbidden in ("clinically effective", "proves clinical efficacy"):
        assert forbidden not in lowered, f"NOVELTY_CONTRACT_FORBIDDEN_PHRASE: {forbidden}"
    # No invented empirical numbers: no percentage or p-value style results.
    assert not re.search(r"\b\d+(\.\d+)?%", text), "NOVELTY_CONTRACT_PERCENTAGE_FOUND"
    assert not re.search(r"\bp\s*[<>=]", text, flags=re.IGNORECASE), "NOVELTY_CONTRACT_PVALUE"
