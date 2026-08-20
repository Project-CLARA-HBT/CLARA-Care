# /goal — CareGuard-VN SBMI external evidence program

Read `CAREGUARD_EXTERNAL_BENCHMARK_MASTER_SPEC.md` first; it is the source of truth. Preserve the literature-derived novelty lock. Do not fabricate data, labels, access, results, or novelty.

Central hypothesis: medication normalization, ambiguity handling, human review, abstention, versioning and DDI lookup already exist in prior work. CareGuard's testable contribution is **Source-Bound Medication Identity (SBMI) as a mandatory downstream release precondition**: no DDI conclusion when a required identity is unresolved, ambiguous, stale, substituted, or source-invalid. Primary question: does strict SBMI reduce false-clear/wrong-identity completion at an acceptable automatic-coverage cost?

Implement under `evaluation/careguard_external/`; final artifacts go to `artifacts/careguard-external/<run-id>/`.

Required work:
1. Audit/reconcile CareGuard strict-mode/source-precedence semantics across code/tests/docs. Never change behavior merely to improve scores.
2. Build lawful, versioned adapters/manifests for operator-frozen DAV product data, RxNorm CPC, DDInter 2.0, DailyMed SPL+RxNorm mappings; n2c2 only with existing lawful DUA access.
3. Attempt to reproduce **RxMap 2026** as the mandatory nearest-neighbor normalization comparator. If impossible, emit sealed `NOT_RUN` evidence with version/URL/reason; never substitute fake RxMap results.
4. Freeze sources, crosswalk/mapping rules, ambiguity policy, perturbations, baselines, seeds, units, stats plan and Git SHA before final testing.
5. Tracks: DAV Vietnam identity; independent normalization; DDInter external positive-pair safety; DailyMed regulatory positives. Include no-diacritic/typo/OCR/code-switch and brand↔generic robustness where source identities support it.
6. Compare RxNorm exact/approximate, fixed fuzzy, CareGuard legacy, CareGuard strict SBMI, oracle-identity CareGuard, and RxMap when reproducible.
7. Primary endpoint: false-clear rate on externally positive interactions. Also report wrong-identity completion, identity exact/set match, abstention, safe coverage, positive-pair recall, oracle-identity recall and **risk–coverage curves**. Do not claim novelty from abstention itself.
8. Decompose every final failure into identity-resolution, DDI-knowledge, release-policy, source/mapping, or transport failure. Oracle identity must use the same downstream DDI engine.
9. Never treat absence from DDInter/DrugBank/DailyMed as a true negative. No specificity/FPR/PPV without explicit independent negative gold.
10. Correct units: clean external product/string/pair is primary; perturbations/aliases are clustered repeats. Use numerator/denominator + 95% CI, paired risk differences, exact McNemar where valid, cluster bootstrap and Holm for prespecified contrasts.
11. Preserve old 242/250 DrugBank deployment result as same-source conformance. Rerun after fixes under a new run ID; never relabel it external/clinical accuracy.
12. Seal outputs with hashes and validators; generate `MANUSCRIPT_RESULTS.md` and machine-readable tables. Update manuscript only from sealed artifacts.
13. Add claim-lint: reject novelty language for normalization, LLM parsing, ambiguity, human review, abstention, terminology versioning, DDI lookup/severity, Vietnamese UI, or wrong-drug/LASA alone. Allowed main claim: SBMI release contract + externally measured false-clear/risk–coverage effect.

If a required source is unavailable or cannot be mapped lawfully, mark `NOT_RUN`. Never replace missing evidence with synthetic success.
