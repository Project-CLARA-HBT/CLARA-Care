# CLARA Medical Answer Harness and Research Workspace Specification

Status: implementation baseline, 2026-07-22

## Product promise

CLARA is not a general-purpose chatbot with medical words added. It is a role-aware
medical reasoning workspace. Every useful answer is an inspectable artifact with an
urgency decision, explicit assumptions, evidence lineage, medication safety checks,
uncertainty, and a next action. The facts and evidence do not change by role; the
presentation and controls do.

The product has three simple entry points:

- **Ask CLARA (everyone):** understand symptoms, results, and medicines; identify
  urgency; prepare for a clinician visit.
- **Clinical view (doctors):** problem representation, cannot-miss diagnoses,
  ranked differential, discriminating questions/tests, medication reconciliation,
  and a reviewable assessment/plan.
- **Research workspace (researchers and clinicians):** reproducible PICO/PECO
  question, source plan, screening/extraction, evidence certainty, contradictions,
  and a versioned living review.

## Evidence and safety basis

The design follows WHO’s ethics and governance principles for AI in health and its
large multimodal model guidance: human agency, safety, transparency, accountability,
equity, and protection of privacy. It uses FDA clinical decision-support transparency
as the boundary for clinician-facing recommendations: the evidence basis must be
available for independent professional review. Research reports follow PRISMA 2020
reporting fields; outcome certainty uses GRADE domains (risk of bias, inconsistency,
indirectness, imprecision, and publication bias). Consumer language follows AHRQ
teach-back and CDC plain-language guidance.

Primary references:

