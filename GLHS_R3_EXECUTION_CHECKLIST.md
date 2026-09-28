# GLHS R3 EXECUTION CHECKLIST

## Phase 0 — Branch & research freeze
- [ ] Branch from `research/glhs-q2-r2-experiments`.
- [ ] Record parent SHA `e7a073749d8d3d434f6d47204238cc6655431f76`.
- [ ] Create `research/glhs_journal/q3_r3/`.
- [ ] Build literature matrix.
- [ ] Freeze novelty contract.
- [ ] Generate claim budget.
- [ ] Establish dual-SHA provenance fields.
- [ ] Confirm all freeze timestamps precede execution.

## Phase 1 — Inference binding
- [ ] Inspect current `GlhsInferenceContextBinding`.
- [ ] Add only missing schema fields.
- [ ] Define canonical request envelope.
- [ ] Digest model-visible disclosure slot.
- [ ] Create binding immediately before provider dispatch.
- [ ] Finalize binding after response.
- [ ] Define retry/fallback binding semantics.
- [ ] Add substitution tests.

## Phase 2 — Proposal lineage/admission
- [x] Centralize GRWC verifier.
- [x] Preserve root lineage during review.
- [x] Block binding-mode downgrade.
- [x] Add stable reason codes.
- [x] Verify same-transaction commit semantics.

## Phase 3 — Dependency completeness
- [ ] Operation dependency registry.
- [ ] Minimum-vector derivation.
- [ ] Conservative-superset semantics.
- [ ] Missing-dependency hard reject.
- [ ] Real PostgreSQL write-skew tests.

## Phase 4 — Prospective protocol freeze
- [ ] E01–E14 protocol files.
- [ ] Seeds frozen.
- [ ] Schedule/cohort hashes frozen.
- [ ] Primary endpoints frozen.
- [ ] Analysis plans frozen.
- [ ] Power analysis frozen where required.

## Phase 5 — P0 experiments
- [ ] E01 actual inference continuity.
- [ ] E02 component ablation.
- [ ] E03 minimal baseline.
- [ ] E04 real PostgreSQL TOCTOU.
- [ ] E05 dependency completeness.
- [ ] E06 anti-downgrade.
- [ ] E07 canonicalization.
- [ ] E08 formal assurance.

## Phase 6 — P1 systems
- [ ] E09 real PostgreSQL concurrency.
- [ ] E10 HTTP/PostgreSQL full-stack.

## Phase 7 — P1 model study
- [ ] Prospective sample-size/power calculation.
- [ ] Frozen real-provider cohort.
- [ ] E11 actual two-model run.
- [ ] Provider reported IDs verified.
- [ ] E12 generated from actual error ledger.

## Phase 8 — External
- [x] E13 source-disjoint tasks.
- [x] Human status honestly recorded.

## Phase 9 — Reproduction
- [ ] Publish raw bytes.
- [ ] Generate checksums.
- [ ] Create immutable release.
- [ ] Fresh checkout reproduction.
- [ ] Network-disabled deterministic analysis.
- [ ] Artifact-deletion negative test.
- [ ] Claim-ledger negative test.
- [ ] Backend/wording consistency test.

## Phase 10 — Manuscript
- [ ] Replace old contribution framing.
- [ ] Rewrite Related Work.
- [ ] Put invariant before architecture.
- [ ] Report minimal-token result prominently.
- [ ] Separate simulations and production evidence.
- [ ] Update limitations.
- [ ] Adapt to selected journal.

## Final gate
- [ ] Every MUST requirement passes.
- [ ] No unsupported model-provider claim.
- [ ] No simulated PostgreSQL claim.
- [ ] No missing raw artifact.
- [ ] No retrospective freeze.
- [ ] No internal-agent “independent review” language.
- [ ] Hostile reviewer audit passes.
