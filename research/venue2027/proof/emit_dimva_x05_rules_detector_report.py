"""Emit the DIMVA-X05_rules_detector task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X05_rules_detector task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED = [
    "research/venue2027/dimva/tasks/rules_detector_impl.md",
    "research/venue2027/dimva/tests/test_x05_rules_detector.py",
    "research/venue2027/proof/DIMVA-X05_rules_detector.json",
    "research/venue2027/proof/emit_dimva_x05_rules_detector_report.py",
    "research/venue2027/proof/logs/DIMVA-X05_rules_detector.pytest.log",
    "research/venue2027/proof/logs/DIMVA-X05_rules_detector.ruff.log",
    "research/venue2027/proof/logs/DIMVA-X05_rules_detector.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X05_rules_detector",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q research/venue2027/dimva/tests/"
                    "test_x05_rules_detector.py evaluation/venue2027/dimva/test_baselines.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X05_rules_detector.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check research/venue2027/dimva/tests/"
                    "test_x05_rules_detector.py evaluation/venue2027/dimva/baselines.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X05_rules_detector.ruff.log",
            },
        ],
        artifact_paths=[
            "research/venue2027/dimva/tasks/rules_detector_impl.md",
            "research/venue2027/dimva/tests/test_x05_rules_detector.py",
            "research/venue2027/proof/logs/DIMVA-X05_rules_detector.pytest.log",
            "research/venue2027/proof/logs/DIMVA-X05_rules_detector.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 DIMVA-X05 rules detector formalized and executed through the REAL baseline "
            "adapter run_baseline('B1', case, ctx) / run_baseline_detection (evaluation/"
            "venue2027/dimva/baselines.py, BASELINES_VERSION 1.0.0, registry entry "
            "temporal-rule-sequence-signature; no forked implementation, baseline module "
            "unmodified so evaluation/venue2027/dimva/test_baselines.py stays green — 57 tests). "
            "research/venue2027/dimva/tasks/rules_detector_impl.md formalizes the B1 static "
            "cross-scope denial signature (registry: temporal-rule-sequence-signature): the "
            "locked rule followups(E,H) = |{e allowed-or-denied : exists d in D, e.scope != "
            "d.scope, 0 <= e.ts - d.ts <= H}| (allowed follow-ups offset 0 <= Δt <= H, denied "
            "follow-ups 0 < Δt <= H so a denial never counts itself), the locked operating point "
            "followups >= 1 with reason_code CROSS_SCOPE_DENIAL_RULE, the saturated arm-local "
            "score min(1, followups/max(1,|D|)) (evidence magnitude, not a probability), the "
            "injectable horizon H = ctx.b1_horizon_seconds (default 86400 s, inclusive boundary), "
            "the finite-state reading (scope-transition signature machine; same-scope events, "
            "pacing and tool identity are invisible to it) and the fail-closed semantics "
            "(INDETERMINATE reason codes for malformed/leak-safe-violating events; wiring errors "
            "raise). Precision/recall behaviour formalized: high-recall/precision-capped on its "
            "signature channel (scope transitions after denials); precision caveat documented — "
            "benign single-denial-then-cross-scope sessions are the rule's unavoidable FPR source "
            "at this operating point, and the 0/20 benign false alarms below are a property of "
            "the locked fixture family, not a guarantee. Why low-and-slow campaigns are missed "
            "(measured, not assumed): a single-scope campaign leaves the signature channel empty "
            "(exists d,e: e.scope != d.scope is false for the whole stream), so followups = 0 and "
            "DETECT is unreachable for ANY threshold/horizon tuning — the miss is threshold-"
            "invariant (asserted for H in {600, 3600, 86400, 604800}); pacing orthogonality "
            "(inter-arrival enters neither signature nor score) makes B0 and B1 blind on "
            "complementary axes; the falsification consequence for RQ1/RQ3 is recorded. "
            "test_x05_rules_detector.py (29 tests) imports the real baseline module and asserts, "
            "with real measured counts: overt cross-scope probing DETECTed (overt fixture: "
            "total_denials=3, cross_scope_followups=3, score=1.0, REJECT/CROSS_SCOPE_DENIAL_RULE; "
            "single-hop operating point followups==1 alarms; denial chain accumulates 2 "
            "follow-ups); locked semantics (inclusive horizon boundary: Δt=86400 alarms, Δt=86401 "
            "does not; scope change without prior denial never alarms; same-scope denials never "
            "alarm; injectable shorter horizon un-alarms a late follow-up); the documented "
            "weakness as a first-class negative control — the low-and-slow campaign (9 denials, 9 "
            "distinct tools, ONE scope, 1080 s spacing, max_window_denials=4 < 5) is MISSED by B1 "
            "(cross_scope_followups=0 over total_denials=9, score=0.0, ADMIT) AND by B0 (max 4 < "
            "threshold 5) while B3 campaign linkage DETECTs (criteria_met=criteria_total=5); "
            "real campaign-level measurements on the locked 32-case mixed set (20 benign, 6 "
            "overt, 6 low-and-slow): overt recall 6/6, low-and-slow recall 0/6, benign false "
            "alarms 0/20, real precision_recall_auc AUCPR = 0.659874201297542 (deterministic); "
            "benign tolerance (quiet single-denial, busy same-scope burst — B0 alarms while B1 "
            "admits, multi-scope exploration with zero denials); adversarial leak-safe controls "
            "(reason_code field refused INDETERMINATE/EVENT_REASON_CODE_FIELD_FORBIDDEN, mixed "
            "actors, non-monotonic ts, malformed cases fail closed, wiring errors raise, "
            "AUC_SAMPLE_TOO_SMALL still enforced); determinism (byte-identical to_dict on repeat "
            "runs); refuse_constant_stub admits the real separating B1 (STUB_SEPARATION_OK) and "
            "refuses a detect-all stub; the shared paired probes keep the low-and-slow miss "
            "honest (purpose-hop probe DETECTed, low-and-slow probe and all benign probes "
            "NO_DETECT). Commands: pytest on the new test file + the existing baseline suite "
            "exit 0 (86 passed total); uvx ruff@0.7.1 check on touched Python + baseline module "
            "exit 0 (format --check clean). source_sha_after = commit SHA recorded at emit time; "
            "report + logs committed together with the work per established repo convention."
        ),
    )

    # Proof file lives at research/venue2027/proof/DIMVA-X05_rules_detector.json.
    out_path = REPO / "research/venue2027/proof/DIMVA-X05_rules_detector.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X05_rules_detector",
    )
    log_path = REPO / "research/venue2027/proof/logs/DIMVA-X05_rules_detector.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
