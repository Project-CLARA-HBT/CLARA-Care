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
   isolated-research attestation. It is not yet wired to an HTTP persistent-write
   adapter, and the development deployment still uses only the production-default
   strict system. Any future `EXECUTED` adapter row must attest HTTP, PostgreSQL,
   cache, and audit observation, reference a hashed raw-observation artifact,
   and carry a semantics-matched isolated-only arm implementation artifact/revision.
   A config or pure decision declaration alone is rejected.
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

The host inspected on 2026-08-16 runs the shared `clara-app` stack, so it is explicitly excluded from this study. The isolated compose file uses a unique project, project-local network, ports, and volumes; its non-tracked environment file must contain new random credentials.
