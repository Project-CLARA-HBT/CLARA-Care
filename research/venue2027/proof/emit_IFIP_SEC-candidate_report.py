"""Emit the IFIP_SEC-candidate proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the IFIP_SEC-candidate task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "IFIP_SEC-candidate"
BASE_SHA = "6fe5fe193a5a55f456f163a853c1b2c41c0c869f"

CHANGED = [
    "evaluation/venue2027/ifip_sec/candidate.py",
    "evaluation/venue2027/ifip_sec/test_candidate.py",
    "research/venue2027/proof/IFIP_SEC-candidate.json",
    "research/venue2027/proof/logs/IFIP_SEC-candidate.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-candidate.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/ifip_sec/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-candidate.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/candidate.py "
            "evaluation/venue2027/ifip_sec/test_candidate.py --config ruff.toml && "
            "uvx ruff@0.7.1 format --check evaluation/venue2027/ifip_sec/candidate.py "
            "evaluation/venue2027/ifip_sec/test_candidate.py --config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-candidate.ruff.log",
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
        artifact_paths=CHANGED[:2],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "IFIP_SEC-candidate (Phase P04; CANDIDATE DESIGN ONLY - no empirical "
            "results, no performance numbers, no win rates): implemented the "
            "replay-closed authorization candidate at "
            "evaluation/venue2027/ifip_sec/candidate.py behind "
            "authorize(receipt, request, nonce_store, ledger) -> Verdict "
            "(ALLOW/DENY with stable reason codes; CANDIDATE_ID="
            "clara.ifip_sec.candidate.replay-closed-lineage-authorization, v1.0.0; "
            "describe_mechanism() exposes the machine-readable design record; "
            "run_candidate(case, ctx) -> Outcome is the task-contract adapter, "
            "ALLOW->ADMIT / DENY->REJECT). Mechanism: every authorization binds a "
            "real HMAC-SHA256 typed-commitment receipt (hmac+hashlib, "
            "constant-time compare) over actor, patient, tenant, purpose, task, "
            "consent/policy epochs, dispatch digest, nonce, parent reference, "
            "delegation-chain hash + depth and proposal-lineage hash, PLUS a "
            "consume-once nonce in an injected store and a delegation-ancestry "
            "walk over an injected ledger - so ANY change in purpose, delegation "
            "chain, proposal lineage or epochs makes a replayed (still "
            "signature-valid) receipt fail closed before the nonce step, and an "
            "unchanged replay fails closed on the consumed nonce. Canonical "
            "pipeline (first-failure-wins, fixed binding order): shape validation "
            "(fail closed, never raising) -> HMAC verification -> expiry -> "
            "ledger registration (RECEIPT_UNKNOWN) -> cycle-safe bounded ancestry "
            "walk (DELEGATION_ANCESTRY_BROKEN) -> commitment re-derivation from "
            "unsigned transport copies (DELEGATION_CHAIN_CHANGED / "
            "LINEAGE_SPLICED) -> request-context binding against the SIGNED "
            "claims (PURPOSE/TENANT/ACTOR/PATIENT/TASK/CONSENT_EPOCH/"
            "POLICY_EPOCH_MISMATCH, DISPATCH_MISMATCH) -> optional live "
            "governance epochs (CONSENT_EPOCH_REVOKED / POLICY_EPOCH_STALE, "
            "CASE-04) -> request-presented chain/lineage binding -> consume-once "
            "nonce LAST (NONCE_REPLAYED), so binding failures never consume. "
            "ABLATION CONTRASTS SHOWN (each removes exactly one mechanism): "
            "ablation_no_lineage_binding() ADMITs the very splice authorize() "
            "DENYs with LINEAGE_SPLICED (ALLOW reason LINEAGE_UNBOUND), proving "
            "the lineage binding is the mechanism; ablation_no_nonce() ADMITs the "
            "very exact replay authorize() DENYs with NONCE_REPLAYED (ALLOW "
            "reason NONCE_UNPROTECTED, store demonstrably never consulted/"
            "consumed), proving the consume-once nonce is the mechanism; both "
            "ablated authorizers still DENY cross-purpose replay "
            "(PURPOSE_MISMATCH) - the security envelope minus one axis. "
            "Fail-closed controls: tampered claim + original MAC -> "
            "RECEIPT_SIGNATURE_INVALID; unregistered receipt -> RECEIPT_UNKNOWN; "
            "expired -> RECEIPT_EXPIRED; dangling parent and ancestor-cycle -> "
            "DELEGATION_ANCESTRY_BROKEN; consent revoked between issue and "
            "presentation -> CONSENT_EPOCH_REVOKED; malformed "
            "receipt/request/store/ledger -> DENY with fail_closed=True and "
            "nothing consumed; boundary faults via run_candidate become first-"
            "class REJECT Outcomes with stable reason codes (never uncounted "
            "exceptions). Determinism: identical inputs across repeats yield "
            "identical verdict dicts and digests; bindings_evaluated order is "
            "fixed (shape ... consume_once_nonce); receipt JSON round-trip "
            "preserves all commitments and re-verifies. Tests: 23 passed "
            "(evaluation/venue2027/ifip_sec full suite: 124 passed). uvx "
            "ruff@0.7.1 check + format --check clean. Independence preserved: the "
            "candidate imports neither the independent oracle, any baseline "
            "adapter nor any label file; the PostgreSQL-serializable nonce "
            "registry/race (IFIP_SEC-X03) and lineage digest storage (IFIP_SEC-"
            "X02) are declared out of scope. source_sha_after = base SHA per "
            "established repo convention (proof report committed together with "
            "the work); the single task commit SHA is created immediately after "
            "this report."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-candidate.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
