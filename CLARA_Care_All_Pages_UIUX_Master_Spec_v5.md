
# CLARA Care — All-Pages UI/UX Transformation Master Spec v5

**Repository:** Project-CLARA-HBT/CLARA-Care  
**Audited baseline:** `main@81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`  
**Web route coverage:** 79/79 App Router `page.tsx` routes  
**Targets:** Web + Flutter Mobile  
**Primary locale:** Vietnamese; English parity required  
**Purpose:** force a true product-wide UI/UX transformation rather than a reskin.

---

## 0. Non-negotiable outcome

A page is **not migrated** because it has new colors, larger radius, glass, a floating dock, or new typography.

A page is migrated only when its:

- information order;
- primary object;
- page composition;
- navigation relationship;
- responsive composition;
- empty/loading/error behavior;
- safety/data-truth presentation;

match the route contract in this document.

The release must fail if any current route is unclassified or still renders a legacy independent layout when it is supposed to be an alias.

---

## 1. Audit conclusions

The repository already has a strong reachability manifest covering every Web `page.tsx`. The new UI program should reuse that discipline for **layout coverage**.

Most important current problems:

1. **The app is still too template-driven.** Many pages can collapse into `PageShell + panel + card grid`, making every workflow feel like the same dashboard.
2. **Admin is over-navigated.** Existing Admin global/workspace navigation is supplemented by a six-tile in-page Admin navigation, creating navigation-as-content.
3. **Professional role identity remains weak.** `/dashboard` is still one role-shared landing route instead of explicit Clinical / Research / Admin compositions.
4. **Mobile Unified is consumer-first for all roles.** Doctor/Admin can still enter a Personal shell, and Council/Scribe are routed through Profile.
5. **Mobile Profile is structurally wrong.** PHR is embedded in a fixed-height nested region; professional tools are mixed with account/profile content.
6. **Mobile Today is not sufficiently task-first.** Generic Start Here actions can precede accepted tasks.
7. **Aliases risk visual duplication.** Compatibility routes must be canonical redirects, not alternative old UIs.
8. **Cards are overused as navigation and grouping.** Repeated data should normally be rows, timeline, table, or flowing editorial sections.
9. **Unknown/unavailable state must stay truthful.** Visual polish must never convert missing telemetry/data into healthy/success.
10. **A single shell cannot fit all roles.** Personal, Clinical, Research, and Admin need different spatial behavior while sharing one design system.

---

## 2. Product expressions and shells

### Personal — Spatial Health Companion

`Context Bar → Content Canvas → Spatial Dock`

Dock: `Hôm nay | LifeMap | ◉ CLARA | Thuốc | Hồ sơ`

No permanent global left sidebar.

### Clinical — Spatial Clinical Instrument

`Clinical Context Bar → Task Canvas → Adaptive Clinical Dock`

Dock: `Tổng quan | Hội chẩn | ◉ CLARA | Ghi chép | Thêm`

FOCUS/IMMERSIVE flows reduce or hide the dock.

### Research — Editorial Evidence Workstation

`Research Context Bar → Reading/Analysis Canvas → Research Dock → optional Source Inspector`

Dock: `Nghiên cứu | Bằng chứng | ◉ CLARA | Nguồn | Thêm`

### Admin — Command Workbench

Admin does **not** inherit the consumer floating dock as its primary navigation.

`Global Context Bar → Admin Command Strip → Dense Work Canvas → optional local Inspector`

Command Strip: `Overview | Knowledge | AI Flow | Monitor | Analytics | More`

Also mandatory:

- `All Admin Tools`;
- `Cmd/Ctrl+K`;
- every authorized admin destination indexed;
- Admin Experience Preview for Personal/Clinical/Research presentation QA without changing authorization.

---

## 3. Shell modes

- `EXPLORE`: hubs and home surfaces.
- `FOCUS`: create/edit/guided flows.
- `IMMERSIVE`: live capture/high-attention work.
- `READ`: results/evidence/documents.
- `READ_COMPOSE`: Chat.
- `DENSE`: source/technical data workbenches.
- `ADMIN_COMMAND`: administration.
- `UTILITY_FOCUS`: auth/onboarding/destructive flows.
- `PUBLIC_*`: shell-free public surfaces.
- `ROLE_ADAPTER`: authoritative role selects the actual page composition.
- `ALIAS_REDIRECT` / `ALIAS_CONTEXT`: no independent legacy visual system.

---

## 4. Cross-page layout laws

1. **Navigation is not page content.** Do not put a feature-card directory under another navigation.
2. **Card budget is low.** Default 0–2 dominant bounded objects per page; repeated entities use rows/tables/timeline.
3. **Glass is chrome only.** Health record, clinical result, legal, evidence, safety, transcript, SOAP, tables are opaque.
4. **Hero is rare.** Personal current action can be a HeroObject; Admin should not have a huge greeting hero.
5. **Reading width is constrained.** Personal prose ~620–760 px; professional read surfaces ~700–900 px.
6. **Mobile is recomposed.** Do not stack desktop columns into a long phone dashboard.
7. **Unknown is never green.**
8. **Local rails are allowed; global sidebars are not.** Example: PHR section index or source inspector.
9. **Every page has explicit Empty / Loading / Error-Unavailable / Populated states.**
10. **Every page must pass the anti-reskin test:** if a reviewer can say “old CLARA + new theme”, it fails.

---

