# Requirements Document

## Introduction

CLARA_Mobile is the Vietnamese-first Flutter companion to the CLARA-Care web app. Its core surfaces (auth, chat, self-med, council, scribe, PHR, research) already work, but the visual design and interaction quality lag behind the web experience. This feature — **CLARA_Mobile UX Polish** — modernizes the mobile app in three connected ways:

1. **A ChatGPT-class conversational chat surface.** The current chat screen is a minimal bubble list. It will be redesigned into a modern assistant experience: distinct user/assistant message treatments, a smooth streaming/typing feel, auto-scroll with a manual "jump to latest" affordance, an inviting empty state with tappable prompt suggestions, an auto-growing multiline composer with send/stop controls, per-message actions (copy, regenerate), and Markdown rendering for assistant answers — all reusing the existing streaming `ApiClient` and the End_User-safe answer projection.

2. **A unified color system adopted from the web app.** The mobile theme is currently seeded from a teal brand color (`ClaraTokens.brandSeed = 0xFF0F766E`) that no longer matches the web app's blue-based palette. Mobile will adopt the web design tokens (`apps/web/styles/globals.css`) so the two clients look like one product, in both light and dark themes, while preserving WCAG AA contrast.

3. **General UI polish and smoother motion** across shared surfaces — consistent spacing/typography, tasteful transitions, and honoring the OS reduced-motion setting.

All changes are **additive and flag-gated**: a new `mobile_ux_polish_enabled` feature flag (resolved through the existing `MobileFeatureFlagResolver`) governs the redesigned experience. When the flag is absent or false, the app behaves exactly as it does today. The work must preserve the app's existing invariants: Vietnamese-first copy with working localization, accessibility (screen-reader labels, ≥44px touch targets, focus handling), and PII-free analytics that never carry message text or model identity.

### Glossary

- **Experience_V2 theme**: The existing modern Material 3 theme (`ClaraTheme.light()/dark()`) built from `ClaraTokens`, applied by the app root.
- **Web palette**: The design-token color values defined in `apps/web/styles/globals.css` (`:root` for light, `html.dark` for dark), blue-based.
- **Polished chat**: The redesigned ChatGPT-style chat surface introduced by this feature.
- **Answer envelope**: The terminal chat response map (`reply`, `emergency`, `fallback`, citations, etc.) rendered through `EndUserSafeAnswer`.
- **`MobileFeatureFlagResolver`**: The existing resolver that reports whether a named mobile feature flag is enabled.
- **Flags-off equivalence**: The property that, with `mobile_ux_polish_enabled` absent/false, observable behavior equals the pre-feature app.
- **Reduced motion**: The OS "reduce motion" accessibility preference, resolved via the existing `A11y.resolveMotionDuration` helper.
- **AA contrast**: WCAG 2.1 Level AA contrast ratios — 4.5:1 for normal text, 3:1 for large text and non-text UI indicators.
- **Streaming client**: `ApiClient.streamChat` (SSE) with `ApiClient.chat` as the blocking fallback.

## Requirements

### Requirement 1: ChatGPT-style chat layout and message rendering

**User Story:** As a mobile user, I want the chat screen to look and feel like a modern AI chat app, so that conversations are clear, readable, and pleasant.

#### Acceptance Criteria

1. WHERE `mobile_ux_polish_enabled` is true, THE polished chat surface SHALL render user turns and assistant turns with visually distinct treatments (alignment, background, and shape) that are consistent within each role.
2. WHEN an assistant turn reaches its terminal answer envelope, THE polished chat surface SHALL render the answer through the existing `EndUserSafeAnswer` projection for the current role, so that no internal runtime fields are exposed to non-admin roles.
3. THE polished chat surface SHALL render assistant answer text as Markdown, supporting headings, ordered/unordered lists, bold/italic, inline code, fenced code blocks, tables, and links.
4. THE polished chat surface SHALL render the standing Vietnamese-first medical disclaimer and the emergency fast-path affordance with the same copy and directive-only behavior as the current chat screen.
5. WHERE `mobile_ux_polish_enabled` is absent or false, THE app SHALL present the current (pre-feature) chat screen unchanged.

### Requirement 2: Streaming, typing indicator, and auto-scroll

**User Story:** As a mobile user, I want answers to stream in smoothly with a clear typing indicator and automatic scrolling, so that the app feels responsive and alive.

#### Acceptance Criteria

