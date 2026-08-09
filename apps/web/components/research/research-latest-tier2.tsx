import ResearchEmptyState from "@/components/research/research-empty-state";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { ResearchTier2Result } from "@/lib/research";
import { getRole, type UserRole } from "@/lib/auth-store";
import { toModeLabel } from "@/lib/user-facing-text";

type ResearchLatestTier2Props = {
  result: ResearchTier2Result | null | undefined;
  title?: string;
  excerptChars?: number;
  className?: string;
  /**
   * Requesting user's role. Detailed runtime telemetry (policy action,
   * fallback usage, raw mode string) is rendered for Admin_Users only; every
   * other role sees a sanitized, plain-language summary (Requirement 4.3).
   * Defaults to the current stored role.
   */
  role?: UserRole;
};

function toExcerpt(answer: string, maxChars: number): string {
  const normalized = answer.replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  if (normalized.length <= maxChars) return normalized;
  return `${normalized.slice(0, Math.max(maxChars - 3, 0)).trimEnd()}...`;
}

function resolveResearchMode(result: ResearchTier2Result): string {
  const mode = result.researchMode?.trim() || result.debug.researchMode?.trim();
  return mode || "unknown";
}

/**
 * Plain-language, End_User-safe phrasing for a policy action. Internal labels
 * such as `Policy: warn` / `Policy: allow` are never shown to non-admin roles
 * (Requirement 4.1); they map to calm Vietnamese summaries instead.
 */
function friendlyPolicySummary(action?: "allow" | "warn" | "block" | "escalate"): {
  label: string;
  className: string;
} | null {
  if (action === "warn") {
    return {
      label: "Cần đọc lưu ý",
      className:
        "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
    };
  }
  if (action === "allow") {
    return {
      label: "Có thể tham khảo",
      className:
        "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
    };
  }
  if (action === "block") {
    return {
      label: "Nội dung bị giới hạn",
      className:
        "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
    };
  }
  if (action === "escalate") {
    return {
      label: "Cần hỗ trợ chuyên môn",
      className:
        "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
    };
  }
  return null;
}

function policyBadge(action?: "allow" | "warn" | "block" | "escalate"): {
  label: string;
  className: string;
} {
  if (action === "warn") {
    return {
      label: "Policy: warn",
      className:
        "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
    };
  }
  if (action === "allow") {
    return {
      label: "Policy: allow",
      className:
        "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
    };
  }
  if (action === "block") {
    return {
      label: "Policy: block",
      className:
        "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
    };
  }
  if (action === "escalate") {
    return {
      label: "Policy: escalate",
      className:
        "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
    };
  }
  return {
    label: "Policy: n/a",
    className: "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
  };
}

export default function ResearchLatestTier2({
  result,
  title = "Latest Tier2 Summary",
  excerptChars = 320,
  className,
  role
}: ResearchLatestTier2Props) {
  if (!result) {
    return (
      <ResearchEmptyState
        className={className}
        title="No Tier2 result yet"
        description="Run a Tier2 query to generate a detailed answer summary for this section."
      />
    );
  }

  const excerpt = toExcerpt(result.answer, excerptChars);
  if (!excerpt) {
    return (
      <ResearchEmptyState
        className={className}
        title="Latest Tier2 answer is empty"
        description="Open Research and run a new Tier2 query to populate this summary."
      />
    );
  }

  const viewerRole = role ?? getRole();
  const policy = policyBadge(result.policyAction);
  const friendlyPolicy = friendlyPolicySummary(result.policyAction);
  const fallbackBadgeClass = result.fallbackUsed
    ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
  // Internal mode strings (e.g. `deep_beta`) are never shown directly; map to a
  // friendly Vietnamese End_User label (Requirement 4.4).
  const internalMode = resolveResearchMode(result);
  const modeLabel = toModeLabel(internalMode);
  const panelClassName = ["chrome-panel rounded-[1.6rem] p-5 sm:p-6", className]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={panelClassName}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Tier2 Output</p>
          <h3 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{title}</h3>
        </div>
        <span className="inline-flex min-h-[38px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-secondary)]">
          Latest
        </span>
      </div>

      {/* End_User-safe summary: friendly mode label + plain-language policy. */}
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
          Chế độ: {modeLabel}
        </span>
        {friendlyPolicy ? (
          <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${friendlyPolicy.className}`}>
            {friendlyPolicy.label}
          </span>
        ) : null}
      </div>

      {/* Detailed runtime telemetry — Admin_Users only (Requirement 4.3). */}
      <TelemetryPanel role={viewerRole} className="mt-3 flex flex-wrap gap-2">
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${policy.className}`}>{policy.label}</span>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${fallbackBadgeClass}`}>
          {result.fallbackUsed ? "Fallback: used" : "Fallback: none"}
        </span>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
          Mode: {internalMode}
        </span>
      </TelemetryPanel>

      <p className="mt-4 text-sm leading-7 text-[var(--text-secondary)]">{excerpt}</p>
    </section>
  );
}