## 5. 79-route layout matrix
| # | Route | Purpose | Shell | Layout |
|---:|---|---|---|---|
| 1 | `/` | Public landing | `PUBLIC_MARKETING` | Brand Story |
| 2 | `/login` | Public auth | `PUBLIC_AUTH` | Auth Focus |
| 3 | `/register` | Public auth | `PUBLIC_AUTH` | Auth Focus |
| 4 | `/forgot-password` | Public auth | `PUBLIC_AUTH` | Recovery Focus |
| 5 | `/reset-password` | Public auth | `PUBLIC_AUTH` | Recovery Focus |
| 6 | `/verify-email` | Public auth | `PUBLIC_AUTH` | Verification Status |
| 7 | `/legal` | Public legal hub | `PUBLIC_LEGAL` | Legal Index |
| 8 | `/legal/consent` | Public legal | `PUBLIC_LEGAL` | Legal Reader |
| 9 | `/legal/cookies` | Public legal | `PUBLIC_LEGAL` | Legal Reader |
| 10 | `/legal/privacy` | Public legal | `PUBLIC_LEGAL` | Legal Reader |
| 11 | `/legal/terms` | Public legal | `PUBLIC_LEGAL` | Legal Reader |
| 12 | `/share/[token]` | Public share | `PUBLIC_SHARE` | Shared Content Reader |
| 13 | `/phr/shared/[token]` | Public PHR share | `PUBLIC_SHARE` | Bounded Record Reader |
| 14 | `/today` | Personal primary | `EXPLORE` | Next-Action Canvas |
| 15 | `/today/tasks/[taskId]` | Personal task | `FOCUS` | Task Detail |
| 16 | `/lifemap` | Personal primary | `EXPLORE` | Journey Canvas |
| 17 | `/lifemap/new` | Personal create | `FOCUS` | Journey Entry |
| 18 | `/lifemap/new/[draftId]/[step]` | Personal guided flow | `FOCUS` | Journey Stepper |
| 19 | `/lifemap/visit-prep` | Compatibility | `ALIAS_CONTEXT` | Canonical Redirect |
| 20 | `/visits` | Personal secondary | `EXPLORE` | Visit Timeline |
| 21 | `/visits/new` | Personal create | `FOCUS` | Visit Prep Wizard |
| 22 | `/family` | Personal secondary | `EXPLORE` | Sharing Hub |
| 23 | `/family/invite` | Personal share flow | `FOCUS` | Invite Wizard |
| 24 | `/family/accept` | Recipient flow | `FOCUS` | Scope Review |
| 25 | `/phr` | Personal/clinical record hub | `FOCUS` | Health Record Workbench |
| 26 | `/phr/[section]` | Record section | `FOCUS` | Record Section Editor |
| 27 | `/medicines` | Personal primary | `EXPLORE` | Medicines Safety Workspace |
| 28 | `/medicines/add` | Medicine add | `FOCUS` | Medication Wizard |
| 29 | `/medicines/cabinet/add` | Cabinet add | `FOCUS` | Cabinet Wizard |
| 30 | `/selfmed` | Compatibility alias | `ALIAS_REDIRECT` | Redirect |
| 31 | `/selfmed/add` | Compatibility alias | `ALIAS_REDIRECT` | Redirect |
| 32 | `/selfmed/ddi` | Compatibility alias | `ALIAS_REDIRECT` | Redirect |
| 33 | `/careguard` | Compatibility alias | `ALIAS_REDIRECT` | Redirect |
| 34 | `/chat` | Cross-mode primary | `READ_COMPOSE` | Editorial AI Workspace |
| 35 | `/chat/shares` | Chat shares | `EXPLORE` | Shared Conversations Library |
| 36 | `/evidence` | Research/clinical evidence | `READ` | Evidence Synthesis |
| 37 | `/research` | Research alias | `ALIAS_REDIRECT` | Redirect |
| 38 | `/research/analyze` | Research alias | `ALIAS_REDIRECT` | Redirect |
| 39 | `/research/citations` | Research alias | `ALIAS_REDIRECT` | Redirect |
| 40 | `/research/deepdive` | Research alias | `ALIAS_REDIRECT` | Redirect |
| 41 | `/research/details` | Research alias | `ALIAS_REDIRECT` | Redirect |
| 42 | `/research/source-hub` | Research source library | `DENSE` | Source Workbench |
| 43 | `/council` | Clinical primary | `EXPLORE` | Case Library |
| 44 | `/council/new` | Council create | `FOCUS` | Council Entry |
| 45 | `/council/new/intake` | Council step | `FOCUS` | Case Intake |
| 46 | `/council/new/specialists` | Council step | `FOCUS` | Specialist Selection |
| 47 | `/council/new/review` | Council step | `FOCUS` | Preflight Review |
| 48 | `/council/result` | Council result | `READ` | Decision Review |
| 49 | `/council/analyze` | Council detail | `READ` | Analysis Focus |
| 50 | `/council/citations` | Council detail | `READ` | Citation Focus |
| 51 | `/council/deepdive` | Council detail | `READ` | Expert Deep Dive |
| 52 | `/council/details` | Council detail | `READ` | Technical Detail |
| 53 | `/council/research` | Council evidence | `READ` | Evidence Focus |
| 54 | `/scribe` | Clinical primary | `IMMERSIVE` | Scribe State Machine |
| 55 | `/dashboard` | Professional landing | `ROLE_ADAPTER` | Role-Adaptive Home |
| 56 | `/dashboard/control-tower` | Admin secondary | `DENSE` | System Topology Workbench |
| 57 | `/dashboard/ecosystem` | Admin secondary | `DENSE` | Integration Workbench |
| 58 | `/admin` | Admin alias | `ALIAS_REDIRECT` | Redirect |
| 59 | `/admin/overview` | Admin primary | `ADMIN_COMMAND` | Operations Overview |
| 60 | `/admin/knowledge-sources` | Admin primary | `ADMIN_COMMAND` | Knowledge Registry |
| 61 | `/admin/answer-flow` | Admin primary | `ADMIN_COMMAND` | Answer Flow Explorer |
| 62 | `/admin/observability` | Admin primary | `ADMIN_COMMAND` | Observability Cockpit |
| 63 | `/admin/analytics` | Admin primary | `ADMIN_COMMAND` | Product Analytics Report |
| 64 | `/admin/analytics/clinical` | Admin secondary | `ADMIN_COMMAND` | Clinical Analytics Report |
| 65 | `/admin/community-moderation` | Admin queue | `ADMIN_COMMAND` | Moderation Workbench |
| 66 | `/admin/dsar` | Admin compliance | `ADMIN_COMMAND` | DSAR Workbench |
| 67 | `/admin/audit-log` | Admin ledger | `ADMIN_COMMAND` | Audit Ledger |
| 68 | `/admin/rag-eval` | Admin evaluation | `ADMIN_COMMAND` | RAG Evaluation Workbench |
| 69 | `/admin/rag-ingestion` | Admin jobs | `ADMIN_COMMAND` | Ingestion Monitor |
| 70 | `/admin/rag-sources` | Admin alias | `ALIAS_REDIRECT` | Redirect |
| 71 | `/admin/source-hub` | Admin alias | `ALIAS_REDIRECT` | Redirect |
| 72 | `/community` | Personal social | `EXPLORE` | Community Feed |
| 73 | `/huong-dan` | Support | `READ` | Help Library |
| 74 | `/welcome` | Onboarding utility | `UTILITY_FOCUS` | Onboarding Router |
| 75 | `/welcome/[step]` | Onboarding step | `UTILITY_FOCUS` | Role-Aware Onboarding |
| 76 | `/role-select` | Compatibility utility | `ALIAS_REDIRECT` | Redirect |
| 77 | `/account/consent` | Account privacy | `FOCUS` | Consent Ledger |
| 78 | `/account/data` | Account data rights | `FOCUS` | Data Rights Center |
| 79 | `/account/data/delete/[step]` | Destructive account flow | `UTILITY_FOCUS` | Deletion Confirmation |

