# IFIP_SEC-scope · Independent contribution and objective

> **Phase:** `P01` · **Venue:** `ifip_sec` · **Priority:** `P0` · **Suggested agent:** `researcher` · **Exclusive resource:** `cpu` · **Status:** `TODO`
>
> **Source audit:** Existing CLARA-Care branch `research/glhs-r4-novelty-hardening`; recorded HEAD `bce92340e190c62208a24aa3304f188080f6fd58` on 2026-11-14. Re-check live HEAD before changes. This is a task specification, not a claim that files have been created in GitHub.

## 0. Objective and expected change

Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage. Study a *multi-principal interleaving* in which a valid consent-purpose receipt is delegated, refreshed and consumed across policy-epoch changes and concurrent replay. Define a consumed-once invariant and a tested provenance binding for delegated proposal chains.

**One task = one scoped pull request / worktree.** First read its dependency artifacts. Do not implement downstream tasks simultaneously within the same commit, and do not overwrite other agents' in-flight changes.

## 1. Dependencies and exact entry conditions

- `SH-claim_overlap` — Enforce publication overlap and scope firewall
- `SH-literature_hardening` — Lock strongest Q1/A/A* comparators from primary sources

Before touching files:

1. Read `AGENTS/EXECUTION_CONTRACT.md` and `AGENTS/RESOURCE_SCHEDULING.md`.
2. `git status --porcelain=v1` must be clean or document user-owned changes and avoid them.
3. `git rev-parse HEAD` and record SHA. Checkout a per-task worktree; never patch `main` directly.
4. Open relevant verified source modules only if this task calls them; source paths may evolve; prove actual import/signature from local checkout.
5. Verify dependencies `artifacts/task_reports/<ID>.json` and their SHA before starting. Missing dependency blocks the task, rather than guessing.

## 2. File and directory ownership

- `research/venue2027/ifip_sec/novelty_contract.md` — **NEW_PROPOSED, create after checking collisions**

**Exact target contract:** `design_scope()->NoveltyRegister`.

- Preserve existing API compatibility and migration semantics. No production secret/data access.
- New files must start with docstring explaining purpose, allowed input, failure semantics and version.
- Typed input/output objects must be JSON-serializable unless an existing typed object is explicitly identified.
- Run under Python >=3.11; use existing repository `pytest`, `ruff` and type conventions.
- All errors must be a stable `reason_code`, not unhandled exceptions that are mistakenly counted as safe rejections.

## 3. Implementation instructions — implement in this order

**Required core algorithm / procedural design:** Write full claim-to-prior-work falsification matrix, target reader, non-overlap and one paragraph scope. Indicate truly distinct endpoint and strongest competing explanation.

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

Contains specific candidate mechanism vs 3 strong baselines.

### Negative / adversarial control

Overlapping published GLHS result as new evidence.

### Stop and revise if

- One forbidden commit or forbidden disclosure survives a complete independently labeled schedule.
- An oracle/test fixture imports candidate implementation and thereby ceases to be independent.
- A baseline is not faithful to its declared semantics, or lacks permission/data/compute parity.
- A holdout is opened before freeze or any output is selectively dropped.
- A real PostgreSQL condition is claimed using only SQLite in-memory observations.
- A routine incomplete/stale/UNKNOWN outcome is counted as a safe rejection or successful completion.

## 5. Required outputs and evidence provenance

- `research/venue2027/ifip_sec/novelty_contract.md`
- `artifacts/venue2027/ifip_sec/<run_id>/manifest.json`

Per-task report format in `AGENTS/TASK_REPORT_SCHEMA.json`:

```json
{
  "task_id": "IFIP_SEC-scope",
  "status": "PASS | BLOCKED | FAIL",
  "source_sha_before": "<git full SHA>",
  "source_sha_after": "<git full SHA>",
  "changed_paths": ["research/venue2027/ifip_sec/novelty_contract.md"],
  "commands": [{"argv": "python3 -m pytest -q tests/venue2027/ifip_sec/...", "exit_code": 0}],
  "artifacts_sha256": {"<path>": "<64 hex>"},
  "oracle_disagreement_count": 0,
  "baseline_parity": "PASS | NOT_APPLICABLE | BLOCKED",
  "unresolved": []
}
```

`0` above is an illustrative schema example, not an observed research result; replace with actual computed values or `null` if not measured. The report is invalid if it asserts PASS without logs.

## 6. Definition of done

1. **Technical DoD:** Signed scope register and go/no-go decision
2. `pytest` positive + negative/property checks pass under a documented environment. SQL/LLM tests use actual backend or remain explicitly BLOCKED.
3. No research claim is derived from unreproduced, mixed-version or historical-frozen evidence.
4. No source overlap, secrets, patient identifiers, provider keys or benchmark-only flags are merged into production paths.
5. Another agent can reproduce the minimal test from a clean checkout and the task report.

## 7. Handoff and next work

Return exactly: `[TASK-ID]`, source SHA, changed files, short engineering rationale, test commands and outputs, scientific-unit counts, baseline parity status, blocks, and the next ready tasks reported by `taskctl.py ready`. If blocked, deliver a minimal reproducer rather than continuing with guessed APIs.

## 8. Risk and review notes

- If a properly scoped Macaroon plus consistent authorization check is decision-equivalent on all attacks, state equivalence and do not claim stronger security.
- Potentially weak novelty relative to existing capability systems; reject manuscript if B1/B2 already meet every invariant.

## Scientific question and strongest alternative

**Paper:** Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage

**Relevant RQs:** RQ1-RQ3. Full study RQs:
- RQ1: Under which delegation and epoch interleavings do signed context-bound capability baselines admit an invalid replay or reject valid operations?
- RQ2: Is the proposed consume-once transition linearizable under two or more real PostgreSQL sessions and revoked scope?
- RQ3: What are token size, verification latency and legitimate operation rejection costs relative to well-configured Macaroons and Zanzibar-like policies?

**Research gap:** Macaroons and Zanzibar already solve substantial parts of contextual authorization and consistency. A credible new claim must show a specific multi-hop lineage/replay counterexample against strong correctly configured caveat-token and versioned authorization baselines, not just signature checking.

**Mechanism:** Receipts are typed commitments: HMAC over actor, patient, tenant, purpose, task, consent/policy epoch, dispatch digest, nonce and parent reference. Verify the full delegation ancestry and atomically consume the nonce, not just signature equality.

**Strong-baseline set** (not all relevant to this particular file):
- bearer signed receipt
- Macaroon HMAC caveats: actor, purpose, task, expiry, nonce
- Zanzibar/OpenFGA with consistency token and fresh policy evaluation
- Cedar/OPA policy decision with replay nonce registry
- proposed delegated lineage transition verifier

**Primary and important supporting outcomes:**
- invalid replay admissions
- valid control acceptance
- duplicate consumption race
- token bytes
- p95 verify latency
- authorization DB round trips

**Falsification rule:** If a properly scoped Macaroon plus consistent authorization check is decision-equivalent on all attacks, state equivalence and do not claim stronger security.

