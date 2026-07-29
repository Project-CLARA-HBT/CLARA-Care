# CLARA ML governance

The deployed-capability inventory is
`services/api/src/clara_api/ml_governance/catalog.json`. Every entry has a
stable ID, truthful implementation kind, provider, intended and forbidden use,
owner, risk class, release state, flag, fallback, and data origin. The catalog
describes deployed code; it is not evidence that a research feature is safe to
promote.

Migration `20260729_0040` adds append-only:

- `ai_use_case_definitions`;
- `ml_registry_objects` for dataset, feature-schema, training-run, artifact,
  evaluation, deployment, drift, and feedback manifests;
- private `ai_context_manifests`; and
- no-content `ml_inference_manifests`.

Updates and deletes are rejected. A changed definition or artifact appends a new
version. The release state machine is:

`research → offline_passed → redteam_passed → shadow → pilot → challenger → champion`

Every active state may transition to `retired` or `recalled`; reverse and
skipped transitions fail closed.

## Artifact and provider safety

Online loading accepts only an artifact under the configured root whose
canonical manifest has an Ed25519 signature from an allowlisted public key and
whose bytes match the signed SHA-256. Private signing keys remain in the
offline pipeline. Path traversal, missing files, unknown keys, malformed
signatures, checksum mismatch, and unapproved states prevent loading and select
the governed fallback.

`SignedArtifactStore` verifies a staged bundle before atomically installing it
under the immutable `<artifact_id>/<version>` identity. Every load rechecks the
manifest signature and artifact checksum. `ML_DEPLOYMENT_MANIFEST_PATH` points
to a server-owned deployment map; its champion, explicitly selected challenger,
and fallback slots are release-state checked. A champion verification failure
can select only the declared deterministic fallback or another independently
signed fallback artifact—it never promotes a challenger.

Provider aliases must resolve through an allowlist to an immutable provider
model ID. If the provider response reports a different ID, inference is held or
falls back; CLARA never silently treats `latest` as an immutable deployment.
The runtime allowlist is supplied through
`ML_PROVIDER_MODEL_ALLOWLIST_JSON`; an absent alias fails closed.

## Dataset snapshot boundary

`write_snapshot_bundle` accepts only records already filtered to one approved
purpose with active consent. It recursively restricts features to typed numeric,
boolean, and missingness values, pseudonymizes person/household/site/source/
device identities with a separate key, computes identity-connected splits, and
runs the time-window leakage audit. It then atomically writes an immutable
NDJSON/manifest/audit bundle outside configured OLTP roots. Every read verifies
the dataset and audit checksums.

The snapshot bundle does not grant target approval or model promotion. A
production export still requires a named approval, active consent policy,
audited job identity, and separately controlled pseudonymization key.

## Templates

The templates in this directory are mandatory release artifacts. Empty
sections, unresolved placeholders, unsigned model artifacts, or missing
approvals block promotion.
