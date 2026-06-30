# Requirements Document

## Introduction

CLARA Research is the existing deep-research and evidence-synthesis surface of the CLARA-Care
monorepo. It is already implemented across web (`apps/web/app/chat/page.tsx`), API
(`services/api/.../endpoints/research.py` with the `ResearchJob` async engine), and ML
(`services/ml/.../agents/research_tier2.py`). It supports three modes — fast (tier1 chat),
deep, and deep_beta (tier2 async jobs) — a federated Source Hub, hybrid retrieval
(`RagPipelineP1`), synthesis, FIDES-lite + NLI claim verification, safety overrides, and a
flow/telemetry rail.

This specification is an **enhancement** of that existing feature. The goal is to make CLARA
Research fully functional and competitive with leading evidence-synthesis products
(OpenEvidence, Consensus, Elicit, Perplexity/OpenAI/Google Deep Research, UpToDate, Scite.ai,
Glass Health, Undermind) while grounding behavior in evidence-based-medicine (EBM) science
(evidence hierarchy, PICO, GRADE, citation faithfulness, NLI claim verification, RAG evaluation
metrics).

The work is scoped along three principles:

- **Additive and feature-flagged.** New behavior MUST default off and preserve current behavior.
  Existing seams MUST be reused: `resolveChatTransport`, `FLOW_STAGE_ALIAS_MAP`,
  `_build_tier2_upstream_payload`, the Source Hub catalog, the `rag_flow`/Control Tower config,
  `factcheck/fides_lite` + `nli_verifier`, the report section/word-budget contract, and the
  `ResearchJob` engine + SSE.
- **Vietnamese-first.** UI and generated output default to Vietnamese, with existing bilingual
  vi/en support preserved.
- **Decision-support, not a medical device.** CLARA-Care is a reference/decision-support tool,
  not a medical device or EMR. Outputs are not treatment orders, appropriate disclaimers are
  retained, and existing medical-safety guardrails (drug–drug interaction floor, dosage/legal
  block, consent gate, emergency fast-path, FIDES CRITICAL block) MUST be preserved.

This document also resolves known defects (a duplicated request contract, non-durable uploaded
files, mis-gated telemetry, and missing claim-to-study traceability) and establishes a
measurable quality gate so that enhancements never regress retrieval quality below the legacy
baseline.

## Glossary

- **CLARA_Research**: The deep-research and evidence-synthesis feature comprising the web
  Research surface, the API `ResearchJob` engine, and the ML `run_research_tier2` orchestrator.
- **Research_API**: The API layer in `services/api/.../endpoints/research.py`, including the
  `ResearchJob` async job engine.
- **Research_Orchestrator**: The ML layer `run_research_tier2` and its sub-stages (planner,
  query plan, retrieval, synthesis, verification, report).
- **Research_Web_UI**: The web Research surface folded into `apps/web/app/chat/page.tsx`.
- **Research_Mobile_UI**: The mobile Research screen (`apps/mobile/lib/screens/research_screen.dart`).
- **tier1**: The synchronous fast chat path used by fast mode.
- **tier2**: The asynchronous `ResearchJob` path used by deep and deep_beta modes.
- **fast / deep / deep_beta**: The three research modes (UI labels Nhanh / Tư duy / Pro).
  deep_beta is the long-form, multi-pass report mode.
- **personal_mode**: Personalization that uses the user's PHR and medicine cabinet; valid only in
  tier2 (the invariant "never (fast && personal)" holds).
- **Source_Hub**: The federated search catalog (PubMed, RxNorm, openFDA, DailyMed,
  ClinicalTrials, EuropePMC, Semantic Scholar, and VN sources vn_moh, vn_kcb,
  vn_canhgiacduoc, vn_vbpl_byt, vn_dav, davidrug).
- **PHR**: Personal Health Record — the user's stored health data within CLARA-Care.
- **PICO**: An EBM question-framing structure: Population, Intervention, Comparison, Outcome.
- **GRADE**: An EBM system for rating the certainty of evidence (high, moderate, low, very low)
  and the strength of a recommendation (strong, conditional).
