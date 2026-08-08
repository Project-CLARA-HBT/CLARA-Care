# Runbook: Regulatory compliance (`COMPLIANCE_*`) staged enablement

Spec: `regulatory-compliance` · Task 9 (final checkpoint / staged enablement per
environment).

This runbook covers the staged, per-environment enablement of the regulatory
compliance layer that operationalizes **AI Law No. 134/2025/QH15** and **Decree
13/2023/NĐ-CP (PDPD)**. Every capability ships **dark, additive, and
feature-flagged**; with all flags off the system is byte-equivalent to the
pre-feature baseline (Requirement 8.1, 8.2; design Property P6). Enablement is a
per-environment configuration change with no schema or data implications at flip
time — the additive migration (`20260415_0011_compliance.py`) has already been
applied and is reversible independently of the flags.

The model is always: **enable in staging → verify per-property suite (P1–P10) +
flags-off regression → flip in production → rollback if needed.**

## Summary — feature flags (all default OFF)

Backend flags are read in `services/api/src/clara_api/core/config.py`. Web
surface flags are read client-side from `NEXT_PUBLIC_COMPLIANCE_*`. A backend
flag governs enforcement/data; the matching web flag governs whether the
corresponding surface renders. Enable them as a pair where both exist.

| Capability | Backend flag | Web flag | Default |
| --- | --- | --- | --- |
| Model / version disclosure in response envelope | `COMPLIANCE_MODEL_DISCLOSURE_ENABLED` | — | `false` |
| AI Transparency Notice + acknowledgement gate | `COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED` (+ `COMPLIANCE_TRANSPARENCY_NOTICE_VERSION`, default `2026-03-v1`) | `NEXT_PUBLIC_COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED` | `false` |
| Granular consent enforcement + Consent Center | `COMPLIANCE_GRANULAR_CONSENT_ENABLED` | `NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED` | `false` |
| Cross-border transfer gate | `COMPLIANCE_CROSS_BORDER_GATING_ENABLED` | — | `false` |
| DSAR self-service + admin queue | `COMPLIANCE_DSAR_ENABLED` | `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` | `false` |
| Admin compliance-records surface | `COMPLIANCE_RECORDS_ADMIN_ENABLED` | — | `false` |
| Scheduled retention / anonymization job | `COMPLIANCE_RETENTION_JOB_ENABLED` | — | `false` |

When a flag is off, its endpoint returns a "feature disabled" shape and its
enforcement is skipped, exactly reproducing today's behavior. Flags are read
from config/env at service start, so flipping one means updating the
environment's config and restarting/redeploying the affected service — there is
no in-request toggle.

## Per-property suite (P1–P10)

These are the targeted, fast suites that gate each enablement. **Do not run the
full or slow test suite** — run only the files below.

| Property | What it asserts | Test |
| --- | --- | --- |
| P1 | Consent ledger is append-only; `has_consent` reflects latest event | `services/api/tests/compliance/test_consent_ledger.py` |
| P2 | Cross-border gate soundness (no identifiable payload offshore without consent) | `services/api/tests/compliance/test_service_facade.py` (outbound_guard) |
| P3 | DSAR export completeness / subject isolation | `services/api/tests/compliance/test_dsar_export.py` |
| P4 | Deletion irreversibility + audit survival (transactional) | `services/api/tests/compliance/test_dsar_delete.py` |
| P5 | No-PII compliance logs | `services/api/tests/compliance/test_no_pii_logs.py` |
| P6 | Flags-off equivalence (baseline) | `services/api/tests/compliance/test_harness.py`, `test_service_facade.py` |
| P7 | RBAC on records / admin DSAR queue | `services/api/tests/compliance/test_records_rbac.py`, `apps/web/app/admin/dsar/page.test.tsx` |
| P8 | Disclosure correctness (`is_fallback` iff `local-synth-*`) | `services/api/tests/compliance/test_model_disclosure.py` |
| P9 | Transparency gate (no medical content before ack when flag on) | `apps/web/components/compliance/transparency-notice-gate.test.tsx` |
| P10 | Consent Center CSRF + contract | `apps/web/lib/compliance.test.ts` |

