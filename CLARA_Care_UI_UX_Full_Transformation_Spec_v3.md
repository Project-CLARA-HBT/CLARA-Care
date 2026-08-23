# CLARA Care — Full UI/UX Transformation Specification v3

> **Document type:** Product Requirements + UX Specification + Visual Design System + Technical Design + Execution Plan + Detailed Task Backlog  
> **Repository:** `Project-CLARA-HBT/CLARA-Care`  
> **Implementation baseline:** `main@81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`  
> **Target clients:** CLARA Web (`apps/web`) + CLARA Mobile (`apps/mobile`)  
> **Primary language:** Vietnamese, with full English parity  
> **Status:** Proposed implementation specification  
> **Priority:** Product-level redesign, not a cosmetic reskin

---

# 0. Executive Decision

CLARA Care must undergo a **complete experience transformation** while preserving its medical-safety, privacy, consent, authorization, provenance, and audit contracts.

The target is **not** another round of dark-mode cards, gradients, or “glass everywhere.” The target is a coherent healthcare product that feels current, calm, intelligent, trustworthy, and immediately understandable to:

- an individual managing personal health;
- a clinician using CLARA as a professional tool;
- a researcher evaluating evidence;
- an administrator operating the platform;
- a family/support recipient interacting through bounded sharing.

The redesign must change all of the following as one coordinated program:

1. Product mental model.
2. Role-aware information architecture.
3. First-run and onboarding behavior.
4. Web and mobile navigation.
5. Page hierarchy.
6. Content density.
7. Visual design language.
8. Color palette.
9. Typography and spacing.
10. Surface/elevation model.
11. Mobile glass/chrome language.
12. Component library.
13. Motion and interaction feedback.
14. Empty/loading/error/offline states.
15. Professional vs personal density.
16. Responsive behavior.
17. Accessibility.
18. Frontend architecture.
19. Token ownership across Web and Flutter.
20. Test, rollout, and legacy cleanup strategy.

The product north star is:

> **CLARA should expose the user's job and next decision — not CLARA's internal module graph.**

---

# 1. Current-State Baseline

## 1.1 Web

The current web client already contains important modernization work and must not regress:

- role-aware route access;
- presentation workspaces: Personal, Clinical, Research, Administration;
- separation of route access from navigation visibility;
- primary navigation limits;
- `More` navigation;
- task-first Today improvements;
- truthful professional Dashboard states;
- bundled SVG icons;
- responsive shell;
- mobile bottom navigation;
- focus-managed mobile drawer;
- answer-first Chat;
- explicit Scribe consent/review stages;
- Council safety/result hierarchy;
- compatibility aliases and deep-link support.

Current key implementation areas:

```text
apps/web/components/app-shell.tsx
apps/web/components/sidebar-nav.tsx
apps/web/components/navigation/*
apps/web/lib/navigation.access.ts
apps/web/lib/navigation.config.ts
apps/web/lib/navigation.workspaces.ts
apps/web/styles/globals.css
apps/web/app/today/*
apps/web/app/dashboard/*
apps/web/app/chat/*
apps/web/app/council/*
apps/web/app/scribe/*
apps/web/app/phr/*
apps/web/app/medicines/*
```

## 1.2 Mobile

The shipped-default mobile experience is the Unified client, selected by:

```text
MOBILE_UNIFIED_ENABLED = true
```

Current primary consumer shell:

```text
Hôm nay · LifeMap · [Hỏi CLARA] · Thuốc · Hồ sơ
```

The Unified root supersedes legacy Dashboard, Experience V2, and V3 when enabled.

Current key implementation areas:

```text
apps/mobile/lib/app.dart
apps/mobile/lib/core/feature_flags.dart
apps/mobile/lib/experience/unified/*
apps/mobile/lib/experience/redesign_shell.dart
apps/mobile/lib/theme/*
apps/mobile/lib/theme/glass/*
```

## 1.3 Critical visual-system inconsistency

At the current baseline, Web and Mobile do **not** have one trustworthy palette source.

Current web `globals.css` uses a deep-well system centered around values such as:

```text
Canvas          #101419
Panel           #1D2025
Muted surface   #272A30
Primary text    #E1E2E9
Brand text      #A4C9FF
Action blue     #0053DB
Warning         #FABD34
Danger          #FFB4AB
```

However, mobile `web_palette.dart` still documents a different web-derived family including values such as:

```text
Light canvas    #F4F6FB
Dark canvas     #1B1A19
Primary action  #2563EB
Dark surface    #292929
```

Therefore the redesign must **replace manual web/mobile palette mirroring with a canonical token contract**.

---

# 2. Product Problems to Solve

## 2.1 P0 — Role model is inconsistent across platforms

Web understands professional workspaces.

Mobile currently gives all roles the same consumer-first root and only reveals selected clinician tools deeper in the Profile hub.

A doctor should not need:

```text
Today → Profile → Tools & Privacy → Council
```

when their job is:

```text
Clinical → Council
```

### Required outcome

Role determines available experiences:

```text
normal      → Personal
doctor      → Clinical + Personal
researcher  → Research + Personal
admin       → Administration + Clinical/Research/Personal as permitted
```

Authorization remains server-side.

---

## 2.2 P0 — Personal PHR onboarding is over-scoped

Personal health profile onboarding must not become a universal gate for professional work.

A doctor must not be required to enter:

- personal height;
- weight;
- blood type;
- other personal health fields

before reaching Scribe, Council, or professional evidence workflows.

### Required outcome

Split onboarding into:

```text
GLOBAL FIRST RUN
PERSONAL HEALTH SETUP
PROFESSIONAL ORIENTATION
TOOL-SPECIFIC CONSENT
```

---

## 2.3 P0 — Profile is a dumping ground on Mobile

Profile currently combines account/privacy surfaces with operational tools.

Target taxonomy:

```text
Profile
├── Health record
├── Visits
├── Family & sharing
├── Connected health
├── Privacy & consent
├── Data rights
├── Preferences
└── Help
```

Not:

```text
Profile
├── Scribe
├── Council
└── other professional work
```

---

## 2.4 P0 — Mobile Today does not prioritize “what now?”

Today must answer:

> **What should I do now?**

If an accepted task exists, it must appear before:

- generic shortcuts;
- progress stats;
- marketing-style cards;
- educational navigation.

---

## 2.5 P0 — Professional home leaks into Personal context

Professional home must never use `/today` as its generic fallback action.

A professional user with no current task should see:

```text
No active professional work.
Ask CLARA
Start Council
Open Scribe
Browse Evidence
```

not:

```text
View personal Today
```

unless they explicitly switch to Personal.

---

## 2.6 P1 — Web shell still has too much orchestration

`AppShell` remains responsible for too many domains:

- session;
- role;
- profile;
- onboarding;
- theme;
- language;
- workspace;
- route guard;
- navigation;
- family notifications;
- logout;
- mobile modal state;
- focus management.

The visual shell is improved, but architectural ownership is still too broad.

---

## 2.7 P1 — Mobile retains too many generations

Current code still contains:

```text
Legacy
Experience V2
Experience V3
Unified
```

Target after parity:

```text
UnifiedRoleAdaptive
LegacyRollbackAdapter
```

Then eventually:

```text
UnifiedRoleAdaptive
```

---

# 3. Product North Star

## 3.1 Personal

CLARA feels like:

> a calm, private health companion that helps me understand what matters, organize my health information, check medication safety, and prepare for care.

## 3.2 Clinician

CLARA feels like:

> a focused clinical co-pilot that helps me ask evidence questions, review complex cases, and produce structured visit documentation without hiding uncertainty or taking clinical control away from me.

## 3.3 Researcher

CLARA feels like:

> an evidence workstation with provenance, source inspection, structured synthesis, and uncertainty.

## 3.4 Administrator

CLARA feels like:

> an operational console for system health, knowledge sources, answer flow, analytics, compliance, and audit — without contaminating user-facing clinical surfaces.

---

# 4. Design Principles

1. **One screen, one dominant job.**
2. **Next action before navigation.**
3. **Safety before visual reduction.**
4. **Data truth before decorative completeness.**
5. **Plain language before internal terminology.**
6. **Role changes presentation, never authorization.**
7. **Profile context changes data scope, never permission scope.**
8. **Critical warnings are never hidden.**
9. **Mobile is purpose-built, not compressed desktop.**
10. **Professional density may be higher than Personal density.**
11. **Glass is chrome, not medical content.**
12. **Motion communicates state, never distracts from care.**
13. **Empty states are useful states.**
14. **Unknown is rendered as unknown.**
15. **No fabricated health score or fake AI confidence.**
16. **Every action must make its consequences understandable.**
17. **Vietnamese is a first-class design constraint, not a translation afterthought.**
18. **Web and Mobile share semantic tokens, not necessarily identical geometry.**
19. **Every authorized capability remains reachable.**
20. **Backward compatibility is explicit and testable.**

---

# 5. Target Product Model

```text
ACCOUNT
│
├── ROLE / SERVER CAPABILITIES
│   ├── normal
│   ├── doctor
│   ├── researcher
│   └── admin
│
├── EXPERIENCE MODE
│   ├── Personal
│   ├── Clinical
│   ├── Research
│   └── Administration
│
├── DATA CONTEXT
│   ├── Self
│   └── Bounded shared context
│
└── CURRENT USER TASK
```

Rules:

- Role defines which modes may be presented.
- Mode defines primary navigation.
- Profile/data context defines which data is being viewed.
- User task defines content hierarchy.
- Server authorization always remains authoritative.
- No client state may grant access.

