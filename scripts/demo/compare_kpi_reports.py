#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare KPI report against previous baseline and emit regression verdict."
    )
    parser.add_argument("--current", required=True, help="Current run kpi-report.json path")
    parser.add_argument("--previous", required=True, help="Previous run kpi-report.json path")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument(
        "--max-drop-rate",
        type=float,
        default=2.0,
        help="Maximum allowed drop in rate_percent metrics before fail.",
    )
    parser.add_argument(
        "--max-latency-increase-ms",
        type=float,
        default=350.0,
        help="Maximum allowed p95 latency increase before fail.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _metric_rate(metrics: dict[str, Any], key: str) -> float | None:
    node = metrics.get(key)
    if not isinstance(node, dict):
        return None
    raw = node.get("rate_percent")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _latency_p95_ms(metrics: dict[str, Any]) -> float | None:
    latency = metrics.get("latency")
    if not isinstance(latency, dict):
        return None
    try:
        return float(latency.get("p95_ms"))
    except (TypeError, ValueError):
        return None


def _line(name: str, current: float | None, previous: float | None, delta: float | None, passed: bool) -> str:
    current_text = "-" if current is None else f"{current:.2f}"
    previous_text = "-" if previous is None else f"{previous:.2f}"
    delta_text = "-" if delta is None else f"{delta:+.2f}"
    verdict = "PASS" if passed else "FAIL"
    return f"| {name} | {current_text} | {previous_text} | {delta_text} | {verdict} |"


def main() -> int:
    args = parse_args()
    current_path = Path(args.current)
    previous_path = Path(args.previous)
    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)

    current = _read_json(current_path)
    previous = _read_json(previous_path)
    current_metrics = current.get("metrics") if isinstance(current.get("metrics"), dict) else {}
    previous_metrics = previous.get("metrics") if isinstance(previous.get("metrics"), dict) else {}

    checks: list[dict[str, Any]] = []
    for key in ("ddi_precision", "fallback_success_rate", "refusal_compliance", "hard_negative_pass_rate"):
        cur = _metric_rate(current_metrics, key)
        prev = _metric_rate(previous_metrics, key)
        if cur is None or prev is None:
            checks.append(
                {
                    "metric": key,
                    "current": cur,
                    "previous": prev,
                    "delta": None,
                    "passed": True,
                    "note": "missing_data_skip",
                }
            )
            continue
        delta = cur - prev
        passed = delta >= -float(args.max_drop_rate)
        checks.append(
            {
                "metric": key,
                "current": cur,
                "previous": prev,
                "delta": delta,
                "passed": passed,
                "threshold": -float(args.max_drop_rate),
            }
        )

    cur_latency = _latency_p95_ms(current_metrics)
    prev_latency = _latency_p95_ms(previous_metrics)
    if cur_latency is None or prev_latency is None:
        checks.append(
            {
                "metric": "latency_p95_ms",
                "current": cur_latency,
                "previous": prev_latency,
                "delta": None,
                "passed": True,
                "note": "missing_data_skip",
            }
        )
    else:
        delta_latency = cur_latency - prev_latency
        checks.append(
            {
                "metric": "latency_p95_ms",
                "current": cur_latency,
                "previous": prev_latency,
                "delta": delta_latency,
                "passed": delta_latency <= float(args.max_latency_increase_ms),
                "threshold": float(args.max_latency_increase_ms),
            }
        )

    failed = [item for item in checks if not bool(item.get("passed"))]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_path": str(current_path),
        "previous_path": str(previous_path),
        "max_drop_rate": float(args.max_drop_rate),
        "max_latency_increase_ms": float(args.max_latency_increase_ms),
        "checks": checks,
        "go": len(failed) == 0,
        "failure_reasons": [f"{item.get('metric')} regression" for item in failed],
    }

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Baseline Regression Compare",
        "",
        f"- Current: `{current_path}`",
        f"- Previous: `{previous_path}`",
        f"- Max drop rate: `{args.max_drop_rate:.2f}`",
        f"- Max latency increase: `{args.max_latency_increase_ms:.2f} ms`",
        f"- Verdict: **{'GO' if report['go'] else 'NO-GO'}**",
        "",
        "| Metric | Current | Previous | Delta | Verdict |",
        "|---|---:|---:|---:|---|",
    ]

    for item in checks:
        lines.append(
            _line(
                str(item.get("metric") or "-"),
                item.get("current"),
                item.get("previous"),
                item.get("delta"),
                bool(item.get("passed")),
            )
        )

    if failed:
        lines.extend(
            [
                "",
                "## Failures",
                *[f"- {reason}" for reason in report["failure_reasons"]],
            ]
        )

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[compare-kpi-reports] ok")
    print(f"- go: {report['go']}")
    print(f"- output_json: {output_json_path}")
    print(f"- output_md: {output_md_path}")
    return 0 if report["go"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
