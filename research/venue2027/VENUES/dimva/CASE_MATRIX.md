# DIMVA — preregisterable scenario and oracle matrix
**Basis:** # DIMVA · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| DIMVA-CASE-01 | Single legitimate retry: authorized retry due to network failure | `BENIGN` | no campaign alert at ordinary false-positive budget | specificity |
| DIMVA-CASE-02 | Purpose-hopping campaign: same evidence replayed under new purpose | `ATTACK` | sequence detector links related attempts | campaign detection |
| DIMVA-CASE-03 | Low-and-slow drift: long sparse sequence with escalating lineage reuse | `ATTACK` | detect at bounded false alarms/day | temporal coverage |
| DIMVA-CASE-04 | Benign care-team handoff: properly delegated role changes | `BENIGN` | do not treat authorized delegation as attack | fairness |
| DIMVA-CASE-05 | Adversarial pacing: attacker shifts time interval beyond fixed window | `ATTACK_OR_EXPOSE_LIMIT` | stress robustness against timing evasion | resilience |
| DIMVA-CASE-06 | Case-family holdout: new patient/task family, same attack family | `MEASURE` | held-out detection PR-AUC and recall | generalization |
| DIMVA-CASE-07 | Attack-family holdout: previously unseen mutation attack mechanism | `MEASURE` | unknown-class or open-set performance reported | novel attacks |
| DIMVA-CASE-08 | Noisy alerts: false positive bursts under busy provider | `MEASURE` | operator budget and alert/day; avoid precision inflation | operational metric |
| DIMVA-CASE-09 | Strong sequence detectors: HMM and boosted features with equal metadata | `MEASURE` | compare fairness, training labels, cost | strong baseline |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "DIMVA-CASE-01",
  "venue": "dimva",
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
