# Competitive_Research_Report — Product Polish & Analytics

Deliverable for Requirements 6.1, 6.2, 6.3, 6.4. Produced by CLARA_Delivery.

This report surveys products comparable to each major **Surface** of CLARA-Care
and distills the **general UX patterns and capabilities** they have in common.
It exists to feed proven, non-proprietary patterns into the UX modernization
work (Epic 8) and the analytics dashboards (Epic 6), with each adopted pattern
traceable back to its originating entry here (Requirement 6.4).

## Compliance note

- This document describes **general UX patterns and capabilities only**. It
  contains **no verbatim copyrighted text and no proprietary assets** (no
  screenshots, logos, design files, code, or prompt content from the products
  surveyed). (Requirement 6.2)
- Every cited source includes an inline **attribution link** to the original
  source. (Requirement 6.3)
- All findings were **paraphrased and summarized** from public sources; no
  source is quoted at length. **Content was rephrased for compliance with
  licensing restrictions.**
- Naming a product describes a *category convention*, not an endorsement or an
  instruction to copy that product. CLARA-Care adopts the underlying pattern,
  expressed through its own design tokens, Vietnamese copy, and safety model.

## How to read the Surface tags

Each pattern is tagged with the CLARA-Care Surface(s) it informs. The six tag
names are fixed so downstream tasks can reference them directly:

- **`Chat fast-first/thinking state`** — the Chat surface (`/chat`); informs the
  Fast_Mode-first answer affordance and the calm "thinking" state.
- **`Research progressive disclosure`** — the Research experience (folded into
  the Chat workspace); informs staged reveal of the long pipeline and citations.
- **`CareGuard severity visualization`** — SelfMed/CareGuard (`/selfmed/ddi`,
  `/careguard`); informs DDI risk-severity display.
- **`Council consensus/divergence layout`** — Council (`/council`); informs
  multi-specialist result grouping.
- **`Scribe SOAP scaffolding`** — Scribe (`/scribe`); informs note structure and
  record/transcribe states.
- **`Admin analytics KPI/date-range conventions`** — Admin analytics dashboards
  (`/admin/analytics`, `/admin/analytics/clinical`); informs KPI cards, date
  ranges, distributions, and empty states.

A pattern may carry more than one tag when it informs several Surfaces.

---

## 1. Medical AI chat assistants

**Comparable products / references:** general-purpose and medical conversational
AI with selectable "fast" versus "reasoning" model behavior.

