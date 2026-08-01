# CLARA master implementation report

Status date: 2026-08-02. This report is evidence-first: it distinguishes
implemented code from planned, blocked and unmeasured work. It does not claim
clinical validation, a human evaluation, production deployment, or a benchmark
result that was not actually run.

Reconciliation checkpoint: this document was updated after the recent V4,
LifeMap, Research, Scribe, Council, CareGuard, deployment and i18n commits,
including `8bd27232` through `6bbefed4`. Per the current user direction, this
documentation-only checkpoint did **not** run format, lint, type checks,
tests, builds, evaluation or deployment. Earlier execution records below are
historical evidence only; they do not validate commits made after those runs.

### Follow-on operational hardening (2026-08-02)

`d0c0a29a` replaces the former CD behavior that started Compose and ran database
migrations on a GitHub runner. The controlled workflow now checks immutable
GHCR manifests, pins SSH host trust, transfers only a bounded release bundle to
the protected target, injects the target environment and GHCR token through SSH
stdin rather than command arguments, verifies a pre-migration Postgres backup,
runs migration and local smoke checks on that host, then records the prior
release and backup paths for a deliberate rollback. It checks the public CSP,
HSTS, frame/nosniff/referrer/permissions headers and the anonymous PHR viewer
route after target activation. The target environment must still be provisioned
with the documented GitHub environment secrets; this source checkpoint neither
ran a production deployment nor asserts that those protected inputs exist.

The subsequent security refinement scopes SSH, environment and GHCR secrets to
the individual CD steps that consume them. It also applies a package-lock
override that resolves Next's optional Sharp dependency to `0.35.3`; a fresh
production `npm audit --omit=dev` recorded one high (`postcss`) and one moderate
(`next` aggregation), down from three high before the override. The remaining
PostCSS 8.4.31 is an exact nested dependency of Next 15.5.22. The audit metadata
listed no compatible fixed Next version (its proposed version is 9.3.3), and
Next 16.2.12 still declares the same PostCSS pin. It remains a release blocker
until a compatible framework/vendor remediation or reviewed replacement exists;
it is not suppressed or reported as fixed.

The current source checkpoint closes a reproduced CSRF transport-confusion
case: a cookie session plus lowercase `authorization: bearer junk` formerly
skipped CSRF before RBAC treated the header differently and fell back to the
cookie. API now uses one case-insensitive Bearer parser at both boundaries;
only a valid, non-revoked explicit credential can receive the CSRF exemption,
and an explicit malformed Bearer credential never downgrades into cookie auth.
It also removes the root metrics `?token=` credential path.

The browser client no longer stores access or refresh tokens in memory or
sessionStorage, and no longer places them in streaming/API Authorization
headers. Login and refresh use the existing HttpOnly cookie pair; legacy
storage keys are purged at browser login/logout. API response token fields
remain for non-browser clients. Regression test sources cover the CSRF bypass,
lowercase valid Bearer handling, header-only metrics, legacy-token purge and
cookie-auth streaming paths. Per the feature-first instruction, this checkpoint
has not run formatting, lint, type checks, tests, builds, evaluation or
deployment; it is implementation evidence, not runtime validation.

`64e7eea5` adds the matching defense-in-depth policy to the maintained Nginx
virtual host: it removes upstream framework disclosure and emits the complete
browser header set even for proxy-generated responses. The controlled-deploy
runbook now requires an approved Nginx install/reload and external HTTPS header
smoke before this is considered active in production.

## Executive summary

This implementation pass strengthened CLARA's safety and evidence boundaries:

- added a typed, checksum-locked CLARA-Eval VN foundation and judge artifacts;
- added a typed Vietnamese/English catalog for the authenticated web shell;
- routed safety, LifeMap, Scribe and Council bounded LLM calls through typed
  model task contracts with a rollback switch;
- set the governed runtime configuration to DeepSeek V4 Pro and Flash task
  profiles, with deployment-time guards for an explicit Pro default, distinct
  Flash profile and task-routing switch;
- added an auditable Vietnamese clinical language pre-processing layer;
- added a structured wording renderer with an independent fidelity verifier and
  deterministic Vietnamese fallback;
- made Today start with the four consumer care tasks instead of requiring a
  person to navigate technical module names;
- removed Scribe's automatic code assignment (including fallback `R69`) and
  fabricated end-user “AI confidence” percentage;
- added consent- and version-bound Scribe clinician edits, a verifier gate for
  synchronous Research results, a governed V4 LifeMap ask path, and a Council
  client boundary which withholds reasoning traces.
- removed the remaining production runtime model/provider configuration seam
  from Research and Control Tower: those paths now reuse the registry-built
  task client and ignore historical `llm_runtime`/`llm_*` JSON keys;
- strengthened a strict CareGuard rollout so a full DrugBank release is
  authoritative only when its mounted manifest, SQLite index and dictionary
  counts match; and
- expanded catalog-backed Vietnamese/English wording across login/onboarding,
  Research, Community, Scribe, administrative RAG, and the corresponding
  Unified/Redesign mobile journeys (chat, profile/PHR, evidence, connected
  health, community, Settings and More);
- added a generated web/mobile consumer-terminology contract, localized the
  Council setup/review/result journey and the guided medicine-entry flow, and
  extended the Unified mobile LifeMap flow through capture, replay, review,
  question and baseline steps;
- preserved the requested UI locale when the normal clinical-answer path
  builds its independently verified structured explanation;
- excluded records explicitly marked retracted by external Research sources
  before they reach the RAG evidence set; and
- added a read-only comparison of immutable LifeMap revisions. It does not
  mutate truth-state, provenance, confirmation state or revision history.
- localized the fixed mobile CareGuard DDI result chrome and the web
  medication-consent gate. These presentation changes do not rewrite clinical
  alerts, change DDI risk, alter DrugBank data or relax consent gating.
- localized the web manual medicine-cabinet entry and the remaining Enterprise
  Scribe consent/transcript, note/sign/export, grounding review,
  coding/addendum and process-status chrome, alongside the corresponding
  redesigned-mobile Scribe consent, transcript-action and session-management
  chrome. These are catalog/presentation changes only: clinician confirmation
  of coding, signed-note immutability, consent gating, transcript provenance
  and backend payloads remain unchanged.
- added additive, locale-neutral Family access-log actor/action/outcome codes
  while retaining the legacy actor label and raw audit fields for released
  clients. Web and mobile now render the bounded codes through their own
  catalogs, with safe legacy fallbacks; the owner/profile-scoped query and
  append-only audit ledger did not change. Family Circle now also replaces raw
  mutation/load errors with its localized generic error states; and
- corrected the mobile Settings transparency row so it describes governed
  DeepSeek V4 Pro/Flash task routing instead of falsely implying that every
  task used Pro. Per-response disclosures remain sourced from the API envelope.
- added an owner-scoped, source-version-bound DrugBank clarification path across
  ML, API, web and mobile. A terminal ambiguity has no DDI conclusion, cache
  projection or local identity inference; and
- exposed the capability-gated, read-only LifeMap visit-preparation draft in
  web with revision citations, uncertainty and a no-write disclosure. The
  guided prescription/OCR flow, Research workspace, Chat shell and a bounded
  legacy Chat workspace region are now catalog-backed in both supported UI
  languages; and
- added a conservative End_User error boundary that renders a caller's
  localized fallback instead of technical/upstream caught-error detail across
  recently migrated consumer flows; and
