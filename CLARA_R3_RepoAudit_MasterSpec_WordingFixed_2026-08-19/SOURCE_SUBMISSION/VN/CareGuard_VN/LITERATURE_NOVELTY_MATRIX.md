# CareGuard-VN Literature & Novelty Matrix (August 2026)

Purpose: lock the manuscript's novelty boundary before external benchmark results are inspected. This is a targeted literature review, not a PRISMA systematic review.

| Research line | Representative evidence | What prior work already establishes | Consequence for CareGuard-VN |
|---|---|---|---|
| Medication normalization | RxNorm; MedXN; Peters et al. 2011 approximate matching; Chen et al. 2026 MCN survey; RxMap 2026 | Exact/normalized/approximate matching, local drug-name variants, LLM-assisted parsing, confidence/review, high RxCUI mapping performance | Do **not** claim noisy medication normalization, LLM parsing, candidate ranking, or human review as novel. RxMap is the nearest-neighbor comparator. |
| Ambiguity in concept normalization | Newman-Griffis et al., JAMIA 2021, doi:10.1093/jamia/ocaa269 | Ambiguity is established and underrepresented in standard clinical normalization benchmarks; multiple ambiguity types are known | Do not claim ambiguity detection as novel. Study the downstream consequence of ambiguity for DDI release. |
| Selective prediction / abstention | Swaminathan et al., JAMIA 2024, doi:10.1093/jamia/ocad182 | Clinical systems can abstain/defer and trade automation coverage against error cost | Do not claim abstention itself. CareGuard must distinguish structural source admissibility from confidence-threshold rejection. |
| Drug-name robustness | Gallifant et al., RABBITS, Findings of EMNLP 2024, doi:10.18653/v1/2024.findings-emnlp.726 | Physician-validated brand/generic substitutions can reduce biomedical LLM benchmark performance by 1–10% | Motivates brand↔generic and local-name robustness strata; does not establish CareGuard novelty by itself. |
| Wrong-drug/LASA safety | Chen et al., MedGuard, CMPB 2024, doi:10.1016/j.cmpb.2023.107869 | Wrong-drug and look-alike/sound-alike medication alerting has been studied in deployed CDSS | Do not claim general wrong-drug prevention as novel. Focus on wrong/ambiguous normalized identity propagating into DDI conclusions. |
| DDI databases | DrugBank; DDInter 2.0 | Large curated DDI knowledge resources and severity/management data already exist | DDI lookup/severity is not novelty. DDInter should be an independent positive reference, not universal truth. |
| DDI evidence verification | CrossDDI, BioNLP 2026 | Verification-first DDI pipelines can require positive interaction claims to be explicitly supported by structured/literature evidence | Do **not** claim evidence-grounded DDI release in general. CareGuard-VN gates the *medication identity* before downstream DDI verification/release. |
| DDI checker validity | Gibson et al., British Journal of Pharmacology 2026, doi:10.1111/bph.70515 | 44-study review found generally poor-to-moderate agreement and heterogeneous/weak reference standards | Never infer negatives from database absence; use source-separated positive references and cautious claims. |
| DDI alert clinical outcomes | Holbrook et al., JAMIA 2025, doi:10.1093/jamia/ocaf139 | Eight controlled/prospective studies (43,413 patients) did not show clear patient-important outcome benefit | The paper evaluates software/information safety, not clinical effectiveness. |
| Terminology versioning | Versioned RxNorm releases and terminology practice | Source/version identifiers are established | Versioning alone is not novel. The candidate contribution is making a stale source-bound identity **inadmissible for a later downstream DDI release**. |
| Vietnam localization | DAV public product registration data | Local product names, ingredients, strength, form, registration/manufacturer fields can provide an external identity source | Vietnamese UI is not novelty. DAV supplies an independently sourced local product-identity stress test. |

## Locked central novelty

**Source-Bound Medication Identity (SBMI) as a downstream release contract.** A DDI conclusion is admissible only if every required medication has a current, source-verifiable identity under the declared policy. Unknown, ambiguous, substituted, stale, or source-invalid identities must produce clarification/non-release rather than a reassuring DDI conclusion.

Formal target:

`Release(DDI(I1,...,In)) => forall i: IdentityAdmissible(surface_i, source_id_i, source_version_i)`

The scientific claim is not that CareGuard can abstain. It is that **mandatory identity admissibility may reduce false-clear and wrong-identity completion, and the paper quantifies the resulting automatic-coverage cost**.

## Required evaluation implications

1. RxMap must be attempted as the nearest-neighbor normalization comparator; if not reproducible, record `NOT_RUN` with evidence.
2. Report false-clear risk versus automatic coverage, not only normalization F1.
3. Add an oracle-identity arm using the exact same DDI engine to separate identity errors from knowledge-base misses.
4. Decompose failures into identity-resolution, DDI-knowledge, release-policy, source/mapping, and transport classes.
5. Keep DDInter/DailyMed as positive references unless an explicit independent negative gold set is obtained.
6. Do not infer patient safety or clinical effectiveness from software results.

## Primary sources checked

- RxMap: JAMIA Open 9(3), 2026, doi:10.1093/jamiaopen/ooag085.
- Newman-Griffis et al.: JAMIA 28(3), 2021, doi:10.1093/jamia/ocaa269.
- Swaminathan et al.: JAMIA 31(1), 2024, doi:10.1093/jamia/ocad182.
- Gallifant et al.: Findings of EMNLP 2024, doi:10.18653/v1/2024.findings-emnlp.726.
- Chen et al.: Computer Methods and Programs in Biomedicine 243, 2024, doi:10.1016/j.cmpb.2023.107869.
- DDInter 2.0: Nucleic Acids Research 53(D1), 2025, doi:10.1093/nar/gkae726.
- Gibson et al.: British Journal of Pharmacology 183(16), 2026, doi:10.1111/bph.70515.
- Holbrook et al.: JAMIA 32(10), 2025, doi:10.1093/jamia/ocaf139.

## 2026 hardening note

The closest new threat to overclaiming is CrossDDI: it already makes interaction verification evidence-grounded. Therefore the manuscript must use **identity-admissibility** language, not generic ``evidence-gated DDI'' language. RxMap and the 2026 MCN survey similarly make clear that normalization, LLM parsing, candidate ranking, confidence/review, and terminology mapping are established.
