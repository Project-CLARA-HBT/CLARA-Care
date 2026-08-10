"""Create a Phase-A implementation freeze only from clean local evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.run_local import seal_artifacts
from evaluation.commitloop.secret_scan import (
    contains_secret_material,
    scan_paths,
    tracked_paths,
)
from evaluation.commitloop.validate import validate_run

FREEZE_INPUTS = (
    "services/api/alembic/versions/20260810_0054_commitloop_commitments.py",
    "services/api/src/clara_api/glhs/commitments.py",
    "services/api/src/clara_api/glhs/commitment_gateway.py",
    "services/api/src/clara_api/glhs/commitment_thss.py",
    "services/api/src/clara_api/glhs/predicate_dsl.py",
    "services/api/src/clara_api/glhs/reconciliation.py",
    "evaluation/commitloop/schemas/prediction.schema.json",
    "evaluation/commitloop/prompts/solver_system.txt",
    "evaluation/commitloop/prompts/generation_candidate_system.txt",
    "evaluation/commitloop/prompts/generation_predicate_system.txt",
    "evaluation/commitloop/prompts/generation_note_system.txt",
    "evaluation/commitloop/prompts/review_system.txt",
    "protocols/commitloop/protocol.yaml",
    "protocols/commitloop/model_manifest.template.json",
    "protocols/commitloop/statistical_analysis_plan.json",
)
REQUIRED_VALIDATION_GATES = frozenset(
    {
        "targeted_tests",
        "migration_round_trip",
        "lint",
        "type_check",
        "property",
        "adversarial",
        "leakage",
        "secret_scan",
        "artifact_validation",
        "local_e2e_resume",
        "docs_naming",
    }
)


class FreezeError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _validate_local_evidence(
    evidence: dict[str, Any], *, expected_git_sha: str
) -> None:
    if evidence.get("schema_version") != "commitloop-phase-a-validation.v1":
        raise FreezeError("local_validation_schema_invalid")
    if evidence.get("validated_git_sha") != expected_git_sha:
        raise FreezeError("local_validation_git_sha_mismatch")
    commands = evidence.get("commands")
    if not isinstance(commands, list) or not commands:
        raise FreezeError("local_validation_commands_required")
    for item in commands:
        if not isinstance(item, dict):
            raise FreezeError("local_validation_not_complete")
        exit_code = item.get("exit_code")
        completed_at = item.get("completed_at_utc")
        try:
            parsed_at = (
                datetime.fromisoformat(completed_at)
                if isinstance(completed_at, str)
                else None
            )
        except ValueError as exc:
            raise FreezeError("local_validation_timestamp_invalid") from exc
        if (
            item.get("result") != "passed"
            or not isinstance(exit_code, int)
            or isinstance(exit_code, bool)
            or exit_code != 0
            or not isinstance(item.get("command"), str)
            or not item["command"].strip()
            or not isinstance(item.get("result_summary"), str)
            or not item["result_summary"].strip()
            or parsed_at is None
            or parsed_at.tzinfo is None
        ):
            raise FreezeError("local_validation_not_complete")
    gates = [item.get("gate") for item in commands]
    if len(gates) != len(set(gates)):
        raise FreezeError("local_validation_duplicate_gate")
    missing_gates = REQUIRED_VALIDATION_GATES - set(gates)
    if missing_gates:
        raise FreezeError(
            "local_validation_gates_missing:" + ",".join(sorted(missing_gates))
        )


def verify_live_repository_matches_freeze(payload: dict[str, Any], root: Path) -> None:
    """Fail closed if the code about to execute differs from the sealed freeze."""

    resolved_root = root.resolve()
    if _git(resolved_root, "status", "--porcelain"):
        raise FreezeError("phase_b_requires_clean_frozen_worktree")
    current_sha = _git(resolved_root, "rev-parse", "HEAD")
    if payload.get("git_sha") != current_sha:
        raise FreezeError("phase_b_git_sha_differs_from_freeze")
    frozen_hashes = payload.get("input_sha256")
    if not isinstance(frozen_hashes, dict) or set(frozen_hashes) != set(FREEZE_INPUTS):
        raise FreezeError("phase_b_freeze_input_inventory_invalid")
    for relative_path in FREEZE_INPUTS:
        path = resolved_root / relative_path
        if not path.is_file() or frozen_hashes.get(relative_path) != _sha256(path):
            raise FreezeError("phase_b_freeze_input_hash_mismatch:" + relative_path)


def create_implementation_freeze(
    *, run_dir: Path, repository_root: Path, validation_evidence: dict[str, Any]
) -> Path:
    root = repository_root.resolve()
    if _git(root, "status", "--porcelain"):
        raise FreezeError("implementation_freeze_requires_clean_worktree")
    if validation_evidence.get("router_calls_before_freeze") != 0:
        raise FreezeError("pre_freeze_router_calls_detected")
    git_sha = _git(root, "rev-parse", "HEAD")
    _validate_local_evidence(validation_evidence, expected_git_sha=git_sha)
    serialized_evidence = json.dumps(validation_evidence, sort_keys=True).encode(
        "utf-8"
    )
    if contains_secret_material(serialized_evidence):
        raise FreezeError("local_validation_evidence_contains_secret")
    validate_run(run_dir)
    run_manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    if run_manifest.get("run_status") != "COMPLETE":
        raise FreezeError("implementation_freeze_requires_complete_local_run")
    findings = scan_paths(tracked_paths(root))
    if findings:
        raise FreezeError("tracked_repository_secret_scan_failed")
    payload = {
        "schema_version": "commitloop-implementation-freeze.v1",
        "phase_a_status": "COMPLETE",
        "router_calls_before_freeze": 0,
        "git_sha": git_sha,
        "migration_head": "20260810_0054",
        "input_sha256": {name: _sha256(root / name) for name in FREEZE_INPUTS},
        "local_validation": validation_evidence,
        "run_manifest_sha256": _sha256(run_dir / "run_manifest.json"),
        "artifact_inventory_before_freeze_sha256": _sha256(
            run_dir / "checksums.sha256"
        ),
        "external_evaluation_status": "NOT_RUN",
        "clinical_adjudication": "NOT_RUN",
    }
    output = run_dir / "implementation_freeze.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    seal_artifacts(run_dir)
    validate_run(run_dir)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--validation-evidence", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    evidence = json.loads(args.validation_evidence.read_text(encoding="utf-8"))
    try:
        output = create_implementation_freeze(
            run_dir=args.run_dir,
            repository_root=args.repo_root,
            validation_evidence=evidence,
        )
    except (FreezeError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
