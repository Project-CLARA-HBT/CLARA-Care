# LifeMap Ask v1 — governed evidence package

Evidence state: repository/offline only. Promotion recommendation: retain the
deterministic fallback; do not promote a generative challenger.

## Use case and human-AI workflow

- Stable use-case ID: `lifemap.ask.v1`
- Intended users: an authenticated profile owner using LifeMap for self-care
  organization.
- Intended output: a read-only answer assembled from exact authorized current
  revisions, with evidence rows and revision citations.
- Human role: the user reads source attribution and unresolved truth states;
  the system never confirms/corrects a fact or changes a task.
- Forbidden uses: diagnosis, prescribing, personal-dose selection, emergency
  replacement, eligibility decisions, or autonomous truth resolution.
- Risk class: health-adjacent informational support with medical hard guards.
- Current champion/fallback: `deterministic-grounded-fallback@1`.
- Release flag: `LIFEMAP_ASK_AI_ENABLED`, default off.

## Dataset datasheet

- Dataset ID: `lifemap-ai-golden-v1`.
- Snapshot: `services/ml/tests/fixtures/lifemap_ai_golden_v1.json`; immutable
  identity is the file SHA-256 computed by the harness.
- Purpose: contract regression for longitudinal, temporal, multimodal,
  correction, contradiction, missingness, wearable-shift, OOD, and adaptive
  containment behavior.
- Population: synthetic Vietnamese and English cases; no production profiles,
  conversations, names, queries, or health records.
- Labels: hand-authored expected safety/grounding contracts.
- Split: all cases are labeled synthetic and held out from model fitting; no
  trained model is fitted by this package.
- Missingness/subgroups: only locale and scenario dimension are represented.
  Demographic, device, site, outcome, and real workflow slices are absent.
- Consent/deletion lineage: not applicable to synthetic records. This fixture
  must never be joined with production identity mappings.
- Prohibited use: clinical effectiveness, prevalence, outcome, subgroup
  fairness, or human-factors claims.
- Known limitation: the fixture validates boundaries, not answer usefulness in
  real longitudinal records.

## Artifact/model card

- Artifact ID: `deterministic-grounded-fallback@1`; it is deterministic code,
  not a trained neural or statistical model.
- Source: `services/api/src/clara_api/lifemap/intelligence.py` and the
  `/lifemap/v2/ask` governed endpoint.
- Inputs: a pre-authorized, profile-partitioned current-revision evidence set
  compiled after purpose, consent, episode, event-type, and time filters.
- Outputs: typed intent, answer, claims, evidence, disclosure, verification,
  private context-manifest ID, and inference-manifest ID.
- Fallback/abstention: absence, unresolved conflict, stale evidence, illegal
  intent, invalid citation, failed entailment, or missing medication FIDES
  evidence blocks or abstains.
- Online learning: prohibited.
- Provider dependency: none for the current deterministic release.
- Rollback: disable `LIFEMAP_ASK_AI_ENABLED`; no canonical record requires
  migration or deletion because the feature is read-only.

## Evaluation and error analysis

Repository evidence currently covers exact citation existence, profile
containment, temporal ordering, contradiction visibility, legal guards,
medication FIDES applicability, abstention, and bilingual scenario contracts.
The broader quality contract is defined in
`lifemap-quality-evaluation-contract-v1.md`.

Known error classes and containment:

| Error | Containment |
| --- | --- |
| Missing/out-of-table citation | Fail closed |
| Claim not entailed by cited revision | Fail closed |
| Hidden disputed/conflicting source | Fail closed |
| Medication/dose claim without FIDES pass | Fail closed |
| No authorized evidence | Abstain |
| Stale/corrected dependency | Projection invalidation and re-query |
| Unsupported diagnosis/prescribing language | Legal hard guard |
| Provider/model outage | Deterministic path has no provider dependency |

No approved real-world error analysis, subgroup study, Vietnamese usability
review, latency/cost production distribution, or human-AI team comparison has
run. Synthetic pass rates must not be reported as real-world performance.

## Hazard analysis

| Hazard | Existing control | Residual evidence needed |
| --- | --- | --- |
| Cross-profile disclosure | Scope before retrieval; exact revision checks | Independent penetration and cohort test |
| Unsupported medical statement | Entailment/citation/FIDES/legal release gates | Frozen adversarial evaluation |
| Old information shown as current | Current-revision retrieval; staleness lineage | Production correction-lag monitoring |
| Conflict silently resolved | Explicit disputed/conflicting fields | Bilingual comprehension study |
| Automation bias | Read-only disclosure and visible sources | Human-factors/DECIDE-AI-style review if decision influence grows |
| Dependency regression | Immutable manifests and rollback flag | Staged rollback drill |

## Reporting framework applicability

TRIPOD+AI is not applicable to the current deterministic retrieval/summary
fallback because it does not estimate an individual outcome or risk. If a
predictive target is separately approved, it requires a target-specific
TRIPOD+AI-aligned report. DECIDE-AI-style early clinical evaluation is required
before any version is allowed to influence live health decisions; prospective
interventional study protocols must use applicable SPIRIT-AI/CONSORT-AI
extensions.

## Decision and approvals

Current decision: retain deterministic fallback, default off. No neural/LLM
challenger, shadow cohort, pilot, or champion transition is approved. Required
independent clinical, privacy, security, product, and model-risk reviewers and
their dates are intentionally blank until real authorized review occurs.
