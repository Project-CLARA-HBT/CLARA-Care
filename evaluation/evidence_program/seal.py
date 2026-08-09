"""Seal a completed evidence-program artifact only after all headline inputs exist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, sha256, verify_freeze

HEADLINE_REQUIRED = (
    "environment.json",
    "cohort_manifest.json",
    "split_manifest.json",
    "domain_policy_manifest.json",
    "annotation_manifest.json",
    "adjudication_manifest.json",
    "oracle_manifest.json",
    "comparator_manifest.json",
    "model_manifest.json",
    "cases.csv",
    "per_run.csv",
    "system_outputs.csv",
    "human_labels.csv",
    "adjudicated_labels.csv",
    "domain_results.csv",
    "thss_utility.csv",
    "adversarial_results.csv",
    "human_review.csv",
    "fullstack_metrics.csv",
    "statistical_results.csv",
    "error_analysis.csv",
    "statistics_plan.json",
    "report.md",
)
FROZEN_BINDINGS = (
    "cohort_manifest.json",
    "split_manifest.json",
    "domain_policy_manifest.json",
    "annotation_manifest.json",
    "adjudication_manifest.json",
    "oracle_manifest.json",
    "comparator_manifest.json",
    "model_manifest.json",
    "statistics_plan.json",
)


def seal(run_dir: Path, freeze_path: Path) -> Path:
    """Write the final SHA inventory, or fail without producing a partial seal."""
    freeze = verify_freeze(freeze_path)
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FreezeError("run_directory_missing")
    missing = [name for name in HEADLINE_REQUIRED if not (run_dir / name).is_file()]
    if missing:
        raise FreezeError("headline_artifacts_missing:" + ",".join(missing))
    bindings = freeze.get("artifact_bindings")
    if not isinstance(bindings, dict):
        raise FreezeError("freeze_artifact_bindings_missing")
    for name in FROZEN_BINDINGS:
        expected = bindings.get(name)
        if not isinstance(expected, str):
            raise FreezeError("freeze_artifact_binding_missing:" + name)
        actual = sha256(run_dir / name)
        if actual != expected:
            raise FreezeError("frozen_artifact_hash_mismatch:" + name)
    files = {
        name: sha256(run_dir / name)
        for name in sorted(HEADLINE_REQUIRED)
    }
    seal_path = run_dir / "artifact-sha256.json"
    payload = {
        "schema_version": "evidence-program-artifact-seal-v1",
        "status": "sealed_headline_artifact",
        "freeze_manifest_sha256": sha256(freeze_path),
        "files": files,
    }
    seal_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return seal_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    try:
        seal_path = seal(args.run_dir, args.freeze)
    except FreezeError as exc:
        parser.error(str(exc))
    print(seal_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
