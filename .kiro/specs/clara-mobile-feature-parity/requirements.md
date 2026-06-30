# Requirements Document

## Introduction

This feature upgrades the **CLARA-Care Flutter mobile app**
(`apps/mobile/*`) from its current partial-coverage starter to **full feature
parity with the web app** (`apps/web/app/*`) and to **production-grade quality**.
It is **additive, remote-config / feature-flag gated, and back-compatible**: it
does not remove or regress any existing mobile screen, and every new surface
defaults to a state that preserves today's behavior until explicitly enabled.

The mobile app today ships six screens — login, dashboard, research
(fast / deep / deep_beta with SSE progress and role-gated telemetry), CareGuard
DDI, AI council, and the legacy PHR record — backed by four core modules:
`api_client` (login, research tier2 + jobs + SSE stream, careguard, council,
system metrics, mobile summary, PHR get/put), a consent- and PII-guarded
`analytics` facade, a fail-closed `research_telemetry_gate`, and a persistent
`session_store` with JWT-expiry handling. Its tests cover only those four core
modules as pure unit / generated-input tests; **no widget tests exist**, there
is **no chat, scribe, self-med cabinet, granular-consent/DSAR, share, or
enhanced PHR/council surface**, **no token refresh**, and **no offline,
accessibility, or model-disclosure handling**.

The web app, by contrast, exposes chat v2 (`chat/_v2/ChatShell` with `/chat`
and `/chat/stream` SSE, `AnswerRenderer`, reduced-motion support, role-gated
telemetry, and model disclosure), an enterprise scribe (audio capture →
transcribe → SOAP, sessions, consent capture/revoke, sign/amend/addendum,
export), the self-med medicine cabinet (list / add / OCR / delete behind a
consent gate, feeding the DDI check), enhanced PHR (entries, observations,
history, completeness, export, share, emergency card, OCR import, reminders,
consent), council cases, research conversations + knowledge sources, the full
auth lifecycle (register, verify-email, forgot/reset/change password, refresh,
logout, OTP, role select, consent-status), the AI-Law/PDPD compliance surfaces
(AI transparency notice, model/version disclosure, granular consent center,
DSAR self-service), and the legal pages. This feature closes those gaps on
mobile while preserving CLARA's safety architecture: RBAC feature gating,
two-medicine DDI guard, End_User-safe projections (no runtime/telemetry leakage),
fail-closed role gating, consent/PII-free analytics, and the self-declared /
decision-support-only positioning of the PHR.

CLARA-Care remains **decision-support software over self-declared data — not a
medical device and not an EMR/EHR**. Nothing here changes that; the mobile app
must surface that positioning consistently. All copy is Vietnamese-first with
bilingual vi/en where a clinical or legal term of art requires it.

## Glossary

