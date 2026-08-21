# GLHS Feature Parity Register & Master Capability Inventory
**Specification Baseline:** `CLARA_Care_Frontend_Redesign_Spec_v0.9.docx` | **Version:** 1.0 (Audited) | **Date:** August 2026

This register serves as the authoritative, contract-verified capability inventory linking legacy and current GLHS capabilities to the modernized 4-Pillar (+ Ask) frontend architecture on Web (Next.js 15) and Mobile (Flutter iOS 26 Liquid Glass / Android Native Fallback).

---

## 1. Information Architecture & Navigation Mapping

```
                                  CLARA CARE FRONTEND ARCHITECTURE
   ┌────────────────────────────────────────────────────────────────────────────────────────┐
   │                          Unified Consumer 4-Pillar IA (+ Ask)                          │
   │                                                                                        │
   │   [ 1. Hôm nay / Home ]   [ 2. Sức khỏe / Health ]   [ 3. Chăm sóc / Care ]            │
   │   [ 4. Bạn / You ]        [ ★ Hỏi CLARA / Ask (Global Action & Multimodal Omnibox) ]   │
   └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
   ┌──────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
   │        Web Responsive Workspace         │   │         Mobile Adaptive Shell            │
   │  - Desktop (>=1200px): Collapsible Rail  │   │  - iOS 26: Native Liquid Glass Nav & Bar │
   │  - Tablet (768-1199px): Master-Detail    │   │  - Android / Fallback: Solid/Blur Shell  │
   │  - Mobile Web (<768px): Single Column    │   │  - Center Elevated "Hỏi CLARA" FAB (60dp)│
   │  - Data Density Compact (Clinician/Admin)│   │  - 44x44+ pt Touch Targets, A11y Scaling │
   └──────────────────────────────────────────┘   └──────────────────────────────────────────┘
```

---

## 2. Exhaustive GLHS Feature Parity Matrix

### Domain 1: Identity, Authentication & Account (`AUTH`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-AUTH-001` | Multi-Factor Credential Login | `public` -> `all` | In: Email, Password, OTP token. Out: Auth Session, JWT, CSRF token. | Rate limiting on failed attempts; sanitizes account existence in error copy; double-submit CSRF cookie initialized. | Web: `/login`<br>Mobile: `LoginScreenV3` | Unit tests in `test_auth.py`, E2E test `login.spec.ts`. | **VERIFIED** |
| `GLHS-CAP-AUTH-002` | User Registration & Terms Acceptance | `public` | In: Name, Email, Password, Disclaimer consent. Out: Account, verification email. | Enforces strong password rules; checks medical disclaimer acceptance before account creation. | Web: `/register`<br>Mobile: `AuthFlowsScreen` | Schema validation test `test_register.py`. | **VERIFIED** |
| `GLHS-CAP-AUTH-003` | First-Run Health Onboarding Wizard | `all authenticated` (`needs_onboarding=true`) | In: Basic vitals (Height, Weight, Blood type, Gender), conditions, allergies. Out: Initial PHR record. | Cannot skip mandatory medical disclaimer; auto-calculates baseline BMI; persists to `/api/v1/phr/onboarding`. | Web: `/welcome/[step]`<br>Mobile: `OnboardingFlow` | Component tests in `onboarding_test.dart`, E2E `welcome.spec.ts`. | **VERIFIED** |
| `GLHS-CAP-AUTH-004` | Active Profile Context Switcher | `normal`, `caregiver`, `doctor`, `admin` | In: Target `profile_id`. Out: Profile scope, active token, invalidates cached views. | Attaches `X-CLARA-Profile-Context` header; clears profile-specific memory; dispatches `clara:profile-context-changed`. | Web: Header dropdown in `ConsumerLayout`<br>Mobile: Appbar switcher in `ProfileHub` | Unit test `profile-boundary.test.ts`. | **VERIFIED** |

---

### Domain 2: Daily Rhythm & Home (`HOME`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-HOME-001` | Today Agenda & Task Schedule | `all` | In: Current date, profile ID. Out: Daily medication schedule, upcoming visits, pending tasks, completion streak. | Displays urgent/overdue items at top; renders "Caught Up" state when empty; supports offline read cache. | Web: `/home` (replaces `/today`)<br>Mobile: `TodaySurface` (Tab 1) | Unit tests in `today_test.dart`, E2E `home.spec.ts`. | **VERIFIED** |
| `GLHS-CAP-HOME-002` | Top Single-Action Recommendation | `all` | In: Profile state, pending alerts. Out: Priority action card with 1-tap CTA. | One dominant primary action; secondary actions visually de-emphasized; no marketing hero banners. | Web: `PrimaryActionCard` on `/home`<br>Mobile: Top priority card on `TodaySurface` | Fast-check property tests in `home-view.test.tsx`. | **VERIFIED** |
| `GLHS-CAP-HOME-003` | Task Execution & Status Transition | `normal`, `caregiver`, `doctor` | In: `task_id`, action (`start`, `complete`, `skip`), reason code, evidence payload. Out: Updated task status, audit log. | Idempotent submission; offline draft marked "Pending sync"; reason codes separated from free-text notes. | Web: `/today/tasks/[taskId]`<br>Mobile: Task review sheet | Contract tests in `test_tasks.py`. | **VERIFIED** |

