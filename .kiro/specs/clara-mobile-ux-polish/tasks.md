# Implementation Plan — CLARA_Mobile UX Polish

- [ ] 1. Feature flag + dependency scaffolding
- [ ] 1.1 Add the `mobile_ux_polish_enabled` gate to `MobileFeatureFlags`, its `--dart-define` build default, the `kMobileUxPolishEnabled` compile-time constant, and the `uxPolishEnabled` resolver getter in `lib/core/feature_flags.dart`. (Req 6, 10.1)
- [ ] 1.2 Add `markdown: ^7.3.1` to `pubspec.yaml` and run `flutter pub get`. (Req 1.3)

- [ ] 2. Web-palette color system
- [ ] 2.1 Create `lib/theme/web_palette.dart` with pure `Color` constants ported (and AA-adjusted where documented) from `apps/web/styles/globals.css` for light and dark, plus a `WebColorScheme.of(brightness)` bundle and a `ClaraStatusColors` `ThemeExtension` (success/warning). (Req 6.1, 6.3, 6.4)
- [ ] 2.2 Extend `ClaraTheme.light/dark` with a `polished` flag: when true, derive the `ColorScheme` from `WebPalette` (explicit roles) and attach `ClaraStatusColors`; when false, keep the current teal-seed theme unchanged. (Req 6.2, 6.5, 5-off)
- [ ] 2.3 Wire `app.dart` to pass `polished: kMobileUxPolishEnabled` to the theme factories on the V2 path; leave the legacy path byte-for-byte unchanged. (Req 6.5, 10.2)

- [ ] 3. Markdown renderer
- [ ] 3.1 Create `lib/widgets/markdown_view.dart`: `MarkdownView` renders GitHub-flavored Markdown (headings, ordered/unordered lists, bold/italic, inline code, fenced code blocks, tables, links, block quotes, rules) themed from the `ColorScheme`; links render as colored non-navigating spans with the URL as semantics label. (Req 1.3)
- [ ] 3.2 Add pure `mdToPlainText(String)` for the copy action and unit-test it. (Req 5.1)

- [ ] 4. Polished chat building blocks
- [ ] 4.1 Create `lib/screens/chat/chat_empty_state.dart`: Vietnamese-first greeting + tappable prompt suggestions, each ≥44px with an accessible label; a callback populates the composer without sending. (Req 4.1–4.4, 9.1, 9.3, P9)
- [ ] 4.2 Create `lib/screens/chat/chat_bubbles.dart`: `UserBubble`, `AssistantBubble` (Markdown for streamed text, `EndUserSafeAnswer` for terminal envelope), `TypingIndicator`, and `MessageActions` (copy/regenerate) with ≥44px labeled targets; regenerate disabled while any turn streams. (Req 1.1, 1.2, 2.2, 5.1–5.5)
- [ ] 4.3 Create `lib/screens/chat/chat_composer.dart`: auto-growing multiline field (bounded max height then internal scroll), send disabled on empty/whitespace, stop control while streaming, offline-aware block, ≥44px labeled send/stop. (Req 3.1–3.5, P4)
- [ ] 4.4 Add a pure `isNearBottom(pixels, maxExtent, threshold)` helper (in `polished_chat_view.dart` or a small util) for auto-scroll gating. (Req 2.3, 2.4, P3)

- [ ] 5. Polished chat view + screen integration
- [ ] 5.1 Create `lib/screens/chat/polished_chat_view.dart` assembling empty state, message list, jump-to-latest affordance, composer, standing disclaimer, and emergency affordance, using shared motion tokens resolved through `A11y.resolveMotionDuration`. (Req 1.4, 2.3, 2.4, 8.1–8.3)
- [ ] 5.2 Add a `polished` field to `ChatScreen` (default false) and delegate the body to `PolishedChatView` when true; keep the legacy body and all existing keys when false. (Req 1.5, 10.4, P1)
- [ ] 5.3 Refactor `_runStreaming` to use a retained `StreamSubscription` + `_cancelled` guard so a stop cancels the stream and finalizes the turn with buffered text and no error; add the `mobile_chat_stopped` coarse event. (Req 3.3, P10)
- [ ] 5.4 Implement regenerate: drop the assistant turn, resubmit the preceding user prompt through the send path; disable while streaming; coarse `mobile_chat_regenerated` event. (Req 5.2, 5.3, 5.4)
- [ ] 5.5 Track `_atBottom`/`_showJumpToLatest` from the scroll controller and gate auto-scroll accordingly. (Req 2.3, 2.4)
- [ ] 5.6 Pass `polished: resolver.uxPolishEnabled` where `ChatScreen` is constructed in `home_screen.dart` and `dashboard_screen.dart`. (Req 10.1)

- [ ] 6. Tests
- [ ] 6.1 Palette parity + AA contrast unit tests (`test/theme/web_palette_test.dart`). (P6, P7)
- [ ] 6.2 Markdown `mdToPlainText` + render smoke tests. (Req 1.3, 5.1)
- [ ] 6.3 Polished chat widget tests: empty-state suggestion populates without sending (P9), send-enable invariant (P4), stop finalizes safely (P10), regenerate (Req 5.2/5.3), jump-to-latest gating (P3), typing indicator (Req 2.2), flags-off equivalence (P1). (Req 1–5, 8, P1/P3/P4/P9/P10)
- [ ] 6.4 Analytics PII-free assertions for the new coarse events. (P5, Req 5.4, 10.3)

- [ ] 7. Build, install, and manual verification
- [ ] 7.1 `flutter analyze` and `flutter test` clean.
- [ ] 7.2 Build the debug APK with the polish + V2 flags on and install via adb to the connected device.
- [ ] 7.3 Manually verify on-device: modern look, web-matching colors (light/dark), smooth streaming, auto-scroll + jump-to-latest, composer grow + stop, empty-state suggestions, copy/regenerate, and Vietnamese-first copy; iterate until stable and smooth.

## Web feature-parity roadmap (extension)

The web app (`apps/web`) exposes these role-gated surfaces: Chat (routed + research tiers), Dashboard, PHR, SelfMed/CareGuard (cabinet + DDI + VN dictionary), Council (intake/consult/result), Scribe (SOAP), Workspace (folders/channels/share/export/notes), and Admin (overview, knowledge-sources, answer-flow, observability). Mobile already has auth, dashboard, chat, careguard, selfmed cabinet, council, scribe, PHR, consent center, DSAR, and shared-resource screens. Parity work applies the same polish (web palette + motion + Vietnamese-first + a11y) to every mobile surface and closes functional gaps.

- [ ] 8. Apply the web-palette theme + motion polish consistently across all existing mobile screens (dashboard, PHR, careguard, selfmed, council, scribe, consent, DSAR, shared-resource, home shell) so the whole app matches the web look. (Req 6, 8)
- [ ] 9. Chat research tiers: expose `fast` / `deep` / `deep_beta` modes on mobile chat (mode selector), mirroring the web unified chat, using the existing tier2 job/poll/SSE API surface where available. (parity)
- [ ] 10. CareGuard parity: medication-label scan/OCR entry, VN drug-dictionary lookup, and severity-ranked DDI result view matching the web CareGuard. (parity)
- [ ] 11. Council parity: full intake → consult → result case flow with consensus/divergence display. (parity)
- [ ] 12. Workspace surface: folders/channels/notes read + share/export, matching the web workspace (feature-flagged). (parity)
- [ ] 13. Admin-only surfaces (observability/flow-events, knowledge sources) as read views for admin role, PII-free. (parity)
- [ ] 14. Per-screen widget tests + on-device verification for each parity surface; small commits per surface.
