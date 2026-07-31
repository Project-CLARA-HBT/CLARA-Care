# CareGuard DrugBank artifact integrity

The full DrugBank SQLite layer is the authoritative DDI source only when its
licensed input artifact is verified. CareGuard rejects an incomplete, changed,
or mismatched artifact before it can produce a DDI conclusion.

## Required manifest identity

`scripts/data/drugbank_ingest.py` emits `manifest.json` with:

- `source=drugbank`, `source_version`, and SHA-256 of the licensed XML input;
- SHA-256 for every DDI and dictionary shard; and
- `manifest_sha256`, calculated from canonical manifest JSON without the
  self-referential field.

The SQLite index stores this identity. A matching label alone is insufficient:
the manifest, source release, source checksum, and every indexed shard must all
agree. Dictionary resolution emits a deterministic trace (`resolution_source`,
`drugbank_id` when provided, and `drugbank_dictionary_version`) without using a
model to guess medication identity.

## Configuration and rollback

`CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true` is the production default.
With `CAREGUARD_DRUGBANK_REQUIRED=true`, any integrity failure fails closed for
drug-drug conclusions; it does not substitute an LLM, external DDI service, or
curated result. Non-DDI emergency, allergy, and lab safeguards still run.

The only emergency compatibility rollback is setting
`CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=false` for a reviewed legacy
artifact. Record the approved artifact version and revert this setting as soon
as a checksum-bearing ingest is available. Do not use this switch to accept an
unknown source or to bypass a failed checksum in clinical strict mode.

## Container release boundary

The ML compose services mount only the approved artifact directory at
`/var/lib/clara/drugbank`; API and web never receive that mount. Configure
container-visible paths explicitly, then use strict mode only after the bundle
has been provisioned:

```dotenv
CAREGUARD_DRUGBANK_ARTIFACT_HOST_DIR=/secure/clara/drugbank
CAREGUARD_DRUGBANK_MANIFEST_PATH=/var/lib/clara/drugbank/manifest.json
CAREGUARD_DRUGBANK_SQLITE_PATH=/var/lib/clara/drugbank/ddi_index.sqlite
CAREGUARD_DRUGBANK_SQLITE_ENABLED=true
CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true
CAREGUARD_DRUGBANK_REQUIRED=true
```

The runtime rejects a strict configuration that disables the SQLite layer or
integrity checks. Readiness is `ready` only when the manifest/source identity,
actual DDI pair count, and actual dictionary record count all match the
indexed database. A changed/missing dictionary is therefore not presented as a
full DrugBank-backed Vietnamese medication normalization service.

## Rebuild procedure

Run this only where the licensed XML is available:

```bash
uv run python scripts/data/drugbank_ingest.py \
  --input /secure/DrugBank/full_database.xml \
  --out-dir services/ml/src/clara_ml/nlp/seed_data/drugbank \
  --source-version <licensed-release-id>
```

Restart the ML service to build the index atomically. Check the authenticated
`/api/v1/careguard/drugbank/status` route for `drugbank.state=ready`,
`manifest_matches_index=true`, `integrity_verified=true`, a positive
`pair_count`, and a positive `dictionary_record_count`; never log the licensed
interaction text or source path in health/telemetry output.
