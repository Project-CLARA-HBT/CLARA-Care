"""Run the SOICT M0--M3 final matrix from its fixed corpus-freeze paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_runner import execute_final_run


def run_soict_final(*, repository_root: Path, output_path: Path) -> dict[str, object]:
    """Delegate only the reviewed SOICT catalog, plan, and final freeze to M0--M3."""

    research_dir = repository_root / "research" / "assurance_soict"
    manifest_path = research_dir / "final_freeze.json"
    if not manifest_path.is_file():
        raise FreezeError("govmut_soict_final_freeze_not_promoted")
    return execute_final_run(
        manifest_path=manifest_path,
        repository_root=repository_root,
        catalog_path=research_dir / "mutation_site_candidates.json",
        statistics_plan_path=research_dir / "statistics_plan.json",
        output_path=output_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_soict_final(repository_root=args.repository_root, output_path=args.output)
    except (FreezeError, ValueError) as exc:
        parser.error(str(exc))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
