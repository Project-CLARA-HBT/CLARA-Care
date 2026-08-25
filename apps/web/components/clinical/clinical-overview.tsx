"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { Badge } from "@/components/ui/badge";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  getSystemDashboard,
  normalizeSystemDashboard,
  type SystemDashboardAlert,
  type SystemDashboardSnapshot,
} from "@/lib/system";
import {
  CouncilCaseRecord,
  getActiveCouncilCaseId,
  getLatestCouncilCase,
} from "@/lib/council";

export type ClinicalLaunchpadTool = {
  id: string;
  href: string;
  icon: IconName;
  titleKey: "clinical.overview.tools.council" | "clinical.overview.tools.scribe" | "clinical.overview.tools.evidence" | "clinical.overview.tools.chat";
  descKey: "clinical.overview.tools.councilDesc" | "clinical.overview.tools.scribeDesc" | "clinical.overview.tools.evidenceDesc" | "clinical.overview.tools.chatDesc";
  badge?: string;
  taglineKey?: string;
  highlights?: Array<{ vi: string; en: string }>;
};

export const CLINICAL_TOOLS: ClinicalLaunchpadTool[] = [
  {
    id: "council",
    href: "/council",
    icon: "progress",
    titleKey: "clinical.overview.tools.council",
    descKey: "clinical.overview.tools.councilDesc",
    badge: "AI Council",
    taglineKey: "council",
    highlights: [
      { vi: "Triage đa chuyên khoa", en: "Multi-specialty triage" },
      { vi: "Phát hiện bất đồng thuận", en: "Divergence detection" },
      { vi: "Xác thực FIDES", en: "FIDES verification" },
    ],
  },
  {
    id: "scribe",
    href: "/scribe",
    icon: "clinical-notes",
    titleKey: "clinical.overview.tools.scribe",
    descKey: "clinical.overview.tools.scribeDesc",
    badge: "SOAP Notes",
    taglineKey: "scribe",
    highlights: [
      { vi: "Chuyển âm hội thoại", en: "Real-time transcription" },
      { vi: "Bệnh án SOAP chuẩn", en: "Standard SOAP notes" },
      { vi: "Ký số an toàn", en: "Secure electronic signing" },
    ],
  },
  {
    id: "evidence",
    href: "/evidence",
    icon: "progress",
    titleKey: "clinical.overview.tools.evidence",
    descKey: "clinical.overview.tools.evidenceDesc",
    badge: "Living Evidence",
    taglineKey: "evidence",
    highlights: [
      { vi: "Phác đồ Bộ Y tế", en: "MoH clinical guidelines" },
      { vi: "Đồ thị tri thức GLHS", en: "GLHS knowledge graph" },
      { vi: "Truy xuất nguồn gốc", en: "Evidence provenance" },
    ],
  },
  {
    id: "chat",
    href: "/chat",
    icon: "clinical-notes",
    titleKey: "clinical.overview.tools.chat",
    descKey: "clinical.overview.tools.chatDesc",
    badge: "Decision Support",
    taglineKey: "chat",
    highlights: [
      { vi: "Tra cứu dược lý", en: "Pharmacology lookups" },
      { vi: "Chỉnh liều eGFR", en: "eGFR renal adjustments" },
      { vi: "Viện dẫn bằng chứng", en: "Multi-layer citations" },
    ],
  },
];

function getCaseStatusChip(
  status: string | undefined,
  language: "vi" | "en",
): { tone: StatusTone; label: string } {
  const s = (status || "").toLowerCase().trim();
  if (s === "completed" || s === "ready" || s === "done" || s === "hoàn thành") {
    return { tone: "success", label: language === "vi" ? "Hoàn thành" : "Completed" };
  }
  if (s === "paused" || s === "waiting_review" || s === "review_required" || s === "cần rà soát") {
    return { tone: "warning", label: language === "vi" ? "Cần rà soát" : "Needs Review" };
  }
  if (s === "escalated" || s === "emergency" || s === "critical" || s === "khẩn cấp") {
    return { tone: "danger", label: language === "vi" ? "Cảnh báo khẩn" : "Escalated" };
  }
  if (s === "running" || s === "in_progress" || s === "intake" || s === "đang xử lý") {
    return { tone: "info", label: language === "vi" ? "Đang xử lý" : "Processing" };
  }
  return { tone: "info", label: language === "vi" ? "Đang mở" : "Active" };
}

