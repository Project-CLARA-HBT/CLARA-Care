"""Execute only the M0--M3 matrix bound by a reviewed GovMut final freeze.

This module deliberately has no candidate discovery or model-review path.  It
admits catalog entries only after ``validate_final_freeze`` has bound their
bytes, targets, limits, seeds, and reviewed dispositions.
"""

from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError, sha256
from evaluation.property_assurance.final_freeze import validate_final_freeze
from evaluation.property_assurance.mutation_runner import (
    execute_mutant,
    load_catalog_mutant,
)
from evaluation.property_assurance.suite_matrix import METHOD_IDS

_GENERATED_METHODS = frozenset({"M1_stateless_property", "M2_state_machine", "M3_combined"})


def _load_object(path: Path, error: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError(error) from exc
    if not isinstance(value, dict):
        raise FreezeError(error)
    return value


def _included_mutant_ids(
    *, manifest_path: Path, catalog_path: Path, manifest: dict[str, Any]
) -> list[str]:
    review = manifest["non_equivalence_review"]
    review_path = (manifest_path.parent / review["artifact"]).resolve()
    reviewed = _load_object(review_path, "govmut_final_runner_review_invalid")
    dispositions = reviewed.get("dispositions")
    catalog = _load_object(catalog_path, "govmut_final_runner_catalog_invalid")
    candidates = catalog.get("candidates")
    if not isinstance(dispositions, list) or not isinstance(candidates, list):
        raise FreezeError("govmut_final_runner_catalog_invalid")

    catalog_ids = [candidate.get("id") for candidate in candidates if isinstance(candidate, dict)]
    if len(catalog_ids) != len(candidates) or not all(
        isinstance(item, str) for item in catalog_ids
    ):
        raise FreezeError("govmut_final_runner_catalog_invalid")
    disposition_by_id = {
        item.get("mutant_id"): item.get("disposition")
        for item in dispositions
        if isinstance(item, dict)
    }
    # Preserve catalog order: the manifest/review decides eligibility, never this runner.
    return [
        mutant_id for mutant_id in catalog_ids if disposition_by_id.get(mutant_id) == "included"
    ]


def _hypothesis_version() -> str:
    try:
        return metadata.version("hypothesis")
    except metadata.PackageNotFoundError as exc:
        raise FreezeError("govmut_final_runner_hypothesis_unavailable") from exc


def execute_final_run(
    *,
    manifest_path: Path,
    repository_root: Path,
    catalog_path: Path,
    statistics_plan_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Run the frozen M0--M3 matrix and persist raw results at ``output_path``."""

    manifest = validate_final_freeze(
        manifest_path=manifest_path,
        repository_root=repository_root,
        catalog_path=catalog_path,
        statistics_plan_path=statistics_plan_path,
    )
    expected_version = manifest["hypothesis"]["version"]
    if _hypothesis_version() != expected_version:
        raise FreezeError("govmut_final_runner_hypothesis_version_mismatch")

    if output_path.exists():
        raise FreezeError("govmut_final_runner_output_already_exists")
    included_ids = _included_mutant_ids(
        manifest_path=manifest_path, catalog_path=catalog_path, manifest=manifest
    )
    if not included_ids:
        raise FreezeError("govmut_final_runner_no_included_mutants")

    limits = manifest["limits"]
    executions: list[dict[str, object]] = []
    for mutant_id in included_ids:
        mutant = load_catalog_mutant(catalog_path=catalog_path, mutant_id=mutant_id)
        for method in METHOD_IDS:
            seeds: list[int | None] = (
                list(manifest["hypothesis"]["ordered_seeds"])
                if method in _GENERATED_METHODS
                else [None]
            )
            for seed in seeds:
                result = execute_mutant(
                    repository_root=repository_root,
                    mutant=mutant,
                    pytest_targets=list(manifest["methods"][method]["targets"]),
                    hypothesis_seed=seed,
                    pytest_timeout_seconds=limits["pytest_timeout_seconds"],
                    retain_raw_output=True,
                )
                executions.append({"method": method, "hypothesis_seed": seed, "result": result})

    output = {
        "schema_version": "govmut-final-run.v1",
        "status": "COMPLETED_NOT_ANALYZED",
        "freeze_id": manifest["freeze_id"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "hypothesis_version": expected_version,
        "limits": limits,
        "included_mutant_ids": included_ids,
        "executions": executions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--statistics-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute_final_run(
            manifest_path=args.manifest,
            repository_root=args.repository_root,
            catalog_path=args.catalog,
            statistics_plan_path=args.statistics_plan,
            output_path=args.output,
        )
    except (FreezeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps({"status": result["status"], "freeze_id": result["freeze_id"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
