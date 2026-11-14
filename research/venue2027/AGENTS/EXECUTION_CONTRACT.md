# System-level execution contract for DeepSeek and Gemini coding agents

**Objective:** Turn the nine 2027 CLARA-Care research designs into independently reproducible, ethically defensible experiments, while preserving original GLHS scientific claims and append-only data integrity.

**Verified repo:** `Project-CLARA-HBT/CLARA-Care`, source branch `research/glhs-r4-novelty-hardening`. Snapshot previously inspected `bce92340e190c62208a24aa3304f188080f6fd58`. Live HEAD may differ: always inspect before patching.

## Instructions to every agent (apply in this exact order)

1. Receive only one task ID and its `TASKS/<ID>.md`, plus `MANIFESTS/tasks.json` and necessary dependency task reports. Do not reinterpret the scientific question.
2. Read all verified existing files referenced in task and check Python/runtime signatures. Existing source paths are *inspection anchors*, proposed study paths are *not yet in repository*. Record discovered differences.
3. If dependency is absent/failed, return BLOCKED with minimal explanation; do not forge a completed dependency.
4. Open isolated worktree from an orchestrator-approved base SHA (`git worktree add ... -b research/venue2027/<venue>/<task-slug>`); no force push/reset and no direct updates to `main`.
5. Start with specific failing unit tests and positive/negative fixtures; code minimal change to pass. Never disable immutable GLHS event listener as a shortcut or use a production DB.
6. Implement typed data contracts and stable reason codes, dataset/algorithm version IDs and any prerequisites; no untracked randomness or hidden provider calls.
7. Execute checks and capture exit codes. Run real PostgreSQL only when declared and in isolated container; do not use SQLite for PG concurrency claims.
8. Verify baseline parity against official examples, oracle independence and exact planned denominator. Never replace unavailable baseline by custom toy and keep same name.
9. Emit exactly one JSON handoff matching `AGENTS/TASK_REPORT_SCHEMA.json`; include files and hashes, tests, scientific metrics (or NOT_RUN), limitations and next deps.
10. Do not fabricate numbers, dates, paper acceptance or paper-specific “Results” before evidence; negative evidence is an output, not failure to be hidden.

## Return content required

- `What I inspected`: source HEAD, existing symbols, new files.
- `What I changed`: diff summary, reason per file, backwards compatibility implications.
- `What I tested`: commands+exit codes and artifact paths; for no test run, status BLOCKED or FAIL.
- `What remains`: clear blockers or next IDs that can run without file conflicts.

## Definition of different responsible agents

- Oracle reviewer cannot reuse candidate code. Candidate agent cannot approve its own ground-truth labels.
- Statistics reviewer cannot change frozen analysis to obtain desired significance.
- Paper agent cannot manually enter Results values that do not exist in the claim ledger.
- Infrastructure agent must enforce data isolation and cost caps; never direct agents to access real patient data.

## No invented downstream API

Conceptual interfaces in specs are *contracts to implement*, not claims that functions currently exist. The only verified repository anchors are listed in `MANIFESTS/source_verified.json`. Any source moved/renamed since audit requires an updated verified map and orchestrator review.
