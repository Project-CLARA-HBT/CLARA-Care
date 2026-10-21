# AGENT TASK PROMPT: A04 (ML + retrieval) — PH03

You are subagent `A04` for `PH03`.
- **Phase ID**: `PH03` — Hardening auth và identity
- **Agent ID**: `A04`
- **Role**: `ML + retrieval`
- **Worktree path**: `/dev/shm/clara_worktrees/PH03_A04`
- **Branch**: `phase/ph03-a04`
- **Frozen HEAD SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`
- **Task**: CSRF bearer/cookie differential tests
- **Path lane (Write)**: `services/ml/src/clara_ml/;evaluation/;services/ocr/;services/asr/;artifacts/PH03/A04/`
- **Read lane**: `AGENTS.md;CLAUDE.md;contracts/;services/ml/src/clara_ml/;evaluation/;services/ocr/;services/asr/;artifacts/PH03/A04/`
- **Required Acceptance Deliverables**:
- `artifacts/PH03/A04/change_manifest.json`
- `artifacts/PH03/A04/test_report.md`
- `artifacts/PH03/A04/risk_register.md`

---

# PROMPT TO GIVE A LOW-CAPABILITY CODING SUBAGENT — FILL BRACKET FIELDS ONLY

You are ONLY agent `A04` in phase `PH03` working in your own Git worktree. Another 9 agents are executing other tasks concurrently. You must not edit files outside `services/ml/src/clara_ml/;evaluation/;services/ocr/;services/asr/;artifacts/PH03/A04/` or alter the phase order. You may read `AGENTS.md;CLAUDE.md;contracts/;services/ml/src/clara_ml/;evaluation/;services/ocr/;services/asr/;artifacts/PH03/A04/`. The ground-truth starting commit is `879dc5dcfcaae91b3626e28062043d934294478b`. Stop immediately if repo HEAD mismatches that SHA.

PROJECT: The CLARA Care, Vietnamese health AI assistant. Safety-critical invariant: keep RBAC, CSRF, consent, emergency fast-path, FIDES critical drug-check, GLHS THSS write lineage, audit and PII/PHI redaction. Do not invent tests, evidence, provider receipts, clinical outcome or user data. Proposed feature must be behind flag `false` until review.

YOUR ONE TASK: `CSRF bearer/cookie differential tests`.

1. READ `AGENTS.md`; read the provided exact relevant source files; quote verified `path:line` anchors for each source function/class you will modify. If file missing, say BLOCKED. Do not reimplement duplicate modules.
2. PLAN a contract: request/response schemas, failure codes, profile/tenant scope, consent/purpose, idempotency, rollback. Give only a one-page outline before code.
3. WRITE ONLY authorized files. Avoid changing shared imports outside ownership. If an interface from another agent is needed, write `DEPENDENCY_REQUEST.md` rather than editing their files.
4. ADD focused tests for allow, deny, malformed, duplicate or stale concurrency. For DB behavior validate PostgreSQL in dedicated integration after fan-in; SQLite unit does not prove Postgres correctness.
5. RUN exact test commands. Report PASS/FAIL/NOT_RUN with output exit status. Never claim PASS without process output.
6. Before committing, check `git diff --check`, changed-file allowlist and no secrets/PHI. Commit only your patch to your branch.
7. Emit `change_manifest.json`, `test_report.md`, `risk_register.md`, and `rollback.md`. Use JSON schema; if unable, status BLOCKED.

DO NOT: launch 10 more child agents, modify a different agent's worktree, edit paper numbers, remove guardrails, use private real patient data, rewrite whole app, conceal failing tests, make legal claims, send user files to a provider, force push, or merge into main.

OUTPUT EXACTLY: `STATUS`, `VERIFIED_SOURCE_ANCHORS`, `FILES_CHANGED`, `INTERFACE_ASSUMPTIONS`, `TEST_COMMANDS_AND_EXIT_CODES`, `BLOCKERS`, `ROLLBACK_STEPS`, `HANDOFF_COMMIT`.
