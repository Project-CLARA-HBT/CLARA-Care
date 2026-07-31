# LifeMap AI use-case evidence packages v1

Evidence state: repository/offline engineering evidence only. All listed flags
remain default off except the separately governed shadow scorer. No package
recommends promotion.

This document covers the LifeMap capabilities added after the original ML
inventory. The existing `lifemap.ask.v1` detailed package remains authoritative
for the Ask endpoint; its inventory component ID is
`lifemap-ask-grounded-v1`.

## Shared dataset boundary

Current repository evaluation uses `lifemap-ai-golden-v1`, the capture fixture,
and focused synthetic unit/property cases. Inputs are hand-authored Vietnamese
and English scenarios without production profiles or identity mappings.
Checksums are computed by their harnesses. No learned component is fitted on
these cases.

These datasets contain no real population, site, device, clinical outcome, or
human-workflow sample. They cannot support effectiveness, calibration,
subgroup, fairness, prevalence, burden, usability, or outcome claims. Synthetic
cases remain separate from real-world estimates and must not be reused as a
nominally independent held-out set after model/prompt tuning.

## `lifemap-hierarchical-summary-v1`

### Use case, model card, and workflow

- Owner/risk: LifeMap; high.
- Intended output: read-only event/day/episode/week/visit summaries assembled
  from structured current claims with source citations.
- Artifact: deterministic
  `clara_api.lifemap.intelligence.hierarchical_summary`; no trained model.
- Human boundary: users inspect cited child sources; summaries never mutate
  truth or silently resolve conflict.
- Forbidden: uncited medical claims, diagnosis, hidden disputed evidence.
- Flag/fallback: `LIFEMAP_AI_SUMMARIES_ENABLED`; ordinary canonical timeline
  and source readers.

### Evaluation, hazards, and rollback

Synthetic tests cover source dependencies, correction invalidation, hierarchy,
missingness and summary faithfulness. Real bilingual comprehension, subgroup,
production latency, correction-lag, and workflow studies are absent.
Principal hazards are unsupported compression, lost temporal context, and
hidden conflict; exact citations, stale propagation, explicit conflict fields,
and abstention contain them. Rollback disables the flag; summaries are
read-only and require no canonical-data migration. TRIPOD+AI is not applicable
because no outcome is predicted.

## `lifemap-multimodal-draft-v1`

### Use case, datasheet, model card, and workflow

- Owner/risk: LifeMap Capture; high.
- Intended output: typed, source-spanned review drafts from authorized OCR,
  ASR, layout, DeepSeek, or optional VLM candidate adapters.
- Input subset: synthetic labels/documents and bounded artifact bytes; no
  production artifact is included in repository evaluation.
- Artifact: provider-neutral validated adapter boundary plus the current
  grounded OCR baseline. Provider models remain separately inventoried.
- Human boundary: every result is a draft; the owner must review and explicitly
  confirm. Diagnostic image interpretation is unsupported.
- Flag/fallback: `LIFEMAP_CAPTURE_ENABLED`; manual entry or no candidate.

### Evaluation, hazards, and rollback

Tests cover checksums, profile lineage, exact text/page/timestamp locators,
finite confidence, units, missing fields, injection findings, degraded output,
emergency bypass, and API revalidation. Approved field-level clinical review,
document/device slices, OCR-provider comparison, confirmation burden, and
wrong-medication thresholds are absent. Hazards include wrong entity/strength,
cross-profile artifact use, injected instructions, and automation bias; the
draft-only boundary, exact spans, fail-closed lineage, and explicit missingness
contain them. Rollback disables Capture and preserves manual entry.

## `lifemap-entity-resolution-v1`

### Use case, datasheet, model card, and workflow

- Owner/risk: LifeMap Data Quality; high.
- Intended output: ranked terminology mapping proposals with method,
  confidence, ambiguity, and mapping revision.
- Input subset: synthetic Vietnamese spelling/alias candidates and approved
  terminology aliases. Licensing approval is still required for production
  terminology snapshots.
- Artifact: deterministic normalization, exact/alias lookup, retrieval and
  graph constraints with an optional governed reranker.
- Human boundary: the owner accepts or declines a server-owned proposal;
  unknown mappings retain the original text.
- Flag/fallback: `LIFEMAP_AI_ENTITY_RESOLUTION_ENABLED`; unmapped exact source.

### Evaluation, hazards, and rollback

Synthetic tests cover normalization, ambiguity, top-k behavior, profile
scoping and rejection of client-invented codes. Real terminology coverage,
wrong-medication cost, subgroup/language slices, calibration and independent
pharmacist review are absent. Principal hazards are false identity and
terminology-version drift; server recomputation, ambiguity, revisions, and
explicit confirmation contain them. Rollback disables proposals and retains
original values. TRIPOD+AI is not applicable.

