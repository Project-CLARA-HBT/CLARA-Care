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
guessed. The SQLite index retains more than one source-backed record when an
alias is ambiguous; it no longer drops a later candidate based on shard order.

## Explicit medication clarification rollout

`CAREGUARD_MEDICATION_CLARIFICATION_ENABLED=false` is the default rollback-safe
setting. When enabled, CareGuard uses only the current licensed DrugBank
dictionary to establish a medication identity. A single exact candidate is used
deterministically. An unknown alias, multiple candidates, a missing stable
DrugBank ID, or a stale/forged choice returns the terminal
`requires_medication_clarification` state before any DDI/risk/recommendation is
computed. The state contains a bounded list of source-backed candidates only;
it is not a DrugBank interaction lookup and contains no LLM-generated identity.

A submitted choice must bind the original normalized alias to the exact
`drugbank_id` and current `drugbank_version`. ML queries the active licensed
index again and accepts the choice only if it matches exactly one record. This
prevents a client from substituting another DrugBank ID.

For the cabinet route, the API must send the same bounded, ordered transport
envelopes to ML:

```json
{
  "medications": ["input alias as stored for this check"],
  "medications_with_meta": [
    {"cabinet_item_id": 42, "input_alias": "input alias as stored for this check"}
  ],
  "medication_resolutions": [
    {
      "cabinet_item_id": 42,
      "input_alias": "input alias as stored for this check",
      "drugbank_id": "DB00000",
      "drugbank_version": "licensed-release"
    }
  ]
}
```

ML accepts a cabinet ID only when it is a positive integer and its
`input_alias` exactly matches a request medication after deterministic token
normalization. For duplicate aliases, it binds IDs only when there are exactly
as many unique metadata IDs as raw occurrences; otherwise all duplicate rows
stay unbound. A per-item resolution must repeat that exact alias and is then
validated against DrugBank. Direct CareGuard requests may omit all cabinet IDs;
their resolutions remain alias-bound and cannot be mistaken for cabinet choices.
The API still has to establish owner scope before sending this internal packet;
selections are request-scoped and must not silently overwrite the user’s cabinet
record.

When strict DrugBank is required and the verified index is unavailable, the
existing unavailable result remains authoritative. With the clarification flag
on, an unavailable indexed dictionary also blocks a partial DDI conclusion even
when strict mode is not otherwise enabled: CareGuard must not fall back to a
local mapping or an LLM to choose a medicine identity. Disable the flag and
restart ML for the prior normalization behavior while investigating the licensed
artifact.

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
