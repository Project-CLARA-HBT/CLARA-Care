# AI Capability Analysis — CLARA LifeMap

Status: proposed portfolio and decision record
Date: 2026-07-28
Companion documents: [requirements.md](requirements.md),
[design.md](design.md), [tasks.md](tasks.md)

## 1. Executive conclusion

LifeMap should become substantially more AI-powered, but the AI should improve
memory, understanding, data quality, and user preparation before it attempts
clinical prediction.

The strongest production opportunities use capabilities CLARA already has:

1. a grounded **Ask My LifeMap** assistant over the user's authorized timeline;
2. hierarchical, source-cited timeline and weekly summaries;
3. multimodal extraction from text, voice, labels, and visit documents into
   reviewable drafts;
4. embedding/graph-assisted medication and health-entity resolution;
5. contradiction, duplicate, and missing-information detection;
6. personalized explanation of deterministic baseline changes;
7. evidence-to-profile matching with explicit `not_assessed` behavior; and
8. low-burden, safety-constrained question selection.

The best initial time-series model is not automatically a Transformer. Current
evidence shows that simple engineered variability features can match or exceed
generic LLM/time-series foundation-model embeddings on wearable health
prediction tasks. LifeMap therefore needs a champion/challenger bake-off:
deterministic robust statistics first, classical ML second, neural sequence
models only when they deliver material, calibrated improvement on CLARA's target
population.

Disease prediction, deterioration scores, treatment-effect estimation, digital
twins, autonomous agents, and continuous/federated learning are research
programs. They must not be shipped under a wellness label without an intended-use
and prospective-evaluation decision.

## 2. Existing CLARA capability inventory

### Already implemented or substantially present

- DeepSeek LLM orchestration with retries, timeouts, circuit-breaking seams, and
  deterministic fallback.
- Hybrid RAG with lexical/vector retrieval, embeddings, optional reranking,
  GraphRAG, query planning, provenance, and evaluation harnesses.
- FIDES verification with blocking of failed critical medication claims.
- Typed medical-answer and disclosure envelopes.
- OCR sidecar for medication labels and Whisper-based ASR for Scribe.
- Medication entity-normalization seams and Vietnamese drug dictionaries.
- Connected-health canonical ingestion and deterministic daily projection.
- Rule-based next-best-question engine with optional LLM wording.
- Council LLM assessments in governed shadow mode.
- No-PII flow telemetry and admin observability infrastructure.

### Important naming correction

`services/ml/src/clara_ml/agents/council_neural.py` implements a small feed-
forward calculation with hand-authored constant weights. It does not load a
trained artifact and has no training dataset, training manifest, validation set,
calibration report, or external validation. Its current shadow containment is
good, but the implementation must be described as a **fixed-weight heuristic
scorer**, not as validated neural ML.

Before it can be called a trained neural model, the project must have:

- a defined target and clinically meaningful label;
- a governed and representative dataset;
- train/validation/test separation at person/site/time level;
- reproducible training code and immutable run manifest;
- comparison with rule, logistic-regression, and tree baselines;
- calibration, subgroup, missingness, shift, and error analysis;
- shadow and prospective evaluation; and
- model-card and release approval.

## 3. Research basis

This portfolio applies:

- [WHO ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240029200):
  autonomy, safety, transparency, accountability, inclusiveness, and sustainable
  responsive AI.
- [FDA/Health Canada/MHRA Good Machine Learning Practice](https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles):
  representative data, independent test sets, human-AI team performance,
  clinically relevant evaluation, clear user information, and post-deployment
  monitoring.
- [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) for transparent
  clinical prediction-model development and evaluation.
