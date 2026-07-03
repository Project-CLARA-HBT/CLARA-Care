# Requirements Document

Clara Mobile — Liquid Glass modernization (Experience_V3.1).

## Introduction

The Experience_V3 redesign shipped a light-first, centered-Chat mobile app on a
shared `ClaraTokens` design system. This follow-up modernizes the *look and
feel* toward the iOS 26 "Liquid Glass" aesthetic and deepens two thin surfaces
(Home, Tủ thuốc/Cabinet — including camera/photo OCR medication capture), while
enabling the full admin feature set on the mobile client.

The work is purely additive and gated behind the existing
`MOBILE_REDESIGN_ENABLED` build gate plus a new `MOBILE_LIQUID_GLASS_ENABLED`
sub-gate (default OFF). No CLARA_API contract changes are required for the UI
work; the only server change is additive feature-flag keys for the `admin`
role (and their emission by `mobile/summary`), plus a new mobile OCR client
method targeting the *existing* CareGuard scan endpoints.

Safety-first invariants from prior specs remain regression-locked and take
precedence over any visual goal: **glass is chrome-only; all clinical content
stays on opaque, high-contrast surfaces.**

## Glossary

- **Liquid Glass / glass**: the iOS-26-style translucent, blurred, specular-edged
  material used only for navigation and control chrome (nav bar, tab bar, FAB,
  sheets headers, floating chips). Approximated in Flutter with `BackdropFilter`
  + a translucent fill + a hairline specular border + soft layered shadows +
  continuous (squircle) corners.
- **Chrome**: non-content UI — navigation, bars, floating actions, sheet
  handles. Eligible for glass.
- **Clinical/critical content**: chat answers, DDI severity/alerts, dosage
  numbers, FIDES verdicts, consent copy, PHR values. NEVER rendered on glass;
  always opaque, AA-contrast surfaces.
- **`GlassSurface`**: the single reusable widget encapsulating the glass
  material, its reduced-transparency/low-end fallback, and squircle shape.
- **Reduced-transparency fallback**: when the OS "Reduce Transparency"/high
  contrast is on, or the device/battery is low-end, glass renders as an opaque
  surface (no `BackdropFilter`) keeping the same shape/shadow/border.
- **OCR capture**: photographing or picking a medication label image, sending it
  to the CareGuard scan-file endpoint, and importing confirmed detections into
  the cabinet.
- **Experience_V3.1 / this spec**: the liquid-glass modernization layered on the
  Experience_V3 redesign.

## Requirements

### Requirement 1: Liquid Glass design system

**User Story:** As a mobile user, I want a modern, premium iOS-26-style
interface, so that CLARA feels current and trustworthy.

#### Acceptance Criteria

1. THE Mobile_App SHALL provide a `GlassSurface` widget and a `GlassTokens`
   token set (blur sigma by role, translucent fill opacities, hairline border,
   specular sheen gradient, layered shadows, continuous/squircle radii) as the
   single source of truth for glass chrome.
2. THE Mobile_App SHALL render navigation chrome (bottom bar, top bars, the
   centered Chat FAB, sheet headers, floating filter chips) using `GlassSurface`
   when Liquid Glass is enabled.
3. WHERE the OS reports Reduce Transparency, high contrast, or the device is
   detected as low-end/battery-saver, THE `GlassSurface` SHALL render an opaque
   fallback (no `BackdropFilter`) preserving the same shape, border, and shadow.
4. THE Mobile_App SHALL use continuous (squircle) corners for glass surfaces and
   maintain concentric radii for nested elements (inner = outer − padding).
5. THE Mobile_App SHALL cap simultaneous on-screen `BackdropFilter`s (≤3),
   isolate static glass chrome behind `RepaintBoundary`, and never animate blur
   sigma (animating only opacity/gradient) to protect frame rate.
6. WHEN Liquid Glass is disabled (`MOBILE_LIQUID_GLASS_ENABLED=false`), THE
   Mobile_App SHALL render the existing Experience_V3 surfaces unchanged
   (fail-closed, byte-for-byte the current redesign).

### Requirement 2: Clinical-content contrast invariant

**User Story:** As a patient or clinician, I want medical content to stay
perfectly legible, so that safety is never traded for style.

#### Acceptance Criteria

1. THE Mobile_App SHALL render all clinical/critical content (chat answers, DDI
   results, dosage, FIDES verdicts, consent copy, PHR values) on opaque surfaces
   that meet WCAG AA (≥4.5:1 body, ≥3:1 large/non-text).
2. THE Mobile_App SHALL NOT place a `BackdropFilter` behind clinical text.
3. WHERE a glass surface hosts any secondary text, THE fill SHALL be at least the
   "thick" opacity token and the pairing SHALL be verified against the lightest
   plausible background.
4. THE Mobile_App SHALL convey status by text + icon (not color alone) on all
   modernized surfaces, preserving the existing `StatusByText` discipline.

### Requirement 3: Richer, modern Home

**User Story:** As a user, I want a Home screen that feels alive and useful, so
that I can see my health context and jump into tools quickly.

#### Acceptance Criteria

1. THE Home surface SHALL present a glass hero header (time-of-day greeting, role
   chip) over the app canvas, with the quick-action tools as modern cards.
2. THE Home surface SHALL show a role-aware, sectioned layout: a primary "tiếp
   tục" / featured action, a quick-actions grid, and a "recent activity" region
   with a friendly empty state (no fabricated data).
3. THE Home surface SHALL derive privileged tools fail-closed from the loaded
   role-scoped summary (a null/unloadable summary shows no privileged cards).
