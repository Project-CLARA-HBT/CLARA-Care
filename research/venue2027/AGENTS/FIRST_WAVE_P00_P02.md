# First wave: exact safe startup sequence (no fictional parallel repair)

**Warm start:** The local task state initially lists all tasks TODO. Do not mark tasks PASS because these specifications exist. Start from `SH-repo_fingerprint` and `SH-agent_protocol` only, per `taskctl.py ready`.

| Agent | Initial task ID | First deliverable | Write lock | Next step only when dependency PASS |
|---|---|---|---|---|
| 1 / repository auditor | `SH-repo_fingerprint` | real repo tree + SHA inventory | read-only | security regression discovery |
| 2 / orchestration auditor | `SH-agent_protocol` | workflow and task-report validity | isolated docs | task report schema review |
| 3 / clinical oracle researcher | **BLOCKED pending initial shared tasks** | prepared truth schema, no labels | read-only | independent oracle |
| 4 / PG engineer | **BLOCKED pending initial shared tasks** | PG container plan | pg-locked | isolated DB provision |
| 5 / baseline engineer | **BLOCKED pending initial shared tasks** | upstream source/version inventory | read-only | registry + parity |
| 6 / statistician | **BLOCKED pending initial shared tasks** | design-only effect size and estimand notes | read-only | analysis policy |
| 7 / security engineer | **BLOCKED pending initial shared tasks** | attack-matrix review | read-only | guard regression |
| 8 / COMPSAC method engineer | **BLOCKED pending shared gates** | RQ and planned scenarios, no new code | read-only | COMPSAC P01 |
| 9 / AIME clinical review lead | **BLOCKED pending ethics/resources** | reviewer rubric research | read-only | AIME protocol |
| 10 / paper editor | **BLOCKED pending primary science evidence** | format/instructions review | read-only | revisions after P08 |

### Why only two tasks start initially

A ten-agent *capacity* does not mean ten independent safe write tasks exist at time zero. The validated dependency DAG determines safe parallelism. Continue `ready` after each independently checked task report; later phases expose more parallel opportunities.

### First live GitHub repository corrections

- Inspect `services/api/src/clara_api/db/models.py` at `_reject_glhs_ledger_mutation` and `_reject_glhs_canonical_content_mutation`. Earlier CI saw four R4 failures under proposal row immutability. Write reproducing tests first; never simply remove immutability event handlers.
- Verify source SHA and CI on actual HEAD, because this plan's audited reference predates the current execution date.
- Keep all experiment logic in `evaluation/venue2027/<venue>/` and `research/venue2027/<venue>/`; production integration needs separate review and feature flag.
- Preserve use of PostgreSQL for concurrency conclusions. SQLite tests are useful for ORM behavior only.
