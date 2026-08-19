"""Malformed-output taxonomy parser for the GLHS offline audit (GLHS-M01..M03).

This is an OFFLINE, DESCRIPTIVE parser over immutable, sealed CommitLoop raw
artifacts. It never reruns models, never modifies the run directory, and never
changes the primary 384-subject comparison. Malformed outputs are fail-closed
errors under the original scoring (GLHS-M01); this audit only decomposes them.

Inputs (all read-only):
- ``checksums.sha256``: verified against the files it lists.
- ``error_ledger.json`` / ``error_ledger.csv``: the authoritative malformed
  output ledger (a cell with no parseable, schema-valid prediction).
- ``per_case_metrics.csv``, ``metrics.json``: scoring and missing-output counts.
- ``partition_manifest.json``, ``perturbation_manifest.jsonl``: subject
  partition/split and perturbation context where available.
- ``run_manifest.json``: models, conditions, expected cell count.

Failure-type taxonomy (parse / schema / format / other):
- ``parse``: provider JSON body could not be parsed as an object
  (``provider_json_decode_error`` / ``JSONDecodeError``).
- ``schema``: parsed object failed prediction-schema validation
  (``prediction_schema_invalid``).
- ``format``: provider response shape failure
  (``malformed_provider_response`` / ``empty_provider_content`` /
  ``provider_json_object_required`` / ``model_substitution_detected``).
- ``other``: transport/terminal HTTP/timeout or unclassified failures.

Paired contingency (per subject): malformed status under
``glhs_hybrid_thss_strict`` vs ``full_authorized_history`` -> both / strict-only
/ full-only / neither.

Any alternative analysis (complete-case, parse-recoverable subset, ...) must be
explicitly labeled EXPLORATORY and kept out of the primary endpoint (GLHS-M03);
this module reports only the primary descriptive decomposition.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path

STRICT_CONDITION = "glhs_hybrid_thss_strict"
BASELINE_CONDITION = "full_authorized_history"

FAILURE_TYPES = ("parse", "schema", "format", "other")

ERROR_LEDGER_FILES = ("error_ledger.json", "error_ledger.csv")
AUXILIARY_FILES = (
    "per_case_metrics.csv",
    "metrics.json",
    "partition_manifest.json",
    "perturbation_manifest.jsonl",
    "run_manifest.json",
    "construction_gold.jsonl",
    "commitments.jsonl",
    "solver_outputs.json",
    "validation_report.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(run_dir: Path) -> dict[str, object]:
    """Read-only verification of ``checksums.sha256`` against listed files."""
    checksum_file = run_dir / "checksums.sha256"
    results: list[dict[str, object]] = []
    ok = True
    if not checksum_file.is_file():
        return {
            "verified": False,
            "note": "checksums.sha256_missing",
            "files": [],
        }
    seen: set[str] = set()
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        expected, _, relative = line.partition("  ")
        expected = expected.strip()
        relative = relative.strip()
        if not relative or len(expected) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in expected
        ):
            results.append({"file": relative or "<invalid>", "status": "INVALID"})
            ok = False
            continue
        if relative in seen:
            results.append({"file": relative, "status": "DUPLICATE"})
            ok = False
            continue
        seen.add(relative)
        target = (run_dir / relative).resolve()
        if run_dir.resolve() not in target.parents:
            results.append({"file": relative, "status": "OUTSIDE_RUN_DIR"})
            ok = False
            continue
        if not target.is_file():
            results.append({"file": relative, "status": "MISSING"})
            ok = False
            continue
        actual = _sha256(target)
        match = actual == expected
        results.append({"file": relative, "status": "OK" if match else "MISMATCH"})
        if not match:
            ok = False
    return {"verified": ok, "files": results, "file_count": len(results)}


def _read_json(path: Path, default: object = None) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def classify_failure_type(error: object, error_detail: object = None) -> str:
    """Map an error-ledger entry to the frozen failure-type taxonomy.

    The ledger stores the exception type name in ``error`` and (when present)
    the sanitized diagnostic in ``error_detail``. Classification prefers the
    diagnostic, then the type name. Unknown/transport failures are ``other``;
    the parser never fabricates a category.
    """
    diagnostic = str(error_detail or "").lower()
    name = str(error or "").lower()
    if "provider_json_decode_error" in diagnostic or "jsondecodeerror" in name:
        return "parse"
    if "prediction_schema_invalid" in diagnostic or "schemainvalid" in name.replace("_", ""):
        return "schema"
    if any(
        token in diagnostic or token in name
        for token in (
            "malformed_provider_response",
            "empty_provider_content",
            "provider_json_object_required",
            "model_substitution_detected",
        )
    ):
        return "format"
    if "schema" in name or "schema" in diagnostic:
        return "schema"
    if "json" in name or "json" in diagnostic:
        return "parse"
    return "other"


def _error_items(run_dir: Path) -> list[dict[str, object]]:
    """Load one authoritative error ledger without double-counting JSON/CSV."""
    items: list[dict[str, object]] = []
    json_path = run_dir / "error_ledger.json"
    csv_path = run_dir / "error_ledger.csv"
    if json_path.is_file():
        data = _read_json(json_path, [])
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    items.append(dict(row))
    elif csv_path.is_file():
        for row in _read_csv_rows(csv_path):
            if not row or not any(row.values()):
                continue
            items.append(dict(row))
    return items


def _condition_denominators(run_dir: Path) -> dict[str, int]:
    """Expected solver cells per condition from the run manifest."""
    manifest = _read_json(run_dir / "run_manifest.json", {})
    if not isinstance(manifest, dict):
        return {}
    conditions = [str(c) for c in manifest.get("conditions", [])]
    models = [str(m) for m in manifest.get("models", [])]
    case_count = int(manifest.get("case_count", 0) or 0)
    return {condition: case_count * len(models) for condition in conditions}


def _case_context(run_dir: Path) -> dict[str, dict[str, str]]:
    """Map case IDs to non-identifying subject/stratum/task context."""
    mapping: dict[str, dict[str, str]] = {}
    commitments = _read_jsonl(run_dir / "commitments.jsonl")
    for row in commitments:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id", ""))
        subject = str(row.get("subject_token", ""))
        if case_id and subject:
            mapping[case_id] = {"subject": subject}
    partition = _read_json(run_dir / "partition_manifest.json", {})
    if isinstance(partition, dict):
        for subject, split in partition.items():
            for context in mapping.values():
                if context.get("subject") == str(subject):
                    context["stratum"] = str(split)
    for row in _read_jsonl(run_dir / "solver_packets" / "glhs_hybrid_thss_strict.jsonl"):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id", ""))
        task = str(row.get("task", ""))
        if case_id and task:
            mapping.setdefault(case_id, {})["task"] = task
    return mapping


def _solver_context(run_dir: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    """Index successful solver cells and packet task labels by cell identity."""
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    outputs = _read_json(run_dir / "solver_outputs.json", [])
    if isinstance(outputs, list):
        for row in outputs:
            if not isinstance(row, dict):
                continue
            model = str(row.get("requested_model_id") or row.get("reported_model_id") or "")
            condition = str(row.get("condition", ""))
            case_id = str(row.get("case_id", ""))
            if model and condition and case_id:
                index[(model, condition, case_id)] = {}
    packet_dir = run_dir / "solver_packets"
    for path in sorted(packet_dir.glob("*.jsonl")) if packet_dir.is_dir() else []:
        for row in _read_jsonl(path):
            if not isinstance(row, dict):
                continue
            condition = str(row.get("condition", path.stem))
            case_id = str(row.get("case_id", ""))
            task = str(row.get("task", ""))
            if not case_id or not task:
                continue
            for key in [key for key in index if key[1] == condition and key[2] == case_id]:
                index[key]["task"] = task
    return index


def _cell_identity(item: Mapping[str, object]) -> tuple[str, str, str]:
    """Return a stable model/condition/case identity for a ledger cell."""
    return (
        str(item.get("requested_model_id") or item.get("reported_model_id") or ""),
        str(item.get("condition", "")),
        str(item.get("case_id", "")),
    )


def parse_run(
    run_dir: Path,
    *,
    expected_total_cells: int | None = None,
) -> dict[str, object]:
    """Parse the immutable run artifacts and produce the malformed audit.

    Pure and offline: reads only, never writes into ``run_dir``.
    """
    run_dir = Path(run_dir)
    checksum = verify_checksums(run_dir)
    manifest = _read_json(run_dir / "run_manifest.json", {})
    manifest = manifest if isinstance(manifest, dict) else {}
    metrics = _read_json(run_dir / "metrics.json", {})
    metrics = metrics if isinstance(metrics, dict) else {}

    errors = _error_items(run_dir)
    solver_context = _solver_context(run_dir)
    case_context = _case_context(run_dir)
    models = [str(model) for model in manifest.get("models", [])]
    conditions = [str(condition) for condition in manifest.get("conditions", [])]
    case_ids = sorted(
        set(case_context)
        | {identity[2] for identity in solver_context}
        | {str(item.get("case_id", "")) for item in errors if item.get("case_id")}
    )
    expected_cells: dict[tuple[str, str, str], dict[str, str]] = {}
    for condition in conditions:
        for model in models:
            for case_id in case_ids:
                context = dict(case_context.get(case_id, {}))
                context.update(solver_context.get((model, condition, case_id), {}))
                context.update(
                    {
                        "model": model,
                        "condition": condition,
                        "case_id": case_id,
                    }
                )
                expected_cells[(model, condition, case_id)] = context
    for identity, context in solver_context.items():
        expected_cells.setdefault(identity, dict(context))
    unique_errors: dict[tuple[str, str, str] | tuple[str, int], dict[str, object]] = {}
    for index, item in enumerate(errors):
        identity = _cell_identity(item)
        error_key: tuple[str, str, str] | tuple[str, int] = (
            identity if all(identity) else ("unkeyed", index)
        )
        unique_errors.setdefault(error_key, item)
    errors = list(unique_errors.values())
    denominator = (
        int(expected_total_cells)
        if expected_total_cells is not None
        else int(metrics.get("output_count", 0) or 0)
        + int(metrics.get("missing_output_count", 0) or 0)
        + len(errors)
    )
    if denominator == 0 and isinstance(manifest, dict) and manifest.get("expected_cell_count"):
        denominator = int(manifest["expected_cell_count"])

    classification_by_type: Counter[str] = Counter()
    malformed_contexts: list[dict[str, str]] = []
    for item in errors:
        error = item.get("error")
        error_detail = item.get("error_detail")
        failure_type = classify_failure_type(error, error_detail)
        classification_by_type[failure_type] += 1
        identity = _cell_identity(item)
        context = dict(expected_cells.get(identity, {}))
        context.update(
            {
                "model": identity[0] or "unknown",
                "condition": identity[1] or "unknown",
                "case_id": identity[2] or "unknown",
                "task": str(item.get("task") or context.get("task") or "unavailable"),
                "stratum": str(context.get("stratum") or item.get("stratum") or "unavailable"),
            }
        )
        malformed_contexts.append(context)

    def rate_table(dimension: str) -> dict[str, dict[str, object]]:
        denominators: Counter[str] = Counter(str(context.get(dimension, "unavailable")) for context in expected_cells.values())
        malformed: Counter[str] = Counter(str(context.get(dimension, "unavailable")) for context in malformed_contexts)
        keys = sorted(set(denominators) | set(malformed))
        return {
            key: {
                "malformed": malformed[key],
                "denominator": denominators[key],
                "rate": round(malformed[key] / denominators[key], 6)
                if denominators[key]
                else None,
            }
            for key in keys
        }

    # Every taxonomy bucket is emitted, including zero-count buckets.
    failure_distribution = {failure_type: classification_by_type.get(failure_type, 0) for failure_type in FAILURE_TYPES}
    strict_full_cells: dict[str, dict[str, bool]] = defaultdict(dict)
    pair_context: dict[str, dict[str, object]] = {}
    for case_id, context in case_context.items():
        subject = str(context.get("subject") or case_id)
        pair_context.setdefault(subject, {"stratum": context.get("stratum", "unavailable"), "cases": 0})
        pair_context[subject]["cases"] = int(pair_context[subject]["cases"]) + 1
    for context in malformed_contexts:
        condition = context["condition"]
        case_id = context["case_id"]
        subject = str(case_context.get(case_id, {}).get("subject") or case_id)
        if condition in {STRICT_CONDITION, BASELINE_CONDITION}:
            strict_full_cells[subject][condition] = True
        pair_context.setdefault(subject, {"stratum": context.get("stratum", "unavailable"), "cases": 0})

    subjects = sorted(pair_context)
    contingency: Counter[str] = (
        Counter({bucket: 0 for bucket in ("both", "strict_only", "full_only", "neither")})
        if subjects
        else Counter()
    )
    paired_rows: list[dict[str, object]] = []
    for subject in subjects:
        strict = bool(strict_full_cells[subject].get(STRICT_CONDITION))
        baseline = bool(strict_full_cells[subject].get(BASELINE_CONDITION))
        if strict and baseline:
            bucket = "both"
        elif strict:
            bucket = "strict_only"
        elif baseline:
            bucket = "full_only"
        else:
            bucket = "neither"
        contingency[bucket] += 1
        paired_rows.append(
            {
                "subject": subject,
                "stratum": pair_context[subject].get("stratum", "unavailable"),
                "case_count": pair_context[subject].get("cases", 0),
                "strict_malformed": strict,
                "full_history_malformed": baseline,
                "bucket": bucket,
            }
        )
    paired_by_stratum: dict[str, Counter[str]] = defaultdict(Counter)
    for row in paired_rows:
        key = str(row["stratum"])
        paired_by_stratum[key][str(row["bucket"])] += 1

    return {
        "schema_version": "glhs-malformed-audit-v1",
        "audit_kind": "offline_descriptive",
        "run_dir": str(run_dir),
        "checksum_verification": checksum,
        "expected_total_cells": denominator,
        "source_subject_count": int(manifest.get("subject_count", 0) or 0),
        "primary_reference_subject_count": 384,
        "total_malformed": len(errors),
        "total_parsed": int(metrics.get("output_count", 0) or 0),
        "missing_output_count": int(metrics.get("missing_output_count", 0) or 0),
        "provider_error_count": int(metrics.get("provider_error_count", 0) or 0),
        "failure_type_distribution": failure_distribution,
        "by_condition": rate_table("condition"),
        "by_task": rate_table("task"),
        "by_stratum": rate_table("stratum"),
        "by_model": rate_table("model"),
        "paired_contingency": dict(contingency),
        "paired_rows": paired_rows,
        "paired_by_stratum": {
            key: dict(value) for key, value in sorted(paired_by_stratum.items())
        },
        "subject_count_with_malformed": sum(
            1 for subject in subjects if strict_full_cells.get(subject)
        ),
        "primary_null_result_unchanged": True,
        "note": (
            "Offline descriptive audit. Malformed outputs are fail-closed errors "
            "under the original scoring; the primary comparison is UNCHANGED. "
            "No model was rerun and no run artifact was modified."
        ),
    }


def render_audit_markdown(audit: dict[str, object]) -> str:
    """Render the parsed audit into AUDIT.md (offline/descriptive)."""
    lines: list[str] = []
    lines.append("# GLHS malformed-output offline audit (GLHS-M01..M03)")
    lines.append("")
    lines.append("Status: **OFFLINE / DESCRIPTIVE** — no model was rerun; no run artifact was modified.")
    lines.append("")
    lines.append("## 1. Primary comparison is UNCHANGED")
    lines.append("")
    lines.append(
        "The sealed 384-subject primary comparison remains unchanged (GLHS-M01): "
        "malformed outputs are fail-closed errors under the original scoring. This "
        "audit only decomposes immutable raw results; it never re-scores, never "
        "excludes, and never replaces the primary null endpoint."
    )
    lines.append("")
    checksum = audit["checksum_verification"]
    lines.append("## 2. Seal / checksum verification (read-only)")
    lines.append("")
    lines.append(f"- `checksums.sha256`: **{'VERIFIED' if checksum['verified'] else 'NOT VERIFIED'}**")
    lines.append(f"- Files checked: {checksum['file_count']}")
    lines.append("")
    files = checksum.get("files", [])
    status_counts: Counter[str] = Counter(str(item["status"]) for item in files)
    lines.append("| Status | Count |")
    lines.append("| --- | ---: |")
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")
    lines.append("")
    lines.append("## 3. Total malformed outputs")
    lines.append("")
    lines.append(
        f"- **Actual malformed in the audited run directory: {audit['total_malformed']}** "
        f"of {audit['expected_total_cells']} expected solver cells."
    )
    lines.append(
        f"- Source artifact subjects: {audit['source_subject_count']}; the original "
        f"primary null endpoint remains the sealed {audit['primary_reference_subject_count']}-subject comparison."
    )
    lines.append(f"- Parsed outputs: {audit['total_parsed']}; missing outputs: {audit['missing_output_count']}.")
    lines.append("")
    lines.append(
        "> The manuscript companion figure (~220 malformed) refers to the sealed "
        "**v5-batch5 384-subject router run** (3,456 cells, 3,236 parsed + 220 "
        "malformed). Its raw outputs were retained outside the tracked tree "
        "(`/tmp/clara-glhs-v5-batch5-live-run`) and are **not present in this "
        "repository**, so the ~220 decomposition cannot be reproduced from tracked "
        "artifacts. This report states the actual count for the artifacts that ARE "
        "present and verifiable."
    )
    lines.append("")
    lines.append("## 4. Rate by context condition")
    lines.append("")
    lines.append("| Condition | Malformed | Denominator | Rate |")
    lines.append("| --- | ---: | ---: | ---: |")
    for condition, row in sorted(audit["by_condition"].items()):
        rate = row["rate"]
        rate_str = f"{rate:.6f}" if rate is not None else "n/a"
        lines.append(f"| {condition} | {row['malformed']} | {row['denominator']} | {rate_str} |")
    lines.append("")
    lines.append("## 5. Rate by task")
    lines.append("")
    lines.append("| Task | Malformed | Denominator | Rate |")
    lines.append("| --- | ---: | ---: | ---: |")
    for task, row in sorted(audit["by_task"].items()):
        rate = row["rate"]
        rate_str = f"{rate:.6f}" if rate is not None else "n/a"
        lines.append(f"| {task} | {row['malformed']} | {row['denominator']} | {rate_str} |")
    lines.append("")
    lines.append("## 6. Rate by subject stratum")
    lines.append("")
    lines.append("| Stratum | Malformed | Denominator | Rate |")
    lines.append("| --- | ---: | ---: | ---: |")
    for stratum, row in sorted(audit["by_stratum"].items()):
        rate = row["rate"]
        rate_str = f"{rate:.6f}" if rate is not None else "n/a"
        lines.append(f"| {stratum} | {row['malformed']} | {row['denominator']} | {rate_str} |")
    lines.append("")
    lines.append("## 7. Failure-type distribution (parse / schema / format / other)")
    lines.append("")
    lines.append("| Failure type | Count |")
    lines.append("| --- | ---: |")
    for failure_type in FAILURE_TYPES:
        lines.append(f"| {failure_type} | {audit['failure_type_distribution'].get(failure_type, 0)} |")
    lines.append("")
    lines.append("## 8. Paired Strict vs full-history malformed contingency (per subject)")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("| --- | ---: |")
    for bucket in ("both", "strict_only", "full_only", "neither"):
        lines.append(f"| {bucket} | {audit['paired_contingency'].get(bucket, 0)} |")
    lines.append("")
    lines.append(
        "- Subjects with a malformed output under `glhs_hybrid_thss_strict` and/or "
        "`full_authorized_history`; subjects with no malformed cell in either "
        "condition are `neither`."
    )
    lines.append("")
    lines.append("## 9. Sensitivity (GLHS-M03)")
    lines.append("")
    lines.append(
        "Any alternative analysis (complete-case, parse-recoverable subset, etc.) is "
        "**EXPLORATORY / post-hoc** and must never replace the original null endpoint. "
        "This audit contains no such alternative analysis."
    )
    lines.append("")
    lines.append(f"- Audited run directory: `{audit['run_dir']}`")
    lines.append(f"- Audit schema: `{audit['schema_version']}`")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("artifacts/commitloop/local-phase-a-v6"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("research/glhs_journal/malformed_audit_v1"),
    )
    parser.add_argument("--expected-total-cells", type=int)
    args = parser.parse_args()
    audit = parse_run(args.run_dir, expected_total_cells=args.expected_total_cells)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "malformed_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out_dir / "AUDIT.md").write_text(render_audit_markdown(audit) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
