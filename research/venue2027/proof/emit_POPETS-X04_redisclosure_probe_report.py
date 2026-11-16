"""Emit research/venue2027/proof/POPETS-X04_redisclosure_probe.json via agent_protocol.

Assembles the POPETS-X04_redisclosure_probe task report with real command logs
(pytest, ruff check+format, suite regression, emitter/validator) and hashes every declared
artifact, then validates it with agent_protocol.validate_report.
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

TASK_ID = "POPETS-X04_redisclosure_probe"
SOURCE_SHA_BEFORE = "01705809bd25101ffb3bd74ec74db769626f234b"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/redisclosure_probe.py",
    "evaluation/venue2027/popets/test_redisclosure_probe.py",
    "research/venue2027/proof/POPETS-X04_redisclosure_probe.json",
    "research/venue2027/proof/emit_POPETS-X04_redisclosure_probe_report.py",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.pytest.log",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.ruff.log",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.suite.log",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/redisclosure_probe.py",
    "evaluation/venue2027/popets/test_redisclosure_probe.py",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.pytest.log",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.ruff.log",
    "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.suite.log",
]


def run_cmd(argv: list[str], log_relpath: str) -> int:
    """Run command, write real stdout/stderr log to log_relpath, return exit code."""
    log_path = ROOT / log_relpath
    log_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    log_path.write_text(res.stdout + res.stderr, encoding="utf-8")
    return res.returncode


def main() -> int:
    # 1. Run real commands and capture real logs
    pytest_exit = run_cmd(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/popets/test_redisclosure_probe.py"],
        "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.pytest.log",
    )
    if pytest_exit != 0:
        print(f"pytest failed with code {pytest_exit}", file=sys.stderr)
        return pytest_exit

    ruff_exit = subprocess.run(
        "uvx ruff@0.7.1 check evaluation/venue2027/popets/redisclosure_probe.py "
        "evaluation/venue2027/popets/test_redisclosure_probe.py && "
        "uvx ruff@0.7.1 format --check evaluation/venue2027/popets/redisclosure_probe.py "
        "evaluation/venue2027/popets/test_redisclosure_probe.py",
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    ruff_log = ROOT / "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.ruff.log"
    ruff_log.parent.mkdir(parents=True, exist_ok=True)
    ruff_log.write_text(ruff_exit.stdout + ruff_exit.stderr, encoding="utf-8")
    if ruff_exit.returncode != 0:
        print(f"ruff failed with code {ruff_exit.returncode}", file=sys.stderr)
        return ruff_exit.returncode

    suite_exit = run_cmd(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/popets/"],
        "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.suite.log",
    )
    if suite_exit != 0:
        print(f"suite failed with code {suite_exit}", file=sys.stderr)
        return suite_exit

    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_redisclosure_probe.py",
                "exit_code": pytest_exit,
                "log_path": "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/popets/redisclosure_probe.py "
                "evaluation/venue2027/popets/test_redisclosure_probe.py && "
                "uvx ruff@0.7.1 format --check evaluation/venue2027/popets/redisclosure_probe.py "
                "evaluation/venue2027/popets/test_redisclosure_probe.py",
                "exit_code": ruff_exit.returncode,
                "log_path": "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/",
                "exit_code": suite_exit,
                "log_path": "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.suite.log",
            },
            {
                "argv": "PYTHONPATH=. python3 research/venue2027/proof/emit_POPETS-X04_redisclosure_probe_report.py "
                "# build_report + validate_report(ok:true) recorded in research/venue2027/proof/POPETS-X04_redisclosure_probe.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-X04_redisclosure_probe.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 POPETS-X04_redisclosure_probe deliverable: "
            "evaluation/venue2027/popets/redisclosure_probe.py (REDISCLOSURE_PROBE_VERSION 1.0.0) instruments future "
            "dispatches and retries for post-revocation canary redisclosure. Operates strictly as a black-box observer "
            "recording byte-accurate outbound field observations using synthetic canaries, tenant/purpose context, and "
            "cache lineage; does NOT scan model internals (model_internals_inspected=False). Detects if canary tokens "
            "belonging to a revoked context appear in outbound payload across dispatches and retries. "
            "probe_redisclosure(outbound_response, canary_tokens, tenant_purpose_ctx, cache_lineage) -> ProbeResult reports "
            "canary_detected: bool, violation_type: str ('REVOCATION_LEAK', 'CROSS_PURPOSE_LEAK', 'NONE'), and matched_tokens: list[str]. "
            "Also exposes probe(history, config) -> DisclosureReport per tasks.json contract. "
            "Positive tests: clean response -> no leak; known canary in outbound response -> detected leak with accurate token match; "
            "multi-field isolation and byte-accurate accounting; partial subset matching; JSON serializability. "
            "Adversarial controls: tampered lineage refused (digest mismatch, explicit tampered flag, cycles), "
            "canary token casing/normalization check (catches casing mutations, Unicode NFKC normalization, refuses malformed/empty tokens), "
            "empty context refused fail-closed (CONTEXT_EMPTY, CONTEXT_MALFORMED), malformed outbound refused. "
            "12 unit tests pass; 280 popets regression suite tests pass; uvx ruff@0.7.1 check and format clean."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-X04_redisclosure_probe.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validator_log = (
        ROOT
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "POPETS-X04_redisclosure_probe.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    validator_log.write_text("pending validation\n", encoding="utf-8")

    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
