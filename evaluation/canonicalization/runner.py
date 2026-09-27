"""Execution runner for E07 Canonicalization Conformance suite.

Runs test vector corpus against Python canonicalization engine (v2-rfc8785, v1-custom, v1-legacy-python)
and executes Node.js cross-runtime verification script.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure services/api/src is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_API_SRC = _REPO_ROOT / "services" / "api" / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from clara_api.glhs.canonical_json import (
    PROFILE_V1_CUSTOM,
    PROFILE_V1_LEGACY_PYTHON,
    PROFILE_V2_RFC8785,
    canonical_hash,
    canonicalize_json,
)


def resolve_python_input(inp: Any) -> Any:
    """Resolve tagged inputs in test vector JSON for Python engine."""
    if isinstance(inp, dict) and "$type" in inp:
        tag_type = inp["$type"]
        if tag_type == "lone_surrogate":
            code = int(inp["value"], 16)
            return chr(code)
        if tag_type == "non_finite_float":
            val = inp["value"]
            if val == "NaN":
                return float("nan")
            return float("-inf") if val.startswith("-") else float("inf")
        if tag_type == "unsafe_decimal":
            return Decimal(inp["value"])
        if tag_type == "integer_overflow":
            return int(inp["value"])
    return inp


def sanitize_for_json(obj: Any) -> Any:
    """Sanitize data structures containing lone surrogates for UTF-8 JSON writing."""
    if isinstance(obj, str):
        out = []
        for ch in obj:
            if 0xD800 <= ord(ch) <= 0xDFFF:
                out.append(f"\\u{ord(ch):04X}")
            else:
                out.append(ch)
        return "".join(out)
    if isinstance(obj, list):
        return [sanitize_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    return obj


def run_conformance_benchmark(
    *,
    vectors_path: Path,
    expected_path: Path,
    node_script_path: Path,
) -> dict[str, Any]:
    """Execute Python and Node.js canonicalization across all test vectors."""
    vectors_data = json.loads(vectors_path.read_text(encoding="utf-8"))
    expected_data = json.loads(expected_path.read_text(encoding="utf-8"))
    exp_map = {e["id"]: e for e in expected_data}

    python_results: list[dict[str, Any]] = []

    v2_passed = 0
    v2_failed = 0

    for vec in vectors_data:
        vid = vec["id"]
        exp = exp_map[vid]

        # Test v2-rfc8785 (authoritative)
        v2_status = "VALID"
        v2_canonical = None
        v2_sha256 = None
        v2_error = None

        try:
            py_inp = resolve_python_input(vec["input"])
            v2_canonical = canonicalize_json(py_inp, profile=PROFILE_V2_RFC8785)
            v2_sha256 = canonical_hash(py_inp, profile=PROFILE_V2_RFC8785)
        except (ValueError, TypeError) as exc:
            v2_status = "REJECTED"
            v2_error = str(exc)

        v2_match = False
        if exp["status"] == "VALID" and v2_status == "VALID":
            v2_match = (
                v2_canonical == exp["expected_canonical_json"]
                and v2_sha256 == exp["expected_sha256"]
            )
        elif exp["status"] == "REJECTED" and v2_status == "REJECTED":
            v2_match = exp["expected_error"] in (v2_error or "")

        if v2_match:
            v2_passed += 1
        else:
            v2_failed += 1

        # Legacy profiles test (compatibility check)
        v1_custom_canonical = None
        v1_custom_error = None
        try:
            py_inp = resolve_python_input(vec["input"])
            v1_custom_canonical = canonicalize_json(py_inp, profile=PROFILE_V1_CUSTOM)
        except Exception as exc:
            v1_custom_error = str(exc)

        v1_legacy_canonical = None
        v1_legacy_error = None
        try:
            py_inp = resolve_python_input(vec["input"])
            v1_legacy_canonical = canonicalize_json(py_inp, profile=PROFILE_V1_LEGACY_PYTHON)
        except Exception as exc:
            v1_legacy_error = str(exc)

        python_results.append({
            "id": vid,
            "category": vec["category"],
            "description": vec["description"],
            "expected_status": exp["status"],
            "expected_canonical": exp.get("expected_canonical_json"),
            "expected_sha256": exp.get("expected_sha256"),
            "expected_error": exp.get("expected_error"),
            "v2_status": v2_status,
            "v2_canonical": v2_canonical,
            "v2_sha256": v2_sha256,
            "v2_error": v2_error,
            "v2_match": v2_match,
            "v1_custom_canonical": v1_custom_canonical,
            "v1_custom_error": v1_custom_error,
            "v1_legacy_canonical": v1_legacy_canonical,
            "v1_legacy_error": v1_legacy_error,
        })

    # Execute Node.js cross-runtime verification
    node_cmd = [
        "node",
        str(node_script_path),
        f"--vectors={vectors_path}",
        f"--expected={expected_path}",
        "--json",
    ]
    node_proc = subprocess.run(
        node_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if node_proc.returncode != 0:
        raise RuntimeError(f"node_verification_failed:\n{node_proc.stderr or node_proc.stdout}")

    node_report = json.loads(node_proc.stdout)

    byte_equality_rate = v2_passed / len(vectors_data)
    cross_runtime_determinism = (
        byte_equality_rate == 1.0
        and node_report.get("byte_equality_rate") == 1.0
    )

    summary = {
        "suite": "E07_canonicalization_conformance",
        "total_vectors": len(vectors_data),
        "python_v2_passed": v2_passed,
        "python_v2_failed": v2_failed,
        "node_passed": node_report["passed"],
        "node_failed": node_report["failed"],
        "byte_equality_rate": byte_equality_rate,
        "cross_runtime_determinism": cross_runtime_determinism,
        "python_results": python_results,
        "node_results": node_report["results"],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vectors",
        type=Path,
        default=_REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "vectors.json",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=_REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "expected.json",
    )
    parser.add_argument(
        "--node-script",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "canonicalization" / "verify_node_rfc8785.js",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "canonicalization" / "output",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = run_conformance_benchmark(
        vectors_path=args.vectors,
        expected_path=args.expected,
        node_script_path=args.node_script,
    )

    results_file = args.output_dir / "results.jsonl"
    with results_file.open("w", encoding="utf-8") as handle:
        for res in summary["python_results"]:
            handle.write(json.dumps(sanitize_for_json(res), ensure_ascii=False) + "\n")

    summary_file = args.output_dir / "summary.json"
    sanitized_summary = sanitize_for_json(summary)
    summary_file.write_text(json.dumps(sanitized_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"[E07 Runner] Total Vectors: {summary['total_vectors']} | "
        f"Python v2 Passed: {summary['python_v2_passed']} | "
        f"Node Passed: {summary['node_passed']} | "
        f"Byte Equality Rate: {summary['byte_equality_rate'] * 100:.2f}% | "
        f"Cross-Runtime Determinism: {summary['cross_runtime_determinism']}"
    )
    return 0 if summary["cross_runtime_determinism"] else 1


if __name__ == "__main__":
    sys.exit(main())
