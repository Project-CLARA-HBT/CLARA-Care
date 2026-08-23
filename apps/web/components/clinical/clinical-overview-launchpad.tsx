"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
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

export default function ClinicalOverviewLaunchpad({
  className = "",
}: {
  className?: string;
}) {
  const language = useUILanguage();
  const [dashboard, setDashboard] = useState<SystemDashboardSnapshot | null>(null);
  const [activeCase, setActiveCase] = useState<CouncilCaseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const copy = useCallback(
    (vi: string, en: string) => (language === "vi" ? vi : en),
    [language],
  );

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
  const needsAttention = ready && (alerts.length > 0 || (expiringCount ?? 0) > 0);

  const statusText = loading
    ? copy("Đang cập nhật", "Updating")
    : error
      ? copy("Chưa xác định", "Unknown")
      : needsAttention
        ? copy("Có mục cần xem lại", "Items need review")
        : copy("Hoạt động bình thường", "Operational");

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

  return (
    <div className={`space-y-8 ${className}`.trim()}>
      {/* Clinician Command Center Hero Banner */}
      <section className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-sm">
        {/* Subtle accent glow */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[var(--brand-600)]/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[var(--brand-primary)]/5 blur-3xl" />

        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[color:var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[color:var(--text-brand)]">
                <Icon name="clinical-notes" size={14} />
                {copy("KHÔNG GIAN LÂM SÀNG • COMMAND CENTER", "CLINICAL WORKSPACE • COMMAND CENTER")}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                <Icon name="check" size={13} className="text-[var(--text-brand)]" />
                {copy("DrugBank v5.1.10 Verified", "DrugBank v5.1.10 Verified")}
              </span>
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              {t(language, "clinical.overview.title")}
            </h1>

            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
              {t(language, "clinical.overview.subtitle")}
            </p>

            {/* Live Status Indicators */}
            <div className="flex flex-wrap items-center gap-2.5 pt-2">
              <span className="inline-flex min-h-8 items-center gap-2 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3.5 py-1 text-xs font-bold text-[var(--text-primary)]">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    loading || error
                      ? "bg-[var(--text-muted)]"
                      : needsAttention
                        ? "bg-[var(--status-warn-text)] animate-pulse"
                        : "bg-[var(--success-500)]"
                  }`}
                />
                <span>{copy("Trạng thái:", "Status:")} {statusText}</span>
              </span>

              <span className="inline-flex min-h-8 items-center gap-2 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
                <Icon name="progress" size={14} className="text-[var(--text-brand)]" />
                {activeCase
                  ? copy(`Ca #${activeCase.id} đang mở`, `Case #${activeCase.id} active`)
                  : copy("Chưa có ca hội chẩn mở", "No active council case")}
              </span>

              {updatedTimestamp ? (
                <span className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-1 text-xs text-[var(--text-muted)]">
                  <Icon name="calendar" size={13} />
                  <span>{copy("Đồng bộ:", "Synced:")} {updatedTimestamp}</span>
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 lg:flex-col lg:items-end">
            <Link
              href={activeCaseHref}
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-lg)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]"
            >
              <Icon name="progress" size={18} />
              {activeCase
                ? t(language, "clinical.overview.resumeAction")
                : t(language, "clinical.overview.newCaseAction")}
            </Link>

            <div className="flex gap-2">
              <Link
                href="/scribe"
                className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="clinical-notes" size={15} />
                {copy("Ghi chép SOAP", "SOAP Scribe")}
              </Link>
              <Link
                href="/selfmed/ddi"
                className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="medication" size={15} />
                {copy("Tra cứu DDI", "DDI Checker")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Network / General error fallback */}
      {error ? (
        <section
          className="rounded-xl border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] p-5"
          role="alert"
        >
          <h2 className="font-bold text-[var(--status-warn-text)]">
            {copy("Chưa tải được tổng quan", "Overview unavailable")}
          </h2>
          <p className="mt-1 text-sm text-[var(--status-warn-text)]">
            {copy(
              "Các công cụ lâm sàng riêng lẻ vẫn hoạt động bình thường. Bạn có thể thử tải lại.",
              "Clinical tools remain directly accessible. You can retry loading.",
            )}
          </p>
          <button
            type="button"
            onClick={() => void loadData()}
            className="mt-3 min-h-10 rounded-lg border border-[color:var(--status-warn-border)] px-4 text-sm font-bold text-[var(--status-warn-text)]"
          >
            {copy("Thử lại", "Retry")}
          </button>
        </section>
      ) : null}

      {/* Real-time Server Alert (Critical Red-flag Alert only at top) */}
      {ready && topAlert && topAlert.severity === "critical" ? (
        <section
          className="rounded-2xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] p-5 shadow-sm transition-all"
          role="alert"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Icon
                name="warning"
                size={22}
                className="text-[var(--status-danger-text)] animate-pulse"
              />
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-bold text-base">
                    {copy("Cảnh báo đỏ lâm sàng (Critical Alert)", "Critical Clinical Red Flag")}
                  </h2>
                  <span className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border border-current">
                    CRITICAL
                  </span>
                </div>
                <p className="mt-1 text-sm leading-relaxed">{topAlert.message}</p>
              </div>
            </div>
            <Link
              href={topAlert.href}
              className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-current bg-[var(--surface-panel)] px-4 text-xs font-bold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
            >
              {copy("Xử lý ngay", "Resolve now")}
            </Link>
          </div>
        </section>
      ) : null}

      {/* Quick Case Resumption with case status chips and last updated time */}
      <section aria-labelledby="active-clinical-activity" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="progress" className="text-[var(--brand-600)]" />
            <h2
              id="active-clinical-activity"
              className="text-xl font-bold text-[var(--text-primary)]"
            >
              {t(language, "clinical.overview.resumableCase")}
            </h2>
          </div>
          <Link
            href="/council/new"
            className="text-xs font-bold text-[var(--text-brand)] hover:underline"
          >
            + {t(language, "clinical.overview.newCaseAction")}
          </Link>
        </div>

        {activeCase ? (
          <article className="group rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 transition-all hover:border-[color:var(--brand-600)] hover:shadow-md">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] transition group-hover:scale-105">
                  <Icon name="clinical-notes" size={24} />
                </span>
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 font-mono text-xs font-bold text-[var(--text-primary)]">
                      #{activeCase.id}
                    </span>
                    {caseStatus ? (
                      <StatusChip
                        tone={caseStatus.tone}
                        label={caseStatus.label}
                        size="sm"
                      />
                    ) : null}
                    {activeCase.intake_mode ? (
                      <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-muted)]">
                        {activeCase.intake_mode === "transcript"
                          ? copy("Hội thoại SOAP", "SOAP Dialogue")
                          : copy("Hội đồng đa khoa", "Clinical Intake")}
                      </span>
                    ) : null}
                  </div>

                  <h3 className="text-lg font-bold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                    {activeCase.title || copy(`Ca hội chẩn #${activeCase.id}`, `Council Case #${activeCase.id}`)}
                  </h3>

                  <p className="text-xs text-[var(--text-secondary)]">
                    <span className="font-semibold">{copy("Lần cập nhật cuối:", "Last updated:")}</span>{" "}
                    {formatLocaleDate(language, new Date(activeCase.updated_at || activeCase.created_at || Date.now()), {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2.5 sm:shrink-0">
                <Link
                  href={activeCaseHref}
                  className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]"
                >
                  <Icon name="progress" size={16} />
                  {t(language, "clinical.overview.resumeAction")}
                </Link>
                <Link
                  href={`/council/new?caseId=${activeCase.id}`}
                  className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
                >
                  {copy("Chỉnh sửa", "Edit")}
                </Link>
              </div>
            </div>
          </article>
        ) : (
          <div className="rounded-2xl border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] p-8 text-center">
            <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[var(--surface-muted)] text-[var(--text-muted)]">
              <Icon name="progress" size={24} />
            </span>
            <h3 className="mt-3 font-bold text-[var(--text-primary)]">
              {t(language, "clinical.overview.noActiveCase")}
            </h3>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {t(language, "clinical.overview.noActiveCaseDesc")}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <Link
                href="/council/new"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)]"
              >
                <Icon name="progress" size={16} />
                {t(language, "clinical.overview.newCaseAction")}
              </Link>
              <Link
                href="/scribe"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-panel)]"
              >
                <Icon name="clinical-notes" size={16} />
                {copy("Ghi chép khám mới (SOAP)", "New SOAP Scribe")}
              </Link>
            </div>
          </div>
        )}
      </section>

      {/* 4 Primary Clinical Tool Cards */}
      <section aria-labelledby="clinical-launchpad-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="clinical-notes" className="text-[var(--text-brand)]" />
            <h2
              id="clinical-launchpad-heading"
              className="text-xl font-bold text-[var(--text-primary)]"
            >
              {t(language, "clinical.overview.launchpad")}
            </h2>
          </div>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            {copy("Hội đồng AI, Scribe, Bằng chứng & Tra cứu", "AI Council, Scribe, Living Evidence & Clinical Chat")}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {CLINICAL_TOOLS.map((tool) => {
            const title = t(language, tool.titleKey);
            const desc = t(language, tool.descKey);

            return (
              <Link
                key={tool.id}
                href={tool.href}
                className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="grid h-12 w-12 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                      <Icon name={tool.icon} size={24} />
                    </span>
                    {tool.badge ? (
                      <span className="rounded-full border border-[color:var(--brand-primary)]/20 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                        {tool.badge}
                      </span>
                    ) : null}
                  </div>

                  <h3 className="mt-4 text-lg font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                    {title}
                  </h3>

                  <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {desc}
                  </p>

                  {/* Highlights list */}
                  {tool.highlights ? (
                    <div className="mt-4 space-y-1.5 border-t border-[color:var(--shell-border)] pt-3">
                      {tool.highlights.map((h, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]"
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--text-brand)] opacity-70" />
                          <span>{language === "vi" ? h.vi : h.en}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="mt-5 flex items-center justify-between pt-2">
                  <span className="text-xs font-bold text-[var(--text-brand)]">
                    {copy("Mở công cụ", "Open tool")}
                  </span>
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:translate-x-1 group-hover:bg-[var(--brand-600)] group-hover:text-[var(--on-secondary-container)]">
                    <Icon name="arrow-right" size={14} />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Real-time Server Alerts and DrugBank Updates Section */}
      <section aria-labelledby="clinical-alerts-drugbank" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="warning" className="text-[var(--brand-600)]" />
            <h2
              id="clinical-alerts-drugbank"
              className="text-xl font-bold text-[var(--text-primary)]"
            >
              {copy("Cảnh báo máy chủ & Cập nhật Dược lý", "Real-Time Server Alerts & DrugBank Updates")}
            </h2>
          </div>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            {copy("Bảo đảm an toàn theo thời gian thực", "Real-time safety guardrails")}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Panel A: Server Alerts & Clinical Safety */}
          <div className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                  <Icon name="warning" size={18} />
                </span>
                <div>
                  <h3 className="font-bold text-base text-[var(--text-primary)]">
                    {copy("Cảnh báo an toàn lâm sàng", "Clinical Safety Alerts")}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Rà soát tương tác, cảnh báo đỏ và ngưỡng an toàn", "DDI checks, red flags, and safety thresholds")}
                  </p>
                </div>
              </div>
              <StatusChip
                tone={alerts.length > 0 ? "warning" : "success"}
                label={
                  alerts.length > 0
                    ? copy(`${alerts.length} cảnh báo`, `${alerts.length} alert${alerts.length > 1 ? "s" : ""}`)
                    : copy("An toàn", "Safe")
                }
                size="sm"
              />
            </div>

            {alerts.length > 0 ? (
              <div className="space-y-3 pt-2">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`flex flex-col gap-2 rounded-xl border p-3.5 sm:flex-row sm:items-center sm:justify-between ${
                      alert.severity === "critical"
                        ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                        : "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <Icon
                        name="warning"
                        size={16}
                        className="mt-0.5 shrink-0"
                      />
                      <span className="text-xs font-semibold leading-relaxed">
                        {alert.message}
                      </span>
                    </div>
                    {alert.href ? (
                      <Link
                        href={alert.href}
                        className="inline-flex shrink-0 items-center gap-1 text-xs font-bold underline hover:opacity-80"
                      >
                        {copy("Xem chi tiết", "View details")}
                        <Icon name="arrow-right" size={12} />
                      </Link>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-xs text-[var(--text-secondary)] space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-[var(--text-primary)]">
                  <Icon name="check" size={16} className="text-[var(--success-500)]" />
                  <span>{copy("Hệ thống hoạt động an toàn", "System operating safely")}</span>
                </div>
                <p className="leading-relaxed">
                  {copy(
                    "Tất cả quy tắc FIDES, chốt chặn kê đơn và kiểm tra tương tác thuốc đang được giám sát chặt chẽ. Chưa phát hiện bất thường.",
                    "All FIDES verification rules, legal hard-guards, and drug-interaction monitors are fully operational.",
                  )}
                </p>
              </div>
            )}
          </div>

          {/* Panel B: DrugBank & Evidence Knowledge Updates */}
          <div className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                  <Icon name="medication" size={18} />
                </span>
                <div>
                  <h3 className="font-bold text-base text-[var(--text-primary)]">
                    {copy("Cơ sở dữ liệu Dược & Tri thức", "DrugBank & Knowledge Bases")}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("DrugBank v5.1.10, Phác đồ Bộ Y tế & KDIGO", "DrugBank v5.1.10, MoH Guidelines & KDIGO")}
                  </p>
                </div>
              </div>
              <StatusChip
                tone="success"
                label={copy("Đã đồng bộ", "Synced")}
                size="sm"
              />
            </div>

            <div className="space-y-3 pt-1">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                    {copy("Thuốc đang theo dõi", "Tracked medicines")}
                  </span>
                  <div className="mt-1 text-xl font-bold text-[var(--text-primary)]">
                    {cabinetCount === null
                      ? copy("Chưa có dữ liệu", "Unavailable")
                      : formatLocaleNumber(language, cabinetCount)}
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                    {copy("Thuốc sắp đến hạn", "Expiring soon")}
                  </span>
                  <div className="mt-1 text-xl font-bold text-[var(--text-primary)]">
                    {expiringCount === null
                      ? 0
                      : formatLocaleNumber(language, expiringCount)}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  href="/selfmed/ddi"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="medication" size={14} />
                  <span>{copy("Kiểm tra tương tác DrugBank", "DrugBank DDI check")}</span>
                </Link>

                <Link
                  href="/medicines"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="medication" size={14} />
                  <span>{copy("Tủ thuốc lâm sàng", "Clinical cabinet")}</span>
                </Link>

                <Link
                  href="/research/source-hub"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="search" size={14} />
                  <span>{copy("Nguồn tri thức y khoa", "Knowledge sources")}</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