1. WHERE streaming is enabled, THE polished chat surface SHALL consume `ApiClient.streamChat` and progressively append answer tokens to the active assistant turn until a terminal `done` or `error` event.
2. WHILE an assistant turn is streaming and has not yet produced text, THE polished chat surface SHALL display a typing indicator.
3. WHEN new assistant content arrives AND the user is already viewing the latest content, THE polished chat surface SHALL keep the newest content visible by auto-scrolling.
4. WHEN the user has scrolled away from the bottom, THE polished chat surface SHALL NOT auto-scroll AND SHALL present a "jump to latest" affordance that returns to the newest message when activated.
5. WHEN the stream errors or disconnects after partial content, THE polished chat surface SHALL preserve the already-streamed text and show a non-PII error note; IF no content was streamed, THEN it SHALL fall back to the blocking `ApiClient.chat` endpoint.

### Requirement 3: Composer with multiline input and send/stop control

**User Story:** As a mobile user, I want a comfortable message composer that grows with my text and lets me stop a running answer, so that I stay in control of the conversation.

#### Acceptance Criteria

1. THE polished composer SHALL provide a multiline text field that grows with content up to a bounded maximum height and then scrolls internally.
2. WHILE the composer text is empty or contains only whitespace, THE polished composer SHALL disable the send control.
3. WHILE an assistant turn is streaming, THE polished composer SHALL present a stop control that cancels the in-flight stream and finalizes the turn with the content received so far.
4. WHEN the user submits a message while offline (connectivity known to be false), THE polished chat surface SHALL block the send, preserve the typed text, and show the existing offline message.
5. THE send and stop controls SHALL each expose an accessible label and a touch target of at least 44×44 logical pixels.

### Requirement 4: Empty state with prompt suggestions

**User Story:** As a new or returning mobile user, I want a welcoming empty chat state with example prompts, so that I know how to start.

#### Acceptance Criteria

1. WHILE the conversation has no messages, THE polished chat surface SHALL display an empty state with a Vietnamese-first greeting and a set of example prompt suggestions.
2. WHEN a user activates a prompt suggestion, THE polished chat surface SHALL populate the composer with that prompt's text without automatically sending it.
3. WHEN the conversation has at least one message, THE polished chat surface SHALL NOT display the empty state.
4. THE empty-state suggestions SHALL each expose an accessible label and a touch target of at least 44×44 logical pixels.

### Requirement 5: Per-message actions (copy, regenerate)

**User Story:** As a mobile user, I want to copy an assistant answer or regenerate it, so that I can reuse or improve responses.

#### Acceptance Criteria

1. WHERE an assistant turn has finished (non-streaming, with text or an answer envelope), THE polished chat surface SHALL present a copy action that places the answer's plain text on the system clipboard and confirms via a transient message.
2. WHERE an assistant turn has finished, THE polished chat surface SHALL present a regenerate action that re-sends the most recent user prompt and produces a new assistant turn.
3. WHILE any assistant turn is streaming, THE polished chat surface SHALL disable the regenerate action.
4. WHEN a message action is emitted to analytics, THE event SHALL be coarse and SHALL NOT contain message text, prompt text, or model identity.
5. THE copy and regenerate controls SHALL each expose an accessible label and a touch target of at least 44×44 logical pixels.

### Requirement 6: Adopt the web color palette into the mobile theme

**User Story:** As a product owner, I want the mobile app to use the same colors as the web app, so that the two clients feel like one coherent product.

#### Acceptance Criteria

1. THE mobile design tokens SHALL define the brand and surface colors from the web palette values in `apps/web/styles/globals.css` for both light and dark brightness, replacing the current teal brand seed.
2. WHERE `mobile_ux_polish_enabled` is true, THE Experience_V2 light theme SHALL derive its `ColorScheme` from the web light palette (background, surface, primary/brand, text, and status colors) AND the dark theme SHALL derive from the web dark palette.
3. THE mobile theme SHALL map the web status colors (success, warning, danger) to the corresponding semantic roles used by mobile surfaces.
4. THE web-palette color tokens SHALL be expressed as pure constants with no widget, I/O, or analytics dependencies, consistent with the existing `ClaraTokens` style.
5. WHERE `mobile_ux_polish_enabled` is absent or false, THE app SHALL apply the current (pre-feature) theme colors unchanged.

### Requirement 7: WCAG AA contrast for the adopted palette

**User Story:** As a user with low vision, I want text and controls to remain legible after the color change, so that the app stays accessible.

#### Acceptance Criteria

1. THE polished light theme SHALL meet WCAG AA contrast for primary and secondary body text against their background surfaces (≥4.5:1 for normal text, ≥3:1 for large text).
2. THE polished dark theme SHALL meet WCAG AA contrast for primary and secondary body text against their background surfaces (≥4.5:1 for normal text, ≥3:1 for large text).
3. THE polished themes SHALL meet WCAG AA contrast (≥4.5:1) for foreground text on the primary/brand action color in both light and dark.
4. THE polished themes SHALL convey status (success, warning, danger, emergency) through text or iconography in addition to color, so that meaning does not rely on color alone.

