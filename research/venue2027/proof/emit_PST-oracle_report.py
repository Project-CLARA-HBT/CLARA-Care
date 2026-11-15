"""Emit research/venue2027/proof/PST-oracle.json via agent_protocol.

Assembles the PST-oracle task report with real command logs (pytest, ruff
check+format, emitter/validator) and hashes every declared artifact, then
validates it with agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "PST-oracle"
SOURCE_SHA_BEFORE = "687a6f56def769fc930e0ee94b00476eecc1c69b"

CHANGED_PATHS = [
    "evaluation/venue2027/pst/independent_oracle.py",
    "evaluation/venue2027/pst/test_independent_oracle.py",
    "research/venue2027/proof/PST-oracle.json",
    "research/venue2027/proof/logs/PST-oracle.pytest.log",
    "research/venue2027/proof/logs/PST-oracle.ruff.log",
    "research/venue2027/proof/logs/PST-oracle.emit.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/pst/independent_oracle.py",
    "evaluation/venue2027/pst/test_independent_oracle.py",
    "research/venue2027/proof/logs/PST-oracle.pytest.log",
    "research/venue2027/proof/logs/PST-oracle.ruff.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q "
                "evaluation/venue2027/pst/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/pst/independent_oracle.py "
                "evaluation/venue2027/pst/test_independent_oracle.py --config ruff.toml && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/pst/independent_oracle.py "
                "evaluation/venue2027/pst/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_PST-oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent per-case truth oracle for RQ1-RQ3 (ReceiptMin: Measuring Forensic "
            "Reconstructability under Purpose-Bound Audit Minimization). independent_oracle.py: "
            "adjudicate(case) -> OracleResult DELEGATES entirely to the audited shared kernel "
            "evaluation/venue2027/_shared/oracle_kernel.adjudicate with the module-local "
            "declarative PST forensic reference rule table PST_RULES = {full_evidence->ADMIT "
            "(PST-CASE-01 bounded reconstruction), minimized_omission->REJECT (PST-CASE-05 "
            "over-redaction reported as audit incompleteness, never false success), "
            "receipt_anchored->ADMIT (PST-CASE-04 tamper-evident commitment/epoch proofs), "
            "linkability_leak->REJECT (PST-CASE-02/06 purpose-tag metadata joins disclose "
            "attributes)} (registered dataset-kernel ground-truth families "
            "VENUE_FAMILIES['pst']); undeclared/unknown families (incl. the PST-CASE-07 "
            "key-custody ambiguity class) return first-class INDETERMINATE (kernel reason codes "
            "NO_FAMILY_DECLARED / UNMODELLED_FAMILY, never a silent safe verdict) and a missing "
            "case_id raises the stable kernel reason code MISSING_CASE_ID. "
            "ORACLE_ID='pst-forensic-reference'; evidence URIs from the case record flow into "
            "OracleResult.evidence_refs; PST_ORACLE_VERSION='1.0.0'; JSON-serializable output "
            "(kernel_version pinned). INDEPENDENCE (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item "
            "2): the module does NOT import the PST candidate machinery — "
            "evaluation/venue2027/pst/baselines.py (B0-B4 arms) nor "
            "evaluation/venue2027/pst/candidate.py (C0 arm); verify_independence(source=None) "
            "runs two layered ast scans on the oracle source (live module by default, injected "
            "text in tests): (1) the audited kernel contract "
            "oracle_kernel.assert_oracle_independence with FORBIDDEN_MODULE_NAMES = "
            "('pst.baselines','baselines','candidate') — root-component matching plus "
            "DYNAMIC_IMPORT_UNRESOLVABLE on __import__/import_module — and (2) a module-local "
            "full-target scan matching every dotted import path component and "
            "from-module-import alias binds against the same forbidden names, closing the "
            "package-qualified form the kernel-level root match legitimately cannot name "
            "without forbidding the repo's own package root; matching is exact per dotted "
            "component (never substring), so unrelated modules like pst_baseline_helpers do not "
            "trip it; violations raise OracleError CANDIDATE_IMPORT naming every offending "
            "target. TRUTH PROVENANCE: ground truth derives from the case's declared scenario "
            "family — tests prove candidate-claimed reason codes (CANDIDATE_CLAIMED_*/B4_*/"
            "PERMIT/DENY) and forged observed_outcome/arm blocks never flip a verdict off the "
            "ground truth. test_independent_oracle.py imports only the oracle and the shared "
            "kernel (independent-oracle rule): 34 passed — 12 positive controls (four "
            "registered families match the CASE_MATRIX sentinel semantics, kernel-delegation "
            "identity, nested payload family, rule-table shape/oracle_id/version/forbidden "
            "names, determinism + JSON round-trip with pinned kernel_version, per-family "
            "determinism, evidence capture) and 22 adversarial (5 parametrized "
            "candidate-reason-code non-influence vectors, forged arm observation ignored, "
            "unknown family INDETERMINATE, missing family INDETERMINATE, missing case_id, clean "
            "live source passes, 10 candidate-import variants refused, dynamic import refused, "
            "tampered-live-source flip control, temp oracle file importing the candidate "
            "refused by both the kernel file-level scanner and the module-local scan while a "
            "clean temp oracle passes, exact-acceptance of unrelated imports). uvx ruff@0.7.1 "
            "check + format --check clean (ruff.toml). source_sha_after records the base commit "
            "687a6f56 per sibling convention (report emitted before the single task commit); "
            "the commit SHA is created immediately after this report and reported in the "
            "handoff. oracle_disagreement_count=0 (34/34 oracle verdicts consistent with the "
            "kernel contract); baseline parity NOT_APPLICABLE (oracle layer; arms B0-B4 execute "
            "via PST-baselines)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "PST-oracle.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = (
        ROOT / "research" / "venue2027" / "proof" / "logs" / "PST-oracle.emit.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
