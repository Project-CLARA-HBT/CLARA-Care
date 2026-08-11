"""Create a zero-call statistical correction bound to a sealed run artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.statistics import (
    paired_condition_statistics,
    per_case_rows_with_subject,
)
from evaluation.commitloop.validate import validate_run


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        item
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
        for item in [json.loads(line)]
        if isinstance(item, dict)
    ]


def _git_sha(repository_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def create_statistical_correction(
    *, run_dir: Path, output: Path, repository_root: Path = Path(".")
) -> dict[str, Any]:
    """Recompute paired statistics without changing sealed predictions or gold."""

    validate_run(run_dir)
    outputs_raw = json.loads(
        (run_dir / "solver_outputs.json").read_text(encoding="utf-8")
    )
    if not isinstance(outputs_raw, list):
        raise TypeError("invalid_solver_outputs")
    outputs = [item for item in outputs_raw if isinstance(item, dict)]
    gold = {
        item["case_id"]: item for item in _jsonl(run_dir / "construction_gold.jsonl")
    }
    subjects = {
        item["case_id"]: item["subject_token"]
        for item in _jsonl(run_dir / "commitments.jsonl")
    }
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("invalid_run_manifest")
    models = manifest.get("models")
    conditions = manifest.get("conditions")
    if not isinstance(models, list) or not all(
        isinstance(item, str) for item in models
    ):
        raise TypeError("invalid_run_models")
    if not isinstance(conditions, list) or not all(
        isinstance(item, str) for item in conditions
    ):
        raise TypeError("invalid_run_conditions")
    corrected = paired_condition_statistics(
        per_case_rows_with_subject(
            outputs=outputs,
            gold_by_case=gold,
            subject_by_case=subjects,
            models=models,
            conditions=conditions,
        )
    )
    source_seal = run_dir / "checksums.sha256"
    payload = {
        "schema_version": "commitloop-statistical-correction.v1",
        "analysis_git_sha": _git_sha(repository_root),
        "source_run_checksums_sha256": hashlib.sha256(
            source_seal.read_bytes()
        ).hexdigest(),
        "source_prediction_count": len(outputs),
        "source_expected_prediction_count": (
            len(subjects) * len(models) * len(conditions)
        ),
        "external_calls": 0,
        "correction_reason": (
            "v1 paired statistics overwrote repeated subject-condition rows instead "
            "of reducing cases to subject-cluster means and did not use the frozen "
            "primary reference condition"
        ),
        "recorded_at": datetime.now(UTC).isoformat(),
        "corrected_statistics": corrected,
        "clinical_adjudication": "NOT_RUN",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = create_statistical_correction(
        run_dir=args.run_dir,
        output=args.output,
        repository_root=args.repo_root,
    )
    print(
        json.dumps(
            {
                "status": "corrected_statistics_complete",
                "external_calls": result["external_calls"],
                "predictions": result["source_prediction_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
