# Mobile consumer terminology contract v1

Version: `2026-07-30.v1`
Status: adopted for the Unified mobile consumer shell

`apps/mobile/lib/core/consumer_terminology.dart` is the typed, runtime-safe
mobile representation of CLARA's task-first consumer wording. It mirrors the
stable product concepts in `apps/web/lib/i18n/catalog.ts`, beginning with the
Today/LifeMap care journey. Vietnamese is the default and fallback; only `en`
or `en-*` selects the English catalog.

This contract is deliberately limited to static product wording. It must not
translate, infer, redact, or mutate medical free text, medication names,
LifeMap truth/provenance, consent decisions, permissions, or an API safety
disposition. Those remain owned by the appropriate safety-aware runtime.

## Contract rules

1. Add each `ConsumerTerm` to both `vi` and `en` maps in one change.
2. Keep existing key names stable through a mobile release window; add a new
   key instead of changing a meaning in place.
3. Keep shared keys aligned with the web typed catalog. The v1 core set uses
   `today.title`, `today.openLifeMap`, `today.pending`, `today.episodes`,
   `today.confirmation`, `today.noDueDate`, `today.emptyTitle`,
   `today.emptyDescription`, `action.askClara`, and `action.open` semantics.
4. Use `ConsumerTerminology.forLocale(controller.languageCode)` at the
   surface boundary. Unknown, persisted, and unavailable locales safely render
   Vietnamese; locale never changes authorization or clinical state.
5. Use `format` only for known static placeholders such as a locally formatted
   due date. Never interpolate medical free text into telemetry or this
   catalog.

## Current migration and verification

`TodaySurface` consumes the contract for task-first headings, empty state,
offline state, session/load failures, onboarding prompt, due-date label, and
completion action. It rebuilds when `LanguageController` changes, while direct
use without a controller remains Vietnamese-first.

Run the contract test when Flutter tooling is available:

```bash
cd apps/mobile
flutter test test/consumer_terminology_contract_test.dart
flutter test test/unified_today_locale_test.dart
flutter analyze lib/core/consumer_terminology.dart lib/experience/unified/today_surface.dart
```

The web catalog remains the present cross-client reference. A generator may
replace the checked-in typed map only if it preserves this API, Vietnamese
fallback, and the contract test.
