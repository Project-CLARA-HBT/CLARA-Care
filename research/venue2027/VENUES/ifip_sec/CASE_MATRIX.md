# IFIP_SEC — preregisterable scenario and oracle matrix
**Basis:** # IFIP_SEC · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| IFIP_SEC-CASE-01 | Legitimate same-purpose execution: valid signed scoped capability, current epoch, matching dispatch | `ALLOW` | accept with minimal verifiable evidence | legitimate coverage |
| IFIP_SEC-CASE-02 | Cross-purpose replay: same receipt reused for separate purpose | `DENY` | purpose-domain separation preserved | purpose replay |
| IFIP_SEC-CASE-03 | Tenant substitution: receipt for tenant A replayed in tenant B | `DENY` | tenant and principal scopes checked | isolation |
| IFIP_SEC-CASE-04 | Revoked capability: signed old token after consent revoke | `DENY` | online epoch check under current governance state | dynamic revocation |
| IFIP_SEC-CASE-05 | Exact disclosure substitution: valid hash for one projection but alternate transport payload | `DENY` | distinct semantic/transport digest checks | byte binding |
| IFIP_SEC-CASE-06 | Recipient mismatch: capability forwarded to different dispatch adapter | `DENY` | audience binding prevents unintended delegation | recipient integrity |
| IFIP_SEC-CASE-07 | Expired receipt: valid signature, timestamp outside bounds | `DENY` | clock skew bounded and documented | expiry |
| IFIP_SEC-CASE-08 | Replay under key rotation: token from old key but still valid epoch and policy | `DECIDE_BY_SPEC` | key retention/retirement protocol explicit | rotation |
| IFIP_SEC-CASE-09 | Macaroon/Cedar parity: competitor with equivalent caveats and online epoch checks | `MEASURE` | measure forgery acceptance, size, verifier cost and liveness | strong comparator |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "IFIP_SEC-CASE-01",
  "venue": "ifip_sec",
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
