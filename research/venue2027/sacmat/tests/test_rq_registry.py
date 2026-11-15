"""Structural tests for the SACMAT-rq_registry preregistration (task SACMAT-rq_registry, P01).

Purpose
-------
Stdlib-only structural gate over ``research/venue2027/sacmat/rq_and_estimands.yaml``.
It verifies the preregistered RQ plan exists, parses as a key/value registry,
contains exactly three RQs, each carrying every mandatory field (research
question, independent unit, population, estimand, paired contrast, primary
metric, secondary metrics, null, alternative, minimum useful difference,
confounders, power/analysis method, falsification condition, primary
endpoint), plus the frozen preregistration controls (independent delegated-
consent policy-case unit, multiplicity, holdout freeze, no invented results).

Allowed input
-------------
The YAML file at the repository-relative path below, read-only, parsed with a
minimal stdlib block scanner (no PyYAML dependency).

Failure semantics
-----------------
Each violation raises a focused ``AssertionError`` naming the missing marker;
the suite fails closed if the registry file itself is absent.

Version
-------
``RQ_REGISTRY_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

RQ_REGISTRY_TEST_VERSION = "1.0.0"

RQ_REGISTRY_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "sacmat"
    / "rq_and_estimands.yaml"
)

RQ_REQUIRED_FIELDS = (
    "research_question",
    "independent_unit",
    "population",
    "estimand",
    "paired_contrast",
    "primary_metric",
    "primary_metric_operationalization",
    "secondary_metrics",
    "null_hypothesis",
    "alternative_hypothesis",
    "minimum_useful_difference",
    "confounders",
    "power_analysis_method",
    "falsification_condition",
    "primary_endpoint",
    "strongest_competing_baseline",
    "independent_oracle",
    "statistical_test",
)


def _load_text() -> str:
    assert RQ_REGISTRY_PATH.is_file(), f"RQ registry missing at {RQ_REGISTRY_PATH}"
    return RQ_REGISTRY_PATH.read_text(encoding="utf-8")


def _top_level_keys(text: str) -> dict[str, str]:
    """Map top-level YAML keys to the raw block that follows them.

    A minimal indentation-aware scan: a top-level key starts at column 0 and
    is not a comment; its block extends from the key line itself until the
    next top-level key, so same-line scalars are retained. This is a
    structural parser only (no value semantics), sufficient to assert the
    registry shape without inventing a YAML dependency.
    """

    keys: dict[str, str] = {}
    current: str | None = None
    block: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            if current is not None:
                block.append(line)
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", line):
            if current is not None:
                keys[current] = "\n".join(block)
            current = line.split(":", 1)[0].strip()
            block = [line]
        elif current is not None:
            block.append(line)
    if current is not None:
        keys[current] = "\n".join(block)
    return keys


def _rq_blocks(text: str) -> dict[str, dict[str, str]]:
    """Map ``  RQn:`` second-level keys to their field dictionaries.

    Each RQ block is scanned into ``field_name -> raw block text`` (the field
    line plus its indented continuation). Fields are mandatory per
    RQ_REQUIRED_FIELDS; missing fields therefore surface as assertion
    failures in the dedicated completeness test rather than KeyErrors.
    """

    blocks: dict[str, dict[str, str]] = {}
    match_iter = re.finditer(r"^  (RQ[1-3]):\s*$", text, flags=re.MULTILINE)
    matches = list(match_iter)
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        fields: dict[str, str] = {}
        field_iter = re.finditer(r"^    ([a-z_]+):(.*)$", body, flags=re.MULTILINE)
        fmatches = list(field_iter)
        for j, fm in enumerate(fmatches):
            fstart = fm.start()
            fend = fmatches[j + 1].start() if j + 1 < len(fmatches) else len(body)
            fields[fm.group(1)] = body[fstart:fend]
        blocks[m.group(1)] = fields
    return blocks


def _blob(raw: str) -> str:
    """Whitespace-normalized text of one field block (key line + continuation)."""

    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    return " ".join(lines)


def _scalar(raw: str) -> str:
    """Value of a single-line ``key: "value"`` block, quotes stripped."""

    match = re.search(r":\s*(.+)$", raw, flags=re.MULTILINE)
    if match is None:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def test_registry_is_nonempty_yaml() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    assert "paper" in keys, "missing top-level key: paper"
    assert "PolicyTrace" in keys["paper"], "paper key must name the PolicyTrace study"
    assert "task_id" in keys and _scalar(keys["task_id"]) == "SACMAT-rq_registry"
    assert "venue" in keys and _scalar(keys["venue"]) == "sacmat"
    assert "phase" in keys and _scalar(keys["phase"]) == "P01"


def test_exactly_three_rqs_with_all_fields() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    assert sorted(rq_blocks) == ["RQ1", "RQ2", "RQ3"], (
        f"expected exactly RQ1, RQ2, RQ3, found {sorted(rq_blocks)}"
    )
    for rq_id, fields in rq_blocks.items():
        for field in RQ_REQUIRED_FIELDS:
            assert field in fields, f"{rq_id} missing required field: {field}"


def test_each_rq_declares_primary_metric_and_endpoint() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    for rq_id, fields in rq_blocks.items():
        assert _scalar(fields["primary_metric"]) == (
            "delegation conformance divergence detection rate"
        ), f"{rq_id} primary_metric must be the study's distinct endpoint"
        assert re.search(r"primary_endpoint:\s*>-", fields["primary_endpoint"]), (
            f"{rq_id} primary_endpoint must be a folded block"
        )
        assert _blob(fields["primary_endpoint"]), f"{rq_id} primary_endpoint must have content"


def test_secondary_metrics_are_lists() -> None:
    text = _load_text()
    for rq_id, fields in _rq_blocks(text).items():
        assert re.search(r"secondary_metrics:\n", fields["secondary_metrics"]), (
            f"{rq_id} secondary_metrics must be a list block"
        )
        items = re.findall(r"^      - ", fields["secondary_metrics"], flags=re.MULTILINE)
        assert len(items) >= 3, f"{rq_id} needs at least 3 secondary metrics"


def test_null_and_alternative_present_and_distinct() -> None:
    text = _load_text()
    for rq_id, fields in _rq_blocks(text).items():
        null_text = _blob(fields["null_hypothesis"])
        alt_text = _blob(fields["alternative_hypothesis"])
        assert null_text and alt_text, f"{rq_id} hypotheses must be non-empty"
        assert null_text != alt_text, f"{rq_id} null and alternative must differ"
        assert "zero" in null_text.lower() or "no " in null_text.lower() or (
            "not" in null_text.lower()
        ), f"{rq_id} null must be the null-direction statement"


def test_minimum_useful_difference_frozen_without_pilot_data() -> None:
    text = _load_text()
    for rq_id, fields in _rq_blocks(text).items():
        blob = _blob(fields["minimum_useful_difference"])
        assert re.search(r"0\.\d+", blob), f"{rq_id} minimum_useful_difference needs a margin"
        assert "frozen" in blob.lower(), (
            f"{rq_id} margin must be declared as frozen prospectively"
        )


def test_confounders_are_explicit_lists() -> None:
    text = _load_text()
    for rq_id, fields in _rq_blocks(text).items():
        items = re.findall(r"^      - ", fields["confounders"], flags=re.MULTILINE)
        assert len(items) >= 4, f"{rq_id} needs at least 4 declared confounders"


def test_power_and_analysis_method_names_test_and_multiplicity() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    assert "McNemar" in _blob(rq_blocks["RQ1"]["power_analysis_method"]), (
        "RQ1 power method must name the McNemar test"
    )
    assert "Wilcoxon" in _blob(rq_blocks["RQ2"]["power_analysis_method"]), (
        "RQ2 power method must name the Wilcoxon signed-rank test"
    )
    for rq_id, fields in rq_blocks.items():
        blob = _blob(fields["power_analysis_method"])
        assert "0.05" in blob, f"{rq_id} power method must fix alpha at 0.05"
        assert ("Holm" in blob) or ("bootstrap" in blob) or ("Wilson" in blob), (
            f"{rq_id} power method must name its multiplicity or interval method"
        )


def test_falsification_conditions_present_and_binding() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    for rq_id, fields in rq_blocks.items():
        blob = _blob(fields["falsification_condition"])
        assert blob.strip(), f"{rq_id} falsification_condition must be non-empty"
    rq2_fc = _blob(rq_blocks["RQ2"]["falsification_condition"])
    rq3_fc = _blob(rq_blocks["RQ3"]["falsification_condition"])
    assert "oracle-call budget" in rq2_fc, (
        "RQ2 falsification must reference the equal oracle-call budget"
    )
    assert "zero" in rq3_fc.lower() or "static policy diff" in rq3_fc, (
        "RQ3 falsification must cover the zero-divergence / static-diff condition"
    )


def test_independent_unit_is_delegated_consent_policy_case() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    assert "independent_unit_definition" in keys, "missing independent_unit_definition"
    unit_blob = " ".join(keys["independent_unit_definition"].split())
    assert "policy history" in unit_blob, "unit must be a policy history"
    assert "authorization request" in unit_blob, "unit must pair exactly one request"
    assert "never" in unit_blob and "independent" in unit_blob, (
        "unit must exclude per-event pseudo-replication"
    )
    for rq_id, fields in _rq_blocks(text).items():
        iu = _blob(fields["independent_unit"])
        assert "policy history" in iu, f"{rq_id} unit must reference policy history"


def test_population_declares_corpus_and_holdout() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    assert "50" in rq_blocks["RQ1"]["population"], "RQ1 population must fix the 50-mutant set"
    assert "50" in rq_blocks["RQ2"]["population"], "RQ2 population must fix the 50-mutant set"
    for rq_id, fields in rq_blocks.items():
        assert "synthetic" in fields["population"], f"{rq_id} population must be synthetic-only"


def test_preregistration_and_no_invented_results() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    assert "preregistration" in keys, "missing preregistration declaration"
    assert "no_results_declaration" in keys, "missing no_results_declaration"
    nr = " ".join(keys["no_results_declaration"].split()).lower()
    assert "no empirical" in nr or "no empirical outcome" in nr, (
        "no_results_declaration must assert that no empirical outcome is present"
    )
    assert "falsification_summary" in keys, "missing falsification_summary"


def test_multiplicity_and_holdout_frozen() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    mult = " ".join(keys.get("multiplicity", "").split())
    assert "exactly three" in mult, "multiplicity must fix exactly three planned comparisons"
    assert "Holm" in mult, "multiplicity must name the Holm correction"
    assert "RQ2" in mult, "multiplicity must declare the RQ2 endpoint as primary"
    freeze = " ".join(keys.get("freezing_and_holdout", "").split()).lower()
    assert "freeze" in freeze, "holdout freeze rule must be declared"
    assert "inaccessible until" in freeze, "holdout must stay inaccessible until freeze"


def test_denominator_and_zero_event_policy_declared() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    assert "denominator_rule" in keys, "missing denominator_rule"
    assert "zero_event_policy" in keys, "missing zero_event_policy"
    for label in (
        "eligible",
        "attempted",
        "completed",
        "rejected",
        "indeterminate",
        "timeout",
        "not_run_external",
        "missing",
    ):
        assert re.search(rf"^  - {label}$", text, flags=re.MULTILINE), (
            f"outcome_accounting missing state: {label}"
        )
    zep = " ".join(keys["zero_event_policy"].split())
    assert "1 - 0.05**(1/N)" in zep, "zero-event bound formula must be recorded"


def test_baselines_b0_to_b4_covered() -> None:
    text = _load_text()
    rq_blocks = _rq_blocks(text)
    rq2_pc = _blob(rq_blocks["RQ2"]["paired_contrast"])
    for arm in ("B0", "B1", "B2", "B3", "B4"):
        assert arm in rq2_pc, f"RQ2 paired_contrast must cover arm {arm}"
    rq1_base = _blob(rq_blocks["RQ1"]["strongest_competing_baseline"])
    assert "xacml18" in rq1_base, "RQ1 strongest baseline must cite xacml18"


def test_engines_and_oracle_declared() -> None:
    text = _load_text()
    for engine in ("Cedar", "OpenFGA", "OPA"):
        assert engine in text, f"engine missing from registry: {engine}"
    rq3_oracle = _blob(_rq_blocks(text)["RQ3"]["independent_oracle"])
    for token in ("PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"):
        assert token in rq3_oracle, f"RQ3 oracle missing value {token}"


def test_falsification_summary_matches_global_contract() -> None:
    text = _load_text()
    keys = _top_level_keys(text)
    fs = " ".join(keys["falsification_summary"].split())
    assert "B3" in fs and "B1" in fs, "falsification summary must name B1 and B3"
    assert "Dataset/Tool" in fs, "falsification summary must name the fallback track"