---

### Domain 3: Conversational Medical AI & Omnibox (`ASK`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-ASK-001` | Unified Multimodal Ask Composer | `all` | In: Text query, camera image, document attachment, voice clip. Out: SSE stream. | Auto-routes intent (no manual model switches); enforces MIME/file-size security checks; handles cancel via `AbortController`. | Web: `AskComposer` on `/ask`<br>Mobile: Center elevated Ask FAB (60dp) | Stream integration tests in `v2-client.test.ts`. | **VERIFIED** |
| `GLHS-CAP-ASK-002` | Safety-First Answer & Evidence Drawer | `all` | In: Model tokens, citations, personal observations. Out: Formatted answer, FIDES verification badges, slide-over evidence inspector. | Emergency symptom fast-path bypasses diagnostic generation; strips internal CoT/telemetry from consumer views; plain Vietnamese terminology. | Web: `AnswerRenderer` + `PersonalEvidenceDrawer`<br>Mobile: `ChatSurfaceV3` | Snapshot and WAI-ARIA tests in `ask.test.tsx`. | **VERIFIED** |
| `GLHS-CAP-ASK-003` | Inline Health Record Write Proposals | `all` | In: Extracted health finding (allergy, condition, vital). Out: Draft proposal card with `Accept`, `Edit`, `Reject` actions. | Requires explicit human confirmation before database commit; enforces GLHS atomic snapshot binding. | Web: `SaveProposalCard` on `/ask`<br>Mobile: Inline candidate card in chat | Invariant test `test_proposal_commit.py`. | **VERIFIED** |

---

### Domain 4: Universal Health Data Capture (`CAP`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-CAP-001` | Universal Multimodal Ingestion Modal | `all` | In: Photo, scanned PDF, voice clip, or manual text. Out: Capture session ID. | Anti-virus scanning; treats document text as untrusted data (prompt-injection isolation); client draft durability. | Web: `UniversalCaptureModal`<br>Mobile: `CabinetOcrSheet` / `LifeMapCapture` | Multi-part upload tests in `capture_test.py`. | **VERIFIED** |
| `GLHS-CAP-CAP-002` | Candidate Extraction & Review Sheet | `all` | In: OCR/VLM extracted candidate fields. Out: Bounding box overlay, confidence scores, accept/edit/reject choices. | Flags OCR discrepancies (`ocr_disagreement`); rejects automated diagnostic image interpretation (text metadata only). | Web: `CandidateReviewSheet`<br>Mobile: Candidate confirmation dialog | Golden fixture tests in `evaluate_ocr_ddi.py`. | **VERIFIED** |
| `GLHS-CAP-CAP-003` | Atomic GLHS Record Commitment | `all` | In: Confirmed candidates, `base_state_version`. Out: Committed PHR entries, updated state version. | TOCTOU check via `If-Match` / `SELECT ... FOR UPDATE`; prevents dirty write overwrites; generates audit events. | Web: `CaptureCommitButton`<br>Mobile: Commit action handler | Concurrency tests in `test_commitment_gateway.py`. | **VERIFIED** |

---

### Domain 5: Health Records & Longitudinal Timeline (`HEALTH`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-HLTH-001` | Longitudinal Health Timeline Replay | `all` | In: Date range, event type filter. Out: Chronological event ledger with source provenance. | Distinguishes valid time ($\tau_v$) from knowledge time ($\tau_k$); renders badges (`Confirmed`, `Device`, `Reported`, `Conflict`). | Web: `/health/timeline`<br>Mobile: `TimelineReplay` in `LifeMapSurface` | Replay integrity tests in `test_timeline.py`. | **VERIFIED** |
| `GLHS-CAP-HLTH-002` | Granular Health Subresource CRUD | `all` | In: Allergy/Condition/Medication payload, `If-Match` ETag. Out: Updated subresource, completeness score. | Replaces whole-record blind `PUT` with atomic subresource endpoints (`PATCH /demographics`, `POST /allergies`, etc.). | Web: `/health` & `/health/[category]`<br>Mobile: `PhrSurfaceV3` | Concurrency tests in `test_phr_concurrency.py`. | **VERIFIED** |
| `GLHS-CAP-HLTH-003` | Vital Measurements & Interactive Trends | `all` | In: Measurement type, value, unit, timestamp. Out: Historical trend chart, abnormal range indicators. | Trend chart does not hide raw values; supports manual entry and connected device auto-sync; strict unit validation. | Web: `/health/measurements`<br>Mobile: Vitals tracker in `ProfileHub` | Unit tests in `measurements.test.tsx`. | **VERIFIED** |
| `GLHS-CAP-HLTH-004` | Diagnostic Lab Results & Reference Flags | `all` | In: Lab report document or manual entry. Out: Structured analytes with reference range flags (`normal`, `abnormal`, `critical`). | Critical values highlighted with accessible icons + text; historical comparison modal. | Web: `/health/results`<br>Mobile: Lab results viewer in `ProfileHub` | Reference range validator tests in `test_labs.py`. | **VERIFIED** |
| `GLHS-CAP-HLTH-005` | Medical Documents Archive & Viewer | `all` | In: Uploaded PDF/JPEG records. Out: Categorized document repository with OCR summaries. | Access-controlled signed download links; preserves file hash and upload provenance. | Web: `/health/documents`<br>Mobile: Document vault in `ProfileHub` | Signed URL validation in `test_documents.py`. | **VERIFIED** |

