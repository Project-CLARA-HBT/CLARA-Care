"""Analysis and summary generator for E07 Canonicalization Conformance.

Analyzes raw execution results from results.jsonl and generates summary.json and summary.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def analyze_conformance_results(
    results_file: Path,
    protocol_file: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Analyze raw execution results and produce summary metrics."""
    protocol_data = json.loads(protocol_file.read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []
    with results_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    total_vectors = len(results)
    if total_vectors < 30:
        raise ValueError(f"insufficient_test_vectors: found {total_vectors}, expected >= 30")

    v2_passed = sum(1 for r in results if r.get("v2_match", False))
    v2_failed = total_vectors - v2_passed

    category_counts: dict[str, int] = defaultdict(int)
    category_passed: dict[str, int] = defaultdict(int)

    for r in results:
        cat = r.get("category", "unknown")
        category_counts[cat] += 1
        if r.get("v2_match", False):
            category_passed[cat] += 1

    category_summary = {
        cat: {
            "total": category_counts[cat],
            "passed": category_passed[cat],
            "pass_rate": category_passed[cat] / category_counts[cat] if category_counts[cat] > 0 else 0.0,
        }
        for cat in sorted(category_counts.keys())
    }

    byte_equality_rate = v2_passed / total_vectors if total_vectors > 0 else 0.0
    cross_runtime_determinism = (v2_failed == 0)

    claim_eligible = (
        total_vectors >= 30
        and byte_equality_rate == 1.0
        and v2_failed == 0
        and cross_runtime_determinism
    )

    summary = {
        "schema_version": "canonicalization-conformance-summary.v1",
        "freeze_id": protocol_data.get("freeze_id", "GLHS-CANONICALIZATION-E07-20260928-01"),
        "analyzed_at_utc": datetime.now(UTC).isoformat(),
        "total_vectors": total_vectors,
        "python_v2_passed": v2_passed,
        "python_v2_failed": v2_failed,
        "byte_equality_rate": byte_equality_rate,
        "cross_runtime_determinism": cross_runtime_determinism,
        "claim_eligible": claim_eligible,
        "category_summary": category_summary,
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output_dir / "summary.md").write_text(
            generate_summary_markdown(summary), encoding="utf-8"
        )

    return summary


def generate_summary_markdown(summary: dict[str, Any]) -> str:
    """Generate human-readable Markdown summary report for E07."""
    lines = [
        "# E07: Canonicalization Conformance Benchmark Summary",
        "",
        f"- **Freeze ID**: `{summary.get('freeze_id')}`",
        f"- **Analyzed At (UTC)**: `{summary.get('analyzed_at_utc')}`",
        f"- **Total Test Vectors**: `{summary.get('total_vectors')}`",
        f"- **Python v2-RFC8785 Passed**: `{summary.get('python_v2_passed')}`",
        f"- **Python v2-RFC8785 Failed**: `{summary.get('python_v2_failed')}`",
        f"- **Byte Equality Rate**: `{summary.get('byte_equality_rate', 0.0) * 100:.2f}%`",
        f"- **Cross-Runtime Determinism**: `{summary.get('cross_runtime_determinism')}`",
        f"- **Claim Eligible**: `{summary.get('claim_eligible')}`",
        "",
        "## Vector Category Summary",
        "",
        "| Category | Total Vectors | Passed | Pass Rate |",
        "| --- | --- | --- | --- |",
    ]

    for cat, stats in summary.get("category_summary", {}).items():
        lines.append(
            f"| `{cat}` | {stats['total']} | {stats['passed']} | {stats['pass_rate'] * 100:.2f}% |"
        )

    lines.extend([
        "",
        "## Conformance Invariants",
        "- **Authoritative Profile**: `clara.canonical-json.v2-rfc8785`",
        "- **Key Ordering**: UTF-16 code units (RFC 8785 Section 3.2.3)",
        "- **Character Escaping**: Control chars 0x00-0x1F hex escaped, raw UTF-8 for >=0x20",
        "- **Surrogate Rejection**: Strict rejection of lone surrogates (0xD800 - 0xDFFF)",
        "- **Integer Safety**: I-JSON safe integer range `[-9007199254740991, 9007199254740991]`",
        "- **Float Formatting**: ECMAScript `Number::toString` formatting, `-0.0` normalized to `0`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("evaluation/canonicalization/output/results.jsonl"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E07_canonicalization/protocol.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/canonicalization/output/derived"),
    )
    args = parser.parse_args()

    summary = analyze_conformance_results(
        results_file=args.results,
        protocol_file=args.protocol,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["claim_eligible"] else 1


if __name__ == "__main__":
    sys.exit(main())
