"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Icon, { type IconName } from "@/components/ui/icon";
import { getRole, type UserRole } from "@/lib/auth-store";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import {
  getSystemDashboard,
  normalizeSystemDashboard,
  type SystemDashboardAlert,
} from "@/lib/system";
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
  doctor: { vi: "Chào bác sĩ", en: "Hello, clinician" },
  admin: { vi: "Chào quản trị viên", en: "Hello, administrator" },
};

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
    { href: "/chat", icon: "clinical-notes", vi: "Hỏi CLARA", en: "Ask CLARA" },
    { href: "/council", icon: "progress", vi: "Hội chẩn", en: "Council" },
    { href: "/scribe", icon: "clinical-notes", vi: "Ghi chép khám", en: "Clinical notes" },
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

export default function DashboardPage() {
  const language = useUILanguage();
  const [role, setRole] = useState<UserRole>("normal");
  const [tasks, setTasks] = useState<DashboardTask[]>([]);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const [alerts, setAlerts] = useState<SystemDashboardAlert[]>([]);
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
  const statusText = loading
    ? copy("Đang cập nhật", "Updating")
    : error
      ? copy("Chưa xác định", "Unknown")
      : needsAttention
        ? copy("Có mục cần xem lại", "Items need review")
        : copy("Không có việc CLARA đánh dấu", "No CLARA-flagged items");

  const shortcuts = shortcutSets[role === "normal" ? "researcher" : role];

  const primary = useMemo(() => {
    if (nextTask) return { href: nextTask.href, label: copy("Làm việc tiếp theo", "Continue next task") };
    return { href: "/today", label: copy("Xem hôm nay", "View today") };
  }, [copy, nextTask]);

  return (
    <PageShell
      title={t(language, "navigation.item.dashboard.title")}
      description={t(language, "navigation.item.dashboard.subtitle")}
      variant="plain"
    >
      <div className="space-y-8">
        <section className="relative overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 shadow-[var(--shadow-soft)] sm:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-[color:var(--surface-brand-soft)] blur-3xl" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                {copy("Không gian công việc", "Work workspace")}
              </p>
              <h2 className="mt-2 text-3xl font-bold tracking-[-0.035em] text-[var(--text-primary)] sm:text-4xl">
                {greeting}
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                {loading
                  ? copy("CLARA đang tổng hợp các việc và cảnh báo thuộc phạm vi tài khoản của bạn.", "CLARA is compiling the tasks and alerts available to your account.")
                  : error
                    ? copy("Chưa thể xác định trạng thái công việc. Các chức năng riêng lẻ vẫn có thể mở trực tiếp.", "Work status is currently unknown. Individual tools remain directly available.")
                    : needsAttention
                  ? copy("Có một số thông tin cần bạn kiểm tra. CLARA đã đưa việc quan trọng nhất lên trước.", "Some information needs review. CLARA has placed the most important action first.")
                  : copy("Không có việc nào được CLARA đánh dấu trong dữ liệu vừa tải. Bạn vẫn cần áp dụng đánh giá chuyên môn phù hợp.", "No items were flagged in the data just loaded. Appropriate professional judgment is still required.")}
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                  <span className={`h-2 w-2 rounded-full ${loading || error ? "bg-[var(--text-muted)]" : needsAttention ? "bg-[var(--status-warn-text)]" : "bg-[var(--success-500)]"}`} />
                  {copy("Trạng thái công việc", "Work status")}: {statusText}
                </span>
                <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                  <Icon name="medication" size={16} />
                  {medicineLabel}
                </span>
              </div>
            </div>
            <Link href={primary.href} className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-xl bg-[var(--brand-600)] px-6 text-sm font-semibold text-white shadow-[var(--shadow-soft)] transition hover:bg-[var(--brand-700)]">
              <Icon name="progress" size={18} />
              {primary.label}
            </Link>
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

        {ready && topAlert ? (
          <section className={`rounded-xl border p-5 ${topAlert.severity === "critical" ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]" : "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]"}`} role="alert">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <Icon name="warning" className={topAlert.severity === "critical" ? "text-[var(--status-danger-text)]" : "text-[var(--status-warn-text)]"} />
                <div>
                  <h2 className={`font-semibold ${topAlert.severity === "critical" ? "text-[var(--status-danger-text)]" : "text-[var(--status-warn-text)]"}`}>{copy("Cần xem lại", "Review required")}</h2>
                  <p className={`mt-1 text-sm leading-6 ${topAlert.severity === "critical" ? "text-[var(--status-danger-text)]" : "text-[var(--status-warn-text)]"}`}>{topAlert.message}</p>
                </div>
              </div>
              <Link href={topAlert.href} className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg border border-current px-4 text-sm font-semibold text-[var(--text-primary)]">
                {copy("Mở mục liên quan", "Open related item")}
              </Link>
            </div>
          </section>
        ) : null}

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

        <section aria-labelledby="dashboard-workflow" className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <h2 id="dashboard-workflow" className="flex items-center gap-2 text-xl font-semibold text-[var(--text-primary)]"><Icon name="progress" className="text-[var(--text-brand)]" />{copy("Luồng công việc", "Workflow")}</h2>
            <Link href={featuredTask?.href ?? "/chat"} className="text-sm font-semibold text-[var(--text-brand)] hover:underline">{copy("Mở công việc", "Open work")}</Link>
          </div>
          <div className="grid gap-5 md:grid-cols-[minmax(0,2fr)_minmax(220px,1fr)]">
            <Link href={featuredTask?.href ?? "/chat"} className="group rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)] transition hover:border-[color:var(--text-brand)]">
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

        <section className="grid gap-6 lg:grid-cols-5">
          <div className="space-y-4 lg:col-span-3">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">{copy("Lối tắt", "Shortcuts")}</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {shortcuts.map((item) => <Link key={item.href} href={item.href} className="flex min-h-28 flex-col items-center justify-center gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-center transition hover:border-[color:var(--text-brand)] hover:bg-[var(--surface-muted)]"><span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]"><Icon name={item.icon} /></span><span className="text-sm font-semibold text-[var(--text-primary)]">{item[language]}</span></Link>)}
            </div>
          </div>
          <div className="space-y-4 lg:col-span-2">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">{copy("Thông tin của bạn", "Your information")}</h2>
            <div className="divide-y divide-[color:var(--shell-border)] overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              <Link href="/medicines" className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="medication" size={18} />{copy("Thuốc đang theo dõi", "Tracked medicines")}</span><span className="text-xs font-semibold text-[var(--text-brand)]">{medicineLabel}</span></Link>
              <Link href={topAlert?.href ?? "/dashboard"} className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="warning" size={18} />{copy("Mục cần xem", "Items to review")}</span><span className="text-xs font-semibold text-[var(--text-secondary)]">{reviewCount === null ? copy("Chưa rõ", "Unknown") : formatLocaleNumber(language, reviewCount)}</span></Link>
              <Link href="/chat" className="flex min-h-14 items-center justify-between gap-4 px-4 hover:bg-[var(--surface-muted)]"><span className="flex items-center gap-3 text-sm text-[var(--text-primary)]"><Icon name="clinical-notes" size={18} />{copy("Hỗ trợ từ CLARA", "CLARA assistance")}</span><span className="text-xs font-semibold text-[var(--text-brand)]">{copy("Mở", "Open")}</span></Link>
            </div>
          </div>
        </section>

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
