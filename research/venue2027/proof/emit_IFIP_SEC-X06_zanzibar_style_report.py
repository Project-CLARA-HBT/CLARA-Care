"""Emit the IFIP_SEC-X06_zanzibar_style proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the IFIP_SEC-X06_zanzibar_style task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "IFIP_SEC-X06_zanzibar_style"

BASE_SHA = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED = [
    "evaluation/venue2027/ifip_sec/consistency_token_adapter.py",
    "evaluation/venue2027/ifip_sec/baselines.py",
    "evaluation/venue2027/ifip_sec/test_baselines.py",
    "research/venue2027/ifip_sec/tasks/zanzibar_style_impl.md",
    "research/venue2027/ifip_sec/tests/test_x06_zanzibar_style.py",
    "research/venue2027/proof/IFIP_SEC-X06_zanzibar_style.json",
    "research/venue2027/proof/logs/IFIP_SEC-X06_zanzibar_style.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-X06_zanzibar_style.ruff.log",
]

COMMANDS = [
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/ifip_sec/tests/test_x06_zanzibar_style.py "
            "evaluation/venue2027/ifip_sec/test_baselines.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X06_zanzibar_style.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check research/venue2027/ifip_sec/ evaluation/venue2027/ifip_sec/ "
            "--config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X06_zanzibar_style.ruff.log",
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
        artifact_paths=CHANGED[:5],
        repo=REPO,
        unresolved=[],
        baseline_parity="PASS",
        notes=(
            "IFIP_SEC-X06_zanzibar_style (Phase P03, RQ1; cost markers feed RQ3): formalized "
            "the task contract 'check_with_revision(principal, resource, token) -> Verdict' as "
            "the DIRECTLY CALLABLE Zanzibar-style consistency-aware authorization comparator "
            "(blueprint arm B2) in evaluation/venue2027/ifip_sec/consistency_token_adapter.py "
            "(CONSISTENCY_ADAPTER_VERSION 1.0.0): append-only relation-tuple changelog with a "
            "logical total-change-ordering revision counter (delete of an absent tuple is a "
            "documented no-op that never fabricates history), zookie-style HMAC consistency "
            "tokens {v,store,revision,mac} (issue_token = fresh/minimize_latency=false head "
            "snapshot; issue_token_at = bounded-staleness capture that refuses never-committed "
            "revisions), relation-walk evaluator with computed_userset / tuple_to_userset "
            "rewrites (single rule or list-of-branches union), union semantics "
            "PRESENT>REVOKED>ABSENT and a (object,relation) cycle guard + depth backstop. "
            "Exact guarantee documented and tested: a FRESH read sees a just-granted relation "
            "(RELATION_PRESENT at the grant revision) and REJECTS a replayed pre-revocation "
            "request with RELATION_REVOKED; a pre-revocation token evaluates the earlier "
            "snapshot and faithfully ADMITs the identical replay inside the bounded-staleness "
            "window (G2) - asserted, never hidden; a pre-grant token does NOT see the "
            "just-granted relation. Token faults are first-class REJECT verdicts with stable "
            "codes (TOKEN_MISSING/TOKEN_UNPARSEABLE/TOKEN_SIGNATURE_INVALID/TOKEN_STORE_"
            "MISMATCH/TOKEN_REVISION_UNKNOWN), never exceptions miscounted as safe rejections. "
            "Real evaluation counts per verdict: tuples_examined, nodes_visited, db_round_"
            "trips (== nodes_visited) and zookie_bytes (RQ3 token-size marker). Unsupported "
            "constructs marked honestly in zanzibar_style_impl.md (no distributed changelog, "
            "no new_epoch per-user monotonic reads, no userset user ids, no intersection/"
            "exclusion, no leases). baselines.py extended purely additively (1.0.0 -> 1.1.0): "
            "new arm B2_INPROCESS_ZANZIBAR registry row + thin run_zanzibar_case dispatcher; "
            "no pre-existing arm/row/reason code changed; the pinned external OpenFGA v1.22.1 "
            "row B2_OPENFGA stays NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE (execution contract "
            "rule 8 - never a toy under the same name); only the test_baselines.py version-pin "
            "assertion widened to the documented additive range ('1.0.0','1.1.0') plus a "
            "pre-existing __post_init__ formatting drift fixed so touched files are format-"
            "clean. New test driver research/venue2027/ifip_sec/tests/test_x06_zanzibar_style."
            "py (26 tests) imports the REAL re-exported implementation and covers: fresh-sees-"
            "grant (positive control with real counts), stale-does-not-see-grant, replay-"
            "rejected-only-with-fresh-token (paired with the asserted stale-window admission), "
            "repeatability/purity, re-grant after revoke, all five token-fault fail-closed "
            "codes, walk semantics (computed_userset, tuple_to_userset hierarchy at snapshot, "
            "union branches, cycle-safe self-parent), unknown principal, delete no-op, "
            "run_baseline wiring (admit/reject/admit-stale paths, missing token as REJECT, "
            "wiring faults raise, registry+NOT_RUN_EXTERNAL row check), real counts + "
            "determinism (identical verdict dicts) and key hygiene. 59 passed (26 X06 + 33 "
            "pre-existing baseline suite); 198 passed on the wider research/venue2027/ifip_sec "
            "+ evaluation/venue2027/ifip_sec set. uvx ruff@0.7.1 check clean on both ifip_sec "
            "packages; touched files format-check clean. baseline_parity=PASS (the arm realizes "
            "the published Zanzibar Sec. 2.3-2.4 snapshot semantics; parity documented in "
            "zanzibar_style_impl.md Sec. 3, no stronger security claimed per the task "
            "falsification rule). source_sha_after records the base commit 06125d52 per the "
            "established sibling convention (POPETS-X06, IFIP_SEC-baselines); the single task "
            "commit SHA is created immediately after this report and recorded in the commit "
            "body. No real PostgreSQL / external OpenFGA claims: in-process reference only."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-X06_zanzibar_style.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
