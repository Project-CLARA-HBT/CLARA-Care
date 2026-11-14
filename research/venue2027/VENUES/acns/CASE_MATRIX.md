# ACNS — preregisterable scenario and oracle matrix
**Basis:** # ACNS · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| ACNS-CASE-01 | Threat-level extraction: accepted paper defines observer at server-side only | `CLASSIFY_L0` | two reviewers agree based on stated assumptions, not keywords | taxonomy validity |
| ACNS-CASE-02 | Transport attestation: paper proves bytes sent but not model internal execution | `CLASSIFY_L1` | exclude unsupported execution claim | claim scope |
| ACNS-CASE-03 | Provider receipt: externally verifiable receipt binds dispatched bytes | `CLASSIFY_L2` | validate receipt trust anchors and replay assumptions | evidence strength |
| ACNS-CASE-04 | Execution attestation: trusted environment attests specific execution and input | `CLASSIFY_L3_CONDITIONAL` | report trusted computing base and gaps | highest attestation |
| ACNS-CASE-05 | Ambiguous method: incomplete technical detail despite published prose | `UNRESOLVED` | record ambiguity with explicit code and author query | conservative coding |
| ACNS-CASE-06 | Reviewer disagreement: two independent reviewers disagree on class | `ADJUDICATE` | retain both raw classifications and third-party decision | inter-rater reliability |
| ACNS-CASE-07 | Date/venue leakage: paper from excluded year or venue enters candidate set | `EXCLUDE` | PRISMA-like explicit eligibility reason | systematic search |
| ACNS-CASE-08 | Proposed demo comparison: same task under 3 observer levels | `MEASURE` | demonstrate scope distinction without overselling execution truth | construct validity |
| ACNS-CASE-09 | Missing fulltext: DOI exists but source inaccessible | `NOT_REVIEWED` | not counted as assessed empirical evidence | missingness |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "ACNS-CASE-01",
  "venue": "acns",
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