---

# 6. Target Information Architecture

# 6.1 Personal — Web

Primary:

1. Hôm nay
2. Hỏi CLARA
3. Hành trình
4. Thuốc & an toàn
5. Hồ sơ sức khỏe

Secondary / More:

- Chuẩn bị đi khám
- Người thân hỗ trợ
- Bằng chứng
- Shared conversations
- Community when enabled
- Consent
- Data rights
- Help

A pure Personal user never sees the term “workspace” in ordinary navigation.

---

# 6.2 Personal — Mobile

Persistent navigation:

```text
Hôm nay | LifeMap | [CLARA] | Thuốc | Hồ sơ
```

Center CLARA action remains a distinctive primary affordance.

---

# 6.3 Clinical — Web

Primary:

1. Tổng quan
2. Hỏi CLARA
3. Hội chẩn
4. Ghi chép khám
5. Bằng chứng

Secondary:

- Source Hub where permitted
- Help
- Personal mode
- bounded contextual health record access where already supported

No invented patient directory.

No invented appointment queue.

No invented task inbox unless server contracts exist.

---

# 6.4 Clinical — Mobile

Persistent navigation:

```text
Tổng quan | Hội chẩn | [CLARA] | Ghi chép | Thêm
```

`Thêm` contains:

- Evidence
- Source Hub if permitted
- Personal
- Account/Profile
- Settings
- Help

---

# 6.5 Research — Web

Primary:

1. Hỏi CLARA
2. Bằng chứng
3. Nguồn nghiên cứu

Secondary:

- Shared conversations
- Help
- Personal mode

Research mode may offer richer citation/source controls but must not put telemetry above the answer.

---

# 6.6 Research — Mobile

Persistent navigation:

```text
Hỏi/Overview | Evidence | [CLARA] | Sources | More
```

Depending on validated usage, the first destination may be Research Overview or recent research history.

Do not create a fake “research dashboard” if no meaningful server-backed state exists.

---

# 6.7 Administration — Web

Primary:

1. Overview
2. Knowledge
3. Answer Flow
4. Monitoring
5. Analytics

Secondary:

- Audit
- Clinical analytics
- RAG evaluation
- Ingestion
- DSAR where enabled
- Control Tower
- Ecosystem
- Help

---

# 6.8 Administration — Mobile

Administration is **desktop-first**.

Mobile admin may expose:

- service status;
- critical operational alerts;
- read-only overview;
- urgent moderation/compliance actions if safe.

Complex flow visualization, dense observability tables, ingestion controls, and high-risk system configuration may remain desktop-only.

A mobile UI must not be created merely for “parity.”

---

# 7. First-Run / Onboarding v2

# 7.1 Global First Run

Applies to all authenticated users.

Steps:

1. Welcome to CLARA.
2. Language.
3. Required AI/transparency notice.
4. Core preference selection.
5. Enter role-appropriate experience.

No health data fields.

Target duration: under one minute if required notices are already understood.

---

# 7.2 Personal Health Setup

Triggered only on entry into Personal health capabilities when server state requires it.

Steps:

1. “Bạn muốn CLARA giúp việc gì?”
2. Optional basic profile.
3. Optional personalization consent.
4. Review.
5. Enter Today.

All health fields:

- self-declared;
- optional unless a backend contract genuinely requires them;
- clearly labelled;
- editable later.

---

# 7.3 Professional Orientation

Clinician example:

```text
CLARA cho công việc lâm sàng

• Hỏi câu hỏi y khoa với nguồn
• Hội chẩn nhiều góc nhìn
• Soạn ghi chép buổi khám
• Xem mức độ chắc chắn và bất đồng

CLARA không thay thế đánh giá chuyên môn của bạn.

[Tiếp tục]
```

No personal health questionnaire.

---

# 7.4 Tool-Specific Consent

Consent appears at the moment it becomes meaningful.

Examples:

- Scribe recording consent before microphone capture.
- Sharing scope before creating a share.
- Personalization consent before personalized use.
- Data export confirmation before export.
- Destructive action confirmation before delete/revoke.

---

# 8. Full Visual Transformation

# 8.1 New Art Direction

Working name:

> **CLARA Spatial Care**

Style:

> **Calm Clinical + Spatial Glass**

The aesthetic must feel:

- modern;
- premium;
- human;
- soft but not childish;
- clinical but not hospital-sterile;
- intelligent without looking like a developer console;
- spatial and layered without neon “AI” visual clichés.

Reference qualities:

- contemporary Apple/iOS spatial hierarchy;
- modern consumer health apps;
- high-quality enterprise health software;
- low-noise AI interfaces;
- editorial readability;
- restrained glass in chrome;
- strong typographic hierarchy.

Avoid:

- cyberpunk;
- cyan-on-black dashboards;
- neon glows;
- holographic panels;
- excessive gradients;
- border around every element;
- cards inside cards inside cards;
- excessive uppercase labels;
- tiny 11px professional UI everywhere;
- glass on critical medical content.

---

# 8.2 Visual Personality

CLARA should communicate four qualities:

## Calm

Large breathing room, quiet background, low-noise surfaces.

## Clear

One obvious primary action, strong hierarchy, concise copy.

## Trustworthy

Semantic colors have stable meaning; no fake confidence; critical states are opaque and legible.

## Intelligent

Contextual organization, progressive disclosure, subtle motion, strong information synthesis.

---

# 9. Canonical Color System v3

The palette below replaces both:

- the current web deep-well palette as the only canonical brand identity;
- the stale manually mirrored Flutter “web palette.”

The system supports full Light and Dark themes.

The default preference should be **System**, not forced Dark.

Light mode is the visual reference for Personal care.

Dark mode has full parity and may be preferred by professional users, but role must not automatically force theme.

---

# 9.1 Brand Blue — “Clara Azure”

| Token | Hex | Usage |
|---|---:|---|
| `brand-50` | `#EFF7FF` | very soft selected background |
| `brand-100` | `#DCEEFF` | soft accent |
| `brand-200` | `#B9DCFF` | subtle highlight |
| `brand-300` | `#86C4FF` | illustration/accent |
| `brand-400` | `#4BA7FF` | hover/accent |
| `brand-500` | `#1A86F5` | bright brand |
| `brand-600` | `#0B6FD8` | primary action |
| `brand-700` | `#095BB4` | pressed/strong |
| `brand-800` | `#0B4A91` | dark text accent |
| `brand-900` | `#103F76` | deep brand |
| `brand-950` | `#0B274D` | deepest brand |

Primary interactive action:

```text
Light: brand-600
Dark:  brand-500 or accessible mapped equivalent
```

Exact foreground/background combinations must pass automated WCAG contrast tests.

---

# 9.2 AI Accent — “Clara Iris”

AI-specific decoration may use a restrained violet accent.

| Token | Hex |
|---|---:|
| `iris-50` | `#F5F3FF` |
| `iris-100` | `#EDE9FE` |
| `iris-300` | `#C4B5FD` |
| `iris-500` | `#8B7CF6` |
| `iris-600` | `#7566E8` |
| `iris-700` | `#6354C9` |

Rules:

- Iris is not a safety color.
- Iris must not mean “confidence.”
- Iris may identify AI/CLARA-generated or AI-assisted content.
- Do not use violet glow around every AI feature.

---

# 9.3 Supportive Mint

| Token | Hex |
|---|---:|
| `mint-50` | `#ECFDF8` |
| `mint-100` | `#D1FAEE` |
| `mint-500` | `#14A88D` |
| `mint-600` | `#0F8A75` |
| `mint-700` | `#0F6F61` |

Usage:

- connected-device success;
- completion;
- supportive non-critical positive state.

Do not use Mint for medication “safe” language unless the underlying safety contract actually supports that conclusion.

---

# 9.4 Semantic Status Palette

## Success

```text
Light text       #137A57
Light background #EAF8F2
Light border     #BCE9D7

Dark text        #75E0B7
Dark background  #102D25
Dark border      #245B49
```

## Warning

```text
Light text       #8A5A00
Light background #FFF7E2
Light border     #F4D58D

Dark text        #FFD37A
Dark background  #33260D
Dark border      #6D501B
```

## Danger

```text
Light text       #B42332
Light background #FFF0F1
Light border     #F4B9BF

Dark text        #FF9CA7
Dark background  #35141A
Dark border      #73303A
```

## Information

Use Brand Blue family.

## Unknown / unavailable

Neutral gray/slate.

Unknown must never be rendered green.

---

# 9.5 Neutral Palette — Light

| Token | Hex |
|---|---:|
| `canvas` | `#F6F8FB` |
| `canvas-subtle` | `#F1F4F8` |
| `surface-0` | `#FFFFFF` |
| `surface-1` | `#FBFCFE` |
| `surface-2` | `#F3F6FA` |
| `surface-3` | `#EBF0F6` |
| `border-subtle` | `#E3E8EF` |
| `border-default` | `#D5DDE7` |
| `border-strong` | `#AEB9C8` |
| `text-primary` | `#162033` |
| `text-secondary` | `#48566A` |
| `text-tertiary` | `#6D7A8E` |
| `text-disabled` | `#9AA5B4` |

The light canvas should not be pure white. White is reserved for primary surfaces.

---

# 9.6 Neutral Palette — Dark

