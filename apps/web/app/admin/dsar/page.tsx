"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
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
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";

/**
 * Admin DSAR queue & compliance workbench (Spec v5 Section 6.66, Requirement 3.6,
 * Property P7).
 *
 * An admin-only surface that lists every Data Subject Access Request in a dense,
 * high-signal table and tracks each against its statutory response window with
 * countdowns, flagging overdue items. Admins can inspect request details, review
 * the audit timeline, and advance resolution status in an inspector drawer.
 *
 * The queue rows carry only request type/status/timestamps and an opaque reference — never PII.
 * RBAC is enforced authoritatively by the backend (`/compliance/dsar/admin/*`).
 */

const KIND_LABEL_KEYS: Record<DsarKind, UITranslationKey> = {
  export: "admin.dsar.kind.export",
  correct: "admin.dsar.kind.correct",
  delete: "admin.dsar.kind.delete",
  restrict: "admin.dsar.kind.restrict",
  withdraw: "admin.dsar.kind.withdraw",
};

const KIND_DESCRIPTIONS: Record<DsarKind, { vi: string; en: string }> = {
  export: {
    vi: "Yêu cầu trích xuất toàn bộ hồ sơ dữ liệu cá nhân theo định dạng máy đọc được.",
    en: "Request to export full personal data profile in machine-readable format.",
  },
  correct: {
    vi: "Yêu cầu đính chính, cập nhật thông tin nhân khẩu hoặc hồ sơ y tế không chính xác.",
    en: "Request to correct or update inaccurate demographic or health record data.",
  },
  delete: {
    vi: "Yêu cầu xóa toàn bộ dữ liệu cá nhân theo quyền được lãng quên (Right to be Forgotten).",
    en: "Request to erase all personal data under the right to be forgotten.",
  },
  restrict: {
    vi: "Yêu cầu tạm thời giới hạn quyền xử lý dữ liệu trong thời gian giải quyết khiếu nại.",
    en: "Request to temporarily restrict data processing during claim review.",
  },
  withdraw: {
    vi: "Rút lại văn bản đồng thuận xử lý dữ liệu y tế đã cấp trước đó.",
    en: "Withdraw previously granted medical data processing consent.",
  },
};

const STATUS_LABEL_KEYS: Record<DsarStatus, UITranslationKey> = {
  received: "admin.dsar.status.received",
  in_progress: "admin.dsar.status.inProgress",
  fulfilled: "admin.dsar.status.fulfilled",
  rejected: "admin.dsar.status.rejected",
};

const STATUS_ORDER: DsarStatus[] = [
  "received",
  "in_progress",
  "fulfilled",
  "rejected",
];

function calculateCountdown(
  dueAt?: string | null,
  resolvedAt?: string | null,
  status?: DsarStatus,
  language: UILanguage = "vi",
): { label: string; tone: "danger" | "warn" | "ok" | "muted"; daysRemaining: number | null } {
  if (status === "fulfilled" || status === "rejected" || resolvedAt) {
    return {
      label: language === "vi" ? "Đã giải quyết" : "Resolved",
      tone: "muted",
      daysRemaining: null,
    };
  }
  if (!dueAt) {
    return { label: "--", tone: "muted", daysRemaining: null };
  }
  const dueDate = new Date(dueAt);
  const dueTime = dueDate.getTime();
  if (Number.isNaN(dueTime)) {
    return { label: "--", tone: "muted", daysRemaining: null };
  }

  const now = Date.now();
  const diffMs = dueTime - now;
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    const overdueDays = Math.abs(diffDays);
    return {
      label: language === "vi" ? `Quá hạn ${overdueDays} ngày` : `Overdue by ${overdueDays}d`,
      tone: "danger",
      daysRemaining: diffDays,
    };
  }
  if (diffDays === 0) {
    return {
      label: language === "vi" ? "Đến hạn hôm nay" : "Due today",
      tone: "warn",
      daysRemaining: 0,
    };
  }
  if (diffDays <= 3) {
    return {
      label: language === "vi" ? `Còn ${diffDays} ngày` : `${diffDays}d left`,
      tone: "warn",
      daysRemaining: diffDays,
    };
  }
  return {
    label: language === "vi" ? `Còn ${diffDays} ngày` : `${diffDays}d left`,
    tone: "ok",
    daysRemaining: diffDays,
  };
}