4. THE Home surface SHALL load with a skeleton, offer pull-to-refresh, and show
   `ErrorRetryView` on load failure.
5. WHERE health context is available without new endpoints (e.g. cabinet item
   count, PHR presence), THE Home surface MAY surface it as at-a-glance stat
   cards; otherwise it SHALL omit them rather than fabricate values.
6. THE Home surface SHALL preserve the standing "hỗ trợ quyết định, không thay
   thế bác sĩ" positioning.

### Requirement 4: Feature-rich Cabinet with OCR capture

**User Story:** As a user, I want to add medicines by photographing their labels,
so that building my cabinet is fast and accurate.

#### Acceptance Criteria

1. THE Cabinet surface SHALL offer an "add by photo" affordance that captures a
   photo (camera) or picks an image, then calls the CareGuard scan-file endpoint
   via a new `ApiClient` multipart method.
2. THE Cabinet surface SHALL present OCR detections for review with a
   manual-confirm gate: low-confidence detections MUST be explicitly confirmed
   before import (mirroring the server confirm-gate contract), and nothing is
   imported without user confirmation.
3. THE Cabinet surface SHALL import confirmed detections via the
   import-detections endpoint and refresh the cabinet.
4. THE Cabinet surface SHALL keep the existing consent gate, ≥2-distinct-medicine
   DDI guard, offline-mutation block, and End_User DDI projection
   (`DdiResultView`) intact and unchanged.
5. THE Cabinet surface SHALL present items as modern cards with structured fields
   (drug, brand, manufacturer, dosage, form, quantity, expiry, note), expiry
   status by text+icon, and per-item normalization/needs-review status.
6. WHERE camera/photo permission is denied or unavailable, THE Cabinet surface
   SHALL fall back to manual entry and surface a clear, non-blocking message.
7. WHEN offline, THE Cabinet surface SHALL block the OCR capture/import mutation
   with the standard offline message and preserve any entered data.

### Requirement 5: Full admin feature enablement (mobile)

**User Story:** As an admin, I want every mobile feature available to me, so that
I can operate and demo the full product.

#### Acceptance Criteria

1. THE `mobile/summary` endpoint SHALL emit, for the `admin` role, every mobile
   feature-flag key the client consumes: `research`, `careguard`, `council`,
   `system_monitor`, `chat_mobile_enabled`, `selfmed_cabinet_mobile_enabled`,
   `scribe_mobile_enabled`, `phr_enhanced_mobile_enabled`,
   `model_disclosure_mobile_enabled`, `transparency_notice_mobile_enabled`,
   `consent_center_mobile_enabled`, `sharing_mobile_enabled`,
   `research_mobile_deep`, and `mobile_ux_polish_enabled` — all `true`.
2. THE server change SHALL be additive per role (the role→flags map remains the
   single source of truth) and SHALL NOT weaken any non-admin role's gates.
3. THE Mobile_App SHALL, for an authenticated admin, surface every gated
   destination (Chat incl. deep research, Cabinet, PHR enhanced, Council,
   Scribe, Consent center, etc.) via the existing fail-closed resolver.
4. THE server change SHALL preserve RBAC: non-authorized roles for a given route
   still receive 403; enabling flags does not bypass `require_roles`.
5. THE Mobile_App SHALL treat unknown/missing flags as OFF (fail-closed),
   unchanged.

### Requirement 6: Modernized surfaces across the app

**User Story:** As a user, I want the whole app — not just Home — to feel modern,
so that the experience is cohesive.

#### Acceptance Criteria

1. THE Mobile_App SHALL apply the glass chrome + modern card/spacing treatment
   consistently across the shell, Home, Cabinet, PHR, Council, Scribe, Settings,
   Chat, and More surfaces.
2. THE Mobile_App SHALL use spring-based/settle micro-interactions for signature
   moments (FAB, sheet reveals) resolved through `A11y.resolveMotionDuration` so
   they collapse under reduced motion.
3. THE Mobile_App SHALL preserve every existing surface's data contract,
   role/consent gating, and safety behavior while restyling.
4. THE Mobile_App SHALL keep ≥48dp tap targets, honor the OS text scaler, and
   expose semantics on all restyled controls.

### Requirement 7: Server model swap (DeepSeek v4)

**User Story:** As an operator, I want the server to run the newer DeepSeek v4
models, so that answer quality improves without code changes.

#### Acceptance Criteria

1. THE deployed server `.env` SHALL set the primary model to `deepseek-v4-pro`
   with a fallback of `deepseek-v4-flash`, and the base URL to the
   `api.yescale.vip` endpoint, keeping existing keys and other settings.
2. THE change SHALL be applied to the running deployment and validated via the
   API/ML health endpoints returning healthy after restart.
3. THE change SHALL NOT alter the DeepSeek-only runtime posture, timeout floors,
   or any safety guardrail.

### Requirement 8: Rollout safety and verification

**User Story:** As a maintainer, I want the modernization verifiable and safe to
ship, so that quality holds.

#### Acceptance Criteria

1. THE Mobile_App SHALL pass `flutter analyze` clean (no new errors/warnings in
   modernized files) and `flutter test` green for new/changed tests.
2. THE Mobile_App SHALL include tests for: `GlassSurface` fallback logic, the
   clinical-content opaque-surface invariant, Home fail-closed tool derivation,
   Cabinet OCR confirm-gate (nothing imported unconfirmed) and offline block,
   and the admin full-enablement resolver.
3. THE release SHALL be built for Android and installed on the test device with
   the redesign + liquid-glass gates on and pointing at the live gateway domain.
