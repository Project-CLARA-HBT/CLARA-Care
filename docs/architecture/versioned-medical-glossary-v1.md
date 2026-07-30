# Versioned medical glossary v1

`apps/web/lib/medical-glossary.ts` contains CLARA's static, versioned consumer
glossary (`2026-07-30.v1`). It provides Vietnamese-first and English text at
three audiences: `lay`, `expanded`, and `professional`.

Each entry has stable ID, explicit aliases, and `do_not_simplify_to` guidance.
The latter is a review/display boundary: it must never rewrite user input,
clinical records, medication names, source text, or a LifeMap truth state.

## Safe integration

Use `MedicalTerm` from `apps/web/components/ui/medical-term.tsx` only with a
structured concept ID or an exact trusted response reference. It deliberately
does not scan free text, call an LLM, provide a diagnosis, determine severity,
or issue medication instructions. Unknown values render nothing.

```tsx
<MedicalTerm concept="uncertainty" locale="vi" expandable />
```

For a reference already supplied by a typed backend response, use
`resolveMedicalConcept(reference)` first and preserve the original canonical
field alongside the display concept. The UI helper is not a terminology mapper
and cannot be used to confirm LifeMap records.

## Versioning and rollback

Do not rename existing concept IDs or silently alter their meaning. Add a new
entry or create a new glossary version, keep the prior version through the web
release window, and record the migration in the release notes. Roll back by
deploying the previous web artifact; this glossary has no database migration,
model dependency, telemetry, or runtime feature flag.

## Validation (deferred for the current implementation pass)

```bash
cd apps/web
npm run test -- lib/medical-glossary.test.ts components/ui/medical-term.test.tsx
npm run lint
npx tsc --noEmit
```

The tests verify catalog completeness and exact-only alias matching. They do
not claim clinical terminology coverage or human readability validation.
