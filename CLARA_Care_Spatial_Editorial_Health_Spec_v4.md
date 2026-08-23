# CLARA Care — Spatial Editorial Health Experience Specification v4

> **Document type:** Product Experience Specification + Design Language + UI System + Interaction Architecture + Technical Design + Migration Plan + Detailed Implementation Backlog  
> **Codename:** **CLARA Spatial Editorial Health**  
> **Design direction:** **C — Spatial Apple-like + Editorial Futuristic Healthcare**  
> **Repository:** `Project-CLARA-HBT/CLARA-Care`  
> **Baseline:** `main@81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`  
> **Targets:** Web + Flutter Mobile  
> **Primary locale:** Vietnamese, full English parity  
> **Status:** New master redesign specification  
> **Supersedes:** v3 wherever this document conflicts.

---

# 0. Executive Mandate

CLARA Care must stop looking and behaving like a collection of healthcare modules placed inside a generic SaaS shell. The next generation must become a **spatial, editorial, role-adaptive health environment** in which content and the current task dominate, while navigation and system chrome appear only when useful.

The design language is **CLARA Spatial Editorial Health**. It combines spatial navigation, editorial healthcare presentation, clinical trust, role-adaptive behavior, and cross-device continuity.

This is not a sidebar reskin, glassmorphism theme, iOS clone, Material 3 reskin, bento dashboard, or dark-mode AI dashboard. It is a product interaction-model redesign.

## 0.1 North-star statement

> **CLARA should expose the user's current job, context, decision, and next safe action — not CLARA's internal module graph.**

## 0.2 Core transformation

Move from:

```text
Permanent sidebar
→ module
→ card grid
→ secondary action
```

To:

```text
Context
→ current task
→ primary content
→ next action
→ evidence/provenance/details
```

---

# 1. Product Identity

CLARA should feel calm, intelligent, premium, human, precise, editorial, spatial, clinically trustworthy, responsive, and deeply considered.

It must not feel corporate, hospital-bureaucratic, cyberpunk, neon, glow-heavy, dashboard-heavy, or like a developer console with healthcare labels.

## 1.1 Visual keywords

Primary: calm, clear, spatial, editorial, light, layered, human, clinical, precise, responsive.

Avoid: neon, holographic, cyberpunk, permanent-left-sidebar, grid-of-cards, glass-everywhere, rainbow-AI, over-rounded-everything.

---

# 2. Design Language Architecture

A CLARA screen is composed from five layers:

```text
L4 TRANSIENT      command palette / sheet / modal / contextual menu
L3 ADAPTIVE       floating dock / contextual island / context bar
L2 TASK OBJECTS   current task / case / journey / recommendation / transcript
L1 EDITORIAL      content / explanation / timeline / evidence / record
L0 AMBIENT        quiet canvas / subtle mode atmosphere
```

Content must visually outrank navigation. Navigation must visually outrank system implementation details.

---

# 3. Fundamental Navigation Decision

## 3.1 Remove permanent global left sidebar

The target Personal, Clinical, and Research experiences must not use a permanently visible global left sidebar as their default shell.

A rail/sidebar may still appear as:
- local navigation inside a complex workspace;
- dense Admin navigation;
- accessibility fallback;
- temporary migration shell;
- large-screen secondary section index.

It must not remain the universal product identity.

## 3.2 New global navigation model

CLARA uses four mechanisms:

1. Global Context Bar
2. Floating Primary Dock
3. Contextual Local Navigation
4. Command Palette

No one mechanism carries the entire information architecture.

---

# 4. Global Context Bar

The Context Bar owns only:
- CLARA identity;
- current experience mode;
- active contextual entity when relevant;
- global search/command trigger;
- meaningful notifications;
- account/avatar.

It does not contain the full navigation tree.

Personal example:

```text
CLARA        Cá nhân ▾                         Search       Profile
```

Clinical:

```text
CLARA        Lâm sàng ▾     Case: —           Search       Dr. A
```

Research:

```text
CLARA        Research ▾      Scope: —          Search       Profile
```

Admin:

```text
CLARA        Admin ▾         Environment       Search       Profile
```

Desktop target height: 52–60px. Mobile: 44–52dp. It may gain opacity when content scrolls under it and may collapse during immersive workflows.

---

# 5. Floating Primary Dock

The Floating Dock is the primary visual signature of the new shell. It is centered or contextually positioned, role-adaptive, compact, content-aware, and capable of safe morphing.

## 5.1 Personal

```text
Hôm nay   LifeMap      ◉ CLARA      Thuốc   Hồ sơ
```

## 5.2 Clinical

```text
Tổng quan   Hội chẩn   ◉ CLARA   Ghi chép   Thêm
```

`Thêm`: Evidence, Sources if authorized, Personal, Help, Account.

## 5.3 Research

```text
Nghiên cứu   Bằng chứng   ◉ CLARA   Nguồn   Thêm
```

## 5.4 Administration

Admin may use a compact command bar plus contextual rail where data density warrants it. Admin is not forced into floating-dock geometry if it reduces operational clarity.

---

# 6. Dock Morphing

The dock has named presentation states:

```text
EXPANDED
COMPACT
ORB_ONLY
CONTEXTUAL
HIDDEN_WITH_ESCAPE
```

Examples:

Resting:

```text
Today LifeMap ◉ Medicines Profile
```

Deep scroll:

```text
      ◉
```

Chat:

```text
◉ Hỏi CLARA
```

Scribe recording:

```text
● Recording   12:42
```

Council focus:

```text
‹ Lâm sàng                         Help
```

Morphing is allowed only if destinations remain discoverable, focus order remains stable, screen-reader semantics remain explicit, reduced-motion fallback remains equivalent, and no warning is obscured.

---

# 7. Contextual Local Navigation

Local navigation is allowed only when a feature has genuine internal complexity, e.g. PHR sections, Council sections, Scribe review, Evidence filters, Research source inspection, Admin operations.

Allowed forms:
- local rail;
- tabs;
- segmented control;
- section index;
- bottom/side sheet.

Global navigation and local navigation must remain visually distinct.

---

# 8. Command Palette

Desktop shortcut: `Ctrl+K` / `Cmd+K`.

Palette examples:

```text
Bạn muốn làm gì?

Hỏi CLARA
Kiểm tra tương tác thuốc
Mở LifeMap
Chuẩn bị buổi khám
Mở hồ sơ sức khỏe

Clinical
Bắt đầu Hội chẩn
Bắt đầu Ghi chép
Mở Bằng chứng

Recent
...
```

