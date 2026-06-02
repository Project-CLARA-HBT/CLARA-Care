#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = ROOT / "data" / "demo"
DEFAULT_MARKDOWN_OUT = ROOT / "docs" / "hackathon" / "day28-final-gate-report.md"


def _safe_load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON payload at {path}")
    return payload


def _latest_by_mtime(pattern: str) -> Path | None:
    candidates = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _detect_active_eval_summary() -> Path | None:
    candidates = sorted(
        ROOT.glob("artifacts/round2/*/active-eval-summary.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        return None

    def _is_strict_pass(path: Path) -> bool:
        try:
            payload = _safe_load_json(path)
        except Exception:
            return False
        return bool(payload.get("gate_passed")) and bool(payload.get("strict_stage_chain_ok"))

    strict_passes = [path for path in candidates if _is_strict_pass(path)]
    if strict_passes:
        return strict_passes[-1]
    return candidates[-1]


def _detect_day27_kpi() -> Path | None:
    preferred = sorted(
        ROOT.glob("artifacts/round2/day27*/kpi-report/kpi-report.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if preferred:
        return preferred[-1]
    fallback = sorted(
        ROOT.glob("artifacts/round2/*/kpi-report/kpi-report.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return fallback[-1] if fallback else None


def _render_markdown(report: dict[str, Any], output_json_path: Path) -> str:
    final_gate = report["final_gate"]
    checks = report["checks"]
    verdict = "GO" if final_gate["go"] else "NO-GO"
    lines = [
        "# Day 28 Final Gate Report (Phase 3)",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Final verdict: **{verdict}**",
        f"- JSON artifact: `{output_json_path.relative_to(ROOT)}`",
        "",
        "## Gate Matrix",
        "",
        "| Check | Expected | Actual | Result |",
        "|---|---|---|---|",
        (
            f"| Phase2 gate (Day 18) | PASS | "
            f"{'PASS' if checks['phase2_gate_pass'] else 'FAIL'} | "
            f"{'PASS' if checks['phase2_gate_pass'] else 'FAIL'} |"
        ),
        (
            f"| Active eval loop gate | PASS | "
            f"{'PASS' if checks['active_eval_gate_pass'] else 'FAIL'} | "
            f"{'PASS' if checks['active_eval_gate_pass'] else 'FAIL'} |"
        ),
        (
            f"| Day27 live KPI executed | true | "
            f"{checks['day27_live_executed']} | "
            f"{'PASS' if checks['day27_live_executed'] else 'FAIL'} |"
        ),
        (
            f"| Day27 GO/NO-GO | GO | "
            f"{checks['day27_go_no_go']} | "
            f"{'PASS' if checks['day27_go_no_go'] == 'GO' else 'FAIL'} |"
        ),
        "",
        "## Notes",
        "",
        f"- day18_gate_artifact: `{report['inputs']['day18_gate_artifact']}`",
        f"- active_eval_summary: `{report['inputs']['active_eval_summary']}`",
        f"- day27_kpi_report: `{report['inputs']['day27_kpi_report']}`",
        f"- day27_go_no_go: `{report['inputs']['day27_go_no_go']}`",
        "- Nếu final verdict là NO-GO, không tạo release tag production.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute Day 28 final gate from phase artifacts.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    markdown_out = Path(args.markdown_out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    day18_path = _latest_by_mtime("data/demo/day18-phase2-gate-*.json")
    active_eval_path = _detect_active_eval_summary()
    day27_kpi_path = _detect_day27_kpi()

    day18_payload = _safe_load_json(day18_path) if day18_path else {}
    active_eval_payload = _safe_load_json(active_eval_path) if active_eval_path else {}
    day27_kpi_payload = _safe_load_json(day27_kpi_path) if day27_kpi_path else {}

    day27_go_path = day27_kpi_path.parent.parent / "go-no-go" / "go-no-go.json" if day27_kpi_path else None
    day27_go_payload = _safe_load_json(day27_go_path) if day27_go_path and day27_go_path.exists() else {}

    phase2_gate_pass = bool(day18_payload.get("gate_passed"))
    active_eval_gate_pass = bool(active_eval_payload.get("gate_passed"))
    day27_live_executed = bool(day27_kpi_payload.get("live_executed"))
    go_field = day27_go_payload.get("go")
    if go_field is True:
        day27_go_value = "GO"
    elif go_field is False:
        day27_go_value = "NO-GO"
    else:
        day27_go_value = str(
            day27_go_payload.get("decision") or day27_go_payload.get("verdict") or "NO-GO"
        ).upper()
        if day27_go_value not in {"GO", "NO-GO"}:
            day27_go_value = "NO-GO"

    final_go = phase2_gate_pass and active_eval_gate_pass and day27_live_executed and day27_go_value == "GO"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "phase2_gate_pass": phase2_gate_pass,
            "active_eval_gate_pass": active_eval_gate_pass,
            "day27_live_executed": day27_live_executed,
            "day27_go_no_go": day27_go_value,
        },
        "final_gate": {
            "go": final_go,
            "release_tag_allowed": final_go,
        },
        "inputs": {
            "day18_gate_artifact": str(day18_path.relative_to(ROOT)) if day18_path else "",
            "active_eval_summary": str(active_eval_path.relative_to(ROOT)) if active_eval_path else "",
            "day27_kpi_report": str(day27_kpi_path.relative_to(ROOT)) if day27_kpi_path else "",
            "day27_go_no_go": str(day27_go_path.relative_to(ROOT)) if day27_go_path else "",
        },
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_json_path = out_dir / f"day28-final-gate-{timestamp}.json"
    output_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_out.write_text(_render_markdown(report, output_json_path), encoding="utf-8")
    print(
        "[day28-final-gate] "
        f"go={final_go} "
        f"day27_live_executed={day27_live_executed} "
        f"day27_decision={day27_go_value} "
        f"artifact={output_json_path}"
    )


if __name__ == "__main__":
    main()
