# Phase PH02 — Agent Prompt & Bounded Context Pack

- **Title**: Thiết lập tổ chức tác nhân và 10 worktree song song
- **Priority**: `P0`
- **Dependencies**: `[0, 1]`
- **Frozen Base SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`
- **Worktree Root**: `/dev/shm/clara_worktrees`
- **Generated (UTC)**: `2026-10-21T13:26:48.329495+00:00`
- **Total Agents**: `10`

## Subagent Task Directory

| Agent | Role | Task | Write Lane | Branch | Prompt File |
|---|---|---|---|---|---|
| **A02** | Data model + migration | git worktree creation tool | `services/api/src/clara_api/db/; services/api/alembic/versions/...` | `phase/ph02-a02` | [A02_task_prompt.md](A02_task_prompt.md) |
| **A01** | API + contract | agent contract JSON schema | `services/api/src/clara_api/api/; contracts/...` | `phase/ph02-a01` | [A01_task_prompt.md](A01_task_prompt.md) |
| **A03** | Domain + GLHS services | ten task-scoped worktree paths | `services/api/src/clara_api/glhs/; services/api/src/clara_api/lifemap/...` | `phase/ph02-a03` | [A03_task_prompt.md](A03_task_prompt.md) |
| **A04** | ML + retrieval | resource quotas and semaphore 10 | `services/ml/src/clara_ml/; evaluation/...` | `phase/ph02-a04` | [A04_task_prompt.md](A04_task_prompt.md) |
| **A05** | Web UX | ownership and path ACL checker | `apps/web/app/; apps/web/components/...` | `phase/ph02-a05` | [A05_task_prompt.md](A05_task_prompt.md) |
| **A06** | Mobile Flutter | agent prompt and bounded context pack | `apps/mobile/; artifacts/PH02/A06/` | `phase/ph02-a06` | [A06_task_prompt.md](A06_task_prompt.md) |
| **A07** | Tests + CI | merge queue and integration worker | `services/api/tests/; services/ml/tests/...` | `phase/ph02-a07` | [A07_task_prompt.md](A07_task_prompt.md) |
| **A08** | Security + privacy | deterministic red-team checker | `docs/security/; docs/compliance/...` | `phase/ph02-a08` | [A08_task_prompt.md](A08_task_prompt.md) |
| **A09** | Docs + research evidence | checkpoint/progress dashboard | `research/; docs/research/...` | `phase/ph02-a09` | [A09_task_prompt.md](A09_task_prompt.md) |
| **A10** | Adversarial audit + integration proposals | failure recovery and resume tool | `docs/reports/; docs/runbooks/...` | `phase/ph02-a10` | [A10_task_prompt.md](A10_task_prompt.md) |

## Execution Instructions

1. Verify repo HEAD in each worktree matches frozen base SHA.
2. Subagents must never write outside their exact write paths.
3. Integration follows deterministic order: `A02 -> A01 -> A03 -> A04 -> A05 -> A06 -> A07 -> A08 -> A09 -> A10`.
4. Bounded context pack JSON: [`bounded_context_pack.json`](bounded_context_pack.json).
