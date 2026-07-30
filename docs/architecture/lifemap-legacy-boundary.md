# LifeMap legacy compatibility boundary

Historical LifeMap rows imported before V2 are not part of a live care
decision.  Their reconciliation helper is therefore isolated at
`clara_api.lifemap.legacy.provenance`.

`legacy_provenance_counts` returns only aggregate categories:

- `confirmed` only where historical provenance explicitly says `verified`;
- `user_reported` for user-reported historical truth states;
- `ambiguous` for unverified or incomplete imports; and
- `invalid` for invalidated or entered-in-error records.

The helper never returns event payloads, provenance contents, or other health
data.  Operators can run the aggregate report with:

```bash
cd services/api
uv run python -m clara_api.scripts.report_lifemap_legacy_provenance
```

The former `clara_api.lifemap.legacy_provenance` import remains a compatibility
shim only.  New code must use the isolated namespace.  This is a code-layout
change; it does not mutate records, alter truth state, or change any API route.
