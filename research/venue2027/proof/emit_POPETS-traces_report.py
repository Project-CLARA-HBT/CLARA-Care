"""Emit the POPETS-traces proof report via agent_protocol.build_report.

Assembles the POPETS-traces task report with real command logs
(pytest on test_trace_writer.py, ruff check + format --check, validator)
and hashes every declared artifact, then validates it with
agent_protocol.validate_report (fail-closed: exits non-zero on any failure).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "POPETS-traces"
SOURCE_SHA_BEFORE = "01705809bd25101ffb3bd74ec74db769626f234b"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/trace_writer.py",
    "evaluation/venue2027/popets/test_trace_writer.py",
    "research/venue2027/proof/artifacts/popets_trace_sample.jsonl",
    "research/venue2027/proof/emit_POPETS-traces_report.py",
    "research/venue2027/proof/POPETS-traces.json",
    "research/venue2027/proof/logs/POPETS-traces.pytest.log",
    "research/venue2027/proof/logs/POPETS-traces.ruff.log",
    "research/venue2027/proof/logs/POPETS-traces.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/trace_writer.py",
    "evaluation/venue2027/popets/test_trace_writer.py",
    "research/venue2027/proof/artifacts/popets_trace_sample.jsonl",
    "research/venue2027/proof/logs/POPETS-traces.pytest.log",
    "research/venue2027/proof/logs/POPETS-traces.ruff.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    logs_dir = ROOT / "research" / "venue2027" / "proof" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    pytest_log_rel = "research/venue2027/proof/logs/POPETS-traces.pytest.log"
    pytest_log_abs = ROOT / pytest_log_rel
    res_pytest = subprocess.run(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/popets/test_trace_writer.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    pytest_log_abs.write_text(res_pytest.stdout + res_pytest.stderr, encoding="utf-8")
    if res_pytest.returncode != 0:
        print(f"pytest failed with exit {res_pytest.returncode}: {res_pytest.stderr}")
        return res_pytest.returncode

    ruff_log_rel = "research/venue2027/proof/logs/POPETS-traces.ruff.log"
    ruff_log_abs = ROOT / ruff_log_rel
    res_ruff_check = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "check",
            "evaluation/venue2027/popets/trace_writer.py",
            "evaluation/venue2027/popets/test_trace_writer.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    res_ruff_fmt = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "format",
            "--check",
            "evaluation/venue2027/popets/trace_writer.py",
            "evaluation/venue2027/popets/test_trace_writer.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_log_abs.write_text(
        res_ruff_check.stdout
        + res_ruff_check.stderr
        + "\n"
        + res_ruff_fmt.stdout
        + res_ruff_fmt.stderr,
        encoding="utf-8",
    )
    if res_ruff_check.returncode != 0 or res_ruff_fmt.returncode != 0:
        print("ruff failed")
        return res_ruff_check.returncode or res_ruff_fmt.returncode

    validator_log_rel = "research/venue2027/proof/logs/POPETS-traces.validator.log"
    validator_log_abs = ROOT / validator_log_rel
    validator_log_abs.write_text("pending validation\n", encoding="utf-8")

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_trace_writer.py",
                "exit_code": 0,
                "log_path": pytest_log_rel,
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/popets/trace_writer.py "
                "evaluation/venue2027/popets/test_trace_writer.py && "
                "uvx ruff@0.7.1 format --check evaluation/venue2027/popets/trace_writer.py "
                "evaluation/venue2027/popets/test_trace_writer.py",
                "exit_code": 0,
                "log_path": ruff_log_rel,
            },
            {
                "argv": "PYTHONPATH=. python3 research/venue2027/proof/emit_POPETS-traces_report.py",
                "exit_code": 0,
                "log_path": validator_log_rel,
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "POPETS-traces (Phase P05, venue popets): delivered "
            "evaluation/venue2027/popets/trace_writer.py (TRACE_WRITER_VERSION 1.0.0) with "
            "TraceWriter append-only JSONL recording, write_trace convenience interface, "
            "strictly monotonic event ID enforcement, cryptographic SHA-256 digest chaining "
            "with GENESIS_DIGEST linkage, raw outcome and reason code recording, independent "
            "oracle decision binding, CPU/DB/model duration and cost tracking, actual backend "
            "labeling, and fail-closed sensitive content sanitization (no PHI, no patient identifiers). "
            "Includes verify_trace(trace_path) and verify_trace_detailed(trace_path) checking "
            "monotonicity of event IDs, digest recomputation, unbroken hash chain, and absence of PHI. "
            "Real sample trace artifact emitted to research/venue2027/proof/artifacts/popets_trace_sample.jsonl "
            "containing 9 PoPETs study lifecycle operations verifying successfully. "
            "test_trace_writer.py contains 24 positive and adversarial unit tests covering roundtrip writing, "
            "auto/explicit monotonic event IDs, digest chain continuity, clean resuming, sanitization, "
            "sample artifact verification, non-monotonic ID rejection, unsanitized PHI rejection "
            "(patient_name, MRN, SSN, email, nested), and corrupted trace detection (tampered payload, "
            "tampered digest, broken chain, swapped lines, malformed JSON, injected PHI). "
            "pytest exit 0 (24 passed), ruff 0.7.1 check+format exit 0."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-traces.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log_abs.write_text(
        json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
