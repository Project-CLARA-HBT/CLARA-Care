# RIVF / GovRed — Manuscript-Ready Results

## Run identity

- Run ID: `2026-08-17-rivf-final-003`
- Frozen source revision: `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`
- Analysis unit: one frozen logical matched case; transport retries collapsed (not independent N)
- Environment: isolated `clara-rivf-20260817-final001` (dedicated ports/network/volumes; synthetic users and records only; production `clara-app-*` untouched)
- Arms: `UNBOUND`, `STATE_VERSION_ONLY`, `SNAPSHOT_BOUND_STATE_ONLY`, `GLHS_STRICT`

## Primary outcome (stale/unauthorized-commit acceptance, primary schedule scope)

| Arm | N (executed) | Stale-commit acceptance | Rate | Wilson 95% CI |
| --- | --- | --- | --- | --- |
| UNBOUND | 270 | 120 | 0.571 | 0.504-0.636 |
| STATE_VERSION_ONLY | 270 | 90 | 0.429 | 0.364-0.496 |
| SNAPSHOT_BOUND_STATE_ONLY | 270 | 90 | 0.429 | 0.364-0.496 |
| GLHS_STRICT | 270 | 30 | 0.143 | 0.102-0.197 |

Paired McNemar (GLHS_STRICT vs UNBOUND, identical logical cases): discordant pairs b=90 (UNBOUND accepts, STRICT rejects), c=0 (STRICT accepts, UNBOUND rejects); p<0.0001 (two-sided).

## Secondary outcomes

- Prohibited disclosure: 0/270 in every arm (Wilson CI lower bound 0).
- Cache/index revocation failure: 0/270 in every arm (adapter never directly invalidates cache; observation is service-owned).
- Audit reconstruction complete: GLHS_STRICT 60/270; SNAPSHOT_BOUND_STATE_ONLY 120/270; UNBOUND/STATE_VERSION_ONLY 0/270.
- NOT_RUN (protocol exclusions / unsupported adapter families): 180 per arm; these contribute to no denominator.

## Interpretation (claim boundary)

GLHS_STRICT reduces stale/unauthorized-commit acceptance relative to UNBOUND in the executable primary schedules, with a fully discordant paired contrast (p<0.0001). This is a controlled software robustness/governance-consistency result on synthetic data; it is not a cybersecurity threat-model result, a clinical-effectiveness result, or evidence about production deployments.
