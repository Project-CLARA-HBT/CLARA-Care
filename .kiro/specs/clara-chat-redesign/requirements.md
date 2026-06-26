# Requirements Document

## Introduction

This feature **rebuilds the CLARA Chat page (`apps/web/app/chat/page.tsx`) from
the ground up** and drastically improves its user experience. The current page
is a single ~4,200-line client component (`ChatWorkspacePage`) holding 60+
`useState` hooks, a hand-rolled resizable workspace panel, a virtualized
conversation list, a command palette, telemetry/flow panels, share/export/notes,
and the chat composer — all in one file. It works, but it is hard to maintain,
visually dense, inconsistent across modes (fast / deep / deep_beta), and the
core "ask → watch reasoning → read answer" flow is buried under workspace
chrome.

The goal is a **modern, focused, accessible chat experience** that makes the
answer and its reasoning the hero, keeps the powerful workspace features but
behind clean progressive-disclosure surfaces, and is built from **small,
testable, composable components** with a coherent design system. It is a
**front-end rebuild only**: it reuses the existing API/SSE contracts
(`lib/research.ts`, `lib/http-client.ts`, chat proxy, tier2 jobs, flow events)
and does not change backend behavior or any safety guardrail.

The rebuild is **incremental and behind a flag**: the new chat mounts under a
flag/route so the existing page keeps serving until the rebuild reaches parity,
then becomes the default. All copy stays Vietnamese-first with bilingual vi/en,
and the existing consent gate, disclaimer, RBAC nav, and telemetry-visibility
rules (admin-only detailed telemetry) are preserved.

## Glossary

- **Chat_Web**: The web chat surface at `apps/web/app/chat`.
- **Composer**: The message input area (prompt, mode selector, personal-mode toggle, send).
- **Turn**: One user query + its CLARA answer (and any tier2 job/flow data).
- **Research mode**: `fast` (tier1 chat proxy), `deep`, `deep_beta` (tier2 jobs).
- **Flow timeline**: The realtime reasoning/stage events for deep/deep_beta runs.
- **Telemetry panel**: Confidence, neural load, logic flow, source intel (admin-visible detail).
- **Workspace**: Folders, conversations, notes, channels, share, export.
- **Progressive disclosure**: Showing the essential UI first and revealing advanced surfaces on demand.
- **Design system**: The shared tokens/components (color, spacing, typography, primitives) the new UI is built on.
- **Parity**: The new chat supports every user-facing capability the current page supports.
- **Feature flag / route gate**: The switch that serves the new chat without deleting the old one.

## Requirements

### Requirement 1: Componentized Architecture

**User Story:** As a maintainer, I want the chat built from small composable components and hooks, so that it is testable and maintainable.

#### Acceptance Criteria

1. THE Chat_Web SHALL decompose the page into focused components (composer, turn view, flow timeline, telemetry panel, conversation list, workspace drawer, command palette) each in its own file.
2. THE Chat_Web SHALL extract data/state logic into custom hooks (e.g. conversations, turns, workspace, streaming) separated from presentation.
3. THE Chat_Web SHALL keep each new component independently unit-testable with the existing Vitest setup.
4. THE Chat_Web SHALL not exceed a documented per-file size budget for the new components.

### Requirement 2: Answer-First, Focused Layout

**User Story:** As a user, I want the conversation and answer to be the focus, so that I can read and reason without UI clutter.

#### Acceptance Criteria

1. THE Chat_Web SHALL present the active conversation and composer as the primary surface, with workspace chrome secondary and collapsible.
2. THE Chat_Web SHALL render answers with readable typography, clear hierarchy, and well-formatted markdown/tables/citations.
3. WHERE a turn is a deep/deep_beta run, THE Chat_Web SHALL show the flow timeline inline with the turn without overwhelming the answer.
4. THE Chat_Web SHALL keep advanced workspace surfaces (folders, notes, shares) behind progressive-disclosure entry points.
5. THE Chat_Web SHALL maintain a responsive layout that works on mobile, tablet, and desktop.

### Requirement 3: Streaming and Reasoning Experience

