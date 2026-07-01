# Technical Design — CLARA_Mobile UX Polish

## Overview

This feature modernizes CLARA_Mobile to feel like one product with CLARA_Web. It delivers three connected changes, all **additive and flag-gated** behind a new `mobile_ux_polish_enabled` flag resolved through the existing `MobileFeatureFlagResolver`:

1. **A ChatGPT-class chat surface** — distinct user/assistant treatments, streaming with a typing indicator, auto-scroll + jump-to-latest, an inviting empty state with prompt suggestions, an auto-growing composer with send/stop, per-message copy/regenerate, and Markdown rendering for assistant answers.
2. **A unified color system adopted from the web palette** (`apps/web/styles/globals.css`) for both light and dark themes, preserving WCAG AA contrast.
3. **General polish and smoother motion** honoring reduced-motion.

When the flag is absent or false, the app is byte-for-byte the pre-feature experience (Property P1). No CLARA_API contract changes.

### Design principles (from the codebase)

- **Purity of tokens/themes.** `ClaraTokens`, `ClaraTypography`, and the new palette module are pure constants/factories — no widgets, I/O, or analytics — mirroring the existing style.
- **Fail-closed flags.** New gates default to `false` in both the server-flag and `--dart-define` halves of the resolver.
- **PII-free analytics.** The chat surface never hands free text or model identity to analytics; only coarse booleans/counts.
- **End_User-safe answers.** Terminal envelopes always render through the existing `EndUserSafeAnswer` projection for the current role.
- **Minimal dependencies.** Markdown is rendered by a small custom widget backed by the Dart-team `markdown` package (one new dependency), giving full control over theming so it matches the web palette. We deliberately avoid the discontinued `flutter_markdown` and heavier `gpt_markdown`/`markdown_widget` packages.

## Requirements analysis & refinements

The requirements are sound. A few clarifications adopted in this design:

- **Palette bootstrapping.** The app theme is built at `MaterialApp` construction time (in `app.dart`), before any server summary is loaded. The runtime `MobileFeatureFlagResolver` needs a post-login summary, so it cannot drive the app-root theme on first frame. We resolve this by adding a compile-time constant `kMobileUxPolishEnabled` (the `--dart-define` half of the same flag) that governs the app-root palette, while the runtime resolver getter `uxPolishEnabled` governs the polished chat UI. Because the resolver combines `server OR build-default`, a build compiled with `MOBILE_UX_POLISH_ENABLED=true` turns on both consistently; a production build with the server flag on turns on the chat polish, and the theme adopts the palette on the next app launch once the flag is baked or via the build default. This matches the existing `kMobileExperienceV2Enabled` precedent exactly.
- **Palette parity token set (P6).** We port the *named* web tokens the mobile surfaces actually consume: `bg-canvas`, `bg-elev-1/2/3`, `text-primary/secondary/muted/brand`, `brand-500/600/700`, `accent-500`, `success-500`, `warn-500`, `danger-500`, and the surface/border tokens (`surface-panel`, `surface-muted`, `surface-brand-soft`, `shell-border`). Web values that use alpha over a canvas are flattened to opaque equivalents against the canvas so a `Color` constant is a faithful match (the parity property compares the mobile constant to the flattened web value).
- **Contrast (P7).** Because some web text tokens are tuned for a glassy gradient background, we verify AA against the *opaque* canvas/surface we actually paint. Where a direct port would miss AA (e.g. `text-muted` on elevated surfaces), we darken/lighten the ported token minimally to clear the threshold and record the adjusted value as the mobile token. The parity property therefore compares against these documented mobile tokens, and the contrast property is the hard gate.
- **Regenerate semantics (Req 5.2).** "Re-sends the most recent user prompt" is implemented as: drop the assistant turn being regenerated, resubmit the immediately-preceding user turn's text through the same send path, producing a fresh assistant turn.

## Architecture

```
app.dart  ── selects ClaraTheme.light/dark(polished: kMobileUxPolishEnabled)
   │
   ▼
ChatScreen (existing, flag-gated on chat_mobile_enabled)
   │  polished == resolver.uxPolishEnabled
   ├── false ─▶ legacy chat body (unchanged, Property P1)
   └── true  ─▶ PolishedChatView
                  ├── ChatEmptyState (greeting + prompt suggestions)
                  ├── ChatMessageList (auto-scroll controller + JumpToLatest)
                  │     ├── UserBubble
                  │     └── AssistantBubble
                  │            ├── TypingIndicator (while empty & streaming)
                  │            ├── MarkdownView (streamed text)
                  │            ├── EndUserSafeAnswer (terminal envelope)
                  │            └── MessageActions (copy / regenerate)
                  └── ChatComposer (auto-grow field + send/stop)
```

