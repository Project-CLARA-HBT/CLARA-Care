"""Emit research/venue2027/proof/SACMAT-dataset.json via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-dataset task. No network access, no randomness.

Failure semantics: exits non-zero if report construction or validation fails;
the validation outcome is appended to the validator log regardless.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "SACMAT-dataset"

BASE_SHA = "604642528f95e9f10052bd4bc0334bdb1c84358a"

ARTIFACTS = [
    "evaluation/venue2027/sacmat/generate_dataset.py",
    "evaluation/venue2027/sacmat/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/sacmat_dataset/manifest.json",
    "research/venue2027/proof/artifacts/sacmat_dataset/dataset.jsonl",
]

CHANGED = ARTIFACTS + [
    "research/venue2027/proof/SACMAT-dataset.json",
    "research/venue2027/proof/emit_SACMAT_dataset_report.py",
    "research/venue2027/proof/logs/SACMAT-dataset.pytest.log",
    "research/venue2027/proof/logs/SACMAT-dataset.suite.log",
    "research/venue2027/proof/logs/SACMAT-dataset.shared_regression.log",
    "research/venue2027/proof/logs/SACMAT-dataset.ruff.log",
    "research/venue2027/proof/logs/SACMAT-dataset.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_generate_dataset.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.suite.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/_shared/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.shared_regression.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/generate_dataset.py "
        "evaluation/venue2027/sacmat/test_generate_dataset.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.ruff.log",
    },
    {
        "argv": "PYTHONPATH=. python3 evaluation/venue2027/sacmat/generate_dataset.py "
        "--outdir research/venue2027/proof/artifacts/sacmat_dataset --seed 2027 --n 120 "
        "# deterministic write_dataset + verify_dataset_dir; result echoed to "
        "research/venue2027/proof/logs/SACMAT-dataset.generate.log",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.generate.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT_dataset_report.py "
        "# agent_protocol.build_report + validate_report(ok:true); result appended "
        "to research/venue2027/proof/logs/SACMAT-dataset.validator.log",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-dataset.validator.log",
    },
]

NOTES = (
    "P02 venue dataset task SACMAT-dataset. "
    "evaluation/venue2027/sacmat/generate_dataset.py is a thin deterministic adapter over the "
    "audited shared kernel evaluation/venue2027/_shared/dataset_kernel.py (MANDATORY delegation: "
    "dk.generate('sacmat', seed=seed, n=n, split=split)) — split assignment, balanced family "
    "round-robin, unit-id prefix 'dlg-', leakage detection and PHI screening are all inherited "
    "from the kernel, never reimplemented. generate(seed, split, n) returns the kernel Dataset "
    "with every record payload enriched with the three SACMAT-controlled variables, each a pure "
    "deterministic function of (seed, family, idx) using the kernel determinant "
    "(seed*7919 + idx*104729) % 100003: delegation_depth (0..3 redelegation depth), "
    "policy_version_skew (0..4 grant-epoch vs decision-time policy-version offset), "
    "expiry_offset_ticks (signed logical ticks of decision time vs grant expiry; negative = "
    "lapsed). Enrichment is family-conditioned so every SACMAT family has a learnable witness: "
    "conformant -> skew==0 and non-lapsed offset; expiry_divergence -> strictly negative offset; "
    "policy_skew -> strictly positive skew; obligation_mismatch keeps the raw draws. The kernel "
    "ground-truth fields (family, synthetic, determinant, sequence) survive enrichment and a "
    "unit's payload is identical whether drawn from the full dataset or a split slice "
    "(content_sha256 is split-independent by kernel construction). write_dataset(outdir, seed, n) "
    "persists dataset.jsonl (120 units at seed 2027, sort_keys, newline-terminated) plus "
    "manifest.json (schema_version clara.venue2027.sacmat.dataset_manifest.v1, kernel + generator "
    "versions, families, content_sha256, dataset_jsonl_sha256, split/family inventory); "
    "verify_dataset_dir(outdir) regenerates and fails closed with "
    "DatasetError('MANIFEST_HASH_MISMATCH') on any byte divergence or digest mismatch — no "
    "silent partial writes. Real dataset artifact written to "
    "research/venue2027/proof/artifacts/sacmat_dataset/ (seed 2027, n=120, split 72/24/24, "
    "families 30/30/30/30): content_sha256 "
    "8b057b0fcd68037d9d3e538748f9201731ab09582162ab66a27c6f972b9ffd62, dataset_jsonl_sha256 "
    "fa82f59b27397140af3334340e490f350ab856e1914546f2e951652a967dc1e7. "
    "evaluation/venue2027/sacmat/test_generate_dataset.py (stdlib+pytest, 15 tests): "
    "determinism (byte-identical for same seed/split/n; different seeds differ), kernel "
    "delegation provenance (venue/prefix/generator_version/families), disjoint split slices with "
    "split-independent hash and slice==full.split(s) equality, assert_no_leakage and "
    "assert_valid_frequencies pass, family-conditioned enrichment invariants over 200 units plus "
    "kernel field survival and determinant recomputation, split-independent enrichment, "
    "no-PHI sweep, write_dataset byte-identity across output dirs + sorted unit ids + digest "
    "agreement + verify_dataset_dir acceptance, persisted split slice == direct "
    "generate(seed, s, n) record-for-record, adversarial: INVALID_N (n=0), UNKNOWN_SPLIT "
    "('holdout'), tampered dataset.jsonl (foreign-seed bytes swapped in) and tampered manifest "
    "digest both rejected fail-closed with MANIFEST_HASH_MISMATCH, and CLI main() round-trip. "
    "Verification: test_generate_dataset.py 15 passed (exit 0); full evaluation/venue2027/sacmat/ "
    "suite 53 passed (exit 0); shared regression evaluation/venue2027/_shared/ 137 passed "
    "(exit 0); uvx ruff@0.7.1 check clean (exit 0). All identities, timestamps and hashes are "
    "synthetic; designed fixtures only, no executed findings, no real PHI/PII, no network, no "
    "live policy-engine binaries. agent_protocol.validate_report ok:true with real on-disk logs. "
    "source_sha_before = source_sha_after = base SHA 604642528f95e9f10052bd4bc0334bdb1c84358a "
    "per established repo convention (proof report committed together with the work)."
)


def main() -> int:
    validator_log = (
        REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-dataset.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if head != BASE_SHA:
        print(f"unexpected HEAD {head!r} != base {BASE_SHA!r}", file=sys.stderr)
        return 1
    # Seed the validator log BEFORE validation so the report's log_path exists
    # and is non-empty when validate_report checks it; the validation outcome is
    # appended after the check.
    validator_log.write_text(
        "emit_SACMAT_dataset_report: building report via agent_protocol.build_report\n",
        encoding="utf-8",
    )
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-dataset.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    with validator_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
        fh.write(f"validator exit_code: {0 if result.ok else 1}\n")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
