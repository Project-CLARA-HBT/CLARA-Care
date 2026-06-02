# Requirements Document

## Introduction

This feature brings the CLARA-Care platform (a Vietnamese, safety-first medical AI assistant) to flagship quality ahead of an upcoming scientific research report. It spans five concerns across the existing polyglot monorepo (Next.js web, FastAPI API gateway, FastAPI ML service, Flutter mobile):

1. **Per-surface polish and audit-driven bug fixing** across chat, research, selfmed/CareGuard, council, scribe, admin control tower, and mobile, prioritized by user impact.
2. **UX modernization** informed by competitive/market research on comparable products, drawing on general UX patterns only (no proprietary or copyrighted content).
3. **A three-part analytics layer**: (a) internal product/usage analytics admin dashboard, (b) clinical-quality and pipeline-health analytics building on existing observability, and (c) third-party event analytics SDK integration across web and mobile.
4. **Flutter mobile parity** improvements, including persistent session storage.
5. **Preservation of existing safety guardrails** (RBAC, consent gating, emergency fast-path, FIDES verification, no-PII telemetry) throughout all changes.

The existing analytics surfaces (admin observability, system metrics, scribe analytics summary) are extended and complemented, not duplicated.

## Glossary

- **CLARA_Web**: The Next.js web application (`apps/web`).
- **CLARA_API**: The FastAPI API gateway service (`services/api`) that owns auth, RBAC, consent, and proxying.
- **CLARA_ML**: The FastAPI ML orchestration service (`services/ml`) that owns routing, RAG, and domain agents.
- **CLARA_Mobile**: The Flutter mobile client (`apps/mobile`).
- **Surface**: A user-facing feature area: Chat, Research, SelfMed, CareGuard, Council, Scribe, Admin Control Tower, Dashboard, or Mobile.
- **End_User**: A non-administrative user with role `normal`, `researcher`, or `doctor`.
- **Admin_User**: A user with role `admin`.
- **DDI**: Drug-Drug Interaction analysis produced by the CareGuard agent.
- **Telemetry**: Internal diagnostic data such as runtime mode, fallback flags, retrieval stack, source errors, and trace metadata.
- **Fast_Mode**: The Chat/Research mode labeled `Nhanh`, internally mapped to tier1 chat.
- **Deep_Mode**: Research modes labeled `Tư duy`/`Pro`, internally `deep`/`deep_beta` tier2 jobs.
- **Product_Analytics**: Internal usage analytics (feature adoption, active users, funnels, retention) presented to Admin_Users.
- **Clinical_Analytics**: Quality and pipeline-health analytics (verification outcomes, DDI severity distribution, routing accuracy, latency, fallback rates) presented to Admin_Users.
- **Analytics_SDK**: A third-party event analytics provider integration (PostHog, Google Analytics, or Plausible).
- **PII**: Personally Identifiable Information, including names, emails, free-text medical queries, drug lists, and patient content.
- **Consent_Status**: The per-user medical-data consent state recorded by CLARA_API (`UserConsent`).
- **RBAC**: Role-Based Access Control enforced by CLARA_API via `require_roles(...)`.
- **Session_Store**: The persistent credential/session storage on CLARA_Mobile.
- **Competitive_Research_Report**: An agent-produced document summarizing general UX/capability patterns from comparable products with source attribution and no verbatim copyrighted content.
- **CLARA_Delivery**: The engineering delivery effort (the agent and contributors) responsible for auditing Surfaces, conducting competitive research, planning fixes, running quality gates, and updating documentation. This is a non-runtime actor representing process outputs rather than a deployed service.
- **Audit_Record**: A written record produced by CLARA_Delivery that enumerates, per Surface, the defects found and their severity rank.

## Requirements

### Requirement 1: Audit-driven, impact-prioritized bug fixing

**User Story:** As a product owner, I want every implemented surface audited and its defects fixed in priority order, so that the platform is reliable enough to be the subject of a scientific research report.

#### Acceptance Criteria

1. THE CLARA_Delivery SHALL produce an Audit_Record that lists, for each Surface, the defects found and a severity rank of `critical`, `high`, `medium`, or `low` based on End_User impact.
2. WHEN a defect is ranked `critical` or `high`, THE CLARA_Delivery SHALL place a corresponding fix task in the implementation plan before any `medium` or `low` defect on the same Surface.
3. WHEN a bug fix is applied to a Surface, THE CLARA_Delivery SHALL add an automated test that fails on the pre-fix behavior and passes on the post-fix behavior.
4. THE CLARA_API SHALL pass `make lint` and the service test suite after each batch of fixes.
5. THE CLARA_ML SHALL pass `make lint` and the service test suite after each batch of fixes.

### Requirement 2: Chat routing and timeout correctness

**User Story:** As an End_User asking a short question, I want a fast answer through the chat path instead of the long research pipeline, so that I am not left waiting on a spinner.

#### Acceptance Criteria

