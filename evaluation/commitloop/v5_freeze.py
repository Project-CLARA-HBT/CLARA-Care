"""Create and verify the pre-provider Phase-B v5 confirmatory freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.run_local import seal_artifacts
from evaluation.commitloop.secret_scan import contains_secret_material
from evaluation.commitloop.v5_cohort import write_cohort
from evaluation.commitloop.v5_reproduce import verify_seal
from evaluation.commitloop.v5_validate import validate_v5_run

FREEZE_PREFIXES = (
    "evaluation/commitloop/",
    "evaluation/comparator_studies/",
    "services/api/src/clara_api/glhs/",
    "services/api/tests/test_commit",
    "services/api/tests/test_glhs",
    "protocols/commitloop/v5-confirmatory/",
)
FREEZE_EXPLICIT = frozenset(
    {
        ".github/workflows/ci.yml",
        "Makefile",
        "services/api/Dockerfile",
        "services/api/pyproject.toml",
        "services/api/uv.lock",
        "services/api/src/clara_api/db/models.py",
        "services/api/src/clara_api/api/v1/endpoints/commitments.py",
        "services/ml/Dockerfile",
        "services/ml/pyproject.toml",
        "services/ml/uv.lock",
        "apps/web/package-lock.json",
    }
)
REQUIRED_VALIDATION_GATES = frozenset(
    {
        "api_full_suite",
        "ml_full_suite",
        "commitloop_evaluator_suite",
        "glhs_targeted_suite",
        "migration_round_trip",
        "ruff_changed_files",
        "mypy_changed_files",
        "docs_check",
        "secret_scan",
        "local_assurance",
        "offline_v5_dry_run",
        "offline_reproduction",
    }
)


class V5FreezeError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def freeze_inputs(root: Path) -> tuple[str, ...]:
    tracked = _git(root, "ls-files").splitlines()
    selected = sorted(
        path
        for path in tracked
        if path in FREEZE_EXPLICIT or path.startswith(FREEZE_PREFIXES)
    )
    if not selected or any(not (root / path).is_file() for path in selected):
        raise V5FreezeError("v5_freeze_input_inventory_invalid")
    return tuple(selected)


def _validate_evidence(evidence: dict[str, Any], *, git_sha: str) -> None:
    if (
        evidence.get("schema_version") != "commitloop-v5-validation-evidence.v1"
        or evidence.get("validated_git_sha") != git_sha
        or evidence.get("provider_calls_before_freeze") != 0
    ):
        raise V5FreezeError("v5_validation_evidence_invalid")
    commands = evidence.get("commands")
    if not isinstance(commands, list):
        raise V5FreezeError("v5_validation_commands_missing")
    seen = set()
    for item in commands:
        if (
            not isinstance(item, dict)
            or item.get("result") != "passed"
            or item.get("exit_code") != 0
            or not isinstance(item.get("command"), str)
            or not item["command"].strip()
            or not isinstance(item.get("completed_at_utc"), str)
        ):
            raise V5FreezeError("v5_validation_command_invalid")
        try:
            completed = datetime.fromisoformat(item["completed_at_utc"])
        except ValueError as exc:
            raise V5FreezeError("v5_validation_timestamp_invalid") from exc
        if completed.tzinfo is None:
            raise V5FreezeError("v5_validation_timestamp_invalid")
        seen.add(str(item.get("gate")))
    missing = REQUIRED_VALIDATION_GATES - seen
    if missing:
        raise V5FreezeError("v5_validation_gates_missing:" + ",".join(sorted(missing)))


def _prior_registry(prior_runs: list[Path]) -> dict[str, Any]:
    if not prior_runs:
        raise V5FreezeError("prior_cohort_registry_required")
    tokens: set[str] = set()
    bundle_hashes: set[str] = set()
    sources = []
    for run in prior_runs:
        verify_seal(run)
        timeline = [
            json.loads(line)
            for line in (run / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        source = json.loads((run / "source_manifest.json").read_text(encoding="utf-8"))
        run_tokens = {str(item["subject_token"]) for item in timeline}
        run_hashes = {str(item) for item in source.get("bundle_payload_sha256", [])}
        tokens.update(run_tokens)
        bundle_hashes.update(run_hashes)
        sources.append(
            {
                "run_name": run.name,
                "sealed_checksum_sha256": _sha256(run / "checksums.sha256"),
                "subject_count": len(run_tokens),
                "bundle_count": len(run_hashes),
            }
        )
    return {
        "schema_version": "commitloop-prior-cohort-exclusions.v1",
        "sources": sources,
        "subject_tokens": sorted(tokens),
        "bundle_payload_sha256": sorted(bundle_hashes),
    }


def _environment(root: Path) -> dict[str, Any]:
    docker_lines = {
        name: (root / name).read_text(encoding="utf-8").splitlines()[0]
        for name in ("services/api/Dockerfile", "services/ml/Dockerfile")
    }
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "dependency_lock_sha256": {
            name: _sha256(root / name)
            for name in (
                "services/api/uv.lock",
                "services/ml/uv.lock",
                "apps/web/package-lock.json",
            )
        },
        "container_base_images": docker_lines,
        "locale": os.environ.get("LANG", ""),
        "timezone": os.environ.get("TZ", "system_default"),
    }


def create_v5_freeze(
    *,
    output_dir: Path,
    offline_run: Path,
    validation_evidence: dict[str, Any],
    prior_runs: list[Path],
    repository_root: Path,
) -> Path:
    root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise V5FreezeError("v5_freeze_output_must_not_exist")
    if _git(root, "status", "--porcelain"):
        raise V5FreezeError("v5_freeze_requires_clean_worktree")
    git_sha = _git(root, "rev-parse", "HEAD")
    _validate_evidence(validation_evidence, git_sha=git_sha)
    if contains_secret_material(json.dumps(validation_evidence).encode()):
        raise V5FreezeError("v5_validation_evidence_contains_secret")

    output_dir.mkdir(parents=True)
    cohort_dir = output_dir / "cohort"
    cohort_path, cohort_manifest_path = write_cohort(cohort_dir)
    cohort_rows = [
        json.loads(line)
        for line in cohort_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    registry = _prior_registry(prior_runs)
    prior_tokens = set(registry["subject_tokens"])
    prior_hashes = set(registry["bundle_payload_sha256"])
    token_overlap = prior_tokens & {str(item["subject_token"]) for item in cohort_rows}
    hash_overlap = prior_hashes & {str(item["bundle_sha256"]) for item in cohort_rows}
    if token_overlap or hash_overlap:
        raise V5FreezeError("v5_prior_cohort_overlap_detected")
    registry_path = output_dir / "prior_cohort_exclusion_registry.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    cohort_manifest = json.loads(cohort_manifest_path.read_text(encoding="utf-8"))
    cohort_manifest.update(
        {
            "status": "FROZEN_PRE_PROVIDER",
            "prior_cohort_overlap_check": "PASS",
            "prior_subject_token_overlap": 0,
            "prior_bundle_hash_overlap": 0,
            "prior_registry_sha256": _sha256(registry_path),
        }
    )
    cohort_manifest_path.write_text(
        json.dumps(cohort_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    dry_run_copy = output_dir / "offline_dry_run"
    shutil.copytree(offline_run, dry_run_copy)
    dry_validation = validate_v5_run(
        dry_run_copy,
        cohort_path=cohort_path,
        cohort_manifest_path=cohort_manifest_path,
    )
    protocol_copy = output_dir / "protocol"
    shutil.copytree(root / "protocols/commitloop/v5-confirmatory", protocol_copy)
    evidence_path = output_dir / "validation_evidence.json"
    evidence_path.write_text(
        json.dumps(validation_evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    environment_path = output_dir / "environment_manifest.json"
    environment_path.write_text(
        json.dumps(_environment(root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    inputs = freeze_inputs(root)
    freeze = {
        "schema_version": "commitloop-v5-freeze.v1",
        "status": "FROZEN_PRE_PROVIDER_APPROVAL_REQUIRED",
        "synthetic_software_evaluation_only": True,
        "clinical_adjudication": "NOT_RUN",
        "git_sha": git_sha,
        "provider_calls_before_freeze": 0,
        "provider_cost_approval": "NOT_GRANTED",
        "input_sha256": {path: _sha256(root / path) for path in inputs},
        "cohort_sha256": _sha256(cohort_path),
        "cohort_manifest_sha256": _sha256(cohort_manifest_path),
        "prior_registry_sha256": _sha256(registry_path),
        "offline_dry_run_checksum_sha256": _sha256(
            dry_run_copy / "checksums.sha256"
        ),
        "offline_dry_run_validation": dry_validation,
        "validation_evidence_sha256": _sha256(evidence_path),
        "environment_manifest_sha256": _sha256(environment_path),
        "protocol_sha256": {
            path.name: _sha256(path)
            for path in sorted(protocol_copy.iterdir())
            if path.is_file()
        },
        "execution_contract": {
            "primary_model": "antigravity/claude-sonnet-4-6",
            "primary_reference_condition": "glhs_hybrid_thss_strict",
            "primary_comparator_condition": "full_authorized_history",
            "subjects": 384,
            "conditions": 9,
            "expected_provider_calls": 3456,
            "retries": 0,
            "fallback": False,
            "post_unblinding_tuning": "PROHIBITED",
        },
    }
    freeze_path = output_dir / "freeze.json"
    freeze_path.write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for path in output_dir.rglob("*"):
        if path.is_file() and contains_secret_material(path.read_bytes()):
            raise V5FreezeError("v5_freeze_contains_secret:" + str(path.name))
    seal_artifacts(output_dir)
    verify_seal(output_dir)
    return freeze_path


def verify_live_repository_matches_v5_freeze(
    freeze_path: Path, repository_root: Path
) -> dict[str, Any]:
    freeze_path = freeze_path.resolve()
    root = repository_root.resolve()
    verify_seal(freeze_path.parent)
    payload = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "commitloop-v5-freeze.v1"
        or payload.get("status") != "FROZEN_PRE_PROVIDER_APPROVAL_REQUIRED"
        or payload.get("provider_calls_before_freeze") != 0
        or payload.get("provider_cost_approval") != "NOT_GRANTED"
    ):
        raise V5FreezeError("v5_freeze_contract_invalid")
    if _git(root, "status", "--porcelain"):
        raise V5FreezeError("v5_execution_requires_clean_worktree")
    if _git(root, "rev-parse", "HEAD") != payload.get("git_sha"):
        raise V5FreezeError("v5_live_git_sha_mismatch")
    inputs = freeze_inputs(root)
    hashes = payload.get("input_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(inputs):
        raise V5FreezeError("v5_freeze_input_inventory_mismatch")
    for relative in inputs:
        if hashes.get(relative) != _sha256(root / relative):
            raise V5FreezeError("v5_freeze_input_hash_mismatch:" + relative)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline-run", type=Path, required=True)
    parser.add_argument("--validation-evidence", type=Path, required=True)
    parser.add_argument("--prior-run", type=Path, action="append", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    evidence = json.loads(args.validation_evidence.read_text(encoding="utf-8"))
    try:
        freeze_path = create_v5_freeze(
            output_dir=args.output,
            offline_run=args.offline_run,
            validation_evidence=evidence,
            prior_runs=args.prior_run,
            repository_root=args.repo_root,
        )
    except (V5FreezeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(freeze_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
