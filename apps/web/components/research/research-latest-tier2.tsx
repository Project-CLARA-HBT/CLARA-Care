import ResearchEmptyState from "@/components/research/research-empty-state";
import { ResearchTier2Result } from "@/lib/research";

type ResearchLatestTier2Props = {
  result: ResearchTier2Result | null | undefined;
  title?: string;
  excerptChars?: number;
  className?: string;
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

function policyBadge(action?: "allow" | "warn" | "block" | "escalate"): {
  label: string;
  className: string;
} {
  if (action === "warn") {
    return {
      label: "Policy: warn",
      className:
        "border-amber-300/55 bg-amber-100/80 text-amber-800 dark:border-amber-700/45 dark:bg-amber-950/45 dark:text-amber-200"
    };
  }
  if (action === "allow") {
    return {
      label: "Policy: allow",
      className:
        "border-emerald-300/55 bg-emerald-100/80 text-emerald-800 dark:border-emerald-700/45 dark:bg-emerald-950/45 dark:text-emerald-200"
    };
  }
  if (action === "block") {
    return {
      label: "Policy: block",
      className:
        "border-rose-300/55 bg-rose-100/80 text-rose-800 dark:border-rose-700/45 dark:bg-rose-950/45 dark:text-rose-200"
    };
  }
  if (action === "escalate") {
    return {
      label: "Policy: escalate",
      className:
        "border-indigo-300/55 bg-indigo-100/80 text-indigo-800 dark:border-indigo-700/45 dark:bg-indigo-950/45 dark:text-indigo-200"
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
  className
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

  const policy = policyBadge(result.policyAction);
  const fallbackBadgeClass = result.fallbackUsed
    ? "border-amber-300/55 bg-amber-100/80 text-amber-800 dark:border-amber-700/45 dark:bg-amber-950/45 dark:text-amber-200"
    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
  const mode = resolveResearchMode(result);
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

      <div className="mt-3 flex flex-wrap gap-2">
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${policy.className}`}>{policy.label}</span>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${fallbackBadgeClass}`}>
          {result.fallbackUsed ? "Fallback: used" : "Fallback: none"}
        </span>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
          Mode: {mode}
        </span>
      </div>

      <p className="mt-4 text-sm leading-7 text-[var(--text-secondary)]">{excerpt}</p>
    </section>
  );
}
