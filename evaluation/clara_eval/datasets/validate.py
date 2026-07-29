"""CLI entry point for CLARA-Eval VN dataset manifest validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .manifest import ManifestValidationError, validate_dataset_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a CLARA-Eval VN dataset manifest"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evaluation/clara_eval/datasets/manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        manifest = validate_dataset_manifest(
            args.manifest, repository_root=args.repository_root
        )
    except ManifestValidationError as exc:
        print(
            json.dumps({"valid": False, "reason": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "suite_id": manifest.suite_id,
                "suite_version": manifest.suite_version,
                "datasets": len(manifest.datasets),
                "tracks": sorted(entry.track_id for entry in manifest.datasets),
                "measurements": "metadata_only_no_metric_values",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
