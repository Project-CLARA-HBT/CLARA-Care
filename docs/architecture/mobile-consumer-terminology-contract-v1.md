# Mobile consumer terminology contract v1

Version: `2026-07-30.v1`
Status: adopted for the Unified mobile consumer shell

`contracts/consumer-terminology/consumer-terminology.v1.json` is the canonical,
versioned source for the small set of static labels shared by the web and
Unified mobile shell. Its checked-in projections are
`apps/mobile/lib/core/consumer_terminology.generated.dart` and
`apps/web/lib/i18n/consumer-terminology.generated.ts`; the web typed catalog
spreads the latter so existing `t(locale, key)` callers remain compatible.
`apps/mobile/lib/core/consumer_terminology.dart` is the runtime-safe mobile
resolver. Vietnamese is the default and fallback; only `en` or `en-*` selects
the English catalog.

This contract is deliberately limited to static product wording. It must not
translate, infer, redact, or mutate medical free text, medication names,
LifeMap truth/provenance, consent decisions, permissions, or an API safety
disposition. Those remain owned by the appropriate safety-aware runtime.

## Contract rules

1. Change the JSON source and both checked-in projections in one change. Run
   `npm run consumer-terminology:check` from `apps/web` before committing.
2. Add each `ConsumerTerm` to both `vi` and `en` maps in one change.
3. Keep existing key names stable through a mobile release window; add a new
   key instead of changing a meaning in place.
4. Keep shared keys aligned with the web typed catalog. The v1 core set covers
   the task-first actions, Today headings/statuses, and Unified-shell
   destinations; it does not claim to be an all-product translation catalog.
5. Use `ConsumerTerminology.forLocale(controller.languageCode)` at the
   surface boundary. Unknown, persisted, and unavailable locales safely render
   Vietnamese; locale never changes authorization or clinical state.
6. Use `format` only for known static placeholders such as a locally formatted
   due date. Never interpolate medical free text into telemetry or this
   catalog.

## Current migration and verification

`TodaySurface` consumes the contract for shared task-first headings, empty
state, due-date label, and completion action. The Unified shell consumes it
for its chat action and four destinations. It rebuilds when
`LanguageController` changes, while direct use without a controller remains
Vietnamese-first.

Run the contract test when Flutter tooling is available:

```bash
cd apps/mobile
flutter test test/consumer_terminology_contract_test.dart
flutter test test/unified_today_locale_test.dart
flutter analyze lib/core/consumer_terminology.dart lib/experience/unified/today_surface.dart

cd ../web
npm run consumer-terminology:check
```