It must never bypass authorization, expose unauthorized actions, place health content in telemetry, or perform destructive actions without confirmation.

---

# 9. CLARA Orb

The CLARA Orb is the persistent product interaction object replacing generic chat-bubble branding for the main assistant action.

States:
- idle;
- hover/focus;
- listening;
- processing;
- ready;
- attention;
- error.

The Orb communicates system interaction only. It must never communicate medical severity, diagnostic confidence, medication safety, or clinical urgency.

Morph path:

```text
Orb
→ compact Ask bar
→ composer
→ full Chat surface
```

Reduced motion converts morphs into direct state swaps.

---

# 10. Canvas-first Layout

Major screens start with the content canvas, not a navigation container. Content determines layout; shell adapts around it.

Preferred composition:

```text
Context / date / mode
Large meaningful heading
Primary object or answer
Supporting context
Flowing list / timeline
Secondary actions
Sources / provenance
Technical detail
```

Avoid card-grid-first composition.

---

# 11. Editorial System

CLARA uses editorial hierarchy rather than dashboard hierarchy.

Order:
1. kicker/context;
2. meaningful headline;
3. immediate answer/next action;
4. supporting context;
5. secondary detail;
6. sources/provenance;
7. technical detail.

Before creating a card ask: **does this content require an independent semantic or interactive boundary?** If not, use spacing, heading, separator, indentation, or background grouping.

---

# 12. Visual Direction

The product becomes light-first with full dark parity. Premium appearance must not depend on dark mode.

## 12.1 Clara Azure

```text
50  #EFF7FF
100 #DCEEFF
200 #B9DCFF
300 #86C4FF
400 #4BA7FF
500 #1A86F5
600 #0B6FD8
700 #095BB4
800 #0B4A91
900 #103F76
950 #0B274D
```

## 12.2 Iris — AI/Research accent

```text
50  #F5F3FF
100 #EDE9FE
200 #DDD6FE
300 #C4B5FD
400 #A78BFA
500 #8B7CF6
600 #7566E8
700 #6354C9
800 #5245A8
900 #443B86
```

Iris must not encode clinical severity or confidence.

## 12.3 Mint — supportive/Clinical orientation

```text
50  #ECFDF8
100 #D1FAEE
200 #A7F3DF
300 #6EE7CF
400 #3AD2B6
500 #14A88D
600 #0F8A75
700 #0F6F61
800 #10594F
900 #104A43
```

---

# 13. Neutral Palette

## 13.1 Light

```text
canvas           #F6F8FB
canvas-soft      #F1F4F8
surface          #FFFFFF
surface-soft     #FBFCFE
surface-muted    #F3F6FA
surface-strong   #EBF0F6
border-subtle    #E3E8EF
border-default   #D5DDE7
border-strong    #AEB9C8
text-primary     #162033
text-secondary   #48566A
text-tertiary    #6D7A8E
text-disabled    #9AA5B4
```

## 13.2 Dark

```text
canvas           #0B111A
canvas-soft      #0E1520
surface          #111A26
surface-soft     #15202D
surface-muted    #1B2735
surface-strong   #223143
border-subtle    #253447
border-default   #33455B
border-strong    #566B83
text-primary     #F2F6FB
text-secondary   #C7D1DE
text-tertiary    #93A2B6
text-disabled    #68788D
```

Dark is blue-neutral, not charcoal-brown, pure black, or neon cyan.

---

# 14. Semantic Status

Success Light: text `#137A57`, bg `#EAF8F2`, border `#BCE9D7`.  
Success Dark: text `#75E0B7`, bg `#102D25`, border `#245B49`.

Warning Light: text `#8A5A00`, bg `#FFF7E2`, border `#F4D58D`.  
Warning Dark: text `#FFD37A`, bg `#33260D`, border `#6D501B`.

Danger Light: text `#B42332`, bg `#FFF0F1`, border `#F4B9BF`.  
Danger Dark: text `#FF9CA7`, bg `#35141A`, border `#73303A`.

Unknown/unavailable/not-loaded uses neutral/slate and must never look healthy.

Role accents are orientation only: Personal Azure, Clinical Mint, Research Iris, Admin Slate/Indigo.

---

# 15. Ambient Atmosphere

Canvas may have extremely subtle mode atmosphere: Azure Personal, Mint/Blue Clinical, Iris/Blue Research, Slate Admin. Opacity generally ≤10–12%. No visible wallpaper, neon glow, or continuous animated gradient.

---

# 16. Glass Material

Glass represents transient system chrome, not medical truth.

Allowed: Floating Dock, Context Bar, Command Palette, sheet, contextual island, compact floating toolbar, non-critical popover.

Disallowed: medication verdict, emergency warning, Council recommendation, evidence body, transcript, SOAP, consent/legal, PHR form, tables, long reading surfaces.

Light glass: rgba(255,255,255,.70/.84), subtle cool stroke, blur 18–28px, saturation ~140%.  
Dark glass: rgba(17,26,38,.68/.84), cool stroke, blur 20–30px, saturation ~135%.

Reduced transparency or weak device → identical geometry rendered with opaque `surface-soft`.

---

# 17. Typography

Primary: `Be Vietnam Pro Variable`.

Fallback: `Segoe UI Variable`, `Segoe UI`, system-ui, -apple-system, sans-serif.

Desktop scale:

```text
Display XL 52/60 650
Display    44/52 650
H1         34/42 650
H2         28/36 650
H3         22/30 620
Title L    20/28 600
Title      18/26 600
Body L     17/29 430
Body       16/26 430
Body S     14/22 430
Label      13/18 600
Caption    12/18 500
```

Important mobile body text should generally be 16sp+. Long reading width: 620–760px; clinical reading may extend 700–900px; dense data can exceed it.

Avoid 11px UI text, excessive uppercase, excessive semibold, title-per-card, or giant clinical hero typography.

---

# 18. Spacing / Radius / Shape

Canonical spacing: `4 8 12 16 20 24 32 40 48 64 80 96`.

Radius: `8 12 16 20 28 999`.

Expressive non-standard shapes may occupy at most ~10–15% of visible surfaces. Avoid blob UI.

Depth uses tonal separation first, border second, shadow only for floating/transient surfaces.

---

# 19. Motion

Tokens:

```text
instant   0–80ms
fast      120–160ms
standard  180–240ms
emphasis  280–360ms
```

Motion is soft, direct, non-bouncy in clinical contexts. Use for dock state changes, Orb→composer, sheets, task completion, source expansion, context switch. Do not animate severity, safety verdicts, or errors playfully.

---

# 20. Responsive Shell Modes