---

### Domain 6: Medications & Drug Safety (`MEDS`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-MEDS-001` | Active Treatment Courses & History | `all` | In: Medication name, dose, frequency, start/end date. Out: Active courses list, historical course records. | Supports versioned course correction (`/correct`) and formal course termination (`/end`). | Web: `/health/medications?tab=courses`<br>Mobile: `MedicinesHub` (Courses tab) | Course lifecycle tests in `test_medications.py`. | **VERIFIED** |
| `GLHS-CAP-MEDS-002` | Medicine Cabinet Inventory | `all` | In: Brand name, packaging photo, expiry date, remaining count. Out: Cabinet items catalog, expiry alerts. | Packaging OCR barcode/label scanning via server bridge; manual confirmation gate before saving. | Web: `/health/medications?tab=cabinet`<br>Mobile: `MedicinesHub` (Cabinet tab) | Scanner integration tests in `cabinet_test.dart`. | **VERIFIED** |
| `GLHS-CAP-MEDS-003` | Real-Time DDI & Allergy Safety Scanner | `all` | In: Active medications + cabinet items + patient allergies. Out: DDI severity matrix, clinical mechanism, action advice. | Local SQLite DrugBank + DAV Merkle index; severe DDI fails closed with explicit warnings; zero false reassurance. | Web: `/health/medications?tab=safety`<br>Mobile: `MedicinesHub` (Safety tab) | Sealed benchmark tests in `evaluate_ocr_ddi.py`. | **VERIFIED** |

---

### Domain 7: Care Management & Doctor Visits (`CARE`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-CARE-001` | Clinical Symptom Checker & Triage | `all` | In: Step-by-step symptom questionnaire responses. Out: Urgency tier (`emergency`, `urgent`, `routine`, `self_care`), handoff pack. | Red-flag symptoms trigger immediate emergency banner and hotline links; does not provide definitive medical diagnoses. | Web: `/care/check-symptoms`<br>Mobile: Symptom triage flow | Triage rule tests in `test_triage.py`. | **VERIFIED** |
| `GLHS-CAP-CARE-002` | Doctor Visit Preparation Wizard | `all` | In: Chief concerns, symptom updates, document attachments. Out: Structured agenda, question suggestions for doctor. | Synthesizes recent LifeMap events and vitals into a concise printable/shareable summary. | Web: `/care/prepare`<br>Mobile: `VisitsSurface` prep wizard | Synthesis tests in `test_visit_prep.py`. | **VERIFIED** |
| `GLHS-CAP-CARE-003` | Visit Management & Appointment Packs | `all` | In: Doctor name, facility, date, specialty. Out: Appointment card, linked documents, time-bounded public share token. | Time-limited share token revocation; Scribe recording verbal consent toggle. | Web: `/care/visits`<br>Mobile: `VisitDetailSurface` | Token expiry tests in `test_visits.py`. | **VERIFIED** |

---

