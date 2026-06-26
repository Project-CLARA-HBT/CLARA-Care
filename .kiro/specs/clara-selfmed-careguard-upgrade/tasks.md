# Implementation Plan: CLARA Self-Med + DDI + CareGuard Upgrade

## Overview

This plan upgrades Self-Medication, DDI, and CareGuard to production-grade
quality, additively and behind feature flags (all new flags default OFF). Tasks
are ordered so each is independently shippable and verifiable, the highest-risk
safety invariants (severity floor, emergency fast-path, projection purity) are
pinned early, and every task that touches a shared path adds a regression test.
Every task preserves the existing consent gate, cross-border guard,
no-prescribing/no-diagnosis boundary, and no-PII telemetry.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the `services/api/tests` and `services/ml/tests` harnesses (pytest +
  hypothesis) and `apps/web/lib/careguard.test.ts` (web).
- Add a CareGuard upgrade test package; tag property tests `P1..P12` mapping to
  the design's Correctness Properties.
- A flags-off baseline fixture asserts byte-equivalence with pre-feature
  behavior (cabinet responses, ML payload, response envelope).

## Tasks

- [ ] 1. Foundations (flags + schema + test harness)
  - [ ] 1.1 Add `SELFMED_*` and `CAREGUARD_*` flags (all default false) to API + ML config; create the CareGuard-upgrade test package and flags-off baseline fixture. _Req 12.1, 12.2_
  - [ ] 1.2 Reversible Alembic migration adding nullable `brand_name`, `manufacturer`, `dosage_form`, `expiry_reminder_json` to `medicine_items`; migration round-trip test. _Req 1.2, 10.3_

- [ ] 2. Checkpoint — foundations land dark; flags-off equivalence test green. **[PBT]** P12 flags-off byte-equivalence.

- [ ] 3. Cabinet CRUD & structured persistence (Req 1, 2, 10)
  - [ ] 3.1 Dual-read/dual-write in `_to_item_response` and the create/update handlers: structured columns when `SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED` on, legacy `[meta]` note when off; legacy notes always decodable. _Req 1.2, 1.3, 1.4_
  - [ ] 3.2 Duplicate guard on `(cabinet_id, normalized_name)`, owner-scope enforcement, quantity/expiry validation. _Req 1.5, 1.6, 1.7_
  - [ ] 3.3 Normalization status + low-confidence OCR confirm gate surfaced in cabinet responses/UI; unmatched names retained as "needs review". _Req 2.1, 2.2, 2.5, 2.6_
  - [ ] 3.4 Expiry computation (expired / expiring-soon) in the cabinet summary; reminder-state persistence behind `SELFMED_EXPIRY_REMINDERS_ENABLED`. _Req 10.1, 10.2, 10.3, 10.4, 10.5_
  - [ ] 3.5 **[PBT]** P1 cabinet CRUD round-trip; **[PBT]** P2 owner isolation. _Req 1, 11.5_

- [ ] 4. DDI matcher, severity floor & source merge (Req 3, 4)
  - [ ] 4.1 Extract an explicit severity-floor helper in `_merge_drug_alerts` (max-severity per pair); keep openFDA-only message protection (INV-2) and the free-text `high` cap (INV in `drug_sources.py`). _Req 4.1, 4.2, 4.3, 4.4, 4.6_
  - [ ] 4.2 Confirm risk classification + emergency fast-path and the End_User projection (`toDdiUserView`) drop mode/fallback/`source_errors` and localize to Vietnamese. _Req 3.3, 3.4, 3.5, 3.6, 7.2_
  - [ ] 4.3 **[PBT]** P3 severity floor; **[PBT]** P4 openFDA message protection; **[PBT]** P5 free-text severity cap.
  - [ ] 4.4 **[PBT]** P6 two-medicine guard; **[PBT]** P7 projection purity; **[PBT]** P9 emergency fast-path.

- [ ] 5. Checkpoint — DDI safety invariants pinned; flags-off behavior unchanged.

- [ ] 6. Pair-indexed matcher for scale (Req 5.4)
  - [ ] 6.1 Build `dict[frozenset[str], list[InteractionRule]]` cached by rule-set version/mtime; match via C(n,2) pair lookup behind `CAREGUARD_DDI_INDEX_ENABLED`. _Req 5.4_
  - [ ] 6.2 **[PBT]** P8 index equivalence (indexed matcher == linear matcher for any rule set + medicine list).

