"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import {
  getSystemDashboard,
  normalizeSystemDashboard,
} from "@/lib/system";

type StatusTone = "ok" | "warn" | "error" | "neutral";

type QuickAction = {
  href: string;
  tag: string;
  label: string;
  detail: string;
  icon: string;
};

type TodayTask = {
  id: string;
  title: string;
  detail: string;
  tone: "normal" | "warn" | "critical";
  href: string;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống",
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: "/selfmed",
    tag: "SelfMed",
    label: "Open Cabinet",
    detail: "Theo dõi thuốc, liều dùng, hạn dùng và nguồn OCR theo thời gian thực.",
    icon: "fa-medkit",
  },
  {
    href: "/careguard",
    tag: "CareGuard",
    label: "Run DDI Check",
    detail: "Đối chiếu tương tác thuốc và đưa cảnh báo theo độ ưu tiên.",
    icon: "fa-shield",
  },
  {
    href: "/council",
    tag: "Council",
    label: "Consensus Board",
    detail: "Tổng hợp quan điểm đa tác tử cho ca lâm sàng phức tạp.",
    icon: "fa-users",
  },
  {
    href: "/research",
    tag: "Research",
    label: "Evidence Sync",
    detail: "Truy xuất tài liệu và kiểm chứng phản hồi bằng trích dẫn rõ ràng.",
    icon: "fa-flask",
  },
];

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatDateTime(value: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("vi-VN", {
    hour12: false,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPercent(value: number): string {
  return `${Math.max(0, value).toFixed(1)}%`;
}

function toneFromStatus(status: string): StatusTone {
  const normalized = status.toLowerCase();
  if (["ok", "healthy", "up", "pass", "ready", "reachable"].some((token) => normalized.includes(token))) return "ok";
  if (["warn", "warning", "degraded", "slow", "unstable"].some((token) => normalized.includes(token))) return "warn";
  if (["down", "fail", "error", "critical", "unhealthy", "offline"].some((token) => normalized.includes(token))) return "error";
  return "neutral";
}

function taskToneClass(tone: TodayTask["tone"]): string {
  if (tone === "critical") return "border-red-300/50 bg-red-500/10 text-red-200";
  if (tone === "warn") return "border-amber-300/50 bg-amber-500/10 text-amber-200";
  return "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]";
}

function asRole(value: string): UserRole | null {
  return value === "normal" || value === "researcher" || value === "doctor" || value === "admin" ? value : null;
}

export default function DashboardPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [userSubject, setUserSubject] = useState("");

  const [healthStatus, setHealthStatus] = useState("unknown");
  const [healthMessage, setHealthMessage] = useState("Chưa có dữ liệu health.");
  const [mlStatus, setMlStatus] = useState("unknown");
  const [mlReachable, setMlReachable] = useState<boolean | null>(null);

  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [errorCount, setErrorCount] = useState<number | null>(null);
  const [avgLatencyMs, setAvgLatencyMs] = useState<number | null>(null);

  const [cabinetCount, setCabinetCount] = useState<number | null>(null);
  const [expiringSoonCount, setExpiringSoonCount] = useState<number | null>(null);
  const [expiredCount, setExpiredCount] = useState<number | null>(null);
  const [missingDosageCount, setMissingDosageCount] = useState<number | null>(null);

  const [enabledSources, setEnabledSources] = useState(0);
  const [totalSources, setTotalSources] = useState(0);
  const [flowEnabledCount, setFlowEnabledCount] = useState(0);
  const [lowContextThreshold, setLowContextThreshold] = useState(0);
  const [flowFlags, setFlowFlags] = useState({
    roleRouter: false,
    intentRouter: false,
    ruleVerification: false,
    nliModel: false,
    ragNli: false,
    ragReranker: true,
    ragGraphRag: true,
    deepseekFallback: false,
    scientificRetrieval: false,
    webRetrieval: false,
    fileRetrieval: false,
  });

  const [recentQueries, setRecentQueries] = useState<Array<{ id: string; query: string; createdAt: number }>>([]);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [serverTasks, setServerTasks] = useState<TodayTask[]>([]);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? ROLE_LABELS.normal, [role]);

  const ddiRiskLabel = useMemo(() => {
    const total = cabinetCount ?? 0;
    if (total < 2) return "Thấp";
    if (total < 5) return "Trung bình";
    return "Cao";
  }, [cabinetCount]);

  const pendingActions = useMemo(() => {
    let count = 0;
    if ((cabinetCount ?? 0) >= 2) count += 1;
    if ((expiringSoonCount ?? 0) > 0) count += expiringSoonCount ?? 0;
    if ((expiredCount ?? 0) > 0) count += expiredCount ?? 0;
    if ((missingDosageCount ?? 0) > 0) count += missingDosageCount ?? 0;
    return count;
  }, [cabinetCount, expiringSoonCount, expiredCount, missingDosageCount]);

  const todayTasks = useMemo<TodayTask[]>(() => {
    if (serverTasks.length > 0) return serverTasks.slice(0, 4);

    const tasks: TodayTask[] = [];
    if ((expiredCount ?? 0) > 0) {
      tasks.push({
        id: "expired",
        title: `Loại bỏ ${expiredCount} thuốc đã hết hạn`,
        detail: "Dọn ngay để tránh nhầm thuốc trong lần dùng tiếp theo.",
        tone: "critical",
        href: "/selfmed",
      });
    }
    if ((expiringSoonCount ?? 0) > 0) {
      tasks.push({
        id: "expiring",
        title: `Rà soát ${expiringSoonCount} thuốc sắp hết hạn`,
        detail: "Chuẩn bị thay thế để không gián đoạn điều trị.",
        tone: "warn",
        href: "/selfmed",
      });
    }
    if ((cabinetCount ?? 0) >= 2) {
      tasks.push({
        id: "ddi",
        title: "Chạy kiểm tra tương tác DDI hôm nay",
        detail: "Kiểm tra nhanh các cặp nguy cơ cao trước khi dùng thuốc.",
        tone: "normal",
        href: "/careguard",
      });
    }
    if ((missingDosageCount ?? 0) > 0) {
      tasks.push({
        id: "dosage",
        title: `Bổ sung liều dùng cho ${missingDosageCount} thuốc`,
        detail: "Dữ liệu đầy đủ giúp pipeline DDI và advisor chính xác hơn.",
        tone: "warn",
        href: "/selfmed",
      });
    }
    if (tasks.length === 0) {
      tasks.push({
        id: "calm",
        title: "Hôm nay không có cảnh báo lớn",
        detail: "Bạn có thể chuyển sang council hoặc research cho ca cần phân tích sâu.",
        tone: "normal",
        href: "/research",
      });
    }
    return tasks.slice(0, 4);
  }, [cabinetCount, expiredCount, expiringSoonCount, missingDosageCount, serverTasks]);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const rawDashboard = await getSystemDashboard();
      const dashboard = normalizeSystemDashboard(rawDashboard);

      const nextRole = asRole(dashboard.user.role);
      if (nextRole) setRole(nextRole);
      setUserSubject(dashboard.user.subject);

      setHealthStatus(dashboard.runtime.apiStatus);
      setHealthMessage(
        dashboard.generatedAt
          ? `Đồng bộ lúc ${new Date(dashboard.generatedAt).toLocaleString("vi-VN")} · ML ${dashboard.runtime.mlStatus.toUpperCase()}`
          : `Runtime API ${dashboard.runtime.apiStatus.toUpperCase()} · ML ${dashboard.runtime.mlStatus.toUpperCase()}`
      );
      setMlStatus(dashboard.runtime.mlStatus);
      setMlReachable(dashboard.runtime.mlReachable);

      setRequestCount(dashboard.runtime.requestCount);
      setErrorCount(dashboard.runtime.errorCount);
      setAvgLatencyMs(dashboard.runtime.avgLatencyMs);

      setCabinetCount(dashboard.cabinet.itemTotal);
      setExpiringSoonCount(dashboard.cabinet.expiringSoonTotal);
      setExpiredCount(dashboard.cabinet.expiredTotal);
      setMissingDosageCount(dashboard.cabinet.missingDosageTotal);

      setEnabledSources(dashboard.sources.enabled);
      setTotalSources(dashboard.sources.total);
      setLowContextThreshold(dashboard.sources.lowContextThreshold);
      setFlowFlags(dashboard.sources.flowFlags);
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
      setCheckedAt(
        dashboard.generatedAt
          ? new Date(dashboard.generatedAt).toLocaleString("vi-VN")
          : new Date().toLocaleString("vi-VN")
      );
    } catch {
      setAlerts(["Không thể tải dữ liệu dashboard tổng hợp."]);
      setCheckedAt(new Date().toLocaleString("vi-VN"));
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    void refreshDashboard();
  }, [refreshDashboard]);

  const healthTone = toneFromStatus(healthStatus);
  const mlTone = toneFromStatus(mlReachable === true ? "ok" : mlReachable === false ? "error" : mlStatus);

  const requestSafe = Math.max(0, Math.trunc(requestCount ?? 0));
  const errorSafe = Math.max(0, Math.trunc(errorCount ?? 0));
  const latencySafe = Math.max(0, Math.round(avgLatencyMs ?? 0));
  const sourceCoverage = totalSources > 0 ? (enabledSources / totalSources) * 100 : 0;
  const errorRate = requestSafe > 0 ? (errorSafe / requestSafe) * 100 : 0;
  const verificationStackEnabled = flowFlags.ruleVerification && flowFlags.nliModel && flowFlags.ragNli;

  const runtimeTiles = [
    { key: "api", label: "API HEALTH", value: healthStatus.toUpperCase(), tone: healthTone },
    { key: "ml", label: "ML SERVICE", value: mlReachable === false ? "OFFLINE" : "ACTIVE", tone: mlTone },
    { key: "latency", label: "LATENCY", value: `${latencySafe}ms`, tone: latencySafe > 1200 ? "error" : latencySafe > 850 ? "warn" : "ok" },
    { key: "error", label: "ERROR RATE", value: formatPercent(errorRate), tone: errorRate >= 10 ? "error" : errorRate >= 5 ? "warn" : "ok" },
  ] as const;

  const moduleOverview = [
    {
      key: "med",
      label: "Medication Status",
      value: `${formatCount(cabinetCount)} meds`,
      sub: (expiredCount ?? 0) > 0 ? `${formatCount(expiredCount)} thuốc hết hạn` : "Ổn định",
    },
    {
      key: "ddi",
      label: "DDI Analysis",
      value: ddiRiskLabel,
      sub: `${formatCount(cabinetCount)} thuốc trong tủ`,
    },
    {
      key: "ai",
      label: "AI Nodes",
      value: `${flowEnabledCount}/11`,
      sub: verificationStackEnabled ? "Verification stack active" : "Verification stack partial",
    },
    {
      key: "db",
      label: "Database",
      value: `${enabledSources}/${totalSources}`,
      sub: `${formatPercent(sourceCoverage)} bật · low-context ${Math.round(lowContextThreshold * 100)}%`,
    },
  ];

  const taskCompletionRatio = Math.max(0, Math.min(100, Math.round((flowEnabledCount / 11) * 100)));

  return (
    <PageShell
      title=""
      description=""
      variant="plain"
    >
      <div className="space-y-8">
        <section className="grid grid-cols-12 gap-6">
          <article className="col-span-12 md:col-span-4 rounded-lg p-5 border-l-2 border-cyan-400/40 border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div className="flex justify-between items-start mb-4">
              <i className="fa fa-check-square-o text-cyan-400" aria-hidden="true" />
              <span className="text-[10px] text-cyan-300/70 font-mono">012-TASKS</span>
            </div>
            <div className="text-2xl font-bold text-[var(--text-primary)]">Tasks</div>
            <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{formatCount(pendingActions)} đang mở</div>
            <div className="mt-4 h-1 w-full bg-[var(--surface-muted)] rounded-full overflow-hidden">
              <div className="h-full bg-cyan-400" style={{ width: `${Math.max(12, Math.min(100, pendingActions * 12))}%` }} />
            </div>
          </article>

          <article className="col-span-12 md:col-span-4 rounded-lg p-5 border-l-2 border-red-300/40 border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div className="flex justify-between items-start mb-4">
              <i className="fa fa-medkit text-red-300" aria-hidden="true" />
              <span className="text-[10px] text-red-200/60 font-mono">CAB-EXP</span>
            </div>
            <div className="text-2xl font-bold text-[var(--text-primary)]">Cabinet Expiry</div>
            <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{formatCount(expiredCount)} hết hạn · {formatCount(expiringSoonCount)} sắp hết hạn</div>
            <div className="mt-4 h-1 w-full bg-[var(--surface-muted)] rounded-full overflow-hidden">
              <div className="h-full bg-red-300" style={{ width: `${Math.max(8, Math.min(100, ((expiredCount ?? 0) + (expiringSoonCount ?? 0)) * 14))}%` }} />
            </div>
          </article>

          <article className="col-span-12 md:col-span-4 rounded-lg p-5 border-l-2 border-sky-300/40 border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div className="flex justify-between items-start mb-4">
              <i className="fa fa-globe text-sky-300" aria-hidden="true" />
              <span className="text-[10px] text-sky-200/60 font-mono">SRC-HNB</span>
            </div>
            <div className="text-2xl font-bold text-[var(--text-primary)]">Research Sources</div>
            <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{enabledSources}/{totalSources} nguồn đang bật</div>
            <div className="mt-4 h-1 w-full bg-[var(--surface-muted)] rounded-full overflow-hidden">
              <div className="h-full bg-sky-300" style={{ width: `${Math.max(5, sourceCoverage)}%` }} />
            </div>
          </article>
        </section>

        <section className="grid grid-cols-12 gap-8">
          <article className="col-span-12 lg:col-span-5">
            <div className="mb-6 flex justify-between items-end">
              <h3 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">Daily Flow Progress</h3>
              <span className="text-[10px] font-mono text-cyan-400/80">SEQUENCE_ACTIVE</span>
            </div>

            <div className="space-y-0 relative">
              <div className="absolute left-[15px] top-4 bottom-4 w-[1px] bg-[color:var(--shell-border)]" />

              <div className="relative pl-12 pb-8">
                <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center z-10 border border-cyan-300/40">
                  <i className="fa fa-check-circle text-[16px] text-cyan-300" aria-hidden="true" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-[var(--text-primary)]">Step 1: SelfMed</span>
                  <span className="text-xs text-[var(--text-secondary)]">Phân tích đơn thuốc cá nhân hoàn tất.</span>
                  <div className="mt-2 text-[10px] font-bold text-cyan-300 px-2 py-0.5 bg-cyan-500/10 rounded self-start">COMPLETED</div>
                </div>
              </div>

              <div className="relative pl-12 pb-8">
                <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center z-10 border border-cyan-300/60">
                  <i className="fa fa-refresh text-[16px] text-cyan-300 animate-spin" aria-hidden="true" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-[var(--text-primary)]">Step 2: CareGuard/DDI</span>
                  <span className="text-xs text-[var(--text-secondary)]">Đang kiểm tra tương tác thuốc thời gian thực.</span>
                  <div className="mt-2 text-[10px] font-bold text-cyan-300 px-2 py-0.5 bg-cyan-500/10 rounded self-start">PROCESSING</div>
                </div>
              </div>

              <div className="relative pl-12 pb-8">
                <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-[var(--surface-muted)] flex items-center justify-center z-10 border border-[color:var(--shell-border)]">
                  <i className="fa fa-clock-o text-[16px] text-[var(--text-muted)]" aria-hidden="true" />
                </div>
                <div className="flex flex-col opacity-70">
                  <span className="text-sm font-bold text-[var(--text-primary)]">Step 3: Council</span>
                  <span className="text-xs text-[var(--text-secondary)]">Hội đồng chuyên gia AI đang chờ lệnh.</span>
                </div>
              </div>

              <div className="relative pl-12">
                <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-[var(--surface-muted)] flex items-center justify-center z-10 border border-[color:var(--shell-border)]">
                  <i className="fa fa-clock-o text-[16px] text-[var(--text-muted)]" aria-hidden="true" />
                </div>
                <div className="flex flex-col opacity-70">
                  <span className="text-sm font-bold text-[var(--text-primary)]">Step 4: Research</span>
                  <span className="text-xs text-[var(--text-secondary)]">Tổng hợp các nghiên cứu y khoa liên quan.</span>
                </div>
              </div>
            </div>
          </article>

          <div className="col-span-12 lg:col-span-7 space-y-8">
            <article className="rounded-xl p-6 border border-cyan-500/15 bg-[var(--surface-panel)]">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Runtime Signals</h3>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-cyan-400 clara-glow-cyan" />
                  <span className="text-[10px] font-mono text-cyan-300">SYSTEM_LIVE</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                {runtimeTiles.map((tile) => (
                  <div className="flex flex-col" key={tile.key}>
                    <span className="text-[10px] text-[var(--text-muted)] mb-1">{tile.label}</span>
                    <span className="text-sm font-mono text-[var(--text-primary)]">{tile.value}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 h-12 flex items-end gap-1">
                {[4, 6, 5, 8, 4, 10, 7, 5, 8, 3, 4, 6, 10, 7].map((h, idx) => (
                  <div
                    key={`bar-${idx}`}
                    className={`flex-1 rounded-t-sm ${idx % 3 === 0 ? "bg-cyan-400/20" : idx % 3 === 1 ? "bg-cyan-400/40" : "bg-cyan-400/60"}`}
                    style={{ height: `${h * 4}px` }}
                  />
                ))}
              </div>
            </article>

            <article>
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Quick Actions</h3>
                <button
                  type="button"
                  onClick={refreshDashboard}
                  disabled={isRefreshing}
                  className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)]"
                >
                  {isRefreshing ? "Đang đồng bộ..." : "Refresh"}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {QUICK_ACTIONS.map((action) => (
                  <Link
                    key={action.href}
                    href={action.href}
                    className="clara-glass-panel p-4 rounded-lg border border-white/5 hover:border-cyan-400/30 transition-all group"
                  >
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 rounded bg-cyan-500/10 text-cyan-300">
                        <i className={`fa ${action.icon} text-[20px]`} aria-hidden="true" />
                      </div>
                      <span className="text-sm font-bold text-[var(--text-primary)]">{action.tag}</span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mb-3">{action.detail}</p>
                    <div className="w-full py-2 rounded bg-[var(--surface-muted)] text-[10px] text-center font-bold uppercase tracking-widest text-cyan-300 group-hover:bg-cyan-500 group-hover:text-white transition-all">
                      Open Now
                    </div>
                  </Link>
                ))}
              </div>
            </article>
          </div>
        </section>

        <section>
          <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] mb-6">Module Overview</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {moduleOverview.map((module) => (
              <article key={module.key} className="bg-[var(--surface-panel)] p-6 rounded-xl border border-[color:var(--shell-border)]">
                <div className="text-[10px] text-[var(--text-muted)] mb-4 uppercase">{module.label}</div>
                <div className="text-3xl font-light mb-1 text-[var(--text-primary)]">{module.value}</div>
                <div className="text-xs text-[var(--text-secondary)]">{module.sub}</div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          <article className="lg:col-span-2 bg-[var(--surface-panel)] rounded-xl border border-[color:var(--shell-border)] overflow-hidden">
            <div className="px-6 py-4 bg-[var(--surface-muted)] flex justify-between items-center border-b border-[color:var(--shell-border)]">
              <h4 className="text-xs font-bold tracking-widest uppercase text-[var(--text-primary)]">System Events Log</h4>
              <span className="text-[10px] text-[var(--text-muted)] font-mono">{checkedAt ?? formatDateTime(Date.now())}</span>
            </div>
            <div className="p-6 font-mono text-[11px] leading-6 max-h-64 overflow-y-auto clara-scrollbar">
              {recentQueries.length > 0 ? (
                recentQueries.slice(0, 6).map((query) => (
                  <div className="flex gap-3 text-[var(--text-secondary)]" key={query.id}>
                    <span className="text-cyan-300">[{formatDateTime(query.createdAt)}]</span>
                    <span>{query.query}</span>
                  </div>
                ))
              ) : (
                <div className="text-[var(--text-secondary)]">Chưa có sự kiện truy vấn gần đây.</div>
              )}
              {alerts.map((alert) => (
                <div key={alert} className="flex gap-3 text-amber-300">
                  <span className="text-cyan-300">[ALERT]</span>
                  <span>{alert}</span>
                </div>
              ))}
              <div className="flex gap-3 text-cyan-300/90">
                <span>[INFO]</span>
                <span>Role: {roleLabel} {userSubject ? `| ${userSubject}` : ""}</span>
              </div>
              <div className="flex gap-3 text-sky-300/90">
                <span>[HEALTH]</span>
                <span>{healthMessage}</span>
              </div>
            </div>
          </article>

          <article className="bg-[var(--surface-panel)] rounded-xl p-6 border border-cyan-500/20">
            <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)] mb-6">Today&apos;s Checklist</h4>
            <div className="space-y-3">
              {todayTasks.map((task) => (
                <Link
                  key={task.id}
                  href={task.href}
                  className={`flex items-start gap-3 rounded-lg border px-3 py-2 transition ${taskToneClass(task.tone)}`}
                >
                  <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded border border-cyan-300/60 text-cyan-200">
                    <i className="fa fa-check text-[10px]" aria-hidden="true" />
                  </span>
                  <span>
                    <p className="text-xs font-semibold">{task.title}</p>
                    <p className="mt-1 text-[11px] opacity-80">{task.detail}</p>
                  </span>
                </Link>
              ))}
            </div>

            <div className="mt-6">
              <div className="mb-2 flex justify-between text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
                <span>Flow completion</span>
                <span>{taskCompletionRatio}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-[var(--surface-muted)] overflow-hidden">
                <div className="h-full bg-gradient-to-r from-cyan-500 to-sky-400" style={{ width: `${taskCompletionRatio}%` }} />
              </div>
            </div>

            <button className="mt-8 w-full py-2 clinical-gradient text-white text-[10px] font-bold uppercase tracking-widest rounded-lg shadow-lg clara-glow-cyan" type="button">
              View All Alerts
            </button>
          </article>
        </section>

        {alerts.length > 0 ? (
          <section className="rounded-2xl border border-red-300/50 bg-red-500/10 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-red-200">Critical Warnings</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {alerts.map((alert) => (
                <p key={alert} className="rounded-lg border border-red-300/40 bg-red-900/20 px-3 py-2 text-sm text-red-100">
                  {alert}
                </p>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
