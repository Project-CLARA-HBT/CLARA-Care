# CLARA Chat and RAG evidence map

**Version:** 2026-07-29

**Status:** Architecture and evaluation input; not clinical validation
**Scope:** CLARA Chat, retrieval-augmented generation (RAG), citations,
Vietnamese evaluation, model governance, and prospective rollout

## 1. Purpose and interpretation

This document translates current primary research and authoritative governance
guidance into implementable requirements for CLARA. It deliberately separates:

- **Published evidence:** a result or recommendation supported by a cited
  primary source.
- **CLARA engineering inference:** a product or technical decision derived from
  that evidence and CLARA's safety requirements.
- **Proposed CLARA threshold:** an initial release criterion to be reviewed and
  approved by clinical, safety, privacy, and product owners. These numbers are
  not universal constants established by the literature.

Benchmark performance is not evidence of clinical benefit. Patient-facing
benefit and safety require evaluation in the intended deployment context.

## 2. Published evidence

### 2.1 RAG can improve or degrade medical answers

A large expert evaluation of medical RAG used 80,502 annotations from 18
medical experts. Only 22% of the top 16 retrieved passages were relevant;
evidence-selection precision was 41–43% and recall was 27–49%. Standard RAG
sometimes reduced factuality and completeness, while evidence filtering and
query reformulation improved downstream benchmark performance. This supports
evaluating retrieval, evidence selection, and generation separately instead of
assuming that adding context is beneficial.

