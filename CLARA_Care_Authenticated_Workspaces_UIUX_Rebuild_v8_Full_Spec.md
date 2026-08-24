# CLARA Care Authenticated Workspaces v8
## Full UI/UX Reconstruction Specification
### Clinical Instrument · Evidence Workstation · Admin Command Workbench · Spatial Companion

**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Audited `main` commit:** `81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`  
**Source audit date:** 2026-08-24  
**Scope:** Authenticated Web application shell and core Personal / Clinical / Research / Admin workspaces  
**Primary screenshot blockers:** `/dashboard`, `/chat`, `/evidence`, `/scribe`, `/admin/overview` plus sibling professional/admin surfaces  
**Required execution mode:** 20–30 active subagents concurrently whenever independent work exists  
**Status semantics:** `IMPLEMENTED != VERIFIED != DONE`

---

# 0. Executive decision

The current professional/authenticated UI is not failing because of isolated spacing or color mistakes. It is failing because multiple pages share the same structural anti-pattern:

```text
global chrome
+ workspace chrome
+ page heading
+ navigation tiles / mode tabs
+ many bordered panels
+ many equal cards
+ bottom floating navigation
```

The result is visually dense while simultaneously wasting space.

The screenshots demonstrate:

- too many navigation layers;
- heavy dark surfaces everywhere;
- weak page-specific hierarchy;
- card walls;
- redundant controls;
- oversized empty zones;
- the bottom dock overlapping or visually competing with primary work;
- workflows that expose every stage simultaneously instead of adapting to state;
- Admin pages behaving like consumer dashboards;
- Clinical pages behaving like configuration dashboards;
- Research pages behaving like generic form pages.

v8 therefore rebuilds the **authenticated workspace system**, not merely individual page styles.

---

# 1. Source audit findings

## 1.1 Route capability matrix

The repository classifies public, Personal, Clinical, Research and Admin routes explicitly. Preserve these classifications and their access policies.

Important canonical routes include:

- `/today`
- `/lifemap`
- `/phr`
- `/medicines`
- `/chat`
- `/evidence`
- `/research/source-hub`
- `/council`
- `/scribe`
- `/dashboard`
- `/admin/overview`
- `/admin/knowledge-sources`
- `/admin/answer-flow`
- `/admin/observability`
- `/admin/analytics`
- other Admin More routes.

Aliases such as `/research*`, `/selfmed*`, `/careguard`, `/admin/rag-sources` remain compatibility aliases/redirects and MUST NOT recreate alternate UI families.

## 1.2 Current generic PageShell problem

`apps/web/components/ui/page-shell.tsx` provides a generic title/description followed by either a plain body or one card wrapper.

This is acceptable for simple utility pages.

It MUST NOT be the compositional authority for:
- Chat;
- Evidence;
- Scribe;
- Council result;
- Admin operational surfaces;
- dense workbenches.

These need dedicated page archetypes.

## 1.3 Current Evidence implementation

`apps/web/app/evidence/page.tsx` currently:
- owns question form;
- LifeMap episode selection;
- polling;
- result matrix;
- applicability;
- contradictions;
- subscriptions;
- notifications;
- uses a main + 360px aside layout.

The behavior is useful and MUST be preserved.

The layout MUST be rebuilt so state determines composition.

## 1.4 Current Scribe implementation

`apps/web/app/scribe/page.tsx` already contains:
- consent capture;
- recording;
- real audio waveform state;
- transcript;
- SOAP generation;
- review/enterprise modes;
- finalization;
- recording-data deletion;
- analytics.

These capabilities MUST NOT be removed.

The current visual problem is that too many capabilities are rendered simultaneously.

v8 uses a state-driven composition.

## 1.5 Current Chat V2

`/chat` defaults to `_v2/ChatShell` unless explicitly disabled.

Existing behavior includes:
- conversation history;
- streaming;
- deep/research modes;
- saved/workspace content;
- command palette;
- source/research result handling;
- medical disclaimer;
- theme;
- localization;
- accessibility helpers.

Do NOT discard these behaviors.

Recompose them into READ_COMPOSE.

## 1.6 Current AdminShell

`apps/web/components/admin/admin-shell.tsx` renders six navigation tiles with `min-h-[90px]`.

This is explicitly rejected in v8.

Admin navigation is navigation, not page content.

## 1.7 Current Dashboard

`apps/web/app/dashboard/page.tsx` already knows the authenticated role and loads tasks/system information.

v8 retains its data/role awareness but replaces the generic greeting/dashboard-card composition with a role adapter.

---

# 2. Product expression by workspace

## Personal

**Spatial Health Companion**

Characteristics:
- light-first;
- calm;
- one next action;
- longitudinal;
- approachable;
- minimal operational jargon.

## Clinical

**Spatial Clinical Instrument**

Characteristics:
- focused;
- task-state driven;
- clear safety/uncertainty;
- information hierarchy before decoration;
- no dashboard-card walls.

## Research

**Editorial Evidence Workstation**

Characteristics:
- reading and source inspection;
- dense when useful;
- synthesis first;
- provenance and limitations visible;
- local inspector patterns.

## Admin

**Command Workbench**

Characteristics:
- operational;
- dense;
- tables/ledgers;
- attention before metrics;
- command palette;
- explicit auditability.

---

# 3. Canonical theme direction

v8 is **light-first in canonical visual QA**.

Dark theme remains fully supported.

Reason:
the current screenshots rely heavily on dark panels and borders, causing every surface to have the same visual weight.

Canonical light canvas creates clearer hierarchy.

## 3.1 Token targets

```text
canvas_light       #F6F8FB
surface_light      #FFFFFF
surface_2_light    #F1F5F9
text_light         #162033
text_2_light       #48566A
muted_light        #6D7A8E
border_light       #E1E7EF
canvas_dark        #0D1219
surface_dark       #131A23
surface_2_dark     #18212C
text_dark          #F0F4FA
text_2_dark        #B7C1CE
muted_dark         #8793A3
border_dark        #27313E
azure              #0B6FD8
azure_bright       #1A86F5
mint               #14A88D
iris               #8B7CF6
warn               #B7791F
danger             #C2413A
```


## 3.2 Dark theme rule

Dark mode is not:
“turn every area into #1B1F25 and add borders.”

Dark mode must preserve:
- hierarchy by tone;
- open canvas;
- fewer borders;
- distinct primary working surface;
- readable muted text.

## 3.3 Border rule

Use borders where they explain:
- table boundaries;
- input boundaries;
- selected state;
- inspector separation.

Do not outline every container.

## 3.4 Shadow rule

Authenticated workspaces use minimal shadow.

Floating:
- command bar;
- dock;
- drawer.

Content:
mostly tonal separation.

---

# 4. Global application shell v8

The shared shell is the most important remediation.

## 4.1 Vertical chrome budget

Desktop maximum:

```text
Preview strip, only when active       24–32px
GlobalCommandBar                      52–58px
Page/local context header             44–72px when needed
```

Do not stack multiple 70–100px navigation bands.

## 4.2 GlobalCommandBar

Contains only:

LEFT
- CLARA brand;
- workspace switcher.

CENTER
- global search / Cmd+K.

RIGHT
- help;
- notifications;
- theme;
- language;
- profile.

Does NOT contain:
- Scribe actions;
- Evidence form actions;
- Council run actions;
- Admin table filters.

## 4.3 PreviewContextStrip

Current bright yellow preview bar overwhelms the product.

New behavior:

- 24–32px;
- muted warm neutral/yellow only as a small semantic accent;
- label: `Admin Preview · Clinical`;
- text: `Presentation only · RBAC unchanged`;
- workspace preview controls grouped to right;
- collapsible;
- never overlays browser/skip link incorrectly;
- cannot cover page title;
- does not alter route access.

## 4.4 WorkspaceDock

For Personal / Clinical / Research only.

Desktop:
- 52–58px visual height;
- floating;
- max 5 primary destinations;
- central CLARA action may be visually emphasized;
- page reserves bottom space.

Clinical:
`Overview | Council | CLARA | Scribe | More`

Research:
`Research | Evidence | CLARA | Sources | More`

Personal:
`Today | LifeMap | CLARA | Medicines | Profile`

Rules:
- no duplicate top-level workspace nav elsewhere;
- no overlap with composer, stats, table footer;
- in Focus Mode it may compact, never disappear without a discoverable way back.

## 4.5 AdminCommandStrip

Admin does NOT use a consumer bottom dock.

Compact top-local navigation:

`Overview | Sources | Answer Flow | Observability | Analytics | More`

Height:
44–48px.

Keyboard:
Cmd/Ctrl+K opens All Tools.

---

# 5. Shared primitives

## 5.1 `GlobalCommandBar`

Brand, workspace switcher, global search/command, language/theme/help/profile. No page-specific actions.

## 5.2 `PreviewContextStrip`

Admin presentation-preview context; visually quiet, collapsible, never dominates page.

## 5.3 `WorkspaceDock`

Primary Personal/Clinical/Research destinations; floating but reserves layout safe area; no overlap.

## 5.4 `AdminCommandStrip`

Compact admin category navigation; replaces six 90px navigation cards.

## 5.5 `PageFrame`

Width, page title, breadcrumb/context, responsive gutters; supports instrument/workbench/full-bleed variants.

## 5.6 `SectionHeader`

Title + short supporting text + optional right action; not a card.

## 5.7 `ContextRail`

Local feature-only rail; never global navigation. Collapsible on <=1280.

## 5.8 `InspectorDrawer`

Context/source/detail inspector; right side drawer on desktop, sheet on mobile.

## 5.9 `ActionBar`

Contextual actions only; sticky only when necessary.

## 5.10 `StatusLedger`

Dense rows for operational states; replaces status-card walls.

## 5.11 `DataTable`

Sortable/filterable table with sticky header and row inspector patterns.

## 5.12 `CommandPalette`

