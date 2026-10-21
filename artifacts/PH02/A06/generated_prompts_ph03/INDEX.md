# Phase PH03 — Agent Prompt & Bounded Context Pack

- **Title**: Hardening auth và identity
- **Priority**: `P0`
- **Dependencies**: `[1]`
- **Frozen Base SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`
- **Worktree Root**: `/dev/shm/clara_worktrees`
- **Generated (UTC)**: `2026-10-21T13:26:54.539382+00:00`
- **Total Agents**: `10`

## Subagent Task Directory

| Agent | Role | Task | Write Lane | Branch | Prompt File |
|---|---|---|---|---|---|
| **A02** | Data model + migration | JWT/session invalidation and rotation | `services/api/src/clara_api/db/; services/api/alembic/versions/...` | `phase/ph03-a02` | [A02_task_prompt.md](A02_task_prompt.md) |
| **A01** | API + contract | auth threat inventory | `services/api/src/clara_api/api/; contracts/...` | `phase/ph03-a01` | [A01_task_prompt.md](A01_task_prompt.md) |
| **A03** | Domain + GLHS services | RBAC object-level profile scope | `services/api/src/clara_api/glhs/; services/api/src/clara_api/lifemap/...` | `phase/ph03-a03` | [A03_task_prompt.md](A03_task_prompt.md) |
| **A04** | ML + retrieval | CSRF bearer/cookie differential tests | `services/ml/src/clara_ml/; evaluation/...` | `phase/ph03-a04` | [A04_task_prompt.md](A04_task_prompt.md) |
| **A05** | Web UX | OTP/login brute-force protection | `apps/web/app/; apps/web/components/...` | `phase/ph03-a05` | [A05_task_prompt.md](A05_task_prompt.md) |
| **A06** | Mobile Flutter | secure password reset and recovery | `apps/mobile/; artifacts/PH03/A06/` | `phase/ph03-a06` | [A06_task_prompt.md](A06_task_prompt.md) |
| **A07** | Tests + CI | web session UX states | `services/api/tests/; services/ml/tests/...` | `phase/ph03-a07` | [A07_task_prompt.md](A07_task_prompt.md) |
| **A08** | Security + privacy | mobile refresh/session persistence | `docs/security/; docs/compliance/...` | `phase/ph03-a08` | [A08_task_prompt.md](A08_task_prompt.md) |
| **A09** | Docs + research evidence | security negative-test suite | `research/; docs/research/...` | `phase/ph03-a09` | [A09_task_prompt.md](A09_task_prompt.md) |
| **A10** | Adversarial audit + integration proposals | auth migration/recovery documentation | `docs/reports/; docs/runbooks/...` | `phase/ph03-a10` | [A10_task_prompt.md](A10_task_prompt.md) |

## Execution Instructions

1. Verify repo HEAD in each worktree matches frozen base SHA.
2. Subagents must never write outside their exact write paths.
3. Integration follows deterministic order: `A02 -> A01 -> A03 -> A04 -> A05 -> A06 -> A07 -> A08 -> A09 -> A10`.
4. Bounded context pack JSON: [`bounded_context_pack.json`](bounded_context_pack.json).
