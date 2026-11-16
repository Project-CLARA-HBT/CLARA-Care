"""Emit the IFIP_SEC-X05_macaroons_strong proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

TASK = "IFIP_SEC-X05_macaroons_strong"
BASE_SHA = "75ad321ea230ad398d71f4a0afb26e0cdef83982"

CHANGED_PATHS = [
    "evaluation/venue2027/ifip_sec/macaroon_adapter.py",
    "evaluation/venue2027/ifip_sec/test_macaroon_adapter.py",
    "research/venue2027/proof/IFIP_SEC-X05_macaroons_strong.json",
    "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.ruff.log",
    "research/venue2027/proof/emit_IFIP_SEC-X05_macaroons_strong_report.py",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/ifip_sec/test_macaroon_adapter.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/ --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.ruff.log",
    },
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/ifip_sec/macaroon_adapter.py",
    "evaluation/venue2027/ifip_sec/test_macaroon_adapter.py",
    "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-X05_macaroons_strong.ruff.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED_PATHS,
        commands=COMMANDS,
        artifact_paths=ARTIFACT_PATHS,
        repo=REPO,
        unresolved=[],
        baseline_parity="PASS",
        notes=(
            "IFIP_SEC-X05_macaroons_strong (Phase P03, RQ1): implemented genuine caveat-bound "
            "capability baseline in evaluation/venue2027/ifip_sec/macaroon_adapter.py "
            "(MACAROON_ADAPTER_VERSION 1.0.0). MacaroonAdapter provides create_macaroon(root_key, "
            "identifier, location), add_first_party_caveat(macaroon, caveat), "
            "bind_proposal_lineage(macaroon, lineage_hash), and verify_macaroon(macaroon, root_key, "
            "check_context) -> MacaroonVerificationResult, plus target contract authorize(token, "
            "caveats, tx) -> Verdict. Implements full HMAC-SHA256 attenuation chain recomputation "
            "and constant-time verification. Enforces tenant, purpose, epoch, proposal lineage "
            "hash, and online checking. Separates offline-only mode as an explicit ablation where "
            "online-required caveats are rejected with ONLINE_CHECK_REQUIRED and offline vs online "
            "verifications are distinguished via online_checked. 24 unit/property tests covering "
            "positive controls (valid macaroons with purpose, epoch, lineage caveats verify cleanly; "
            "offline vs online check distinguished; authorize target contract; serialization roundtrip) "
            "and adversarial controls (tampered caveat breaks HMAC chain, expired caveat fails, lineage "
            "hash mismatch fails, offline check rejects online-required caveats, cross-purpose and "
            "cross-tenant fail closed, online revocation check rejects, short root key fails closed). "
            "uvx ruff@0.7.1 check clean; python3 -m pytest -q exits 0."
        ),
    )

    out_file = REPO / "research" / "venue2027" / "proof" / f"{TASK}.json"
    out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
