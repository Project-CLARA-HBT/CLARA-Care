# Risk Register — PH00 Baseline Audit (Subagent A10)

**Phase:** PH00
**Agent:** A10 — Adversarial Audit + Integration Proposals
**Target Worktree:** `/dev/shm/clara_worktrees/PH00_A10`
**Base SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Status:** ACTIVE AUDIT REGISTER

---

## Risk Assessment Matrix

| Risk ID | Category | Severity | Likelihood | Impact | Title & Vulnerability Summary | Mitigations & Integration Gate |
|---|---|---|---|---|---|---|
| **RISK-01** | Data Integrity | **CRITICAL** | High | High | **Alembic 0062 Migration SQLite Batch Alter Failure**<br>Missing explicit foreign key constraint name causes `ValueError: Constraint must have a name` under SQLite batch alterations. Prevents fresh environment bootstrap and automated SQLite integration test runs. | Patch `20260824_0062_social_bookmarks_and_threading.py` to supply explicit name for foreign key constraint before merging migration chain. Gate A02 on SQLite and PostgreSQL bidirectional test. |
| **RISK-02** | Product Safety | **CRITICAL** | High | High | **Consumer Care Screen Synthetic Data Substitution**<br>`apps/web/app/(consumer)/care/page.tsx` catches network/API errors and renders fabricated doctor appointments and care plans instead of displaying an error state. Patients may believe they have real consultations booked. | Remove catch-block data fabrications in web and mobile consumers; replace with fail-closed retry UI and clear network disconnection notice. |
| **RISK-03** | System Telemetry | **HIGH** | High | Medium | **Admin Telemetry Hardcoded False-Healthy Metrics**<br>`apps/web/lib/admin-system.ts` substitutes fake nominal statistics (21,500 req, 16 errors, 99.99% uptime, 100% FIDES pass) when API metrics fail, blinding operations to system outages and degraded ML services. | Require `admin-system.ts` to surface `UNKNOWN` or `DOWN` status indicators and nullify metrics when probe calls fail. |
| **RISK-04** | Operational Integrity | **HIGH** | Medium | Medium | **Visit Preparation Optimistic False-Success**<br>`apps/web/app/(consumer)/care/prepare/page.tsx` sets `setSaveSuccess(true)` inside the error catch block, falsely reassuring patients that their handoff questions and clinical notes were saved to the server. | Ensure `setSaveSuccess(true)` executes only upon HTTP 200/201 response. Render non-dismissible error banner upon exception. |
| **RISK-05** | Legal & Compliance | **HIGH** | High | High | **Premature Scientific & Clinical Claims**<br>`docs/research/glhs_claim_ledger.yaml` lists 10 core claims with `gate_passed: false` and publication status `NOT SUBMISSION READY`. External publications or regulatory submissions citing these claims expose project to compliance violations. | Enforce strict automated check in CI preventing promotion of unverified claims in papers or product documentation. |
| **RISK-06** | Security | **MEDIUM** | Medium | Medium | **Expired Accepted Vulnerability Finding**<br>Advisory `GHSA-wj6h-64fc-37mp` in `docs/security/accepted-findings.md` expired on 2026-09-24 without re-certification or patch removal. Violates 90-day review policy. | Re-evaluate `python-jose` dependency tree; update review justification and bounded review window in `accepted-findings.md`. |
| **RISK-07** | CI / DX | **MEDIUM** | High | Low | **Route Layout Check Broken in Node Environment**<br>`npm run route-layout:check` fails due to direct TypeScript import without loader, creating 82 false error alerts in web test runs. | Update `scripts/check-route-layout-registry.mjs` to execute via `tsx` or compile TypeScript contract first. |
| **RISK-08** | CI / DX | **LOW** | High | Low | **Docs Check Regex Pattern Flaws**<br>`scripts/docs/check-docs-links.sh` flags false positives on Markdown route tables (`(consumer)/home/`) and scans log files in `docs/formal/`. | Refine regex in `check-docs-links.sh` to restrict file scanning strictly to `*.md` files and require leading slash anchored to word boundaries. |

---

## Quality Gate Escalation Path
- **P0 / Critical Risks (RISK-01, RISK-02):** Must be resolved before entering Phase PH01/PH02 integration. Worktrees touching migrations (A02) and consumer UI (A05) must not propagate these patterns.
- **P1 / High Risks (RISK-03, RISK-04, RISK-05):** Assigned to relevant subagents for Phase PH40 (Mock/Skeleton Elimination) and Phase PH17 (Medical-Legal Guardrails).