---

## 6. Page-by-page layout contracts

### 6.1 `/`

**Purpose:** Public landing  
**Shell:** `PUBLIC_MARKETING`  
**Archetype:** **Brand Story**

**Top-to-bottom layout**

1. Quiet public header.
2. Editorial hero: outcome-first copy + product visual.
3. 3 narrative sections: Personal / Clinical / Evidence.
4. Trust & safety strip.
5. Real product workflow examples.
6. Footer/legal.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.2 `/login`

**Purpose:** Public auth  
**Shell:** `PUBLIC_AUTH`  
**Archetype:** **Auth Focus**

**Top-to-bottom layout**

1. Brand/back link.
2. Single sign-in form.
3. Field-level errors + recovery.
4. Forgot/register secondary.
5. No app shell.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.3 `/register`

**Purpose:** Public auth  
**Shell:** `PUBLIC_AUTH`  
**Archetype:** **Auth Focus**

**Top-to-bottom layout**

1. Same auth shell as login.
2. Compact registration form.
3. Legal/consent acknowledgement.
4. Create account.
5. Verify-email transition.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.4 `/forgot-password`

**Purpose:** Public auth  
**Shell:** `PUBLIC_AUTH`  
**Archetype:** **Recovery Focus**

**Top-to-bottom layout**

1. Centered recovery heading.
2. Email field.
3. Send link.
4. Success/resend state.
5. Back to sign in.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.5 `/reset-password`

**Purpose:** Public auth  
**Shell:** `PUBLIC_AUTH`  
**Archetype:** **Recovery Focus**

**Top-to-bottom layout**

1. Centered reset form.
2. New password + confirm.
3. Requirements.
4. Submit.
5. Expired-token recovery.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.6 `/verify-email`

**Purpose:** Public auth  
**Shell:** `PUBLIC_AUTH`  
**Archetype:** **Verification Status**

**Top-to-bottom layout**

1. Verification status.
2. Instructions.
3. Resend/refresh.
4. Verified → continue.
5. Expired/invalid recovery.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.7 `/legal`

**Purpose:** Public legal hub  
**Shell:** `PUBLIC_LEGAL`  
**Archetype:** **Legal Index**

**Top-to-bottom layout**

1. Title + last updated.
2. Plain-language intro.
3. Legal topics as rows.
4. No dashboard chrome.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.8 `/legal/consent`

**Purpose:** Public legal  
**Shell:** `PUBLIC_LEGAL`  
**Archetype:** **Legal Reader**

**Top-to-bottom layout**

1. Title/version/date.
2. Plain-language summary.
3. Sticky/local contents.
4. Canonical legal body.
5. Related controls link.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.9 `/legal/cookies`

**Purpose:** Public legal  
**Shell:** `PUBLIC_LEGAL`  
**Archetype:** **Legal Reader**

**Top-to-bottom layout**

1. Title/version/date.
2. Summary.
3. Cookie categories.
4. Preference action if supported.
5. Canonical body.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.10 `/legal/privacy`

**Purpose:** Public legal  
**Shell:** `PUBLIC_LEGAL`  
**Archetype:** **Legal Reader**

**Top-to-bottom layout**

1. Title/version/date.
2. Summary.
3. Data categories/purposes/rights.
4. Retention/contact.
5. Canonical body.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.11 `/legal/terms`

**Purpose:** Public legal  
**Shell:** `PUBLIC_LEGAL`  
**Archetype:** **Legal Reader**

**Top-to-bottom layout**

1. Title/version/date.
2. Summary.
3. Service/medical boundaries.
4. Canonical body.
5. Related legal links.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.12 `/share/[token]`

**Purpose:** Public share  
**Shell:** `PUBLIC_SHARE`  
**Archetype:** **Shared Content Reader**

**Top-to-bottom layout**

1. Shared-with-you header.
2. Scope/expiry/read-only banner.
3. Shared content.
4. Sources/provenance.
5. Expired/revoked state.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.13 `/phr/shared/[token]`

**Purpose:** Public PHR share  
**Shell:** `PUBLIC_SHARE`  
**Archetype:** **Bounded Record Reader**

**Top-to-bottom layout**

1. Shared-record header.
2. Exact section scope.
3. Read-only record sections.
4. Provenance/last updated.
5. Expired/revoked state.

**Desktop / tablet / mobile rule**

- Desktop: editorial whitespace + constrained content width.
- Mobile: single column, shell-free, no authenticated dock/rail.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.14 `/today`

**Purpose:** Personal primary  
**Shell:** `EXPLORE`  
**Archetype:** **Next-Action Canvas**

**Top-to-bottom layout**

1. Date/context header.
2. Next accepted task as HeroObject.
3. Upcoming accepted tasks.
4. Pending confirmations.
5. Active journey preview.
6. Utilities: Ask / Medicines / Visit.
7. Week/progress last.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.
- FAIL: generic quick actions appear above a real accepted task.

### 6.15 `/today/tasks/[taskId]`

**Purpose:** Personal task  
**Shell:** `FOCUS`  
**Archetype:** **Task Detail**

**Top-to-bottom layout**

1. Back + task state.
2. Task title/context.
3. Instructions + source/journey.
4. Primary completion/record action.
5. Confirmation truth state.
6. Activity/provenance.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.16 `/lifemap`

**Purpose:** Personal primary  
**Shell:** `EXPLORE`  
**Archetype:** **Journey Canvas**

**Top-to-bottom layout**

1. Journey heading + Create.
2. Active journey HeroObject.
3. Current focus + next action.
4. Journey timeline.
5. Other journeys grouped as rows.
6. First-use empty state.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.17 `/lifemap/new`

**Purpose:** Personal create  
**Shell:** `FOCUS`  
**Archetype:** **Journey Entry**

**Top-to-bottom layout**

1. Goal question.
2. Plain-language examples.
3. Create/continue draft.
4. No dashboard modules.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.18 `/lifemap/new/[draftId]/[step]`

