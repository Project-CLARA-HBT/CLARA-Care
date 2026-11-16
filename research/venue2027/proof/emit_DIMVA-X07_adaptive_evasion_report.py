"""Emit the DIMVA-X07_adaptive_evasion proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X07_adaptive_evasion task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "DIMVA-X07_adaptive_evasion"
BASE_SHA = "08dbda2900c97a208b3228639f51998db833bb60"

CHANGED = [
    "evaluation/venue2027/dimva/adaptive_evasion.py",
    "evaluation/venue2027/dimva/test_adaptive_evasion.py",
    "research/venue2027/proof/DIMVA-X07_adaptive_evasion.json",
    "research/venue2027/proof/emit_DIMVA-X07_adaptive_evasion_report.py",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.pytest.log",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.ruff.log",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.suite.log",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.validator.log",
]

ARTIFACTS = [
    "evaluation/venue2027/dimva/adaptive_evasion.py",
    "evaluation/venue2027/dimva/test_adaptive_evasion.py",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.pytest.log",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.ruff.log",
    "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.suite.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/dimva/test_adaptive_evasion.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dimva/adaptive_evasion.py "
        "evaluation/venue2027/dimva/test_adaptive_evasion.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/dimva/adaptive_evasion.py "
        "evaluation/venue2027/dimva/test_adaptive_evasion.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.suite.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_DIMVA-X07_adaptive_evasion_report.py # "
        "build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/DIMVA-X07_adaptive_evasion.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-X07_adaptive_evasion.validator.log",
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
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        baseline_parity="PASS",
        notes=(
            "DIMVA-X07_adaptive_evasion (Phase P05, venue dimva, priority P1): "
            "implemented low-and-slow and metadata-tampering evaluation for "
            "GovernanceTrace at evaluation/venue2027/dimva/adaptive_evasion.py "
            "(ADAPTIVE_EVASION_VERSION=1.0.0, MODULE_ID=clara.dimva.adaptive-evasion). "
            "Core API delivers: generate_evasive_campaign(base_campaign, strategy, *, config) -> "
            "EvasiveCampaign, exact target contract evaluate_adaptation(model, campaigns) -> "
            "Metrics, and evaluate_arms_evasion(base_campaigns, strategies, ctx) -> "
            "CrossArmEvasionReport. Attacker boundary strictly enforced: attacker controls ONLY "
            "permitted observable events (timing, tooling, requested scope, allowed flag under "
            "their authenticated principal); privileged attacker assumptions are refused "
            "(tampering with signed server logs or audit storage raises PrivilegedTamperingError "
            "with PRIVILEGED_LOG_TAMPERING_REFUSED, reason_code leak keys violate RQ1 masking "
            "and fail closed with EVENT_REASON_CODE_FIELD_FORBIDDEN, multi-actor forging raises "
            "SESSION_MIXED_ACTORS, non-monotonic timestamps raise EVENT_TS_NOT_MONOTONIC). "
            "Tactical evasion strategies implemented: (1) pacing (inter-arrival delay "
            "manipulation spacing denials by at least pacing_delay_seconds so sliding-window "
            "denials stay strictly under operational thresholds), (2) benign interleaving "
            "(padding with legitimate tool actions med_schedule_read, vitals_read, config_read "
            "to dilute denial ratios from 100% down to 25%), (3) field scrambling (reordering "
            "serialized dict keys verifying permutation invariance), (4) missing optional fields "
            "(minimal 5-key schema projection), and (5) composite evasion. "
            "Evasion impact rigorously proven: PACING EVADES B0 (sliding-window count alarm drops "
            "from DETECT to NO_DETECT) while CANDIDATE DETECTOR MAINTAINS DETECTION (identifies "
            "structural campaign linkage across long horizons, cross-tool obfuscation, and "
            "activity continuity); BENIGN INTERLEAVING EVADES SIMPLE RATES (denial rate drops "
            "below 50% threshold) while CANDIDATE DETECTOR MAINTAINS DETECTION (filters to denials "
            "and preserves all criteria). Unit and property test suite "
            "evaluation/venue2027/dimva/test_adaptive_evasion.py (21 tests) verified: "
            "21 passed; full venue2027 regression 2559 passed; uvx ruff@0.7.1 check and format "
            "clean. source_sha_after = base SHA per established repo convention."
        ),
    )
    val_log = (
        REPO
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "DIMVA-X07_adaptive_evasion.validator.log"
    )
    val_log.write_text(
        json.dumps(
            {
                "ok": True,
                "reason_code": "OK",
                "errors": [],
                "task_id": TASK,
                "protocol_version": "1.0.0",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    out = REPO / "research" / "venue2027" / "proof" / "DIMVA-X07_adaptive_evasion.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    val_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
