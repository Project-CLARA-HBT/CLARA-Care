# GovRed RIVF — Three-state primary interpretation (E-001)

GRD-01: final scientific tables distinguish `CONFIRMED_INVALID`,
`INDETERMINATE`, and `CONFIRMED_SAFE_OR_REJECTED` (plus the operational failure
state). The historical binary non-safe composite **remains a secondary frozen
endpoint only** and is reported unchanged, never relabelled.

## Schema

`evaluation/governance_adversarial/final_analysis_schema.py`
(`govred-three-state-primary-v1`) re-derives the primary table from the sealed
`results/final-003-analysis-v2.json` (read-only, unchanged) into a **new**
derived artifact:

`results/final-003-three-state-primary.json`

Derivation rules (explicit, machine-checked):

| State | Rule |
| --- | --- |
| `INDETERMINATE` | `concurrent_stale_state_write` residuals — the frozen GLHS TOCTOU wording classifies the concurrency/ordering family as `INDETERMINATE_ORDERING`; these are **not** relabelled as confirmed violations. |
| `CONFIRMED_INVALID` | residual families in weaker arms whose guarding coordinate the arm design removes (`authorization_consent_toctou`, `role_mismatch` → `governance_revalidation`; `stale_thss_replay` → `state_revalidation`), attributed `arm_omitted_coordinate`. Controlled ablation outcomes, never production defects. |
| `CONFIRMED_SAFE_OR_REJECTED` | remainder of the primary denominator (210/arm). |
| `OPERATIONAL_FAILURE` | availability failures (zero in final-003). |

Every row sums to the primary denominator; the derivation fails closed if the
arithmetic does not hold or the source schema is not the sealed
`govred-analysis-v2`.

## Primary three-state table (re-derived from final-003)

| Arm | primary_endpoint_n | CONFIRMED_INVALID | INDETERMINATE | CONFIRMED_SAFE_OR_REJECTED | OPERATIONAL_FAILURE |
| --- | ---: | ---: | ---: | ---: | ---: |
| UNBOUND | 210 | 90 | 30 | 90 | 0 |
| STATE_VERSION_ONLY | 210 | 60 | 30 | 120 | 0 |
| SNAPSHOT_BOUND_STATE_ONLY | 210 | 60 | 30 | 120 | 0 |
| GLHS_STRICT | 210 | **0** | **30** | **180** | 0 |

GLHS_STRICT is the headline arm: no confirmed invalid acceptance, the only
residual class is the `INDETERMINATE` concurrency/ordering family, consistent
with `strict_residual_root_cause_taxonomy.json` (`INDETERMINATE_ORDERING`,
30/30 concurrent stale-state writes).

## Secondary frozen binary endpoint (unchanged)

Reported verbatim from the sealed analysis, as a frozen secondary endpoint:

| Arm | primary_failures | rate | Wilson 95% CI |
| --- | ---: | ---: | --- |
| UNBOUND | 120 | 0.571 | 0.504–0.636 |
| STATE_VERSION_ONLY | 90 | 0.429 | 0.364–0.496 |
| SNAPSHOT_BOUND_STATE_ONLY | 90 | 0.429 | 0.364–0.496 |
| GLHS_STRICT | 30 | 0.143 | 0.102–0.197 |

The binary composite must never be presented as a three-state table and vice
versa; GRD-01 keeps it as the historical frozen endpoint only.

## Boundaries

- Sealed files (`results/final-003-analysis-v2.json`,
  `results/final-003-analysis-diff.md`,
  `provenance/final-003-reconciliation.json`) are never modified; this work
  only adds a derived artifact.
- Residual concurrency outcomes are never majority-voted into safety and never
  upgraded to confirmed violations (see `repetition_protocol_v1/` for the
  frozen instrumentation that may later resolve them).