**Purpose:** Personal guided flow  
**Shell:** `FOCUS`  
**Archetype:** **Journey Stepper**

**Top-to-bottom layout**

1. Compact step progress.
2. One current step.
3. Field validation.
4. Back/Continue.
5. Review/edit links.
6. Durable draft status.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.19 `/lifemap/visit-prep`

**Purpose:** Compatibility  
**Shell:** `ALIAS_CONTEXT`  
**Archetype:** **Canonical Redirect**

**Top-to-bottom layout**

1. No independent UI.
2. Preserve context.
3. Redirect to canonical Visit preparation.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.20 `/visits`

**Purpose:** Personal secondary  
**Shell:** `EXPLORE`  
**Archetype:** **Visit Timeline**

**Top-to-bottom layout**

1. Heading + Prepare visit.
2. Upcoming visit if real.
3. Chronological visit timeline.
4. Linked artifacts metadata.
5. Empty state.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.21 `/visits/new`

**Purpose:** Personal create  
**Shell:** `FOCUS`  
**Archetype:** **Visit Prep Wizard**

**Top-to-bottom layout**

1. Visit info.
2. Concerns.
3. Medicines/documents.
4. Questions.
5. Review → Visit Pack.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.22 `/family`

**Purpose:** Personal secondary  
**Shell:** `EXPLORE`  
**Archetype:** **Sharing Hub**

**Top-to-bottom layout**

1. Heading + Invite.
2. Tabs: I share / Shared with me / Access log.
3. Scope-aware rows.
4. Revoked/expired history.
5. Empty state.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.23 `/family/invite`

**Purpose:** Personal share flow  
**Shell:** `FOCUS`  
**Archetype:** **Invite Wizard**

**Top-to-bottom layout**

1. Recipient.
2. Data scope.
3. Allowed actions/purpose.
4. Duration.
5. Review.
6. Explicit send.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.24 `/family/accept`

**Purpose:** Recipient flow  
**Shell:** `FOCUS`  
**Archetype:** **Scope Review**

**Top-to-bottom layout**

1. Inviter/context.
2. Exact scope.
3. Permissions/purpose.
4. Duration.
5. Accept / Decline.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.25 `/phr`

**Purpose:** Personal/clinical record hub  
**Shell:** `FOCUS`  
**Archetype:** **Health Record Workbench**

**Top-to-bottom layout**

1. Record header + active profile context.
2. Local section index on wide desktop.
3. Structured record sections.
4. Section completeness only.
5. Provenance/conflict state.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.
- FAIL: PHR remains a nested fixed-height scroll region in the canonical mobile experience.

### 6.26 `/phr/[section]`

**Purpose:** Record section  
**Shell:** `FOCUS`  
**Archetype:** **Record Section Editor**

**Top-to-bottom layout**

1. Back/local record index.
2. Section title + provenance.
3. Focused fields/list.
4. Validation.
5. Save/conflict handling.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.27 `/medicines`

**Purpose:** Personal primary  
**Shell:** `EXPLORE`  
**Archetype:** **Medicines Safety Workspace**

**Top-to-bottom layout**

1. Heading + Add medicine.
2. Current/confirmed medicines.
3. Needs confirmation.
4. Interaction Safety ActionObject.
5. Cabinet as secondary.
6. Authority availability near safety result.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.28 `/medicines/add`

**Purpose:** Medicine add  
**Shell:** `FOCUS`  
**Archetype:** **Medication Wizard**

**Top-to-bottom layout**

1. Search/identify.
2. Verify formulation/dose.
3. Usage details.
4. Review.
5. Explicit confirm.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.29 `/medicines/cabinet/add`

**Purpose:** Cabinet add  
**Shell:** `FOCUS`  
**Archetype:** **Cabinet Wizard**

**Top-to-bottom layout**

1. Scan/search package.
2. Verify identity.
3. Cabinet-only explanation.
4. Add to cabinet.
5. No implicit current-use conversion.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.30 `/selfmed`

**Purpose:** Compatibility alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → canonical Medicines/Cabinet.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.31 `/selfmed/add`

**Purpose:** Compatibility alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect/shared canonical cabinet-add flow.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.32 `/selfmed/ddi`

**Purpose:** Compatibility alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → Medicines Safety.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.33 `/careguard`

**Purpose:** Compatibility alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → Medicines Safety.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.34 `/chat`

**Purpose:** Cross-mode primary  
**Shell:** `READ_COMPOSE`  
**Archetype:** **Editorial AI Workspace**

**Top-to-bottom layout**

1. Compact context row.
2. Centered conversation reading column.
3. Answer-first hierarchy.
4. Sources after answer.
5. Optional role-gated source inspector.
6. Morphing composer island.
7. History as drawer/sheet.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.35 `/chat/shares`

**Purpose:** Chat shares  
**Shell:** `EXPLORE`  
**Archetype:** **Shared Conversations Library**

**Top-to-bottom layout**

1. Heading + filter.
2. Share rows.
3. Scope/expiry/status.
4. Row actions.
5. Empty/expired states.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.36 `/evidence`

**Purpose:** Research/clinical evidence  
**Shell:** `READ`  
**Archetype:** **Evidence Synthesis**

**Top-to-bottom layout**

1. Question/scope controls.
2. Synthesis first.
3. Applicability.
4. Uncertainty.
5. Key evidence.
6. Sources.
7. Technical retrieval collapsed.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.37 `/research`

**Purpose:** Research alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → Chat in Research context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.38 `/research/analyze`

**Purpose:** Research alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → canonical research analysis context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.39 `/research/citations`

**Purpose:** Research alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → canonical citation context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.40 `/research/deepdive`

**Purpose:** Research alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → canonical expert/source context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.41 `/research/details`

**Purpose:** Research alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect only → canonical research detail context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.42 `/research/source-hub`

**Purpose:** Research source library  
**Shell:** `DENSE`  
**Archetype:** **Source Workbench**

**Top-to-bottom layout**

1. Search/filter bar.
2. Dense source table/list.
3. Authority/freshness columns.
4. Selected source inspector.
5. Manage mode only by capability.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.43 `/council`

**Purpose:** Clinical primary  
**Shell:** `EXPLORE`  
**Archetype:** **Case Library**

**Top-to-bottom layout**

1. Clinical heading + New Council.
2. Continue real resumable case.
3. Recent cases as rows.
4. Real stage/warning state.
5. Empty state.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.44 `/council/new`

**Purpose:** Council create  
**Shell:** `FOCUS`  
**Archetype:** **Council Entry**

