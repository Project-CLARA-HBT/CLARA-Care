# GLHS evaluation-only exact-binding matched ablation

Evaluation-only package for the GLHS exact-binding ablation
(`MASTER_SPEC_REVIEWER_R3_2026-08-19.md` section 2.3 GLHS-A01..A06, section
3.3, workstream C-004..C-011). This is a **scientific, evaluation-only
artifact**. It never modifies production code, never adds a feature flag, and
is never selectable through production HTTP, environment settings, tenant
configuration, or runtime flags (GLHS-A02).

## The two matched arms (GLHS-A01)

Both arms derive from the same current production validation primitives in
`services/api/src/clara_api/glhs/`:

| Arm | Kept | Omitted / Added |
| --- | --- | --- |
| `FULL_GOVERNANCE_NO_EXACT_BINDING` | state, current authorization, policy, consent, actor, role, purpose, task, DB locking, idempotency, ordinary provenance, audit | ONLY the persisted exact THSS identity/digest/evidence dependency |
| `GLHS_EXACT_BINDING` | identical to the arm above | adds the exact THSS ID/digest/manifest/evidence-membership/expiry dependency |

The no-binding arm is implemented by calling
`validate_current_governance_coordinates()` and **skipping**
`validate_exact_disclosure_dependency()`. The exact-binding arm runs the same
governance primitive plus the production
`validate_exact_disclosure_dependency()` primitive; production routes compose
these primitives through `validate_bound_proposal_context()` (C-003). The
no-binding arm exists only
under `evaluation/` (GLHS-A02): `adapter.py` refuses to import when the import
stack contains a `services/` frame (GR-03, C-004), and `validate.py` scans
`services/**` for any `disable_binding` / `no_exact_binding` flag vocabulary.

## Why an ablation

GLHS-B05 requires commit-time root revalidation of the exact THSS dependency.
The ablation proves this dependency is what blocks the eight binding-specific
attack families (GLHS-A03): every adversarial schedule holds current
state/governance coordinates valid and changes **only** the disclosure
dependency (C-007). Controls prove exact binding does not simply reject every
write (GLHS-A04).

## Primary schedule families (spec 3.3)

1. wrong snapshot ID but same profile/current versions
2. wrong snapshot digest
3. mutated snapshot payload with unchanged current state/governance
4. evidence used by proposal but absent from disclosed set
5. substitute another valid snapshot from same profile/state version
6. expired original snapshot while state/policy/consent remain unchanged
7. minimized evidence-set swap
8. lineage-root/snapshot substitution after human review

Freeze (GLHS-A05): 8 families x 32 adversarial schedules = 256 adversarial
plus 64 valid controls (8 per family) = **320 logical schedules**. Each
schedule executes under both arms = **640 executions**. The scientific unit is
the logical schedule.

## Layout

```text
evaluation/glhs_binding_only_ablation/
  README.md                  this file
  protocol.schema.json       JSON schema for the frozen protocol
  protocol.json              frozen protocol (GLHS-A06 analysis plan frozen pre-execution)
  schedules.json             frozen 320 logical schedules
  build_schedules.py         deterministic generator that produced schedules.json
  adapter.py                 evaluation-only validation adapter (two arm modes)
  postgres_runner.py         runs both arms through an isolated PostgreSQL /
                             real production commitment admission path
  observer.py                append-only, hash-chained execution stream
  analyze.py                 paired per-family/aggregate analysis (GLHS-A06)
  validate.py                Gate C arm-diff + no-production-flag check
  seal.py                    SHA-256 seal of protocol/schedules/sources/raw/analysis
  tests/                     pytest suite
research/glhs_journal/binding_only_ablation/
  FREEZE.md                  freeze statement and honest execution status
  claim_to_evidence.csv      claim -> artifact mapping
  results/                   raw execution streams + analysis (after execution only)
  seal/                      artifact-sha256.json + seal.json (after execution only)
```

## Running

```bash
export PYTHONPATH=.:services/api/src

# Postgres (final backend; isolated random schema, real production admission path)
export GLHS_BINDING_ABLATION_ISOLATED_RESEARCH=1
export GLHS_BINDING_ABLATION_DATABASE_URL='postgresql+psycopg://user:pass@host:5432/glhs_ablation'
python evaluation/glhs_binding_only_ablation/postgres_runner.py --backend postgres

# SQLite smoke (real production code paths on SQLite; NOT the final run)
python evaluation/glhs_binding_only_ablation/postgres_runner.py --backend sqlite

python evaluation/glhs_binding_only_ablation/analyze.py
python evaluation/glhs_binding_only_ablation/seal.py --run-id <run_id>
```

## Analysis (GLHS-A06)

Primary: paired invalid-commit acceptance on the 256 adversarial schedules.
Per arm: numerator/denominator. Paired absolute risk difference (arm A minus
arm B) plus a 95% paired bootstrap CI with a deterministic seed (10 000
resamples), discordant counts, and the exact two-sided McNemar test. Results
are reported per family over each family's 32 schedules. Controls report
valid-commit acceptance per arm and the rejection-reason distribution. There
is **no adaptive sample-size increase** after result inspection.

## Honesty contract

- The seal covers exactly what actually executed. A Postgres seal is written
  only when a real isolated PostgreSQL run produced the raw stream; a SQLite
  smoke run is labeled `backend=sqlite_smoke` and `note` states it is not the
  final run.
- The raw execution stream is append-only and hash-chained; `observer.py`
  re-verifies the chain and fails closed on content mutation, insertion, or
  reordering. Stream length is anchored by the SHA-256 seal (the seal covers
  the exact stream bytes, so tail truncation is detectable against the seal).
- `adapter.py` imports the production primitives at module level from
  `clara_api.glhs.gateway`; there is no fallback implementation or production
  availability flag.
- `protocol.json` verifies its canonical `protocol_hash` and
  `analysis_plan_hash`; the runner verifies the byte hash of `schedules.json`
  before execution.