- [ ] 7. DrugBank merge layer — provisioning, integrity & precedence (Req 5)
  - [ ] 7.1 Manifest verification + cache-by-mtime + degrade-to-curated on missing/unparseable shard; surface active rule-set version in metadata. _Req 5.3, 5.5_
  - [ ] 7.2 Author `nlp/seed_data/drugbank/README`/runbook for out-of-band provisioning via `scripts/data/drugbank_ingest.py`; curated-only default required to function without bulk shards. _Req 5.6_
  - [ ] 7.3 **[PBT]** P10 DrugBank precedence (curated severity+message preserved; DrugBank adds uncovered pairs only) and flags-off equivalence when `CAREGUARD_DRUGBANK_ENABLED` off. _Req 5.1, 5.2_

- [ ] 8. Offline / degraded-mode fallback (Req 6)
  - [ ] 8.1 Verify server local-rules fallback + `fallback_used` recording; fail-closed safe message when curated store unreadable (no fabricated all-clear). _Req 6.1, 6.2, 6.4, 6.5_
  - [ ] 8.2 Client cached last-known `DdiUserView` labeled "offline / không phải thời gian thực" behind `CAREGUARD_OFFLINE_FALLBACK_ENABLED` (web + mobile). _Req 6.3_

- [ ] 9. Mobile parity (Req 8)
  - [ ] 9.1 Mobile cabinet CRUD screen against `/api/v1/careguard/cabinet*` behind `CAREGUARD_MOBILE_CABINET_ENABLED`; preserve two-medicine guard, projection, and consent gate. _Req 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 10. Observability & analytics (Req 9)
  - [ ] 10.1 Keep coarse product events; behind `CAREGUARD_OBSERVABILITY_ENABLED` add no-PII per-source/fallback/normalization-confidence/version/latency metrics; admin-only aggregate read. _Req 9.1, 9.3, 9.4, 9.5_
  - [ ] 10.2 **[PBT]** P11 no-PII telemetry guard (adversarial drug names/identifiers dropped from persisted projection). _Req 9.2, 11.4_

- [ ] 11. Guardrail & back-compat regression (Req 7, 12)
  - [ ] 11.1 Regression tests: consent gate, cross-border guard, PHR-reconciliation, no-prescribing/no-diagnosis boundary, dosage-token stripping, clinician-review directive + PHR hedge preserved. _Req 7.1, 7.3, 7.4, 7.5, 12.6_
  - [ ] 11.2 RBAC/owner-scope on cabinet + dictionary-admin + metrics; CSRF on cookie-auth mutations. _Req 12.4, 12.5_

- [ ] 12. Final checkpoint — full flags-off regression + per-property suite (P1..P12) green; staged-enablement runbook per environment. **[PBT]** P12 re-run.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"], "dependsOn": [] },
    { "wave": 2, "tasks": ["2"], "dependsOn": ["1"] },
    { "wave": 3, "tasks": ["3", "4"], "dependsOn": ["2"] },
    { "wave": 4, "tasks": ["5"], "dependsOn": ["4"] },
    { "wave": 5, "tasks": ["6", "8"], "dependsOn": ["5"] },
    { "wave": 6, "tasks": ["7"], "dependsOn": ["6"] },
    { "wave": 7, "tasks": ["9", "10", "11"], "dependsOn": ["3", "4", "8"] },
    { "wave": 8, "tasks": ["12"], "dependsOn": ["7", "9", "10", "11"] }
  ]
}
```

## Notes

### Property → implementing test task
- P1 → 3.5 · P2 → 3.5 · P3 → 4.3 · P4 → 4.3 · P5 → 4.3 · P6 → 4.4 · P7 → 4.4 · P8 → 6.2 · P9 → 4.4 · P10 → 7.3 · P11 → 10.2 · P12 → 2 / 12

### Staged enablement order (production)
1. `SELFMED_CABINET_STRUCTURED_FIELDS` + `SELFMED_EXPIRY_REMINDERS` (user-visible, low risk)
2. `CAREGUARD_DDI_INDEX` (after index-equivalence verified)
3. `CAREGUARD_DRUGBANK_ENABLED` (existing flag; after shards provisioned + precedence verified)
4. `CAREGUARD_OFFLINE_FALLBACK` + `CAREGUARD_MOBILE_CABINET`
5. `CAREGUARD_OBSERVABILITY` (after no-PII guard green)

### Subagent assignment guidance
- API cabinet + persistence (tasks 1, 3, 11) — one writer.
- ML matcher + severity + DrugBank (tasks 4, 6, 7) — disjoint writer.
- Web/mobile clients + offline (tasks 8.2, 9) — disjoint writer.
- Observability (task 10) — independent.

### Preserved guardrails (must never regress)
No prescribing / no definitive diagnosis / no personal dosage · DDI severity
floor · openFDA cannot override curated Vietnamese message · emergency fast-path
· consent gate · cross-border transfer guard · no-PII telemetry · RBAC + CSRF.
