"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ConduitFlowLine,
  MatrixHeatmapMini,
  NeonAreaChart,
  RadarPulseChart,
  SegmentRingGauge,
  TelemetryBars
} from "@/components/dashboard/futuristic-charts";
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

type TimelinePoint = {
  at: number;
  requests: number;
  errors: number;
  latencyMs: number;
  cabinetCount: number;
  reliability: number;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống"
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: "/selfmed/add",
    tag: "SelfMed",
    label: "Thêm thuốc mới",
    detail: "Nhập tay hoặc OCR để cập nhật tủ thuốc."
  },
  {
    href: "/careguard",
    tag: "CareGuard",
    label: "Kiểm tra tương tác DDI",
    detail: "Kiểm tra rủi ro tương tác theo tủ thuốc hiện tại."
  },
  {
    href: "/research",
    tag: "Research",
    label: "Nghiên cứu chuyên sâu",
    detail: "Hỏi đáp có trích dẫn và lớp kiểm chứng."
  },
  {
    href: "/selfmed",
    tag: "Cabinet",
    label: "Rà soát tủ thuốc",
    detail: "Xem thuốc sắp hết hạn hoặc dữ liệu thiếu liều dùng."
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
      subtitle: "Bắt đầu nhẹ nhàng với checklist thuốc và tình trạng hệ thống."
    };
  }
  if (hour < 18) {
    return {
      title: "Chào buổi chiều",
      subtitle: "Theo dõi nhanh các chỉ số chính để giữ trải nghiệm ổn định."
    };
  }
  return {
    title: "Chào buổi tối",
    subtitle: "Tổng kết trong ngày và chuẩn bị các việc ưu tiên cho ngày mai."
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

function timelineClassForTaskTone(tone: TodayTask["tone"]): string {
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
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);

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
        title: "Hôm nay hệ thống ổn định",
        detail: "Bạn có thể tiếp tục cập nhật dữ liệu mới hoặc chạy research chuyên sâu.",
        tone: "normal",
        href: "/research"
      });
    }
    return tasks.slice(0, 4);
  }, [cabinetCount, expiredCount, expiringSoonCount, missingDosageCount]);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    const nextAlerts: string[] = [];

    let nextRequestCount = requestCount ?? 0;
    let nextErrorCount = errorCount ?? 0;
    let nextLatencyMs = Math.round(avgLatencyMs ?? 0);
    let nextCabinetCount = cabinetCount ?? 0;

    try {
      const [healthResult, metricsResult, dependenciesResult, cabinetResult, meResult, conversationsResult, controlTowerResult] = await Promise.allSettled([
        getApiHealth(),
        getSystemMetrics(),
        getSystemDependencies(),
        getCabinet(),
        api.get<AuthMePayload>("/auth/me"),
        listResearchConversations(5),
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
        nextRequestCount = Math.max(0, Math.trunc(metrics.requestCount ?? 0));
        nextErrorCount = Math.max(0, Math.trunc(metrics.errorCount ?? 0));
        nextLatencyMs = Math.max(0, Math.round(metrics.avgLatencyMs ?? 0));
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
        nextCabinetCount = items.length;
      } else {
        nextAlerts.push("Không thể tải dữ liệu tủ thuốc.");
      }

      if (controlTowerResult.status === "fulfilled") {
        const config = controlTowerResult.value;
        const sources = Array.isArray(config.rag_sources) ? config.rag_sources : [];
        const enabled = sources.filter((source) => source.enabled).length;
        setEnabledSources(enabled);
        setTotalSources(sources.length);

        const flow = {
          roleRouter: Boolean(config.rag_flow.role_router_enabled),
          intentRouter: Boolean(config.rag_flow.intent_router_enabled),
          ruleVerification: Boolean(config.rag_flow.rule_verification_enabled ?? config.rag_flow.verification_enabled),
          nliModel: Boolean(config.rag_flow.nli_model_enabled),
          ragNli: Boolean(config.rag_flow.rag_nli_enabled),
          ragReranker: Boolean(config.rag_flow.rag_reranker_enabled),
          ragGraphRag: Boolean(config.rag_flow.rag_graphrag_enabled),
          deepseekFallback: Boolean(config.rag_flow.deepseek_fallback_enabled),
          scientificRetrieval: Boolean(config.rag_flow.scientific_retrieval_enabled),
          webRetrieval: Boolean(config.rag_flow.web_retrieval_enabled),
          fileRetrieval: Boolean(config.rag_flow.file_retrieval_enabled)
        };

        setFlowFlags(flow);
        setFlowEnabledCount(Object.values(flow).filter(Boolean).length);
        setLowContextThreshold(config.rag_flow.low_context_threshold);
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

      const healthTone = toneFromStatus(healthResult.status === "fulfilled" ? normalizeApiHealth(healthResult.value).status : healthStatus);
      const mlTone = toneFromStatus(dependenciesResult.status === "fulfilled"
        ? (normalizeSystemDependencies(dependenciesResult.value).mlReachable === false ? "offline" : "reachable")
        : mlStatus);
      const nextErrorRate = nextRequestCount > 0 ? (nextErrorCount / nextRequestCount) * 100 : 0;
      const nextReliability = reliabilityScore({
        healthTone,
        mlTone,
        errorRate: nextErrorRate,
        latencyMs: nextLatencyMs
      });

      setTimeline((prev) => {
        const point: TimelinePoint = {
          at: Date.now(),
          requests: nextRequestCount,
          errors: nextErrorCount,
          latencyMs: nextLatencyMs,
          cabinetCount: nextCabinetCount,
          reliability: nextReliability
        };
        return [...prev, point].slice(-36);
      });

      setAlerts(nextAlerts);
      setCheckedAt(new Date().toLocaleString("vi-VN"));
    } finally {
      setIsRefreshing(false);
    }
  }, [avgLatencyMs, cabinetCount, errorCount, healthStatus, mlStatus, requestCount]);

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

  const trendThroughput = timeline.length > 1
    ? Math.round((timeline[timeline.length - 1].requests - timeline[0].requests) / (timeline.length - 1))
    : requestSafe;

  const graphLabels = timeline.map((point, index) => `T${index + 1}`);
  const requestsSeries = timeline.map((point) => point.requests);
  const errorsSeries = timeline.map((point) => point.errors);
  const latencySeries = timeline.map((point) => point.latencyMs);
  const reliabilitySeries = timeline.map((point) => point.reliability);
  const cabinetSeries = timeline.map((point) => point.cabinetCount);

  const radarAxes = [
    { label: "API", value: healthTone === "ok" ? 90 : healthTone === "warn" ? 55 : 26 },
    { label: "ML", value: mlTone === "ok" ? 88 : mlTone === "warn" ? 52 : 24 },
    { label: "DDI", value: (cabinetCount ?? 0) > 1 ? 82 : 46 },
    { label: "RAG", value: Math.round(sourceCoverage) },
    { label: "Kiểm chứng", value: verificationStackEnabled ? 92 : 30 },
    { label: "Độ trễ", value: latencySafe < 800 ? 84 : latencySafe < 1200 ? 56 : 28 },
    { label: "Lỗi", value: errorRate < 5 ? 86 : errorRate < 10 ? 52 : 22 }
  ];

  const matrixRows = ["An toàn", "Vận hành", "Tri thức", "Flow", "Phản hồi"];
  const matrixColumns = ["Ổn định", "Độ trễ", "Lỗi", "Độ phủ", "Tin cậy"];
  const matrixValues = [
    [reliability, latencySafe < 850 ? 82 : 48, errorRate < 6 ? 83 : 34, Math.round(sourceCoverage), verificationStackEnabled ? 92 : 40],
    [healthTone === "ok" ? 90 : 45, latencySafe < 900 ? 80 : 44, errorRate < 8 ? 78 : 38, 74, reliability],
    [flowFlags.scientificRetrieval ? 88 : 42, 72, errorRate < 10 ? 74 : 36, Math.round(sourceCoverage), flowFlags.fileRetrieval ? 84 : 38],
    [
      Math.round((flowEnabledCount / 11) * 100),
      latencySafe < 850 ? 78 : 46,
      errorRate < 9 ? 72 : 34,
      Math.round((flowEnabledCount / 11) * 92),
      flowFlags.intentRouter ? 86 : 40
    ],
    [reliability, latencySafe < 800 ? 84 : 44, errorRate < 7 ? 80 : 36, 70, reliabilitySeries.length > 0 ? reliabilitySeries[reliabilitySeries.length - 1] : reliability]
  ];

  const telemetryBars = [
    { label: "Lưu lượng", value: trendThroughput, target: Math.max(1, trendThroughput + 10), tone: "ok" as const },
    { label: "Tải lỗi", value: errorSafe, target: Math.max(2, Math.round(requestSafe * 0.08)), tone: errorRate >= 8 ? "error" as const : "warn" as const },
    { label: "Độ trễ (ms)", value: latencySafe, target: 900, tone: latencySafe > 1000 ? "error" as const : "warn" as const },
    { label: "Ổn định", value: Math.round(reliability), target: 82, tone: reliability >= 82 ? "ok" as const : "warn" as const }
  ];

  const flowStages = [
    { label: "Đầu vào", status: healthTone === "error" ? "error" as const : healthTone === "warn" ? "warn" as const : "ok" as const, detail: healthStatus },
    { label: "Định tuyến", status: flowFlags.roleRouter && flowFlags.intentRouter ? "ok" as const : "warn" as const, detail: `${flowEnabledCount}/11` },
    { label: "Truy xuất", status: sourceCoverage >= 55 ? "ok" as const : "warn" as const, detail: `${enabledSources}/${totalSources}` },
    { label: "Phân tích", status: mlTone === "error" ? "error" as const : mlTone === "warn" ? "warn" as const : "ok" as const, detail: mlStatus },
    { label: "Kiểm chứng", status: verificationStackEnabled ? "ok" as const : "warn" as const, detail: verificationStackEnabled ? "bật" : "tắt" },
    { label: "Phản hồi", status: reliability >= 70 ? "ok" as const : reliability >= 50 ? "warn" as const : "error" as const, detail: `${Math.round(reliability)}%` }
  ];

  const medicationCards = [
    {
      label: "Số lượng thuốc",
      value: formatCount(cabinetCount),
      hint: "Đang quản lý trong tủ thuốc"
    },
    {
      label: "Sắp hết hạn (30 ngày)",
      value: formatCount(expiringSoonCount),
      hint: "Nên ưu tiên thay thế"
    },
    {
      label: "Đã hết hạn",
      value: formatCount(expiredCount),
      hint: "Cần loại bỏ để tránh nhầm"
    },
    {
      label: "Thiếu liều dùng",
      value: formatCount(missingDosageCount),
      hint: "Nên bổ sung để check DDI chính xác"
    }
  ];

  const kpis = [
    { label: "Độ ổn định", value: `${Math.round(reliability)}%`, detail: "Điểm tổng hợp vận hành" },
    { label: "Lưu lượng", value: formatCount(trendThroughput), detail: "Biến động request gần nhất" },
    { label: "Tỷ lệ lỗi", value: formatPercent(errorRate), detail: `${formatCount(errorSafe)} lỗi` },
    { label: "Độ trễ", value: `${latencySafe} ms`, detail: "Trung bình phản hồi" },
    { label: "Độ phủ RAG", value: `${enabledSources}/${totalSources}`, detail: formatPercent(sourceCoverage) },
    { label: "Flow bật", value: `${flowEnabledCount}/11`, detail: `Ngưỡng ${Math.round(lowContextThreshold * 100)}%` },
    { label: "Rủi ro DDI", value: ddiRiskLabel, detail: `${formatCount(cabinetCount)} thuốc` },
    { label: "Việc chờ", value: formatCount(pendingActions), detail: "Danh sách ưu tiên" }
  ];

  const friendlySummary = useMemo(() => {
    if (alerts.length > 0) {
      return "Hệ thống đang có lưu ý cần kiểm tra. Bạn nên xử lý các mục cảnh báo trước.";
    }
    if (pendingActions > 0) {
      return `Hiện có ${formatCount(pendingActions)} việc cần xử lý. Ưu tiên các mục an toàn thuốc trước.`;
    }
    if (reliability >= 80) {
      return "Mọi thứ đang ổn định. Bạn có thể tiếp tục cập nhật dữ liệu hoặc tra cứu chuyên sâu.";
    }
    return "Hệ thống hoạt động bình thường, nên theo dõi thêm để giữ độ ổn định cao.";
  }, [alerts.length, pendingActions, reliability]);

  return (
    <PageShell
      title="Dashboard"
      description="Trang tổng quan thân thiện của CLARA: theo dõi nhanh sức khỏe hệ thống, tủ thuốc và các việc cần làm."
      variant="plain"
    >
      <div className="space-y-4 sm:space-y-5">
        <section className="relative overflow-hidden rounded-[1.75rem] border border-[color:var(--shell-border)] bg-[linear-gradient(145deg,rgba(255,255,255,0.92),rgba(224,242,254,0.7))] p-4 shadow-soft sm:p-5 lg:p-6 dark:bg-[linear-gradient(145deg,rgba(2,6,23,0.92),rgba(8,47,73,0.72))]">
          <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-500/12" />
          <div className="pointer-events-none absolute -left-20 bottom-0 h-44 w-44 rounded-full bg-sky-300/20 blur-3xl dark:bg-sky-500/12" />

          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-3xl space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Tổng Quan Hôm Nay</p>
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

          <div className="mt-4 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
            <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">Vai trò: {roleLabel}</span>
            <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">Độ ổn định: {Math.round(reliability)}%</span>
            <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">Rủi ro DDI: {ddiRiskLabel}</span>
            <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">
              Việc cần làm: {formatCount(pendingActions)}
            </span>
            <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">
              {checkedAt ? `Cập nhật: ${checkedAt}` : "Đang đồng bộ dữ liệu..."}
            </span>
            {userSubject ? (
              <span className="inline-flex min-h-9 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3">
                {userSubject}
              </span>
            ) : null}
          </div>

          <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-secondary)]">
            {friendlySummary}
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((kpi) => (
            <article key={kpi.label} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">{kpi.label}</p>
              <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{kpi.value}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{kpi.detail}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
          <NeonAreaChart
            title="Theo Dõi Trực Tiếp (Request / Lỗi / Độ trễ / Tủ thuốc)"
            labels={graphLabels}
            series={[
              { id: "req", label: "Lưu lượng", color: "#22d3ee", values: requestsSeries.length > 0 ? requestsSeries : [requestSafe] },
              { id: "err", label: "Lỗi", color: "#f43f5e", values: errorsSeries.length > 0 ? errorsSeries : [errorSafe] },
              { id: "lat", label: "Độ trễ", color: "#f59e0b", values: latencySeries.length > 0 ? latencySeries : [latencySafe] },
              { id: "cab", label: "Tủ thuốc", color: "#14b8a6", values: cabinetSeries.length > 0 ? cabinetSeries : [Math.max(0, cabinetCount ?? 0)] }
            ]}
            className="min-h-[22rem]"
          />

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
            <SegmentRingGauge
              label="Độ ổn định"
              value={Math.round(reliability)}
              max={100}
              subLabel="Tổng hợp API + ML + lỗi + độ trễ"
              color="#38bdf8"
            />
            <SegmentRingGauge
              label="Độ phủ RAG"
              value={Math.round(sourceCoverage)}
              max={100}
              subLabel={`${enabledSources}/${totalSources} nguồn đang bật`}
              color="#14b8a6"
            />
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1fr_1fr_1.1fr]">
          <RadarPulseChart title="Radar Hệ Thống" axes={radarAxes} />
          <MatrixHeatmapMini title="Ma Trận Vận Hành" rows={matrixRows} columns={matrixColumns} values={matrixValues} />
          <div className="space-y-4">
            <TelemetryBars title="Chỉ Số Chính" items={telemetryBars} />
            <ConduitFlowLine title="Luồng Xử Lý" stages={flowStages} />
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Thao Tác Nhanh</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Bắt đầu nhanh</h3>
              </div>
              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                {QUICK_ACTIONS.length} mục
              </span>
            </div>

            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
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
                  <p className="mt-2 text-xs font-semibold text-[var(--text-brand)] transition group-hover:translate-x-0.5">Bắt đầu</p>
                </Link>
              ))}
            </div>
          </article>

          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Việc Cần Làm</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Việc cần xử lý hôm nay</h3>
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
                  className={`block rounded-xl border p-3 transition hover:border-[color:var(--shell-border-strong)] ${timelineClassForTaskTone(task.tone)}`}
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

        <section className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Tình Trạng Thuốc</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Tình trạng tủ thuốc</h3>
              </div>
              <Link
                href="/selfmed"
                className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)]"
              >
                Mở tủ thuốc
              </Link>
            </div>

            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              {medicationCards.map((item) => (
                <div key={item.label} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{item.label}</p>
                  <p className="mt-1.5 font-mono text-2xl font-semibold text-[var(--text-primary)]">{item.value}</p>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.hint}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Trạng Thái Hệ Thống</p>
            <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Sức khỏe hệ thống</h3>

            <div className="mt-3 space-y-2.5">
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Sức khỏe API</p>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClassForTone(healthTone)}`}>
                    {healthStatus}
                  </span>
                </div>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">{healthMessage}</p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Trạng thái ML</p>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClassForTone(mlTone)}`}>
                    {mlReachable === true ? "sẵn sàng" : mlReachable === false ? "mất kết nối" : mlStatus}
                  </span>
                </div>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  {mlReachable === true ? "Sẵn sàng cho luồng DDI và luồng nghiên cứu." : "Hãy kiểm tra dịch vụ ML hoặc bật cơ chế dự phòng."}
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Chỉ số vận hành</p>
                <div className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
                  <p>Tổng request: <span className="font-semibold text-[var(--text-primary)]">{formatCount(requestCount)}</span></p>
                  <p>Tổng lỗi: <span className="font-semibold text-[var(--text-primary)]">{formatCount(errorCount)}</span></p>
                  <p>
                    Latency TB: <span className="font-semibold text-[var(--text-primary)]">{avgLatencyMs === null ? "--" : `${avgLatencyMs.toFixed(2)} ms`}</span>
                  </p>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Hoạt Động Gần Đây</p>
              <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Lịch sử truy vấn gần đây</h3>
            </div>
            <Link
              href="/research"
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)]"
            >
              Mở tra cứu
            </Link>
          </div>

          <div className="mt-3 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {recentQueries.length > 0 ? (
              recentQueries.map((query) => (
                <article
                  key={query.id}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
                >
                  <p className="line-clamp-2 text-sm text-[var(--text-primary)]">{query.query}</p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">{formatDateTime(query.createdAt)}</p>
                </article>
              ))
            ) : (
              <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-secondary)] sm:col-span-2 lg:col-span-3">
                Chưa có lịch sử research gần đây.
              </p>
            )}
          </div>
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