Global Cmd/Ctrl+K; avoids duplicating tool-launch cards.

## 5.13 `FocusSurface`

Single dominant working object; editor/answer/transcript/result.

## 5.14 `StateStepper`

Workflow progress with current/complete states; compact, not six equal boxes.

## 5.15 `EvidenceSourceRow`

Source authority/provenance pattern used consistently in Chat/Evidence/Council.

## 5.16 `ClinicalSafetyNotice`

High-salience safety/uncertainty without visual panic.

## 5.17 `EmptyState`

Task-specific, one primary action; no giant empty panels.

# 6. Requirements registry

- **UX8-001** — All screenshoted authenticated surfaces MUST be rebuilt using role-specific workspace archetypes rather than the generic PageShell + SurfaceCard pattern.
- **UX8-002** — The canonical visual QA baseline MUST include light theme; dark theme remains fully supported but cannot be the only polished theme.
- **UX8-003** — Professional surfaces MUST use opaque information surfaces; glass is restricted to global navigation, floating workspace dock, popovers and transient chrome.
- **UX8-004** — A page MUST have one dominant working object. Multiple equal panels cannot compete for primary attention.
- **UX8-005** — Navigation, page controls and workflow controls MUST be visually distinguishable and must not be duplicated.
- **UX8-006** — Admin preview UI MUST remain presentation-only and MUST NOT change authorization/RBAC behavior.
- **UX8-007** — The preview context strip MUST consume <=32px height when expanded and MAY be collapsed; bright warning color cannot dominate the application.
- **UX8-008** — WorkspaceDock MUST reserve bottom safe-area space so it never overlaps tables, stats, composer, transcript or action bars.
- **UX8-009** — Admin pages MUST NOT use WorkspaceDock as primary navigation; use AdminCommandStrip and global command palette.
- **UX8-010** — Clinical/Research pages MAY use WorkspaceDock, but focus-heavy scenes can compact it while preserving discoverability.
- **UX8-011** — GlobalCommandBar MUST contain only global controls: brand, workspace, command/search, help, theme/language, profile.
- **UX8-012** — Page-specific actions MUST not be placed in GlobalCommandBar.
- **UX8-013** — Generic PageShell heading treatment MUST not dictate complex workbench layouts.
- **UX8-014** — Card count on rewritten professional pages SHOULD decrease by >=50%, and Admin Overview by >=60%.
- **UX8-015** — Large empty whitespace MUST be intentional and associated with a focused task; empty unused columns are forbidden.
- **UX8-016** — Body copy MUST use natural Vietnamese first; internal implementation terminology is kept out of ordinary/professional UI unless the page is explicitly admin/developer-facing.
- **UX8-017** — Evidence, Council and Chat source/provenance presentation MUST use a shared source-row/inspector pattern.
- **UX8-018** — Clinical uncertainty/safe-stop states MUST be visually distinct from success states.
- **UX8-019** — No page may visually imply an autonomous diagnosis or treatment decision.
- **UX8-020** — Scribe consent MUST remain explicit and precondition recording.
- **UX8-021** — Scribe Finalized/Draft/Signed semantics MUST remain distinct.
- **UX8-022** — Evidence question confirmation MUST remain explicit before deep retrieval if backend contract requires it.
- **UX8-023** — Evidence monitor/subscription is secondary to synthesis and cannot permanently occupy the primary layout.
- **UX8-024** — Chat history is contextual and cannot permanently consume >25% of viewport width at <=1440px unless user pins it.
- **UX8-025** — Admin status data SHOULD be presented as ledgers/tables where scanning/comparison matters, not metric cards.
- **UX8-026** — Desktop visual density MUST be role-appropriate: Personal calm; Clinical focused; Research analytical; Admin dense but legible.
- **UX8-027** — Light and dark themes MUST both meet WCAG 2.2 AA contrast for normal text and controls.
- **UX8-028** — At 200% zoom, all primary workflows MUST remain usable without two-dimensional page scrolling.
- **UX8-029** — At 320px viewport width, no body-level horizontal overflow.
- **UX8-030** — All primary interactions MUST support keyboard and touch/click; hover-only controls are forbidden.
- **UX8-031** — Reduced motion MUST not remove state transitions semantically; it only removes decorative motion.
- **UX8-032** — Motion MUST be localized to state changes, drawers, focus transitions and data updates; no decorative continuous animation is required for authenticated workspaces.
- **UX8-033** — No new heavyweight 3D/animation dependency is needed for these authenticated workspaces.
- **UX8-034** — Shared workbench primitives MUST use semantic tokens and not hard-coded dark-only values.
- **UX8-035** — All route authorization, owner/profile isolation, consent, CSRF, audit, safety and provenance behavior MUST be preserved.
- **UX8-036** — Aliases in the route-capability matrix MUST remain redirects/shared-flow aliases, not regain duplicate legacy UIs.
- **UX8-037** — All screenshoted routes MUST have dedicated desktop/tablet/mobile visual regression baselines.
- **UX8-038** — A route cannot be marked DONE until both implementation and visual verification are complete.
- **UX8-039** — /dashboard: MUST implement the target archetype `ROLE_ADAPTER` and remove the screenshot-specific failure pattern: The screenshot shows a generic 'Tổng quan công việc' page with a large greeting hero and a row of four tool cards. For professional users this duplicates navigation and hides the next operational decision.
- **UX8-040** — /dashboard: acceptance — Within 3 seconds a clinician can identify the next action.
- **UX8-041** — /dashboard: acceptance — Admin sees no duplicate admin home concept.
- **UX8-042** — /dashboard: acceptance — At 1440px the first viewport is >60% actionable content, not navigation/greeting.
- **UX8-043** — /chat: MUST implement the target archetype `READ_COMPOSE` and remove the screenshot-specific failure pattern: The screenshot stacks global top chrome, a permanent conversation sidebar, another local header, mode controls, disclaimer, a large empty welcome and the bottom dock. The center is visually empty while chrome consumes attention.
- **UX8-044** — /chat: acceptance — No more than one permanent sidebar.
- **UX8-045** — /chat: acceptance — No duplicated global/workspace/page navigation.
- **UX8-046** — /chat: acceptance — Empty state does not contain >4 large action tiles.
- **UX8-047** — /chat: acceptance — Clinical disclaimer remains persistent but visually quiet.
- **UX8-048** — /evidence: MUST implement the target archetype `EVIDENCE_WORKBENCH` and remove the screenshot-specific failure pattern: The current page uses a generic PageShell + two-column layout. Before research, the left side is nearly empty while a tall question form occupies the right. After execution, evidence matrix and interpretation are nested card piles rather than a research workflow.
- **UX8-049** — /evidence: acceptance — Before run, no 50/50 layout with an empty left half.
- **UX8-050** — /evidence: acceptance — After run, synthesis occupies the visual center.
- **UX8-051** — /evidence: acceptance — Source authority/provenance is inspectable without reading raw IDs.
- **UX8-052** — /evidence: acceptance — Safe-stop state cannot resemble successful evidence availability.
- **UX8-053** — /scribe: MUST implement the target archetype `SCRIBE_STATE_MACHINE` and remove the screenshot-specific failure pattern: The screenshot is overloaded: six-step row, mode tabs, consent checkbox, consent button, start button, regenerate, finalize, three columns, statistics, bottom dock. Every workflow state is visible at once, causing cognitive overload.
- **UX8-054** — /scribe: acceptance — At any state there is exactly one visually dominant primary action.
- **UX8-055** — /scribe: acceptance — Consent cannot be skipped visually or behaviorally.
- **UX8-056** — /scribe: acceptance — Recording state does not show irrelevant SOAP empty cards.
- **UX8-057** — /scribe: acceptance — Finalize is not visually equivalent to Signed/Published.
- **UX8-058** — /admin/overview: MUST implement the target archetype `ADMIN_COMMAND` and remove the screenshot-specific failure pattern: Current AdminShell itself renders six ~90px navigation tiles, and overview content adds more card groups. The screenshot becomes a dense card wall with large hero, status cards, recent table, all-tools cards, top preview controls and bottom workspace dock.
- **UX8-059** — /admin/overview: acceptance — First viewport shows attention/system state, not navigation cards.
- **UX8-060** — /admin/overview: acceptance — Card count reduced by at least 60% compared with current overview.
- **UX8-061** — /admin/overview: acceptance — Admin navigation consumes <=56px vertical space excluding global chrome.
- **UX8-062** — /council: MUST implement the target archetype `CLINICAL_DECISION` and remove the screenshot-specific failure pattern: Council risks the same pattern: form cards, agent/specialist cards, generic dashboard chrome.
- **UX8-063** — /council: acceptance — Result is decision-first.
- **UX8-064** — /council: acceptance — No autonomous-treatment framing.
- **UX8-065** — /council: acceptance — No agent-card wall.
- **UX8-066** — /research/source-hub: MUST implement the target archetype `SOURCE_WORKBENCH` and remove the screenshot-specific failure pattern: Source administration/research discovery should not be a grid of catalog cards.
- **UX8-067** — /research/source-hub: acceptance — User can scan >10 sources without scrolling through giant cards.
- **UX8-068** — /research/source-hub: acceptance — Search/filter remains visible.
- **UX8-069** — /medicines: MUST implement the target archetype `MEDICINE_WORKSPACE` and remove the screenshot-specific failure pattern: Needs coherent truth-state hierarchy and must avoid dashboard-card fragmentation.
- **UX8-070** — /medicines: acceptance — Current/cabinet distinction is unambiguous.
- **UX8-071** — /medicines: acceptance — Unavailable authority never reads as safe.
- **UX8-072** — /phr: MUST implement the target archetype `RECORD_WORKBENCH` and remove the screenshot-specific failure pattern: PHR must not be embedded in fixed-height nested panel or treated as card dashboard.
- **UX8-073** — /phr: acceptance — One page-level scroll.
- **UX8-074** — /phr: acceptance — Sharing scope visible before confirmation.
- **UX8-075** — /today: MUST implement the target archetype `PERSONAL_TODAY` and remove the screenshot-specific failure pattern: Generic stats/hero can obscure the next accepted task.
- **UX8-076** — /today: acceptance — First primary object is actionable task, not KPI cards.
- **UX8-077** — /lifemap: MUST implement the target archetype `LONGITUDINAL` and remove the screenshot-specific failure pattern: Longitudinal data must feel like a journey/timeline rather than dashboard analytics.
- **UX8-078** — /lifemap: acceptance — Timeline is primary visual.
- **UX8-079** — /lifemap: acceptance — No analytics-card wall.

