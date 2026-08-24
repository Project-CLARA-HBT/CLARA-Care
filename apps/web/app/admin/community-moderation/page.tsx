"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import { InlineError } from "@/components/ui/surface";
import {
  SocialReport,
  actOnReport,
  listReports,
  SocialUnavailableError,
} from "@/lib/social";
import { getStoredUILanguage, type UILanguage, onUILanguageChange } from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";

/**
 * Admin Moderation Workbench (Spec v8 Section 12.11, Spec v5 Section 6.65).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Community Moderation Workbench
 *
 * Dedicated admin workbench to inspect community moderation queues, preview reported
 * posts and comments, and execute audited actions (dismiss report / remove violating content)
 * with mandatory confirmation dialogs for irreversible operations.
 *
 * Server-side RBAC is enforced authoritatively; every action is logged into the Zero-PII
 * audit trail without storing user identity.
 */

type ReasonInfo = {
  labelVi: string;
  labelEn: string;
  severity: "high" | "medium" | "low";
  descriptionVi: string;
  descriptionEn: string;
};

const REASON_METADATA: Record<string, ReasonInfo> = {
  spam: {
    labelVi: "Spam & Quảng cáo",
    labelEn: "Spam & Promotional",
    severity: "medium",
    descriptionVi: "Nội dung quảng cáo sai quy định, liên kết ngoài độc hại hoặc tin nhắn lặp lại liên tục.",
    descriptionEn: "Unsolicited promotion, suspicious external links, or bulk repetitive posting.",
  },
  harassment: {
    labelVi: "Quấy rối & Thù ghét",
    labelEn: "Harassment & Hate",
    severity: "high",
    descriptionVi: "Lời lẽ xúc phạm cá nhân, công kích thành viên hoặc đe dọa an toàn cộng đồng.",
    descriptionEn: "Personal attacks, bullying, hateful remarks, or safety threats.",
  },
  user_report: {
    labelVi: "Người dùng báo cáo",
    labelEn: "User Flagged",
    severity: "medium",
    descriptionVi: "Thành viên cộng đồng gửi khiếu nại về nội dung không phù hợp với tiêu chuẩn y tế.",
    descriptionEn: "Community member complaint regarding inappropriate or misleading health content.",
  },
};

function getReasonInfo(reason: string): ReasonInfo {
  return (
    REASON_METADATA[reason] ?? {
      labelVi: reason || "Khác",
      labelEn: reason || "Other",
      severity: "low",
      descriptionVi: "Báo cáo nội dung vi phạm quy tắc chung của cộng đồng CLARA Care.",
      descriptionEn: "General complaint regarding community guidelines.",
    }
  );
}