Named shell states:

```text
EXPLORE
FOCUS
IMMERSIVE
READ
DENSE
```

EXPLORE: Today, LifeMap hub, Medicines, Profile, Clinical Overview. Full context bar + dock.

FOCUS: PHR section, Visit Prep, Council setup, source inspection. Compact chrome + local navigation.

IMMERSIVE: Scribe capture, certain Chat flows. Minimal chrome, explicit escape.

READ: Evidence, long Chat answer, Council result, transcript/SOAP. Reading width and provenance optimized.

DENSE: Admin and data-heavy professional surfaces. Local rail and compact rows allowed.

---

# 21. Product Model

```text
ACCOUNT
├── ROLE / CAPABILITIES
├── EXPERIENCE MODE
│   ├── Personal
│   ├── Clinical
│   ├── Research
│   └── Administration
├── DATA CONTEXT
└── CURRENT TASK
```

Role defines available modes; mode defines shell/navigation; data context defines scope; task defines hierarchy. Server authorization always wins.

---

# 22. Mode Defaults

```text
normal     → Personal
doctor     → Clinical
researcher → Research
admin      → Administration
```

Professional users may explicitly switch to Personal if authorized. Single-mode Personal users never see unnecessary workspace terminology.

---

# 23. Onboarding

Global first run for everyone:
1. Welcome.
2. Language.
3. Required transparency/legal.
4. Core preferences.
5. Enter role-appropriate mode.

No health questionnaire.

Personal setup only when entering Personal health capabilities: goal, optional basic profile, optional personalization consent, review, Today.

Doctor orientation: Ask evidence questions, Council, Scribe, uncertainty/sources. No personal height, weight, blood type.

Tool-specific consent appears at the point of use.

---

# 24. Personal Today

Active composition:

```text
Hôm nay, [date]

Greeting / one-sentence state

PRIMARY NEXT TASK OBJECT

Completed count / pending confirmation

Recent journey timeline

Ask CLARA · Check medicine · Prepare visit
```

Required ordering:

```text
next accepted task
→ upcoming
→ pending confirmation
→ journey context
→ secondary shortcuts
→ progress/statistics
```

First-time Today has one primary CTA: start a health journey. Ask CLARA is secondary. No zero-stat dashboard.

---

# 25. LifeMap

LifeMap becomes a narrative health journey, not project management.

Hub: active journey, current focus, next step, timeline preview, other journeys, archived.

Detail order: current state → next accepted action → timeline → questions/evidence → updates/revisions → advanced provenance.

Truth-state semantics must remain unchanged.

---

# 26. Medicines

One hub, three explicit domains:

```text
Đang dùng
Cần xác nhận
Tủ thuốc
Kiểm tra an toàn
```

Cabinet copy must state that possession does not imply current use.

Safety result order: authority availability → medicines checked → highest-priority issue → next action → details → sources.

Never show a green all-clear when DrugBank/authority is unavailable or medicine identity is unresolved.

---

# 27. Profile and PHR

Profile becomes an identity/settings/data hub:
- Health Record;
- Family & Sharing;
- Connected Health;
- Privacy & Consent;
- Data Rights;
- Preferences;
- Help.

Council and Scribe do not live here.

PHR opens full-page/full-screen. Desktop may use a local section rail; mobile uses section list → focused editor. Remove fixed-height nested PHR scroll.

PHR uses opaque surfaces and preserves provenance, validation, conflict behavior, and no-silent-overwrite semantics.

---

# 28. Family / Sharing

Hub groups: Tôi chia sẻ, Được chia sẻ với tôi, Nhật ký truy cập.

Every share exposes recipient, scope, allowed actions, purpose, duration, revocation. Shared context always shows who shared it and the current scope. No token in telemetry.

---

# 29. Visit Preparation

Flow:
1. Visit info.
2. Concerns.
3. Medicines/documents.
4. Questions.
5. Review.

Scribe recording controls only appear when contextually supported and consent-safe.

---

# 30. Chat

Chat uses editorial answer hierarchy:
1. Emergency/critical warning.
2. Direct answer.
3. What to do next.
4. What remains uncertain.
5. Explanation.
6. Sources.
7. Role-gated advanced detail.

Desktop uses centered reading column with optional source inspector. Conversation history may open contextually; it is not required as a permanent left sidebar in focused mode.

Personal uses plain language. Clinical includes applicability/evidence/uncertainty. Research adds provenance/source controls. Consumer DOM must not contain hidden diagnostics, prompts, chain-of-thought, or provider secrets.

---

# 31. Clinical Overview

Professional home is a launchpad, not a KPI dashboard.

```text
Greeting

Continue
[real resumable item only if supported]

Start
Council       Scribe

Ask CLARA
[professional composer]

Review
[real alerts only]
```

If no work exists, say so honestly. Never fallback to Personal `/today` implicitly.

---

# 32. Council

Council uses FOCUS shell.

Flow:

```text
Case → Question → Context → Review → Run → Result
```

Result uses READ shell and order:
1. red flags/escalation;
2. recommendation;
3. agreement/disagreement;
4. uncertainty;
5. evidence;
6. clinician action;
7. technical detail.

Pipeline visualization remains secondary.

---

# 33. Scribe

Capture uses IMMERSIVE shell.

```text
Back
elapsed time
Orb / recording indicator
waveform
Pause / Stop
Consent status
Microphone status
```

Then morphs into Transcript → SOAP → Review.

Distinct states: Recording, Transcript ready, Draft, Reviewed, Finalized legacy, Signed, Exported, Amended. Never imply signed when only finalized.

Transcript and SOAP use opaque, high-contrast surfaces.

---

# 34. Evidence / Research

Evidence presentation:

```text
Question
Scope
Synthesis
Key evidence
Applicability
Uncertainty
Sources
```

Technical search detail is progressive disclosure. Source Hub separates Browse from Manage. Research may use more citation density and provenance but remains content-first.

---

# 35. Admin

Admin intentionally supports dense surfaces: tables, filters, local rail, compact charts, status rows, command bar. Avoid giant card grids. Unknown must not appear healthy. Mobile Admin may remain intentionally limited/read-only for complex operations.

---

# 36. Core Component System

Required primitives:

```text
Button
IconButton
Link
TextField
TextArea
Search
Select
Checkbox
Radio
Switch
SegmentedControl
Tabs
Chip
Status
Badge
Avatar
Tooltip
Popover
Menu
Surface
HeroObject
ActionObject
ListRow
DataRow
Alert
Toast
Snackbar
Modal
Sheet
SideSheet
ConfirmDialog
Stepper
Timeline
SourceDisclosure
CitationAnchor
ContextBar
FloatingDock
Orb
CommandPalette
ModeSwitcher
ProfileMenu
LocalRail
SectionIndex
PageHeading
EditorialSection
EmptyState
Skeleton
InlineError
```