| Token | Hex |
|---|---:|
| `canvas` | `#0B111A` |
| `canvas-subtle` | `#0E1520` |
| `surface-0` | `#111A26` |
| `surface-1` | `#15202D` |
| `surface-2` | `#1B2735` |
| `surface-3` | `#223143` |
| `border-subtle` | `#253447` |
| `border-default` | `#33455B` |
| `border-strong` | `#566B83` |
| `text-primary` | `#F2F6FB` |
| `text-secondary` | `#C7D1DE` |
| `text-tertiary` | `#93A2B6` |
| `text-disabled` | `#68788D` |

Dark surfaces should be blue-neutral, not charcoal-brown and not pure black.

---

# 9.7 Role Accent

Role color is optional **orientation**, not semantic state.

```text
Personal       Azure
Clinical       Teal/Mint
Research       Iris
Administration Slate/Indigo
```

Use only for:

- tiny mode badge;
- navigation accent;
- workspace icon;
- optional header micro-accent.

Never recolor warning/danger/success based on role.

---

# 9.8 Gradient Policy

Allowed gradients:

1. Brand hero ambient background.
2. CLARA primary action ambient highlight.
3. Decorative illustration.
4. Non-data onboarding background.

Example:

```css
background:
  radial-gradient(
    60rem 34rem at 80% -10%,
    rgb(26 134 245 / 10%),
    transparent 68%
  );
```

Disallowed:

- safety cards;
- tables;
- medication interaction verdicts;
- clinical recommendations;
- Scribe transcript/SOAP;
- data visualization legends;
- every generic card.

---

# 10. Glass System

Glass is a **navigation and chrome material**.

## 10.1 Allowed

- mobile floating nav;
- mobile top bar;
- command palette;
- transient side sheet;
- compact toolbar;
- floating contextual controls;
- desktop command bar when background content is underneath.

## 10.2 Disallowed

- medication interaction result;
- red-flag clinical alert;
- Council final recommendation;
- transcript;
- SOAP note;
- consent/legal text;
- data table;
- form containing sensitive information;
- long-reading content.

## 10.3 Light Glass

```text
fill              rgba(255,255,255,0.72)
fill-strong       rgba(255,255,255,0.86)
stroke            rgba(255,255,255,0.74)
edge              rgba(142,164,190,0.22)
blur regular      18px
blur strong       28px
saturation        130–150%
```

## 10.4 Dark Glass

```text
fill              rgba(17,26,38,0.68)
fill-strong       rgba(17,26,38,0.84)
stroke            rgba(110,139,170,0.22)
edge              rgba(164,197,230,0.14)
blur regular      20px
blur strong       30px
saturation        125–140%
```

## 10.5 Fallback

If:

- reduced transparency;
- platform blur unsupported;
- performance tier fails;
- battery/low-power policy requires;

render identical geometry with an opaque `surface-1` or `surface-2`.

No layout change during fallback.

---

# 11. Typography

# 11.1 Font

Primary:

```text
"Be Vietnam Pro Variable"
```

Fallback:

```text
"Segoe UI Variable",
"Segoe UI",
system-ui,
-apple-system,
sans-serif
```

Rationale:

- excellent Vietnamese readability;
- friendly but professional;
- strong numeric and UI performance;
- already aligned with CLARA's current language direction.

Do not introduce multiple decorative font families.

---

# 11.2 Type Scale

## Web

| Token | Size | Line | Weight |
|---|---:|---:|---:|
| Display XL | 48 | 56 | 650 |
| Display | 40 | 48 | 650 |
| H1 | 32 | 40 | 650 |
| H2 | 26 | 34 | 650 |
| H3 | 21 | 28 | 620 |
| Title | 18 | 26 | 600 |
| Body L | 17 | 28 | 430 |
| Body | 15.5–16 | 25 | 430 |
| Body S | 14 | 22 | 430 |
| Label | 13 | 18 | 600 |
| Caption | 12 | 18 | 500 |

Avoid default visible text below 12px.

## Mobile

Use the same semantic hierarchy mapped to Flutter TextTheme and dynamic type.

Minimum important body size:

```text
16sp equivalent
```

Labels may use 12–14sp depending on function.

---

# 11.3 Typography Rules

- Sentence case by default.
- Avoid excessive uppercase section labels.
- Uppercase may be used only for tiny metadata with adequate tracking.
- Vietnamese diacritics must never feel cramped.
- Body paragraphs use comfortable line height.
- Long clinical/evidence reading width should be constrained.
- Tabular data may use tighter line-height only where necessary.
- Use tabular numerals for metrics and dates where supported.

---

# 12. Spacing System

Canonical 4px base:

```text
space-0   0
space-1   4
space-2   8
space-3   12
space-4   16
space-5   20
space-6   24
space-8   32
space-10  40
space-12  48
space-16  64
space-20  80
```

Rules:

- 16px normal mobile screen inset.
- 20–24px large phone/tablet inset.
- 24–32px desktop section padding.
- 32–48px between major desktop sections.
- 12–16px between related controls.
- 8px within micro-control groups.

---

# 13. Corner Radius

Canonical:

```text
radius-xs     8
radius-sm     12
radius-md     16
radius-lg     20
radius-xl     28
radius-pill   999
```

Usage:

- fields: 12–14;
- buttons: 12–14;
- standard cards: 16–20;
- hero surfaces: 24–28;
- sheets: 24–28 top corners;
- nav pill: pill;
- status badge: pill.

Avoid mixing 4, 8, 12, 14, 20, 24 arbitrarily.

---

# 14. Elevation and Depth

The redesign uses **tonal depth first, shadow second**.

## Light

```text
Level 0 — canvas
Level 1 — surface / subtle border
Level 2 — raised card / 1 soft shadow
Level 3 — popover / sheet
Level 4 — modal / floating command
```

Suggested shadows:

```text
shadow-1: 0 1px 2px rgba(20,32,51,.04)
shadow-2: 0 6px 20px rgba(20,32,51,.07)
shadow-3: 0 16px 40px rgba(20,32,51,.12)
```

## Dark

Rely more on:

- surface tone;
- subtle stroke;
- restrained highlight.

Avoid heavy black shadows.

---

# 15. Iconography

Use one semantic icon abstraction per client.

Requirements:

- rounded/simple geometry;
- consistent optical size;
- 20px standard web;
- 22–24dp primary mobile nav;
- 16–18 small metadata;
- icons are decorative when adjacent visible label already defines action;
- icon-only actions require accessible labels;
- no external icon font required for critical UI;
- no mixed icon styles inside one navigation area.

Avoid literal “AI sparkle” icon for every CLARA action.

---

# 16. Illustration Policy

Illustration is allowed for:

- onboarding;
- first-time empty states;
- generic no-data state;
- safe educational explanation.

Illustration must not:

- imply diagnosis;
- imply a medicine is safe;
- depict false clinical certainty;
- replace actual data;
- be visually dominant inside professional tools.

Preferred style:

- abstract;
- geometric;
- soft depth;
- simple health motifs;
- no uncanny pseudo-medical human anatomy generated decoratively.

---

# 17. Motion System

Motion should feel responsive and physical.

Tokens:

```text
instant     0–80ms
fast        120–160ms
standard    180–240ms
emphasis    280–360ms
```

Recommended easing:

```text
enter       cubic-bezier(.2,.8,.2,1)
exit        cubic-bezier(.4,0,1,1)
standard    cubic-bezier(.2,0,0,1)
```

Use spring-style native transitions where Flutter/platform semantics are stronger.

Motion use:

- nav selection;
- expanding source detail;
- sheet presentation;
- completing task;
- contextual status transition;
- skeleton → content.

Do not animate:

- critical warning appearance in a playful way;
- error messages with bouncing;
- clinical recommendation changes;
- safety verdict with confetti.

Reduced motion:

- eliminate non-essential spatial animation;
- retain instantaneous state change/focus.

---

# 18. Component System v3

Every component must have:

- light theme;
- dark theme;
- hover/pressed/focus/disabled/loading/error;
- text scaling;
- RTL-safe geometry where practical even if RTL is not currently shipped;
- keyboard semantics on Web;
- screen reader semantics;
- Vietnamese long-copy fixture.

Core primitives:

```text
Button
IconButton
Link
Field
TextArea
Select
SearchField
Checkbox
Radio
Switch
SegmentedControl
Tabs
Badge
StatusChip
Avatar
Tooltip
Popover
Menu
Surface
Card
ActionCard
ListRow
DataRow
Progress
Skeleton
EmptyState
InlineError
Alert
Toast
Snackbar
Modal
BottomSheet
SideSheet
ConfirmDialog
Stepper
Timeline
SourceDisclosure
CitationAnchor
PageHeader
SectionHeader
AppShell
TopBar
BottomNav
NavigationRail
WorkspaceMenu
ProfileMenu
CommandBar
```

---

# 19. Button Hierarchy

## Primary

Solid Brand Blue.

Use only one primary action per local decision area.

## Secondary

Tonal brand surface.

## Tertiary

Text/quiet button.

## Danger

Red semantic action only for actual destructive operations.

## Clinical confirmation

A confirmation is not automatically a green button.

Action color remains Brand unless semantics genuinely mean positive completion.

---

# 20. Surface Hierarchy

Use fewer cards.

A page may contain:

```text
Canvas
  Section
    one Surface/Card if grouping is needed
```

Avoid:

```text
Card
  Card
    Card
      row with its own border
```

Lists should often use:

- one parent surface;
- separators;
- grouped rows;

instead of individual cards for every row.

---

# 21. Responsive Grid

# 21.1 Web

Breakpoints:

