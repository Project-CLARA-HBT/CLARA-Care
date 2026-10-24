# Web UX Risk Register — CLARA-Care (PH12 / A05)

**Document Status:** Sealed Audit Baseline · Subagent A05  
**Repository Branch:** `phase/ph12-a05`  
**Base Commit SHA:** `36e5b95facf155985012354e6005bb7097c36d0b`  
**Write Lane:** `apps/web/app/`, `apps/web/components/`, `apps/web/lib/`, `artifacts/PH12/A05/`  
**Date:** October 24, 2026  
**Subject:** LifeMap Longitudinal Conflict Provenance UI, Multi-Source Contradiction Resolution, Bitemporal Perspective Switching, and Audit Trail Safety.

---

## 1. Executive Summary

As part of Phase PH12 (Subagent A05: Web UX), the Conflict Provenance and Multi-Source Contradiction UI was implemented and integrated into the LifeMap Journey Timeline (`/lifemap/timeline`). LifeMap synthesizes longitudinal data from multiple heterogeneous sources: hospital EHR feeds, OCR scanned documents, AI Scribe consultation summaries, and patient self-reported logs.

Because disparate sources can report conflicting clinical facts (e.g., conflicting medication dosages, contradictory vital signs, or disparate diagnosis dates), the Web UX must provide:
1. Clear, non-alarming indicators of multi-source contradictions.
2. Side-by-side bitemporal attribution (Valid Time vs Transaction/System Time).
3. Strictly guarded audit resolution flows that prevent lost updates and record mandatory clinical justifications.
4. Fail-closed feature flag gating (`NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED`, default false).

This risk register evaluates eight specific risk vectors associated with the Conflict Provenance UX.

---

## 2. Risk Matrix & Severity Definitions

| Severity | Definition | Operational Action Required |
|:---|:---|:---|
| **CRITICAL** | Overwriting verified clinical history, lost updates due to concurrent modification, or unvalidated clinical changes. | Immediate release gate block; hotfix required. |
| **HIGH** | Clinician confusion between Valid and Transaction time, ambiguous source attributions, or unhandled network errors. | Mandatory architectural mitigation prior to deployment. |
| **MEDIUM** | Suboptimal UX sorting, minor localization inaccuracies, or validation messaging edge cases. | Remediate in current sprint with operational controls. |
| **LOW / INFO** | Visual spacing, badge contrast refinements, or telemetry instrumentation. | Tracked in UX backlog. |

---

## 3. Comprehensive Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status | Mitigating Architectural Control |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **UX-CP-01** | Concurrency / Data Integrity | Concurrent Dispute/Resolution Mutation Conflict (Lost Update) | **CRITICAL** | Medium | Severe | **Mitigated** | Optimistic concurrency enforced with `If-Match: <revision>` header and `Idempotency-Key` (`lifemap-conflict-provenance.ts:236`). |
| **UX-CP-02** | Audit Compliance | Empty or Inadequate Resolution Justification Submitted | **HIGH** | High | High | **Mitigated** | `validateResolutionReason` requires non-empty text between 2 and 500 characters, blocking submission otherwise (`lifemap-conflict-provenance.ts:118`). |
| **UX-CP-03** | Clinical Usability | Bitemporal Timestamp Confusion (Valid Time vs Recorded Time) | **HIGH** | Medium | High | **Mitigated** | Side-by-side display clearly distinguishes "Thời gian thực tế (Valid Time)" and "Thời gian ghi nhận (System Time)" (`conflict-provenance-inspector.tsx:185`). |
| **UX-CP-04** | Clinical Safety | Premature or Inaccurate Automatic Severity Escalation | **MEDIUM** | Low | Medium | **Mitigated** | Rule-based classifier (`classifyContradiction`) uses deterministic source hierarchy: EMR vs Patient clash = Critical, >48h drift = Warning (`lifemap-conflict-provenance.ts:144`). |
| **UX-CP-05** | Authorization | Cross-Profile Conflict Inspection via URL Parameter Tampering | **CRITICAL** | Low | Severe | **Mitigated** | Endpoints and UI rely on session context cookies and profile scopes; unauthorized profile IDs return 404 (`profile_scope.py`). |
| **UX-CP-06** | Accidental Action | Unintended Resolution or Dispute Action Triggered by Misclick | **HIGH** | Medium | High | **Mitigated** | Inspector modal requires explicit action selection, source radio selection, reason input, and confirmation button click (`conflict-provenance-inspector.tsx:280`). |
| **UX-CP-07** | Performance | Large Number of Unresolved Conflicts Causing Render Lag | **MEDIUM** | Low | Medium | **Mitigated** | Events filter and conflict count memoized via `useMemo`; conflict toggle limits render tree to active contradictions (`longitudinal-conflict-timeline.tsx:98`). |
| **UX-CP-08** | Reliability | Network Disruption During Resolution Action Submission | **MEDIUM** | Medium | Medium | **Mitigated** | `handleActionSubmit` wraps API call in `try...catch...finally`, displays user-facing error message, and retains form state (`conflict-provenance-inspector.tsx:98`). |

