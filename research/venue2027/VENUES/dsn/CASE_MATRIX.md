# DSN — preregisterable scenario and oracle matrix
**Basis:** # DSN · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| DSN-CASE-01 | Nominal durable transition: one governed commit and one outbox event, no failure | `COMMITTED` | lineage, clinical row and durable outbox refer to same operation ID | success-path correctness |
| DSN-CASE-02 | Crash before SQL COMMIT: SIGKILL after flushed ORM changes but before server confirms transaction commit | `REJECTED_OR_NOT_COMMITTED` | no committed clinical mutation or falsely issued success receipt | atomicity |
| DSN-CASE-03 | Crash after SQL COMMIT before HTTP response: server commits then dies before returning response | `COMMITTED` | retry discovers committed record by idempotency key; one durable effect | unknown response reconciliation |
| DSN-CASE-04 | Broker replay: broker delivers same outbox message three times after consumer restart | `COMMITTED` | idempotent effect executed once; deliveries all recorded | duplicate effect prevention |
| DSN-CASE-05 | Revocation interleaving: consent revoked between initial authorization and actual mutation commit | `REJECTED` | authorization rechecked under applicable locks; no forbidden write | governance race |
| DSN-CASE-06 | Corrupted receipt: signed receipt digest differs from stored transition | `INDETERMINATE` | flag tamper, reconcile independently, no silent successful state | forensic validity |
| DSN-CASE-07 | Outbox delayed: message persists but broker is unavailable for bounded interval | `COMMITTED_BUT_PENDING_DELIVERY` | separate storage commit status from downstream delivery; bounded convergence | liveness |
| DSN-CASE-08 | Concurrent duplicate operation: two writers commit same operation ID concurrently | `ONE_COMMIT` | unique constraint and proper transaction retry avoid double effect | idempotency |
| DSN-CASE-09 | Durability cost stress: fixed offered rate at 1,2,4,8 workers | `MEASURE` | p99 RTO, fsyncs and queueing recorded for every arm | resource frontier |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "DSN-CASE-01",
  "venue": "dsn",
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
