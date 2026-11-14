# COMPSAC — preregisterable scenario and oracle matrix
**Basis:** # COMPSAC · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| COMPSAC-CASE-01 | Independent partition mutation: new observation unrelated to target dependency graph | `ALLOW` | valid write not rejected by unrelated profile-wide update | false-stale |
| COMPSAC-CASE-02 | Required medication changed: read set depends on metformin and metformin updated | `REJECT_OR_RECOMPUTE` | no stale dependent write admitted | safety |
| COMPSAC-CASE-03 | Consent revoked concurrently: governance epoch changes before write lock | `DENY` | fresh read under lock prevents forbidden commit | consent correctness |
| COMPSAC-CASE-04 | Missing dependency edge: generated closure omits required allergy resource | `DENY_OR_INDETERMINATE` | independent schema oracle detects incompleteness | closure completeness |
| COMPSAC-CASE-05 | Phantom insert: negative predicate read, new matching row inserted | `DENY_OR_SERIALIZE` | predicate/phantom handling matches strong PG baseline | write-skew |
| COMPSAC-CASE-06 | Opposite lock order: two writers lock resources in reverse order | `NO_DEADLOCK` | canonical lock ordering or bounded retry | concurrency |
| COMPSAC-CASE-07 | High contention: Zipf-skew case at 16 workers | `MEASURE` | same isolation levels, retry counts, throughput & tail latency | scaling |
| COMPSAC-CASE-08 | Empty dependency closure: operation has no domain dependencies, governance still applies | `ALLOW_IF_GOVERNED` | policy/consent anchor never omitted | minimal scope |
| COMPSAC-CASE-09 | PG SSI parity: SERIALIZABLE baseline implements identical policy semantics | `MEASURE` | compare safe throughput and aborts without unfair per-arm work | strong comparison |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "COMPSAC-CASE-01",
  "venue": "compsac",
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
