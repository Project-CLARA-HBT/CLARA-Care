# GLHS Q2-R2 Execution Checklist

**Source of truth:** `codex/commitloop-phase-a`  
**Audited head:** `81f040d3e05905cc384239c5ae130f629e722d3e`

## Gate 0 — freeze semantics

- [ ] Cut experiment branch from audited/latest approved SHA.
- [ ] Run full lint/type/test baseline.
- [ ] Complete paper/code synchronization audit.
- [ ] Confirm canonicalization profile in code and manuscript match.
- [ ] Confirm formal model is public/inspectable and paper wording matches.
- [ ] Generate write-route inventory.
- [ ] Freeze global statistics plan.
- [ ] Initialize all claim ledger rows as NOT_RUN.

## Gate 1 — novelty/minimality

- [ ] Implement 2^3 identity/digest/evidence binding component ablation.
- [ ] Build component-discriminating schedule holdout.
- [ ] Run/seal E01 on isolated PostgreSQL.
- [ ] Implement MIN_READSET_TOKEN baseline.
- [ ] Optional HMAC token baseline.
- [ ] Run same schedules against baseline(s).
- [ ] Update novelty framing based on actual equivalence/disagreement.

## Gate 2 — downgrade/dependency safety

- [ ] Test all THSS-origin write routes for downgrade.
- [ ] Add schema-derived required dependency contract.
- [ ] Mutate one required dependency at a time.
- [ ] Add pairwise omission mutants.
- [ ] Add classic multi-entity write-skew schedules.
- [ ] Require zero accepted required-dependency omission mutants.

## Gate 3 — concurrency/TOCTOU

- [ ] Replay V2-05 and V2-09 with instrumentation.
- [ ] Publish root-cause classification without rewriting old evidence.
- [ ] Generate/freeze ≥1,024 unique logical TOCTOU schedules.
- [ ] Use admissible outcome sets for overlap schedules.
- [ ] Execute primary PostgreSQL pass.
- [ ] Execute nested jitter robustness repetitions.
- [ ] Preserve/shrink every forbidden outcome.
- [ ] Seal raw + analysis artifacts.

## Gate 4 — protocol assurance

- [ ] Publish canonical JSON machine-readable vectors.
- [ ] Cross-check RFC8785-native vectors independently.
- [ ] Test historical canonicalization profiles.
- [ ] Document formal state model/bounds.
- [ ] Map all 11 invariants to production enforcement.
- [ ] Mutation-test invariant checker.
- [ ] Execute depth 5/6 sealed formal exploration.

## Gate 5 — model-context replication

- [ ] Create new source-disjoint confirmatory cohort/freeze.
- [ ] Power study for ±2 pp equivalence margin.
- [ ] Freeze exact Claude + Gemini model IDs.
- [ ] No fallback.
- [ ] Randomize/interleave request order.
- [ ] Run primary Strict THSS vs full history paired grid.
- [ ] Validate every expected call/cell.
- [ ] Stratify malformed outputs by condition and taxonomy.
- [ ] Run deterministic repair / one-retry sensitivity as secondary analysis.
- [ ] Reproduce derived results with network disabled.

## Gate 6 — optional systems/external strengthening

- [ ] Run Zipfian/partial-overlap/multi-entity concurrency benchmark.
- [ ] Run service-layer performance at final SHA.
- [ ] Add HTTP full-stack performance if kept in main manuscript.
- [ ] Freeze lawful external structured cohort if available.
- [ ] Independent human adjudication only if qualified reviewers are actually available.

## Final release gate

- [ ] All required artifacts have immutable checksums.
- [ ] No NOT_RUN row contributes to a numerator/denominator.
- [ ] Exact code SHA and environment recorded.
- [ ] No evaluation-only disable flag exists in production paths.
- [ ] All headline tables regenerate from sealed raw artifacts.
- [ ] Claim-to-evidence ledger passes.
- [ ] Paper/code sync has no material unresolved discrepancy.
- [ ] Manuscript updated only after gate passes.
- [ ] Historical frozen artifacts remain untouched.
