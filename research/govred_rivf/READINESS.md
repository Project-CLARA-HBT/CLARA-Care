# GovRed-Health authorization-drift RIVF readiness

Status: **FINAL FOUR-ARM EXECUTED AND ANALYZED — claim eligibility requires sealed raw store + dual-model protocol QA**. Final run `2026-08-17-rivf-final-003`, code revision `5b2c0dbf`, 450 logical cases per arm (180 NOT_RUN per protocol exclusions, 270 EXECUTED per arm). Primary stale/unauthorized-commit acceptance: UNBOUND 0.571 (95% CI 0.504-0.636), STATE_VERSION_ONLY 0.429 (0.364-0.496), SNAPSHOT_BOUND_STATE_ONLY 0.429 (0.364-0.496), GLHS_STRICT 0.143 (0.102-0.197). Paired McNemar GLHS_STRICT vs UNBOUND p<0.0001 (b=90, c=0). Prohibited disclosure 0/270 all arms. Results in `artifacts/govred/2026-08-17-rivf-final-003/` (gitignored raw store) and `research/govred_rivf/results/analysis.json`.

Literature-hardened contribution lock: matched governed disclosure → explicit
authorization/state mutation → persistent commit schedules. This is a
controlled software robustness/governance-consistency study, not a generic
cybersecurity or prompt-injection benchmark.

Implemented protocol controls: a manifest schema and balanced development-manifest builder with 9 primary authorization-drift schedules and 6 separately reported secondary stress families, plus program-level claim controls. These are not results.

Exact blockers:

1. An isolated development HTTP → auth/policy → Redis → PostgreSQL boundary is healthy under run ID `2026-08-16-rivf-dev-001`, but it has no final code-revision attestation or completed audit observer.
2. A research-only commit-admission contract now implements the prespecified
   `UNBOUND`, `STATE_VERSION_ONLY`, `SNAPSHOT_BOUND_STATE_ONLY`, and
   `GLHS_STRICT` binding/state/governance distinctions behind the explicit
   isolated-research attestation. A narrow authenticated synthetic HTTP-to-GST
   primitive now exercises the selected arm, but it is not a complete-boundary
   adapter and does not cover the whole manifest. Any future `EXECUTED` adapter
   row must attest HTTP, PostgreSQL, cache, and audit observation, reference a
   hashed raw-observation artifact, and carry a semantics-matched isolated-only
   arm implementation artifact/revision. A config or pure decision declaration
   alone is rejected.
   `boundary_adapter_capability_matrix.json` records why the currently examined
   public Commitment route may support a development HTTP commit probe but cannot
   receive a complete-boundary attestation: it has no cache/index stage, no
   public evidence writer, and no public consent-revoke mutation.
   A matching service-local gate now refuses any named arm unless the process is
   explicitly attested, non-production, and bound to a `clara-rivf-*` project.
   The isolated gate now reaches the real GST persistent-admission path: the
   four arms differ only in their prespecified snapshot, state, and governance
   revalidation coordinates, while normal processes retain strict admission.
   An authenticated synthetic HTTP probe route is mounted only with that same
   gate and drives profile scope, synthetic THSS/evidence, an optional synthetic
   consent revoke, and GST admission. This is a tested adapter primitive, not a
   cache/index route, complete-boundary observer, frozen-manifest executor, or
   RIVF run.
   The frozen-manifest executor now independently verifies that any future
   `EXECUTED` observation and arm-implementation artifacts are local,
   root-contained files whose SHA-256 values match the declared values. This
   closes only an artifact-integrity precondition; it does not supply an
   adapter, cache/index route, public revoke path, arm implementation, or run.
3. Final locked manifest, independently reviewed frozen statistics plan, and final test partition are absent.
4. No classified raw boundary observations, frozen-manifest analysis, figures/tables, or claim-eligible sealed `artifacts/govred/<run-id>/` inventory exists.
5. The official IEEE-RIVF 2026 CFP was checked on 2026-08-16 and recorded in `venue_cfp_receipt_20260817.json`: English IEEE A4 PDF, up to six pages, EDAS, with the listed extended deadline of 2026-08-31. Recheck immediately before final formatting and again before any submission; this closes no evidence or submission gate.

The historic VPS transport probe is not RIVF outcome evidence because it stores only response hashes and requires operator classification.

Development-only evidence: `artifacts/govred/2026-08-16-rivf-dev-001/development_smoke.json` records a UI-context recovery probe; `development_smoke_v2.json` records a synthetic foreign-profile request to the real Lifemap scope resolver, rejected as `404 scope_forbidden` through the isolated HTTP/API/Redis/PostgreSQL path. Neither is drawn from the frozen manifest, has a research-arm comparison or DB/audit observation, and neither may be used as a headline attack rate.

The rebuilt, source-attested `2026-08-16-rivf-dev-002` environment repeats the
Lifemap scope smoke under a fresh project/volumes and records its own artifact.
It improves development traceability only: it remains `NOT_RUN` for the frozen
RIVF benchmark and has no comparative arms or complete DB/cache/audit observer.

