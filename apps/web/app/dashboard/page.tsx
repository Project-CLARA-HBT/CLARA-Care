"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import { getSystemDashboard, normalizeSystemDashboard } from "@/lib/system";

type TodayTask = {
  id: string;
  title: string;
  detail: string;
  tone: "normal" | "warn" | "critical";
  href: string;
};
type WorkflowState = "done" | "current" | "pending";

type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
  status: string;
  tone: "primary" | "secondary" | "muted";
};

type QuickAccess = {
  href: string;
  title: string;
  detail: string;
  icon: string;
};

const ROLE_GREETINGS: Record<UserRole, string> = {
  normal: "Chào buổi tối",
  researcher: "Chào buổi tối, Nhà nghiên cứu",
  doctor: "Chào buổi tối, Bác sĩ",
  admin: "Chào buổi tối, Quản trị viên",
};

const QUICK_ACCESS: QuickAccess[] = [
  { href: "/chat", title: "Mở CLARA Chat", detail: "Hỏi đáp có dẫn nguồn", icon: "search" },
  { href: "/council", title: "Mở hội chẩn AI", detail: "Phân tích ca bệnh", icon: "forum" },
  { href: "/selfmed", title: "Rà soát tủ thuốc", detail: "Đối chiếu đơn thuốc", icon: "medication" },
  { href: "/careguard", title: "Kiểm tra CareGuard", detail: "Theo dõi cảnh báo an toàn", icon: "security" },
  { href: "/scribe", title: "Mở Medical Scribe", detail: "Ghi âm và ghi chép bệnh án", icon: "mic" },
];

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatRelative(value: number): string {
  const now = Date.now();
  const diffMs = Math.max(0, now - value);
  const diffHour = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHour === 0) return "Vừa xong";
  if (diffHour < 24) return `${diffHour} giờ trước`;
  return "Hôm qua";
}

function statusPillClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["critical", "high", "error", "fail"].some((token) => normalized.includes(token))) {
    return "bg-red-500/15 text-red-700 dark:text-red-300";
  }
  if (["draft", "pending", "warning", "warn", "nháp", "chờ"].some((token) => normalized.includes(token))) {
    return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
  }
  if (["hoàn tất", "da ra soat", "đã rà soát", "xong"].some((token) => normalized.includes(token))) {
    return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  }
  return "bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function activityToneClass(tone: ActivityItem["tone"]): string {
  if (tone === "primary") return "border-l-[var(--brand-600)]";
  if (tone === "secondary") return "border-l-[var(--brand-500)]";
  return "border-l-[color:var(--shell-border)]";
}

