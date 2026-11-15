"""Emit the DIMVA-dataset proof report via the shared agent protocol.

Run from the task worktree root. The report is built with
``agent_protocol.build_report`` (task_id='DIMVA-dataset'), then validated
with ``validate_report``; the script exits non-zero unless ok=True.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    sha_before = _git("rev-parse", "HEAD")
    report = ap.build_report(
        task_id="DIMVA-dataset",
        status="PASS",
        source_sha_before=sha_before,
        source_sha_after=sha_before,  # single-commit convention: final SHA in handoff
        changed_paths=[
            "evaluation/venue2027/dimva/generate_dataset.py",
            "evaluation/venue2027/dimva/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/dimva_dataset/dataset.jsonl",
            "research/venue2027/proof/artifacts/dimva_dataset/manifest.json",
            "research/venue2027/proof/DIMVA-dataset.json",
            "research/venue2027/proof/logs/DIMVA-dataset.pytest.log",
            "research/venue2027/proof/logs/DIMVA-dataset.ruff.log",
            "research/venue2027/proof/logs/DIMVA-dataset.validator.log",
            "research/venue2027/proof/logs/DIMVA-dataset.artifact.log",
        ],
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "evaluation/venue2027/dimva/test_generate_dataset.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DIMVA-dataset.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dimva/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DIMVA-dataset.ruff.log",
            },
            {
                "argv": (
                    "python3 -c \"from evaluation.venue2027.dimva.generate_dataset "
                    "import write_dataset; "
                    "write_dataset('research/venue2027/proof/artifacts/"
                    "dimva_dataset', seed=2027, n=120)\""
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DIMVA-dataset.artifact.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dimva/generate_dataset.py",
            "evaluation/venue2027/dimva/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/dimva_dataset/dataset.jsonl",
            "research/venue2027/proof/artifacts/dimva_dataset/manifest.json",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 deterministic dataset builder for GovernanceTrace (DIMVA 2027). "
            "generate(seed, split, n) delegates family assignment, split "
            "partitioning, leakage discipline and the content hash to the shared "
            "kernel dataset_kernel.generate('dimva', ...) (kernel v1.0.0, unit "
            "prefix camp-, four registered families benign_session / low_and_slow "
            "/ cross_tool_obfuscation / burst_probe) and only adds the "
            "DIMVA-specific payload enrichment: campaign_length_events, tools_used "
            "(synthetic T01-T12 codes), denial_rate and inter_arrival_delay_seconds "
            "drawn from per-family operational ranges via pure integer modular "
            "arithmetic on the kernel determinant (no random module, no clock, no "
            "environment). write_dataset(outdir, seed, n) materializes "
            "dataset.jsonl + manifest.json (content_sha256, JSONL byte hash, split "
            "and family inventory, both generator versions) and fails closed via "
            "assert_valid_frequencies BEFORE creating any file. Real artifact "
            "written: research/venue2027/proof/artifacts/dimva_dataset/ (seed=2027, "
            "n=120: 72/24/24 train/dev/test, 30 per family, "
            "dataset_jsonl_sha256=14fe61ff142e93eceea32619620982c61eb2ea7366a48b50f86d"
            "d0c23f6c1c6f). Determinism proven: same seed -> identical JSONL bytes; "
            "content hash split-independent per kernel contract. Tests: 22 passed "
            "(positive: kernel delegation identity, determinism, split disjointness "
            "via assert_no_leakage, camp- unit prefix, operational-field bounds, "
            "family-regime separation, JSON-serializability + PHI-free keys, "
            "balanced frequencies, write_dataset manifest/idempotency; adversarial: "
            "n=0/-5 -> INVALID_N, unknown split -> UNKNOWN_SPLIT, duplicate-unit "
            "leakage -> SPLIT_LEAKAGE, degenerate families -> "
            "INVALID_FAMILY_FREQUENCY with no directory created, unknown family "
            "enrichment -> UNKNOWN_DIMVA_FAMILY, kernel registry drift guard, "
            "cross-venue unit-id collision guard). Shared foundations + dimva "
            "regression: 216 passed. ruff@0.7.1 check + format clean. "
            "source_sha_after = base SHA per established repo convention (proof "
            "report committed together with the work in the single task commit)."
        ),
    )
    out_path = REPO / "research" / "venue2027" / "proof" / "DIMVA-dataset.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    validation = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-dataset",
    )
    print(json.dumps(validation.to_dict(), indent=2))
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
