"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import {
  BarList,
  KpiCard,
  PanelCard,
  type BarRow,
} from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  computeFeedbackMetrics,
  exportFeedbackToBenchmark,
  getCategoryMeta,
  getRoleMeta,
  getSeverityMeta,
  getTriageStatusMeta,
  listClinicalFeedback,
  updateFeedbackTriage,
  type ClinicalFeedbackItem,
  type FeedbackCategory,
  type FeedbackRating,
  type FeedbackSeverity,
  type SubmitterRole,
  type TriageStatus,
} from "@/lib/clinical-feedback";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Clinical Feedback Triage Queue (Spec v8 Section 12.8 / Spec v8 Admin Sibling Contracts).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Clinical Feedback Triage Queue
 *
 * A specialized clinical feedback triage workbench that ingests feedback from
 * physicians, clinical pharmacists, specialists, and users. Provides an accuracy
 * rating breakdown, clinical category risk distributions, high-density stream
 * table with multi-dimensional filtering, and a slide-over resolution inspector
 * drawer to audit queries, AI claims, and execute triage actions.
 *
 * Server-side RBAC enforced; zero PII stored or exposed.
 */

export default function ClinicalFeedbackTriagePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackList, setFeedbackList] = useState<ClinicalFeedbackItem[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Inspector & Selection State
  const [selectedItem, setSelectedItem] = useState<ClinicalFeedbackItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Drawer Form State
  const [editStatus, setEditStatus] = useState<TriageStatus>("new");
  const [editSeverity, setEditSeverity] = useState<FeedbackSeverity>("medium");
  const [editAssignedTo, setEditAssignedTo] = useState("");
  const [editResolutionNote, setEditResolutionNote] = useState("");
  const [editRootCause, setEditRootCause] = useState("");

  // Filters State
  const [statusFilter, setStatusFilter] = useState<TriageStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<FeedbackSeverity | "all">("all");
  const [ratingFilter, setRatingFilter] = useState<FeedbackRating | "all">("all");
  const [roleFilter, setRoleFilter] = useState<SubmitterRole | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listClinicalFeedback();
      setFeedbackList(data);
      if (selectedItem) {
        const refreshed = data.find((d) => String(d.id) === String(selectedItem.id));
        if (refreshed) {
          setSelectedItem(refreshed);
        }
      }
    } catch (err) {
      setError(
        safeUserFacingError(
          err,
          uiLanguage === "vi"
            ? "Không thể tải luồng phản hồi lâm sàng. Vui lòng thử lại."
            : "Failed to load clinical feedback stream. Please retry."
        ),
      );
    } finally {
      setLoading(false);
    }
  }, [uiLanguage, selectedItem]);

  useEffect(() => {
    if (role === "admin") {
      void loadData();
    } else if (role !== null) {
      setLoading(false);
    }
  }, [role, loadData]);

  // Open Drawer and initialize edit form
  const handleOpenInspector = (item: ClinicalFeedbackItem) => {
    setSelectedItem(item);
    setEditStatus(item.triage_status);
    setEditSeverity(item.severity);
    setEditAssignedTo(item.assigned_to ?? "");
    setEditResolutionNote(item.resolution_note ?? "");
    setEditRootCause(item.root_cause ?? "");
    setDrawerOpen(true);
  };

  const handleCloseInspector = () => {
    setDrawerOpen(false);
  };

  // Save Triage Updates
  const handleSaveTriage = async (overrideStatus?: TriageStatus) => {
    if (!selectedItem) return;
    setIsSaving(true);
    try {
      const nextStatus = overrideStatus ?? editStatus;
      const updated = await updateFeedbackTriage(selectedItem.id, {
        triage_status: nextStatus,
        severity: editSeverity,
        assigned_to: editAssignedTo.trim() || undefined,
        resolution_note: editResolutionNote.trim() || undefined,
        root_cause: editRootCause.trim() || undefined,
        resolved_at: nextStatus === "resolved" ? new Date().toISOString() : undefined,
      });

      setFeedbackList((prev) =>
        prev.map((item) => (String(item.id) === String(updated.id) ? updated : item)),
      );
      setSelectedItem(updated);
      setEditStatus(updated.triage_status);

      const msg =
        uiLanguage === "vi"
          ? `Đã cập nhật trạng thái phản hồi #${updated.id} thành công.`
          : `Successfully updated feedback #${updated.id} triage status.`;
      setToastMessage(msg);
      setTimeout(() => setToastMessage(null), 4000);

      if (overrideStatus === "resolved") {
        setDrawerOpen(false);
      }
    } catch (err) {
      setError(
        safeUserFacingError(
          err,
          uiLanguage === "vi"
            ? "Lỗi khi lưu thông tin xử lý. Vui lòng thử lại."
            : "Error saving triage resolution. Please retry."
        ),
      );
    } finally {
      setIsSaving(false);
    }
  };

  // Export to RAG Benchmark
  const handleExportToBenchmark = async () => {
    if (!selectedItem) return;
    setIsExporting(true);
    try {
      const res = await exportFeedbackToBenchmark(selectedItem.id);
      if (res.success) {
        const updated: ClinicalFeedbackItem = {
          ...selectedItem,
          added_to_eval_benchmark: true,
        };
        setSelectedItem(updated);
        setFeedbackList((prev) =>
          prev.map((item) => (String(item.id) === String(updated.id) ? updated : item)),
        );
        const msg =
          uiLanguage === "vi"
            ? `Đã xuất phản hồi #${selectedItem.id} sang bộ RAG Golden Benchmark (${res.benchmark_id || "OK"}).`
            : `Exported feedback #${selectedItem.id} to RAG Golden Benchmark (${res.benchmark_id || "OK"}).`;
        setToastMessage(msg);
        setTimeout(() => setToastMessage(null), 4500);
      }
    } catch (err) {
      setError(
        safeUserFacingError(
          err,
          uiLanguage === "vi"
            ? "Không thể xuất sang RAG Benchmark."
            : "Failed to export to RAG Benchmark."
        ),
      );
    } finally {
      setIsExporting(false);
    }
  };

  // Computed Metrics
  const metrics = useMemo(() => computeFeedbackMetrics(feedbackList), [feedbackList]);

  // Filtered List
  const filteredFeedback = useMemo(() => {
    return feedbackList.filter((item) => {
      if (statusFilter !== "all" && item.triage_status !== statusFilter) return false;
      if (severityFilter !== "all" && item.severity !== severityFilter) return false;
      if (ratingFilter !== "all" && item.rating !== ratingFilter) return false;
      if (roleFilter !== "all" && item.submitter_role !== roleFilter) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchId = String(item.id).toLowerCase().includes(q);
        const matchQuery = item.user_query.toLowerCase().includes(q);
        const matchComment = item.comment.toLowerCase().includes(q);
        const matchSpecialty = (item.submitter_specialty ?? "").toLowerCase().includes(q);
        const matchCategory = getCategoryMeta(item.category, uiLanguage).label.toLowerCase().includes(q);
        if (!matchId && !matchQuery && !matchComment && !matchSpecialty && !matchCategory) {
          return false;
        }
      }
      return true;
    });
  }, [feedbackList, statusFilter, severityFilter, ratingFilter, roleFilter, searchQuery, uiLanguage]);

  // Accuracy Rating Distribution Bars
  const ratingDistributionRows: BarRow[] = useMemo(() => {
    const total = metrics.total_feedback || 1;
    return [
      {
        label: uiLanguage === "vi" ? "★★★★★ 5 sao (Rất chính xác)" : "★★★★★ 5 stars (Accurate)",
        value: metrics.rating_breakdown[5],
        display: `${metrics.rating_breakdown[5]} (${Math.round((metrics.rating_breakdown[5] / total) * 100)}%)`,
        tone: "ok",
      },
      {
        label: uiLanguage === "vi" ? "★★★★☆ 4 sao (Chính xác / Tốt)" : "★★★★☆ 4 stars (Good)",
        value: metrics.rating_breakdown[4],
        display: `${metrics.rating_breakdown[4]} (${Math.round((metrics.rating_breakdown[4] / total) * 100)}%)`,
        tone: "ok",
      },
      {
        label: uiLanguage === "vi" ? "★★★☆☆ 3 sao (Cần lưu ý / Nuance)" : "★★★☆☆ 3 stars (Nuanced)",
        value: metrics.rating_breakdown[3],
        display: `${metrics.rating_breakdown[3]} (${Math.round((metrics.rating_breakdown[3] / total) * 100)}%)`,
        tone: "warn",
      },
      {
        label: uiLanguage === "vi" ? "★★☆☆☆ 2 sao (Thiếu chính xác)" : "★★☆☆☆ 2 stars (Inaccurate)",
        value: metrics.rating_breakdown[2],
        display: `${metrics.rating_breakdown[2]} (${Math.round((metrics.rating_breakdown[2] / total) * 100)}%)`,
        tone: "warn",
      },
      {
        label: uiLanguage === "vi" ? "★☆☆☆☆ 1 sao (Sai sót nghiêm trọng)" : "★☆☆☆☆ 1 star (Critical Hazard)",
        value: metrics.rating_breakdown[1],
        display: `${metrics.rating_breakdown[1]} (${Math.round((metrics.rating_breakdown[1] / total) * 100)}%)`,
        tone: "danger",
      },
    ];
  }, [metrics, uiLanguage]);

  // Clinical Risk Category Distribution Bars
  const categoryDistributionRows: BarRow[] = useMemo(() => {
    const total = metrics.total_feedback || 1;
    const categories: FeedbackCategory[] = [
      "dosage_ddi",
      "contraindication",
      "hallucination",
      "citation_mismatch",
      "clinical_nuance",
      "positive_accurate",
    ];

    return categories.map((cat) => {
      const meta = getCategoryMeta(cat, uiLanguage);
      const count = metrics.category_breakdown[cat] ?? 0;
      return {
        label: meta.label,
        value: count,
        display: `${count} (${Math.round((count / total) * 100)}%)`,
        tone: meta.tone,
      };
    });
  }, [metrics, uiLanguage]);

  const pageTitle =
    uiLanguage === "vi"
      ? "Hàng đợi xử lý phản hồi lâm sàng"
      : "Clinical Feedback Triage Queue";
  const pageDescription =
    uiLanguage === "vi"
      ? "Theo dõi phản hồi từ bác sĩ, chuyên gia và người dùng lâm sàng. Phân loại độ chính xác, tiếp nhận và giải quyết sai sót thông tin y tế."
      : "Review clinical user feedback stream, triage medical accuracy ratings, and resolve clinical safety issues.";

  // Defense-in-depth Role Check
  if (role !== null && role !== "admin") {
    return (
      <AdminShell activeTab="feedback" title={pageTitle} description={pageDescription}>
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-6 text-[var(--status-danger-text)] shadow-soft"
        >
          <div className="flex items-center gap-3">
            <Icon name="warning" size={24} className="shrink-0 text-[var(--status-danger-text)]" />
            <div>
              <h2 className="text-base font-semibold">
                {uiLanguage === "vi" ? "Không có quyền truy cập" : "Access Forbidden"}
              </h2>
              <p className="mt-1 text-sm opacity-90">
                {uiLanguage === "vi"
                  ? "Bạn không có quyền truy cập hàng đợi xử lý phản hồi lâm sàng (yêu cầu vai trò Quản trị viên - Admin)."
                  : "You do not have permission to view the Clinical Feedback Triage Queue (Admin role required)."}
              </p>
            </div>
          </div>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell activeTab="feedback" title={pageTitle} description={pageDescription}>
      <div className="space-y-6">
        {/* Toast / Notification Banner */}
        {toastMessage ? (
          <div
            role="status"
            className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-xs sm:text-sm font-semibold text-[var(--status-ok-text)] shadow-sm animate-in fade-in slide-in-from-top-1"
          >
            <div className="flex items-center gap-2">
              <Icon name="check" size={16} />
              <span>{toastMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setToastMessage(null)}
              className="text-xs opacity-75 hover:opacity-100"
              aria-label="Đóng thông báo"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-xs sm:text-sm text-[var(--status-danger-text)] shadow-sm"
          >
            <div className="flex items-center gap-2">
              <Icon name="warning" size={16} />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-xs opacity-75 hover:opacity-100"
              aria-label="Đóng lỗi"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        {/* Top Header & Live Sync Controls */}
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[var(--status-ok-text)] animate-pulse" />
              <h1 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                {pageTitle}
              </h1>
              <Badge tone="brand" className="ml-1 font-mono text-[10px]">
                TRIAGE-Q
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {pageDescription}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon="refresh"
              loading={loading}
              onClick={() => void loadData()}
              aria-label={uiLanguage === "vi" ? "Tải lại danh sách" : "Reload feedback"}
            >
              {uiLanguage === "vi" ? "Làm mới" : "Refresh"}
            </Button>
          </div>
        </header>

        {/* Top-Level Summary KPIs */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <KpiCard
            label={uiLanguage === "vi" ? "Tổng phản hồi" : "Total Feedback"}
            value={loading ? "--" : String(metrics.total_feedback)}
            hint={uiLanguage === "vi" ? "Từ bác sĩ & người dùng" : "From clinicians & users"}
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Điểm chính xác TB" : "Avg Accuracy Rating"}
            value={loading ? "--" : `${metrics.avg_accuracy_rating} / 5.0`}
            hint={
              metrics.avg_accuracy_rating >= 4.0
                ? uiLanguage === "vi"
                  ? "★ Chuẩn xác lâm sàng cao"
                  : "★ High Clinical Concordance"
                : uiLanguage === "vi"
                ? "⚠ Cần lưu ý chất lượng"
                : "⚠ Quality Attention Needed"
            }
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Cần xử lý khẩn (P0/P1)" : "Critical Unresolved (P0/P1)"}
            value={loading ? "--" : String(metrics.unresolved_critical_high)}
            hint={
              metrics.unresolved_critical_high > 0
                ? uiLanguage === "vi"
                  ? "Yêu cầu rà soát ngay"
                  : "Requires Immediate Review"
                : uiLanguage === "vi"
                ? "Không có ca tồn đọng"
                : "Zero Critical Pending"
            }
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Tỷ lệ giải quyết" : "Resolution Rate"}
            value={loading ? "--" : `${metrics.resolution_rate}%`}
            hint={
              uiLanguage === "vi"
                ? `${metrics.status_breakdown.resolved + metrics.status_breakdown.dismissed} / ${metrics.total_feedback} đã xử lý`
                : `${metrics.status_breakdown.resolved + metrics.status_breakdown.dismissed} / ${metrics.total_feedback} triaged`
            }
          />
        </div>

        {/* Distribution Panels: Rating Breakdown & Category Risk Breakdown */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <PanelCard
            title={uiLanguage === "vi" ? "Phân bố đánh giá độ chính xác" : "Accuracy Rating Breakdown"}
            description={
              uiLanguage === "vi"
                ? "Tỷ lệ và số lượng phản hồi theo mức thang điểm chính xác (1 - 5 sao)"
                : "Distribution of feedback items by clinical accuracy scale (1 - 5 stars)"
            }
          >
            <BarList rows={ratingDistributionRows} />
          </PanelCard>

          <PanelCard
            title={uiLanguage === "vi" ? "Phân loại vấn đề & Rủi ro lâm sàng" : "Clinical Risk Category Breakdown"}
            description={
              uiLanguage === "vi"
                ? "Tập trung các nhóm lỗi: tương tác liều lượng, chống chỉ định, ảo giác y văn"
                : "Breakdown of reported issues: DDI/dosage, contraindications, hallucinations"
            }
          >
            <BarList rows={categoryDistributionRows} />
          </PanelCard>
        </div>

        {/* Interactive Filter Toolbar */}
        <section
          aria-label={uiLanguage === "vi" ? "Bộ lọc hàng đợi" : "Queue filters"}
          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft space-y-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Status Pills */}
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Triage Status Filter">
              <span className="text-xs font-semibold text-[var(--text-muted)] mr-1">
                {uiLanguage === "vi" ? "Trạng thái:" : "Status:"}
              </span>
              {(
                [
                  { key: "all", vi: "Tất cả", en: "All" },
                  { key: "new", vi: "Chờ tiếp nhận", en: "Pending" },
                  { key: "in_triage", vi: "Đang điều tra", en: "In Triage" },
                  { key: "resolved", vi: "Đã giải quyết", en: "Resolved" },
                  { key: "dismissed", vi: "Đã bỏ qua", en: "Dismissed" },
                ] as const
              ).map((tab) => {
                const isActive = statusFilter === tab.key;
                const count =
                  tab.key === "all"
                    ? feedbackList.length
                    : metrics.status_breakdown[tab.key];

                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setStatusFilter(tab.key)}
                    className={[
                      "inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border px-2.5 py-1 text-xs font-semibold transition-all",
                      isActive
                        ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-white shadow-xs"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <span>{uiLanguage === "vi" ? tab.vi : tab.en}</span>
                    <span
                      className={[
                        "rounded px-1 text-[10px] font-mono",
                        isActive
                          ? "bg-black/20 text-white"
                          : "bg-[var(--surface-panel)] text-[var(--text-muted)]",
                      ].join(" ")}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Search Input */}
            <div className="relative min-w-[220px] flex-1 max-w-xs">
              <Icon
                name="search"
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={
                  uiLanguage === "vi"
                    ? "Tìm câu hỏi, ghi chú, mã..."
                    : "Search query, notes, ID..."
                }
                className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-1.5 pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
              />
              {searchQuery ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  aria-label="Xóa tìm kiếm"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  <Icon name="close" size={12} />
                </button>
              ) : null}
            </div>
          </div>

          {/* Secondary Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[color:var(--shell-border)]/60 text-xs">
            {/* Severity Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="severity-select" className="font-medium text-[var(--text-secondary)]">
                {uiLanguage === "vi" ? "Mức độ rủi ro:" : "Severity:"}
              </label>
              <select
                id="severity-select"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value as FeedbackSeverity | "all")}
                className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
              >
                <option value="all">{uiLanguage === "vi" ? "Tất cả mức độ" : "All severities"}</option>
                <option value="critical">{uiLanguage === "vi" ? "Nghiêm trọng (P0)" : "Critical (P0)"}</option>
                <option value="high">{uiLanguage === "vi" ? "Cao (P1)" : "High (P1)"}</option>
                <option value="medium">{uiLanguage === "vi" ? "Trung bình (P2)" : "Medium (P2)"}</option>
                <option value="low">{uiLanguage === "vi" ? "Thấp (P3)" : "Low (P3)"}</option>
              </select>
            </div>

            {/* Rating Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="rating-select" className="font-medium text-[var(--text-secondary)]">
                {uiLanguage === "vi" ? "Đánh giá sao:" : "Rating:"}
              </label>
              <select
                id="rating-select"
                value={ratingFilter === "all" ? "all" : String(ratingFilter)}
                onChange={(e) =>
                  setRatingFilter(e.target.value === "all" ? "all" : (Number(e.target.value) as FeedbackRating))
                }
                className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
              >
                <option value="all">{uiLanguage === "vi" ? "Tất cả số sao" : "All ratings"}</option>
                <option value="5">★★★★★ (5)</option>
                <option value="4">★★★★☆ (4)</option>
                <option value="3">★★★☆☆ (3)</option>
                <option value="2">★★☆☆☆ (2)</option>
                <option value="1">★☆☆☆☆ (1)</option>
              </select>
            </div>

            {/* Role Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="role-select" className="font-medium text-[var(--text-secondary)]">
                {uiLanguage === "vi" ? "Người gửi:" : "Submitter:"}
              </label>
              <select
                id="role-select"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value as SubmitterRole | "all")}
                className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
              >
                <option value="all">{uiLanguage === "vi" ? "Tất cả vai trò" : "All submitters"}</option>
                <option value="doctor">{uiLanguage === "vi" ? "Bác sĩ" : "Physician"}</option>
                <option value="specialist">{uiLanguage === "vi" ? "Chuyên gia y khoa" : "Specialist"}</option>
                <option value="pharmacist">{uiLanguage === "vi" ? "Dược sĩ" : "Pharmacist"}</option>
                <option value="researcher">{uiLanguage === "vi" ? "Nghiên cứu viên" : "Researcher"}</option>
                <option value="normal">{uiLanguage === "vi" ? "Người dùng" : "End User"}</option>
              </select>
            </div>

            {(statusFilter !== "all" || severityFilter !== "all" || ratingFilter !== "all" || roleFilter !== "all" || searchQuery) ? (
              <button
                type="button"
                onClick={() => {
                  setStatusFilter("all");
                  setSeverityFilter("all");
                  setRatingFilter("all");
                  setRoleFilter("all");
                  setSearchQuery("");
                }}
                className="text-xs text-[var(--brand-500)] hover:underline ml-auto font-medium"
              >
                {uiLanguage === "vi" ? "Xóa toàn bộ lọc" : "Reset filters"}
              </button>
            ) : null}
          </div>
        </section>

        {/* Clinical User Feedback Stream Table (DENSE layout) */}
        <section
          aria-label={uiLanguage === "vi" ? "Luồng phản hồi lâm sàng" : "Clinical feedback stream"}
          className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-soft"
        >
          <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-3 flex items-center justify-between">
            <h2 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <Icon name="clinical-notes" size={16} className="text-[var(--text-brand)]" />
              <span>
                {uiLanguage === "vi" ? "Hàng đợi tiếp nhận & Xử lý phản hồi" : "Feedback Triage Stream"}
              </span>
              <span className="font-normal text-[var(--text-muted)] text-xs">
                ({filteredFeedback.length} / {feedbackList.length})
              </span>
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 text-[var(--text-muted)] font-semibold uppercase tracking-wider text-[10px]">
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "Mã & Ngày" : "ID & Date"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "Đánh giá" : "Rating"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "Người gửi" : "Submitter"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "Phân loại lỗi" : "Category & Risk"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 min-w-[260px]">
                    {uiLanguage === "vi" ? "Nội dung câu hỏi & Nhận xét lâm sàng" : "Query & Clinical Observation"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "FIDES" : "FIDES"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                    {uiLanguage === "vi" ? "Trạng thái" : "Status"}
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right whitespace-nowrap">
                    {uiLanguage === "vi" ? "Thao tác" : "Actions"}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--shell-border)]/60">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-[var(--text-muted)]">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Icon name="progress" size={24} className="animate-spin text-[var(--text-brand)]" />
                        <span>{uiLanguage === "vi" ? "Đang tải dữ liệu phản hồi..." : "Loading clinical feedback..."}</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredFeedback.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-[var(--text-muted)]">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Icon name="search" size={28} className="text-[var(--text-muted)]" />
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                          {uiLanguage === "vi" ? "Không tìm thấy phản hồi phù hợp" : "No matching feedback found"}
                        </p>
                        <p className="text-xs text-[var(--text-secondary)] max-w-sm">
                          {uiLanguage === "vi"
                            ? "Thử thay đổi bộ lọc trạng thái, số sao hoặc từ khóa tìm kiếm."
                            : "Try adjusting your status filters, rating filters, or search keyword."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredFeedback.map((item) => {
                    const catMeta = getCategoryMeta(item.category, uiLanguage);
                    const sevMeta = getSeverityMeta(item.severity, uiLanguage);
                    const statusMeta = getTriageStatusMeta(item.triage_status, uiLanguage);
                    const roleMeta = getRoleMeta(item.submitter_role, uiLanguage);
                    const isSelected = selectedItem?.id === item.id;

                    const statusToneMap: Record<TriageStatus, StatusTone> = {
                      new: "danger",
                      in_triage: "warning",
                      resolved: "success",
                      dismissed: "unknown",
                    };

                    const badgeToneMap: Record<FeedbackSeverity, BadgeTone> = {
                      critical: "danger",
                      high: "danger",
                      medium: "warn",
                      low: "ok",
                    };

                    return (
                      <tr
                        key={item.id}
                        className={[
                          "transition-colors hover:bg-[var(--surface-muted)]/60 cursor-pointer",
                          isSelected ? "bg-[var(--surface-brand-soft)]/50" : "",
                        ].join(" ")}
                        onClick={() => handleOpenInspector(item)}
                      >
                        {/* ID & Date */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="font-mono font-bold text-[var(--text-brand)]">
                            #{item.id}
                          </div>
                          <div className="text-[10px] text-[var(--text-muted)]">
                            {item.created_at ? formatLocaleDate(uiLanguage, item.created_at) : ""}
                          </div>
                        </td>

                        {/* Rating */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-1 font-semibold text-[var(--text-primary)]">
                            <span className="text-amber-400">
                              {"★".repeat(item.rating)}
                              <span className="text-[var(--text-muted)]/40">
                                {"☆".repeat(5 - item.rating)}
                              </span>
                            </span>
                            <span className="text-[10px] font-mono text-[var(--text-muted)]">
                              ({item.rating})
                            </span>
                          </div>
                        </td>

                        {/* Submitter */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-mono font-bold text-[var(--text-secondary)]">
                              {roleMeta.badge}
                            </span>
                            <span className="font-medium text-[var(--text-primary)]">
                              {roleMeta.label}
                            </span>
                          </div>
                          {item.submitter_specialty ? (
                            <div className="text-[10px] text-[var(--text-muted)] truncate max-w-[120px]">
                              {item.submitter_specialty}
                            </div>
                          ) : null}
                        </td>

                        {/* Category & Severity */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Badge tone={badgeToneMap[item.severity]} className="text-[10px] py-0 px-1.5">
                              {sevMeta.label}
                            </Badge>
                          </div>
                          <div className="mt-1 text-[11px] text-[var(--text-secondary)] font-medium">
                            {catMeta.label}
                          </div>
                        </td>

                        {/* Query & Comment */}
                        <td className="py-3 px-3">
                          <div className="font-medium text-[var(--text-primary)] line-clamp-1">
                            Q: {item.user_query}
                          </div>
                          <div className="mt-0.5 text-[11px] text-[var(--text-muted)] line-clamp-1 italic">
                            &ldquo;{item.comment}&rdquo;
                          </div>
                        </td>

                        {/* FIDES Safety Verdict */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          {item.fides_verdict ? (
                            <span
                              className={[
                                "inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-semibold",
                                item.fides_verdict === "BLOCKED_CRITICAL"
                                  ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border border-[color:var(--status-danger-border)]"
                                  : item.fides_verdict === "CONTESTED"
                                  ? "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border border-[color:var(--status-warn-border)]"
                                  : "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]",
                              ].join(" ")}
                            >
                              {item.fides_verdict}
                            </span>
                          ) : (
                            <span className="text-[10px] text-[var(--text-muted)]">--</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <StatusChip
                            size="sm"
                            tone={statusToneMap[item.triage_status]}
                            label={statusMeta.label}
                          />
                        </td>

                        {/* Action */}
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenInspector(item);
                            }}
                            className="!min-h-[30px] !py-1 !px-2.5 text-xs"
                            aria-label={
                              uiLanguage === "vi"
                                ? `Kiểm tra phản hồi #${item.id}`
                                : `Inspect feedback #${item.id}`
                            }
                          >
                            <Icon name="eye" size={13} />
                            <span>{uiLanguage === "vi" ? "Kiểm tra" : "Inspect"}</span>
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Resolution Inspector Drawer */}
        {selectedItem ? (
          <Inspector
            open={drawerOpen}
            onClose={handleCloseInspector}
            title={
              uiLanguage === "vi"
                ? `Chi tiết phản hồi #${selectedItem.id}`
                : `Feedback Detail #${selectedItem.id}`
            }
            subtitle={
              selectedItem.created_at
                ? uiLanguage === "vi"
                  ? `Tiếp nhận ngày ${formatLocaleDate(uiLanguage, selectedItem.created_at)}`
                  : `Received on ${formatLocaleDate(uiLanguage, selectedItem.created_at)}`
                : ""
            }
            badge={
              <Badge
                tone={
                  selectedItem.severity === "critical" || selectedItem.severity === "high"
                    ? "danger"
                    : selectedItem.severity === "medium"
                    ? "warn"
                    : "ok"
                }
              >
                {getSeverityMeta(selectedItem.severity, uiLanguage).label}
              </Badge>
            }
            badges={
              <div className="flex items-center gap-1.5">
                <span className="text-amber-400 text-xs">
                  {"★".repeat(selectedItem.rating)}
                </span>
                <StatusChip
                  size="sm"
                  tone={
                    selectedItem.triage_status === "resolved"
                      ? "success"
                      : selectedItem.triage_status === "new"
                      ? "danger"
                      : selectedItem.triage_status === "in_triage"
                      ? "warning"
                      : "unknown"
                  }
                  label={getTriageStatusMeta(selectedItem.triage_status, uiLanguage).label}
                />
              </div>
            }
            size="lg"
            density="compact"
            footer={
              <div className="flex flex-wrap items-center justify-between w-full gap-2">
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCloseInspector}
                  >
                    {uiLanguage === "vi" ? "Đóng" : "Close"}
                  </Button>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {!selectedItem.added_to_eval_benchmark ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="check"
                      loading={isExporting}
                      onClick={() => void handleExportToBenchmark()}
                      title={
                        uiLanguage === "vi"
                          ? "Thêm câu hỏi và câu trả lời đã chỉnh sửa vào bộ Golden RAG Benchmark"
                          : "Export question and corrected answer to Golden RAG Benchmark"
                      }
                    >
                      {uiLanguage === "vi" ? "Xuất RAG Golden Set" : "Export RAG Golden"}
                    </Button>
                  ) : (
                    <Badge tone="ok" className="text-xs">
                      {uiLanguage === "vi" ? "✓ Đã đưa vào Golden Set" : "✓ In Golden Benchmark"}
                    </Badge>
                  )}

                  {selectedItem.triage_status !== "resolved" ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={isSaving}
                      onClick={() => void handleSaveTriage("resolved")}
                    >
                      {uiLanguage === "vi" ? "Đánh dấu đã giải quyết" : "Mark as Resolved"}
                    </Button>
                  ) : null}

                  <Button
                    variant="primary"
                    size="sm"
                    loading={isSaving}
                    onClick={() => void handleSaveTriage()}
                  >
                    {uiLanguage === "vi" ? "Lưu xử lý" : "Save Changes"}
                  </Button>
                </div>
              </div>
            }
          >
            <div className="space-y-4">
              {/* Section 1: Submitter & Metadata */}
              <InspectorSection
                title={uiLanguage === "vi" ? "1. Thông tin phản hồi & Người thẩm định" : "1. Feedback & Submitter Metadata"}
                defaultExpanded
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
                  <InspectorField
                    label={uiLanguage === "vi" ? "Mã phản hồi" : "Feedback ID"}
                    value={`#${selectedItem.id}`}
                    copyable
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Mã truy vấn" : "Query ID"}
                    value={selectedItem.query_id ?? "N/A"}
                    copyable
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Người gửi" : "Submitter Role"}
                    value={
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold">{getRoleMeta(selectedItem.submitter_role, uiLanguage).label}</span>
                        {selectedItem.submitter_specialty ? (
                          <span className="text-xs text-[var(--text-muted)]">({selectedItem.submitter_specialty})</span>
                        ) : null}
                      </div>
                    }
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Xếp hạng độ chính xác" : "Accuracy Rating"}
                    value={
                      <div className="flex items-center gap-1">
                        <span className="text-amber-400 font-bold">{"★".repeat(selectedItem.rating)}</span>
                        <span className="text-xs text-[var(--text-muted)]">({selectedItem.rating}/5)</span>
                      </div>
                    }
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Phân loại vấn đề" : "Issue Category"}
                    value={getCategoryMeta(selectedItem.category, uiLanguage).label}
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Đánh giá FIDES" : "FIDES Verdict"}
                    value={
                      selectedItem.fides_verdict ? (
                        <span className="font-mono font-bold text-xs">{selectedItem.fides_verdict}</span>
                      ) : (
                        "--"
                      )
                    }
                  />
                </div>
              </InspectorSection>

              {/* Section 2: Clinical Context & AI Output */}
              <InspectorSection
                title={uiLanguage === "vi" ? "2. Bối cảnh truy vấn & Câu trả lời CLARA" : "2. Clinical Query & CLARA Output"}
                defaultExpanded
              >
                <div className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {uiLanguage === "vi" ? "Câu hỏi lâm sàng của người dùng:" : "User Clinical Query:"}
                    </span>
                    <div className="mt-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs sm:text-sm font-medium text-[var(--text-primary)]">
                      {selectedItem.user_query}
                    </div>
                  </div>

                  <div>
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {uiLanguage === "vi" ? "Câu trả lời do CLARA sinh ra:" : "CLARA Generated Output:"}
                    </span>
                    <div className="mt-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed">
                      {selectedItem.clara_response}
                    </div>
                  </div>

                  {selectedItem.cited_guidelines && selectedItem.cited_guidelines.length > 0 ? (
                    <div>
                      <span className="text-xs font-semibold text-[var(--text-secondary)]">
                        {uiLanguage === "vi" ? "Y văn & Hướng dẫn đối chiếu:" : "Referenced Guidelines & Evidence:"}
                      </span>
                      <ul className="mt-1 space-y-1">
                        {selectedItem.cited_guidelines.map((guideline, idx) => (
                          <li
                            key={idx}
                            className="flex items-start gap-1.5 text-xs text-[var(--text-secondary)]"
                          >
                            <Icon name="clinical-notes" size={13} className="shrink-0 mt-0.5 text-[var(--text-brand)]" />
                            <span>{guideline}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </InspectorSection>

              {/* Section 3: Clinician's Observations & Proposal */}
              <InspectorSection
                title={uiLanguage === "vi" ? "3. Nhận xét chuyên môn & Đề xuất điều chỉnh" : "3. Clinician Observation & Proposal"}
                defaultExpanded
              >
                <div className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {uiLanguage === "vi" ? "Ý kiến chuyên gia y khoa:" : "Clinician Comment:"}
                    </span>
                    <div className="mt-1 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/40 p-3 text-xs sm:text-sm text-[var(--text-primary)]">
                      {selectedItem.comment}
                    </div>
                  </div>

                  {selectedItem.proposed_correction ? (
                    <div>
                      <span className="text-xs font-semibold text-[var(--text-secondary)]">
                        {uiLanguage === "vi" ? "Đề xuất sửa đổi lâm sàng chuẩn:" : "Proposed Clinical Correction:"}
                      </span>
                      <div className="mt-1 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/40 p-3 text-xs sm:text-sm text-[var(--status-ok-text)] font-medium">
                        {selectedItem.proposed_correction}
                      </div>
                    </div>
                  ) : null}
                </div>
              </InspectorSection>

              {/* Section 4: Triage & Resolution Workflow Controls */}
              <InspectorSection
                title={uiLanguage === "vi" ? "4. Xử lý & Phân loại Triage" : "4. Triage Resolution & Workflow"}
                defaultExpanded
              >
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Status selector */}
                    <div>
                      <label htmlFor="triage-status-select" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                        {uiLanguage === "vi" ? "Trạng thái tiếp nhận" : "Triage Status"}
                      </label>
                      <select
                        id="triage-status-select"
                        value={editStatus}
                        onChange={(e) => setEditStatus(e.target.value as TriageStatus)}
                        className="w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      >
                        <option value="new">{uiLanguage === "vi" ? "Chờ tiếp nhận (New)" : "Pending / New"}</option>
                        <option value="in_triage">{uiLanguage === "vi" ? "Đang điều tra (In Triage)" : "In Triage"}</option>
                        <option value="resolved">{uiLanguage === "vi" ? "Đã giải quyết (Resolved)" : "Resolved"}</option>
                        <option value="dismissed">{uiLanguage === "vi" ? "Đã bỏ qua (Dismissed)" : "Dismissed"}</option>
                      </select>
                    </div>

                    {/* Severity selector */}
                    <div>
                      <label htmlFor="severity-level-select" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                        {uiLanguage === "vi" ? "Mức độ ưu tiên" : "Severity Level"}
                      </label>
                      <select
                        id="severity-level-select"
                        value={editSeverity}
                        onChange={(e) => setEditSeverity(e.target.value as FeedbackSeverity)}
                        className="w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                      >
                        <option value="critical">{uiLanguage === "vi" ? "Nghiêm trọng (P0 - Critical)" : "Critical (P0)"}</option>
                        <option value="high">{uiLanguage === "vi" ? "Cao (P1 - High)" : "High (P1)"}</option>
                        <option value="medium">{uiLanguage === "vi" ? "Trung bình (P2 - Medium)" : "Medium (P2)"}</option>
                        <option value="low">{uiLanguage === "vi" ? "Thấp (P3 - Low)" : "Low (P3)"}</option>
                      </select>
                    </div>
                  </div>

                  {/* Assigned Unit */}
                  <div>
                    <label htmlFor="assigned-to-input" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                      {uiLanguage === "vi" ? "Đơn vị / Ban phụ trách" : "Assigned Team / Specialist"}
                    </label>
                    <input
                      id="assigned-to-input"
                      type="text"
                      value={editAssignedTo}
                      onChange={(e) => setEditAssignedTo(e.target.value)}
                      placeholder={
                        uiLanguage === "vi"
                          ? "VD: Hội đồng An toàn Dược lâm sàng"
                          : "e.g. Clinical Safety Board"
                      }
                      className="w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                    />
                  </div>

                  {/* Root Cause Analysis */}
                  <div>
                    <label htmlFor="root-cause-input" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                      {uiLanguage === "vi" ? "Phân tích nguyên nhân gốc rễ" : "Root Cause Analysis"}
                    </label>
                    <input
                      id="root-cause-input"
                      type="text"
                      value={editRootCause}
                      onChange={(e) => setEditRootCause(e.target.value)}
                      placeholder={
                        uiLanguage === "vi"
                          ? "VD: Thiếu rule cảnh báo liều suy thận trong knowledge graph"
                          : "e.g. Missing renal dosing constraint in knowledge graph"
                      }
                      className="w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                    />
                  </div>

                  {/* Resolution Notes */}
                  <div>
                    <label htmlFor="resolution-note-textarea" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                      {uiLanguage === "vi" ? "Ghi chú giải quyết & Biện pháp khắc phục" : "Resolution Notes & Corrective Actions"}
                    </label>
                    <textarea
                      id="resolution-note-textarea"
                      rows={3}
                      value={editResolutionNote}
                      onChange={(e) => setEditResolutionNote(e.target.value)}
                      placeholder={
                        uiLanguage === "vi"
                          ? "Nhập các bước đã khắc phục (đã cập nhật rule FIDES, bổ sung tài liệu guideline mới...)"
                          : "Enter corrective steps (updated FIDES rules, added latest clinical guideline...)"
                      }
                      className="w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
                    />
                  </div>
                </div>
              </InspectorSection>
            </div>
          </Inspector>
        ) : null}
      </div>
    </AdminShell>
  );
}
