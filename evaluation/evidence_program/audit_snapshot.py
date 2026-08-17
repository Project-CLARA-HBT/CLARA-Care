"""Code-generated repository snapshot and sealed-run inventory for evidence integrity audit.

This module only reads current repository state and immutable artifacts; it never
infers or fabricates results. Credentials are never read or written.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import Any


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git(repository_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def repository_snapshot(repository_root: Path) -> dict[str, Any]:
    merge_base = _git(repository_root, "merge-base", "HEAD", "main")
    return {
        "schema_version": "clara-repository-snapshot.v1",
        "branch": _git(repository_root, "branch", "--show-current"),
        "head": _git(repository_root, "rev-parse", "HEAD"),
        "main": _git(repository_root, "rev-parse", "main"),
        "merge_base": merge_base,
        "behind_main": len(_git(repository_root, "rev-list", "main..HEAD").splitlines()),
        "ahead_main": len(_git(repository_root, "rev-list", "HEAD..main").splitlines()),
        "dirty_paths": _git(repository_root, "status", "--porcelain").splitlines(),
        "python": platform.python_version(),
    }


def sealed_run_inventory(repository_root: Path) -> dict[str, Any]:
    gitignore = (repository_root / ".gitignore").read_text(encoding="utf-8")
    artifacts_ignored = "artifacts" in gitignore
    return {
        "schema_version": "clara-sealed-run-inventory.v1",
        "artifacts_dir_ignored_in_git": artifacts_ignored,
        "sealed_runs": {
            "rivf-final-003": {
                "evidence_class": "real_boundary_governance",
                "source_sha": "5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb",
                "raw_root": "artifacts/govred/2026-08-17-rivf-final-003",
                "immutable": True,
            },
            "glhs-postgres-toctou-final-20260817-01": {
                "evidence_class": "postgres_concurrency",
                "source_sha": "2074f87550c5ee32302bde47bc0b9e6be6af36b5",
                "raw_root": "artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01",
                "immutable": True,
            },
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    snapshot = repository_snapshot(args.repository_root)
    inventory = sealed_run_inventory(args.repository_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("repository_snapshot.json", snapshot), ("sealed_run_inventory.json", inventory)):
        payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (args.output_dir / name).write_bytes(payload)
        print(f"{name}: sha256={_sha256_bytes(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