1. WHEN an End_User submits a query in Fast_Mode, THE CLARA_Web SHALL send the request to the tier1 chat endpoint rather than the research tier2 job pipeline.
2. WHILE a query is processed in Deep_Mode, THE CLARA_Web SHALL route the request to the research tier2 job pipeline.
3. WHEN `LLM_DEEPSEEK_ONLY` is enabled and the supplied runtime matches the configured DeepSeek environment, THE CLARA_ML SHALL reuse the default DeepSeek client instead of creating a runtime client with a shortened timeout.
4. THE CLARA_API SHALL apply an ML request timeout that is greater than or equal to the CLARA_ML synthesis timeout for the same request.
5. IF the chat pipeline cannot return an answer before its timeout, THEN THE CLARA_Web SHALL display a user-readable retry message that excludes raw error codes and stack traces.

### Requirement 3: DDI output clarity for non-expert users

**User Story:** As an End_User checking my medicines, I want interaction results in plain Vietnamese without internal diagnostics, so that I understand the risk and what to do.

#### Acceptance Criteria

1. WHEN CareGuard returns a DDI result to an End_User, THE CLARA_Web SHALL display only risk level, alerts, recommendations, and reference sources, and SHALL exclude runtime mode, fallback flags, and `source_errors` blocks.
2. IF the CareGuard analysis produces only openFDA co-occurrence evidence without a local or RxNav alert, THEN THE CLARA_ML SHALL omit a standalone synthetic alert and SHALL retain openFDA data only as enrichment for an existing alert.
3. WHEN at least one `drug_drug` alert is ranked `medium`, THE CLARA_ML SHALL aggregate the overall risk level to at least `medium`.
4. THE CLARA_Web SHALL present DDI alert messages and recommendations in Vietnamese for the common risk groups, including bleeding, reduced clopidogrel efficacy, drowsiness or dizziness, hyperkalemia, and myopathy risk.
5. WHEN a DDI check is requested with fewer than two medicines, THE CLARA_Web SHALL prompt the End_User to add at least two medicines and SHALL NOT call the DDI analysis.
6. IF an upstream connector returns an error such as `openfda http_400` while another source still provides a valid signal, THEN THE CLARA_Web SHALL hide the connector error from the End_User.

### Requirement 4: No telemetry or internal-error leakage to end users

**User Story:** As an End_User, I want a clean interface without engineering jargon, so that the product feels trustworthy and approachable.

#### Acceptance Criteria

1. THE CLARA_Web SHALL exclude internal telemetry labels such as `research mode`, `retrieval`, `RAG mode`, `Fallback mode`, and `Policy: Warn/Allow` from primary End_User views.
2. WHEN CLARA_API returns an upstream error, THE CLARA_Web SHALL render a sanitized message that excludes internal URLs, connector identifiers, and HTTP status detail strings.
3. WHERE an Admin_User views a Surface, THE CLARA_Web SHALL expose detailed telemetry panels that remain hidden from non-admin roles.
4. THE CLARA_Web SHALL present mode labels to End_Users as `Nhanh`, `Tư duy`, `Pro`, `Tự chọn`, and `Đầy đủ`.

### Requirement 5: UX modernization and accessibility polish

**User Story:** As an End_User, I want a modern, consistent, and accessible interface across every surface, so that the product feels best-in-class.

#### Acceptance Criteria

1. THE CLARA_Web SHALL apply a consistent set of design tokens for color, spacing, radius, and typography across Chat, Research, SelfMed, CareGuard, Council, Scribe, Dashboard, and Admin surfaces.
2. WHEN an End_User loads a primary Surface, THE CLARA_Web SHALL render distinct loading, empty, error, and populated states for asynchronous content.
3. THE CLARA_Web SHALL meet WCAG 2.1 AA contrast ratios for text and interactive controls on primary Surfaces.
4. WHEN an End_User navigates with a keyboard, THE CLARA_Web SHALL expose a visible focus indicator and a logical tab order on interactive controls.
5. WHERE a Surface displays primary actions, THE CLARA_Web SHALL provide Vietnamese task-oriented labels consistent with the existing guidance page.

### Requirement 6: Competitive-research-informed improvements without copyright infringement

**User Story:** As a product owner, I want improvement ideas grounded in how comparable products solve similar problems, so that CLARA adopts proven patterns without copying protected content.

#### Acceptance Criteria

1. THE CLARA_Delivery SHALL produce a Competitive_Research_Report covering products comparable to each major Surface.
2. THE Competitive_Research_Report SHALL describe only general UX patterns and capabilities and SHALL exclude verbatim copyrighted text and proprietary assets.
3. WHEN the Competitive_Research_Report cites an external source, THE Competitive_Research_Report SHALL include an attribution link to that source.
4. WHEN an improvement is implemented based on the Competitive_Research_Report, THE CLARA_Delivery SHALL reference the originating pattern in the implementation plan.

### Requirement 7: Internal product and usage analytics dashboard

**User Story:** As an Admin_User, I want a product analytics dashboard, so that I can measure feature adoption, active users, and usage funnels.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL expose Product_Analytics metrics covering active users, per-Surface usage counts, and conversion funnels.
2. IF a request to a Product_Analytics endpoint lacks the `admin` role, THEN THE CLARA_API SHALL respond with HTTP 403.
3. WHEN an Admin_User opens the Product_Analytics dashboard, THE CLARA_Web SHALL display active-user trends, per-Surface adoption, and retention over a selectable date range.
4. THE CLARA_API SHALL aggregate Product_Analytics metrics without returning End_User free-text query content or drug lists.
5. WHEN no data exists for the selected date range, THE CLARA_Web SHALL display an explicit empty state on the Product_Analytics dashboard.

