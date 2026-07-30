# Runbook: CLARA Research enhancement (`RESEARCH_*`) staged rollout

Spec: `clara-research` · Task 22 (final checkpoint / staged enablement).

This runbook covers the staged enablement of the CLARA Research enhancement:
agentic query decomposition + bounded gap-fill, recency/trust-tier ranking,
PICO framing, GRADE certainty labels, consensus + conflicting-evidence,
claim-level NLI verdicts, claim-to-study traceability + Citation Registry,
clarifying questions, progressive disclosure, role-adaptive output,
consent-gated personalization, export/share, the Vietnamese golden-set quality
gate, durable owner-isolated uploads, and role-gated telemetry. Every behavior
ships dark behind a default-off `RESEARCH_*` flag and is additive. It describes
enabling in staging, verifying guardrail preservation and the golden-set
quality gate, the production flip, and rollback.

## Summary

All new research behavior ships dark behind default-off feature flags. When
every flag is off the research pipeline and endpoints produce byte-for-byte
identical output to the pre-enhancement baseline (Requirement 20.2; design
Property 35 — flags-off legacy equivalence). Flags are read from config/env at
service start, so flipping one means updating the environment config and
restarting/redeploying the affected service — there is no in-request toggle.

ML flags (`services/ml/src/clara_ml/config.py`):

| Env var                                       | Default | Behavior when on                                  |
| --------------------------------------------- | ------- | ------------------------------------------------- |
| `RESEARCH_QUERY_DECOMPOSITION_ENABLED`        | `false` | Sub-question decomposition (deep / deep_beta)     |
| `RESEARCH_GAP_FILL_ENABLED`                   | `false` | Bounded gap-fill retrieval passes                 |
| `RESEARCH_GAP_FILL_MAX_PASSES`                | `2`     | ML-side gap-fill pass bound (0–8)                 |
| `RESEARCH_RECENCY_TRUST_RANKING_ENABLED`      | `false` | Composite trust-tier/recency ranking + surfacing  |
| `RESEARCH_PICO_ENABLED`                        | `false` | PICO framing with named-rejection semantics       |
| `RESEARCH_EVIDENCE_SIGNALS_ENABLED`            | `false` | Provenance-only source metadata for verified claims |
| `RESEARCH_GRADE_ENABLED`                       | `false` | Deprecated compatibility key; does not enable GRADE output |
| `RESEARCH_CONSENSUS_ENABLED`                   | `false` | Support/contrast/neutral counts + conflict section|
| `RESEARCH_CLAIM_TRACE_ENABLED`                 | `false` | Traced claims + Citation Registry appendix        |
| `RESEARCH_ROLE_ADAPTIVE_OUTPUT_ENABLED`        | `false` | Exclusive normal/researcher/doctor output profiles|

API flags (`services/api/src/clara_api/core/config.py`):

| Env var                                       | Default | Behavior when on                                  |
| --------------------------------------------- | ------- | ------------------------------------------------- |
| `RESEARCH_API_GAP_FILL_HARD_MAX`              | `3`     | API hard ceiling on gap-fill passes (1–10)        |
| `RESEARCH_CLARIFYING_QUESTIONS_ENABLED`       | `false` | `POST /research/clarify` + UI start gate          |
| `RESEARCH_ROLE_GATED_TELEMETRY_ENABLED`       | `false` | Role-gated, PII-stripped telemetry rails          |
| `RESEARCH_PERSONALIZATION_ENABLED`            | `false` | Consent-gated PHR/cabinet personalization         |
| `RESEARCH_EXPORT_ENABLED`                     | `false` | `POST .../export?format=md\|docx\|pdf`            |
| `RESEARCH_SHARE_ENABLED`                      | `false` | Read-only share via `WorkspaceConversationShare`  |
| `RESEARCH_QUALITY_GATE_ENABLED`               | `false` | Golden-set regression gate in CI                  |
| `RESEARCH_DURABLE_UPLOADS_ENABLED`            | `false` | Durable, owner-isolated uploaded files            |
| `RESEARCH_UPLOAD_OBJECT_STORE_URL`            | `""`    | Object-store backend URL for durable uploads      |

The web mobile deep-mode surface is additionally gated by the
`RESEARCH_MOBILE_DEEP_ENABLED` remote-config flag on the mobile client.

### Evidence-release boundary

