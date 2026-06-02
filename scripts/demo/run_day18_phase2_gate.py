#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DAY17_REPORT = ROOT / "data" / "demo" / "day17-vn-brand-combo-eval-20260402-184837.json"
DEFAULT_BASELINE_SUMMARY = (
    ROOT / "data" / "demo" / "hard-negative-mined-phase1-day9-20260402-224131.jsonl.summary.json"
)
DEFAULT_OUT_DIR = ROOT / "data" / "demo"
DEFAULT_MARKDOWN_OUT = ROOT / "docs" / "hackathon" / "day18-phase2-gate.md"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON payload at {path}")
    return payload


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _baseline_miss_rate_from_summary(
    summary: dict[str, Any],
    default_total: int,
) -> tuple[float, int, int, str]:
    reasons = summary.get("reason_breakdown", {})
    if not isinstance(reasons, dict):
        reasons = summary.get("reasons", {})
    if not isinstance(reasons, dict):
        reasons = {}
    misses = _safe_int(reasons.get("critical_ddi_miss"), default=0)
    total = _safe_int(summary.get("critical_total"), default=default_total)
    if total <= 0:
        total = default_total
    if total <= 0:
        return (1.0, misses, total, "fallback_assumed")
    return (misses / total, misses, total, "from_summary")


def _render_markdown(report: dict[str, Any], output_json_path: Path) -> str:
    checks = report["checks"]
    metrics = report["metrics"]
    verdict = "PASS" if report["gate_passed"] else "FAIL"
    lines = [
        "# Day 18 Gate Report (Phase 2)",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Gate verdict: **{verdict}**",
        f"- JSON artifact: `{output_json_path.relative_to(ROOT)}`",
        "",
        "## KPI Inputs",
        "",
        f"- Mapping accuracy (Day 17): **{metrics['mapping_accuracy'] * 100:.2f}%**",
        f"- Current critical DDI miss rate: **{metrics['current_critical_miss_rate'] * 100:.2f}%**",
        f"- Baseline critical DDI miss rate: **{metrics['baseline_critical_miss_rate'] * 100:.2f}%**",
        f"- Critical DDI miss reduction: **{metrics['critical_miss_reduction'] * 100:.2f}%**",
        "",
        "## Gate Checks",
        "",
        "| Check | Threshold | Actual | Result |",
        "|---|---:|---:|---|",
        (
            f"| Mapping accuracy | >= {checks['mapping_accuracy']['threshold'] * 100:.2f}% "
            f"| {checks['mapping_accuracy']['actual'] * 100:.2f}% "
            f"| {'PASS' if checks['mapping_accuracy']['passed'] else 'FAIL'} |"
        ),
        (
            f"| Critical DDI miss reduction | >= {checks['critical_miss_reduction']['threshold'] * 100:.2f}% "
            f"| {checks['critical_miss_reduction']['actual'] * 100:.2f}% "
            f"| {'PASS' if checks['critical_miss_reduction']['passed'] else 'FAIL'} |"
        ),
        "",
        "## Notes",
        "",
        f"- Baseline source mode: `{metrics['baseline_source_mode']}`",
        "- Day 18 gate uses deterministic local DDI (`external_ddi_enabled=false`) from Day 17 report.",
        "- If this gate passes, phase2 can be tagged `phase2-ready`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day 18 gate for Phase 2.")
    parser.add_argument("--day17-report", default=str(DEFAULT_DAY17_REPORT))
    parser.add_argument("--baseline-summary", default=str(DEFAULT_BASELINE_SUMMARY))
    parser.add_argument("--baseline-critical-total", type=int, default=30)
    parser.add_argument("--min-mapping-accuracy", type=float, default=0.90)
    parser.add_argument("--min-critical-miss-reduction", type=float, default=0.40)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    day17_path = Path(args.day17_report).resolve()
    baseline_path = Path(args.baseline_summary).resolve()
    out_dir = Path(args.out_dir).resolve()
    markdown_path = Path(args.markdown_out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    day17 = _load_json(day17_path)
    brand = day17.get("brand_combo", {}) if isinstance(day17, dict) else {}
    critical = day17.get("critical_ddi", {}) if isinstance(day17, dict) else {}

    mapping_accuracy = _safe_float(brand.get("accuracy"))
    current_miss_rate = _safe_float(critical.get("critical_ddi_miss_rate"))
    critical_total = _safe_int(critical.get("total_high_expected_cases"), default=args.baseline_critical_total)

    baseline_mode = "assumed"
    baseline_rate = 1.0
    baseline_misses = critical_total
    baseline_total = critical_total
    if baseline_path.exists():
        baseline = _load_json(baseline_path)
        baseline_rate, baseline_misses, baseline_total, baseline_mode = _baseline_miss_rate_from_summary(
            baseline,
            default_total=max(critical_total, args.baseline_critical_total),
        )

    if baseline_rate <= 0:
        critical_reduction = 1.0 if current_miss_rate <= 0 else 0.0
    else:
        critical_reduction = max(0.0, (baseline_rate - current_miss_rate) / baseline_rate)

    mapping_pass = mapping_accuracy >= args.min_mapping_accuracy
    critical_pass = critical_reduction >= args.min_critical_miss_reduction
    gate_passed = mapping_pass and critical_pass

    report = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "gate_passed": gate_passed,
        "checks": {
            "mapping_accuracy": {
                "threshold": args.min_mapping_accuracy,
                "actual": mapping_accuracy,
                "passed": mapping_pass,
            },
            "critical_miss_reduction": {
                "threshold": args.min_critical_miss_reduction,
                "actual": critical_reduction,
                "passed": critical_pass,
            },
        },
        "metrics": {
            "mapping_accuracy": mapping_accuracy,
            "current_critical_miss_rate": current_miss_rate,
            "baseline_critical_miss_rate": baseline_rate,
            "critical_miss_reduction": critical_reduction,
            "baseline_critical_miss_cases": baseline_misses,
            "baseline_critical_total": baseline_total,
            "current_critical_total": critical_total,
            "baseline_source_mode": baseline_mode,
        },
        "inputs": {
            "day17_report": str(day17_path),
            "baseline_summary": str(baseline_path),
        },
    }

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_json_path = out_dir / f"day18-phase2-gate-{timestamp}.json"
    output_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = _render_markdown(report, output_json_path)
    markdown_path.write_text(markdown, encoding="utf-8")

    print(
        "[day18-phase2-gate] "
        f"pass={gate_passed} "
        f"mapping={mapping_accuracy * 100:.2f}% "
        f"critical_reduction={critical_reduction * 100:.2f}% "
        f"artifact={output_json_path}"
    )

    if args.strict and not gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
