"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Icon, { type IconName } from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { getRole, type UserRole } from "@/lib/auth-store";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import {
  getSystemDashboard,
  normalizeSystemDashboard,
  type SystemDashboardAlert,
} from "@/lib/system";
import {
  CouncilCaseRecord,
  getActiveCouncilCaseId,
  getLatestCouncilCase,
} from "@/lib/council";
import { useUILanguage } from "@/lib/use-ui-language";

type DashboardTask = {
  id: string;
  title: string;
  detail: string;
  tone: "normal" | "warn" | "critical";
  href: string;
};

type RecentItem = { id: string; query: string; createdAt: number };

const roleGreeting: Record<UserRole, { vi: string; en: string }> = {
  normal: { vi: "Chào bạn", en: "Hello" },
  researcher: { vi: "Chào nhà nghiên cứu", en: "Hello, researcher" },
  doctor: { vi: "Trung tâm Lâm sàng & Hội chẩn", en: "Clinical & Consultation Command Center" },
  admin: { vi: "Chào quản trị viên", en: "Hello, administrator" },
};

type ClinicalToolCard = {
  id: string;
  href: string;
  icon: IconName;
  badge: string;
  vi: { title: string; desc: string };
  en: { title: string; desc: string };
};

const PRIMARY_CLINICAL_TOOLS: ClinicalToolCard[] = [
  {
    id: "council",
    href: "/council",
    icon: "progress",
    badge: "AI Council",
    vi: {
      title: "Hội chẩn AI (Council)",
      desc: "Phân tích đa chuyên khoa, phát hiện bất đồng thuận và cảnh báo tương tác FIDES.",
    },
    en: {
      title: "AI Council",
      desc: "Multi-specialty AI analysis, conflict detection, and FIDES safety verification.",
    },
  },
  {
    id: "scribe",
    href: "/scribe",
    icon: "clinical-notes",
    badge: "SOAP Notes",
    vi: {
      title: "Ghi chép khám (Scribe)",
      desc: "Tạo bệnh án SOAP theo thời gian thực từ hội thoại khám bệnh và phiên ghi âm.",
    },
    en: {
      title: "Clinical Scribe (SOAP)",
      desc: "Real-time SOAP clinical note generation from consultation dialogue.",
    },
  },
  {
    id: "evidence",
    href: "/evidence",
    icon: "progress",
    badge: "Living Evidence",
    vi: {
      title: "Bằng chứng sống (Living Evidence)",
      desc: "Tra cứu y văn, phác đồ điều trị Bộ Y tế và mạng lưới đồ thị tri thức GLHS.",
    },
    en: {
      title: "Living Evidence",
      desc: "Access verified medical literature, MoH guidelines, and GLHS knowledge graph.",
    },
  },
  {
    id: "chat",
    href: "/chat",
    icon: "clinical-notes",
    badge: "Decision Support",
    vi: {
      title: "Tra cứu lâm sàng (Chat)",
      desc: "Trợ lý lâm sàng hỗ trợ tra cứu nhanh thông tin y khoa, dược lý và liều dùng.",
    },
    en: {
      title: "Clinical Chat",
      desc: "Clinical AI assistant for rapid medical, pharmacological, and dosage lookups.",
    },
  },
];

const shortcutSets: Record<Exclude<UserRole, "normal">, Array<{
  href: string;
  icon: IconName;
  vi: string;
  en: string;
}>> = {
  researcher: [
    { href: "/chat", icon: "clinical-notes", vi: "Hỏi CLARA", en: "Ask CLARA" },
    { href: "/evidence", icon: "progress", vi: "Thư viện bằng chứng", en: "Evidence library" },
    { href: "/research/source-hub", icon: "clinical-notes", vi: "Nguồn nghiên cứu", en: "Research sources" },
  ],
  doctor: [
    { href: "/council", icon: "progress", vi: "Hội chẩn AI", en: "AI Council" },
    { href: "/scribe", icon: "clinical-notes", vi: "Ghi chép SOAP", en: "SOAP Scribe" },
    { href: "/evidence", icon: "progress", vi: "Bằng chứng", en: "Evidence" },
    { href: "/chat", icon: "clinical-notes", vi: "Tra cứu lâm sàng", en: "Clinical Chat" },
  ],
  admin: [
    { href: "/dashboard/ecosystem", icon: "progress", vi: "Giám sát hệ thống", en: "System monitoring" },
    { href: "/admin/knowledge-sources", icon: "clinical-notes", vi: "Nguồn tri thức", en: "Knowledge sources" },
    { href: "/admin/analytics", icon: "progress", vi: "Phân tích", en: "Analytics" },
  ],
};

