# CareGuard-VN source-gate checklist (G-001 / G-002)

Status: **CHECKLIST FROZEN**; the checklist is used once the authorized DAV
identity frame is delivered (G-001 MANUAL). Currently the Vietnam identity
frame is **NOT ACQUIRED** and the source set cannot pass `validate_source_set`.

## Hash-bound source-manifest format

One manifest per source role, schema `careguard-vn.source-manifest.v1`
(validated by `evaluation/careguard_external/source_manifest.py`). Required
fields:

`schema_version`, `status` (`FROZEN_ACQUIRED`), `source_name`,
`independence_role`, `source_url`, `retrieved_at_utc`, `version_or_release`,
`access_terms`, `license`, `redistribution_policy`
(`raw_prohibited`/`derived_only`/`permitted`), `redistribution_review_status`
(`PENDING`/`RESOLVED`/`NOT_APPLICABLE`), `payload_sha256`, `row_count`,
`record_hash_algorithm` (`sha256(canonical_record_json)`), `record_hash_inventory`,
`raw_retention_location`.

Per-record hash inventory is required (not just a payload hash). Probes,
unresolved terms, missing raw-retention locations, incomplete inventories, and
duplicate declared source identities/URLs/payload hashes across nominal roles
are rejected (fail-closed).

## Rights / access provenance fields

- `access_terms` — official acquisition authorization or published access
  statement (required; `PENDING_REVIEW` rejected).
- `license` — published license/rights statement, or "Not published;
  acquisition authorization recorded in access_terms".
- `redistribution_policy` / `redistribution_review_status` — pending public
  redistribution review is metadata only; raw payload stays outside git with
  `raw_prohibited` until a release review permits otherwise.

## Four-role source set

All four independent roles must be present with distinct declared source
identities, URLs, and payload hashes:

| Role | Source | Status at this freeze |
| --- | --- | --- |
| identity_frame | DAV official product export | **NOT ACQUIRED** (CG-01 gate) |
| terminology | RxNorm 2026-08-03 prescribable | acquired (controlled manifest) |
| positive_ddi_reference | DDInter 2.0 | acquired (controlled manifest) |
| regulatory_confirmation | DailyMed current SPL subset | acquired (5-record subset) |

`validate_source_set` still rejects the current set because the identity-frame
role is absent.

## Steps once DAV is delivered (G-001 + G-002)

1. **G-001 MANUAL** — Obtain the official/current authorized DAV export or API
   delivery; record rights/access provenance (official URL, retrieval time,
   release/version, format, record-ID field, access terms, license statement
   when published, redistribution-review status). Do not scrape a portal or
   treat a search result as current marketed status.
2. **G-002** — Store the payload in the operator-controlled archive outside
   git; run `python -m evaluation.careguard_external.acquire_dav` with the
   retained file, official `*.dav.gov.vn` URL, release label, record-ID field,
   access terms, and output path. The command hashes the raw payload and every
   record, rejects missing/duplicate IDs, and emits a `FROZEN_ACQUIRED`
   identity-frame manifest only after validation.
3. Verify all record hashes against the emitted `record_hash_inventory`;
   verify `payload_sha256` matches the delivered file; confirm
   `validate_source_set` now passes with all four roles.
4. Only then proceed to normalization / mapping-candidate generation
   (PIPELINE_SPEC.md), reviewer protocol (MAPPING_REVIEW_PROTOCOL.md), and the
   frozen statistics plan (STATISTICS_PLAN_FROZEN.md). No final benchmark may
   run until Gate G (four-role source-set validation + statistics freeze)
   passes.

## Prohibited

No zero-count or metadata-probe substitute for a missing source; no DAV crawl;
no scraping of the public portal; no negative labels from reference absence.
