# CareGuard-VN External Benchmark Master Spec

Status: execution specification for a results-ready independent CareGuard manuscript.
Repository: `Project-CLARA-HBT/CLARA-Care`
Audited main snapshot at drafting: `81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`.

## 0. Scientific objective

Build, run, seal, and report an external evaluation of CareGuard that answers a different question from GLHS:

> Does making current, source-verifiable medication identity a mandatory precondition for downstream DDI release reduce false-clear outcomes at a defensible automatic-coverage cost, particularly under noisy, ambiguous, local-brand, and stale identity conditions?

Do **not** optimize for a pretty accuracy number. The primary outcome is safety under independently sourced identity/DDI evidence.

## 0.1 Literature-derived novelty lock

The manuscript and implementation program MUST preserve the following boundary established by the August 2026 literature review. Do not broaden novelty after results are known.

**Already established; never claim as novel in isolation:** RxNorm medication normalization; approximate/fuzzy drug-name matching; LLM-assisted lexical normalization; confidence tiers; ambiguity characterization; optional human review; abstention/selective prediction; terminology/source versioning; DDI lookup/severity databases; Vietnamese-language rendering; wrong-drug/LASA detection.

**Closest contemporary comparator:** RxMap (JAMIA Open 2026, doi:10.1093/jamiaopen/ooag085), which combines deterministic RxNorm candidate generation, LLM-assisted parsing, ingredient-level reconciliation, confidence/review, and reports RxCUI F1 0.966 on 22,624 unique strings. Any paper claim that CareGuard is novel merely because it handles noisy names, uncertainty, LLM parsing, or human review is invalid.

**Other mandatory boundary literature:**
- Peters et al. 2011 approximate RxNorm matching: intended concept top-3 in ~90-96% of matched local drug-name variants.
- Newman-Griffis et al. 2021 (doi:10.1093/jamia/ocaa269): ambiguity is established and underrepresented in clinical normalization benchmarks.
- Swaminathan et al. 2024 (doi:10.1093/jamia/ocad182): selective prediction/abstention and automation-vs-error trade-offs are established.
- Gallifant et al. RABBITS, EMNLP Findings 2024 (doi:10.18653/v1/2024.findings-emnlp.726): physician-validated brand/generic substitutions can reduce biomedical LLM performance by 1-10%.
- Chen et al. MedGuard 2024 (doi:10.1016/j.cmpb.2023.107869): wrong-drug/LASA alerting is established medication-safety work.
- Gibson et al. 2026 (doi:10.1111/bph.70515): 44-study systematic review shows generally poor-to-moderate agreement and weak/heterogeneous DDI reference standards.
- Holbrook et al. 2025 (doi:10.1093/jamia/ocaf139): DDI alerts have not demonstrated clear patient-important outcome benefit; do not convert software-safety findings into clinical-effectiveness claims.

**Novelty that MAY be tested:** the composition of these established components into a **Source-Bound Medication Identity (SBMI) release contract**. A DDI conclusion is admissible only when every required medication identity is current, source-verifiable, and unambiguous under the declared policy. Stale source-bound selections are inadmissible. The scientific endpoint is not 'can the system abstain?' but **does mandatory identity gating reduce false-clear/wrong-identity completion at a stated automatic-coverage cost?**

**Required error decomposition:** compare end-to-end CareGuard with an oracle-identity arm using the same downstream DDI engine. Attribute failures to (a) identity resolution, (b) DDI knowledge coverage, or (c) release-policy failure. Never collapse them into one accuracy number.

**Required headline visualization:** risk-coverage curve (false-clear and/or wrong-identity risk versus automatic coverage), plus fixed prespecified operating points if applicable. Do not select a threshold on final-test results.


## 1. Non-negotiable claim boundaries

1. Do not call same-DrugBank source-to-runtime checks clinical accuracy.
2. Do not use CareGuard-authored fixtures, curated local rules, or the runtime DrugBank artifact as the sole external oracle.
3. Do not infer a true negative merely because a pair is absent from DDInter, DrugBank, DailyMed, or another knowledge base.
4. Do not report specificity/FPR/PPV unless an explicit independently adjudicated negative reference set exists.
5. Do not silently upgrade the old `242/250` deployment result after source-level fixes. A new runtime artifact requires a new run ID and recorded deployment revision/image/source hashes.
6. Do not describe DAV registration data as definitive current market status. Use it as an external product-identity source and preserve the portal's caveat about later amendments/withdrawals.
7. Do not redistribute licensed DrugBank data or n2c2-protected content.
8. No clinical-effectiveness, prescribing, patient-outcome, or regulatory-compliance claim.

## 2. Required codebase audit before benchmark

