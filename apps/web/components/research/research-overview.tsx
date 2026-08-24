"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip } from "@/components/ui/status-chip";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
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

export function ResearchOverview({
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

  const ready = !loading && !error;
  const recentQueries = dashboard?.research?.recentQueries ?? [];
  const activeQuery = recentQueries[0] ?? null;

  const enabledSources = dashboard?.sources.enabled ?? null;
  const totalSources = dashboard?.sources.total ?? null;
  const hasSourceIssues =
    ready &&
    Boolean(
      (enabledSources !== null && totalSources !== null && enabledSources < totalSources) ||
        (dashboard && dashboard.sources.lowContextThreshold > 0.8),
    );

  const needsAttention = ready && (alerts.length > 0 || hasSourceIssues);

  const updatedTimestamp = dashboard?.generatedAt
    ? formatLocaleDate(language, new Date(dashboard.generatedAt), {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  if (loading) {
    return (
      <div className={`space-y-6 ${className}`.trim()} aria-busy="true">
        {/* Structural Skeleton matching final operational rows */}
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
    <div className={`space-y-6 ${className}`.trim()} data-role-view="researcher">
      {/* 1. Contextual Header (Spec v8 §7.1: No giant hero banner; next action is first) */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--shell-border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {copy("Nhà nghiên cứu Y học", "Medical Researcher")}
            </span>
            <span className="text-xs text-[var(--text-muted)]">•</span>
            <span className="text-xs text-[var(--text-muted)]">
              {updatedTimestamp ? `${copy("Cập nhật:", "Updated:")} ${updatedTimestamp}` : copy("Hôm nay", "Today")}
            </span>
          </div>
          <h1 className="mt-1 text-xl font-bold tracking-tight text-[var(--text-primary)] sm:text-2xl">
            {t(language, "navigation.item.research.title")}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            <Icon name="check" size={13} className="text-[var(--text-brand)]" />
            <span>GLHS Knowledge Graph & Living Evidence</span>
          </span>

          <Link
            href="/evidence"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3 py-1.5 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
          >
            <Icon name="plus" size={14} />
            <span>{copy("Đặt câu hỏi nghiên cứu", "New Research Inquiry")}</span>
          </Link>
        </div>
      </header>

      {/* 2. Offline or Error State */}
      {error && (
        <section
          role="alert"
          className="flex items-center justify-between rounded-xl border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)]/20 p-4 text-xs text-[var(--status-warn-text)]"
        >
          <div className="flex items-center gap-2.5">
            <Icon name="warning" size={16} className="shrink-0" />
            <div>
              <p className="font-semibold">{copy("Chưa tải được tổng quan hoặc máy chủ ngoại tuyến", "Subsystem offline or unreachable")}</p>
              <p className="mt-0.5 text-[var(--text-muted)]">{copy("Các công cụ nghiên cứu vẫn hoạt động trực tiếp.", "Research tools remain directly accessible.")}</p>
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

      {/* 3. Attention Queue (Spec v8 §7.1: Attention Queue appears above routine work when issues require action) */}
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
                {copy("Hàng đợi cần chú ý & Cảnh báo nguồn", "Attention Queue & Source Issues")}
              </h2>
            </div>
            <span className="rounded-full bg-[color:var(--status-warn-bg)] px-2 py-0.5 text-[11px] font-bold text-[color:var(--status-warn-text)]">
              {alerts.length + (hasSourceIssues ? 1 : 0)} {copy("mục cần xử lý", "items")}
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

            {hasSourceIssues && (
              <div className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="inline-flex rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-300 border border-amber-700/50">
                    {copy("Nguồn dữ liệu", "Sources")}
                  </span>
                  <span className="truncate font-medium text-[var(--text-primary)]">
                    {copy(
                      `Có ${totalSources! - enabledSources!} nguồn dữ liệu y khoa chưa sẵn sàng hoặc độ nhạy thấp.`,
                      `${totalSources! - enabledSources!} research source(s) unverified or degraded.`,
                    )}
                  </span>
                </div>
                <Link
                  href="/research/source-hub"
                  className="shrink-0 ml-3 font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {copy("Kiểm tra Source Hub →", "Inspect Source Hub →")}
                </Link>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 4. Priority Next Action (Spec v8 §7.1: Active research question / Recent run FIRST) */}
      <section
        aria-label={copy("Câu hỏi nghiên cứu gần nhất", "Active Research Inquiry")}
        className="rounded-2xl border border-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-5 shadow-xs"
      >
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="search" size={15} />
            </span>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
              {copy("Câu hỏi nghiên cứu gần nhất", "Active Research Question")}
            </h2>
          </div>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            {recentQueries.length} {copy("phiên gần đây", "recent runs")}
          </span>
        </div>

        {activeQuery ? (
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1.5 min-w-0">
              <div className="flex items-center gap-2">
                <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)]">
                  PICO / RAG
                </span>
                <h3 className="truncate text-base font-semibold text-[var(--text-primary)]">
                  {activeQuery.query}
                </h3>
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                {copy("Thời gian thực hiện:", "Executed:")}{" "}
                {formatLocaleDate(language, new Date(activeQuery.createdAt), {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </p>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
              <Link
                href={`/evidence`}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-4 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
              >
                <span>{copy("Tiếp tục nghiên cứu", "Continue research")}</span>
                <Icon name="arrow-right" size={14} />
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-4 flex flex-col items-center justify-center py-6 text-center">
            <p className="text-xs text-[var(--text-muted)]">
              {copy("Chưa có hoạt động gần đây để hiển thị.", "No recent research activity to display.")}
            </p>
            <Link
              href="/evidence"
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:bg-[color:var(--surface-panel)]"
            >
              <Icon name="plus" size={14} />
              <span>{copy("Bắt đầu tra cứu bằng chứng", "Start evidence synthesis")}</span>
            </Link>
          </div>
        )}
      </section>

      {/* 5. Routine Work Grid (Living Evidence / Source Hub / Evidence Surveillance) */}
      <div className="grid gap-4 sm:grid-cols-3">
        {/* Living Evidence Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Bằng chứng sống (Living Evidence)", "Living Evidence Synthesis")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {copy("Tra cứu phác đồ Bộ Y tế & Đồ thị tri thức GLHS.", "MoH guidelines & GLHS knowledge graph.")}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/evidence"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Bằng chứng sống →", "Living Evidence →")}
            </Link>
          </div>
        </div>

        {/* Source Hub Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="search" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Kho nguồn nghiên cứu (Source Hub)", "Research Source Hub")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {enabledSources !== null ? (
                <span>{copy(`Đã đồng bộ ${enabledSources}/${totalSources} nguồn dữ liệu.`, `${enabledSources}/${totalSources} sources verified.`)}</span>
              ) : (
                <span>{copy("Chưa có dữ liệu", "No data")}</span>
              )}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/research/source-hub"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Quản lý nguồn →", "Manage sources →")}
            </Link>
          </div>
        </div>

        {/* Surveillance & Changes Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size={16} />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {copy("Giám sát biến động y văn", "Evidence Surveillance")}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              {copy("Theo dõi liên tục cập nhật khuyến cáo và cảnh báo.", "Continuous guideline and safety alerts tracking.")}
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/40 flex items-center justify-between">
            <Link
              href="/evidence"
              className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
            >
              {copy("Theo dõi biến động →", "Track changes →")}
            </Link>
          </div>
        </div>
      </div>

      {/* AI Research Chat Quick Link */}
      <div className="flex items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)]/60 px-4 py-3 text-xs">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <Icon name="clinical-notes" size={15} className="text-[var(--text-brand)]" />
          <span>{copy("Tra cứu y khoa và viện dẫn bằng chứng chi tiết bằng AI Chat?", "Deep evidence synthesis with AI Chat?")}</span>
        </div>
        <Link
          href="/chat"
          className="font-semibold text-[var(--text-brand)] hover:underline"
        >
          {copy("Tra cứu y khoa (Chat) →", "Medical Chat →")}
        </Link>
      </div>
    </div>
  );
}

export const ResearchOverviewLaunchpad = ResearchOverview;
export default ResearchOverview;
