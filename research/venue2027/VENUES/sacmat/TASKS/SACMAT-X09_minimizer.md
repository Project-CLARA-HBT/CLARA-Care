# SACMAT-X09_minimizer · Reduce fault-revealing trace

> **Phase:** `P05` · **Venue:** `sacmat` · **Priority:** `P1` · **Suggested agent:** `security` · **Exclusive resource:** `cpu` · **Status:** `TODO`
>
> **Source audit:** Existing CLARA-Care branch `research/glhs-r4-novelty-hardening`; recorded HEAD `bce92340e190c62208a24aa3304f188080f6fd58` on 2026-11-14. Re-check live HEAD before changes. This is a task specification, not a claim that files have been created in GitHub.

## 0. Objective and expected change

VENUE-SPECIFIC: PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines; proposed scientific mechanism and evaluation for RQ1.

**One task = one scoped pull request / worktree.** First read its dependency artifacts. Do not implement downstream tasks simultaneously within the same commit, and do not overwrite other agents' in-flight changes.

## 1. Dependencies and exact entry conditions

- `SACMAT-runner` — Uniform arm executor

Before touching files:

1. Read `AGENTS/EXECUTION_CONTRACT.md` and `AGENTS/RESOURCE_SCHEDULING.md`.
2. `git status --porcelain=v1` must be clean or document user-owned changes and avoid them.
3. `git rev-parse HEAD` and record SHA. Checkout a per-task worktree; never patch `main` directly.
4. Open relevant verified source modules only if this task calls them; source paths may evolve; prove actual import/signature from local checkout.
5. Verify dependencies `artifacts/task_reports/<ID>.json` and their SHA before starting. Missing dependency blocks the task, rather than guessing.

## 2. File and directory ownership

- `evaluation/venue2027/sacmat/temporal_witness_minimizer.py` — **NEW_PROPOSED, create after checking collisions**

**Exact target contract:** `minimize(trace,predicate)->Trace`.

- Preserve existing API compatibility and migration semantics. No production secret/data access.
- New files must start with docstring explaining purpose, allowed input, failure semantics and version.
- Typed input/output objects must be JSON-serializable unless an existing typed object is explicitly identified.
- Run under Python >=3.11; use existing repository `pytest`, `ruff` and type conventions.
- All errors must be a stable `reason_code`, not unhandled exceptions that are mistakenly counted as safe rejections.

## 3. Implementation instructions — implement in this order

**Required core algorithm / procedural design:** Delta-debug ordered events without deleting required granting context; ensure still exposes same semantic fault on real engine.

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

Positive fixtures: the correct governed operation is accepted or measured; expected outputs are schema-valid and reproducible.

### Negative / adversarial control

Reduction changes expected decision, nonterminating shrink.

### Stop and revise if

- One forbidden commit or forbidden disclosure survives a complete independently labeled schedule.
- An oracle/test fixture imports candidate implementation and thereby ceases to be independent.
- A baseline is not faithful to its declared semantics, or lacks permission/data/compute parity.
- A holdout is opened before freeze or any output is selectively dropped.
- A real PostgreSQL condition is claimed using only SQLite in-memory observations.
- A routine incomplete/stale/UNKNOWN outcome is counted as a safe rejection or successful completion.

## 5. Required outputs and evidence provenance

- `evaluation/venue2027/sacmat/temporal_witness_minimizer.py`
- `artifacts/venue2027/sacmat/<run_id>/minimizer.json`

Per-task report format in `AGENTS/TASK_REPORT_SCHEMA.json`:

```json
{
  "task_id": "SACMAT-X09_minimizer",
  "status": "PASS | BLOCKED | FAIL",
  "source_sha_before": "<git full SHA>",
  "source_sha_after": "<git full SHA>",
  "changed_paths": ["evaluation/venue2027/sacmat/temporal_witness_minimizer.py"],
  "commands": [{"argv": "python3 -m pytest -q tests/venue2027/sacmat/...", "exit_code": 0}],
  "artifacts_sha256": {"<path>": "<64 hex>"},
  "oracle_disagreement_count": 0,
  "baseline_parity": "PASS | NOT_APPLICABLE | BLOCKED",
  "unresolved": []
}
```

`0` above is an illustrative schema example, not an observed research result; replace with actual computed values or `null` if not measured. The report is invalid if it asserts PASS without logs.

## 6. Definition of done

1. **Technical DoD:** Minimal witness with reproducible mutation ID.
2. `pytest` positive + negative/property checks pass under a documented environment. SQL/LLM tests use actual backend or remain explicitly BLOCKED.
3. No research claim is derived from unreproduced, mixed-version or historical-frozen evidence.
4. No source overlap, secrets, patient identifiers, provider keys or benchmark-only flags are merged into production paths.
5. Another agent can reproduce the minimal test from a clean checkout and the task report.

## 7. Handoff and next work

Return exactly: `[TASK-ID]`, source SHA, changed files, short engineering rationale, test commands and outputs, scientific-unit counts, baseline parity status, blocks, and the next ready tasks reported by `taskctl.py ready`. If blocked, deliver a minimal reproducer rather than continuing with guessed APIs.

## 8. Risk and review notes

- If trace generator does not outperform stateful and MC/DC-guided baselines at equal oracle-call budget, do not claim novel fault detection; publish portability limits transparently.
- SACMAT Dataset/Tool track is likely better than a main claim. Need actual external engine execution rather than merely naming them.

## Scientific question and strongest alternative

**Paper:** PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines

**Relevant RQs:** RQ1. Full study RQs:
- RQ1: Which distinct trace-level policy errors are undetected by static rule/decision coverage but exposed by temporal metamorphic tests?
- RQ2: How many executable mutants representing revocation, delegation, purpose and temporal precedence are killed by comparable budgets for random, MC/DC-inspired and PolicyTrace generation?
- RQ3: Across Cedar, OpenFGA and OPA, which semantics are faithfully expressible, and where do adapters necessarily diverge?

**Research gap:** MC/DC XACML policy testing and XACBench cover static policy structures; what must be demonstrated as new is systematic conformance testing of policy *histories* with revocation/redelegation and replay, including portability failures attributable to mismatched semantics.

**Mechanism:** Define a portable three/four-valued decision oracle (PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE) and a partial mapping to each PDP; test revocation-before-replay, delegation expiration, explicit-deny precedence and temporal reorderings.

**Strong-baseline set** (not all relevant to this particular file):
- uniform random authorization requests
- MC/DC-inspired XACML policy testing (Xu et al. SACMAT 2018)
- XACBench policy profile–driven synthetic tests
- property-based history generator without temporal metamorphs
- PolicyTrace temporal generator plus oracle

**Primary and important supporting outcomes:**
- mutation score at fixed oracle budget
- trace witness detection coverage
- policy-engine disagreement
- invalid/indeterminate parity
- generation runtime
- minimal failure trace length

**Falsification rule:** If trace generator does not outperform stateful and MC/DC-guided baselines at equal oracle-call budget, do not claim novel fault detection; publish portability limits transparently.