All support Light/Dark, relevant interactive states, VI/EN, large text, keyboard/screen reader semantics.

HeroObject is reserved for dominant current task/continuation/first-use CTA. Repeated entities use ListRow rather than isolated cards.

---

# 37. Accessibility

Target WCAG 2.2 AA.

Required: keyboard navigation, visible focus, focus trap/restoration, 320px reflow, 200% zoom, Flutter dynamic type, TalkBack/VoiceOver, reduced motion, reduced transparency, forced/high contrast where applicable, no color-only state, correct errors/live regions, and touch targets.

Targets: Web 44×44px where practical; Mobile 48×48dp.

Focus ring must remain visible on light, dark, glass, and opaque surfaces.

---

# 38. Canonical Design Token Architecture

Create:

```text
packages/design-tokens/
  clara.tokens.json
  schema.json
  generate/
  README.md
```

Generate:

```text
apps/web/styles/generated/clara.tokens.css
apps/mobile/lib/theme/generated/clara_tokens.g.dart
```

Categories: color, surface, text, action, status, spacing, radius, type, motion, blur, shadow, size, density, breakpoint.

Components consume semantic tokens, not raw palette values. Replace current manually mirrored Web/Mobile palettes.

---

# 39. Web Architecture

Target:

```text
RootLayout
└── AppProviders
    ├── SessionProvider
    ├── ProfileProvider
    ├── PreferenceProvider
    ├── ExperienceProvider
    ├── CommandProvider
    └── AdaptiveShell
        ├── ContextBar
        ├── ShellContent
        ├── FloatingDock
        └── TransientLayerHost
```

`AdaptiveShellState` contains mode, shellMode, activeDestination, optional contextual entity.

Route registry must explicitly define access, canonicalMode, shellMode, destination, aliases. Authorization must remain independent from navigation presentation.

Migration: current AppShell → provider extraction → AdaptiveShell facade → route-by-route migration → old shell removal. No big-bang rewrite.

---

# 40. Mobile Architecture

Introduce:

```dart
enum ExperienceMode { personal, clinical, research, administration }
enum ShellMode { explore, focus, immersive, read, dense }
enum ClaraDestination {
  today, lifeMap, askClara, medicines, profile,
  clinicalOverview, council, scribe, evidence,
  researchHome, sourceHub, adminOverview
}
```

`ExperienceConfig` defines mode, dock destinations, primary action, More destinations.

Target root:

```text
AdaptiveClaraShell
├── ContextBar
├── DestinationHost
├── MorphingDock
├── ClaraOrb
└── OverlayHost
```

Current Legacy/V2/V3/Unified → intermediate UnifiedSpatial + LegacyRollbackAdapter → final UnifiedSpatial.

---

# 41. State Ownership

Session belongs to SessionProvider/store. Profile context belongs to ProfileProvider. Mode belongs to ExperienceProvider/store. Local workflow state belongs to each feature. Shell owns only presentation state. Do not create a new monolithic shell state object.

---

# 42. Safety / Privacy Invariants

Must preserve server RBAC, consent, CSRF, profile isolation, sharing boundaries, DrugBank authority and fail-closed behavior, FIDES, emergency fast path, audit, no-autonomous-confirm rules, provenance, Scribe state integrity, no chain-of-thought exposure.

Analytics must not include prompts, transcript, SOAP, diagnosis, medication names, measurements, document body, sharing token, or raw health data.

Safe events may include mode_entered, dock_destination_opened, command_palette_opened, orb_opened, today_next_task_opened, council_started, scribe_started, evidence_opened, mode_switched.

---

# 43. Performance Requirements

No duplicate auth/profile fetches. No hidden heavyweight panels. Lazy source inspector and admin diagnostics. Route-level splitting. Lightweight Orb animation. Glass fallback. Inactive mobile destination must not fetch unnecessarily. No second icon system without approval. Common bundle increase should remain within an approved small delta.

---

# 44. Implementation Plan

## Phase 0 — Baseline
Route map, role/capability matrix, screenshots, a11y, performance, safety/security test freeze.

## Phase 1 — Canonical tokens
Token schema, CSS/Dart generation, contrast/parity tests.

## Phase 2 — Spatial primitives
ContextBar, FloatingDock, Orb, CommandPalette, HeroObject, ActionObject, LocalRail, shell states.

## Phase 3 — Role-adaptive architecture
Mode model, route/destination registries, ExperienceProvider, ExperienceConfig.

## Phase 4 — Onboarding split
Global, Personal, Clinical, Research/Admin orientations.

## Phase 5 — Shell migration
AdaptiveShell Web + AdaptiveClaraShell Mobile.

## Phase 6 — Personal
Today, LifeMap, Medicines, Profile, PHR, Visits, Family.

## Phase 7 — Chat/Evidence
Editorial Chat, source inspector, Evidence.

## Phase 8 — Clinical
Clinical Overview, Council, Scribe.

## Phase 9 — Research/Admin
Professional/dense surfaces.

## Phase 10 — Legacy cleanup
Old sidebar, stale palettes, V2/V3 roots, dead CSS, obsolete flags.

## Phase 11 — Release validation
Functional, E2E, visual, a11y, performance, security, privacy, safety, rollback.

---

# Detailed Backlog — Baseline & audit

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-001 | P0 | Freeze Web route inventory | 100% routes classified |
| SEH-002 | P0 | Freeze server role/capability matrix | Reviewed against backend |
| SEH-003 | P0 | Capture Personal visual baseline | All primary routes |
| SEH-004 | P0 | Capture Clinical visual baseline | All primary routes |
| SEH-005 | P0 | Capture Research visual baseline | All primary routes |
| SEH-006 | P0 | Capture Admin visual baseline | All primary routes |
| SEH-007 | P0 | Capture phone/tablet baseline | Light/Dark |
| SEH-008 | P0 | Record Web bundle baseline | Reproducible |
| SEH-009 | P0 | Record Flutter performance baseline | Reproducible |
| SEH-010 | P0 | Freeze safety suite | Pass before redesign |
| SEH-011 | P0 | Freeze auth/RBAC/consent suite | Pass before redesign |
| SEH-012 | P1 | Inventory permanent sidebar dependencies | Complete dependency graph |

