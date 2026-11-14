"""CLARA-Care 2027 shared task SH-worktree_layout.

Purpose
-------
Define and enforce the isolated-worktree policy for the research program so that
concurrent agents never edit the same path or touch production.

This module is executable policy, not prose: :func:`allocate_worktree` computes a
deterministic worktree path/branch, and :class:`PathLockRegistry` refuses any
second concurrent claim on an already-locked path.

Allowed input
-------------
Study slug, task id, and a set of paths an agent intends to write.

Failure semantics
-----------------
- Illegal slugs are refused with a stable ``reason_code``.
- A lock conflict raises :class:`LockConflict` (never silent overwrite).
- Attempting to claim a reserved production path is refused.

Version
-------
``WORKTREE_POLICY_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

WORKTREE_POLICY_VERSION = "1.0.0"

WORKTREE_ROOT = Path("/dev/shm/clara_worktrees")
BRANCH_PREFIX = "research/venue2027"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Paths no research agent may ever write. These are production/clinical paths.
PROTECTED_PREFIXES: tuple[str, ...] = (
    "services/api/alembic/versions/",
    "services/api/src/clara_api/glhs/",
    "services/api/src/clara_api/db/models.py",
    "apps/web/app/",
    ".github/workflows/",
)

# Shared research infrastructure that must be written by one owner at a time.
LOCKED_PREFIXES: tuple[str, ...] = (
    "research/venue2027/_shared/",
    "research/venue2027/MANIFESTS/",
    "research/venue2027/STATE/",
)


class WorktreePolicyError(ValueError):
    """Raised when a worktree request violates policy."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class LockConflict(WorktreePolicyError):
    """Raised when two agents claim the same path concurrently."""


@dataclasses.dataclass(frozen=True)
class WorktreeAllocation:
    study: str
    task_id: str
    path: Path
    branch: str

    def to_dict(self) -> dict[str, str]:
        return {
            "study": self.study,
            "task_id": self.task_id,
            "path": str(self.path),
            "branch": self.branch,
        }


def _slug(value: str, *, field: str) -> str:
    if not _SLUG_RE.match(value):
        raise WorktreePolicyError("INVALID_SLUG", f"{field}={value!r} is not a safe slug")
    return value


def allocate_worktree(study: str, task_id: str) -> WorktreeAllocation:
    """Return the deterministic worktree path and branch for a task."""

    study_slug = _slug(study, field="study")
    task_slug = _slug(task_id.lower().replace(".", "-"), field="task_id")
    path = WORKTREE_ROOT / f"venue2027_{study_slug}_{task_slug}"
    branch = f"{BRANCH_PREFIX}/{study_slug}/{task_slug}"
    return WorktreeAllocation(study=study_slug, task_id=task_id, path=path, branch=branch)


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    norm = path.strip().lstrip("./")
    return any(norm == p.rstrip("/") or norm.startswith(p) for p in prefixes)


def assert_writable(paths: list[str] | tuple[str, ...]) -> None:
    """Refuse any path outside the research tree or in a protected production area."""

    for path in paths:
        if _matches(path, PROTECTED_PREFIXES):
            raise WorktreePolicyError(
                "PROTECTED_PATH", f"{path} is production/clinical and cannot be edited by a research agent"
            )
        if not path.strip().lstrip("./").startswith("research/"):
            raise WorktreePolicyError(
                "OUTSIDE_RESEARCH_TREE",
                f"{path} is outside research/ and is not owned by the 2027 program",
            )


class PathLockRegistry:
    """In-memory exclusive path lock registry for concurrent agent scheduling."""

    def __init__(self) -> None:
        self._locks: dict[str, str] = {}

    def claim(self, agent_id: str, paths: list[str] | tuple[str, ...]) -> None:
        """Atomically claim ``paths`` for ``agent_id`` or raise :class:`LockConflict`."""

        assert_writable(paths)
        keys = [self._lock_key(p.strip().lstrip("./")) for p in paths]
        conflicts: list[str] = []
        for path, key in zip(paths, keys, strict=True):
            owner = self._locks.get(key)
            if owner is not None and owner != agent_id:
                conflicts.append(f"{path} (held by {owner})")
        if conflicts:
            raise LockConflict("LOCK_CONFLICT", "; ".join(conflicts))
        for key in keys:
            self._locks[key] = agent_id

    @staticmethod
    def _lock_key(path: str) -> str:
        # Locked prefixes are treated as a single exclusive resource so two
        # agents cannot race on different files under the same shared area.
        for prefix in LOCKED_PREFIXES:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                return prefix
        return path

    def release(self, agent_id: str) -> None:
        for path in [p for p, owner in self._locks.items() if owner == agent_id]:
            del self._locks[path]

    def holders(self) -> dict[str, str]:
        return dict(self._locks)