## `lifemap-review-findings-v1`

### Use case, datasheet, model card, and workflow

- Owner/risk: LifeMap Data Quality; high.
- Intended output: deterministic duplicate, contradiction and missingness
  findings, plus optional registry-bound `possible_duplicate` or
  `possible_conflict` pairs over exactly two authorized current revisions.
- Input subset: synthetic current/disputed revision pairs with labeled
  relationships; no production corrections are training data.
- Artifact: deterministic rules with an optional governed V4 Flash candidate
  route. The route may return only a closed revision-ID pair and relation; it
  is not a truth classifier.
- Human boundary: findings remain reviewable and reversible; no fact is
  deleted or silently selected.
- Flag/fallback: `LIFEMAP_AI_REVIEW_FINDINGS_ENABLED` and independent
  `LIFEMAP_REVIEW_MODEL_PROPOSALS_ENABLED`; rule-only result or no finding.

### Evaluation, hazards, and rollback

Tests cover bounded proposal types, exact lineage, duplicate/contradiction
rules, rejection of cross-field or unauthorized model pairs, and human
resolution. Approved contradiction recall, false-conflict burden, bilingual
comprehension, source/device slices and independent clinical review are absent.
Hazards are missed conflict, false conflict, and hidden truth replacement;
append-only resolution and visible dispute state contain them. Rollback disables
the model-pair switch without changing canonical facts.

## `lifemap-question-ranker-shadow-v1`

### Use case, datasheet, model card, and workflow

- Owner/risk: LifeMap Personalization; high.
- Intended output: shadow scores only over the deterministic eligible question
  set.
- Input subset: synthetic bounded eligibility, burden and interaction features.
  Production corrections/interactions are not implicit training data.
- Artifact: deterministic scorer or separately signed supervised ranker. No
  signed learned artifact is approved in this package.
- Human boundary: the scorer cannot generate text, change eligibility, bypass
  burden ceilings, or affect emergency routing.
- Flag/fallback: `LIFEMAP_AI_QUESTION_RANKER_SHADOW_ENABLED`; deterministic
  ordering.

### Evaluation, hazards, and rollback

Contract tests cover action-set containment, propensity logging, deterministic
fallback, shadow comparison and bounded pilot protocol. Ranking utility,
off-policy uncertainty, burden/safety, fairness, real response propensity, and
human usefulness evidence are absent. Hazards are notification pressure,
feedback loops and subgroup burden; deterministic eligibility and pressure
ceilings contain them. Rollback removes the shadow score. A future predictive
ranker requires a target-specific TRIPOD+AI-aligned report where applicable.

## `lifemap-evidence-matching-v1`

### Use case, datasheet, model card, and workflow

- Owner/risk: Living Evidence; high.
- Intended output: source-spanned PICO, guideline and trial-criterion
  candidates, followed by deterministic match/mismatch/unknown comparison
  against confirmed authorized facts.
- Input subset: synthetic evidence excerpts and typed confirmed facts; no
  production profile or proprietary corpus is included.
- Artifact: bounded extraction boundary plus versioned applicability rules; no
  model may infer a missing private eligibility fact.
- Human boundary: output says possible match for review, never diagnosis,
  treatment advice, enrollment eligibility, or an automatic notification.
- Flag/fallback: `LIFEMAP_AI_EVIDENCE_MATCHING_ENABLED`; `not_assessed` plus
  ordinary cited evidence.

### Evaluation, hazards, and rollback

Tests cover source spans, typed criteria, match/mismatch/unknown separation,
contradiction/supersession, citation validation and abstention. Approved
eligibility precision, unknown calibration, citation-quality study, retrieval
shift, subgroup results, and user/clinician comprehension are absent. Hazards
include false eligibility, missing-fact inference and stale guidance; possible-
match wording, confirmed-fact rules, retrieval dates and supersession contain
them. Rollback disables matching and retains the evidence record.

## Cross-use-case decision

All packages lack real subgroup and human-AI workflow results, independent
reviewer signatures, approved monitoring thresholds, and exercised rollback
evidence. Predictive reporting is not applicable to deterministic
retrieval/extraction features; it becomes mandatory if a separately approved
target is introduced. DECIDE-AI-style early evaluation is required before any
capability influences live health decisions, and applicable prospective trials
must use SPIRIT-AI/CONSORT-AI reporting.

Decision: retain default-off/research or shadow state. Empty approval evidence
is a release blocker, not an invitation to infer approval.
