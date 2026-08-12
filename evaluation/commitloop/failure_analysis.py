"""Development-only, sanitized failure analysis for sealed CommitLoop runs.

The analyser refuses the ``sealed_test`` partition.  It writes aggregates only:
no prompt, provider response, bundle, or subject identifier is copied into the
report.  Its recommendations are hypotheses for production investigation, not
post-hoc scoring changes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

TAXONOMY = (
    "MODEL_FORMAT_FAILURE",
    "TEMPORAL_SELECTION_ERROR",
    "KNOWLEDGE_TIME_ERROR",
    "CONFLICT_COLLAPSE",
    "STALE_STATE_LEAK",
    "PROVENANCE_LOSS",
    "OVER_DISCLOSURE",
    "OVER_REDACTION",
    "UNSUPPORTED_ASSERTION",
    "CRITICAL_OMISSION",
    "CONTEXT_OVERFLOW",
    "RETRIEVAL_MISS",
    "STATE_SERIALIZATION_ERROR",
    "STALE_WRITE_ACCEPTED",
    "UNNECESSARY_WRITE_REJECTION",
    "IDEMPOTENCY_FAILURE",
    "HIGH_MUTATION_CONTENTION",
    "PROMPT_INJECTION_SUCCESS",
    "DATASET_MAPPING_ERROR",
    "LATENCY_REGRESSION",
)

_CANDIDATES = {
    "MODEL_FORMAT_FAILURE": "Harden structured-output recovery at the provider boundary; preserve terminal failures.",
    "TEMPORAL_SELECTION_ERROR": "Exercise production bitemporal reconstruction and deterministic decisive-event ordering.",
    "KNOWLEDGE_TIME_ERROR": "Verify knowledge-time cutoffs in production snapshot reconstruction before retrieval/ranking.",
    "CONFLICT_COLLAPSE": "Preserve unresolved conflict state and provenance through the production GLHS/THSS serializer.",
    "STALE_STATE_LEAK": "Test state-version binding and revalidation using concurrent production transitions.",
    "PROVENANCE_LOSS": "Audit assertion-to-evidence links and manifest assertion hashes in the production THSS path.",
    "OVER_DISCLOSURE": "Audit purpose/actor minimization against authorized recall in production THSS.",
    "OVER_REDACTION": "Audit required-fact coverage before minimization in production THSS.",
    "CONTEXT_OVERFLOW": "Measure and reduce context serialization without removing decisive evidence.",
    "RETRIEVAL_MISS": "Inspect production temporal filtering and state-aware candidate ranking.",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _taxonomy(
    *, gold: dict[str, Any], output: dict[str, Any] | None, failed: bool, condition: str
) -> str:
    if failed or output is None:
        return "MODEL_FORMAT_FAILURE"
    prediction = output.get("prediction")
    if not isinstance(prediction, dict):
        return "MODEL_FORMAT_FAILURE"
    if prediction.get("evidence_state") != gold.get("evidence_state"):
        if gold.get("evidence_state") == "CONFLICTED":
            return "CONFLICT_COLLAPSE"
        if prediction.get("evidence_state") == "INSUFFICIENT_EVIDENCE":
            return "OVER_REDACTION" if condition == "glhs_hybrid_thss_strict" else "CRITICAL_OMISSION"
        return "UNSUPPORTED_ASSERTION"
    if prediction.get("timeliness_state") != gold.get("timeliness_state"):
        return "KNOWLEDGE_TIME_ERROR"
    if prediction.get("lifecycle_state") != gold.get("lifecycle_state"):
        if (
            prediction.get("lifecycle_state") == "OPEN"
            and gold.get("lifecycle_state")
            in {"CANCELLED", "SUPERSEDED", "SATISFIED", "PARTIALLY_SATISFIED"}
        ):
            return "STALE_STATE_LEAK"
        return "TEMPORAL_SELECTION_ERROR"
    return "UNSUPPORTED_ASSERTION"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen_cohort_metadata(
    *,
    frozen_cohort_path: Path | None,
    freeze_path: Path | None,
    selected_subjects: set[str],
    analysis_split: str,
) -> dict[str, dict[str, str]]:
    """Load only selected-subject strata after checking the pre-provider seal."""

    if (frozen_cohort_path is None) != (freeze_path is None):
        raise ValueError("frozen_cohort_and_freeze_must_be_supplied_together")
    if frozen_cohort_path is None or freeze_path is None:
        return {}
    freeze = _read_json(freeze_path)
    if freeze.get("cohort_sha256") != _sha256(frozen_cohort_path):
        raise ValueError("failure_analysis_frozen_cohort_hash_mismatch")
    metadata: dict[str, dict[str, str]] = {}
    for row in _read_jsonl(frozen_cohort_path):
        token = str(row.get("subject_token", ""))
        if token not in selected_subjects:
            continue
        split = str(row.get("split", ""))
        if split != analysis_split:
            raise ValueError("failure_analysis_cohort_split_mismatch")
        stratum = row.get("stratum")
        if not isinstance(stratum, str) or not stratum:
            raise ValueError("failure_analysis_cohort_stratum_invalid")
        metadata[token] = {"stratum": stratum, "split": split}
    if set(metadata) != selected_subjects:
        raise ValueError("failure_analysis_cohort_subject_inventory_mismatch")
    return metadata


def _gap_rows(
    *,
    totals: Counter[tuple[str, str, str]],
    correct: Counter[tuple[str, str, str]],
    dimension: str,
) -> list[dict[str, object]]:
    return [
        {
            "model": model,
            "condition": condition,
            dimension: value,
            "correct": correct[(model, condition, value)],
            "denominator": total,
            "accuracy": correct[(model, condition, value)] / total,
        }
        for (model, condition, value), total in sorted(totals.items())
    ]


def analyze_development_run(
    *,
    run_dir: Path,
    output_dir: Path,
    analysis_split: str = "development",
    frozen_cohort_path: Path | None = None,
    freeze_path: Path | None = None,
) -> dict[str, object]:
    """Produce aggregates for one non-final subject split from a sealed run."""

    if analysis_split == "sealed_test":
        raise ValueError("final_holdout_failure_analysis_forbidden")
    if analysis_split not in {"development", "validation"}:
        raise ValueError("analysis_split_invalid")
    manifest = _read_json(run_dir / "run_manifest.json")
    partitions = _read_json(run_dir / "partition_manifest.json")
    if not isinstance(partitions, dict):
        raise TypeError("partition_manifest_invalid")
    selected_subjects = {
        str(subject) for subject, split in partitions.items() if split == analysis_split
    }
    if not selected_subjects:
        raise ValueError("analysis_split_empty")
    commitments = {
        str(item["case_id"]): item
        for item in _read_jsonl(run_dir / "commitments.jsonl")
        if str(item.get("subject_token")) in selected_subjects
    }
    selected_cases = set(commitments)
    gold = {
        str(item["case_id"]): item
        for item in _read_jsonl(run_dir / "construction_gold.jsonl")
        if str(item.get("case_id")) in selected_cases
    }
    outputs = {
        str(item["key"]): item for item in _read_json(run_dir / "solver_outputs.json")
    }
    errors = {
        str(item["key"]): item for item in _read_json(run_dir / "error_ledger.json")
    }
    models = [str(item) for item in manifest["models"]]
    conditions = [str(item) for item in manifest["conditions"]]
    if not selected_cases or not selected_cases.issubset(gold):
        raise ValueError("analysis_case_inventory_invalid")
    cohort_metadata = _load_frozen_cohort_metadata(
        frozen_cohort_path=frozen_cohort_path,
        freeze_path=freeze_path,
        selected_subjects=selected_subjects,
        analysis_split=analysis_split,
    )
    perturbations = {
        str(item["case_id"]): str(item.get("variant_kind", "base"))
        for item in _read_jsonl(run_dir / "perturbation_manifest.jsonl")
        if str(item.get("case_id")) in selected_cases
    }

    failures: Counter[tuple[str, str, str, str, str, str]] = Counter()
    cell_totals: Counter[tuple[str, str, str]] = Counter()
    cell_correct: Counter[tuple[str, str, str]] = Counter()
    stratum_totals: Counter[tuple[str, str, str]] = Counter()
    stratum_correct: Counter[tuple[str, str, str]] = Counter()
    variant_totals: Counter[tuple[str, str, str]] = Counter()
    variant_correct: Counter[tuple[str, str, str]] = Counter()
    for case_id in sorted(selected_cases):
        item = commitments[case_id]
        domain = str(item.get("domain") or "unknown")
        subject = str(item["subject_token"])
        stratum = cohort_metadata.get(subject, {}).get("stratum", "unavailable")
        variant_kind = perturbations.get(case_id, "base")
        for model in models:
            for condition in conditions:
                key = f"{model}:{condition}:{case_id}"
                output = outputs.get(key)
                failed = key in errors
                label = _taxonomy(
                    gold=gold[case_id],
                    output=output,
                    failed=failed,
                    condition=condition,
                )
                prediction = output.get("prediction", {}) if output else {}
                exact = int(
                    isinstance(prediction, dict)
                    and all(
                        prediction.get(axis) == gold[case_id].get(axis)
                        for axis in ("lifecycle_state", "evidence_state", "timeliness_state")
                    )
                )
                coordinates = (model, condition, domain)
                cell_totals[coordinates] += 1
                cell_correct[coordinates] += exact
                stratum_coordinates = (model, condition, stratum)
                stratum_totals[stratum_coordinates] += 1
                stratum_correct[stratum_coordinates] += exact
                variant_coordinates = (model, condition, variant_kind)
                variant_totals[variant_coordinates] += 1
                variant_correct[variant_coordinates] += exact
                if not exact:
                    failures[(label, model, condition, domain, stratum, variant_kind)] += 1

    output_dir.mkdir(parents=True, exist_ok=False)
    taxonomy_rows = [
        {
            "taxonomy": label,
            "model": model,
            "condition": condition,
            "domain": domain,
            "stratum": stratum,
            "variant_kind": variant_kind,
            "count": count,
            "split": analysis_split,
        }
        for (label, model, condition, domain, stratum, variant_kind), count in sorted(
            failures.items()
        )
    ]
    _write_csv(
        output_dir / "failure_taxonomy.csv",
        taxonomy_rows,
        ["taxonomy", "model", "condition", "domain", "stratum", "variant_kind", "count", "split"],
    )
    clusters = [
        {**row, "cluster_id": f"{row['taxonomy']}:{row['model']}:{row['condition']}:{row['domain']}:{row['stratum']}:{row['variant_kind']}"}
        for row in taxonomy_rows
    ]
    (output_dir / "failure_clusters.json").write_text(
        json.dumps({"schema_version": "glhs-bench.failure-clusters.v1", "clusters": clusters}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    gap_rows = [
        {
            "model": model,
            "condition": condition,
            "domain": domain,
            "correct": cell_correct[(model, condition, domain)],
            "denominator": total,
            "accuracy": cell_correct[(model, condition, domain)] / total,
        }
        for (model, condition, domain), total in sorted(cell_totals.items())
    ]
    _write_csv(output_dir / "benchmark_gap_matrix.csv", gap_rows, ["model", "condition", "domain", "correct", "denominator", "accuracy"])
    _write_csv(
        output_dir / "stratum_gap_matrix.csv",
        _gap_rows(totals=stratum_totals, correct=stratum_correct, dimension="stratum"),
        ["model", "condition", "stratum", "correct", "denominator", "accuracy"],
    )
    _write_csv(
        output_dir / "variant_gap_matrix.csv",
        _gap_rows(totals=variant_totals, correct=variant_correct, dimension="variant_kind"),
        ["model", "condition", "variant_kind", "correct", "denominator", "accuracy"],
    )
    model_rows = []
    for model in models:
        rows = [row for row in gap_rows if row["model"] == model]
        correct, denominator = sum(int(row["correct"]) for row in rows), sum(int(row["denominator"]) for row in rows)
        model_rows.append({"model": model, "correct": correct, "denominator": denominator, "accuracy": correct / denominator})
    _write_csv(output_dir / "model_gap_matrix.csv", model_rows, ["model", "correct", "denominator", "accuracy"])
    source = str(_read_json(run_dir / "source_manifest.json").get("source", "unknown"))
    correct, denominator = sum(int(row["correct"]) for row in gap_rows), sum(int(row["denominator"]) for row in gap_rows)
    _write_csv(output_dir / "dataset_gap_matrix.csv", [{"dataset": source, "correct": correct, "denominator": denominator, "accuracy": correct / denominator}], ["dataset", "correct", "denominator", "accuracy"])
    domain_rows = []
    for domain in sorted({str(row["domain"]) for row in gap_rows}):
        rows = [row for row in gap_rows if row["domain"] == domain]
        d_correct, d_denominator = sum(int(row["correct"]) for row in rows), sum(int(row["denominator"]) for row in rows)
        domain_rows.append({"domain": domain, "correct": d_correct, "denominator": d_denominator, "accuracy": d_correct / d_denominator})
    _write_csv(output_dir / "domain_gap_matrix.csv", domain_rows, ["domain", "correct", "denominator", "accuracy"])

    counts = Counter({label: sum(count for (name, *_rest), count in failures.items() if name == label) for label in TAXONOMY})
    observed = [(name, count) for name, count in counts.items() if count]
    root_cause = [
        "# Development-only root-cause hypotheses",
        "",
        "This is an aggregate, synthetic software analysis. It excludes the sealed test split and does not alter scoring or task selection.",
        "",
        "| Failure taxonomy | Count | Production investigation |",
        "| --- | ---: | --- |",
        *[f"| {name} | {count} | {_CANDIDATES.get(name, 'Classify with a focused production-path regression test.')} |" for name, count in observed],
    ]
    (output_dir / "root_cause_analysis.md").write_text("\n".join(root_cause) + "\n", encoding="utf-8")
    candidates = [
        "# Improvement candidates",
        "",
        "Each candidate is a hypothesis requiring a production-path test, a development rerun, and validation before final evaluation.",
        "",
    ]
    for index, (name, _count) in enumerate(observed, start=1):
        candidates.extend([f"## IMP-{index:03d}: {name}", "", _CANDIDATES.get(name, "Add focused classification and regression coverage."), ""])
    (output_dir / "improvement_candidates.md").write_text("\n".join(candidates), encoding="utf-8")
    return {
        "schema_version": "glhs-bench.failure-analysis.v1",
        "status": "DEVELOPMENT_ONLY",
        "split": analysis_split,
        "subject_count": len(selected_subjects),
        "case_count": len(selected_cases),
        "failure_count": sum(failures.values()),
        "cohort_strata_verified": bool(cohort_metadata),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "validation"), default="development")
    parser.add_argument("--frozen-cohort", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze_development_run(run_dir=args.run_dir, output_dir=args.output, analysis_split=args.split, frozen_cohort_path=args.frozen_cohort, freeze_path=args.freeze), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
