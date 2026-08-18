# GLHS Persisted-Governance Concurrency V2 — Protocol Artifacts & Run

Frozen protocol artifacts for the W4 GLHS persisted-governance + concurrency v2
workstream. This directory is the execution boundary for the v2 protocol; the
v1 protocol (`research/glhs_journal/postgres_toctou_protocol.json`) is frozen
and untouched.

## Files

| File | Role |
| --- | --- |
| `postgres_toctou_protocol_v2.json` | Frozen 12-schedule protocol. `schema_version=glhs-postgres-governance-toctou-final-v2`, `status=FROZEN_FINAL_REVIEWED`, `run_id=GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01`. |
| `statistics_plan_v2.json` | Frozen statistics plan (endpoints, Wilson upper CI, indeterminate/operational rules). |
| `run_v2_raw.json` | Executor output: raw per-schedule v2 observations + classification audit (created at run time). |
| `README.md` | This run book. |

## Isolation contract

The protocol and executor refuse to run unless the run is:

- `backend: postgresql`
- `operator_owned: true`
- `random_schema_per_run: true` (each execution creates a random
  `glhs_toctou_final_v2_<hex>` schema and drops it afterwards)
- `shared_or_default_database: false` (the URL database must not be
  `postgres`, `template0`, `template1`, or empty)
- `production_resources: false`

`unit_of_analysis = one frozen logical schedule; retries remain within the same
schedule and are never an independent N`.

## Fail-closed gates (never bypass)

The executor refuses (exit 2, `{"status": "REFUSED", ...}`) when:

- `GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH` is not `1`, or
- no PostgreSQL URL is provided (CLI `--database-url` or
  `GLHS_TOCTOU_FINAL_DATABASE_URL`), or
- the URL is not `postgresql://` / `postgresql+psycopg://`, or
- the protocol is not `FROZEN_FINAL_REVIEWED`, or
- the protocol's isolation contract differs from the frozen v2 contract.

Results are never fabricated: every observation comes from running the real
schedule against the real CLARA GLHS gateway (`compile_thss`,
`propose_assertion`, `apply_transition`, `record_evidence`,
`reconstruct_governed_decision`) over the real `clara_api.db.models` rows
(`GlhsAssertion`, `GlhsSnapshotManifest`, `GlhsTransition`, `UserConsent`). A
schedule whose observed classification differs from the frozen expected
classification is recorded as an explicit classification-audit mismatch and the
run status becomes `EXECUTED_V2_OBSERVATION_MISMATCH` (not claim-eligible).

## Prerequisites (isolated VPS Postgres)

- Project: `clara-rivf-20260817-final001`
- Postgres container: `clara-rivf-20260817-final001-postgres-1`
- A fresh, operator-created database: `glhs_final_v2` (the executor refuses
  shared/default databases; it creates and drops its own random schema inside
  this database and touches no other schema).

No repository code connects to any remote database outside an explicit,
attested operator run. Tests use injected fakes only.

## Run procedure (operator, on the VPS host)

From the repository root, with the API venv:

```bash
# 1. Create the fresh isolated database (operator-owned, once).
docker exec clara-rivf-20260817-final001-postgres-1 \
  psql -U <postgres_user> -c 'CREATE DATABASE glhs_final_v2;'

# 2. Attest isolation and point the executor at the fresh database.
export GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH=1
export GLHS_TOCTOU_FINAL_DATABASE_URL='postgresql+psycopg://<user>:<pass>@127.0.0.1:5432/glhs_final_v2'

# 3. Run the frozen v2 protocol (writes research/glhs_journal/protocol_v2/run_v2_raw.json).
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.glhs_postgres_toctou.executor_v2 \
  --protocol research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json \
  --output research/glhs_journal/protocol_v2/run_v2_raw.json
```

The random schema is created, all 12 schedules run through the real gateway and
persisted governance writers, the observation set is validated with
`validate_v2`, and the schema is dropped in `finally`.

### Copy the result back

```bash
# From the VPS back to the repo checkout on the research host:
scp <vps>:'/path/to/CLARA-Care/research/glhs_journal/protocol_v2/run_v2_raw.json' \
  research/glhs_journal/protocol_v2/run_v2_raw.json
```

## Reading the output

`run_v2_raw.json` contains:

- `status`: `EXECUTED_V2_FROZEN_OBSERVATIONS` (claim-eligible) or
  `EXECUTED_V2_OBSERVATION_MISMATCH` (a schedule's observed classification
  differed from the frozen expectation — investigate, never recode as safe).
- `schedules`: the 12 normalized v2 observations (observer-complete).
- `classification_audit`: per schedule `{expected_classification,
  observed_classification, matches}`.
- `validation`: output of `validate_v2` (`VALIDATED_V2_OBSERVATIONS_NOT_EXECUTED`
  — the pure gate; `database_executed=false`).
- `postgres_metadata`: PostgreSQL version + transaction isolation level.
- `source_revision`: git short SHA of the code that produced the run.

Statistical endpoints (see `statistics_plan_v2.json`) are computed from the
raw observations: `forbidden_commit_observed` rate with a Wilson upper bound,
`rejection_auditability`, `committed_reconstructability`, `false_stale_burden`,
and latency p50/p95/p99. INDETERMINATE is never counted as safe, and
deadlock/serialization outcomes are operational, never safety success.

## Notes

- The policy-epoch schedules (`TOCTOU-V2-03`, `TOCTOU-V2-12`) persist a real
  `glhs_governance_policy_epochs` row and, for the commit attempt only, set the
  gateway's sanctioned isolated-research policy-version override
  (`CLARA_GOVRED_ISOLATED_RESEARCH=1` + `GOVRED_RESEARCH_ARM=GLHS_STRICT` +
  `GOVRED_RESEARCH_POLICY_VERSION=policy-v2`) inside a context manager that
  restores the environment afterwards. This is how the real gateway revalidates
  a stale-policy proposal; no production behavior changes.
- All fixture data is synthetic and non-PHI; observations contain structural
  identifiers and counts only.
- The executor never runs without the attestation and never touches the running
  SOICT process, CareGuard, or the frozen v1 protocol.
