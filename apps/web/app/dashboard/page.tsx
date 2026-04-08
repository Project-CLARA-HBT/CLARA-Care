"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import api from "@/lib/http-client";
import { listResearchConversations } from "@/lib/research";
import { getCabinet } from "@/lib/selfmed";
import {
  getApiHealth,
  getControlTowerConfig,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics
} from "@/lib/system";

type AuthMePayload = {
  subject?: string;
  role?: UserRole;
  full_name?: string;
};

type QuickAction = {
  href: string;
  tag: string;
  label: string;
  detail: string;
};

type TodayTask = {
  id: string;
  title: string;
  detail: string;
  tone: "normal" | "warn" | "critical";
  href: string;
};

type StatusTone = "ok" | "warn" | "error" | "neutral";

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống"
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: "/selfmed",
    tag: "SelfMed",
    label: "Rà soát tủ thuốc",
    detail: "Kiểm tra hạn dùng, liều dùng và bổ sung thông tin còn thiếu."
  },
  {
    href: "/careguard",
    tag: "CareGuard",
    label: "Kiểm tra tương tác DDI",
    detail: "Chạy kiểm tra rủi ro tương tác giữa các thuốc hiện có."
  },
  {
    href: "/council",
    tag: "Council",
    label: "Mở hội chẩn",
    detail: "Tổng hợp ý kiến đa chuyên gia cho ca cần quyết định nhanh."
  },
  {
    href: "/research",
    tag: "Research",
    label: "Nghiên cứu có trích dẫn",
    detail: "Tra cứu tài liệu, đối chiếu bằng chứng và ghi lại kết luận."
  }
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
    minute: "2-digit"
  });
}

function formatPercent(value: number): string {
  return `${Math.max(0, value).toFixed(1)}%`;
}

function getGreeting(now: Date): { title: string; subtitle: string } {
  const hour = now.getHours();
  if (hour < 12) {
    return {
      title: "Chào buổi sáng",
      subtitle: "Kiểm tra nhanh tủ thuốc và tín hiệu hệ thống trước khi bắt đầu."
    };
  }
  if (hour < 18) {
    return {
      title: "Chào buổi chiều",
      subtitle: "Theo dõi checklist chăm sóc trong ngày và xử lý các cảnh báo đang mở."
    };
  }
  return {
    title: "Chào buổi tối",
    subtitle: "Tổng kết các hoạt động trong ngày để chuẩn bị kế hoạch tiếp theo."
  };
}

function toneFromStatus(status: string): StatusTone {
  const normalized = status.toLowerCase();
  if (["ok", "healthy", "up", "pass", "ready", "reachable"].some((token) => normalized.includes(token))) return "ok";
  if (["warn", "warning", "degraded", "slow", "unstable"].some((token) => normalized.includes(token))) return "warn";
  if (["down", "fail", "error", "critical", "unhealthy", "offline"].some((token) => normalized.includes(token))) return "error";
  return "neutral";
}

function badgeClassForTone(tone: StatusTone): string {
  if (tone === "ok") {
    return "border-[color:var(--status-ok-border)] bg-[color:var(--status-ok-bg)] text-[color:var(--status-ok-text)]";
  }
  if (tone === "warn") {
    return "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] text-[color:var(--status-warn-text)]";
  }
  if (tone === "error") {
    return "border-[color:var(--status-danger-border)] bg-[color:var(--status-danger-bg)] text-[color:var(--status-danger-text)]";
  }
  return "border-[color:var(--status-neutral-border)] bg-[color:var(--status-neutral-bg)] text-[color:var(--status-neutral-text)]";
}

function cardClassForTaskTone(tone: TodayTask["tone"]): string {
  if (tone === "critical") {
    return "border-[color:var(--status-danger-border)] bg-[color:var(--status-danger-bg)]";
  }
  if (tone === "warn") {
    return "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)]";
  }
  return "border-[color:var(--shell-border)] bg-[var(--surface-panel)]";
}

