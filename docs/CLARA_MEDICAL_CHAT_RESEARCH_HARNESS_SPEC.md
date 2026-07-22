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