Run the API per-property suite (targeted, fast):

```
.venv-api/bin/python -m pytest \
  services/api/tests/compliance/test_consent_ledger.py \
  services/api/tests/compliance/test_service_facade.py \
  services/api/tests/compliance/test_dsar_export.py \
  services/api/tests/compliance/test_dsar_delete.py \
  services/api/tests/compliance/test_no_pii_logs.py \
  services/api/tests/compliance/test_harness.py \
  services/api/tests/compliance/test_records_rbac.py \
  services/api/tests/compliance/test_model_disclosure.py \
  -p no:randomly -q
```

Run the web property suite (targeted):

```
# from apps/web
npx vitest run \
  components/compliance/transparency-notice-gate.test.tsx \
  app/admin/dsar/page.test.tsx \
  lib/compliance.test.ts
```

### Flags-off regression gate

Before and after any enablement, confirm the flags-off baseline still holds.
With every `COMPLIANCE_*` flag at its default `false`, the consent gate, ML
proxy, response envelope, and all compliance endpoints behave exactly as the
pre-feature system. The standing assertion lives in
`services/api/tests/compliance/test_harness.py` (config-layer baseline,
`assert_flags_off_baseline`) and `test_service_facade.py` (every flag-gated
method is a no-op when its flag is off). Any change to these files or a failure
here is a hard stop — do not promote.

## Prerequisites (one-time, before any environment)

- Spec tasks 1–8 complete (foundations + migration, transparency + disclosure,
  granular consent, cross-border gate, DSAR, records/retention, legal pages).
- Migration `20260415_0011_compliance.py` applied to the target environment, and
  its upgrade/downgrade round-trip verified (additive tables `dsar_requests`,
  `compliance_events`, `transfer_assessments`; widened `user_consents.purpose`).
- `TransferRegistry` seeded with the offshore processors (YEScale DeepSeek LLM +
  embedding endpoints) with jurisdiction / purpose / TIA reference.
- Governance docs present under `docs/compliance/` (`ropa.md`,
  `risk-management-file.md`, `dpia.md`, `transfer-impact-assessments.md`,
  `incident-log.md`) — the admin records manifest is assembled from these.
- Static checks clean: `ruff check services/api/src/clara_api/compliance` and no
  IDE diagnostics on the compliance backend module, `apps/web/lib/compliance.ts`,
  `apps/web/app/account/{consent,data}/page.tsx`,
  `apps/web/app/admin/dsar/page.tsx`, `apps/web/app/legal/privacy/page.tsx`.
- Web lint clean on the compliance web surfaces (`next lint`).

## Staged enablement order

Enable in the order below — lowest user-facing/clinical risk first. Each step is
gated on its property check(s) plus the flags-off regression gate. **Complete
each step fully in staging, then production, before starting the next.** Do not
batch multiple flags into a single flip.

1. `COMPLIANCE_MODEL_DISCLOSURE_ENABLED` — additive envelope field only (P8).
2. `COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED` (+ web flag) — user-visible notice
   gate (P9). Set `COMPLIANCE_TRANSPARENCY_NOTICE_VERSION` deliberately; bumping
   it forces re-acknowledgement on next access (Requirement 1.6).
3. `COMPLIANCE_GRANULAR_CONSENT_ENABLED` (+ web flag) — purpose-typed consent
   enforcement; enable only after the Consent Center ships and P1 + P10 pass.
4. `COMPLIANCE_CROSS_BORDER_GATING_ENABLED` — offshore-call gating; enable only
   after the in-country / local fallback is verified and P2 + P5 pass.
5. `COMPLIANCE_DSAR_ENABLED` (+ web flag) and `COMPLIANCE_RECORDS_ADMIN_ENABLED`
   — DSAR self-service, admin queue, and records manifest; enable after the
   admin queue RBAC is verified and P3 + P4 + P7 pass.
