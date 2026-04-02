#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Gate:
    id: str
    passed: bool
    detail: str


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _gate_file_exists(path: Path, gate_id: str) -> Gate:
    return Gate(gate_id, path.exists(), f"path={path}")


def _gate_go_nogo(path: Path) -> Gate:
    payload = _read_json(path)
    go = payload.get("go") is True
    return Gate("go_no_go_gate", go, f"go={payload.get('go')}")


def _gate_demo_cases(path: Path) -> Gate:
    payload = _read_json(path)
    passed = payload.get("overall_pass") is True
    return Gate("demo_cases_gate", passed, f"overall_pass={payload.get('overall_pass')}")


def _gate_legal(path: Path) -> Gate:
    payload = _read_json(path)
    passed = payload.get("overall_pass") is True
    return Gate("legal_attribution_gate", passed, f"overall_pass={payload.get('overall_pass')}")


def _write_report(out_dir: Path, run_id: str, gates: list[Gate]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": all(g.passed for g in gates),
        "gates": [{"id": g.id, "passed": g.passed, "detail": g.detail} for g in gates],
    }
    json_path = out_dir / "readiness.json"
    md_path = out_dir / "readiness.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Round2 Demo Readiness",
        "",
        f"- run_id: `{run_id}`",
        f"- ready: `{'YES' if payload['ready'] else 'NO'}`",
        "",
        "| Gate | Result | Detail |",
        "|---|---|---|",
    ]
    for g in gates:
        lines.append(f"| `{g.id}` | **{'PASS' if g.passed else 'FAIL'}** | {g.detail} |")
    lines.append("")
    lines.append("> Lưu ý: gate này chỉ đánh giá readiness kỹ thuật từ artifact; rehearsal/pitch thủ công vẫn cần log riêng.")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Ready: {'YES' if payload['ready'] else 'NO'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Round2 demo readiness from canonical artifacts.")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    base = Path("artifacts") / "round2" / args.run_id
    gates = [
        _gate_file_exists(base / "data-manifest" / "data-manifest.json", "artifact_data_manifest"),
        _gate_file_exists(base / "test-report" / "test-report.json", "artifact_test_report"),
        _gate_file_exists(base / "fallback-proof" / "fallback-proof.json", "artifact_fallback_proof"),
        _gate_file_exists(base / "kpi-report" / "kpi-report.json", "artifact_kpi_report"),
        _gate_go_nogo(base / "go-no-go" / "go-no-go.json"),
        _gate_demo_cases(base / "demo-cases" / "demo-cases-summary.json"),
        _gate_legal(base / "legal-attribution-review" / "legal-attribution-review.json"),
    ]

    out_dir = base / "readiness"
    _write_report(out_dir, args.run_id, gates)
    return 0 if all(g.passed for g in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