- **Evidence_Hierarchy**: The EBM ranking of evidence types (systematic review > randomized
  controlled trial > cohort study > case study > expert opinion).
- **FIDES**: The existing FIDES-lite verification component that assigns a trust verdict to
  synthesized content using trust tier and recency.
- **NLI**: Natural Language Inference — entailment classification used to judge whether a cited
  source supports (entails), contradicts, or is neutral toward a synthesized claim.
- **Claim_Verdict**: The per-claim verification result: supported, unsupported, or contradicted.
- **RAG**: Retrieval-Augmented Generation — the retrieve-then-synthesize pipeline
  (`RagPipelineP1`).
- **recall@k**: The fraction of relevant source documents retrieved within the top k results.
- **faithfulness**: The degree to which synthesized statements are supported by the retrieved
  evidence rather than fabricated.
- **citation_accuracy**: The fraction of citations that correctly point to a source supporting
  the associated claim.
- **trust_tier**: A ranking of a source's authority/reliability used in ranking and FIDES
  verdicts.
- **study_id**: A stable external identifier for a source — PMID, DOI, or RXCUI.
- **Consensus_View**: An evidence-agreement summary showing how many sources support, contrast,
  or are neutral toward a key claim.
- **Citation_Registry**: The structured appendix listing every citation referenced in a report,
  with study_id, source type, trust_tier, and publication/effective date.
- **Golden_Set**: The curated Vietnamese golden question/answer evaluation set used by the
  quality harness.
- **Quality_Gate**: The automated evaluation gate that blocks regressions against defined metric
  thresholds.
- **Admin**: A user with role `admin`. Other roles are `normal`, `researcher`, and `doctor`.
- **Feature_Flag**: A configuration switch that enables a new behavior; all new behavior defaults
  to off.

## Requirements

### Requirement 1: Single Authoritative Tier2 Request Contract

**User Story:** As an API maintainer, I want one unambiguous Tier2 research request schema, so
that request validation is deterministic and no field is silently overridden.

#### Acceptance Criteria

1. THE Research_API SHALL define each field of the Tier2 research request
   (`ResearchTier2JobCreateRequest`) exactly once.
2. THE Research_API SHALL define `deep_pass_count` as a single optional integer field with one
   set of bounds (minimum 1, maximum 6).
3. WHEN a request provides a `deep_pass_count` value outside the bounds 1 through 6, THE
   Research_API SHALL reject the request with a validation error identifying `deep_pass_count`.
4. THE Research_API SHALL define `ui_language` exactly once, accepting only the values `vi` and
   `en`, defaulting to `vi`, and accepting the alias `answer_language`.
5. THE Research_API SHALL define `llm_runtime` exactly once with a single declared type.
6. WHEN a previously valid Tier2 request payload that conformed to the legacy contract is
   submitted, THE Research_API SHALL accept it and produce the same `request_payload`
   persistence behavior as before, except where bounds in criterion 2 reject it.

### Requirement 2: Durable, Owner-Isolated Uploaded Research Files

**User Story:** As a researcher uploading documents, I want my uploaded files to remain
available across restarts and workers, so that my research job can reliably use them.

#### Acceptance Criteria

1. WHEN a user uploads a research file, THE Research_API SHALL persist the file in durable storage
   that survives process restart.
2. WHEN a research job runs on any worker, THE Research_API SHALL make every uploaded file
   referenced by that job's `uploaded_file_ids` accessible to that worker.
3. THE Research_API SHALL associate each uploaded file with its owning user identifier.
4. IF a user references an `uploaded_file_id` that is not owned by that user, THEN THE
   Research_API SHALL reject the reference with an authorization error and SHALL NOT include the
   file content in the job.
5. WHEN a previously uploaded file is referenced after a service restart, THE Research_API SHALL
   resolve the file by its identifier without error.
6. WHEN an uploaded file is retrieved for processing, THE Research_API SHALL deliver the same
   content and OCR-bridge result that the existing upload path produced.