Source: [Rethinking Retrieval-Augmented Generation for Medicine: A Large-Scale,
Systematic Expert Evaluation and Practical
Insights](https://arxiv.org/abs/2511.06738)

RAGAS decomposes evaluation into retrieval/context quality, faithful use of
context, and answer quality. ARES similarly evaluates context relevance,
answer faithfulness, and answer relevance, and calibrates automated evaluation
using a small human-labelled set. RAGVUE further argues for diagnostic,
explainable evaluation of retrieval quality, completeness, strict claim-level
faithfulness, and judge calibration rather than one opaque aggregate score.

Sources:

- [RAGAS: Automated Evaluation of Retrieval Augmented
  Generation](https://aclanthology.org/2024.eacl-demo.16/)
- [ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation
  Systems](https://aclanthology.org/2024.naacl-long.20/)
- [RAGVUE: A Diagnostic View for Explainable and Automated Evaluation of
  Retrieval-Augmented Generation](https://aclanthology.org/2026.eacl-demo.35/)

### 2.2 Hybrid retrieval is promising but must be ablated locally

A biomedical retrieval ablation on BioASQ-13b reported that hybrid BM25 plus
dense retrieval with reciprocal-rank fusion outperformed naive dense retrieval
on faithfulness and context recall in that experiment. It also found that no
single strategy dominated every metric and that HyDE improved faithfulness
while substantially reducing context precision. A 2026 multi-turn RAG system
combining query rewriting, sparse+dense retrieval, answerability gating, and a
faithfulness guard ranked fourth among 29 systems in its SemEval task.

Sources:

- [BioRAG: A Systematic Ablation Study of Retrieval Strategies for Biomedical
  RAG](https://aclanthology.org/2026.bionlp-1.10/)
- [DUTIR at SemEval-2026 Task 8: A Hybrid Retrieval and Faithfulness-Guarded
  Framework for Multi-Turn RAG](https://aclanthology.org/2026.semeval-1.48/)

These studies support testing hybrid retrieval, not declaring it universally
optimal.

### 2.3 Conversation history is a safety variable

A clinical RAG experiment repeated the same query at different dialogue
lengths and reported hallucination increasing from 5% with no history to 40%
with ten prior exchanges. This result is system-specific, but demonstrates that
multi-turn history length and construction must be explicitly evaluated.

Source: [RAG in clinical practice: a cautionary tale of AI
“Truthfulness”](https://www.nature.com/articles/s44401-026-00115-x)

### 2.4 Vietnamese benchmarks cover complementary capabilities

- VM14K contains 14,000 expert-annotated Vietnamese medical multiple-choice
  questions across 34 specialties and four difficulty levels.
- ViMedAQA covers Vietnamese abstractive medical question answering in body
  parts, disease, drugs, and medicine.
- VIMQA contains more than 10,000 Vietnamese multi-hop questions with
  sentence-level supporting facts. It is not medical, but is useful for testing
  retrieval and evidence reasoning in Vietnamese.

Sources:

- [VM14K: First Vietnamese Medical
  Benchmark](https://arxiv.org/abs/2506.01305)
- [ViMedAQA: A Vietnamese Medical Abstractive Question-Answering Dataset and
  Findings of Large Language
  Model](https://aclanthology.org/2024.acl-srw.31/)
- [VIMQA: A Vietnamese Dataset for Advanced Reasoning and Explainable
  Multi-hop Question Answering](https://aclanthology.org/2022.lrec-1.700/)

None of these datasets alone validates CLARA's citations, local corpus,
emergency routing, safety guards, or real patient-facing use.

### 2.5 Human oversight and prospective evidence remain necessary

A 2026 systematic review found that only 19 of 1,048 studies using real-world
patient data were prospective randomized trials; much of the evidence base
still used simulated scenarios or examination-style questions. A prospective
shadow evaluation in emergency neurology illustrates a stronger pattern:
prospective enrolment, comparison against confirmed diagnoses, and blinded
expert assessment. Its clinical findings are specific to that system and
cannot be transferred to CLARA.

Sources:

- [LLM-assisted systematic review of large language models in clinical
  medicine](https://www.nature.com/articles/s41591-026-04229-5)
- [Development and prospective shadow evaluation of a domain-specific large
  language model for emergency neurological
  diagnosis](https://www.nature.com/articles/s41746-026-02644-z)

WHO guidance requires human autonomy, safety, transparency, accountability,
inclusion, equity, and continuing assessment. WHO also calls for expert
supervision and clear evidence of benefit before widespread routine medical
use of LLMs.

Sources:

- [WHO ethics and governance of artificial intelligence for
  health](https://www.who.int/publications/i/item/9789240029200)
- [WHO calls for safe and ethical AI for
  health](https://www.who.int/news/item/16-05-2023-who-calls-for-safe-and-ethical-ai-for-health)

The final IMDRF Good Machine Learning Practice principles and NIST AI Risk
Management Framework support documented lifecycle controls, testing,
independent/domain review, production monitoring, third-party model
monitoring, appeal and override, and change management.

Sources:

- [IMDRF Good machine learning practice for medical device development:
  Guiding
  principles](https://www.imdrf.org/documents/good-machine-learning-practice-medical-device-development-guiding-principles)
- [NIST AI RMF
  Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST Generative AI
  Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)

### 2.6 Prospective evaluation and reporting standards

DECIDE-AI is a reporting guideline for early-stage, live clinical evaluation
of AI decision-support systems, with attention to safety, clinical utility,
human factors, and preparation for larger trials. SPIRIT-AI and CONSORT-AI
extend protocol and trial-reporting guidance for interventions containing an
AI component. FUTURE-AI provides lifecycle recommendations for trustworthy and
deployable health AI. These are reporting and development frameworks; following
them does not by itself prove that an intervention is safe or beneficial.

Sources:

- [DECIDE-AI early-stage clinical evaluation reporting
  guideline](https://www.bmj.com/content/377/bmj-2022-070904)
- [SPIRIT-AI clinical trial protocol
  extension](https://www.nature.com/articles/s41591-020-1037-7)
- [CONSORT-AI clinical trial report
  extension](https://www.nature.com/articles/s41591-020-1034-x)
- [FUTURE-AI international consensus
  guideline](https://www.bmj.com/content/388/bmj-2024-081554.long)

### 2.7 Dated evidence-to-decision bibliography

The table records what each source can and cannot justify. Dates are publication
dates when a version of record exists and initial preprint dates otherwise.

| Date | Source and setting | Population or evaluation unit | Important limitation | Exact CLARA decision informed |
| --- | --- | --- | --- | --- |
| 2025-11-10 | [Kim et al., medical RAG expert evaluation](https://arxiv.org/abs/2511.06738) | 800 outputs over 200 patient/USMLE-style queries; 80,502 annotations from 18 medical experts | Preprint; evaluated selected models, tasks, and corpora rather than CLARA or Vietnamese deployment | Do not authorize RAG by architecture alone; evaluate retrieval, selection, and generation separately; test filtering, rewriting, and context size |
| 2024-03 | [RAGAS](https://aclanthology.org/2024.eacl-demo.16/) | Reference-free RAG evaluation experiments | Automated metrics can inherit judge error and are not clinical validation | Keep separate context, faithfulness, and answer metrics; never use one aggregate as the safety gate |
| 2024-06 | [ARES](https://aclanthology.org/2024.naacl-long.20/) | Eight knowledge-intensive tasks with synthetic judge training and small human-labelled evaluation sets | Not medical or Vietnamese by default | Calibrate automated evaluators against a frozen human-labelled set and report uncertainty |
| 2026-03 | [RAGVUE](https://aclanthology.org/2026.eacl-demo.35/) | Diagnostic reference-free RAG evaluation examples | Evaluation framework evidence, not clinical outcome evidence | Preserve stage-level explanations and explicit judge calibration |
| 2026-07 | [BioRAG](https://aclanthology.org/2026.bionlp-1.10/) | Retrieval ablations on BioASQ-13b | One biomedical benchmark; automated RAGAS-style measures; no CLARA/Vietnamese clinical workflow | Treat BM25+dense+RRF as a candidate and run local ablations; do not declare one retriever universally best |
| 2026-07 | [DUTIR multi-turn RAG](https://aclanthology.org/2026.semeval-1.48/) | SemEval-2026 Task 8 blind test | Competition system and dataset, not patient-facing clinical validation | Evaluate rewrite, hybrid fusion, answerability gating, and a faithfulness guard as separable components |
| 2026-07-03 | [Clinical RAG conversation-length experiment](https://www.nature.com/articles/s44401-026-00115-x) | Repeated executions of a standardized clinical query at increasing dialogue lengths | Single system and experimental construction; percentages are not transferable performance estimates | Make history length/construction a frozen release slice and prohibit unbounded transcript injection |
| 2025-06-02 | [VM14K](https://arxiv.org/abs/2506.01305) | 14,000 Vietnamese medical MCQs across 34 specialties and four difficulty levels | MCQ knowledge benchmark; does not test CLARA grounding, citations, conversation, or clinical benefit | Use only as one Vietnamese knowledge slice; require a private clinician-adjudicated CLARA suite |
| 2024-08 | [ViMedAQA](https://aclanthology.org/2024.acl-srw.31/) | Vietnamese abstractive medical QA across four topic groups | Narrower topic coverage; not a release-quality citation or safety benchmark | Add an abstractive Vietnamese QA slice without treating it as sufficient for release |
| 2022-06 | [VIMQA](https://aclanthology.org/2022.lrec-1.700/) | More than 10,000 Vietnamese multi-hop QA pairs with supporting facts | Wikipedia-based and not medical | Use for Vietnamese multi-hop/supporting-fact mechanics only |
| 2026 | [LLM clinical-medicine systematic review](https://www.nature.com/articles/s41591-026-04229-5) | Broad literature review; 1,048 studies used real-world patient data and 19 were prospective randomized trials | Heterogeneous tasks/models and reporting quality | Do not infer clinical benefit from offline QA; require proportional prospective evaluation |
| 2026-04-18 | [Emergency-neurology prospective shadow evaluation](https://www.nature.com/articles/s41746-026-02644-z) | 433 prospectively enrolled patients with confirmed diagnoses and blinded expert review | One domain-specific system and care setting; results do not transfer to CLARA | Use prospective enrolment, reference outcomes, and blinded review as design patterns, not borrowed performance claims |
| 2021-06-28 | [WHO ethics and governance guidance](https://www.who.int/publications/i/item/9789240029200) | International expert guidance for health AI | Normative guidance, not a performance study | Retain human control, transparency, accountability, equity, and continuous assessment |
| 2025-01-29 | [IMDRF final GMLP principles](https://www.imdrf.org/documents/good-machine-learning-practice-medical-device-development-guiding-principles) | International regulator consensus for AI-enabled medical-device development | Applicability depends on CLARA's intended use and jurisdiction | Maintain lifecycle traceability, representative evaluation, human-AI consideration, monitoring, and controlled change |
| 2023-01 / 2024-07 | [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) and [Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | Cross-sector risk-management guidance | Voluntary and not health-specific regulation | Require documented TEVV, independent review, immutable third-party identity, monitoring, override, incident response, and change control |
| 2022-05-18 | [DECIDE-AI](https://www.bmj.com/content/377/bmj-2022-070904) | Consensus reporting guideline for early live AI decision-support evaluation | Reporting guideline, not proof of study quality or benefit | Use for early human-AI workflow, safety, clinical utility, and human-factors reporting |
| 2020-09-09 | [SPIRIT-AI](https://www.nature.com/articles/s41591-020-1037-7) and [CONSORT-AI](https://www.nature.com/articles/s41591-020-1034-x) | Consensus extensions for AI intervention trial protocols and reports | Reporting guidance; only applicable when CLARA conducts an interventional trial | Pre-register and report applicable prospective trials with exact intervention/version, inputs/outputs, error handling, and human interaction |
| 2025-02-05 | [FUTURE-AI](https://www.bmj.com/content/388/bmj-2024-081554.long) | International healthcare-AI consensus guideline | Broad lifecycle guidance, not a use-case release certificate | Apply fairness, universality, traceability, usability, robustness, and explainability across the lifecycle |

## 3. CLARA engineering requirements

Everything in this section is a **CLARA engineering inference** unless marked
otherwise.

### 3.1 Request and safety routing

1. Apply consent, authentication, role, and policy checks before model access.
2. Run the deterministic emergency fast-path before retrieval or diagnostic
   reasoning. A positive emergency result bypasses normal RAG generation.
3. Classify intent, language, audience, temporal scope, jurisdiction, and
   clinical risk.
4. Detect prescribing, diagnosis, personal-dosage, prompt-injection, and data
   exfiltration intents through hard guards outside the generative model.
5. Create a structured retrieval request that preserves clinical entities,
   negation, time constraints, and the original user text.

### 3.2 Selective hybrid retrieval

1. Normalize Vietnamese and English queries without discarding diacritics,
   abbreviations, medication spelling variants, or negation.
2. Retrieve independently with:
   - a lexical retriever such as BM25;
   - a pinned multilingual dense retriever;
   - optional structured filters for jurisdiction, publication/effective date,
     audience, specialty, and source authority.
3. Preserve raw ranks and scores from every retrieval provider.
4. Fuse ranked lists with a deterministic, versioned method such as reciprocal
   rank fusion.
5. Filter non-allowlisted, expired, superseded, unauthorized, or
   prompt-injection-bearing sources before reranking.
6. Rerank the remaining candidates with a pinned model and configuration.
7. Gate generation on evidence sufficiency: required topic coverage, source
   authority, freshness, contradiction state, and retrieval confidence.
8. If evidence is insufficient, ask a focused clarifying question or abstain.
   Do not fill gaps from unverified parametric memory.

### 3.3 Adaptive context, not a global top-k

CLARA must evaluate at least `k = {3, 5, 8, 10, 16}` for each major intent and
risk class. The selected policy must:

- stop adding passages when marginal relevance is below a calibrated value;
- fit a versioned context-token budget;
- remove near duplicates;
- retain evidence needed to expose genuine conflicts;
- favor fewer high-confidence passages for critical medical claims;
- record the chosen policy and retrieved set in a replayable trace.

No top-k value may become a production default solely because it performed best
on a general benchmark.

### 3.4 Safe query rewriting and multi-turn context

1. Preserve the original query next to every rewritten query.
2. Compare extracted entities, negation, temporality, dosage, and intent before
   accepting a rewrite.
3. Reject a rewrite that changes clinical meaning.
4. Retrieve fresh evidence for each turn.
5. Convert older conversation history to a bounded, structured, user-reviewable
   fact summary; do not inject an unbounded transcript.
6. Test behavior at 0, 2, 5, 10, and 20 prior turns, including correction,
   contradiction, and topic-switch scenarios.

### 3.5 Source and citation contract

Each indexed chunk must carry:

- immutable source and chunk IDs;
- canonical URL or document ID;
- publisher, jurisdiction, audience, and authority tier;
- publication, effective, expiry, supersession, ingestion, and retrieval dates
  where applicable;
- document version and content hash;
- section, page, and character/span locators;
- source language;
- ingestion, parser, chunker, embedding, and index versions;
- access policy and tenant/profile partition where applicable.

Every externally verifiable medical claim in an answer must map to at least one
exact evidence span. Citations must open that span and display source identity
and date.

Citation presence is not citation correctness. A claim-to-span verifier must
label each link as `supported`, `contradicted`, or `insufficient`. Critical
unsupported or contradicted claims are blocked. Noncritical unsupported claims
are removed or explicitly presented as uncertainty.

Conflicting sources must be represented as a conflict with their dates,
jurisdictions, and authority. The generator must not silently blend
incompatible recommendations.

### 3.6 Retrieved content is untrusted input

1. Delimit retrieved content as data, never instructions.
2. Remove active content and unsafe markup during ingestion.
3. Detect prompt injection in documents, queries, and generated candidates.
4. Prevent retrieved text from overriding system policy, tool permissions, or
   data-access boundaries.
5. Include poisoned-document, cross-tenant, source-spoofing, and indirect
   prompt-injection cases in every release evaluation.

## 4. Stage-aware evaluation

### 4.1 Retrieval

Measure and report:

- Recall@k and Precision@k;
- nDCG@k and MRR;
- source-authority and freshness coverage;
- corpus-miss and no-answer detection rates;
- duplicate and near-duplicate rate;
- conflict retrieval recall;
- cross-profile or unauthorized retrieval count, which must remain zero.

### 4.2 Evidence selection and context construction

Measure and report:

- selected-evidence precision and recall;
- required-claim-slot coverage;
- context utilization;
- irrelevant-context sensitivity;
- lost-in-the-middle sensitivity;
- contradiction recognition;
- original-to-rewritten-query semantic preservation.

### 4.3 Generation

Measure and report:

- claim-level entailment precision;
- unsupported-claim and contradiction rates;
- citation correctness and citation completeness;
- factuality, completeness, relevance, and actionability;
- uncertainty and abstention calibration;
- emergency recall and escalation appropriateness;
- prohibited diagnosis, prescribing, and personal-dosage output rates;
- instruction-following under retrieved prompt injection.

### 4.4 End-to-end and operational quality

Measure and report:

- task success and user comprehension;
- clinician-rated safety, accuracy, completeness, and usefulness;
- time to a correct, supported answer;
- correction, dispute, override, and escalation rates;
- safety and quality gaps across language, specialty, age group, gender where
  lawful and available, literacy level, disability/accessibility mode, and
  other approved cohorts;
- p50, p95, and p99 latency;
- token, retrieval, reranking, and generation cost;
- availability, timeout, degradation, and fail-safe behavior.

### 4.5 Automated judge governance

Automated judges must be calibrated against blinded bilingual clinician
annotations. Record agreement, disagreement classes, confidence intervals,
judge model/revision, prompt hash, and evaluator version. A model judge must
never be the sole gate for a critical safety release.

## 5. Proposed CLARA release thresholds

The following are **proposed CLARA thresholds, not literature-established
constants**. Clinical and safety owners must approve or replace them before
they become release policy.

| Gate | Initial proposal |
| --- | --- |
| Emergency fast-path recall | 100% on the locked red-team set |
| Critical unsupported dosage or DDI claims | 0 |
| Critical claim-to-citation entailment precision | 100% |
| Critical medical-claim citation completeness | 100% |
| Overall medical claim-to-citation entailment precision | at least 98% |
| Overall unsupported medical-claim rate | at most 1% |
| Cross-profile or unauthorized retrieval | 0 |
| Prohibited diagnosis, prescribing, or personal-dosage output | 0 on locked safety suite |
| Vietnamese versus English safety regression | no statistically material regression |
| Retrieval quality versus incumbent | non-inferior with a prespecified 95% confidence interval |
| Latency and cost | within the approved per-route SLO and budget |

No weighted aggregate can compensate for failure of a critical gate. Report
confidence intervals and denominators, not just point estimates.

## 6. Vietnamese evaluation suite

CLARA should use:

- VM14K for Vietnamese medical knowledge breadth, specialty, and difficulty;
- ViMedAQA for Vietnamese abstractive medical QA;
- VIMQA for Vietnamese multi-hop retrieval and supporting-fact reasoning;
- a private, frozen CLARA benchmark for capabilities not covered above.

The private benchmark must be authored and adjudicated by qualified native
Vietnamese clinicians and include:

- Vietnamese lay phrasing and health-literacy variation;
- regional wording, diacritic loss, typos, abbreviations, and code switching;
- Vietnamese medication brand and generic-name variants;
- emergency and red-flag presentations;
- negation, temporality, pregnancy, age, allergy, renal/hepatic, and interaction
  constraints;
- local and international guideline conflicts;
- unanswerable and insufficient-evidence questions;
- exact citation-span labels;
- multi-turn corrections, contradictions, and topic switches;
- prompt injection and poisoned sources.

Train, development, public test, and private test data must be separated.
Contamination checks and dataset versions must be recorded. Results must be
reported separately by language, specialty, difficulty, risk class, and
relevant approved cohorts.

## 7. Immutable release manifests

Every candidate and production release must have an immutable
`RagReleaseManifest` containing:

- unique manifest ID, creation time, approvers, intended use, and risk class;
- provider and exact model ID/revision, never only a floating alias;
- API mode and relevant decoding/tool configuration;
- system, policy, routing, and prompt-template hashes;
- retriever, reranker, embedding, entailment verifier, guard, and judge
  model/revisions;
- source allowlist and corpus snapshot/content hash;
- parser, chunker, index schema, fusion, top-k/context, and filtering config;
- feature-flag snapshot;
- evaluation dataset and evaluator versions;
- evidence-package hash and release decision;
- predecessor and rollback manifest IDs.

The request-time manifest ID must be present in no-PII audit telemetry. A
provider alias change, model revision, prompt/policy change, corpus or index
change, evaluator change, or retrieval-policy change creates a new candidate
release and triggers the applicable gates. Production must support immediate
rollback to the prior approved manifest.

This exact schema is a CLARA engineering implementation of traceability and
change-control principles; it is not prescribed verbatim by WHO, NIST, or
IMDRF.

## 8. Prospective rollout

Release progression must be:

1. frozen offline component and end-to-end evaluation;
2. independent, blinded bilingual clinician review;
3. shadow mode on representative deployment traffic with no patient-visible
   generated answer;
4. limited, consented pilot with human review and predefined stopping rules;
5. staged release with automatic rollback;
6. prospective post-release monitoring and periodic re-evaluation.

Before a pilot, preregister:

- intended users, use case, exclusions, and claims;
- primary safety and benefit endpoints;
- sample-size rationale;
- language, specialty, risk, and subgroup analyses;
- acceptance thresholds and confidence intervals;
- stopping, pause, rollback, incident, and disclosure rules;
- human-review responsibilities and response times.

Monitor emergency misses, critical unsupported claims, citation failures,
abstention, overrides, disputes, subgroup gaps, model/provider drift, corpus
freshness, latency, and availability. A critical gate breach pauses or rolls
back the release automatically.

Users and clinicians must be able to inspect evidence, correct source facts,
dispute an output, override a recommendation, and report harm. CLARA remains a
clinical assistant and health-information tool; it does not autonomously
diagnose or prescribe.

## 9. Required implementation artifacts

- Immutable `RagReleaseManifest` schema and signed registry
- Provenance-rich `RetrievedChunk` schema
- `ClaimEvidenceLink` schema with verifier outcome and exact locator
- Replayable, no-PII per-stage trace
- Frozen evaluation bundle and contamination record
- Retrieval ablation runner for sparse, dense, hybrid, k sweep, rewrite,
  reranker, filter, and history policies
- Bilingual clinician adjudication interface with blinded pairwise review and
  disagreement resolution
- Shadow and pilot protocols
- Monitoring dashboard, incident response, and rollback runbook
- Evidence package and explicit approval record for every release

## 10. Decision summary

These are CLARA's target architecture decisions, not a claim that the current
runtime or any release has already passed them:

1. Hybrid BM25+dense retrieval with deterministic fusion is the leading
   candidate, not an automatically approved production strategy.
2. Frozen per-intent and per-risk ablations select retrieval mode and context
   from at least `k = {3, 5, 8, 10, 16}`; no global “largest context” policy is
   allowed.
3. A failed evidence-sufficiency gate returns a focused clarification,
   source-only response, deterministic safety response, or abstention.
4. Every released medical claim needs an exact source span and claim-level
   existence, entailment, temporal, conflict, authority, profile, legal, and
   FIDES checks where applicable.
5. Multi-turn history is bounded and structured; every release is tested
   across history-length and correction/contradiction slices.
6. Automated judges support triage only after calibration against blinded
   bilingual clinician review and never solely authorize a critical release.
7. VM14K, ViMedAQA, and VIMQA are complementary offline slices, not Vietnamese
   clinical-validation certificates.
8. Exact provider/model, prompts, policies, retrievers, corpus/index snapshot,
   evaluators, and rollback identity are immutable within a release.
9. Promotion follows frozen offline evaluation, independent review, red-team,
   shadow, bounded human-reviewed pilot, staged release, and monitoring;
   prospective evaluation is required when the output may influence health
   decisions.

The evidence does not support treating RAG as an automatic factuality control
or claiming clinical benefit from benchmark gains.
