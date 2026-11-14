"""Structural tests for IFIP_SEC-scope novelty contract.

Positive controls:
- Every required section of research/venue2027/ifip_sec/novelty_contract.md exists.
- Exactly 3 RQ blocks, each carrying the 5 mandated fields (primary endpoint,
  strongest competing baseline, independent oracle, statistical test,
  falsification condition).
- >= 3 named baseline arms from the blueprint baseline table.
- A single explicitly named truly-distinct endpoint.
- Archive refusal: frozen GLHS E15-E22 are refused as new evidence.
- Explicit ACNS (SoK) and DIMVA (detection) differentiation assertions.
- Exactly one Decision line, and it is GO.

Adversarial controls:
- A contract with a missing RQ field or a NO-GO/multiple decision must be
  REFUSED by the validator (never silently accepted as conforming).
"""

from __future__ import annotations

import pathlib
import re

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[1] / "novelty_contract.md"

REQUIRED_SECTIONS = (
    "Title and target reader",
    "Claim-to-prior-work falsification matrix",
    "Research questions and endpoint contracts",
    "Scope",
    "Non-overlap declaration",
    "Decision",
)

REQUIRED_RQ_FIELDS = (
    "Primary endpoint",
    "Strongest competing baseline",
    "Independent oracle",
    "Statistical test",
    "Falsification condition",
)

REQUIRED_BASELINES = ("B0", "B1", "B2", "B3")

PRIOR_WORK_IDS = (
    "macaroons14",
    "zanzibar19",
    "cedar",
    "openfga",
    "xacml18",
    "nistabac",
    "rats9334",
    "elle20",
    "silo13",
    "opa",
    "agentdojo24",
    "toolemu24",
    "injecagent24",
)


def _contract_text() -> str:
    assert CONTRACT_PATH.is_file(), f"missing contract: {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def _rq_block_texts(text: str) -> list[str]:
    """Extract the ### RQ blocks (and nothing after the scope section)."""
    pattern = re.compile(r"^### (RQ\d[^#\n]*)$(.*?)(?=^### |\Z)", re.M | re.S)
    return [m.group(0) for m in pattern.finditer(text)]


# ------------------------------------------------------------------ sections
def test_contract_exists() -> None:
    assert CONTRACT_PATH.is_file()


def test_required_sections_present() -> None:
    text = _contract_text()
    headings = re.findall(r"^#+ .*$", text, re.M)
    joined = "\n".join(headings)
    for section in REQUIRED_SECTIONS:
        assert section in joined, f"missing section heading: {section}"


def test_title_and_target_reader_declared() -> None:
    text = _contract_text()
    assert "Working title:" in text
    assert "Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage" in text
    assert "Target reader:" in text


# ------------------------------------------------------------------ RQ blocks
def test_exactly_three_rqs() -> None:
    blocks = _rq_block_texts(_contract_text())
    assert len(blocks) == 3, f"expected exactly 3 RQ blocks, found {len(blocks)}"


def test_each_rq_has_all_five_fields() -> None:
    blocks = _rq_block_texts(_contract_text())
    for i, block in enumerate(blocks, start=1):
        for field in REQUIRED_RQ_FIELDS:
            assert f"**{field}:**" in block, f"RQ{i} missing field: {field}"


def test_rq_baselines_come_from_blueprint_table() -> None:
    text = _contract_text()
    for arm in REQUIRED_BASELINES:
        assert re.search(rf"^\| {arm} \|", text, re.M), f"baseline arm {arm} not declared"


# ------------------------------------------------------- falsification matrix
def test_falsification_matrix_cites_real_prior_work_ids() -> None:
    text = _contract_text()
    assert "Closest prior work" in text
    for pid in PRIOR_WORK_IDS:
        assert f"`{pid}`" in text, f"prior-work id missing from matrix: {pid}"


def test_falsification_matrix_has_required_differentiator_and_test() -> None:
    text = _contract_text()
    assert "Required differentiator" in text
    assert "Falsifying test" in text


# -------------------------------------------------------- distinct endpoint
def test_single_truly_distinct_endpoint_named() -> None:
    text = _contract_text()
    assert "TRULY DISTINCT ENDPOINT" in text
    assert "replay acceptance rate across purpose, delegation and AI proposal lineage" in text
    assert text.count("TRULY DISTINCT ENDPOINT") == 1