function toneClasses(tone: DashboardTask["tone"]): string {
  if (tone === "critical") return "border-[color:var(--danger-500)] bg-[color:var(--status-danger-bg)]";
  if (tone === "warn") return "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)]";
  return "border-[color:var(--shell-border)] bg-[color:var(--surface-panel)]";
}

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

export default function DashboardPage() {
  const language = useUILanguage();
  const [role, setRole] = useState<UserRole>("normal");
  const [tasks, setTasks] = useState<DashboardTask[]>([]);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const [alerts, setAlerts] = useState<SystemDashboardAlert[]>([]);
  const [activeCase, setActiveCase] = useState<CouncilCaseRecord | null>(null);
  const [cabinetCount, setCabinetCount] = useState<number | null>(null);
  const [expiringCount, setExpiringCount] = useState<number | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const copy = useCallback(
    (vi: string, en: string) => (language === "vi" ? vi : en),
    [language],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const dashboard = normalizeSystemDashboard(await getSystemDashboard());
      const nextRole = dashboard.user.role;
      setRole(
        nextRole === "researcher" || nextRole === "doctor" || nextRole === "admin" || nextRole === "normal"
          ? nextRole
          : getRole(),
      );
      setTasks(dashboard.tasks.map((item) => ({
        id: item.id,
        title: item.title,
        detail: item.detail,
        tone: item.tone,
        href: item.href,
      })));
      setRecent(dashboard.research.recentQueries);
      setAlerts(dashboard.alerts.filter((item) => item.message.trim()));
      setCabinetCount(dashboard.cabinet.itemTotal);
      setExpiringCount(dashboard.cabinet.expiringSoonTotal);
      setGeneratedAt(dashboard.generatedAt);
    } catch {
      setError(true);
      setTasks([]);
      setRecent([]);
      setAlerts([]);
      setCabinetCount(null);
      setExpiringCount(null);
      setGeneratedAt(null);
      setRole(getRole());
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

  useEffect(() => { void load(); }, [load]);

  const nextTask = tasks[0] ?? null;
  const ready = !loading && !error;
  const needsAttention = ready && (alerts.length > 0 || (expiringCount ?? 0) > 0);
  const topAlert = alerts.find((item) => item.severity === "critical") ?? alerts[0] ?? null;
  const reviewCount = ready ? alerts.length + ((expiringCount ?? 0) > 0 ? 1 : 0) : null;
  const featuredTask = tasks[1] ?? tasks[0] ?? null;
  const updated = generatedAt
    ? formatLocaleDate(language, new Date(generatedAt), { dateStyle: "medium", timeStyle: "short" })
    : null;
  const medicineLabel = cabinetCount === null
    ? copy("Chưa có dữ liệu thuốc", "Medicine data unavailable")
    : copy(
      `${formatLocaleNumber(language, cabinetCount)} thuốc đang theo dõi`,
      `${formatLocaleNumber(language, cabinetCount)} medicines tracked`,
    );
  const greeting = roleGreeting[role][language];
  const isDoctor = role === "doctor";
  const statusText = loading
    ? copy("Đang cập nhật", "Updating")
    : error
      ? copy("Chưa xác định", "Unknown")
      : needsAttention
        ? copy("Có mục cần xem lại", "Items need review")
        : copy("Hoạt động bình thường", "Operational");

  const shortcuts = shortcutSets[role === "normal" ? "researcher" : role];

  const primary = useMemo(() => {
    if (activeCase) {
      const caseHref = activeCase.status === "completed" || activeCase.status === "ready"
        ? `/council/result?caseId=${activeCase.id}`
        : `/council/new/intake?caseId=${activeCase.id}`;
      return { href: caseHref, label: copy("Tiếp tục ca lâm sàng", "Resume clinical case") };
    }
    if (nextTask) return { href: nextTask.href, label: copy("Làm việc tiếp theo", "Continue next task") };
    return { href: isDoctor ? "/clinical" : "/today", label: isDoctor ? copy("Trung tâm Lâm sàng", "Clinical Center") : copy("Xem hôm nay", "View today") };
  }, [activeCase, copy, isDoctor, nextTask]);

  const caseStatus = activeCase ? getCaseStatusChip(activeCase.status, language) : null;
  const activeCaseHref = activeCase
    ? activeCase.status === "completed" || activeCase.status === "ready"
      ? `/council/result?caseId=${activeCase.id}`
      : `/council/new/intake?caseId=${activeCase.id}`
    : "/council/new";

  return (
    <PageShell
      title={t(language, "navigation.item.dashboard.title")}
      description={t(language, "navigation.item.dashboard.subtitle")}
      variant="plain"
    >
      <div className="space-y-8">
        {/* Clinician Command Center & Work Workspace Hero */}
        <section className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-sm">
          <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[var(--brand-600)]/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[var(--brand-primary)]/5 blur-3xl" />

          <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[color:var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[var(--text-brand)]">
                  <Icon name="clinical-notes" size={14} />
                  {isDoctor
                    ? copy("TRUNG TÂM LÂM SÀNG & HỘI CHẨN", "CLINICAL COMMAND CENTER")
                    : copy("Không gian công việc", "Work workspace")}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                  <Icon name="check" size={13} className="text-[var(--text-brand)]" />
                  {copy("DrugBank v5.1.10 Verified", "DrugBank v5.1.10 Verified")}
                </span>
              </div>

              <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                {greeting}
              </h1>

              <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
                {loading
                  ? copy("CLARA đang tổng hợp các việc và cảnh báo thuộc phạm vi tài khoản của bạn.", "CLARA is compiling the tasks and alerts available to your account.")
                  : error
                    ? copy("Chưa thể xác định trạng thái công việc. Các chức năng riêng lẻ vẫn có thể mở trực tiếp.", "Work status is currently unknown. Individual tools remain directly available.")
                    : needsAttention
                  ? copy("Có một số thông tin cần bạn kiểm tra. CLARA đã đưa việc quan trọng nhất lên trước.", "Some information needs review. CLARA has placed the most important action first.")
                  : copy("Không có việc nào được CLARA đánh dấu trong dữ liệu vừa tải. Bạn vẫn cần áp dụng đánh giá chuyên môn phù hợp.", "No items were flagged in the data just loaded. Appropriate professional judgment is still required.")}
              </p>

              <div className="flex flex-wrap items-center gap-2 pt-2">
                <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                  <span className={`h-2.5 w-2.5 rounded-full ${loading || error ? "bg-[var(--text-muted)]" : needsAttention ? "bg-[var(--status-warn-text)] animate-pulse" : "bg-[var(--success-500)]"}`} />
                  {copy("Trạng thái công việc", "Work status")}: {statusText}
                </span>
                <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                  <Icon name="medication" size={16} />
                  {medicineLabel}
                </span>
                {activeCase ? (
                  <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                    <Icon name="progress" size={16} className="text-[var(--text-brand)]" />
                    {copy(`Ca #${activeCase.id} đang mở`, `Case #${activeCase.id} active`)}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex flex-wrap gap-3 lg:flex-col lg:items-end">
              <Link href={primary.href} className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)]">
                <Icon name="progress" size={18} />
                {primary.label}
              </Link>
              {isDoctor ? (
                <Link href="/council/new" className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]">
                  <Icon name="progress" size={14} />
                  {copy("+ Ca hội chẩn mới", "+ New Council Case")}
                </Link>
              ) : null}
            </div>
          </div>
        </section>

        {error ? (
          <section className="rounded-xl border border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] p-5" role="alert">
            <h2 className="font-semibold text-[var(--status-warn-text)]">{copy("Chưa tải được tổng quan", "Overview unavailable")}</h2>
            <p className="mt-1 text-sm text-[var(--status-warn-text)]">{copy("Các trang chăm sóc vẫn dùng được. Bạn có thể thử tải lại tổng quan.", "Care pages remain available. You can retry loading the overview.")}</p>
            <button type="button" onClick={() => void load()} className="mt-4 min-h-11 rounded-lg border border-[color:var(--status-warn-border)] px-4 text-sm font-semibold text-[var(--status-warn-text)]">
              {copy("Thử lại", "Retry")}
            </button>
          </section>
        ) : null}

        {ready && topAlert && topAlert.severity === "critical" ? (
          <section className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] p-5 shadow-sm" role="alert">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <Icon name="warning" size={22} className="text-[var(--status-danger-text)] animate-pulse" />
                <div>
                  <h2 className="font-semibold text-base">{copy("Cảnh báo đỏ lâm sàng (Critical Alert)", "Critical Clinical Red Flag")}</h2>
                  <p className="mt-1 text-sm leading-6">{topAlert.message}</p>
                </div>
              </div>
              <Link href={topAlert.href} className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg border border-current bg-[var(--surface-panel)] px-4 text-sm font-bold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]">
                {copy("Mở mục liên quan", "Open related item")}
              </Link>
            </div>
          </section>
        ) : null}

        {/* Quick Case Resumption with case status chips and last updated time */}
        {activeCase ? (
          <section aria-labelledby="dashboard-active-case" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="dashboard-active-case" className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]">
                <Icon name="progress" className="text-[var(--brand-600)]" />
                {copy("Ca lâm sàng đang thực hiện", "Active Clinical Case")}
              </h2>
              <Link href="/council/new" className="text-xs font-bold text-[var(--text-brand)] hover:underline">
                + {copy("Tạo ca mới", "New case")}
              </Link>
            </div>

            <article className="group rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 transition-all hover:border-[color:var(--brand-600)] hover:shadow-md">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
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
                    {copy("Tiếp tục ca này", "Resume case")}
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
          </section>
        ) : null}

        {/* 4 Primary Clinical Tool Cards */}
        <section aria-labelledby="dashboard-clinical-tools" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 id="dashboard-clinical-tools" className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]">
              <Icon name="clinical-notes" className="text-[var(--text-brand)]" />
              {copy("4 công cụ lâm sàng cốt lõi", "4 Primary Clinical Tools")}
            </h2>
            <Link href="/clinical" className="text-xs font-bold text-[var(--text-brand)] hover:underline">
              {copy("Mở toàn bộ trung tâm lâm sàng", "Open full clinical center")} →
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PRIMARY_CLINICAL_TOOLS.map((tool) => (
              <Link
                key={tool.id}
                href={tool.href}
                className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                      <Icon name={tool.icon} size={22} />
                    </span>
                    <span className="rounded-full border border-[color:var(--brand-primary)]/20 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                      {tool.badge}
                    </span>
                  </div>

                  <h3 className="mt-4 text-base font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                    {tool[language].title}
                  </h3>

                  <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {tool[language].desc}
                  </p>
                </div>

                <div className="mt-5 flex items-center justify-between pt-2">
                  <span className="text-xs font-bold text-[var(--text-brand)]">
                    {copy("Truy cập", "Open")}
                  </span>
                  <span className="grid h-6 w-6 place-items-center rounded-md bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:translate-x-1 group-hover:bg-[var(--brand-600)] group-hover:text-[var(--on-secondary-container)]">
                    <Icon name="arrow-right" size={13} />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Real-time Server Alerts and DrugBank Updates Section */}
        <section aria-labelledby="dashboard-alerts-drugbank" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 id="dashboard-alerts-drugbank" className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]">
              <Icon name="warning" className="text-[var(--brand-600)]" />
              {copy("Cảnh báo máy chủ & Cập nhật Dược lý", "Real-Time Server Alerts & DrugBank Updates")}
            </h2>
            <span className="text-xs font-semibold text-[var(--text-muted)]">
              {copy("DrugBank v5.1.10 & FIDES Guardrails", "DrugBank v5.1.10 & FIDES Guardrails")}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Panel A: Server Alerts */}
            <div className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                    <Icon name="warning" size={18} />
                  </span>
                  <div>
                    <h3 className="font-bold text-base text-[var(--text-primary)]">
                      {copy("Cảnh báo máy chủ & An toàn", "Server & Safety Alerts")}
                    </h3>
                    <p className="text-xs text-[var(--text-muted)]">
                      {copy("Giám sát an toàn FIDES và chốt chặn pháp lý", "FIDES safety verification and legal guardrails")}
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
                <div className="space-y-3 pt-1">
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
                        <Icon name="warning" size={16} className="mt-0.5 shrink-0" />
                        <span className="text-xs font-semibold leading-relaxed">{alert.message}</span>
                      </div>
                      {alert.href ? (
                        <Link href={alert.href} className="inline-flex shrink-0 items-center gap-1 text-xs font-bold underline hover:opacity-80">
                          {copy("Xem", "View")}
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
                    <span>{copy("Hệ thống an toàn lâm sàng hoạt động bình thường", "Clinical safety system operational")}</span>
                  </div>
                  <p className="leading-relaxed">
                    {copy(
                      "Tất cả quy tắc FIDES, chốt chặn kê đơn và kiểm tra tương tác thuốc đang được giám sát chặt chẽ.",
                      "All FIDES verification rules, legal hard-guards, and drug-interaction monitors are fully operational.",
                    )}
                  </p>
                </div>
              )}
            </div>

            {/* Panel B: DrugBank & Knowledge Updates */}
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
                  label={copy("Đã xác thực", "Verified")}
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
                        ? copy("Chưa có dữ liệu thuốc", "Medicine data unavailable")
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
                    <span>{copy("Tủ thuốc", "Cabinet")}</span>
                  </Link>

                  <Link
                    href="/evidence"
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] hover:text-[var(--text-brand)]"
                  >
                    <Icon name="progress" size={14} />
                    <span>{copy("Thư viện bằng chứng", "Evidence")}</span>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Next action section */}
        <section aria-labelledby="dashboard-next" className="space-y-4">
          <h2 id="dashboard-next" className="flex items-center gap-2 text-xl font-semibold text-[var(--text-primary)]">
            <Icon name="progress" className="text-[var(--brand-600)]" />
            {copy("Việc tiếp theo", "Next action")}
          </h2>
          {loading ? (
            <div className="h-28 animate-pulse rounded-xl bg-[var(--surface-muted)]" role="status" aria-live="polite" aria-label={copy("Đang tải việc tiếp theo", "Loading next action")} />
          ) : error ? null : nextTask ? (
            <article className={`flex flex-col gap-5 rounded-xl border p-5 sm:flex-row sm:items-center sm:justify-between ${toneClasses(nextTask.tone)}`}>
              <div className="flex min-w-0 items-start gap-4">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]"><Icon name={nextTask.tone === "critical" ? "warning" : "clinical-notes"} /></span>
                <div><h3 className="font-semibold text-[var(--text-primary)]">{nextTask.title}</h3><p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{nextTask.detail}</p></div>
              </div>
              <Link href={nextTask.href} className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg border border-[color:var(--shell-border-strong)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:border-[color:var(--text-brand)] hover:text-[var(--text-brand)]">
                {copy("Mở việc này", "Open task")}
              </Link>
            </article>
          ) : (
            <div className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
              <h3 className="font-semibold text-[var(--text-primary)]">{copy("Hôm nay chưa có việc cần xử lý", "No action is due today")}</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{copy("Bạn có thể mở LifeMap hoặc hỏi CLARA khi cần.", "Open LifeMap or ask CLARA whenever you need help.")}</p>
            </div>
          )}
        </section>

        {/* Workflow section */}
        <section aria-labelledby="dashboard-workflow" className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <h2 id="dashboard-workflow" className="flex items-center gap-2 text-xl font-semibold text-[var(--text-primary)]"><Icon name="progress" className="text-[var(--text-brand)]" />{copy("Luồng công việc", "Workflow")}</h2>
            <Link href={featuredTask?.href ?? "/chat"} className="text-sm font-semibold text-[var(--text-brand)] hover:underline">{copy("Mở công việc", "Open work")}</Link>
          </div>
          <div className="grid gap-5 md:grid-cols-[minmax(0,2fr)_minmax(220px,1fr)]">
            <Link href={featuredTask?.href ?? "/chat"} className="group rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 transition-colors hover:border-[color:var(--text-brand)]">
              <span className="inline-flex rounded-md bg-[var(--surface-brand-soft)] px-3 py-1 text-xs font-semibold text-[var(--text-brand)]">{featuredTask ? copy("Đang chờ xử lý", "Pending") : copy("Sẵn sàng", "Ready")}</span>
              <h3 className="mt-4 text-lg font-semibold text-[var(--text-primary)]">{featuredTask?.title ?? copy("Bắt đầu một công việc với CLARA", "Start a task with CLARA")}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{featuredTask?.detail ?? copy("Chọn một lối tắt phù hợp với vai trò của bạn ở bên dưới.", "Choose a role-appropriate shortcut below.")}</p>
              <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-brand)]">{copy("Tiếp tục", "Continue")}<Icon name="arrow-right" size={16} className="transition group-hover:translate-x-1" /></span>
            </Link>
            <Link href="/chat" className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] p-6 text-center transition hover:border-[color:var(--text-brand)]">
              <span className="grid h-12 w-12 place-items-center rounded-full bg-[var(--surface-panel)] text-[var(--text-brand)]"><Icon name="clinical-notes" /></span>
              <h3 className="mt-4 font-semibold text-[var(--text-primary)]">{copy("Hỏi CLARA", "Ask CLARA")}</h3>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{copy("Bắt đầu từ một câu hỏi rõ ràng.", "Start with one clear question.")}</p>
            </Link>
          </div>
        </section>

        {/* Shortcuts & Information grid */}
        <section className="grid gap-6 lg:grid-cols-5">
          <div className="space-y-4 lg:col-span-3">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">{copy("Lối tắt", "Shortcuts")}</h2>
            <div className={`grid grid-cols-1 gap-3 ${shortcuts.length === 4 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-3"}`}>
              {shortcuts.map((item) => <Link key={item.href} href={item.href} className="flex min-h-28 flex-col items-center justify-center gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-center transition hover:border-[color:var(--text-brand)] hover:bg-[var(--surface-muted)]"><span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]"><Icon name={item.icon} /></span><span className="text-sm font-semibold text-[var(--text-primary)]">{item[language]}</span></Link>)}
            </div>
          </div>
          <div className="space-y-4 lg:col-span-2">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">{copy("Thông tin của bạn", "Your information")}</h2>
            <div className="divide-y divide-[color:var(--shell-border)] overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              <Link href="/medicines" className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="medication" size={18} />{copy("Thuốc đang theo dõi", "Tracked medicines")}</span><span className="text-xs font-semibold text-[var(--text-brand)]">{medicineLabel}</span></Link>
              <Link href={topAlert?.href ?? "/dashboard"} className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="warning" size={18} />{copy("Mục cần xem", "Items to review")}</span><span className="text-xs font-semibold text-[var(--text-secondary)]">{reviewCount === null ? copy("Chưa rõ", "Unknown") : formatLocaleNumber(language, reviewCount)}</span></Link>
              <Link href="/admin/analytics" className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="progress" size={18} />{copy("Phân tích hệ thống", "System analytics")}</span><span className="text-xs font-semibold text-[var(--text-brand)]">{copy("Mở", "Open")}</span></Link>
              <Link href="/chat" className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="clinical-notes" size={18} />{copy("Hỗ trợ từ CLARA", "CLARA assistance")}</span><span className="text-xs font-semibold text-[var(--text-brand)]">{copy("Mở", "Open")}</span></Link>
            </div>
          </div>
        </section>

        {/* Recent Activity */}
        <section aria-labelledby="dashboard-recent" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="dashboard-recent" className="text-xl font-semibold text-[var(--text-primary)]">{copy("Hoạt động gần đây", "Recent activity")}</h2>{updated ? <span className="text-xs text-[var(--text-muted)]">{copy("Cập nhật", "Updated")}: {updated}</span> : null}</div>
          <div className="divide-y divide-[color:var(--shell-border)] overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            {recent.length ? recent.slice(0, 3).map((item) => (
              <Link key={item.id} href="/chat" className="flex items-start gap-4 p-4 transition hover:bg-[var(--surface-muted)]">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]"><Icon name="clinical-notes" size={18} /></span>
                <div className="min-w-0 flex-1"><h3 className="truncate text-sm font-semibold text-[var(--text-primary)]">{item.query}</h3><p className="mt-1 text-xs text-[var(--text-secondary)]">{formatLocaleDate(language, new Date(item.createdAt), { dateStyle: "medium", timeStyle: "short" })}</p></div>
              </Link>
            )) : <p className="p-5 text-sm text-[var(--text-secondary)]">{copy("Chưa có hoạt động gần đây để hiển thị.", "No recent activity to display.")}</p>}
          </div>
        </section>
      </div>
    </PageShell>
  );
}
