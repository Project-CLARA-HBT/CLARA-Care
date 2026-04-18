# Chat Flow Map (/chat)

## Entry points
- `/chat` (main workspace)
- `/chat/shares` (share manager)

## Main user goals
- ask a question and get an answer
- manage conversations and folders
- write and manage notes
- share/revoke public links
- export conversations (.md/.docx)
- inspect telemetry and source confidence

## Screen inventory
- S01 Chat Home Desktop
- S02 Chat Home Desktop - Active Conversation + Telemetry Open
- S03 Chat Home Desktop - Left Panel in Notes View
- S04 Chat Home Desktop - Left Panel in Discover View
- S05 Chat Home Desktop - Left Panel in Shares View
- S06 Scope Manager Modal
- S07 Command Palette Modal
- S08 Share Management Page (/chat/shares)
- S09 Chat Home Mobile - Default
- S10 Chat Home Mobile - Sidebar Open
- S11 Chat Home Mobile - Composer Focused
- S12 Chat Home Mobile - Telemetry Bottom Panel

## Primary flow edges
- S01 -> S02: open telemetry panel
- S01 -> S06: click Folders / Scope Manager
- S01 -> S07: keyboard command palette (Cmd/Ctrl+Shift+P)
- S01 -> S03/S04/S05: switch left view tabs
- S05 -> S08: open share manager
- S01 -> S09: responsive breakpoint
- S09 -> S10: open mobile sidebar
- S09 -> S11: focus chat composer
- S09 -> S12: open telemetry panel

## Key UI blocks to preserve
- Left workspace panel with segmented views: all/chat/notes/discover/shares
- Conversation list with search/filter/folder controls
- Message timeline and composer
- Action strip: rename, export, share, revoke, manage shares
- Telemetry rail/panel with confidence + source intel + logic flow
- Modals: scope manager, command palette

## States to design
- empty state (no conversation)
- loading state
- degraded state (workspace API unavailable)
- active state (selected conversation)
- share active/inactive states
- note edit/create states
