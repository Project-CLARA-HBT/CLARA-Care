# DSN-schema · Case/run/output JSON schemas

> **Phase:** `P02` · **Venue:** `dsn` · **Priority:** `P0` · **Suggested agent:** `architect` · **Exclusive resource:** `cpu` · **Status:** `TODO`
>
> **Source audit:** Existing CLARA-Care branch `research/glhs-r4-novelty-hardening`; recorded HEAD `bce92340e190c62208a24aa3304f188080f6fd58` on 2026-11-14. Re-check live HEAD before changes. This is a task specification, not a claim that files have been created in GitHub.

## 0. Objective and expected change

Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations. Recoverability is a safety property of the *joint* clinical row, immutable decision lineage, and asynchronous side-effect record, not just of one database commit. Define a recoverable outcome function that returns COMMITTED, REJECTED, or INDETERMINATE until reconcilable ground truth exists.

**One task = one scoped pull request / worktree.** First read its dependency artifacts. Do not implement downstream tasks simultaneously within the same commit, and do not overwrite other agents' in-flight changes.

## 1. Dependencies and exact entry conditions

- `DSN-rq_registry` — RQ, estimand, hypotheses and metrics
- `DSN-threat` — Threat, trust and failure model
- `SH-base_contracts` — Define common schemas of cases, traces and runs

Before touching files:

1. Read `AGENTS/EXECUTION_CONTRACT.md` and `AGENTS/RESOURCE_SCHEDULING.md`.
2. `git status --porcelain=v1` must be clean or document user-owned changes and avoid them.
3. `git rev-parse HEAD` and record SHA. Checkout a per-task worktree; never patch `main` directly.
4. Open relevant verified source modules only if this task calls them; source paths may evolve; prove actual import/signature from local checkout.
5. Verify dependencies `artifacts/task_reports/<ID>.json` and their SHA before starting. Missing dependency blocks the task, rather than guessing.

## 2. File and directory ownership

- `research/venue2027/dsn/protocols/study.schema.json` — **NEW_PROPOSED, create after checking collisions**

**Exact target contract:** `validate_study_json(record)->bool`.

- Preserve existing API compatibility and migration semantics. No production secret/data access.
- New files must start with docstring explaining purpose, allowed input, failure semantics and version.
- Typed input/output objects must be JSON-serializable unless an existing typed object is explicitly identified.
- Run under Python >=3.11; use existing repository `pytest`, `ruff` and type conventions.
- All errors must be a stable `reason_code`, not unhandled exceptions that are mistakenly counted as safe rejections.

## 3. Implementation instructions — implement in this order

**Required core algorithm / procedural design:** Extend shared schemas with venue-specific unit, observer, family, expected/observed decision, synthetic provenance and source authority; disallow silent nulls.

1. **Discover:** inspect file existence, imports and callers; record results in the handoff report. If absent, create the exact proposed path; if existing and substantially different, block with a concrete symbol map rather than fabricating adaptation.
2. **Formalize:** define the input dataclass/Pydantic model or JSON Schema, legal state transition relation, output types, explicit UNKNOWN/INDETERMINATE and stable error codes. Write at least two positive and two adversarial vectors *before* implementing the algorithm.
3. **Implement smallest correct vertical slice:** a pure-function reference where possible; use injected I/O for DB, network and model; no hidden clock/randomness, no live provider for unit tests. Keep policy, clinical context and timing externalized in the test fixture.
4. **Preserve trustworthy boundaries:** validate scope (tenant, principal, purpose, policy/consent epoch); verify all evidence sources or fail closed. Do not use statistical confidence or cryptographic digest as clinical reasoning proof.
5. **Implement exact semantics:** follow the core algorithm above; version output format and never silently drop missing dependency. Make retries idempotent by stable logical operation ID if persistent effects are involved.
6. **Add observability:** record attempt ID, independent unit ID, arm ID, source SHA, backend, duration, error class and input/output SHA256; sanitize sensitive content and do not silently filter failures.
7. **Test:** run small deterministic unit/property tests, edge cases, integration tests (only if requires PostgreSQL/model/engine), baseline parity tests and tamper tests.
8. **Compare:** prove expected behavior against the independent oracle and strongest baseline semantics in this scope; produce minimal counterexample to candidate if any. Never repair oracle to match candidate post hoc.
9. **Lint and type-check:** run `ruff check` on touched Python files and `pytest` on specific tests. Run repository gate after integration, never only syntax check.
10. **Close:** output changed-files list, source hashes, exact commands/exit codes, runtime and RAM/DB/model budget, unresolved blockers and next dependent task IDs. Request independent sign-off for oracle and security-sensitive changes.