---

# 7. Priority route redesign contracts

## 7.1 `/dashboard` — ROLE_ADAPTER

**Mission:** Replace generic greeting/card dashboard with role-specific operational overview; admin should not see duplicate admin home.

### Current failure

The screenshot shows a generic 'Tổng quan công việc' page with a large greeting hero and a row of four tool cards. For professional users this duplicates navigation and hides the next operational decision.

### Target

Role Adapter. `/dashboard` is not a universal dashboard template; it resolves a role-specific overview without bypassing server authorization.

### Desktop composition

- Admin: either redirect/present `/admin/overview` as canonical view, or render the same AdminCommandOverview composition. Do not maintain a separate card-heavy admin dashboard.
- Doctor: Clinical Overview with top row: Active case / recording-in-progress / evidence changes / safety attention. Primary object is 'Continue current clinical work', not a greeting.
- Researcher: Research Overview with active research question, evidence updates, source issues, recent runs.
- No giant welcome card. Name/greeting may appear as small contextual text in top header only.
- Remove four 'core tool' cards. Tools belong to WorkspaceDock / command palette.

### Required states

- Loading: structural skeleton matching final rows, not giant gray rectangles.
- Normal: next task/action first.
- Needs attention: Attention Queue appears above routine work.
- Offline/partial: explicit subsystem state while preserving available tools.

### Mobile

One priority action, attention queue, two compact recent-work rows; no desktop card grid.

### Acceptance

- Within 3 seconds a clinician can identify the next action.
- Admin sees no duplicate admin home concept.
- At 1440px the first viewport is >60% actionable content, not navigation/greeting.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.2 `/chat` — READ_COMPOSE

**Mission:** Centered clinical/research reading workspace; history is contextual, composer is dominant, sources are inspectable.

### Current failure

The screenshot stacks global top chrome, a permanent conversation sidebar, another local header, mode controls, disclaimer, a large empty welcome and the bottom dock. The center is visually empty while chrome consumes attention.

### Target

READ_COMPOSE clinical/research conversation workspace. Reading column and composer are the dominant surfaces; everything else is contextual.

### Desktop composition

- GlobalCommandBar remains at top; remove redundant local navigation that duplicates workspace chrome.
- Conversation history is a 280–320px collapsible drawer/rail, closed by default on <=1440 unless the user explicitly pins it.
- Main reading column 760–900px centered inside the available canvas.
- Composer is anchored to reading column, not viewport-wide. Reserve WorkspaceDock safe area.
- Mode selector moves into composer toolbar as a compact control; avoid a second top segmented mode bar.
- Welcome state: one calm clinical/research prompt, composer, 3–4 starter chips. Remove four large shortcut cards.
- After answer: answer hierarchy is Direct answer → What matters → Next action → Uncertainty → Sources; technical/research detail expands on demand.
- Sources open InspectorDrawer on wide desktop; inline disclosure on narrow layouts.
- History, saved content, export/share are secondary drawers/menus.

### Required states

- Empty/new chat.
- Conversation loaded.
- Streaming/retrieval running.
- Source inspector open.
- Workspace/history drawer open.
- Error/fail-closed.

### Mobile

History becomes sheet; composer remains bottom above mobile workspace nav; answer is full width within 16px gutters.

### Acceptance

- No more than one permanent sidebar.
- No duplicated global/workspace/page navigation.
- Empty state does not contain >4 large action tiles.
- Clinical disclaimer remains persistent but visually quiet.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.3 `/evidence` — EVIDENCE_WORKBENCH

**Mission:** Question → confirm → retrieve → synthesize → inspect → monitor; results dominate after execution.

### Current failure

The current page uses a generic PageShell + two-column layout. Before research, the left side is nearly empty while a tall question form occupies the right. After execution, evidence matrix and interpretation are nested card piles rather than a research workflow.

### Target

Editorial Evidence Workstation with clear state transitions: Ask → Confirm → Retrieve → Synthesize → Inspect → Monitor.

### Desktop composition

- Before question: centered Question Canvas (max 820px) with journey selector and primary question. Optional population/outcome/horizon lives under 'Add context', not permanently stacked.
- Confirmation: show compiled question, missing dimensions and one Confirm/Run action in a focused review surface.
- Running: central progress timeline with source retrieval, verification, synthesis; no fake percentage if backend has none.
- Result: switch composition to 3-area workbench: compact Source Index 240–280px; Synthesis/Interpretation reading area 680–820px; Inspector 300–360px.
- Default result tab = Synthesis, not raw matrix.
- Synthesis order: Bottom line → Applicability → Uncertainty → Contradictions → Key evidence.
- Matrix becomes secondary tab/workspace.
- Subscriptions/monitoring move to a compact 'Follow updates' popover/drawer, not a permanent right card.
- Notifications become an inbox indicator + drawer, not another card stack.

### Required states

- No LifeMap episodes.
- Question draft.
- Question confirmed.
- Run queued/retrieving/verifying.
- Evidence available.
- Safe stop/no release.
- Monitoring enabled.
- Update notification received.

### Mobile

Question full-screen; result uses synthesis first, then tabs Sources / Applicability / Uncertainty; source details as bottom sheet.

### Acceptance

- Before run, no 50/50 layout with an empty left half.
- After run, synthesis occupies the visual center.
- Source authority/provenance is inspectable without reading raw IDs.
- Safe-stop state cannot resemble successful evidence availability.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.4 `/scribe` — SCRIBE_STATE_MACHINE

**Mission:** Consent → capture → transcript → SOAP → review/finalize; layout changes with workflow state.

### Current failure

The screenshot is overloaded: six-step row, mode tabs, consent checkbox, consent button, start button, regenerate, finalize, three columns, statistics, bottom dock. Every workflow state is visible at once, causing cognitive overload.

### Target

A clinical state machine whose layout changes with the task. One state, one dominant object, one primary action.

### Desktop composition

- Idle: session picker + centered 'Start new note' / continue session. No transcript/SOAP panels until relevant.
- Consent: focused consent surface. One explicit capture-consent action. Recording controls remain disabled/secondary.
- Recording: immersive Capture Stage. Large timer, restrained waveform, pause/stop, consent status. Session rail collapses to 220px or hidden in Focus Mode. SOAP preview is not shown yet.
- Transcript Review: transcript becomes dominant 60–70% width; speaker/time editing and save. Contextual 'Generate SOAP draft' primary action.
- SOAP Review: 56/44 or 60/40 layout — SOAP draft dominant; transcript secondary and collapsible. Subjective/Objective/Assessment/Plan are document sections, not four cards.
- Finalize: summary/checklist of unresolved items, Finalize Draft action. Signing/publishing is a separate explicit stage if supported by backend.
- Enterprise Review is accessed from 'More / Review mode', not one of three always-visible tabs competing with capture.
- Remove bottom statistics strip from primary workspace; analytics belongs to separate inspector/report.

### Required states

- No session.
- Draft session, no consent.
- Consent captured.
- Recording.
- Transcribing.
- Transcript ready.
- SOAP draft ready.
- Review.
- Finalized.
- Recording data delete flow.

### Mobile

Full-screen state pages; session list is drawer; recording is edge-to-edge center stage; review switches between Transcript/SOAP tabs.

### Acceptance

- At any state there is exactly one visually dominant primary action.
- Consent cannot be skipped visually or behaviorally.
- Recording state does not show irrelevant SOAP empty cards.
- Finalize is not visually equivalent to Signed/Published.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.5 `/admin/overview` — ADMIN_COMMAND

**Mission:** Attention Queue → System Status Ledger → Operations → Audit Digest; no hero, no dashboard-card wall.

### Current failure

Current AdminShell itself renders six ~90px navigation tiles, and overview content adds more card groups. The screenshot becomes a dense card wall with large hero, status cards, recent table, all-tools cards, top preview controls and bottom workspace dock.

### Target

Admin Command Workbench. Navigation is compact; information hierarchy is operational, dense, and inspectable.

### Desktop composition

- Replace AdminShell navigation-card grid with 44–48px AdminCommandStrip: Overview / Sources / Answer Flow / Observability / Analytics / More.
- No giant 'System Command Center' hero. Top section is Attention Queue.
- Attention Queue: 0–5 ordered rows with severity, system, issue, owner/action, timestamp. Empty healthy state is one compact row.
- System Status Ledger: dense table/list of Knowledge Core / Answer Flow / RAG Eval / Data Ingestion with state, last successful check, current issue, action. Do not use 4 cards.
- Recent Operations: existing audit-like table becomes full-width primary operational history.
- Audit Digest: compact security/compliance activity list with link to immutable audit log.
- All Tools Launcher is removed from page body; expose via Cmd/Ctrl+K and a compact 'All tools' menu in AdminCommandStrip.
- System health metrics use sparklines/real charts only when data supports them; do not invent KPI tiles.

### Required states

- Healthy.
- Attention required.
- Partial subsystem failure.
- Inventory/config fetch failed.
- Preview mode.

### Mobile

Admin uses top command menu + vertical Attention Queue + status rows; no six-column card nav.

### Acceptance

