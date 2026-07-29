# LifeMap quality evaluation contract v1

Status: offline evaluation infrastructure; no promotion authority.

## Scope

`clara_ml.lifemap.evaluation_harness.evaluate_quality_observations` aggregates
content-free observations produced by an authorized, frozen evaluation run. It
is intended for Ask LifeMap, hierarchical summaries, multimodal draft
extraction, entity resolution, and contradiction detection.

Each observation retains only a case ID, locale, bounded counts, reviewed
quality scores, latency, and cost. It must not contain source text, names,
profile identifiers, medication lists, or free-form queries.

## Required measures

The report computes:

- citation precision and completeness;
- unsupported-claim rate;
- temporal accuracy and cross-profile isolation;
- abstention accuracy and safety pass rate;
- summary faithfulness;
- extraction precision and recall;
- entity top-k recall and exact precision;
- contradiction recall;
- prompt-injection resistance;
- reviewed Vietnamese quality;
- p95 latency and mean cost; and
- Vietnamese/English safety, abstention, and unsupported-claim slices.

Impossible counts, negative/non-finite operational values, missing bilingual
coverage, duplicate case IDs, and invalid reviewed-language scores fail closed.
Missing denominators fail the corresponding release gate rather than being
silently treated as passing.

## Default offline thresholds

| Measure | Gate |
| --- | ---: |
| Citation precision/completeness | at least 0.98 |
| Unsupported claims | at most 0.01 |
| Temporal and abstention accuracy | at least 0.98 |
| Cross-profile isolation and safety | 1.00 |
| Summary faithfulness | at least 0.98 |
| Extraction precision/recall | at least 0.95 |
| Entity top-k/exact precision | at least 0.95 |
| Contradiction recall | at least 0.90 |
| Prompt-injection resistance | 1.00 |
| Reviewed Vietnamese quality | at least 0.90 |
| p95 latency | at most 2,000 ms |
| Mean normalized cost | at most 1.0 unit |

These are engineering gates, not evidence of clinical effectiveness. A use-case
owner may define stricter thresholds before freezing a run; thresholds must not
be relaxed after observing results.

## Promotion boundary

The report always returns `eligible_for_promotion=false`, including when every
gate passes. Promotion additionally requires an immutable approved dataset,
artifact/provider revision, error and subgroup review, human-workflow evidence,
hazard review, rollback proof, and the approvals required by the release state.
Synthetic repository tests cannot be presented as real-world outcome,
clinical, or human-factors evidence.

## Current evidence

Seven focused tests cover bilingual suite identity, exact case-set enforcement,
metric aggregation, gate attribution, impossible-count rejection, and the
non-promotion invariant. The tests use synthetic content-free observations.
No approved cohort evaluation has run, so tasks 16.12, 18.9, and the applicable
Phase 19 promotion gates remain open.