**Top-to-bottom layout**

1. Concise entry explanation.
2. Start/continue draft.
3. No clinical feature card grid.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.45 `/council/new/intake`

**Purpose:** Council step  
**Shell:** `FOCUS`  
**Archetype:** **Case Intake**

**Top-to-bottom layout**

1. Step progress.
2. Question/case context.
3. Red-flag feedback.
4. Optional compact context summary.
5. Continue.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.46 `/council/new/specialists`

**Purpose:** Council step  
**Shell:** `FOCUS`  
**Archetype:** **Specialist Selection**

**Top-to-bottom layout**

1. Step progress.
2. Selectable specialist rows/chips.
3. System vs clinician selection distinction.
4. Advanced rationale collapsed.
5. Continue.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.47 `/council/new/review`

**Purpose:** Council step  
**Shell:** `FOCUS`  
**Archetype:** **Preflight Review**

**Top-to-bottom layout**

1. Case summary.
2. Question/context.
3. Specialists.
4. Evidence/limits.
5. Critical missing info.
6. One Run Council action.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.48 `/council/result`

**Purpose:** Council result  
**Shell:** `READ`  
**Archetype:** **Decision Review**

**Top-to-bottom layout**

1. Case/run context.
2. Red flags.
3. Recommendation/synthesis.
4. Agreement/disagreement.
5. Uncertainty.
6. Clinician actions.
7. Evidence.
8. Specialist perspectives.
9. Expert technical detail collapsed.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.49 `/council/analyze`

**Purpose:** Council detail  
**Shell:** `READ`  
**Archetype:** **Analysis Focus**

**Top-to-bottom layout**

1. Same Council Result shell.
2. Analysis section focused.
3. Decision context remains visible.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.50 `/council/citations`

**Purpose:** Council detail  
**Shell:** `READ`  
**Archetype:** **Citation Focus**

**Top-to-bottom layout**

1. Same Council Result shell.
2. Sources focused.
3. Source inspector.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.51 `/council/deepdive`

**Purpose:** Council detail  
**Shell:** `READ`  
**Archetype:** **Expert Deep Dive**

**Top-to-bottom layout**

1. Same Council Result shell.
2. Expert deep-dive expanded.
3. Decision context retained.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.52 `/council/details`

**Purpose:** Council detail  
**Shell:** `READ`  
**Archetype:** **Technical Detail**

**Top-to-bottom layout**

1. Same Council Result shell.
2. Technical detail expanded.
3. No separate diagnostics dashboard.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.53 `/council/research`

**Purpose:** Council evidence  
**Shell:** `READ`  
**Archetype:** **Evidence Focus**

**Top-to-bottom layout**

1. Council decision context.
2. Evidence synthesis.
3. Applicability/uncertainty.
4. Sources.
5. Research controls by capability.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.54 `/scribe`

**Purpose:** Clinical primary  
**Shell:** `IMMERSIVE`  
**Archetype:** **Scribe State Machine**

**Top-to-bottom layout**

1. Idle/library: New recording + recent sessions.
2. Consent Focus.
3. Capture Immersive.
4. Transcript Read.
5. SOAP Read/Edit.
6. Draft/Reviewed/Finalized/Signed/Exported/Amended explicit.

**Desktop / tablet / mobile rule**

- All sizes: task controls dominate; global navigation is hidden/reduced.
- Phone: safe-area-aware controls; desktop never fills spare width with unrelated modules.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.
- FAIL: capture retains full global navigation or glass behind transcript/SOAP.

### 6.55 `/dashboard`

**Purpose:** Professional landing  
**Shell:** `ROLE_ADAPTER`  
**Archetype:** **Role-Adaptive Home**

**Top-to-bottom layout**

1. Role adapter only.
2. Doctor → Clinical Overview.
3. Researcher → Research Overview.
4. Admin → /admin/overview.
5. Normal → /today.
6. No generic professional dashboard fallback.

**Desktop / tablet / mobile rule**

- Select the real composition from authoritative role/capabilities first; no generic role-neutral fallback.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.56 `/dashboard/control-tower`

**Purpose:** Admin secondary  
**Shell:** `DENSE`  
**Archetype:** **System Topology Workbench**

**Top-to-bottom layout**

1. Admin command shell.
2. Environment/service topology or dependency list.
3. Compact status ledger.
4. Selected service inspector.
5. Recent events/errors.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.57 `/dashboard/ecosystem`

**Purpose:** Admin secondary  
**Shell:** `DENSE`  
**Archetype:** **Integration Workbench**

**Top-to-bottom layout**

1. Admin command shell.
2. Search/filter.
3. Integration registry table/list.
4. Selected integration inspector.
5. Real configuration actions only.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.58 `/admin`

**Purpose:** Admin alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Immediate redirect → /admin/overview.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.59 `/admin/overview`

**Purpose:** Admin primary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Operations Overview**

**Top-to-bottom layout**

1. Admin Context Bar + Command Strip.
2. Page title/context — no giant greeting hero.
3. Attention Queue.
4. System Status Ledger.
5. Active/Recent Operations.
6. Audit/activity digest.
7. All Tools + Cmd/Ctrl+K.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.
- FAIL: left rail + top nav + floating bottom dock + in-content six-card navigation coexist.
- FAIL: any active Admin capability is discoverable only by typing the URL.

### 6.60 `/admin/knowledge-sources`

**Purpose:** Admin primary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Knowledge Registry**

**Top-to-bottom layout**

1. Admin Command Strip.
2. Sticky search/filter/manage row.
3. Dense source registry table.
4. Selected-source inspector.
5. Bulk actions only when supported.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.61 `/admin/answer-flow`

**Purpose:** Admin primary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Answer Flow Explorer**

**Top-to-bottom layout**

1. Admin Command Strip.
2. Trace/filter controls.
3. Pipeline/stage visualization as primary object.
4. Selected stage inspector.
5. Recent traces/events.
6. Advanced debug lazy-loaded.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.62 `/admin/observability`

**Purpose:** Admin primary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Observability Cockpit**

**Top-to-bottom layout**

1. Admin Command Strip.
2. Environment/time filters.
3. Compact service state strip.
4. Service matrix + event/error timeline.
5. Real charts only.
6. Selected signal inspector.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.63 `/admin/analytics`

**Purpose:** Admin primary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Product Analytics Report**

**Top-to-bottom layout**

