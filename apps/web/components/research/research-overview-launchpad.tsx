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

export type ResearchLaunchpadTool = {
  id: string;
  href: string;
  icon: IconName;
  badge?: string;
  vi: { title: string; desc: string; highlights: string[] };
  en: { title: string; desc: string; highlights: string[] };
};

export const RESEARCH_TOOLS: ResearchLaunchpadTool[] = [
  {
    id: "evidence",
    href: "/evidence",
    icon: "progress",
    badge: "Living Evidence",
    vi: {
      title: "Bằng chứng sống (Living Evidence)",
      desc: "Tra cứu y văn có bình duyệt, phác đồ điều trị Bộ Y tế và mạng lưới đồ thị tri thức GLHS.",
      highlights: [
        "Phác đồ Bộ Y tế & Quốc tế",
        "Đồ thị tri thức GLHS",
        "Phân tích PICO đa chiều",
      ],
    },
    en: {
      title: "Living Evidence Synthesis",
      desc: "Access verified clinical literature, MoH guidelines, and GLHS knowledge graph.",
      highlights: [
        "MoH & International Guidelines",
        "GLHS Knowledge Graph",
        "Multi-dimensional PICO Synthesis",
      ],
    },
  },
  {
    id: "chat",
    href: "/chat",
    icon: "clinical-notes",
    badge: "Research Chat",
    vi: {
      title: "Tra cứu y khoa (AI Chat)",
      desc: "Trợ lý AI phân tích bằng chứng chuyên sâu, so sánh nghiên cứu và kiểm tra nhận định y khoa.",
      highlights: [
        "Truy xuất có viện dẫn nguồn",
        "Kiểm tra mâu thuẫn NLI",
        "Trích xuất luận điểm khoa học",
      ],
    },
    en: {
      title: "Medical Research Chat",
      desc: "AI research assistant for deep evidence synthesis, study comparison, and claim verification.",
      highlights: [
        "Source-grounded citations",
        "NLI contradiction checks",
        "Scientific claim extraction",
      ],
    },
  },
  {
    id: "source-hub",
    href: "/research/source-hub",
    icon: "search",
    badge: "Corpus Ingestion",
    vi: {
      title: "Kho nguồn nghiên cứu (Source Hub)",
      desc: "Đồng bộ và quản lý nguồn dữ liệu y khoa từ PubMed, Europe PMC, Bộ Y tế và Dược thư Quốc gia.",
      highlights: [
        "Đồng bộ PubMed & Europe PMC",
        "Cơ sở dữ liệu Dược thư Quốc gia",
        "Kiểm chuẩn nguồn tài liệu",
      ],
    },
    en: {
      title: "Research Source Hub",
      desc: "Unified ingestion hub for PubMed, Europe PMC, VN MoH, and National Pharmacopoeia.",
      highlights: [
        "PubMed & Europe PMC sync",
        "National Pharmacopoeia DB",
        "Corpus validation & provenance",
      ],
    },
  },
  {
    id: "surveillance",
    href: "/evidence",
    icon: "progress",
    badge: "Surveillance",
    vi: {
      title: "Giám sát biến động y văn",
      desc: "Theo dõi liên tục cập nhật khuyến cáo mới, thay đổi phác đồ và cảnh báo an toàn thuốc.",
      highlights: [
        "Cảnh báo mâu thuẫn phác đồ",
        "Theo dõi khuyến cáo mới",
        "Thông báo cập nhật thời gian thực",
      ],
    },
    en: {
      title: "Evidence Surveillance",
      desc: "Continuous monitoring of guideline updates, protocol changes, and drug safety alerts.",
      highlights: [
        "Guideline divergence alerts",
        "New recommendation tracking",
        "Real-time update notifications",
      ],
    },
  },
];

function toneClasses(tone?: "normal" | "warn" | "critical"): string {
  if (tone === "critical") return "border-[color:var(--danger-500)] bg-[color:var(--status-danger-bg)]";
  if (tone === "warn") return "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)]";
  return "border-[color:var(--shell-border)] bg-[color:var(--surface-panel)]";
}

