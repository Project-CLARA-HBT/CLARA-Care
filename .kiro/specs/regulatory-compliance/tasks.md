# Implementation Plan: Regulatory Compliance (AI Law 134/2025 + PDPD 13/2023)

## Overview

This plan implements the compliance layer additively and behind feature flags
(all default OFF). Tasks are ordered so each is independently shippable and
verifiable, and so the highest legal-risk gaps (transparency, consent,
cross-border transfer, DSAR) land first. Every task preserves existing
guardrails and adds a regression test where it touches a shared path.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing `services/api/tests` harness (pytest + hypothesis).
- Add a `compliance` test package; tag property tests `P1..P10` mapping to the
  design's Correctness Properties.
- A flags-off baseline fixture asserts byte-equivalence with pre-feature behavior.

## Tasks

- [x] 1. Foundations (schema + flags + service skeleton)
  - [x] 1.1 Add `COMPLIANCE_*` flags to `services/api/.../config.py` (all default false) + test harness package.
  - [x] 1.2 Alembic migration `20260415_0011_compliance.py`: `dsar_requests`, `compliance_events`, `transfer_assessments`; widen `user_consents.purpose`. Reversible downgrade. Migration round-trip test.
  - [x] 1.3 `ComplianceService` facade with `has_consent`, `record_event` (no-PII projection), and flag-aware no-ops.
  - [x] 2. Checkpoint — foundations land dark, flags-off equivalence test green.

- [x] 3. AI Transparency & model disclosure (Req 1)
  - [x] 3.1 `AiTransparencyNotice` versioned content (vi/en) + `GET/POST .../transparency-notice[/ack]`.
  - [x] 3.2 Response-envelope `ai_disclosure` from `model_used` (fallback iff `local-synth-*`); gated by `COMPLIANCE_MODEL_DISCLOSURE_ENABLED`. Property P8.
  - [x] 3.3 Web notice gate in authenticated layout; Property P9 (no medical content before ack when flag on).

- [x] 4. Granular consent + Consent Center (Req 2)
  - [x] 4.1 Purpose enum + `grant`/`withdraw`/`has_consent` append-only ledger. Property P1.
  - [x] 4.2 Wire `has_consent` into personalization/research/sharing call sites behind flag.
  - [x] 4.3 Web Consent Center (`/account/consent`) with per-purpose toggles; CSRF on mutations. Property P10.

- [x] 5. Cross-border transfer gate (Req 4)
  - [x] 5.1 `TransferRegistry` seeded with YEScale DeepSeek + embedding processors (jurisdiction/purpose/TIA ref).
  - [x] 5.2 `outbound_guard(user)` consulted by ML proxy; consent-absent ⇒ in-country/local degrade. Property P2.
  - [x] 5.3 No-PII transfer event logging. Property P5.

- [x] 6. DSAR self-service + admin queue (Req 3)
  - [x] 6.1 `DsarService.request` (append-only log) + acknowledgement + due-date tracking.
  - [x] 6.2 `export(user)` machine-readable bundle from user's own rows. Property P3.
  - [x] 6.3 `delete(user)` irreversible anonymization + audit survival. Property P4 (transactional).
  - [x] 6.4 Web DSAR surface (`/account/data`) + admin queue (RBAC). Property P7.

- [ ] 7. Records, risk management & retention (Req 6, 7)
  - [x] 7.1 Author `docs/compliance/`: `ropa.md`, `risk-management-file.md`, `dpia.md`, `transfer-impact-assessments.md`, `incident-log.md`.
  - [-] 7.2 `GET /compliance/records` admin manifest (RBAC). Property P7.
  - [~] 7.3 `RetentionPolicy` + scheduled anonymization job under `scripts/ops/` (flag-gated).
  - [~] 7.4 No-PII CI guard test for compliance logs. Property P5.

- [ ] 8. Privacy-policy + legal-page updates
  - [~] 8.1 Extend `apps/web/app/legal/privacy` with processor list + cross-border disclosure + DSAR instructions.
  - [~] 8.2 Add AI-system transparency section referencing Law 134/2025 classification.

- [~] 9. Final checkpoint — full flags-off regression + per-property suite green; runbook for staged enablement per environment.

## Notes

### Property → implementing test task
- P1 → 4.1 · P2 → 5.2 · P3 → 6.2 · P4 → 6.3 · P5 → 7.4 · P6 → 2 · P7 → 6.4/7.2 · P8 → 3.2 · P9 → 3.3 · P10 → 4.3

### Staged enablement order (production)
1. `MODEL_DISCLOSURE` + `TRANSPARENCY_NOTICE` (user-visible, low risk)
2. `GRANULAR_CONSENT` (after Consent Center ships)
3. `CROSS_BORDER_GATING` (after in-country fallback verified)
4. `DSAR` + `RETENTION_JOB` (after admin queue + ops cron verified)

### Subagent assignment guidance
- Backend service + migration (tasks 1, 4.1, 5, 6.1–6.3) — one writer.
- Web surfaces (3.3, 4.3, 6.4, 8) — disjoint writer.
- Governance docs (7.1) — independent, no code.
