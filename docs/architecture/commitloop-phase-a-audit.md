# CommitLoop Phase-A / Phase-B execution audit

Status date: 2026-08-11. Phase A is frozen and the bounded Phase-B synthetic
benchmark is complete. `router_calls_before_initial_freeze` remains zero.

| Requirement | Current evidence | Status |
| --- | --- | --- |
| Versioned, GST-coupled, append-only commitments | Migration `20260810_0054`; commitment gateway/reconstruction tests; full migration-chain upgrade → downgrade → upgrade round trip | Implemented, targeted validation passed |
| Four independent product-state axes and policies | `commitments.py`, reconciliation and policy tests | Implemented, targeted validation passed |
| Bounded no-code predicate DSL | Closed operator validator plus Hypothesis property tests | Implemented, targeted validation passed |
| THSS scope/consent/state/conflict/sufficiency projection | `commitment_thss.py` and gateway tests | Implemented, targeted validation passed |
| Profile/consent/RBAC/CSRF API boundary | Nine route contract/integration tests cover anonymous 401; active, missing, and revoked medical consent; append-only re-acceptance; cookie CSRF; owner proposal/transition/read; stale state rejection; cross-owner 404; strict THSS snapshot compilation; timezone/domain validation. The shared append-only medical-consent query now selects the latest row correctly and fails closed on revocation. | Implemented, focused integration validation passed; PostgreSQL and isolated deployed-boundary runs remain external. |
| Source-grounded FHIR construction and deterministic gold | CommitLoop construction/oracle/leakage tests, including R4 `ServiceRequest` and STU3 `ProcedureRequest` without provenance relabeling. Ingestion requires an aware local timestamp and defines `known_at` as the later of source `meta.lastUpdated` and local ingestion, while retaining the raw source timestamp. | Implemented, targeted validation passed |
| Typed model generation/review with deterministic acceptance | Injected-transport generation tests, secret-free artifacts, explicit candidate-slot precision/recall/F1, and temporal-window scoring | Implemented, targeted validation passed |
| Full local fake-provider grid/resume/seal | Versioned `local-phase-a-v7` artifact: two subjects, two source cases plus 18 opaque materialized adversarial variants, two models and nine conditions; 10 construction/review + 360 solver calls; resumed run uses 0 calls. Durable output/error ledgers prevent double billing if a crash precedes a checkpoint write. Solver requests use the frozen v2 system prompt and strict prediction schema, including explicit escalation. The sealed validator checks the full grid, per-cell artifacts, declared models/conditions, prompt/schema hashes, provenance, tampering, solver/construction/variant/temporal-boundary metric denominators, and credential/header markers. | Implemented, targeted validation passed |
| Phase-B execution boundary | Exact-model probe records family, JSON-contract support, usage availability, retries, non-streaming behavior, endpoint hash, and a closed requested→reported ID mapping. The initial real probe failed closed on namespace-stripped reported IDs before benchmark start; two bounded diagnostics established the exact short IDs. Arbitrary aliases, requested-ID echoes, and fallbacks remain rejected. Replacement-freeze schema records the initial zero-call proof, superseded SHA, reason, and three post-freeze diagnostic calls. The replacement canonical probe passed both mappings in one attempt each with no fallback. | Complete; canonical probe artifact valid |
| Distinct baseline packets and comparator fidelity | Long-context, Naive RAG, and LWW adapters/cards/tests; the BTSA packet invokes an independent bitemporal arbitration adapter with registry, capabilities, mapping, deviations, and fidelity tests. Primary-source review confirms Algorithm 1 and published constants but no pinned extraction/equivalence/refinement/constraint implementation, calibration split, or official code revision. | Mechanism integration complete; no faithful end-to-end BTSA reproduction claim is supportable from available assets |
| Adversarial, property, leakage, secret gates | DSL property, leak/tamper, full tracked-repository secret scan, and hash-verified deterministic materialization of every minimal adversarial manifest into opaque case IDs, separate gold, and all nine solver packets. Five assignment values in tracked history are explicitly redacted; scanner tests preserve ordinary `risk-...` paths and reject a redaction marker with appended material. The knowledge-time ablation removes known-time metadata only from evidence visible at cutoff and cannot expose late evidence. | Local gates complete; real application-boundary adversarial execution remains blocked |
| Naming and docs validation | Naming/protocol tests and `make docs-check` passed | Implemented, targeted validation passed |
| Root lint/type/test gates | Targeted lint/mypy pass; the full API suite exits 0 with 1,357 passed and 1 skipped. After repairing contract drift without enabling runtime fallback or request-selected providers, the full ML suite exits 0 with 1,500 passed and 2 skipped. Post-fix root reruns report 635 Ruff findings and 332 mypy errors across 43 API/ML files. | API and ML service gates passed; root lint and root type gates fail on repository-wide debt |
| Clean SHA and sealed `implementation_freeze.json` | Replacement freeze `20543ed6cef6d9d1f2189bbb77a1266fcf21ae8d` is `COMPLETE` and `VALID`, freezes 18 inputs, preserves the initial zero-call proof, and discloses three diagnostic calls before replacement. It supersedes `154ee41064c936c1c599c26a70a8460840cce304`; the historical v1 seal was valid at its own SHA but the stricter v2 mapping validator intentionally rejects its old full-ID fake outputs. Repository-wide credential remediation remains complete. | Complete; replacement seal and artifact secret scan passed |
| Bounded Phase-B benchmark | Canonical probe SHA-256 `125cbdf9f1e8e52cd19120c9e59700e6dbec040afff6e913f6d10b4d1a1cbca8`; benchmark manifest binds to the replacement freeze and probe. Two controlled synthetic source fixtures plus 18 adversarial variants produce 360/360 solver cells over two models and nine conditions with zero solver/provider errors. Four model-assisted construction requests ended in two deterministic `GlhsInvariantError` rejections; the solver grid still completed. The complete artifact validates, passes secret scanning, and resumes with an injected no-call transport using zero requests. | Complete; 364 benchmark requests, 369 disclosed external calls across the full initial-probe/diagnostic/replacement-probe/benchmark lifecycle |
| Phase-B outcome | Lifecycle accuracy `231/360`, evidence `215/360`, timeliness `0/360`, escalation `169/360`, and all-axes exact `0/360`. Adversarial escalation is `134/324`; missed conflicts are `32/36`, missed loops `36/144`, and both two-snapshot time-boundary families are `0/36`. Because every arm has zero exact accuracy, no primary-endpoint winner is supported. | Negative/mixed synthetic software result; no superiority or clinical claim |
| Corrective iteration after error analysis | The first run exposed general evaluator defects: timeliness gold diverged from production decisive-time/grace semantics; due/grace and contradiction relation were absent from solver packets; predicate generation lacked its allowed source-grounded projection; only runner surfaces, not transitive benchmark code, were frozen; and the two-event cohort made every condition information-sufficient. Local corrections are covered by 57 evaluator tests, Ruff, mypy, runtime-alignment tests, and an eight-subject/44-case controlled mechanism cohort. | Local corrective Phase A in progress; prior Phase-B artifact remains immutable; zero new router calls until replacement freeze |

## Claim limits

- Synthetic fixtures validate software behavior, not clinical safety, utility, or
  validity.
- `synthetic_protocol_oracle` is not clinical adjudication; all such fields are
  `NOT_RUN`.
- BTSA remains mechanism-mapped only. It must not be presented as a faithful
  implementation or used for direct superiority/equivalence claims.
- Transition accuracy is measured only on minimal two-snapshot valid-time and
  known-time boundary pairs. Longer longitudinal replay is `NOT_MEASURED`.
- Real-EHR, clinical review, and isolated live-adversarial execution remain
  `BLOCKED_EXTERNAL / NOT_RUN`.
- The two source records are controlled R4 fixtures, not the available Synthea
  archive. The 20-case grid must not be described as Synthea evidence.
- The provider-reported total-token field is retained verbatim even though it
  does not equal prompt plus completion tokens; provider accounting semantics
  were not independently verified.

## Remaining external gates

1. Run real-EHR and clinician-adjudicated evaluation under the required data,
   governance, and review approvals.
2. Run isolated deployed-boundary and PostgreSQL-specific adversarial checks.
3. Resolve or separately govern the pre-existing repository-wide Ruff/mypy debt.
4. Add longer longitudinal replay before making temporal-transition claims.