export default function ResearchOverviewLaunchpad({
  className = "",
}: {
  className?: string;
}) {
  const language = useUILanguage();
  const [dashboard, setDashboard] = useState<SystemDashboardSnapshot | null>(null);
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
  const tasks = dashboard?.tasks ?? [];
  const nextTask = tasks[0] ?? null;
  const recentQueries = dashboard?.research.recentQueries ?? [];
  const enabledSourcesCount = dashboard?.sources.enabled ?? null;

  const ready = !loading && !error;
  const needsAttention = ready && alerts.length > 0;

  const statusText = loading
    ? copy("Đang cập nhật", "Updating")
    : error
      ? copy("Chưa xác định", "Unknown")
      : needsAttention
        ? copy("Có mục cần xem lại", "Items need review")
        : copy("Hoạt động bình thường", "Operational");

  const updatedTimestamp = dashboard?.generatedAt
    ? formatLocaleDate(language, new Date(dashboard.generatedAt), {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  return (
    <div className={`space-y-8 ${className}`.trim()}>
      {/* Research & Evidence Command Center Hero Banner */}
      <section className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-sm">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[var(--brand-600)]/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[var(--brand-primary)]/5 blur-3xl" />

        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[color:var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[color:var(--text-brand)]">
                <Icon name="progress" size={14} />
                {copy("KHÔNG GIAN NGHIÊN CỨU & Y VĂN", "RESEARCH & EVIDENCE WORKSPACE")}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                <Icon name="check" size={13} className="text-[var(--text-brand)]" />
                {copy("GLHS Knowledge Graph & Living Evidence", "GLHS Knowledge Graph & Living Evidence")}
              </span>
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              {copy("Trung tâm Nghiên cứu & Bằng chứng Y học", "Medical Research & Evidence Center")}
            </h1>

            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
              {copy(
                "Không gian tổng hợp bằng chứng y học sống, phân tích đa chiều và đối chiếu tri thức y khoa có dẫn nguồn.",
                "Explore living medical evidence, source-grounded syntheses, and multi-tier clinical knowledge hubs.",
              )}
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
                <Icon name="search" size={14} className="text-[var(--text-brand)]" />
                {enabledSourcesCount !== null
                  ? copy(`${enabledSourcesCount} nguồn tri thức sẵn sàng`, `${enabledSourcesCount} active knowledge sources`)
                  : copy("Kho tri thức y khoa", "Medical knowledge corpus")}
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
              href="/chat"
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-lg)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]"
            >
              <Icon name="clinical-notes" size={18} />
              {copy("Tra cứu y khoa (Chat)", "Ask CLARA (Chat)")}
            </Link>

            <div className="flex gap-2">
              <Link
                href="/evidence"
                className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="progress" size={15} />
                {copy("Bằng chứng sống", "Living Evidence")}
              </Link>
              <Link
                href="/research/source-hub"
                className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="search" size={15} />
                {copy("Nguồn nghiên cứu", "Source Hub")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Network / Error fallback */}
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
              "Các trang nghiên cứu và tra cứu vẫn dùng được bình thường. Bạn có thể thử tải lại.",
              "Research tools remain directly accessible. You can retry loading.",
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

      {/* Active System / Research Alerts */}
      {ready && topAlert ? (
        <section
          className={`rounded-2xl border p-5 shadow-sm transition-all ${
            topAlert.severity === "critical"
              ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
              : "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
          }`}
          role="alert"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Icon
                name="warning"
                size={22}
                className={topAlert.severity === "critical" ? "animate-pulse" : ""}
              />
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-bold text-base">
                    {topAlert.severity === "critical"
                      ? copy("Cảnh báo khẩn y văn (Critical Alert)", "Critical Research Flag")
                      : copy("Thông báo nghiên cứu & An toàn", "Research & Safety Notice")}
                  </h2>
                </div>
                <p className="mt-1 text-sm leading-relaxed">{topAlert.message}</p>
              </div>
            </div>
            {topAlert.href ? (
              <Link
                href={topAlert.href}
                className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-current bg-[var(--surface-panel)] px-4 text-xs font-bold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                {copy("Mở mục liên quan", "Open related item")}
              </Link>
            ) : null}
          </div>
        </section>
      ) : null}

      {/* Next Research Action */}
      {ready && nextTask ? (
        <section aria-labelledby="research-next-task" className="space-y-3">
          <h2
            id="research-next-task"
            className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]"
          >
            <Icon name="progress" className="text-[var(--brand-600)]" />
            {copy("Việc cần rà soát", "Action item")}
          </h2>
          <article className={`flex flex-col gap-4 rounded-xl border p-5 sm:flex-row sm:items-center sm:justify-between ${toneClasses(nextTask.tone)}`}>
            <div className="flex min-w-0 items-start gap-4">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]">
                <Icon name={nextTask.tone === "critical" ? "warning" : "clinical-notes"} size={20} />
              </span>
              <div>
                <h3 className="font-bold text-[var(--text-primary)]">{nextTask.title}</h3>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{nextTask.detail}</p>
              </div>
            </div>
            <Link
              href={nextTask.href}
              className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg border border-[color:var(--shell-border-strong)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:border-[color:var(--text-brand)] hover:text-[var(--text-brand)]"
            >
              {copy("Mở việc này", "Open task")}
            </Link>
          </article>
        </section>
      ) : null}

      {/* 4 Primary Research & Evidence Tools Cards */}
      <section aria-labelledby="research-launchpad-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="clinical-notes" className="text-[var(--text-brand)]" />
            <h2
              id="research-launchpad-heading"
              className="text-xl font-bold text-[var(--text-primary)]"
            >
              {copy("4 công cụ nghiên cứu & y văn cốt lõi", "4 Primary Research & Evidence Tools")}
            </h2>
          </div>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            {copy("Living Evidence, AI Chat, Source Hub & Surveillance", "Living Evidence, AI Chat, Source Hub & Surveillance")}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {RESEARCH_TOOLS.map((tool) => {
            const currentContent = tool[language];

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
                    {currentContent.title}
                  </h3>

                  <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {currentContent.desc}
                  </p>

                  <div className="mt-4 space-y-1.5 border-t border-[color:var(--shell-border)] pt-3">
                    {currentContent.highlights.map((highlight, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]"
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-[var(--text-brand)] opacity-70" />
                        <span>{highlight}</span>
                      </div>
                    ))}
                  </div>
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

      {/* Research Activity & Knowledge Base Grid */}
      <section aria-labelledby="research-activity-sources" className="space-y-4">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Panel A: Recent Queries & Activity */}
          <div className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                  <Icon name="clinical-notes" size={18} />
                </span>
                <div>
                  <h3 className="font-bold text-base text-[var(--text-primary)]">
                    {copy("Hoạt động tra cứu gần đây", "Recent Research Queries")}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Các câu hỏi nghiên cứu và bằng chứng vừa tổng hợp", "Recent evidence lookups and syntheses")}
                  </p>
                </div>
              </div>
              <Link href="/chat" className="text-xs font-bold text-[var(--text-brand)] hover:underline">
                {copy("Xem tất cả", "View all")} →
              </Link>
            </div>

            <div className="divide-y divide-[color:var(--shell-border)] overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              {recentQueries.length > 0 ? (
                recentQueries.slice(0, 4).map((item) => (
                  <Link
                    key={item.id}
                    href={`/chat?q=${encodeURIComponent(item.query)}`}
                    className="flex items-start gap-3 p-3.5 transition hover:bg-[var(--surface-muted)]"
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-brand)]">
                      <Icon name="clinical-notes" size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h4 className="truncate text-sm font-semibold text-[var(--text-primary)]">
                        {item.query}
                      </h4>
                      <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                        {formatLocaleDate(language, new Date(item.createdAt), {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </p>
                    </div>
                  </Link>
                ))
              ) : (
                <p className="p-5 text-sm text-[var(--text-secondary)]">
                  {copy("Chưa có hoạt động gần đây để hiển thị.", "No recent activity to display.")}
                </p>
              )}
            </div>
          </div>

          {/* Panel B: Knowledge Bases & Quick Shortcuts */}
          <div className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                  <Icon name="progress" size={18} />
                </span>
                <div>
                  <h3 className="font-bold text-base text-[var(--text-primary)]">
                    {copy("Kho tri thức & Lối tắt nhanh", "Knowledge Bases & Shortcuts")}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Phác đồ Bộ Y tế, PubMed, Europe PMC và Dược thư", "MoH Guidelines, PubMed, Europe PMC & Pharmacopoeia")}
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
                    {copy("Nguồn tri thức kích hoạt", "Active knowledge sources")}
                  </span>
                  <div className="mt-1 text-xl font-bold text-[var(--text-primary)]">
                    {enabledSourcesCount === null
                      ? copy("Đang đồng bộ", "Syncing")
                      : formatLocaleNumber(language, enabledSourcesCount)}
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                    {copy("Mô hình kiểm chứng", "Verification engine")}
                  </span>
                  <div className="mt-1 text-xl font-bold text-[var(--text-primary)]">
                    FIDES NLI
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  href="/evidence"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="progress" size={14} />
                  <span>{copy("Thư viện bằng chứng", "Evidence library")}</span>
                </Link>

                <Link
                  href="/chat"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="clinical-notes" size={14} />
                  <span>{copy("Hỏi CLARA", "Ask CLARA")}</span>
                </Link>

                <Link
                  href="/research/source-hub"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                >
                  <Icon name="search" size={14} />
                  <span>{copy("Nguồn nghiên cứu", "Research sources")}</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