- First viewport shows attention/system state, not navigation cards.
- Card count reduced by at least 60% compared with current overview.
- Admin navigation consumes <=56px vertical space excluding global chrome.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.6 `/council` — CLINICAL_DECISION

**Mission:** Case context + question + Council run; decision/result hierarchy, not agent-card theater.

### Current failure

Council risks the same pattern: form cards, agent/specialist cards, generic dashboard chrome.

### Target

Spatial Clinical Instrument focused on case → question → context → run → structured result.

### Desktop composition

- Case header compact and persistent.
- Intake uses a single guided form surface with progressive disclosure.
- Specialist selection is secondary; do not make AI agents the primary visual metaphor.
- Running state shows phases and safe-stop status.
- Result defaults to decision document: Red flags → Synthesis → Agreement/Disagreement → Uncertainty → Clinician actions → Evidence.
- Sources open right inspector.

### Required states

- New
- Intake
- Specialists
- Review
- Running
- Result
- Safe stop
- Evidence detail

### Mobile

Guided steps full screen; result document vertical.

### Acceptance

- Result is decision-first.
- No autonomous-treatment framing.
- No agent-card wall.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.7 `/council/result` — CLINICAL_RESULT

**Mission:** Red flags → synthesis → disagreement → uncertainty → actions → evidence.

## 7.8 `/research/source-hub` — SOURCE_WORKBENCH

**Mission:** Search/filter source inventory + inspector; professional research tool, not generic cards.

### Current failure

Source administration/research discovery should not be a grid of catalog cards.

### Target

Research source workbench.

### Desktop composition

- Sticky search/filter/action row.
- Main table/list with source name, type, authority, live-sync capability, last update, status.
- Inspector opens on selected source.
- Saved queries / connectors are secondary tabs.

### Required states

- Loading
- Ready
- Filtered
- Inspector open
- Offline/partial

### Mobile

Rows + filter sheet + source detail sheet.

### Acceptance

- User can scan >10 sources without scrolling through giant cards.
- Search/filter remains visible.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.9 `/medicines` — MEDICINE_WORKSPACE

**Mission:** Current/confirmed → needs confirmation → safety action → cabinet.

### Current failure

Needs coherent truth-state hierarchy and must avoid dashboard-card fragmentation.

### Target

Medication workspace with semantic states.

### Desktop composition

- Top: Current & confirmed medicines.
- Then: Needs confirmation.
- Then: Safety action/results with authority state adjacent.
- Then: Cabinet/owned products.
- Use rows, sections, and one safety focus surface; not card grid.

### Required states

- No medicines
- Current
- Needs confirmation
- Safety checking
- Authority unavailable
- Safety result
- Cabinet

### Mobile

Sectioned list + full-screen safety result.

### Acceptance

- Current/cabinet distinction is unambiguous.
- Unavailable authority never reads as safe.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.10 `/phr` — RECORD_WORKBENCH

**Mission:** Structured Health Record with local section index; no nested fixed-height page.

### Current failure

PHR must not be embedded in fixed-height nested panel or treated as card dashboard.

### Target

Health Record Workbench.

### Desktop composition

- Local section index on wide screens only.
- Record content is document/workbench style.
- Sharing/consent opens inspector/drawer.
- Edit forms use focused section route `/phr/[section]`.

### Required states

- View
- Edit
- Share scope
- Consent
- Export

### Mobile

Full-screen section pages; no nested scrolling.

### Acceptance

- One page-level scroll.
- Sharing scope visible before confirmation.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.11 `/today` — PERSONAL_TODAY

**Mission:** Next accepted task first, then upcoming/pending/journey; no generic KPI hero.

### Current failure

Generic stats/hero can obscure the next accepted task.

### Target

Personal Today.

### Desktop composition

- Date/context.
- Next accepted task as HeroObject.
- Upcoming.
- Pending confirmation.
- Journey preview.
- Utilities.
- Week/progress last.

### Required states

- Task available
- No task
- Needs confirmation
- Attention

### Mobile

One task first; secondary modules collapsed.

### Acceptance

- First primary object is actionable task, not KPI cards.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;

## 7.12 `/lifemap` — LONGITUDINAL

**Mission:** Active journey + current focus + next action + longitudinal timeline.

### Current failure

Longitudinal data must feel like a journey/timeline rather than dashboard analytics.

### Target

Longitudinal workspace.

### Desktop composition

- Active journey hero.
- Current focus.
- Next action.
- Large timeline.
- Other journeys as rows.

### Required states

- Empty
- One active journey
- Multiple journeys
- Event selected

### Mobile

Vertical timeline.

### Acceptance

- Timeline is primary visual.
- No analytics-card wall.

### Reject if

- the page can still be described as `old page + new colors`;
- every function is visible at once;
- equal cards determine the hierarchy;
- navigation competes with the working object;


# 8. Evidence detailed state machine

## E0 — Bootstrap

Visible:
- page identity;
- journey/context resolution skeleton.

Hidden:
- subscriptions;
- notifications;
- raw matrix.

## E1 — Ask

Primary object:
Question Canvas.

Fields:
- journey;
- question.

Secondary:
`Add context` expands:
- population;
- outcomes;
- horizon.

Primary action:
`Save question` / equivalent current backend semantics.

## E2 — Confirm

Show:
- normalized/compiled question;
- missing context;
- selected journey;
- boundaries.

Primary:
Confirm.

Secondary:
Edit.

## E3 — Retrieve

Show real phase language:
- preparing;
- retrieving;
- verifying;
- synthesizing.

Do not fabricate percentage.

Provide cancel if current behavior supports abort.

## E4 — Result

Default center:
Synthesis.

Structure:
1. Bottom line.
2. Applicability.
3. What remains uncertain.
4. Contradictions.
5. Key evidence.

Source Index:
local rail.

Inspector:
source details.

## E5 — Safe Stop

Strong but calm.

Show:
- no release;
- reason;
- what user can change;
- retry or edit question.

Never show green success badge beside safe stop.

## E6 — Monitor

Monitoring configuration in drawer/popover.

Updates accessible via notification center.

---

# 9. Scribe detailed state machine

## S0 — No session

Primary:
Create session.

Secondary:
Recent sessions.

## S1 — Consent required

Primary object:
Consent.

Explain:
- what will be captured;
- recording/transcript handling;
- data control;
- next step.

Primary:
Capture consent.

## S2 — Recording

Primary object:
Capture Stage.

Show:
- timer;
- microphone state;
- subtle waveform;
- stop/pause;
- session title.

Do not show:
- empty SOAP cards;
- analytics;
- 6-step strip;
- regenerate action.

## S3 — Transcribing

Show:
- recording complete;
- progress/status;
- safe wait state.

## S4 — Transcript review

Primary:
Transcript editor.

Secondary:
session context.

Primary action:
Generate/refresh SOAP.

## S5 — SOAP review

Primary:
SOAP document.

Use document sections:
Subjective
Objective
Assessment
Plan.

Do not render them as four equal dashboard cards.

Transcript available as collapsible reference.

## S6 — Finalize

Checklist:
- transcript reviewed;
- SOAP reviewed;
- unresolved warnings;
- status.

Primary:
Finalize draft.

Signing/publishing:
separate if supported.

## S7 — Data-rights action

Deletion:
explicit modal;
clear impact;
safe ordering;
result state.

---

# 10. Chat detailed layout

## 10.1 Empty

Canvas center:
- concise title;
- one explanatory sentence;
- composer;
- starter chips.

No giant four-card launcher.

## 10.2 Conversation

Main reading column:
760–900px.

Message styling:
- user turn visually compact;
- CLARA answer is document-like;
- sources and next action are separate semantic blocks.

## 10.3 History

Desktop:
drawer/local rail, collapsible.

Pinned only by user preference.

Tablet/mobile:
sheet.

## 10.4 Composer

Composer owns:
- question;
- mode;
- personal context toggle where permitted;
- send/cancel;
- small source/research options.

No separate mode header.

## 10.5 Source inspection

Right inspector:
- source;
- type;
- why relevant;
- limitations;
- open original.

---

# 11. Admin command architecture

## 11.1 Navigation

Delete the six large navigation tile pattern from AdminShell.

Replace with AdminCommandStrip.

## 11.2 Page body hierarchy

All admin pages use:

```text
compact page title/context
→ attention / state
→ primary workbench
→ secondary details
```

Not:

```text
hero
→ KPI cards
→ KPI cards
→ tool cards
```

## 11.3 Tables are allowed

Admin is a scanning/comparison domain.

Use:
- dense rows;
- sticky headers;
- filters;
- inspectors;
- saved views.

Do not avoid tables merely to appear modern.

# 12. Admin sibling route contracts

## 12.1 `/admin/overview` — Command overview

- Follow the full `/admin/overview` contract in Section 7.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.2 `/admin/knowledge-sources` — Dense source inventory + inspector

- Sticky query/filter/connection controls at top.
- Default view is dense inventory table, not cards.
- Columns: Source, category/type, authority/tier, enabled/sync state, last update, document/item count where available.
- Selecting a row opens source inspector on right; editing occurs in inspector/drawer.
- Bulk actions require explicit selection state and confirmation where destructive.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.3 `/admin/answer-flow` — Pipeline is the main object + stage inspector

- Pipeline graph/linear stage map is the primary object.
- Stages show router/retrieval/guardrail/generation/review using actual available configuration.
- Selecting stage opens inspector with config, last health/event, dependencies.
- Flow flags belong to stage inspector; no metric-card matrix.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.4 `/admin/observability` — Service health + real event/error timeline + charts + inspector

- Top compact filter bar for time range/service/severity.
- Service state ledger first.
- Real event/error timeline second.
- Charts only for data actually returned; no decorative fake graphs.
- Inspector links events to subsystem and audit context.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.5 `/admin/analytics` — Product analytics workbench