```text
< 640       compact phone
640–899     large phone / small tablet
900–1199    tablet / compact desktop
1200–1439   desktop
>= 1440     large desktop
```

Do not rely only on Tailwind's historical breakpoint names; define responsive behavior by product need.

## Content widths

Personal reading:

```text
max 1120px page
640–760px long reading column
```

Clinical data:

```text
up to 1280–1440px where genuinely useful
```

Admin:

```text
up to 1440–1600px for operational tables
```

---

# 21.2 Mobile

Phone compact:

- floating bottom chrome;
- single content column;
- sheet-based secondary navigation.

Tablet:

- navigation rail;
- content may use master/detail where beneficial;
- never scale phone cards to huge empty widths.

---

# 22. Web Shell v3

Desktop structure:

```text
┌──────────────────────────────────────────────────────┐
│ Sidebar │ Top/global context                         │
│         ├────────────────────────────────────────────┤
│         │ Content                                    │
│         │                                            │
└──────────────────────────────────────────────────────┘
```

## Sidebar expanded

Target width:

```text
248–264px
```

Structure:

```text
CLARA
[professional mode picker if >1 useful mode]

Primary navigation

More

────────
Account/profile
```

Do not place:

- theme buttons;
- language buttons;
- logout;
- profile switch;

all as independent always-visible sidebar actions.

Put them into Account/Profile menus.

## Sidebar collapsed

Target:

```text
72px
```

Workspace click opens a popover.

Do not cycle modes blindly.

---

# 23. Mobile Shell v3

## Personal

```text
┌───────────────────────┐
│ contextual top bar    │
│                       │
│ screen content        │
│                       │
│  floating glass nav   │
│ A   B   CLARA   C   D │
└───────────────────────┘
```

## Professional

Same shell geometry, different destination map.

Center CLARA remains stable, reducing relearning when switching mode.

---

# 24. Top Bar Rules

Personal top bar:

- current context;
- notifications only when useful;
- profile avatar;
- page action only if global to page.

Professional top bar may add:

- mode/context label;
- current case/session context;
- profile/context switch if supported.

Do not duplicate page title and top-bar title unless one becomes compact on scroll.

---

# 25. Personal Today Redesign

# 25.1 Active state

Above fold:

```text
Hôm nay

TIẾP THEO
Đo huyết áp
Trước 08:30
[Open]

2 việc khác hôm nay
1 mục chờ xác nhận
```

Next:

- upcoming tasks;
- pending confirmation warning;
- journey context.

Then compact utility actions:

```text
Hỏi CLARA
Kiểm tra thuốc
Chuẩn bị đi khám
```

Progress analytics appear below useful tasks.

## Requirements

- no generic action grid before the next task;
- no meaningless zero stat cards;
- no AI-generated task shown as confirmed unless server says human-confirmed;
- offline cache clearly labelled;
- offline writes blocked if contract requires online state.

---

# 26. First-Time Today

```text
Chào bạn.

Bạn muốn CLARA giúp việc gì trước?

[ Bắt đầu một hành trình sức khỏe ]

Hỏi CLARA về một vấn đề sức khỏe
```

Optional supporting examples:

- theo dõi huyết áp;
- chuẩn bị tái khám;
- quản lý thuốc.

Examples must not imply diagnosis.

---

# 27. LifeMap Redesign

LifeMap should feel like a health journey, not project-management software.

Hub:

```text
Hành trình sức khỏe

Active journeys
───────────────
[Journey]
Current focus
Next step
Last update

Archived
```

Journey detail:

1. Current state.
2. Next accepted action.
3. Timeline.
4. Questions / Evidence.
5. Updates / revisions.
6. Advanced provenance/details behind disclosure.

Creation:

```text
Goal
→ what to track
→ schedule
→ reminders/support
→ review
```

No episode write before explicit review if current contract supports draft behavior.

---

# 28. Medicines Redesign

One hub, three concepts.

```text
Thuốc & an toàn

[+ Thêm thuốc]

Đang dùng
...

Cần xác nhận
...

Tủ thuốc
...

KIỂM TRA AN TOÀN
[Kiểm tra tương tác]
```

Never merge records solely by display name.

Cabinet items use explicit copy:

> “Có trong tủ thuốc — không có nghĩa là đang sử dụng.”

Interaction safety:

1. medicines checked;
2. availability/authority status;
3. highest-priority warning;
4. actionable guidance;
5. sources;
6. unavailable/fail-closed state.

Never produce a green “safe” conclusion when authority is unavailable.

---

# 29. PHR Redesign

# 29.1 Hub

Do not embed a 55%-height PHR screen inside Profile.

Profile shows summary:

```text
Hồ sơ sức khỏe
4/6 phần đã cập nhật
Cập nhật gần nhất ...
[Open]
```

Full PHR:

```text
Identity
Contacts & insurance
Allergies
Conditions/history
Medicines
Measurements
Documents
```

Each section:

- full-screen/focused;
- clear save state;
- provenance where relevant;
- conflict/reload behavior;
- no silent overwrite claims.

---

# 30. Visit Preparation

Flow:

```text
1. Thông tin buổi khám
2. Điều bạn lo lắng
3. Thuốc & tài liệu
4. Câu hỏi muốn hỏi
5. Xem lại
```

Review screen creates a portable mental model:

```text
Visit Pack
```

Scribe recording controls only appear where contextually appropriate.

---

# 31. Family / Sharing

Hub tabs:

```text
Tôi chia sẻ
Được chia sẻ với tôi
Nhật ký truy cập
```

Invitation flow must state:

- who;
- what data;
- allowed actions;
- purpose;
- duration;
- revoke path.

No token in telemetry.

Shared context must be visually obvious:

```text
Bạn đang xem dữ liệu được chia sẻ bởi ...
Phạm vi: ...
```

---

# 32. Chat Redesign

# 32.1 Core hierarchy

Every answer:

1. Critical/emergency warning if applicable.
2. Direct answer.
3. What to do next.
4. Uncertainty.
5. Sources.
6. Concise explanation.
7. Role-gated advanced details.

Composer stays visually dominant.

## Personal

Minimal expert terminology.

## Clinician

May show:

- applicability;
- guideline/evidence strength;
- specialist disagreement;
- source metadata;
- uncertainty.

## Research

May show:

- deeper source inspection;
- provenance;
- search mode;
- evidence synthesis controls.

No raw chain-of-thought.

No internal prompt.

No unsafe provider secret.

---

# 33. Clinical Overview

The professional home is a launchpad, not a fabricated analytics dashboard.

Doctor:

```text
Xin chào bác sĩ

TIẾP TỤC
[real resumable activity if available]

CÔNG CỤ
Hỏi CLARA
Hội chẩn
Ghi chép khám
Bằng chứng

CẦN XEM LẠI
[real alerts only]
```

If no resumable work exists:

```text
Chưa có công việc đang tiếp tục.

[Hỏi CLARA] [Hội chẩn] [Ghi chép]
```

Do not fallback to `/today`.

---

# 34. Council Redesign

Case flow:

```text
Case
→ Question
→ Relevant context
→ Review
→ Run
→ Result
```

Result hierarchy:

1. Escalation / red flags.
2. Core recommendation.
3. Agreement and disagreement.
4. Uncertainty.
5. Evidence.
6. Clinician action.
7. Technical details.

Technical pipeline visualization is secondary.

---

# 35. Scribe Redesign

Canonical UI states:

```text
Consent
→ Capture
→ Transcript review
→ SOAP review
→ Draft complete
→ Sign/export where supported
```

Explicit badges:

```text
Recording
Transcript ready
Draft
Reviewed
Finalized legacy
Signed
Exported
Amended
```

Never imply signed when only finalized.

The transcript/SOAP reading area uses opaque high-contrast surfaces, not glass.

---

# 36. Evidence / Research Redesign

Evidence flow:

```text
Question
→ Confirm scope
→ Run
→ Results
```

Results:

- direct synthesis;
- key sources;
- applicability;
- uncertainty;
- source details;
- update/subscription secondary.

Source Hub:

```text
Browse
Sync / Manage
```

Do not mix connector administration into ordinary evidence browsing.

---

# 37. Admin Redesign

Admin should use a denser but visually coherent system.

Guidelines:

- tables over card grids where comparison matters;
- no synthetic KPI;
- status chips with text;
- expandable technical detail;
- global filters sticky where useful;
- monitoring failure states explicit;
- data visualization source and time window visible.

Admin may use reduced radius and denser spacing tokens while staying in the same system.

---

# 38. UX Density Modes

These are design presets, not user-facing toggles initially.

## Comfortable — Personal

```text
content gap       24–32
card padding      20–24
row min height    56
body size         16+
```

## Compact — Clinical

```text
content gap       16–24
card padding      16–20
row min height    48
body size         14–16
```

## Dense — Admin

```text
content gap       12–20
table row         40–48
body size         13.5–15
```

Touch targets remain accessible.

---

# 39. Microcopy Rules

Prefer:

```text
Hỏi CLARA
Cần xem lại
Chưa có dữ liệu
Không thể kiểm tra lúc này
Mục này chưa được xác nhận
```

Avoid consumer-facing:

```text
Inference confidence
Pipeline stage
Router verdict
Model tier
RAG cluster
Fallback branch
```

unless explicitly needed in authorized expert diagnostics.

Error messages contain:

1. what happened;
2. whether data may be incomplete;
3. what the user can do.

---

# 40. Loading States

Use skeleton only where layout is predictable.

Use inline spinner for button-level operation.

Never replace the whole application with a spinner for a small local refresh.

