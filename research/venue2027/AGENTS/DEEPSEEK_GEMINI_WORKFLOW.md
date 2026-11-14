# DeepSeek / Gemini — operational handoff, context packing, and prompt discipline

## Context packing per worker

The orchestrator gives one task at a time in this order:

1. The task's text `python3 scripts/taskctl.py prompt <TASK-ID> --model deepseek|gemini`.
2. The needed *real* source modules from the checked-out branch: include relevant function signatures and caller examples, not unverifiable snippets from another branch.
3. The exact last passing predecessor task reports (including commit hashes and test commands).
4. For a venue task, `VENUES/<venue>/RESEARCH_BLUEPRINT.md` plus `VENUES/<venue>/CASE_MATRIX.md` and relevant policies from `GATES/`.
5. The worker's exclusive write scope and the orchestrator-approved worktree name.

## DeepSeek worker settings

- Use one agent for test-first implementation and a different auditor for critical code/benchmark fidelity. Do not create 10 simultaneous workers that all modify the same ORM file.
- To reduce context consumption: ask the worker to summarize discovered symbols in 10-20 lines and include only necessary source windows; inspect the full implementation before editing.
- Return a patch with clear changed files, explicit runnable commands and JSON task report; do not substitute prose claims for logs.
- If call limits arise, pause at a substep boundary, store a checkpoint containing SHA, test results and next action. Resume from that artifact, not from guessed memory.

## Gemini worker settings

- Start each task from a clean source checkout or isolated worktree; pass `source_verified.json` and the task file along with actual repo files.
- For long contexts, keep RQ + oracle + DoD at the *end* of the prompt as a final verification checklist.
- Ask Gemini to output short audit-ready changed-path list and the exact patch, not a full rewrite of thousands of lines.
- Treat generated Python/SQL/LaTeX as untrusted until reproducibly built; a model's verbal “tested” is not an executed test.

## Standard stopping behavior for both

Reply BLOCKED with one minimal example and the exact missing resource when an upstream task, clinical annotation, paid API, actual PG server or external comparator is missing. Do not invent a database path or positive outcome. Never claim finished clinical safety from a synthetic-only design. No real patient data.

## Manual copy/paste examples

```bash
cd CLARA_2027_DEEPSEEK_GEMINI_IMPLEMENTATION_SPEC_V3
python3 scripts/taskctl.py validate
python3 scripts/taskctl.py ready --venue shared
python3 scripts/taskctl.py prompt SH-repo_fingerprint --model deepseek > deepseek_task.md
python3 scripts/taskctl.py prompt SH-agent_protocol --model gemini > gemini_task.md
python3 scripts/taskctl.py list --venue compsac --phase P04
python3 scripts/taskctl.py audit
```

The orchestrator must also provide the *relevant repository files* in the same working session. A prompt text alone is not a substitute for working-tree access or actual execution.