- **Mobile_App**: The CLARA-Care Flutter client under `apps/mobile/`.
- **Web_App**: The reference Next.js client under `apps/web/app/`, treated as the parity baseline for feature surface and End_User-safe projections.
- **CLARA_API**: The FastAPI gateway under `services/api/src/clara_api`, the shared backend both clients call.
- **Api_Client**: The mobile networking layer (`lib/core/api_client.dart`) that wraps CLARA_API endpoints.
- **Feature parity**: Every End_User-facing capability the Web_App offers for a given role is reachable, and behaves equivalently, on the Mobile_App.
- **Production-grade quality**: Offline resilience, accessibility, robust error states, session/token lifecycle, role-gated fail-closed telemetry, and widget-level test coverage on top of feature parity.
- **Remote-config flag**: A per-role capability switch delivered by `GET /api/v1/mobile/summary` (`feature_flags`) or a compile-time `--dart-define`, whose default preserves current behavior.
- **Role-gated telemetry**: The web Requirement-3 rule, mirrored on mobile, that the detailed pipeline/telemetry rail is shown **iff** the role is `admin`; all other roles see a sanitized summary; an unevaluable role fails closed.
- **End_User-safe projection**: A view that excludes internal runtime fields (RAG/research/fallback mode, retrieval, connector `source_errors`, policy verdicts) from non-admin surfaces.
- **SSE**: Server-Sent Events; the streaming transport CLARA_API uses for chat (`/chat/stream`), research jobs (`/research/tier2/jobs/{id}/stream`), and scribe (`/scribe/sessions/{id}/stream`).
- **Model disclosure**: The user-visible label of the AI model family/version used to produce a response, and a degraded/fallback label when the local deterministic path was used (mirrors web compliance Requirement 1.3/1.4).
- **AI Transparency Notice**: The versioned disclosure that the user is interacting with an AI medical assistant that does not replace a clinician (mirrors web compliance Requirement 1).
- **Granular consent**: Purpose-typed, versioned, revocable consent (core service, personalization, research, cross-border processing, sharing, analytics) surfaced in a self-service consent center.
- **DSAR**: Data Subject Access Request (export, correct, delete, restrict, withdraw) — the PDPD rights surface mirrored on mobile.
- **Self-med cabinet**: The user's personal medicine list (`/selfmed` cabinet CRUD) that feeds the DDI / CareGuard check.
- **Scribe session**: An ambient-documentation session (transcript → SOAP note) with consent capture, versioning, signing, and export.
- **PHR**: Personal Health Record — self-declared, decision-support-only profile, allergies, conditions, medications.
- **Session_Store**: The persistent mobile credential store (`lib/core/session_store.dart`) backed by secure storage, with JWT-expiry handling.
- **Token refresh**: Exchanging a stored refresh token at `POST /api/v1/auth/refresh` for a new access token when the access token expires.
- **Offline / degraded mode**: App behavior when the device has no connectivity or CLARA_API is unreachable: cached reads where safe, clear messaging, and queued or blocked writes.
- **Accessibility (a11y)**: Screen-reader semantics, minimum 48dp touch targets, dynamic text scaling, sufficient contrast, and reduced-motion support.

## Requirements

### Requirement 1: Conversational Chat Parity (web `chat/_v2`)

**User Story:** As a user, I want a mobile chat that streams answers with citations and safety framing like the web chat, so that I can use CLARA's primary surface on my phone.

#### Acceptance Criteria

1. THE Mobile_App SHALL provide a chat surface that submits a user message to CLARA_API and renders the assistant answer with its citations/sources.
2. WHERE streaming is enabled, THE Mobile_App SHALL consume the `POST /api/v1/chat/stream` SSE stream and progressively render answer tokens until a terminal event.
3. WHEN the SSE stream errors or disconnects, THE Mobile_App SHALL fall back to a non-PII error state and preserve any already-streamed content.
4. THE Mobile_App SHALL render the standing medical disclaimer and the directive to review with a licensed clinician on the chat surface.
5. THE Mobile_App SHALL present an emergency fast-path affordance directing the user to emergency services without diagnostic reasoning.
6. THE Mobile_App SHALL exclude internal runtime fields (RAG/research/fallback mode, retrieval, connector source errors, policy verdicts) from the chat answer view for non-admin roles.
7. WHERE the chat surface is gated by a remote-config flag, THE Mobile_App SHALL keep the surface hidden/disabled when the flag is absent or false.

### Requirement 2: Deep Research Production Hardening (web `research`)

**User Story:** As a researcher, I want the deep-research progress and results to be reliable and role-appropriate on mobile, so that long-running jobs are trustworthy.

#### Acceptance Criteria

1. THE Mobile_App SHALL preserve the existing fast (`/research/tier2`) and deep/deep_beta (job + SSE) research paths without regression.
2. WHILE a research job streams, THE Mobile_App SHALL display ordered pipeline stages and the current status note, and SHALL keep progress visible after completion.
3. THE Mobile_App SHALL show the detailed telemetry rail IF AND ONLY IF the role is `admin`, and SHALL show a sanitized summary (internal labels stripped) to every other recognized role.
4. WHEN the requesting role cannot be evaluated, THE Mobile_App SHALL fail closed: expose no telemetry and block the research job.
5. WHERE deep research is gated by remote config (`research_mobile_deep`), THE Mobile_App SHALL offer only fast research when the flag is false.
6. WHEN a streaming research job is interrupted by app backgrounding or connectivity loss, THE Mobile_App SHALL surface a recoverable error rather than crashing or hanging.

