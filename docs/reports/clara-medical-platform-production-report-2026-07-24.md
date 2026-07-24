# CLARA Medical Platform — Production Implementation and Validation Report

Date: 2026-07-24  
Production: `https://theclaracare.com`  
Release under validation: `d17faff4` plus final citation/hydration patch

## Executive verdict

CLARA now has materially stronger medical evidence handling than the starting
system: scientific retrieval always executes when a deep plan requests it;
PubMed/Europe PMC records retain abstracts and trial identifiers; pivotal
primary trials are protected from degraded-ranker starvation; evidence claims
receive bounded LLM/NLI verification and repair; DrugBank is the required and
exclusive DDI authority; Scribe has a real ASR/SOAP lifecycle; and Chat carries
an explicit UI language into the safety fast path.

The system must **not yet claim benchmark superiority over ChatGPT, Gemini, or
other general LLMs**. That claim remains gated on held-out HealthBench/MIRAGE
results, statistical confidence intervals, and clinician review. Safe
abstention is a valid safety outcome, but is not evidence of clinical quality.

## Specifications and research basis

- `docs/CLARA_MEDICAL_CHAT_RESEARCH_HARNESS_SPEC.md`: multi-agent medical
  orchestrator, context compiler, evidence agents, curator, synthesizers,
  critic, citation binder, release adjudicator, and memory boundaries.
- `docs/design/clara-medical-benchmark-and-rollout-spec-2026-07-24.md`:
  benchmark arms, zero-tolerance safety gates, confidence intervals, rollout
  criteria, and rollback rules.
- `data/eval/clara-medical-benchmark-manifest.template.json`: reproducible
  evaluation manifest.

Primary research used for the design:

- OpenAI HealthBench: 5,000 multi-turn health conversations and 48,562
  physician-written rubric criteria.
- MIRAGE/MedRAG: retrieval-augmented generation benchmark across medical QA
  datasets.
- MultiMedQA: broad medical knowledge and safety evaluation.
- Stanford MedHELM: transparent, reproducible medical foundation-model
  evaluation.
- MedAgentBoard: evidence that multi-agent systems are not automatically
  superior to a strong single-agent baseline.
- WHO guidance for ethics and governance of large multimodal models in health.

## Implemented production changes

### Medical Research and RAG

- PubMed `efetch` hydration now carries full abstracts, PMID, DOI, NCT IDs,
  publication types, source type, and study design.
- Europe PMC now carries abstracts and equivalent scientific identifiers.
- Explicit deep scientific plans always invoke external scientific retrieval;
  an internal persistent hit can no longer suppress PubMed/Europe PMC.
- Evidence supplied to NLI is no longer truncated to a synthetic 180–240
  character fragment; grounded excerpts can extend to 2,400 characters.
- The verifier performs one bounded repair pass when claims omit references or
  exact quotes.
- Semantic-cache identity includes the retrieval plan, ranking policy, source
  policy, provider overrides, top-k, and embedding model/dimension. Uploaded
  documents bypass shared semantic cache.
- When embeddings fail, degraded ranking reserves verified primary trials
  before source round-robin selection and exposes scientific provenance to the
  LLM reranker. Primary RCTs are preserved through final aggregation.

### DrugBank and medicine manager

- Production DrugBank index is ready with version
  `drugbank-2026-07-03`, 1,428,193 interaction pairs, and a matching manifest.
- `CAREGUARD_DRUGBANK_REQUIRED=true` enforces DrugBank-only DDI conclusions.
- If DrugBank is unavailable, CLARA returns a typed no-conclusion state; it
  does not silently substitute local rules, RxNav, or OpenFDA.
- Allergy, emergency, renal/laboratory, and other non-DDI safety checks remain
  available during a DrugBank outage.

### Scribe

- API and ML have separate bounded transcription timeouts (180 and 150
  seconds).
- Blocking ASR work runs outside the async event loop.
- A valid no-speech result is HTTP 200 with `text=""` and
  `no_speech_detected=true`; upstream failures remain typed 502 errors.
- Session, consent, SOAP generation, review, sign, audit, and export are backed
  by real services and persisted records.

### Chat, auth, and frontend

- The frontend passes `ui_language` explicitly through non-stream and SSE Chat
  requests. The emergency safety fast path no longer guesses language with
  regex.
- Vietnamese and English emergency guidance, including `medical_answer_v2`
  actions, is localized consistently.
- Auth uses secure HttpOnly access/refresh cookies plus CSRF protection and
  refresh rotation.
- Protected product routes retain the application navigation, sidebar, and
  light/dark theme CSS markers after login.

### Council

- Council role gates and persisted run/history paths work end-to-end.
- The deterministic `rule_based_council_v2` remains the release authority.
  Specialist LLM agents remain shadow-only until clinician-reviewed benchmark
  gates pass. The UI/API disclose this rather than presenting shadow output as
  a clinical consensus.

## Production E2E evidence

