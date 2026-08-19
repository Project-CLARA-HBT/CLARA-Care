"""Run the W9 GovMut follow-up M0--M3 matrix from its w9 corpus-freeze paths.

Mirrors ``soict_final_runner`` exactly in behavior (delegates to
``final_runner.execute_final_run`` after requiring the promoted W9 freeze) but
binds the *W9* catalog, statistics plan, and promoted W9 freeze. The sealed W8
paths (``final_freeze.json``, ``mutation_site_candidates.json``, ``final_run.json``,
``results/final-analysis.json``, ``seal/*``) are never read or written here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_runner import execute_final_run
from evaluation.property_assurance.w9_human_review import validate_human_review_gate


def run_w9_final(*, repository_root: Path, output_path: Path) -> dict[str, object]:
    """Delegate only the reviewed W9 catalog, plan, and W9 freeze to M0--M3."""

    research_dir = repository_root / "research" / "assurance_soict"
    manifest_path = research_dir / "w9_final_freeze.json"
    if not manifest_path.is_file():
        raise FreezeError("govmut_w9_final_freeze_not_promoted")
    validate_human_review_gate(
        manifest_path=manifest_path, catalog_path=research_dir / "w9_catalog.json"
    )
    return execute_final_run(
        manifest_path=manifest_path,
        repository_root=repository_root,
        catalog_path=research_dir / "w9_catalog.json",
        statistics_plan_path=research_dir / "statistics_plan.json",
        output_path=output_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_w9_final(repository_root=args.repository_root, output_path=args.output)
    except (FreezeError, ValueError) as exc:
        parser.error(str(exc))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
