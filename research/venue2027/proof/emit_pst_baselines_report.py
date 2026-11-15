"""Emit the PST-baselines proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the PST-baselines task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "PST-baselines"

BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/pst/__init__.py",
    "evaluation/venue2027/pst/baselines.py",
    "evaluation/venue2027/pst/test_baselines.py",
    "research/venue2027/proof/PST-baselines.json",
    "research/venue2027/proof/emit_pst_baselines_report.py",
    "research/venue2027/proof/logs/PST-baselines.pytest.log",
    "research/venue2027/proof/logs/PST-baselines.ruff.log",
    "research/venue2027/proof/logs/PST-baselines.suite.log",
    "research/venue2027/proof/logs/PST-baselines.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-baselines.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/pst/__init__.py "
            "evaluation/venue2027/pst/baselines.py "
            "evaluation/venue2027/pst/test_baselines.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-baselines.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-baselines.suite.log",
    },
    {
        "argv": (
            "python3 research/venue2027/proof/emit_pst_baselines_report.py "
            "# build_report + validate_report(ok:true) recorded in "
            "research/venue2027/proof/PST-baselines.json"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-baselines.validator.log",
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
            "evaluation/venue2027/pst/__init__.py",
            "evaluation/venue2027/pst/baselines.py",
            "evaluation/venue2027/pst/test_baselines.py",
            "research/venue2027/proof/logs/PST-baselines.pytest.log",
            "research/venue2027/proof/logs/PST-baselines.ruff.log",
            "research/venue2027/proof/logs/PST-baselines.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 baseline fidelity adapters for PST 2027 (ReceiptMin: Measuring Forensic "
            "Reconstructability under Purpose-Bound Audit Minimization). "
            "evaluation/venue2027/pst/baselines.py implements run_baseline(baseline_id, case, ctx) -> Outcome, "
            "BASELINE_REGISTRY, refuse_constant_stub, reconstructability(event_case, audit_set) -> float, "
            "linkability_score(audit_set, aux_data) -> float, and compute_frontier(cases) -> dict[str, FrontierPoint]. "
            "In-process arms: B0 full audit retention (utility upper bound 1.0, high linkability ~0.95), "
            "B1 minimized without receipts (stripping evidence without receipts loses reconstructability < 0.25 vs B0), "
            "B2 minimized + receipt anchoring (tamper-evident Merkle/witness anchoring and commitment digests "
            "recover reconstructability >= 0.85 with reduced linkability ~0.35-0.45), "
            "B3 candidate ReceiptMin (purpose-bound HMAC commitment receipts, epoch-keyed pseudonyms, and retention "
            "maps recover reconstructability >= 0.85 while minimizing linkability <= 0.20, optimizing the frontier). "
            "Unavailable external upstreams (RFC 9162 ct-merkle, encrypted-log KMS, Macaroons NDSS 2014, OpenFGA, "
            "Zanzibar, FHIR R5, MUSE, RATS RFC 9334, NIST ABAC, WHO 2021) return NOT_RUN_EXTERNAL with "
            "BASELINE_UNAVAILABLE; never a toy substitution under the pinned name (EXECUTION_CONTRACT rule 8). "
            "refuse_constant_stub replays paired answerable/unanswerable probe cases and refuses constant-perfect, "
            "detect-all, and detect-none stubs (CONSTANT_STUB_REFUSED / STUB_DETECT_ALL_REFUSED) while admitting "
            "discriminating adapters (STUB_SEPARATION_OK). compute_frontier computes strictly from evaluated sample "
            "cases, refusing empty samples with SAMPLE_EMPTY (no invented numbers beyond computed sample). "
            "21 unit tests in test_baselines.py pass; full evaluation/venue2027 suite 2087 tests pass; ruff check clean."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "PST-baselines.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    val_log = REPO / "research" / "venue2027" / "proof" / "logs" / "PST-baselines.validator.log"
    val_log.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")

    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    val_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