Professional tools should preserve already loaded context while refreshing a secondary panel.

---

# 41. Empty States

Every empty state must answer:

1. Is this normal?
2. What does it mean?
3. What can I do?
4. Is data unavailable vs truly empty?

Examples:

```text
No current journeys
No saved medicines
No Council case yet
No system alert returned
Unable to load alerts
```

These are different states and must not share one generic “Nothing here” component copy.

---

# 42. Error / Unknown State

Never map error to success-like presentation.

Examples:

```text
Unknown
Unavailable
Not loaded
Insufficient evidence
Authority unavailable
```

These need their own semantic neutral/warning presentation.

---

# 43. Accessibility Requirements

Target: WCAG 2.2 AA.

Must test:

- keyboard complete navigation;
- focus visibility;
- focus trap;
- focus restoration;
- 200% browser zoom;
- 320px reflow;
- Flutter dynamic text;
- screen reader;
- reduced motion;
- reduced transparency;
- high contrast/forced colors where applicable;
- no color-only status;
- error association;
- live-region updates;
- touch targets.

Minimum targets:

```text
Web    44 × 44 px where practical
Mobile 48 × 48 dp
```

---

# 44. Web Technical Architecture

Target:

```text
RootLayout
└── AppProviders
    ├── SessionProvider
    ├── ProfileProvider
    ├── PreferenceProvider
    ├── ExperienceProvider
    └── AuthenticatedShell
        ├── DesktopNavigation
        ├── MobileNavigation
        ├── GlobalTopBar
        └── RouteContent
```

## SessionProvider

Owns:

- authentication state;
- authoritative role;
- `/auth/me`;
- logout.

Must not refetch solely because pathname changes.

## ProfileProvider

Owns:

- active profile;
- permitted profile context;
- owned profile switching;
- shared-context reset behavior.

## PreferenceProvider

Owns only:

- language;
- theme;
- sidebar collapse;
- user display preferences.

No health data in browser preference storage.

## ExperienceProvider

Inputs:

```ts
role
capabilities
pathname
persistedMode
```

Outputs:

```ts
availableModes
activeMode
navigation
modeHome
```

---

# 45. Web Route Model

Define one explicit route registry.

```ts
type ExperienceMode =
  | "personal"
  | "clinical"
  | "research"
  | "admin";

interface RouteDefinition {
  id: string;
  href: string;
  match?: string[];
  access: {
    roles: UserRole[];
    flags?: string[];
  };
  canonicalMode?: ExperienceMode;
  aliasOf?: string;
  public?: boolean;
  authenticatedUtility?: boolean;
}
```

Presentation:

```ts
interface ExperienceDefinition {
  id: ExperienceMode;
  allowedRoles: UserRole[];
  homeRouteId: string;
  primaryRouteIds: string[];
  secondaryRouteIds: string[];
  mobilePrimaryRouteIds: string[];
}
```

Critical invariant:

> Route authorization must never import primary navigation.

---

# 46. Mobile Technical Architecture

Introduce:

```dart
enum ExperienceMode {
  personal,
  clinical,
  research,
  administration,
}
```

And:

```dart
class ExperienceConfig {
  final ExperienceMode mode;
  final List<ClaraDestination> primary;
  final ClaraDestination primaryAction;
  final List<ClaraDestination> more;
}
```

Destination enum:

```dart
enum ClaraDestination {
  today,
  lifeMap,
  askClara,
  medicines,
  profile,
  clinicalOverview,
  council,
  scribe,
  evidence,
  sourceHub,
  adminOverview,
  settings,
  help,
}
```

Central builder:

```dart
Widget buildDestination(
  ClaraDestination destination,
  AppDependencies dependencies,
);
```

Role logic must not be scattered through ProfileHub.

---

# 47. Canonical Token Architecture

Create a repository-level semantic token source.

Recommended:

```text
packages/design-tokens/
  clara.tokens.json
  schema.json
  README.md
```

Example:

```json
{
  "color": {
    "light": {
      "canvas": "#F6F8FB",
      "surface": "#FFFFFF",
      "textPrimary": "#162033",
      "brandPrimary": "#0B6FD8"
    },
    "dark": {
      "canvas": "#0B111A",
      "surface": "#111A26",
      "textPrimary": "#F2F6FB",
      "brandPrimary": "#1A86F5"
    }
  }
}
```

Generate:

```text
apps/web/styles/generated/tokens.css
apps/mobile/lib/theme/generated/clara_tokens.g.dart
```

Never manually copy palette values again.

Generated files must contain a source hash/version.

---

# 48. Token Categories

Canonical token contract includes:

```text
color
typography
spacing
radius
elevation
motion
breakpoint
opacity
blur
component sizing
density
```

Semantic aliases:

```text
surface.canvas
surface.panel
surface.raised
surface.glass
text.primary
text.secondary
text.muted
action.primary
action.primaryHover
status.success.*
status.warning.*
status.danger.*
status.unknown.*
focus.ring
```

Components consume semantic tokens, not raw palette tokens unless needed for visualization.

---

# 49. Web Token Migration

Replace current global ad-hoc variables gradually.

Migration order:

1. Canonical generated tokens.
2. Compatibility aliases.
3. New components use canonical names.
4. Migrate existing surfaces.
5. Delete legacy aliases after static import check.
6. Raw color allowlist only for data visualization where necessary.

No giant one-shot CSS rewrite.

---

# 50. Mobile Token Migration

Replace:

- stale `WebPalette`;
- legacy teal seed dependence in active Unified path;
- duplicated radius/spacing where mismatched.

Keep legacy paths untouched until removal gate if needed, but Unified must use generated semantic tokens.

---

# 51. Feature-Flag Strategy

Feature flags must not create permanent product generations.

Allowed:

```text
new shell rollout
new token rollout
temporary legacy rollback
specific feature capability
```

Avoid long-term:

```text
Legacy vs V2 vs V3 vs Unified combinations
```

Document supported combinations explicitly.

---

# 52. Safety Invariants

The redesign must not change:

- server RBAC authority;
- consent authority;
- CSRF;
- profile isolation;
- public-share boundaries;
- DrugBank authority/fail-closed behavior;
- FIDES safety behavior;
- emergency fast path;
- auditability;
- no-autonomous-confirm rules;
- no chain-of-thought exposure;
- provenance rules;
- signed/finalized distinction.

UI may improve presentation, never weaken these controls.

---

# 53. Privacy Invariants

Never place in analytics:

- prompt/question content;
- patient name;
- transcript;
- SOAP content;
- medication names;
- diagnosis;
- document body;
- public-share token;
- health measurements;
- raw profile identifiers where avoidable.

Analytics events use coarse no-PII identifiers.

---

# 54. Analytics Events

Examples:

```text
experience_mode_entered
navigation_destination_opened
today_next_task_opened
today_task_completed
personal_setup_started
personal_setup_skipped
clinical_council_opened
clinical_scribe_opened
research_evidence_opened
profile_health_record_opened
mode_switched
```

Use server-safe anonymized/coarse context.

---

# 55. Functional Requirements

## 55.1 Role / Mode

| ID | Requirement | Priority |
|---|---|---|
| ROLE-001 | UI derives available modes from server-authoritative role/capability state. | MUST |
| ROLE-002 | Doctor defaults to Clinical on Web and Mobile. | MUST |
| ROLE-003 | Researcher defaults to Research/professional experience. | MUST |
| ROLE-004 | Admin defaults to Administration. | MUST |
| ROLE-005 | Personal remains explicitly reachable to professional roles when authorized. | MUST |
| ROLE-006 | Mode switching never grants route access. | MUST |
| ROLE-007 | Normal user never sees a one-choice mode/workspace selector. | MUST |
| ROLE-008 | Professional user always sees current mode clearly. | MUST |
| ROLE-009 | Direct authorized links preserve requested destination. | MUST |
| ROLE-010 | Invalid persisted mode falls back safely. | MUST |

## 55.2 Onboarding

| ID | Requirement | Priority |
|---|---|---|
| ONB-001 | Personal PHR setup must not globally block professional modes. | MUST |
| ONB-002 | Global onboarding contains no personal health questionnaire. | MUST |
| ONB-003 | Personal health facts remain optional/self-declared unless contract requires otherwise. | MUST |
| ONB-004 | Clinician orientation is role-appropriate. | MUST |
| ONB-005 | Required legal/transparency gates remain enforced. | MUST |
| ONB-006 | Tool-specific consent appears at point of use. | MUST |
| ONB-007 | Personal setup is resumable. | SHOULD |

## 55.3 Navigation

| ID | Requirement | Priority |
|---|---|---|
| NAV-001 | Desktop primary destinations ≤7 per mode. | MUST |
| NAV-002 | Phone persistent destinations ≤5 including center action. | MUST |
| NAV-003 | Every authorized capability remains reachable. | MUST |
| NAV-004 | `More` never becomes authorization. | MUST |
| NAV-005 | Collapsed mode switch uses menu/popover, not blind cycling. | SHOULD |
| NAV-006 | Existing compatibility deep links remain supported until explicit retirement. | MUST |
| NAV-007 | Personal users do not need to understand “workspace.” | MUST |

## 55.4 Personal