The evidence-release boundary is not an optional presentation flag. Both the
synchronous `POST /api/v1/research/tier2` route and the durable
`POST /api/v1/research/tier2/jobs` worker run the same deterministic quality
gate after ML verification and attribution. If an answer has no resolvable
citations, no retrieved evidence, zero support, or any unsupported/
contradicted claim, CLARA preserves its citation and verifier artifacts but
replaces the clinical conclusion with an abstention. This applies regardless
of whether optional Research presentation flags are enabled.

End-user views show a plain-language verification state and evidence count,
never an uncalibrated verifier confidence percentage, raw FIDES labels, or
chain-of-thought. Detailed verifier diagnostics stay in the appropriate
professional/admin rails.

## Prerequisites

- Spec tasks 1–21 complete (shared flag/payload foundations through the
  guardrail + backward-compatibility preservation suite).
- Static checks clean (verified at this checkpoint):
  - `ruff check services/api/src` → all checks passed
  - `ruff check services/ml/src` → all checks passed
  - No editor/compiler diagnostics on the touched API, ML, web, and mobile
    source files.
- All `RESEARCH_*` flags confirmed declared and **default-off** in both
  `services/ml/src/clara_ml/config.py` and
  `services/api/src/clara_api/core/config.py`.
- Guardrail-preservation suite green (`services/ml/tests/safety`,
  `services/api/tests` guardrail tests): DDI floor, dosage/legal block, consent
  gate, emergency fast-path, FIDES CRITICAL block, and decision-support
  disclaimer all in force (Requirement 20.1, 20.5).

> Performance note: do **not** run the full/slow research pipeline test path as
> part of this gate — it can run for hours. Verify with diagnostics + `ruff` and
> targeted fast test files only.

## Stage 1 — Enable in staging

1. In the **staging** API and ML service environments, enable the desired
   `RESEARCH_*` flags. Roll out in additive waves rather than all at once, e.g.:
   - Wave A (retrieval quality): `RESEARCH_QUERY_DECOMPOSITION_ENABLED`,
     `RESEARCH_GAP_FILL_ENABLED`, `RESEARCH_RECENCY_TRUST_RANKING_ENABLED`.
   - Wave B (evidence presentation): `RESEARCH_PICO_ENABLED`,
     `RESEARCH_EVIDENCE_SIGNALS_ENABLED`, `RESEARCH_CONSENSUS_ENABLED`,
     `RESEARCH_CLAIM_TRACE_ENABLED`, `RESEARCH_ROLE_ADAPTIVE_OUTPUT_ENABLED`.
   - Wave C (surface/IO): `RESEARCH_CLARIFYING_QUESTIONS_ENABLED`,
     `RESEARCH_ROLE_GATED_TELEMETRY_ENABLED`, `RESEARCH_PERSONALIZATION_ENABLED`,
     `RESEARCH_EXPORT_ENABLED`, `RESEARCH_SHARE_ENABLED`,
     `RESEARCH_DURABLE_UPLOADS_ENABLED` (+ `RESEARCH_UPLOAD_OBJECT_STORE_URL`).

`RESEARCH_EVIDENCE_SIGNALS_ENABLED` is deliberately provenance-only: it emits
the retrieved source id, source type, internal authority band, publication date,
and whether the claim directly resolved to that source. It must not be described
as GRADE, evidence certainty, recommendation strength, or a treatment decision.
`RESEARCH_GRADE_ENABLED` remains accepted only to avoid breaking old environment
files and has no runtime effect. Roll back the new output by setting
`RESEARCH_EVIDENCE_SIGNALS_ENABLED=false`; no data migration is required.
2. For durable uploads, provision and set `RESEARCH_UPLOAD_OBJECT_STORE_URL`
   before enabling `RESEARCH_DURABLE_UPLOADS_ENABLED`. If the backend is
   unreachable while the flag is on, uploads surface a 503 (no silent data loss);
   confirm the backend is healthy first.
3. Restart/redeploy the API and ML services so the new config is read at start.
4. Confirm activation via trace/telemetry on a `deep`/`deep_beta` request: the
   enabled stages (decomposition, gap-fill pass count, ranking, PICO, GRADE,
   consensus, traced claims) should appear in the result payload; with flags off
   those keys are omitted.

## Stage 2 — Verify guardrail preservation + golden-set quality gate (staging)

Before touching production, confirm both that nothing regressed and that
retrieval quality holds.

### Guardrail-preservation checks (must hold with zero violations)