export default function AdminDsarQueuePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState<number | string | null>(null);
  const [requests, setRequests] = useState<DsarRequestRecord[]>([]);
  const [overdueCount, setOverdueCount] = useState(0);

  // Filters & Drawer State
  const [selectedRequest, setSelectedRequest] = useState<DsarRequestRecord | null>(null);
  const [statusFilter, setStatusFilter] = useState<DsarStatus | "all">("all");
  const [kindFilter, setKindFilter] = useState<DsarKind | "all">("all");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, number>) =>
      t(uiLanguage, key, values),
    [uiLanguage],
  );
  const queueErrorText = copy("admin.dsar.loadError");
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
      const reqList = data.requests ?? [];
      setRequests(reqList);
      setOverdueCount(data.overdue_count ?? 0);

      // Keep selected request synchronized if open
      setSelectedRequest((prev) => {
        if (!prev) return null;
        return reqList.find((r) => String(r.id) === String(prev.id)) ?? prev;
      });
    } catch {
      setError(queueErrorText);
    } finally {
      setLoading(false);
    }
  }, [flagOn, isAdmin, queueErrorText]);

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
      } catch {
        setError(queueErrorText);
      } finally {
        setPendingId(null);
      }
    },
    [queueErrorText, refresh],
  );

  // Filtered requests
  const filteredRequests = useMemo(() => {
    return requests.filter((req) => {
      if (statusFilter !== "all" && req.status !== statusFilter) return false;
      if (kindFilter !== "all" && req.kind !== kindFilter) return false;
      if (overdueOnly && !req.overdue) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        const idMatch = String(req.id).toLowerCase().includes(query);
        const kindLabel = copy(KIND_LABEL_KEYS[req.kind]).toLowerCase();
        if (!idMatch && !kindLabel.includes(query)) return false;
      }
      return true;
    });
  }, [requests, statusFilter, kindFilter, overdueOnly, searchQuery, copy]);

  // Role is resolved on mount; treat the brief null state as still loading.
  const roleResolved = role !== null;
  const showForbidden = roleResolved && !isAdmin;
  const showDisabled = !flagOn || (!loading && roleResolved && isAdmin && !enabled);

  const inProgressCount = useMemo(
    () => requests.filter((r) => r.status === "in_progress").length,
    [requests],
  );
  const fulfilledCount = useMemo(
    () => requests.filter((r) => r.status === "fulfilled").length,
    [requests],
  );

  return (
    <AdminShell
      activeTab="dsar"
      title={copy("admin.dsar.title")}
      description={copy("admin.dsar.description")}
    >
      <div className="space-y-5">
        {showForbidden ? (
          <p
            role="alert"
            className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm font-medium text-[var(--status-danger-text)]"
          >
            {copy("admin.dsar.forbidden")}
          </p>
        ) : showDisabled ? (
          <p
            role="status"
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {copy("admin.dsar.disabled")}
          </p>
        ) : (
          <>
            {/* Top KPI & Urgent Countdown Banner */}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard
                label={uiLanguage === "vi" ? "Tổng yêu cầu" : "Total Requests"}
                value={String(requests.length)}
                hint={uiLanguage === "vi" ? "Hàng đợi luật định PDPD / GDPR" : "Statutory compliance queue"}
              />
              <KpiCard
                label={uiLanguage === "vi" ? "Quá hạn" : "Overdue"}
                value={String(overdueCount)}
                hint={
                  overdueCount > 0
                    ? copy("admin.dsar.overdueSummary", { count: overdueCount })
                    : copy("admin.dsar.none")
                }
              />
              <KpiCard
                label={uiLanguage === "vi" ? "Đang xử lý" : "In Progress"}
                value={String(inProgressCount)}
                hint={uiLanguage === "vi" ? "Đang giải quyết trong hạn luật" : "Within statutory window"}
              />
              <KpiCard
                label={uiLanguage === "vi" ? "Đã hoàn tất" : "Fulfilled"}
                value={String(fulfilledCount)}
                hint={uiLanguage === "vi" ? "Đã phê duyệt / xuất dữ liệu" : "Exported / erased"}
              />
            </div>

            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-danger-text)]"
              >
                {error}
              </p>
            ) : null}

            {/* Filter & Search Command Strip */}
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  {/* Status filter */}
                  <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                    <span className="font-semibold uppercase tracking-wider">{uiLanguage === "vi" ? "Trạng thái:" : "Status:"}</span>
                    <select
                      aria-label="Filter by Status"
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value as DsarStatus | "all")}
                      className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)]"
                    >
                      <option value="all">{uiLanguage === "vi" ? "Tất cả trạng thái" : "All Statuses"}</option>
                      {STATUS_ORDER.map((st) => (
                        <option key={st} value={st}>
                          {copy(STATUS_LABEL_KEYS[st])}
                        </option>
                      ))}
                    </select>
                  </label>

                  {/* Kind filter */}
                  <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                    <span className="font-semibold uppercase tracking-wider">{uiLanguage === "vi" ? "Loại quyền:" : "Kind:"}</span>
                    <select
                      aria-label="Filter by Kind"
                      value={kindFilter}
                      onChange={(e) => setKindFilter(e.target.value as DsarKind | "all")}
                      className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)]"
                    >
                      <option value="all">{uiLanguage === "vi" ? "Tất cả loại quyền" : "All Request Types"}</option>
                      {(["export", "correct", "delete", "restrict", "withdraw"] as DsarKind[]).map((kd) => (
                        <option key={kd} value={kd}>
                          {copy(KIND_LABEL_KEYS[kd])}
                        </option>
                      ))}
                    </select>
                  </label>

                  {/* Overdue toggle */}
                  <label className="flex cursor-pointer items-center gap-1.5 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={overdueOnly}
                      onChange={(e) => setOverdueOnly(e.target.checked)}
                      className="rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-0"
                    />
                    <span className={overdueOnly ? "text-[color:var(--status-danger-text)] font-bold" : ""}>
                      {uiLanguage === "vi" ? "Chỉ quá hạn" : "Overdue only"}
                    </span>
                  </label>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    placeholder={uiLanguage === "vi" ? "Tìm theo mã yêu cầu..." : "Search request ID..."}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="min-h-[34px] w-44 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] sm:w-56"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="refresh"
                    onClick={() => void refresh()}
                    disabled={loading}
                  >
                    {uiLanguage === "vi" ? "Làm mới" : "Refresh"}
                  </Button>
                </div>
              </div>
            </div>

            {/* Main Workbench: Table + Selected Request Inspector */}
            <div className="grid grid-cols-12 gap-5">
              {/* Dense Table Column */}
              <div className={selectedRequest ? "col-span-12 xl:col-span-7" : "col-span-12"}>
                <PanelCard
                  title={uiLanguage === "vi" ? "Hàng đợi xử lý yêu cầu quyền dữ liệu" : "Statutory DSAR Queue"}
                  description={
                    uiLanguage === "vi"
                      ? "Bảng kiểm soát thời hạn phản hồi quy định theo Luật AI & PDPD (Nghị định 13/2023/NĐ-CP)."
                      : "Statutory response window compliance table under AI & Data Privacy regulations."
                  }
                >
                  {loading ? (
                    <p className="py-6 text-center text-sm text-[var(--text-secondary)]">
                      {copy("admin.dsar.loading")}
                    </p>
                  ) : filteredRequests.length === 0 ? (
                    <p className="py-6 text-center text-sm text-[var(--text-muted)]">
                      {copy("admin.dsar.empty")}
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                            <th className="py-2.5 pr-3 font-semibold">{copy("admin.dsar.refId")}</th>
                            <th className="py-2.5 pr-3 font-semibold">{uiLanguage === "vi" ? "Loại quyền" : "Kind"}</th>
                            <th className="py-2.5 pr-3 font-semibold">{uiLanguage === "vi" ? "Trạng thái" : "Status"}</th>
                            <th className="py-2.5 pr-3 font-semibold">{copy("admin.dsar.submittedAt")}</th>
                            <th className="py-2.5 pr-3 font-semibold">{copy("admin.dsar.dueAt")}</th>
                            <th className="py-2.5 pr-3 font-semibold">{uiLanguage === "vi" ? "Đếm ngược hạn" : "Countdown"}</th>
                            <th className="py-2.5 text-right font-semibold">{uiLanguage === "vi" ? "Thao tác" : "Action"}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredRequests.map((request) => {
                            const countdown = calculateCountdown(
                              request.due_at,
                              request.resolved_at,
                              request.status,
                              uiLanguage,
                            );
                            const isSelected = selectedRequest?.id === request.id;

                            return (
                              <tr
                                key={request.id}
                                onClick={() => setSelectedRequest(request)}
                                className={[
                                  "cursor-pointer border-b border-[color:var(--shell-border)] transition last:border-0 hover:bg-[var(--surface-muted)]",
                                  isSelected ? "bg-[var(--surface-brand-soft)]" : "",
                                  request.overdue ? "bg-[var(--status-danger-bg)]/30" : "",
                                ].join(" ")}
                              >
                                <td className="py-2.5 pr-3 font-mono font-bold text-[var(--text-primary)]">
                                  #{request.id}
                                </td>
                                <td className="py-2.5 pr-3">
                                  <span className="font-semibold text-[var(--text-primary)]">
                                    {copy(KIND_LABEL_KEYS[request.kind])}
                                  </span>
                                </td>
                                <td className="py-2.5 pr-3">
                                  <span
                                    className={[
                                      "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                                      request.status === "fulfilled"
                                        ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                                        : request.status === "rejected"
                                          ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                          : request.status === "in_progress"
                                            ? "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                                            : "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
                                    ].join(" ")}
                                  >
                                    {copy(STATUS_LABEL_KEYS[request.status])}
                                  </span>
                                </td>
                                <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                                  {request.created_at
                                    ? formatLocaleDate(uiLanguage, request.created_at, {
                                        dateStyle: "short",
                                        timeStyle: "short",
                                      })
                                    : "--"}
                                </td>
                                <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                                  {request.due_at ? formatLocaleDate(uiLanguage, request.due_at) : "--"}
                                </td>
                                <td className="py-2.5 pr-3">
                                  <span
                                    className={[
                                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold",
                                      countdown.tone === "danger"
                                        ? "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                        : countdown.tone === "warn"
                                          ? "border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                                          : countdown.tone === "ok"
                                            ? "border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                                            : "text-[var(--text-muted)]",
                                    ].join(" ")}
                                  >
                                    {countdown.label}
                                  </span>
                                </td>
                                <td className="py-2.5 text-right">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedRequest(request);
                                    }}
                                    className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                                  >
                                    {uiLanguage === "vi" ? "Chi tiết" : "Inspect"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </PanelCard>
              </div>

              {/* Request Inspector Drawer / Side Sheet */}
              {selectedRequest ? (
                <div className="col-span-12 xl:col-span-5">
                  <div className="rounded-[var(--radius-lg)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
                    {/* Header */}
                    <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-[var(--text-primary)]">
                            #{selectedRequest.id}
                          </span>
                          <span className="rounded-md bg-[var(--surface-brand-soft)] px-2 py-0.5 text-xs font-semibold text-[var(--text-brand)]">
                            {copy(KIND_LABEL_KEYS[selectedRequest.kind])}
                          </span>
                          {selectedRequest.overdue ? (
                            <span className="rounded-md border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--status-danger-text)]">
                              {copy("admin.dsar.overdueBadge")}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          {KIND_DESCRIPTIONS[selectedRequest.kind]?.[uiLanguage] ?? ""}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="close"
                        aria-label={uiLanguage === "vi" ? "Đóng inspector" : "Close inspector"}
                        onClick={() => setSelectedRequest(null)}
                      />
                    </div>

                    <div className="mt-4 space-y-4">
                      {/* Statutory Deadline Countdown Box */}
                      {(() => {
                        const cd = calculateCountdown(
                          selectedRequest.due_at,
                          selectedRequest.resolved_at,
                          selectedRequest.status,
                          uiLanguage,
                        );
                        return (
                          <div
                            className={[
                              "rounded-[var(--radius-md)] border p-3.5",
                              cd.tone === "danger"
                                ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]"
                                : cd.tone === "warn"
                                  ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]"
                                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
                            ].join(" ")}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                                {uiLanguage === "vi" ? "Thời hạn phản hồi luật định" : "Statutory Response Window"}
                              </span>
                              <span
                                className={[
                                  "rounded-full px-2.5 py-0.5 text-xs font-bold",
                                  cd.tone === "danger"
                                    ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                    : cd.tone === "warn"
                                      ? "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                                      : "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
                                ].join(" ")}
                              >
                                {cd.label}
                              </span>
                            </div>
                            <p className="mt-2 text-xs text-[var(--text-secondary)]">
                              {uiLanguage === "vi"
                                ? "Thời hạn xử lý tối đa theo Nghị định 13/2023/NĐ-CP (72 giờ / 30 ngày tùy theo loại quyền)."
                                : "Mandatory response timeframes under statutory privacy requirements."}
                            </p>
                          </div>
                        );
                      })()}

                      {/* Timeline Progression */}
                      <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                          {uiLanguage === "vi" ? "Tiến trình thời gian" : "Action Timeline"}
                        </p>
                        <ul className="mt-3 space-y-2.5 text-xs">
                          <li className="flex items-center justify-between">
                            <span className="text-[var(--text-secondary)]">{copy("admin.dsar.submittedAt")}:</span>
                            <span className="font-semibold text-[var(--text-primary)]">
                              {selectedRequest.created_at
                                ? formatLocaleDate(uiLanguage, selectedRequest.created_at, {
                                    dateStyle: "medium",
                                    timeStyle: "short",
                                  })
                                : "--"}
                            </span>
                          </li>
                          <li className="flex items-center justify-between">
                            <span className="text-[var(--text-secondary)]">{copy("admin.dsar.dueAt")}:</span>
                            <span className="font-semibold text-[var(--text-primary)]">
                              {selectedRequest.due_at
                                ? formatLocaleDate(uiLanguage, selectedRequest.due_at)
                                : "--"}
                            </span>
                          </li>
                          {selectedRequest.resolved_at ? (
                            <li className="flex items-center justify-between">
                              <span className="text-[var(--text-secondary)]">{copy("admin.dsar.resolvedAt")}:</span>
                              <span className="font-semibold text-[var(--status-ok-text)]">
                                {formatLocaleDate(uiLanguage, selectedRequest.resolved_at, {
                                  dateStyle: "medium",
                                  timeStyle: "short",
                                })}
                              </span>
                            </li>
                          ) : null}
                        </ul>
                      </div>

                      {/* Status Transition Control */}
                      <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                        <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                          {copy("admin.dsar.statusLabel")}
                        </label>
                        <div className="mt-2 flex items-center gap-2">
                          <select
                            aria-label={copy("admin.dsar.statusLabel")}
                            disabled={pendingId === selectedRequest.id}
                            value={selectedRequest.status}
                            onChange={(e) =>
                              void onChangeStatus(
                                selectedRequest.id,
                                e.target.value as DsarStatus,
                              )
                            }
                            className="min-h-[38px] flex-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] disabled:opacity-60"
                          >
                            {STATUS_ORDER.map((status) => (
                              <option key={status} value={status}>
                                {copy(STATUS_LABEL_KEYS[status])}
                              </option>
                            ))}
                          </select>
                          {pendingId === selectedRequest.id ? (
                            <span className="text-xs text-[var(--text-muted)]">
                              {copy("admin.dsar.saving")}
                            </span>
                          ) : null}
                        </div>
                      </div>

                      {/* Zero-PII Audit Note */}
                      <div className="flex items-start gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-[11px] text-[var(--text-muted)]">
                        <Icon name="check" size="1rem" className="mt-0.5 shrink-0 text-[var(--text-brand)]" />
                        <p>
                          {uiLanguage === "vi"
                            ? "Bản ghi này tuân thủ Zero-PII: Không lưu trữ hoặc tiết lộ tên, email hoặc thông tin nhận dạng trực tiếp trên giao diện quản trị."
                            : "Zero-PII compliant: No personal identifiers, email addresses, or health telemetry are rendered in this view."}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </>
        )}
      </div>
    </AdminShell>
  );
}