### Requirement 8: Motion polish honoring reduced motion

**User Story:** As a mobile user, I want smooth but unobtrusive animations that respect my accessibility settings, so that the app feels refined without causing discomfort.

#### Acceptance Criteria

1. THE polished surfaces SHALL animate message appearance, scrolling, and control state changes using the shared motion duration tokens.
2. WHERE the OS reduced-motion preference is enabled, THE polished surfaces SHALL resolve non-essential motion durations to zero via the existing `A11y.resolveMotionDuration` helper, so that content still appears but without animation.
3. THE polished surfaces SHALL NOT gate the delivery of chat content, answers, or error states on the completion of any animation.

### Requirement 9: Vietnamese-first localization preserved

**User Story:** As a Vietnamese-speaking user, I want the polished UI to remain Vietnamese-first, so that the experience stays natural for me.

#### Acceptance Criteria

1. THE polished surfaces SHALL present all user-facing copy Vietnamese-first, with English used only when the app is explicitly in English mode, matching the existing screens' behavior.
2. THE app SHALL retain the localization delegates required for Material widgets, so that no `MaterialLocalizations`-related failure occurs on any polished surface.
3. THE polished copy (disclaimer, emergency guidance, error, empty state, control labels) SHALL be defined as localizable strings rather than hard-coded English.

### Requirement 10: Flag-gated, analytics-safe, and behavior-preserving

**User Story:** As a platform owner, I want the redesign to be safely rollable and privacy-preserving, so that we can ship it without regressing existing behavior or leaking data.

#### Acceptance Criteria

1. THE redesigned experience SHALL be gated behind the `mobile_ux_polish_enabled` flag resolved through `MobileFeatureFlagResolver`, and SHALL be fully disabled when the flag is absent or false.
2. WHERE `mobile_ux_polish_enabled` is absent or false, THE observable behavior of every affected surface SHALL equal the pre-feature app (flags-off equivalence).
3. THE polished surfaces SHALL emit only coarse, PII-free analytics events, and SHALL NOT send message text, prompt text, transcript content, or model identity to analytics.
4. THE polished chat surface SHALL preserve the existing chat gate (`chat_mobile_enabled`) and the existing session/token behavior, layering the polish flag on top rather than replacing them.
5. THE changes SHALL be additive to the existing mobile app structure and SHALL NOT alter the server API contracts consumed by the mobile client.

## Correctness Properties

These executable properties are validated via property-based testing (PBT) where practical, and via widget/unit tests otherwise.

- **P1 (Flags-off equivalence):** For any app state, WHEN `mobile_ux_polish_enabled` is absent or false, the rendered surfaces and their observable behavior are identical to the pre-feature app. (Req 1.5, 5-off, 6.5, 10.2)
- **P2 (Streaming monotonic accumulation):** For any sequence of `token` events followed by a terminal event, the assistant turn's displayed text equals the in-order concatenation of received token texts; a terminal `done` never discards previously streamed text. (Req 2.1, 2.5)
- **P3 (Auto-scroll gating):** For any scroll position, auto-scroll occurs on new content if and only if the user is at/near the bottom; otherwise the "jump to latest" affordance is offered and position is preserved. (Req 2.3, 2.4)
- **P4 (Send-enable invariant):** For any composer text, the send control is enabled if and only if the trimmed text is non-empty and no send is already in flight. (Req 3.2)
- **P5 (Analytics PII-free):** For any user input (message text, prompt text) and any answer envelope, no analytics event payload contains that free text or any model-identity field. (Req 5.4, 10.3)
- **P6 (Palette parity):** For each named web palette token used by mobile, the corresponding mobile token equals the web value for the matching brightness. (Req 6.1, 6.2)
- **P7 (AA contrast):** For every specified foreground/background pairing in both light and dark polished themes, the contrast ratio meets its WCAG AA threshold. (Req 7.1, 7.2, 7.3)
- **P8 (Reduced-motion collapse):** For any motion token, when reduced motion is enabled the resolved duration is zero, and content/answers/errors are still delivered. (Req 8.2, 8.3)
- **P9 (Suggestion populates, never auto-sends):** For any prompt suggestion activation on an empty conversation, the composer text becomes the suggestion text and no message is sent until the user submits. (Req 4.2)
- **P10 (Stop finalizes safely):** WHEN stop is activated during streaming, the in-flight stream is cancelled and the assistant turn is finalized with exactly the content received before cancellation, with no error state raised for the user-initiated stop. (Req 3.3)
