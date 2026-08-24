"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon, { type IconName } from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  computeAuditStats,
  exportAuditLogZeroPii,
  filterAuditRecords,
  getActionCategory,
  getActionCategoryLabel,
  getAdminAuditLog,
  type AdminAuditRecord,
  type AuditActionCategory,
  type AuditFilterParams,
  type AuditOutcome,
} from "@/lib/admin-audit";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * Security Audit Log Explorer (Spec v8 Section 12.6 / Spec v5 Section 6.62 / Requirement 9.4).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Security Audit Log Explorer / System Audit Ledger
 *
 * Dense, immutable, append-only security audit trail explorer providing:
 * 1. High-level Summary KPI Strip (Total Events, Success Rate, High-Risk Events, Unique Actors, Zero-PII status).
 * 2. Multi-dimensional real-time filters (text query, time window, action category, outcome status).
 * 3. Dense, immutable audit ledger table displaying actor, action, resource, IP hash, outcome status, and timestamps.
 * 4. Slide-out inspector drawer with cryptographic witness coordinates and syntax-styled Zero-PII context payload.
 * 5. Zero-PII Export trigger supporting JSON and CSV formats with strict privacy validation.
 * 6. Server-side authoritative RBAC gating for Admin role.
 */

const ACTION_CATEGORY_OPTIONS: Array<{
  value: "all" | AuditActionCategory;
  labelVi: string;
  labelEn: string;
}> = [
  { value: "all", labelVi: "Tất cả danh mục", labelEn: "All Categories" },
  { value: "kb", labelVi: "Kho tri thức (KB)", labelEn: "Knowledge Base (KB)" },
  { value: "rag", labelVi: "RAG & Pipeline", labelEn: "RAG & Pipeline" },
  { value: "user", labelVi: "Người dùng & Phiên", labelEn: "Users & Sessions" },
  { value: "governance", labelVi: "Tuân thủ & DSAR", labelEn: "Compliance & DSAR" },
  { value: "security", labelVi: "Bảo mật & Cảnh báo", labelEn: "Security & Alerts" },
  { value: "other", labelVi: "Khác", labelEn: "Other Operations" },
];

const TIME_RANGE_OPTIONS: Array<{
  value: "all" | "24h" | "7d" | "30d";
  labelVi: string;
  labelEn: string;
}> = [
  { value: "all", labelVi: "Tất cả thời gian", labelEn: "All Time" },
  { value: "24h", labelVi: "24 giờ qua", labelEn: "Last 24 Hours" },
  { value: "7d", labelVi: "7 ngày qua", labelEn: "Last 7 Days" },
  { value: "30d", labelVi: "30 ngày qua", labelEn: "Last 30 Days" },
];

const OUTCOME_OPTIONS: Array<{
  value: "all" | AuditOutcome;
  labelVi: string;
  labelEn: string;
}> = [
  { value: "all", labelVi: "Tất cả kết quả", labelEn: "All Outcomes" },
  { value: "success", labelVi: "Thành công (Success)", labelEn: "Success" },
  { value: "failure", labelVi: "Thất bại (Failure)", labelEn: "Failure" },
  { value: "denied", labelVi: "Bị từ chối (Denied)", labelEn: "Denied" },
  { value: "warning", labelVi: "Cảnh báo (Warning)", labelEn: "Warning" },
];

function getOutcomeStatusMeta(outcome: string, isVi: boolean): {
  tone: StatusTone;
  badgeTone: BadgeTone;
  label: string;
  iconName: IconName;
} {
  const norm = (outcome || "").toLowerCase();
  if (norm === "success") {
    return {
      tone: "success",
      badgeTone: "ok",
      label: isVi ? "Thành công" : "Success",
      iconName: "check",
    };
  }
  if (norm === "denied") {
    return {
      tone: "danger",
      badgeTone: "danger",
      label: isVi ? "Bị từ chối (403)" : "Denied (403)",
      iconName: "warning",
    };
  }
  if (norm === "failure" || norm === "error") {
    return {
      tone: "danger",
      badgeTone: "danger",
      label: isVi ? "Thất bại" : "Failure",
      iconName: "close",
    };
  }
  return {
    tone: "warning",
    badgeTone: "warn",
    label: isVi ? "Cảnh báo" : "Warning",
    iconName: "warning",
  };
}

