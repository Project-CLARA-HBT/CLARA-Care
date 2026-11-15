"""Emit the POPETS-X05_full_refresh task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "evaluation/venue2027/popets/baselines.py",
    "research/venue2027/popets/tasks/full_refresh_impl.md",
    "research/venue2027/popets/tests/test_x05_full_refresh.py",
    "research/venue2027/proof/logs/POPETS-X05_full_refresh.pytest.log",
    "research/venue2027/proof/logs/POPETS-X05_full_refresh.ruff.log",
    "research/venue2027/proof/logs/POPETS-X05_full_refresh.validator.log",
    "research/venue2027/proof/POPETS-X05_full_refresh.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="POPETS-X05_full_refresh",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q research/venue2027/popets/tests/"
                    "test_x05_full_refresh.py evaluation/venue2027/popets/test_baselines.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-X05_full_refresh.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check research/venue2027/popets/tests/"
                    "test_x05_full_refresh.py evaluation/venue2027/popets/baselines.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-X05_full_refresh.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/popets/baselines.py",
            "research/venue2027/popets/tasks/full_refresh_impl.md",
            "research/venue2027/popets/tests/test_x05_full_refresh.py",
            "research/venue2027/proof/logs/POPETS-X05_full_refresh.pytest.log",
            "research/venue2027/proof/logs/POPETS-X05_full_refresh.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "X05 strong full-refresh comparator formalized and executed through the REAL "
            "baseline adapter run_baseline('coarse-cache-purge-on-revocation', case, ctx) "
            "(evaluation/venue2027/popets/baselines.py, FAITHFUL_PORT, no forked "
            "implementation): research/venue2027/popets/tasks/full_refresh_impl.md "
            "formalizes the arm (purge ALL cached projections of the subject on any "
            "revocation; serve every dispatch by recompute-or-hit from the live source "
            "snapshot), its transition relation, the revocation-complete future-disclosure "
            "guarantee (post-revocation dispatches touching revoked coverage are "
            "REJECT/REVOKED_CONTEXT with zero exposed bytes, cache state can never "
            "resurrect revoked context) and the RQ3 cost model. Backwards-compatible cost "
            "accounting added to baselines.py _run_coarse_purge: recompute_count (admitted "
            "misses actually rebuilt from live source; REJECT fails closed before rebuild "
            "and pays no rebuild), cache_entries_at_purge, and cost {cache_hits, "
            "cache_misses, purge_events, entries_destroyed_by_purges, recomputes, "
            "peak_cache_size}; admission decisions, outcome labels and invalidation_events "
            "unchanged; parity fixture coarse_purge_parity.json still reproduces exactly. "
            "test_x05_full_refresh.py (12 tests) imports the real baseline, runs a "
            "revocation workload (direct + transitive retry + cached-unaffected-grant "
            "lineages), asserts all cached projections purged (invalidation_events==1, "
            "cache_entries_at_purge==2), no revoked-context leakage (post-revocation "
            "REJECT/REVOKED_CONTEXT, exposed_bytes==0, cache_hit False), false-invalidation "
            "rebuild of an unaffected grant, records the real recompute_count "
            "(==3 on the revocation workload, ==4 under two purge windows), plus "
            "fail-closed adversarial controls (LINEAGE_SOURCE_MISSING, WORKLOAD_MALFORMED, "
            "determinism, parity vector). evaluation/venue2027/popets/test_baselines.py "
            "stays green (33 tests). 45 passed total; uvx ruff@0.7.1 check clean."
        ),
    )

    # Proof file lives at research/venue2027/proof/POPETS-X05_full_refresh.json.
    out_path = REPO / "research/venue2027/proof/POPETS-X05_full_refresh.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="POPETS-X05_full_refresh",
    )
    log_path = REPO / "research/venue2027/proof/logs/POPETS-X05_full_refresh.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
