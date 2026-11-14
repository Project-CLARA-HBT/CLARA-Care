# Shared base contracts (v1) — versioning policy and validator rules

Scope: `case.v1.schema.json`, `run_manifest.v1.schema.json`, `oracle_decision.v1.schema.json`,
validated by `_shared/tools/schema_validator.py` (pure stdlib, JSON Schema 2020-12 subset).

These schemas are the program-level contract reused by all nine venue studies
(`research/venue2027/MANIFESTS/scientific_program.json`). They encode, per
`SH-base_contracts.md` and `GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`:

- **independent experimental unit** — explicit `independent_unit_id`
  (`^[A-Za-z0-9._:.-]{1,128}$`) plus a declared `unit_kind`
  (`case|history|run|session|subject|benchmark_run`). Repeated attempts sharing a
  `independent_unit_id` are clustered, not independent.
- **backend** — `postgresql | sqlite | synthetic`. PostgreSQL claims must use the `postgresql` backend; SQLite observations are never
  substituted for PG concurrency/recovery claims.
- **frozen source** — `source_sha` (40 lowercase hex, full git commit) and exact
  `branch` (compared by exact string, never prefix).
- **seed** — required integer; untracked randomness is forbidden.
- **arm id** — `arm_id` (single) / `arms` (run manifest), from predeclared baseline tables.
- **evidence pointers** — ≥1 per record, each with `pointer_kind`, resolvable `uri`,
  and `sha256`; hash mismatch fails closed.
- **explicit INDETERMINATE** — oracle `outcome` enum is
  `PASS | FAIL | INDETERMINATE | NOT_RUN_EXTERNAL | FORBIDDEN_EVENT`; run manifest
  denominators carry `indeterminate`, `not_run_external`, `timeout`,
  `environment_failure`, `abstained`, `missing` as first-class counts. Incomplete,
  stale or externally-blocked executions are never tallied as safe rejections or
  completions.

## Timestamps cannot establish unit independence

`created_at`, `frozen_at`, `started_at`, `finished_at` and `adjudicated_at` are
**forensic metadata only**. The schemas deliberately make every identity/claim field
(`independent_unit_id`, `unit_kind`, `source_sha`, `seed`, `branch`, `arm_id`,
`evidence[].sha256`) required and typed, while timestamps are optional strings with no
uniqueness or ordering constraint. Two attempts with identical timestamps or adjacent
timestamps may belong to the same clustered unit or to different units — nothing may be
inferred either way from time alone. Analyses must group by `independent_unit_id`
(adjusted for `unit_kind`); "this record is a new independent unit because its timestamp
differs" is an invalid inference under this contract, and validators refuse documents
that omit `independent_unit_id` regardless of how rich their timestamps are.

## Versioning policy

- **Additive-only within v1.** Any change that keeps every existing valid v1 document
  valid and every existing invalid v1 document invalid is allowed *without* a version
  bump: adding an optional property, adding an enum member to a previously
  closed-but-extendable *response* field, tightening a `description`, or adding a new
  `$defs` entry. Property removals, type changes, new required fields, enum removals,
  pattern tightening and `additionalProperties: true` flips are **breaking**.
- **Breaking change ⇒ new major version file.** Create `case.v2.schema.json` (etc.) with
  `"const": "2"` for `schema_version`; never edit the semantics of a `v1` file. Both
  versions may coexist; consumers pin one. `schema_version` is a required `const` so a
  v2 document can never silently validate against the v1 schema.
- **Enum policy detail.** Response/outcome enums (`outcome`, denominator keys) may gain
  members additively within v1 only if the new member is *not* foldable into an existing
  success/rejection bucket (preserves mutually exclusive denominators). Input-identity
  enums (`backend`, `unit_kind`, `pointer_kind`) are frozen within v1; additions there
  are breaking (they change what a claim *means*).
- **Deprecation.** Within v1, mark fields to be removed in the next major version by
  prefixing their `description` with `DEPRECATED(v1):` and keep validating them.
- **Validator compatibility.** The stdlib validator supports exactly:
  `type`, `required`, `enum`, `const`, `pattern`, `minLength`, `maxLength`, `minimum`,
  `maximum`, `minItems`, `maxItems`, `items`, `properties`, `additionalProperties`,
  `$ref` (local `#/$defs/...` or sibling-file `name.schema.json#/$defs/...`),
  `oneOf`, `anyOf`, `allOf`, `not`, and `$defs`. Anything else in a schema is a hard
  error (`UNKNOWN_KEYWORD`) — fail closed, do not skip unknown keywords. Every schema
  here must stay within this subset.

## Validator rules (failure semantics)

- Validation is **fail closed**: missing required fields, malformed patterns (e.g.
  short or uppercase `source_sha`, missing `independent_unit_id`, missing `backend`),
  non-enums and unresolvable refs are rejections with stable reason codes
  (`REQUIRED_MISSING`, `PATTERN_MISMATCH`, `ENUM_MISMATCH`, `REF_UNRESOLVED`,
  `UNKNOWN_KEYWORD`, `TYPE_MISMATCH`, `CONST_MISMATCH`, ...), never warnings.
- Negative controls are part of the contract: a case missing `independent_unit_id`,
  missing `backend`, or carrying an unfrozen/non-40-hex `source_sha` MUST be rejected
  (see `_shared/tests/test_base_contracts.py`).
- `INDETERMINATE` and `NOT_RUN_EXTERNAL` MUST validate as legal oracle outcomes and as
  denominator counts — an environment that cannot record them is noncompliant.
- Schemas forbid additional properties; unknown fields are rejected so that
  side-channel data cannot ride along unvalidated.