# Detailed Backlog — Tokens

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-020 | P0 | Create token package/schema | Schema validates |
| SEH-021 | P0 | Encode Azure palette | Generated |
| SEH-022 | P0 | Encode Iris palette | Generated |
| SEH-023 | P0 | Encode Mint palette | Generated |
| SEH-024 | P0 | Encode Light neutral system | Generated |
| SEH-025 | P0 | Encode Dark neutral system | Generated |
| SEH-026 | P0 | Encode semantic statuses | AA contrast |
| SEH-027 | P0 | Encode glass tokens | Light/Dark/fallback |
| SEH-028 | P0 | Encode type/spacing/radius/motion | Generated |
| SEH-029 | P0 | Generate Web CSS tokens | Build integrated |
| SEH-030 | P0 | Generate Flutter Dart tokens | Analyze pass |
| SEH-031 | P0 | Add token hash/version | Traceable |
| SEH-032 | P0 | Add contrast test matrix | WCAG AA |
| SEH-033 | P0 | Add Web/Mobile parity tests | Exact semantic parity |
| SEH-034 | P1 | Add raw-color lint | New violations blocked |
| SEH-035 | P1 | Map legacy vars to compatibility aliases | No big-bang break |
| SEH-036 | P1 | Deprecate stale mobile WebPalette | Zero active Unified imports |

# Detailed Backlog — Spatial primitives

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-050 | P0 | Build ContextBar Web | Responsive/a11y |
| SEH-051 | P0 | Build ContextBar Flutter | Responsive/a11y |
| SEH-052 | P0 | Build FloatingDock Web | Keyboard/touch |
| SEH-053 | P0 | Build MorphingDock Flutter | Touch/a11y |
| SEH-054 | P0 | Build CLARA Orb | All states |
| SEH-055 | P0 | Build Orb reduced-motion path | Equivalent state |
| SEH-056 | P0 | Build Orb semantics | Screen-reader pass |
| SEH-057 | P1 | Implement dock collapse/expand | Discoverable |
| SEH-058 | P1 | Expand dock on keyboard focus | Pass |
| SEH-059 | P0 | Create typed shell modes | Exhaustive |
| SEH-060 | P1 | Build LocalRail | Scoped only |
| SEH-061 | P1 | Build ContextIsland | Reusable |
| SEH-062 | P1 | Build CommandPalette Web | Keyboard complete |
| SEH-063 | P1 | Build Mobile command trigger | Accessible |
| SEH-064 | P1 | Build ProfileMenu | Single global trigger |
| SEH-065 | P1 | Build ModeSwitcher | Capability filtered |
| SEH-066 | P0 | Implement opaque glass fallback | Same geometry |
| SEH-067 | P0 | Validate focus on glass | Visible |
| SEH-068 | P1 | Dock collision/safe-area handling | No overlap |
| SEH-069 | P1 | Dock scroll heuristics | No accidental hiding |

# Detailed Backlog — Editorial components

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-080 | P0 | Build PageHeading | VI/EN |
| SEH-081 | P0 | Build EditorialSection | Responsive |
| SEH-082 | P0 | Build HeroObject | All themes |
| SEH-083 | P0 | Build ActionObject | All themes |
| SEH-084 | P0 | Build ListRow | Density variants |
| SEH-085 | P0 | Build Status | No color-only |
| SEH-086 | P0 | Rebuild Alert | Semantic |
| SEH-087 | P0 | Rebuild Button | All states |
| SEH-088 | P0 | Rebuild Field/TextArea | Errors/a11y |
| SEH-089 | P0 | Rebuild Sheet | Trap/restore |
| SEH-090 | P0 | Rebuild Modal | Trap/restore |
| SEH-091 | P1 | Build SectionIndex | Readable |
| SEH-092 | P1 | Build Timeline | Reusable |
| SEH-093 | P1 | Build SourceDisclosure | Citation parity |
| SEH-094 | P1 | Build CitationAnchor | Keyboard |
| SEH-095 | P1 | Build EmptyState family | State-specific |
| SEH-096 | P1 | Build Skeleton family | Stable layout |
| SEH-097 | P1 | Build Stepper | Desktop/mobile |
| SEH-098 | P1 | Build SegmentedControl | Keyboard |
| SEH-099 | P1 | Build contextual toolbar | FOCUS shell |

# Detailed Backlog — Web architecture

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-110 | P0 | Extract SessionProvider | Single auth source |
| SEH-111 | P0 | Extract ProfileProvider | Single context source |
| SEH-112 | P1 | Extract PreferenceProvider | No health data |
| SEH-113 | P0 | Build ExperienceProvider | Typed |
| SEH-114 | P1 | Build CommandProvider | No PII persistence |
| SEH-115 | P0 | Build exhaustive route registry | Complete |
| SEH-116 | P0 | Build destination registry | Complete |
| SEH-117 | P0 | Assign shell mode per route | Tests |
| SEH-118 | P0 | Keep access independent from menu | Architecture test |
| SEH-119 | P0 | Derive mode from deep link | Tests |
| SEH-120 | P0 | Invalid mode safe fallback | Tests |
| SEH-121 | P1 | Build AdaptiveShell facade | Backward-compatible |
| SEH-122 | P1 | Migrate routes off global sidebar | No regression |
| SEH-123 | P1 | Remove blind workspace cycling | Deterministic picker |
| SEH-124 | P1 | Stop pathname auth refetch | Network test |
| SEH-125 | P1 | Preserve compatibility deep links | E2E |

# Detailed Backlog — Mobile architecture

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-140 | P0 | Add ExperienceMode | Typed |
| SEH-141 | P0 | Add ShellMode | Typed |
| SEH-142 | P0 | Add ClaraDestination | Typed |
| SEH-143 | P0 | Add ExperienceConfig | Role tests |
| SEH-144 | P0 | Centralize destination factory | Single owner |
| SEH-145 | P0 | Build UnifiedSpatial root | Normal role pass |
| SEH-146 | P0 | Build Clinical config | Doctor pass |
| SEH-147 | P0 | Build Research config | Researcher pass |
| SEH-148 | P1 | Build bounded Admin config | Documented |
| SEH-149 | P0 | Remove Council from ProfileHub | Top-level Clinical |
| SEH-150 | P0 | Remove Scribe from ProfileHub | Top-level Clinical |
| SEH-151 | P0 | Add explicit Personal switch | Professional pass |
| SEH-152 | P1 | Add shell-mode state | Stable |
| SEH-153 | P1 | Add deep-link mode derivation | Tests |
| SEH-154 | P1 | Stop inactive destination fetch | Network test |
| SEH-155 | P1 | Build tablet spatial rail | Responsive |
| SEH-156 | P0 | Safe-area validation | No overlap |
| SEH-157 | P0 | Dynamic text nav tests | No clipping |