1. Admin Command Strip.
2. Sticky time/dimension filters.
3. Compact KPI strip only if real.
4. 1–2 primary charts.
5. Breakdown table.
6. Metric definitions.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.64 `/admin/analytics/clinical`

**Purpose:** Admin secondary  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Clinical Analytics Report**

**Top-to-bottom layout**

1. Definition/safety note.
2. Aggregate filters.
3. Primary trends.
4. Verification/DDI/latency breakdown.
5. Privacy-safe table.
6. No patient-care inference.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.65 `/admin/community-moderation`

**Purpose:** Admin queue  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Moderation Workbench**

**Top-to-bottom layout**

1. Queue filters.
2. Moderation table/list.
3. Selected item inspector.
4. Action panel.
5. Confirm irreversible actions.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.66 `/admin/dsar`

**Purpose:** Admin compliance  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **DSAR Workbench**

**Top-to-bottom layout**

1. Status filters.
2. Request table.
3. Selected request inspector.
4. Deadline/action timeline.
5. Audited actions.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.67 `/admin/audit-log`

**Purpose:** Admin ledger  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Audit Ledger**

**Top-to-bottom layout**

1. Query/filter row.
2. Immutable dense ledger table.
3. Selected event inspector.
4. Export only if supported.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.68 `/admin/rag-eval`

**Purpose:** Admin evaluation  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **RAG Evaluation Workbench**

**Top-to-bottom layout**

1. Run controls separated from inspection.
2. Runs table.
3. Selected run metrics.
4. Regressions/failures.
5. Category breakdown.
6. Sample/error inspector.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.69 `/admin/rag-ingestion`

**Purpose:** Admin jobs  
**Shell:** `ADMIN_COMMAND`  
**Archetype:** **Ingestion Monitor**

**Top-to-bottom layout**

1. Start action if supported.
2. Source/status filters.
3. Jobs table.
4. Selected job stages.
5. Failure/retry detail.
6. Raw logs lazy.

**Desktop / tablet / mobile rule**

- Wide desktop: use width for table/list + inspector/analysis canvas. Do not center a narrow dashboard.
- Tablet: inspector becomes side sheet/drawer; filters compress without losing reachability.
- Phone: keep safe read/monitor behavior; complex high-risk mutations may remain desktop-only if stated explicitly.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.70 `/admin/rag-sources`

**Purpose:** Admin alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect → /admin/knowledge-sources.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.71 `/admin/source-hub`

**Purpose:** Admin alias  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect → canonical Knowledge or Research Source context.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.72 `/community`

**Purpose:** Personal social  
**Shell:** `EXPLORE`  
**Archetype:** **Community Feed**

**Top-to-bottom layout**

1. Community heading + safety distinction.
2. Topic/filter controls.
3. One composer action.
4. Flowing feed list.
5. Peer vs CLARA/evidence distinction.
6. Report/mute/privacy actions.

**Desktop / tablet / mobile rule**

- Desktop: broad canvas with intentional whitespace, not manufactured multi-column dashboard density.
- Mobile: current/next work must remain ahead of generic shortcuts/statistics.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.73 `/huong-dan`

**Purpose:** Support  
**Shell:** `READ`  
**Archetype:** **Help Library**

**Top-to-bottom layout**

1. Search first.
2. Role-aware topic rows.
3. Article reader.
4. Local contents on wide screen.
5. No feature-card catalog.

**Desktop / tablet / mobile rule**

- Wide desktop: constrained main reading column; optional source/section inspector is secondary.
- Tablet: single main column + overlay inspector.
- Phone: one reading column; sources/details become full-screen or sheets.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.74 `/welcome`

**Purpose:** Onboarding utility  
**Shell:** `UTILITY_FOCUS`  
**Archetype:** **Onboarding Router**

**Top-to-bottom layout**

1. Resolve onboarding requirement.
2. Route to exact step.
3. Only progress/status if rendered.
4. No universal PHR gate.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.75 `/welcome/[step]`

**Purpose:** Onboarding step  
**Shell:** `UTILITY_FOCUS`  
**Archetype:** **Role-Aware Onboarding**

**Top-to-bottom layout**

1. Single focused column.
2. Global or role-specific step.
3. Compact progress.
4. Back/Continue.
5. Professional onboarding excludes personal body metrics.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.76 `/role-select`

**Purpose:** Compatibility utility  
**Shell:** `ALIAS_REDIRECT`  
**Archetype:** **Redirect**

**Top-to-bottom layout**

1. Redirect utility only.
2. Resolve authoritative role/capabilities.
3. No client-side permission grant.

**Desktop / tablet / mobile rule**

- No independent responsive UI; transition directly to the canonical destination while preserving safe context.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.77 `/account/consent`

**Purpose:** Account privacy  
**Shell:** `FOCUS`  
**Archetype:** **Consent Ledger**

**Top-to-bottom layout**

1. Privacy/consent header.
2. Consent ledger rows.
3. Purpose/state/version/date.
4. Detail sheet.
5. Grant/revoke with consequence copy.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.78 `/account/data`

**Purpose:** Account data rights  
**Shell:** `FOCUS`  
**Archetype:** **Data Rights Center**

**Top-to-bottom layout**

1. Data Rights header.
2. Export/access/delete action rows.
3. Request status/timeline.
4. Deletion isolated as destructive.
5. No settings-card grid.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

### 6.79 `/account/data/delete/[step]`

**Purpose:** Destructive account flow  
**Shell:** `UTILITY_FOCUS`  
**Archetype:** **Deletion Confirmation**

**Top-to-bottom layout**

1. Consequences.
2. Scope review.
3. Required confirmation/auth.
4. Final destructive submit.
5. Server-confirmed status.

**Desktop / tablet / mobile rule**

- Desktop: centered work column; optional local context rail only if it reduces memory load.
- Phone/tablet: one task column; Back/progress/primary action stay stable and reachable.

**Rejection criteria**

- FAIL: old information order retained with only palette/radius/navigation changes.
- FAIL: repeated data converted into unnecessary equal-weight card grids.

---

## 7. Mobile surface contracts

Flutter is not URL-isomorphic to Web, so create an exhaustive `ClaraDestination` / `ExperienceConfig` registry and a migration manifest for every reachable surface.

### 7.1 Personal Today

Order: Context → next accepted task → upcoming → pending confirmations → journey preview → utilities → dock.

Current generic Start Here actions must move below actual accepted work.

### 7.2 LifeMap

Active journey hero → current focus → next accepted action → timeline → other journeys rows → Create.

### 7.3 Medicines

