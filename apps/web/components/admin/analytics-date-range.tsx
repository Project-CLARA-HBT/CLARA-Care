"use client";

import { useId } from "react";
import type { AnalyticsRange } from "@/lib/analytics-dashboard";

/**
 * Shared date-range picker for the admin analytics dashboards.
 *
 * Emits a `{ from, to }` ISO-date range that the Product/Clinical panels pass
 * straight through to the admin-gated analytics endpoints. Styling is driven
 * entirely by design tokens (`--surface-*`, `--shell-border*`, `--text-*`,
 * `--brand-*`, `--radius-*`); no hardcoded colors. Inputs carry visible focus
 * rings and Vietnamese labels (Requirement 5.4/5.5).
 */

export type AnalyticsDateRangeProps = {
  value: Required<AnalyticsRange>;
  onChange: (next: Required<AnalyticsRange>) => void;
  /** Invoked when the admin asks to re-run with the current range. */
  onApply: () => void;
  /** Disables the controls while a request is in flight. */
  busy?: boolean;
};

const FIELD_CLASS = [
  "min-h-[44px] rounded-[var(--radius-sm)] border border-[color:var(--shell-border)]",
  "bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-primary)]",
  "transition focus-visible:outline-none focus-visible:ring-2",
  "focus-visible:ring-[color:var(--brand-600)] focus-visible:ring-offset-2",
  "focus-visible:ring-offset-[color:var(--surface-muted)]"
].join(" ");

export function AnalyticsDateRange({
  value,
  onChange,
  onApply,
  busy = false
}: AnalyticsDateRangeProps) {
  const fromId = useId();
  const toId = useId();
  const invalid = Boolean(value.from && value.to && value.from > value.to);

  return (
    <form
      className={[
        "flex flex-wrap items-end gap-3 rounded-[var(--radius-md)]",
        "border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"
      ].join(" ")}
      onSubmit={(event) => {
        event.preventDefault();
        if (!invalid) onApply();
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={fromId} className="text-xs font-semibold text-[var(--text-secondary)]">
          Từ ngày
        </label>
        <input
          id={fromId}
          type="date"
          className={FIELD_CLASS}
          value={value.from}
          max={value.to || undefined}
          onChange={(event) => onChange({ ...value, from: event.target.value })}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={toId} className="text-xs font-semibold text-[var(--text-secondary)]">
          Đến ngày
        </label>
        <input
          id={toId}
          type="date"
          className={FIELD_CLASS}
          value={value.to}
          min={value.from || undefined}
          onChange={(event) => onChange({ ...value, to: event.target.value })}
        />
      </div>

      <button
        type="submit"
        disabled={busy || invalid}
        className={[
          "min-h-[44px] rounded-[var(--radius-sm)] border border-[color:var(--brand-600)]",
          "bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-[#cdd7ff] transition",
          "hover:bg-[var(--brand-700)] focus-visible:outline-none focus-visible:ring-2",
          "focus-visible:ring-[color:var(--brand-600)] focus-visible:ring-offset-2",
          "focus-visible:ring-offset-[color:var(--surface-muted)]",
          "disabled:cursor-not-allowed disabled:opacity-60"
        ].join(" ")}
      >
        {busy ? "Đang tải..." : "Áp dụng"}
      </button>

      {invalid ? (
        <p role="alert" className="w-full text-xs text-[color:var(--status-danger-text)]">
          Khoảng ngày không hợp lệ: ngày bắt đầu phải trước hoặc bằng ngày kết thúc.
        </p>
      ) : null}
    </form>
  );
}

export default AnalyticsDateRange;
