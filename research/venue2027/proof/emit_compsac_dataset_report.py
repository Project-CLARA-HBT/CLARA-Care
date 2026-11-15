"""Emit the COMPSAC-dataset proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the COMPSAC-dataset task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "COMPSAC-dataset"
BASE_SHA = "604642528f95e9f10052bd4bc0334bdb1c84358a"

CHANGED = [
    "evaluation/venue2027/compsac/generate_dataset.py",
    "evaluation/venue2027/compsac/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/compsac_dataset/dataset.jsonl",
    "research/venue2027/proof/artifacts/compsac_dataset/inventory.json",
    "research/venue2027/proof/logs/COMPSAC-dataset.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-dataset.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/compsac/test_generate_dataset.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-dataset.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/compsac/generate_dataset.py "
            "evaluation/venue2027/compsac/test_generate_dataset.py && "
            "uvx ruff@0.7.1 format --check evaluation/venue2027/compsac/generate_dataset.py "
            "evaluation/venue2027/compsac/test_generate_dataset.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-dataset.ruff.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED,
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "COMPSAC-dataset (P02): deterministic synthetic dataset and split builder "
            "delegating entirely to the audited shared kernel "
            "evaluation/venue2027/_shared/dataset_kernel.py (generate / detect_split_leakage / "
            "assert_no_leakage / assert_valid_frequencies); no split, family-assignment, "
            "hash or validation logic re-implemented locally. generate(seed, split=None, n=120) "
            "-> kernel Dataset for venue 'compsac' (unit prefix sched-, families "
            "clean/omitted_dependency/epoch_race/stale_readset, 60/20/20 split by independent "
            "unit, split-independent buffered content hash), augmented with the COMPSAC-specific "
            "per-family schedule payload "
            "clara.compsac.schedule-payload-v1 (dependency_density family base + seed/idx "
            "jitter in [0,1], contention_level sweeping the blueprint worker tiers 1/2/4/8/16, "
            "zipf_skew in [0.5,1.5], graph_fanout 1-8 derived from density) computed by pure "
            "integer arithmetic from (seed, family, idx) - no RNG object, no clock, no dict "
            "iteration order. write_dataset(outdir, seed, n) emits dataset.jsonl (sorted, "
            "stable JSON) + inventory.json with per-split/per-family cardinalities, kernel "
            "content_sha256, jsonl_sha256 and versions; real artifact generated at "
            "research/venue2027/proof/artifacts/compsac_dataset/ (seed=42, n=240, content "
            "sha256 bcf74be49842c15345d35e4e2d2a400d0c57f556ae3ac53c2d5cfc156989e889, "
            "by_family 60/60/60/60, by_split 144/48/48, guards re-verified on the artifact: "
            "assert_no_leakage over train/dev/test views + assert_valid_frequencies both OK). "
            "Fail-closed semantics: kernel reason codes UNKNOWN_VENUE/INVALID_N/UNKNOWN_SPLIT/"
            "SPLIT_LEAKAGE/INVALID_FAMILY_FREQUENCY/PHI_FIELD_PRESENT plus local UNKNOWN_FAMILY "
            "for unregistered schedule families. Tests 12 passed: positive (same seed identical "
            "content hash and byte-identical JSONL incl. write_dataset reruns; split filter "
            "returns exactly that split with hash/inventory split-independence; inventory "
            "totals==n across records, splits, families and written artifacts; no leakage "
            "across the three split views; balanced family frequencies within kernel tolerance "
            "0.35; schedule payload present, bounded, deterministic and contention tiers "
            "actually sweep {1,2,4,8,16}) and adversarial (same unit_id in two splits detected "
            "as SPLIT_LEAKAGE by the kernel; zero-record and dominant families refused "
            "INVALID_FAMILY_FREQUENCY; unknown split 'holdout' refused UNKNOWN_SPLIT; unknown "
            "family refused UNKNOWN_FAMILY; n<=0 refused INVALID_N; no PHI-named field in any "
            "payload or written artifact). baseline_parity=NOT_APPLICABLE: dataset builder, no "
            "baseline arms involved. source_sha_after = base SHA per established repo "
            "convention (proof report committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "COMPSAC-dataset.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