# Detailed Backlog — Onboarding

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-170 | P0 | Define global onboarding contract | No personal health data |
| SEH-171 | P0 | Implement Web global onboarding | Pass |
| SEH-172 | P0 | Implement Mobile global onboarding | Pass |
| SEH-173 | P0 | Split Personal setup | Personal-only |
| SEH-174 | P0 | Build doctor orientation | No PHR questionnaire |
| SEH-175 | P1 | Build researcher orientation | Role-specific |
| SEH-176 | P1 | Build admin orientation | Role-specific |
| SEH-177 | P0 | Unblock Clinical from Personal setup | E2E |
| SEH-178 | P0 | Unblock Research from Personal setup | E2E |
| SEH-179 | P0 | Unblock Admin from Personal setup | E2E |
| SEH-180 | P0 | Preserve ConsentGate ordering | Safety pass |
| SEH-181 | P1 | Implement skip/resume | Durable |
| SEH-182 | P1 | VI/EN terminology parity | CI |

# Detailed Backlog — Personal shell & Today

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-200 | P0 | Implement Personal dock Web | Five destinations |
| SEH-201 | P0 | Implement Personal dock Mobile | Five destinations |
| SEH-202 | P1 | Add dock compact-on-scroll | Reversible |
| SEH-203 | P1 | Add Orb→composer morph | Reduced-motion parity |
| SEH-204 | P1 | Remove permanent Personal sidebar | Migrated routes |
| SEH-205 | P1 | Build Personal Context Bar | Minimal |
| SEH-206 | P1 | Consolidate global settings into profile menu | Single owner |
| SEH-220 | P0 | Recompose Today editorial canvas | Approved visual |
| SEH-221 | P0 | Place next accepted task first | Above fold |
| SEH-222 | P0 | Build HeroObject for next task | Real data |
| SEH-223 | P0 | Move stats after task | Hierarchy pass |
| SEH-224 | P1 | Replace quick-action grid | Compact utilities |
| SEH-225 | P0 | Build first-time state | One primary CTA |
| SEH-226 | P0 | Build caught-up state | Truthful |
| SEH-227 | P0 | Build completed state | Truthful |
| SEH-228 | P0 | Preserve pending confirmation | Safety |
| SEH-229 | P0 | Preserve offline freshness | Safety |
| SEH-230 | P0 | Preserve offline write block | Safety |
| SEH-231 | P1 | Add real LifeMap timeline preview | No synthetic data |
| SEH-232 | P1 | Align Web/Mobile Today hierarchy | Parity |

# Detailed Backlog — LifeMap

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-240 | P1 | Replace card grid with journey composition | Editorial |
| SEH-241 | P0 | Preserve truth states | Tests |
| SEH-242 | P1 | Build active journey HeroObject | Next action |
| SEH-243 | P1 | Build journey timeline | Real events |
| SEH-244 | P1 | Build journey READ layout | Readable |
| SEH-245 | P1 | Rebuild journey creation flow | Focused |
| SEH-246 | P0 | Preserve explicit review before durable writes | Contract |
| SEH-247 | P1 | Add provenance disclosure | Progressive |

# Detailed Backlog — Medicines

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-260 | P0 | Recompose Medicines hub | Three domains explicit |
| SEH-261 | P0 | Preserve course/cabinet distinction | Visible |
| SEH-262 | P0 | One canonical Add action | Per viewport |
| SEH-263 | P0 | Clarify Cabinet copy | No usage implication |
| SEH-264 | P0 | Rebuild interaction safety result | Fail closed |
| SEH-265 | P0 | Preserve DrugBank authority | Safety tests |
| SEH-266 | P0 | Preserve unresolved identity clarification | Tests |
| SEH-267 | P0 | Build authority unavailable state | Never safe-like |
| SEH-268 | P1 | Convert repeated medicine cards to ListRow | Cleaner |
| SEH-269 | P1 | Build medicine source disclosure | Readable |
| SEH-270 | P1 | Web/Mobile visual parity | Screenshots |

# Detailed Backlog — Profile / PHR / family

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-280 | P0 | Remove fixed-height PHR embedding | No nested scroll |
| SEH-281 | P0 | Recompose Profile taxonomy | Correct groups |
| SEH-282 | P0 | Build PHR summary | Opens full PHR |
| SEH-283 | P0 | Build PHR hub | Focused |
| SEH-284 | P0 | Build local PHR rail desktop | Scoped |
| SEH-285 | P0 | Build full-page PHR mobile sections | No nested shell |
| SEH-286 | P0 | Preserve provenance | Visible |
| SEH-287 | P0 | Preserve conflict behavior | Explicit |
| SEH-288 | P1 | Rebuild measurements | Readable |
| SEH-289 | P1 | Rebuild documents | Readable |
| SEH-290 | P1 | Completion summary without health score | Truthful |
| SEH-300 | P1 | Recompose Family hub | Three groups |
| SEH-301 | P0 | Show sharing scope | Explicit |
| SEH-302 | P0 | Show expiry | Explicit |
| SEH-303 | P0 | Show revoke path | Accessible |
| SEH-304 | P0 | Shared context banner | Always visible |
| SEH-305 | P1 | Rebuild Visit Prep | Five-step |
| SEH-306 | P0 | Preserve contextual Scribe consent | Safety |
| SEH-307 | P1 | Build Visit Pack review | Clear |

# Detailed Backlog — Chat / Evidence

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-320 | P0 | Build editorial Chat answer | Answer-first |
| SEH-321 | P0 | Preserve emergency hierarchy | Highest priority |
| SEH-322 | P0 | Build responsive reading column | Correct width |
| SEH-323 | P1 | Build optional source inspector | Lazy |
| SEH-324 | P1 | Remove permanent history sidebar in focus mode | Contextual history |
| SEH-325 | P0 | Build Personal detail preset | Concise |
| SEH-326 | P0 | Build Clinical detail preset | Evidence-rich |
| SEH-327 | P0 | Build Research detail preset | Provenance-rich |
| SEH-328 | P0 | Canonicalize source list | Inline/list agreement |
| SEH-329 | P0 | Keep diagnostics lazy and role-gated | No consumer leakage |
| SEH-330 | P0 | Consumer DOM excludes internal diagnostics | Test |
| SEH-331 | P0 | No CoT/raw hidden reasoning | Test |
| SEH-332 | P1 | Implement Orb→composer transition | Accessible |
| SEH-333 | P1 | Minimize composer toolbar | No clutter |
| SEH-450 | P0 | Build Evidence READ layout | Synthesis first |
| SEH-451 | P0 | Show applicability | Clear |
| SEH-452 | P0 | Show uncertainty | Clear |
| SEH-453 | P1 | Build role-gated source inspector | Pass |
| SEH-454 | P1 | Split Source Hub Browse/Manage | Explicit |

