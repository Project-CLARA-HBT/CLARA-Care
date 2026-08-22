"""Agreement analysis for blinded dual-model reviews; cases, not calls, are units.

Supports post-reconciliation analysis and optional frozen-duplicate self-consistency
(duplicate runs never increase N).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.model_adjudication.run_v2 import MODELS


def _initial_labels(result: dict[str, Any]) -> tuple[str, str]:
    reviews = (
        result.get("initial_reviews") if "initial_reviews" in result else result.get("reviews")
    )
    if not isinstance(reviews, list) or len(reviews) < 2:
        raise ValueError("model_review_analysis_reviews_missing")
    return (reviews[0]["review"]["label"], reviews[1]["review"]["label"])


def _final_labels(result: dict[str, Any]) -> tuple[str, str]:
    if result.get("status") in ("AGREED_AFTER_RECONCILIATION", "UNRESOLVED"):
        revised = result.get("revised_reviews")
        if not isinstance(revised, list) or len(revised) < 2:
            raise ValueError("model_review_analysis_revised_missing")
        return (revised[0]["review"]["label"], revised[1]["review"]["label"])
    return _initial_labels(result)


def _cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    labels = sorted(set(left) | set(right))
    expected = sum((left[label] / n) * (right[label] / n) for label in labels)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1 - expected)


def _self_consistency(
    canonical: list[dict[str, Any]], duplicates: list[dict[str, Any]]
) -> dict[str, Any] | None:
    primary = {r["case_id"]: r for r in canonical}
    comparisons = 0
    consistent = 0
    cases_with_duplicates: set[str] = set()
    for dup in duplicates:
        dup_of = dup.get("duplicate_of")
        if dup_of not in primary:
            continue
        cases_with_duplicates.add(dup_of)
        dup_labels = _final_labels(dup)
        primary_labels = _final_labels(primary[dup_of])
        comparisons += 2
        consistent += sum(dl == pl for dl, pl in zip(dup_labels, primary_labels, strict=True))
    if comparisons == 0:
        return None
    return {
        "duplicate_comparisons": comparisons,
        "consistent_comparisons": consistent,
        "rate": consistent / comparisons,
        "cases_with_duplicates": sorted(cases_with_duplicates),
    }


def analyze(data_dir: Path) -> dict[str, Any]:
    if data_dir.is_file():
        if (data_dir.parent / data_dir.stem).is_dir():
            data_dir = data_dir.parent / data_dir.stem
    if data_dir.is_dir():
        raw_items: list[Any] = [
            json.loads(path.read_text(encoding="utf-8")) for path in sorted(data_dir.glob("*.json"))
        ]
        results = [
            r
            for r in raw_items
            if isinstance(r, dict)
            and "case_id" in r
            and ("reviews" in r or "initial_reviews" in r)
        ]
    else:
        parsed = json.loads(data_dir.read_text(encoding="utf-8"))
        if isinstance(parsed, list):
            results = [r for r in parsed if isinstance(r, dict) and "case_id" in r]
        elif isinstance(parsed, dict) and "cases" in parsed:
            results = [r for r in parsed["cases"] if isinstance(r, dict) and "case_id" in r]
        else:
            results = [parsed] if isinstance(parsed, dict) and "case_id" in parsed else []
    canonical = [r for r in results if not r.get("frozen_duplicate")]
    duplicates = [r for r in results if r.get("frozen_duplicate")]
    if not canonical:
        raise ValueError("model_review_analysis_no_cases")
    initial_pairs = [_initial_labels(r) for r in canonical]
    final_pairs = [_final_labels(r) for r in canonical]
    n = len(canonical)
    initial_agreement = sum(a == b for a, b in initial_pairs) / n
    disagreement_count = sum(a != b for a, b in initial_pairs)
    reconciliation_count = sum(
        r.get("status") in ("AGREED_AFTER_RECONCILIATION", "UNRESOLVED") for r in canonical
    )
    post_agreement = sum(a == b for a, b in final_pairs) / n
    unresolved_count = sum(r.get("status") == "UNRESOLVED" for r in canonical)
    left_dist = Counter(a for a, _ in initial_pairs)
    right_dist = Counter(b for _, b in initial_pairs)
    out: dict[str, Any] = {
        "case_count": n,
        "initial_agreement": initial_agreement,
        "initial_cohens_kappa": _cohens_kappa(initial_pairs),
        "disagreement_count": disagreement_count,
        "reconciliation_count": reconciliation_count,
        "post_reconciliation_agreement": post_agreement,
        "unresolved_count": unresolved_count,
        "unresolved_rate": unresolved_count / n,
        "per_model_label_distribution": {
            "reviewer_a": {"model_id": MODELS[0], "labels": dict(sorted(left_dist.items()))},
            "reviewer_b": {"model_id": MODELS[1], "labels": dict(sorted(right_dist.items()))},
        },
        "unit_of_analysis": "case; model calls and retries are not independent units",
    }
    self_consistency = _self_consistency(canonical, duplicates)
    if self_consistency is not None:
        out["frozen_duplicate_self_consistency"] = self_consistency
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", "--raw-dir", "--reconciled", dest="data_dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(analyze(args.data_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)