### Requirement 3: Role-Gated Research Telemetry

**User Story:** As a product owner, I want detailed research telemetry visible only to admins and
a sanitized summary shown to everyone else, so that internal pipeline details are not exposed to
end users.

#### Acceptance Criteria

1. WHERE the requesting user has role `admin`, THE Research_Web_UI SHALL display both the detailed
   research telemetry rail and the sanitized progress summary.
2. WHERE the requesting user has a role other than `admin`, THE Research_Web_UI SHALL display a
   sanitized progress summary that excludes internal pipeline labels such as "RAG mode" and
   "retrieval".
3. THE Research_Web_UI SHALL gate the detailed telemetry rail on the user role rather than on a
   localStorage flag.
4. WHEN telemetry is emitted to any client, THE Research_API SHALL exclude personally
   identifiable information from the telemetry payload.
5. THE Research_Web_UI SHALL preserve the existing `FLOW_STAGE_ALIAS_MAP` stage names for the
   sanitized summary.
6. IF role-based telemetry gating fails or cannot be evaluated, THEN THE Research_Web_UI SHALL
   deny all telemetry access.

### Requirement 4: Agentic Query Decomposition

**User Story:** As a researcher with a complex question, I want the system to break my question
into sub-questions, so that retrieval covers each part of the question.

#### Acceptance Criteria

1. WHERE agentic query decomposition is enabled by its Feature_Flag AND the research mode is deep
   or deep_beta, WHEN a research job runs, THE Research_Orchestrator SHALL decompose the query
   into an ordered set of sub-questions.
2. THE Research_Orchestrator SHALL execute retrieval for each generated sub-question.
3. WHERE agentic query decomposition is disabled, THE Research_Orchestrator SHALL execute the
   existing single-query plan behavior unchanged.
4. THE Research_Orchestrator SHALL record the generated sub-questions in the job telemetry.
5. IF query decomposition produces no sub-questions, THEN THE Research_Orchestrator SHALL fall
   back to retrieving against the original query.
6. IF telemetry recording fails, THEN THE Research_Orchestrator SHALL continue the research
   operation.

### Requirement 5: Iterative Gap-Fill Retrieval With Budget

**User Story:** As a researcher, I want the system to detect missing evidence and retrieve more
within a bounded budget, so that gaps are filled without unbounded cost.

#### Acceptance Criteria

1. WHERE iterative gap-fill retrieval is enabled by its Feature_Flag, WHEN the
   Research_Orchestrator detects a sub-question with insufficient supporting evidence, THE
   Research_Orchestrator SHALL perform an additional retrieval pass for that sub-question.
2. THE Research_Orchestrator SHALL limit the number of gap-fill retrieval passes to a configured
   maximum.
3. WHEN the configured gap-fill pass maximum is reached, THE Research_Orchestrator SHALL stop
   issuing further gap-fill passes and proceed to synthesis.
4. THE Research_Orchestrator SHALL record the count of gap-fill passes performed in the job
   telemetry.
5. THE Research_API SHALL enforce the configured gap-fill pass maximum externally and SHALL
   forcibly terminate gap-fill retrieval once the maximum is exceeded.

### Requirement 6: Recency and Trust-Tier Ranking Surfaced to the User

**User Story:** As a researcher, I want sources ranked by recency and trust tier and to see those
factors, so that I can judge the strength of the evidence.

#### Acceptance Criteria

1. THE Research_Orchestrator SHALL rank retrieved sources using both publication/effective date
   and trust_tier.
2. THE Research_Orchestrator SHALL include the trust_tier and publication/effective date for each
   surfaced source in the result payload.
3. WHERE two sources support the same claim, THE Research_Orchestrator SHALL order the higher
   trust_tier source ahead of the lower trust_tier source.
4. THE Research_Web_UI SHALL display the trust_tier and date for each surfaced source.

### Requirement 7: PICO-Structured Question Framing

**User Story:** As a clinician, I want clinical questions framed in PICO terms, so that the
synthesis addresses the population, intervention, comparison, and outcome.

#### Acceptance Criteria

