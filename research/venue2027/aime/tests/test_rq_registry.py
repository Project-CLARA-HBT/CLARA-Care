"""Structural tests for the AIME 2027 preregistered RQ registry (task AIME-rq_registry).

Purpose
-------
Stdlib-only structural gate for ``research/venue2027/aime/rq_and_estimands.yaml``.
It checks: exactly three RQs (RQ1-RQ3), each carrying every preregistration field
(independent unit, population, estimand, paired contrast, primary metric, secondary
metrics, null, alternative, minimum useful difference, confounders, power/analysis
method, falsification condition, primary endpoint); the blinded-clinician
adjudication contract fields (blinding, reviewer eligibility, agreement statistic);
the synthetic-only and preregistered-only standing declarations; the no-clinical-
efficacy claim discipline; and hard negatives — no invented empirical results,
no efficacy claim language, and no pooled-repeated-events-as-independent unit
wording.

Allowed input
-------------
The registry YAML file at repository path
``research/venue2027/aime/rq_and_estimands.yaml``. Parsing uses a stdlib-only
indentation/``key:`` subset parser (the registry is authored to that subset);
PyYAML is intentionally not imported so the gate runs on bare CPython.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``RQ_REGISTRY_``; pytest reports the failing check directly.

Version
-------
``RQ_REGISTRY_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

RQ_REGISTRY_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
REGISTRY_PATH = (
    REPO_ROOT / "research" / "venue2027" / "aime" / "rq_and_estimands.yaml"
)


def _load_registry_text() -> str:
    assert REGISTRY_PATH.is_file(), f"RQ_REGISTRY_MISSING: {REGISTRY_PATH}"
    return REGISTRY_PATH.read_text(encoding="utf-8")


def _scalar(value: str) -> object:
    """Coerce a YAML-subset scalar to bool/int/str."""
    text = value.strip().strip('"').strip("'")
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text in ("null", "~", ""):
        return None
    return text


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[dict, int]:
    """Parse a ``key:``/``key: value`` block of the registry's YAML subset.

    Handles nested mappings and ``- `` list items (mapping items, scalar items,
    and inline ``- key: value`` starts of mapping items). Block scalars are
    represented as joined text under their key; long folded lines are joined.
    """
    result: dict[str, object] = {}
    i = start
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            # Continuation of a folded block scalar for the previous key.
            i += 1
            continue
        list_match = re.match(r"^- (.+)$", stripped)
        if list_match is not None:
            # A list item at this level: treated by the caller via _parse_list.
            break
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", stripped)
        assert match is not None, f"RQ_REGISTRY_PARSE_ERROR line {i + 1}: {raw!r}"
        key, value = match.group(1), match.group(2)
        if value:
            result[key] = _scalar(value)
            i += 1
            continue
        # Block value: mapping or list below.
        j = i + 1
        child_indent: int | None = None
        is_list = False
        while j < len(lines):
            line = lines[j]
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                j += 1
                continue
            line_indent = len(line) - len(line.lstrip(" "))
            if line_indent <= indent:
                break
            if child_indent is None:
                child_indent = line_indent
                is_list = bool(re.match(r"^- ", line_stripped))
            break
        if child_indent is None:
            result[key] = ""
            i += 1
            continue
        if is_list:
            items, j2 = _parse_list(lines, j, child_indent)
            result[key] = items
            i = j2
        else:
            mapping, j2 = _parse_block(lines, j, child_indent)
            result[key] = mapping
            i = j2
    return result, i


def _parse_list(
    lines: list[str], start: int, indent: int
) -> tuple[list[object], int]:
    """Parse ``- `` list items; supports scalar items and mapping items."""
    items: list[object] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        line_indent = len(raw) - len(raw.lstrip(" "))
        if line_indent != indent or not stripped.startswith("- "):
            break
        item_text = stripped[2:]
        inline = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", item_text)
        if inline is None:
            items.append(_scalar(item_text))
            i += 1
            continue
        # Mapping item: first key inline, remainder parsed as a nested block.
        item_indent = line_indent + 2
        synth = lines[:i]
        synth.append(" " * item_indent + item_text)
        mapping, j = _parse_block(synth, i, item_indent)
        # _parse_block over the synthetic list breaks immediately; instead parse
        # the remaining keys at item_indent directly.
        mapping = {inline.group(1): _scalar(inline.group(2))}
        j = i + 1
        while j < len(lines):
            line = lines[j]
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                j += 1
                continue
            line_indent2 = len(line) - len(line.lstrip(" "))
            if line_indent2 != item_indent or line_stripped.startswith("- "):
                break
            match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", line_stripped)
            if match is None:
                break
            key, value = match.group(1), match.group(2)
            if value:
                mapping[key] = _scalar(value)
                j += 1
                continue
            # nested block under this key (deeper indent)
            k = j + 1
            child_indent2: int | None = None
            is_list2 = False
            while k < len(lines):
                nested = lines[k].strip()
                if not nested or nested.startswith("#"):
                    k += 1
                    continue
                nested_indent = len(lines[k]) - len(lines[k].lstrip(" "))
                if nested_indent <= item_indent:
                    break
                if child_indent2 is None:
                    child_indent2 = nested_indent
                    is_list2 = bool(re.match(r"^- ", nested))
                break
            if child_indent2 is None:
                mapping[key] = ""
                j += 1
                continue
            if is_list2:
                nested_items, k2 = _parse_list(lines, k, child_indent2)
                mapping[key] = nested_items
            else:
                nested_map, k2 = _parse_block(lines, k, child_indent2)
                mapping[key] = nested_map
            j = k2
        items.append(mapping)
        i = j
    return items, i


def _parse_registry(text: str) -> dict:
    """Parse the registry's YAML subset into a nested dict."""
    # Join folded continuation lines (deeper-indented plain text belonging to
    # the previous scalar key) so the block parser sees one logical line.
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("- ")
            and not re.match(r"^[A-Za-z0-9_.-]+:", stripped)
        ):
            if lines:
                lines[-1] = lines[-1].rstrip() + " " + stripped
                continue
        lines.append(raw)
    mapping, _ = _parse_block(lines, 0, 0)
    return mapping