6. `COMPLIANCE_RETENTION_JOB_ENABLED` — scheduled anonymization; enable last,
   after the ops cron under `scripts/ops/` is verified and P5 passes.

## Per-flag procedure

Repeat the following for **each** flag, in the order above.

### Stage 1 — Enable in staging

1. In the **staging** environment, set the backend flag (and its `NEXT_PUBLIC_*`
   web counterpart where one exists) to `true`. For the transparency notice,
   also confirm `COMPLIANCE_TRANSPARENCY_NOTICE_VERSION` is the intended value.
2. Restart/redeploy the affected service(s) so the new config is read at start
   (API for backend flags; web app for `NEXT_PUBLIC_*` flags).
3. Confirm activation: the corresponding endpoint now returns its enabled shape
   (not `{"enabled": false}`), and the surface renders. For cross-border gating,
   confirm a no-PII transfer event is recorded on outbound decisions.

### Stage 2 — Verify in staging

1. Run the per-property suite entry for this flag (table above) plus the
   flags-off regression gate (`test_harness.py`, `test_service_facade.py`).
2. Confirm zero PII in any compliance log or telemetry for the newly active path
   (P5) — `compliance_events.meta_json` and DSAR rows carry counts/flags and
   opaque refs only, never query text, drug lists, names, or emails.
3. Confirm guardrails are intact and unchanged: legal hard-guard
   (no prescribing/diagnosis/dosage), emergency fast-path, clinician-review
   directive, FIDES CRITICAL block, RBAC, and CSRF on mutating endpoints
   (Requirement 5, 8.3–8.6).
4. **Promotion gate:** proceed only when the property check(s) for this flag and
   the flags-off regression gate pass with zero failures and no guardrail
   regression. Any failure is a hard stop.

### Stage 3 — Flip on in production

1. After staging passes the promotion gate, set the same flag(s) to `true` in
   the **production** environment.
2. Restart/redeploy the affected production service(s).
3. Confirm activation in production via the enabled endpoint shape / rendered
   surface, and confirm no-PII telemetry on the new path.
4. Monitor early production traffic for the newly enabled capability:
   - disclosure/notice: no rise in errors; envelope/notice renders correctly;
   - consent/cross-border: consent-absent paths degrade to in-country/local
     (labeled degraded), no identifiable payload leaves offshore (P2);
   - DSAR/records: admin-only access enforced (401/403 for non-admin, P7);
   - retention: the scheduled job anonymizes/deletes expired rows and writes
     audit rows, with no PII (P5) and append-only audit survival (P4).

### Rollback

Rollback is a single config change per flag with no data/schema implications
(the layer is additive and the legacy path is always preserved):

1. In the affected environment, set the flag (and its `NEXT_PUBLIC_*`
   counterpart) back to `false`.
2. Restart/redeploy the affected service(s).
3. With the flag off, the corresponding endpoint returns the inert
   `{"enabled": false}` shape and enforcement is skipped — behavior reverts to
   exact pre-feature baseline (Requirement 8.2; Property P6, verified by
   `test_harness.py` / `test_service_facade.py`).

Flags are independent: rolling one back does not affect the others. No
migration, data backfill, or cleanup is required to roll back. If a deeper
rollback is ever needed, the additive migration `20260415_0011_compliance.py`
has a reversible downgrade, but flipping flags off is the normal, sufficient
mitigation and requires no clinical-code redeploy.

## Notes

- The retention job (`COMPLIANCE_RETENTION_JOB_ENABLED`) is the only flag that
  performs irreversible data changes (anonymization/deletion). Enable it last,
  verify the cron under `scripts/ops/` in staging against a non-production
  dataset first, and confirm append-only audit rows survive (P4) before the
  production flip. Its summary must contain counts only; it clears expired PHR
  and medicine-cabinet health data, query/response logs and auth-token hashes
  according to `docs/compliance/ropa.md`.
- Bumping `COMPLIANCE_TRANSPARENCY_NOTICE_VERSION` is itself a user-visible
  change: it forces re-acknowledgement on next access. Treat a version bump like
  a re-enablement — verify P9 in staging before applying it to production.