| Feature | Result | Evidence |
|---|---|---|
| Auth/session | Pass | Register/login, cookie-only `/auth/me`, refresh rotation, protected routes |
| Login UX | Pass at HTTP/SSR level | Login remains a real form; no automatic jump into Chat |
| Chat emergency VI/EN | Pass | 200; 0.423 s VI, 2.222 s EN; `emergency-fastpath-v1`; correctly localized |
| Chat SSE | Pass | `start`, `step`, 24 token events, `done`; 200 in 0.875 s |
| Chat normal, idle | Functional pass with quality warning | 200 in 33.602 s; real model; 8 citations; no fallback; uncertainty still high |
| Chat normal, concurrent load | Fail | Dual 60 s ML timeouts caused safe fallback while Research/Scribe ran |
| Research external retrieval | Pass | PubMed and Europe PMC executed; external stage present in trace |
| Research evidence quality, first retest | Fail safely | 1/10 supported; pivotal RCTs starved before reranker; abstained |
| Research primary-trial remediation | Pass for retrieval/selection | Both pivotal RCTs entered LLM scoring, final context, and citations |
| Research answer release, final retest | Fail safely | NLI provider unavailable; 0/10 supported; quality gate abstained |
| DrugBank status | Pass | Ready, 1,428,193 pairs, manifest match |
| Cabinet CRUD | Pass | Create/update/list/delete |
| DrugBank positive DDI | Pass | Warfarin+ibuprofen and atorvastatin+amiodarone, DrugBank-only attribution |
| DrugBank negative DDI | Pass | Paracetamol+loratadine authoritative negative |
| DrugBank fail-closed | Pass | No external fallback and no DDI conclusion; other safety checks preserved |
| Scribe voiced WAV | Transport/contract pass | 200 in 18.220 s; non-empty transcript |
| Scribe silence | Pass | 200 in 11.107 s; typed no-speech contract |
| Scribe lifecycle | Pass | Create, consent, SOAP, review, sign, audit, export; policy 409 before signing |
| Council role/run/history | Pass | Researcher denied; doctor run and history work; release authority disclosed |
| Web routes/theme | Pass at HTTP/static level only | Protected redirects, SSR navigation/sidebar, light/dark CSS markers |

All E2E users, jobs, medicine records, Scribe sessions, tokens, and temporary
files created for this validation were deleted and their absence verified.

The final Research rerun took 267.501 seconds. Compared with the defective run,
both pivotal trials—PMID `32970396` (DAPA-CKD) and PMID `36331190`
(EMPA-KIDNEY)—entered the LLM pool, were selected, survived final aggregation,
and appeared in the surfaced citations. The editorial PMID `37529652` received
an LLM relevance score of 0.4 and was rejected below the 0.55 floor in the
successful pass. Final context increased from four to eight records and
citations from four to nine.

That rerun also exposed two availability failures: PubMed EFetch hydration
timed out and the LLM NLI provider was unavailable. CLARA therefore produced
0 supported / 10 insufficient claims and correctly withheld a medical
conclusion. The post-rerun patch now exposes PMID, DOI, NCT, source type, study
design, and publication types directly in citation payloads when present, and
gives the single bounded PubMed EFetch hydration call a 12–20 second budget.

## Known release blockers

1. **No benchmark superiority claim yet.** Official/held-out evaluation data and
   clinician adjudication are still required.
2. **Load isolation is insufficient.** One API worker and one ML worker on a
   3-vCPU/3.8-GB host allow deep Research/Scribe work to delay normal Chat.
   The target architecture needs separate interactive and batch worker pools,
   priority queues, admission control, and resource budgets.
3. **Embedding provider is intermittent.** The system now degrades safely and
   protects primary evidence, but a second independent embedding provider or a
   properly sized local biomedical embedding service is still required.
4. **ASR clinical accuracy is unproven.** Synthetic eSpeak audio validates
   transport and timeout behavior, not medical word-error rate. A labeled,
   human-recorded Vietnamese clinical set is required.
5. **Immediate access-token revocation is incomplete.** Refresh state is
   removed when an account is deleted, but an already issued stateless access
   JWT remains valid until expiry. A token-version/revocation check is required.
6. **Visual browser validation was unavailable.** Navigation, sidebar, and
   theme behavior passed SSR/static checks, but no claim is made for screenshot
   or cross-browser visual QA.
7. **Host storage is undersized.** The 33-GB root volume reached 99% during
   builds. Old rebuildable CLARA rollback images and build cache were removed,
   returning the host to about 92%; production should move to at least 64 GB.
8. **GitHub push is blocked.** Local Git has no GitHub credential, and the
   production credential lacks write permission. Production was deployed from
   a verified Git bundle and fast-forwarded to the exact local commit.

## Benchmark and rollout gates

The fair comparison uses the same backbone across:

- B0: direct ordinary LLM
- B1: medical system prompt
- B2: naive RAG
- B3: strong medical RAG
- B4: full CLARA harness

Primary datasets are HealthBench and MIRAGE, with PubMedQA and MedQA/MedMCQA as
secondary knowledge checks, dedicated medical safety suites, and a private
Vietnamese clinician holdout. Reporting must include bootstrap confidence
intervals, paired significance tests, worst-of-16 stability, citation
correctness, abstention calibration, latency, cost, and zero-tolerance safety
violations.

Promotion is allowed only when B4 beats the strongest same-backbone baseline
with statistically credible gains and no safety-gate regression. Until then,
the stronger multi-agent Council and autonomous release paths remain shadowed.
