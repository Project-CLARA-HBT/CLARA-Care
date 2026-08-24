"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import { PanelCard } from "@/components/admin/analytics-primitives";
import { getAdminAuditLog, type AdminAuditRecord } from "@/lib/admin-audit";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * Admin-action audit-log panel (Requirement 9.4).
 *
 * Lists the append-only admin-action audit records most-recent-first through
 * the four mutually-exclusive AsyncSection states (loading / empty / error /
 * populated). Error copy is routed through `sanitizeUpstreamError` so no raw
 * upstream detail (codes, stack traces, internal URLs) reaches the admin view.
 *
 * The records are PII-free by construction (opaque `actor_ref` + a PII-projected
 * `meta`), so the view shows only opaque references, bounded action/target/
 * outcome strings, counts/flags, and timestamps. While `ADMIN_AUDIT_LOG_ENABLED`
 * is off the endpoint returns a feature-disabled 404, surfaced here as the
 * sanitized error state. All styling uses design tokens.
 */

function buildState(
  loading: boolean,
  error: string,
  records: AdminAuditRecord[] | null
): AsyncState<AdminAuditRecord[]> {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: error };
  if (!records || records.length === 0) return { kind: "empty" };
  return { kind: "populated", data: records };
}

function formatTimestamp(value: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("vi-VN");
}

function formatMeta(meta: Record<string, unknown>): string {
  const keys = Object.keys(meta ?? {});
  if (keys.length === 0) return "--";
  try {
    return JSON.stringify(meta);
  } catch {
    return "--";
  }
}

export function AdminAuditPanel() {
  const [records, setRecords] = useState<AdminAuditRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminAuditLog();
      setRecords(result.records);
    } catch (cause) {
      setRecords(null);
      setError(sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Emit a single coarse, no-PII Admin view event when the audit log is opened.
  // The audit trail is an operability/observability surface, so it reuses the
  // existing `observability` view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "observability" });
  }, []);

  const state = useMemo(() => buildState(loading, error, records), [loading, error, records]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className={[
            "rounded-[var(--radius-md)] border border-[color:var(--shell-border)]",
            "bg-[var(--surface-muted)] px-3 py-1.5 text-sm font-semibold text-[var(--text-secondary)]",
            "transition hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
          ].join(" ")}
        >
          Làm mới
        </button>
      </div>

      <AsyncSection<AdminAuditRecord[]>
        state={state}
        loadingLabel="Đang tải nhật ký kiểm toán..."
        emptyTitle="Chưa có bản ghi kiểm toán"
        emptyDescription="Chưa có hành động quản trị nào được ghi nhận. Các thao tác quản trị sẽ xuất hiện ở đây."
      >
        {(rows) => <AdminAuditTable rows={rows} />}
      </AsyncSection>
    </div>
  );
}

function AdminAuditTable({ rows }: { rows: AdminAuditRecord[] }) {
  return (
    <PanelCard
      title="Nhật ký hành động quản trị"
      description="Các hành động quản trị được ghi nhận, mới nhất trước. Không chứa thông tin định danh (PII)."
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
              <th className="py-2 pr-4 font-semibold">Thời điểm</th>
              <th className="py-2 pr-4 font-semibold">Hành động</th>
              <th className="py-2 pr-4 font-semibold">Đối tượng</th>
              <th className="py-2 pr-4 font-semibold">Kết quả</th>
              <th className="py-2 pr-4 font-semibold">Tác nhân</th>
              <th className="py-2 font-semibold">Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-[color:var(--shell-border)] last:border-0"
              >
                <td className="py-2 pr-4 text-[var(--text-secondary)]">
                  {formatTimestamp(row.created_at)}
                </td>
                <td className="py-2 pr-4 font-medium text-[var(--text-primary)]">{row.action}</td>
                <td className="py-2 pr-4 text-[var(--text-secondary)]">{row.target || "--"}</td>
                <td className="py-2 pr-4">
                  <span
                    className={[
                      "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold",
                      row.outcome === "failure"
                        ? "bg-[var(--status-danger-bg)] text-[color:var(--status-danger-text)]"
                        : "bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                    ].join(" ")}
                  >
                    {row.outcome || "--"}
                  </span>
                </td>
                <td className="py-2 pr-4 font-mono text-xs text-[var(--text-muted)]">
                  {row.actor_ref || "--"}
                </td>
                <td className="py-2 font-mono text-xs text-[var(--text-muted)]">
                  {formatMeta(row.meta)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
}

export default AdminAuditPanel;
