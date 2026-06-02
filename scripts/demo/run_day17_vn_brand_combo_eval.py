#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ML_SRC = ROOT / "services" / "ml" / "src"
if str(ML_SRC) not in sys.path:
    sys.path.insert(0, str(ML_SRC))

from clara_ml.agents.careguard import run_careguard_analyze  # noqa: E402


DEFAULT_BRAND_CASES_PATH = ROOT / "data" / "demo" / "vn_brand_combo_eval.json"
DEFAULT_DDI_GOLDSET_PATH = ROOT / "data" / "demo" / "ddi-goldset.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "demo"
DEFAULT_DOC_PATH = ROOT / "docs" / "hackathon" / "day17-vn-brand-combo-eval.md"


@dataclass
class BrandCaseResult:
    input_name: str
    expected_normalized: str
    actual_normalized: str
    passed: bool
    mapped_count: int
    normalization_confidence: float


def _load_brand_cases(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid brand case payload at {path}")
    cases: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        input_name = str(item.get("input", "")).strip()
        expected = str(item.get("expected_normalized", "")).strip().lower()
        if not input_name or not expected:
            continue
        cases.append({"input": input_name, "expected_normalized": expected})
    if not cases:
        raise ValueError(f"No valid brand/combo cases loaded from {path}")
    return cases


def _load_ddi_goldset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _severity_rank(value: str) -> int:
    normalized = _normalize_text(value)
    if normalized == "critical":
        return 4
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def evaluate_brand_combo_cases(cases: list[dict[str, str]]) -> dict[str, Any]:
    results: list[BrandCaseResult] = []
    for case in cases:
        input_name = case["input"]
        expected = case["expected_normalized"]
        payload = run_careguard_analyze(
            {
                "medications": [input_name],
                "external_ddi_enabled": False,
            }
        )
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        normalized_inputs = metadata.get("normalized_inputs", [])
        if not isinstance(normalized_inputs, list):
            normalized_inputs = []
        actual = ""
        if normalized_inputs:
            first = normalized_inputs[0]
            if isinstance(first, dict):
                actual = _normalize_text(str(first.get("normalized_name", "")))
            else:
                actual = _normalize_text(str(first))
        confidence = float(metadata.get("normalization_confidence", 0.0) or 0.0)
        mapped_count = int(metadata.get("vn_dictionary_mapped_count", 0) or 0)
        results.append(
            BrandCaseResult(
                input_name=input_name,
                expected_normalized=expected,
                actual_normalized=actual,
                passed=actual == expected,
                mapped_count=mapped_count,
                normalization_confidence=confidence,
            )
        )

    passed = sum(1 for item in results if item.passed)
    total = len(results)
    accuracy = passed / total if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": accuracy,
        "results": [
            {
                "input": item.input_name,
                "expected_normalized": item.expected_normalized,
                "actual_normalized": item.actual_normalized,
                "passed": item.passed,
                "mapped_count": item.mapped_count,
                "normalization_confidence": item.normalization_confidence,
            }
            for item in results
        ],
    }


def evaluate_critical_ddi_miss(ddi_cases: list[dict[str, Any]]) -> dict[str, Any]:
    critical_cases = [
        row
        for row in ddi_cases
        if bool(row.get("expected_alert"))
        and _severity_rank(str(row.get("expected_min_severity", ""))) >= _severity_rank("high")
    ]
    evaluations: list[dict[str, Any]] = []
    for row in critical_cases:
        medications = row.get("medications", [])
        if not isinstance(medications, list):
            medications = []
        payload = run_careguard_analyze(
            {
                "medications": medications,
                "external_ddi_enabled": False,
            }
        )
        ddi_alerts = payload.get("ddi_alerts", []) if isinstance(payload, dict) else []
        if not isinstance(ddi_alerts, list):
            ddi_alerts = []
        max_actual = max(
            (_severity_rank(str(alert.get("severity", ""))) for alert in ddi_alerts if isinstance(alert, dict)),
            default=0,
        )
        expected_rank = _severity_rank(str(row.get("expected_min_severity", "")))
        hit = max_actual >= expected_rank and max_actual >= _severity_rank("high")
        evaluations.append(
            {
                "case_id": row.get("case_id", ""),
                "medications": medications,
                "expected_min_severity": row.get("expected_min_severity", ""),
                "actual_max_severity_rank": max_actual,
                "hit": hit,
            }
        )

    total = len(evaluations)
    hits = sum(1 for item in evaluations if item["hit"])
    misses = total - hits
    miss_rate = misses / total if total else 0.0
    return {
        "total_high_expected_cases": total,
        "high_detected_cases": hits,
        "critical_ddi_miss_cases": misses,
        "critical_ddi_miss_rate": miss_rate,
        "evaluations": evaluations,
    }


