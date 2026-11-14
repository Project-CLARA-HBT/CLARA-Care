"""Structural test for the COMPSAC-scope novelty contract.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/novelty_contract.md`` satisfies
the P01 scope gate: required sections, exactly three RQs with all five required
fields, the five blueprint baseline arms, the truly-distinct-endpoint sentence,
DSN differentiation, frozen-archive refusal, and an explicit GO/NO-GO decision.

Allowed input
-------------
Read-only access to the contract file and the worktree root. No network, no DB.

Failure semantics
-----------------
Each check fails with an assertion message naming the missing contract element;
no silent passes. Test is stdlib-only (no pytest fixtures beyond plain asserts).

Version
-------
``compsac-novelty-contract-test-v1``
"""

from __future__ import annotations

import pathlib
import re

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "novelty_contract.md"

RQ_SECTIONS = ("RQ1", "RQ2", "RQ3")

RQ_REQUIRED_FIELDS = (
    "Primary endpoint",
    "Strongest competing baseline",
    "Independent oracle",
    "Statistical test",
    "Falsification condition",
)

BLUEPRINT_BASELINES = (
    "B0",  # global-profile version OCC
    "B1",  # Silo-style entity readset OCC with commit-time validation
    "B2",  # PostgreSQL SERIALIZABLE (SSI)
    "B3",  # entity-OCC without semantic dependency closure (ablation)
    "B4",  # proposed dependency-complete scope-local OCC (candidate)
)

BASELINE_NAMES = (
    "global-profile version OCC",
    "Silo-style entity readset OCC",
    "PostgreSQL SERIALIZABLE",
    "entity-OCC without semantic dependency closure",
    "dependency-complete scope-local OCC",
)

TRULY_DISTINCT_ENDPOINT_SENTENCE = (
    "automatically derived, semantically required cross-resource dependencies "
    "for AI-generated clinical writes, quantified as a safety/throughput frontier"
)


def _contract_text() -> str:
    assert CONTRACT.is_file(), f"novelty contract missing at {CONTRACT}"
    return CONTRACT.read_text(encoding="utf-8")


def test_required_top_level_sections_present() -> None:
    text = _contract_text()
    for marker in (
        "Paper title",
        "Target reader",
        "Scope paragraph",
        "Claim-to-prior-work falsification matrix",
        "Research questions",
        "Non-overlap",
        "DSN differentiation",
        "Frozen-archive refusal",
        "Go/No-Go decision",
    ):
        assert marker in text, f"missing required section marker: {marker}"


def test_target_reader_named() -> None:
    text = _contract_text()
    assert "Target reader:" in text, "target reader not stated"


def test_exactly_three_rqs_with_all_five_fields() -> None:
    text = _contract_text()
    rq_headers = re.findall(r"^### (RQ\d)", text, flags=re.MULTILINE)
    assert rq_headers == list(RQ_SECTIONS), (
        f"expected exactly RQ1-RQ3 subsections, found: {rq_headers}"
    )
    for rq in RQ_SECTIONS:
        start = text.index(f"### {rq}")
        next_markers = [
            text.index(f"### {n}") for n in RQ_SECTIONS if text.index(f"### {n}") > start
        ]
        end = min(next_markers) if next_markers else len(text)
        body = text[start:end]
        for field in RQ_REQUIRED_FIELDS:
            assert f"**{field}:**" in body, f"{rq} missing field: {field}"


def test_five_blueprint_baseline_arms_named() -> None:
    text = _contract_text()
    for arm in BLUEPRINT_BASELINES:
        assert re.search(rf"\b{arm}\b", text), f"baseline arm {arm} not named"
    for name in BASELINE_NAMES:
        assert name in text, f"baseline name missing: {name}"


def test_prior_work_ids_present() -> None:
    text = _contract_text()
    for prior in ("silo13", "elle20", "zanzibar19", "macaroons14", "Ports & Grittner"):
        assert prior in text, f"real prior-work id missing: {prior}"


def test_truly_distinct_endpoint_sentence_present() -> None:
    text = _contract_text()
    assert TRULY_DISTINCT_ENDPOINT_SENTENCE in text, (
        "truly-distinct-endpoint sentence missing or altered"
    )


def test_dsn_differentiation_present() -> None:
    text = _contract_text()
    assert "DSN differentiation" in text, "DSN differentiation section missing"
    assert "crash" in text.lower(), "DSN crash-consistency contrast missing"
    assert "benign contention" in text, "benign-contention contrast missing"


def test_frozen_archive_refusal_present() -> None:
    text = _contract_text()
    assert "E15" in text and "E22" in text, "E15-E22 refusal range missing"
    assert "background, not new venue experiments" in text, (
        "E15-E22 must be refused as background, not new evidence"
    )
    assert "sqlite:///:memory:" in text, "SQLite-backend refusal for PG claims missing"


def test_decision_line_go_or_no_go_with_justification() -> None:
    text = _contract_text()
    m = re.search(r"^Decision: (GO|NO-GO)$", text, flags=re.MULTILINE)
    assert m is not None, "missing explicit `Decision: GO`/`Decision: NO-GO` line"
    decision = m.group(1)
    start = text.index(m.group(0))
    justification = text[start : start + 2000]
    assert "Justification" in justification, f"decision {decision} lacks justification section"


def test_no_invented_empirical_results() -> None:
    text = _contract_text()
    forbidden = re.compile(
        r"\b(p\s*[<=]\s*0\.\d+|\d+(\.\d+)?\s*(x|×)\s*(faster|higher|lower)"
        r"|\d+(\.\d+)?\s*(ops/sec|ms)\s*(measured|observed))",
        re.IGNORECASE,
    )
    hits = forbidden.findall(text)
    assert not hits, f"apparent invented empirical numbers in contract: {hits}"
