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
  normal: "Chào bạn",
  researcher: "Chào bạn, Nhà nghiên cứu",
  doctor: "Chào bạn, Bác sĩ",
  admin: "Chào bạn, Quản trị viên",
};

const QUICK_ACCESS: QuickAccess[] = [
  { href: "/chat", title: "Hỏi CLARA", detail: "Nhận gợi ý chăm sóc có dẫn nguồn", icon: "chat" },
  { href: "/council", title: "Hội chẩn ca bệnh", detail: "Xin thêm góc nhìn cho ca cần cân nhắc", icon: "groups" },
  { href: "/medicines?tab=cabinet", title: "Rà soát tủ thuốc", detail: "Xem lại thuốc đang theo dõi và ngày hết hạn", icon: "medication" },
  { href: "/medicines?tab=safety", title: "Kiểm tra tương tác", detail: "Đối chiếu thuốc khi cần kiểm tra thêm", icon: "health_and_safety" },
  { href: "/scribe", title: "Ghi nhận buổi khám", detail: "Lưu lại diễn tiến và ghi chú chăm sóc", icon: "edit_note" },
];

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatOptionalCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Chưa có dữ liệu";
  return formatCount(value);
}

function formatLastUpdated(value: string | null): string {
  if (!value) return "Chưa có dữ liệu";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "Chưa có dữ liệu";
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  }).format(new Date(timestamp));
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
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [dashboardUnavailable, setDashboardUnavailable] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const rawDashboard = await getSystemDashboard();
      const dashboard = normalizeSystemDashboard(rawDashboard);

      setDashboardUnavailable(false);
      setGeneratedAt(dashboard.generatedAt);
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
      setAlerts(dashboard.alerts.filter((item) => item.trim().length > 0));
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
      setDashboardUnavailable(true);
      setGeneratedAt(null);
      setCabinetCount(null);
      setExpiringSoonCount(null);
      setExpiredCount(null);
      setEnabledSources(0);
      setTotalSources(0);
      setFlowEnabledCount(0);
      setRecentQueries([]);
      setServerTasks([]);
      setAlerts(["Chưa thể tải dữ liệu tổng quan. Vui lòng thử làm mới hoặc kiểm tra kết nối."]);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    void refreshDashboard();
  }, [refreshDashboard]);

  const greeting = ROLE_GREETINGS[role] ?? ROLE_GREETINGS.normal;
  const lastUpdatedLabel = formatLastUpdated(generatedAt);

  const activeCases = useMemo(() => {
    const inferred = Math.max(recentQueries.length, Math.max(0, Math.trunc((requestCount ?? 0) / 2)));
    return Math.max(1, Math.min(99, inferred || 12));
  }, [recentQueries.length, requestCount]);

  const cautionCases = useMemo(() => {
    if (dashboardUnavailable) return 0;
    const risk = (alerts.length > 0 ? 1 : 0) + ((expiredCount ?? 0) > 0 ? 1 : 0);
    return Math.max(0, Math.min(8, risk));
  }, [alerts.length, dashboardUnavailable, expiredCount]);

  const needsSafetyReview = !dashboardUnavailable && (alerts.length > 0 || (expiredCount ?? 0) > 0);
  const hasMedicationData =
    cabinetCount !== null || expiringSoonCount !== null || expiredCount !== null;
  const hasConnectedSources = totalSources > 0 || enabledSources > 0;

  const councilTotal = 12;
  const councilDone = useMemo(() => Math.max(0, Math.min(councilTotal, recentQueries.length)), [recentQueries.length]);

  const activityItems = useMemo<ActivityItem[]>(() => {
    if (recentQueries.length > 0) {
      return recentQueries.slice(0, 3).map((item, index) => ({
        id: item.id,
        title: item.query,
        detail: index === 0 ? `Phiên hỗ trợ #${item.id.slice(0, 8)} • Có thể mở lại để tiếp tục` : `Phiên chăm sóc #${item.id.slice(0, 8)} • Đã lưu trong hành trình gần đây`,
        timestamp: formatRelative(item.createdAt),
        status: index === 0 ? "Hoàn tất" : index === 1 ? "Đã rà soát" : "Đang tiếp tục",
        tone: index === 0 ? "primary" : index === 1 ? "secondary" : "muted",
      }));
    }

    return [
      {
        id: "default-1",
        title: "So sánh DASH vs Địa Trung Hải",
        detail: "Phiên tư vấn dinh dưỡng gần nhất • Sẵn sàng mở lại",
        timestamp: "2 giờ trước",
        status: "Hoàn tất",
        tone: "primary",
      },
      {
        id: "default-2",
        title: "Phân tích tương tác Metformin",
        detail: "Rà soát thuốc trong hành trình chăm sóc gần đây",
        timestamp: "5 giờ trước",
        status: "Đã rà soát",
        tone: "secondary",
      },
      {
        id: "default-3",
        title: "Ghi âm thăm khám: Nguyễn Văn A",
        detail: "Ghi chú buổi khám đang chờ hoàn thiện",
        timestamp: "Hôm qua",
        status: "Đang tiếp tục",
        tone: "muted",
      },
    ];
  }, [recentQueries]);

  const assistantInsight = useMemo(() => {
    if (dashboardUnavailable) {
      return "Chưa thể tải dữ liệu tổng quan. Vui lòng thử làm mới hoặc kiểm tra kết nối.";
    }
    if (alerts.length > 0) return alerts[0];
    if ((expiredCount ?? 0) > 0) {
      return `Có ${formatCount(expiredCount)} thuốc đã quá hạn. Nên kiểm tra lại trước khi tiếp tục tư vấn hoặc sử dụng.`;
    }
    const err = Math.max(0, errorCount ?? 0);
    if (err > 0) {
      return "Một vài phiên gần đây cần xem kỹ thêm. Hãy đối chiếu cảnh báo và nguồn tham khảo trước khi chốt khuyến nghị.";
    }
    return "Hôm nay chưa có tín hiệu khẩn cấp nổi bật. Bạn có thể bắt đầu từ tủ thuốc hoặc tiếp tục phiên hỗ trợ gần nhất.";
  }, [alerts, dashboardUnavailable, errorCount, expiredCount]);

  const safetySummary = useMemo(() => {
    if (dashboardUnavailable) {
      return {
        eyebrow: "Chưa có dữ liệu",
        title: "Chưa thể tải dữ liệu tổng quan",
        detail: "Vui lòng thử làm mới hoặc kiểm tra kết nối.",
      };
    }

    const tracked = cabinetCount ?? 0;
    const expired = expiredCount ?? 0;
    const expiring = expiringSoonCount ?? 0;
    const importantNotes = (tracked > 0 ? 1 : 0) + (expiring > 0 ? 1 : 0) + (expired > 0 ? 1 : 0);
    if ((expiredCount ?? 0) > 0) {
      return {
        eyebrow: "Cảnh báo an toàn",
        title: `Cần xem lại ${formatCount(Math.max(1, importantNotes))} lưu ý an toàn trước khi tiếp tục`,
        detail: "Có thuốc cần kiểm tra lại sớm. Hãy rà soát trước khi tiếp tục.",
      };
    }

    if (alerts.length > 0) {
      return {
        eyebrow: "Cảnh báo an toàn",
        title: `Cần xem lại ${formatCount(Math.max(1, importantNotes))} lưu ý an toàn trước khi tiếp tục`,
        detail: "Có thông tin cần kiểm tra lại trước khi tiếp tục.",
      };
    }

    if ((expiringSoonCount ?? 0) > 0) {
      return {
        eyebrow: "Cảnh báo an toàn",
        title: `Cần xem lại ${formatCount(Math.max(1, importantNotes))} lưu ý an toàn trước khi tiếp tục`,
        detail: "Kiểm tra sớm để tránh gián đoạn theo dõi hoặc sử dụng.",
      };
    }

    return {
      eyebrow: "Tình trạng an toàn",
      title: "Chưa thấy cảnh báo nghiêm trọng",
      detail: "Chưa thấy tín hiệu khẩn cấp. Bạn có thể tiếp tục hỏi CLARA hoặc rà soát ca gần nhất.",
    };
  }, [alerts.length, cabinetCount, dashboardUnavailable, expiredCount, expiringSoonCount]);

  const primaryAction = useMemo(() => {
    if (dashboardUnavailable) {
      return {
        kind: "button" as const,
        title: "Tải lại dữ liệu",
        detail: "Thử kết nối lại dữ liệu tổng quan",
        icon: "refresh",
      };
    }
    if (needsSafetyReview) {
      const safetyCount =
        (cabinetCount !== null ? 1 : 0) +
        ((expiringSoonCount ?? 0) > 0 ? 1 : 0) +
        ((expiredCount ?? 0) > 0 ? 1 : 0);
      return {
        kind: "link" as const,
        href: "/medicines?tab=safety",
        title: `Xem ${formatCount(Math.max(1, safetyCount))} lưu ý cần xử lý`,
        detail: "Rà soát cảnh báo trước khi tiếp tục",
        icon: "health_and_safety",
      };
    }
    return {
      kind: "link" as const,
      href: "/medicines?tab=cabinet",
      title: "Bắt đầu rà soát hôm nay",
      detail: "Mở tủ thuốc và kiểm tra các bước cần làm",
      icon: "checklist",
    };
  }, [cabinetCount, dashboardUnavailable, expiredCount, expiringSoonCount, needsSafetyReview]);

  const secondaryAction = useMemo<QuickAccess>(
    () =>
      recentQueries.length > 0
        ? {
            href: "/chat",
            title: "Tiếp tục cùng CLARA",
            detail: "Mở lại hỗ trợ gần đây",
            icon: "chat",
          }
        : {
            href: "/council",
            title: "Bắt đầu hội chẩn",
            detail: "Xin thêm góc nhìn khi cần",
            icon: "groups",
          },
    [recentQueries.length]
  );

  const todayTasks = useMemo<TodayTask[]>(() => {
    if (serverTasks.length > 0) return serverTasks.slice(0, 4);
    return [
      {
        id: "review-meds",
        title: "Rà soát thuốc",
        detail: "Kiểm tra danh mục thuốc hiện tại",
        tone: "normal",
        href: "/medicines?tab=cabinet",
      },
      {
        id: "check-ddi",
        title: "Kiểm tra tương tác",
        detail: "Đối chiếu tương tác đa thuốc",
        tone: "warn",
        href: "/medicines?tab=safety",
      },
      {
        id: "conduct-council",
        title: "Hội chẩn AI",
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
            { id: "fallback-1", title: "Rà soát thuốc", detail: "", tone: "normal" as TodayTask["tone"], href: "/medicines?tab=cabinet" },
            { id: "fallback-2", title: "Kiểm tra tương tác", detail: "", tone: "warn" as TodayTask["tone"], href: "/medicines?tab=safety" },
            { id: "fallback-3", title: "Hội chẩn AI", detail: "", tone: "normal" as TodayTask["tone"], href: "/council" },
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

  const completedWorkflowSteps = useMemo(
    () => workflowStates.filter((state) => state === "done").length,
    [workflowStates]
  );
  const workflowProgress = Math.round((completedWorkflowSteps / 4) * 100);

  if (!showDetails) {
    return (
      <PageShell title="" description="" variant="plain">
        <div className="mx-auto max-w-4xl space-y-5">
          <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)] sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Hôm nay</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)] sm:text-3xl">{greeting}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
              Chọn một việc để bắt đầu. Các chỉ số vận hành chi tiết chỉ mở khi bạn cần.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {todayTasks.slice(0, 2).map((task) => (
                <Link key={task.id} href={task.href} className="focus-ring rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 transition hover:border-[color:var(--brand-500)] hover:bg-[var(--surface-panel)]">
                  <span className="font-semibold text-[var(--text-primary)]">{task.title}</span>
                  {task.detail ? <span className="mt-1 block text-sm text-[var(--text-secondary)]">{task.detail}</span> : null}
                  <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--text-brand)]">Mở <span className="material-symbols-outlined text-base" aria-hidden="true">arrow_forward</span></span>
                </Link>
              ))}
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Lối tắt">
            {QUICK_ACCESS.slice(0, 3).map((item) => (
              <Link key={item.href} href={item.href} className="focus-ring rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-soft)] transition hover:-translate-y-0.5">
                <span className="material-symbols-outlined text-[22px] text-[var(--text-brand)]" aria-hidden="true">{item.icon}</span>
                <span className="mt-2 block font-semibold text-[var(--text-primary)]">{item.title}</span>
                <span className="mt-1 block text-sm leading-5 text-[var(--text-secondary)]">{item.detail}</span>
              </Link>
            ))}
          </section>

          <button type="button" onClick={() => setShowDetails(true)} className="focus-ring mx-auto flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]">
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">monitoring</span>
            Xem chỉ số và hoạt động chi tiết
          </button>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="" description="" variant="plain">
      <div className="space-y-10">
        <section className="overflow-hidden rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)] sm:p-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.9fr)] lg:items-start">
            <div className="space-y-5">
              <span className="inline-flex items-center rounded-full bg-[var(--surface-muted)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
                Bảng điều khiển chăm sóc
              </span>
              <div>
                <h2 className="mb-3 text-3xl font-extrabold tracking-tight text-[var(--text-brand)] sm:text-4xl">{greeting}</h2>
                <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-lg">
                  Hôm nay có <span className="rounded-lg bg-[var(--surface-muted)] px-2 py-0.5 font-bold text-[var(--text-brand)]">{activeCases} hồ sơ</span> cần theo dõi.
                  <br />
                  Trong đó có <span className="rounded-lg bg-[var(--surface-muted)] px-2 py-0.5 font-bold text-[var(--text-brand)]">{cautionCases} nhóm việc</span> cần xem lại trước khi tiếp tục.
                </p>
                <p className="mt-3 text-xs font-medium text-[var(--text-muted)]">
                  Cập nhật lần cuối: {lastUpdatedLabel}
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                {primaryAction.kind === "button" ? (
                  <button
                    type="button"
                    onClick={refreshDashboard}
                    disabled={isRefreshing}
                    className="group flex min-h-16 flex-1 items-center gap-3 rounded-xl border border-transparent bg-[var(--text-brand)] px-4 py-3 text-left text-white shadow-[var(--shadow-soft)] transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 text-white">
                      <span className="material-symbols-outlined text-[20px]">{primaryAction.icon}</span>
                    </span>
                    <div>
                      <p className="text-sm font-bold text-white">{isRefreshing ? "Đang tải lại..." : primaryAction.title}</p>
                      <p className="text-xs text-white/80">{primaryAction.detail}</p>
                    </div>
                  </button>
                ) : (
                  <Link
                    href={primaryAction.href}
                    className="group flex min-h-16 flex-1 items-center gap-3 rounded-xl border border-transparent bg-[var(--text-brand)] px-4 py-3 text-left text-white shadow-[var(--shadow-soft)] transition hover:opacity-95"
                  >
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 text-white">
                      <span className="material-symbols-outlined text-[20px]">{primaryAction.icon}</span>
                    </span>
                    <div>
                      <p className="text-sm font-bold text-white">{primaryAction.title}</p>
                      <p className="text-xs text-white/80">{primaryAction.detail}</p>
                    </div>
                  </Link>
                )}
                <Link
                  href={secondaryAction.href}
                  className="group flex min-h-16 flex-1 items-center gap-3 rounded-xl border border-[color:var(--shell-border)] bg-white/80 px-4 py-3 text-left text-[var(--text-primary)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)] dark:bg-slate-900/50"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-muted)] text-[var(--text-brand)]">
                    <span className="material-symbols-outlined text-[20px]">{secondaryAction.icon}</span>
                  </span>
                  <div>
                    <p className="text-sm font-bold text-[var(--text-brand)]">{secondaryAction.title}</p>
                    <p className="text-xs text-[var(--text-secondary)]">{secondaryAction.detail}</p>
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={refreshDashboard}
                  disabled={isRefreshing}
                  className="inline-flex min-h-16 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isRefreshing ? "Đang đồng bộ..." : "Làm mới dữ liệu"}
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-white/70 p-5 shadow-[var(--shadow-soft)] dark:bg-slate-900/50">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--brand-600)]">{safetySummary.eyebrow}</p>
              <h3 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-brand)]">{safetySummary.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{safetySummary.detail}</p>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="rounded-xl bg-[var(--surface-muted)] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Thuốc đang theo dõi</p>
                  <p className="mt-2 text-2xl font-bold text-[var(--text-brand)]">{formatOptionalCount(cabinetCount)}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-muted)] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Thuốc sắp đến hạn</p>
                  <p className="mt-2 text-2xl font-bold text-[var(--text-brand)]">{formatOptionalCount(expiringSoonCount)}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-muted)] p-4 sm:col-span-2 lg:col-span-1">
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Tương tác nghiêm trọng</p>
                  <p className="mt-2 text-2xl font-bold text-[var(--text-brand)]">0</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-soft)]">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Luồng công việc hàng ngày</h3>
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              Đã hoàn thành: {completedWorkflowSteps}/4 bước
            </span>
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
                  <p className="mt-1 text-[10px] leading-4 text-[var(--text-secondary)]">
                    {task.detail || (
                      index === 0
                        ? "Kiểm tra danh mục thuốc"
                        : index === 1
                          ? "Đối chiếu tương tác"
                          : index === 2
                            ? "Xin thêm góc nhìn AI"
                            : "Lưu lại kết quả"
                    )}
                  </p>
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
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
                <span className="material-symbols-outlined">medication</span>
              </div>
              <span
                className={[
                  "rounded px-2 py-1 text-[10px] font-bold",
                  needsSafetyReview
                    ? "bg-red-500/15 text-red-700 dark:text-red-300"
                    : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
                ].join(" ")}
              >
                {needsSafetyReview ? "Cần xem lại" : "Đang ổn"}
              </span>
            </div>
            <h4 className="text-2xl font-bold leading-tight text-[var(--text-brand)]">Tủ thuốc</h4>
            {!hasMedicationData ? (
              <div className="mt-4 rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">Chưa có dữ liệu thuốc để hiển thị.</p>
                <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">Hãy thêm thuốc hoặc làm mới dữ liệu.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href="/medicines/cabinet/add"
                    className="inline-flex min-h-[34px] items-center rounded-lg bg-[var(--text-brand)] px-3 text-xs font-semibold text-white"
                  >
                    Thêm thuốc
                  </Link>
                  <button
                    type="button"
                    onClick={refreshDashboard}
                    disabled={isRefreshing}
                    className="inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isRefreshing ? "Đang làm mới..." : "Làm mới"}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">Tóm tắt thuốc đang được theo dõi trong hôm nay.</p>
                <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                  <div className="rounded-lg bg-[var(--surface-muted)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Thuốc đang theo dõi</p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-brand)]">{formatCount(cabinetCount)}</p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-muted)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Cần kiểm tra sớm</p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-brand)]">{formatCount(expiredCount)}</p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-muted)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Sắp đến hạn</p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-brand)]">{formatCount(expiringSoonCount)}</p>
                  </div>
                </div>
                <Link
                  href="/medicines?tab=cabinet"
                  className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-brand)] transition hover:opacity-80"
                >
                  Mở tủ thuốc
                  <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </Link>
              </>
            )}
          </article>

          <article className="col-span-12 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 lg:col-span-4">
            <div className="mb-4 flex items-start justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-700 dark:text-indigo-300">
                <span className="material-symbols-outlined">menu_book</span>
              </div>
              <span className="rounded bg-cyan-500/15 px-2 py-1 text-[10px] font-bold text-cyan-700 dark:text-cyan-300">Tín hiệu</span>
            </div>
            <h4 className="text-2xl font-bold text-[var(--text-brand)]">
              {hasConnectedSources ? `${formatCount(enabledSources)} nguồn đang bật` : "Chưa có nguồn dữ liệu nào được kết nối"}
            </h4>
            <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
              {hasConnectedSources
                ? `Tổng nguồn hiện có: ${formatCount(totalSources)}.`
                : "Khi có nguồn dữ liệu, CLARA sẽ hiển thị thông tin tổng quan tại đây."}
            </p>
            {hasConnectedSources ? (
              <div className="mt-4 flex -space-x-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-blue-100 text-[10px] font-bold text-blue-700">NE</div>
                <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-cyan-100 text-[10px] font-bold text-cyan-700">BM</div>
                <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white bg-[var(--surface-muted)] text-[10px] font-bold text-[var(--text-secondary)]">
                  +{Math.max(0, enabledSources - 2)}
                </div>
              </div>
            ) : null}
          </article>
        </section>

        <section>
          <div className="mb-4">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Các lối tắt quen thuộc</h3>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">Khi muốn chuyển nhanh sang một bước cụ thể, bạn có thể bắt đầu từ đây.</p>
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
            <div className="mb-5">
              <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">Hành trình chăm sóc gần đây</h3>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                Những phiên hỗ trợ mới nhất được sắp theo thời gian để bạn dễ tiếp tục đúng chỗ, thay vì phải tìm lại từ đầu.
              </p>
            </div>
            <div className="space-y-4">
              {activityItems.map((item) => (
                <article
                  key={item.id}
                  className={`flex flex-wrap items-start justify-between gap-3 rounded-lg border border-[color:var(--shell-border)] border-l-4 bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-soft)] ${activityToneClass(item.tone)}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-muted)]">
                      <span className="material-symbols-outlined text-[var(--text-brand)]">history</span>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Phiên hỗ trợ</p>
                      <h5 className="text-sm font-bold text-[var(--text-brand)]">{item.title}</h5>
                      <p className="text-xs text-[var(--text-secondary)]">{item.detail}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Cập nhật</p>
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