export function ClinicalOverview({
  className = "",
}: {
  className?: string;
}) {
  const language = useUILanguage();
  const [dashboard, setDashboard] = useState<SystemDashboardSnapshot | null>(null);
  const [activeCase, setActiveCase] = useState<CouncilCaseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Quick interactive calculation demo state
  const [demoEgfrCreatinine, setDemoEgfrCreatinine] = useState("1.2");
  const [demoEgfrAge, setDemoEgfrAge] = useState("65");
  const [demoEgfrGender, setDemoEgfrGender] = useState<"M" | "F">("M");

  const copy = useCallback(
    (vi: string, en: string) => (language === "vi" ? vi : en),
    [language],
  );

  // Simple CKD-EPI quick reference calculation
  const calculatedEgfr = (() => {
    const scr = parseFloat(demoEgfrCreatinine) || 1.0;
    const age = parseFloat(demoEgfrAge) || 60;
    const isFemale = demoEgfrGender === "F";
    const kappa = isFemale ? 0.7 : 0.9;
    const alpha = isFemale ? -0.241 : -0.302;
    const minRatio = Math.min(scr / kappa, 1);
    const maxRatio = Math.max(scr / kappa, 1);
    const genderFactor = isFemale ? 1.012 : 1.0;
    const egfr =
      142 *
      Math.pow(minRatio, alpha) *
      Math.pow(maxRatio, -1.2) *
      Math.pow(0.9938, age) *
      genderFactor;
    return Math.round(egfr);
  })();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const raw = await getSystemDashboard();
      const normalized = normalizeSystemDashboard(raw);
      setDashboard(normalized);
    } catch {
      setError(true);
      setDashboard(null);
    }

    try {
      const activeId = getActiveCouncilCaseId();
      let found: CouncilCaseRecord | null = null;
      if (activeId) {
        found = await getLatestCouncilCase();
      } else {
        found = await getLatestCouncilCase();
      }
      setActiveCase(found);
    } catch {
      setActiveCase(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const alerts = dashboard?.alerts.filter((item) => item.message.trim()) ?? [];
  const topAlert: SystemDashboardAlert | null =
    alerts.find((item) => item.severity === "critical") ?? alerts[0] ?? null;

  const ready = !loading && !error;
  const cabinetCount = dashboard?.cabinet.itemTotal ?? null;
  const expiringCount = dashboard?.cabinet.expiringSoonTotal ?? null;

  const isMlReachable = dashboard?.runtime.mlReachable === true;
  const isApiOk = dashboard?.runtime.apiStatus === "ok";
  const isMlOk =
    isMlReachable ||
    dashboard?.runtime.mlStatus === "ok" ||
    dashboard?.runtime.mlStatus === "reachable";
  const isOffline =
    error ||
    (!loading &&
      (dashboard === null ||
        dashboard.runtime.mlReachable === false ||
        dashboard.runtime.apiStatus === "down" ||
        dashboard.runtime.apiStatus === "error" ||
        dashboard.runtime.mlStatus === "unreachable" ||
        dashboard.runtime.mlStatus === "error" ||
        dashboard.runtime.mlStatus === "down"));
  const isRuleVerificationEnabled = Boolean(dashboard?.sources.flowFlags.ruleVerification);
  const isDegraded =
    ready &&
    !isOffline &&
    Boolean(
      dashboard &&
        (dashboard.runtime.apiStatus === "degraded" ||
          dashboard.runtime.mlStatus === "degraded" ||
          !isRuleVerificationEnabled),
    );
  const isVerified =
    ready &&
    !isOffline &&
    !isDegraded &&
    Boolean(dashboard) &&
    isApiOk &&
    isMlOk &&
    isRuleVerificationEnabled;

  const needsAttention = ready && (alerts.length > 0 || (expiringCount ?? 0) > 0 || isDegraded);

  const activeCaseHref = activeCase
    ? activeCase.status === "completed" || activeCase.status === "ready"
      ? `/council/result?caseId=${activeCase.id}`
      : `/council/new/intake?caseId=${activeCase.id}`
    : "/council/new";

  const caseStatus = activeCase ? getCaseStatusChip(activeCase.status, language) : null;
  const updatedTimestamp = dashboard?.generatedAt
    ? formatLocaleDate(language, new Date(dashboard.generatedAt), {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  if (loading) {
    return (
      <div className={`space-y-6 ${className}`.trim()} aria-busy="true">
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-4">
          <div className="space-y-2">
            <div className="h-4 w-40 animate-pulse rounded bg-[color:var(--surface-muted)]" />
            <div className="h-6 w-64 animate-pulse rounded bg-[color:var(--surface-muted)]" />
          </div>
          <div className="h-7 w-32 animate-pulse rounded-full bg-[color:var(--surface-muted)]" />
        </div>

        <div className="space-y-4">
          <div className="h-36 w-full animate-pulse rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)]" />
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="h-28 animate-pulse rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)]" />
            <div className="h-28 animate-pulse rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-8 ${className}`.trim()} data-role-view="doctor" data-testid="clinical-overview">
      {/* 1. Contextual Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--shell-border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {copy("Bác sĩ Lâm sàng", "Clinical Doctor")}
            </span>
            <span className="text-xs text-[var(--text-muted)]">•</span>
            <span className="text-xs text-[var(--text-muted)]">
              {updatedTimestamp ? `${copy("Cập nhật:", "Updated:")} ${updatedTimestamp}` : copy("Hôm nay", "Today")}
            </span>
          </div>
          <h1 className="mt-1 text-xl font-bold tracking-tight text-[var(--text-primary)] sm:text-2xl">
            {t(language, "clinical.overview.title")}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isOffline ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--status-warn-text)]">
              <Icon name="warning" size={13} />
              {copy("DrugBank v5.1.10 Ngoại tuyến", "DrugBank v5.1.10 Offline")}
            </span>
          ) : !isVerified ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--status-warn-text)]">
              <Icon name="warning" size={13} />
              {copy("DrugBank v5.1.10 Chưa xác thực", "DrugBank v5.1.10 Unverified")}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
              <Icon name="check" size={13} className="text-[var(--text-brand)]" />
              {copy("DrugBank v5.1.10 Verified", "DrugBank v5.1.10 Verified")}
            </span>
          )}

          <Link
            href="/clinical/standards"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[color:var(--surface-panel)] transition"
          >
            <Icon name="clinical-notes" size={13} />
            <span>{copy("Tiêu chuẩn Lâm sàng", "Clinical Standards")}</span>
          </Link>

          <Link
            href="/council/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3 py-1.5 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
          >
            <Icon name="plus" size={14} />
            <span>{copy("Tạo ca hội chẩn", "New Council Case")}</span>
          </Link>
        </div>
      </header>

      {/* 2. Offline or Error Subsystem State */}
      {isOffline && (
        <section
          role="alert"
          className="flex items-center justify-between rounded-xl border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)]/20 p-4 text-xs text-[var(--status-warn-text)]"
        >
          <div className="flex items-center gap-2.5">
            <Icon name="warning" size={16} className="shrink-0" />
            <div>
              <p className="font-semibold">{copy("Chưa tải được tổng quan hoặc máy chủ ngoại tuyến", "Subsystem offline or unreachable")}</p>
              <p className="mt-0.5 text-[var(--text-muted)]">{copy("Các công cụ độc lập vẫn hoạt động bình thường.", "Local offline capabilities remain functional.")}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadData()}
            className="rounded-lg border border-[color:var(--status-warn-border)] bg-[color:var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] hover:bg-[color:var(--surface-muted)]"
          >
            {copy("Thử lại", "Retry")}
          </button>
        </section>
      )}

      {/* 3. Attention Queue */}
      {needsAttention && (
        <section
          aria-label={copy("Hàng đợi cần chú ý", "Attention Queue")}
          className="rounded-2xl border border-[color:var(--status-warn-border)]/80 bg-[color:var(--status-warn-bg)]/10 p-5 shadow-xs"
        >
          <div className="flex items-center justify-between border-b border-[color:var(--status-warn-border)]/30 pb-3">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[color:var(--status-warn-bg)] text-[color:var(--status-warn-text)]">
                <Icon name="warning" size={15} />
              </span>
              <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Hàng đợi cần chú ý & Cảnh báo an toàn", "Attention Queue & Safety Alerts")}
              </h2>
            </div>
            <span className="rounded-full bg-[color:var(--status-warn-bg)] px-2 py-0.5 text-[11px] font-bold text-[color:var(--status-warn-text)]">
              {alerts.length + (expiringCount && expiringCount > 0 ? 1 : 0)} {copy("mục cần xử lý", "items")}
            </span>
          </div>

          <div className="mt-3 divide-y divide-[color:var(--shell-border)]/50 text-xs">
            {topAlert && (
              <div className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                      topAlert.severity === "critical"
                        ? "bg-red-900/40 text-red-300 border border-red-700/50"
                        : "bg-amber-900/40 text-amber-300 border border-amber-700/50"
                    }`}
                  >
                    {topAlert.severity === "critical" ? copy("Khẩn cấp", "Critical") : copy("Cảnh báo", "Warning")}
                  </span>
                  <span className="truncate font-medium text-[var(--text-primary)]">
                    {topAlert.message}
                  </span>
                </div>
                {topAlert.href && (
                  <Link
                    href={topAlert.href}
                    className="shrink-0 ml-3 font-semibold text-[var(--text-brand)] hover:underline"
                  >
                    {copy("Xử lý ngay →", "Action →")}
                  </Link>
                )}
              </div>
            )}

            {expiringCount && expiringCount > 0 ? (
              <div className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="inline-flex rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-300 border border-amber-700/50">
                    {copy("Tủ thuốc", "Cabinet")}
                  </span>
                  <span className="truncate font-medium text-[var(--text-primary)]">
                    {copy(
                      `Có ${expiringCount} thuốc sắp đến hạn kiểm tra liều dùng hoặc hết hạn.`,
                      `${expiringCount} medication(s) expiring or require dosage review.`,
                    )}
                  </span>
                </div>
                <Link
                  href="/medicines"
                  className="shrink-0 ml-3 font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {copy("Rà soát tủ thuốc →", "Review cabinet →")}
                </Link>
              </div>
            ) : null}
          </div>
        </section>
      )}

      {/* 4. Priority Next Action (Active Case) */}
      <section
        aria-label={copy("Công việc lâm sàng đang thực hiện", "Active Clinical Work")}
        className="rounded-2xl border border-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-5 shadow-xs"
      >
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="clinical-notes" size={15} />
            </span>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
              {copy("Ca lâm sàng đang thực hiện", "Active Clinical Case")}
            </h2>
          </div>
          {caseStatus && <StatusChip tone={caseStatus.tone} label={caseStatus.label} />}
        </div>

        {activeCase ? (
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1.5 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-[var(--text-brand)]">
                  #{activeCase.id}
                </span>
                <h3 className="truncate text-base font-semibold text-[var(--text-primary)]">
                  {activeCase.title || copy("Ca lâm sàng chưa đặt tên", "Untitled Case")}
                </h3>
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                {copy("Lần cập nhật cuối:", "Last updated:")}{" "}
                {formatLocaleDate(language, new Date(activeCase.updated_at || activeCase.created_at), {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </p>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
              <Link
                href={activeCaseHref}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-4 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
              >
                <span>{copy("Tiếp tục ca này", "Continue this case")}</span>
                <Icon name="arrow-right" size={14} />
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-4 flex flex-col items-center justify-center py-6 text-center">
            <p className="text-xs text-[var(--text-muted)]">
              {copy("Chưa có hoạt động gần đây để hiển thị.", "No recent clinical case in progress.")}
            </p>
            <Link
              href="/council/new"
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:bg-[color:var(--surface-panel)]"
            >
              <Icon name="plus" size={14} />
              <span>{copy("Tạo ca hội chẩn mới", "Start new clinical case")}</span>
            </Link>
          </div>
        )}
      </section>

      {/* 5. Routine Work Grid (SOAP Scribe / Living Evidence / Cabinet Safety) */}
      <div className="grid gap-4 sm:grid-cols-3">
        {/* Scribe Session Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="clinical-notes" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Ghi chép SOAP", "SOAP Notes")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {copy("Chuyển âm hội thoại và lập bệnh án chuẩn SOAP kèm ký số SHA-256.", "Real-time voice scribe & structured SOAP notes with SHA-256 e-signature.")}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/scribe"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Mở Scribe →", "Open Scribe →")}
            </Link>
          </div>
        </div>

        {/* Living Evidence Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Bằng chứng", "Living Evidence")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {copy("Phác đồ Bộ Y tế, Dược thư Quốc gia và mạng lưới tri thức GLHS.", "MoH guidelines, National Pharmacopoeia & GLHS knowledge graph.")}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/evidence"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Tra cứu phác đồ →", "Explore guidelines →")}
            </Link>
          </div>
        </div>

        {/* Drug Safety & Medicines Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="medication" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Tủ thuốc & Dược lý", "Medicines & Rx")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {cabinetCount === null ? (
                <span>{copy("Chưa có dữ liệu", "No data")}</span>
              ) : (
                <span>
                  {copy(`Đang quản lý ${cabinetCount} thuốc.`, `${cabinetCount} tracked medications.`)}
                </span>
              )}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/medicines"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Kiểm tra tương tác DrugBank →", "Check DrugBank interactions →")}
            </Link>
          </div>
        </div>
      </div>

      {/* Decision Support Quick Link */}
      <div className="flex items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)]/60 px-4 py-3 text-xs">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <Icon name="clinical-notes" size={15} className="text-[var(--text-brand)]" />
          <span>{copy("Cần hỗ trợ tra cứu lâm sàng đa tầng?", "Need multi-layer clinical reasoning?")}</span>
        </div>
        <Link
          href="/chat"
          className="font-semibold text-[var(--text-brand)] hover:underline"
        >
          {copy("Tra cứu lâm sàng →", "Clinical Chat →")}
        </Link>
      </div>

      {/* 6. Comprehensive Clinical Architecture & Standards Showcase Section */}
      <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 shadow-xs space-y-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--shell-border)] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge tone="brand">{copy("ĐẶC TẢ KIẾN TRÚC LÂM SÀNG", "CLINICAL ARCHITECTURE")}</Badge>
              <span className="text-xs font-mono text-[var(--text-muted)]">Luật KBCB 2023 & FIDES v1.2</span>
            </div>
            <h2 className="mt-1 text-lg font-bold text-[var(--text-primary)]">
              {copy("Khung Năng lực Lâm sàng & Giao thức An toàn Y tế", "Clinical Capability Framework & Safety Protocols")}
            </h2>
          </div>

          <Link
            href="/clinical/standards"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] px-3.5 py-1.5 text-xs font-bold text-[var(--text-brand)] hover:bg-[var(--surface-brand-soft)]/80 transition"
          >
            <span>{copy("Xem toàn bộ Tiêu chuẩn Y khoa →", "View Full Medical Standards →")}</span>
          </Link>
        </div>

        {/* 4 Architectural Pillars Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          {/* Pillar 1: Multi-Specialist Council */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-purple-400 font-bold uppercase tracking-wider">
              <Icon name="progress" size={15} />
              <span>AI Council • 5 Chuyên khoa</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              {copy(
                "Điều phối song song Tim mạch, Thần kinh, Thận học, Dược lý và Nội tiết. Tự động phát hiện bất đồng thuận và tổng hợp khuyến nghị.",
                "Parallel orchestration across Cardiology, Neurology, Nephrology, Pharmacology, and Endocrinology with divergence detection.",
              )}
            </p>
            <div className="pt-2 border-t border-[color:var(--shell-border)]/50">
              <Link href="/council" className="font-semibold text-[var(--text-brand)] hover:underline">
                {copy("Khám phá Hội đồng AI →", "Explore AI Council →")}
              </Link>
            </div>
          </div>

          {/* Pillar 2: Ambient Scribe & SOAP */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-emerald-400 font-bold uppercase tracking-wider">
              <Icon name="clinical-notes" size={15} />
              <span>SOAP & Ký số Điện tử</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              {copy(
                "Chuyển âm hội thoại tiếng Việt y khoa (Whisper), tự động lập bệnh án SOAP 4 phần và ký số SHA-256 bảo đảm tính pháp lý.",
                "Vietnamese biomedical ASR (Whisper), 4-part SOAP structuring, and tamper-evident SHA-256 e-signatures.",
              )}
            </p>
            <div className="pt-2 border-t border-[color:var(--shell-border)]/50">
              <Link href="/scribe" className="font-semibold text-[var(--text-brand)] hover:underline">
                {copy("Phiên Scribe trực tiếp →", "Live Scribe Session →")}
              </Link>
            </div>
          </div>

          {/* Pillar 3: FIDES Hard-Veto */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-red-400 font-bold uppercase tracking-wider">
              <Icon name="warning" size={15} />
              <span>FIDES Hard-Veto Invariant</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              {copy(
                "Phủ quyết tuyệt đối: Bất kỳ liều dùng hoặc chống chỉ định nào thiếu căn cứ đều bị CHẶN NGAY, bất kể các câu khác đều đúng.",
                "Absolute Hard-Veto: Ungrounded dosage, contraindications, or DDI conflicts are blocked unconditionally.",
              )}
            </p>
            <div className="pt-2 border-t border-[color:var(--shell-border)]/50">
              <Link href="/clinical/standards#fides-verification" className="font-semibold text-[var(--text-brand)] hover:underline">
                {copy("Xem Ma trận FIDES →", "View FIDES Matrix →")}
              </Link>
            </div>
          </div>

          {/* Pillar 4: Zero-CoT Privacy */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-sky-400 font-bold uppercase tracking-wider">
              <Icon name="check" size={15} />
              <span>Zero-CoT & Zero-PII</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              {copy(
                "Triệt tiêu 100% thẻ suy luận <think> thô trước khi stream về trình duyệt. Không lưu vết PII trong logs theo Nghị định 13/2023.",
                "100% <think> reasoning token suppression before SSE stream delivery. Zero-PII logging under Decree 13/2023.",
              )}
            </p>
            <div className="pt-2 border-t border-[color:var(--shell-border)]/50">
              <Link href="/clinical/standards#zero-cot-privacy" className="font-semibold text-[var(--text-brand)] hover:underline">
                {copy("Chuẩn bảo mật Zero-CoT →", "Zero-CoT Standards →")}
              </Link>
            </div>
          </div>
        </div>

        {/* Interactive Clinical Calculator & Pharmacology Widget Preview */}
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-5 space-y-4">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Icon name="medication" size={16} className="text-[var(--text-brand)]" />
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                {copy("Công cụ Tính toán Nhanh eGFR CKD-EPI (2021) & An toàn Thận", "Quick eGFR CKD-EPI (2021) & Renal Clearance Calculator")}
              </h3>
            </div>
            <span className="text-[11px] font-mono text-[var(--text-muted)]">Equation: 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.2 × 0.9938^Age</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-4 items-end text-xs">
            <div>
              <label className="block text-[11px] font-semibold text-[var(--text-secondary)] mb-1">
                {copy("Serum Creatinine (mg/dL)", "Serum Creatinine (mg/dL)")}
              </label>
              <input
                type="number"
                step="0.1"
                min="0.2"
                max="15"
                value={demoEgfrCreatinine}
                onChange={(e) => setDemoEgfrCreatinine(e.target.value)}
                className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 font-mono text-[var(--text-primary)] focus-ring outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--text-secondary)] mb-1">
                {copy("Tuổi bệnh nhân (Năm)", "Patient Age (Years)")}
              </label>
              <input
                type="number"
                min="18"
                max="110"
                value={demoEgfrAge}
                onChange={(e) => setDemoEgfrAge(e.target.value)}
                className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 font-mono text-[var(--text-primary)] focus-ring outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--text-secondary)] mb-1">
                {copy("Giới tính sinh học", "Biological Sex")}
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setDemoEgfrGender("M")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-bold transition ${
                    demoEgfrGender === "M"
                      ? "bg-[var(--surface-brand-soft)] border-[color:var(--brand-primary)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
                  }`}
                >
                  {copy("Nam (M)", "Male (M)")}
                </button>
                <button
                  type="button"
                  onClick={() => setDemoEgfrGender("F")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-bold transition ${
                    demoEgfrGender === "F"
                      ? "bg-[var(--surface-brand-soft)] border-[color:var(--brand-primary)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
                  }`}
                >
                  {copy("Nữ (F)", "Female (F)")}
                </button>
              </div>
            </div>

            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 text-center">
              <div className="text-[10px] uppercase font-bold text-[var(--text-muted)]">eGFR Kết quả</div>
              <div className="flex items-baseline justify-center gap-1">
                <span className={`text-xl font-black ${calculatedEgfr < 30 ? "text-red-400" : calculatedEgfr < 60 ? "text-amber-300" : "text-emerald-400"}`}>
                  {calculatedEgfr}
                </span>
                <span className="text-[10px] text-[var(--text-secondary)] font-mono">mL/min/1.73m²</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export const ClinicalOverviewLaunchpad = ClinicalOverview;
export default ClinicalOverview;