### Component and file plan

| File | Kind | Responsibility |
| --- | --- | --- |
| `lib/theme/web_palette.dart` | new, pure | Web-derived color constants (light + dark) + a `WebColorScheme.of(brightness)` bundle. Pure `Color` constants only. |
| `lib/theme/clara_theme.dart` | modify | `light({bool polished})` / `dark({bool polished})`. When `polished`, build the `ColorScheme` from `WebPalette` (explicit roles) instead of the teal seed. Flag-off path unchanged. |
| `lib/core/feature_flags.dart` | modify | Add `mobile_ux_polish_enabled` key, its `--dart-define` default, the `kMobileUxPolishEnabled` compile-time constant, and the `uxPolishEnabled` resolver getter. |
| `lib/app.dart` | modify | Pass `polished: kMobileUxPolishEnabled` to the theme factories (V2 path only). Flag-off path unchanged. |
| `lib/widgets/markdown_view.dart` | new | `MarkdownView(text, ...)` renders Markdown (headings, lists, bold/italic, inline code, fenced code, tables, links) via the `markdown` package AST, themed from the color scheme. Pure `mdToPlainText(...)` helper for copy. |
| `lib/screens/chat/polished_chat_view.dart` | new | The polished body: empty state, list, composer, jump-to-latest, motion. Stateless-ish view driven by callbacks/state passed from `ChatScreen`. |
| `lib/screens/chat/chat_bubbles.dart` | new | `UserBubble`, `AssistantBubble`, `TypingIndicator`, `MessageActions`. |
| `lib/screens/chat/chat_composer.dart` | new | Auto-growing composer with send/stop, offline-aware, ≥44px targets. |
| `lib/screens/chat/chat_empty_state.dart` | new | Greeting + prompt suggestions (localized). |
| `lib/screens/chat_screen.dart` | modify | Add `polished` field (default false). When true, delegate body to `PolishedChatView`; add stream cancellation (stop), regenerate, and jump-to-latest state. Keep all existing behavior/keys when `polished == false`. |
| `lib/experience/home_screen.dart`, `lib/screens/dashboard_screen.dart` | modify | Pass `polished: resolver.uxPolishEnabled` when constructing `ChatScreen`. |
| `pubspec.yaml` | modify | Add `markdown: ^7.3.1`. |

### Stream cancellation (stop control, Req 3.3 / P10)

`ApiClient.streamChat` returns a `Stream<SseEvent>`. The screen consumes it via `await for`. To support **stop**, the polished path subscribes with `stream.listen(...)` and retains the `StreamSubscription`, or wraps the `await for` loop with a `_cancelled` flag plus `subscription.cancel()`. On stop:

1. Cancel the subscription.
2. Finalize the assistant turn with exactly the buffered text so far (`_completeAnswer` with `{'reply': buffer}` if non-empty, otherwise mark finished with no error).
3. Do **not** raise a user-facing error (a user-initiated stop is not an error).
4. Emit a coarse `mobile_chat_stopped` analytics event (no text).

Implementation: refactor `_runStreaming` to use an explicit `StreamSubscription` stored on the state, driven by a `Completer` so the method still `await`s completion. The `_cancelled` guard prevents the "closed without terminal event" branch from treating a user stop as a fallback trigger.

### Auto-scroll gating (Req 2.3 / 2.4 / P3)

A `ScrollController` listener maintains `_atBottom` (within a small threshold of `maxScrollExtent`). On new content:

- If `_atBottom`, animate to the end (duration resolved through `A11y.resolveMotionDuration`).
- Else, do not scroll and show a `JumpToLatest` FAB-style affordance that, on tap, animates to the end and hides itself.

The threshold and the "is at bottom" computation are extracted into a pure helper `isNearBottom(pixels, maxExtent, threshold)` for property testing (P3).

### Markdown rendering (Req 1.3)

`MarkdownView` parses with `md.Document(extensionSet: md.ExtensionSet.gitHubFlavored)` to get block nodes, then walks the AST:

- Block nodes → `Column` of themed widgets: headings (`headline*`/`title*`), paragraphs (`bodyMedium`), unordered/ordered lists (indented rows with markers), fenced code blocks (monospace in a `surfaceContainer` panel with horizontal scroll), tables (`Table` widget with header row emphasis), block quotes (left border + muted text), thematic breaks (`Divider`).
- Inline nodes → `RichText`/`TextSpan` tree: bold, italic, inline code (monospace chip background), links (primary color; tapping is best-effort — since we avoid `url_launcher`, links render as colored, non-tappable spans with the URL preserved as the semantics label; this satisfies "render links" without adding a dependency or making outbound requests).
- A pure `mdToPlainText(String)` strips markdown to plain text for the copy action (Req 5.1).

All colors come from the active `ColorScheme`, so light/dark and the web palette apply automatically.

## Data models

No new persistent models and no API changes. In-memory chat state reuses the existing `ChatMessage` (mutable, accumulates streamed tokens). We add:

- `ChatMessage.lastUserPrompt` lookup is derived from the list (no new field needed for regenerate).
- The polished view is driven by the existing `_ChatScreenState` plus new transient state: `_atBottom`, `_showJumpToLatest`, `_activeSubscription`, `_cancelled`.

## Theme mapping (web → mobile ColorScheme)

Light (from `:root`) and dark (from `html.dark`):

| ColorScheme role | Light source | Dark source |
| --- | --- | --- |
| `primary` | `--brand-600` `#2563EB` | `--brand-500` `#3B82F6` |
| `onPrimary` | white (AA verified ≥4.5) | white/near-white (AA verified) |
| `primaryContainer` | `--surface-brand-soft` `#DBEAFE` | flattened `--surface-brand-soft` |
| `secondary` | `--brand-700` `#1D4ED8` | `--text-brand` `#93C5FD` |
| `surface` | `--bg-elev-3` `#FFFFFF` | `--bg-elev-3` `#1D2840` |
| `surfaceContainerHighest` | flattened `--surface-muted` `#EFF6FF` | flattened `--surface-muted` |
| `background`/scaffold | `--bg-canvas` `#F7F9FB` | `--bg-canvas` `#111A2D` |
| `onSurface` | `--text-primary` `#1F2937` | `--text-primary` `#DAE2FD` |
| `onSurfaceVariant` | `--text-muted` (AA-adjusted) | `--text-muted` (AA-adjusted) |
| `outline` | flattened `--shell-border` | flattened `--shell-border` |
| `error` | `--danger-500` `#DC2626` | `#F87171` (dark danger) |
| success (custom ext) | `--success-500` `#16A34A` | `#6EE7B7` |
| warning (custom ext) | `--warn-500` `#F59E0B` | `#FCD34D` |

Status colors that Material's `ColorScheme` has no slot for (success/warning) are exposed via a small `ClaraStatusColors` `ThemeExtension` so surfaces can read them without hard-coding, and are always paired with text/icon (Req 7.4) via the existing `StatusByText`.

## Correctness properties → test strategy

| Property | Test |
| --- | --- |
| P1 Flags-off equivalence | Widget test: `ChatScreen(polished:false)` renders the legacy keys (`chat-empty`, `chat-input`, `chat-send`); theme with `polished:false` equals current `ColorScheme.fromSeed(teal)`. |
| P2 Streaming monotonic accumulation | Unit/widget: token frames accumulate; `done` never discards buffered text (reuse existing chat test harness). |
| P3 Auto-scroll gating | Pure test of `isNearBottom`; widget test toggles jump-to-latest. |
| P4 Send-enable invariant | Widget/PBT: send enabled iff trimmed non-empty and not sending. |
| P5 Analytics PII-free | Unit: captured events contain no message/prompt text or model id (fake analytics). |
| P6 Palette parity | Unit: each mobile token equals the documented web value per brightness. |
| P7 AA contrast | Unit: contrast-ratio helper asserts each fg/bg pair clears its threshold. |
| P8 Reduced-motion collapse | Unit/widget: `A11y.resolveMotionDuration` → zero under reduced motion; content still delivered. |
| P9 Suggestion populates, never sends | Widget: tapping a suggestion fills composer, sends nothing. |
| P10 Stop finalizes safely | Widget: stop mid-stream cancels, finalizes with buffered text, no error state. |

## Rollout & safety

- Default OFF via both flag halves; flag-off path is unchanged (byte-for-byte).
- No API/contract changes; no new outbound network calls (markdown links are non-navigating).
- One new, well-known, Dart-team-maintained dependency (`markdown`), pinned.
- Vietnamese-first copy for all new strings; Material localization delegates already present on the V2 path.