Create `evaluation/careguard_external/` and first generate `semantics_audit.json` that records:
- active source precedence when DrugBank is ready;
- behavior when DrugBank is unavailable/degraded;
- clarification feature-flag semantics;
- legacy vs strict identity path;
- whether local curated rules can override, supplement, or are bypassed by ready DrugBank;
- severity derivation path and whether any DrugBank free-text heuristic is used;
- external source status (RxNav retired, openFDA behavior);
- exact API endpoints used by the benchmark.

Resolve documentation/code contradictions before headline runs. Update docs/tests so there is one canonical policy. Do not change semantics merely to improve benchmark performance.

## 3. External source adapters

### 3.1 DAV identity source
Implement an adapter that accepts an **operator-frozen official DAV export/snapshot**. Prefer an official bulk/API/export path if documented. If no public bulk path exists, do not bypass anti-bot/access controls; provide a reproducible importer for an operator-supplied CSV/JSON snapshot.

Minimum normalized fields:
`dav_record_id`, `registration_or_license_id`, `product_name`, `active_ingredients[]`, `strength`, `dosage_form`, `manufacturer`, `source_url_or_record_ref`, `retrieved_at`.

Use DAV for identity only. Preserve raw source fields and a normalized derivative separately.

### 3.2 RxNorm
Support the July 6, 2026 Current Prescribable Content release or a later explicitly frozen release. Record archive name, checksum, release date, and parser version. Build exact and approximate deterministic baselines without using final-test outcomes to set thresholds.

### 3.3 DDInter 2.0
Implement importer for official downloadable DDInter 2.0 CSV partitions. Freeze all downloaded files with SHA-256 and row counts. Construct an external **positive DDI** set after identity mapping. Never create negatives by random absence.

### 3.4 DailyMed
Implement bulk SPL + SPL-RxNorm mapping importer. Extract only explicitly interaction-relevant positive warnings using deterministic rules. Freeze extraction rules before final evaluation. Manually audit a small random subset of extractor outputs before sealing; do not tune rules on CareGuard errors from the final set.

### 3.5 n2c2 (optional gated track)
Provide an importer only. Never automate credential acquisition, DUA bypass, or redistribution. If data are available lawfully, filter the official annotations to RxNorm-relevant medication/treatment concepts and report that the terminology version is older than the 2026 runtime terminology.

### 3.6 RxMap comparator
RxMap is the mandatory nearest-neighbor comparator to **attempt**. First inspect its official paper/code/reproducibility path and applicable terms. If reproducible, run it on the same lawful frozen normalization units without final-test tuning. If it cannot lawfully or technically be reproduced, record a machine-readable `NOT_RUN` reason plus the attempted version/URL/date; still cite it prominently as the closest prior work. Never fabricate or approximate RxMap results with an unrelated LLM pipeline.

## 4. Canonical benchmark identity schema

Every medication concept must use a source-separated structure:

```json
{
  "surface": "...",
  "source_record_id": "...",
  "product_name": "...",
  "ingredients": [{"name":"...","rxnorm_id":"...","drugbank_id":"..."}],
  "strength": "...",
  "dose_form": "...",
  "manufacturer": "...",
  "mapping_status": "exact|reviewed|ambiguous|unmapped",
  "mapping_evidence": ["..."]
}
```

Never force an ambiguous cross-database mapping. Exclude or independently adjudicate it according to a frozen policy.

## 5. Benchmark tracks

### Track A — Vietnam product identity
Primary unit: unique DAV product/registration record.
Conditions: clean product name plus versioned robustness transforms: no-diacritic, punctuation/space, strength/form suffix, manufacturer suffix, deterministic typo, OCR-like substitutions, Vietnamese-English code-switch templates, and a brand--generic invariance stratum where the external source supports both forms (motivated by RABBITS).

Transformations are repeated observations clustered under the same product, not independent products.

Metrics:
- exact ingredient-set accuracy;
- ingredient precision/recall/F1 for combinations;
- wrong-identity completion rate;
- abstention/clarification rate;
- safe coverage = correct completed / all cases;
- clarification candidate-set recall where applicable;
- risk--coverage curve for wrong-identity/false-clear risk versus automatic coverage.

### Track B — External normalization
Use lawful n2c2 data if available and/or another independently annotated public medication-string set. Compare:
1. RxNorm exact;
2. RxNorm approximate;
3. fixed fuzzy baseline;
4. CareGuard legacy;
5. CareGuard strict;
6. RxMap if reproducible.

Do not tune thresholds/prompts on final test.

### Track C — DDInter external positive-pair safety
Primary unit: unordered canonical drug pair.
Require pair mapping independent of CareGuard output.
Run each pair through:
- CareGuard legacy;
- CareGuard strict;
- oracle-identity CareGuard (gold identity injected into DDI stage).

Primary endpoint:
`false_clear_rate = externally positive pairs returned as completed no-major-DDI / externally positive eligible pairs`.