function taskToneLabel(tone: TodayTask["tone"]): string {
  if (tone === "critical") return "Ưu tiên cao";
  if (tone === "warn") return "Theo dõi";
  return "Bình thường";
}

function reliabilityScore(params: {
  healthTone: StatusTone;
  mlTone: StatusTone;
  errorRate: number;
  latencyMs: number;
}): number {
  const healthPart = params.healthTone === "ok" ? 34 : params.healthTone === "warn" ? 20 : 8;
  const mlPart = params.mlTone === "ok" ? 28 : params.mlTone === "warn" ? 16 : 6;
  const errorPart = Math.max(0, 24 - params.errorRate * 1.5);
  const latencyPart = Math.max(0, 14 - Math.max(0, params.latencyMs - 280) / 90);
  return Math.max(0, Math.min(100, healthPart + mlPart + errorPart + latencyPart));
}

export default function DashboardPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [displayName, setDisplayName] = useState("bạn");
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
    ragReranker: false,
    ragGraphRag: false,
    deepseekFallback: false,
    scientificRetrieval: false,
    webRetrieval: false,
    fileRetrieval: false
  });

  const [recentQueries, setRecentQueries] = useState<Array<{ id: string; query: string; createdAt: number }>>([]);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? ROLE_LABELS.normal, [role]);
  const greeting = useMemo(() => getGreeting(new Date()), []);

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
    const tasks: TodayTask[] = [];
    if ((expiredCount ?? 0) > 0) {
      tasks.push({
        id: "expired",
        title: `Loại bỏ ${expiredCount} thuốc đã hết hạn`,
        detail: "Dọn ngay để tránh nhầm thuốc trong lần dùng tiếp theo.",
        tone: "critical",
        href: "/selfmed"
      });
    }
    if ((expiringSoonCount ?? 0) > 0) {
      tasks.push({
        id: "expiring",
        title: `Rà soát ${expiringSoonCount} thuốc sắp hết hạn`,
        detail: "Chuẩn bị thay thế để không gián đoạn điều trị.",
        tone: "warn",
        href: "/selfmed"
      });
    }
    if ((cabinetCount ?? 0) >= 2) {
      tasks.push({
        id: "ddi",
        title: "Chạy kiểm tra tương tác DDI hôm nay",
        detail: "Kiểm tra nhanh các cặp nguy cơ cao trước khi dùng thuốc.",
        tone: "normal",
        href: "/careguard"
      });
    }
    if ((missingDosageCount ?? 0) > 0) {
      tasks.push({
        id: "dosage",
        title: `Bổ sung liều dùng cho ${missingDosageCount} thuốc`,
        detail: "Dữ liệu đầy đủ giúp pipeline DDI và advisor chính xác hơn.",
        tone: "warn",
        href: "/selfmed"
      });
    }
    if (tasks.length === 0) {
      tasks.push({
        id: "calm",
        title: "Hôm nay không có cảnh báo lớn",
        detail: "Bạn có thể chuyển sang council hoặc research cho ca cần phân tích sâu.",
        tone: "normal",
        href: "/research"
      });
    }
    return tasks.slice(0, 4);
  }, [cabinetCount, expiredCount, expiringSoonCount, missingDosageCount]);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    const nextAlerts: string[] = [];

    try {
      const [healthResult, metricsResult, dependenciesResult, cabinetResult, meResult, conversationsResult, controlTowerResult] = await Promise.allSettled([
        getApiHealth(),
        getSystemMetrics(),
        getSystemDependencies(),
        getCabinet(),
        api.get<AuthMePayload>("/auth/me"),
        listResearchConversations(6),
        getControlTowerConfig()
      ]);

      if (healthResult.status === "fulfilled") {
        const health = normalizeApiHealth(healthResult.value);
        setHealthStatus(health.status);
        setHealthMessage(health.message);
      } else {
        nextAlerts.push("Không thể lấy trạng thái sức khỏe API.");
      }

      if (metricsResult.status === "fulfilled") {
        const metrics = normalizeSystemMetrics(metricsResult.value);
        setRequestCount(metrics.requestCount);
        setErrorCount(metrics.errorCount);
        setAvgLatencyMs(metrics.avgLatencyMs);
      } else {
        nextAlerts.push("Không thể lấy số liệu hệ thống.");
      }

      if (dependenciesResult.status === "fulfilled") {
        const dependencies = normalizeSystemDependencies(dependenciesResult.value);
        setMlStatus(dependencies.mlStatus);
        setMlReachable(dependencies.mlReachable);
      } else {
        nextAlerts.push("Không thể lấy trạng thái phụ thuộc hệ thống.");
      }

      if (cabinetResult.status === "fulfilled") {
        const items = cabinetResult.value.items ?? [];
        const now = Date.now();
        const dayMs = 24 * 60 * 60 * 1000;
        const soonBoundary = now + 30 * dayMs;

        let soon = 0;
        let expired = 0;
        let missingDosage = 0;

        items.forEach((item) => {
          if (!String(item.dosage ?? "").trim()) {
            missingDosage += 1;
          }
          if (!item.expires_on) return;
          const expireMs = Date.parse(item.expires_on);
          if (!Number.isFinite(expireMs)) return;
          if (expireMs < now) {
            expired += 1;
          } else if (expireMs <= soonBoundary) {
            soon += 1;
          }
        });

        setCabinetCount(items.length);
        setExpiringSoonCount(soon);
        setExpiredCount(expired);
        setMissingDosageCount(missingDosage);
      } else {
        nextAlerts.push("Không thể tải dữ liệu tủ thuốc.");
      }

      if (controlTowerResult.status === "fulfilled") {
        const config = controlTowerResult.value;
        const sources = Array.isArray(config.rag_sources) ? config.rag_sources : [];
        const enabled = sources.filter((source) => source.enabled).length;
        setEnabledSources(enabled);
        setTotalSources(sources.length);

        const ragFlow = config.rag_flow ?? {};
        const flow = {
          roleRouter: Boolean(ragFlow.role_router_enabled),
          intentRouter: Boolean(ragFlow.intent_router_enabled),
          ruleVerification: Boolean(ragFlow.rule_verification_enabled ?? ragFlow.verification_enabled),
          nliModel: Boolean(ragFlow.nli_model_enabled),
          ragNli: Boolean(ragFlow.rag_nli_enabled),
          ragReranker: Boolean(ragFlow.rag_reranker_enabled),
          ragGraphRag: Boolean(ragFlow.rag_graphrag_enabled),
          deepseekFallback: Boolean(ragFlow.deepseek_fallback_enabled),
          scientificRetrieval: Boolean(ragFlow.scientific_retrieval_enabled),
          webRetrieval: Boolean(ragFlow.web_retrieval_enabled),
          fileRetrieval: Boolean(ragFlow.file_retrieval_enabled)
        };

        setFlowFlags(flow);
        setFlowEnabledCount(Object.values(flow).filter(Boolean).length);
        setLowContextThreshold(Number(ragFlow.low_context_threshold ?? 0));
      } else {
        nextAlerts.push("Không thể tải control tower config.");
      }

      if (meResult.status === "fulfilled") {
        const me = meResult.value.data ?? {};
        if (me.role) {
          setRole(me.role);
        }
        const subject = String(me.subject ?? "");
        const fullName = String(me.full_name ?? "").trim();
        const inferredName = subject.includes("@") ? subject.split("@")[0] : "bạn";
        setDisplayName(fullName || inferredName || "bạn");
        setUserSubject(subject);
      }

      if (conversationsResult.status === "fulfilled") {
        const mapped = conversationsResult.value
          .map((item) => ({
            id: String(item.id),
            query: String(item.query ?? "").trim(),
            createdAt: Number(item.createdAt ?? Date.now())
          }))
          .filter((item) => item.query);
        setRecentQueries(mapped);
      } else {
        nextAlerts.push("Không thể tải lịch sử research gần đây.");
      }

      setAlerts(nextAlerts);
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
  const mlTone = toneFromStatus(
    mlReachable === true ? "ok" : mlReachable === false ? "error" : mlStatus
  );

  const requestSafe = Math.max(0, Math.trunc(requestCount ?? 0));
  const errorSafe = Math.max(0, Math.trunc(errorCount ?? 0));
  const latencySafe = Math.max(0, Math.round(avgLatencyMs ?? 0));
  const sourceCoverage = totalSources > 0 ? (enabledSources / totalSources) * 100 : 0;
  const errorRate = requestSafe > 0 ? (errorSafe / requestSafe) * 100 : 0;
  const reliability = reliabilityScore({
    healthTone,
    mlTone,
    errorRate,
    latencyMs: latencySafe
  });

  const verificationStackEnabled = flowFlags.ruleVerification && flowFlags.nliModel && flowFlags.ragNli;

  const runtimeSignals = [
    {
      label: "API",
      value: healthStatus,
      detail: healthMessage,
      tone: healthTone
    },
    {
      label: "ML",
      value: mlReachable === true ? "sẵn sàng" : mlReachable === false ? "mất kết nối" : mlStatus,
      detail: mlReachable === true ? "Đủ điều kiện chạy DDI, council và research." : "Nên kiểm tra service ML hoặc cơ chế fallback.",
      tone: mlTone
    },
    {
      label: "Độ trễ",
      value: `${latencySafe} ms`,
      detail: "Độ trễ trung bình gần nhất",
      tone: latencySafe > 1200 ? "error" : latencySafe > 850 ? "warn" : "ok"
    },
    {
      label: "Tỷ lệ lỗi",
      value: formatPercent(errorRate),
      detail: `${formatCount(errorSafe)} lỗi trên ${formatCount(requestSafe)} request`,
      tone: errorRate >= 10 ? "error" : errorRate >= 5 ? "warn" : "ok"
    }
  ] as const;

  const quickStatusCards = [
    {
      label: "Độ ổn định",
      value: `${Math.round(reliability)}%`,
      detail: "Điểm tổng hợp API, ML, lỗi và độ trễ"
    },
    {
      label: "Việc cần xử lý",
      value: formatCount(pendingActions),
      detail: "Checklist ưu tiên trong ngày"
    },
    {
      label: "Tủ thuốc",
      value: formatCount(cabinetCount),
      detail: `${formatCount(expiredCount)} hết hạn, ${formatCount(expiringSoonCount)} sắp hết hạn`
    },
    {
      label: "Nguồn Research",
      value: `${enabledSources}/${totalSources}`,
      detail: `${formatPercent(sourceCoverage)} nguồn đang bật`
    }
  ];

  const moduleCards = [
    {
      module: "SelfMed",
      href: "/selfmed",
      summary: "Quản lý thuốc, liều dùng và hạn dùng để giảm sai sót khi sử dụng.",
      stat: `${formatCount(cabinetCount)} thuốc`,
      signal: (expiredCount ?? 0) > 0 ? `${formatCount(expiredCount)} đã hết hạn` : "Không có thuốc hết hạn"
    },
    {
      module: "CareGuard",
      href: "/careguard",
      summary: "Đánh giá tương tác DDI theo dữ liệu tủ thuốc hiện tại.",
      stat: `Rủi ro DDI: ${ddiRiskLabel}`,
      signal: (cabinetCount ?? 0) >= 2 ? "Đủ dữ liệu để kiểm tra DDI" : "Cần ít nhất 2 thuốc để so cặp"
    },
    {
      module: "Council",
      href: "/council",
      summary: "Hội chẩn đa tác tử để hỗ trợ quyết định với ca phức tạp.",
      stat: verificationStackEnabled ? "Stack kiểm chứng: bật" : "Stack kiểm chứng: một phần",
      signal: `Flow đang bật ${flowEnabledCount}/11`
    },
    {
      module: "Research",
      href: "/research",
      summary: "Tra cứu tài liệu có trích dẫn, lưu hội thoại và tái sử dụng kết quả.",
      stat: `${recentQueries.length} truy vấn gần đây`,
      signal: `Ngưỡng low-context ${Math.round(lowContextThreshold * 100)}%`
    }
  ];

  const friendlySummary = useMemo(() => {
    if (alerts.length > 0) {
      return "Hệ thống đang có lưu ý cần kiểm tra. Nên xử lý cảnh báo trước khi chạy tác vụ chuyên sâu.";
    }
    if (pendingActions > 0) {
      return `Hiện có ${formatCount(pendingActions)} việc cần xử lý. Ưu tiên thuốc hết hạn và dữ liệu thiếu liều dùng.`;
    }
    if (reliability >= 80) {
      return "Mọi thứ đang ổn định. Bạn có thể tiếp tục careguard, council hoặc research theo nhu cầu.";
    }
    return "Hệ thống hoạt động bình thường, nên theo dõi thêm để giữ độ ổn định cao.";
  }, [alerts.length, pendingActions, reliability]);

  return (
    <PageShell
      title="Dashboard"
      description="Bảng điều khiển người dùng CLARA: rõ ràng theo luồng hằng ngày từ tủ thuốc, an toàn thuốc đến hội chẩn và nghiên cứu."
      variant="plain"
    >
      <div className="space-y-4 sm:space-y-5">
        <section className="relative overflow-hidden rounded-[1.75rem] border border-[color:var(--shell-border)] bg-[linear-gradient(145deg,rgba(255,255,255,0.94),rgba(224,242,254,0.68))] p-4 shadow-soft sm:p-5 lg:p-6 dark:bg-[linear-gradient(145deg,rgba(2,6,23,0.92),rgba(8,47,73,0.72))]">
          <div className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-500/12" />
          <div className="pointer-events-none absolute -left-20 bottom-0 h-40 w-40 rounded-full bg-sky-300/20 blur-3xl dark:bg-sky-500/12" />

          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-3xl space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Daily Flow Dashboard</p>
              <h2 className="text-2xl font-semibold text-[var(--text-primary)] sm:text-3xl">
                {greeting.title}, {displayName}
              </h2>
              <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{greeting.subtitle}</p>
            </div>

            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
              <button
                type="button"
                onClick={refreshDashboard}
                disabled={isRefreshing}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-sky-600 bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isRefreshing ? "Đang làm mới..." : "Làm mới"}
              </button>
              <Link
                href="/role-select"
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)]"
              >
                Đổi vai trò
              </Link>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Vai trò</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">{roleLabel}</p>
            </div>
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Ổn định tổng quan</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">{Math.round(reliability)}%</p>
            </div>
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Việc cần làm</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">{formatCount(pendingActions)} mục</p>
            </div>
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Cập nhật</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">{checkedAt ?? "Đang đồng bộ..."}</p>
            </div>
          </div>

          <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
            {friendlySummary}
            {userSubject ? <span className="ml-1 text-[var(--text-muted)]">({userSubject})</span> : null}
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {quickStatusCards.map((card) => (
            <article key={card.label} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">{card.label}</p>
              <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{card.value}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{card.detail}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Luồng Hằng Ngày</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Bắt đầu theo thứ tự ưu tiên</h3>
              </div>
            </div>

            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              <Link
                href="/selfmed"
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 transition hover:border-[color:var(--shell-border-strong)]"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 1</p>
                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">SelfMed: rà soát dữ liệu thuốc</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{formatCount(expiredCount)} hết hạn, {formatCount(missingDosageCount)} thiếu liều dùng.</p>
              </Link>

              <Link
                href="/careguard"
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 transition hover:border-[color:var(--shell-border-strong)]"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 2</p>
                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">CareGuard: kiểm tra tương tác DDI</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">Mức rủi ro hiện tại: {ddiRiskLabel}. Nên chạy kiểm tra mỗi ngày.</p>
              </Link>

              <Link
                href="/council"
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 transition hover:border-[color:var(--shell-border-strong)]"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 3</p>
                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Council: hội chẩn ca phức tạp</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">Flow đang bật {flowEnabledCount}/11, sẵn sàng tổng hợp nhiều góc nhìn.</p>
              </Link>

              <Link
                href="/research"
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 transition hover:border-[color:var(--shell-border-strong)]"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 4</p>
                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Research: kiểm chứng và ghi nhận bằng chứng</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{enabledSources}/{totalSources} nguồn bật, phù hợp để đi sâu chuyên đề.</p>
              </Link>
            </div>
          </article>

          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Runtime Signals</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Tín hiệu vận hành ngắn gọn</h3>
              </div>
            </div>

            <div className="mt-3 space-y-2.5">
              {runtimeSignals.map((signal) => (
                <div key={signal.label} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{signal.label}</p>
                    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClassForTone(signal.tone)}`}>
                      {signal.value}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">{signal.detail}</p>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Thao Tác Nhanh</p>
              <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Đi tắt vào các thao tác chính</h3>
            </div>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
              {QUICK_ACTIONS.length} mục
            </span>
          </div>

          <div className="mt-3 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {QUICK_ACTIONS.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="group rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 transition hover:border-[color:var(--shell-border-strong)]"
              >
                <span className="inline-flex rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                  {action.tag}
                </span>
                <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{action.label}</p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{action.detail}</p>
                <p className="mt-2 text-xs font-semibold text-[var(--text-brand)] transition group-hover:translate-x-0.5">Mở ngay</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Các Module Chính</p>
              <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Tổng quan theo chức năng</h3>
            </div>
          </div>

          <div className="mt-3 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            {moduleCards.map((moduleCard) => (
              <article key={moduleCard.module} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{moduleCard.module}</p>
                <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">{moduleCard.summary}</p>
                <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{moduleCard.stat}</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{moduleCard.signal}</p>
                <Link
                  href={moduleCard.href}
                  className="mt-3 inline-flex min-h-9 items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)]"
                >
                  Mở {moduleCard.module}
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Hoạt Động Gần Đây</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Lịch sử research gần nhất</h3>
              </div>
              <Link
                href="/research"
                className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)]"
              >
                Mở research
              </Link>
            </div>

            <div className="mt-3 space-y-2.5">
              {recentQueries.length > 0 ? (
                recentQueries.slice(0, 5).map((query) => (
                  <article
                    key={query.id}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
                  >
                    <p className="line-clamp-2 text-sm text-[var(--text-primary)]">{query.query}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{formatDateTime(query.createdAt)}</p>
                  </article>
                ))
              ) : (
                <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-secondary)]">
                  Chưa có lịch sử research gần đây.
                </p>
              )}
            </div>
          </article>

          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Checklist Hôm Nay</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Việc cần làm ngay</h3>
              </div>
              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                {todayTasks.length} mục
              </span>
            </div>

            <div className="mt-3 space-y-2.5">
              {todayTasks.map((task) => (
                <Link
                  key={task.id}
                  href={task.href}
                  className={`block rounded-xl border p-3 transition hover:border-[color:var(--shell-border-strong)] ${cardClassForTaskTone(task.tone)}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{task.title}</p>
                    <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                      {taskToneLabel(task.tone)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{task.detail}</p>
                </Link>
              ))}
            </div>
          </article>
        </section>

        {alerts.length > 0 ? (
          <section className="rounded-[1.4rem] border border-[color:var(--status-danger-border)] bg-[color:var(--status-danger-bg)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[color:var(--status-danger-text)]">Lưu Ý Nhanh</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {alerts.map((alert) => (
                <p
                  key={alert}
                  className="rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[color:var(--status-danger-text)]"
                >
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
