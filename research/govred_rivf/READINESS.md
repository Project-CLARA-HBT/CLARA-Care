# GovRed-Health authorization-drift RIVF readiness

Status: **NOT RUN — not submission-ready**.

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
