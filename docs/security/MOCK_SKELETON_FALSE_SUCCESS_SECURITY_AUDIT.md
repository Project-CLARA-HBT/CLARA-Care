# Mock, Skeleton & False-Success Security Audit (PH40)

## Executive Summary
This forensic security audit investigates 112 heuristic candidates from `MOCK_SKELETON_CANDIDATES.csv` to identify true operational risks, false-success vulnerabilities, and privacy boundaries across The CLARA Care platform.

## P0 Security & False-Success Vulnerability Classification

### 1. Hardcoded Telemetry & Nominal Defaulting on Downstream Failure (P0)
- **Source Location:** `apps/web/lib/admin-system.ts:463-505`
- **Mechanism:** When `getSystemMetrics()` or `getSystemDependencies()` fails to respond or throws network error, the fallback code returns:
  ```typescript
  { requestCount: 21500, errorCount: 16, avgLatencyMs: 24.5, uptimePct: 99.98 }
  ```
- **Security Impact:** Operators monitoring platform security see green "healthy" statuses and low error counts even when backend workers or ML services are completely offline. This presents a severe **false-success oracle**.
- **Remediation Specification (PH41):** Replace synthetic metrics with explicit `StatusTone = "danger"`, `state = "UNAVAILABLE"`, and zeroed counters.

### 2. Client-Side Presentation Role Gating vs Server RBAC (P0)
- **Source Location:** `apps/web/app/admin/overview/page.tsx`, `apps/mobile/lib/experience/presentation_mode.dart`
- **Mechanism:** Presentation mode switches layout, while admin screens inspect user claims client-side.
- **Security Impact:** If a client manipulates UI storage to display an admin view, they must never receive administrative data.
- **Audit Verification:** Confirmed that backend routes in `services/api/src/clara_api/api/v1/endpoints/admin_*.py` strictly enforce `require_roles("admin")`, returning HTTP 403 unconditionally regardless of client view state.

### 3. Fail-Closed Inert Placeholders vs Unimplemented Features (False Positive Triage)
- **Source Location:** `apps/mobile/lib/screens/scribe_screen.dart`, `apps/mobile/lib/widgets/ai_transparency_notice_gate.dart`
- **Triage Result:** **FALSE POSITIVE FOR DEFECT**. These inert placeholders are deliberate, safety-first fail-closed barriers:
  - `ai_transparency_notice_gate.dart`: Blocks medical conversation until patient consents to AI transparency disclosure.
  - `scribe_screen.dart`: Inert when unauthenticated to prevent unauthorized microphone activation.

### 4. Public Landing Product Fixtures Isolation (Privacy Verification)
- **Source Location:** `apps/web/components/landing/v7/landing-data-v7.ts`, `apps/web/components/landing/v6/`
- **Triage Result:** Public demonstration fixtures (`V7_DEMO_SOURCES`, `V7_DEMO_MEDICINES`) are strictly segregated from authenticated patient data stores (`/today`, `/phr`, `/medicines`). No cross-contamination of real patient state occurs.

## Compliance & Threat Matrix

| Candidate ID | Vulnerability Classification | Risk Level | Disposition | Target Phase |
|--------------|------------------------------|------------|-------------|--------------|
| CAND-0001 | HARDCODED_TELEMETRY | P0 | Verified Fake-Success Fallback | PH41 (Admin Control-Plane) |
| CAND-0043 | TRUE_DEFAULT_ON_FETCH_FAILURE | P0 | Verified False-Success Fallback | PH41 (Admin Control-Plane) |
| CAND-0049 | INERT_OR_DISABLED_FLOW | Info | Validated Fail-Closed Safety Gate | Retain (Safety Invariant) |
| CAND-0050 | INERT_OR_DISABLED_FLOW | Info | Validated Fail-Closed Safety Gate | Retain (Safety Invariant) |
| CAND-0056 | BASE_CLASS_ABSTRACT | Info | Standard Python ABC NotImplementedError | Retain (Design Pattern) |
| CAND-0058 | FLAG_DEFAULT_DISABLED | P1 | Dark Safety Flag Verified | Review in Domain Phases |