function getActionBadgeTone(category: AuditActionCategory): BadgeTone {
  switch (category) {
    case "kb":
      return "brand";
    case "rag":
      return "neutral";
    case "user":
      return "warn";
    case "governance":
      return "ok";
    case "security":
      return "danger";
    default:
      return "neutral";
  }
}

export default function SecurityAuditLogPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>(() => getStoredUILanguage());
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [records, setRecords] = useState<AdminAuditRecord[]>([]);

  // Selection & Inspector
  const [selectedRecord, setSelectedRecord] = useState<AdminAuditRecord | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [timeRange, setTimeRange] = useState<"all" | "24h" | "7d" | "30d">("all");
  const [actionCategory, setActionCategory] = useState<"all" | AuditActionCategory>("all");
  const [outcomeFilter, setOutcomeFilter] = useState<"all" | AuditOutcome>("all");

  // Export Modal & Toast State
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<"json" | "csv">("json");
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const isVi = uiLanguage === "vi";

  useEffect(() => {
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getAdminAuditLog(500);
      setRecords(response.records || []);
    } catch (cause) {
      const errText = cause instanceof Error ? cause.message : String(cause);
      setError(sanitizeUpstreamError(errText));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role === "admin") {
      void loadLogs();
    } else if (role !== null) {
      setLoading(false);
    }
  }, [role, loadLogs]);

  // Filtered Records & Statistics
  const filterParams: AuditFilterParams = useMemo(
    () => ({
      query: searchQuery,
      timeRange,
      actionCategory,
      outcome: outcomeFilter,
    }),
    [searchQuery, timeRange, actionCategory, outcomeFilter]
  );

  const filteredRecords = useMemo(
    () => filterAuditRecords(records, filterParams),
    [records, filterParams]
  );

  const stats = useMemo(() => computeAuditStats(records), [records]);

  // Handle Export Trigger
  const handleExport = (format: "json" | "csv") => {
    const targetRecords = filteredRecords.length > 0 ? filteredRecords : records;
    if (targetRecords.length === 0) {
      setNotification({
        type: "error",
        message: isVi
          ? "Không có bản ghi kiểm toán nào để xuất."
          : "No audit records available to export.",
      });
      return;
    }

    const result = exportAuditLogZeroPii(targetRecords, format);
    setExportModalOpen(false);
    setNotification({
      type: "success",
      message: isVi
        ? `Đã xuất ${result.count} bản ghi kiểm toán Zero-PII (${result.filename}) thành công.`
        : `Successfully exported ${result.count} Zero-PII audit records (${result.filename}).`,
    });
  };

  const resetFilters = () => {
    setSearchQuery("");
    setTimeRange("all");
    setActionCategory("all");
    setOutcomeFilter("all");
  };

  const hasActiveFilters =
    Boolean(searchQuery.trim()) ||
    timeRange !== "all" ||
    actionCategory !== "all" ||
    outcomeFilter !== "all";

  // RBAC Access Control Check
  if (role !== null && role !== "admin") {
    return (
      <AdminShell
        activeTab="audit-log"
        title={isVi ? "Nhật ký kiểm toán bảo mật" : "Security Audit Log Explorer"}
        description={
          isVi
            ? "Lịch sử hành động quản trị hệ thống append-only, loại trừ PII hoàn toàn."
            : "Immutable append-only admin audit trail with complete PII exclusion."
        }
      >
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-8 text-center shadow-sm">
          <Icon name="warning" size={40} className="mx-auto mb-3 text-[var(--status-danger-text)]" />
          <h2 className="text-lg font-bold text-[var(--status-danger-text)]">
            {isVi ? "Từ chối quyền truy cập (Access Denied)" : "Access Forbidden"}
          </h2>
          <p className="mt-2 text-sm text-[var(--status-danger-text)] opacity-90 max-w-md mx-auto">
            {isVi
              ? "Bạn không có quyền truy cập Nhật ký Kiểm toán Quản trị. Yêu cầu quyền quản trị viên (Admin) để kiểm tra các bản ghi kiểm toán hệ thống."
              : "You do not have permission to access the Security Audit Log Explorer. Admin role required."}
          </p>
        </div>
      </AdminShell>
    );
  }

  const pageTitle = isVi ? "Nhật ký kiểm toán bảo mật" : "Security Audit Log Explorer";
  const pageDesc = isVi
    ? "Lịch sử kiểm toán hệ thống bất biến (Append-only WAL), lưu trữ tác nhân, hành động, tài nguyên, mã băm IP và loại trừ PII hoàn toàn."
    : "Immutable append-only audit trail explorer capturing actors, actions, resources, IP hashes, outcomes, and strictly zero PII.";

  return (
    <AdminShell activeTab="audit-log" title={pageTitle} description={pageDesc}>
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="Security Audit Log Explorer"
        data-density="dense"
        className="space-y-5"
      >
        {/* Notification Toast */}
        {notification && (
          <div
            role="status"
            className={`flex items-center justify-between gap-3 rounded-[var(--radius-md)] border px-4 py-3 text-xs font-semibold shadow-xs ${
              notification.type === "success"
                ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                : "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
            }`}
          >
            <div className="flex items-center gap-2">
                <Icon
                  name={notification.type === "success" ? "check" : "warning"}
                  size={16}
                  className="shrink-0"
                />
              <span>{notification.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="text-current opacity-70 hover:opacity-100 focus:outline-none"
              aria-label="Close notification"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        )}

        {/* Top Header Strip & Actions */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                {pageTitle}
              </h1>
              <span className="inline-flex items-center rounded-md bg-[var(--surface-muted)] px-2 py-0.5 font-mono text-[11px] font-bold text-[var(--text-muted)] border border-[color:var(--shell-border)]">
                GOV-02
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-[var(--status-ok-bg)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--status-ok-text)] animate-pulse" />
                {isVi ? "Sổ cái bất biến (WAL)" : "Immutable WAL Active"}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {pageDesc}
            </p>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void loadLogs()}
                disabled={loading}
                aria-label={isVi ? "Làm mới nhật ký kiểm toán" : "Refresh audit logs"}
              >
              <Icon
                name="refresh"
                size={14}
                className={`mr-1.5 ${loading ? "animate-spin" : ""}`}
              />
              {isVi ? "Làm mới" : "Refresh"}
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={() => setExportModalOpen(true)}
              aria-label={isVi ? "Xuất kiểm toán Zero-PII" : "Zero-PII export trigger"}
              className="min-h-[36px] text-xs font-semibold shadow-xs"
            >
              <Icon name="download" size={14} className="mr-1.5" />
              {isVi ? "Xuất Zero-PII" : "Zero-PII Export"}
            </Button>
          </div>
        </header>

        {/* Summary KPI Strip */}
        <section aria-label="Audit summary metrics" className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiCard
            label={isVi ? "Tổng sự kiện kiểm toán" : "Total Audit Events"}
            value={String(stats.totalEvents)}
            hint={isVi ? "Append-only ghi nhận" : "Append-only recorded"}
          />
          <KpiCard
            label={isVi ? "Tỷ lệ thành công" : "Success Rate"}
            value={`${stats.successRate}%`}
            hint={
              isVi
                ? `${stats.successCount} thành công`
                : `${stats.successCount} succeeded`
            }
          />
          <KpiCard
            label={isVi ? "Sự kiện an ninh / Rủi ro" : "Security & High-Risk"}
            value={String(stats.highRiskCount)}
            hint={
              isVi
                ? `${stats.deniedCount} từ chối • ${stats.failureCount} lỗi`
                : `${stats.deniedCount} denied • ${stats.failureCount} failed`
            }
          />
          <KpiCard
            label={isVi ? "Tác nhân định danh" : "Unique Actors"}
            value={String(stats.uniqueActors)}
            hint={isVi ? "Mã băm ẩn danh" : "Opaque hashed refs"}
          />
          <KpiCard
            label={isVi ? "Bảo vệ PII & Bất biến" : "PII Redaction & WAL"}
            value="100% Zero-PII"
            hint={isVi ? "SHA-256 IP Masking" : "SHA-256 IP Masked"}
          />
        </section>

        {/* Multi-dimensional Search & Filter Row */}
        <section
          aria-label="Audit log filters"
          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 shadow-xs space-y-3"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-2.5 items-center">
            {/* Search Input */}
            <div className="lg:col-span-4 relative">
              <Icon
                name="search"
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={
                  isVi
                    ? "Tìm tác nhân, hành động, tài nguyên, IP hash, payload..."
                    : "Search actor, action, resource, IP hash, payload..."
                }
                aria-label={isVi ? "Tìm kiếm nhật ký kiểm toán" : "Search audit logs"}
                className="w-full min-h-[38px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] pl-9 pr-8 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-[color:var(--brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--brand-primary)]"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  aria-label="Clear search"
                >
                  <Icon name="close" size={13} />
                </button>
              )}
            </div>

            {/* Time Range Filter */}
            <div className="lg:col-span-3">
              <select
                value={timeRange}
                onChange={(e) =>
                  setTimeRange(e.target.value as "all" | "24h" | "7d" | "30d")
                }
                aria-label={isVi ? "Lọc theo khoảng thời gian" : "Filter by time range"}
                className="w-full min-h-[38px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] px-3 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
              >
                {TIME_RANGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {isVi ? opt.labelVi : opt.labelEn}
                  </option>
                ))}
              </select>
            </div>

            {/* Action Category Filter */}
            <div className="lg:col-span-3">
              <select
                value={actionCategory}
                onChange={(e) =>
                  setActionCategory(e.target.value as "all" | AuditActionCategory)
                }
                aria-label={isVi ? "Lọc theo danh mục hành động" : "Filter by action category"}
                className="w-full min-h-[38px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] px-3 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
              >
                {ACTION_CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {isVi ? opt.labelVi : opt.labelEn}
                  </option>
                ))}
              </select>
            </div>

            {/* Outcome Status Filter */}
            <div className="lg:col-span-2">
              <select
                value={outcomeFilter}
                onChange={(e) =>
                  setOutcomeFilter(e.target.value as "all" | AuditOutcome)
                }
                aria-label={isVi ? "Lọc theo kết quả" : "Filter by outcome status"}
                className="w-full min-h-[38px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] px-3 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
              >
                {OUTCOME_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {isVi ? opt.labelVi : opt.labelEn}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Active Filter Indicators & Reset */}
          {hasActiveFilters && (
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[color:var(--shell-border)] text-xs">
              <span className="text-[var(--text-secondary)]">
                {isVi
                  ? `Hiển thị ${filteredRecords.length} / ${records.length} sự kiện kiểm toán`
                  : `Showing ${filteredRecords.length} of ${records.length} audit events`}
              </span>
              <button
                type="button"
                onClick={resetFilters}
                className="inline-flex items-center gap-1 font-semibold text-[var(--text-brand)] hover:underline"
              >
                <Icon name="close" size={12} />
                {isVi ? "Đặt lại bộ lọc" : "Reset filters"}
              </button>
            </div>
          )}
        </section>

        {/* Error State Banner */}
        {error && (
          <div className="rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-xs font-semibold text-[var(--status-danger-text)]">
            <p>{error}</p>
          </div>
        )}

        {/* Dense Immutable Audit Trail Table */}
        <PanelCard
          title={isVi ? "Sổ cái kiểm toán bảo mật bất biến" : "Immutable Security Audit Ledger"}
          description={
            isVi
              ? "Toàn bộ thao tác quản trị được lưu trữ tuần tự (mới nhất trước). Không thể sửa đổi hay xóa bỏ."
              : "Sequential append-only log of all administrative actions (most-recent-first). Tamper-evident & non-repudiable."
          }
        >
          {loading ? (
            <div className="py-16 text-center text-xs text-[var(--text-muted)]">
              <Icon name="refresh" size={24} className="mx-auto mb-2 animate-spin text-[var(--text-brand)]" />
              <p>{isVi ? "Đang tải nhật ký kiểm toán hệ thống..." : "Loading security audit trail..."}</p>
            </div>
          ) : filteredRecords.length === 0 ? (
            <div className="py-16 text-center text-xs text-[var(--text-muted)] space-y-2">
              <Icon name="search" size={32} className="mx-auto text-[var(--text-muted)] opacity-60" />
              <p className="font-semibold text-sm text-[var(--text-primary)]">
                {isVi ? "Không tìm thấy bản ghi kiểm toán phù hợp" : "No matching audit records found"}
              </p>
              <p className="text-[var(--text-secondary)] max-w-sm mx-auto">
                {hasActiveFilters
                  ? isVi
                    ? "Hãy thử điều chỉnh bộ lọc tìm kiếm hoặc khoảng thời gian để xem thêm kết quả."
                    : "Try adjusting your search terms or filter criteria."
                  : isVi
                  ? "Hệ thống chưa có bản ghi kiểm toán nào được tạo."
                  : "No audit events recorded yet."}
              </p>
              {hasActiveFilters && (
                <Button variant="secondary" size="sm" onClick={resetFilters} className="mt-2 text-xs">
                  {isVi ? "Xóa bộ lọc" : "Clear filters"}
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4 sm:mx-0">
              <table
                className="w-full text-left text-xs border-collapse"
                aria-label={isVi ? "Bảng nhật ký kiểm toán bảo mật" : "Security audit log table"}
              >
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                      {isVi ? "Thời điểm" : "Timestamp"}
                    </th>
                    <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                      {isVi ? "Tác nhân" : "Actor"}
                    </th>
                    <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                      {isVi ? "Hành động" : "Action"}
                    </th>
                    <th scope="col" className="py-2.5 px-3">
                      {isVi ? "Tài nguyên" : "Resource"}
                    </th>
                    <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                      {isVi ? "Mã băm IP" : "IP Hash"}
                    </th>
                    <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                      {isVi ? "Kết quả" : "Outcome"}
                    </th>
                    <th scope="col" className="py-2.5 px-3 text-right whitespace-nowrap">
                      {isVi ? "Thao tác" : "Inspect"}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--shell-border)]">
                  {filteredRecords.map((row) => {
                    const category = getActionCategory(row.action);
                    const outcomeMeta = getOutcomeStatusMeta(String(row.outcome), isVi);
                    const isSelected = selectedRecord?.id === row.id;

                    return (
                      <tr
                        key={row.id}
                        onClick={() => {
                          setSelectedRecord(row);
                          setInspectorOpen(true);
                        }}
                        className={`cursor-pointer transition-colors duration-100 hover:bg-[var(--surface-muted)] ${
                          isSelected ? "bg-[var(--surface-brand-soft)]" : ""
                        }`}
                      >
                        {/* Timestamp */}
                        <td className="py-2.5 px-3 whitespace-nowrap text-[var(--text-secondary)]">
                          {row.created_at
                            ? formatLocaleDate(uiLanguage, row.created_at, {
                                dateStyle: "short",
                                timeStyle: "medium",
                              })
                            : "--"}
                        </td>

                        {/* Actor (Opaque Ref) */}
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <span className="font-mono font-semibold text-[var(--text-primary)]">
                            {row.actor_ref || "--"}
                          </span>
                        </td>

                        {/* Action Verb */}
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <Badge tone={getActionBadgeTone(category)}>
                            {row.action}
                          </Badge>
                        </td>

                        {/* Target Resource */}
                        <td className="py-2.5 px-3 max-w-[200px] truncate text-[var(--text-primary)] font-medium">
                          <span title={row.target || row.resource || ""}>
                            {row.resource || row.target || "--"}
                          </span>
                        </td>

                        {/* IP Hash */}
                        <td className="py-2.5 px-3 whitespace-nowrap font-mono text-[11px] text-[var(--text-muted)]">
                          <span className="inline-flex items-center gap-1">
                            <Icon name="warning" size={11} className="text-[var(--text-muted)]" />
                            {row.ip_hash || "--"}
                          </span>
                        </td>

                        {/* Outcome Status */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <StatusChip tone={outcomeMeta.tone} label={outcomeMeta.label} size="sm" />
                          </td>

                        {/* Inspect Button */}
                        <td className="py-2.5 px-3 text-right whitespace-nowrap">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedRecord(row);
                              setInspectorOpen(true);
                            }}
                            aria-label={`Inspect audit log #${row.id}`}
                            className="text-xs h-7 px-2"
                          >
                            <Icon name="eye" size={13} className="mr-1" />
                            {isVi ? "Xem" : "Inspect"}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </PanelCard>

        {/* Slide-out Event Inspector Drawer */}
        <Inspector
          open={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
          title={
            selectedRecord
              ? isVi
                ? `Chi tiết sự kiện #${selectedRecord.id}`
                : `Audit Event #${selectedRecord.id}`
              : isVi
              ? "Chi tiết kiểm toán"
              : "Audit Detail"
          }
          subtitle={
            selectedRecord
              ? `${selectedRecord.action} • ${
                  selectedRecord.created_at
                    ? formatLocaleDate(uiLanguage, selectedRecord.created_at, {
                        dateStyle: "medium",
                        timeStyle: "medium",
                      })
                    : "--"
                }`
              : undefined
          }
          badge={
            selectedRecord ? (
                <Badge
                  tone={getOutcomeStatusMeta(String(selectedRecord.outcome), isVi).badgeTone}
                >
                {getOutcomeStatusMeta(String(selectedRecord.outcome), isVi).label}
              </Badge>
            ) : undefined
          }
          actions={
            selectedRecord ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  exportAuditLogZeroPii([selectedRecord], "json");
                  setNotification({
                    type: "success",
                    message: isVi
                      ? `Đã xuất sự kiện kiểm toán #${selectedRecord.id} (Zero-PII JSON).`
                      : `Exported audit event #${selectedRecord.id} (Zero-PII JSON).`,
                  });
                }}
                className="text-xs h-7"
              >
                <Icon name="download" size={12} className="mr-1" />
                {isVi ? "Xuất sự kiện" : "Export Event"}
              </Button>
            ) : undefined
          }
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="text-[11px] text-[var(--text-muted)] font-mono">
                WAL_SEQ #{selectedRecord?.id} • ISO 27001
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setInspectorOpen(false)}
                className="text-xs"
              >
                {isVi ? "Đóng" : "Close"}
              </Button>
            </div>
          }
        >
          {selectedRecord ? (
            <div className="space-y-4">
              {/* Event Overview Section */}
              <InspectorSection
                title={isVi ? "Tổng quan sự kiện" : "Event Overview"}
                description={
                  isVi
                    ? "Thông tin cơ bản về hành động quản trị được ghi nhận"
                    : "Core parameters of the logged administrative operation"
                }
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 text-xs">
                  <InspectorField
                    label={isVi ? "Mã sự kiện (ID)" : "Event ID"}
                    value={<span className="font-mono font-bold">#{selectedRecord.id}</span>}
                  />
                  <InspectorField
                    label={isVi ? "Thời điểm (UTC & Local)" : "Timestamp"}
                    value={
                      <span>
                        {selectedRecord.created_at
                          ? formatLocaleDate(uiLanguage, selectedRecord.created_at, {
                              dateStyle: "medium",
                              timeStyle: "medium",
                            })
                          : "--"}
                      </span>
                    }
                    hint={selectedRecord.created_at || undefined}
                  />
                  <InspectorField
                    label={isVi ? "Hành động (Action Verb)" : "Action Verb"}
                    value={
                      <Badge
                        tone={getActionBadgeTone(getActionCategory(selectedRecord.action))}
                      >
                        {selectedRecord.action}
                      </Badge>
                    }
                  />
                  <InspectorField
                    label={isVi ? "Danh mục (Category)" : "Category"}
                    value={
                      <span className="font-semibold text-[var(--text-secondary)]">
                        {getActionCategoryLabel(
                          getActionCategory(selectedRecord.action),
                          isVi ? "vi" : "en"
                        )}
                      </span>
                    }
                  />
                </div>
              </InspectorSection>

              {/* Security & Cryptographic Coordinates */}
              <InspectorSection
                title={isVi ? "Tọa độ an ninh & Định danh" : "Security & Identity Coordinates"}
                description={
                  isVi
                    ? "Định danh tác nhân và chữ ký mạng đã được băm an toàn (Zero-PII)"
                    : "Anonymized actor references and cryptographic IP hash signatures"
                }
              >
                <div className="space-y-2.5 p-3 text-xs">
                  <InspectorField
                    label={isVi ? "Tác nhân (Actor Ref)" : "Actor Reference"}
                    value={
                      <span className="font-mono font-bold text-[var(--text-primary)]">
                        {selectedRecord.actor_ref}
                      </span>
                    }
                    hint={
                      isVi
                        ? "Mã tham chiếu ẩn danh một chiều, không chứa email hay tên người dùng"
                        : "One-way opaque hash reference, excluding names and emails"
                    }
                    copyable
                  />

                  <InspectorField
                    label={isVi ? "Tài nguyên đích (Resource/Target)" : "Target Resource"}
                    value={
                      <span className="font-mono text-[var(--text-primary)]">
                        {selectedRecord.target || selectedRecord.resource || "--"}
                      </span>
                    }
                    copyable
                  />

                  <InspectorField
                    label={isVi ? "Mã băm địa chỉ IP (IP Hash)" : "Client IP Hash (SHA-256)"}
                    value={
                      <span className="font-mono text-[var(--text-secondary)]">
                        {selectedRecord.ip_hash || "--"}
                      </span>
                    }
                    hint={
                      isVi
                        ? "Địa chỉ IP được băm SHA-256 theo Nghị định 13/2023/NĐ-CP"
                        : "Client IP masked via SHA-256 pursuant to privacy regulations"
                    }
                    copyable
                  />

                  <InspectorField
                    label={isVi ? "Cam kết bất biến (Integrity)" : "Immutability Witness"}
                    value={
                      <span className="inline-flex items-center gap-1 text-[var(--status-ok-text)] font-semibold">
                        <Icon name="check" size={13} />
                        APPEND_ONLY_WAL_WITNESS
                      </span>
                    }
                  />
                </div>
              </InspectorSection>

              {/* Zero-PII Meta Payload Section */}
              <InspectorSection
                title={isVi ? "Dữ liệu ngữ cảnh (Zero-PII Payload)" : "Zero-PII Context Payload"}
                description={
                  isVi
                    ? "Các tham số hoạt động, cờ và số lượng (đã loại trừ toàn bộ PII)"
                    : "Operational parameters, counts, and flags with zero personal data"
                }
              >
                <div className="p-3">
                  {Object.keys(selectedRecord.meta || {}).length > 0 ? (
                    <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] p-3">
                      <pre className="text-[11px] font-mono text-[var(--text-secondary)] whitespace-pre-wrap break-all overflow-x-auto leading-relaxed">
                        {JSON.stringify(selectedRecord.meta, null, 2)}
                      </pre>
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--text-muted)] italic">
                      {isVi
                        ? "Không có tham số phụ (Payload trống)"
                        : "No additional metadata payload."}
                    </p>
                  )}
                </div>
              </InspectorSection>

              {/* Compliance Invariant Note */}
              <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-[11px] text-[var(--text-muted)] space-y-1">
                <p className="font-semibold text-[var(--text-secondary)] flex items-center gap-1">
                  <Icon name="warning" size={12} />
                  {isVi ? "Nguyên tắc kiểm toán bất biến" : "Immutability & Zero-PII Policy"}
                </p>
                <p>
                  {isVi
                    ? "Bản ghi kiểm toán này được gắn nhãn bất biến trong cơ sở dữ liệu. Mọi yêu cầu trích xuất tuân thủ Nghị định 13/2023/NĐ-CP và tiêu chuẩn an toàn dữ liệu y tế."
                    : "This record is stored in an immutable append-only ledger. Zero personal health or identifying information is stored or exposed."}
                </p>
              </div>
            </div>
          ) : null}
        </Inspector>

        {/* Zero-PII Export Configuration Modal */}
        <Modal
          open={exportModalOpen}
          onClose={() => setExportModalOpen(false)}
          title={isVi ? "Xuất nhật ký kiểm toán Zero-PII" : "Zero-PII Audit Log Export"}
        >
          <div className="space-y-4 text-xs">
            <p className="text-[var(--text-secondary)]">
              {isVi
                ? `Bạn đang chuẩn bị xuất ${
                    filteredRecords.length > 0 ? filteredRecords.length : records.length
                  } bản ghi kiểm toán. Toàn bộ thông tin định danh cá nhân đã được loại trừ tự động (Zero-PII).`
                : `You are about to export ${
                    filteredRecords.length > 0 ? filteredRecords.length : records.length
                  } audit records. All identifying personal information is automatically redacted (Zero-PII).`}
            </p>

            {/* Format Selection */}
            <div className="space-y-2">
              <label className="block font-bold uppercase tracking-wider text-[var(--text-muted)] text-[11px]">
                {isVi ? "Định dạng tệp trích xuất" : "Export File Format"}
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setExportFormat("json")}
                  className={`flex flex-col items-center justify-center p-3 rounded-[var(--radius-md)] border font-semibold transition-all ${
                    exportFormat === "json"
                      ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <Icon name="download" size={18} className="mb-1" />
                  <span>JSON (Structured)</span>
                  <span className="text-[10px] font-normal opacity-70">
                    {isVi ? "Phù hợp máy đọc & SIEM" : "Machine-readable & SIEM"}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setExportFormat("csv")}
                  className={`flex flex-col items-center justify-center p-3 rounded-[var(--radius-md)] border font-semibold transition-all ${
                    exportFormat === "csv"
                      ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <Icon name="download" size={18} className="mb-1" />
                  <span>CSV (Spreadsheet)</span>
                  <span className="text-[10px] font-normal opacity-70">
                    {isVi ? "Phù hợp Excel & Báo cáo" : "Spreadsheet & Reporting"}
                  </span>
                </button>
              </div>
            </div>

            {/* Privacy Invariant Guarantee */}
            <div className="rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-[11px] text-[var(--status-ok-text)]">
              <span className="font-bold block mb-0.5">
                {isVi ? "Cam kết Zero-PII:" : "Zero-PII Compliance Guarantee:"}
              </span>
              <span>
                {isVi
                  ? "Tệp xuất chỉ chứa mã định danh ẩn danh, mã băm SHA-256 và tham số đếm số học. Tuyệt đối không chứa họ tên, email, câu hỏi hoặc dữ liệu y tế cá nhân."
                  : "The export contains only opaque hashes, SHA-256 signatures, and non-identifying counts. Zero personal or health data is exported."}
              </span>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[color:var(--shell-border)]">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExportModalOpen(false)}
                className="text-xs"
              >
                {isVi ? "Hủy" : "Cancel"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleExport(exportFormat)}
                className="text-xs font-semibold"
              >
                <Icon name="download" size={14} className="mr-1.5" />
                {isVi ? "Tải xuống tệp Zero-PII" : "Download Zero-PII Export"}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AdminShell>
  );
}
