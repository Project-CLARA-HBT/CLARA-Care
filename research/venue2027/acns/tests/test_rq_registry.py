"""Structural gate for ACNS-rq_registry (frozen RQ, estimand, hypotheses, metrics).

Purpose
-------
Machine-checks task ``ACNS-rq_registry`` (venue ``acns``, phase ``P01``)
against its deliverable contract: ``research/venue2027/acns/
rq_and_estimands.yaml`` must preregister **exactly three RQs (RQ1-RQ3)**,
each carrying all required planning fields:

- ``research_question`` — verbatim scope from the blueprint;
- ``independent_unit`` / ``population`` / ``estimand`` — the SoK unit rules;
- ``paired_contrast`` — each claim/pair is its own control;
- ``primary_metric`` / ``secondary_metrics`` — primary vs supporting split;
- ``null_hypothesis`` / ``alternative_hypothesis`` — directional H0/H1;
- ``minimum_useful_difference`` — the registered useful-effect bound;
- ``confounders`` — named threats and mitigations;
- ``power_analysis`` / ``analysis_method`` — exact tests, fixed seeds, N floors;
- ``falsification_condition`` — the negative-result commitment;
- ``primary_endpoint`` — the single gated endpoint per RQ.

The test also asserts the registry stays SoK-shaped (estimator concerns
evidence-boundary coverage, not mechanism superiority; endpoints are the
blueprint's coverage/kappa/reproduction endpoints; no runtime defense metric
appears as an endpoint) and that **no empirical value is invented** (no
observed kappa, coverage, reproduction rate or corpus-size claim is asserted;
only design-time planning constants are present).

Allowed input
-------------
Read-only access to the registry YAML and the ACNS novelty contract.
No network, no database, no provider calls, no randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_RQ_``; pytest reports the failing check directly. Stdlib-only besides
pytest itself.

Version
-------
``ACNS_RQ_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

ACNS_RQ_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "rq_and_estimands.yaml"
NOVELTY_CONTRACT_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "novelty_contract.md"

REQUIRED_TOP_FIELDS = (
    "schema_version",
    "contract",
    "paper",
    "contribution_class",
    "estimator_frame",
    "preregistration_status",
    "corpus_window",
    "confidence_budget",
    "denominator_discipline",
    "sok_no_mechanism_clause",
)

REQUIRED_RQ_FIELDS = (
    "id",
    "name",
    "research_question",
    "independent_unit",
    "population",
    "estimand",
    "paired_contrast",
    "primary_metric",
    "secondary_metrics",
    "null_hypothesis",
    "alternative_hypothesis",
    "minimum_useful_difference",
    "confounders",
    "power_analysis",
    "analysis_method",
    "falsification_condition",
    "primary_endpoint",
)

RQ_IDS = ("RQ1", "RQ2", "RQ3")

# SoK-appropriate primary endpoints: evidence-boundary coverage instruments,
# never mechanism-superiority metrics.
EXPECTED_ENDPOINTS = {
    "RQ1": "coverage of the evidence-strength lattice",
    "RQ2": "counterexample reproduction rate",
    "RQ3": "inter-rater cohen's kappa",
}

# Runtime defense metrics that would violate the SoK contribution class
# (novelty_contract F4/F6) if any appeared as an endpoint/metric name.
FORBIDDEN_ENDPOINT_PHRASES = (
    "detection pr-auc",
    "prevention rate",
    "attack success rate",
    "false alarm budget",
    "replay acceptance rate",
    "pr_auc",
    "detection rate",
)

# Empirical-value inventing patterns: an observed-value assertion pattern in a
# design-time preregistration. These names must only appear as *metric names*
# or *planning* constants, never asserted with an observed "=" / "is" value
# outside analysis_method/power_analysis/null hypotheses/registered margins.
METRIC_NAME_PATTERNS = (
    r"kappa\s*=\s*0?\.\d+",
    r"coverage\s*=\s*0?\.\d+",
    r"reproduction rate\s*=\s*0?\.\d+",
    r"ambiguous[- ]claim fraction\s*=\s*0?\.\d+",
)

REQUIRED_PLANNING_CONSTANTS = ("20271115", "0.05", "0.80", "0.60", "N=52", "N=18", "N=120")

BASELINE_REFERENCES = ("RFC 9334", "W3C PROV", "AgentDojo", "ToolEmu")


def _registry_text() -> str:
    assert REGISTRY_PATH.is_file(), f"ACNS_RQ_MISSING: registry file absent at {REGISTRY_PATH}"
    return REGISTRY_PATH.read_text(encoding="utf-8")


def _rq_blocks(text: str) -> dict[str, str]:
    """Split the registry into per-RQ blocks keyed by the list-item id field."""
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r"^\s+- id:\s*(RQ[123])\s*$", text, flags=re.MULTILINE)
    ]
    assert len(starts) == 3, f"ACNS_RQ_COUNT: expected exactly 3 RQ list items, found {len(starts)}"
    blocks: dict[str, str] = {}
    for i, (pos, rq_id) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        blocks[rq_id] = text[pos:end]
    return blocks


def _folded(text: str) -> str:
    """Collapse YAML folded-scalar line wrapping to single-spaced text."""
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# Positive controls: structure
# ---------------------------------------------------------------------------


def test_registry_exists_with_header_and_version() -> None:
    text = _registry_text()
    assert "ACNS-rq_registry" in text, "ACNS_RQ_ID: task id missing from registry header"
    assert "clara.venue2027.acns.rq-registry.v1" in text, "ACNS_RQ_CONTRACT: contract id missing"
    assert (
        "SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems" in text
    ), "ACNS_RQ_PAPER: paper title missing"
    assert "schema_version: 1" in text, "ACNS_RQ_SCHEMA_VERSION: schema_version field missing"


def test_top_level_governance_fields_present() -> None:
    text = _registry_text()
    for field in REQUIRED_TOP_FIELDS:
        assert re.search(
            rf"^{field}:", text, flags=re.MULTILINE
        ), f"ACNS_RQ_TOP_FIELD: missing top-level field {field!r}"


def test_exactly_three_rqs_with_all_required_fields() -> None:
    blocks = _rq_blocks(_registry_text())
    assert sorted(blocks) == sorted(
        RQ_IDS
    ), f"ACNS_RQ_IDS: RQ ids must be exactly {RQ_IDS}, got {sorted(blocks)}"
    for rq_id, block in blocks.items():
        for field in REQUIRED_RQ_FIELDS:
            assert re.search(
                rf"^\s+-? ?{field}:", block, flags=re.MULTILINE
            ), f"ACNS_RQ_FIELD_{rq_id}: required field {field!r} missing"


def test_rq_text_verbatim_from_blueprint() -> None:
    blocks = _rq_blocks(_registry_text())
    expected = {
        "RQ1": "Which attestation claims are actually supported by which observable "
        "evidence and trusted parties in published agent systems?",
        "RQ2": "Which claimed implication pairs are invalid under explicit adversarial "
        "and provider models, and can small executable witnesses demonstrate this?",
        "RQ3": "How consistently can independent reviewers classify claims and "
        "reproduce counterexamples across a pre-registered corpus?",
    }
    for rq_id, question in expected.items():
        assert _folded(question) in _folded(
            blocks[rq_id]
        ), f"ACNS_RQ_VERBATIM_{rq_id}: research_question text not verbatim from blueprint"


def test_baseline_references_present() -> None:
    text = _registry_text()
    for ref in BASELINE_REFERENCES:
        assert ref in text, f"ACNS_RQ_BASELINE: baseline reference {ref!r} missing"


# ---------------------------------------------------------------------------
# Positive controls: SoK framing
# ---------------------------------------------------------------------------


def test_sok_estimator_framing_is_coverage_not_mechanism() -> None:
    text = _registry_text()
    assert "contribution_class: SoK" in text, "ACNS_RQ_SOK_CLASS: SoK class not declared"
    assert (
        "estimator_frame: evidence_boundary_coverage_not_mechanism_superiority" in text
    ), "ACNS_RQ_ESTIMATOR_FRAME: coverage-not-superiority estimator frame missing"
    assert (
        "sok_no_mechanism_clause" in text
    ), "ACNS_RQ_NO_MECHANISM: explicit no-mechanism clause missing"


def test_primary_endpoints_are_sok_appropriate() -> None:
    blocks = _rq_blocks(_registry_text())
    for rq_id, endpoint in EXPECTED_ENDPOINTS.items():
        block = blocks[rq_id].lower()
        assert (
            "primary_endpoint:" in block
        ), f"ACNS_RQ_ENDPOINT_FIELD_{rq_id}: primary_endpoint field missing"
        endpoint_block = re.search(r"primary_endpoint:.*?(?=\n\s{2}- |\Z)", blocks[rq_id], re.S)
        assert (
            endpoint_block is not None
        ), f"ACNS_RQ_ENDPOINT_MISSING_{rq_id}: primary_endpoint block not parseable"
        assert (
            endpoint in endpoint_block.group(0).lower()
        ), f"ACNS_RQ_ENDPOINT_VALUE_{rq_id}: primary endpoint must name {endpoint!r}"


def test_no_forbidden_mechanism_metric_as_endpoint() -> None:
    blocks = _rq_blocks(_registry_text())
    for rq_id, block in blocks.items():
        endpoint_text = (
            re.search(r"primary_endpoint:.*?(?=\n\s{2}- |\Z)", block, re.S).group(0).lower()
            if re.search(r"primary_endpoint:.*?(?=\n\s{2}- |\Z)", block, re.S)
            else ""
        )
        metric_text = (
            re.search(r"primary_metric:.*?(?=\n\s{2}- |\n\s+\w+_hypothesis)", block, re.S)
            .group(0)
            .lower()
            if re.search(r"primary_metric:.*?(?=\n\s{2}- |\n\s+\w+_hypothesis)", block, re.S)
            else ""
        )
        for phrase in FORBIDDEN_ENDPOINT_PHRASES:
            assert phrase not in endpoint_text and phrase not in metric_text, (
                f"ACNS_RQ_FORBIDDEN_METRIC_{rq_id}: mechanism metric {phrase!r} "
                "must not appear as primary endpoint/metric"
            )


def test_preregistration_only_no_invented_empirical_values() -> None:
    text = _registry_text()
    assert (
        "preregistration_status: thresholds_fixed_before_any_data_collection" in text
    ), "ACNS_RQ_PREREG: preregistration status declaration missing"
    # Observed-value assertion patterns must not appear anywhere: a design-time
    # registry plans thresholds, it never reports observed metric values.
    for pattern in METRIC_NAME_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        assert match is None, (
            f"ACNS_RQ_NO_INVENTED_VALUE: pattern {pattern!r} matched "
            f"{match.group(0)!r} — observed values are forbidden in a preregistration"
        )
    assert (
        "manifest.json" in text
    ), "ACNS_RQ_MANIFEST_ROUTE: observed values must route via run manifests"
    assert "ACNS-freeze" in text, "ACNS_RQ_FREEZE_GATE: freeze gate reference missing"


def test_design_time_constants_frozen() -> None:
    text = _registry_text()
    for constant in REQUIRED_PLANNING_CONSTANTS:
        assert (
            constant in text
        ), f"ACNS_RQ_PLANNING_CONSTANT: design-time constant {constant!r} missing"


def test_paired_contrast_and_unit_antipseudoreplication() -> None:
    blocks = _rq_blocks(_registry_text())
    for rq_id, block in blocks.items():
        assert "paired_contrast:" in block, f"ACNS_RQ_PAIRED_{rq_id}: paired contrast missing"
    text = _registry_text()
    assert (
        "pseudo-replication" in text
    ), "ACNS_RQ_ANTIPSEUDO: anti-pseudo-replication rule not stated"


# ---------------------------------------------------------------------------
# Adversarial controls: registry must refuse SoK violations and drift
# ---------------------------------------------------------------------------


def test_falsification_conditions_match_novelty_contract() -> None:
    blocks = _rq_blocks(_registry_text())
    contract = NOVELTY_CONTRACT_PATH.read_text(encoding="utf-8")
    # RQ1: RFC 9334 sufficiency OR agreement failure collapses the arm.
    assert (
        "RFC 9334 suffices" in blocks["RQ1"]
    ), "ACNS_RQ_FALS_RQ1: RQ1 falsification must state the RFC 9334-suffices collapse"
    assert (
        "withdrawn" in blocks["RQ1"].split("falsification_condition:")[1]
    ), "ACNS_RQ_FALS_RQ1_WITHDRAW: RQ1 falsification must withdraw the SoK claim"
    # RQ2: reproduction below threshold or B0/B2 restatement falsifies.
    assert (
        "0.80" in blocks["RQ2"].split("falsification_condition:")[1]
    ), "ACNS_RQ_FALS_RQ2: RQ2 falsification must reference the registered 0.80 threshold"
    assert (
        "taxonomy" in blocks["RQ2"].split("falsification_condition:")[1]
    ), "ACNS_RQ_FALS_RQ2_RESTATE: RQ2 falsification must cover the taxonomy-restatement case"
    # RQ3: kappa margin vs B3-style generic coding.
    assert (
        "0.10" in blocks["RQ3"].split("falsification_condition:")[1]
    ), "ACNS_RQ_FALS_RQ3: RQ3 falsification must reference the registered 0.10 kappa margin"
    assert (
        "B3" in blocks["RQ3"].split("falsification_condition:")[1]
    ), "ACNS_RQ_FALS_RQ3_B3: RQ3 falsification must reference the B3-style generic coding"
    # The contract itself commits the same gates (cross-document consistency).
    assert (
        "the SoK claim is withdrawn" in contract or "no SoK claim is made" in contract
    ), "ACNS_RQ_CONTRACT_GATES: novelty contract gates missing"


def test_hypotheses_are_directional_with_registered_bounds() -> None:
    blocks = _rq_blocks(_registry_text())
    # RQ1: H0 pi<=0.05 vs H1 pi>0.05 with 0.15 useful difference.
    assert (
        "0.05" in blocks["RQ1"].split("null_hypothesis:")[1].split("alternative_hypothesis:")[0]
    ), "ACNS_RQ_H0_RQ1: RQ1 null must state the 0.05 bound"
    assert (
        "0.15" in blocks["RQ1"].split("minimum_useful_difference:")[1].split("confounders:")[0]
    ), "ACNS_RQ_MARGIN_RQ1: RQ1 useful difference must state the 0.15 bound"
    # RQ2: H0 rho<=0.50 vs H1 rho>0.50 with 0.80 useful threshold.
    assert (
        "0.50" in blocks["RQ2"].split("null_hypothesis:")[1].split("alternative_hypothesis:")[0]
    ), "ACNS_RQ_H0_RQ2: RQ2 null must state the 0.50 bound"
    assert (
        "0.80" in blocks["RQ2"].split("minimum_useful_difference:")[1].split("confounders:")[0]
    ), "ACNS_RQ_MARGIN_RQ2: RQ2 useful difference must state the 0.80 threshold"
    # RQ3: kappa margin 0.10 vs B3-style generic coding.
    assert (
        "0.10" in blocks["RQ3"].split("null_hypothesis:")[1].split("alternative_hypothesis:")[0]
    ), "ACNS_RQ_H0_RQ3: RQ3 null must state the 0.10 kappa margin"


def test_exact_tests_and_fixed_seed_no_post_hoc_drift() -> None:
    text = _registry_text()
    assert "Clopper" in text, "ACNS_RQ_EXACT_CI: exact Clopper-Pearson CI method missing"
    assert "McNemar" in text, "ACNS_RQ_MCNEAR: exact McNemar method missing"
    assert "kappa" in text.lower(), "ACNS_RQ_KAPPA: Cohen's kappa method missing"
    assert "bootstrap" in text.lower(), "ACNS_RQ_BOOTSTRAP: bootstrap CI method missing"
    assert (
        text.count("seed 20271115") >= 2
    ), "ACNS_RQ_SEED: fixed analysis seed 20271115 must pin bootstrap resampling"
    assert (
        "assert_frozen_analysis" in text
    ), "ACNS_RQ_DRIFT_GUARD: frozen-plan drift guard reference missing"


def test_denominator_and_ineterminate_discipline() -> None:
    text = _registry_text()
    assert "denominator_discipline:" in text, "ACNS_RQ_DENOM: denominator discipline missing"
    for status in (
        "eligible",
        "attempted",
        "completed",
        "rejected",
        "indeterminate",
        "timeout",
        "not_run_external",
        "missing",
    ):
        assert status in text, f"ACNS_RQ_STATUS: required outcome status {status!r} not reported"
    assert (
        "INDETERMINATE" in text and "never coerced" in text
    ), "ACNS_RQ_INDETERMINATE: INDETERMINATE retention rule missing"


def test_oracle_independence_and_no_repair_clauses() -> None:
    text = _registry_text()
    assert (
        "never imports witness code" in text or "truth.json" in text
    ), "ACNS_RQ_ORACLE: independent-oracle (truth.json fixed before execution) clause missing"
    assert "repaired" in text, "ACNS_RQ_NO_REPAIR: no-post-hoc-repair commitment missing"


def test_no_placeholder_text() -> None:
    text = _registry_text()
    for marker in ("TBD", "TODO", "FIXME", "XXX", "<placeholder"):
        assert marker not in text, f"ACNS_RQ_PLACEHOLDER: placeholder {marker!r} present"


def test_confounders_and_power_present_per_rq() -> None:
    blocks = _rq_blocks(_registry_text())
    for rq_id, block in blocks.items():
        assert "confounders:" in block, f"ACNS_RQ_CONF_{rq_id}: confounders missing"
        assert "power_analysis:" in block, f"ACNS_RQ_POWER_{rq_id}: power analysis missing"
        assert "analysis_method:" in block, f"ACNS_RQ_ANALYSIS_{rq_id}: analysis method missing"
        # N floors must be registered before data collection, never from target p-values.
        assert re.search(r"N=\d+", block), f"ACNS_RQ_NFLOOR_{rq_id}: planning N floor missing"