### Requirement 3: Self-Med Cabinet + DDI Parity (web `selfmed`, `careguard`)

**User Story:** As a user, I want to manage my medicine cabinet and check interactions on mobile, so that the DDI check uses my real medication list.

#### Acceptance Criteria

1. THE Mobile_App SHALL list the user's self-med cabinet items with their source (manual/OCR/barcode/imported) and key fields (dosage, quantity, expiry).
2. THE Mobile_App SHALL allow adding and deleting cabinet items against CLARA_API, behind the existing self-med consent gate.
3. THE Mobile_App SHALL require at least two distinct medicines before invoking the DDI/CareGuard analysis, prompting the user otherwise.
4. THE Mobile_App SHALL render the DDI result as an End_User-safe projection: risk level, alerts, recommendations, and reference sources only — excluding runtime mode, fallback flags, and connector source errors.
5. WHERE self-med consent has not been granted, THE Mobile_App SHALL gate cabinet and DDI surfaces behind the consent affordance.
6. THE Mobile_App SHALL surface cabinet-derived safety notices (e.g., expired items, missing dosage) consistent with the web self-med surface.

### Requirement 4: Ambient Scribe Parity (web `scribe`)

**User Story:** As a clinician, I want to capture a consult and generate a SOAP note on mobile, so that documentation works at the bedside.

#### Acceptance Criteria

1. THE Mobile_App SHALL allow an authorized role to create, list, and open scribe sessions via CLARA_API.
2. THE Mobile_App SHALL capture or upload audio and submit it to `POST /api/v1/scribe/transcribe`, appending the transcribed text to the active session.
3. THE Mobile_App SHALL generate and display the SOAP note (regenerate) for a session and surface session status (draft/ready/finalized/error).
4. THE Mobile_App SHALL capture and allow revocation of scribe consent for a session before audio is processed, and SHALL block processing when consent is absent.
5. THE Mobile_App SHALL sanitize backend-derived clinical text through the telemetry-label stripper so internal jargon never reaches the End_User view.
6. THE Mobile_App SHALL restrict scribe surfaces to roles authorized by CLARA_API and SHALL hide them for unauthorized roles.
7. WHERE the scribe surface is gated by a remote-config flag, THE Mobile_App SHALL keep it hidden when the flag is absent or false.

### Requirement 5: Enhanced PHR Parity (web `phr`)

**User Story:** As a user, I want my mobile health record to match the web record's capabilities, so that I can manage allergies, conditions, medications, and provenance on my phone.

#### Acceptance Criteria

1. THE Mobile_App SHALL preserve the existing legacy PHR view/edit (`GET/PUT /record`) without regression.
2. THE Mobile_App SHALL display each entry's provenance (`information_source`) and verification (`verification_status`) badges, defaulting to self-declared / unconfirmed when absent.
3. THE Mobile_App SHALL render a persistent self-declared / decision-support-only / not-an-EMR disclaimer on every PHR surface.
4. THE Mobile_App SHALL surface server validation failures (field length/range, severity/status domains) as inline, PII-free errors.
5. THE Mobile_App SHALL provide Vietnamese-first bilingual vi/en copy, defaulting to Vietnamese.
6. WHERE the enhanced PHR contract is enabled by remote config, THE Mobile_App SHALL additionally surface PHR export and emergency-card reads without changing legacy behavior when the flag is off.

### Requirement 6: Authentication Lifecycle Parity (web auth)

**User Story:** As a user, I want full account flows on mobile, so that I can register, recover access, and stay signed in securely.

#### Acceptance Criteria

1. THE Mobile_App SHALL support registration, email verification, and password reset/forgot flows against CLARA_API, or SHALL clearly route the user to complete them.
2. WHEN an access token is expired but a valid refresh token is held, THE Mobile_App SHALL obtain a new access token via `POST /api/v1/auth/refresh` before failing a request.
3. WHEN refresh fails or no valid refresh token exists, THE Mobile_App SHALL clear the session and route to login.
4. THE Mobile_App SHALL preserve the existing persist-on-login, restore-valid-session-on-launch, and clear-on-sign-out behavior of the Session_Store.
5. THE Mobile_App SHALL never persist or transmit credentials outside secure storage and the authenticated request header.
6. WHERE the backend requires consent acknowledgement (`/auth/consent-status`), THE Mobile_App SHALL surface the consent gate before serving gated medical content.