- [DECIDE-AI](https://www.nature.com/articles/s41591-022-01772-9) for early,
  live human-AI evaluation.
- [CONSORT-AI](https://www.nature.com/articles/s41591-020-1034-x) if a
  prospective trial evaluates an AI intervention.
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) for
  lifecycle governance, measurement, and risk management.
- [Model Cards](https://doi.org/10.1145/3287560.3287596) and
  [Datasheets for Datasets](https://arxiv.org/abs/1803.09010) for transparent
  artifact documentation.
- Research evaluating modern wearable representations, which found
  [simple entropy/variability features often matched or exceeded generic LLM and
  time-series foundation-model embeddings](https://pubmed.ncbi.nlm.nih.gov/42317862/).
- Research on [conformal prediction in clinical applications](https://pmc.ncbi.nlm.nih.gov/articles/PMC9309105/)
  as one possible uncertainty layer, subject to its assumptions and validation.

These sources support disciplined comparison and evaluation; they do not prove
that a specific LifeMap model is effective.

## 4. Decision framework

Every candidate AI feature is scored on:

| Dimension | Question |
| --- | --- |
| User value | Does it reduce work, improve understanding, or prepare a safer next step? |
| Decision impact | Can it change a health action, or only organize/explain? |
| Data readiness | Does CLARA possess representative, consented data and reliable labels? |
| Groundability | Can every output be tied to exact LifeMap or evidence sources? |
| Reversibility | Can the output be corrected, ignored, or rolled back without harm? |
| Uncertainty | Can the system detect insufficiency, distribution shift, and abstain? |
| Evaluation | Is there a measurable offline and prospective success criterion? |
| Privacy | Can it work with minimum necessary data and purpose consent? |
| Operational fit | Can it meet latency, cost, resilience, and model-hosting constraints? |
| Regulatory risk | Does the intended output approach diagnosis, prognosis, or treatment? |

Release classes:

- **P — Production candidate**: organizational/explanatory, grounded, reversible,
  and testable with current capabilities.
- **S — Shadow/pilot**: potentially useful but needs learned-model evidence,
  calibration, or human-factors validation.
- **R — Research only**: clinical prediction, causal/treatment impact, adaptive
  learning, or insufficient data/labels.
- **X — Prohibited under current intended use**: diagnosis, prescribing,
  personal dosing, autonomous emergency downgrading, or autonomous medical action.

## 5. Prioritized feature portfolio

| Feature | Main technique | Class | Why |
| --- | --- | --- | --- |
| Ask My LifeMap | temporal RAG + LLM | P | High user value; answers can cite owned facts and abstain |
| Timeline/weekly digest | hierarchical summarization + templates | P | Reduces cognitive load; reversible derived view |
| Multimodal capture | OCR/ASR/VLM + typed extraction | P | Removes manual entry; drafts prevent silent truth |
| Health entity linking | embeddings + rules + knowledge graph | P | Improves duplicates, medicines, terminology, FHIR export |
| Contradiction/missingness assistant | NLI + rules + LLM explanation | P/S | Finds review needs; must never choose truth automatically |
| Personalized evidence explanation | profile-aware RAG + rules | P/S | Useful when applicability is explicit and citations validate |
| Baseline explanation | robust stats + constrained LLM verbalization | P | Model explains a deterministic result, not invents one |
| Episode clustering suggestion | embeddings/clustering | S | Can organize history, but user must confirm grouping |
| Personal anomaly challenger | isolation/tree/autoencoder/sequence model | S | Requires data sufficiency, calibration, and false-alert control |
| Short-horizon wellness forecast | GBM/TFT/TCN/TSFM bake-off | S/R | Useful only for non-clinical signals with uncertainty and abstention |
| Adaptive question ranking | learning-to-rank/contextual bandit | S/R | Needs counterfactual evaluation; safety eligibility remains deterministic |
| Engagement/friction detection | survival/classification model | S | Can adjust reminders, but must not manipulate or shame |
| Trial/guideline matching | PICO extraction + retrieval + rules | S | Eligibility is nuanced; requires human confirmation |
| Caregiver digest | grounded summarization + consent filter | P | Useful if grant filtering happens before model context |
| Synthetic test generation | LLM + validators | P for testing | Improves coverage; never becomes clinical evidence |
| Local privacy classifier | compact transformer/rules | P/S | Can redact/routes data before cloud calls |
| Disease/deterioration prediction | supervised deep model | R | Clinical intended-use and representative labels absent |
| Individual treatment-effect model | causal ML | R | Observational LifeMap data cannot justify treatment advice |
| Digital twin | multimodal generative/causal model | R | No validated physiology or intervention model |
| Federated/continuous learning | FL + DP | R | Complexity, poisoning, non-IID, consent, and device cost unresolved |
| Autonomous care agent | agentic LLM | X | Cannot accept tasks, change treatment, or act without the user |

## 6. Feature specifications

### AI-1 — Ask My LifeMap

User value: ask questions such as “When did this start?”, “What changed before my
appointment?”, or “Which information is still unconfirmed?”

Pipeline:

1. policy compiler creates an authorized profile/event/source filter;
2. intent router separates timeline lookup, comparison, explanation, evidence,
   and prohibited clinical intent;
3. hybrid temporal retrieval selects exact event revisions, tasks, decisions,
   documents, and source spans;
4. a deterministic evidence table is assembled;
5. the LLM generates a typed answer whose claims cite evidence-table IDs;
6. claim-evidence verification and safety guards run;
7. unsupported claims are removed or the answer abstains.

Required output:

```text
answer
timeline_claims[{text, evidence_ids, effective_time}]
unknowns[]
conflicts[]
stale_inputs[]
suggested_user_actions[]   # view/correct/prepare-question only
model_disclosure
```

The assistant must answer only from the selected ProfileScope plus explicitly
authorized external evidence. It must not retrieve a different family profile by
semantic similarity.

Success measures:

- claim-level citation precision and completeness;
- temporal-order accuracy;
- profile isolation;
- contradiction/unknown recall;
- abstention appropriateness;
- user comprehension;
- latency and cost.

### AI-2 — Hierarchical timeline intelligence

Raw events are compressed into:

- event-level display summaries;
- daily clusters;
- episode summaries;
- weekly/monthly digests; and
- visit-preparation summaries.

Each summary stores input revision IDs and is invalidated by corrections.
Summaries cannot introduce diagnoses or merge contradictory facts. A deterministic
template is the fallback. Generated language must distinguish “you recorded,”
“a device measured,” “a document says,” and “CLARA inferred.”

### AI-3 — Multimodal capture intelligence

Model routing:

- native text -> medical entity extraction;
- audio -> ASR, timestamped segments, then extraction;
- medicine label -> OCR plus optional vision-language candidate extraction;
- visit document -> OCR/layout model plus instruction candidates;
- chart/image screenshot -> layout/OCR only unless an approved image model and
  use case exist.

Every modality produces the same typed `CaptureCandidate` contract. The system
must preserve modality-specific provenance, confidence, and source span.
Diagnostic interpretation of medical images is outside scope.

### AI-4 — Semantic normalization and knowledge graph

Use an ensemble:

1. exact normalized dictionary/identifier match;
2. Vietnamese alias and spelling normalization;
3. embedding retrieval for candidate generation;
4. graph constraints for ingredient/product/form/route relationships;
5. optional cross-encoder reranking; and
6. calibrated accept/suggest/ambiguous thresholds.

The engine outputs candidates; a high threshold may auto-code low-risk
terminology only if the original text is preserved and the mapping is easily
reversible. Medication identity and other critical mappings require confirmation
unless validated policy explicitly allows the source.

### AI-5 — Contradiction, duplicate, and missingness assistant

Signals:

- same fact with incompatible values/time overlap;
- medication marked both active and stopped;
- allergy/medication conflict;
- repeated document or connector record;
- event that contradicts a confirmed revision;
- missing unit, source, effective time, strength, route, or critical answer.

Rules provide the safety floor. NLI/LLM may propose contradiction pairs and a
plain-language explanation. It cannot select the winner or invalidate a fact.

### AI-6 — Personal pattern discovery

The production champion remains the deterministic robust baseline. Challengers:

- robust z/MAD and change-point methods;
- isolation forest or one-class methods over engineered features;
- gradient-boosted models for sufficiency/quality-aware signal detection;
- autoencoder, TCN, Transformer, or time-series foundation-model embeddings when
  enough data exist.

Required comparisons:

- simple baseline versus every complex model;
- within-person and out-of-person/site/time splits;
- false alerts per user-week, lead time, stability, subgroup performance;
- calibration/coverage and OOD rejection;
- missingness and device-change robustness;
- cost, latency, and explainability.

Output remains “pattern change,” not “condition detected.”

### AI-7 — Pattern relationship explorer

LifeMap may surface descriptive lagged relationships such as:

“On recorded days with later sleep, your next-day step count was usually lower.”

Requirements:

- minimum paired observations and coverage;
- correction for repeated comparisons or a discovery/confirmation split;
- effect size and uncertainty, not p-value alone;
- visible confounders and data gaps;
- no causal language;
- no medication or treatment recommendation.

LLM use is limited to explaining deterministic statistical results.

### AI-8 — Short-horizon wellness forecasting

Initial permitted targets are low-risk organizational signals, for example:

- likelihood that a user-set activity routine is missed;
- expected range for a non-clinical wearable metric; or
- likelihood that an accepted task remains incomplete.

Prohibited without a separate program:

- disease onset;
- hospitalization/deterioration;
- emergency downgrading;
- medication response;
- pregnancy/pediatric risk;
- treatment outcomes.

Every forecast needs horizon, interval/set, data sufficiency, calibration,
model/version, and abstention/OOD status. Forecasts begin shadow-only.

### AI-9 — Adaptive next-best question

Deterministic policy controls:

- which fields may be asked;
- emergency behavior;
- consent and sensitivity;
- burden/cooldown;
- whether an answer may change an allowed output.

A learned ranker may only order already-eligible questions. Development order:

1. supervised learning-to-rank from clinician/user utility labels;
2. offline policy evaluation;
3. shadow ranking;
4. randomized micro-pilot with safety review;
5. contextual bandit only if sample size, consent, exploration limits, and
   stopping rules are adequate.

Rewards must combine information gain, user-reported usefulness, burden,
dismissal, and safety; click/answer rate alone is not an acceptable objective.

### AI-10 — Personalized evidence intelligence

Capabilities:

- extract PICO/eligibility concepts from a confirmed user question;
- retrieve guidelines, reviews, and studies separately;
- detect contradictions and supersession;
- compare explicit eligibility rules with confirmed facts;
- explain matches, mismatches, and unknowns;
- generate clinician-discussion questions.

The model must not infer missing sensitive facts to improve a match. Trial
matching stays “possible match for review,” not eligibility confirmation.

### AI-11 — Engagement and friction support

The model may detect repeated snoozes, missed tasks, notification overload, or
complex workflows and offer:

- fewer reminders;
- a different time;
- a smaller user-defined step;
- pausing the feature; or
- asking for help.

It must not label non-adherence, manipulate emotion, optimize addiction, hide
clinician instructions, or escalate message pressure based on vulnerability.

### AI-12 — Consent-safe caregiver digest

The API applies grant and purpose filters before the model sees context. The
digest cites exact shared facts, identifies stale/pending content, and cannot
include withheld categories. Revocation invalidates the digest and any cache.

### AI-13 — Synthetic evaluation and red-team generation

LLMs may produce:

- Vietnamese paraphrases and typo/noise variants;
- emergency/negation/temporal counterexamples;
- prompt-injection documents;
- OCR/ASR error simulations;
- longitudinal correction and contradiction scenarios; and
- accessibility/readability variants.

Synthetic cases are tagged as synthetic, reviewed, deduplicated from evaluation
sets, and never represented as clinical evidence or production user data.

### AI-14 — Privacy-preserving/local intelligence

Near-term:

- deterministic/client-side detection of obvious identifiers;
- on-device document preprocessing and optional redaction preview;
- local embeddings only if model/license/device cost and leakage tests pass.

Research:

- federated or split learning;
- secure aggregation;
- differential privacy;
- personalized local fine-tuning.

Federated learning is not privacy by default. Model updates can leak information;
non-IID data, poisoning, consent withdrawal, deletion, energy cost, and secure
aggregation must be resolved.

## 7. ML lifecycle requirements

### Dataset contract

Each dataset version records:

- purpose and allowed use;
- lawful basis/consent and withdrawal handling;
- source population, sites, devices, time range, languages;
- inclusion/exclusion and label definition;
- person/site/time split keys and leakage analysis;
- missingness, duplicates, class balance, subgroup distribution;
- annotator instructions/agreement and adjudication;
- known bias/limitations;
- transformations and checksums;
- retention and deletion lineage.

### Training run contract

Each run records:

- source commit and environment/container digest;
- dataset and feature-schema versions;
- model architecture and initialization/pretraining source;
- hyperparameters and random seeds;
- train/validation/test split identities;
- metrics, confidence intervals, calibration, and slices;
- artifact checksum/signature;
- intended use, exclusions, and comparison baseline.

### Promotion contract

```text
research -> offline candidate -> red-team -> shadow -> limited pilot
         -> released challenger -> champion
```

No model skips a stage. Promotion requires the relevant owners and a predefined
rollback. Online self-updating models are not permitted; a learned update is a
new immutable version.

### Inference contract

Each inference records no-PII operational metadata and an authorized private
manifest reference:

```text
model_version, feature_schema_version, input_watermark,
purpose, output, uncertainty, abstention_reason,
ood_state, latency, fallback, policy_version
```

The private manifest links exact input revisions but is never emitted to
telemetry.

## 8. Model evaluation

### Common metrics

- discrimination/ranking where relevant;
- calibration slope/intercept, Brier score, ECE with caveats;
- sensitivity/specificity/PPV/NPV at declared thresholds;
- coverage and error for conformal outputs where assumptions are justified;
- abstention utility and OOD detection;
- subgroup and worst-slice results;
- missingness/device/language/time-shift robustness;
- human-AI team outcome;
- latency, cost, availability, and fallback rate.

### LLM/RAG metrics

- claim-level citation precision/recall;
- evidence entailment and contradiction;
- temporal grounding;
- unsupported-claim and fabricated-citation rate;
- instruction hierarchy/prompt-injection resistance;
- safety-policy adherence;
- uncertainty/abstention appropriateness;
- Vietnamese readability and clinical-review agreement.

### Time-series metrics

- user-level split with no window leakage;
- event-based sensitivity and false alerts/user-week;
- lead time and alert duration;
- calibration across horizon;
- device/source shift;
- seasonal and missing-data robustness;
- comparison with robust statistical and classical-ML baselines.

Average performance cannot compensate for a zero-tolerance safety or
cross-profile failure.

## 9. Data readiness gates

Before training any supervised personal model:

1. the target label must correspond to a permitted intended use;
2. sample-size and event-count analysis must be approved;
3. labels must have defined provenance and acceptable agreement;
4. train/test separation must prevent person, household, source-document, device,
   and future-time leakage;
5. deletion/consent withdrawal must propagate to derived training datasets;
6. every candidate must beat a simple baseline materially and on worst slices;
7. external or temporal validation must pass before user-facing release; and
8. prospective human-AI evaluation is required if outputs influence health
   decisions.

If these gates are not met, implement the data/evaluation pipeline and run
research or shadow inference only.

## 10. Recommended delivery order

### Wave A — Grounded intelligence

- Ask My LifeMap;
- hierarchical summaries/digests;
- multimodal draft capture;
- entity resolution;
- contradiction/missingness assistant;
- constrained baseline explanations;
- synthetic safety-test generation.

These exploit existing CLARA infrastructure and remain reversible.

### Wave B — Personalized ML in shadow

- episode-clustering suggestions;
- anomaly challengers;
- relationship explorer;
- question ranker;
- friction model;
- evidence/trial matching.

These need labels, calibration, and user studies.

### Wave C — Prospective/research program

- wellness forecasting;
- clinical risk models;
- causal treatment-effect modeling;
- time-series foundation models;
- federated learning;
- digital twins.

No Wave C feature is implied by completing the production convergence phases.

## 11. Stop and prohibition rules

Immediately disable or prevent promotion if:

- any output accesses the wrong ProfileScope;
- the LLM cites a nonexistent or unauthorized fact;
- a model creates or confirms truth directly;
- a model downgrades an emergency or bypasses FIDES;
- OOD/insufficient inputs still receive confident output;
- correction or consent revocation does not invalidate derived output;
- subgroup safety performance violates its floor;
- drift exceeds a predefined boundary without safe fallback;
- an adaptive model changes outside the approved release process; or
- the product begins presenting research output as diagnosis, prognosis, or
  treatment advice.
