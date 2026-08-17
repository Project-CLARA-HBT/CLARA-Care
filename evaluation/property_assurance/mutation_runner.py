"""Fresh-process execution for one anchored GovMut overlay."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from hashlib import sha256
from pathlib import Path

from evaluation.property_assurance.mutation_overlay import MutantOverlay, apply_overlay
from evaluation.property_assurance.suite_matrix import (
    METHOD_IDS,
    load_development_suite_matrix,
)


def repository_revision(repository_root: Path) -> str:
    """Return the Git revision or an explicit unavailable marker for test fixtures."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and len(revision) == 40 else "UNAVAILABLE"


def target_file_hashes(*, repository_root: Path, pytest_targets: list[str]) -> dict[str, str]:
    """Require immutable file targets and record their exact pre-run bytes."""

    hashes: dict[str, str] = {}
    for target in pytest_targets:
        relative_path = target.partition("::")[0]
        path = repository_root / relative_path
        if not path.is_file():
            raise ValueError("govmut_pytest_target_must_be_existing_file")
        hashes[target] = sha256(path.read_bytes()).hexdigest()
    return hashes


def absolute_pytest_targets(*, repository_root: Path, pytest_targets: list[str]) -> list[str]:
    """Keep test discovery in the staged cwd while preserving node selectors."""

    absolute: list[str] = []
    for target in pytest_targets:
        relative_path, separator, selector = target.partition("::")
        path = repository_root / relative_path
        absolute.append(f"{path}::{selector}" if separator else str(path))
    return absolute


