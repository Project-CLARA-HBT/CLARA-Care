"""Fail-closed secret scan for tracked CommitLoop code and sealed artifacts."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PATTERNS = (
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        rb"(?:ROUTER|OPENAI|ANTHROPIC)_API_KEY[ \t]*=[ \t]*"
        rb"(?!\[REDACTED\](?=$|[\s#\\\"']))[^\s#\\\"']+"
    ),
    re.compile(rb"Authorization\s*:\s*Bearer\s+[A-Za-z0-9_.-]{12,}", re.IGNORECASE),
)


def contains_secret_material(raw: bytes) -> bool:
    return any(pattern.search(raw) for pattern in PATTERNS)


def scan_paths(paths: list[Path]) -> list[str]:
    findings = []
    for path in paths:
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        if contains_secret_material(raw):
            findings.append(str(path))
    return sorted(findings)


def tracked_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode() for item in result.stdout.split(b"\0") if item]


def expand_paths(root: Path, values: list[str]) -> list[Path]:
    paths = []
    for value in values:
        path = (root / value).resolve()
        if root not in path.parents and path != root:
            raise ValueError("scan_path_outside_repo")
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(item for item in path.rglob("*") if item.is_file())
        else:
            raise ValueError("scan_path_missing")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--artifact-dir", type=Path, action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    paths = expand_paths(root, args.path) if args.path else tracked_paths(root)
    for artifact_dir in args.artifact_dir:
        if artifact_dir.is_dir():
            paths.extend(path for path in artifact_dir.rglob("*") if path.is_file())
    findings = scan_paths(paths)
    if findings:
        raise SystemExit("secret_scan_failed:" + ",".join(findings))
    print("secret_scan_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