| ID | Requirement | Priority |
|---|---|---|
| PER-001 | Populated Today places next accepted task before generic shortcuts. | MUST |
| PER-002 | Empty Today contains one main CTA and Ask CLARA secondary. | MUST |
| PER-003 | Pending confirmation is explicitly not a conclusion. | MUST |
| PER-004 | Offline cached data shows freshness. | MUST |
| PER-005 | Unsupported offline writes are blocked. | MUST |
| PER-006 | PHR opens as full surface, not nested fixed-height scroll. | MUST |
| PER-007 | Medicines/Cabinet/Safety remain distinct. | MUST |
| PER-008 | Family sharing displays scope/duration/revocation clearly. | MUST |

## 55.5 Clinical

| ID | Requirement | Priority |
|---|---|---|
| CLIN-001 | Council is reachable in one primary-nav interaction from Clinical home. | MUST |
| CLIN-002 | Scribe is reachable in one primary-nav interaction. | MUST |
| CLIN-003 | Professional home never implicitly falls back to Personal Today. | MUST |
| CLIN-004 | Professional home uses only real supported state. | MUST |
| CLIN-005 | Scribe consent occurs before capture when required. | MUST |
| CLIN-006 | Signed/finalized/exported/amended remain distinct. | MUST |
| CLIN-007 | Council red flags and disagreement precede technical diagnostics. | MUST |
| CLIN-008 | Personal data mode is explicitly distinguishable from professional mode. | MUST |

## 55.6 Research

| ID | Requirement | Priority |
|---|---|---|
| RES-001 | Evidence synthesis precedes technical telemetry. | MUST |
| RES-002 | Source inspection supports provenance and applicability. | MUST |
| RES-003 | Source Hub separates browsing from connector/sync operations. | SHOULD |
| RES-004 | Research detail is role-gated. | MUST |

## 55.7 Visual System

| ID | Requirement | Priority |
|---|---|---|
| VIS-001 | One canonical token source generates Web and Mobile tokens. | MUST |
| VIS-002 | Light and Dark theme have full parity. | MUST |
| VIS-003 | System is default theme preference for new users. | SHOULD |
| VIS-004 | Glass is restricted to chrome/transient UI. | MUST |
| VIS-005 | Safety-critical content is opaque/high contrast. | MUST |
| VIS-006 | No new arbitrary raw colors outside approved visualization scope. | MUST |
| VIS-007 | Semantic statuses have stable meaning across role/theme/platform. | MUST |
| VIS-008 | Vietnamese typography supports all text scales without clipping. | MUST |

---

# 56. Non-Functional Requirements

## Accessibility

```text
WCAG 2.2 AA
No critical/serious automated findings on representative routes
Manual keyboard test
Screen reader test
320px reflow
200% zoom
Dynamic text mobile
Reduced motion
Reduced transparency
```

## Performance

- no second icon library;
- no rendering hidden expensive panels;
- no duplicate session/profile requests caused by presentation refactor;
- lazy diagnostics;
- bundle increase target ≤5% without explicit review;
- glass fallback on low-capability devices;
- maintain smooth 60fps class interaction target on supported mobile devices.

## Maintainability

- no role business logic in visual-only components;
- explicit route registry;
- explicit mode registry;
- generated tokens;
- typed navigation;
- shared state ownership;
- legacy code removal criteria.

---

# 57. Implementation Plan

# Phase 0 — Baseline and Invariants

Deliver:

- exact route inventory;
- exact role/capability matrix;
- current screenshots;
- current accessibility baseline;
- current bundle baseline;
- current Flutter performance baseline;
- safety test freeze.

Exit criteria:

- representative Personal + Doctor + Researcher + Admin flows reproducible;
- no implementation changes yet.

---

# Phase 1 — Canonical Design Tokens

Deliver:

```text
packages/design-tokens/clara.tokens.json
generated CSS
generated Dart tokens
contrast tests
token parity tests
```

Do not redesign all screens yet.

Exit:

- Web and Mobile consume the same generated values on selected primitives.

---

# Phase 2 — Component Library v3

Build/migrate:

- Button;
- Field;
- Surface;
- Card;
- ListRow;
- Status;
- Alert;
- Sheet;
- Modal;
- Tabs;
- PageHeader;
- Empty;
- Loading;
- Navigation primitives.

Exit:

- Story/demo/test fixtures for Light/Dark/VI/EN/large-text.

---

# Phase 3 — Role-Adaptive Product Model

Web:

- formalize mode registry;
- remove remaining presentation/access coupling.

Mobile:

- `ExperienceMode`;
- `ExperienceConfig`;
- `ClaraDestination`;
- role-aware root;
- Council/Scribe removed from Profile.

Exit:

```text
normal → Personal
doctor → Clinical
researcher → Research
admin → Administration
```

---

# Phase 4 — Onboarding Split

Deliver:

- global onboarding;
- personal health setup;
- professional orientation;
- correct gating.

Exit:

- doctor with incomplete Personal PHR can still access permitted Clinical tools;
- normal user's Personal setup remains safe.

---

# Phase 5 — Shell Transformation

Web:

- new Sidebar;
- new Top Bar;
- profile menu;
- deterministic mode switch;
- new mobile nav treatment.

Mobile:

- floating spatial nav v3;
- role-aware destinations;
- glass fallback;
- refined top bar.

Exit:

- navigation parity and accessibility pass.

---

# Phase 6 — Personal Experience

Redesign:

- Today;
- LifeMap;
- Medicines;
- PHR;
- Visits;
- Family;
- Profile.

Exit:

- Personal core journeys pass at all supported viewports.

---

# Phase 7 — Clinical Experience

Redesign:

- professional overview;
- Council;
- Scribe;
- clinical evidence presentation.

Exit:

- doctor can complete canonical flows without entering Personal.

---

# Phase 8 — Research / Admin

Redesign:

- Evidence;
- Source Hub;
- Research shell;
- Admin overview/monitoring/analytics touched surfaces.

Exit:

- professional density spec and data integrity pass.

---

# Phase 9 — Visual Sweep / Legacy Removal

- migrate remaining arbitrary colors;
- remove obsolete CSS;
- remove stale `WebPalette`;
- collapse V2/V3 mobile roots;
- retain only approved rollback adapter.

---

# Phase 10 — Release Validation

- full unit;
- integration;
- E2E;
- visual;
- accessibility;
- bundle;
- performance;
- safety;
- security;
- privacy;
- rollout gate.

---

# 58. Detailed Task Backlog

## 58.1 Baseline

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-001 | P0 | Freeze current web route manifest | 100% routes classified |
| V3-002 | P0 | Freeze mobile destination inventory | all Unified destinations documented |
| V3-003 | P0 | Create normal user fixture | reusable E2E |
| V3-004 | P0 | Create doctor fixture | reusable E2E |
| V3-005 | P0 | Create researcher fixture | reusable E2E |
| V3-006 | P0 | Create admin fixture | reusable E2E |
| V3-007 | P0 | Capture 4-viewport web visual baseline | stored synthetic evidence |
| V3-008 | P0 | Capture phone/tablet mobile baseline | stored synthetic evidence |
| V3-009 | P0 | Capture dark/light baseline | representative screens |
| V3-010 | P0 | Record bundle/build baseline | reproducible |
| V3-011 | P0 | Record mobile frame/perf baseline | reproducible |
| V3-012 | P0 | Lock safety test suites | all pass before redesign |

## 58.2 Canonical tokens

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-020 | P0 | Create token package/schema | schema validated |
| V3-021 | P0 | Encode Light neutral palette | generated |
| V3-022 | P0 | Encode Dark neutral palette | generated |
| V3-023 | P0 | Encode Brand Azure palette | generated |
| V3-024 | P0 | Encode Iris/Mint accents | generated |
| V3-025 | P0 | Encode semantic status palette | contrast pass |
| V3-026 | P0 | Encode spacing/radius/motion | generated |
| V3-027 | P0 | Generate Web CSS tokens | build-integrated |
| V3-028 | P0 | Generate Flutter Dart tokens | build-integrated |
| V3-029 | P0 | Add generated token version/hash | parity traceable |
| V3-030 | P0 | Add contrast test matrix | AA pass |
| V3-031 | P0 | Add web/mobile parity test | exact semantic parity |
| V3-032 | P1 | Add raw-color lint/allowlist | new violations blocked |
| V3-033 | P1 | Map current CSS vars to compatibility aliases | no big-bang break |
| V3-034 | P1 | Deprecate stale mobile `WebPalette` | no Unified imports |

## 58.3 Typography / visual foundation

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-040 | P0 | Define shared typography scale | VI/EN fixtures pass |
| V3-041 | P0 | Map web typography tokens | component tests |
| V3-042 | P0 | Map Flutter TextTheme | dynamic type pass |
| V3-043 | P1 | Define density presets | Personal/Clinical/Admin |
| V3-044 | P1 | Define canonical radius | no new arbitrary radius |
| V3-045 | P1 | Define elevation rules | theme parity |
| V3-046 | P1 | Define glass tokens | light/dark/fallback |
| V3-047 | P1 | Define illustration policy | documented |
| V3-048 | P1 | Define motion tokens/easing | reduced motion pass |

## 58.4 Components

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-050 | P0 | Rebuild Button variants | all states + a11y |
| V3-051 | P0 | Rebuild IconButton | target + label tests |
| V3-052 | P0 | Rebuild Field/TextArea | error semantics |
| V3-053 | P0 | Rebuild Select/Search | keyboard + mobile |
| V3-054 | P0 | Rebuild Alert/Status | no color-only state |
| V3-055 | P1 | Rebuild Card/Surface | density variants |
| V3-056 | P1 | Build ListRow | Personal/Clinical density |
| V3-057 | P1 | Build ActionCard | one-primary hierarchy |
| V3-058 | P0 | Rebuild Modal/Sheet | trap/restore/inert |
| V3-059 | P1 | Build PageHeader/SectionHeader | consistent hierarchy |
| V3-060 | P1 | Build EmptyState variants | true-empty/error distinction |
| V3-061 | P1 | Build Skeleton patterns | layout-stable |
| V3-062 | P1 | Build SourceDisclosure | citation parity |
| V3-063 | P1 | Build Stepper | mobile/web accessible |
| V3-064 | P1 | Build Timeline | LifeMap/Council reuse |
| V3-065 | P1 | Build mode/context badge | role accent only |