### Requirement 8: Clinical-quality and pipeline-health analytics

**User Story:** As an Admin_User, I want clinical-quality and pipeline-health analytics built on existing observability, so that I can monitor verification outcomes and routing health for the research report.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL expose Clinical_Analytics metrics covering FIDES verification verdict distribution, DDI severity distribution, router role/intent confidence, fallback rate, and per-tier latency.
2. THE CLARA_API SHALL derive Clinical_Analytics from existing observability, system metrics, and flow-event sources rather than introducing a duplicate collection path for those signals.
3. WHEN an Admin_User opens the Clinical_Analytics dashboard, THE CLARA_Web SHALL display verification outcomes, DDI severity distribution, and latency percentiles for a selectable date range.
4. WHEN a `CRITICAL` claim is blocked by FIDES verification, THE CLARA_API SHALL count the event in the Clinical_Analytics blocked-claims metric.
5. THE CLARA_Web SHALL render Clinical_Analytics separately from the existing scribe analytics summary without removing the scribe summary.

### Requirement 9: Third-party event analytics SDK integration

**User Story:** As a product owner, I want a third-party analytics SDK wired into web and mobile, so that I can track product events with an established analytics tool.

#### Acceptance Criteria

1. WHERE an Analytics_SDK is configured, THE CLARA_Web SHALL initialize the Analytics_SDK and emit named product events for primary Surface interactions.
2. WHERE an Analytics_SDK is configured, THE CLARA_Mobile SHALL initialize the Analytics_SDK and emit named product events for primary screen interactions.
3. IF an End_User has not granted analytics Consent_Status, THEN THE CLARA_Web SHALL suppress all Analytics_SDK event transmission.
4. THE CLARA_Web SHALL exclude PII from every Analytics_SDK event payload, including names, emails, free-text queries, and drug lists.
5. WHERE no Analytics_SDK credentials are configured, THE CLARA_Web SHALL operate normally with Analytics_SDK transmission disabled.
6. THE CLARA_Web SHALL identify users in Analytics_SDK events by an opaque pseudonymous identifier rather than email or name.

### Requirement 10: Mobile feature parity and persistent session

**User Story:** As a CLARA_Mobile user, I want my session to persist across app restarts and more web features available on mobile, so that the mobile experience is closer to the web.

#### Acceptance Criteria

1. WHEN an End_User authenticates on CLARA_Mobile, THE CLARA_Mobile SHALL store the session credentials in the persistent Session_Store.
2. WHEN CLARA_Mobile restarts while a stored session remains valid, THE CLARA_Mobile SHALL restore the authenticated session without requiring re-login.
3. WHEN a stored session token is expired or invalid on launch, THE CLARA_Mobile SHALL clear the Session_Store and route the End_User to the login screen.
4. THE CLARA_Mobile SHALL provide functional parity for login, dashboard, research, CareGuard, and council screens against their CLARA_Web counterparts within the scope of mobile-supported actions.
5. WHEN an End_User signs out on CLARA_Mobile, THE CLARA_Mobile SHALL remove all stored credentials from the Session_Store.

### Requirement 11: Safety guardrail preservation

**User Story:** As a safety officer, I want all existing guardrails preserved across the polish and analytics work, so that no change weakens medical safety or privacy.

#### Acceptance Criteria

1. THE CLARA_API SHALL continue to enforce RBAC on every endpoint that required a role before this feature.
2. WHEN an End_User accesses a medical-data Surface without granted Consent_Status, THE CLARA_Web SHALL continue to present the consent gate before showing medical content.
3. WHEN an emergency symptom is detected, THE CLARA_ML SHALL continue to return the emergency escalation response and SHALL NOT perform diagnostic reasoning.
4. WHEN a `CRITICAL` drug dosage or DDI claim fails verification, THE CLARA_ML SHALL continue to block the response.
5. THE CLARA_API SHALL exclude PII from system metrics, flow events, and analytics aggregation outputs.
6. WHEN a mutating request uses cookie authentication, THE CLARA_API SHALL continue to enforce CSRF protection.

### Requirement 12: Documentation and configuration drift correction

**User Story:** As a developer, I want project documentation and configuration to match the as-built system, so that onboarding and operations are reliable.

#### Acceptance Criteria

1. THE CLARA_Delivery SHALL update `CLAUDE.md` so that the repository is described as an implemented monorepo rather than documentation-only.
2. WHEN a configuration key is defined more than once in `.env.example`, THE CLARA_Delivery SHALL reduce that key to a single authoritative definition.
3. THE CLARA_Delivery SHALL update `data/docs/index.md` references so that they resolve to existing paths in the current repository structure.
4. THE CLARA_Delivery SHALL document the new Product_Analytics, Clinical_Analytics, and Analytics_SDK configuration keys in `.env.example`.
