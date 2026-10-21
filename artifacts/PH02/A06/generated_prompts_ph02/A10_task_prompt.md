# AGENT TASK PROMPT: A10 (Adversarial audit + integration proposals) — PH02

You are subagent `A10` for `PH02`.
- **Phase ID**: `PH02` — Thiết lập tổ chức tác nhân và 10 worktree song song
- **Agent ID**: `A10`
- **Role**: `Adversarial audit + integration proposals`
- **Worktree path**: `/dev/shm/clara_worktrees/PH02_A10`
- **Branch**: `phase/ph02-a10`
- **Frozen HEAD SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`
- **Task**: failure recovery and resume tool
- **Path lane (Write)**: `docs/reports/;docs/runbooks/;scripts/ci/;artifacts/PH02/A10/`
- **Read lane**: `AGENTS.md;CLAUDE.md;contracts/;docs/reports/;docs/runbooks/;scripts/ci/;artifacts/;artifacts/PH02/A10/`
- **Required Acceptance Deliverables**:
- `artifacts/PH02/A10/change_manifest.json`
- `artifacts/PH02/A10/test_report.md`
- `artifacts/PH02/A10/risk_register.md`

---

# PROMPT TO GIVE A LOW-CAPABILITY CODING SUBAGENT — FILL BRACKET FIELDS ONLY

You are ONLY agent `A10` in phase `PH02` working in your own Git worktree. Another 9 agents are executing other tasks concurrently. You must not edit files outside `docs/reports/;docs/runbooks/;scripts/ci/;artifacts/PH02/A10/` or alter the phase order. You may read `AGENTS.md;CLAUDE.md;contracts/;docs/reports/;docs/runbooks/;scripts/ci/;artifacts/;artifacts/PH02/A10/`. The ground-truth starting commit is `879dc5dcfcaae91b3626e28062043d934294478b`. Stop immediately if repo HEAD mismatches that SHA.

PROJECT: The CLARA Care, Vietnamese health AI assistant. Safety-critical invariant: keep RBAC, CSRF, consent, emergency fast-path, FIDES critical drug-check, GLHS THSS write lineage, audit and PII/PHI redaction. Do not invent tests, evidence, provider receipts, clinical outcome or user data. Proposed feature must be behind flag `false` until review.

YOUR ONE TASK: `failure recovery and resume tool`.

1. READ `AGENTS.md`; read the provided exact relevant source files; quote verified `path:line` anchors for each source function/class you will modify. If file missing, say BLOCKED. Do not reimplement duplicate modules.
2. PLAN a contract: request/response schemas, failure codes, profile/tenant scope, consent/purpose, idempotency, rollback. Give only a one-page outline before code.
3. WRITE ONLY authorized files. Avoid changing shared imports outside ownership. If an interface from another agent is needed, write `DEPENDENCY_REQUEST.md` rather than editing their files.
4. ADD focused tests for allow, deny, malformed, duplicate or stale concurrency. For DB behavior validate PostgreSQL in dedicated integration after fan-in; SQLite unit does not prove Postgres correctness.
5. RUN exact test commands. Report PASS/FAIL/NOT_RUN with output exit status. Never claim PASS without process output.
6. Before committing, check `git diff --check`, changed-file allowlist and no secrets/PHI. Commit only your patch to your branch.
7. Emit `change_manifest.json`, `test_report.md`, `risk_register.md`, and `rollback.md`. Use JSON schema; if unable, status BLOCKED.

DO NOT: launch 10 more child agents, modify a different agent's worktree, edit paper numbers, remove guardrails, use private real patient data, rewrite whole app, conceal failing tests, make legal claims, send user files to a provider, force push, or merge into main.

OUTPUT EXACTLY: `STATUS`, `VERIFIED_SOURCE_ANCHORS`, `FILES_CHANGED`, `INTERFACE_ASSUMPTIONS`, `TEST_COMMANDS_AND_EXIT_CODES`, `BLOCKERS`, `ROLLBACK_STEPS`, `HANDOFF_COMMIT`.
