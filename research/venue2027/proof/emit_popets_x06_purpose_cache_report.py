"""Emit the POPETS-X06_purpose_cache proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the POPETS-X06_purpose_cache task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "POPETS-X06_purpose_cache"

BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "evaluation/venue2027/popets/baselines.py",
    "evaluation/venue2027/popets/fixtures/purpose_aware_cache_x06_parity.json",
    "research/venue2027/popets/tasks/purpose_cache_impl.md",
    "research/venue2027/popets/tests/test_x06_purpose_cache.py",
    "research/venue2027/proof/POPETS-X06_purpose_cache.json",
    "research/venue2027/proof/logs/POPETS-X06_purpose_cache.pytest.log",
    "research/venue2027/proof/logs/POPETS-X06_purpose_cache.ruff.log",
]

COMMANDS = [
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/popets/tests/test_x06_purpose_cache.py "
            "evaluation/venue2027/popets/test_baselines.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X06_purpose_cache.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/popets/ evaluation/venue2027/popets/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X06_purpose_cache.ruff.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 format --check research/venue2027/popets/tests/"
            "test_x06_purpose_cache.py evaluation/venue2027/popets/baselines.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X06_purpose_cache.ruff.log",
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
        artifact_paths=CHANGED[:4],
        repo=REPO,
        unresolved=[],
        baseline_parity="PASS",
        notes=(
            "POPETS-X06_purpose_cache (Phase P03, RQ3): formalized the task contract "
            "'fetch(key, epoch, purpose) -> Context' as the DIRECTLY CALLABLE comparator arm "
            "purpose-aware-cache-x06 in evaluation/venue2027/popets/baselines.py (additive over "
            "POPETS_BASELINES_VERSION 1.0.0 -> 1.1.0): typed PurposeCacheEntry lines keyed "
            "(subject, grant, purpose, consent_epoch), public purpose_cache_fetch refusing "
            "cross-purpose reads (PURPOSE_MISMATCH) and superseded epochs (EPOCH_STALE), "
            "idempotent per-revocation epoch rotation, fail-closed on missing lineage sources "
            "and malformed keys, content never serialized into detail (byte counts only). "
            "Real measured accounting per run: cache_entries_created, cache_entries_total, "
            "live_entries_current_epoch, cache_hits, cache_misses, recomputations, "
            "invalidation_events, purpose_isolation_violations, exposed_bytes_total. "
            "New test driver research/venue2027/popets/tests/test_x06_purpose_cache.py (18 "
            "tests) runs the SAME context under TWO DIFFERENT purposes through the real "
            "run_baseline: asserts separate cache entries (cache_entries_created>=2, "
            "live_entries_current_epoch==2), NO cross-purpose reuse/leakage (first use under "
            "each purpose misses even with identical cached lineage; every HIT is a "
            "same-purpose same-epoch record; purpose_isolation_violations==0 and no "
            "context_leaked_across_purposes record across all runs; post-revocation rotation "
            "scoped to the revoked purpose while the other purpose is admitted at the same "
            "instant), real entry/recomputation counts reconciled (cache_hits + cache_misses "
            "== dispatch_count; recomputations == cache_misses; rotation creates a fresh "
            "entry at the new epoch while the superseded entry stays audit-only and "
            "unreachable), the direct fetch contract adversarials (PURPOSE_MISMATCH on "
            "cross-purpose read, EPOCH_STALE/CACHE_MISS on rotated keys, KEY_MALFORMED on "
            "malformed keys), parity_check True for all four implemented baselines, "
            "determinism, and EXECUTION_ERROR/WORKLOAD_MALFORMED fail-closed. The new arm "
            "ships its own parity fixture purpose_aware_cache_x06_parity.json. 55 passed "
            "(18 X06 + 37 pre-existing baseline suite, all green unmodified); full "
            "research/venue2027 + evaluation/venue2027 regression: 1526 passed. "
            "uvx ruff@0.7.1 check clean on both popets packages and touched files (repo-wide "
            "ruff has pre-existing unrelated findings in untouched scripts/services files; "
            "no new findings introduced - verified by before/after diff). "
            "baseline_parity=PASS (all four implemented POPETS parity vectors reproduce). "
            "source_sha_after records the base commit 293bde7b per established sibling "
            "convention (POPETS-baselines, ACNS-baselines); the single task commit SHA is "
            "created immediately after this report and recorded in the commit body. No claim "
            "of retroactive erasure: the arm measures post-revocation future dispatches only."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "POPETS-X06_purpose_cache.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