Current medicines → Needs confirmation → Safety ActionObject → Cabinet.

Current use, unresolved confirmation, and cabinet ownership must never look equivalent.

### 7.4 Profile

Identity/account → Health Record → Family/Sharing → Connected Health → Privacy/Consent → Data Rights → Preferences → Help.

Council/Scribe are removed from Profile taxonomy.

PHR is no longer embedded as a fixed-height child.

### 7.5 PHR

Hub → section list → full-screen section editor.

### 7.6 Chat

Compact context → conversation → sources sheet → morphing composer island.

### 7.7 Doctor mobile default

Clinical Overview → Council → CLARA center action → Scribe → More.

Doctor must not default to the consumer Personal shell.

### 7.8 Council

Home/library `EXPLORE`; intake/specialists/review `FOCUS`; result `READ`.

### 7.9 Scribe

Consent `FOCUS` → Capture `IMMERSIVE` → Transcript `READ` → SOAP `READ/EDIT`.

### 7.10 Research

Research → Evidence → CLARA → Sources → More.

### 7.11 Admin mobile

Keep bounded: read-only/low-risk overview, critical status inspection, and only safe well-designed mutations. Do not compress complex Answer Flow / ingestion / audit analytics / Knowledge management into tiny phone card grids for fake parity.

---

## 8. Admin redesign rules

### 8.1 Remove current in-page six-tile Admin navigation

Replace with a compact Command Strip plus `More`.

### 8.2 Reachability

All active Admin routes must be reachable through at least one of:

- Command Strip;
- All Admin Tools launcher;
- Cmd/Ctrl+K.

No URL-only active features.

### 8.3 Experience Preview

Admin Context Bar can switch presentation preview:

- Clinical;
- Research;
- Personal.

This never changes server RBAC, never impersonates another account, and never fabricates patient data.

---

## 9. Technical design

### 9.1 Route layout registry

Create a typed manifest:

```ts
interface RouteLayoutContract {
  routeId: string;
  experience?: "personal" | "clinical" | "research" | "admin";
  shellMode:
    | "explore"
    | "focus"
    | "immersive"
    | "read"
    | "read-compose"
    | "dense"
    | "admin-command"
    | "utility-focus"
    | "role-adapter"
    | "public"
    | "alias";
  archetype: string;
  canonicalTarget?: string;
  showGlobalDock: boolean;
  allowLocalRail?: boolean;
  allowInspector?: boolean;
}
```

CI asserts:

`filesystem page routes == route-capability matrix == v5 layout registry`

### 9.2 App shell decomposition

Target:

```text
RootLayout
└ AppProviders
  ├ SessionProvider
  ├ ProfileProvider
  ├ PreferenceProvider
  └ ExperienceProvider
    └ ExperienceShell
      ├ PersonalShell
      ├ ClinicalShell
      ├ ResearchShell
      └ AdminShell
```

`AppShell` becomes a compatibility facade and then a thin composition layer.

### 9.3 Mobile root

Replace role-agnostic consumer destination construction with:

```dart
ExperienceConfig experienceFor(
  UserRole role,
  CapabilitySet capabilities,
)
```

Then build destinations from typed configs, not hard-coded one-size-fits-all consumer destinations.

### 9.4 Design tokens

Canonical source:

```text
packages/design-tokens/clara.tokens.json
→ apps/web/styles/generated/clara.tokens.css
→ apps/mobile/lib/theme/generated/clara_tokens.g.dart
```

No manually mirrored active token palette.

---

## 10. Design system primitives

Required primitives:

- `ContextBar`
- `SpatialDock`
- `AdminCommandStrip`
- `AllToolsLauncher`
- `CommandPalette`
- `ClaraOrb`
- `HeroObject`
- `ActionObject`
- `EditorialSection`
- `ListRow`
- `DataTable`
- `Inspector`
- `LocalRail`
- `SectionIndex`
- `Status`
- `Alert`
- `SourceDisclosure`
- `CitationAnchor`
- `Stepper`
- `Timeline`
- `Sheet`
- `Modal`
- `EmptyState`
- `LoadingState`
- `ErrorState`

Density presets:

- Personal: Comfortable
- Clinical: Compact
- Research: Compact/Reader
- Admin: Dense

---

## 11. Requirements

### Functional

- Preserve all authorized capabilities.
- Keep compatibility URLs but remove duplicate visual identities.
- No feature is hidden simply to simplify navigation.
- Professional onboarding cannot be blocked by Personal PHR setup.
- Admin route reachability remains exhaustive.
- Profile context and authorization remain separate concepts.
- Human confirmation semantics remain visible.
- Signed/final Scribe states remain explicit.

### Non-functional

- WCAG 2.2 AA target.
- No critical performance regression.
- Vietnamese-first copy; English parity.
- No PII analytics.
- No chain-of-thought exposure.
- Safety/provenance information cannot be hidden for aesthetics.
- Unknown/unavailable states never display as success.

---

## 12. Implementation plan

### M0 — Freeze & evidence
- Snapshot 79-route matrix.
- Capture current desktop/mobile-web screenshots.
- Inventory Mobile reachable surfaces.
- Freeze safety/RBAC/API invariants.

### M1 — Layout architecture
- Route layout registry.
- Shell modes.
- Context Bar.
- Personal/Clinical/Research Dock.
- Admin Command Strip.
- Inspector/local rail.
- Hero/Action/List primitives.

### M2 — Public/Auth/Utility
Transform all public, auth, legal, onboarding and account/privacy routes.

### M3 — Personal
Today, LifeMap, Visits, Family, PHR, Medicines, Community.

### M4 — Chat/Research
Chat, shares, Evidence, Source Hub, legacy redirects.

### M5 — Clinical
Role-adaptive dashboard, all Council routes/states, all Scribe states.

### M6 — Admin
Overview, Knowledge, Answer Flow, Observability, Analytics, Clinical Analytics, Moderation, DSAR, Audit, RAG Eval, Ingestion, Control Tower, Ecosystem.

### M7 — Mobile role adaptation
Unified root config, Personal, Clinical, Research, bounded Admin, Profile/PHR refactor.

### M8 — Cleanup/hardening
Legacy roots/visuals, visual regression, a11y, performance, E2E, route reachability.

---

## 13. Detailed task list