1. WHERE PICO framing is enabled by its Feature_Flag AND the query is a clinical question, WHEN a
   research job runs, THE Research_Orchestrator SHALL produce a PICO structure identifying
   Population, Intervention, Comparison, and Outcome.
2. IF a PICO element cannot be determined from the query, THEN THE Research_Orchestrator SHALL
   reject the request with an error identifying the undetermined PICO element rather than
   fabricating a value.
3. THE Research_Orchestrator SHALL include the PICO structure in the result payload.
4. WHERE PICO framing is disabled, THE Research_Orchestrator SHALL produce the synthesis without
   a PICO structure.

### Requirement 8: GRADE-Style Evidence Certainty Labels

**User Story:** As a clinician, I want each key claim labeled with an evidence-certainty rating,
so that I understand how confident the evidence is.

#### Acceptance Criteria

1. WHERE GRADE labeling is enabled by its Feature_Flag, THE Research_Orchestrator SHALL assign
   each key claim an evidence-certainty label of high, moderate, low, or very low.
2. THE Research_Orchestrator SHALL derive each certainty label from the Evidence_Hierarchy and
   trust_tier of the supporting sources.
3. WHERE a synthesized item is a recommendation, THE Research_Orchestrator SHALL assign a
   recommendation strength of strong or conditional.
4. WHEN the Research_Orchestrator has assigned a certainty label to a key claim, THE
   Research_Web_UI SHALL display that certainty label, and SHALL NOT display a certainty label for
   a claim before a label has been assigned.
5. WHERE GRADE labeling is disabled, THE Research_Orchestrator SHALL produce key claims without
   certainty labels.

### Requirement 9: Evidence Agreement (Consensus) View

**User Story:** As a researcher, I want to see how many sources support, contrast, or are neutral
toward a key claim, so that I can gauge the consensus across the literature.

#### Acceptance Criteria

1. WHERE the Consensus_View is enabled by its Feature_Flag, THE Research_Orchestrator SHALL
   compute, for each key claim, the count of sources that support, contrast, and are neutral
   toward the claim.
2. THE Research_Orchestrator SHALL derive support, contrast, and neutral classifications from the
   NLI verification result for each source-claim pair.
3. THE Research_Web_UI SHALL display the support, contrast, and neutral counts for each key claim.
4. WHERE sources both support and contrast the same claim, THE Research_Orchestrator SHALL include
   a structured conflicting-evidence section that lists the contrasting sources.

### Requirement 10: Claim-Level NLI Verification With Surfaced Verdicts

**User Story:** As a clinician, I want each synthesized claim verified against its cited sources
with a visible verdict, so that I can trust which statements are supported.

#### Acceptance Criteria

1. THE Research_Orchestrator SHALL assign each synthesized claim a Claim_Verdict of supported,
   unsupported, or contradicted using the existing NLI verifier.
2. THE Research_Web_UI SHALL display the Claim_Verdict for each synthesized claim.
3. IF a claim is classified as a CRITICAL medical-safety claim AND its Claim_Verdict is not
   supported, THEN THE Research_Orchestrator SHALL block that claim from the delivered output via
   the existing FIDES/safety override.
4. THE Research_Orchestrator SHALL preserve the existing FIDES verdict-tightening behavior based
   on trust_tier and recency.
5. IF a query is out of scope for CLARA_Research, THEN THE Research_Orchestrator SHALL immediately
   halt all processing and refuse the query rather than perform retrieval or synthesis.

### Requirement 11: Claim-to-Study Traceability and Provenance

**User Story:** As a researcher, I want every synthesized claim linked to its specific supporting
citations with study identifiers, so that I can trace each claim to its evidence.

#### Acceptance Criteria

1. THE Research_Orchestrator SHALL link each synthesized claim to the specific citation or
   citations that support that claim in the production result payload.
2. THE Research_Orchestrator SHALL include, for each citation, a study_id (PMID, DOI, or RXCUI),
   source type, trust_tier, and publication/effective date.
