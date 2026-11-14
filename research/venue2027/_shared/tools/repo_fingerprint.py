"""CLARA-Care 2027 shared task SH-repo_fingerprint.

Purpose
-------
Create a reproducible, read-only inventory of the code snapshot used by every
2027 venue study. The fingerprint binds every downstream research artifact to an
exact commit, working-tree cleanliness state, toolchain, SQL dialect and a
SHA256 digest of all tracked source files.

Allowed input
-------------
A path to a git repository checkout. The function never clones, fetches, resets
or mutates the repository. All git access is through read-only plumbing
(``rev-parse``, ``status --porcelain``, ``ls-files``, ``ls-files -s``).

Failure semantics
-----------------
Every failure is reported with a stable ``reason_code`` and the function returns
a frozen :class:`Fingerprint` with ``ok=False``. It never raises for expected
environmental conditions (dirty tree, not-a-git-repository, missing HEAD). The
caller must treat ``ok=False`` as a hard stop, not as a safe/clean result.

Version
-------
``REPO_FINGERPRINT_SCHEMA_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

REPO_FINGERPRINT_SCHEMA_VERSION = "1.0.0"

ReasonCode = Literal[
    "OK",
    "NOT_A_GIT_REPO",
    "NO_HEAD",
    "DIRTY_WORKTREE",
    "MISSING_REQUIRED_FILE",
    "GIT_UNAVAILABLE",
]

# Files whose presence / absence is part of the program contract. These are the
# verified anchors from MANIFESTS/source_verified.json that the study relies on
# at the time of audit. A missing anchor is reported, never silently ignored.
REQUIRED_ANCHOR_FILES: tuple[str, ...] = (
    "services/api/src/clara_api/glhs/admission.py",
    "services/api/src/clara_api/glhs/commitment_gateway.py",
    "services/api/src/clara_api/glhs/commit_kernel.py",
    "services/api/src/clara_api/glhs/canonical_json.py",
    "services/api/src/clara_api/glhs/inference_attestation.py",
    "services/api/src/clara_api/db/models.py",
    "services/api/src/clara_api/api/router.py",
    "services/api/pyproject.toml",
)

# Deliberately excluded from the content digest: runtime/build caches that are
# not part of the scientific snapshot and may legitimately differ between hosts.
EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".git/",
    "node_modules/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "apps/web/.next/",
    "apps/web/node_modules/",
)

# The fingerprint output and proof logs describe the snapshot, so including them
# in the snapshot digest would make it self-referential and unstable.
EXCLUDED_EXACT: tuple[str, ...] = (
    "research/venue2027/_shared/repo_fingerprint.json",
)


@dataclasses.dataclass(frozen=True)
class FileDigest:
    """A single tracked file and its SHA256 content digest."""

    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size_bytes": self.size_bytes}


@dataclasses.dataclass(frozen=True)
class Fingerprint:
    """Immutable result of :func:`snapshot`.

    ``ok`` is False for any environmental failure. ``reason_code`` explains why.
    ``missing_required_files`` lists contract anchors that were not found.
    """

    ok: bool
    reason_code: ReasonCode
    schema_version: str
    repo_root: str
    head_sha: str
    branch: str
    worktree_clean: bool
    tracked_file_count: int
    total_bytes: int
    content_sha256: str
    toolchains: dict[str, str]
    sql_dialect: str
    db_fixture_type: str
    files: tuple[FileDigest, ...]
    missing_required_files: tuple[str, ...]
    detail: str = ""

    def to_dict(self, *, include_files: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "reason_code": self.reason_code,
            "repo_root": self.repo_root,
            "head_sha": self.head_sha,
            "branch": self.branch,
            "worktree_clean": self.worktree_clean,
            "tracked_file_count": self.tracked_file_count,
            "total_bytes": self.total_bytes,
            "content_sha256": self.content_sha256,
            "toolchains": self.toolchains,
            "sql_dialect": self.sql_dialect,
            "db_fixture_type": self.db_fixture_type,
            "missing_required_files": list(self.missing_required_files),
            "detail": self.detail,
        }
        if include_files:
            payload["files"] = [f.to_dict() for f in self.files]
        return payload


def _run_git(repo: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def _detect_toolchains(repo: Path) -> dict[str, str]:
    """Record the toolchain versions that determine reproducibility."""

    toolchains: dict[str, str] = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
    }
    for name, argv in (
        ("node", ["node", "--version"]),
        ("uv", ["uv", "--version"]),
        ("docker", ["docker", "--version"]),
    ):
        exe = shutil.which(argv[0])
        if not exe:
            toolchains[name] = "absent"
            continue
        try:
            res = subprocess.run(argv, capture_output=True, text=True, check=False)
            toolchains[name] = (res.stdout or res.stderr).strip() or "unknown"
        except OSError:
            toolchains[name] = "unavailable"
    lock = repo / "services/api/uv.lock"
    toolchains["uv_lock_sha256"] = _sha256_file(lock) if lock.is_file() else "absent"
    return toolchains


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_excluded(path: str) -> bool:
    if path in EXCLUDED_EXACT:
        return True
    return any(path == p.rstrip("/") or path.startswith(p) for p in EXCLUDED_PREFIXES)


def _tracked_files(repo: Path) -> list[str]:
    res = _run_git(repo, ["ls-files", "-z"])
    if res.returncode != 0:
        return []
    return [p for p in res.stdout.split("\0") if p]


def _detect_sql_dialect(repo: Path) -> str:
    """Infer the declared SQL dialect from dependency + config evidence."""

    pyproject = repo / "services/api/pyproject.toml"
    text = pyproject.read_text(encoding="utf-8", errors="ignore") if pyproject.is_file() else ""
    has_psycopg = "psycopg" in text
    has_sqlite = "sqlite" in text
    config = repo / "services/api/src/clara_api/core/config.py"
    cfg_text = config.read_text(encoding="utf-8", errors="ignore") if config.is_file() else ""
    if has_psycopg and ("postgresql" in cfg_text or "postgresql" in text):
        return "postgresql"
    if has_psycopg:
        return "postgresql-declared"
    if has_sqlite:
        return "sqlite-only"
    return "unknown"


def _detect_db_fixture_type(repo: Path) -> str:
    """Classify the *default test* backend, which gates PG-concurrency claims."""

    found_sqlite = False
    found_pg = False
    for scope in ("services/api/tests",):
        base = repo / scope
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "sqlite" in text:
                found_sqlite = True
            if "postgresql" in text or "psycopg" in text:
                found_pg = True
    if found_sqlite and found_pg:
        return "mixed-sqlite-and-postgresql"
    if found_pg:
        return "postgresql"
    if found_sqlite:
        return "sqlite"
    return "unknown"


def snapshot(repo: str | os.PathLike[str], *, require_clean: bool = True) -> Fingerprint:
    """Produce a read-only fingerprint of ``repo``.

    Parameters
    ----------
    repo:
        Path to an existing git checkout. It is never modified.
    require_clean:
        When True (default) a dirty worktree yields ``reason_code=DIRTY_WORKTREE``
        and ``ok=False`` so a study can never silently bind to uncommitted code.

    Returns
    -------
    Fingerprint
        Frozen, JSON-serialisable inventory. Callers must check ``ok``.
    """

    root = Path(repo).resolve()
    if shutil.which("git") is None:
        return _failure(root, "GIT_UNAVAILABLE", "git binary not found on PATH")
    if not (root / ".git").exists():
        return _failure(root, "NOT_A_GIT_REPO", f"{root} is not a git checkout")

    head = _run_git(root, ["rev-parse", "HEAD"])
    if head.returncode != 0 or not head.stdout.strip():
        return _failure(root, "NO_HEAD", head.stderr.strip() or "rev-parse HEAD failed")
    head_sha = head.stdout.strip()

    branch_res = _run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "DETACHED"

    status_res = _run_git(root, ["status", "--porcelain=v1"])
    dirty_lines = [ln for ln in status_res.stdout.splitlines() if ln.strip()]
    worktree_clean = not dirty_lines

    files: list[FileDigest] = []
    aggregate = hashlib.sha256()
    total_bytes = 0
    for rel in sorted(_tracked_files(root)):
        if _is_excluded(rel):
            continue
        abspath = root / rel
        if not abspath.is_file():
            # Tracked but deleted in worktree: record the fact via dirty state,
            # never fabricate a digest.
            continue
        digest = _sha256_file(abspath)
        size = abspath.stat().st_size
        files.append(FileDigest(path=rel, sha256=digest, size_bytes=size))
        aggregate.update(f"{rel}\0{digest}\n".encode())
        total_bytes += size
    content_sha = aggregate.hexdigest()

    missing = tuple(p for p in REQUIRED_ANCHOR_FILES if not (root / p).is_file())

    base = dict(
        schema_version=REPO_FINGERPRINT_SCHEMA_VERSION,
        repo_root=str(root),
        head_sha=head_sha,
        branch=branch,
        worktree_clean=worktree_clean,
        tracked_file_count=len(files),
        total_bytes=total_bytes,
        content_sha256=content_sha,
        toolchains=_detect_toolchains(root),
        sql_dialect=_detect_sql_dialect(root),
        db_fixture_type=_detect_db_fixture_type(root),
        files=tuple(files),
        missing_required_files=missing,
    )

    if require_clean and not worktree_clean:
        return Fingerprint(
            ok=False,
            reason_code="DIRTY_WORKTREE",
            detail=f"{len(dirty_lines)} uncommitted path(s); refusing to bind study evidence",
            **base,
        )
    if missing:
        return Fingerprint(
            ok=False,
            reason_code="MISSING_REQUIRED_FILE",
            detail=f"missing contract anchors: {', '.join(missing)}",
            **base,
        )
    return Fingerprint(ok=True, reason_code="OK", detail="", **base)


def _failure(root: Path, code: ReasonCode, detail: str) -> Fingerprint:
    return Fingerprint(
        ok=False,
        reason_code=code,
        schema_version=REPO_FINGERPRINT_SCHEMA_VERSION,
        repo_root=str(root),
        head_sha="",
        branch="",
        worktree_clean=False,
        tracked_file_count=0,
        total_bytes=0,
        content_sha256="",
        toolchains={},
        sql_dialect="unknown",
        db_fixture_type="unknown",
        files=(),
        missing_required_files=(),
        detail=detail,
    )


def write_fingerprint(fp: Fingerprint, dest: str | os.PathLike[str]) -> Path:
    """Write ``fp`` as pretty JSON to ``dest`` (parent dirs created)."""

    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fp.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-repo_fingerprint")
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument(
        "--out",
        default="research/venue2027/_shared/repo_fingerprint.json",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    fp = snapshot(args.repo, require_clean=not args.allow_dirty)
    write_fingerprint(fp, args.out)
    summary = {
        "ok": fp.ok,
        "reason_code": fp.reason_code,
        "head_sha": fp.head_sha,
        "branch": fp.branch,
        "tracked_file_count": fp.tracked_file_count,
        "content_sha256": fp.content_sha256,
        "sql_dialect": fp.sql_dialect,
        "db_fixture_type": fp.db_fixture_type,
        "detail": fp.detail,
    }
    print(json.dumps(summary, indent=2))
    return 0 if fp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
