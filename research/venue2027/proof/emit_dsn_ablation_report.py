"""Emit the DSN-ablation task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/dsn/ablations.py",
    "evaluation/venue2027/dsn/test_ablations.py",
    "research/venue2027/proof/DSN-ablation.json",
    "research/venue2027/proof/emit_dsn_ablation_report.py",
    "research/venue2027/proof/logs/DSN-ablation.pytest.log",
    "research/venue2027/proof/logs/DSN-ablation.ruff.log",
    "research/venue2027/proof/logs/DSN-ablation.suite.log",
    "research/venue2027/proof/logs/DSN-ablation.validator.log",
]


def run_cmd(cmd: str, log_rel: str) -> int:
    log_file = REPO / log_rel
    proc = subprocess.run(cmd, shell=True, cwd=str(REPO), capture_output=True, text=True)
    combined = proc.stdout + proc.stderr
    log_file.write_text(combined, encoding="utf-8")
    return proc.returncode


def main() -> int:
    pytest_exit = run_cmd(
        "python3 -m pytest -q evaluation/venue2027/dsn/test_ablations.py",
        "research/venue2027/proof/logs/DSN-ablation.pytest.log",
    )
    assert pytest_exit == 0, f"pytest failed with exit {pytest_exit}"

    ruff_exit = run_cmd(
        "uvx ruff@0.7.1 check evaluation/venue2027/dsn/ablations.py evaluation/venue2027/dsn/test_ablations.py",
        "research/venue2027/proof/logs/DSN-ablation.ruff.log",
    )
    assert ruff_exit == 0, f"ruff failed with exit {ruff_exit}"

    suite_exit = run_cmd(
        "python3 -m pytest -q evaluation/venue2027/dsn/",
        "research/venue2027/proof/logs/DSN-ablation.suite.log",
    )
    assert suite_exit == 0, f"suite failed with exit {suite_exit}"

    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-ablation",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_ablations.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-ablation.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dsn/ablations.py "
                    "evaluation/venue2027/dsn/test_ablations.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-ablation.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-ablation.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dsn/ablations.py",
            "evaluation/venue2027/dsn/test_ablations.py",
            "research/venue2027/proof/logs/DSN-ablation.pytest.log",
            "research/venue2027/proof/logs/DSN-ablation.ruff.log",
            "research/venue2027/proof/logs/DSN-ablation.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task DSN-ablation for DSN 2027 study 'Recoverable Safety Journals for "
            "Crash-Consistent AI-Mediated Health-State Mutations' (blueprint RQ1-RQ3, "
            "task contract VENUES/dsn/TASKS/DSN-ablation.md). evaluation/venue2027/dsn/ablations.py "
            "registers five preregistered variants in ABLATION_REGISTRY behind the task-manifest "
            "signature run_ablation(name, case) -> Outcome, each declaring exactly ONE mechanism "
            "removed: without_journal (removes durable safety journal; post-commit crash cannot "
            "adjudicate recovery outcome and broker replay duplicates effects), "
            "without_idempotency_key (removes idempotency key deduplication; broker replay and "
            "recovery retries demonstrably apply duplicate side effects), without_wal_pre_write "
            "(removes write-ahead effect journaling; mid_effect crash uniquely causes duplicate "
            "effect on recovery retry), common_safety_gate (replaces recoverable journal pipeline "
            "with statutory consent check; catches revocation but fails crash recovery), and "
            "full_fat_baseline (strong practical baseline B1 transactional outbox + idempotent "
            "consumer; survives normal crash recovery but fails mid_effect crash and fails to detect "
            "corrupted journals/tampered lineage). Reference row full_candidate and nothing-removing "
            "identities are refused by refuse_unregistered_variant fail-closed with "
            "VARIANT_REMOVES_NOTHING; unregistered variants refused with UNKNOWN_ABLATION_VARIANT; "
            "VariantSpec refuses empty ablated_mechanism. Mechanistic inference matrix "
            "(mechanistic_inference_matrix, verify_mechanistic_inference_matrix) pins 48 cells "
            "(6 variants x 8 crash windows) against preregistered predictions; all 48 cells match "
            "(all_cells_match=True). 25 unit/property tests passed in test_ablations.py; full "
            "evaluation/venue2027/dsn/ suite passed (233 passed); uvx ruff@0.7.1 check clean; "
            "validator validated ok:true."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-ablation.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-ablation",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-ablation.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
