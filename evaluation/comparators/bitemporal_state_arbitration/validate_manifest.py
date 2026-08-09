from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED = frozenset({
    "version", "status", "source_reference", "direct_empirical_comparison_allowed",
    "paper_to_code_mapping", "implementation_module", "unit_test_module",
    "unspecified_choices_recorded", "excluded_glhs_features",
})


def validate(path: Path, *, repository_root: Path | None = None) -> None:
    manifest = load_frozen_json(path)
    missing = REQUIRED.difference(manifest)
    if missing:
        raise FreezeError("comparator_manifest_fields_missing:" + ",".join(sorted(missing)))
    if manifest["status"] not in {"mechanism_only_not_faithful", "faithful_source_reviewed"}:
        raise FreezeError("comparator_status_invalid")
    if manifest["status"] == "mechanism_only_not_faithful" and manifest["direct_empirical_comparison_allowed"] is not False:
        raise FreezeError("mechanism_only_comparator_cannot_release_direct_claim")
    if manifest["unspecified_choices_recorded"] is not True:
        raise FreezeError("comparator_unspecified_choices_unrecorded")
    if repository_root is not None:
        for key in ("paper_to_code_mapping", "implementation_module", "unit_test_module"):
            candidate = repository_root / str(manifest[key])
            if not candidate.is_file():
                raise FreezeError("comparator_artifact_missing:" + key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path)
    args = parser.parse_args()
    try:
        validate(args.manifest, repository_root=args.repository_root)
    except FreezeError as exc:
        parser.error(str(exc))
