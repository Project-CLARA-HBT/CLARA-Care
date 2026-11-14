"""Structural tests for the DIMVA-scope novelty contract (P01).

Purpose
-------
Stdlib-only structural verification of
``research/venue2027/dimva/novelty_contract.md``. The contract is a signed
scope register, not an empirical result: these tests assert the *structure*
required by ``VENUES/dimva/TASKS/DIMVA-scope.md`` — title, target reader,
falsification matrix with real prior-work ids, exactly three RQs with five
fields each, a distinct detection endpoint, IFIP SEC differentiation, archive
refusal and an explicit GO/NO-GO decision.

Allowed input
-------------
The contract markdown file at ``CONTRACT_PATH`` and the verified prior-work
ledger at ``LEDGER_PATH``. Read-only; no network, no randomness, no clock.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test
name; nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import pathlib
import re

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[2] / "dimva" / "novelty_contract.md"
LEDGER_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "_shared" / "literature_validity_ledger.csv"
)
REGISTRY_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "_shared" / "publication_overlap_registry.yaml"
)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Title and target reader",
    "## Claim-to-prior-work falsification matrix",
    "## Research questions",
    "## Distinct contribution and endpoint",
    "## Non-overlap: IFIP SEC (prevention) vs DIMVA (detection)",
    "## Archive refusal: frozen GLHS E15–E22 are not new evidence",
    "## Strong baseline set",
)

RQ_HEADERS: tuple[str, ...] = (
    "### RQ1 —",
    "### RQ2 —",
    "### RQ3 —",
)

RQ_FIELD_LABELS: tuple[str, ...] = (
    "- **Primary endpoint:**",
    "- **Strongest competing baseline:**",
    "- **Independent oracle:**",
    "- **Statistical test:**",
    "- **Falsification condition:**",
)

FORBIDDEN_ARCHIVE_IDS: tuple[str, ...] = (
    "E15",
    "E16",
    "E17",
    "E18",
    "E19",
    "E20",
    "E21",
    "E22",
)

_BASELINE_LABEL = "- **Strongest competing baseline:**"


def _contract_text() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def _rq_blocks(text: str) -> list[str]:
    """Split the Research questions section into per-RQ blocks."""
    section = text.split("## Research questions", 1)[1]
    section = section.split("## Strong baseline set", 1)[0]
    parts = re.split(r"\n### RQ\d ", section)
    return [p for p in parts if p.strip().startswith("—") or p.startswith("RQ")][:3]


def _extract_field(block: str, label: str) -> str:
    match = re.search(re.escape(label) + r"\s*(.+)", block)
    assert match is not None, f"missing field label {label!r}"
    return match.group(1).strip()


def _normalized(text: str) -> str:
    """Lowercase and fold hyphens so 'ground-truth' matches 'ground truth'."""
    return text.lower().replace("-", " ").replace("–", " ")


# --------------------------------------------------------------- structure
def test_contract_file_exists() -> None:
    assert CONTRACT_PATH.is_file(), f"missing contract: {CONTRACT_PATH}"


def test_required_sections_present() -> None:
    text = _contract_text()
    for section in REQUIRED_SECTIONS:
        assert section in text, f"missing required section: {section!r}"


def test_title_and_target_reader_present() -> None:
    text = _contract_text()
    assert "GovernanceTrace" in text, "contract title (paper name) missing"
    assert "Target reader:" in text, "target reader statement missing"


def test_decision_line_go_or_no_go() -> None:
    text = _contract_text()
    matches = re.findall(r"^Decision: (GO|NO-GO)$", text, flags=re.MULTILINE)
    assert matches, "no explicit 'Decision: GO' / 'Decision: NO-GO' line"
    assert matches.count(matches[0]) == len(matches), "contradictory decisions"


# ------------------------------------------------------------ falsification
def test_falsification_matrix_rows_and_real_prior_work_ids() -> None:
    text = _contract_text()
    matrix_section = text.split("## Claim-to-prior-work falsification matrix", 1)[1]
    matrix_section = matrix_section.split("## Research questions", 1)[0]
    rows = re.findall(r"^\| C\d+ \|", matrix_section, flags=re.MULTILINE)
    assert len(rows) >= 3, f"expected >=3 matrix rows, found {len(rows)}"

    ledger_ids = {
        line.split(",", 1)[0]
        for line in LEDGER_PATH.read_text(encoding="utf-8").strip().splitlines()[1:]
    }
    used_ids = set(re.findall(r"\| (C\d+) \| ([a-z0-9_]+) \|", matrix_section))
    cited = {pid for _, pid in used_ids}
    assert cited, "no prior-work ids cited in the falsification matrix"
    unknown = cited - ledger_ids
    assert not unknown, f"invented prior-work ids not in ledger: {sorted(unknown)}"


def test_falsification_matrix_covers_closest_prior_work() -> None:
    text = _contract_text()
    for pid in ("agentdojo24", "toolemu24", "sommer10"):
        assert f"| {pid} |" in text, f"closest prior work {pid} not cited"


# ------------------------------------------------------------------- RQs
def test_exactly_three_rqs_with_five_fields() -> None:
    text = _contract_text()
    rqs = _rq_blocks(text)
    assert len(rqs) == 3, f"expected exactly 3 RQs, found {len(rqs)}"
    for rq in rqs:
        for label in RQ_FIELD_LABELS:
            assert label in rq, f"RQ block missing {label!r}"


def test_primary_endpoints_are_distinct_across_rqs() -> None:
    rqs = _rq_blocks(_contract_text())
    endpoints = [_extract_field(rq, "- **Primary endpoint:**") for rq in rqs]
    lowered = [e.lower() for e in endpoints]
    assert len(set(lowered)) == 3, f"primary endpoints must be distinct: {endpoints}"


def test_each_rq_has_baseline_oracle_statistic_and_falsifier() -> None:
    rqs = _rq_blocks(_contract_text())
    for rq in rqs:
        baseline = _extract_field(rq, _BASELINE_LABEL)
        assert baseline.strip(), "empty competing baseline"
        oracle = _normalized(_extract_field(rq, "- **Independent oracle:**"))
        assert "oracle" in oracle or "ground truth" in oracle, (
            f"oracle statement must reference independent ground truth: {oracle!r}"
        )
        stat = _normalized(_extract_field(rq, "- **Statistical test:**"))
        assert any(
            kw in stat for kw in ("mcnemar", "bootstrap", "permutation", "wilcoxon", "exact test")
        ), f"statistical test must name a concrete test: {stat!r}"
        falsifier = _extract_field(rq, "- **Falsification condition:**")
        assert len(falsifier) > 40, "falsification condition too vague"


# ---------------------------------------------- distinct detection endpoint
def test_primary_endpoint_is_detection_metric_not_prevention_rate() -> None:
    """The RQ1 primary endpoint must be a detection metric (e.g. AUCPR at a
    fixed false-positive budget), never a prevention/admission rate."""
    text = _contract_text()
    rq1 = _rq_blocks(text)[0]
    endpoint = _extract_field(rq1, "- **Primary endpoint:**").lower()

    detection_markers = ("aucpr", "pr-auc", "auc", "recall", "precision")
    assert any(m in endpoint for m in detection_markers), (
        f"RQ1 primary endpoint is not a detection metric: {endpoint!r}"
    )
    assert "false" in endpoint and "budget" in endpoint, (
        f"RQ1 primary endpoint must be tied to a fixed false-positive budget: {endpoint!r}"
    )

    forbidden_prevention = (
        "replay acceptance rate",
        "invalid admission",
        "unauthorized commit",
        "prevention rate",
        "admission rate",
    )
    negated = _normalized(endpoint)
    for term in forbidden_prevention:
        for m in re.finditer(re.escape(term), negated):
            window = negated[max(0, m.start() - 24) : m.start()]
            assert re.search(r"\bnot\b", window), (
                f"RQ1 primary endpoint affirms prevention metric {term!r} "
                f"(negation not found in preceding context): {endpoint!r}"
            )


def test_distinct_contribution_names_detection_endpoint() -> None:
    text = _contract_text()
    distinct = text.split("## Distinct contribution and endpoint", 1)[1]
    distinct = distinct.split("## Non-overlap", 1)[0]
    assert "campaign-level probing detection AUC" in distinct
    assert "fixed false-positive budget" in distinct
    assert "minimal agent events" in distinct


def test_strong_baseline_set_has_at_least_three_arms() -> None:
    text = _contract_text()
    section = text.split("## Strong baseline set", 1)[1]
    section = section.split("## Distinct contribution and endpoint", 1)[0]
    arms = re.findall(r"^\| B\d+ \|", section, flags=re.MULTILINE)
    assert len(arms) >= 3, f"expected >=3 baselines, found {len(arms)}"


# ----------------------------------------------------- IFIP SEC differentiation
def test_ifip_sec_differentiation_present() -> None:
    text = _contract_text()
    section = text.split("## Non-overlap: IFIP SEC (prevention) vs DIMVA (detection)", 1)[1]
    section = section.split("## Archive refusal", 1)[0]
    lowered = section.lower()
    assert "prevention" in lowered and "detection" in lowered
    assert "replay acceptance rate" in lowered, "must name IFIP SEC's replay acceptance endpoint"
    assert "campaign-level pr-auc" in lowered or "pr-auc" in lowered, (
        "must name DIMVA's distinct endpoint"
    )
    for part in ("(1)", "(2)", "(3)", "(4)"):
        assert part in section, f"missing distinction part {part}"


def test_overlap_registry_declares_dimva_distinct() -> None:
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    assert "- study: dimva" in registry
    assert "- study: ifip_sec" in registry
    dimva_block = registry.split("- study: dimva", 1)[1].split("- study:", 1)[0]
    ifip_block = registry.split("- study: ifip_sec", 1)[1].split("- study:", 1)[0]
    assert "reuses_archive: []" in dimva_block
    assert "detection" in dimva_block
    assert "prevent" in ifip_block, "ifip_sec must remain the prevention study"


# --------------------------------------------------------- archive refusal
def test_archive_refusal_section_present() -> None:
    text = _contract_text()
    assert "## Archive refusal: frozen GLHS E15–E22 are not new evidence" in text
    section = text.split("## Archive refusal", 1)[1].split("## Decision", 1)[0]
    lowered = section.lower()
    assert "background only" in lowered
    assert "not new" in lowered, "refusal must state E15–E22 are not new evidence"
    assert "sqlite:///:memory:" in section, "must record that E15–E19 ran on in-memory SQLite"
    assert "not_run_provider_attestation_unavailable" in lowered


def test_archive_ids_never_used_as_evidence_in_rq_sections() -> None:
    """E15–E22 may appear only in the archive-refusal/matrix provenance
    context, never inside an RQ block as supporting evidence."""
    text = _contract_text()
    rq_section = text.split("## Research questions", 1)[1].split("## Strong baseline set", 1)[0]
    for evid in FORBIDDEN_ARCHIVE_IDS:
        assert not re.search(rf"\b{evid}\b", rq_section), (
            f"frozen archive evidence {evid} must not be used as RQ evidence"
        )
