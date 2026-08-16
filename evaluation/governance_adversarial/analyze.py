"""Generate transparent GovRed aggregate results from classified raw rows."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.protocol import ARMS, FAMILIES, family_scope
from evaluation.governance_adversarial.validate_results import validate


def _flag(row: dict[str, str], name: str) -> bool:
    return row[name] == "true"


def _attack_success(row: dict[str, str]) -> bool:
    return any(_flag(row, name) for name in (
        "unauthorized_disclosure", "successful_bypass", "stale_or_unauthorized_commit",
        "wrong_subject_exposure", "cache_index_revocation_failure",
    )) or not _flag(row, "audit_reconstruction_complete")


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float | None]:
    if total == 0:
        return {"estimate": None, "lower": None, "upper": None}
    estimate = successes / total
    denominator = 1 + z * z / total
    center = (estimate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(estimate * (1 - estimate) / total + z * z / (4 * total * total)) / denominator
    return {"estimate": estimate, "lower": max(0.0, center - margin), "upper": min(1.0, center + margin)}


def _exact_mcnemar_pvalue(discordant_a: int, discordant_b: int) -> float | None:
    total = discordant_a + discordant_b
    if total == 0:
        return None
    lower_tail = sum(math.comb(total, index) for index in range(min(discordant_a, discordant_b) + 1)) / 2**total
    return min(1.0, 2 * lower_tail)


def analyze(results: Path, manifest: Path) -> dict[str, Any]:
    validate(results, manifest)
    with results.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    executed = [row for row in rows if row["run_status"] == "EXECUTED"]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in executed:
        grouped[(row["family"], row["arm"])].append(row)
    aggregates: list[dict[str, object]] = []
    for family in FAMILIES:
        for arm in ARMS:
            values = grouped[(family, arm)]
            primary = _attack_success_count(values)
            aggregates.append({
                "family": family,
                "reporting_scope": family_scope(family),
                "arm": arm,
                "executed_logical_cases": len(values),
                "not_run_logical_cases": sum(1 for row in rows if row["family"] == family and row["arm"] == arm and row["run_status"] == "NOT_RUN"),
                "attack_success": primary,
                "prohibited_disclosure": _rate(values, "unauthorized_disclosure"),
                "stale_or_unauthorized_commit": _rate(values, "stale_or_unauthorized_commit"),
                "latency_ms": _latency(values),
            })
    comparisons = _holm_adjust(_paired_comparisons(executed))
    primary_aggregates = [
        aggregate for aggregate in aggregates
        if aggregate["reporting_scope"] == "primary_authorization_drift"
    ]
    return {
        "schema_version": "govred-analysis-v1",
        "result_status": "classified_boundary_results",
        "unit_of_analysis": "frozen logical attack instance",
        "aggregate_outcomes": aggregates,
        "primary_authorization_drift_outcomes": primary_aggregates,
        "paired_attack_success_comparisons": comparisons,
        "not_run_rows": len(rows) - len(executed),
        "warning": "NOT RUN rows are not denominators; secondary stress families are not pooled into the primary endpoint.",
    }


def _rate(values: list[dict[str, str]], column: str) -> dict[str, object]:
    successes = sum(_flag(row, column) for row in values)
    return {"successes": successes, "total": len(values), "wilson_95": _wilson(successes, len(values))}


def _attack_success_count(values: list[dict[str, str]]) -> dict[str, object]:
    successes = sum(_attack_success(row) for row in values)
    return {"successes": successes, "total": len(values), "wilson_95": _wilson(successes, len(values))}


def _latency(values: list[dict[str, str]]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None}
    ordered = sorted(float(row["latency_ms"]) for row in values)
    return {"p50": _percentile(ordered, 0.5), "p95": _percentile(ordered, 0.95)}


def _percentile(values: list[float], fraction: float) -> float:
    index = (len(values) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return values[lower] if lower == upper else values[lower] + (values[upper] - values[lower]) * (index - lower)


def _paired_comparisons(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_case: dict[tuple[str, str], dict[str, bool]] = defaultdict(dict)
    for row in rows:
        by_case[(row["family"], row["case_id"])][row["arm"]] = _attack_success(row)
    comparisons: list[dict[str, object]] = []
    for family in FAMILIES:
        for left, right in (("UNBOUND", "GLHS_STRICT"), ("STATE_VERSION_ONLY", "GLHS_STRICT"), ("SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT")):
            pairs = [outcomes for (row_family, _), outcomes in by_case.items() if row_family == family and left in outcomes and right in outcomes]
            left_only = sum(outcomes[left] and not outcomes[right] for outcomes in pairs)
            right_only = sum(outcomes[right] and not outcomes[left] for outcomes in pairs)
            comparisons.append({"family": family, "reporting_scope": family_scope(family), "left_arm": left, "right_arm": right, "paired_cases": len(pairs), "left_only_failures": left_only, "right_only_failures": right_only, "exact_mcnemar_p_unadjusted": _exact_mcnemar_pvalue(left_only, right_only)})
    return comparisons


def _holm_adjust(comparisons: list[dict[str, object]]) -> list[dict[str, object]]:
    """Adjust planned arm contrasts within each reporting scope.

    Comparisons with no discordant pair have no p-value and are deliberately
    excluded from the correction denominator.
    """
    for scope in {str(item["reporting_scope"]) for item in comparisons}:
        indexed = [
            (index, item) for index, item in enumerate(comparisons)
            if item["reporting_scope"] == scope and item["exact_mcnemar_p_unadjusted"] is not None
        ]
        ordered = sorted(indexed, key=lambda pair: float(pair[1]["exact_mcnemar_p_unadjusted"]))
        total, previous = len(ordered), 0.0
        for rank, (_, item) in enumerate(ordered):
            adjusted = min(1.0, max(previous, float(item["exact_mcnemar_p_unadjusted"]) * (total - rank)))
            item["exact_mcnemar_p_holm"] = adjusted
            previous = adjusted
        for _, item in indexed:
            item["holm_family"] = scope
    for item in comparisons:
        if item["exact_mcnemar_p_unadjusted"] is None:
            item["exact_mcnemar_p_holm"] = None
            item["holm_family"] = item["reporting_scope"]
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = analyze(args.results, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
