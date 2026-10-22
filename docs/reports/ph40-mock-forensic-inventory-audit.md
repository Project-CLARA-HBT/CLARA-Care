# PH40 Adversarial Review & Forensic Inventory Audit Report

## Phase Information
- **Phase ID:** `PH40` (Mock, skeleton, fake-success forensic inventory)
- **Role:** Subagent A10 (Adversarial Reviewer & Quality Gate)
- **Base Baseline SHA:** `db1ba377c0b02047a27ebbe5db2b291a1aebbbcd`
- **Audit Date:** 2026-10-22

## Top 20 Highest-Risk Status Adversarial Runtime Challenge

| # | Candidate ID | Category | Location | Runtime Challenge | Adversarial Verdict |
|---|--------------|----------|----------|-------------------|---------------------|
| 1 | CAND-0001 | HARDCODED_TELEMETRY | `apps/web/app/admin/system/page.tsx:186` | Chip status mapper | **CONFIRMED DEFECT:** Needs replacement by live health API |
| 2 | CAND-0002 | HARDCODED_TELEMETRY | `apps/web/components/admin/admin-overview-panel.tsx:109` | Promise.allSettled health check | **CONFIRMED DEFECT:** Masked network errors |
| 3 | CAND-0040 | HARDCODED_TELEMETRY | `apps/web/lib/admin-system.ts:161` | Type declaration | **REJECTED (TYPE DEF):** Legitimate TypeScript union |
| 4 | CAND-0042 | HARDCODED_TELEMETRY | `apps/web/lib/admin-system.ts:238` | Default tone return | **CONFIRMED DEFECT:** Replaced in PH41 with dynamic tone |
| 5 | CAND-0043 | TRUE_DEFAULT_ON_FETCH_FAILURE | `apps/web/lib/admin-system.ts:464` | Nominal health fallback | **CONFIRMED CRITICAL:** False-success oracle |
| 6 | CAND-0045 | HARDCODED_TELEMETRY | `apps/web/lib/admin-system.ts:469` | Hardcoded 21500 req count | **CONFIRMED CRITICAL:** Fabricated metrics |
| 7 | CAND-0047 | TRUE_DEFAULT_ON_FETCH_FAILURE | `apps/web/lib/admin-system.ts:474` | ML reachable true fallback | **CONFIRMED CRITICAL:** Hides ML downtime |
| 8 | CAND-0048 | HARDCODED_TELEMETRY | `apps/web/lib/admin-system.ts:497` | Hardcoded 99.98% uptime | **CONFIRMED CRITICAL:** Fabricated uptime |
| 9 | CAND-0049 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/widgets/ai_transparency_notice_gate.dart:119` | Flag off behavior | **REJECTED AS DEFECT:** Deliberate fail-closed consent gate |
| 10 | CAND-0050 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/screens/scribe_screen.dart:40` | Scribe flag disabled | **REJECTED AS DEFECT:** Safety feature gate |
| 11 | CAND-0051 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/screens/scribe_screen.dart:892` | Inert placeholder UI | **REJECTED AS DEFECT:** Prevents unauthorized recording |
| 12 | CAND-0052 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/experience/redesign/cabinet_screen_v3.dart:920` | CRUD gate disabled | **REJECTED AS DEFECT:** Preserves drug record safety |
| 13 | CAND-0053 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/experience/redesign/scribe_surface_v3.dart:17` | Zero network calls | **REJECTED AS DEFECT:** Valid fail-closed invariant |
| 14 | CAND-0054 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/experience/redesign/scribe_surface_v3.dart:750` | Gate 1 flag off | **REJECTED AS DEFECT:** Clinical workflow safety |
| 15 | CAND-0055 | INERT_OR_DISABLED_FLOW | `apps/mobile/lib/experience/redesign/scribe_surface_v3.dart:1053` | Inert placeholder | **REJECTED AS DEFECT:** Clinician authorization barrier |
| 16 | CAND-0056 | BASE_CLASS_ABSTRACT | `services/ml/src/clara_ml/agents/base.py:22` | raise NotImplementedError | **REJECTED AS DEFECT:** Standard Python abstract class |
| 17 | CAND-0057 | BASE_CLASS_ABSTRACT | `services/ml/src/clara_ml/ingestion/connectors/base.py:218` | raise NotImplementedError | **REJECTED AS DEFECT:** Connector interface contract |
| 18 | CAND-0058 | FLAG_DEFAULT_DISABLED | `services/api/src/clara_api/core/config.py:247` | RAG_SCRIBE_STREAMING_ENABLED=False | **VALID SAFETY FLAG:** Dark flag until DAG ready |
| 19 | CAND-0059 | FLAG_DEFAULT_DISABLED | `services/api/src/clara_api/core/config.py:250` | RAG_SCRIBE_DIARIZATION_ENABLED=False | **VALID SAFETY FLAG:** Dark flag until DAG ready |
| 20 | CAND-0060 | FLAG_DEFAULT_DISABLED | `services/api/src/clara_api/core/config.py:253` | HARDENING_MFA_ENFORCED=False | **VALID SAFETY FLAG:** Staged for PH42 MFA cutover |

## Summary of Findings
- **Real False-Success / P0 Defects Confirmed:** 6 items (all concentrated in `apps/web/lib/admin-system.ts` and admin overview panel).
- **Legitimate Fail-Closed Invariants Preserved:** 7 items (mobile inert UI and consent gates).
- **Standard Abstract Interfaces Preserved:** 2 items (Python abstract base classes).
- **Valid Dark Safety Flags Confirmed:** 3 items (staged for activation in designated downstream phases).