# Detailed Backlog — Clinical

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-350 | P0 | Implement Clinical dock Web | Correct |
| SEH-351 | P0 | Implement Clinical dock Mobile | Correct |
| SEH-352 | P0 | Doctor defaults to Clinical | Tests |
| SEH-353 | P0 | Council top-level destination | One primary action |
| SEH-354 | P0 | Scribe top-level destination | One primary action |
| SEH-355 | P1 | Build Clinical Context Bar | Mode visible |
| SEH-356 | P1 | Build explicit Personal switch | Clear context |
| SEH-357 | P0 | Remove Personal fallback from professional home | Tests |
| SEH-370 | P0 | Recompose Clinical Overview | No KPI filler |
| SEH-371 | P0 | Show real resumable activity only | No fabrication |
| SEH-372 | P0 | Honest no-active-work state | Pass |
| SEH-373 | P1 | Build Council ActionObject | Direct |
| SEH-374 | P1 | Build Scribe ActionObject | Direct |
| SEH-375 | P1 | Build professional Ask CLARA composer | Readable |
| SEH-376 | P0 | Show only real alerts | Truthful |
| SEH-377 | P0 | Never fallback to /today | E2E |

# Detailed Backlog — Council

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-390 | P0 | Migrate Council to FOCUS shell | No global clutter |
| SEH-391 | P0 | Build accessible case stepper | Pass |
| SEH-392 | P0 | Recompose case context review | Readable |
| SEH-393 | P0 | Build safe run state | Pass |
| SEH-394 | P0 | Migrate result to READ shell | Hierarchy |
| SEH-395 | P0 | Red flags first | Safety |
| SEH-396 | P0 | Recommendation second | Clear |
| SEH-397 | P0 | Agreement/disagreement visible | Explicit |
| SEH-398 | P0 | Uncertainty visible | Explicit |
| SEH-399 | P1 | Evidence after core decision | Readable |
| SEH-400 | P1 | Technical detail behind disclosure | No clutter |
| SEH-401 | P0 | Preserve clinician oversight | Tests |

# Detailed Backlog — Scribe

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-420 | P0 | Migrate capture to IMMERSIVE shell | Focused |
| SEH-421 | P0 | Consent before capture | Test |
| SEH-422 | P0 | Build recording island | Clear |
| SEH-423 | P0 | Build lightweight timer/waveform | Smooth |
| SEH-424 | P0 | Show microphone state | Explicit |
| SEH-425 | P0 | Accessible pause/stop controls | Pass |
| SEH-426 | P0 | Build transcript READ layout | Opaque |
| SEH-427 | P0 | Build SOAP review layout | Opaque |
| SEH-428 | P0 | Preserve canonical state labels | Distinct |
| SEH-429 | P0 | Preserve signed/finalized distinction | Tests |
| SEH-430 | P0 | Preserve audit/addendum semantics | Tests |
| SEH-431 | P1 | Capture→review continuity motion | Reduced-motion parity |
| SEH-432 | P1 | Reduce dock during recording | No distraction |

# Detailed Backlog — Research / Admin

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-455 | P1 | Build Research dock | Role-aware |
| SEH-456 | P1 | Research home only from real data | No synthetic dashboard |
| SEH-457 | P0 | Preserve source authority/ranking | Tests |
| SEH-458 | P1 | Research density preset | Readable |
| SEH-470 | P1 | Define DENSE shell | Coherent |
| SEH-471 | P1 | Build optional local Admin rail | Scoped |
| SEH-472 | P1 | Recompose Admin Overview | Real data |
| SEH-473 | P1 | Recompose Monitoring | Unknown != healthy |
| SEH-474 | P1 | Recompose Analytics | Data-first |
| SEH-475 | P1 | Recompose Knowledge | Compact |
| SEH-476 | P1 | Recompose Answer Flow | Readable |
| SEH-477 | P1 | Preserve audit/compliance semantics | Tests |
| SEH-478 | P1 | Document limited Mobile Admin scope | Intentional |

# Detailed Backlog — Accessibility / performance / cleanup

| ID | Priority | Task | Acceptance |
|---|---|---|---|
| SEH-500 | P0 | Keyboard dock | Complete |
| SEH-501 | P0 | Screen-reader dock | Complete |
| SEH-502 | P0 | Command Palette focus trap | Pass |
| SEH-503 | P0 | Context Bar focus order | Pass |
| SEH-504 | P0 | Orb semantics | Pass |
| SEH-505 | P0 | Reduced motion | Pass |
| SEH-506 | P0 | Reduced transparency | Pass |
| SEH-507 | P0 | 320px reflow | Pass |
| SEH-508 | P0 | 200% zoom | Pass |
| SEH-509 | P0 | Flutter text scaling | Pass |
| SEH-510 | P0 | TalkBack critical journeys | Pass |
| SEH-511 | P0 | VoiceOver critical journeys | Pass |
| SEH-512 | P0 | Status non-color semantics | Pass |
| SEH-513 | P1 | Forced colors/high contrast | Usable |
| SEH-514 | P1 | Vietnamese long-copy stress test | No clipping |
| SEH-530 | P0 | Bundle diff each milestone | Reviewed |
| SEH-531 | P0 | No duplicate icon system | Verified |
| SEH-533 | P1 | Lazy source inspector | Verified |
| SEH-534 | P1 | Lazy admin diagnostics | Verified |
| SEH-535 | P1 | Orb frame/perf test | Smooth |
| SEH-536 | P1 | Glass performance/fallback test | Pass |
| SEH-537 | P0 | No inactive mobile fetch | Verified |
| SEH-538 | P0 | No duplicate auth/profile fetch | Verified |
| SEH-539 | P0 | Hydration/console gate | Zero critical |
| SEH-540 | P0 | Flutter analyze/test gate | Pass |
| SEH-560 | P1 | Inventory sidebar dependencies | Complete |
| SEH-561 | P1 | Remove old global sidebar after migration | No supported dependency |
| SEH-562 | P1 | Inventory V2/V3 imports | Complete |
| SEH-563 | P1 | Build rollback adapter | Tested |
| SEH-564 | P2 | Remove V2 | Zero import |
| SEH-565 | P2 | Remove V3 | Zero import |
| SEH-566 | P2 | Remove stale mobile palette | Zero import |
| SEH-567 | P2 | Remove dead CSS | Visual pass |
| SEH-568 | P2 | Remove obsolete feature flags | Matrix updated |
| SEH-569 | P2 | Update architecture docs | Accurate |
| SEH-570 | P2 | Update design-system docs | Accurate |


