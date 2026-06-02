import type { ReactNode } from "react";
import type { UserRole } from "@/lib/auth-store";
import { stripTelemetryLabels } from "@/lib/user-facing-text";

/**
 * Role-gated telemetry surface (Requirement 4.3, Property 11).
 *
 * Detailed telemetry panels are visible to Admin_Users only; every other role
 * (`normal`, `researcher`, `doctor`) receives a sanitized summary instead.
 *
 * Visibility is exposed as a pure function of `(role, payload)` so it can be
 * unit/property tested in isolation (task 3.7) without rendering React. Per
 * Property 11 the decision depends solely on the role: detailed telemetry is
 * shown if and only if `role === "admin"`, regardless of payload contents.
 *
 * Design: `.kiro/specs/product-polish-analytics/design.md` section 2
 * Requirements: 4.3 (admin-only detailed telemetry panels).
 */

/** The portion of a telemetry surface a given role is allowed to see. */
export type TelemetryVisibility = {
  /** Detailed/raw telemetry — admin only. */
  showDetailed: boolean;
  /** Sanitized, end-user-safe summary — shown to non-admin roles. */
  showSummary: boolean;
};

/**
 * Pure predicate: detailed telemetry is visible iff the role is `admin`.
 *
 * This is the canonical helper the property test (task 3.7, Property 11)
 * imports. It is deliberately payload-independent so the invariant
 * "visibility === (role is admin)" holds for any payload.
 *
 * Requirement 4.3.
 */
export function isTelemetryVisible(role: UserRole): boolean {
  return role === "admin";
}

/**
 * Backwards-compatible alias for {@link isTelemetryVisible}.
 * @deprecated Prefer `isTelemetryVisible`.
 */
export const shouldShowTelemetry = isTelemetryVisible;

/**
 * Pure visibility decision as a function of `(role, payload)`.
 *
 * `payload` is accepted for call-site parity and future extension, but the
 * decision is intentionally role-only so the invariant in Property 11 holds for
 * any payload (including empty/undefined).
 */
export function telemetryVisibility(role: UserRole, _payload?: unknown): TelemetryVisibility {
  const showDetailed = isTelemetryVisible(role);
  return { showDetailed, showSummary: !showDetailed };
}

export type TelemetryPanelProps = {
  /** Requesting user's role, e.g. from `getRole()`. */
  role: UserRole;
  /** Detailed telemetry content rendered only for Admin_Users. */
  children: ReactNode;
  /**
   * Sanitized summary node rendered for non-admin roles. When omitted (and no
   * `summaryText` is supplied), non-admin roles see nothing (panel hidden).
   *
   * Callers passing a node are responsible for keeping it free of internal
   * telemetry jargon. Prefer `summaryText` to delegate that sanitization here.
   */
  summary?: ReactNode;
  /**
   * Plain-text summary for non-admin roles. It is sanitized through
   * `stripTelemetryLabels` before rendering so internal telemetry labels
   * (`research mode`, `retrieval`, `RAG mode`, `Fallback mode`,
   * `Policy: Warn/Allow`) never reach an End_User view. If both `summary` and
   * `summaryText` are provided, `summary` wins.
   */
  summaryText?: string;
  /**
   * Optional raw telemetry payload. Not used for the gating decision (the
   * decision is role-only per Property 11); accepted so callers can keep the
   * payload colocated with the panel and for parity with `telemetryVisibility`.
   */
  payload?: unknown;
  /** Optional wrapper class for layout integration. */
  className?: string;
};

/**
 * Role-gated wrapper that renders detailed telemetry only for Admin_Users and
 * the sanitized summary (if provided) for everyone else.
 *
 * Requirement 4.3.
 */
export default function TelemetryPanel({
  role,
  children,
  summary,
  summaryText,
  payload,
  className,
}: TelemetryPanelProps) {
  const { showDetailed } = telemetryVisibility(role, payload);

  if (showDetailed) {
    return (
      <div className={className} data-telemetry-view="detailed">
        {children}
      </div>
    );
  }

  if (summary !== undefined && summary !== null) {
    return (
      <div className={className} data-telemetry-view="summary">
        {summary}
      </div>
    );
  }

  if (typeof summaryText === "string") {
    const sanitized = stripTelemetryLabels(summaryText);
    if (sanitized) {
      return (
        <div className={className} data-telemetry-view="summary">
          {sanitized}
        </div>
      );
    }
  }

  return null;
}