def _load_registry() -> dict:
    return _parse_registry(_load_registry_text())


# --------------------------------------------------------------------------
# Positive controls
# --------------------------------------------------------------------------
def test_registry_top_level_sections_present() -> None:
    registry = _load_registry()
    for section in (
        "schema_version",
        "declarations",
        "blinded_adjudication_contract",
        "statistical_conventions",
        "rqs",
        "guardrails",
    ):
        assert section in registry, f"RQ_REGISTRY_SECTION_MISSING: {section}"


def test_exactly_three_rqs() -> None:
    registry = _load_registry()
    rqs = registry["rqs"]
    assert isinstance(rqs, list), "RQ_REGISTRY_RQS_NOT_LIST"
    assert len(rqs) == 3, f"RQ_REGISTRY_RQ_COUNT: {len(rqs)}"
    ids = [rq.get("id") for rq in rqs]
    assert ids == ["RQ1", "RQ2", "RQ3"], f"RQ_REGISTRY_RQ_IDS: {ids}"


def test_each_rq_has_all_preregistration_fields() -> None:
    registry = _load_registry()
    required = (
        "question",
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
    for rq in registry["rqs"]:
        missing = [field for field in required if field not in rq]
        assert not missing, f"RQ_REGISTRY_FIELD_MISSING {rq.get('id')}: {missing}"
        for field in required:
            if field == "secondary_metrics":
                assert isinstance(rq[field], list) and rq[field], (
                    f"RQ_REGISTRY_SECONDARY_EMPTY {rq.get('id')}"
                )
            elif field == "confounders":
                assert isinstance(rq[field], list) and len(rq[field]) >= 3, (
                    f"RQ_REGISTRY_CONFOUNDERS_THIN {rq.get('id')}"
                )
            else:
                value = str(rq[field])
                assert value.strip(), f"RQ_REGISTRY_FIELD_EMPTY {rq.get('id')}: {field}"


def test_each_rq_declares_null_and_alternative_distinct() -> None:
    registry = _load_registry()
    for rq in registry["rqs"]:
        assert rq["null_hypothesis"] != rq["alternative_hypothesis"], (
            f"RQ_REGISTRY_NULL_EQUALS_ALT {rq.get('id')}"
        )


def test_primary_endpoint_matches_registered_distinct_endpoint() -> None:
    registry = _load_registry()
    endpoint = "unsafe clinical action rate under consent/medication history changes"
    for rq in registry["rqs"]:
        assert str(rq.get("primary_endpoint", "")) == endpoint, (
            f"RQ_REGISTRY_ENDPOINT_MISMATCH {rq.get('id')}"
        )
    assert str(registry["declarations"]["primary_endpoint_registered"]) == endpoint, (
        "RQ_REGISTRY_ENDPOINT_REGISTRATION_MISMATCH"
    )


def test_blinded_adjudication_contract_fields() -> None:
    registry = _load_registry()
    contract = registry["blinded_adjudication_contract"]
    blinding = contract["blinding"]
    assert blinding["blinded"] is True, "RQ_REGISTRY_BLINDING_FALSE"
    for field in (
        "blinded_to_model_arm",
        "blinded_to_provider_identity",
        "blinded_to_method_labels",
    ):
        assert blinding[field] is True, f"RQ_REGISTRY_BLINDING_FIELD: {field}"
    eligibility = contract["reviewers"]["reviewer_eligibility"]
    assert isinstance(eligibility, list) and len(eligibility) >= 3, (
        "RQ_REGISTRY_ELIGIBILITY_THIN"
    )
    agreement = contract["inter_rater_agreement"]["statistic"]
    lowered = str(agreement).lower()
    assert "kappa" in lowered, f"RQ_REGISTRY_AGREEMENT_STATISTIC: {agreement}"
    assert contract["inter_rater_agreement"]["reported_not_assumed"] is True, (
        "RQ_REGISTRY_AGREEMENT_ASSUMED"
    )
    assert contract["reviewers"]["candidate_model_agent_never_reviews"] is True, (
        "RQ_REGISTRY_CANDIDATE_AS_REVIEWER"
    )


def test_blinded_review_language_present() -> None:
    text = _load_registry_text().lower()
    assert "blinded" in text, "RQ_REGISTRY_BLINDED_LANGUAGE"
    assert "third_reviewer_path" in text, "RQ_REGISTRY_THIRD_REVIEWER"
    assert "indeterminate" in text, "RQ_REGISTRY_INDETERMINATE_PRESERVED"


def test_synthetic_only_and_preregistered_only_language() -> None:
    registry = _load_registry()
    declarations = registry["declarations"]
    assert declarations["synthetic_only"] is True, "RQ_REGISTRY_SYNTHETIC_ONLY"
    assert declarations["no_real_phi"] is True, "RQ_REGISTRY_NO_REAL_PHI"
    assert declarations["preregistered_only"] is True, "RQ_REGISTRY_PREREGISTERED"
    assert declarations["no_clinical_efficacy_claim"] is True, (
        "RQ_REGISTRY_NO_EFFICACY_FLAG"
    )
    text = _load_registry_text().lower()
    assert "synthetic vignettes only" in text, "RQ_REGISTRY_SYNTHETIC_PHRASE"
    assert "no real phi" in text, "RQ_REGISTRY_NO_PHI_PHRASE"
    assert "synthetic action correctness is not clinical efficacy" in text, (
        "RQ_REGISTRY_EFFICACY_DISCLAIMER"
    )
    assert str(declarations["dataset"]) == "synthetic-aime-2027", (
        "RQ_REGISTRY_DATASET"
    )


def test_estimands_are_paired_contrasts() -> None:
    registry = _load_registry()
    for rq in registry["rqs"]:
        lowered = str(rq["paired_contrast"]).lower()
        assert "versus" in lowered, f"RQ_REGISTRY_CONTRAST_NOT_PAIRED {rq.get('id')}"
        arm_match = re.search(r"b\d", lowered)
        assert arm_match is not None, f"RQ_REGISTRY_CONTRAST_NO_ARM {rq.get('id')}"


def test_falsification_conditions_present_per_rq() -> None:
    registry = _load_registry()
    for rq in registry["rqs"]:
        lowered = str(rq["falsification_condition"]).lower()
        assert lowered.strip(), f"RQ_REGISTRY_FALSIFICATION_EMPTY {rq.get('id')}"
        # Each falsification condition names a concrete trigger, not boilerplate.
        assert any(
            token in lowered
            for token in ("indistinguishable", "no statistically supported", "not stable")
        ), f"RQ_REGISTRY_FALSIFICATION_GENERIC {rq.get('id')}"


def test_guardrails_forbid_pseudo_replication() -> None:
    registry = _load_registry()
    guardrails = registry["guardrails"]
    unit_rule = str(guardrails["unit_rule"]).lower()
    assert "clustered" in unit_rule, "RQ_REGISTRY_UNIT_RULE_NOT_CLUSTERED"
    assert str(guardrails["no_invented_results"]).strip(), "RQ_REGISTRY_NO_GUARD"


# --------------------------------------------------------------------------
# Negative / adversarial controls
# --------------------------------------------------------------------------
def test_no_invented_empirical_results() -> None:
    text = _load_registry_text()
    # No percentage-style observations and no p-value comparisons anywhere.
    assert not re.search(r"\b\d+(\.\d+)?%", text), "RQ_REGISTRY_PERCENTAGE_FOUND"
    assert not re.search(r"\bp\s*[<>=]\s*\d", text, flags=re.IGNORECASE), (
        "RQ_REGISTRY_PVALUE_FOUND"
    )
    # No efficacy-style claim language anywhere in a preregistration artifact.
    lowered = text.lower()
    for forbidden in (
        "clinically effective",
        "proves clinical efficacy",
        "demonstrates clinical efficacy",
        "statistically significant improvement was observed",
    ):
        assert forbidden not in lowered, f"RQ_REGISTRY_FORBIDDEN_PHRASE: {forbidden}"


def test_no_results_section_or_observed_outcomes() -> None:
    lines = _load_registry_text().lower().splitlines()
    for line in lines:
        stripped = line.strip()
        # A results/observed *section or field* (a YAML key line) is forbidden;
        # prose mentions inside declarations ("no empirical results") are fine.
        assert not re.match(r"^results\s*:", stripped), "RQ_REGISTRY_RESULTS_SECTION"
        assert not re.match(r"^observed\s*:", stripped), "RQ_REGISTRY_OBSERVED_FIELD"
        assert "effect size was" not in stripped, "RQ_REGISTRY_EFFECT_CLAIM"


def test_parser_rejects_pooled_independence_wording_in_unit_rule() -> None:
    registry = _load_registry()
    for rq in registry["rqs"]:
        lowered = str(rq["independent_unit"]).lower()
        assert "never independent units" in lowered or "clustered" in lowered, (
            f"RQ_REGISTRY_UNIT_PSEUDO_REPLICATION {rq.get('id')}"
        )


def test_adversarial_parser_missing_registry_fails() -> None:
    import unittest.mock

    with unittest.mock.patch.object(pathlib.Path, "is_file", return_value=False):
        try:
            _load_registry()
        except AssertionError as exc:
            assert "RQ_REGISTRY_MISSING" in str(exc), "RQ_REGISTRY_WRONG_ERROR"
        else:
            raise AssertionError("RQ_REGISTRY_MISSING_NOT_RAISED")


def test_registry_schema_version_frozen() -> None:
    registry = _load_registry()
    assert str(registry["schema_version"]) == "1.0.0", "RQ_REGISTRY_SCHEMA_VERSION"
    assert str(registry["study"]) == "aime", "RQ_REGISTRY_STUDY"
    assert str(registry["task_id"]) == "AIME-rq_registry", "RQ_REGISTRY_TASK_ID"