---

# 45. Acceptance Journeys

## Personal first use

```text
Login
→ Global first run
→ optional Personal setup
→ Today
→ start journey OR Ask CLARA
```

No global sidebar dependency and no workspace terminology for single-mode Personal users.

## Returning Personal

```text
Login
→ Today
→ next accepted task visible immediately
→ open/complete
```

## Doctor

```text
Login
→ Clinical Overview
→ Council
```

and:

```text
Login
→ Clinical Overview
→ Scribe
→ Consent
→ Capture
→ Transcript
→ SOAP
→ Draft complete
```

No Personal PHR onboarding block.

## Doctor entering Personal

```text
Clinical
→ explicit mode switch
→ Personal
→ optional Personal setup
→ Today
```

Context change must be visually obvious.

## Researcher

```text
Login
→ Research
→ Evidence / Ask CLARA
→ inspect sources
```

## Shared context

```text
Personal
→ Family/Shared
→ bounded resource
→ scope remains visible
```

---

# 46. Visual Acceptance Matrix

Required Light + Dark screenshots for Login, Personal Today first-time, Personal Today active, LifeMap, Medicines, safety result, Profile, PHR, Chat answer, Family, Clinical Overview, Council setup, Council result, Scribe consent, Scribe capture, Transcript, SOAP, Evidence, Research source detail, Admin Overview, Monitoring.

Web viewports: 390×844, tablet, 1280×800, 1440×900, wide desktop. Mobile: compact phone, large phone, tablet.

For every page ask:
1. Is the current task obvious?
2. Can the page be understood without reading global navigation?
3. Is there one primary action?
4. Are there unnecessary cards?
5. Is glass limited to chrome?
6. Is safety content opaque?
7. Is typography readable?
8. Is role/mode clear?
9. Is local navigation genuinely contextual?
10. Does it still look like a generic SaaS dashboard?

If #10 is yes, redesign again.

---

# 47. Quality Gates

Do not ship if any of the following remain true:
- Personal requires a permanent global sidebar;
- Clinical requires a permanent global sidebar;
- Council/Scribe remain hidden in Profile;
- Personal onboarding blocks Clinical/Research/Admin;
- Today begins with generic shortcuts or stats;
- PHR remains fixed-height embedded scroll;
- professional home implicitly falls back to Personal;
- safety verdicts use decorative glass;
- Light mode feels secondary;
- Web/Mobile maintain duplicate palettes manually;
- Orb communicates medical severity;
- navigation morphing reduces discoverability;
- reduced motion/transparency breaks layout;
- synthetic medical or operational data fills visual empty space.

The redesign must be rejected if the result is merely old CLARA + new colors + rounded floating nav. Spatial hierarchy, shell behavior, composition, component vocabulary, role adaptation, and task prioritization must materially change.

---

# 48. Definition of Done

The program is complete only when:
1. Personal, Clinical, and Research no longer depend on permanent global sidebar navigation.
2. Context Bar ships.
3. Floating Dock ships.
4. CLARA Orb ships.
5. Command Palette ships on Web.
6. EXPLORE/FOCUS/IMMERSIVE/READ/DENSE shell modes are implemented.
7. Web/Mobile use one canonical token source.
8. Light/Dark are first-class.
9. Today is next-action-first.
10. PHR is full-surface.
11. Profile taxonomy is corrected.
12. Council/Scribe are top-level Clinical tools.
13. Professional onboarding is independent from Personal PHR.
14. Chat is editorial answer-first.
15. Council result is decision-first.
16. Scribe capture is immersive.
17. Evidence is synthesis-first.
18. Admin remains data-dense and truthful.
19. Safety-critical content uses opaque surfaces.
20. Critical accessibility paths pass.
21. Authorization/consent/provenance/DrugBank/FIDES semantics do not regress.
22. No CoT or private implementation detail leaks.
23. No PII telemetry regressions.
24. V2/V3 mobile layers are removed or bounded behind an explicit temporary rollback adapter.
25. Architecture docs match shipped code.

---

# 49. Engineering Rules

1. Re-read current implementation before each milestone.
2. Revalidate `main` if repository state changes materially.
3. Treat server behavior as truth.
4. Do not invent unsupported backend capability.
5. Preserve all safety semantics.
6. Work incrementally, not big-bang.
7. Keep milestones independently testable and revertible.
8. Add tests with each architectural/navigation/safety change.
9. Use generated semantic tokens for all new visual work.
10. Put visible copy into typed VI/EN localization.
11. Preserve deep links and compatibility aliases until explicit retirement.
12. Menu visibility must never become authorization.
13. Keep professional and personal context visibly distinct.
14. Preserve bounded shared-profile context.
15. Preserve no-PII analytics.
16. Preserve no-chain-of-thought behavior.
17. Do not use raw colors in new components without an approved exception.
18. Do not retain the legacy global sidebar merely because it is easier.
19. Do not put glass on content because the shell uses glass.
20. Do not mark a task complete without evidence.

---

# 50. Progress Artifact

Maintain:

```text
docs/ui-transformation-v4/PROGRESS.md
```

Every task records: Task ID, status, files changed, screens affected, tests, visual evidence, accessibility evidence, safety considerations, known differences, rollback notes.

Recommended docs split:

```text
docs/ui-transformation-v4/
  00-overview.md
  01-design-language.md
  02-product-model.md
  03-navigation-and-shell.md
  04-visual-system.md
  05-components.md
  06-personal-experience.md
  07-clinical-experience.md
  08-research-admin.md
  09-technical-architecture.md
  10-accessibility.md
  11-migration-plan.md
  12-task-backlog.md
  PROGRESS.md
```

---

# 51. Final Design Statement

CLARA must no longer be perceived as **a healthcare dashboard with AI features**.

It should be perceived as:

> **A calm, spatial health operating environment that reshapes itself around the user's current context, role, and task.**

Personal CLARA is a premium trustworthy health companion. Clinical CLARA is a focused professional instrument. Research CLARA is an editorial evidence workstation. Administration is a dense but coherent operational console. All four must feel unmistakably like one CLARA product.

Final non-negotiable principle:

> **Navigation should feel like a tool that appears when needed. Content should feel like the product.**
