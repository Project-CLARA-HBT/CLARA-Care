# ACNS-overlap · Venue publication and evidence isolation

> **Phase:** `P01` · **Venue:** `acns` · **Priority:** `P0` · **Suggested agent:** `research_lead` · **Exclusive resource:** `cpu` · **Status:** `TODO`
>
> **Source audit:** Existing CLARA-Care branch `research/glhs-r4-novelty-hardening`; recorded HEAD `bce92340e190c62208a24aa3304f188080f6fd58` on 2026-11-14. Re-check live HEAD before changes. This is a task specification, not a claim that files have been created in GitHub.

## 0. Objective and expected change

SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems. An evidence-to-claim lattice for assembly, egress, transport acknowledgment, provider-attested receipt, execution trace and semantic consumption, with mechanized *counterexample witnesses* showing which implications fail absent explicit trust assumptions.

**One task = one scoped pull request / worktree.** First read its dependency artifacts. Do not implement downstream tasks simultaneously within the same commit, and do not overwrite other agents' in-flight changes.

## 1. Dependencies and exact entry conditions

- `ACNS-scope` — Independent contribution and objective
- `SH-claim_overlap` — Enforce publication overlap and scope firewall

Before touching files:

1. Read `AGENTS/EXECUTION_CONTRACT.md` and `AGENTS/RESOURCE_SCHEDULING.md`.
2. `git status --porcelain=v1` must be clean or document user-owned changes and avoid them.
3. `git rev-parse HEAD` and record SHA. Checkout a per-task worktree; never patch `main` directly.
4. Open relevant verified source modules only if this task calls them; source paths may evolve; prove actual import/signature from local checkout.
5. Verify dependencies `artifacts/task_reports/<ID>.json` and their SHA before starting. Missing dependency blocks the task, rather than guessing.

## 2. File and directory ownership

- `research/venue2027/acns/overlap_audit.md` — **NEW_PROPOSED, create after checking collisions**

**Exact target contract:** `audit(study)->OverlapDecision`.

- Preserve existing API compatibility and migration semantics. No production secret/data access.
- New files must start with docstring explaining purpose, allowed input, failure semantics and version.
- Typed input/output objects must be JSON-serializable unless an existing typed object is explicitly identified.
- Run under Python >=3.11; use existing repository `pytest`, `ruff` and type conventions.
- All errors must be a stable `reason_code`, not unhandled exceptions that are mistakenly counted as safe rejections.

## 3. Implementation instructions — implement in this order

**Required core algorithm / procedural design:** Diff manuscript section text, purpose, RQs, raw case IDs, labels, figures and endpoint against all nine tracks plus HEALTHINF/GLHS/GovRed/GovMut; document unique extension evidence.

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

No duplicate primary claim or data presented twice as new.

### Negative / adversarial control

Same E15–E22 outcome rebranded.

### Stop and revise if

- One forbidden commit or forbidden disclosure survives a complete independently labeled schedule.
- An oracle/test fixture imports candidate implementation and thereby ceases to be independent.
- A baseline is not faithful to its declared semantics, or lacks permission/data/compute parity.
- A holdout is opened before freeze or any output is selectively dropped.
- A real PostgreSQL condition is claimed using only SQLite in-memory observations.
- A routine incomplete/stale/UNKNOWN outcome is counted as a safe rejection or successful completion.

## 5. Required outputs and evidence provenance

- `research/venue2027/acns/overlap_audit.md`
- `artifacts/venue2027/acns/<run_id>/manifest.json`

Per-task report format in `AGENTS/TASK_REPORT_SCHEMA.json`:

```json
{
  "task_id": "ACNS-overlap",
  "status": "PASS | BLOCKED | FAIL",
  "source_sha_before": "<git full SHA>",
  "source_sha_after": "<git full SHA>",
  "changed_paths": ["research/venue2027/acns/overlap_audit.md"],
  "commands": [{"argv": "python3 -m pytest -q tests/venue2027/acns/...", "exit_code": 0}],
  "artifacts_sha256": {"<path>": "<64 hex>"},
  "oracle_disagreement_count": 0,
  "baseline_parity": "PASS | NOT_APPLICABLE | BLOCKED",
  "unresolved": []
}
```

`0` above is an illustrative schema example, not an observed research result; replace with actual computed values or `null` if not measured. The report is invalid if it asserts PASS without logs.

## 6. Definition of done

1. **Technical DoD:** PASS or explicit alternative-venue merger
2. `pytest` positive + negative/property checks pass under a documented environment. SQL/LLM tests use actual backend or remain explicitly BLOCKED.
3. No research claim is derived from unreproduced, mixed-version or historical-frozen evidence.
4. No source overlap, secrets, patient identifiers, provider keys or benchmark-only flags are merged into production paths.
5. Another agent can reproduce the minimal test from a clean checkout and the task report.

## 7. Handoff and next work

Return exactly: `[TASK-ID]`, source SHA, changed files, short engineering rationale, test commands and outputs, scientific-unit counts, baseline parity status, blocks, and the next ready tasks reported by `taskctl.py ready`. If blocked, deliver a minimal reproducer rather than continuing with guessed APIs.

## 8. Risk and review notes

- If taxonomy fails coder agreement or merely restates RFC 9334 / existing provenance literature without new cases and insights, do not claim SoK contribution.
- ACNS 2027 CFP may not offer SoK-specific track; only submit after checking venue scope and completed original systematic method.

## Scientific question and strongest alternative

**Paper:** SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems

**Relevant RQs:** RQ1-RQ3. Full study RQs:
- RQ1: Which attestation claims are actually supported by which observable evidence and trusted parties in published agent systems?
- RQ2: Which claimed implication pairs are invalid under explicit adversarial and provider models, and can small executable witnesses demonstrate this?
- RQ3: How consistently can independent reviewers classify claims and reproduce counterexamples across a pre-registered corpus?

**Research gap:** Existing cryptographic attestation terminology (IETF RATS) and agent safety benchmarks address related but nonidentical assurance claims. A SoK contributes only if its systematic taxonomy is reproducible, independently double-coded and resolves real disagreements, not if it rebrands provenance as new.

**Mechanism:** Define observation/trust axes, mechanically enumerate implication candidates, construct counterexamples for false implications, and publish extraction rules and independently adjudicated study selection ledger.

**Strong-baseline set** (not all relevant to this particular file):
- RFC 9334/RATS attestation evidence framework
- W3C PROV provenance and audit events
- AgentDojo/ToolEmu evidence and attack observability categories
- two independent human-coded new taxonomy

**Primary and important supporting outcomes:**
- inter-rater Cohen kappa
- ambiguous claim fraction
- counterexample reproduction rate
- coverage of evidence-strength lattice
- disagreement resolution rate

**Falsification rule:** If taxonomy fails coder agreement or merely restates RFC 9334 / existing provenance literature without new cases and insights, do not claim SoK contribution.

