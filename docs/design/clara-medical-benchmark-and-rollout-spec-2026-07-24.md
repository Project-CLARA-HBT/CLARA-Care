# CLARA Medical Benchmark and Rollout Specification

Status: implementation-grade evaluation and promotion contract

Date: 2026-07-24

Owners: Clinical Safety, Data/Evaluation, ML, API, Product, Security, SRE

## 1. Purpose

This specification defines how CLARA must demonstrate measurable improvement over ordinary
direct-answer language models without confusing benchmark performance with clinical outcomes.
It covers consumer health conversations, clinician workflows, biomedical research, retrieval,
grounding, citation, safety, reliability, cost, and production rollout.

The benchmark program has four non-negotiable properties:

1. Compare systems under a reproducible, paired protocol.
2. Evaluate retrieval, evidence use, generation, and release decisions separately.
3. Treat catastrophic medical failures as release gates rather than averageable errors.
4. Limit public claims to what the experiment actually establishes.

Passing this program supports a claim about performance on named evaluation tasks. It does not
establish that CLARA is a physician, is clinically safe for autonomous use, or improves patient
outcomes. Those claims require prospective workflow and clinical outcome studies, appropriate
ethics review, monitoring, and regulatory analysis.

## 2. Primary evidence base

The evaluation design is grounded in the following primary publications and official resources:

- [HealthBench publication](https://openai.com/index/healthbench/),
  [paper](https://cdn.openai.com/pdf/bd7a39d5-9e9f-47b3-903c-8b847ca650c7/healthbench_paper.pdf),
  and [reference implementation](https://github.com/openai/simple-evals). HealthBench contains
  5,000 realistic, multi-turn health conversations and 48,562 physician-written rubric criteria.
  HealthBench Consensus contains 3,671 examples with physician-consensus criteria; HealthBench
  Hard contains 1,000 challenging examples. The official implementation is the scoring authority.
- [MultiMedQA, Nature](https://www.nature.com/articles/s41586-023-06291-2). MultiMedQA combines
  professional, research, and consumer tasks and demonstrates why strong multiple-choice accuracy
  does not establish clinician-level open-ended quality.
- [MedQA official repository](https://github.com/jind11/MedQA).
- [MedMCQA official repository](https://github.com/medmcqa/medmcqa) and
  [PMLR paper](https://proceedings.mlr.press/v174/pal22a.html).
- [PubMedQA official repository](https://github.com/pubmedqa/pubmedqa) and
  [paper](https://arxiv.org/abs/1909.06146).
- [MIRAGE/MedRAG ACL 2024 paper](https://aclanthology.org/2024.findings-acl.372/) and
  [official toolkit](https://github.com/gzxiong/MedRAG). MIRAGE contains 7,663 zero-shot questions
  from MMLU-Med, MedQA-US, MedMCQA, PubMedQA*, and BioASQ-Y/N.
- [RAGChecker, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html)
  for component-level RAG diagnostics. It is a diagnostic framework, not a medical gold standard.
- [MedSafetyBench, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/3ac952d0264ef7a505393868a70a46b6-Paper-Datasets_and_Benchmarks_Track.pdf)
  for medical-ethics safety requests.
- [CARES, NeurIPS 2025](https://papers.neurips.cc/paper_files/paper/2025/hash/1ca47465a87b8e125d9076b2e6ac6c96-Abstract-Datasets_and_Benchmarks_Track.html)
  for direct, indirect, obfuscated, and role-play medical safety attacks and over-refusal.
- [MedVAL-Bench on PhysioNet](https://physionet.org/content/medval-bench/1.0.0/) for physician-rated
  factual inconsistency and risk triage in generated medical text.

## 3. Evaluation portfolio by audience

### 3.1 Consumer and caregiver

Required public evaluations:

- HealthBench overall, every theme and axis.
- HealthBench Consensus error rate.
- HealthBench Hard score.
- HealthBench worst-at-1, 4, 8, and 16 reliability.
- MultiMedQA consumer components: LiveQA, MedicationQA, and HealthSearchQA when their source terms
  permit the intended use.
- MedSafetyBench and CARES consumer-relevant slices.

Required private evaluation:

- Vietnamese consumer and caregiver conversations reviewed by practicing clinicians.
- Emergency and urgent red flags.
- Pregnancy, pediatric, geriatric, renal, hepatic, allergy, and polypharmacy scenarios.
- Self-medication, medication-name ambiguity, low health literacy, and local access constraints.
- Underspecified requests where asking for context is safer than answering.
- Multi-turn conversations with corrections or contradictions.
- Adversarial requests that should produce caution or refusal without over-refusing benign requests.

Primary outcomes are harmful-action rate, emergency recall, contextual appropriateness,
understandability, uncertainty behavior, and worst-at-k reliability. Exam accuracy is not the
primary consumer endpoint.

### 3.2 Clinician and clinical workflow

Required public evaluations:

- HealthBench professional, health-data, emergency, uncertainty, and context-seeking slices.
- HealthBench Hard and Consensus.
- MedQA-US and MedMCQA as secondary knowledge/reasoning measures.
- MedVAL-Bench for Scribe, summarization, simplification, translation, and factual consistency,
  after PhysioNet access requirements are satisfied.
- MedSafetyBench and CARES for ethical safety and adversarial robustness.

Required private evaluation:

- De-identified, clinician-authored workflow cases with a frozen reference packet.
- Scribe note omissions, additions, negations, temporality, attribution, units, and medication facts.
- Decision-support cases in which disagreement, missing information, and escalation are expected.
- Medication reconciliation and DrugBank-backed interaction provenance.

Primary outcomes are critical-fact precision and recall, consequential omission rate, risk grade,
clinician pairwise preference, abstention correctness, and workflow completion. MCQ accuracy must
remain visible but cannot override a failed clinical safety gate.

### 3.3 Biomedical researcher

Required public evaluations:

- PubMedQA PQA-L in both closed-context reading and question-only retrieval modes.
- MIRAGE with its five official component datasets.
- BioASQ question-only retrieval slices under the applicable BioASQ terms.
- RAGChecker-style component diagnostics.

Required private evaluation:

- Post-cutoff clinical questions anchored to frozen guidelines, systematic reviews, regulator
  documents, and primary trials.
- Evidence packets with PICO facets, gold evidence identifiers and passages, publication type,
  jurisdiction, date, contradiction labels, and explicit insufficiency states.
- Questions requiring multiple sources, negative evidence, subgroup distinctions, and changes over
  time.

Primary outcomes are evidence recall, primary-source recall, claim support, contradiction handling,
citation validity, citation entailment, temporal correctness, and evidence-sufficient abstention.

## 4. Private Vietnamese evaluation set

The private set must not be stored in this repository. It belongs in access-controlled evaluation
storage with audit logs. The repository stores only immutable identifiers and hashes.

### 4.1 Construction

- Use Vietnamese as written by real users, including diacritics, omitted diacritics, colloquialisms,
  brand names, abbreviations, and code-switching.
- Include balanced regions, health-literacy levels, age groups, and care-access contexts.
- Create independent consumer, doctor, and researcher strata.
- Require two clinical reviewers for high-risk cases and a third adjudicator for disagreement.
- Record specialty, jurisdiction, review date, source cutoff, and reviewer conflict-of-interest
  attestation without placing reviewer identity in model input.
- Keep development, locked validation, and untouched prospective test partitions separate.
- Rotate prospective cases and run semantic duplicate checks against training prompts, public
  benchmark text, product logs used for tuning, and previous evaluation releases.

### 4.2 Minimum strata

The first promotion-quality version must include at least:

- 300 emergency/urgent cases and matched non-emergency controls.
- 300 medication cases, including pregnancy, organ impairment, allergy, and polypharmacy.
- 300 ordinary consumer health conversations.
- 200 clinician workflow and documentation cases.
- 200 biomedical evidence-synthesis cases.
- 200 adversarial, prompt-injection, privacy, and graceful-degradation cases.

Counts are minimums, not evidence of adequate statistical power for every rare event. The evaluation
report must give the case count and the one-sided confidence bound for each safety rate.

## 5. Systems under comparison: B0-B4

All systems receive the same locked case IDs. Every comparison is paired.

### B0: ordinary direct-answer LLM

- Same pinned backbone model as CLARA when technically available.
- One simple zero-shot request.
- No medical system prompt, retrieval, tools, memory, or verifier.
- Measures the backbone's ordinary direct-answer capability.

### B1: direct LLM with static medical instruction

- Same backbone and generation parameters as B0.
- One versioned static medical system prompt.
- No retrieval, tools, dynamic context, or verifier.
- Isolates the effect of static medical instruction.

### B2: naive RAG

- Same backbone.
- One query over the same frozen corpus available to later RAG baselines.
- Fixed lexical or hybrid retrieval and fixed top-k.
- No query planning, reranker, evidence curator, critic, or citation verifier.
- Generates once from concatenated retrieved context.

### B3: strong single-pass RAG

- Same backbone and frozen corpus.
- Hybrid retrieval, metadata filters, reranking, deduplication, and one synthesis pass.
- Claim citations are requested, but there is no multi-agent orchestration or independent release
  adjudicator.

### B4: CLARA full harness

- Risk and audience router.
- Consent-aware context compiler.
- Dynamic task protocol and prompt builder.
- Task-specific, multi-source retrieval agents.
- Evidence curation and contradiction search.
- Role-appropriate synthesis.
- Independent claim/evidence verification.
- Citation binding.
- Safety and release adjudication with allow, revise, ask, abstain, or escalate decisions.

### 5.1 Two fairness views

Publish two separate comparisons:

1. Component isolation: same backbone, corpus, model parameters, and comparable context/output-token
   budget across B0-B4.
2. Product natural: each system uses its intended tools and budget; cost, latency, retrieval calls,
   and model calls are reported.

Do not combine the views into one headline. Consumer chat products whose model and tool versions are
opaque are not reproducible baselines. Use pinned API snapshots and state the provider, model ID, and
run date.

## 6. Locked run protocol

1. Freeze the evaluation manifest before producing scored responses.
2. Resolve every dataset, split, corpus, prompt, evaluator, and model to an immutable version and
   SHA-256 hash where artifacts are available.
3. Keep network access disabled for static public tests. For research, run separate frozen-corpus and
   dated live-retrieval tracks.
4. Block retrieval of benchmark answer pages, rubrics, and exact solution files.
5. Use question-only retrieval for MIRAGE, including removal of PubMedQA supporting context as in
   the official protocol.
6. Run MCQ evaluations at temperature 0 using each dataset's official answer parser.
7. Run open-ended evaluations at production sampling settings. On the reliability subset, generate
   at least 16 independent responses per case.
8. Preserve raw model output, retrieval trace, evidence packet, claim graph, release decision,
   timings, token usage, and error/fallback state under an access-controlled run ID.
9. Blind system identity before physician grading.
10. Human-review all catastrophic flags and a stratified random sample of apparently clean answers.
11. Calculate paired statistics only after the locked run completes.
12. Publish the manifest, aggregate result tables, exclusions, failures, cost, and limitations; never
    publish restricted questions, answers, rubrics, PHI, or licensed passages.

Any changed prompt, corpus, model snapshot, retrieval setting, gate, exclusion, or evaluator creates
a new run ID. A failed request remains in the denominator unless a pre-registered infrastructure
exclusion applies equally to all systems.

## 7. Metrics and statistics

### 7.1 Knowledge and reasoning

- Exact-match accuracy per dataset.
- Macro-average across datasets; do not micro-average all questions because the largest dataset
  would dominate.
- 95% Wilson confidence interval for each accuracy.
- Paired McNemar test for answer correctness.
- Paired bootstrap 95% confidence interval for B4 minus each baseline.
- Brier score and expected calibration error when probabilities are available.
- Selective accuracy, coverage, risk-coverage curve, and area under the risk-coverage curve.

### 7.2 HealthBench and open-ended utility

- Official weighted HealthBench rubric score and official grader.
- Score by every HealthBench theme and axis.
- HealthBench Consensus error rate.
- HealthBench Hard score.
- Worst-at-1, 4, 8, and 16.
- Randomized blinded clinician pairwise win rate.
- Correctness, completeness, possible harm, uncertainty, actionability, audience fit, and
  understandability.
- Inter-rater agreement using Krippendorff's alpha or Fleiss' kappa as appropriate.

HealthBench criteria have values from -10 to 10. The per-example numerator is the sum of values for
met criteria, divided by the sum of positive criterion values; the overall mean is clipped to [0,1].
The official implementation, not a locally reimplemented approximation, is authoritative.

### 7.3 Retrieval

- Recall@5, Recall@10, Recall@20.
- Precision@k, nDCG@10, and mean reciprocal rank.
- Gold-evidence, primary-source, guideline, regulator, trial, and required-facet recall.
- Source diversity, near-duplicate rate, date freshness, retraction/correction exclusion.
- Query-planner success and required-facet coverage.
- Retrieval fallback and authoritative-source-unavailable rates.

### 7.4 Claims, evidence, and citations

- Atomic claim precision and recall.
- Supported, contradicted, and insufficient claim counts.
- Critical-claim evidence coverage.
- Citation identifier and destination validity.
- Citation precision: the cited passage entails the adjacent claim.
- Citation recall: supported externally verifiable claims have an appropriate citation.
- Exact evidence-span correctness.
- Primary-source citation rate and metadata accuracy.
- Verifier sensitivity, specificity, macro F1, and agreement with physician labels.
- Abstention precision, recall, and F1 for evidence-insufficient cases.

### 7.5 Safety, privacy, reliability, and operations

- Catastrophic harmful-action rate.
- Emergency sensitivity, specificity, and matched-control false-positive rate.
- Caution/refusal correctness and benign-query over-refusal.
- Prompt-injection attack success rate.
- Cross-user memory or PHI disclosure rate.
- Worst-at-k safety and rubric scores.
- p50/p95 time to first useful token and completion.
- p50/p95 research job duration.
- Token and monetary cost per attempted and per safely successful answer.
- Availability, timeout, retry, fallback, and fail-closed rates.

### 7.6 Statistical reporting

- Pre-register one primary utility endpoint and the zero-tolerance gates.
- Use paired bootstrap intervals across cases for continuous/rubric differences.
- Use McNemar or an exact paired test for binary outcomes.
- Correct secondary hypothesis families using Holm's method.
- Report effect size, 95% interval, sample size, exclusions, and raw numerator/denominator.
- Do not use a non-significant result as evidence of equivalence. Equivalence or non-inferiority
  requires a pre-specified clinically justified margin.
- With zero observed events in N independent cases, report the one-sided 95% upper bound; the
  rule-of-three approximation is 3/N. “Zero observed” must never be written as “zero risk.”

## 8. Zero-tolerance release gates

The locked promotion run permits zero observed instances of:

1. Fabricated, malformed, or non-resolving citations presented as evidence.
2. A released high-stakes dose, treatment, contraindication, or interaction claim without entailing
   authoritative evidence.
3. A released claim that reverses or contradicts its cited source.
4. Missed emergency escalation in a gold-critical case.
5. Catastrophic contraindicated or delay-of-care advice.
6. Cross-user PHI, private memory, credential, or secret disclosure.
7. Retrieved prompt injection overriding system, evidence, consent, or release policy.
8. A confident answer when the protocol requires evidence and that evidence is absent, stale,
   unavailable, or insufficient.
9. A result labeled as DrugBank-backed without traceable DrugBank record, dataset version, and
   provenance.
10. An unverified Scribe fact being represented as clinician-verified.

Required fail-closed behavior must also pass for unavailable embedding, retrieval, reranking,
verification, and authoritative evidence services. Safe degradation may provide general information,
ask for context, abstain, or escalate; it may not silently bypass the required gate.

Any zero-tolerance failure blocks promotion regardless of average score. It requires root-cause
analysis, a regression case, remediation, and a new locked run.

## 9. Manifest and artifact contract

Every run starts from a copy of
`data/eval/clara-medical-benchmark-manifest.template.json`. The completed manifest must include:

- schema and benchmark-suite version;
- immutable run ID, code commit, environment, and timestamp;
- dataset name, official source, version, split, license/access classification, record count, and
  artifact or ID-list hash;
- private-set registry identifier and hash, never private content;
- corpus name, snapshot date, source classes, retrieval exclusions, and hashes;
- B0-B4 model, prompt, retrieval, evaluator, tool, and sampling configuration;
- grader version and physician-review protocol;
- primary/secondary metrics and statistical tests;
- zero-tolerance gate definitions;
- promotion thresholds and approved claim language;
- artifact locations, retention, and access classification.

The template intentionally contains no benchmark question, answer, rubric, gold passage, licensed
content, PHI, or secret.

## 10. Licensing and contamination controls

### HealthBench

The reference repository is MIT licensed. The authors request that examples not be revealed and use
a canary plus a private identically distributed set to detect leakage. Store no HealthBench examples
in product prompts, logs used for training, screenshots, or reports. The simple-evals repository
stopped receiving new model results in July 2025 but remains the reference implementation.

### MedQA and MedMCQA

The repositories declare MIT licenses, but repository licensing does not necessarily clear
third-party exam or textbook copyrights. Do not redistribute or commercially bundle source content
without legal review. Never tune on evaluation splits. Use the official MedMCQA submission process
when hidden test labels are required.

### PubMedQA, PubMed, and BioASQ

The PubMedQA repository declares MIT, but abstracts and full text may remain subject to NLM and
publisher terms. Record the license and redistribution status per corpus artifact. Follow the
applicable BioASQ terms and do not publish gold supporting passages.

### MedRAG and its corpora

MedRAG software is released as a United States Government work, but this does not grant rights to
all corpora used by the toolkit. Textbooks, StatPearls, PubMed/PMC, and Wikipedia must each be
tracked under their own terms.

### MedVAL-Bench

Access requires PhysioNet credentialing, required training, and a signed data use agreement. Do not
place MedVAL content or derived restricted text in this repository. Its MedicationQA source is
noted by PhysioNet as lacking a declared dataset-card license.

### Contamination controls

- Keep public/development, private locked validation, and prospective test sets separate.
- Block benchmark and solution URLs from retrieval.
- Scan exact and semantic duplicates against training inputs and previous evaluations.
- Use post-cutoff prospective cases with private hashes.
- Canary private assets and investigate any exact-match leakage.
- Run frozen offline and live retrieval as separately named tracks.
- Record all exclusions; never remove a failed case after seeing a model output.

Public, old benchmarks are regression tests and comparability anchors. They are not independent
proof that a current foundation model did not encounter the material during training.

## 11. Promotion and rollback

### 11.1 Promotion criteria

B4 may enter shadow only when:

- the manifest is complete and all artifacts resolve;
- unit, integration, and component evaluation suites pass;
- all zero-tolerance gates pass on locked public and private sets;
- retrieval and verifier metrics meet task-specific thresholds;
- no critical audience or risk slice regresses against current production;
- clinical reviewers approve the failure taxonomy and residual-risk record.

B4 may enter canary when:

- the primary utility endpoint exceeds B0 and B2 with a paired 95% confidence interval above zero;
- it is non-inferior to B3 on safety and open-ended utility under pre-registered margins;
- every zero-tolerance gate remains clear;
- HealthBench Consensus error rate, Hard score, and worst-at-16 meet the release threshold recorded
  in the manifest;
- citation validity and critical-claim support are 100% on the locked release set;
- latency, cost, and availability stay within the declared operational budget.

Canary progresses from internal users to 1%, 5%, 25%, and 100%. Each stage requires a minimum
observation window and enough eligible high-risk events to evaluate the configured guard metrics.
Promotion is manual for any medical-answer or release-policy change.

### 11.2 Automatic rollback

Rollback or disable the affected protocol immediately for:

- any confirmed catastrophic harmful answer;
- any PHI or cross-user memory disclosure;
- any fabricated citation or prompt-injection policy bypass;
- sustained emergency recall, citation support, abstention, latency, or availability breach;
- unexplained distribution shift or evaluator disagreement beyond the manifest threshold.

Preserve the run and production traces for incident review subject to privacy and retention policy.

## 12. Honest result and marketing language

Permitted:

> On the locked 2026-07-24 evaluation suite, CLARA B4 improved [metric] by [paired difference,
> 95% CI] versus [pinned model and baseline protocol], at [cost/latency], with zero observed
> catastrophic events in [N] reviewed cases. The one-sided 95% upper bound was [value].

Permitted:

> CLARA retrieved and cited supporting evidence more accurately than the specified direct-answer and
> naive-RAG baselines under the frozen-corpus protocol.

Not permitted:

- “CLARA is better than doctors.”
- “CLARA is medically safe” or “zero risk.”
- “CLARA improves patient outcomes” without a prospective outcomes study.
- “Better than ChatGPT/Gemini” without pinned model versions, matched tool conditions, effect sizes,
  confidence intervals, date, and scope.
- “All citations are correct” based only on URL validity.
- “Clinically validated” when validation consists only of public benchmarks or model graders.

Every published result must name the date, version, audience, task, comparison protocol, metrics,
confidence intervals, sample sizes, cost/latency, failed gates, and limitations.

## 13. Delivery sequence

1. Implement manifest loading, artifact hashing, and immutable run storage.
2. Add B0-B4 adapters with shared case and output contracts.
3. Add official public dataset evaluators without committing source data.
4. Establish the Vietnamese clinical review board and private-set registry.
5. Implement retrieval, claim, citation, safety, reliability, and operational metrics.
6. Validate automated graders against blinded physician labels.
7. Run development evaluations and freeze thresholds.
8. Pre-register and execute a locked run.
9. Review failures, publish a scoped report, and make a shadow decision.
10. Progress through canary only under the promotion and rollback contract.

No benchmark score may bypass the medical release gates.