## 58.5 Web architecture

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-070 | P0 | Extract SessionProvider | one authoritative request |
| V3-071 | P0 | Extract ProfileProvider | context centralized |
| V3-072 | P1 | Extract PreferenceProvider | no health data |
| V3-073 | P0 | Build ExperienceProvider | typed mode state |
| V3-074 | P0 | Build explicit route registry | exhaustive |
| V3-075 | P0 | Build experience navigation registry | presentation-only |
| V3-076 | P0 | Add direct-link mode derivation tests | correct mode |
| V3-077 | P0 | Add unauthorized-state tests | no hidden auth |
| V3-078 | P1 | Reduce AppShell to composition facade | orchestration removed |
| V3-079 | P1 | Remove pathname-triggered duplicate session calls | network test |
| V3-080 | P1 | Version persisted mode key | safe fallback |

## 58.6 Mobile architecture

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-090 | P0 | Add `ExperienceMode` | typed |
| V3-091 | P0 | Add `ClaraDestination` | typed |
| V3-092 | P0 | Add `ExperienceConfig` | role tested |
| V3-093 | P0 | Centralize destination builder | single owner |
| V3-094 | P0 | Make Unified root role-adaptive | all role tests |
| V3-095 | P0 | Remove Council from ProfileHub | top-level Clinical |
| V3-096 | P0 | Remove Scribe from ProfileHub | top-level Clinical |
| V3-097 | P1 | Add explicit Personal switch | professional flow |
| V3-098 | P1 | Add mode persistence | ID only |
| V3-099 | P1 | Add deep-link mode derivation | tested |
| V3-100 | P1 | Ensure inactive heavyweight destinations do not fetch | network test |

## 58.7 Onboarding

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-110 | P0 | Define global onboarding contract | no personal health fields |
| V3-111 | P0 | Split Personal setup UI | Personal-only |
| V3-112 | P0 | Add clinician orientation | no PHR questionnaire |
| V3-113 | P1 | Add researcher orientation | role appropriate |
| V3-114 | P1 | Add admin orientation | role appropriate |
| V3-115 | P0 | Stop Personal onboarding from blocking Clinical | E2E pass |
| V3-116 | P0 | Stop Personal onboarding from blocking Research/Admin | E2E pass |
| V3-117 | P0 | Preserve ConsentGate ordering | safety pass |
| V3-118 | P1 | Test skip/resume | durable state |
| V3-119 | P1 | Harmonize Web/Mobile onboarding copy | terminology CI |

## 58.8 Web shell

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-130 | P0 | Rebuild desktop sidebar visual | new token system |
| V3-131 | P0 | Rebuild mobile web bottom nav | ≤5 destinations |
| V3-132 | P1 | Rebuild top bar | no duplicated page title |
| V3-133 | P0 | Consolidate profile/settings/logout menu | one trigger |
| V3-134 | P1 | Add deterministic mode popover | no blind cycling |
| V3-135 | P1 | Hide mode selector for single-mode Personal user | tested |
| V3-136 | P1 | Add professional mode badge | visually clear |
| V3-137 | P0 | Maintain focus/keyboard behavior | a11y pass |
| V3-138 | P1 | Add glass chrome with opaque fallback | reduced transparency pass |
| V3-139 | P1 | Migrate shell to new colors/radius/type | visual pass |

## 58.9 Mobile shell

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-150 | P0 | Rebuild floating nav geometry | no overlap/overflow |
| V3-151 | P0 | Add generated glass tokens | parity |
| V3-152 | P0 | Add opaque glass fallback | same geometry |
| V3-153 | P0 | Build Personal destination config | correct |
| V3-154 | P0 | Build Clinical destination config | correct |
| V3-155 | P0 | Build Research destination config | correct |
| V3-156 | P1 | Build minimal Admin mobile config | safe/read-only scope |
| V3-157 | P1 | Rebuild tablet navigation rail | role-aware |
| V3-158 | P1 | Add mode switch sheet for professionals | explicit context |
| V3-159 | P0 | Dynamic text navigation labels | no clipping |
| V3-160 | P0 | TalkBack/VoiceOver semantics | pass |
| V3-161 | P1 | Reduced motion/transparency behavior | pass |

## 58.10 Personal Today

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-170 | P0 | Move next task to first substantive position | above fold |
| V3-171 | P0 | Remove pre-task stats hierarchy | tested |
| V3-172 | P1 | Convert generic quick actions to compact row/sheet | reduced scroll |
| V3-173 | P0 | Build first-time state | one primary CTA |
| V3-174 | P0 | Build caught-up state | no fake urgency |
| V3-175 | P0 | Build completed state | truthful |
| V3-176 | P0 | Preserve pending-confirmation warning | safety |
| V3-177 | P0 | Preserve offline freshness label | safety |
| V3-178 | P0 | Preserve offline write block | safety |
| V3-179 | P1 | Align Web/Mobile Today hierarchy | parity |

## 58.11 Profile / PHR

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-190 | P0 | Remove 55%-viewport PHR embedding | no nested scroll |
| V3-191 | P0 | Build PHR summary row/card | opens full PHR |
| V3-192 | P0 | Reorganize Profile groups | correct taxonomy |
| V3-193 | P1 | Add data-derived completion summary | no health score |
| V3-194 | P0 | Rebuild PHR hub | focused sections |
| V3-195 | P0 | Rebuild PHR section forms | validation/a11y |
| V3-196 | P0 | Preserve provenance | visible |
| V3-197 | P0 | Preserve conflict-safe behavior | no silent overwrite |
| V3-198 | P1 | Rebuild documents/measurement surfaces | visual parity |
| V3-199 | P1 | Harmonize Web/Mobile Profile information architecture | parity |

## 58.12 Medicines

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-210 | P0 | Rebuild Medicines hub | 3-domain distinction |
| V3-211 | P0 | Add one canonical Add action | one per viewport |
| V3-212 | P0 | Clarify Cabinet copy | not “currently taking” |
| V3-213 | P0 | Rebuild Interaction Safety result | fail-closed |
| V3-214 | P0 | Preserve DrugBank authority | safety test |
| V3-215 | P0 | Preserve unresolved identity clarification | tested |
| V3-216 | P1 | Redesign medicine detail row | readable |
| V3-217 | P1 | Redesign first-run medicine flow | focused steps |
| V3-218 | P0 | Block false all-clear when unavailable | tested |
| V3-219 | P1 | Web/Mobile visual parity | screenshots |

## 58.13 LifeMap / Visits / Family

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-230 | P1 | Rebuild LifeMap hub | journey-first |
| V3-231 | P0 | Preserve truth-state semantics | tested |
| V3-232 | P1 | Rebuild LifeMap detail timeline | current action first |
| V3-233 | P1 | Rebuild journey creation | focused steps |
| V3-234 | P0 | No unsupported persistence claims | API audit |
| V3-235 | P1 | Rebuild Visit prep | 5 steps |
| V3-236 | P0 | Preserve contextual Scribe consent | tested |
| V3-237 | P1 | Rebuild Family tabs | scope clear |
| V3-238 | P0 | Rebuild invitation review | scope/duration/revoke |
| V3-239 | P0 | Shared context banner | visible scope |

## 58.14 Chat / Evidence

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-250 | P0 | Rebuild Chat shell hierarchy | composer/answer first |
| V3-251 | P0 | Keep emergency content highest | safety |
| V3-252 | P1 | Build Personal answer detail preset | concise |
| V3-253 | P1 | Build Clinical answer detail preset | evidence-rich |
| V3-254 | P1 | Build Research detail preset | provenance-rich |
| V3-255 | P0 | Canonicalize source disclosure | inline/list agreement |
| V3-256 | P0 | Keep admin diagnostics lazy | bundle |
| V3-257 | P0 | Consumer DOM excludes internal diagnostics | privacy |
| V3-258 | P0 | No CoT/raw hidden reasoning | tested |
| V3-259 | P1 | Rebuild Evidence flow | question→confirm→run→results |
| V3-260 | P1 | Separate Source Hub browse/sync | clear roles |

## 58.15 Clinical

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-270 | P0 | Build professional Clinical home | no Personal fallback |
| V3-271 | P0 | Council top-level Web/Mobile | one nav action |
| V3-272 | P0 | Scribe top-level Web/Mobile | one nav action |
| V3-273 | P1 | Add real resume surface where backend supports | no fabrication |
| V3-274 | P0 | Rebuild Council wizard chrome | focused |
| V3-275 | P0 | Rebuild Council results hierarchy | red flags first |
| V3-276 | P0 | Preserve disagreement/uncertainty | visible |
| V3-277 | P0 | Rebuild Scribe consent | before capture |
| V3-278 | P0 | Rebuild capture state | clear recording |
| V3-279 | P0 | Rebuild transcript review | opaque reading surface |
| V3-280 | P0 | Rebuild SOAP review | explicit editing/review |
| V3-281 | P0 | Distinguish complete/finalized/signed/exported | tested |
| V3-282 | P0 | Preserve audit/addendum semantics | tested |

