# Product specification — CLARA calm, task-first experience

## Problem statement

CLARA has broad personal, clinical, research, and administrative capability, but the current interface exposes too many destinations and panels at once. Navigation mirrors modules rather than user intent; several screens compete for attention; icon-font and dialog failures reduce trust; and professional diagnostics can dominate the health answer. A previous “simplification” demonstrated the opposite failure: hiding routes without a workspace and More model made the product look incomplete. This modernization must reduce cognitive load while preserving discoverability and every authorized capability.

## Goals

1. Give each screen one dominant task or decision.
2. Organize navigation into permitted Personal, Clinical, Research, and Administration workspaces, each with at most seven primary items.
3. Keep every capability reachable through primary navigation, More, contextual actions, focused flows, or compatible direct links.
4. Establish one calm, semantic light/dark design system and a reliable bundled SVG icon layer.
5. Make personal health setup and care workflows progressive, resumable, and plain-language Vietnamese first.
6. Prioritize health answers, warnings, actions, uncertainty, and sources over internal telemetry.
7. Align Council and Scribe with the main shell while preserving clinician control, consent, auditability, and safety.
8. Achieve WCAG 2.2 AA for applicable interfaces and create repeatable responsive/visual evidence.
9. Reduce coupling in the shell, navigation, and large feature surfaces without replacing the stack.

## Non-goals

- Replacing Next.js, React, Tailwind, or the API/ML architecture.
- Changing medical decision logic, DrugBank authority, FIDES, emergency routing, or LifeMap truth-state rules.
- Inventing a patient directory, clinical work queue, or Admin Settings service that the backend does not provide.
- Merging medication data models by display name.
- Removing legacy aliases or the Chat rollback path before their documented retirement gates.
- Exposing chain-of-thought, raw prompts, uncalibrated confidence, provider secrets, or PII.
- Treating hidden navigation as authorization.

## Target personas

- Personal user (`normal`): wants clear daily actions, trustworthy answers, medication safety, and control of personal data.
- Researcher (`researcher`): needs evidence discovery, provenance, structured research modes, and query history without operational telemetry clutter.
- Clinician (`doctor`): needs patient-context tools already supported by the active profile, Council, Scribe, evidence, and unambiguous clinician review states.
- Administrator (`admin`): needs knowledge operations, answer-flow controls, observability, analytics, audit/compliance, and optional deep diagnostics.
- Supporter/recipient: uses bounded invitations/public capabilities and needs explicit scope, duration, and revocation communication.

## Current pain points

- Flat role menu reaches 25 entries.
- Repeated Ask CLARA/profile/logout controls.
- Desktop and mobile shell behavior diverges.
- PHR icons display raw ligature names.
- Today, Dashboard, LifeMap, Visits, Family, and Scribe are visually overloaded.
- Chat can display three major columns and internal stages before the answer.
- Synthetic Dashboard fallbacks and uncalibrated confidence undermine medical trust.
- Dialog/focus behavior is inconsistent.
- Typography and touch targets are too small in multiple flows.
- Global CSS and oversized client components slow safe change.

## Product principles

1. Safety before visual simplicity.
2. One dominant task; progressively disclose secondary detail.
3. Preserve access; simplify presentation.
4. Data truth over decorative completeness—empty is better than fabricated.
5. Plain language before internal terminology.
6. Server authorization is authoritative.
7. Explicit confirmation for health, share, sign, delete, and release actions.
8. Mobile is a purpose-built layout, not a squeezed desktop.
9. Light mode is the reference; dark mode has full parity.
10. Compatibility is explicit, tested, and time-bounded.

## Target experience

After authentication, CLARA selects a permitted workspace from the server-verified role and the requested route. The sidebar shows a compact workspace switcher and no more than seven primary destinations. Secondary capabilities remain in More and contextual flows. The page owns its heading; the topbar provides only useful global context, notifications/help, and one profile menu.

Personal care opens on Today. Empty Today presents one journey CTA and one Ask CLARA text action. LifeMap, Visit preparation, medicine onboarding, Family invitation, and PHR sections use focused URL-addressable steps. Chat keeps the answer and composer primary; sources and user-safe rationale are disclosures; expert/admin diagnostics are role-gated and lazy. Council presents escalation and consensus before metrics. Scribe follows Capture → Transcript review → SOAP review → Completion, with consent and signed/finalized semantics explicit.

## In-scope screens

- Shell, sidebar, topbar, profile menu, workspace switcher, mobile navigation, unauthorized state.
- Overview/Dashboard, Today, LifeMap, Visit preparation, Family, PHR, Medicines.
- Chat, research modes/history, Living Evidence, research Source Hub.
- Council and its wizard/result routes; Scribe.
- Admin landing/navigation consistency and shared primitives on touched admin screens.
- Public/auth pages insofar as tokens, icon resilience, focus, theme, and screenshots are concerned.

## Out-of-scope behavior

- New clinical inference or data authority.
- New external integrations.
- Destructive database migrations.
- A new patient-list product without backend support.
- Full mobile Flutter redesign; shared terminology remains synchronized, but this program targets the production web app.

## Success metrics

| Metric | Target |
|---|---|
| Primary nav count | ≤7 per workspace; mobile ≤4 + More. |
| Capability reachability | 100% active/conditional routes classified and reachable when authorized. |
| Duplicate shell actions | One Ask CLARA entry and one profile trigger per viewport. |
| Raw icon names | Zero on representative pages with third-party fonts blocked. |
| Accessibility | No Critical/Serious automated findings on representative routes; documented manual WCAG 2.2 AA checks. |
| Validation | Lint, explicit type-check, unit, integration, build, i18n/terminology, E2E and affected safety tests pass. |
| Responsive evidence | Desktop, laptop, tablet, and 390×844 mobile screenshots for required routes. |
| Performance | No second icon library; common/per-route build sizes stay within measured baseline +5% unless approved and explained. |
| Trust | No synthetic production metrics or uncalibrated confidence; safety/provenance remain visible. |

## Risks and mitigations

- Hidden capability regression: route registry and capability-reachability tests precede menu changes.
- Shell redirect loops: characterize session/onboarding/profile behavior, then extract incrementally.
- Safety information collapsed: only secondary technical detail may be hidden; warnings/escalation remain primary.
- Citation numbering regression: normalize one source view-model before consolidating displays.
- Legacy breakage: preserve aliases and rollback flag; use milestone commits.
- Screenshot churn: fixed locale/timezone/fixtures, reduced motion, and masked dynamic data.
- Scope expansion into backend: use existing contracts first; isolate optional API hardening such as PHR concurrency.

## Launch and rollback

Ship in milestone commits. Foundations are backward-compatible aliases; shell/workspace changes may use a short-lived `NEXT_PUBLIC_UI_SHELL_V2` kill switch only if rollout risk warrants it. Both paths share the same route-access module. Preserve Chat V2 rollback and all route redirects. Revert the last stable milestone rather than rewriting history. No UI feature flag may weaken RBAC, consent, medical safety, or audit behavior.

