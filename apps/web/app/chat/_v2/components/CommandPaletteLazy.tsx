"use client";

import dynamic from "next/dynamic";

import type { CommandPaletteProps } from "@/app/chat/_v2/components/CommandPalette";

/**
 * Lazy boundary for the advanced `CommandPalette` (Requirement 7.3, design
 * Property P9).
 *
 * The command palette is an "advanced surface" that is only reachable on demand
 * (Ctrl/⌘+K, ⌘+Shift+P, or the header action), so its code should not ship in
 * the initial chat bundle (Requirement 7.3). This wrapper enforces that:
 *
 * - The palette module is pulled in via `next/dynamic`, so it is code-split.
 * - The dynamic component is only rendered — and therefore the chunk only
 *   fetched — once the palette is actually opened (`palette.isOpen === true`).
 *
 * `import type { CommandPaletteProps }` is erased at compile time, so importing
 * the prop type here does NOT eagerly pull in the palette implementation.
 */

const CommandPalette = dynamic(
  () => import("@/app/chat/_v2/components/CommandPalette"),
  { ssr: false },
);

export default function CommandPaletteLazy(props: CommandPaletteProps) {
  // Defer the chunk fetch until the palette is opened on demand (Req 7.3, P9).
  if (!props.palette.isOpen) {
    return null;
  }
  return <CommandPalette {...props} />;
}