Development run `2026-08-17-rivf-dev-004` adds a sanitized, operator-driven
store observer around one synthetic foreign-profile request. The HTTP request
was denied (`404 scope_forbidden`) and its PostgreSQL and PHR-audit hashes were
unchanged between pre- and post-request snapshots. The Redis hash changed, so
this probe does **not** establish a cache-invalidation result. It has no
research-arm comparison, no governed disclosure-to-commit schedule, and remains
development-only; its artifact inventory is sealed as
`sealed_development_not_claim_eligible` and its separately retained failed
transfer is not part of the run inventory.

For subsequent probes, the sanitized store observer independently requires the
explicit `CLARA_GOVRED_ISOLATED_RESEARCH=1` attestation and `clara-rivf-`
container names before issuing any Docker query. Its PostgreSQL signature now
includes GLHS assertions, transitions, snapshot manifests, commitment proposals,
versions, and transitions in addition to PHR/Lifemap counts; audit output is
still retained only as a hash. This is an operational isolation/observation
guard only and does not retroactively turn the development probe into headline
evidence or an HTTP research-arm adapter.

Development run `2026-08-17-rivf-dev-005` repeated that single synthetic
foreign-profile probe against the pre-existing isolated
`clara-rivf-20260816-dev002` deployment with the expanded GLHS-aware observer.
The request was denied (`404 scope_forbidden`); PostgreSQL and audit hashes were
unchanged while Redis changed. Its source hashes, sanitized result, and seal are
retained in `artifacts/govred/2026-08-17-rivf-dev-005/`. This remains one
strict-system development observation: it neither identifies the Redis change
nor establishes cache invalidation, audit completeness, an arm comparison, or
any frozen-benchmark result.

Development run `2026-08-17-rivf-dev011` deployed the current committed source
to a fresh remote `clara-rivf-20260817-dev011` project with distinct loopback
port, network, volumes, and generated credentials. A synthetic foreign-profile
request was denied (`404 scope_forbidden`); the sampled isolated PostgreSQL,
PHR-audit, and namespaced Redis hashes were unchanged across the request. The
sealed sanitized artifact is retained in
`artifacts/govred/2026-08-17-rivf-dev011/`. This is one strict-system
development boundary probe only: it does not exercise a cache/index route,
research arm, governed disclosure-to-commit schedule, or complete audit matrix.

Development run `2026-08-17-rivf-dev012` deployed a separate source-attested
isolated project with the `STATE_VERSION_ONLY` arm explicitly selected. A new
synthetic user completed the real HTTP auth and consent steps, then the
isolated probe created synthetic THSS/evidence, revoked consent, and called
GST admission through the synthetic HTTP route. The request committed (`201`,
`transition_committed`) as this arm intentionally omits governance
revalidation. The sampled PostgreSQL and namespaced Redis signatures changed;
the PHR-audit hash remained empty and is not audit-completeness evidence. The
sealed artifact documents one mechanism trace only: it is not a cache/index
test, full arm comparison, frozen-manifest execution, or RIVF result.

The separately deployed `2026-08-17-rivf-dev013` strict-arm counterpart used
the same authenticated synthetic consent-revoke schedule and returned `409`
`assertion_consent_mismatch`. Its sealed artifact is a single strict mechanism
trace, not a frozen paired comparison: it has no complete cache/index or
audit-reconstruction observation and cannot support an attack-rate claim.

Development run `2026-08-17-rivf-dev014` used another fresh, source-attested
isolated project with `STATE_VERSION_ONLY`. Its authenticated synthetic route
first committed a separate synthetic state advance, then attempted the target
proposal from the now-stale state. GST rejected the target with `409`
`stale_state_version`, as required by that arm's state revalidation coordinate.
The sealed artifact is one development mechanism trace only: it has no
cache/index or audit-reconstruction observation, frozen schedule execution, or
claim-eligible RIVF result.

Development run `2026-08-17-rivf-dev015` repeated the same synthetic
state-advance schedule on a separate fresh `UNBOUND` project. The target
transition committed (`201`, `transition_committed`), consistent with the
deliberately unbound arm omitting state revalidation. This sealed trace does
not constitute a paired comparison, attack rate, cache/index observation,
audit-reconstruction observation, or frozen RIVF result.

Development run `2026-08-17-rivf-dev016` used a separate fresh
`SNAPSHOT_BOUND_STATE_ONLY` project for the same synthetic state-advance
schedule. The target was rejected (`409`, `stale_state_version`), retaining
both snapshot binding and state revalidation while omitting governance
revalidation by design. Its sealed development artifact is not a frozen arm
comparison, cache/index observation, audit-reconstruction observation, or
claim-eligible RIVF result.

The host inspected on 2026-08-16 runs the shared `clara-app` stack, so it is explicitly excluded from this study. The isolated compose file uses a unique project, project-local network, ports, and volumes; its non-tracked environment file must contain new random credentials.

