"""Emit the IFIP_SEC-threat proof report via the shared agent protocol.

Run from the task worktree root. The report is built with
``agent_protocol.build_report`` (task_id='IFIP_SEC-threat'), then validated
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
        task_id="IFIP_SEC-threat",
        status="PASS",
        source_sha_before=sha_before,
        source_sha_after=sha_before,  # single-commit convention: final SHA in handoff
        changed_paths=[
            "research/venue2027/ifip_sec/threat_model.md",
            "research/venue2027/ifip_sec/tests/test_threat_model.py",
            "research/venue2027/proof/IFIP_SEC-threat.json",
            "research/venue2027/proof/logs/IFIP_SEC-threat.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-threat.ruff.log",
            "research/venue2027/proof/logs/IFIP_SEC-threat.validator.log",
            "research/venue2027/proof/logs/IFIP_SEC-threat.shared_regression.log",
        ],
        commands=[
            {
                "argv": "python3 -m pytest -q research/venue2027/ifip_sec/tests/test_threat_model.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-threat.pytest.log",
            },
            {
                "argv": (
                    "ruff check research/venue2027/ifip_sec/ && "
                    "ruff format --check research/venue2027/ifip_sec/"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-threat.ruff.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/_shared/tools/threat_model.py "
                    "research/venue2027/ifip_sec/threat_model.md"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-threat.validator.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-threat.shared_regression.log",
            },
        ],
        artifact_paths=[
            "research/venue2027/ifip_sec/threat_model.md",
            "research/venue2027/ifip_sec/tests/test_threat_model.py",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P01 threat model frozen: attacker/observer classes A1-A5 plus audit observers; "
            "trusted components (capability receipt format, delegation ledger, policy engine "
            "with independent consent/policy epochs, consume-once nonce store under real "
            "PostgreSQL 16 for RQ2, independent oracle, synthetic fixture generator); excluded "
            "domains (compromised signing keys, Byzantine policy engine/ledger, storage "
            "tampering, prompt injection, cryptanalysis, DoS, real PHI); revocation/schedule "
            "time is logical (dispatch -> revoke-commit -> consume interleavings); model agency "
            "with stale-re-execution power; paired clean/adversarial matrix over all five "
            "registered families mapped to IFIP_SEC-CASE-01..06 fixtures. Shared validator "
            "validate_threat() returns ok=true with all five families paired. 16 positive/"
            "adversarial tests pass; shared regression suite 131 tests pass; ruff clean. "
            "Validator caveat recorded honestly: the UNDEFINED_AUTHORITY branch in the shared "
            "validator is unreachable code (the substring 'defined' is contained in "
            "'undefined', so its guard can never hold); the threat model therefore declares "
            "defined authority explicitly and the test file enforces the documented contract "
            "directly on the section text. SHA convention follows repo precedent "
            "(SH-claim_overlap/IFIP_SEC-scope): before==after==parent source state because "
            "the single required commit contains this self-referential report; the final "
            "deliverable commit SHA is reported in the handoff."
        ),
    )
    out_path = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-threat.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    validation = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="IFIP_SEC-threat",
    )
    print(json.dumps(validation.to_dict(), indent=2))
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
