# Stitch Upload Checklist

## Before generating
- Confirm project name: CLARA Chat Redesign
- Set primary language for UI text: Vietnamese
- Set platform variants: Desktop + Mobile
- Keep consistent naming: S01..S12

## In Stitch
- Generate Prompt 00 once (design baseline)
- Generate each screen prompt in order
- For each screen, keep previous context so components stay consistent
- After each generation, quickly rename frame to its ID

## Validation list
- Left panel has all 5 views (All/Chat/Notes/Discover/Shares)
- Telemetry panel exists in desktop + mobile states
- Scope Manager modal and Command Palette modal both exist
- Share Manager page table has all required columns/actions
- Export/share actions are visible in active conversation state
- Dark mode contrast is readable and not over-bright

## Handoff from Stitch
- Export to Figma for manual polish
- Export code only after flow is locked
- Keep one source of truth for tokens/colors from Prompt 00 output