- DDI severity floor still enforced; CareGuard DDI analysis unchanged with its
  optional layers off (Requirement 20.1).
- No dosage prescription / no definitive diagnosis; legal/scope block intact.
- Consent gate enforced: personalization incorporated **only** with
  `personal_mode` + mode ∈ {deep, deep_beta} + consent granted; no consent runs
  without personalization (not an error). `personal_mode` + fast is rejected
  (Requirement 15.1–15.3; design Properties 29, 30).
- Emergency / acute queries take the emergency fast-path; out-of-scope queries
  refuse before any retrieval/synthesis (Requirement 10.5; Property 20).
- FIDES CRITICAL unsupported-claim block and verdict-tightening preserved
  (Requirement 10.3, 10.4; Properties 18, 19).
- Decision-support disclaimer present in every role profile when the asset is
  available (Requirement 14.5, 20.5; Property 28).
- Telemetry is PII-free and role-gated; fail-closed when role cannot be
  evaluated (Requirement 3.x, 15.4; Properties 6, 7). Mobile mirrors the gate
  and blocks the job when role-gating cannot be evaluated (Requirement 19.4).
- Job caps preserved: per-user active ≤ 5, global pending ≤ 200; RBAC matrix
  unchanged (Requirement 20.3, 20.4; Properties 36, 37).

### Golden-set quality gate

1. Enable `RESEARCH_QUALITY_GATE_ENABLED` in the staging/CI environment.
2. Run the Vietnamese golden-set harness (`services/ml` `research_quality` +
   `golden_set_vi`). It computes `recall@k`, `faithfulness`,
   `citation_accuracy`, `unsupported_claim_rate`, and `refusal_compliance`
   (Requirement 17.1, 17.2).
3. The gate **passes** only when `recall@k` is at or above the recorded legacy
   baseline and every other metric meets its configured threshold; each metric
   is reported alongside its threshold (Requirement 17.3–17.5; design
   Property 32). Investigate any breach before promoting.

### Promotion gate

Proceed to production only when guardrail-preservation checks show **zero**
violations and the golden-set quality gate passes (recall@k ≥ baseline, all
other metrics within threshold). Any guardrail violation or quality-gate failure
is a hard stop — do not promote.

## Stage 3 — Flip on in production

1. After staging passes the promotion gate, enable the same `RESEARCH_*` flags
   (in the same additive waves) in the **production** API and ML environments.
   Provision `RESEARCH_UPLOAD_OBJECT_STORE_URL` before
   `RESEARCH_DURABLE_UPLOADS_ENABLED`.
2. Restart/redeploy the production API and ML services.
3. Confirm via production telemetry that enabled stages appear and that
   telemetry remains PII-free and role-gated.
4. Monitor early production `deep`/`deep_beta` traffic for:
   - gap-fill pass counts staying within `RESEARCH_GAP_FILL_MAX_PASSES` and the
     API hard ceiling `RESEARCH_API_GAP_FILL_HARD_MAX`
   - no rise in guardrail blocks bypassed, no fabricated citations, every anchor
     resolving into the Citation Registry
   - no regression in refusal compliance or unsupported-claim rate
   - upload durability/owner-isolation behaving (non-owned `file_id` → 403)
5. Keep `RESEARCH_QUALITY_GATE_ENABLED` on in CI so future changes are gated
   against the recorded baseline.

## Rollback

Rollback is a per-flag env change with no data/schema implications for the
pipeline behavior (all work is additive and the legacy path is preserved):

1. In the affected environment set the offending `RESEARCH_*` flag(s) back to
   `false` (or, for a full rollback, all of them).
2. Restart/redeploy the affected service.
3. With the flags off, the pipeline and endpoints revert to exact
   pre-enhancement behavior (Requirement 20.2; design Property 35 — flags-off
   legacy equivalence). New payload keys are omitted and legacy request/response
   shapes are preserved.

Notes:

- Disabling `RESEARCH_DURABLE_UPLOADS_ENABLED` reverts uploads to the in-memory
  fallback backend; the `research_uploaded_files` table and any persisted rows
  remain and are simply no longer read (no destructive migration required to
  roll back).
- `RESEARCH_API_GAP_FILL_HARD_MAX` and `RESEARCH_GAP_FILL_MAX_PASSES` are bounds,
  not on/off switches; lowering them tightens the budget without disabling the
  feature.
