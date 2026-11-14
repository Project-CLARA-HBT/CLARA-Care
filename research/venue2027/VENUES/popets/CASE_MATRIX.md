# POPETS — preregisterable scenario and oracle matrix
**Basis:** # POPETS · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| POPETS-CASE-01 | Authorized disclosure: valid consent, purpose and version, no revocation | `ALLOW` | exact disclosed bytes authorized for specified principal/purpose | authorized utility |
| POPETS-CASE-02 | Revocation before retry: old context cached, consent revoked before retry dispatch | `DENY` | no revoked synthetic canary leaves process after effective revoke | retry leakage |
| POPETS-CASE-03 | Derived summary chain: field -> summary -> second summary with purpose inherited | `DENY_ON_REVOKE` | transitive closure reaches all derived cache artifacts | lineage completeness |
| POPETS-CASE-04 | Unrelated record edit: independent field changed, no policy or dependency edge changed | `ALLOW` | scope-local recomputation preserves utility without stale read | false invalidation |
| POPETS-CASE-05 | Cross-purpose cache reuse: request for purpose B reuses context built for A | `DENY` | strict purpose and actor binding; no cache confusion | purpose binding |
| POPETS-CASE-06 | Already-delivered copy: provider received bytes before revocation | `OUT_OF_SCOPE_PAST` | measure only preventable future disclosures; never claim retroactive erasure | threat precision |
| POPETS-CASE-07 | Missing lineage edge: derived cache with unknown ancestry | `INDETERMINATE` | fail closed or force fresh authorized reconstruction | incomplete provenance |
| POPETS-CASE-08 | Attacker-controlled retry: retries out of causal order with old epoch | `DENY` | revalidate epoch immediately prior to dispatch | adversarial timing |
| POPETS-CASE-09 | Task utility parity: same authorized task with recompute baseline | `MEASURE` | measure task completion and latency at matched disclosure bounds | efficiency |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "POPETS-CASE-01",
  "venue": "popets",
  "synthetic_only": true,
  "random_seed": 42,
  "scenario_family": "<registered-family-id>",
  "group_id": "<independent-unit-id>",
  "actor_id": "synthetic-actor",
  "tenant_id": "synthetic-tenant",
  "purpose": "self_care",
  "timeline": [
    {
      "order": 0,
      "event_kind": "INITIAL_STATE",
      "logical_time": 0,
      "payload_ref": "sha256:..."
    }
  ],
  "expected_oracle_decision": "<one of allowed statuses>",
  "oracle_spec_revision": "<frozen independent oracle SHA>",
  "baseline_arms": [
    "B0",
    "B1"
  ],
  "candidate_arm": "C0",
  "split": "development|holdout"
}
```

## Task mapping
1. `dataset` generates these classes with independent scenario-family splits.
2. `oracle` creates truth without importing candidate.
3. `baseline_tests` applies same scenario and adversary capabilities to strongest comparators.
4. `unit` checks core invariants on minimal cases.
5. `pilot` logs cost and variance on development only.
6. `confirm` uses heldout variants, not the exact nine examples.
7. `stats` includes planned denominator and unknowns.

## Minimum QA on the fixture generator
- Deterministic seed under fixed generator version; every case contains versioned policy and timeline.
- No empirical win rates inferred from the expected-outcome column.
- If two interpretations of an oracle label are plausible, keep `INDETERMINATE` until independently adjudicated.
- Mutant injection must trigger independent oracle evidence instead of introspecting candidate internals.