3. THE Research_Web_UI SHALL render inline sentence-level citation anchors that link each
   synthesized claim to its supporting citation or citations.
4. THE Research_Orchestrator SHALL include a Citation_Registry appendix listing every citation
   referenced in the report.
5. THE Research_Orchestrator SHALL NOT emit a citation that does not correspond to a retrieved
   source.
6. IF a synthesized claim would have no supporting retrieved source, THEN THE
   Research_Orchestrator SHALL prevent that claim from being synthesized and SHALL NOT attach a
   fabricated citation.

### Requirement 12: Clarifying Questions Before an Ambiguous Deep Run

**User Story:** As a user submitting an ambiguous query, I want the system to ask clarifying
questions before running a deep job, so that the research addresses my actual intent.

#### Acceptance Criteria

1. WHERE clarifying questions are enabled by its Feature_Flag AND the research mode is deep or
   deep_beta, IF a submitted query is ambiguous, THEN THE Research_Web_UI SHALL present clarifying
   questions before starting the job.
2. WHEN the user answers the clarifying questions, THE Research_Web_UI SHALL include the answers
   in the research job request.
3. WHERE the user chooses to skip clarifying questions, THE Research_Web_UI SHALL start the job
   using the original query.
4. WHERE the submitted query is unambiguous, THE Research_Web_UI SHALL start the job without
   presenting clarifying questions.
5. WHILE a query is ambiguous AND the user has neither answered nor skipped the clarifying
   questions, THE Research_Web_UI SHALL NOT start the research job.

### Requirement 13: Progressive Disclosure of the Research Pipeline

**User Story:** As a user watching a deep run, I want to see the plan, retrieval, synthesis, and
verification stages progress, so that I understand what the system is doing.

#### Acceptance Criteria

1. WHILE a research job is running, THE Research_Web_UI SHALL disclose the stages plan,
   retrieval, synthesis, and verification in order via the SSE progress stream.
2. THE Research_Web_UI SHALL map disclosed stages through the existing `FLOW_STAGE_ALIAS_MAP`.
3. WHEN a stage completes, THE Research_Web_UI SHALL mark that stage as complete before disclosing
   the next stage.
4. THE Research_Web_UI SHALL apply the role-gating defined in Requirement 3 to the level of detail
   disclosed at each stage.

### Requirement 14: Role-Adaptive Output

**User Story:** As a user of a given role, I want output tailored to my role, so that I receive
the appropriate level of clinical and evidentiary detail.

#### Acceptance Criteria

1. WHERE the user role is `normal`, THE Research_Orchestrator SHALL produce plain-language output
   only.
2. WHERE the user role is `researcher`, THE Research_Orchestrator SHALL produce an evidence-pack
   output only that includes citations and evidence detail.
3. WHERE the user role is `doctor`, THE Research_Orchestrator SHALL produce an IMRaD-structured
   clinical brief only.
4. THE Research_Orchestrator SHALL default generated output to Vietnamese unless `ui_language` is
   `en`.
5. THE Research_Orchestrator SHALL include the decision-support disclaimer in every role's output.
6. IF the decision-support disclaimer is unavailable, THEN THE Research_Orchestrator SHALL deliver
   the output without the disclaimer and SHALL record the omission.

### Requirement 15: Consent-Gated, PII-Safe Personalization

**User Story:** As a patient, I want personalization to use my PHR and medicine cabinet only with
my consent and with my data protected, so that my health information stays private.

#### Acceptance Criteria

1. WHERE `personal_mode` is enabled AND the research mode is deep or deep_beta AND the user has
   granted consent, THE Research_Orchestrator SHALL incorporate the user's PHR and medicine
   cabinet into the synthesis.
2. THE Research_API SHALL reject any request that sets `personal_mode` while the research mode is
   fast, preserving the invariant "never (fast && personal)".
3. IF the user has not granted consent, THEN THE Research_Orchestrator SHALL run without
   personalization.
4. THE Research_API SHALL exclude PHR and medicine-cabinet personally identifiable information
   from telemetry and analytics payloads.

### Requirement 16: Research Report Export and Sharing

