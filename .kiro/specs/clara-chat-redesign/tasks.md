# Implementation Plan: CLARA Chat Redesign

## Overview

Rebuild `apps/web/app/chat` from the ground up into a componentized,
answer-first, accessible chat — incrementally and behind `CHAT_V2` (flag/route),
reusing all existing API/SSE contracts and changing no backend behavior. The
legacy page is preserved and served until documented parity. Every task is
verifiable with `npm run lint`, `npm run test` (Vitest), and `npm run build` in
`apps/web`.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing Vitest + fast-check setup in `apps/web`.
- Add a `_v2/__tests__` area; co-locate component/hook tests.
- A flag-off regression test asserts the route renders the legacy page unchanged.

## Tasks

- [x] 1. Scaffolding + flag gate
  - [x] 1.1 Move current page verbatim to `_legacy/page-legacy.tsx`; make `page.tsx` a gate on `CHAT_V2` (default off ⇒ legacy). Flag-off regression test. Property P1.
  - [x] 1.2 Establish design tokens + base primitives (Button, IconButton, Drawer, Tooltip, StatusDot, Tabs) with accessible states + light/dark. Requirement 4.

- [x] 2. Extract pure utilities + hooks (no presentation)
  - [x] 2.1 Move formatting helpers to `_v2/lib/chat-format.ts` + `telemetry-format.ts`; port their property tests. Property P8.
  - [x] 2.2 `useConversations` (CRUD/favorite/folder + local fallback). Requirement 6.1, 6.5.
  - [x] 2.3 `useChatTurns` (load/persist per conversation, no turn loss). Property P4.
  - [x] 2.4 `useChatStream` wrapping `lib/research.ts` (fast stream + tier2 job poll/SSE + fallback + cancel). Requirement 3, Property P2, P4.
  - [x] 2.5 `useWorkspace` (notes/shares/export/search) + `useCommandPalette`.

- [ ] 3. Shell + layout
  - [x] 3.1 `ChatShell` responsive layout (sidebar/canvas/drawer), ARIA landmarks, skip-link, global shortcuts, focus management. Requirement 2.1, 5.
  - [x] 3.2 Theme integration (light/dark, `prefers-reduced-motion`). Requirement 4.2, 4.5.

- [x] 4. Conversation canvas (hero)
  - [x] 4.1 `MessageLog` virtualized turns. Requirement 7.1.
  - [x] 4.2 `AnswerRenderer` (typographic markdown/tables/citations) + per-turn error boundary. Requirement 2.2.
  - [x] 4.3 `FlowTimeline` inline deep/deep_beta status mapping. Requirement 2.3, 3.2; degraded labeling. Property P5.
  - [x] 4.4 `TelemetryPanel` lazy + admin-only detail. Requirement 6.6, 7.3; Property P7.

- [x] 5. Composer
  - [x] 5.1 Prompt + mode selector (fast/deep/deep_beta) + personal toggle + send/cancel; responsive during runs. Requirement 3.5, 4.4.
  - [x] 5.2 Live region for streaming updates. Requirement 5.2.

- [x] 6. Sidebar + workspace + command palette
  - [x] 6.1 `ConversationSidebar` (list/search/folders entry, virtualized). Requirement 2.4, 6.4, 7.1.
  - [x] 6.2 `WorkspaceDrawer` (notes/shares with expiry/rotate/revoke/export md+docx) behind progressive disclosure. Requirement 6.1, 6.2.
  - [x] 6.3 `CommandPalette` parity actions, keyboard-first. Requirement 6.3, 5.1.

- [x] 7. Accessibility + performance hardening
  - [x] 7.1 Keyboard nav + focus management across drawers/modals/palette; AA contrast audit. Requirement 5, Property P6.
  - [x] 7.2 Memoization/state-colocation pass; lazy-load advanced surfaces. Requirement 7.2, 7.3, Property P9.

- [ ] 8. Parity verification + rollout
  - [x] 8.1 Parity checklist test matrix mapping each Requirement 6 capability to a v2 test. Property P3.
  - [x] 8.2 No-PII client analytics assertion. Property P8/8.5. Consent/disclaimer/RBAC preserved. Property P10.
  - [-] 8.3 Enable `CHAT_V2` in staging; verify parity; flip default in production; schedule legacy removal in a later cleanup task.

## Notes

### Property → implementing test task
- P1 → 1.1 · P2 → 2.4 · P3 → 8.1 · P4 → 2.3/2.4 · P5 → 4.3 · P6 → 7.1 · P7 → 4.4 · P8 → 2.1/8.2 · P9 → 7.2 · P10 → 8.2

### Subagent assignment guidance (disjoint write scopes)
- Hooks/utilities (`_v2/lib`, `_v2/hooks`) — one writer.
- Canvas + composer (`_v2/components/{MessageLog,TurnView,AnswerRenderer,FlowTimeline,TelemetryPanel,Composer}`) — disjoint writer.
- Sidebar + drawer + palette (`_v2/components/{ConversationSidebar,WorkspaceDrawer,CommandPalette}`) — disjoint writer.
- Shell + tokens/primitives — disjoint writer.
Serialize integration (task 8) after the parallel component work lands.