def execute_mutant(
    *,
    repository_root: Path,
    mutant: MutantOverlay,
    pytest_targets: list[str],
    hypothesis_seed: int | None = None,
    pytest_timeout_seconds: int = 120,
    retain_raw_output: bool = False,
) -> dict[str, object]:
    """Run one mutant in a copied API source tree without touching production code."""

    root = repository_root.resolve()
    if not pytest_targets:
        raise ValueError("govmut_pytest_targets_required")
    if not isinstance(pytest_timeout_seconds, int) or pytest_timeout_seconds <= 0:
        raise ValueError("govmut_pytest_timeout_invalid")
    target_hashes = target_file_hashes(repository_root=root, pytest_targets=pytest_targets)
    provenance: dict[str, object] = {
        "repository_revision": repository_revision(root),
        "pytest_targets": pytest_targets,
        "pytest_target_sha256": target_hashes,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "hypothesis_seed": hypothesis_seed,
    }
    with tempfile.TemporaryDirectory(prefix="govmut-overlay-") as temporary:
        stage = Path(temporary) / "stage"
        source_root = root / "services/api/src"
        staged_source = stage / "services/api/src"
        shutil.copytree(source_root, staged_source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(
            root / "services/api/tests",
            stage / "services/api/tests",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            root / "evaluation",
            stage / "evaluation",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        overlay_root = Path(temporary) / "overlay"
        applied = apply_overlay(repository_root=root, overlay_root=overlay_root, mutant=mutant)
        replacement = overlay_root / applied.source_path
        destination = stage / applied.source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(replacement, destination)
        environment = {
            **os.environ,
            "PYTHONPATH": f"{staged_source}{os.pathsep}{stage}",
        }
        staged_targets = absolute_pytest_targets(
            repository_root=stage, pytest_targets=pytest_targets
        )
        import_probe = subprocess.run(
            [sys.executable, "-c", "import clara_api; print(clara_api.__file__)"],
            cwd=stage,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        imported_path = Path(import_probe.stdout.strip())
        if import_probe.returncode != 0 or not imported_path.is_file():
            raise RuntimeError("govmut_staged_import_probe_failed")
        try:
            imported_path.resolve().relative_to(staged_source.resolve())
        except ValueError as exc:
            raise RuntimeError("govmut_staged_import_probe_failed") from exc
        provenance["staged_import_path"] = str(imported_path)
        started = time.perf_counter()
        try:
            pytest_command = [sys.executable, "-m", "pytest", "-q"]
            if hypothesis_seed is not None:
                pytest_command.extend(["--hypothesis-seed", str(hypothesis_seed)])
            completed = subprocess.run(
                [*pytest_command, *staged_targets],
                cwd=stage,
                env=environment,
                capture_output=True,
                text=True,
                timeout=pytest_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            result: dict[str, object] = {
                **provenance,
                "mutant_id": mutant.mutant_id,
                "classification": "INFRASTRUCTURE_ERROR_NOT_KILLED",
                "returncode": None,
                "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
                "original_sha256": applied.original_sha256,
                "mutated_sha256": applied.mutated_sha256,
                "stdout_sha256": sha256(stdout.encode()).hexdigest(),
                "stderr_sha256": sha256(stderr.encode()).hexdigest(),
                "error": "govmut_pytest_timeout",
            }
            if retain_raw_output:
                result.update({"stdout": stdout, "stderr": stderr})
            return result
        output = (completed.stdout + completed.stderr).lower()
        if completed.returncode == 0:
            classification = "SURVIVED"
        elif "error during collection" in output:
            classification = "INFRASTRUCTURE_ERROR_NOT_KILLED"
        elif " failed" in output:
            classification = "KILLED_TEST_ASSERTION"
        else:
            classification = "INFRASTRUCTURE_ERROR_NOT_KILLED"
        result = {
            **provenance,
            "mutant_id": mutant.mutant_id,
            "classification": classification,
            "returncode": completed.returncode,
            "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
            "original_sha256": applied.original_sha256,
            "mutated_sha256": applied.mutated_sha256,
            "stdout_sha256": sha256(completed.stdout.encode()).hexdigest(),
            "stderr_sha256": sha256(completed.stderr.encode()).hexdigest(),
        }
        if retain_raw_output:
            result.update({"stdout": completed.stdout, "stderr": completed.stderr})
        return result


def load_catalog_mutant(*, catalog_path: Path, mutant_id: str) -> MutantOverlay:
    """Load one catalogued mutant without accepting arbitrary source mutations."""

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    candidates = catalog.get("candidates")
    if not isinstance(candidates, list):
        raise TypeError("govmut_catalog_candidates_invalid")
    matches = [item for item in candidates if isinstance(item, dict) and item.get("id") == mutant_id]
    if len(matches) != 1:
        raise ValueError("govmut_catalog_mutant_not_unique")
    match = matches[0]
    fields = ("id", "source_path", "anchor", "replacement")
    if not all(isinstance(match.get(field), str) and match[field] for field in fields):
        raise ValueError("govmut_catalog_mutant_invalid")
    return MutantOverlay(
        mutant_id=match["id"],
        source_path=match["source_path"],
        anchor=match["anchor"],
        replacement=match["replacement"],
    )


def suite_targets(*, matrix_path: Path, method: str) -> list[str]:
    """Resolve a complete named development suite through its checked matrix."""

    if method not in METHOD_IDS:
        raise ValueError("govmut_suite_method_invalid")
    return load_development_suite_matrix(matrix_path)[method]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute one catalogued GovMut overlay.")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--mutant", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", action="append")
    parser.add_argument("--suite-matrix", type=Path)
    parser.add_argument("--method", choices=METHOD_IDS)
    parser.add_argument("--hypothesis-seed", type=int)
    args = parser.parse_args()
    if args.target and (args.suite_matrix or args.method):
        parser.error("govmut_targets_and_matrix_are_mutually_exclusive")
    if bool(args.suite_matrix) != bool(args.method):
        parser.error("govmut_suite_matrix_and_method_required_together")
    if args.suite_matrix:
        pytest_targets = suite_targets(matrix_path=args.suite_matrix, method=args.method)
        if args.method in {"M1_stateless_property", "M2_state_machine", "M3_combined"} and args.hypothesis_seed is None:
            parser.error("govmut_hypothesis_seed_required_for_generated_method")
    elif args.target:
        pytest_targets = args.target
    else:
        parser.error("govmut_pytest_target_or_suite_matrix_required")
    result = execute_mutant(
        repository_root=Path("."),
        mutant=load_catalog_mutant(catalog_path=args.catalog, mutant_id=args.mutant),
        pytest_targets=pytest_targets,
        hypothesis_seed=args.hypothesis_seed,
        retain_raw_output=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = args.output.with_suffix(".stdout.txt")
    stderr_path = args.output.with_suffix(".stderr.txt")
    stdout = result.pop("stdout")
    stderr = result.pop("stderr")
    assert isinstance(stdout, str) and isinstance(stderr, str)
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    result.update(
        {
            "catalog_sha256": sha256(args.catalog.read_bytes()).hexdigest(),
            "raw_output_retained": True,
            "stdout_artifact": str(stdout_path),
            "stderr_artifact": str(stderr_path),
        }
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
