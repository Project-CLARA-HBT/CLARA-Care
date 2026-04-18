# CLARA Chat Redesign - Stitch Handoff

This package is made so you can quickly move `/chat` redesign work into Google Stitch.

## Important
I cannot directly upload to your Stitch workspace because that requires your Google account session.
What I prepared here:
- full flow map for `/chat`
- screen-by-screen prompts (desktop + mobile)
- handoff checklist so you can create all screens quickly in Stitch

## Files
- `chat-flow-map.md`
- `stitch-prompts.md`
- `stitch-checklist.md`

## Fast use (10-15 min setup)
1. Open `https://stitch.withgoogle.com/` and create a new project: `CLARA Chat Redesign`.
2. Paste `Prompt 00` from `stitch-prompts.md` as the design baseline.
3. Generate screens in order from `Prompt 01` to `Prompt 12`.
4. Keep naming in Stitch using the same IDs (e.g. `S01_Chat_Home_Desktop`).
5. Connect flows in prototype mode using `chat-flow-map.md`.
6. Export to Figma/code when done.

## Suggested generation order
- Desktop first: S01 -> S08
- Mobile second: S09 -> S12

## Existing app references
- Main chat page: `apps/web/app/chat/page.tsx`
- Share management page: `apps/web/app/chat/shares/page.tsx`
- Chat components: `apps/web/components/chat-workspace/*`
- Workspace/research APIs: `apps/web/lib/workspace.ts`, `apps/web/lib/research*.ts`