**User Story:** As a researcher, I want to export my research report and share a read-only link,
so that I can distribute findings with their citations.

#### Acceptance Criteria

1. WHEN a user requests an export of a completed research report, THE Research_API SHALL produce
   the report in Markdown, DOCX, or PDF as requested.
2. THE Research_API SHALL include the citations and Citation_Registry in every exported report.
3. WHEN a user requests sharing, THE Research_API SHALL produce a read-only shareable link using
   the existing workspace share mechanism.
4. WHERE a research report has not completed, THE Research_API SHALL reject an export request for
   that report.

### Requirement 17: Measurable Quality Harness and Regression Gate

**User Story:** As a quality owner, I want an automated evaluation harness with a Vietnamese
golden set and metric thresholds, so that enhancements never regress retrieval and synthesis
quality.

#### Acceptance Criteria

1. THE Quality_Gate SHALL evaluate CLARA_Research against the Vietnamese Golden_Set.
2. THE Quality_Gate SHALL compute recall@k, faithfulness, citation_accuracy, unsupported-claim
   rate, and refusal compliance.
3. IF recall@k falls below the legacy baseline recorded for the Golden_Set, THEN THE Quality_Gate
   SHALL fail.
4. IF the measured faithfulness, citation_accuracy, unsupported-claim rate, or refusal compliance
   breaches its configured threshold, THEN THE Quality_Gate SHALL fail.
5. THE Quality_Gate SHALL report each computed metric alongside its threshold.

### Requirement 18: deep_beta Report Section and Length Contract

**User Story:** As a researcher requesting a Pro report, I want the long report to meet its
section and length contract by generation, so that the report is complete without relying on
post-hoc padding.

#### Acceptance Criteria

1. WHERE the research mode is deep_beta, THE Research_Orchestrator SHALL generate a report that
   contains the sections required by the report section contract.
2. WHERE the research mode is deep_beta, THE Research_Orchestrator SHALL generate a report whose
   length meets the configured minimum word count (`DEEP_BETA_REPORT_MIN_WORDS`).
3. IF generated content does not meet the minimum word count, THEN THE Research_Orchestrator SHALL
   perform an additional generation pass for the deficient sections before applying any fallback.
4. THE Research_Orchestrator SHALL preserve the existing markdown naturalness sanitizers on the
   generated report.

### Requirement 19: Mobile Research Parity

**User Story:** As a mobile user, I want the Research screen to support deep research, so that I
can run and review research jobs from the mobile app.

#### Acceptance Criteria

1. THE Research_Mobile_UI SHALL allow a user to submit a research query in fast, deep, and
   deep_beta modes.
2. WHILE a research job is running, THE Research_Mobile_UI SHALL display progress using the SSE
   progress stream.
3. WHEN a research job completes, THE Research_Mobile_UI SHALL display the result including
   citations and SHALL keep the final progress display visible after completion.
4. THE Research_Mobile_UI SHALL apply the role-gating defined in Requirement 3 to telemetry
   detail, and IF role-gating fails, THEN THE Research_Mobile_UI SHALL block the research job.

### Requirement 20: Guardrail and Backward-Compatibility Preservation

**User Story:** As a safety owner, I want all existing medical-safety guardrails and current
behavior preserved, so that enhancements do not weaken safety or break existing flows.

#### Acceptance Criteria

1. THE CLARA_Research feature SHALL preserve the drug–drug interaction floor, the dosage/legal
   block, the consent gate, the emergency fast-path, and the FIDES CRITICAL block.
2. WHERE every new Feature_Flag is disabled, THE CLARA_Research feature SHALL behave as it did
   before this enhancement.
3. THE Research_API SHALL preserve the per-user active job cap of 5 and the global pending job cap
   of 200.
4. THE Research_API SHALL preserve the existing RBAC behavior for roles `normal`, `researcher`,
   `doctor`, and `admin`.
5. THE CLARA_Research feature SHALL retain the decision-support disclaimer indicating that outputs
   are not treatment orders and that CLARA-Care is not a medical device or EMR.
