# Research worktree and path-lock policy

> Generated from the executable policy in
> `research/venue2027/_shared/tools/worktree_policy.py` (version `1.0.0`).
> The prose below is a description of enforced code, not a substitute for it.

## Worktree layout

Each independent task runs in its own `git worktree` on its own branch:

- Worktree root: `/dev/shm/clara_worktrees/venue2027_<study>_<task>`
- Branch: `research/venue2027/<study>/<task-slug>`
- Base: the orchestrator-approved frozen SHA; no force-push, no reset, never `main`.

Allocation is deterministic via `allocate_worktree(study, task)`. Unsafe slugs
are refused with `INVALID_SLUG`.

## Ownership and locking

- Paths are claimed with `PathLockRegistry.claim(agent_id, paths)`. A second
  concurrent claim on the same path raises `LockConflict` — never a silent
  overwrite.
- Shared research areas are locked as a single exclusive resource:
  `research/venue2027/_shared/`, `research/venue2027/MANIFESTS/`,
  `research/venue2027/STATE/`.
- Only the orchestrator integrates verified patches; agents never merge.

## Protected (never writable by a research agent)

- `services/api/alembic/versions/` (migration history)
- `services/api/src/clara_api/glhs/` (GLHS ledger/kernel)
- `services/api/src/clara_api/db/models.py` (ORM + immutable listeners)
- `apps/web/app/` (production consumer surface)
- `.github/workflows/` (CI gates)

Attempts yield `PROTECTED_PATH`; anything outside `research/` yields
`OUTSIDE_RESEARCH_TREE`.

## Artifact directory and ignore rules

Per-task evidence lives under `research/venue2027/proof/` and
`artifacts/task_reports/`. Raw run logs, trace files and hashes are retained.
Nothing in a worktree is committed to `main` directly.

## Merge ownership

The orchestrator alone cherry-picks an agent's single branch HEAD after the
report validates (zero-exit commands, in-repo SHA, artifact hashes, satisfied
dependencies). Two agents that share a file are serialized by the path lock.
