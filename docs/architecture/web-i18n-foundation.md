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

`apps/web/lib/i18n/primary-surfaces.test.ts` is a deliberately scoped
hard-coded-copy scanner for the authenticated shell (`AppShell`, desktop
topbar and sidebar). It prevents newly migrated primary-shell strings from
drifting back to literals. Domain pages retain existing bilingual maps while
they are migrated incrementally; this document does not claim those pages are
already fully catalog-backed.

## Migration rule

1. Add a key to both catalogs in the same change.
2. Use `t(locale, key)` for visible text, errors, empty states and aria labels.
3. Add the surface to the scanner only after its strings are catalog-backed.
4. Preserve `vi` fallback and never send locale preference or translated
medical free text to telemetry.

Run the focused contract locally:

```bash
cd apps/web
npx vitest run lib/i18n
npx tsc --noEmit
npm run lint
```