export default function CommunityModerationPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<SocialReport[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  // Filters & Inspector State
  const [selectedReport, setSelectedReport] = useState<SocialReport | null>(null);
  const [reasonFilter, setReasonFilter] = useState<string>("all");
  const [targetTypeFilter, setTargetTypeFilter] = useState<"all" | "post" | "comment">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Confirmation Modal State
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    report: SocialReport | null;
    action: "dismiss" | "remove" | null;
  }>({
    open: false,
    report: null,
    action: null,
  });

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listReports();
      setReports(data);
      setSelectedReport((prev) => {
        if (!prev) return null;
        return data.find((r) => r.id === prev.id) ?? null;
      });
    } catch (err) {
      if (err instanceof SocialUnavailableError) {
        setUnavailable(true);
      } else {
        setError(
          uiLanguage === "vi"
            ? "Không thể tải hàng đợi kiểm duyệt."
            : "Failed to load moderation queue.",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [uiLanguage]);

  useEffect(() => {
    void load();
  }, [load]);

  const executeAction = useCallback(async () => {
    if (!confirmModal.report || !confirmModal.action) return;
    const { report, action } = confirmModal;
    setBusyId(report.id);
    try {
      await actOnReport(report.id, action);
      setReports((prev) => prev.filter((r) => r.id !== report.id));
      if (selectedReport?.id === report.id) {
        setSelectedReport(null);
      }
      setConfirmModal({ open: false, report: null, action: null });
    } catch {
      setError(
        uiLanguage === "vi"
          ? "Không thể xử lý báo cáo. Vui lòng thử lại."
          : "Failed to process report. Please retry.",
      );
    } finally {
      setBusyId(null);
    }
  }, [confirmModal, selectedReport, uiLanguage]);

  const promptAction = (report: SocialReport, action: "dismiss" | "remove") => {
    setConfirmModal({
      open: true,
      report,
      action,
    });
  };

  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      if (reasonFilter !== "all" && r.reason !== reasonFilter) return false;
      if (targetTypeFilter !== "all" && r.target_type !== targetTypeFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const idMatch = String(r.id).includes(q) || String(r.target_id).includes(q);
        const reasonMatch = r.reason.toLowerCase().includes(q);
        if (!idMatch && !reasonMatch) return false;
      }
      return true;
    });
  }, [reports, reasonFilter, targetTypeFilter, searchQuery]);

  const postReportsCount = useMemo(
    () => reports.filter((r) => r.target_type === "post").length,
    [reports],
  );
  const commentReportsCount = useMemo(
    () => reports.filter((r) => r.target_type === "comment").length,
    [reports],
  );
  const highSeverityCount = useMemo(
    () =>
      reports.filter((r) => getReasonInfo(r.reason).severity === "high").length,
    [reports],
  );

  const title = uiLanguage === "vi" ? "Kiểm duyệt cộng đồng" : "Community Moderation";
  const description =
    uiLanguage === "vi"
      ? "Xem xét các báo cáo nội dung. Gỡ nội dung vi phạm hoặc bỏ qua báo cáo."
      : "Review content violation reports. Remove violating items or dismiss reports.";

  if (unavailable) {
    return (
      <AdminShell activeTab="community-moderation" title={title} description={description}>
        <div
          role="status"
          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-6 text-center shadow-soft"
        >
          <Icon name="warning" size={32} className="mx-auto text-[var(--text-muted)]" />
          <p className="mt-2 text-sm font-semibold text-[var(--text-secondary)]">
            {uiLanguage === "vi" ? "Tính năng cộng đồng đang tắt." : "Community platform is currently disabled."}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {uiLanguage === "vi"
              ? "Cờ SOCIAL_PLATFORM_ENABLED hiện đang tắt trong môi trường này."
              : "The SOCIAL_PLATFORM_ENABLED flag is off for this environment."}
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell activeTab="community-moderation" title={title} description={description}>
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="Community Moderation Workbench"
        data-density="DENSE"
        className="space-y-5"
      >
        {error ? <InlineError message={error} /> : null}

        {/* Top KPI Cards */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label={uiLanguage === "vi" ? "Báo cáo chờ duyệt" : "Pending Reports"}
            value={String(reports.length)}
            hint={uiLanguage === "vi" ? "Hàng đợi kiểm duyệt trực tiếp" : "Active moderation queue"}
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Bài viết bị báo cáo" : "Reported Posts"}
            value={String(postReportsCount)}
            hint={uiLanguage === "vi" ? "Bài đăng cộng đồng" : "Feed post targets"}
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Bình luận bị báo cáo" : "Reported Comments"}
            value={String(commentReportsCount)}
            hint={uiLanguage === "vi" ? "Bình luận thảo luận" : "Comment thread targets"}
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Vi phạm nghiêm trọng" : "High Severity"}
            value={String(highSeverityCount)}
            hint={uiLanguage === "vi" ? "Quấy rối / Đe dọa an toàn" : "Harassment / Safety threats"}
          />
        </div>

        {/* Filter Toolbar */}
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {/* Reason Filter */}
              <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">
                  {uiLanguage === "vi" ? "Lý do:" : "Reason:"}
                </span>
                <select
                  aria-label="Filter by Reason"
                  value={reasonFilter}
                  onChange={(e) => setReasonFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)]"
                >
                  <option value="all">{uiLanguage === "vi" ? "Tất cả lý do" : "All Reasons"}</option>
                  <option value="user_report">{uiLanguage === "vi" ? "Người dùng báo cáo" : "User Report"}</option>
                  <option value="spam">{uiLanguage === "vi" ? "Spam & Quảng cáo" : "Spam"}</option>
                  <option value="harassment">{uiLanguage === "vi" ? "Quấy rối & Thù ghét" : "Harassment"}</option>
                </select>
              </label>

              {/* Target Type Filter */}
              <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">
                  {uiLanguage === "vi" ? "Đối tượng:" : "Target:"}
                </span>
                <select
                  aria-label="Filter by Target"
                  value={targetTypeFilter}
                  onChange={(e) => setTargetTypeFilter(e.target.value as "all" | "post" | "comment")}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)]"
                >
                  <option value="all">{uiLanguage === "vi" ? "Tất cả đối tượng" : "All Target Types"}</option>
                  <option value="post">{uiLanguage === "vi" ? "Bài viết" : "Posts"}</option>
                  <option value="comment">{uiLanguage === "vi" ? "Bình luận" : "Comments"}</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder={uiLanguage === "vi" ? "Tìm theo mã báo cáo / đối tượng..." : "Search report / target ID..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="min-h-[34px] w-48 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] sm:w-64"
              />
              <Button
                variant="secondary"
                size="sm"
                icon="refresh"
                onClick={() => void load()}
                disabled={loading}
              >
                {uiLanguage === "vi" ? "Làm mới" : "Refresh"}
              </Button>
            </div>
          </div>
        </div>

        {/* Main Workbench Split Layout */}
        <div className="grid grid-cols-12 gap-5">
          {/* Dense Table Column */}
          <div className={selectedReport ? "col-span-12 xl:col-span-7" : "col-span-12"}>
            <PanelCard
              title={uiLanguage === "vi" ? "Hàng đợi báo cáo vi phạm cộng đồng" : "Community Moderation Queue"}
              description={
                uiLanguage === "vi"
                  ? "Danh sách báo cáo từ thành viên và hệ thống kiểm duyệt tự động."
                  : "Queue of user complaints and automated safety violation triggers."
              }
            >
              {loading ? (
                <p className="py-6 text-center text-sm text-[var(--text-secondary)]">
                  {uiLanguage === "vi" ? "Đang tải hàng đợi kiểm duyệt…" : "Loading moderation queue..."}
                </p>
              ) : filteredReports.length === 0 ? (
                <p className="py-6 text-center text-sm text-[var(--text-muted)]">
                  {uiLanguage === "vi"
                    ? "Không có báo cáo nào đang chờ xử lý."
                    : "No pending moderation reports."}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                        <th className="py-2.5 pr-3 font-semibold">
                          {uiLanguage === "vi" ? "Mã báo cáo" : "Report ID"}
                        </th>
                        <th className="py-2.5 pr-3 font-semibold">
                          {uiLanguage === "vi" ? "Đối tượng" : "Target"}
                        </th>
                        <th className="py-2.5 pr-3 font-semibold">
                          {uiLanguage === "vi" ? "Lý do" : "Reason"}
                        </th>
                        <th className="py-2.5 pr-3 font-semibold">
                          {uiLanguage === "vi" ? "Thời gian" : "Time"}
                        </th>
                        <th className="py-2.5 text-right font-semibold">
                          {uiLanguage === "vi" ? "Thao tác" : "Actions"}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredReports.map((report) => {
                        const reasonInfo = getReasonInfo(report.reason);
                        const isSelected = selectedReport?.id === report.id;

                        return (
                          <tr
                            key={report.id}
                            onClick={() => setSelectedReport(report)}
                            className={[
                              "cursor-pointer border-b border-[color:var(--shell-border)] transition last:border-0 hover:bg-[var(--surface-muted)]",
                              isSelected ? "bg-[var(--surface-brand-soft)]" : "",
                            ].join(" ")}
                          >
                            <td className="py-2.5 pr-3 font-mono font-bold text-[var(--text-primary)]">
                              #{report.id}
                            </td>
                            <td className="py-2.5 pr-3">
                              <span className="font-semibold text-[var(--text-primary)]">
                                {report.target_type === "post"
                                  ? uiLanguage === "vi"
                                    ? "Bài viết"
                                    : "Post"
                                  : uiLanguage === "vi"
                                    ? "Bình luận"
                                    : "Comment"}{" "}
                                #{report.target_id}
                              </span>
                            </td>
                            <td className="py-2.5 pr-3">
                              <span
                                className={[
                                  "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold",
                                  reasonInfo.severity === "high"
                                    ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                    : reasonInfo.severity === "medium"
                                      ? "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                                      : "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
                                ].join(" ")}
                              >
                                {uiLanguage === "vi" ? reasonInfo.labelVi : reasonInfo.labelEn}
                              </span>
                            </td>
                            <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                              {report.created_at
                                ? formatLocaleDate(uiLanguage, report.created_at, {
                                    dateStyle: "short",
                                    timeStyle: "short",
                                  })
                                : "--"}
                            </td>
                            <td className="py-2.5 text-right">
                              <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setSelectedReport(report)}
                                  className="!min-h-[28px] !px-2 text-xs"
                                >
                                  {uiLanguage === "vi" ? "Xem" : "Inspect"}
                                </Button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  disabled={busyId === report.id}
                                  onClick={() => promptAction(report, "dismiss")}
                                  className="!min-h-[28px] !px-2 text-xs"
                                >
                                  {uiLanguage === "vi" ? "Bỏ qua" : "Dismiss"}
                                </Button>
                                <Button
                                  variant="danger"
                                  size="sm"
                                  disabled={busyId === report.id}
                                  onClick={() => promptAction(report, "remove")}
                                  className="!min-h-[28px] !px-2 text-xs"
                                >
                                  {uiLanguage === "vi" ? "Gỡ nội dung" : "Remove"}
                                </Button>
                              </div>
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

          {/* Selected Item Inspector & Content Preview Drawer */}
          {selectedReport ? (
            <div className="col-span-12 xl:col-span-5">
              <div className="rounded-[var(--radius-lg)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
                {/* Header */}
                <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-[var(--text-primary)]">
                        #{selectedReport.id}
                      </span>
                      <span className="rounded-md bg-[var(--surface-brand-soft)] px-2 py-0.5 text-xs font-semibold text-[var(--text-brand)]">
                        {selectedReport.target_type === "post"
                          ? uiLanguage === "vi"
                            ? "Bài viết"
                            : "Post"
                          : uiLanguage === "vi"
                            ? "Bình luận"
                            : "Comment"}{" "}
                        #{selectedReport.target_id}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      {uiLanguage === "vi" ? "Chi tiết nội dung và nguyên nhân khiếu nại" : "Report details and violation preview"}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="close"
                    aria-label={uiLanguage === "vi" ? "Đóng chi tiết" : "Close inspector"}
                    onClick={() => setSelectedReport(null)}
                  />
                </div>

                <div className="mt-4 space-y-4">
                  {/* Reason & Policy Card */}
                  {(() => {
                    const info = getReasonInfo(selectedReport.reason);
                    return (
                      <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                            {uiLanguage === "vi" ? "Lý do báo cáo" : "Violation Reason"}
                          </span>
                          <span
                            className={[
                              "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                              info.severity === "high"
                                ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                : "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
                            ].join(" ")}
                          >
                            {uiLanguage === "vi" ? info.labelVi : info.labelEn}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-[var(--text-secondary)]">
                          {uiLanguage === "vi" ? info.descriptionVi : info.descriptionEn}
                        </p>
                      </div>
                    );
                  })()}

                  {/* Content Preview Box */}
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {uiLanguage === "vi" ? "Xem trước nội dung bị khiếu nại" : "Reported Content Preview"}
                    </p>
                    <div className="mt-3 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs leading-relaxed text-[var(--text-primary)]">
                      <div className="mb-2 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                        <span>
                          {selectedReport.target_type === "post"
                            ? uiLanguage === "vi"
                              ? "Bài viết cộng đồng"
                              : "Feed Post"
                            : uiLanguage === "vi"
                              ? "Bình luận thảo luận"
                              : "Thread Comment"}{" "}
                          #{selectedReport.target_id}
                        </span>
                        <span>
                          {formatLocaleDate(uiLanguage, selectedReport.created_at, {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </span>
                      </div>
                      <p className="italic text-[var(--text-secondary)]">
                        {uiLanguage === "vi"
                          ? `[Nội dung của ${selectedReport.target_type === "post" ? "bài viết" : "bình luận"} #${selectedReport.target_id} đang được giữ nguyên trên hệ thống để xem xét xử lý vi phạm.]`
                          : `[Content body for ${selectedReport.target_type} #${selectedReport.target_id} is retained in moderation staging for compliance inspection.]`}
                      </p>
                    </div>
                  </div>

                  {/* Action Panel in Inspector */}
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {uiLanguage === "vi" ? "Hành động xử lý kiểm duyệt" : "Moderation Actions"}
                    </p>
                    <div className="mt-3 flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={busyId === selectedReport.id}
                        onClick={() => promptAction(selectedReport, "dismiss")}
                        className="flex-1"
                      >
                        {uiLanguage === "vi" ? "Bỏ qua báo cáo" : "Dismiss Report"}
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={busyId === selectedReport.id}
                        onClick={() => promptAction(selectedReport, "remove")}
                        className="flex-1"
                      >
                        {uiLanguage === "vi" ? "Gỡ bỏ nội dung" : "Remove Content"}
                      </Button>
                    </div>
                  </div>

                  {/* Zero-PII Audit Note */}
                  <div className="flex items-start gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-[11px] text-[var(--text-muted)]">
                    <Icon name="eye" size={16} className="mt-0.5 shrink-0 text-[var(--text-brand)]" />
                    <p>
                      {uiLanguage === "vi"
                        ? "Hành động kiểm duyệt sẽ được ghi vào nhật ký kiểm toán quản trị (Zero-PII Audit Log). Quyết định gỡ nội dung là bất khả hồi."
                        : "All moderation actions are recorded in the Zero-PII audit log. Removing content is irreversible."}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Irreversible Action Confirmation Modal */}
      <Modal
        open={confirmModal.open}
        onClose={() => setConfirmModal({ open: false, report: null, action: null })}
        role="alertdialog"
        title={
          confirmModal.action === "remove"
            ? uiLanguage === "vi"
              ? "Xác nhận gỡ nội dung vi phạm"
              : "Confirm Content Removal"
            : uiLanguage === "vi"
              ? "Xác nhận bỏ qua báo cáo"
              : "Confirm Report Dismissal"
        }
        description={
          confirmModal.action === "remove"
            ? uiLanguage === "vi"
              ? `Bạn có chắc chắn muốn gỡ ${confirmModal.report?.target_type === "post" ? "bài viết" : "bình luận"} #${confirmModal.report?.target_id}? Thao tác này sẽ ẩn nội dung khỏi bảng tin cộng đồng và được lưu vào nhật ký kiểm toán quản trị.`
              : `Are you sure you want to remove ${confirmModal.report?.target_type} #${confirmModal.report?.target_id}? This content will be hidden from the community and audited.`
            : uiLanguage === "vi"
              ? `Bạn có chắc chắn muốn bỏ qua báo cáo #${confirmModal.report?.id}? Nội dung sẽ tiếp tục được giữ nguyên và hiển thị trên cộng đồng.`
              : `Are you sure you want to dismiss report #${confirmModal.report?.id}? The content will remain visible on the platform.`
        }
        footer={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConfirmModal({ open: false, report: null, action: null })}
              disabled={Boolean(busyId)}
            >
              {uiLanguage === "vi" ? "Hủy" : "Cancel"}
            </Button>
            <Button
              variant={confirmModal.action === "remove" ? "danger" : "secondary"}
              size="sm"
              onClick={() => void executeAction()}
              disabled={Boolean(busyId)}
            >
              {busyId
                ? uiLanguage === "vi"
                  ? "Đang xử lý…"
                  : "Processing..."
                : confirmModal.action === "remove"
                  ? uiLanguage === "vi"
                    ? "Xác nhận gỡ"
                    : "Confirm Removal"
                  : uiLanguage === "vi"
                    ? "Xác nhận bỏ qua"
                    : "Confirm Dismiss"}
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-xs text-[var(--text-secondary)]">
          <p>
            {uiLanguage === "vi"
              ? "Thao tác này tuân theo Quy chuẩn An toàn Cộng đồng CLARA Care (FIDES & Community Safety Kernel)."
              : "This action complies with CLARA Care Community Safety Standards."}
          </p>
        </div>
      </Modal>
    </AdminShell>
  );
}