- WHO, [Ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240029200)
- WHO, [Ethics and governance of large multimodal models](https://www.who.int/publications/i/item/9789240084759)
- FDA, [Clinical Decision Support Software guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software)
- Cochrane, [GRADE certainty of evidence](https://training.cochrane.org/handbook/current/chapter-14)
- PRISMA, [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020-checklist)
- AHRQ, [Teach-back](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/teachback.html)

## Medical Answer Harness

The request pipeline is a gated graph, not one prompt:

1. Normalize language, role, intent, age group, pregnancy, acuity, medicines, and
   whether the request is consumer education, clinical decision support, or research.
2. Extract a structured clinical state. Distinguish user-entered facts from model
   inferences and show missing high-impact facts.
3. Run a deterministic emergency/red-flag gate before retrieval or generation. An
   emergency result leads with urgent action and does not delay escalation for more
   questions.
4. Ask only high-information clarification questions that could change urgency,
   differential, medication safety, or the research protocol.
5. Resolve drugs to normalized ingredients/RxNorm identifiers and run deterministic
   DrugBank interaction, duplication, allergy, dose/unit, and patient-factor checks.
   Combine DrugBank with current labels and safety communications; never infer “no
   interaction” from a failed lookup.
6. Plan retrieval by claim type: official guideline/regulatory label, systematic
   review, primary study, trial registry, or patient education source.
7. Store an evidence snapshot. Each source has a stable identifier, title, publisher,
   publication/effective date, retrieval timestamp, study type, population, excerpt
   hash, and retraction/correction state.
8. Build atomic claims and a claim-to-evidence graph. Unsupported claims are labeled
   uncertain and cannot appear in decision-ready sections.
9. Synthesize a role-specific answer from the same verified facts.
10. Verify citation entailment, contradictions, dates, population applicability,
    dose/units, allergies, contraindications, and unsafe omissions. Repair or abstain
    when a gate fails.

Stable result contract: `medical_answer_v2` contains `audience`, `intent`, `urgency`,
`actions_now`, `actions_today`, `monitoring`, `red_flags`, `problem_representation`,
`differential`, `medication_safety`, `claims`, `evidence`, `contradictions`,
`assumptions`, `missing_information`, `uncertainty`, `follow_up`, and `run_manifest`.

Consumer output leads with “What to do now”, uses plain language, gives red flags,
safe self-care and “do not” actions, and ends with a teach-back question. It never
prescribes, starts, stops, or titrates prescription treatment.

Clinician output adds a one-line problem representation, cannot-miss diagnoses,
evidence-for/evidence-against differentials, discriminating tests, immediate versus
conditional management, medication reconciliation, and a copyable but explicitly
review-required SOAP/handoff artifact.

## Research workspace

Research is a persistent, reproducible workspace rather than a disposable answer.
The user can edit the question and PICO/PECO fields, select source families, attach
files, answer clarification questions, and inspect the live job stages. A run stores:

- protocol/question, inclusion and exclusion criteria;
- exact search strings, sources, timestamps, filters, and dataset versions;
- deduplicated records and screening decisions;
- extraction matrix (design, population, intervention/exposure, comparator, outcomes,
  follow-up, effect, funding, limitations);
- risk-of-bias and outcome-level GRADE judgments with reasons;
- claim passports, supporting excerpts, contradictory evidence, and applicability;
- export/share version and a “watch this question” update cursor.

The UI exposes four progressive surfaces: **Frame** (PICO and missing fields),
**Search** (sources and executable plan), **Synthesize** (claims, effects,
contradictions, certainty), and **Watch** (new trials, corrections, retractions,
guideline changes, and semantic conclusion diffs). A report is called a rapid
evidence summary unless the declared protocol and PRISMA fields are actually complete.

## Non-negotiable invariants

- Emergency cases bypass normal retrieval and are tested in Vietnamese and English.
- Critical DrugBank findings survive every answer renderer verbatim as deterministic
  safety findings.
- Each actionable claim has an evidence snapshot or is explicitly uncertain and
  suppressed from decision-ready sections.
- Personal records enter a model request only after current explicit consent and an
  on-screen context preview.
- Provider API keys are never accepted into or persisted in research job payloads.
- Role changes presentation only; they never change claim truth or citation support.
- Research jobs and events survive API restart, support cancellation, and represent
  actual work rather than elapsed-time placeholders.
- Degraded answers cannot look decision-ready.

## Target multi-agent medical architecture

This section defines the target architecture. It is a delivery contract, not a claim
that every component exists today. “Agent” means an independently testable bounded
worker with typed input/output and an explicit failure policy; it does not imply that
every worker needs a different foundation model.

### Components and responsibilities

1. **Run orchestrator:** owns the durable run state, dependency graph, deadlines,
   cancellation, retries, artifact hashes, and release decision. It cannot author
   clinical claims.
2. **Risk/router:** classifies emergency risk, audience, intent, jurisdiction,
   personalization consent, and required workflows. Deterministic emergency and
   medication floors remain active even when its LLM classifier fails.
3. **Context compiler:** converts the current turn, user-confirmed history,
   medicine cabinet, uploaded documents, and prior run artifacts into a
   provenance-tagged context pack. It excludes data that lacks current purpose-bound
   consent and never silently copies an inference into the facts partition.
4. **Dynamic protocol and prompt builder:** selects a versioned protocol, required
   agent graph, evidence hierarchy, output schema, specialty lenses, and prompt
   modules from the routed task. It composes prompts from reviewed modules; it does
   not accept arbitrary prompt text from retrieved documents.
5. **Task-specific RAG agents:** independently retrieve guideline/regulatory,
   systematic-review, primary-study/trial, drug/label, and user-document evidence.
   Each agent returns source records and errors, never answer prose.
6. **Evidence curator:** deduplicates, detects corrections/retractions, ranks against
   the original question, screens inclusion criteria, extracts study attributes, and
   produces an evidence set with explicit rejected-source reasons.
7. **Role and specialty synthesizers:** produce candidate claims and answer plans for
   consumer, clinician, researcher, and requested specialty lenses from the same
   curated evidence. They may differ in framing and depth, never in source truth.
8. **Critic and contradiction verifier:** independently tests claim entailment,
   numerical consistency, population applicability, missing cannot-miss items,
   guideline conflicts, and disagreements between synthesizers.
9. **Citation binder:** binds every releasable atomic claim to stable evidence IDs and
   exact support spans. It rejects dangling, fabricated, or merely topical
   citations.
10. **Safety/release adjudicator:** combines deterministic clinical floors with
    verifier findings. It releases, releases with warnings, requests clarification,
    escalates urgently, or abstains. It is the only component allowed to mark an
    answer decision-ready.
11. **Longitudinal memory service:** stores user-confirmed facts, preferences, and
    versioned artifacts in separate scopes. It never treats model-generated
    differentials, summaries, or inferred diagnoses as confirmed medical history.

### Typed contracts

The transport may use JSON/Pydantic/TypeScript, but the semantic contracts are:

```text
RunRequest {
  run_id, channel: chat|research|council, user_id, role, locale, jurisdiction,
  question, attachments[], requested_mode, specialty_lenses[],
  consent_grants[], client_capabilities, deadline_ms
}

ClinicalFact {
  fact_id, kind, value, unit?, effective_at?, status: confirmed|reported|inferred,
  provenance: user|record|document|tool|model, source_ref?, confidence?,
  consent_scope?, expires_at?
}

RouteDecision {
  audience, intent, acuity, emergency, required_agents[], prohibited_actions[],
  clarification_questions[], protocol_id, protocol_version, rationale_codes[],
  confidence, deterministic_floor_applied
}

ContextPack {
  facts[], inferences[], medicines[], allergies[], prior_artifact_refs[],
  attachment_refs[], exclusions[], token_manifest, consent_manifest, pii_manifest
}

RetrievalTask {
  task_id, claim_type, canonical_question, pico?, source_family,
  inclusion_criteria[], exclusion_criteria[], date_window?, jurisdiction?,
  max_records, timeout_ms
}

EvidenceRecord {
  evidence_id, stable_source_id, title, publisher, url?, study_id?,
  source_type, published_at?, retrieved_at, population?, intervention?,
  comparator?, outcomes[], support_spans[], trust_tier, relevance_score?,
  correction_state, content_hash
}

CandidateClaim {
  claim_id, text, claim_type, author_agent, evidence_ids[],
  population_scope?, certainty?, assumptions[], clinical_impact
}

VerificationFinding {
  finding_id, claim_id?, check_type, verdict:
    supported|partially_supported|unsupported|contradicted|not_applicable,
  evidence_ids[], severity, explanation, repair_instruction?
}

BoundCitation {
  citation_id, claim_id, evidence_id, support_span_hash,
  entailment_verdict, display_order
}

ReleaseDecision {
  action: release|warn|clarify|urgent_escalation|abstain,
  reason_codes[], releasable_claim_ids[], suppressed_claim_ids[],
  required_warnings[], human_review_required, policy_version
}

MedicalRunArtifact {
  schema_version, request, route, context_manifest, protocol_manifest,
  evidence[], claims[], findings[], citations[], release, answer_variants,
  safety_findings[], agent_runs[], run_manifest
}
```

Every agent response includes `agent_id`, `agent_version`, `prompt_bundle_version`,
`model_provider`, `model_id`, `started_at`, `completed_at`, `status`, `input_hash`,
`output_hash`, `warnings[]`, and structured `errors[]`. Unknown fields are additive;
removing or changing field meaning requires a schema-version migration.

### Durable state machine

The orchestrator permits only these transitions:

```text
created
  -> risk_routing
  -> awaiting_clarification | context_compilation | urgent_escalation
  -> protocol_compilation
  -> retrieving
  -> curating
  -> synthesizing
  -> verifying
  -> citation_binding
  -> release_adjudication
  -> released | released_with_warning | abstained | failed | cancelled
```

Emergency escalation is terminal for the normal answer path but may emit a short,
pre-approved urgent-action artifact. A failed retrieval agent does not fail the run
unless its source family is mandatory. A failed safety floor, citation binder, or
release adjudicator fails closed. Retries are idempotent by
`run_id + stage + agent_version + input_hash`; resumed runs reuse immutable completed
artifacts rather than regenerating them.

### Protocol, prompt, and version policy

- `protocol_id@version` declares the graph, mandatory source families, clinical
  floors, schemas, context budgets, release thresholds, and permitted fallbacks.
- A prompt bundle is composed from signed modules: role, task, jurisdiction,
  evidence-use, safety, output-schema, and specialty modules. Retrieved content is
  data-delimited and cannot override those modules.
- Production runs pin protocol, prompt bundle, model configuration, terminology
  dataset, DrugBank version, and evaluator versions in the run manifest.
- Prompt changes use semantic versions. Any safety, evidence hierarchy, tool-use, or
  output-contract change requires offline replay plus shadow evaluation; copy-only
  changes still require schema and safety smoke tests.
- The system stores prompt/module hashes and redacted inputs, not secrets or
  unrestricted chain-of-thought. Observable reasoning is represented as structured
  decisions, evidence links, and concise rationale codes.

### Context budgets and memory boundaries

Budgets are configuration values enforced before provider calls. Initial target
ceilings are:

| Surface | Total compiled context | Evidence allocation | Prior-memory allocation | Target answer |
| --- | ---: | ---: | ---: | ---: |
| Consumer Chat | 16k tokens | 6k | 2k | 1.2k |
| Clinician Chat | 24k | 10k | 4k | 2.5k |
| Research Fast | 48k | 30k | 4k | 4k |
| Research Deep | 96k per synthesis pass | 64k | 6k | 12k |
| Council | 64k shared pack; 20k per specialist | 36k | 6k | 6k |

The compiler reserves at least 15% for system/protocol instructions and 10% for tool
results and repair. It ranks evidence by claim coverage, authority, recency, and
diversity; truncation is recorded in `token_manifest`. It may summarize only after
preserving identifiers, numerical effects, contraindications, quoted support spans,
and uncertainty.

Memory scopes are `turn`, `conversation`, `workspace`, and `longitudinal`. Raw chat
content does not automatically enter longitudinal memory. Longitudinal writes require
an explicit user confirmation, purpose, retention policy, and a reversible audit
record. Consumer, clinician, and research workspaces are access-controlled views over
the same confirmed facts; Council receives only the minimum case context authorized
for that run.

### Parallelism, deadlines, and fallbacks

- Risk routing and deterministic safety checks start immediately; urgent escalation
  cancels nonessential retrieval.
- Independent RAG source-family agents run in parallel with a default concurrency
  cap of four. Specialty synthesizers may run in parallel only after the curated
  evidence snapshot is frozen.
- Target stage budgets: router 3 s, context/protocol 3 s, each Chat retrieval agent
  8 s, Chat synthesis plus verification 12 s, Research Fast 120 s total, Research
  Deep 10 minutes total, and Council 3 minutes total. Deployment configuration may
  lower these values but cannot remove release floors.
- Retry at most once for transient network/provider failure, with jitter and the same
  idempotency key. Validation, policy, authentication, and empty-evidence failures
  are not retried.
- Provider failure may switch to an approved secondary model only when the protocol
  records the change and reruns verification. Embedding failure may use attributable
  lexical retrieval; it cannot synthesize fake evidence. Missing mandatory evidence
  produces clarification or abstention, not a confident local-rule answer.
- Partial specialist or source failure is visible in the released artifact. Council
  cannot call silence “consensus”, and Research cannot call incomplete retrieval a
  systematic review.

### Anti-correlated failure controls

- Retrieval, synthesis, and verification have separate prompts, schemas, and
  credentials; the verifier does not receive the synthesizer’s hidden reasoning.
- At least two independent source families are required for high-impact claims unless
  an authoritative regulator/label is the sole appropriate source.
- Critical medication and emergency checks use deterministic curated data in
  addition to LLM review. LLM agreement cannot override a DrugBank or emergency
  floor.
- A verifier model should differ from the primary synthesizer by model family or
  checkpoint for high-risk releases. When unavailable, the result requires human
  review or abstains rather than presenting correlated agreement as validation.
- Evidence diversity is measured by publisher, study cohort, source family, and
  retrieval path—not raw citation count. Duplicate abstracts, mirrors, and
  guideline summaries do not count as independent confirmation.
- Canary contradictions, citation swaps, prompt-injection documents, unit conversion
  traps, and stale-guideline cases run continuously in evaluation and shadow traffic.

### Role UX profiles

- **Normal user:** one clear urgency banner; “what to do now/today”; plain-language
  explanation; medicine warnings; uncertainty; red flags; teach-back. Evidence is
  expandable, not an obstacle to the next safe action.
- **Doctor:** problem representation; cannot-miss diagnoses; evidence for/against;
  discriminating tests; medicine reconciliation; guideline applicability; provenance;
  a review-required note/handoff. Suppressed claims and disagreements remain visible.
- **Researcher:** editable protocol/PICO; exact searches; inclusion decisions;
  extraction table; risk of bias/GRADE; contradiction map; citation registry; run
  comparison and reproducible export.
- **Specialty Council:** shared case summary, per-specialty assessments, disagreement
  matrix, evidence links, missing-data requests, and named human override. A final
  recommendation displays whether it is deterministic, LLM-assisted, shadow-only,
  or human-confirmed.

All profiles use the same claim IDs, evidence IDs, release decision, and safety
findings. UI simplification must never delete a warning; it may progressively
disclose supporting detail.

### Observability, evaluation, and promotion

Stage telemetry records latency, deadline consumption, model/tool version, retrieval
yield, deduplication, evidence diversity, claim counts, entailment verdicts,
contradictions, citation binding, release action, abstention reason, and fallback
path. It excludes raw protected health information, provider secrets, unrestricted
prompts, and chain-of-thought. Traces correlate by `run_id`, `stage_run_id`, and
`evidence_snapshot_hash`.

Offline evaluation is stratified by role, language, specialty, acuity, age group,
pregnancy, renal/hepatic impairment, polypharmacy, and evidence availability. It
measures emergency sensitivity, unsafe-action rate, DDI recall, citation
precision/entailment, unsupported-claim rate, contradiction recall, evidence
diversity, calibration, PICO fidelity, GRADE agreement, readability, latency, cost,
and abstention appropriateness.

Promotion proceeds `development -> offline replay -> red-team -> shadow -> limited
canary -> production`. Zero-tolerance blockers are fabricated citations, a missed
curated emergency, release of a contradicted high-impact claim, loss of a critical
DrugBank warning, consent-boundary violation, or cross-user data leakage. Other
metrics require a non-inferiority confidence interval against the current production
baseline plus signed clinical/safety review. Rollback is automatic on blocker events
or sustained SLO regression.

### Mapping to CLARA and current gaps

| Target component | Current CLARA mapping | Status and gap |
| --- | --- | --- |
| Run orchestrator | Research durable jobs/events; Chat request pipeline; Council run history | **Partial.** No single durable typed DAG, shared cancellation model, or cross-surface idempotent resume contract. |
| Risk/router | Chat semantic medical-intent classifier plus deterministic emergency path | **Partial.** Routing exists, but protocol selection and specialty graph construction are not unified across surfaces. |
| Context compiler | Chat/session context, medicine cabinet/PHR hooks, Research uploads and source selections | **Partial.** No common provenance/consent/token manifest or strict facts-versus-inferences partition. |
| Dynamic protocol/prompt builder | Research query planner and mode profiles; existing role prompts | **Partial.** Prompt modules are not yet governed as one signed, replayable protocol bundle. |
| Task-specific RAG agents | Research scientific/web/internal/file connectors and source router | **Partial.** These are retrieval paths, not yet independently contracted agents with mandatory-source policies and isolated failure budgets. |
| Evidence curator | Deduplication/ranking, relevance gating, verification matrices, evidence snapshots | **Partial.** Retraction/correction checking, full study extraction, diversity accounting, and consistent rich-citation transport still need hard gates. |
| Role/specialty synthesizers | Role-adaptive Chat/Research output; Council specialist assessment path | **Partial.** Shared-claim multi-synthesizer comparison and specialty-specific evaluation are not complete. |
| Critic/contradiction verifier | Research quality gate, fact-check/NLI paths, contradiction summaries | **Partial.** Independent-model anti-correlation and uniform claim-level repair/recheck are not guaranteed. |
| Citation binder | Research citation registry/traced claims and API evidence snapshot | **Partial.** End-to-end invariant tests must guarantee citation count, identifiers, support spans, and metadata survive ML, API, persistence, export, and web rendering. |
| Safety/release adjudicator | Chat emergency/refusal controls, DrugBank-backed CareGuard, Research fail-closed quality gate | **Partial.** There is no shared release-decision contract or uniform human-review state across Chat, Research, and Council. |
| Longitudinal memory | Authenticated sessions, conversations, PHR/medicine cabinet, workspace persistence | **Partial.** Purpose-bound longitudinal write confirmation, expiry, provenance, and model-inference exclusion are not unified. |
| Council target | Case/run/stream/history/oversight surfaces; deterministic release recommendation with LLM specialist work available in shadow configuration | **Partial.** It is not yet a fully evidence-grounded, independently verified multi-agent medical council; shadow output must not be represented as the released clinical decision. |

Implementation order is: shared schemas and run manifest; orchestrator/state machine;
context and consent compiler; retrieval-agent contracts and evidence curator; claim,
critic, and citation binding; release adjudicator; role renderers; then longitudinal
memory promotion. Each slice remains behind feature flags until its evaluation and
rollback gates pass.

## Evaluation and release gates

Maintain role/language/specialty/acuity suites for emergency sensitivity, critical DDI
recall, contraindications/allergies, citation precision and entailment, freshness,
PICO fidelity, screening/extraction agreement, GRADE agreement, readability, and
abstention calibration. Fabricated citations, missed curated emergencies, and
contraindicated high-risk medication instructions are zero-tolerance deployment
blocks. Human-factors and post-release drift monitoring are required before expanding
high-impact clinical recommendations.

## Current implementation slice

This release fixes authoritative session/role hydration, restores reachable Research
routes, provides a real job-backed Research workspace with upload/source/clarification
controls, and exposes role-filtered tools from Chat. Existing API/ML research jobs,
source hub, DrugBank, citation, export, and share contracts are reused; no mock data
is introduced. Durable answer-run/evidence-snapshot persistence, deterministic
claim gates, worker recovery, and true token streaming remain tracked as the next
backend migration slice and must not be represented as complete until their gates
pass.