### Requirement 7: AI Transparency & Model Disclosure (web compliance Req 1)

**User Story:** As a user, I want to know I am talking to an AI and which model answered, so that I can judge the response.

#### Acceptance Criteria

1. THE Mobile_App SHALL present a versioned AI Transparency Notice stating the user is interacting with an AI medical assistant that does not replace a clinician.
2. WHEN the current notice version is unacknowledged AND the gate flag is on, THE Mobile_App SHALL record acknowledgement before serving medical content.
3. WHERE model disclosure is enabled, THE Mobile_App SHALL display the model family/version for a response when CLARA_API provides it.
4. WHEN a response is produced by the local deterministic fallback, THE Mobile_App SHALL label it as a degraded/fallback answer.
5. WHERE disclosure data is absent from the response, THE Mobile_App SHALL omit the disclosure affordance rather than displaying a placeholder.

### Requirement 8: Granular Consent Center & DSAR (web compliance Req 2, 3)

**User Story:** As a data subject, I want to manage consent and exercise my data rights on mobile, so that I retain control of my health data.

#### Acceptance Criteria

1. THE Mobile_App SHALL expose a self-service consent center listing each processing purpose (core service, personalization, research, cross-border processing, sharing, analytics) with grant/withdraw toggles.
2. THE Mobile_App SHALL make consent withdrawal at least as easy as granting it.
3. THE Mobile_App SHALL allow an authenticated data subject to submit DSAR requests (export, correct, delete, restrict, withdraw) and SHALL show an acknowledgement.
4. WHEN analytics consent is withdrawn, THE Mobile_App SHALL immediately stop analytics transmission.
5. THE Mobile_App SHALL NOT include PII in any DSAR/consent client-side telemetry or logs.
6. WHERE the consent/DSAR flags are off, THE Mobile_App SHALL behave equivalently to the pre-feature app.

### Requirement 9: Offline & Network Resilience

**User Story:** As a mobile user with intermittent connectivity, I want the app to degrade gracefully, so that I am never stuck on a broken screen.

#### Acceptance Criteria

1. WHEN the device is offline or CLARA_API is unreachable, THE Mobile_App SHALL present a clear, non-PII offline/error state with a retry affordance on each data surface.
2. THE Mobile_App SHALL apply a bounded timeout to network requests and SHALL not hang indefinitely on a stalled request or stream.
3. WHERE a read has a previously loaded value, THE Mobile_App MAY display the cached value labeled as potentially stale rather than blanking the screen.
4. WHEN connectivity is restored, THE Mobile_App SHALL allow the user to retry the failed operation without losing entered input.
5. THE Mobile_App SHALL block mutating operations (PHR save, cabinet add, scribe processing) while offline rather than silently dropping them, and SHALL inform the user.

### Requirement 10: Accessibility

**User Story:** As a user relying on assistive technology, I want the mobile app to be accessible, so that I can use every feature.

#### Acceptance Criteria

1. THE Mobile_App SHALL provide screen-reader semantics (labels/roles) for all interactive controls and primary content regions.
2. THE Mobile_App SHALL ensure interactive touch targets meet the platform minimum (≥48dp).
3. THE Mobile_App SHALL respect the OS dynamic text-scaling setting without clipping primary content or controls.
4. THE Mobile_App SHALL respect the OS reduced-motion setting by suppressing non-essential animation, mirroring the web `usePrefersReducedMotion` behavior.
5. THE Mobile_App SHALL convey status (risk level, errors, progress) through text/semantics and not by color alone.

### Requirement 11: Error States & Telemetry Discipline

**User Story:** As a user, I want errors to be clear and never leak sensitive data, so that I trust the app.

#### Acceptance Criteria