**User Story:** As a user running a Pro query, I want a clear realtime view of CLARA's progress, so that long runs feel responsive and trustworthy.

#### Acceptance Criteria

1. WHEN a fast query streams tokens, THE Chat_Web SHALL render incremental answer tokens smoothly.
2. WHEN a deep/deep_beta job runs, THE Chat_Web SHALL show realtime stage/flow updates with clear status (pending/in-progress/done/warning/failed).
3. THE Chat_Web SHALL handle streaming fallback and job-polling exactly as the current contracts require, without losing turns.
4. WHERE a run degrades to local fallback, THE Chat_Web SHALL clearly label the answer as degraded.
5. THE Chat_Web SHALL keep the composer responsive (cancel/await) during an active run.

### Requirement 4: Modern, Consistent Visual Design

**User Story:** As a user, I want a modern, cohesive interface, so that the product feels trustworthy and pleasant.

#### Acceptance Criteria

1. THE Chat_Web SHALL use a consistent design-token system for color, spacing, typography, and elevation.
2. THE Chat_Web SHALL support light and dark themes consistent with the rest of the app.
3. THE Chat_Web SHALL use consistent, accessible interactive states (hover, focus-visible, active, disabled).
4. THE Chat_Web SHALL present mode selection (fast/deep/deep_beta) and personal mode with clear, modern affordances.
5. THE Chat_Web SHALL use motion/transitions purposefully and respect `prefers-reduced-motion`.

### Requirement 5: Accessibility

**User Story:** As a user relying on assistive technology, I want the chat to be accessible, so that I can use every capability.

#### Acceptance Criteria

1. THE Chat_Web SHALL provide full keyboard navigation for composer, conversation list, command palette, and panels.
2. THE Chat_Web SHALL expose correct semantics/ARIA for the message log, streaming updates (live region), and controls.
3. THE Chat_Web SHALL meet WCAG AA contrast for text and essential UI in both themes.
4. THE Chat_Web SHALL manage focus correctly when opening/closing drawers, modals, and the command palette.
5. THE Chat_Web SHALL preserve visible focus indicators and `prefers-reduced-motion` handling.

### Requirement 6: Feature Parity and Workspace Capabilities

**User Story:** As an existing user, I want every current capability preserved, so that the rebuild loses nothing.

#### Acceptance Criteria

1. THE Chat_Web SHALL preserve conversation create/select/rename/delete, favorites, and folder organization.
2. THE Chat_Web SHALL preserve notes, sharing (with expiry/rotation/revoke), and export (markdown/docx).
3. THE Chat_Web SHALL preserve the command palette and its actions.
4. THE Chat_Web SHALL preserve search across conversations.
5. THE Chat_Web SHALL preserve the local-fallback workspace behavior when the workspace API is unavailable.
6. THE Chat_Web SHALL preserve telemetry/flow panels with admin-only detail visibility.

### Requirement 7: Performance

**User Story:** As a user with many conversations, I want the chat to stay fast, so that it is usable at scale.

#### Acceptance Criteria

1. THE Chat_Web SHALL virtualize long conversation lists and long message logs.
2. THE Chat_Web SHALL avoid unnecessary re-renders via memoization and state colocation.
3. THE Chat_Web SHALL lazy-load advanced surfaces (telemetry detail, workspace drawers, export tooling).
4. THE Chat_Web SHALL keep initial interaction responsive on mid-range hardware.

### Requirement 8: Incremental Rollout, Back-Compatibility, and Guardrails

**User Story:** As a platform operator, I want the rebuild to roll out safely, so that users are never broken mid-migration.

#### Acceptance Criteria

1. THE Chat_Web SHALL mount the new chat behind a flag/route while the existing page remains available until parity.
2. WHERE the flag is off, THE Chat_Web SHALL serve the existing experience unchanged.
3. THE Chat_Web SHALL reuse existing API/SSE contracts without backend changes.
4. THE Chat_Web SHALL preserve the consent gate, medical disclaimer, and RBAC-based navigation.
5. THE Chat_Web SHALL preserve no-PII handling in any client telemetry/analytics calls.
6. THE Chat_Web SHALL reach documented parity before becoming the default, with the old page removable in a later cleanup.
