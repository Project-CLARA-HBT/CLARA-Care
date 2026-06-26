"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  isDsarEnabled,
  listAdminDsarQueue,
  updateDsarStatus,
  type DsarKind,
  type DsarRequestRecord,
  type DsarStatus,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

/**
 * Admin DSAR queue (regulatory-compliance Requirement 3.6, design §C, Property
 * P7).
 *
 * An admin-only surface that lists every Data Subject Access Request and tracks
 * each against its statutory response window, flagging overdue items. Admins
 * can advance a request's resolution status. The queue rows carry only request
 * type/status/timestamps and an opaque reference — never PII.
 *
 * RBAC is enforced authoritatively by the backend (`/compliance/dsar/admin/*`
 * return 401/403 for non-admin; Property P7). This surface additionally hides
 * itself client-side for non-admin roles and only activates when
 * `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` is on, otherwise current behavior is
 * preserved (Requirement 8.1, 8.2).
 */

const KIND_LABELS: Record<DsarKind, Record<UILanguage, string>> = {
  export: { vi: "Xuất dữ liệu", en: "Export" },
  correct: { vi: "Chỉnh sửa", en: "Correction" },
  delete: { vi: "Xóa", en: "Deletion" },
  restrict: { vi: "Hạn chế xử lý", en: "Restriction" },
  withdraw: { vi: "Rút đồng thuận", en: "Withdraw consent" },
};

const STATUS_LABELS: Record<DsarStatus, Record<UILanguage, string>> = {
  received: { vi: "Đã tiếp nhận", en: "Received" },
  in_progress: { vi: "Đang xử lý", en: "In progress" },
  fulfilled: { vi: "Đã hoàn tất", en: "Fulfilled" },
  rejected: { vi: "Đã từ chối", en: "Rejected" },
};

const STATUS_ORDER: DsarStatus[] = [
  "received",
  "in_progress",
  "fulfilled",
  "rejected",
];

const COPY = {
  vi: {
    title: "Hàng đợi DSAR (Quản trị)",
    description:
      "Theo dõi và xử lý các yêu cầu của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP, đối chiếu với thời hạn luật định.",
    disabled:
      "Tính năng yêu cầu quyền dữ liệu (DSAR) hiện chưa được bật cho môi trường này.",
    forbidden: "Bạn không có quyền truy cập trang quản trị này.",
    loading: "Đang tải hàng đợi...",
    loadError: "Không thể tải hàng đợi DSAR. Vui lòng thử lại.",
    empty: "Chưa có yêu cầu nào trong hàng đợi.",
    overdueBadge: "Quá hạn",
    overdueSummary: (n: number) => `${n} yêu cầu quá hạn`,
    none: "Không có yêu cầu quá hạn",
    submittedAt: "Tiếp nhận",
    dueAt: "Hạn xử lý",
    resolvedAt: "Hoàn tất",
    statusLabel: "Cập nhật trạng thái",
    refId: "Mã yêu cầu",
    saving: "Đang lưu...",
  },
  en: {
    title: "DSAR queue (Admin)",
    description:
      "Monitor and resolve data-subject requests under Decree 13/2023/NĐ-CP, tracked against the statutory response window.",
    disabled: "Data-subject requests (DSAR) are not enabled for this environment yet.",
    forbidden: "You do not have permission to access this admin page.",
    loading: "Loading queue...",
    loadError: "Could not load the DSAR queue. Please try again.",
    empty: "No requests in the queue yet.",
    overdueBadge: "Overdue",
    overdueSummary: (n: number) => `${n} overdue request${n === 1 ? "" : "s"}`,
    none: "No overdue requests",
    submittedAt: "Received",
    dueAt: "Due",
    resolvedAt: "Resolved",
    statusLabel: "Update status",
    refId: "Request ID",
    saving: "Saving...",
  },
} as const;

export default function AdminDsarQueuePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState<number | string | null>(null);
  const [requests, setRequests] = useState<DsarRequestRecord[]>([]);
  const [overdueCount, setOverdueCount] = useState(0);

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);
  const flagOn = isDsarEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    setRoleState(getRole());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const isAdmin = role === "admin";

  const refresh = useCallback(async () => {
    if (!flagOn || !isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listAdminDsarQueue();
      setEnabled(Boolean(data.enabled));
      setRequests(data.requests ?? []);
      setOverdueCount(data.overdue_count ?? 0);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, isAdmin, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onChangeStatus = useCallback(
    async (id: number | string, status: DsarStatus) => {
      setPendingId(id);
      setError("");
      try {
        await updateDsarStatus(id, status);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : text.loadError);
      } finally {
        setPendingId(null);
      }
    },
    [refresh, text.loadError],
  );

  // Role is resolved on mount; treat the brief null state as still loading.
  const roleResolved = role !== null;
  const showForbidden = roleResolved && !isAdmin;
  const showDisabled = !flagOn || (!loading && roleResolved && isAdmin && !enabled);

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-4">
        {showForbidden ? (
          <p
            role="alert"
            className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm font-medium text-[var(--status-danger-text)]"
          >
            {text.forbidden}
          </p>
        ) : showDisabled ? (
          <p
            role="status"
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {text.disabled}
          </p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3">
              <span
                className={[
                  "rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em]",
                  overdueCount > 0
                    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                    : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
                ].join(" ")}
              >
                {overdueCount > 0 ? text.overdueSummary(overdueCount) : text.none}
              </span>
            </div>

            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-danger-text)]"
              >
                {error}
              </p>
            ) : null}

            {loading ? (
              <p className="text-sm text-[var(--text-secondary)]">{text.loading}</p>
            ) : requests.length ? (
              <ul className="space-y-2">
                {requests.map((request) => (
                  <li
                    key={request.id}
                    className={[
                      "rounded-2xl border bg-[var(--surface-panel)] p-4",
                      request.overdue
                        ? "border-[color:var(--status-danger-border)]"
                        : "border-[color:var(--shell-border)]",
                    ].join(" ")}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-bold text-[var(--text-primary)]">
                            {KIND_LABELS[request.kind]?.[uiLanguage] ?? request.kind}
                          </p>
                          {request.overdue ? (
                            <span className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--status-danger-text)]">
                              {text.overdueBadge}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                          {text.refId}: {request.id}
                          {request.created_at
                            ? ` · ${text.submittedAt}: ${new Date(request.created_at).toLocaleString()}`
                            : ""}
                          {request.due_at
                            ? ` · ${text.dueAt}: ${new Date(request.due_at).toLocaleDateString()}`
                            : ""}
                          {request.resolved_at
                            ? ` · ${text.resolvedAt}: ${new Date(request.resolved_at).toLocaleDateString()}`
                            : ""}
                        </p>
                      </div>
                      <label className="flex shrink-0 items-center gap-2 text-[12px] text-[var(--text-secondary)]">
                        <span className="sr-only">{text.statusLabel}</span>
                        <select
                          aria-label={text.statusLabel}
                          disabled={pendingId === request.id}
                          value={request.status}
                          onChange={(e) =>
                            void onChangeStatus(
                              request.id,
                              e.target.value as DsarStatus,
                            )
                          }
                          className="min-h-[36px] rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-sm font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {STATUS_ORDER.map((status) => (
                            <option key={status} value={status}>
                              {STATUS_LABELS[status][uiLanguage]}
                            </option>
                          ))}
                        </select>
                        {pendingId === request.id ? (
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {text.saving}
                          </span>
                        ) : null}
                      </label>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">{text.empty}</p>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
