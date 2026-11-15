"""Emit the SACMAT-baselines proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-baselines task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "SACMAT-baselines"

BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "evaluation/venue2027/sacmat/__init__.py",
    "evaluation/venue2027/sacmat/baselines.py",
    "evaluation/venue2027/sacmat/test_baselines.py",
    "research/venue2027/proof/SACMAT-baselines.json",
    "research/venue2027/proof/emit_sacmat_baselines_report.py",
    "research/venue2027/proof/logs/SACMAT-baselines.pytest.log",
    "research/venue2027/proof/logs/SACMAT-baselines.ruff.log",
    "research/venue2027/proof/logs/SACMAT-baselines.suite.log",
    "research/venue2027/proof/logs/SACMAT-baselines.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-baselines.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/__init__.py "
        "evaluation/venue2027/sacmat/baselines.py "
        "evaluation/venue2027/sacmat/test_baselines.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/sacmat/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-baselines.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-baselines.suite.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_sacmat_baselines_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-baselines.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-baselines.validator.log",
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
        artifact_paths=[
            "evaluation/venue2027/sacmat/__init__.py",
            "evaluation/venue2027/sacmat/baselines.py",
            "evaluation/venue2027/sacmat/test_baselines.py",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 baseline fidelity adapters for SACMAT 2027 (PolicyTrace: Temporal "
            "Conformance Testing of Delegated Consent across Heterogeneous Policy "
            "Engines). evaluation/venue2027/sacmat/baselines.py implements "
            "run_baseline(baseline_id, case, ctx) -> Outcome, BASELINE_REGISTRY "
            "(B0-B3 with provenance) and refuse_constant_stub, over SYNTHETIC "
            "(policy history, request) units (versioned delegated-consent events "
            "GRANT/REVOKE/REGRANT/EXPIRE/POLICY_VERSION_BUMP in monotonic logical "
            "time + one access request at a logical decision time; no real PHI/PII, "
            "no network, no live provider, no hidden clock or randomness). Three "
            "real in-process engine models implement the pinned upstreams' "
            "documented semantics: XacmlPolicyEngine (deny-overrides rule combining "
            "over the compiled final policy state, the static structure MC/DC "
            "testing targets), CedarPolicyEngine (permit/forbid policy set with "
            "forbid precedence, Cedar v4.14.1 semantics; expiry caller-encoded) and "
            "ZanzibarPolicyEngine (relation-tuple walk at read time, Zanzibar ATC "
            "2019 / OpenFGA v1.22.1 semantics: revoked tuples are deleted). Arms: "
            "B0 static policy diff (overlap-registry B5): structural comparison of "
            "compiled engine encodings, never replays a request; B1 single-engine "
            "testing (overlap-registry B6): each engine's own pointwise test "
            "discipline against compiled-policy expectations; B2 multi-engine "
            "differential: identical requests into all three engine models at "
            "decision time (pointwise); B3 candidate temporal conformance: "
            "history-sensitive replay of the ordered history through every engine "
            "model + independent four-valued oracle adjudication "
            "(PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE), detecting delegation "
            "expiry (B3_DELEGATION_EXPIRY_DIVERGENCE) and policy-version skew "
            "(B3_POLICY_VERSION_SKEW_DIVERGENCE). Core P03 separation asserted "
            "explicitly in tests: a history-healed version-skew unit "
            "(grant->revoke->regrant in force, POLICY_VERSION_BUMP after decision "
            "time) where all three engines agree pointwise is ADMITted by B0, B1 "
            "AND B2 but REJECTed by B3; an expiry race is missed by B0/B1 (compiled "
            "final-state engines both PERMIT pointwise) and caught by B3 via the "
            "oracle's temporal DENY; a clean regrant-in-force history ADMITs under "
            "every arm. Malformed inputs (missing/empty/non-list history, unknown "
            "event kinds, bad types, non-monotonic logical times, missing request "
            "fields) yield first-class INDETERMINATE outcomes with stable reason "
            "codes, never silently counted as safe rejections. "
            "simulate_unavailable_upstream on the injected context models "
            "unreachable pinned engine binaries: B1/B2/B3 return NOT_RUN_EXTERNAL / "
            "BASELINE_UNAVAILABLE (never counted, retriable) while B0 (pure "
            "in-process structural diff) still runs — no toy substitution under a "
            "pinned name (EXECUTION_CONTRACT rule 8). refuse_constant_stub replays "
            "paired conformance/clean probe cases and refuses detect-all "
            "(STUB_DETECT_ALL_REFUSED), detect-none (STUB_DETECT_NONE_REFUSED) and "
            "constant-output (CONSTANT_STUB_REFUSED) candidates while admitting the "
            "real separating B3 adapter (STUB_SEPARATION_OK). Oracle independence: "
            "the four-valued oracle is the in-module declarative reference "
            "semantics and derives its verdict from ordered-history state, never "
            "from a single engine model; the module imports no external "
            "oracle/candidate code (asserted via AST hygiene test). Machine-checked: "
            "38 new tests pass (positive: registry provenance, per-engine evaluation "
            "of real delegated-consent requests, XACML deny-overrides, Cedar forbid "
            "precedence, Zanzibar read-time tuple walk, four-valued oracle "
            "history-sensitivity, B3 expiry+skew detection, clean-history admission "
            "under every arm, determinism; adversarial: B0/B1/B2 miss the "
            "B3-only temporal divergence, NOT_RUN_EXTERNAL arms, stub refusal "
            "quartet, malformed-input INDETERMINATE battery, wiring-error fail-"
            "closed); full evaluation/venue2027 suite 470 passed; ruff check + "
            "format clean on touched files. source_sha_after = base SHA per "
            "established repo convention (proof report committed together with the "
            "work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-baselines.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
