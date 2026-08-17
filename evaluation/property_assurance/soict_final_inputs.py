"""Generate the SOICT dual-model packet and the corresponding corpus-freeze input.

The generated freeze input is deliberately not executable until independent model
dispositions and the runner's installed Hypothesis version are recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

from evaluation.property_assurance.suite_matrix import METHOD_IDS, load_development_suite_matrix

_STUDY_ID = "assurance-soict-2026"
_MODELS = ["gemini-3.6-flash-high", "claude-sonnet-4-6"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _revision(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _hypothesis_version() -> str | None:
    try:
        return metadata.version("hypothesis")
    except metadata.PackageNotFoundError:
        return None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_soict_final_inputs(*, repository_root: Path, output_dir: Path) -> dict[str, Path]:
    """Write deterministic SOICT review and freeze inputs bound to current local bytes."""

    research_dir = repository_root / "research" / "assurance_soict"
    catalog_path = research_dir / "mutation_site_candidates.json"
    statistics_path = research_dir / "statistics_plan.json"
    matrix_path = research_dir / "development_suite_matrix.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    candidates = catalog.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("govmut_soict_catalog_invalid")
    matrix = load_development_suite_matrix(matrix_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "dual_model_review_manifest.json"
    freeze_path = output_dir / "corpus_freeze_input.json"
    cases: list[dict[str, object]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not all(
            isinstance(candidate.get(field), str) and candidate[field]
            for field in ("id", "family_seed", "source_path", "anchor", "replacement")
        ):
            raise ValueError("govmut_soict_catalog_invalid")
        cases.append(
            {
                "case_id": candidate["id"],
                "evidence": {
                    "E1": f"Fault family: {candidate['family_seed']}.",
                    "E2": f"One-change overlay in {candidate['source_path']}: replace `{candidate['anchor']}` with `{candidate['replacement']}`.",
                    "E3": "Classify only behavioral non-equivalence of this controlled overlay. Do not assess clinical correctness, severity, or production deployment.",
                },
            }
        )
    _write_json(
        review_path,
        {
            "schema_version": "clara-model-review-manifest.v1",
            "status": "frozen",
            "study_id": _STUDY_ID,
            "rubric": {
                "allowed_labels": ["NON_EQUIVALENT", "EQUIVALENT", "INVALID", "UNCERTAIN"],
                "task": "Determine whether the supplied one-change mutation can change observable governed-system behavior. This is a software-assurance non-equivalence review, not human review or clinical validation.",
                "decision_rule": "Return NON_EQUIVALENT only when the changed enforcement can produce an observable behavioral difference. Return EQUIVALENT for no observable difference, INVALID for a malformed/non-applicable overlay, and UNCERTAIN when the evidence is insufficient.",
                "final_disposition_rule": "Only mutual NON_EQUIVALENT maps to included. Mutual EQUIVALENT maps to excluded_equivalent. Mutual INVALID maps to excluded_unexecutable. All other outcomes, including disagreement after at most one anonymous reconciliation round, map to unresolved.",
                "model_ids": _MODELS,
            },
            "cases": cases,
        },
    )
    hypothesis_version = _hypothesis_version()
    methods = {
        method: {
            "targets": targets,
            "target_sha256": {
                target: _sha256(repository_root / target.partition("::")[0]) for target in targets
            },
        }
        for method, targets in matrix.items()
    }
    _write_json(
        freeze_path,
        {
            "schema_version": "govmut-final-freeze-input.v1",
            "status": "awaiting_dual_model_review_and_hypothesis_environment",
            "study_id": _STUDY_ID,
            "code_revision": _revision(repository_root),
            "catalog": "mutation_site_candidates.json",
            "catalog_sha256": _sha256(catalog_path),
            "statistics_plan": "statistics_plan.json",
            "statistics_plan_sha256": _sha256(statistics_path),
            "methods": {method: methods[method] for method in METHOD_IDS},
            "hypothesis": {"version": hypothesis_version, "ordered_seeds": None},
            "limits": {
                "pytest_timeout_seconds": None,
                "hypothesis_max_examples": None,
                "hypothesis_stateful_step_count": None,
            },
            "non_equivalence_review": {
                "model_ids": _MODELS,
                "manifest": review_path.name,
                "result_artifact": None,
                "results_sha256": None,
            },
            "promotion_rule": "After both model reviews and optional anonymous reconciliation are recorded, set every final disposition, freeze nonempty ordered seeds and positive limits, replace this input with govmut-final-freeze.v1 status frozen, and then invoke evaluation.property_assurance.soict_final_runner.",
        },
    )
    return {"review_manifest": review_path, "corpus_freeze_input": freeze_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = generate_soict_final_inputs(
        repository_root=args.repository_root, output_dir=args.output_dir
    )
    print(json.dumps({name: str(path) for name, path in outputs.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