# ------------------------------------------------------------ non-overlap
def test_archive_refusal_e15_e22() -> None:
    text = _contract_text()
    assert "E15" in text and "E22" in text
    # The refusal must be explicit: frozen archive is background, not evidence.
    refusal = re.search(r"Refusal of the frozen GLHS R4 archive[^#]*", text, re.S)
    assert refusal is not None, "missing explicit E15-E22 archive-refusal section"
    body = refusal.group(0)
    assert "background, not new evidence" in body
    assert "refuse" in body.lower()


def test_acns_differentiation_assertion() -> None:
    text = _contract_text()
    assert "ACNS" in text
    assert "SoK" in text
    assert "evidence-boundary coverage matrix" in text
    assert "replay acceptance rate across purpose/delegation lineage" in text


def test_dimva_differentiation_assertion() -> None:
    text = _contract_text()
    assert "DIMVA" in text
    assert "probing detection AUC at a fixed false-positive budget" in text
    assert "prevention, not detection" in text


def test_other_venue_distinctions_covered() -> None:
    text = _contract_text()
    for venue in ("DSN", "COMPSAC", "PoPETs", "SACMAT", "AIME", "PST"):
        assert venue in text, f"venue distinction missing: {venue}"


# ------------------------------------------------------------------ decision
def test_exactly_one_decision_line_and_go() -> None:
    text = _contract_text()
    decisions = re.findall(r"^\*\*Decision:\s*(GO|NO-GO)\*\*", text, re.M)
    assert len(decisions) == 1, f"expected exactly one Decision line, found {len(decisions)}"
    assert decisions[0] == "GO"


# ------------------------------------------------- adversarial validator controls
def _validate_contract(raw: str) -> list[str]:
    """Minimal re-implementation of the structural gate used above.

    Returns a list of violation strings; empty means conforming. Used to
    demonstrate refusal of mutated (non-conforming) contracts.
    """
    violations: list[str] = []
    blocks = _rq_block_texts(raw)
    if len(blocks) != 3:
        violations.append(f"RQ count {len(blocks)} != 3")
    for i, block in enumerate(blocks, start=1):
        for field in REQUIRED_RQ_FIELDS:
            if f"**{field}:**" not in block:
                violations.append(f"RQ{i} missing {field}")
    decisions = re.findall(r"^\*\*Decision:\s*(GO|NO-GO)\*\*", raw, re.M)
    if len(decisions) != 1:
        violations.append(f"decision count {len(decisions)} != 1")
    elif decisions[0] != "GO":
        violations.append("decision is not GO")
    if "TRULY DISTINCT ENDPOINT" not in raw:
        violations.append("missing distinct endpoint declaration")
    for pid in ("macaroons14", "zanzibar19", "elle20"):
        if f"`{pid}`" not in raw:
            violations.append(f"missing prior-work id {pid}")
    if "Refusal of the frozen GLHS R4 archive" not in raw:
        violations.append("missing E15-E22 archive refusal")
    for sibling in ("ACNS", "SoK", "DIMVA"):
        if sibling not in raw:
            violations.append(f"missing sibling differentiation: {sibling}")
    return violations


def test_mutated_contract_without_rq_field_is_refused() -> None:
    raw = _contract_text().replace("**Independent oracle:**", "**Oracle note:**", 1)
    problems = _validate_contract(raw)
    assert problems, "validator must refuse an RQ block missing a mandated field"


def test_contract_without_distinct_endpoint_is_refused() -> None:
    raw = _contract_text().replace("TRULY DISTINCT ENDPOINT", "PRIMARY CONTRIBUTION", 1)
    assert _validate_contract(raw), "validator must refuse missing distinct endpoint"


def test_no_go_or_ambiguous_decision_is_refused() -> None:
    no_go = _contract_text().replace("**Decision: GO**", "**Decision: NO-GO**", 1)
    assert any("decision" in p for p in _validate_contract(no_go))
    double = _contract_text() + "\n**Decision: GO**\n"
    assert any("decision" in p for p in _validate_contract(double))


# ------------------------------------------------------------- hygiene gates
def test_no_invented_empirical_results() -> None:
    text = _contract_text()
    # The contract must not present fabricated result numbers as observed.
    assert "0/800" not in text
    assert "N=2,500" not in text and "N = 2,500" not in text
    assert "p < 10" not in text
    assert "prospective" in text.lower()


def test_status_is_prospective_not_evidence() -> None:
    text = _contract_text()
    assert "not experimental evidence" in text.lower()
    assert "synthetic-ifip_sec-2027" in text