export default function DashboardPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [errorCount, setErrorCount] = useState<number | null>(null);
  const [cabinetCount, setCabinetCount] = useState<number | null>(null);
  const [expiringSoonCount, setExpiringSoonCount] = useState<number | null>(null);
  const [expiredCount, setExpiredCount] = useState<number | null>(null);
  const [enabledSources, setEnabledSources] = useState(0);
  const [totalSources, setTotalSources] = useState(0);
  const [flowEnabledCount, setFlowEnabledCount] = useState(0);
  const [healthStatus, setHealthStatus] = useState("unknown");
  const [mlStatus, setMlStatus] = useState("unknown");
  const [recentQueries, setRecentQueries] = useState<Array<{ id: string; query: string; createdAt: number }>>([]);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [serverTasks, setServerTasks] = useState<TodayTask[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const rawDashboard = await getSystemDashboard();
      const dashboard = normalizeSystemDashboard(rawDashboard);

      setRole((dashboard.user.role as UserRole) ?? getRole());
      setHealthStatus(dashboard.runtime.apiStatus);
      setMlStatus(dashboard.runtime.mlStatus);
      setRequestCount(dashboard.runtime.requestCount);
      setErrorCount(dashboard.runtime.errorCount);

      setCabinetCount(dashboard.cabinet.itemTotal);
      setExpiringSoonCount(dashboard.cabinet.expiringSoonTotal);
      setExpiredCount(dashboard.cabinet.expiredTotal);

      setEnabledSources(dashboard.sources.enabled);
      setTotalSources(dashboard.sources.total);
      setFlowEnabledCount(dashboard.sources.flowEnabledCount);

      setRecentQueries(dashboard.research.recentQueries);
      setAlerts(dashboard.alerts);
      setServerTasks(
        dashboard.tasks.map((task) => ({
          id: task.id,
          title: task.title,
          detail: task.detail,
          tone: task.tone,
          href: task.href,
        }))
      );
    } catch {
      setAlerts(["Không thể tải dữ liệu dashboard tổng hợp."]);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    void refreshDashboard();
  }, [refreshDashboard]);

  const greeting = ROLE_GREETINGS[role] ?? ROLE_GREETINGS.normal;

  const activeCases = useMemo(() => {
    const inferred = Math.max(recentQueries.length, Math.max(0, Math.trunc((requestCount ?? 0) / 2)));
    return Math.max(1, Math.min(99, inferred || 12));
  }, [recentQueries.length, requestCount]);

  const cautionCases = useMemo(() => {
    const risk = (alerts.length > 0 ? 1 : 0) + ((expiredCount ?? 0) > 0 ? 1 : 0);
    return Math.max(0, Math.min(8, risk));
  }, [alerts.length, expiredCount]);

  const councilTotal = 12;
  const councilDone = useMemo(() => Math.max(0, Math.min(councilTotal, recentQueries.length)), [recentQueries.length]);

  const activityItems = useMemo<ActivityItem[]>(() => {
    if (recentQueries.length > 0) {
      return recentQueries.slice(0, 3).map((item, index) => ({
        id: item.id,
        title: item.query,
        detail: `Mã truy vấn #${item.id.slice(0, 8)} • Hỏi đáp lâm sàng`,
        timestamp: formatRelative(item.createdAt),
        status: index === 0 ? "Hoàn tất" : index === 1 ? "Đã rà soát" : "Bản nháp",
        tone: index === 0 ? "secondary" : index === 1 ? "muted" : "primary",
      }));
    }

    return [
      {
        id: "default-1",
        title: "So sánh DASH vs Địa Trung Hải",
        detail: "Mã bệnh nhân: #8821 • Hỏi đáp lâm sàng",
        timestamp: "2 giờ trước",
        status: "Hoàn tất",
        tone: "secondary",
      },
      {
        id: "default-2",
        title: "Phân tích tương tác Metformin",
        detail: "Mã bệnh nhân: #9042 • Đồng bộ tủ thuốc",
        timestamp: "5 giờ trước",
        status: "Đã rà soát",
        tone: "muted",
      },
      {
        id: "default-3",
        title: "Ghi âm thăm khám: Nguyễn Văn A",
        detail: "Mã bệnh nhân: #7731 • Biên bản Scribe",
        timestamp: "Hôm qua",
        status: "Bản nháp",
        tone: "primary",
      },
    ];
  }, [recentQueries]);

  const assistantInsight = useMemo(() => {
    if (alerts.length > 0) return alerts[0];
    const err = Math.max(0, errorCount ?? 0);
    if (err > 0) {
      return `Runtime đang ghi nhận ${err} lỗi gần nhất. Ưu tiên rà soát lại flow verification trước khi chốt khuyến nghị.`;
    }
    return "Pipeline hoạt động ổn định. Có thể ưu tiên hội chẩn các ca đa thuốc để tăng chất lượng quyết định lâm sàng.";
  }, [alerts, errorCount]);

  const todayTasks = useMemo<TodayTask[]>(() => {
    if (serverTasks.length > 0) return serverTasks.slice(0, 4);
    return [
      {
        id: "review-meds",
        title: "Rà soát thuốc",
        detail: "Kiểm tra danh mục thuốc hiện tại",
        tone: "normal",
        href: "/selfmed",
      },
      {
        id: "check-ddi",
        title: "Kiểm tra DDI",
        detail: "Đối chiếu tương tác đa thuốc",
        tone: "warn",
        href: "/careguard",
      },
      {
        id: "conduct-council",
        title: "Chạy hội chẩn",
        detail: "Hội chẩn các ca cần quyết định",
        tone: "normal",
        href: "/council",
      },
      {
        id: "record-findings",
        title: "Ghi nhận kết quả",
        detail: "Ghi nhận kết luận và theo dõi",
        tone: "normal",
        href: "/scribe",
      },
    ];
  }, [serverTasks]);

  const workflowTasks = useMemo<TodayTask[]>(
    () =>
      (todayTasks.length >= 4
        ? todayTasks.slice(0, 4)
        : [
            ...todayTasks,
            { id: "fallback-1", title: "Rà soát thuốc", detail: "", tone: "normal" as TodayTask["tone"], href: "/selfmed" },
            { id: "fallback-2", title: "Kiểm tra DDI", detail: "", tone: "warn" as TodayTask["tone"], href: "/careguard" },
            { id: "fallback-3", title: "Chạy hội chẩn", detail: "", tone: "normal" as TodayTask["tone"], href: "/council" },
            { id: "fallback-4", title: "Ghi nhận kết quả", detail: "", tone: "normal" as TodayTask["tone"], href: "/scribe" },
          ]).slice(0, 4),
    [todayTasks]
  );

  const workflowStates = useMemo<WorkflowState[]>(() => {
    const medsDone = (cabinetCount ?? 0) > 0;
    const ddiDone = (requestCount ?? 0) > 0;
    const councilDoneStep = councilDone >= councilTotal;
    const councilRunning = !councilDoneStep && councilDone > 0;
    const recordDone = recentQueries.length >= 3;

    return [
      medsDone ? "done" : "current",
      ddiDone ? "done" : medsDone ? "current" : "pending",
      councilDoneStep ? "done" : councilRunning ? "current" : "pending",
      recordDone ? "done" : councilRunning || councilDoneStep ? "current" : "pending",
    ];
  }, [cabinetCount, councilDone, recentQueries.length, requestCount]);

  const workflowProgress = useMemo(() => {
    const completed = workflowStates.filter((state) => state === "done").length;
    return Math.round((completed / 4) * 100);
  }, [workflowStates]);

  return (
    <PageShell title="" description="" variant="plain">
      <div className="space-y-10">
        <section className="flex flex-wrap items-end justify-between gap-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)]">
          <div>
            <h2 className="mb-2 text-3xl font-extrabold tracking-tight text-[var(--text-brand)] sm:text-4xl">{greeting}</h2>
            <p className="text-sm text-[var(--text-secondary)] sm:text-lg">
              Hệ thống đang theo dõi <span className="font-bold text-[var(--text-brand)]">{activeCases} ca lâm sàng</span>. Có {" "}
              <span className="font-bold text-[var(--text-brand)]">{cautionCases}</span> trường hợp cần lưu ý đặc biệt tối nay.
            </p>
          </div>
          <div className="rounded-xl border-l-4 border-[var(--brand-600)] bg-cyan-500/10 px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--brand-600)]">Trạng thái AI</p>
            <p className="text-sm font-semibold text-[var(--text-primary)]">Pipeline ổn định</p>
          </div>
        </section>

        <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)]">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Luồng công việc hàng ngày</h3>
            <span className="text-xs text-[var(--text-secondary)]">Tiến độ: {workflowProgress}% hoàn thành</span>
          </div>

          <div className="relative grid gap-4 md:grid-cols-4">
            <div className="absolute left-[12.5%] right-[12.5%] top-8 hidden h-1 overflow-hidden rounded-full bg-[var(--surface-muted)] md:block">
              <div
                className="h-full rounded-full bg-[var(--brand-500)] transition-[width] duration-300 ease-out"
                style={{ width: `${Math.max(0, Math.min(100, workflowProgress))}%` }}
              />
            </div>

            {workflowTasks.map((task, index) => {
              const state = workflowStates[index] ?? "pending";
              const isDone = state === "done";
              const isCurrent = state === "current";
              return (
                <Link key={task.id} href={task.href} className="relative z-10 rounded-xl p-3 text-center hover:bg-[var(--surface-muted)]">
                  <div
                    className={[
                      "mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full",
                      isDone
                        ? "bg-[var(--brand-500)] text-white"
                        : isCurrent
                          ? "border-4 border-[var(--brand-500)] bg-white text-[var(--brand-600)] dark:bg-slate-900"
                          : "bg-[var(--surface-muted)] text-[var(--text-muted)]",
                    ].join(" ")}
                  >
                    {isDone ? (
                      <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                        check
                      </span>
                    ) : isCurrent ? (
                      <span className="text-xs font-bold">{String(index + 1).padStart(2, "0")}</span>
                    ) : (
                      <span className="material-symbols-outlined text-[18px]">edit_note</span>
                    )}
                  </div>
                  <p className="text-xs font-bold text-[var(--text-primary)]">{task.title}</p>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="grid grid-cols-12 gap-6">
          <article className="col-span-12 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 lg:col-span-4">
            <div className="mb-4 flex items-start justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-[var(--text-brand)]">
                <span className="material-symbols-outlined">groups</span>
              </div>
              <span className="rounded bg-blue-500/10 px-2 py-1 text-[10px] font-bold">Tiến độ hội chẩn</span>
            </div>
            <h4 className="text-2xl font-bold text-[var(--text-brand)]">
              {councilDone} / {councilTotal} ca
            </h4>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">Đã hoàn thành hội chẩn AI</p>
            <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
              <div className="h-full bg-[var(--brand-500)]" style={{ width: `${(councilDone / councilTotal) * 100}%` }} />
            </div>
          </article>

          <article className="col-span-12 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 lg:col-span-4">
            <div className="mb-4 flex items-start justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-700 dark:text-cyan-300">
                <span className="material-symbols-outlined">pill</span>
              </div>
              <span className="rounded bg-red-500/15 px-2 py-1 text-[10px] font-bold text-red-700 dark:text-red-300">Cảnh báo</span>
            </div>
            <h4 className="text-2xl font-bold text-[var(--text-brand)]">{formatCount(cabinetCount)} thuốc đang theo dõi</h4>
            <p className="mt-1 text-xs font-bold text-red-700 dark:text-red-300">
              {alerts[0] ?? "Hệ thống phát hiện tín hiệu tương tác thuốc cần ưu tiên kiểm tra."}
            </p>
            <div className="mt-4 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
              <span className="h-2 w-2 rounded-full bg-red-500" />
              {formatCount(expiredCount)} thuốc hết hạn • {formatCount(expiringSoonCount)} sắp hết hạn
            </div>
          </article>

          <article className="col-span-12 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 lg:col-span-4">
            <div className="mb-4 flex items-start justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-700 dark:text-indigo-300">
                <span className="material-symbols-outlined">menu_book</span>
              </div>
              <span className="rounded bg-cyan-500/15 px-2 py-1 text-[10px] font-bold text-cyan-700 dark:text-cyan-300">Tín hiệu</span>
            </div>
            <h4 className="text-2xl font-bold text-[var(--text-brand)]">{formatCount(enabledSources)} nguồn đang bật</h4>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Tổng nguồn: {formatCount(totalSources)} • API: {healthStatus.toUpperCase()} • ML: {mlStatus.toUpperCase()}
            </p>
            <div className="mt-4 flex -space-x-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-blue-100 text-[10px] font-bold text-blue-700">NE</div>
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-cyan-100 text-[10px] font-bold text-cyan-700">BM</div>
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-[var(--surface-muted)] text-[10px] font-bold text-[var(--text-secondary)]">
                +{Math.max(0, enabledSources - 2)}
              </div>
            </div>
          </article>
        </section>

        <section>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Truy cập nhanh</h3>
            <button
              type="button"
              onClick={refreshDashboard}
              disabled={isRefreshing}
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)]"
            >
              {isRefreshing ? "Đang đồng bộ..." : "Làm mới"}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            {QUICK_ACCESS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 text-left shadow-[var(--shadow-soft)] transition hover:-translate-y-1 hover:shadow-[var(--shadow-float)]"
              >
                <span className="material-symbols-outlined mb-3 block text-[var(--brand-600)]">{item.icon}</span>
                <p className="text-sm font-bold text-[var(--text-brand)]">{item.title}</p>
                <p className="mt-1 text-[10px] text-[var(--text-secondary)]">{item.detail}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="grid grid-cols-12 gap-8">
          <div className="col-span-12 lg:col-span-8">
            <h3 className="mb-5 text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Hoạt động lâm sàng gần đây</h3>
            <div className="space-y-4">
              {activityItems.map((item) => (
                <article
                  key={item.id}
                  className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[color:var(--shell-border)] border-l-4 bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-soft)] ${activityToneClass(item.tone)}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-muted)]">
                      <span className="material-symbols-outlined text-[var(--text-brand)]">chat_bubble</span>
                    </div>
                    <div>
                      <h5 className="text-sm font-bold text-[var(--text-brand)]">{item.title}</h5>
                      <p className="text-xs text-[var(--text-secondary)]">{item.detail}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-bold text-[var(--text-brand)]">{item.timestamp}</p>
                    <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${statusPillClass(item.status)}`}>
                      {item.status}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="col-span-12 space-y-6 lg:col-span-4">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Trợ lý CLARA</h3>
            <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)]">
              <div className="relative z-10">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--text-brand)] text-white">
                    <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
                  </div>
                  <span className="text-sm font-bold text-[var(--text-brand)]">Nhận định hỗ trợ</span>
                </div>

                <div className="mb-6 border-l-4 border-cyan-400 pl-4">
                  <p className="text-sm italic leading-relaxed text-[var(--text-secondary)]">“{assistantInsight}”</p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded-lg bg-white/70 p-3 dark:bg-slate-900/50">
                    <span className="text-xs font-medium text-[var(--text-secondary)]">Độ tự tin ước tính</span>
                    <span className="text-xs font-bold text-cyan-700 dark:text-cyan-300">
                      Cao ({Math.max(0.5, Math.min(0.98, 1 - (errorCount ?? 0) * 0.02)).toFixed(2)})
                    </span>
                  </div>
                  <button
                    type="button"
                    className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-2.5 text-xs font-bold text-[var(--text-primary)] transition hover:bg-white/90 dark:hover:bg-slate-800"
                  >
                    Xem chi tiết phân tích
                  </button>
                </div>
              </div>
            </article>

          </div>
        </section>
      </div>
    </PageShell>
  );
}
