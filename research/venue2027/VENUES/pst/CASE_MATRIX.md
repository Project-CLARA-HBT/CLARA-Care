# PST — preregisterable scenario and oracle matrix
**Basis:** # PST · independently executable study implementation book. These are *designed fixtures* to implement and adjudicate, not executed research findings.
## Rules common to each case
Use synthetic identities, timestamps and stable source hashes; separate expected logical judgment from actual candidate output. Where expected is `MEASURE`/`INDETERMINATE`, do not coerce it to PASS. For each case generate 3 artifacts: `case.json` (input), `truth.json` (independent oracle/adjudicated label), `observed.json` (per-arm output with duration, status and evidence hashes). Runners MUST count timeout/unknown/rejected by arm.

| Fixture ID | Scenario / controlled input | Oracle target | Exact assertion / measured endpoint | Scientific purpose |
|---|---|---|---|---|
| PST-CASE-01 | Legitimate audit query: authorized investigator reconstructs bounded decision | `RECONSTRUCT` | minimal evidence sufficient for declared query | utility |
| PST-CASE-02 | Cross-tenant correlation: attacker combines two audit extracts | `NO_UNNECESSARY_LINK` | measure joinability and attack accuracy | unlinkability |
| PST-CASE-03 | Repeated-query differencing: adversary queries twice with adjacent windows | `MEASURE_LEAK` | quantify leakage; apply consistent query budgets | composition |
| PST-CASE-04 | Receipt tampering: forensic witness modified after commit | `DETECT_TAMPER` | validate hash chain and source audit | integrity |
| PST-CASE-05 | Overredaction: minimal receipt omits field needed for valid review | `INDETERMINATE` | report audit incompleteness, not false success | utility bound |
| PST-CASE-06 | Explicit sensitive metadata: purpose field reveals patient attribute | `EVALUATE_DISCLOSURE` | threat model governs redaction | metadata privacy |
| PST-CASE-07 | Missing key custody: authorized decryptor has no valid key | `INDETERMINATE` | report availability and key-governance limitations | reproducibility |
| PST-CASE-08 | Full log comparator: full raw logs as strong-forensic baseline | `MEASURE` | audit utility plus metadata leakage and storage | trade-off |
| PST-CASE-09 | No-log comparator: no retained receipt | `MEASURE` | privacy gain reported alongside reconstruction loss | trade-off |

## Per-case JSONL record contract
```json
{
  "schema_version": "clara.venue2027.scenario.v1",
  "case_id": "PST-CASE-01",
  "venue": "pst",
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
