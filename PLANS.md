# Long-running implementation plans

CLARA work that spans multiple checkpoints uses an ExecPlan under `docs/`. The plan must state scope, dependencies, commands, expected behavior, rollback, decisions, and observable progress.

## Rules

1. Inspect source, guidance, tests, and current git state before editing.
2. Keep unrelated user changes untouched.
3. Break work into stable, reviewable commits; do not rewrite history or force-push.
4. Update the plan, task list, traceability, and decision log after each checkpoint.
5. Run the closest tests first, then widen validation. Record pass, fail, and not-run with evidence.
6. Preserve safety invariants: RBAC, consent, emergency, FIDES, DrugBank, provenance/truth state, auditability, CSRF, profile isolation, no PII, and no chain-of-thought.
7. A task is not complete because a skeleton compiles; it needs integrated behavior and acceptance evidence.
8. Use subagents for bounded audits/reviews with non-overlapping ownership. The root agent integrates and reviews all changes.

## UI modernization

The active plan is `docs/ui-modernization/07-exec-plan.md`. Read the complete plan and requirements before modifying frontend production code. `08-task-list.md` is the source for task status and `11-decisions-and-progress.md` is the living decision/checkpoint log.