def _render_markdown(report: dict[str, Any], output_json_path: Path) -> str:
    brand = report["brand_combo"]
    critical = report["critical_ddi"]
    generated_at = report["generated_at"]
    lines = [
        "# Day 17 Evaluation Report",
        "",
        f"- Generated at: `{generated_at}`",
        f"- JSON artifact: `{output_json_path.relative_to(ROOT)}`",
        "",
        "## VN Brand/Combo Mapping",
        "",
        f"- Total: **{brand['total']}**",
        f"- Passed: **{brand['passed']}**",
        f"- Failed: **{brand['failed']}**",
        f"- Accuracy: **{brand['accuracy'] * 100:.2f}%**",
        "",
        "| Input | Expected | Actual | Result |",
        "|---|---|---|---|",
    ]
    for row in brand["results"]:
        result = "PASS" if row["passed"] else "FAIL"
        lines.append(
            f"| {row['input']} | {row['expected_normalized']} | {row['actual_normalized']} | {result} |"
        )

    lines.extend(
        [
            "",
            "## Critical DDI Miss",
            "",
            f"- High/Critical expected cases: **{critical['total_high_expected_cases']}**",
            f"- High/Critical detected: **{critical['high_detected_cases']}**",
            f"- Miss cases: **{critical['critical_ddi_miss_cases']}**",
            f"- Miss rate: **{critical['critical_ddi_miss_rate'] * 100:.2f}%**",
            "",
            "> Note: This evaluation uses local DDI engine (`external_ddi_enabled=false`) for deterministic Day 17 check.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Day 17 evaluator for VN brand/combo mapping and critical DDI miss."
    )
    parser.add_argument(
        "--brand-cases",
        default=str(DEFAULT_BRAND_CASES_PATH),
        help="Path to VN brand/combo case JSON file.",
    )
    parser.add_argument(
        "--ddi-goldset",
        default=str(DEFAULT_DDI_GOLDSET_PATH),
        help="Path to DDI goldset JSONL file.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for JSON report.",
    )
    parser.add_argument(
        "--markdown-out",
        default=str(DEFAULT_DOC_PATH),
        help="Markdown report output path.",
    )
    args = parser.parse_args()

    brand_cases_path = Path(args.brand_cases).resolve()
    ddi_goldset_path = Path(args.ddi_goldset).resolve()
    out_dir = Path(args.out_dir).resolve()
    markdown_path = Path(args.markdown_out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    brand_cases = _load_brand_cases(brand_cases_path)
    ddi_cases = _load_ddi_goldset(ddi_goldset_path)

    brand_report = evaluate_brand_combo_cases(brand_cases)
    critical_report = evaluate_critical_ddi_miss(ddi_cases)

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "brand_combo": brand_report,
        "critical_ddi": critical_report,
    }
    json_path = out_dir / f"day17-vn-brand-combo-eval-{timestamp}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = _render_markdown(report, json_path)
    markdown_path.write_text(markdown, encoding="utf-8")

    print(f"[day17-eval] json={json_path}")
    print(f"[day17-eval] markdown={markdown_path}")
    print(
        "[day17-eval] summary "
        f"accuracy={brand_report['accuracy'] * 100:.2f}% "
        f"critical_miss_rate={critical_report['critical_ddi_miss_rate'] * 100:.2f}%"
    )


if __name__ == "__main__":
    main()