### Foundation
- `UX5-001` Add `route-layout.registry.ts`.
- `UX5-002` Add CI equality gate against route matrix/filesystem.
- `UX5-003` Introduce shell mode primitives.
- `UX5-004` Split Personal/Clinical/Research/Admin shell renderers.
- `UX5-005` Build Context Bar.
- `UX5-006` Build role-adaptive Spatial Dock.
- `UX5-007` Build Admin Command Strip.
- `UX5-008` Build All Tools launcher.
- `UX5-009` Build Command Palette.
- `UX5-010` Build HeroObject / ActionObject / ListRow / Inspector / LocalRail.

### Personal
- `UX5-020` Recompose Today task-first.
- `UX5-021` Recompose task detail.
- `UX5-022` Recompose LifeMap hub.
- `UX5-023` Recompose LifeMap guided flow.
- `UX5-024` Recompose Visits timeline.
- `UX5-025` Recompose visit prep wizard.
- `UX5-026` Recompose Family sharing hub.
- `UX5-027` Recompose invite/accept flows.
- `UX5-028` Rebuild PHR hub/workbench.
- `UX5-029` Rebuild PHR section editors.
- `UX5-030` Recompose Medicines hub.
- `UX5-031` Recompose medicine/cabinet add flows.
- `UX5-032` Recompose Community.

### Chat/Research
- `UX5-040` Recompose Chat into editorial READ_COMPOSE.
- `UX5-041` Move history to drawer/sheet.
- `UX5-042` Build source inspector.
- `UX5-043` Recompose Chat shares.
- `UX5-044` Recompose Evidence synthesis-first.
- `UX5-045` Recompose Source Hub dense workbench.
- `UX5-046` Convert research legacy routes to canonical redirects.

### Clinical
- `UX5-050` Convert `/dashboard` to role adapter.
- `UX5-051` Build Clinical Overview.
- `UX5-052` Recompose Council home.
- `UX5-053` Recompose Council intake.
- `UX5-054` Recompose specialist selection.
- `UX5-055` Recompose Council review/run.
- `UX5-056` Rebuild Council result document hierarchy.
- `UX5-057` Merge Council detail routes onto result shell.
- `UX5-058` Rebuild Scribe as explicit state machine.
- `UX5-059` Make capture immersive.

### Admin
- `UX5-060` Remove six-tile in-page Admin navigation.
- `UX5-061` Build Admin Command Strip.
- `UX5-062` Build Admin Experience Preview.
- `UX5-063` Rebuild Admin Overview without hero/tool-card directory.
- `UX5-064` Rebuild Knowledge Sources.
- `UX5-065` Rebuild Answer Flow.
- `UX5-066` Rebuild Observability.
- `UX5-067` Rebuild Product Analytics.
- `UX5-068` Rebuild Clinical Analytics.
- `UX5-069` Rebuild Moderation queue.
- `UX5-070` Rebuild DSAR.
- `UX5-071` Rebuild Audit Log.
- `UX5-072` Rebuild RAG Eval.
- `UX5-073` Rebuild Ingestion Monitor.
- `UX5-074` Rebuild Control Tower.
- `UX5-075` Rebuild Ecosystem.
- `UX5-076` Add Admin reachability test.
- `UX5-077` Convert Admin aliases to redirects.

### Mobile
- `UX5-080` Introduce `ExperienceConfig`.
- `UX5-081` Build role-adaptive destination registry.
- `UX5-082` Fix professional onboarding split.
- `UX5-083` Move accepted tasks above Start Here.
- `UX5-084` Remove PHR fixed-height embedding.
- `UX5-085` Remove Council/Scribe from Profile taxonomy.
- `UX5-086` Build Clinical mobile shell.
- `UX5-087` Build Research mobile shell.
- `UX5-088` Recompose mobile Council.
- `UX5-089` Recompose mobile Scribe.
- `UX5-090` Consolidate legacy/V2/V3/Unified roots after parity gates.

### Quality
- `UX5-100` 79-route screenshot manifest.
- `UX5-101` Light/dark/compact visual baselines.
- `UX5-102` Empty/loading/error fixtures.
- `UX5-103` axe/keyboard/focus scans.
- `UX5-104` 320px + 200% zoom tests.
- `UX5-105` mobile dynamic type + TalkBack/VoiceOver.
- `UX5-106` performance regression budget.
- `UX5-107` RBAC/profile isolation regression.
- `UX5-108` consent/emergency/FIDES/DrugBank safety regression.
- `UX5-109` no-PII telemetry regression.
- `UX5-110` anti-reskin manual sign-off for every non-alias route.

---

## 14. Visual QA matrix

Every non-alias route:

- Light desktop
- Dark desktop
- Light compact/mobile-web
- Dark compact/mobile-web
- Loading
- Empty
- Error/unavailable
- Populated

High-value routes additionally:

- tablet;
- 200% zoom;
- warning/critical state;
- role variants.

High-value routes: `/today`, `/lifemap`, `/medicines`, `/phr`, `/chat`, `/evidence`, `/council`, `/council/result`, `/scribe`, `/dashboard`, `/admin/overview`, `/admin/knowledge-sources`, `/admin/answer-flow`, `/admin/observability`, `/admin/rag-eval`.

---

## 15. Definition of Done

1. 79/79 Web routes classified in layout registry.
2. Every non-alias route visibly recomposed.
3. Every alias renders no independent old UI.
4. Personal/Clinical/Research have no permanent global left sidebar.
5. Admin uses Command Workbench, not consumer dock + duplicate navigation layers.
6. Admin Overview has no giant greeting hero and no Clinical feature directory cards.
7. Every authorized Admin destination is discoverable without typing a URL.
8. Admin Experience Preview exists without changing authorization.
9. Today is next-task-first.
10. LifeMap is journey-first.
11. Medicines clearly separates current / unresolved / safety / cabinet.
12. PHR is a real workbench, not nested fixed-height content.
13. Chat is editorial answer-first.
14. Evidence is synthesis-first.
15. Council is decision-first.
16. Scribe capture is immersive and state semantics remain explicit.
17. Mobile doctor defaults to Clinical.
18. Council/Scribe are not hidden in Mobile Profile.
19. Professional onboarding is not blocked by Personal PHR setup.
20. Light and dark both pass visual/a11y gates.
21. Safety/RBAC/profile/privacy invariants pass.
22. A reviewer cannot reasonably summarize the result as “old CLARA with a floating nav”.

---

## 16. Final design law

**Every page earns its layout from the user's job.**

CLARA must not expose its internal module graph as the product.

The transformation comes from hierarchy, role adaptation, editorial composition, spatial interaction, typography, truthful states, and task focus—not decorative effects.
