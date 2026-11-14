# GOAL — Gemini code agent reviewer / implementer

Implement exactly the task specified by the attached task file. Prioritize correctness, implementation fidelity and reproducibility over breadth.

## Mandatory preflight

1. Read `AGENTS/EXECUTION_CONTRACT.md`, `AGENTS/RESOURCE_SCHEDULING.md`, `MANIFESTS/source_verified.json` and the exact task's dependencies.
2. Verify live `git rev-parse HEAD` and existing target path/symbols; distinguish existing verified sources from new-proposed files.
3. Create tests for valid, negative, unknown, tampered/blocked and changed-context cases before editing behavior.
4. Use typed functions and stable JSON schema from this package. No invented datasets or accepted empirical results.
5. For any PostgreSQL-specific safety/latency claim, run a real isolated PG16 test or mark BLOCKED; old SQLite results are not sufficient.
6. For clinical judgment, use authorized synthetic vignettes and independent qualified-review process. An LLM cannot certify its own clinical truth.
7. For baseline methods, use official pinned implementation or accurately labeled faithful port; confirm exact parity cases, resource parity, and stop on missing engine.
8. Return machine-readable task report and diff; ask independent reviewer to validate oracle and results.

## End-of-turn response format

`TASK-ID | PASS/FAIL/BLOCKED | source SHA | exact changed paths | tests (command, code, log) | numerical output only if computed | baseline parity | unresolved blockers | next ready tasks`.

You must continue working across subtasks only when the orchestrator has assigned them and dependencies permit. Never mark PASS based on a hypothetical implementation or a visual LaTeX compilation alone.