- extended typed-catalog wording to legacy Chat action/notice/confirmation
  copy and the Council workspace, flow canvas, oversight and dashboard chrome.
  The Council timeline keeps its safety/review determination on raw step
  identifiers rather than translated display labels. This
  does not translate dynamic clinical content or establish all-surface i18n;
  and
- extended that conservative boundary to operator-facing Control Tower, RAG
  administration and Ecosystem Monitoring: caught transport/upstream errors
  render typed generic fallbacks, while known operational status labels and
  locale number/date formatting are catalog-backed. Structured successful
  operational data remains unmodified.

The repository already contained significant LifeMap, CareGuard, Council,
Research and mobile work. The work above integrates with those safety
boundaries without weakening RBAC, consent, CSRF, emergency handling, FIDES,
no-PII telemetry or LifeMap confirmation/provenance rules.

## Current and target architecture

Current request flow remains Web/Mobile → API → ML. Deterministic policy owns
authorization, consent, state transition, audit, emergency fast-path, final
DrugBank DDI authority and confirmed LifeMap writes. The new target selection
boundary is `clara_ml.llm.model_registry`: a bounded task resolves to the
configured DeepSeek V4 Pro or Flash profile, a versioned prompt/output contract
and a safe fallback. `DEEPSEEK_MODEL` is guarded to the Pro profile; Flash is
for contract-approved bounded work. No end-user request selects a provider or
model. These are repository/runtime-config changes only: no production
environment or provider availability was verified in this checkpoint.

The Vietnamese language layer retains its deterministic baseline and now has
an optional registry-governed V4 Flash source-span augmentation. It accepts
only checksum-bound closed categories and Unicode offsets, validates them in
application code, fails soft to the baseline and emits only categorical/count
projections. It is not an evaluated neural clinical model. Semantic LLM
classification remains bounded to closed JSON and is followed by deterministic
safety policy.

## PR/checkpoint summary