- Apply the Admin Command Workbench archetype; use dense operational rows/tables and local inspector patterns rather than card grids.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.6 `/admin/analytics/clinical` — Clinical analytics drill-down

- Apply the Admin Command Workbench archetype; use dense operational rows/tables and local inspector patterns rather than card grids.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.7 `/admin/community-moderation` — Moderation queue/workbench

- Moderation queue with content preview, reason, risk, reporter context, decision actions.
- Bulk actions carefully scoped and auditable.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.8 `/admin/dsar` — DSAR case queue + lifecycle

- Case queue ordered by deadline/state.
- Detail is lifecycle/document view with permitted actions.
- Do not use cards for each request.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.9 `/admin/audit-log` — Immutable ledger table + inspector

- Immutable ledger/table first.
- Sticky filters/search.
- Row detail inspector with actor/action/object/result and correlation metadata.
- PII/sensitive data rules preserved; UI must not reveal redacted internals.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.10 `/admin/rag-eval` — Evaluation runs + benchmark inspector

- Run/benchmark list + result comparison workbench.
- One selected evaluation run dominates; metrics grouped semantically.
- Comparison charts/tables use real data only.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.11 `/admin/rag-ingestion` — Ingestion jobs + source pipeline

- Jobs pipeline: queued/running/failed/complete.
- Source → ingest → parse/index → publish status.
- Errors show actionable stage and retry where backend permits.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.12 `/dashboard/control-tower` — Admin advanced control surface

- Apply the Admin Command Workbench archetype; use dense operational rows/tables and local inspector patterns rather than card grids.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.

## 12.13 `/dashboard/ecosystem` — System ecosystem topology/health

- Apply the Admin Command Workbench archetype; use dense operational rows/tables and local inspector patterns rather than card grids.
- Preserve RBAC, audit and backend behavior.
- Provide desktop/tablet/mobile visual regression.


# 13. Responsive architecture

## Desktop >= 1440

Use full workbench widths.

Avoid centering every page inside the same narrow 960px column.

Recommended:
- reading: 760–900px;
- standard workbench: 1180–1360px;
- dense admin: 1280–1500px;
- full-screen Scribe capture: available viewport minus shell.

## Compact desktop 1024–1439

- collapse local inspectors into drawers;
- unpin Chat history by default;
- reduce Admin columns;
- maintain one dominant object.

## Tablet 768–1023

- no 3-column Scribe;
- no fixed Evidence three-pane;
- use tabs/drawers;
- preserve GlobalCommandBar compact mode.

## Mobile <=767

- page-level one-column;
- WorkspaceDock is bottom mobile navigation where appropriate;
- admin navigation becomes top menu/command sheet;
- no nested scroll workspaces except purpose-built lists/editors;
- safe-area insets honored.

---

# 14. Motion

Authenticated app motion is purposeful and restrained.

Use:
- 140–220ms state transitions;
- 220–320ms drawers;
- 180ms hover/focus;
- no decorative parallax.

Scribe:
workflow state transition.

Evidence:
question→result composition transition.

Chat:
drawer/source inspector.

Admin:
row inspector.

`prefers-reduced-motion`:
remove transform travel; preserve opacity/state changes where necessary.

---

# 15. Accessibility

Target WCAG 2.2 AA.

Mandatory:
- semantic headings;
- landmarks;
- keyboard;
- visible focus;
- real buttons/tabs;
- aria-live only for meaningful async status;
- no excessive live-region chatter;
- 200% zoom;
- 320px reflow;
- accessible tables;
- row inspector activation by keyboard;
- Scribe recording state announced appropriately;
- Evidence polling status not announced on every poll tick.

---

# 16. Safety, privacy, security invariants

Do not change:
- server RBAC;
- route access;
- owner/profile isolation;
- consent gates;
- CSRF;
- audit logging;
- source provenance;
- DrugBank fail-closed semantics;
- emergency escalation;
- Scribe signing/finalization distinction;
- public-share shell isolation;
- no PII in analytics;
- no chain-of-thought.

Admin Preview:
presentation only.

It cannot:
- impersonate;
- widen API access;
- bypass role checks;
- change current authenticated identity.

---

# 17. Component architecture proposal

```text
apps/web/components/workspaces-v8/
  shell/
    authenticated-shell.tsx
    global-command-bar.tsx
    preview-context-strip.tsx
    workspace-dock.tsx
    admin-command-strip.tsx
    page-frame.tsx

  primitives/
    section-header.tsx
    context-rail.tsx
    inspector-drawer.tsx
    action-bar.tsx
    status-ledger.tsx
    workbench-table.tsx
    state-stepper.tsx
    source-row.tsx
    safety-notice.tsx
    focus-surface.tsx

  chat/
    chat-workbench.tsx
    history-drawer.tsx
    answer-document.tsx
    source-inspector.tsx

  evidence/
    evidence-workbench.tsx
    question-canvas.tsx
    confirmation-review.tsx
    run-progress.tsx
    synthesis-document.tsx
    source-index.tsx
    evidence-inspector.tsx

  scribe/
    scribe-workbench.tsx
    session-drawer.tsx
    consent-stage.tsx
    capture-stage.tsx
    transcript-stage.tsx
    soap-review-stage.tsx
    finalize-stage.tsx

  admin/
    admin-workbench-frame.tsx
    attention-queue.tsx
    system-status-ledger.tsx
    operations-ledger.tsx
    audit-digest.tsx
```

Do not force exact filenames if current architecture has better ownership boundaries.

---

# 18. Migration strategy

## Phase 0 — Visual freeze

Capture current screenshots for all P0 routes.

## Phase 1 — Shell

Implement shared chrome first.

Do not mix shell and page redesign in one giant PR unless orchestration can isolate changes.

## Phase 2 — P0 pages

Parallel:
- Dashboard;
- Chat;
- Evidence;
- Scribe;
- Admin Overview.

## Phase 3 — Clinical/Research siblings

- Council;
- Source Hub;
- PHR;
- Medicines;
- LifeMap;
- Today.

## Phase 4 — Admin family

All canonical admin routes.

## Phase 5 — aliases & cleanup

Ensure aliases redirect only.

Remove legacy duplicate navigation/card-shell patterns after verification.

---

# 19. Multi-agent execution

**Required: maintain 20–30 ACTIVE subagents concurrently whenever independent work exists.**

One orchestrator.

Suggested active allocation during P0:

```text
01 orchestrator
02 shared shell owner
03 preview strip
04 global command bar
05 workspace dock
06 admin command strip
07 token/theme
08 dashboard
09 dashboard tests
10 chat layout
11 chat history/composer
12 chat source inspector
13 chat a11y
14 evidence state machine
15 evidence result workbench
16 evidence tests
17 scribe state machine
18 scribe capture
19 scribe transcript/SOAP
20 scribe tests
21 admin overview
22 admin status ledger
23 admin ops/audit
24 mobile
25 tablet
26 accessibility
27 visual regression
28 performance
29 safety/security review
30 integration reviewer
```

Refill slots immediately.

---

# 20. Verification matrix

Required viewports:

```text
1920x1080
1728x1117
1536x960
1440x900
1366x768
1280x800
1024x768
820x1180
768x1024
430x932
390x844
375x812
360x800
320x800
```

Required themes:
- Light canonical.
- Dark.

Required modes:
- normal role;
- doctor;
- researcher;
- admin;
- Admin Preview where permitted.

Required additional:
- 200% zoom;
- keyboard only;
- reduced motion.

---

# 21. Visual scoring rubric

Each P0 route scores 0–10:

- Hierarchy.
- Task clarity.
- Navigation clarity.
- Density appropriateness.
- Product identity.
- Visual refinement.
- Responsive quality.
- Accessibility.
- Safety semantics.
- Consistency.

Release:
- no P0 route below 8.5;
- hierarchy/task clarity >=9;
- no safety/accessibility category below 9.

---

# 22. Global rejection checklist

FAIL if:

- six-card AdminShell navigation remains;
- Dashboard still begins with a giant greeting hero;
- Chat still has permanent history + local nav + mode bar + bottom dock all competing;
- Evidence still uses empty left / tall right form layout;
- Scribe still renders all workflow stages simultaneously;
- Scribe recording state still shows empty SOAP boxes;
- Admin Overview remains a card wall;
- bottom dock overlaps content;
- preview bar covers/clips page title;
- dark theme still relies on outlining every box;
- light theme is unpolished;
- page is only recolored, not recomposed.

---

# 23. Detailed task backlog

The following task list is intentionally granular so the orchestrator can keep 20–30 agents active without inventing unsafe overlapping work.

## 23.1 Audit & screenshot mapping

- **WS8-0001** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0002** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0003** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0004** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0005** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0006** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0007** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0008** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0009** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0010** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0011** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0012** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0013** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0014** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0015** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0016** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0017** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0018** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0019** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0020** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0021** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0022** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0023** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0024** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0025** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0026** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0027** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0028** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0029** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0030** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0031** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0032** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0033** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0034** [P0] — audit or document one current screenshot/route/component/layout failure and map it to an owned remediation #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.2 Shared shell/chrome

- **WS8-0035** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0036** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0037** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0038** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0039** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0040** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0041** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0042** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0043** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0044** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0045** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0046** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0047** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0048** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0049** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0050** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0051** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0052** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0053** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0054** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0055** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0056** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0057** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0058** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0059** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0060** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0061** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0062** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0063** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0064** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0065** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0066** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0067** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0068** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0069** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0070** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0071** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0072** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0073** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0074** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0075** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0076** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0077** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0078** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0079** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0080** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0081** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0082** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0083** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0084** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0085** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0086** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0087** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0088** [P0] — implement or verify one shared shell, PageFrame, command bar, dock, safe-area or inspector behavior #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.3 Design tokens/themes

