"""Emit the IFIP_SEC-dataset task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "604642528f95e9f10052bd4bc0334bdb1c84358a"

CHANGED = [
    "evaluation/venue2027/ifip_sec/generate_dataset.py",
    "evaluation/venue2027/ifip_sec/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/ifip_sec_dataset/manifest.json",
    "research/venue2027/proof/artifacts/ifip_sec_dataset/inventory.json",
    "research/venue2027/proof/artifacts/ifip_sec_dataset/records.jsonl",
    "research/venue2027/proof/logs/IFIP_SEC-dataset.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-dataset.ruff.log",
    "research/venue2027/proof/logs/IFIP_SEC-dataset.artifact.log",
    "research/venue2027/proof/IFIP_SEC-dataset.json",
]


def main() -> int:
    report = ap.build_report(
        task_id="IFIP_SEC-dataset",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "evaluation/venue2027/ifip_sec/test_generate_dataset.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-dataset.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/ --config ruff.toml",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-dataset.ruff.log",
            },
            {
                "argv": (
                    "python3 -m evaluation.venue2027.ifip_sec.generate_dataset "
                    "--outdir research/venue2027/proof/artifacts/ifip_sec_dataset "
                    "--seed 2027 --n 120"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-dataset.artifact.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/ifip_sec/generate_dataset.py",
            "evaluation/venue2027/ifip_sec/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/ifip_sec_dataset/manifest.json",
            "research/venue2027/proof/artifacts/ifip_sec_dataset/inventory.json",
            "research/venue2027/proof/artifacts/ifip_sec_dataset/records.jsonl",
            "research/venue2027/proof/logs/IFIP_SEC-dataset.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-dataset.ruff.log",
            "research/venue2027/proof/logs/IFIP_SEC-dataset.artifact.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 synthetic dataset and split builder: generate(seed, split, n) -> Dataset "
            "delegates all record construction to the audited shared kernel "
            "evaluation/venue2027/_shared/dataset_kernel.generate('ifip_sec', ...) (kernel "
            "version 1.0.0 pinned; venue families fresh_accept / cross_purpose_replay / "
            "delegation_replay / lineage_splice; unit prefix req) and layers the IFIP-specific "
            "authorization payload deterministically: purpose vs granted_purpose (cross-purpose "
            "replay signal), delegation_depth, consent_epoch vs parent_consent_epoch (lineage-"
            "splice signal), replay_flag, and nonce_state in {fresh, consumed, "
            "consumed_by_delegate} (consume-once state). Content hash is split-independent and "
            "byte-identical for repeated (seed, n): dataset content_sha256 "
            "2d0ee6208972bee35b2a0953e1f7520eed49af94bb711ce0fb57395e3fa8ad14, records_sha256 "
            "438894047162669bcbff3c15b0648ed28f6cfbc8bea306962e5637171f45843f (seed 2027, n=120; "
            "train 72 / dev 24 / test 24; 30 records per family; synthetic_only=true, "
            "phi_fields=[]). write_dataset(outdir, seed, n) runs the fail-closed validators "
            "(assert_valid_frequencies, assert_no_leakage via per-split regeneration) BEFORE any "
            "file is written, then persists records.jsonl / inventory.json / manifest.json; a "
            "validation failure leaves the output directory absent (crash-clean). Real dataset "
            "artifact committed at research/venue2027/proof/artifacts/ifip_sec_dataset/. 20 "
            "tests (9 positive incl. determinism, split-independence, family ground-truth "
            "encoding, write determinism; 11 adversarial incl. UNKNOWN_SPLIT, INVALID_N, "
            "UNKNOWN_FAMILY, PHI_FIELD_PRESENT, INVALID_FAMILY_FREQUENCY, SPLIT_LEAKAGE, "
            "no-leakage between named splits, fail-clean write) pass; uvx ruff@0.7.1 clean. "
            "source_sha_after = base commit 60464252 per sibling convention (ACNS-X01/ACNS-"
            "scope); the single task commit is created immediately after this report and "
            "recorded in the commit body."
        ),
    )

    # Proof file lives at research/venue2027/proof/IFIP_SEC-dataset.json.
    out_path = REPO / "research/venue2027/proof/IFIP_SEC-dataset.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="IFIP_SEC-dataset",
        completed_tasks=["IFIP_SEC-schema", "SH-schedule_engine"],
        task_dependencies=["IFIP_SEC-schema", "SH-schedule_engine"],
    )
    log_path = REPO / "research/venue2027/proof/logs/IFIP_SEC-dataset.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