1. THE Mobile_App SHALL render descriptive, PII-free, Vietnamese-first error messages for failed requests on every data surface.
2. THE Mobile_App SHALL keep the analytics facade consent- and credential-gated and SHALL strip PII (names, contact, free-text queries, drug/medication/symptom/allergy/diagnosis) from every event payload.
3. THE Mobile_App SHALL identify users only by an opaque pseudonymous id, never by email or name.
4. WHEN an unexpected exception occurs in a screen, THE Mobile_App SHALL contain it within the screen and SHALL NOT crash the app or leak the stack trace to the user.
5. THE Mobile_App SHALL never transmit free-text medical content (queries, transcripts, drug lists, symptoms) to analytics.

### Requirement 12: Sharing & Deep Links (web `share`, `chat/shares`)

**User Story:** As a user, I want to open shared CLARA content on mobile, so that links work across devices.

#### Acceptance Criteria

1. WHERE sharing is enabled, THE Mobile_App SHALL open a shared resource by token (e.g., shared PHR or chat) via the corresponding CLARA_API read endpoint.
2. WHEN a share token is invalid, expired, or revoked, THE Mobile_App SHALL show a clear non-PII error rather than partial content.
3. THE Mobile_App SHALL render shared content read-only and SHALL apply the same End_User-safe projection rules as first-party surfaces.
4. WHERE the sharing flag is off, THE Mobile_App SHALL not expose share entry points.

### Requirement 13: Role-Aware Navigation & Feature Gating

**User Story:** As a user, I want to see only the tools my role and configuration allow, so that the app reflects my access.

#### Acceptance Criteria

1. THE Mobile_App SHALL derive available tools from the `feature_flags` returned by `GET /api/v1/mobile/summary` for the authenticated role.
2. WHERE a capability flag is false or absent, THE Mobile_App SHALL disable or hide the corresponding entry point.
3. THE Mobile_App SHALL keep PHR reachable for every authenticated role, consistent with backend RBAC.
4. WHEN the summary cannot be loaded, THE Mobile_App SHALL fail closed (no privileged tools shown) and SHALL present a retry.
5. THE Mobile_App SHALL never expose admin-only surfaces (e.g., system metrics, detailed telemetry) to non-admin roles.

### Requirement 14: Widget & Integration Test Coverage

**User Story:** As an engineer, I want the mobile app covered by widget and property tests, so that parity and safety invariants are enforced in CI.

#### Acceptance Criteria

1. THE Mobile_App SHALL retain its existing passing unit/generated tests for analytics, the research telemetry gate, and the session store.
2. THE Mobile_App SHALL add widget tests for each primary screen covering loading, success, empty, and error states.
3. THE Mobile_App SHALL add tests asserting role-gated telemetry fail-closed behavior at the widget level (non-admin sees sanitized summary; unevaluable role blocks the job).
4. THE Mobile_App SHALL add tests asserting End_User-safe projections drop internal runtime fields for chat, DDI, and scribe views.
5. THE Mobile_App SHALL add tests asserting no PII reaches analytics from any screen interaction.
6. THE test suite SHALL run under `flutter test` without requiring platform channels or live network access.

### Requirement 15: Guardrails, Back-Compatibility & Privacy Preservation

**User Story:** As a platform operator, I want parity work to default safely and never regress existing behavior, so that adoption carries no clinical or operational risk.

#### Acceptance Criteria

1. THE Mobile_App SHALL gate all new surfaces behind remote-config / `--dart-define` flags whose defaults preserve current behavior.
2. WHERE all new flags are off, THE Mobile_App SHALL behave equivalently to the pre-feature app (existing six screens, existing contracts).
3. THE Mobile_App SHALL preserve the two-medicine DDI guard, fail-closed telemetry gate, consent/PII-free analytics, and self-declared PHR positioning.
4. THE Mobile_App SHALL preserve secure-storage-only credential handling and SHALL not introduce PII into any client log or analytics surface.
5. THE Mobile_App SHALL not change any CLARA_API contract; all parity is achieved through additive client code only.
6. THE Mobile_App SHALL keep the default API base URL aligned with the documented gateway port and SHALL allow override via `--dart-define`.