- **WS8-0089** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0090** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0091** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0092** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0093** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0094** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0095** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0096** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0097** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0098** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0099** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0100** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0101** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0102** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0103** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0104** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0105** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0106** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0107** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0108** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0109** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0110** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0111** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0112** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0113** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0114** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0115** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0116** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0117** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0118** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0119** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0120** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0121** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0122** [P0] — implement or verify one semantic token/light-dark/contrast/border/surface rule #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.4 Navigation & preview mode

- **WS8-0123** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0124** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0125** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0126** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0127** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0128** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0129** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0130** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0131** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0132** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0133** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0134** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0135** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0136** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0137** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0138** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0139** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0140** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0141** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0142** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0143** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0144** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0145** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0146** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0147** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0148** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0149** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0150** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0151** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0152** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0153** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0154** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0155** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0156** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0157** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0158** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0159** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0160** [P0] — implement or test one workspace navigation, Admin Preview, scroll/active state, or duplication-removal rule #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.5 Dashboard role adapter

- **WS8-0161** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0162** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0163** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0164** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0165** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0166** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0167** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0168** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0169** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0170** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0171** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0172** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0173** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0174** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0175** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0176** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0177** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0178** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0179** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0180** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0181** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0182** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0183** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0184** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0185** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0186** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0187** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0188** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0189** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0190** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0191** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0192** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0193** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0194** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0195** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0196** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0197** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0198** [P0] — implement or test one role-specific Dashboard composition/state/action/responsive rule #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.6 Chat READ_COMPOSE

- **WS8-0199** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0200** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0201** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0202** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0203** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0204** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0205** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0206** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0207** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0208** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0209** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0210** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0211** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0212** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0213** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0214** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0215** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0216** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0217** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0218** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0219** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0220** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0221** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0222** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0223** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0224** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0225** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0226** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0227** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0228** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0229** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0230** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0231** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0232** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0233** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0234** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0235** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0236** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0237** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0238** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0239** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0240** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0241** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0242** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0243** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0244** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0245** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0246** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0247** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0248** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0249** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0250** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0251** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0252** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0253** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0254** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0255** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0256** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0257** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0258** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0259** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0260** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0261** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0262** [P0] — implement or test one Chat canvas/history/composer/source/mode/welcome/responsive behavior #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.7 Evidence workbench

- **WS8-0263** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0264** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0265** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0266** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0267** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0268** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0269** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0270** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0271** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0272** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0273** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0274** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0275** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0276** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0277** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0278** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0279** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0280** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0281** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0282** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0283** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0284** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0285** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0286** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0287** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0288** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0289** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0290** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0291** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0292** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0293** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0294** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0295** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0296** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0297** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0298** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0299** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0300** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0301** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0302** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0303** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0304** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0305** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0306** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0307** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0308** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0309** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0310** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0311** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0312** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0313** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0314** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0315** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0316** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0317** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0318** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0319** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0320** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0321** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0322** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0323** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0324** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0325** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0326** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0327** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #65.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0328** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #66.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0329** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #67.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0330** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #68.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0331** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #69.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0332** [P0] — implement or test one Evidence Ask/Confirm/Run/Synthesis/Source/Monitor state or transition #70.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.8 Scribe state machine

- **WS8-0333** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0334** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0335** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0336** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0337** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0338** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0339** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0340** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0341** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0342** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0343** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0344** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0345** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0346** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0347** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0348** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0349** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0350** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0351** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0352** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0353** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0354** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0355** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0356** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0357** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0358** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0359** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0360** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0361** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0362** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0363** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0364** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0365** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0366** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0367** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0368** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0369** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0370** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0371** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0372** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0373** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0374** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0375** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0376** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0377** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0378** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0379** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0380** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0381** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0382** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0383** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0384** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0385** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0386** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0387** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0388** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0389** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0390** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0391** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0392** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0393** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0394** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0395** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0396** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0397** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #65.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0398** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #66.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0399** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #67.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0400** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #68.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0401** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #69.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0402** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #70.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0403** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #71.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0404** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #72.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0405** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #73.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0406** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #74.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0407** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #75.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0408** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #76.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0409** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #77.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0410** [P0] — implement or test one Scribe consent/capture/transcript/SOAP/review/finalize state or transition #78.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.9 Council clinical instrument

- **WS8-0411** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0412** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0413** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0414** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0415** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0416** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0417** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0418** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0419** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0420** [P0] — implement or test one Council case/question/run/result/evidence/responsive rule #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0421** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0422** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0423** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0424** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0425** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0426** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0427** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0428** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0429** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0430** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0431** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0432** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0433** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0434** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0435** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0436** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0437** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0438** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0439** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0440** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0441** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0442** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0443** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0444** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0445** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0446** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0447** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0448** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0449** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0450** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0451** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0452** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0453** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0454** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0455** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0456** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0457** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0458** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0459** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0460** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0461** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0462** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0463** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0464** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0465** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0466** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0467** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0468** [P1] — implement or test one Council case/question/run/result/evidence/responsive rule #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.10 Medicines + PHR + LifeMap + Today

- **WS8-0469** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0470** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0471** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0472** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0473** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0474** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0475** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0476** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0477** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0478** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0479** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0480** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0481** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0482** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0483** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0484** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0485** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0486** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0487** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0488** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0489** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0490** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0491** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0492** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0493** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0494** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0495** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0496** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0497** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0498** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0499** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0500** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0501** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0502** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0503** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0504** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0505** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0506** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0507** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0508** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0509** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0510** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0511** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0512** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0513** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0514** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0515** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0516** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0517** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0518** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0519** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0520** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0521** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0522** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0523** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0524** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0525** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0526** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0527** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0528** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0529** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0530** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0531** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0532** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0533** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #65.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0534** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #66.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0535** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #67.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0536** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #68.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0537** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #69.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0538** [P1] — implement or test one personal/core health workspace hierarchy or responsive contract #70.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.11 Admin command architecture

- **WS8-0539** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0540** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0541** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0542** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0543** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0544** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0545** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0546** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0547** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0548** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0549** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0550** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0551** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0552** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0553** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0554** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0555** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0556** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0557** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0558** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0559** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0560** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0561** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0562** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0563** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0564** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0565** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0566** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0567** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0568** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0569** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0570** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0571** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0572** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0573** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0574** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0575** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0576** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0577** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0578** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0579** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0580** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0581** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0582** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0583** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0584** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0585** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0586** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0587** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0588** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0589** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0590** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0591** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0592** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0593** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0594** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0595** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0596** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0597** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0598** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0599** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0600** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0601** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0602** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0603** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #65.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0604** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #66.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0605** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #67.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0606** [P1] — implement or test one AdminCommandStrip/table/ledger/inspector/command-palette primitive #68.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.12 Admin overview

- **WS8-0607** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0608** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0609** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0610** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0611** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0612** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0613** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0614** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0615** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0616** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0617** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0618** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0619** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0620** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0621** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0622** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0623** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0624** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0625** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0626** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0627** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0628** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0629** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0630** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0631** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0632** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0633** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0634** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0635** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0636** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0637** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0638** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0639** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0640** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0641** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0642** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0643** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0644** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0645** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0646** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0647** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0648** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0649** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0650** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0651** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0652** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0653** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0654** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0655** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0656** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0657** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0658** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0659** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0660** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0661** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0662** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0663** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0664** [P1] — implement or test one Attention Queue/System Ledger/Operations/Audit Digest state #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.13 Admin sibling pages