## 4. Verifiable behavior

### Positive / supported control

Valid case and run fixtures accepted.

### Negative / adversarial control

Missing backend/seed/label/subject grouping rejected.

### Stop and revise if

- One forbidden commit or forbidden disclosure survives a complete independently labeled schedule.
- An oracle/test fixture imports candidate implementation and thereby ceases to be independent.
- A baseline is not faithful to its declared semantics, or lacks permission/data/compute parity.
- A holdout is opened before freeze or any output is selectively dropped.
- A real PostgreSQL condition is claimed using only SQLite in-memory observations.
- A routine incomplete/stale/UNKNOWN outcome is counted as a safe rejection or successful completion.

## 5. Required outputs and evidence provenance

- `research/venue2027/dsn/protocols/study.schema.json`
- `artifacts/venue2027/dsn/<run_id>/manifest.json`

Per-task report format in `AGENTS/TASK_REPORT_SCHEMA.json`:

```json
{
  "task_id": "DSN-schema",
  "status": "PASS | BLOCKED | FAIL",
  "source_sha_before": "<git full SHA>",
  "source_sha_after": "<git full SHA>",
  "changed_paths": ["research/venue2027/dsn/protocols/study.schema.json"],
  "commands": [{"argv": "python3 -m pytest -q tests/venue2027/dsn/...", "exit_code": 0}],
  "artifacts_sha256": {"<path>": "<64 hex>"},
  "oracle_disagreement_count": 0,
  "baseline_parity": "PASS | NOT_APPLICABLE | BLOCKED",
  "unresolved": []
}
```

`0` above is an illustrative schema example, not an observed research result; replace with actual computed values or `null` if not measured. The report is invalid if it asserts PASS without logs.

## 6. Definition of done

1. **Technical DoD:** Schema property tests and sample records
2. `pytest` positive + negative/property checks pass under a documented environment. SQL/LLM tests use actual backend or remain explicitly BLOCKED.
3. No research claim is derived from unreproduced, mixed-version or historical-frozen evidence.
4. No source overlap, secrets, patient identifiers, provider keys or benchmark-only flags are merged into production paths.
5. Another agent can reproduce the minimal test from a clean checkout and the task report.

## 7. Handoff and next work

Return exactly: `[TASK-ID]`, source SHA, changed files, short engineering rationale, test commands and outputs, scientific-unit counts, baseline parity status, blocks, and the next ready tasks reported by `taskctl.py ready`. If blocked, deliver a minimal reproducer rather than continuing with guessed APIs.

## 8. Risk and review notes

- If a correctly engineered PostgreSQL transaction + outbox + idempotent consumer achieves the same invariants and equal/better recovery cost, discard the new mechanism superiority claim.
- Very high novelty bar, deadline nearly immediate. Do not submit a routine outbox implementation as a breakthrough.

## Scientific question and strongest alternative

**Paper:** Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations

**Relevant RQs:** RQ1-RQ3. Full study RQs:
- RQ1: Across crash cut points, are there executions where the clinical state, decision receipt, and outbox state disagree after bounded recovery?
- RQ2: Under at-least-once replay and concurrent consent revocation, does recovery preserve idempotence, causal order, and correct INDETERMINATE labels?
- RQ3: What is the added durable-write, p99 latency and recovery-time cost compared with transactional outbox and durable workflow baselines?

**Research gap:** Transactional outbox and database WAL already give crash-safe writes; the unresolved issue worth testing is whether an AI proposal lineage and user-visible decision stay consistent across crash windows and arbitrary duplicate deliveries. Without a new counterexample to a careful outbox baseline, this is an application paper, not a DSN A contribution.

**Mechanism:** A reconciler checks a versioned decision receipt against the committed row, independent outbox receipt and consent epoch. Invalid/ambiguous evidence never becomes a positive outcome; retry decisions are keyed to immutable operation IDs.

**Strong-baseline set** (not all relevant to this particular file):
- DB transaction only + fire-and-forget side effect
- PostgreSQL atomic write + transactional outbox + idempotent consumer
- Durable workflow/saga with compensation and stable operation IDs
- Proposed reconciliation safety journal

**Primary and important supporting outcomes:**
- orphan clinical writes per independent history
- phantom user-visible success
- eventual safe reconciliation fraction
- duplicate side effects
- RTO p50/p95/p99
- extra fsyncs per operation

**Falsification rule:** If a correctly engineered PostgreSQL transaction + outbox + idempotent consumer achieves the same invariants and equal/better recovery cost, discard the new mechanism superiority claim.

