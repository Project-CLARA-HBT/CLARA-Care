# Design-system specification

## Direction

CLARA should feel calm, trustworthy, medically appropriate, and readable in Vietnamese. The reference theme is light mode: a quiet cool canvas, opaque surfaces, restrained blue action color, explicit status treatment, and limited elevation. Dark mode uses the same semantic roles, not a second visual language.

## Semantic token contract

Feature components must use semantic variables/classes, not raw palette values.

```text
surface-canvas       page background
surface-base         standard card/form surface
surface-subtle       quiet section background
surface-raised       elevated card/side sheet
surface-overlay      modal/popover
content-primary      main text
content-secondary    supporting text
content-muted        captions/disabled guidance
content-inverse      text on primary action
content-link         links
border-subtle        non-interactive dividers
border-control       input/control boundary (must remain visible)
border-strong        selected/critical boundary
action-primary       primary blue action
action-primary-hover hover/pressed action
action-secondary     secondary control
action-danger        destructive action
feedback-success-*   background/border/text/icon
feedback-warning-*   background/border/text/icon
feedback-danger-*    background/border/text/icon
feedback-info-*      background/border/text/icon
focus-color/width/offset
radius-control/card/panel/pill
shadow-card/overlay/focus
```

Target values are adapted from the requested palette and must be checked against the existing token tests before replacement:

| Role | Light | Dark |
|---|---|---|
| Canvas | `#F6F8FC` | `#0B1220` |
| Base | `#FFFFFF` | `#111827` |
| Subtle/elevated | `#EEF3F8` / `#FFFFFF` | `#172033` |
| Primary text | `#172033` | `#F8FAFC` |
| Secondary text | `#526277` | `#AFC0D3` |
| Border | `#D8E2EC` (non-control only) | `#2A3950` |
| Action | `#2563EB` | `#60A5FA` |
| Action hover | `#1D4ED8` | `#2563EB` |
| Success | `#0F9F6E` | `#34D399` |
| Warning | `#D97706` | `#FBBF24` |
| Danger | `#DC2626` | `#FB7185` |

`#D8E2EC` cannot be the only boundary for an interactive white control; use control border, contrast, and/or elevation together. Existing audited token names remain aliases during migration.

## Typography

- Page heading 28–32 px; section heading 18–20 px; body 15–16 px; button 14–15 px; caption 12–13 px minimum.
- Use the existing Vietnamese-capable system/Inter stack only after local/runtime loading is proven; external font failure must not break icons or layout.
- Do not use wide uppercase labels for medical content. Visualizations may use compact labels with an approved exception.
- Line height body 1.5–1.6; Vietnamese diacritics must not clip at 200% zoom.

## Spacing, radius, elevation, and motion

- 8 px-oriented spacing scale.
- Controls 8–10 px radius; cards 14–16 px; panels 18–20 px; pills only for badges/filters.
- Surface 0 canvas, Surface 1 card, Surface 2 overlay; maximum three common card variants: StandardCard, InteractiveCard, StatusCard.
- Shadows are low contrast and tokenized. No functional neon glow, decorative gradients, or pulsing non-urgent state.
- Respect `prefers-reduced-motion`; preserve only essential progress transitions.

## Icon system

Create `apps/web/components/ui/icon.tsx` with:

- typed `IconName` union and a code-owned SVG map;
- deterministic fallback icon for unknown names;
- `decorative`/`label` props that enforce accessible semantics;
- fixed viewBox and dimensions to avoid layout shift;
- no arbitrary SVG/HTML from props;
- migration aliases for current material names.

Use the Icon component in PHR, shell, shared primitives, then domain pages. Do not add a second runtime icon library. Material Symbols may remain as a temporary audited compatibility layer, but a font failing to load must never expose its ligature text.

## Shared primitives

| Primitive | Contract |
|---|---|
| `PageHeader` | One `h1`, context/subtitle, optional action slot; no duplicate shell title. |
| `Section` | Semantic grouping with heading and spacing. |
| `Card` / `InteractiveCard` / `StatusCard` | Token surfaces, optional status and interaction semantics. |
| `StatCard` | Only for measured non-empty values; never fabricated health/confidence. |
| `StatusBadge` | Text + icon/state; never color alone. |
| `EmptyState` | One clear primary action, optional low-emphasis text action. |
| `Tabs` | Native/ARIA tab semantics, keyboard arrows/Home/End, URL-backed when route state matters. |
| `Stepper` | Flow name, current/total step, completed states, back/next/review. |
| `SideSheet` | Focus trap, inert background, Escape/backdrop, restore focus, responsive width. |
| `ConfirmDialog` | Consequence summary, explicit confirm/cancel, focus/error behavior. |
| `FormField` | Label, required/optional, hint/error IDs, `aria-invalid`, disabled/loading. |
| `DataList` | Empty/loading/partial/error states and responsive row semantics. |
| `WorkspaceSwitcher` | Permitted workspace presentation only; no role mutation. |
| `CreateMenu` | Contextual creation actions; keyboard and one primary CTA policy. |
| `Alert` / `LiveStatus` | `role=alert` for urgent errors; `role=status` polite for non-urgent transitions. |
| `ProgressList` | PHR/setup completion with honest states, not clinical certainty percentages. |

Every nontrivial primitive gets a focused test, dark-mode behavior, keyboard behavior, and responsive minimum-size check.

## Domain presentation rules

- Safety, emergency, DDI unavailable, unresolved identity, consent, provenance, and clinician review are always visible or immediately adjacent to the decision.
- Technical detail (retrieval stages, raw IDs, provider/model, query telemetry) is progressive disclosure and role-gated.
- Empty states explain what is missing and what the user can do next; no fabricated counts.
- Async errors preserve accepted input and announce status once.

## Consumer terminology boundary

The personal workspace must not expose internal terms such as `RAG`, `NLI`, `FIDES`, `provenance`, `truth state`, `telemetry`, `pipeline`, `corpus`, or raw `confidence`. Consumer-safe alternatives are “Nguồn tham khảo”, “Thông tin CLARA dựa vào”, “Điều chưa chắc chắn”, and “Bạn nên làm gì tiếp theo”. Professional/research users may receive concise evidence terminology; administrators may receive operational labels in an explicitly labelled details panel. A static scan covers visible text, loading/error/empty copy, aria labels, and legacy research/admin imports, with an allowlist documented in the test plan.

## Styling migration

Keep the existing `globals.css` entrypoint during migration, but separate stable layers internally or into imported CSS:

```text
tokens → reset/base → typography → shell → shared components → domain compatibility
```

Inventory each legacy class before deleting it. Keep Chat rollback and legal/public consumers until retirement evidence exists. New screens cannot introduce raw Tailwind palette/hex values outside a documented chart exception.

## Icon and font acceptance

- Block Google Fonts in a browser test: app still has named controls and no ligature text.
- PHR DOM contains SVG icons and never raw names.
- Icon-only controls have accessible labels; decorative icons are hidden.
- Layout remains stable while font assets fail or are slow.
