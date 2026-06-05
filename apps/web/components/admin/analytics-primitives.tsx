import type { ReactNode } from "react";

/**
 * Small, token-driven presentational primitives shared by the Product and
 * Clinical analytics panels: KPI cards, a labeled bar list (for distributions
 * and per-Surface adoption), and a simple sparkline-style trend bar chart.
 *
 * All styling uses design tokens (`--surface-*`, `--shell-border*`,
 * `--text-*`, `--brand-*`, `--status-*`, `--radius-*`) — no hardcoded colors.
 */

export function PanelCard({
  title,
  description,
  children
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={[
        "rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]",
        "bg-[var(--surface-panel)] p-5 shadow-soft"
      ].join(" ")}
    >
      <header className="mb-4">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
        {description ? (
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}

export function KpiCard({
  label,
  value,
  hint
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <article
      className={[
        "rounded-[var(--radius-md)] border border-[color:var(--shell-border)]",
        "bg-[var(--surface-muted)] p-4"
      ].join(" ")}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-2 text-2xl font-bold text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-1 text-xs text-[var(--text-secondary)]">{hint}</p> : null}
    </article>
  );
}

export type BarRow = {
  label: string;
  value: number;
  /** Optional display string; defaults to the numeric value. */
  display?: string;
  tone?: "brand" | "ok" | "warn" | "danger" | "neutral";
};

const TONE_BG: Record<NonNullable<BarRow["tone"]>, string> = {
  brand: "var(--brand-600)",
  ok: "var(--status-ok-text)",
  warn: "var(--status-warn-text)",
  danger: "var(--status-danger-text)",
  neutral: "var(--text-muted)"
};

/**
 * Horizontal bar list used for per-Surface adoption, severity distributions,
 * and verdict distributions. Bar widths are normalized against the max value
 * in the set. Each row exposes its numeric value to assistive tech.
 */
export function BarList({ rows }: { rows: BarRow[] }) {
  const max = rows.reduce((acc, row) => Math.max(acc, row.value), 0);
  return (
    <ul className="space-y-3">
      {rows.map((row) => {
        const pct = max > 0 ? Math.round((row.value / max) * 100) : 0;
        const color = TONE_BG[row.tone ?? "brand"];
        return (
          <li key={row.label}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-[var(--text-secondary)]">{row.label}</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {row.display ?? row.value}
              </span>
            </div>
            <div
              className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--surface-muted)]"
              role="meter"
              aria-valuenow={row.value}
              aria-valuemin={0}
              aria-valuemax={max}
              aria-label={row.label}
            >
              <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Minimal vertical bar chart for a time series (e.g. active-user trend).
 * Renders one column per point; heights are normalized against the max value.
 */
export function TrendBars({
  points
}: {
  points: Array<{ label: string; value: number }>;
}) {
  const max = points.reduce((acc, point) => Math.max(acc, point.value), 0);
  return (
    <div className="flex items-end gap-1.5 overflow-x-auto pb-2" role="img" aria-label="Biểu đồ xu hướng">
      {points.map((point) => {
        const heightPct = max > 0 ? Math.max(6, Math.round((point.value / max) * 100)) : 6;
        return (
          <div key={point.label} className="flex min-w-[16px] flex-1 flex-col items-center gap-1">
            <div className="flex h-28 w-full items-end">
              <div
                className="w-full rounded-t-[var(--radius-sm)] bg-[var(--brand-600)]"
                style={{ height: `${heightPct}%` }}
                title={`${point.label}: ${point.value}`}
              />
            </div>
            <span className="text-[10px] text-[var(--text-muted)]">{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}
