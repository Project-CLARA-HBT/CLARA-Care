"""Emit the ACNS-dataset proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-dataset task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-dataset"
BASE_SHA = "604642528f95e9f10052bd4bc0334bdb1c84358a"

CHANGED = [
    "evaluation/venue2027/acns/generate_dataset.py",
    "evaluation/venue2027/acns/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/acns_dataset/records.jsonl",
    "research/venue2027/proof/artifacts/acns_dataset/records.csv",
    "research/venue2027/proof/artifacts/acns_dataset/inventory.json",
    "research/venue2027/proof/artifacts/acns_dataset/manifest.json",
    "research/venue2027/proof/ACNS-dataset.json",
    "research/venue2027/proof/logs/ACNS-dataset.pytest.log",
    "research/venue2027/proof/logs/ACNS-dataset.ruff.log",
    "research/venue2027/proof/logs/ACNS-dataset.suite.log",
    "research/venue2027/proof/logs/ACNS-dataset.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_generate_dataset.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-dataset.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-dataset.ruff.log",
    },
    {
        "argv": (
            "python3 -m pytest -q evaluation/venue2027/_shared/ evaluation/venue2027/acns/ "
            "research/venue2027/_shared/tests/ research/venue2027/acns/tests/"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-dataset.suite.log",
    },
]


def main() -> int:
    manifest = json.loads(
        (REPO / "research/venue2027/proof/artifacts/acns_dataset/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:6],  # module, tests, dataset bundle (report/log files excluded)
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P02 synthetic dataset and split builder for ACNS (SoK: Evidence Boundaries of "
            "Attestation in Tool-Using AI Systems). "
            "evaluation/venue2027/acns/generate_dataset.py implements the manifest signature "
            "generate(seed:int, split:str, n:int) -> Dataset plus write_dataset(outdir, seed, n) "
            "by delegating record construction, family assignment, split-by-independent-unit "
            "and PHI-field rejection to the audited shared kernel "
            "evaluation.venue2027._shared.dataset_kernel (v1.0.0, commit 60464252); this module "
            "adds only the ACNS evidence-claim payload and the artifact writer. "
            "ACNS payload (deterministic pure arithmetic on (seed, idx), no clock/randomness/"
            "network/provider, re-checked against the kernel PHI-field rule): "
            "claimed_attestation_level on the evidence-to-claim lattice L0-ASSUMED..L4-COMMITTED "
            "(threat model §1.2; dispatch-dimension claims are capped at L1-ASSEMBLED), "
            "receipt_binding_present (True only for bound_evidence/attestation_downgrade), "
            "evidence_gap_code from the pre-registered register G1-G9 (threat model §6: NONE, "
            "G2_RECEIPT_AS_EXECUTION for attestation_downgrade, "
            "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE for unbound_claim, G4_SIGNATURE_AS_CONTEXT for "
            "replayed_receipt) and source_type in {provider_receipt, transport_ack, "
            "attested_execution, timestamp_only, undisclosed} — gap semantics pinned to the "
            "ACNS-baselines fixture register (_smoke_fixtures.py) so oracle and baselines agree "
            "on labels. Split filter accepts train|dev|test|all; inventory and content_sha256 "
            "are computed on the full buffered record set so they are split-independent. "
            "Real dataset artifact written: research/venue2027/proof/artifacts/acns_dataset/ "
            f"(seed=2027, n=200, content_sha256={manifest['content_sha256']}; records.jsonl/"
            "records.csv/inventory.json/manifest.json with per-file SHA256 bindings; unit ids "
            "evd-2027-NNNNN). Tests: 15 passed (positive: same-seed hash identity, seed "
            "sensitivity, split-filter hash independence, unit-disjoint splits, all 4 kernel "
            "families represented with the exact expected payload binding, inventory counts, "
            "PHI-free keys, fixture-register alignment, write_dataset bundle reproducibility "
            "byte-identical across runs; adversarial: unknown split UNKNOWN_SPLIT fail-closed, "
            "n=0 INVALID_N, same-unit split leakage SPLIT_LEAKAGE, degenerate family frequency "
            "INVALID_FAMILY_FREQUENCY, manifest overwrite OVERWRITE_REFUSED, manifest SHA "
            "tampering detection). Shared foundations + venue2027 suites regression: 518 "
            "passed. uvx ruff@0.7.1 check clean on evaluation/venue2027/acns/. "
            "source_sha_after = base SHA per established repo convention (proof report "
            "committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-dataset.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    with (REPO / "research/venue2027/proof/logs/ACNS-dataset.validator.log").open(
        "w", encoding="utf-8"
    ) as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