---

## 4. Detailed Risk Deep Dives & Verification Anchors

### 4.1 UX-CP-01: Concurrent Dispute/Resolution Mutation Conflict (Lost Update)
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `apps/web/lib/lifemap-conflict-provenance.ts:236-250`
  - `apps/web/components/lifemap/conflict-provenance-inspector.tsx:78-85`
  - `apps/web/app/lifemap/timeline/page.tsx:456-488`
- **Threat Vector:**
  Two clinicians review the same conflicting prescription simultaneously. Clinician A amends the dosage while Clinician B disputes the event. Without optimistic concurrency, Clinician B could overwrite Clinician A's amendment without awareness of the revision bump.
- **Enforced Control:**
  `buildResolutionHeaders` extracts the latest revision number across conflicting sources and sets `If-Match: String(currentRevision)`. The API backend checks the `If-Match` header against the database revision. If outdated, it returns HTTP 409 Conflict (`stale_version`), preventing lost updates.

### 4.2 UX-CP-02: Empty or Inadequate Resolution Justification
- **Severity:** **HIGH**
- **Affected Anchors:**
  - `apps/web/lib/lifemap-conflict-provenance.ts:118-139`
  - `apps/web/components/lifemap/conflict-provenance-inspector.tsx:64-72`
- **Threat Vector:**
  A user attempts to dismiss or resolve a critical conflict without documenting the clinical rationale, creating an unauditable modification in medical records.
- **Enforced Control:**
  `validateResolutionReason` executes strict client-side validation: string must be trimmed, non-empty, and bounded between 2 and 500 characters. Submitting whitespace or empty input surfaces an inline error: `"Vui lòng nhập lý do giải quyết để ghi nhận vào lịch sử kiểm toán."`

### 4.3 UX-CP-03: Bitemporal Timestamp Confusion
- **Severity:** **HIGH**
- **Affected Anchors:**
  - `apps/web/components/lifemap/longitudinal-conflict-timeline.tsx:107-117`
  - `apps/web/components/lifemap/conflict-provenance-inspector.tsx:185-215`
- **Threat Vector:**
  A lab report drawn on Monday was processed and imported into the EMR on Friday. If the UI presents only the Friday import timestamp, the clinician may misinterpret treatment onset or acute changes.
- **Enforced Control:**
  Both timestamps are explicitly labeled in the inspector. The timeline provides a toggle between "Thời gian thực tế (Valid Time)" and "Thời gian ghi nhận (System Time)", allowing clinicians to observe exactly when the biological event occurred vs when the system recorded it.

---

## 5. Verification Sign-Off

All 8 identified risks have been mitigated by design and verified by automated unit and component test suites (`53 passed in Vitest`). Residual risk is evaluated as **LOW / ACCEPTABLE**.