This endpoint must be plotted against automatic coverage for every system that can abstain/defer. The confirmatory comparison is strict SBMI versus prespecified automation-first baselines at declared operating points; the paper must not claim novelty from abstention itself.

Secondary:
- external positive-pair detection recall;
- abstention rate;
- identity-failure rate;
- oracle-identity recall;
- legacy-vs-strict paired difference.

No specificity unless explicit negative gold is added.

### Track D — DailyMed regulatory positive subset
Primary unit: explicit label-supported interaction pair/target after frozen extraction and mapping.
Report warning recall, abstention, identity failure, and false-clear rate. Keep this separate from DDInter rather than pooling sources with different curation semantics.

## 6. Baselines and ablations

Required:
- CareGuard legacy/non-strict;
- CareGuard strict source-bound;
- RxNorm exact;
- RxNorm approximate;
- transparent fuzzy matcher;
- oracle identity + same DDI engine;
- RxMap if reproducible; otherwise a sealed `NOT_RUN` feasibility record is mandatory.

Ablations:
- strict without version binding;
- strict without ambiguity blocking (test-only sandbox, never production default);
- exact source dictionary only vs bounded Vietnamese free-text extraction;
- optional LLM span augmentation on/off, with proof that the model cannot directly choose IDs or DDI conclusions.

## 7. Statistics

- Every result includes numerator/denominator and 95% CI.
- Paired binary contrasts: paired risk difference + exact McNemar when valid.
- Multiple prespecified confirmatory contrasts: Holm correction.
- Perturbation conditions: cluster bootstrap by original product/string/pair.
- Report both per-clean-unit and per-perturbation summaries; never inflate N by calling aliases/perturbations independent clinical units.
- If the final informative discordant-pair count is below the prespecified power target, say so.

Before final execution, add `statistics_plan.json` with primary endpoint, confirmatory contrasts, alpha, CI method, cluster unit, exclusions, missing/error policy, and power rationale. Freeze/hash it before running final test.

## 8. Source and run freeze

Create `evaluation/careguard_external/freeze.py` and a manifest schema requiring:
- code Git SHA;
- source URLs/access statements;
- source versions/retrieval dates;
- file SHA-256 and row counts;
- mapping-policy hash;
- perturbation-policy hash;
- baseline versions/configs;
- feature flags;
- seeds;
- final unit counts;
- development/test disjointness proof.

Final raw outputs go to:
`artifacts/careguard-external/<run-id>/`

Required files:
- `source_manifest.json`
- `freeze.json`
- `statistics_plan.json`
- `identity_cases.parquet|csv`
- `ddi_positive_cases.parquet|csv`
- `raw_predictions.csv`
- `errors.csv`
- `metrics.json`
- `paired_statistics.json`
- `artifact-sha256.json`
- `MANUSCRIPT_RESULTS.md`

A seal command must fail if any required artifact is missing or if hashes changed.

## 9. Performance and deployment rerun

After semantics are fixed, rerun the existing DrugBank runtime conformance on the actual isolated deployment. Preserve the old run. The new run must record deployment/image digest, DrugBank source version/hash, positive/absent-pair sample construction, seed, latency distribution, and exact failures.

This remains technical conformance and must be reported separately from DDInter/DailyMed external validation.

## 10. Manuscript integration

Update the arXiv draft only from sealed artifacts. Replace every `PENDING SEALED EXTERNAL RUN` marker with source-generated tables/text. Never hand-copy a number into the paper if it is not traceable to `artifact-sha256.json`.

Generate at least:
- Figure 1: literature-derived SBMI contract: source-bound identity -> admissible/clarification -> DDI release;
- Figure 2: external source separation and evaluation design;
- Figure 3: primary risk--coverage curve: automatic coverage vs wrong-identity/false-clear risk;
- Table 1: source versions and frozen counts;
- Table 2: identity benchmark;
- Table 3: DDInter positive-pair results;
- Table 4: DailyMed regulatory subset;
- Table 5: ablations/error taxonomy.

## 11. Release gate

Headline claims are allowed only if:
- final external source manifests are frozen and hashed;
- no test-set tuning occurred;
- DDInter/DailyMed results are source-separated;
- identity mapping ambiguity policy is frozen;
- unit-of-analysis is correct;
- all failures are retained;
- manuscript numbers exactly reproduce from sealed artifacts.

If external sources cannot be lawfully obtained or a valid mapping cannot be established, mark that track `NOT RUN`; never replace missing evidence with synthetic success.

Before manuscript release, run a claim-lint that rejects phrases implying novelty for normalization, ambiguity detection, abstention, DDI lookup, terminology versioning, Vietnamese UI, or wrong-drug detection alone. The allowed central claim is SBMI-as-downstream-release-precondition plus its externally measured false-clear/risk--coverage effect.