### Domain 8: Account, Family & Privacy Controls (`YOU`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-YOU-001` | Emergency Health Card Configuration | `all` | In: Blood type, emergency contact, critical allergies, field toggles. Out: Printable/scannable Emergency Card view. | Accessible via public token `/phr/shared/[token]`; sensitive data masked unless explicitly enabled. | Web: `/you/profile` & `/phr/emergency-card`<br>Mobile: Emergency card in `ProfileHub` | Security tests in `test_emergency_card.py`. | **VERIFIED** |
| `GLHS-CAP-YOU-002` | Granular Family Circle Sharing | `all` | In: Supporter email, permission scopes (`view`, `add_observation`, `complete_task`), expiry date. Out: Invitation token, grant ledger. | Preview without mutation; time-bound expiry; immutable access audit log inspector; instant grant revocation. | Web: `/you/sharing`<br>Mobile: `FamilySurface` | Grant lifecycle tests in `test_family.py`. | **VERIFIED** |
| `GLHS-CAP-YOU-003` | Privacy, Consent & AI Transparency | `all` | In: 6 purpose-specific consent toggles, AI feature switches. Out: Immutable consent history ledger. | Granular consent revocation immediately halts dependent AI reasoning; zero CoT disclosure guarantee. | Web: `/you/privacy` & `/account/consent`<br>Mobile: `ConsentCenterScreen` | Compliance audit tests in `test_compliance.py`. | **VERIFIED** |
| `GLHS-CAP-YOU-004` | Data Subject Access Rights (DSAR) | `all` | In: DSAR request type (`export`, `correct`, `restrict`, `delete`), password confirmation. Out: Encrypted data archive, deletion receipt. | Multi-step destructive deletion wizard; export checked against current RBAC permissions; admin queue tracking. | Web: `/account/data`<br>Mobile: `DsarScreen` | DSAR workflow tests in `test_dsar.py`. | **VERIFIED** |
| `GLHS-CAP-YOU-005` | Connected Health Device Integration | `all` | In: Platform connector selection (Apple Health, Health Connect, Garmin, Fitbit), category permissions. Out: Sync status, sync log. | Disconnect allows permanent deletion of imported external data; pause/resume sync controls. | Web: `/you/integrations`<br>Mobile: `ConnectedHealthScreen` | Connector interface tests in `test_connectors.py`. | **VERIFIED** |

---

### Domain 9: Professional & Clinician Workspaces (`PRO`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-PRO-001` | Multi-Specialist Clinical Council | `doctor`, `admin` | In: Case clinical summary, lab attachments, specialist panel configuration. Out: Deliberation consensus, conflict map, handoff summary. | Multi-agent reasoning across specialties; clinician oversight pause/override capability; shadow evidence attachment. | Web: `/council/*`<br>Mobile: `CouncilScreen` | Deliberation pipeline tests in `test_council.py`. | **VERIFIED** |
| `GLHS-CAP-PRO-002` | Ambient Clinical Scribe (SOAP Notes) | `doctor`, `admin` | In: Web Audio live recording or audio upload. Out: ASR transcript, SOAP note draft, ICD-10 suggestions, FHIR/DOCX export. | Verbal patient consent verification required; electronic signature locks note against edits; formal addenda support. | Web: `/scribe`<br>Mobile: `ScribeScreen` | Scribe lifecycle tests in `test_scribe.py`. | **VERIFIED** |
| `GLHS-CAP-PRO-003` | Living Medical Evidence & Source Hub | `researcher`, `doctor`, `admin` | In: PICO clinical query, literature source selection (PubMed, MOH, DailyMed). Out: Categorized evidence matrix, contradiction alerts. | Scheduled monitoring subscriptions; applicability assessment against patient baseline. | Web: `/evidence` & `/research/source-hub`<br>Mobile: `LivingEvidenceSurface` | Evidence aggregator tests in `test_evidence.py`. | **VERIFIED** |

---

### Domain 10: Technical Control Tower & Administration (`ADMIN`)
| GLHS Capability ID | Capability Name | Roles & Scope | Inputs / Outputs | Rules & Edge Cases | New UX Mapping (Web / Mobile) | Acceptance Evidence | Status |
|---|---|---|---|---|---|---|---|
| `GLHS-CAP-ADM-001` | System Observability & Service Signals | `admin` | In: Service queries. Out: Real-time health signals across Web, API, ML, OCR, ASR, PostgreSQL, Redis, and Milvus. | No sensitive patient data in logs; latency and error budget percentiles. | Web: `/admin/observability` & `/dashboard/control-tower` | Observability tests in `test_observability.py`. | **VERIFIED** |
| `GLHS-CAP-ADM-002` | RAG Knowledge Sources & Evaluation | `admin` | In: Document uploads, trust tier adjustments, golden Q&A eval trigger. Out: Corpus stats, watermark logs, `Recall@k` & `nDCG@k` scores. | Multi-tier synthesis configuration; golden evaluation benchmark trend charts. | Web: `/admin/knowledge-sources`, `/admin/rag-ingestion`, `/admin/rag-eval` | Evaluation harness tests in `test_rag_eval.py`. | **VERIFIED** |
| `GLHS-CAP-ADM-003` | Immutable System Audit Log | `admin` | In: Filter by date, actor, role, action. Out: Searchable immutable audit event trail. | Records all administrative changes, permission modifications, and data export requests. | Web: `/admin/audit-log` | Audit logging tests in `test_admin_audit.py`. | **VERIFIED** |
