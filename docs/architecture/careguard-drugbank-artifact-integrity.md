# CareGuard DrugBank artifact integrity

The licensed full DrugBank SQLite index is the authoritative DDI source only
after it is rebuilt from a verified artifact manifest. An LLM and the smaller
curated Vietnamese rules never replace DrugBank authority.

`manifest.json` identifies `source=drugbank`, the licensed release and source
SHA-256, carries a canonical self-digest (`manifest_sha256`), and includes a
SHA-256 for each DDI and optional dictionary shard. The store verifies every
digest while atomically rebuilding `ddi_index.sqlite`, then persists the
manifest/source identity in SQLite metadata. A current manifest and index must
match on all identity fields before readiness is `ready`.

The optional indexed dictionary resolves exact normalized Vietnamese aliases
deterministically. It returns the normalized ingredient plus DrugBank ID and
RxCUI for traceability; an unrecognized name remains unresolved and is never
guessed.

The artifact bundle is deployment-owned rather than image-owned. ML resolves
`CAREGUARD_DRUGBANK_MANIFEST_PATH` and `CAREGUARD_DRUGBANK_SQLITE_PATH` (default
to its ML-only `/var/lib/clara/drugbank` mount); shard paths remain constrained
to the manifest directory. This makes the licensed release replaceable without
rebuilding an application image while retaining atomic SQLite index replacement.

## Fail-closed operation and rollback

Use `CAREGUARD_DRUGBANK_REQUIRED=true` for strict clinical deployments. If the
verified index is unavailable or mismatched, the DrugBank DDI conclusion is
unavailable; an empty result is never presented as safe.

Strict mode requires the SQLite layer and checksum verification at config load.
It also requires both the DDI and dictionary counts recorded in the signed
manifest to match readable database tables. This is intentionally stronger than
a version-label comparison: it prevents a stale or DDI-only database from being
represented as a full DrugBank + Vietnamese-normalization release.

`CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true` is the default. Only a
short, audited compatibility rollback for a previously verified legacy artifact
may set it to `false`; restore it after regenerating the artifact:

```bash
python scripts/data/drugbank_ingest.py \
  --input /secure/DrugBank.xml \
  --source-version <licensed-release>
```

Do not commit DrugBank XML, license credentials, or licensed output outside
its approved deployment store.
