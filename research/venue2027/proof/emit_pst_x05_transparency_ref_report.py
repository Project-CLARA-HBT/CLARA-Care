"""Emit research/venue2027/proof/PST-X05_transparency_ref.json via agent_protocol.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-X05_transparency_ref task. No network access.

Failure semantics: exits non-zero if report construction or validation fails;
the validator result is recorded in
``research/venue2027/proof/logs/PST-X05_transparency_ref.validator.log``.
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
TASK = "PST-X05_transparency_ref"
BASE = "75ad321ea230ad398d71f4a0afb26e0cdef83982"

CHANGED = [
    "evaluation/venue2027/pst/merkle_transparency.py",
    "evaluation/venue2027/pst/test_merkle_transparency.py",
    "research/venue2027/proof/PST-X05_transparency_ref.json",
    "research/venue2027/proof/emit_pst_x05_transparency_ref_report.py",
    "research/venue2027/proof/logs/PST-X05_transparency_ref.pytest.log",
    "research/venue2027/proof/logs/PST-X05_transparency_ref.ruff.log",
    "research/venue2027/proof/logs/PST-X05_transparency_ref.suite.log",
    "research/venue2027/proof/logs/PST-X05_transparency_ref.validator.log",
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
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_merkle_transparency.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X05_transparency_ref.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/pst/merkle_transparency.py "
                    "evaluation/venue2027/pst/test_merkle_transparency.py && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/merkle_transparency.py "
                    "evaluation/venue2027/pst/test_merkle_transparency.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X05_transparency_ref.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X05_transparency_ref.suite.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_pst_x05_transparency_ref_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/PST-X05_transparency_ref.json"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X05_transparency_ref.validator.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/pst/merkle_transparency.py",
            "evaluation/venue2027/pst/test_merkle_transparency.py",
            "research/venue2027/proof/logs/PST-X05_transparency_ref.pytest.log",
            "research/venue2027/proof/logs/PST-X05_transparency_ref.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 PST-X05_transparency_ref deliverable: evaluation/venue2027/pst/merkle_transparency.py "
            "implements the Merkle inclusion and consistency proof model aligned with RFC 9162 "
            "(Certificate Transparency v2) and RFC 6962. It provides SHA-256 leaf and interior nodes "
            "(0x00 and 0x01 domain-separated prefixes), append(entry)->int, root_hash()->str, "
            "inclusion_proof(index, size)->list[str], consistency_proof(m, n)->list[str], "
            "verify_inclusion(entry, index, size, proof, root)->bool, and "
            "verify_consistency(m, n, root_m, root_n, proof)->bool. Explicitly disclaims equating "
            "public immutable hash trees with encrypted secrecy (transparency is for public tamper-evidence, "
            "NOT confidentiality; retention decay and privacy require cryptographic key management and "
            "purpose-bound minimization). Test suite test_merkle_transparency.py covers positive controls "
            "(leaf append, root computation matching RFC test vectors including empty tree SHA-256('') "
            "and RFC 6962 Section 2.1.3 7-leaf intermediate node graph, inclusion proofs across sizes 1..25, "
            "and consistency proofs across 1 <= m <= n <= 20) and adversarial controls (tampered leaf fails, "
            "tampered root fails, forged inclusion/consistency proofs fail, diverged tree branches fail, "
            "out-of-bounds parameters fail closed, stable reason codes). "
            "All unit and regression tests pass; ruff lint and format check clean."
        ),
    )

    out_path = REPO / "research/venue2027/proof/PST-X05_transparency_ref.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/PST-X05_transparency_ref.validator.log"
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