| PR                              | Status                                | Evidence / limitation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PR-01 Audit/ADRs                | implemented                           | Architecture inventory, ADRs and master ledger: `919b8ba7`; static active-eval baseline is NO-GO (`442c85e5`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| PR-02 i18n                      | partial                               | Typed vi/en catalog now covers the authenticated shell, auth/onboarding, Today, consumer chat, consent (including the Medicines medical-consent gate), LifeMap review and focused multi-step LifeMap and Visit creation, Medicines (including guided and manual cabinet entry), Living Evidence, Research/source hub, Community, Scribe and its Enterprise consent/transcript, note/sign/export, grounding, coding/addendum and process panels, Council setup/review/result and administrative RAG web flows. The browser locale is mirrored to a SameSite language cookie and the root layout reads it for server-rendered document language, with Vietnamese retained as the fallback. Focused Chat V2 checkpoints move researcher/doctor welcome prompts, Workspace Drawer notes/shares/export copy, Command Palette chrome, Medical Answer Canvas labels/empty states, Answer Renderer research-integrity/citation chrome, the Flow Timeline heading, Message Log ARIA chrome, Turn View error/research action chrome, admin-only Telemetry Panel chrome, and all Chat Shell notices/commands/ARIA/navigation chrome into the typed catalog; share expiry uses the shared locale date formatter and all ten focused routes have narrow CI contracts. `4972eeca`, `263332a2`, `4afabf66`, `979a4c67`, `6f9ba2f0`, `a5dd64a6`, `003873f4`, `2cbf5a3b` and `c88e42cb` complete static user-facing catalog copy in the legacy Chat rollback surface; the direct locale branch left there is only time formatting. `86f45eae` shares typed Chat V2 day buckets; `b117e534` covers the Council oversight dialog; and `a091c197` covers Research Markdown export, code/chart/Mermaid state and citation controls. `5cb5cbf3`, `a58186d0`, `c68b9927` and `fe531c5b` extend the same typed catalog to legacy Chat action copy and Council workspace/flow/oversight/dashboard chrome; the timeline classifies from raw deterministic identifiers before rendering translated labels. `4f91a333`, `1abbd400` and `33a0c309` add safe typed fallbacks for operator error states and locale-aware Ecosystem chrome, without translating or mutating structured operational data. The remaining navigation catalog checkpoint makes labels, descriptions, page metadata, group labels, mobile drawer copy, feature-gated privacy destinations, and unknown/special page fallbacks change together between vi/en. This does not claim all mobile/domain strings are migrated. Static strings and other web/mobile domain surfaces remain; no fresh verification was run. |
| PR-03 task-first UX             | implemented primary journey           | Web and Unified-mobile Today now begin with four consumer tasks: ask about a health concern, check a medicine, save health information, and prepare for a visit. The mobile cards open the existing consent-gated Chat, Medicines, PHR and Visits surfaces and cannot create or confirm data by themselves. Web Visit creation is now split into name, purpose, time and final review; draft values stay local and the only create call is the explicit final action. The follow-up visit selection first verifies that the returned identifier is in the owner-scoped list. Family invitations now use the same recipient → owner-scoped item → purpose → final-review progression; the sole create call comes after review, and the returned one-time code stays off URLs. On web and Unified mobile, recipient acceptance first invokes a non-mutating, recipient-bound preview that returns only scope category/actions/purpose/expiry; the separate accept is still the only grant write and the preview neither consumes nor audits the capability. On mobile the code is confined to the temporary input controller, is cleared before successful route exit and does not return to the parent. The Medicines list sends new entries to the existing guided creation route and retains only an explicit versioned correction form for an already selected course; its non-persisted DrugBank-ID correction input was removed. Research/evidence remain deep-link-compatible but no longer crowd personal navigation. Dense legacy surfaces remain; the new mobile widget/API contract coverage is added but not run in this checkpoint.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| PR-04 registry/contracts        | implemented for bounded tasks         | Safety triage, LifeMap capture/visit/ask, Scribe, Council shadow, RAG reranking/NLI, RAG synthesis and Research planning/reasoning use registry task contracts. `8bd27232` removes the explicit Research/RAG runtime override seam and ignores historical Control Tower/provider JSON keys, so request payloads and queued jobs cannot select a provider, endpoint, model or key. `32afb304` removes the remaining RAG compatibility helper/client-construction dead path; the historical runtime payload is now discarded before generation. The Research Tier2 planner, reasoning and deep-beta constructors now likewise discard their compatibility-only runtime payload and call the registry with deployment settings, blocking payload-selected provider, endpoint, credential, model, retry policy and timeout. `59e63b90` makes the optional external Encoder-SLM shadow adapter resolve exclusively through its closed, shadow-only registry contract. The governed configuration routes V4 Pro to safety/reasoning and V4 Flash to bounded extraction/reranking/planning; `6399e054` aligns code/sample/compose fallback defaults on `https://api.yescale.io/v1`, without claiming provider availability. Deployment validation requires the distinct profiles, DeepSeek-only mode and task routing. `04aa0095` corrects the mobile Settings disclosure to describe the governed Pro/Flash route rather than claim Pro for every task; actual-response chips still use the API disclosure. `1f90fc0f` removes unused Qwen installer defaults; the ASR boundary now uses a separate registry-owned audio contract (`whisper-1` default) and allowlisted provider route rather than falsely reporting Flash or sending audio to a V4 text model. `136214df` makes the generic text task builder unable to acquire an audio endpoint; audio construction must use the dedicated ASR builder. Task contracts now apply their declared temperature and token ceiling at the client boundary; Research's long-report contract explicitly raises its documented ceiling to 12,288 and has prompt version `research-reasoning.v2`. `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` restores the legacy single configured DeepSeek model, while explicit rollback selects a known prior model. Runtime deployment remains unverified.                                                                                                                                                                                                                      |
| PR-05 Vietnamese clinical layer | partial hybrid                        | `1f16c7c6` adds normalization, typo handling, negation, experiencer, temporality, units and medication aliases; `70cc2877` expands the deterministic fallback clinical-language layer. The current checkpoint adds `CLINICAL_LANGUAGE_EXTRACTION`, a registry-governed V4 Flash task that may return only checksum-bound, closed-category Unicode source spans. Application code validates all spans and fails soft to the deterministic packet. It is used only after chat/Council emergency handling, projects categorical/count metadata without source text, and has no evaluated encoder/clinical benchmark.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| PR-06 hybrid router             | partial                               | The primary chat semantic boundary now parses the provider response through an extra-forbidden Pydantic decision contract instead of releasing a free dictionary. It carries only action/reason/emergency/task/bounded confidence and registry-owned model identity; it cannot contain clinical prose, provider rationale, authorization or a treatment decision. Emergency output enters the deterministic fast path, and malformed/extra output falls back to deterministic emergency/legal policy. Safe chat intents and LifeMap ask requests have governed V4 task paths, but deterministic emergency/legal policy remains authoritative. `clara_ml.model_router` supplies a typed metadata-only shadow route; the external Encoder-SLM is still default-off and cannot alter a deterministic emergency/legal outcome, authorization, consent, DrugBank or confirmed LifeMap write. An evaluated encoder/SLM classifier is not installed; source tests were added but not run.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| PR-07 renderer                  | implemented deterministic baseline    | Structured input, audience templates, independent fidelity verifier and deterministic Vietnamese fallback are integrated into `medical_answer_v2`. `fba3e639` preserves the selected UI locale in the normal response path as well as the emergency path. A reviewed human-usability score remains unmeasured.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| PR-08 CareGuard                 | partial/pre-existing                  | DrugBank SQLite readiness/fail-closed path exists. `d12d15e0` requires source release/hash, canonical manifest digest, per-shard checksums and matching DDI **and** dictionary table counts before a strict full release is authoritative; deterministic Vietnamese alias matches expose DrugBank/RxCUI traceability without guessing. A one-time web `medication_text` path is capped at 2,000 characters and uses deterministic Vietnamese clinical extraction plus exact local dictionary/DrugBank alias candidates only; it never lets an LLM select identity, does not save to a cabinet/PHR or cache an output, and returns a terminal no-conclusion clarification on any unresolved/ambiguous/invalid text. The current checkpoint adds an independent default-off span-augmentation switch: V4 Flash can nominate only exact original medication substrings, then the existing deterministic Vietnamese/DrugBank resolver remains the sole source for canonical names, DrugBank IDs and DDI facts. The separate `CAREGUARD_MEDICATION_CLARIFICATION_ENABLED` gate rebuilds the licensed index as a candidate-aware schema, rejects a first-record-wins collision, and returns a terminal source-backed choice task before any DDI risk/recommendation/all-clear. API binds the choice to the owner-scoped cabinet item and cleaned raw alias; ML revalidates alias, DrugBank ID and current artifact version. The UI never caches or projects that terminal state as a DDI result. Feature-flagged wording remains downstream of final facts. Licensed full-DrugBank benchmark data is unavailable in this checkout; the new ML/API/web contract tests are unrun.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| PR-09 Scribe                    | implemented safety correction in code | `eaa749c0` removes automatic code/R69 and uncalibrated percentage. `0c6b268d` additionally requires consent for clinician-edit mutations and applies version-aware edit conflict handling. The ASR payload model is separately fail-closed and never reported as V4 Flash. Medical-ASR correction now requires model-declared exact Unicode transcript offsets and rejects an ambiguous/unbound token instead of binding its first textual occurrence; the Enterprise UI consumes both batch and stream candidates only as read-only review text and contains no replacement callback or apply control, so a clinician must edit the transcript independently after source review. The selected-session recording-derived data flow now reads an owner-scoped capability endpoint tied to the existing default-off `RAG_SCRIBE_RECORDING_DATA_DELETION_ENABLED` switch, renders no destructive control on rejection, requires explicit confirmation, waits for started browser transcript saves, then clears and re-reads session truth. It deletes only persistent transcript/ASR-diarization metadata; raw audio is not stored and signed notes/audit history are retained. The focused client and UI-invariant tests are added but not run in this checkpoint.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| PR-10 Council                   | partial                               | Structured intake, specialist/shadow and ablation paths exist; fixed-weight heuristic does not drive deterministic triage and the consumer UI no longer presents it as neural or as a percentage. Non-emergency transcript consultations may now expose the optional clinical source-span packet only as review-required intake metadata; it is never merged into Council clinical facts or used by the specialist/adjudication path. The Council Research-snapshot path is now end-to-end but shadow-only: a doctor explicitly chooses a completed snapshot owned by that account, API maps only allowlisted citation provenance to an append-only attachment of opaque IDs/categories, and each run revalidates the attachment before internal injection. It rejects all client-built packets and never sends source prose, query text, result prose, title, URL or score to Council; the selected packet cannot support a finding or alter deterministic triage. API and ML both require `COUNCIL_EVIDENCE_PACKET_SHADOW_ENABLED=true`; turning it off and restarting both hides selectors, prevents attachment writes/injection and restores the legacy path. The default-off API disclosure seam now persists only validated model provenance (`model_family`, `model_version`, `is_fallback`), explicitly reports missing provenance as `unknown`, and rejects upstream prompt/confidence fields. The independently default-off `COUNCIL_MEDICATION_SAFETY_ENABLED` path calls CareGuard with strict DrugBank required and external DDI disabled, projects only bounded state/version/opaque alert identifiers, never enters an LLM packet, and can only raise urgency or require review. The nested `COUNCIL_SPECIALIST_WORKFLOW_SHADOW_ENABLED` gate now projects the existing LLM shadow through five code-owned specialist profiles, strict V5 fact-ID-bound JSON, a deterministic independent verifier and a monotonic adjudicator. Its output is explicitly `none_shadow_only`: it cannot lower or write back triage, clear review, change facts/recommendations, or affect access state. Disable either Council shadow flag and restart ML to roll it back. Source contracts are added but unrun; these changes do not establish clinical specialist evaluation.                                                                                                                                                                                                                                                                                  |
| PR-11 Research verifier         | partial/pre-existing                  | Claim/citation tracing and research-quality harness exist. `9ce7d6d3` makes synchronous Research responses pass the verifier gate before release. The release gate now requires a structurally valid, explicit verifier state/version/summary/rows contract for any factual answer: missing, malformed, unavailable or skipped verification produces a safe abstention even if citations are present. Chat V2 consumes only a bounded API-owned passed/reason projection and explains a withheld conclusion with localized allowlisted reason codes; it never exposes verifier rows, provider errors, prompts, PII, confidence, or a fake GRADE label. The default-off reader-mode path requires API and ML acknowledgement plus a build-time web control: its closed plain/professional selector is non-generative, role-limited, and API attaches it only after the existing gate passes, referencing unchanged released markdown and citation identifiers. A withheld conclusion receives no presentation payload. `9f71e9fd` filters explicitly retracted external records before final RAG evidence selection. The former watermark-backfill skeleton now lazy-composes the existing source registry and ingestion orchestrator only after both `RAG_INGESTION_ENABLED` and the independent default-off `RAG_BACKFILL_ENABLED` switch pass; a sanitized per-source failure does not stop independent sources. Focused reader-mode contracts are present but unrun; a reviewed RAG gold set and current regression execution are absent.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

| PR-12 LifeMap | partial/pre-existing | Revision/provenance/capture review and Vietnamese locale support exist. `6294386d` adds a governed V4 LifeMap ask path that is read-only and retains the existing confirmation/truth-state boundary. The consumer Ask surface now provides four task-first Vietnamese/English timeline/change/missingness/visit prompts and displays the routed search purpose plus uncertainty in plain language, without a new API/model call or any mutation. `47162ccc` adds a read-only comparison between immutable revision snapshots, without modifying source revisions or truth-state. The optional `LIFEMAP_TEXT_DRAFT_EXTRACTION_ENABLED` route now uses a registry-owned V4 Flash task to classify only exact source spans into closed-category, review-only `text_draft` candidates; API reconstructs phrases from user text, preserves an internal source row and maps explicit confirmation back to the existing `text` event. The separately default-off `LIFEMAP_REVIEW_MODEL_PROPOSALS_ENABLED` route accepts only a bounded packet of already consented/profile-scoped active revisions, calls the V4 Flash registry task, validates exact same-field revision-ID pairs again in the API, and persists only append-only `model_proposal` findings requiring human resolution; it cannot write an event, revision or truth-state and falls back to rule findings on every failure. Capture UI now reports source ambiguity as a review instruction rather than exposing an uncalibrated confidence assertion. The existing deterministic summary and Vietnamese visit-preparation endpoints are explicitly configurable in both API compose variants, remain default-off, consent-gated/profile-scoped and cannot mutate truth-state. Its API/ML tests are added but not run. Broader NL-query/visit-summary evaluation needs approved cases. |
| PR-13 CLARA-Eval VN | implemented foundation | `0b103426`: nine tracks, suite configs, manifests, smoke/nightly/release/judge artifacts and CI integration. `59722a20` adds metric-specific evidence gaps and exact measurement commands for all six judge headlines. `cb2eb1e0` keeps `confidence-intervals.json` aligned to real observation state and replaces critical-error/Council-ablation placeholders with observed rows, so zero is never confused with absent measurement. Product quality metrics remain `not_measured` until approved data/execution exists. |
| PR-14 security/ops | partial | The locked release workflow now materializes a separately approved release manifest only under `RUNNER_TEMP` and requires it to match the locked dataset reference, resolved immutable release SHA and retrieval snapshot before any live request; artifacts retain only a dataset-reference hash and release SHA. Release remains fail-closed on missing/mismatched evidence. Security checkpoints upgrade Axios and its HTTP/form transitive closure, Next 15.5.22, Mermaid 10.9.6, DOMPurify 3.4.12, UUID 14.0.1 and Playwright 1.62.0. `012e0b5b` wires Scribe stage flags, ASR controls, Encoder-SLM shadow controls and CareGuard wording controls into both application compose variants instead of relying on `--env-file` substitution alone; its environment guard also rejects an unprovisioned strict DrugBank mount. `1b0a394f` propagates the API Scribe timeout budget to production compose so it exceeds the default ML ASR budget. The existing guard rejects a deployment environment that lacks the exact governed `deepseek-v4-pro`/`deepseek-v4-flash` configuration, DeepSeek-only mode or enabled task routing; an operator uses the dedicated rollback variables rather than replacing those defaults. A separate `MODEL_ROUTING_OBSERVABILITY_ENABLED` switch defaults off and makes the registry expose only bounded aggregate task/profile/version/risk/rollback selection evidence to protected metrics; it retains no raw model name, prompt, input, output, URL, identifier or credential and is not evidence of invocation success, cost or clinical quality. `f612e2b5`, `4f91a333` and `1abbd400` prevent raw caught transport/upstream errors from becoming end-user or operator-copy in their bounded flows. CI now requires web Vitest and production-artifact Playwright E2E gates when web/CI changes; the local production-dependency audit historical record decreased from 11 (7 high, 4 moderate) to 3 high, all in the Next/PostCSS/Sharp chain without a compatible audit-proposed fix. Restore/security certification evidence, current scan results and the remaining dependency remediation remain external/ongoing work. |
| PR-15 mobile parity | partial/incremental | Unified mobile, locale wiring and consent paths exist. In addition to the shell/Profile hub locale checkpoints, catalog work covers onboarding, chat, LifeMap planning/capture/replay/review/questions/baselines and static dispute-queue chrome, Medicines hub/cabinet, fixed CareGuard DDI result chrome, Visits, Family/visit detail and access-log rendering from backward-compatible stable API codes, PHR, living evidence, connected health, community, Settings and More. The redesign shell resolves navigation labels and its primary Chat action from `LanguageController` plus the shared consumer terminology. Its first screen now localizes the already-existing Chat, medicine-safety and profile task cards plus Tools/Recent/error chrome; it deliberately adds no Visit callback/card and does not claim downstream screen migration. Login V3 now also binds to the same language controller, localizes all static/assistive validation copy, and maps authentication failures to generic locale-safe messages instead of raw API detail. The recipient Family acceptance flow now makes the server's non-mutating preview visible before its independent accept write. The invitation capability appears only in a temporary masked input and header, never in a URL, route argument, local storage, log or parent state; errors deliberately do not reveal its state. The LifeMap dispute queue leaves server-provided event type, revision, status and the clinical-review boundary unchanged; localization covers only the static consumer UI around it. Unified-mobile Today now has real task-first routes to Chat, Medicines, PHR and Visits. The server-authoritative `lifemap_vietnamese_drafts` capability now switches the latter to a localized, read-only/copy-only preparation draft; an unavailable capability leaves the established Visit lifecycle unchanged. The draft only calls the consent-gated, profile-scoped endpoint and never creates a Visit, event, task, revision or confirmation. Its focused callback/widget coverage is added but not run. `01ae02a4` adds focused API contract assertions for the Family codes, but they were not run. `fca5fba9` provides a generated shared consumer-terminology contract rather than claiming a fully shared UI catalog. Device E2E execution and fresh verification of these commits remain outstanding. |

`74e2c075` repairs the static i18n gate's typed-English catalog parsing and
derives the mobile resolver mapping from every canonical terminology key. These
are CI contract improvements only; no device rendering or all-surface scanner
claim is made.

The subsequent `5cb5cbf3` checkpoint further catalogizes static legacy Chat
action, notice and confirmation wording, plus Council Workspace navigation,
headings, citation fallback and empty-state copy. It changes no dynamic user,
API or clinical content, and no Council facts, triage, prompts, specialist or
adjudication outputs, or access controls. PR-02 and PR-10 therefore remain
**partial**, not evidence of whole-app i18n or clinical Council validation.

`de590313`, `a7a274ca` and `7e57d3ba` add and extend a conservative
`safeUserFacingError` boundary in consumer flows. Technical, malformed,
timeout-like or oversized caught-error detail is replaced with the existing
localized generic fallback; request semantics, logging, authorization and
clinical results are unchanged. This is source-level End_User error hardening
under PR-14, not a fresh security, PII or runtime-validation result.

## Latest implementation checkpoints

- The `/huong-dan` task guide now resolves its complete static task, step,
  action and label copy through the typed vi/en catalog and reacts to the
  persisted UI locale. This is a bounded consumer-surface migration, not a
  claim that all remaining web/mobile strings are localized.
- PHR OCR imports now require medical-disclaimer consent before upload and
  confirmation, fail closed on the existing OCR prompt-injection screen, attach
  reviewable corrected-text offsets, and return a short-lived owner-bound review token.
  The web modal requires explicit acceptance for every retained candidate;
  scan output never commits a medication. Those bounded offsets appear only in
  a collapsed source-reference control and are stripped before confirmation.
  Its complete user-facing copy now
  uses the typed vi/en catalog instead of a component-local bilingual map. The
  token contains only opaque candidate IDs, not OCR text, and supports
  discarding candidates. This source checkpoint has not run tests, build or
  deployment.
- The PHR read-only share manager, FHIR export control, emergency-card field
  selector and medication-reminder panel now resolve their scopes, statuses
  and safe errors through the same typed vi/en catalog. This does not change
  the server-enforced sharing-consent, capability, expiry, revocation,
  owner-scoped export, emergency-card data or medication-reminder boundary.
- The guided personal-data deletion route now resolves its three steps,
  consequences, irreversible-action acknowledgement, receipt/status and safe
  errors from the typed vi/en catalog. Receipt timestamps now use the selected
  application locale rather than an uncontrolled browser default; the final
  DSAR mutation remains separately explicit and CSRF-protected.
- The RBAC-protected admin DSAR queue now uses typed vi/en labels and selected
  locale timestamps. Mutation failures no longer project caught transport text
  into its UI; only the localized safe error is shown, while authorized audit
  facts remain server-provided queue data.
- The consent centre now renders all six backend ledger purposes, including
  AI-transparency acknowledgement. It uses the existing append-only grant and
  withdrawal route and catalog keys; no new consent policy, access grant or
  mutation path was introduced. A static catalog contract guards this visible
  ledger coverage. This source checkpoint has not run tests, build or deployment.
- Mobile's gated Consent Center now reads and mutates the same append-only
  `/api/v1/compliance/consent` ledger as web for all six server purposes. It
  re-reads canonical state after each grant/withdrawal, fails closed without
  showing a control when the ledger cannot be read, and removes the obsolete
  device-local pseudo-ledger whose toggles could not affect API policy. Product
  analytics remains disabled by default and is not presented as a server
  compliance purpose. Focused widget contracts are added but unrun.
- The mobile Data Rights screen now shares the authenticated API client rather
  than maintaining a second direct-HTTP transport. Only a closed DSAR kind is
  sent for non-destructive requests. Its explicit second confirmation for
  deletion maps solely to `/api/v1/compliance/dsar/delete`, the server's
  transactional anonymization route, rather than creating a generic deletion
  request. Retry state stores only that closed kind, and safe errors suppress
  upstream transport detail. Focused widget contracts are added but unrun.
- The mobile public PHR share viewer now likewise delegates its opaque,
  read-only token request to the shared API client instead of retaining a
  second HTTP transport. It deliberately sends no access token, never persists
  the capability in the viewer, preserves the strict safe-field projection,
  and collapses all public-link errors to one non-PII unavailable message.
  Its focused fake-client widget contracts are added but unrun.
- Android intent handling now accepts only canonical HTTPS
  `theclaracare.com/phr/shared/{token}` links (including warm intents), retains
  the capability only in memory, and presents its public read-only viewer
  without an authenticated or medical-consent detour. Viewer availability still
  requires the separate mobile build and server sharing gates. Android App Link
  verification needs the release certificate fingerprint in a deployed Digital
  Asset Links file; this repository deliberately does not invent one.
- The PHR share manager's existing web URL (`/phr/shared/{token}`) now has a
  public viewer rather than resolving to a missing route. Middleware and the
  AppShell treat only that prefix as public; the viewer calls the existing
  read-only endpoint, keeps the capability out of UI/telemetry, whitelists the
  same profile/allergy/condition/medication or emergency-card fields as mobile,
  and collapses all failures to one localized unavailable state. Focused source
  contracts are added but unrun.
- Public capability routes now suppress Analytics Consent bootstrap and use
  `noindex`/`no-referrer` metadata, preventing a share URL from becoming an
  analytics-consent request referrer or a searchable page. The API's existing
  global no-store security header remains the response-cache control.
- The parallel public conversation route (`/share/{token}`) now uses the same
  `noindex`/`no-referrer` metadata, no longer displays an owner label, and
  collapses invalid, expired, revoked and transport failures into one localized
  public unavailable state. Static content, expiry formatting and its empty
  state now use typed vi/en copy. No authorized message content, share
  capability semantics, audit behavior or backend policy was changed; the
  endpoint now normalizes all unavailable lifecycle states to one opaque 404
  code. This source checkpoint has not run tests, build or deployment.
- The legacy Research right rail's attached-file and evidence panels now use
  typed vi/en labels, locale-aware file sizes and a localized accessible
  file-removal label. Citation content, source URLs, upload behavior and every
  research/evidence release boundary are unchanged. This source checkpoint has
  not run tests, build or deployment.
- The legacy Research flow timeline now localizes its status, mode, bounded
  telemetry labels, empty state and date/number/duration rendering via the
  typed vi/en catalog. It makes no change to stage/event data, RAG execution or
  release policy. This source checkpoint has not run tests, build or deployment.

- `d53af25a` and `99a69fbe`: CareGuard ambiguity is a terminal, fail-closed
  DrugBank clarification contract from ML through web/mobile; no result can be
  inferred before the API revalidates the owner-scoped source choice.
- `00993943`: the mobile terminal clarification wording follows the app locale
  without changing that safety boundary.
- `1f06dab6`: a Scribe batch request carrying `session_id` is owner-scoped and
  rechecks live visit-recording consent before any audio is sent to ASR; the
  legacy unscoped route remains compatible while the global rollout is off.
- `8ca4f4c7`: web uses the existing consent/profile-scoped visit-preparation
  endpoint only as a read-only, source-cited draft. It neither creates nor
  confirms LifeMap state. The same checkpoint removes an uncalibrated OCR
  percentage from the guided medicine-entry presentation.
- `4bf1a47f`, `524b9b02` and `ec306759`: typed vi/en migration now includes
  Chat V2 shell chrome, a bounded legacy workspace sidebar and the Research
  workspace. This is still not a claim of all-page i18n completion.
- `14414393`: the asynchronous mobile visit-preparation review-only notice is
  announced as a live accessibility region without changing the draft data or
  its consent/capability conditions.
- `8583b8e6`: Research citation trace/registry rows require a real retrieved
  context binding; stale or injected labels cannot anchor a claim.
- `3f33a751`: Council's shadow-specialist contract is now constrained to
  bound evidence findings and non-prescriptive actions that cannot undercut
  its proposed triage level. The path remains unreleased shadow evidence.
- `4fd15a63` and `8bbc1689`: the remaining bounded legacy Chat composer and
  the AI Transparency Notice gate are catalog-backed. The composer no longer
  displays a raw job identifier; acknowledgement errors are sanitized rather
  than exposing transport detail.
- `4972eeca` keeps the legacy conversation-history rollback area bilingual,
  including state and assistive-control copy. `a091c197` passes the active UI
  locale through Research Markdown export, code/chart/Mermaid and citation
  controls. Neither changes chat/research rendering or safety policy.
- `136214df` makes registry text-client construction text-only, preserving the
  dedicated ASR provider boundary. `615a3024` verifies cabinet OCR uploads
  before any provider call; bad file evidence or an unavailable required
  scanner cannot reach OCR.
- `dbc90d28` removes internal LifeMap field/rule identifiers from the mobile
  review explanation without changing revision/provenance/truth-state. The
  production compose Scribe timeout is explicitly wired in `1b0a394f`.
- `cb2eb1e0` fixes judge-report evidence state: observed confidence intervals,
  critical errors and ablations replace their unavailable placeholders rather
  than appearing alongside them. It does not add a clinical benchmark result.
- `366f199a` moves the no-longer-imported ResearchRightRail cluster and its
  exclusively-owned panels into an explicit legacy artifact; active routes do
  not import it. `b117e534` localizes the Council clinician oversight dialog
  without changing its RBAC, payload or mutation mechanics.
- `743c6dea` replaces the former RAG watermark-backfill skeleton with a
  default-off, dual-gated lazy composition of the existing source registry and
  ingestion orchestrator. The same checkpoint adds deployment/runtime guards;
  it has no new execution or external-ingestion evidence.
- `58433d68` moves legacy Chat starter questions into the typed catalog and
  adds a scoped literal-copy gate for that static surface. `8de7f745` records
  the credentialed Google Chirp-3 adapter accurately and narrows its provider
  locale inputs. `85659f9b` renames the active RAG component to
  `EvidenceReranker`, retaining only compatibility aliases; its ranking and
  candidate-only evidence boundary do not change.
- `de590313`, `a7a274ca` and `7e57d3ba` introduce and extend a conservative
  End_User error boundary: technical/upstream caught errors render the
  already-localized generic fallback rather than raw transport detail. The
  helper does not alter requests, telemetry or safety policy.
- `5cb5cbf3` applies the same boundary to legacy Chat and catalogizes its
  remaining static action/notice/confirmation wording. It also catalogizes
  Council Workspace static navigation, headings, citation fallback and
  empty-state copy. Dynamic user/API/clinical content and Council facts,
  triage, prompts and outputs remain unchanged.

All of these checkpoints have static whitespace evidence only in this pass;
their tests, builds, evaluation and deployment remain deferred by instruction.

## Features and safety invariants preserved

- RBAC/profile isolation, consent and cookie CSRF remain API-owned.
- Emergency fast-path remains deterministic and does not wait for model output.
- FIDES/claim verification and DrugBank authority are unchanged.
- The optional CareGuard wording projection is OFF by default, is derived only
  from final risk/readiness/provenance categories, and cannot make a required
  DrugBank source failure look like an all-clear.
- Registry task contracts retain DeepSeek-only behavior and a controlled rollback:
  `MODEL_REGISTRY_ENABLED`, `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED`,
  `MODEL_REGISTRY_FORCE_ROLLBACK` and `MODEL_REGISTRY_ROLLBACK_MODEL`.
- V4 task selection never changes deterministic emergency, authorization,
  consent, DrugBank, confirmed LifeMap-write or final safety-policy decisions.
- Research/RAG and Control Tower configuration cannot reintroduce an
  end-user- or job-selected LLM provider, endpoint, model or API key; their
  historical runtime keys are ignored and omitted on write.
- Strict CareGuard operation requires a verified mounted DrugBank release with
  matching DDI and dictionary inventory. It never substitutes a curated rule
  set or LLM conclusion when that release is unavailable.
- Council reasoning is not released through the consumer client/streaming view;
  only the permitted conclusion structure remains available.
- Scribe clinician changes are consent-gated and version-aware; they do not
  restore automatic coding or uncalibrated confidence.
- Eval manifests and reports do not copy secret values, PHI, prompts or patient
  text; their fixture policy rejects PHI/secrets.
- Scribe no longer assigns diagnosis/procedure codes from regex text and no
  longer renders an uncalibrated confidence percentage.
- The renderer emits consumer wording only from released severity/action/
  warning/uncertainty fields; its independent verifier rejects missing
  warnings, softened uncertainty, added dose text and unapproved prescribing
  language before a response is released.

## Tests and evaluation evidence

The table below records historical executions in this workspace. It is not a
current green status. Per current user direction, no format/lint/type check,
unit/integration/contract/migration/safety test, eval smoke, build, secret/PII
review, E2E run or deployment was run after the following newer commits:
`716e062d`, `6294386d`, `9ce7d6d3`, `0c6b268d`, `ee156724`, `81d1d6b9`,
`39de7393`, `99ab3182`, `0a6cee55`, `bd9a07e0`, `b30f2608`, `d182fc31`,
`2b0bf003`, `cc60d16d`, `6cf1bc39`, `1dbe8c1f`, `6364da91`, `5f8151e0`,
`8bd27232`, `daf1e551`, `1bf5a214`, `d12d15e0`, `012e0b5b`, `511107f9`,
`4e898cab`, `33cb11ec`, `b15210a2`, `f1eb4fa2`, `26547a8f`, `a4989c14` and
`3d90e878`, `43102b4a`, `1b6c7cbd`, `85c8e5b4`, `027423b1`, `d153d79b`,
`70cc2877`, `59e63b90`, `fca5fba9`, `c872746c`, `9f71e9fd`, `c4249152`,
`59037f19`, `47162ccc`, `89b1aade`, `c0ac3777`, `3628db26`, `8fdfac33`,
`d6a5abc5`, `fba3e639`, `f24ee6f4`, `b0ac6e40`, `d6a9371c` and `b7327001`.
Tests added in those commits are therefore **not run**, rather than pass or
fail.

The same no-run status applies to the subsequent implementation checkpoints
`d53af25a`, `a4b9458c`, `99a69fbe`, `4bf1a47f`, `eda8b7d6`, `00993943`,
`524b9b02`, `ec306759`, `1f06dab6`, `8ca4f4c7`, `14414393`, `8583b8e6` and
`3f33a751`, `4fd15a63` and `8bbc1689`. Their pull-request notes
record only static whitespace checks; they are not evidence of runtime health.

Historical executions:

| Check                                                       | Result                                                                                                                                                                                                                                         |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Web lint + TypeScript                                       | pass for i18n and Scribe checkpoints                                                                                                                                                                                                           |
| Web full unit/property suite                                | pass: 75 files, 638 tests                                                                                                                                                                                                                      |
| Eval formatting/Ruff/mypy                                   | pass: 12 files; mypy clean                                                                                                                                                                                                                     |
| Eval unit suite                                             | pass: 8 tests                                                                                                                                                                                                                                  |
| Eval manifest validator                                     | pass: 9 required tracks, checksums/counts validated                                                                                                                                                                                            |
| Eval smoke and judge runner                                 | pass via `python -m evaluation.clara_eval.run ...`                                                                                                                                                                                             |
| Eval release suite                                          | expected non-zero (2): no approved locked/live evidence; diagnostics written                                                                                                                                                                   |
| Model registry focused suite                                | pass: 39 tests (registry, Council shadow, capture triage, main API)                                                                                                                                                                            |
| RAG registry runtime seam                                   | pass: 34 focused RAG/registry tests; direct provider construction is absent from `rag/pipeline.py`                                                                                                                                             |
| RAG full Ruff/mypy                                          | not clean: focused undefined-name Ruff check passed, but the existing full selected files report 60 Ruff findings and 52 mypy findings; they were not suppressed or weakened by this work.                                                     |
| Vietnamese language/router focused suite                    | pass: 14 tests                                                                                                                                                                                                                                 |
| LifeMap intelligence/invariant suite                        | pass: 9 tests (read-only ask, exact revision citations, profile scope and truth-state-preserving summaries)                                                                                                                                    |
| CareGuard normalization/DrugBank focused suite              | pass: 42 tests                                                                                                                                                                                                                                 |
| CareGuard structured wording adapter                        | pass: 35 focused renderer/guardrail/DrugBank tests; default flag preserves the old response, enabled flag adds only a verified consumer projection.                                                                                            |
| Current web production build                                | pass: Next production build completed after current UI/router checkpoints                                                                                                                                                                      |
| Renderer contract/fidelity + emergency response integration | pass: 18 focused tests; Ruff and mypy clean for renderer and `medical_answer_v2`                                                                                                                                                               |
| Task-first Today/navigation                                 | pass: focused lint, TypeScript and 11 navigation/i18n/static surface tests                                                                                                                                                                     |
| Guided-flow locale bridge                                   | pass: Prettier, targeted ESLint, TypeScript, catalog tests and 13 guided-flow tests; test switches the global locale and observes English progress/save wording.                                                                               |
| Web dependency security checkpoint                          | pass: full web lint, TypeScript, production build and 75 test files / 639 tests after targeted Axios/Next/Mermaid/DOMPurify/UUID/Playwright updates; `npm audit --omit=dev --json` recorded 11→3 vulnerabilities (7 high/4 moderate → 3 high). |
| Web E2E first retry                                         | fail before assertions: Playwright standalone production server exceeded the prior 120-second build startup timeout. The bounded timeout is now 300 seconds and the retry is pending; no E2E assertion is claimed as passed.                   |
| Mobile Unified locale navigation                            | pass: `flutter test test/unified_root_test.dart` (5 tests) and targeted `flutter analyze` (no issues)                                                                                                                                          |
| Mobile Profile hub locale                                   | pass: `flutter test test/unified_root_test.dart` (6 tests), `flutter test test/unified_a11y_responsive_test.dart` (12 tests), targeted `flutter analyze`, and Dart format.                                                                     |
| Mobile debug APK build                                      | environment-blocked: Snap Flutter reported missing `cap_dac_override`; no APK result is claimed                                                                                                                                                |
| Static active-eval                                          | executed after portable previous-run selector fix, NO-GO as expected; it recorded zero runtime measurements and no latency samples                                                                                                             |

At the time of the historical run, `make` was unavailable in this workspace
(`make: command not found`), so `make eval-judge-report` was not invoked
literally. The exact Python command behind that target was recorded as having
been executed successfully then; this reconciliation does not re-run it. The
API full suite has no confirmed terminal result: its first execution detached
before a summary and a background log rerun was stopped by the environment
before it wrote output. Do not infer its status from focused tests; run the
direct command below before release.

## Evaluation results, critical errors and cost/latency

`artifacts/judge-report/` is generated on demand and is ignored by git. The
judge landing page shows exactly the six requested judge headline measures
(Vietnamese emergency recall, medication-normalization top-1, severe DrugBank
DDI recall, unsupported RAG claim rate, Scribe clinician edit-time reduction,
and router large-LLM cost reduction). The report emits one genuine measurement:
checked-in fixture manifest integrity.
All clinical quality, human usability, DrugBank recall, ASR WER, RAG quality,
Council ablation, model latency and cost metrics are explicitly `not_measured`
with a reason and a command. This repository contains no approved reviewed
corpus, immutable retrieval snapshot, licensed full DrugBank benchmark, live
provider trace, cost ledger or human-study result to compute them.

`cb2eb1e0` additionally enforces this distinction in the generated artifacts:
an observed binary safety category can report zero only after approved cases
actually ran, and a measured confidence interval/ablation replaces its
unavailable placeholder. The checkpoint itself was not executed in this pass,
so it provides no new measurement.

Manifest version `2026-07-30.foundation.2` records a specific evidence gap for
each headline, rather than falling back to a generic report message: noisy
Vietnamese emergency corpus, pharmacist-adjudicated Vietnamese medication
mapping, licensed full-DrugBank pairs/index, Vietnamese gold claims with an
immutable retrieval snapshot, consented clinician edit-time study, and an
aggregate routing usage ledger respectively. These entries are metadata only,
not benchmark values.

The static active-eval baseline is NO-GO, not a release approval: its DDI,
fallback and refusal runtime counts were zero and latency samples were absent.
There are no measured before/after clinical or cost/latency improvements.

## Data migrations and rollback

### Capability share hardening (`20260801_0047`)

Workspace/Research và PHR public-share capabilities hiện chỉ lưu SHA-256 ở
database; response tạo/xoay là nơi duy nhất có token thô. Migration backfill
digest để các URL đã cấp vẫn đọc được, sau đó xóa cột plaintext. Owner metadata
không còn trả URL cũ; thao tác cấp lại xoay capability và sao chép URL mới ngay
lúc cấp. Downgrade chỉ tương thích schema vì hash không thể đảo ngược; xem
`docs/runbooks/public-capability-share-rotation.md` trước khi rollback.

### Retention-policy enforcement (`20260801_0048`)

Khi `COMPLIANCE_RETENTION_JOB_ENABLED=true`, retention sweep giờ thực thi đúng
các category đã công bố: xóa `queries` quá 365 ngày, `auth_tokens` quá 90 ngày,
và ẩn danh cabinet không hoạt động quá 1.095 ngày bằng cách xóa inventory và
nhãn. Kết quả chỉ gồm count. Revision thêm index cho các timestamp cutoff;
`alembic downgrade 20260801_0047` chỉ bỏ index, không khôi phục dữ liệu đã bị
xóa/ẩn danh. Kiểm thử mới được thêm nhưng chưa chạy trong checkpoint này theo
thứ tự triển khai được yêu cầu.

### Web/mobile release hardening

Next production build no longer ignores TypeScript or ESLint failures. Android
now uses package `com.theclaracare.app` and never assigns the debug keystore to
release builds. CI fails closed unless protected release-signing inputs are
present, verifies the produced APK signature, and the web only serves Android
Digital Asset Links after a syntactically valid production certificate
fingerprint is configured. This source change has not yet been built, signed or
deployed in this checkpoint.

Alembic revision `20260731_0046` adds the append-only
`council_evidence_attachments` table, scoped by Council case, owner and
completed Research job. It stores only server-built opaque snapshot/evidence
IDs and controlled categories, never Research query/result/source text. Apply
it with `cd services/api && alembic upgrade head`. Operational rollback is to
set `COUNCIL_EVIDENCE_PACKET_SHADOW_ENABLED=false` for both API and ML and
restart both services; this hides the selector, prevents new writes and
restores the legacy request path while retaining audit rows. A schema rollback
exists as `cd services/api && alembic downgrade 20260729_0045`, but it drops
that additive table and must not be used where retained audit attachments are
required.

Roll back a checkpoint by deploying its prior commit after preserving the
current database and audit trail; do not rewrite history. For a governed V4
task-routing incident, first set
`MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` to use the legacy single
configured DeepSeek model. If a model rollback is needed, set an explicit known
prior model in `MODEL_REGISTRY_ROLLBACK_MODEL`, enable
`MODEL_REGISTRY_FORCE_ROLLBACK`, restart ML, then run `make eval-smoke` when
testing resumes. Disable the force flag after recovery.

## External blockers and remaining work

1. Approved locked clinical datasets, clinician review and immutable retrieval
   snapshots are unavailable. Run `make eval-nightly` after provisioning them;
   then run `make eval-release` for a release decision.
2. Licensed full DrugBank benchmark/index material is unavailable in this
   checkout. Provision it only server-side, then run `make eval-release`.
3. No live provider cost/latency trace is installed. Collect sanitized,
   aggregate routing telemetry and run `make eval-nightly`.
4. Full web/domain-page i18n and common mobile terminology are not yet fully
   catalog-backed. Recent auth/onboarding, chat, consent, LifeMap, Medicines,
   Research, Community, Council, Scribe/admin RAG, PHR/evidence,
   connected-health and Settings/More checkpoints make substantial progress.
   The Settings model disclosure now accurately says governed V4 Pro/Flash
   routing, but wider scanner enforcement remains absent.
   A generated consumer-terminology contract now exists, but it is not a full
   shared/generated UI catalog. Continue migration surface by surface with
   parity tests; do not label it complete before scanner scope covers them.
5. RAG synthesis, reranking, NLI verification and Research planning/reasoning
   are registry-bound, and historical provider/runtime JSON inputs are ignored.
   The refactor has not received a fresh full authorization, contract or
   regression run; execute those deferred gates before treating the boundary as
   release evidence.
6. Production deployment was not attempted in this checkpoint per user
   direction. Before deployment, set the production environment's governed
   `DEEPSEEK_MODEL`, `DEEPSEEK_PRO_MODEL`, `DEEPSEEK_FLASH_MODEL`,
   `LLM_DEEPSEEK_ONLY`, `MODEL_REGISTRY_ENABLED` and
   `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED` values. If strict CareGuard is
   enabled, also provision the licensed artifact mount and keep SQLite/manifest
   integrity enabled. Run the runtime guard and the deferred release validation
   before a deploy. No current server capacity, artifact availability or
   provider-availability assertion is made here.
7. Docker/container execution is unverified in this checkpoint: no current
   image build, registry push, daemon availability or deployment-host access is
   asserted. Before a release, use a provisioned Docker-capable CI/deployment
   environment to build the affected images, run the runtime guard against the
   actual protected environment file, and retain the resulting image digest for
   rollback.
8. GitHub's push response was observed moving from 130 to 100 and then to 59
   dependency advisories on the default branch after this dependency refresh
   (latest observed: 1 critical, 28 high, 22 moderate, 8 low). Targeted web
   lock upgrades reduced the local
   production-dependency audit from 11 to 2, but this does not establish that
   GitHub's cross-ecosystem advisory total is resolved. The three remaining
   historical web findings were in the Next/PostCSS/Sharp chain; the Sharp
   finding is now remediated, leaving one high PostCSS finding and one moderate
   Next aggregation. The audit metadata offers no compatible Next 15 fix.
   Assess a Next 16/React migration separately with service and web regression
   evidence rather than forcing a misleading downgrade.

## Exact local, CI and evaluation commands

```bash
# quality and service tests (standard developer/CI image)
make lint && make type-check && make test && make docs-check
cd apps/web && npm run lint && npx tsc --noEmit && npm run test && npm run build

# before any strict CareGuard deployment (does not print licensed artifact data)
REQUIRE_DEEPSEEK=true scripts/ops/validate_runtime_env.sh /opt/clara-care/.env

# Docker-capable local/CI environment: validate resolved compose and build/start
# only after the quality gates above. This was not run for this checkpoint.
make check-env
docker compose --env-file .env -f deploy/docker/docker-compose.app.yml config
make docker-app-up

# authorized deployment host only, after a protected environment file, licensed
# DrugBank mount and release image digests have been provisioned
REQUIRE_DEEPSEEK=true scripts/deploy/redeploy_app_stack.sh /opt/clara-care

# CLARA-Eval VN
make eval-smoke
make eval-nightly
make eval-release
make eval-judge-report

# direct fallback when make is unavailable
PYTHONPATH=services/api/src services/api/.venv/bin/pytest -q services/api/tests
python -m evaluation.clara_eval.run \
  --config evaluation/configs/judge_demo.yaml \
  --output artifacts/judge-report

# static active-eval baseline (does not substitute for live metrics)
bash scripts/demo/run_active_eval_loop.sh \
  --run-id local-static-baseline --mode static --strict false
```

## Revalidation checkpoint — 2026-08-02

This is a source-and-local-validation checkpoint, not a production deployment.
The following commands were actually executed after the CSRF/cookie, header,
sharing, retention and release-hardening checkpoints:

| Gate | Result | Evidence / limitation |
| --- | --- | --- |
| Focused API CSRF and health contracts | pass | `31 passed` (`test_health.py` and `test_rbac_owner_scope_csrf.py`); verifies malformed lower-case bearer does not bypass cookie CSRF and metrics accepts the header token only. |
| Research Tier2 API contracts | pass with warnings | `59 passed` in `39.66s` (`tests/test_p2_proxy_endpoints.py`). The quality gate now preserves an upstream `block`/`escalate` safety verdict while it withholds a degraded research answer; the request contract also proves provider/runtime credentials are neither caller-selected nor persisted. |
| Web lint | pass with warnings | Exit 0; eight existing React hook-dependency warnings remain. |
| Web type-check | pass | `npx tsc --noEmit` exited 0. |
| Web i18n and terminology | pass | `npm run i18n:check` (3,241 vi/en keys; 38 migrated surfaces) and `npm run consumer-terminology:check` passed. |
| Web unit suite | pass | `677/677` tests in `295/295` files. The i18n test changes preserve the same safety assertions by asserting both the typed key usage and catalog text. |
| Web production build | pass with warnings | `npm run build` completed. The same eight hook-dependency warnings remain; TypeScript and ESLint errors are no longer ignored. |
| Documentation links | pass | `bash scripts/docs/check-docs-links.sh`. |
| Eval smoke | pass | Direct target implementation: `python3 -m evaluation.clara_eval.run --config evaluation/configs/smoke.yaml --output artifacts/clara-eval-vn/smoke`. |
| Judge report | pass | Direct target implementation emitted all required judge-report files, including HTML, Markdown, JSON/CSV manifests, critical-errors, ablations and examples. It measures fixture-manifest integrity only and marks 28 product metrics `not_measured` with reasons and commands. |
| Python repository lint | fail (baseline) | `ruff check` reports 652 pre-existing findings across scripts and API/ML tests. No broad automatic rewrite was applied. |
| Python repository type-check | fail (baseline) | `mypy` reports 337 errors in 45 files across existing API/ML source. This is a separate remediation backlog; it is not hidden by the release configuration. |
| Full API suite | interrupted (environment) | The direct `services/api/.venv/bin/python -m pytest -q` run remained CPU-active for over 10 minutes and wrote about 8 GB of SQLite test I/O before controlled SIGINT. It produced no terminal result, so it is neither pass nor fail evidence. Focused CSRF/health contracts remain the confirmed API result. |

After that interrupted run, `370ef516` made the API test bootstrap select a
private temporary SQLite database before importing the application engine. A
fresh focused run again passed `31` tests in `15.27s`, and the checksum of
`services/api/clara.db` remained unchanged. This fixes the unsafe workspace
database coupling; it does not turn the previously interrupted full suite into
a passing result.

`make` is unavailable in this workspace (`make: command not found`), so the
eval targets were executed through the exact Python commands in the Makefile.
The target definitions remain present; a standard CI image can invoke
`make eval-smoke` and `make eval-judge-report` directly.

External live verification on 2026-08-02 showed that
`https://theclaracare.com/`, `/login`, and `/share/not-a-real-token` still
return an old artifact/proxy response: no CSP, HSTS, `nosniff`, frame policy,
referrer policy or permissions policy, and `X-Powered-By: Next.js` is present.
The committed Nginx config therefore has **not** reached that host. Do not
describe the browser-header remediation as deployed until a controlled
release installs the config, validates `nginx -t`, reloads Nginx, and repeats
the external header smoke check.