- **WS8-0665** [P1] — migrate or test one canonical Admin route or shared operational pattern #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0666** [P1] — migrate or test one canonical Admin route or shared operational pattern #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0667** [P1] — migrate or test one canonical Admin route or shared operational pattern #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0668** [P1] — migrate or test one canonical Admin route or shared operational pattern #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0669** [P1] — migrate or test one canonical Admin route or shared operational pattern #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0670** [P1] — migrate or test one canonical Admin route or shared operational pattern #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0671** [P1] — migrate or test one canonical Admin route or shared operational pattern #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0672** [P1] — migrate or test one canonical Admin route or shared operational pattern #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0673** [P1] — migrate or test one canonical Admin route or shared operational pattern #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0674** [P1] — migrate or test one canonical Admin route or shared operational pattern #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0675** [P1] — migrate or test one canonical Admin route or shared operational pattern #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0676** [P1] — migrate or test one canonical Admin route or shared operational pattern #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0677** [P1] — migrate or test one canonical Admin route or shared operational pattern #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0678** [P1] — migrate or test one canonical Admin route or shared operational pattern #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0679** [P1] — migrate or test one canonical Admin route or shared operational pattern #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0680** [P1] — migrate or test one canonical Admin route or shared operational pattern #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0681** [P1] — migrate or test one canonical Admin route or shared operational pattern #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0682** [P1] — migrate or test one canonical Admin route or shared operational pattern #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0683** [P1] — migrate or test one canonical Admin route or shared operational pattern #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0684** [P1] — migrate or test one canonical Admin route or shared operational pattern #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0685** [P1] — migrate or test one canonical Admin route or shared operational pattern #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0686** [P1] — migrate or test one canonical Admin route or shared operational pattern #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0687** [P1] — migrate or test one canonical Admin route or shared operational pattern #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0688** [P1] — migrate or test one canonical Admin route or shared operational pattern #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0689** [P1] — migrate or test one canonical Admin route or shared operational pattern #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0690** [P1] — migrate or test one canonical Admin route or shared operational pattern #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0691** [P1] — migrate or test one canonical Admin route or shared operational pattern #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0692** [P1] — migrate or test one canonical Admin route or shared operational pattern #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0693** [P1] — migrate or test one canonical Admin route or shared operational pattern #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0694** [P1] — migrate or test one canonical Admin route or shared operational pattern #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0695** [P1] — migrate or test one canonical Admin route or shared operational pattern #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0696** [P1] — migrate or test one canonical Admin route or shared operational pattern #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0697** [P1] — migrate or test one canonical Admin route or shared operational pattern #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0698** [P1] — migrate or test one canonical Admin route or shared operational pattern #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0699** [P1] — migrate or test one canonical Admin route or shared operational pattern #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0700** [P1] — migrate or test one canonical Admin route or shared operational pattern #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0701** [P1] — migrate or test one canonical Admin route or shared operational pattern #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0702** [P1] — migrate or test one canonical Admin route or shared operational pattern #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0703** [P1] — migrate or test one canonical Admin route or shared operational pattern #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0704** [P1] — migrate or test one canonical Admin route or shared operational pattern #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0705** [P1] — migrate or test one canonical Admin route or shared operational pattern #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0706** [P1] — migrate or test one canonical Admin route or shared operational pattern #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0707** [P1] — migrate or test one canonical Admin route or shared operational pattern #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0708** [P1] — migrate or test one canonical Admin route or shared operational pattern #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0709** [P1] — migrate or test one canonical Admin route or shared operational pattern #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0710** [P1] — migrate or test one canonical Admin route or shared operational pattern #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0711** [P1] — migrate or test one canonical Admin route or shared operational pattern #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0712** [P1] — migrate or test one canonical Admin route or shared operational pattern #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0713** [P1] — migrate or test one canonical Admin route or shared operational pattern #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0714** [P1] — migrate or test one canonical Admin route or shared operational pattern #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0715** [P1] — migrate or test one canonical Admin route or shared operational pattern #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0716** [P1] — migrate or test one canonical Admin route or shared operational pattern #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0717** [P1] — migrate or test one canonical Admin route or shared operational pattern #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0718** [P1] — migrate or test one canonical Admin route or shared operational pattern #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0719** [P1] — migrate or test one canonical Admin route or shared operational pattern #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0720** [P1] — migrate or test one canonical Admin route or shared operational pattern #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0721** [P1] — migrate or test one canonical Admin route or shared operational pattern #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0722** [P1] — migrate or test one canonical Admin route or shared operational pattern #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0723** [P1] — migrate or test one canonical Admin route or shared operational pattern #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0724** [P1] — migrate or test one canonical Admin route or shared operational pattern #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0725** [P1] — migrate or test one canonical Admin route or shared operational pattern #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0726** [P1] — migrate or test one canonical Admin route or shared operational pattern #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0727** [P1] — migrate or test one canonical Admin route or shared operational pattern #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0728** [P1] — migrate or test one canonical Admin route or shared operational pattern #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0729** [P1] — migrate or test one canonical Admin route or shared operational pattern #65.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0730** [P1] — migrate or test one canonical Admin route or shared operational pattern #66.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0731** [P1] — migrate or test one canonical Admin route or shared operational pattern #67.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0732** [P1] — migrate or test one canonical Admin route or shared operational pattern #68.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0733** [P1] — migrate or test one canonical Admin route or shared operational pattern #69.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0734** [P1] — migrate or test one canonical Admin route or shared operational pattern #70.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0735** [P1] — migrate or test one canonical Admin route or shared operational pattern #71.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0736** [P1] — migrate or test one canonical Admin route or shared operational pattern #72.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0737** [P1] — migrate or test one canonical Admin route or shared operational pattern #73.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0738** [P1] — migrate or test one canonical Admin route or shared operational pattern #74.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0739** [P1] — migrate or test one canonical Admin route or shared operational pattern #75.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0740** [P1] — migrate or test one canonical Admin route or shared operational pattern #76.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.14 Research source hub

- **WS8-0741** [P1] — implement or test one source list/filter/inspector/status behavior #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0742** [P1] — implement or test one source list/filter/inspector/status behavior #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0743** [P1] — implement or test one source list/filter/inspector/status behavior #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0744** [P1] — implement or test one source list/filter/inspector/status behavior #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0745** [P1] — implement or test one source list/filter/inspector/status behavior #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0746** [P1] — implement or test one source list/filter/inspector/status behavior #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0747** [P1] — implement or test one source list/filter/inspector/status behavior #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0748** [P1] — implement or test one source list/filter/inspector/status behavior #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0749** [P1] — implement or test one source list/filter/inspector/status behavior #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0750** [P1] — implement or test one source list/filter/inspector/status behavior #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0751** [P1] — implement or test one source list/filter/inspector/status behavior #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0752** [P1] — implement or test one source list/filter/inspector/status behavior #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0753** [P1] — implement or test one source list/filter/inspector/status behavior #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0754** [P1] — implement or test one source list/filter/inspector/status behavior #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0755** [P1] — implement or test one source list/filter/inspector/status behavior #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0756** [P1] — implement or test one source list/filter/inspector/status behavior #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0757** [P1] — implement or test one source list/filter/inspector/status behavior #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0758** [P1] — implement or test one source list/filter/inspector/status behavior #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0759** [P1] — implement or test one source list/filter/inspector/status behavior #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0760** [P1] — implement or test one source list/filter/inspector/status behavior #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0761** [P1] — implement or test one source list/filter/inspector/status behavior #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0762** [P1] — implement or test one source list/filter/inspector/status behavior #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0763** [P1] — implement or test one source list/filter/inspector/status behavior #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0764** [P1] — implement or test one source list/filter/inspector/status behavior #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0765** [P1] — implement or test one source list/filter/inspector/status behavior #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0766** [P1] — implement or test one source list/filter/inspector/status behavior #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0767** [P1] — implement or test one source list/filter/inspector/status behavior #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0768** [P1] — implement or test one source list/filter/inspector/status behavior #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0769** [P1] — implement or test one source list/filter/inspector/status behavior #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0770** [P1] — implement or test one source list/filter/inspector/status behavior #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0771** [P1] — implement or test one source list/filter/inspector/status behavior #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0772** [P1] — implement or test one source list/filter/inspector/status behavior #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.15 Responsive/tablet/mobile

- **WS8-0773** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0774** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0775** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0776** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0777** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0778** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0779** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0780** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0781** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0782** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0783** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0784** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0785** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0786** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0787** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0788** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0789** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0790** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0791** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0792** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0793** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0794** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0795** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0796** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0797** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0798** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0799** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0800** [P1] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0801** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0802** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0803** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0804** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0805** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0806** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0807** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0808** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0809** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0810** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0811** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0812** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0813** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0814** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0815** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0816** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0817** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0818** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0819** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0820** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0821** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0822** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0823** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0824** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0825** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #53.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0826** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #54.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0827** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #55.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0828** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #56.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0829** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #57.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0830** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #58.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0831** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #59.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0832** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #60.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0833** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #61.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0834** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #62.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0835** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #63.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0836** [P2] — recompose or verify one route at one target breakpoint, including dock/safe-area behavior #64.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.16 Accessibility

- **WS8-0837** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0838** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0839** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0840** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0841** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0842** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0843** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0844** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0845** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0846** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0847** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0848** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0849** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0850** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0851** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0852** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0853** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0854** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0855** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0856** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0857** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0858** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0859** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0860** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0861** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0862** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0863** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0864** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0865** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0866** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0867** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0868** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0869** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0870** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0871** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0872** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0873** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0874** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0875** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0876** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0877** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0878** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0879** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0880** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0881** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0882** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0883** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0884** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0885** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #49.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0886** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #50.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0887** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #51.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0888** [P2] — verify or fix one keyboard/focus/semantic/live-region/contrast/zoom/reflow issue #52.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.17 Performance

- **WS8-0889** [P2] — profile or optimize one render/list/observer/bundle/layout issue #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0890** [P2] — profile or optimize one render/list/observer/bundle/layout issue #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0891** [P2] — profile or optimize one render/list/observer/bundle/layout issue #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0892** [P2] — profile or optimize one render/list/observer/bundle/layout issue #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0893** [P2] — profile or optimize one render/list/observer/bundle/layout issue #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0894** [P2] — profile or optimize one render/list/observer/bundle/layout issue #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0895** [P2] — profile or optimize one render/list/observer/bundle/layout issue #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0896** [P2] — profile or optimize one render/list/observer/bundle/layout issue #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0897** [P2] — profile or optimize one render/list/observer/bundle/layout issue #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0898** [P2] — profile or optimize one render/list/observer/bundle/layout issue #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0899** [P2] — profile or optimize one render/list/observer/bundle/layout issue #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0900** [P2] — profile or optimize one render/list/observer/bundle/layout issue #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0901** [P2] — profile or optimize one render/list/observer/bundle/layout issue #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0902** [P2] — profile or optimize one render/list/observer/bundle/layout issue #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0903** [P2] — profile or optimize one render/list/observer/bundle/layout issue #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0904** [P2] — profile or optimize one render/list/observer/bundle/layout issue #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0905** [P2] — profile or optimize one render/list/observer/bundle/layout issue #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0906** [P2] — profile or optimize one render/list/observer/bundle/layout issue #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0907** [P2] — profile or optimize one render/list/observer/bundle/layout issue #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0908** [P2] — profile or optimize one render/list/observer/bundle/layout issue #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0909** [P2] — profile or optimize one render/list/observer/bundle/layout issue #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0910** [P2] — profile or optimize one render/list/observer/bundle/layout issue #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0911** [P2] — profile or optimize one render/list/observer/bundle/layout issue #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0912** [P2] — profile or optimize one render/list/observer/bundle/layout issue #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0913** [P2] — profile or optimize one render/list/observer/bundle/layout issue #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0914** [P2] — profile or optimize one render/list/observer/bundle/layout issue #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0915** [P2] — profile or optimize one render/list/observer/bundle/layout issue #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0916** [P2] — profile or optimize one render/list/observer/bundle/layout issue #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0917** [P2] — profile or optimize one render/list/observer/bundle/layout issue #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0918** [P2] — profile or optimize one render/list/observer/bundle/layout issue #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0919** [P2] — profile or optimize one render/list/observer/bundle/layout issue #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0920** [P2] — profile or optimize one render/list/observer/bundle/layout issue #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0921** [P2] — profile or optimize one render/list/observer/bundle/layout issue #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0922** [P2] — profile or optimize one render/list/observer/bundle/layout issue #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.18 Safety/security invariants

