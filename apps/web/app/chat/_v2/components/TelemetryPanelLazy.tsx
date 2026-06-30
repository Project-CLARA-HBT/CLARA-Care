"use client";

import dynamic from "next/dynamic";

import type { UserRole } from "@/lib/auth-store";
import type { TelemetryPanelProps } from "@/app/chat/_v2/components/TelemetryPanel";

/**
 * Lazy boundary for the detailed `TelemetryPanel` (Requirement 6.6, 7.3;
 * design Property P7).
 *
 * The detailed telemetry surface is an "advanced surface" that must be
 * lazy-loaded (Requirement 7.3) and is admin-only (Requirement 6.6, Property
 * P7). This wrapper enforces both:
 *
 * - The panel module is pulled in via `next/dynamic`, so its code is never part
 *   of the initial chat bundle and is only fetched on demand.
 * - The dynamic import is gated behind `role === "admin"` so the chunk is never
 *   even requested for a non-admin — non-admin roles can never load or see
 *   detailed telemetry (Property P7). The underlying `TelemetryPanel` also
 *   re-checks the role via the shared role-gated wrapper (defense in depth).
 *
 * `import type { TelemetryPanelProps }` is erased at compile time, so importing
 * the prop type here does NOT eagerly pull in the panel implementation.
 */

const TelemetryPanel = dynamic(
  () => import("@/app/chat/_v2/components/TelemetryPanel"),
  { ssr: false },
);

export type TelemetryPanelLazyProps = TelemetryPanelProps & {
  role: UserRole;
};

export default function TelemetryPanelLazy(props: TelemetryPanelLazyProps) {
  // Hard gate: only admins ever mount (and therefore download) the detailed
  // telemetry chunk. Non-admins render nothing here (Property P7, Req 7.3).
  if (props.role !== "admin") {
    return null;
  }
  return <TelemetryPanel {...props} />;
}
