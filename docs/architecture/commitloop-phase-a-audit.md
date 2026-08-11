# CommitLoop Phase-A completion audit

Status date: 2026-08-11. This audit is evidence-based and does not authorize
Phase B. `router_calls_before_freeze` remains zero.

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
| Phase-B execution boundary | Exact-model probe records family, JSON-contract support, usage availability, retries, non-streaming behavior, endpoint hash, and a closed requested→reported ID mapping. The initial real probe failed closed on namespace-stripped reported IDs before benchmark start; two bounded diagnostics established the exact short IDs. Arbitrary aliases, requested-ID echoes, and fallbacks remain rejected. Replacement-freeze schema records the initial zero-call proof, superseded SHA, reason, and three post-freeze diagnostic calls. | Mapping repair implemented locally; all external calls stopped pending replacement freeze |
| Distinct baseline packets and comparator fidelity | Long-context, Naive RAG, and LWW adapters/cards/tests; the BTSA packet invokes an independent bitemporal arbitration adapter with registry, capabilities, mapping, deviations, and fidelity tests. Primary-source review confirms Algorithm 1 and published constants but no pinned extraction/equivalence/refinement/constraint implementation, calibration split, or official code revision. | Mechanism integration complete; no faithful end-to-end BTSA reproduction claim is supportable from available assets |
| Adversarial, property, leakage, secret gates | DSL property, leak/tamper, full tracked-repository secret scan, and hash-verified deterministic materialization of every minimal adversarial manifest into opaque case IDs, separate gold, and all nine solver packets. Five assignment values in tracked history are explicitly redacted; scanner tests preserve ordinary `risk-...` paths and reject a redaction marker with appended material. The knowledge-time ablation removes known-time metadata only from evidence visible at cutoff and cannot expose late evidence. | Local gates complete; real application-boundary adversarial execution remains blocked |
| Naming and docs validation | Naming/protocol tests and `make docs-check` passed | Implemented, targeted validation passed |
| Root lint/type/test gates | Targeted lint/mypy pass; the full API suite exits 0 with 1,357 passed and 1 skipped. After repairing contract drift without enabling runtime fallback or request-selected providers, the full ML suite exits 0 with 1,500 passed and 2 skipped. Post-fix root reruns report 635 Ruff findings and 332 mypy errors across 43 API/ML files. | API and ML service gates passed; root lint and root type gates fail on repository-wide debt |
| Clean SHA and sealed `implementation_freeze.json` | Initial freeze `154ee41064c936c1c599c26a70a8460840cce304` truthfully records zero prior router calls. It is superseded after three post-freeze probe/diagnostic calls exposed the reported-ID contract gap; no benchmark ran. Replacement-freeze support prevents those calls from being reset or hidden and expands the frozen input inventory to the provider/probe/benchmark code. Repository-wide credential remediation remains complete. | Pending clean-SHA rerun and replacement seal; no further external calls allowed until then |

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

## Conditions before Phase B

1. Resolve the clean-worktree/committed-SHA boundary without discarding user
   changes.
2. Record the existing root lint/type debt separately from the passing,
   task-scoped frozen surface; do not misstate either result.
3. Complete the remaining local/API assurance evidence and create a valid
   implementation freeze with exact command results and zero router calls.
4. Only then run the bounded exact-model provider probe.