- **WS8-0923** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0924** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0925** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0926** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0927** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0928** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0929** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0930** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0931** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0932** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0933** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0934** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0935** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0936** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0937** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0938** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0939** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0940** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0941** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0942** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0943** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0944** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0945** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0946** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0947** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0948** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0949** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0950** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0951** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0952** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0953** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0954** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0955** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0956** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0957** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0958** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0959** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0960** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0961** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0962** [P2] — verify one RBAC/consent/source/safe-stop/PII/audit/signing invariant after UI rewrite #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.19 Visual regression

- **WS8-0963** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0964** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0965** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0966** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0967** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0968** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0969** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0970** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0971** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0972** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0973** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0974** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0975** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0976** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0977** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0978** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0979** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0980** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0981** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0982** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0983** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0984** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0985** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0986** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0987** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0988** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0989** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0990** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0991** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0992** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0993** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0994** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0995** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0996** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0997** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0998** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-0999** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1000** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1001** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1002** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1003** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1004** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1005** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #43.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1006** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #44.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1007** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #45.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1008** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #46.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1009** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #47.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1010** [P2] — capture/review one route/theme/viewport visual baseline and record acceptance #48.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.

## 23.20 Integration/release

- **WS8-1011** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #1.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1012** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #2.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1013** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #3.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1014** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #4.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1015** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #5.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1016** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #6.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1017** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #7.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1018** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #8.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1019** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #9.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1020** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #10.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1021** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #11.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1022** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #12.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1023** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #13.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1024** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #14.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1025** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #15.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1026** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #16.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1027** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #17.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1028** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #18.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1029** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #19.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1030** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #20.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1031** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #21.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1032** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #22.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1033** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #23.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1034** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #24.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1035** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #25.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1036** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #26.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1037** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #27.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1038** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #28.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1039** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #29.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1040** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #30.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1041** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #31.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1042** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #32.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1043** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #33.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1044** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #34.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1045** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #35.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1046** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #36.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1047** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #37.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1048** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #38.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1049** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #39.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1050** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #40.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1051** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #41.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.
- **WS8-1052** [P2] — perform one integration, cleanup, alias, build, type, E2E, rollback, or final review gate #42.
  - Owner must declare files before editing.
  - Acceptance must be objective and screenshot/test verifiable.
  - Task is not DONE until VERIFIED.


# 24. Task count

**Total detailed tasks: 1052**

The size is intentional.

Codex MUST keep **20–30 subagents active concurrently** where the dependency graph permits.

---

# 25. Definition of Done

v8 is complete only when:

1. Global chrome is visually simplified.
2. Preview strip no longer dominates or clips content.
3. Bottom WorkspaceDock never overlaps page content.
4. Admin uses AdminCommandStrip, not navigation cards.
5. Light theme is canonical-quality.
6. Dark theme is equally coherent.
7. `/dashboard` is role-adaptive.
8. Admin does not receive a duplicate generic dashboard.
9. `/chat` is READ_COMPOSE.
10. Chat history is contextual.
11. Chat welcome is simplified.
12. Composer owns mode controls.
13. Chat source inspector works.
14. `/evidence` uses state-dependent composition.
15. Evidence Ask state is centered/focused.
16. Evidence Result is synthesis-first.
17. Evidence monitoring is secondary.
18. Safe-stop is distinct.
19. `/scribe` uses workflow states.
20. Consent is explicit.
21. Recording is immersive/focused.
22. Transcript review is dominant when appropriate.
23. SOAP is a document, not four cards.
24. Finalize remains distinct from signing.
25. `/admin/overview` starts with Attention Queue.
26. Admin uses status ledgers/tables.
27. Operations and audit are scannable.
28. Admin card count is reduced >=60%.
29. `/council` is decision-first.
30. `/research/source-hub` is a workbench.
31. Medicines truth states are clear.
32. PHR has one page-level scroll.
33. LifeMap is longitudinal.
34. Today prioritizes next accepted action.
35. All canonical admin routes follow command-workbench patterns.
36. Aliases do not regain duplicate UIs.
37. 320px passes.
38. 200% zoom passes.
39. Keyboard passes.
40. Reduced motion passes.
41. Light/dark contrast passes.
42. No PII analytics regression.
43. No RBAC regression.
44. No consent regression.
45. No provenance/safety regression.
46. Build passes.
47. Type-check passes.
48. Unit tests pass.
49. E2E passes.
50. Visual regression approved for all P0 routes.
51. Independent UI review gives every P0 route >=8.5/10.
52. No screenshot can reasonably be described as `card wall + duplicated navigation`.

---

# 26. Final design law

**Personal:** next action and longitudinal context.

**Clinical:** one clinical task, one dominant instrument.

**Research:** synthesis and evidence inspection.

**Admin:** attention, system state, operations, audit.

Never use one generic dashboard pattern for all four.

---

# 27. Embedded /goal

```text
/goal

Rebuild the CLARA Care authenticated Web workspaces according to
CLARA_Care_Authenticated_Workspaces_UIUX_Rebuild_v8_Full_Spec.md.

Repository:
Project-CLARA-HBT/CLARA-Care

Audited baseline:
81c024d74ea9201b31e22b5c02b1b6f852c0ce9e

PRIMARY FAILURE TO FIX

The current authenticated app is visually overloaded and structurally generic:
too many navigation layers, too many bordered cards, dark panel walls,
weak task hierarchy, duplicated tool launchers, and workflows that display
every state simultaneously.

This is not a styling pass.

Reconstruct the shared shell and the major workspaces.

REQUIRED PRODUCT EXPRESSIONS

Personal → Spatial Health Companion
Clinical → Spatial Clinical Instrument
Research → Editorial Evidence Workstation
Admin → Command Workbench

P0 ROUTES

/dashboard
/chat
/evidence
/scribe
/admin/overview

P1

/council
/council/result
/research/source-hub
/medicines
/phr
/lifemap
/today
all canonical /admin/* workspaces

HARD CONCURRENCY REQUIREMENT

Maintain 20–30 SUBAGENTS ACTIVE AT THE SAME TIME whenever independent work exists.

This is active concurrency, not total agents over the lifetime of the task.

Use one orchestrator.
Use explicit file ownership.
Immediately refill completed slots.
Do not serialize independent page work.

GLOBAL SHELL

Implement:
GlobalCommandBar
PreviewContextStrip
WorkspaceDock
AdminCommandStrip
PageFrame
ContextRail
InspectorDrawer
ActionBar

Remove duplicated navigation.

Preview mode must remain presentation-only and must never bypass RBAC.

WorkspaceDock must reserve layout safe area and never overlay real content.

Admin must not use consumer bottom dock as its primary navigation.

DASHBOARD

Make /dashboard a role adapter.

Admin → canonical Admin overview.
Doctor → Clinical Overview.
Researcher → Research Overview.
Normal → Today/Personal.

Remove giant greeting hero and four-tool card launcher.

CHAT

Implement READ_COMPOSE.

Centered reading column.
Composer dominant.
History contextual/collapsible.
Mode controls inside composer.
Sources in inspector.
No duplicated local header/navigation.
No large welcome card grid.

EVIDENCE

Implement:
Ask
→ Confirm
→ Retrieve
→ Synthesize
→ Inspect
→ Monitor.

Before run:
centered question canvas.

After run:
Synthesis first.
Source Index + reading area + Inspector on wide desktop.

Monitoring and notifications are secondary.

SCRIBE

Implement true state machine:

No session
→ Consent
→ Recording
→ Transcript
→ SOAP Review
→ Finalize.

Do not render every state simultaneously.

Recording is a focused capture stage.
Transcript is dominant during transcript review.
SOAP is a document, not four cards.
Finalize is not Signed.

ADMIN

Delete six 90px navigation cards from AdminShell.

Use compact AdminCommandStrip.

Admin Overview:

Attention Queue
→ System Status Ledger
→ Recent Operations
→ Audit Digest.

No giant hero.
No status-card wall.
No All Tools card launcher.

Use command palette for tool launch.

VISUAL

Canonical QA is light-first.
Dark theme remains supported.

Reduce cards by >=50% on professional pages.
Admin Overview >=60%.

Glass:
navigation/transient chrome only.

Clinical/research/admin content:
opaque.

Do not solve hierarchy with borders around everything.

RESPONSIVE

Desktop, tablet, mobile are separate compositions.

No 3-column Scribe on tablet/mobile.
No fixed Evidence 3-pane on mobile.
No permanent Chat history on compact widths.
No six-column Admin navigation at any breakpoint.

ACCESSIBILITY

WCAG 2.2 AA.
Keyboard.
Focus.
320px.
200% zoom.
Reduced motion.
Accessible tables/tabs/drawers.

SAFETY

Preserve:
server RBAC
profile isolation
consent
CSRF
audit
provenance
fail-closed safety
emergency handling
Scribe status semantics
no PII analytics
no chain-of-thought.

EXECUTION

Wave 0:
audit + screenshot baselines.

Wave 1:
shared shell/chrome.

Wave 2:
P0 routes in parallel.

Wave 3:
clinical/research/personal siblings.

Wave 4:
admin family.

Wave 5:
responsive/a11y/performance.

Wave 6:
independent visual review and refinement.

Keep 20–30 active agents throughout independent waves.

DONE means VERIFIED.

Do not stop when pages merely compile.

Do not stop at “better than before”.

Continue until:
- navigation is coherent;
- each page has one dominant working object;
- the screenshots no longer resemble dark card dashboards;
- P0 visual QA >=8.5/10;
- task hierarchy >=9/10;
- all safety/accessibility gates pass.

Final rejection test:

If a page can still be described as
“the old CLARA page with new colors and rounded panels”,
it is NOT DONE.
```
