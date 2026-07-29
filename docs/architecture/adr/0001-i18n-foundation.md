# ADR 0001: Catalog-based Vietnamese-first i18n

Status: accepted for PR-02 implementation.

CLARA will use typed, build-checked Vietnamese and English catalogs. Vietnamese
is the fallback locale. Static product, validation and accessibility text must
not call an LLM. Locale persistence may remain non-URL based during migration to
avoid breaking deep links. Missing keys fail CI; legacy strings migrate by domain.

Rollback: retain current Vietnamese-first strings while disabling only the new
provider through configuration; do not change health content or authorization.
