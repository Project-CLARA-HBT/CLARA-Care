# SACMAT — preregisterable scenario and oracle matrix
**Basis:** # SACMAT · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| SACMAT-CASE-01 | ABAC permit: matching subject role, resource and purpose | `PERMIT` | policy compiler and independent oracle agree | basic soundness |
| SACMAT-CASE-02 | ABAC deny: purpose mismatch with otherwise valid attributes | `DENY` | deny at PDP and enforcement point | basic completeness |
| SACMAT-CASE-03 | Consent mutation: grant is withdrawn before access | `DENY` | current policy eval invalidates stale grant | dynamic policy |
| SACMAT-CASE-04 | Indeterminate policy: missing authoritative consent epoch | `INDETERMINATE` | never silently map to valid permit | three-valued semantics |
| SACMAT-CASE-05 | Policy precedence: conflicting permit/deny policies | `DECIDE_BY_XACML_RULE` | match declared policy-combining algorithm | normative semantics |
| SACMAT-CASE-06 | Mutant dropped purpose check: test removes purpose predicate | `DETECT_MUTANT` | corpus test kills security-critical mutant | benchmark sensitivity |
| SACMAT-CASE-07 | False-positive mutation: semantically equivalent mutant | `EQUIVALENT` | manual equivalence adjudication recorded | mutation validity |
| SACMAT-CASE-08 | Cedar comparator: same policy expressed in native Cedar semantics | `MEASURE` | record translator differences and true engine parity | strong comparator |
| SACMAT-CASE-09 | Property test unseen roles: out-of-training subject/resource pair | `MEASURE` | macro recall and over-permit rate on held-out policy families | generalization |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "SACMAT-CASE-01",
  "venue": "sacmat",
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
