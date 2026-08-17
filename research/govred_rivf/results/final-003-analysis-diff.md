# RIVF final-003 analysis diff (v1 historical vs v2 canonical)

Generated from unchanged final-003 raw rows. v1 (`results/analysis.json`) remains the historical record; v2 (`results/final-003-analysis-v2.json`) is the canonical regeneration.

## Denominator presentation (AUD-010)

- primary denominator = 210 (executed mandatory-primary families only), shown separately from all-executed = 270.
- NOT_RUN = 180 per arm, explicitly excluded from denominators.
- GLHS_STRICT primary: 30/210 = 0.1429 (Wilson 95% CI 0.1019-0.1966).

## Exact p-value (AUD-004)

- v1 stored `p_two_sided: 0.0` (underflow).
- v2 stores exact binomial two-sided p = 1.615587e-27 (log10 = -26.79). Never an underflowed zero.

## Endpoint split (AUD-012)

Five separate endpoints, no composite "attack success":

| arm | invalid_commit_acceptance | disclosure | wrong_subject | cache_failure | availability |
|---|---|---|---|---|---|
| UNBOUND | 150 | 0 | 0 | 0 | 0 |
| STATE_VERSION_ONLY | 120 | 0 | 0 | 0 | 0 |
| SNAPSHOT_BOUND_STATE_ONLY | 120 | 0 | 0 | 0 | 0 |
| GLHS_STRICT | 60 | 0 | 0 | 0 | 0 |

Note: GLHS_STRICT invalid_commit_acceptance = 60 counts the secondary `audit_reconstruction_failure` stress family (committed by design to test reconstruction); the mandatory-primary residual is 30, all `concurrent_stale_state_write`.

## Family-stratified primary residual (AUD-018)

GLHS_STRICT mandatory-primary residual by family:

| family | failures |
|---|---|
| concurrent_stale_state_write | 30 |
| all other mandatory-primary families | 0 |

Serial authorization-drift families (consent, policy, role, stale-state, digest, cross-subject, cache-revoke) show zero invalid commits in the strict arm; the residual is a concurrency/ordering family consistent with GLHS TOCTOU-03 INDETERMINATE classification.
