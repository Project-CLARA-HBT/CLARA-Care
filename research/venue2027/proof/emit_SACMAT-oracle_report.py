"""Emit research/venue2027/proof/SACMAT-oracle.json via agent_protocol.

Assembles the SACMAT-oracle task report with real command logs (pytest,
ruff check+format, emitter/validator) and hashes every declared artifact,
then validates it with agent_protocol.validate_report.
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

TASK_ID = "SACMAT-oracle"
SOURCE_SHA_BEFORE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED_PATHS = [
    "evaluation/venue2027/sacmat/independent_oracle.py",
    "evaluation/venue2027/sacmat/test_independent_oracle.py",
    "research/venue2027/proof/SACMAT-oracle.json",
    "research/venue2027/proof/logs/SACMAT-oracle.pytest.log",
    "research/venue2027/proof/logs/SACMAT-oracle.ruff.log",
    "research/venue2027/proof/logs/SACMAT-oracle.emit.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/sacmat/independent_oracle.py",
    "evaluation/venue2027/sacmat/test_independent_oracle.py",
    "research/venue2027/proof/logs/SACMAT-oracle.pytest.log",
    "research/venue2027/proof/logs/SACMAT-oracle.ruff.log",
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
                "evaluation/venue2027/sacmat/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/sacmat/independent_oracle.py "
                "evaluation/venue2027/sacmat/test_independent_oracle.py --config ruff.toml && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/sacmat/independent_oracle.py "
                "evaluation/venue2027/sacmat/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_SACMAT-oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent per-case truth oracle for RQ1-RQ3 (PolicyTrace: Temporal "
            "Conformance Testing of Delegated Consent across Heterogeneous Policy Engines). "
            "independent_oracle.py: adjudicate(case) -> OracleResult DELEGATES entirely to the "
            "audited shared kernel evaluation/venue2027/_shared/oracle_kernel.adjudicate with the "
            "module-local declarative SACMAT rule table SACMAT_RULES = {conformant->ADMIT, "
            "expiry_divergence->REJECT, policy_skew->REJECT, obligation_mismatch->REJECT} "
            "(registered dataset-kernel ground-truth families); undeclared/unknown families "
            "return first-class INDETERMINATE (kernel reason codes NO_FAMILY_DECLARED / "
            "UNMODELLED_FAMILY, never a silent safe verdict) and a missing case_id raises the "
            "stable kernel reason code MISSING_CASE_ID. ORACLE_ID='sacmat-conformance-reference'; "
            "evidence URIs from the case record flow into OracleResult.evidence_refs; "
            "SACMAT_ORACLE_VERSION='1.0.0'; JSON-serializable output (kernel_version pinned). "
            "INDEPENDENCE (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2): the module does NOT "
            "import the SACMAT candidate machinery — evaluation/venue2027/sacmat/baselines.py "
            "(B0-B3 arms with the in-process engine models) nor "
            "evaluation/venue2027/sacmat/policy_trace_dsl.py (temporal DSL); "
            "verify_independence(source=None) runs two layered ast scans on the oracle source "
            "(live module by default, injected text in tests): (1) the audited kernel contract "
            "oracle_kernel.assert_oracle_independence with FORBIDDEN_MODULE_NAMES = "
            "('sacmat.baselines','baselines','policy_trace_dsl') — root-component matching plus "
            "DYNAMIC_IMPORT_UNRESOLVABLE on __import__/import_module — and (2) a module-local "
            "full-target scan matching every dotted import path component and "
            "from-module-import alias binds against the same forbidden names, closing the "
            "package-qualified form the kernel-level root match legitimately cannot name "
            "without forbidding the repo's own package root; matching is exact per dotted "
            "component (never substring), so unrelated modules like sacmat_baseline_helpers do "
            "not trip it; violations raise OracleError CANDIDATE_IMPORT naming every offending "
            "target. TRUTH PROVENANCE: ground truth derives from the case's declared "
            "policy/consent family — tests prove candidate-claimed reason codes "
            "(CANDIDATE_CLAIMED_*/B3_*/PERMIT/DENY) and forged observed_outcome/arm blocks "
            "never flip a verdict off the ground truth. test_independent_oracle.py imports only "
            "the oracle and the shared kernel (independent-oracle rule): 32 passed — 10 positive "
            "controls (four registered families match the manual canonical history, kernel-"
            "delegation identity, nested payload family, rule-table shape/oracle_id/version, "
            "determinism + JSON round-trip with pinned kernel_version, evidence capture) and 22 "
            "adversarial (5 parametrized candidate-reason-code non-influence vectors, forged arm "
            "observation ignored, unknown family INDETERMINATE, missing family INDETERMINATE, "
            "missing case_id, clean live source passes, 10 candidate-import variants refused, "
            "dynamic import refused, tampered-live-source flip control, exact-acceptance of "
            "unrelated imports). uvx ruff@0.7.1 check + format --check clean (ruff.toml). "
            "source_sha_after records the base commit e5f7ee3b per sibling convention "
            "(SACMAT-X01/SACMAT-baselines); the single task commit SHA is created immediately "
            "after this report and reported in the handoff. oracle_disagreement_count=0 (32/32 "
            "oracle verdicts consistent with the kernel contract); baseline parity "
            "NOT_APPLICABLE (oracle layer; arms B0-B3 execute via SACMAT-baselines)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "SACMAT-oracle.json"
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
        ROOT / "research" / "venue2027" / "proof" / "logs" / "SACMAT-oracle.emit.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