### Pattern 1.1 — Separate fast answers from slow reasoning, and set the right expectation up front
Tools that offer both quick and deep modes draw a clear line between models
tuned for low-latency, real-time replies and models that take longer to "think
through" harder problems; the guidance is to match the mode to the task so the
interface can set the right waiting expectation
([Vercel AI SDK Academy — model types and performance](https://vercel.com/academy/ai-sdk/model-types-and-performance)).
For CLARA, this reinforces routing Fast_Mode straight to the tier1 chat path
(no long job pipeline) and showing a lightweight answer affordance immediately.

- **Surfaces:** `Chat fast-first/thinking state`

### Pattern 1.2 — Make the "thinking" state calm and visible rather than a blank spinner
Research on conversational diagnostic AI emphasizes a visible reasoning/turn
structure during multi-step interactions
([Nature Medicine — advancing conversational diagnostic AI with multimodal reasoning](https://www.nature.com/articles/s41591-026-04371-0)).
Separately, design analyses of generative AI "tools for thought" warn that
**opacity of reasoning** and **over-reliance** are real risks to mitigate in the
interface
([IEEE Computer Society — generative AI as a tool for thought in digital healthcare](https://www.computer.org/publications/tech-news/trends/generative-ai-powered-healthcare)).
The takeaway: when a deep mode is genuinely working, show a calm, labeled
"thinking" state (and, where possible, a brief progress cue) instead of an
unexplained long spinner — but keep internal reasoning telemetry out of the
End_User view.

- **Surfaces:** `Chat fast-first/thinking state`, `Research progressive disclosure`

### Pattern 1.3 — Offer retry/regenerate as a first-class recovery affordance
Because conversational quality varies between responses, comparable assistants
commonly expose a retry/regenerate action so users can recover from a poor or
failed turn without re-typing
([Stanford HAI — MedArena: comparing LLMs for medicine in the wild](https://hai.stanford.edu/news/medarena-comparing-llms-for-medicine-in-the-wild)).
For CLARA this pairs naturally with the sanitized timeout copy: a calm Vietnamese
retry message plus a one-tap "try again."

- **Surfaces:** `Chat fast-first/thinking state`

---

## 2. Medical research / literature tools

**Comparable products / references:** evidence-synthesis and literature-search
assistants that answer clinical questions with linked sources.

### Pattern 2.1 — Plain-language answer first, with verifiable linked citations
The dominant convention is to accept a plain-language question and return a
structured synthesis where each claim links back to its underlying source so the
reader can verify it
([Consensus — comparison vs OpenEvidence](https://consensus.app/home/vs/open-evidence/);
[Contrary Research — OpenEvidence business breakdown](https://research.contrary.com/company/openevidence)).
Independent write-ups note the same citation-anchored answer style for
point-of-care use
([UBC Wiki — Open Evidence](https://wiki.ubc.ca/Open_Evidence)).
For CLARA: keep the synthesized answer primary and render sources as compact,
clickable citation chips.

- **Surfaces:** `Research progressive disclosure`, `CareGuard severity visualization` (citation chips)

### Pattern 2.2 — Progressive disclosure of complexity
Progressive disclosure — show the essentials first and reveal advanced detail on
demand — is a long-established pattern for reducing cognitive load and learning
curve
([Nielsen Norman Group — progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/);
[Interaction Design Foundation — progressive disclosure glossary](https://www.interaction-design.org/literature/book/the-glossary-of-human-computer-interaction/progressive-disclosure)).
Applied to the research pipeline, this means a collapsed-by-default stage
timeline and "show details" expanders rather than dumping every retrieval/stage
artifact into the primary view.

- **Surfaces:** `Research progressive disclosure`, `Admin analytics KPI/date-range conventions`

### Pattern 2.3 — Frame mode pickers by outcome, not internal tier names
Comparison guides for research assistants describe modes in terms of the user's
goal — fast discovery versus rigorous, evidence-backed synthesis — rather than
internal model tiers
([DeepResearcher — compare AI research tools](https://deepresearcher.site/)).
This supports CLARA's Vietnamese outcome-oriented labels (`Nhanh`, `Tư duy`,
`Pro`, `Đầy đủ`) over internal names like `deep_beta`.

- **Surfaces:** `Research progressive disclosure`, `Chat fast-first/thinking state`

---

## 3. Drug-interaction checkers

**Comparable products / references:** consumer and professional drug-interaction
checkers.

### Pattern 3.1 — A small, named severity scale with a plain-language meaning
Established checkers classify each interaction on a short, named scale —
typically Major / Moderate / Minor — and pair each level with a plain-language
description of clinical significance and what to do (e.g., avoid the combination
versus monitor)
([Drugs.com — drug interactions overview](https://drugs.com/drug_interactions.html);
[Drugs.com — severity scale explanation](https://www.drugs.com/answers/scale-find-severity-drug-drug-interaction-checker-3558036.html)).
This maps cleanly onto CLARA's `low | medium | high | critical` model: every
level needs a short Vietnamese label and a one-line "what this means / what to
do."

- **Surfaces:** `CareGuard severity visualization`

### Pattern 3.2 — Summarize the result set before the details
Professional checkers commonly lead with a count-style summary of how many
interactions fall in each severity band before listing individual pairs
([Drugs.com — codeine interactions checker](https://www.drugs.com/drug-interactions/codeine.html)).
For CLARA, a compact "overall risk + count by severity" header above the alert
list helps a non-expert grasp the picture quickly.

- **Surfaces:** `CareGuard severity visualization`, `Admin analytics KPI/date-range conventions`

### Pattern 3.3 — Check medications, supplements, and food together with verifiable references
Comparable tools present a single checker spanning drugs, supplements, and
common foods, and attach references the user can consult
([Medscape — drug interaction checker](https://reference.medscape.com/drug-interactionchecker)).
This supports CLARA showing reference-source chips (not raw connector
identifiers) alongside each alert.

- **Surfaces:** `CareGuard severity visualization`

### Pattern 3.4 — Severity must not rely on color alone (accessibility)
WCAG Success Criterion 1.4.1 requires that color is never the sole means of
conveying information, including for status and severity indicators; pair color
with text and/or an icon/shape
([W3C — Understanding SC 1.4.1: Use of Color](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html);
[MDN — use of color](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Perceivable/Use_of_color)).
For CLARA's DDI severity badges this means color + Vietnamese label + an
icon/shape, never color by itself.

- **Surfaces:** `CareGuard severity visualization`, `Admin analytics KPI/date-range conventions`, `Council consensus/divergence layout`

---

## 4. AI clinical-council / second-opinion tools

**Comparable products / references:** multi-agent and multi-disciplinary
clinical reasoning systems (e.g., virtual/molecular tumor-board orchestration and
multi-specialist intake agents). Sources are research/industry write-ups, used
here only for general layout conventions.

### Pattern 4.1 — Specialist roles are explicit, then an aggregator reconciles them
Multi-agent clinical systems consistently model named specialist agents whose
outputs are reconciled by an aggregator/orchestrator step
([arXiv — virtualizing multi-disciplinary reasoning via collaborative agents](https://arxiv.org/html/2604.08927v2);
[Microsoft — multi-agent orchestration for cancer care](https://www.microsoft.com/en-us/industry/blog/healthcare/2025/05/19/developing-next-generation-cancer-care-management-with-multi-agent-orchestration/)).
For CLARA's Council, label each specialist node clearly in Vietnamese and show a
distinct reconciled-summary section.

- **Surfaces:** `Council consensus/divergence layout`

### Pattern 4.2 — Make consensus versus divergence the primary structure
The value of a multi-specialist view comes from showing where opinions agree and
where they diverge; analyses note that diversity across models surfaces
disagreements worth reviewing rather than hiding them
([arXiv — do mixed-vendor multi-agent LLMs improve clinical diagnosis?](https://arxiv.org/html/2603.04421v2)).
CLARA's Council should group results into a "consensus" block and a clearly
separated "points of divergence / needs attention" block, in plain Vietnamese.

- **Surfaces:** `Council consensus/divergence layout`

### Pattern 4.3 — Multidisciplinary review is a staged, summarized workflow
Descriptions of (virtual) tumor-board workflows frame the process as staged —
gather case data, have specialists assess, then summarize for a decision
([ASCO — virtual molecular tumor boards](https://ascopubs.org/doi/10.1200/CCI.19.00169);
[arXiv — Healthcare Agent Orchestrator for tumor-board summarization](https://arxiv.org/abs/2509.06602v1)).
This supports a Council intake stepper plus a concise final summary, with the
heavy per-stage detail kept behind progressive disclosure.

- **Surfaces:** `Council consensus/divergence layout`, `Research progressive disclosure`

---

## 5. Medical scribe / SOAP tools

**Comparable products / references:** ambient clinical-documentation and AI SOAP
note tools.

### Pattern 5.1 — SOAP is the default note scaffold
AI documentation tools structure the generated note around the standard SOAP
sections (Subjective, Objective, Assessment, Plan), turning a conversation into a
structured, reviewable note
([SOAPNoteAI — AI SOAP notes guide](https://soapnoteai.com/soap-note-guides-and-example/ai-soap-notes-guide/)).
CLARA's Scribe should present these four sections explicitly as the editing
scaffold.

- **Surfaces:** `Scribe SOAP scaffolding`

### Pattern 5.2 — Capture is ambient; the clinician reviews and signs
The ambient pattern is: passively listen, transcribe, and organize into a
structured note that the clinician then reviews and finalizes — the human stays
in the loop for sign-off
([Suki — ambient clinical documentation developer docs](https://developer.suki.ai/documentation/ambient-documentation);
[Suki — what is ambient clinical intelligence (2026 guide)](https://www.suki.ai/blog/what-is-ambient-clinical-intelligence-the-2026-guide-for-health-systems)).
CLARA's Scribe should make record → transcribe → draft → review an explicit,
visible flow with a clear "review before finalize" step.

- **Surfaces:** `Scribe SOAP scaffolding`

### Pattern 5.3 — Show pipeline state, and mark suggested codes as drafts
Architecture write-ups describe documentation as a multi-stage pipeline (capture
→ transcription → note generation → code suggestion → review), where suggested
billing/clinical codes are proposals for clinician confirmation, not final
output
([Fora Soft — AI scribe architecture for ambient documentation](https://www.forasoft.com/blog/article/ai-scribe-architecture-ambient-documentation-2026/)).
Comparison guides reinforce that first-pass accuracy plus easy review is the bar
([Glass Health — best AI medical scribe, compared](https://glass.health/resources/best-ai-medical-scribe)).
For CLARA: surface distinct record/transcribe/draft states and visually mark
derived codes as draft suggestions.

- **Surfaces:** `Scribe SOAP scaffolding`

---

## 6. Analytics dashboards

**Comparable products / references:** SaaS product- and usage-analytics
dashboards.

### Pattern 6.1 — Lead with KPI summary cards, then drill down
A common dashboard convention puts high-level KPI/summary cards at the top with
immediate drill-downs into detail below
([Lazarev — dashboard UX design best practices and examples](https://lazarev.agency/articles/dashboard-ux-design)).
CLARA's Product and Clinical analytics pages should open with KPI cards (active
users, per-Surface usage, fallback rate, blocked claims) above the charts.

- **Surfaces:** `Admin analytics KPI/date-range conventions`

### Pattern 6.2 — A selectable date range with auto-refresh is table stakes
Guides on building analytics dashboards treat a date-range filter (plus KPI
cards and interactive charts) as a baseline expectation
([RapiDevelopers — building dashboards for data analysis](https://rapidevelopers.com/bubble-tutorial/building-dashboards-data-analysis-bubble);
[Medium/NeuroNux — user-friendly SaaS dashboard best practices](https://medium.com/neuronux/how-to-design-a-user-friendly-saas-dashboard-best-practices-key-features-2e5307aba8bd)).
This matches the `?from=&to=` range on CLARA's analytics endpoints and the
date-range picker on both dashboards.

- **Surfaces:** `Admin analytics KPI/date-range conventions`

### Pattern 6.3 — Funnels and retention visualize where users drop off
Funnel-analysis dashboards visualize the sequential stages users move through to
expose drop-off points and friction, and retention views track returning cohorts
([InetSoft — application usage funnel analysis dashboard](https://www.inetsoft.com/info/application-usage-funnel-analysis-dashboard/);
[UMA Technology — analytics dashboards for customer retention](https://umatechnology.org/guide-to-automating-analytics-dashboards-for-customer-retention/)).
This grounds CLARA's `funnels` and `retention` sections in the Product_Analytics
response shape.

- **Surfaces:** `Admin analytics KPI/date-range conventions`

### Pattern 6.4 — Explicit empty/zero-data states
Dashboard UX guidance stresses showing a clear state when there is no data for
the current selection rather than a blank or broken chart
([FullSession — UX analytics framework: metrics, tools, prioritization](https://www.fullsession.io/blog/ux-analytics-framework-metrics-tools-prioritization/)).
This supports CLARA's `has_data=false` empty state on both analytics dashboards
and the shared four-state `AsyncSection` (loading / empty / error / populated).

- **Surfaces:** `Admin analytics KPI/date-range conventions`, `Research progressive disclosure`

---

## Pattern → Surface → downstream task cross-reference (Requirement 6.4)

When an Epic 6 or Epic 8 task adopts a pattern below, it should cite the pattern
ID (e.g., "implements CR §1.1") so the improvement is traceable to its source.

| Pattern | Surface tag(s) | Informs task(s) |
|---|---|---|
| 1.1 Fast vs reasoning, expectation set up front | Chat fast-first/thinking state | 2.1, 2.3, 8.5, 8.6 |
| 1.2 Calm, visible thinking state | Chat fast-first/thinking state; Research progressive disclosure | 8.1, 8.5, 9.1, 9.2 |
| 1.3 Retry/regenerate recovery | Chat fast-first/thinking state | 2.8, 2.9, 9.1 |
| 2.1 Plain-language answer + linked citations | Research progressive disclosure; CareGuard severity visualization | 9.2, 9.3, 8.5 |
| 2.2 Progressive disclosure of complexity | Research progressive disclosure; Admin analytics | 8.1, 8.5, 9.2, 6.1, 6.2 |
| 2.3 Outcome-framed mode pickers | Research progressive disclosure; Chat fast-first/thinking state | 3.4, 8.6, 9.1, 9.2 |
| 3.1 Named severity scale + plain meaning | CareGuard severity visualization | 4.10, 8.5, 9.3 |
| 3.2 Summarize result set before details | CareGuard severity visualization; Admin analytics | 9.3, 6.1 |
| 3.3 Medication/supplement/food + reference chips | CareGuard severity visualization | 9.3, 8.5 |
| 3.4 Severity not by color alone (WCAG 1.4.1) | CareGuard severity visualization; Admin analytics; Council | 8.3, 8.4, 8.5, 8.6 |
| 4.1 Explicit specialists + aggregator | Council consensus/divergence layout | 9.4, 8.5 |
| 4.2 Consensus vs divergence as primary structure | Council consensus/divergence layout | 9.4, 8.5 |
| 4.3 Staged, summarized review workflow | Council consensus/divergence layout; Research progressive disclosure | 9.4, 8.1, 8.6 |
| 5.1 SOAP default scaffold | Scribe SOAP scaffolding | 9.5, 8.5, 8.6 |
| 5.2 Ambient capture, clinician review/sign | Scribe SOAP scaffolding | 9.5, 8.6 |
| 5.3 Visible pipeline states + draft-marked codes | Scribe SOAP scaffolding | 9.5, 8.1 |
| 6.1 KPI cards then drill-down | Admin analytics KPI/date-range conventions | 6.1, 6.2 |
| 6.2 Selectable date range | Admin analytics KPI/date-range conventions | 6.1, 6.2 |
| 6.3 Funnels + retention | Admin analytics KPI/date-range conventions | 6.1 |
| 6.4 Explicit empty/zero-data states | Admin analytics KPI/date-range conventions; Research progressive disclosure | 6.1, 6.2, 8.1, 8.2 |

---

## Sources (attribution)

All sources are linked inline above; consolidated here for reference. Content
from these sources was rephrased and summarized for compliance with licensing
restrictions; no verbatim copyrighted text or proprietary assets are reproduced.

**Medical AI chat assistants**
- Vercel AI SDK Academy — model types and performance: https://vercel.com/academy/ai-sdk/model-types-and-performance
- Nature Medicine — advancing conversational diagnostic AI with multimodal reasoning: https://www.nature.com/articles/s41591-026-04371-0
- IEEE Computer Society — generative AI as a tool for thought in digital healthcare: https://www.computer.org/publications/tech-news/trends/generative-ai-powered-healthcare
- Stanford HAI — MedArena: comparing LLMs for medicine in the wild: https://hai.stanford.edu/news/medarena-comparing-llms-for-medicine-in-the-wild

**Medical research / literature tools**
- Consensus — comparison vs OpenEvidence: https://consensus.app/home/vs/open-evidence/
- Contrary Research — OpenEvidence business breakdown: https://research.contrary.com/company/openevidence
- UBC Wiki — Open Evidence: https://wiki.ubc.ca/Open_Evidence
- Nielsen Norman Group — progressive disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- Interaction Design Foundation — progressive disclosure glossary: https://www.interaction-design.org/literature/book/the-glossary-of-human-computer-interaction/progressive-disclosure
- DeepResearcher — compare AI research tools: https://deepresearcher.site/

**Drug-interaction checkers**
- Drugs.com — drug interactions overview: https://drugs.com/drug_interactions.html
- Drugs.com — severity scale explanation: https://www.drugs.com/answers/scale-find-severity-drug-drug-interaction-checker-3558036.html
- Drugs.com — codeine interactions checker: https://www.drugs.com/drug-interactions/codeine.html
- Medscape — drug interaction checker: https://reference.medscape.com/drug-interactionchecker
- W3C — Understanding SC 1.4.1: Use of Color: https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html
- MDN — use of color: https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Perceivable/Use_of_color

**AI clinical-council / second-opinion tools**
- arXiv — virtualizing multi-disciplinary reasoning via collaborative agents: https://arxiv.org/html/2604.08927v2
- arXiv — do mixed-vendor multi-agent LLMs improve clinical diagnosis?: https://arxiv.org/html/2603.04421v2
- arXiv — Healthcare Agent Orchestrator for tumor-board summarization: https://arxiv.org/abs/2509.06602v1
- Microsoft — multi-agent orchestration for cancer care: https://www.microsoft.com/en-us/industry/blog/healthcare/2025/05/19/developing-next-generation-cancer-care-management-with-multi-agent-orchestration/
- ASCO — virtual molecular tumor boards: https://ascopubs.org/doi/10.1200/CCI.19.00169

**Medical scribe / SOAP tools**
- SOAPNoteAI — AI SOAP notes guide: https://soapnoteai.com/soap-note-guides-and-example/ai-soap-notes-guide/
- Suki — ambient clinical documentation developer docs: https://developer.suki.ai/documentation/ambient-documentation
- Suki — what is ambient clinical intelligence (2026 guide): https://www.suki.ai/blog/what-is-ambient-clinical-intelligence-the-2026-guide-for-health-systems
- Fora Soft — AI scribe architecture for ambient documentation: https://www.forasoft.com/blog/article/ai-scribe-architecture-ambient-documentation-2026/
- Glass Health — best AI medical scribe, compared: https://glass.health/resources/best-ai-medical-scribe

**Analytics dashboards**
- Lazarev — dashboard UX design best practices and examples: https://lazarev.agency/articles/dashboard-ux-design
- RapiDevelopers — building dashboards for data analysis: https://rapidevelopers.com/bubble-tutorial/building-dashboards-data-analysis-bubble
- Medium/NeuroNux — user-friendly SaaS dashboard best practices: https://medium.com/neuronux/how-to-design-a-user-friendly-saas-dashboard-best-practices-key-features-2e5307aba8bd
- InetSoft — application usage funnel analysis dashboard: https://www.inetsoft.com/info/application-usage-funnel-analysis-dashboard/
- UMA Technology — analytics dashboards for customer retention: https://umatechnology.org/guide-to-automating-analytics-dashboards-for-customer-retention/
- FullSession — UX analytics framework: metrics, tools, prioritization: https://www.fullsession.io/blog/ux-analytics-framework-metrics-tools-prioritization/
