# Web i18n foundation

The web default locale is Vietnamese (`vi`); English (`en`) is available from
the authenticated shell and stored under the existing `clara_ui_language`
preference. Locale is presentation-only and never authorizes access or changes
medical truth state.

## Typed catalog

`apps/web/lib/i18n/catalog.ts` is the typed source for shared shell language,
including accessible names, loading/logout labels, navigation groups, role
labels, profile labels and locale-aware date/number formatters. The catalog
test enforces Vietnamese/English key parity and interpolation behavior.

`apps/web/scripts/check-i18n.mjs` is a required CI contract, run before web
lint/build. It statically checks key parity and duplicate keys, fails on dead
catalog keys, and enforces import/key/literal contracts for every migrated
surface. It currently covers the authenticated shell, shared loading/retry
states, Today and the Medicines hub chrome (title, description, tabs and
accessible tab name). A contributor cannot skip this by omitting a Vitest
pattern: the `web-lint-build` CI job calls `npm run i18n:check` on every web or
CI change.

`apps/web/lib/i18n/primary-surfaces.test.ts` remains a focused unit-level
regression test. Domain pages retain existing bilingual maps while they are
migrated incrementally; this document does not claim those pages are already
fully catalog-backed.

## Migration rule

1. Add a key to both catalogs in the same change.
2. Use `t(locale, key)` for visible text, errors, empty states and aria labels.
3. Add the surface to `MIGRATED_SURFACES` in the CI contract only after its
   strings are catalog-backed; list each key and banned prior literal.
4. Preserve `vi` fallback and never send locale preference or translated
medical free text to telemetry.

Run the focused contract locally:

```bash
cd apps/web
npm run i18n:check
npx vitest run lib/i18n
npx tsc --noEmit
npm run lint
```
