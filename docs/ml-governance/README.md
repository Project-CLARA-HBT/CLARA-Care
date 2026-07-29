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

Provider aliases must resolve through an allowlist to an immutable provider
model ID. If the provider response reports a different ID, inference is held or
falls back; CLARA never silently treats `latest` as an immutable deployment.

## Templates

The templates in this directory are mandatory release artifacts. Empty
sections, unresolved placeholders, unsigned model artifacts, or missing
approvals block promotion.
