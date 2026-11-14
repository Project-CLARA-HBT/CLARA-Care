# Scheduling and optimization of expensive DeepSeek/Gemini multi-agent work

## Non-negotiable order

1. Shared P00 fixes/source fingerprint before any risky database work (except independent literature/SoK research).
2. Scientific RQ, oracle, baseline fidelity and data safety before new clever mechanisms.
3. Development-only pilots to estimate power/cost and remove nonviable designs.
4. Frozen confirmatory run exactly once per independent campaign; revisions require a declared fresh holdout.
5. Manuscript Results and claims are machine-derived from released raw evidence.

## Ten-agent allocation (maximum, not required)

| Slot | Role | Work | Resource class |
|---|---|---|---|
| 01 | GLHS maintainer | shared R4 immutable ledger defect, minimal fix | repo-locked |
| 02 | Independent oracle | study truth specification and clinical review contracts | cpu/reviewer |
| 03 | Research reviewer | literature, strongest baselines, publication overlap | cpu |
| 04 | PostgreSQL engineer | isolated PG16 harness, concurrency/recovery | pg-locked |
| 05 | Baseline engineer | pinned upstream code and semantic parity | cpu/network |
| 06 | Method engineer | venue-specific algorithm, property tests | cpu |
| 07 | Test engineer | adversarial fixtures and mutation tests | cpu |
| 08 | Statistician | power/margins, paired analysis, data-checks | cpu |
| 09 | Reproduction auditor | checksum and chronology/security gates | cpu |
| 10 | Paper/writing agent | independent manuscript updates; funding/format | cpu |

## Concurrency locks

- `repo-locked`: only one writer to existing GLHS ORM, migrations and production `glhs/` path. Everyone else reads.
- `pg-locked`: max one heavy postgres fault experiment per host/isolated DB; parallel PG worker count is *within* the experiment.
- `model-api`: one budgeted model-calls coordinator. Never run unreconciled model endpoints in multiple agents.
- `clinical-review`: human adjudication cannot be performed by the same candidate-model agent.
- `holdout-locked`: only the confirmatory runner can open holdout after freeze; avoid parallel tuning agents accessing it.
- `paper`: may update separate venue papers in parallel, but no shared results claims until evidence gate.

## Efficiency techniques

- Unit tests and formal exploration before live provider calls. Use synthetic offline tests first.
- Keep raw event fixtures static and content-hashed. Cache repeated **deterministic** public-source extraction and upstream build artifacts, but never cache decisions across changed governance epochs.
- Reuse shared schema and executor code across papers; require *new independent science* and separately held-out datasets.
- Use stratified pilot to find boundary cases; main study uses preregistered sampling, not success-selected seeds.
- Stop jobs on changed primary protocol hash, missing oracle, failed baseline parity, production DB URL or model cost ceiling.
- Profile 1x/2x/4x scaling under a fixed hardware configuration; report hardware and all compute/DB/network expenses.
- Prioritize COMPSAC (systems, no provider needed), AIME (clinical review and model cost), PoPETs (revocation graph). DSN and IFIP SEC are near-term/high novelty risk; do not weaken evidence to meet a deadline.

## Bounded budgets (illustrative pilot defaults; must be revised after resource inventory)

- Pure unit tasks: 10–20 minutes per smoke run, 1–2 GB RAM when feasible, zero remote API calls.
- PostgreSQL pilot: 1 dedicated compose cluster, max 4 workers initially, < 1 CPU-hour per venue pilot before scale-up; record actual settings.
- Model/LLM pilot: spend cap must be explicit in `config`, start with 5–10 vignettes and one cheap arm per verified provider, then estimate full factorial cost. Never suggest running underfunded experiments secretly.
- Clinical annotation: freeze reviewer roster/eligibility/blinding and funding before releasing main cases.
- SoK source screening: manual-full-text status and recheck dates; do not confuse ten LLM-coded papers with independent review.

## Cross-agent integration rules

- Only orchestrator merges; all agents submit `task_report.json` and patch/PR. No git force-push to shared branch.
- Lock ownership at path granularity; two tasks on same file run sequentially.
- Shared library interfaces are versioned; changes need consumer compatibility tests.
- Development and main data are isolated by access control and machine-readable freeze, not just filenames.
- `BLOCKED` means wait for necessary evidence or authority; never silently substitute toy models/engines.
