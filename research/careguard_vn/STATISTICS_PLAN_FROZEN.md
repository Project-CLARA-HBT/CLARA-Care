# CareGuard-VN frozen statistics plan (Workstream G, G-010)

Status: **FROZEN** (planning/spec only). No benchmark has run and none may run
until the CG-01 external MANUAL gate (authorized DAV identity frame) passes.

Machine-readable artifact: `statistics_plan_freeze.json`
sha256 `09b4fbdf42a1755b08a49f38e36c433a423c24f46420a67d8262ea7de640a508`
(bound by the git commit recorded in `READINESS.md`).

This freeze supersedes the draft `statistics_plan.json` (v1, `draft_not_run`),
which remains untouched for historical immutability.

## Units

- **Identity unit**: one frozen DAV product identity case (one official DAV
  product record with `source_record_id` and `source_record_hash`).
- **DDI unit**: one frozen logical medication pair/case (accepted identity A ×
  accepted identity B matched to an external positive reference).
- **Clustering unit**: canonical product identity cluster. Natural variants
  (brand/generic/strength/form/registrant) and noisy variants
  (typo/whitespace/punctuation/diacritic) of one product resolve to the same
  cluster key. Within-cluster dependence is acknowledged: primary analysis is
  case-level with cluster-robust inference plus a cluster-level sensitivity run.

## Primary endpoint (CG-04)

**End-to-end false reassurance** = proportion of **all frozen externally
positive cases** for which CareGuard releases a completed reassuring
(no-interaction) conclusion when reassurance must not be released.

- Denominator: **all** frozen externally positive cases in the test set.
  Identity failure/ambiguity stays in the denominator and cannot be excluded.
- Numerator components (prespecified): wrong-identity reassurance,
  ambiguous/unresolved reassurance, stale/invalid-identity reassurance, and
  positive-reference missed after admissible identity.
- Uncertainty: two-sided 95% Wilson interval.

## Secondary decomposition

1. **Conditional DDI false-clear** — false-clear rate among admissibly
   resolved identities only. Decomposition, not a substitute endpoint.
2. **Identity accuracy** — accepted mapping matches the adjudicated frozen
   identity ledger; reported with numerator/denominator and abstentions.
3. **Abstention/clarification** — rate of clarification / unavailable
   (no-reassurance) conclusions per identity-resolution state.
4. **Risk-coverage grid** — coverage and false reassurance by stratum:
   DDInter risk/severity level, identity-resolution state, source-field
   completeness, brand-generic invariance stratum. Empty cells are reported as
   empty, never as zero.
5. **Error decomposition** — identity-stage vs DDI-knowledge error via the
   Mode B oracle-identity boundary on identical frozen inputs.

## Precision objective (CG-03)

Target: enough positive-reference cases that the two-sided 95% interval for a
plausible 5–10% false-reassurance rate has half-width ≤ 3 pp:

```
n = ceil( z^2 · p · (1−p) / h^2 ),  z = 1.96, h = 0.03
p = 0.05  ->  n = 203   (achieved half-width 0.0300)
p = 0.10  ->  n = 385   (achieved half-width 0.0300)
planning_target_n = 385   (maximum over the plausible range)
```

Reproduced by `research/careguard_vn/precision_requirement.py`. If the mapped
eligible positive population cannot meet the target, report the **achieved
precision** with the observed denominator; do not manufacture pseudo-independent
perturbations.

## Sample selection

Use all eligible frozen externally positive cases, or a prespecified
stratified sample/cap. Never stop based on observed performance.
Stratification dimensions: DDInter risk/severity level, identity-resolution
state, registration/registrant, dosage form. Cap is prespecified at
source-set freeze; no performance-adaptive stopping.

## Development/test split

Split at the product-identity-case level (never by string), 80/20
development/test, stratified by registrant and DDInter risk level. Split is
assigned only after source mapping and before any CareGuard result
inspection. Development-only rows may tune normalization aliases/rules and are
never reused as test rows. **Assignment is BLOCKED** until the DAV identity
frame is delivered and mapped.

## Exclusions (prespecified reason codes)

| Code | Reason |
| --- | --- |
| E01 | DAV record lacks active-ingredient text |
| E02 | DAV record lacks product-name text |
| E03 | duplicate registration number with conflicting identity fields (source_conflict) |
| E04 | non-medication product (device/cosmetic/not a drug) |
| E05 | no RxNorm candidate above deterministic threshold |
| E06 | external positive pair has no eligible frozen identity on either side |
| E07 | DailyMed confirmation subset never used as a negative or exclusion driver |
| E08 | record not in the frozen source-manifest row-hash inventory |

## Source hashes (frozen, from controlled manifests)

| Role | Source | Hash / inventory |
| --- | --- | --- |
| Positive DDI reference | DDInter 2.0 | controlled-manifest sha256 `253cf0ab…986c26`; payload bundle sha256 `b49b8094…44bb1`; 222,383 rows |
| Terminology | RxNorm 2026-08-03 prescribable | published MD5 `5854a3cc…a0625`; payload sha256 `ca904847…71000`; 6,183,895 RRF rows |
| Regulatory confirmation | DailyMed warfarin subset | payload sha256 `1d0d99c8…ceef3`; 5 records, per-record hashes in manifest |
| Vietnam identity frame | DAV | **NOT_ACQUIRED** — CG-01 external MANUAL gate; source-set freeze BLOCKED |

## Release rule and non-claims

Reassurance is released only for accepted identities bound to a current frozen
source record; ambiguous/unresolved/stale/conflicting identities return
clarification or unavailable and count toward abstention. No negative/
specificity claim is made (DDInter absence is not a negative label). No
performance result is claimed.