## 58.16 Research / Admin

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-290 | P1 | Build Research mode navigation | coherent |
| V3-291 | P1 | Add recent research only if real data exists | no fake history |
| V3-292 | P1 | Redesign Source Hub | browse/manage split |
| V3-293 | P1 | Redesign Admin Overview | real metrics only |
| V3-294 | P1 | Redesign Monitoring | unknown != healthy |
| V3-295 | P1 | Redesign Analytics surfaces | dense/data-first |
| V3-296 | P1 | Redesign Audit/Compliance touched surfaces | coherent |
| V3-297 | P1 | Keep complex admin controls desktop-only where appropriate | documented |

## 58.17 Accessibility / responsive

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-310 | P0 | Axe representative web routes | no serious/critical |
| V3-311 | P0 | Keyboard route matrix | pass |
| V3-312 | P0 | 320px reflow | no horizontal overflow |
| V3-313 | P0 | 200% zoom | usable |
| V3-314 | P0 | Flutter textScale matrix | no critical clipping |
| V3-315 | P0 | TalkBack/VoiceOver critical flows | pass |
| V3-316 | P1 | Forced colors/high contrast check | usable |
| V3-317 | P0 | Reduced motion | pass |
| V3-318 | P0 | Reduced transparency | pass |
| V3-319 | P0 | Touch target scan | pass |
| V3-320 | P1 | Vietnamese long-copy stress test | no truncation |

## 58.18 Performance / quality

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-330 | P0 | Web clean build budget | ≤ approved delta |
| V3-331 | P0 | Route chunk analysis | no accidental heavy common chunk |
| V3-332 | P1 | Lazy-load advanced diagnostics | verified |
| V3-333 | P1 | Avoid hidden mobile network fetch | verified |
| V3-334 | P1 | Glass rendering performance test | fallback works |
| V3-335 | P0 | Console/hydration error gate | zero |
| V3-336 | P0 | Flutter analyze | pass |
| V3-337 | P0 | Flutter unit/widget tests | pass |
| V3-338 | P0 | Web unit/type/lint/build | pass |

## 58.19 Legacy cleanup

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-350 | P1 | Inventory V2/V3 mobile imports | complete |
| V3-351 | P1 | Build rollback adapter | explicit |
| V3-352 | P2 | Remove V2 after parity gate | zero import |
| V3-353 | P2 | Remove V3 after parity gate | zero import |
| V3-354 | P2 | Remove stale mobile palette | zero import |
| V3-355 | P2 | Remove proven-dead web CSS | visual/build pass |
| V3-356 | P2 | Remove obsolete raw color aliases | token lint pass |
| V3-357 | P2 | Update architecture docs | current |
| V3-358 | P2 | Update feature flag matrix | supported-only |

## 58.20 Release

| ID | P | Task | Acceptance |
|---|---:|---|---|
| V3-370 | P0 | Personal Web E2E | pass |
| V3-371 | P0 | Personal Mobile E2E | pass |
| V3-372 | P0 | Doctor Web E2E | pass |
| V3-373 | P0 | Doctor Mobile E2E | pass |
| V3-374 | P0 | Research role E2E | pass |
| V3-375 | P0 | Admin role E2E | pass |
| V3-376 | P0 | Safety regression matrix | pass |
| V3-377 | P0 | Security/RBAC/CSRF/consent matrix | pass |
| V3-378 | P0 | Privacy/telemetry static review | pass |
| V3-379 | P0 | Visual review Light/Dark | approved |
| V3-380 | P0 | A11y release review | approved |
| V3-381 | P1 | Controlled rollout | metrics stable |
| V3-382 | P1 | Rollback drill | successful |
| V3-383 | P2 | Legacy deletion approval | explicit |

---

# 59. Required Acceptance Journeys

## Personal — First Use

```text
Login
→ Global first run
→ optional Personal setup
→ Today
→ Create journey OR Ask CLARA
```

No workspace terminology required.

## Personal — Returning

```text
Login
→ Today
→ next accepted task visible
→ open/complete
```

## Doctor

```text
Login
→ Clinical Overview
→ Council
```

or:

```text
Login
→ Clinical Overview
→ Scribe
→ Consent
→ Capture
→ Transcript review
→ SOAP review
→ Draft complete
```

No Personal PHR onboarding.

## Doctor entering Personal

```text
Clinical
→ Mode switch
→ Personal
→ optional Personal setup
→ Today
```

The UI must visibly indicate context changed.

## Researcher

```text
Login
→ Research
→ Ask/Evidence
→ inspect sources
```

## Shared resource

```text
Personal
→ Family/Shared
→ open bounded resource
→ explicit scope visible
```

No silent full-profile context.

---

# 60. Visual Acceptance Screens

Required screenshots for every release candidate:

## Web

Light + Dark:

- Login
- Personal Today first-time
- Personal Today active
- LifeMap
- Medicines
- PHR hub
- Chat answer
- Family
- Clinical Overview
- Council first-use
- Council result
- Scribe consent
- Scribe transcript
- Research Evidence
- Admin Overview

Viewports:

```text
1440×900
1280×800
tablet
390×844
```

## Mobile

Light + Dark:

- Global onboarding
- Personal Today
- Personal first-time
- Medicines
- Profile
- Chat
- Clinical Overview
- Council
- Scribe
- Research/Evidence

Devices:

```text
compact phone
large phone
tablet
```

---

# 61. Definition of Done

The redesign is not done when screenshots look new.

It is done when all of the following are true:

1. Web and Mobile use one canonical semantic token source.
2. Personal and professional users receive role-appropriate IA.
3. A clinician is not blocked by Personal PHR setup.
4. Council and Scribe are top-level Clinical tools.
5. Today shows next action before generic shortcuts.
6. Profile no longer embeds PHR as a fixed-height nested scroll.
7. Professional home never falls back implicitly to Personal Today.
8. Safety-critical content is visually explicit and opaque.
9. Glass is limited to chrome.
10. Light/Dark theme both meet accessibility requirements.
11. Vietnamese long-copy works across supported viewports.
12. No capability is lost through navigation simplification.
13. No UI state fabricates medical or operational data.
14. Route access remains server-authoritative.
15. No chain-of-thought or private implementation detail leaks to consumer UI.
16. Full regression and safety suites pass.
17. V2/V3 legacy mobile layers are removed or explicitly bounded behind an approved rollback adapter.
18. Architecture documentation describes the code that actually ships.

---

# 62. Non-Goals

This program does **not**:

- replace Next.js;
- replace Flutter;
- rewrite CLARA's API/ML architecture;
- invent a patient directory;
- invent a clinical queue;
- invent appointment management;
- merge medication records by display name;
- alter DrugBank/FIDES authority;
- weaken consent/RBAC;
- expose hidden reasoning;
- fabricate confidence;
- make every screen glass;
- add a new design framework without demonstrated need.

---

# 63. Final Product Shape

```text
                            CLARA
                              │
              ┌───────────────┴────────────────┐
              │                                │
        PERSONAL CARE                    PROFESSIONAL
              │                                │
       Hôm nay / Today                   Role overview
       LifeMap                           Ask CLARA
       Ask CLARA                         Council
       Medicines                         Scribe
       Health Profile                    Evidence
              │                                │
              └────────── ACCOUNT ─────────────┘
                         Privacy
                         Sharing
                         Preferences
                         Help
```

Research and Administration extend the professional model without polluting Personal care.

The redesign must make CLARA feel like **one premium healthcare product**, not a collection of modules sharing a logo.

---

# 64. Implementation Notes for Codex / Engineering Agents

When implementing this specification:

1. Read current code before editing.
2. Treat the current backend and safety contracts as authoritative.
3. Do not claim support for an API capability that does not exist.
4. Do not collapse safety warnings for visual cleanliness.
5. Prefer incremental adapters over big-bang rewrites.
6. Keep each milestone independently testable and revertible.
7. Every visual change must use generated semantic tokens.
8. New user-visible strings must enter typed VI/EN localization.
9. Add tests with every navigation/safety/state change.
10. Before deleting legacy code, prove no supported route/import/flag depends on it.
11. Do not use screenshots alone as evidence of authorization or clinical correctness.
12. Do not ship synthetic health/clinical/operational values to fill visual empty space.

---

# 65. Source-of-Truth Baseline References

This specification was prepared against:

```text
main@81c024d74ea9201b31e22b5c02b1b6f852c0ce9e

apps/web/styles/globals.css
apps/web/components/app-shell.tsx
apps/web/components/sidebar-nav.tsx
apps/web/components/navigation/*
apps/web/lib/navigation.access.ts
apps/web/lib/navigation.config.ts
apps/web/lib/navigation.workspaces.ts
apps/web/app/today/page.tsx
apps/web/app/dashboard/page.tsx

apps/mobile/lib/app.dart
apps/mobile/lib/core/feature_flags.dart
apps/mobile/lib/experience/unified/unified_root.dart
apps/mobile/lib/experience/unified/today_surface.dart
apps/mobile/lib/experience/unified/profile_hub.dart
apps/mobile/lib/experience/unified/onboarding_flow.dart
apps/mobile/lib/experience/redesign_shell.dart
apps/mobile/lib/theme/clara_theme.dart
apps/mobile/lib/theme/tokens.dart
apps/mobile/lib/theme/web_palette.dart
```

Re-audit these references against the latest commit before implementation begins if `main` changes materially.
