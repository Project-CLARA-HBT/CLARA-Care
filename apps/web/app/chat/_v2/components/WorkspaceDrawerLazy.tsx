"use client";

import dynamic from "next/dynamic";

import type { WorkspaceDrawerProps } from "@/app/chat/_v2/components/WorkspaceDrawer";

/**
 * Lazy boundary for the advanced `WorkspaceDrawer` (Requirement 7.3, design
 * Property P9).
 *
 * The workspace drawer (notes / shares / export tooling) is an "advanced
 * surface" that must be lazy-loaded so it is never part of the initial chat
 * bundle (Requirement 7.3). This wrapper enforces that:
 *
 * - The drawer module is pulled in via `next/dynamic`, so its code (and the
 *   export/docx tooling it transitively uses) is code-split.
 * - The dynamic component is only rendered — and therefore the chunk only
 *   fetched — once the drawer is actually opened (`open === true`). Rendering
 *   nothing while closed keeps the chunk request fully on demand.
 *
 * `import type { WorkspaceDrawerProps }` is erased at compile time, so importing
 * the prop type here does NOT eagerly pull in the drawer implementation.
 */

const WorkspaceDrawer = dynamic(
  () => import("@/app/chat/_v2/components/WorkspaceDrawer"),
  { ssr: false },
);

export default function WorkspaceDrawerLazy(props: WorkspaceDrawerProps) {
  // Defer the chunk fetch until the drawer is opened on demand (Req 7.3, P9).
  if (!props.open) {
    return null;
  }
  return <WorkspaceDrawer {...props} />;
}