Development run `2026-08-17-rivf-dev018-attested-*` used four fresh isolated
PostgreSQL/Redis/API projects, one for each prespecified research arm, with
source revision `a03677956a3f39c10e548428f605c262d4f33599` and synthetic
records only. Its sealed per-arm matrix exercised baseline, consent revoke,
deployment-level policy-version change, actor switch, subject replay, stale
state, digest tamper attempt, natural snapshot expiry, and concurrent consent
writer schedules. Every applicable development oracle matched. The two
snapshot-binding arms recorded PostgreSQL trigger rejection of the direct
digest-tampering attempt and admission rejection after natural expiry; the
strict arm rejected the sequential governance mutations. Concurrent committed
outcomes are retained as `indeterminate_ordering_transition_committed`, never
as safe. The unbound and state-version-only arms correctly mark snapshot-only
families `NOT_RUN` rather than zero failures. This is development evidence
only: it does not observe a governed cache/index route or independent complete
audit reconstruction per logical case, is not a frozen manifest, and is not an
RIVF attack-rate or superiority result.

Development run `2026-08-17-rivf-dev020-cacheaudit` then exercised the new
isolated-only governed-disclosure Redis cache and separate HTTP audit observer
on `STATE_VERSION_ONLY` and `GLHS_STRICT`. After the same persisted synthetic
consent revocation, the state-only arm retained an opaque cache entry and
committed; the strict arm invalidated the entry and rejected admission. The
post-commit observer correctly reported no complete reconstruction for the
unbound state-only commit and `not_committed` for the strict rejection. This
two-arm trace is sealed development evidence only. It neither provides the
full four-arm cache study nor establishes audit completeness, a frozen
complete-boundary run, or any headline RIVF outcome.

## Workstream E — GovRed completion status (2026-08-19)

Final-003 remains the sealed historical study (read-only). Workstream E adds
new, separately frozen artifacts. Current state:

- **E-001 three-state primary (GRD-01).** `final_analysis_schema.py`
  (`govred-three-state-primary-v1`) re-derives the primary table into
  `results/final-003-three-state-primary.json` and
  `three_state_primary.md`. GLHS_STRICT: CONFIRMED_INVALID 0,
  INDETERMINATE 30 (concurrent_stale_state_write, never relabelled as
  confirmed violations), CONFIRMED_SAFE_OR_REJECTED 180, OPERATIONAL_FAILURE 0.
  The binary non-safe composite remains a secondary frozen endpoint only.
- **E-002/E-003 repetition protocol (GRD-02).** `govred_repetition_protocol.py`
  freezes 30 scenarios x 50 repetitions with DB commit-order evidence
  (`pg_xact_commit_timestamp`, never txid-order-only). Frozen under
  `repetition_protocol_v1/` and marked **PENDING EXECUTION**: no reachable
  isolated PostgreSQL on this host (docker unavailable). No INDETERMINATE
  schedule has been reclassified.
- **E-004 Not Run capability audit (GRD-03).** `not_run_capability.py` ->
  `not_run_capability_audit.md`: 16 family-arm rows IMPLEMENTABLE_FAITHFULLY
  (cross_subject_retrieval, purpose_mismatch, policy_version_change,
  unrelated_disclosure_request), 8 REQUIRES_LLM_ATTACK_STUDY (gst_bypass_prompt,
  patient_evidence_prompt_injection), 0 TASK_OR_ARM_SEMANTICS_UNSUPPORTED.
  Three mandatory-primary families were completed in the adapter at commit
  `bd0d7d65` (capability, not result).
- **E-005 feasible Not Run scenarios.** `not_run_adapter_scenarios.py`
  implements DB-free scenario drivers for the feasible families using the
  existing persisted governance writers (`advance_governance_policy_epoch`,
  `purpose_or_authorization_change`, `role_change`); prompt-injection families
  stay unimplemented (E-006).
- **E-007/E-008 audit opportunity denominators (GRD-04).**
  `opportunity_schema.py` -> `audit_opportunity_denominators.md`: completeness
  reported only within each eligible opportunity set (rejected-operations
  record, committed-operations reconstruction, governance-mutation trace
  linkage). The frozen final-003 observer emits only the reconstruction boolean
  (0.400 within its eligible set); rejection-record and trace-linkage are
  `not_emitted` and reported as such, never as completeness claims.
- **E-009 fresh holdout (GRD-05).** `holdout_protocol.py` +
  `holdout_v1/FREEZE.md` + `holdout_v1/schedules_skeleton.json`: 39 skeleton
  schedules, **FROZEN-NOT-EXECUTED** under a manual independent-human
  authorship gate. LLM-simulated authorship is forbidden; the gate is open.
- **E-010 new freeze.** Not started; requires the manual gates above.
- **E-011 publication routing (GRD-06).** `PUBLICATION_ROUTING.md`: **RIVF
  primary** (final-003 is its sealed study); BigData Healthcare held
  /extension-only until resolved concurrency + holdout + additional
  backend/attack-family evidence.

Remaining manual gates before any new freeze or submission: independent human
holdout authors (E-009), repetition execution against an isolated PostgreSQL
(E-002/E-003), and a new GovRed freeze (E-010).
