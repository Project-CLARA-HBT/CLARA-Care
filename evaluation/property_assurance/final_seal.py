"""Seal a completed GovMut SOICT result root with a reproducible evidence kit.

The seal validates the run first (fail-closed), inventories every pre-existing
file under the result root into ``artifact-sha256.json``, records the execution
environment (git source SHA, Hypothesis version, limits, Python) in
``environment.json``, derives a claim-to-evidence map into
``claim_to_evidence.csv``, and writes a human-readable ``README.md``.  The four
seal outputs reference each other's hashes, so they are excluded from the
inventory to avoid a self-referential hash cycle.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256 as _sha256
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_analyze import ANALYSIS_SCHEMA_VERSION
from evaluation.property_assurance.final_validate import validate_final_run
from evaluation.property_assurance.suite_matrix import METHOD_IDS

SEAL_INVENTORY_SCHEMA = "govmut-final-seal-artifact-inventory.v1"
SEAL_ENVIRONMENT_SCHEMA = "govmut-final-seal-environment.v1"
_SEAL_OUTPUTS = (
    "artifact-sha256.json",
    "environment.json",
    "README.md",
    "claim_to_evidence.csv",
)


def _source_revision(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FreezeError("govmut_final_seal_repository_revision_unavailable") from exc
    revision = completed.stdout.strip()
    if len(revision) != 40:
        raise FreezeError("govmut_final_seal_repository_revision_invalid")
    return revision


def _inventory(result_root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(result_root.rglob("*")):
        if not path.is_file() or path.name in _SEAL_OUTPUTS:
            continue
        relative = path.relative_to(result_root).as_posix()
        files[relative] = _sha256(path.read_bytes()).hexdigest()
    return files


def _load_analysis(result_root: Path, run_name: str) -> dict[str, Any] | None:
    analysis_path = result_root / run_name.replace("final_run", "final_analysis")
    if not analysis_path.is_file():
        return None
    try:
        value = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_final_seal_analysis_invalid_json") from exc
    if not isinstance(value, dict) or value.get("schema_version") != ANALYSIS_SCHEMA_VERSION:
        raise FreezeError("govmut_final_seal_analysis_schema_mismatch")
    return value


def _claims(analysis: dict[str, Any] | None) -> list[tuple[str, str, str, str]]:
    """Return (claim_id, claim, metric, value) rows derived from the analysis."""

    rows: list[tuple[str, str, str, str]] = []
    if analysis is None:
        return rows
    scores = analysis.get("mutation_scores")
    robustness = analysis.get("robustness_scores")
    if not isinstance(scores, dict) or not isinstance(robustness, dict):
        return rows
    for method in METHOD_IDS:
        entry = scores.get(method)
        if isinstance(entry, dict) and entry.get("score") is not None:
            rows.append(
                (
                    f"CLAIM-MUTSCORE-{method}",
                    f"Mutant-level mutation score for {method}",
                    "mutation_score",
                    f"{entry['score']:.4f}",
                )
            )
            rows.append(
                (
                    f"CLAIM-INFRA-{method}",
                    f"Infra-excluded mutants for {method}",
                    "excluded_infra_mutants",
                    str(entry.get("excluded_infra_mutants", 0)),
                )
            )
        robust = robustness.get(method)
        if isinstance(robust, dict) and robust.get("score") is not None:
            rows.append(
                (
                    f"CLAIM-ROBUST-{method}",
                    f"Robust (detected_all_seeds) score for {method}",
                    "robustness_score",
                    f"{robust['score']:.4f}",
                )
            )
    return rows


def seal_result_root(
    *,
    result_root: Path,
    repository_root: Path,
    run_name: str = "final_run.json",
) -> dict[str, Path]:
    """Seal a validated result root and return the four output paths."""

    result_root = result_root.resolve()
    repository_root = repository_root.resolve()
    if not result_root.is_dir():
        raise FreezeError("govmut_final_seal_result_root_missing")
    run_path = result_root / run_name
    if not run_path.is_file():
        raise FreezeError("govmut_final_seal_run_missing")
    run = validate_final_run(run_path)

    inventory = _inventory(result_root)
    analysis = _load_analysis(result_root, run_name)
    claims = _claims(analysis)
    source_sha = _source_revision(repository_root)
    sealed_at = datetime.now(UTC).isoformat()

    environment = {
        "schema_version": SEAL_ENVIRONMENT_SCHEMA,
        "status": "sealed",
        "sealed_at": sealed_at,
        "freeze_id": run.freeze_id,
        "source_sha": source_sha,
        "hypothesis_version": run.hypothesis_version,
        "limits": run.limits,
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "implementation": sys.implementation.name,
        },
    }
    inventory_payload = {
        "schema_version": SEAL_INVENTORY_SCHEMA,
        "status": "sealed",
        "sealed_at": sealed_at,
        "freeze_id": run.freeze_id,
        "run_sha256": run.raw.get("manifest_sha256"),
        "files": inventory,
        "total_files": len(inventory),
    }

    artifacts: dict[str, Path] = {}
    environment_path = result_root / "environment.json"
    environment_path.write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts["environment.json"] = environment_path

    inventory_path = result_root / "artifact-sha256.json"
    inventory_path.write_text(
        json.dumps(inventory_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts["artifact-sha256.json"] = inventory_path

    claims_path = result_root / "claim_to_evidence.csv"
    with claims_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "claim_id",
                "claim",
                "metric",
                "value",
                "evidence_artifact",
                "evidence_sha256",
            ]
        )
        evidence_files = [run_name]
        if analysis is not None:
            evidence_files.append(run_name.replace("final_run", "final_analysis"))
        for claim_id, claim, metric, value in claims:
            for evidence in evidence_files:
                writer.writerow(
                    [
                        claim_id,
                        claim,
                        metric,
                        value,
                        evidence,
                        _sha256((result_root / evidence).read_bytes()).hexdigest(),
                    ]
                )
        if not claims:
            writer.writerow(
                [
                    "CLAIM-NONE",
                    "No analysis artifact present; only the raw run is evidence",
                    "raw_run",
                    "present",
                    run_name,
                    _sha256(run_path.read_bytes()).hexdigest(),
                ]
            )
    artifacts["claim_to_evidence.csv"] = claims_path

    readme_lines = [
        "# Sealed GovMut SOICT result root",
        "",
        f"- Freeze: `{run.freeze_id}`",
        f"- Run schema: `{run.raw.get('schema_version')}`",
        f"- Source SHA: `{source_sha}`",
        f"- Hypothesis: `{run.hypothesis_version}`",
        f"- Limits: `{json.dumps(run.limits, sort_keys=True)}`",
        f"- Outcomes: `{json.dumps(run.outcome_counts, sort_keys=True)}`",
        f"- Sealed at: `{sealed_at}`",
        "",
        "## Artifacts",
        "",
        "| Path | SHA-256 |",
        "| --- | --- |",
    ]
    hashed_outputs = [name for name in _SEAL_OUTPUTS if name != "README.md"]
    for name in sorted([*inventory, *hashed_outputs]):
        digest = _sha256((result_root / name).read_bytes()).hexdigest()
        readme_lines.append(f"| `{name}` | `{digest}` |")
    readme_lines.extend(
        [
            "",
            "## Claims",
            "",
            "See `claim_to_evidence.csv` for claim-to-evidence mapping.",
            (
                "Aggregation follows the frozen rule in "
                "`research/assurance_soict/ANALYSIS_PLAN.md` (primary "
                "`detected_any_seed`; robustness `detected_all_seeds`; seeds are "
                "deterministic streams, not independent N)."
            ),
            "",
            "This work stream is not external clinical validation.",
        ]
    )
    readme_path = result_root / "README.md"
    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    artifacts["README.md"] = readme_path
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--run-name", default="final_run.json")
    args = parser.parse_args()
    try:
        artifacts = seal_result_root(
            result_root=args.result_root,
            repository_root=args.repository_root,
            run_name=args.run_name,
        )
    except FreezeError as exc:
        parser.error(str(exc))
    print(json.dumps({name: str(path) for name, path in artifacts.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
