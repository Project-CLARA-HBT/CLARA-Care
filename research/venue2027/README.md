# CLARA-Care 2027 — DeepSeek/Gemini granular implementation specification v3

**Created:** 2026-11-14 · **Repository:** Project-CLARA-HBT/CLARA-Care · **Verified reference branch:** research/glhs-r4-novelty-hardening · **Historical audited SHA:** `bce92340e190c62208a24aa3304f188080f6fd58`.

**Core deliverable:** 322 individually addressable implementation tasks across 10 workstreams (one shared + nine conference studies), a dependency DAG, per-venue phase books, per-task input/output contracts, release gates, and DeepSeek/Gemini handoff prompts. All code paths are *proposed additions* unless `MANIFESTS/source_verified.json` marks them existing.

**Important:** This spec does not modify GitHub repository or claim any newly executed conference experiment. It is a detailed implementable plan. Some tasks require external original implementations, clinician review or paid model access; statuses must stay BLOCKED until those resources exist.

## Start here

1. `python3 scripts/taskctl.py validate` — prove task DAG has no cycles and task files exist.
2. `python3 scripts/taskctl.py ready --venue shared` — list runnable shared prerequisites; no other task marked complete yet.
3. `python3 scripts/taskctl.py prompt SH-repo_fingerprint > agent_task.md` — standalone per-task prompt to paste into Gemini or DeepSeek.
4. On real agent completion, validate actual run logs and place one report in `artifacts/task_reports/`; run `python3 scripts/taskctl.py mark <ID> PASS --report path/to/report.json`.
5. `python3 scripts/taskctl.py ready --venue compsac` — see next ready work after preconditions.
6. Follow `AGENTS/MASTER_GOAL_DEEPSEEK.md` / `AGENTS/MASTER_GOAL_GEMINI.md` and phase books.

## Navigation

- `VENUES/<venue>/RESEARCH_BLUEPRINT.md`: exact paper, RQs, baselines, falsification and planned endpoints.
- `VENUES/<venue>/PHASES/P01.md` ... `P09.md`: order and deliverables at phase granularity.
- `VENUES/<venue>/TASKS/<TASK-ID>.md`: detailed single-file instructions, tests and handoff contract.
- `SHARED/TASKS/`: repository repair, independent oracle, PG16, baseline and audit infrastructure.
- `MANIFESTS/tasks.json`: structured machine-readable full task dependency graph.
- `MANIFESTS/tasks.csv`: convenient task list for Sheets, Excel or issue tracking.
- `AGENTS/`: prompts, resource locks, task report schema and agent protocol.
- `GATES/`: fail-closed scientific and CI checks, originality, safety and uncertainty.
- `CONTEXT/PAPERS/<venue>/`: previous polished LaTeX and supporting background specs for agents to read, not to overwrite.

## Workstreams

- `dsn` — Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations; 33 tasks.
- `popets` — Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts; 33 tasks.
- `ifip_sec` — Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage; 33 tasks.
- `acns` — SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems; 33 tasks.
- `compsac` — Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes; 33 tasks.
- `aime` — Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories; 33 tasks.
- `sacmat` — PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines; 33 tasks.
- `dimva` — GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events; 33 tasks.
- `pst` — ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization; 33 tasks.

## Distinctions essential to scientific validity

- `PASS` means running code and evidence checked, not a planned result.
- `NOT_RUN_EXTERNAL` means missing a real comparator; never count it as zero failures.
- `INDETERMINATE` is not a safe rejection or a successful task.
- Signed receipts prove integrity within a trusted observer, not the truth of neural internal reasoning or clinical safety.
- PostgreSQL serializability and crash recovery require real isolated PG transactions; SQLite unit tests only validate API behavior.
- Strong baseline tied or better => report that and narrow the scientific contribution.
- Different venues require genuinely independent novel questions/primary evidence; use alternate venue routing if overlapping.
