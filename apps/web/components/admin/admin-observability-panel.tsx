"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ConduitFlowLine,
  MatrixHeatmapMini,
  NeonAreaChart,
  RadarPulseChart,
  SegmentRingGauge,
  TelemetryBars
} from "@/components/dashboard/futuristic-charts";
import {
  getApiHealth,
  getControlTowerConfig,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics
} from "@/lib/system";

type FlowFlags = {
  roleRouter: boolean;
  intentRouter: boolean;
  ruleVerification: boolean;
  nliModel: boolean;
  ragReranker: boolean;
  ragNli: boolean;
  ragGraphRag: boolean;
  deepseekFallback: boolean;
  scientificRetrieval: boolean;
  webRetrieval: boolean;
  fileRetrieval: boolean;
};

type ObservabilityState = {
  loading: boolean;
  error: string;
  apiStatus: string;
  apiMessage: string;
  mlReachable: boolean | null;
  mlStatus: string;
  requestCount: number | null;
  errorCount: number | null;
  avgLatencyMs: number | null;
  totalSources: number;
  enabledSources: number;
  flowEnabledCount: number;
  lowContextThreshold: number;
  flow: FlowFlags;
};

type TimelinePoint = {
  at: number;
  requests: number;
  errors: number;
  latencyMs: number;
  flowEnabledCount: number;
  sourceCoverage: number;
};

type AlertLevel = "info" | "warn" | "critical";

type AlertItem = {
  level: AlertLevel;
  title: string;
  detail: string;
  source: string;
};

const INITIAL_STATE: ObservabilityState = {
  loading: true,
  error: "",
  apiStatus: "unknown",
  apiMessage: "",
  mlReachable: null,
  mlStatus: "unknown",
  requestCount: null,
  errorCount: null,
  avgLatencyMs: null,
  totalSources: 0,
  enabledSources: 0,
  flowEnabledCount: 0,
  lowContextThreshold: 0,
  flow: {
    roleRouter: false,
    intentRouter: false,
    ruleVerification: false,
    nliModel: false,
    ragReranker: false,
    ragNli: false,
    ragGraphRag: false,
    deepseekFallback: false,
    scientificRetrieval: false,
    webRetrieval: false,
    fileRetrieval: false
  }
};

const TOTAL_FLOW_FLAGS = 11;

function clamp(value: number, min = 0, max = 100): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function toInt(value: number | null): number {
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value ?? 0)) : 0;
}

function formatCount(value: number | null): string {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(Math.max(0, value ?? 0));
}

function formatPercent(value: number): string {
  return `${Math.max(0, value).toFixed(1)}%`;
}

function toneForStatus(status: string): "ok" | "warn" | "error" {
  const normalized = status.toLowerCase();
  if (normalized.includes("ok") || normalized.includes("healthy") || normalized.includes("reachable")) return "ok";
  if (normalized.includes("warn") || normalized.includes("degraded")) return "warn";
  return "error";
}

function buildRiskMatrix(params: {
  errors: number;
  errorRate: number;
  latencyMs: number;
  sourceCoverage: number;
  flowEnabled: number;
}): number[][] {
  const { errors, errorRate, latencyMs, sourceCoverage, flowEnabled } = params;
  return [
    [clamp(28 - errors), clamp(errorRate * 2), clamp(errorRate * 4), clamp(errorRate * 6)],
    [clamp(40 - latencyMs / 20), clamp(latencyMs / 8), clamp(latencyMs / 5), clamp(latencyMs / 2.4)],
    [clamp(sourceCoverage), clamp(100 - sourceCoverage), clamp((100 - sourceCoverage) * 1.3), clamp((100 - sourceCoverage) * 1.7)],
    [
      clamp((flowEnabled / TOTAL_FLOW_FLAGS) * 100),
      clamp(((TOTAL_FLOW_FLAGS - flowEnabled) / TOTAL_FLOW_FLAGS) * 100),
      clamp(((TOTAL_FLOW_FLAGS - flowEnabled) / TOTAL_FLOW_FLAGS) * 130),
      clamp(((TOTAL_FLOW_FLAGS - flowEnabled) / TOTAL_FLOW_FLAGS) * 170)
    ]
  ];
}

function computeFlowHealth(flow: FlowFlags): number {
  const requiredKeys: Array<keyof FlowFlags> = [
    "roleRouter",
    "intentRouter",
    "ruleVerification",
    "nliModel",
    "ragNli",
    "ragReranker",
    "scientificRetrieval"
  ];
  const requiredOn = requiredKeys.filter((key) => flow[key]).length;
  const optionalOn = [flow.deepseekFallback, flow.webRetrieval, flow.fileRetrieval, flow.ragGraphRag].filter(Boolean).length;
  return clamp(requiredOn * 11 + optionalOn * 6);
}

export default function AdminObservabilityPanel() {
  const [state, setState] = useState<ObservabilityState>(INITIAL_STATE);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));

    try {
      const [healthRaw, metricsRaw, dependenciesRaw, config] = await Promise.all([
        getApiHealth(),
        getSystemMetrics(),
        getSystemDependencies(),
        getControlTowerConfig()
      ]);

      const health = normalizeApiHealth(healthRaw);
      const metrics = normalizeSystemMetrics(metricsRaw);
      const dependencies = normalizeSystemDependencies(dependenciesRaw);

      const sources = Array.isArray(config.rag_sources) ? config.rag_sources : [];
      const enabledSources = sources.filter((source) => source.enabled).length;

      const flow = {
        roleRouter: Boolean(config.rag_flow.role_router_enabled),
        intentRouter: Boolean(config.rag_flow.intent_router_enabled),
        ruleVerification: Boolean(config.rag_flow.rule_verification_enabled ?? config.rag_flow.verification_enabled),
        nliModel: Boolean(config.rag_flow.nli_model_enabled),
        ragReranker: Boolean(config.rag_flow.rag_reranker_enabled),
        ragNli: Boolean(config.rag_flow.rag_nli_enabled),
        ragGraphRag: Boolean(config.rag_flow.rag_graphrag_enabled),
        deepseekFallback: Boolean(config.rag_flow.deepseek_fallback_enabled),
        scientificRetrieval: Boolean(config.rag_flow.scientific_retrieval_enabled),
        webRetrieval: Boolean(config.rag_flow.web_retrieval_enabled),
        fileRetrieval: Boolean(config.rag_flow.file_retrieval_enabled)
      };

      const flowEnabledCount = Object.values(flow).filter(Boolean).length;
      const sourceCoverage = sources.length > 0 ? (enabledSources / sources.length) * 100 : 0;

      setState({
        loading: false,
        error: "",
        apiStatus: health.status,
        apiMessage: health.message,
        mlReachable: dependencies.mlReachable,
        mlStatus: dependencies.mlStatus,
        requestCount: metrics.requestCount,
        errorCount: metrics.errorCount,
        avgLatencyMs: metrics.avgLatencyMs,
        totalSources: sources.length,
        enabledSources,
        flowEnabledCount,
        lowContextThreshold: config.rag_flow.low_context_threshold,
        flow
      });

      setTimeline((prev) => {
        const point: TimelinePoint = {
          at: Date.now(),
          requests: toInt(metrics.requestCount),
          errors: toInt(metrics.errorCount),
          latencyMs: toInt(metrics.avgLatencyMs),
          flowEnabledCount,
          sourceCoverage: Math.round(sourceCoverage)
        };
        const next = [...prev, point];
        return next.slice(-30);
      });
    } catch (cause) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: cause instanceof Error ? cause.message : "Không thể tải ảnh chụp trạng thái hệ thống."
      }));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => {
      void load();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, load]);

  const requests = toInt(state.requestCount);
  const errors = toInt(state.errorCount);
  const success = Math.max(0, requests - errors);
  const latencyMs = toInt(state.avgLatencyMs);
  const errorRate = requests > 0 ? (errors / requests) * 100 : 0;
  const sourceCoverage = state.totalSources > 0 ? (state.enabledSources / state.totalSources) * 100 : 0;
  const flowHealth = computeFlowHealth(state.flow);

  const apiTone = toneForStatus(state.apiStatus);
  const mlTone = state.mlReachable === false ? "error" : toneForStatus(state.mlStatus);
  const runtimeStability = clamp(100 - errorRate * 2.2 - latencyMs / 58 - (state.mlReachable === false ? 24 : 0));
  const verificationStrength = clamp(flowHealth - state.lowContextThreshold * 28 + 12);

  const axisLabels = useMemo(() => {
    if (timeline.length === 0) return ["t-5", "t-4", "t-3", "t-2", "t-1", "now"];
    return timeline.map((item) => {
      const date = new Date(item.at);
      return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
    });
  }, [timeline]);

  const trafficSeries = useMemo(
    () => [
      {
        id: "requests",
        label: "Request",
        color: "#22d3ee",
        values: timeline.map((item) => item.requests)
      },
      {
        id: "errors",
        label: "Lỗi",
        color: "#fb7185",
        values: timeline.map((item) => item.errors)
      }
    ],
    [timeline]
  );

  const performanceSeries = useMemo(
    () => [
      {
        id: "latency",
        label: "Độ trễ",
        color: "#60a5fa",
        values: timeline.map((item) => item.latencyMs)
      },
      {
        id: "sourceCoverage",
        label: "Độ phủ nguồn",
        color: "#34d399",
        values: timeline.map((item) => item.sourceCoverage)
      }
    ],
    [timeline]
  );

  const radarAxes = useMemo(
    () => [
      { label: "Vận hành", value: runtimeStability, max: 100 },
      { label: "Kiểm chứng", value: verificationStrength, max: 100 },
      { label: "Độ phủ", value: sourceCoverage, max: 100 },
      { label: "Flow", value: flowHealth, max: 100 },
      { label: "API", value: apiTone === "ok" ? 95 : apiTone === "warn" ? 68 : 40, max: 100 }
    ],
    [apiTone, flowHealth, runtimeStability, sourceCoverage, verificationStrength]
  );

  const signalItems = useMemo<
    Array<{ label: string; value: number; tone: "ok" | "warn" | "danger" }>
  >(
    () => [
      { label: "Độ ổn định", value: Math.round(runtimeStability), tone: runtimeStability < 65 ? "warn" : "ok" },
      { label: "Mức kiểm chứng", value: Math.round(verificationStrength), tone: verificationStrength < 70 ? "warn" : "ok" },
      { label: "Sức khỏe flow", value: Math.round(flowHealth), tone: flowHealth < 60 ? "danger" : "ok" },
      { label: "Độ phủ nguồn", value: Math.round(sourceCoverage), tone: sourceCoverage < 50 ? "warn" : "ok" }
    ],
    [flowHealth, runtimeStability, sourceCoverage, verificationStrength]
  );

  const verificationStackEnabled = state.flow.ruleVerification && state.flow.nliModel && state.flow.ragNli;

  const pipelineStages = useMemo<
    Array<{ label: string; status: "ok" | "warn" | "error" | "idle"; note: string }>
  >(
    () => [
      { label: "Cổng vào", status: apiTone === "ok" ? "ok" : apiTone === "warn" ? "warn" : "error", note: state.apiStatus },
      { label: "Role Router", status: state.flow.roleRouter ? "ok" : "warn", note: state.flow.roleRouter ? "BẬT" : "TẮT" },
      { label: "Intent Router", status: state.flow.intentRouter ? "ok" : "warn", note: state.flow.intentRouter ? "BẬT" : "TẮT" },
      {
        label: "Kiểm chứng Rule + NLI",
        status: verificationStackEnabled ? "ok" : "error",
        note: verificationStackEnabled ? "BẬT" : "TẮT"
      },
      { label: "ML Runtime", status: mlTone === "ok" ? "ok" : mlTone === "warn" ? "warn" : "error", note: state.mlReachable === false ? "mất kết nối" : "sẵn sàng" }
    ],
    [apiTone, mlTone, state.apiStatus, state.flow.intentRouter, state.flow.roleRouter, state.mlReachable, verificationStackEnabled]
  );

  const alerts = useMemo<AlertItem[]>(() => {
    const rows: AlertItem[] = [];

    if (apiTone !== "ok") {
      rows.push({
        level: apiTone === "error" ? "critical" : "warn",
        title: "API đang giảm ổn định",
        detail: state.apiMessage || "Tín hiệu từ cổng vào chưa ổn định.",
        source: "api"
      });
    }

    if (state.mlReachable === false) {
      rows.push({
        level: "critical",
        title: "Không kết nối được ML",
        detail: state.mlStatus || "Không nhận được phản hồi từ dịch vụ ML.",
        source: "ml"
      });
    }

    if (errorRate >= 15) {
      rows.push({
        level: "critical",
        title: "Tỷ lệ lỗi vượt ngưỡng",
        detail: `Tỷ lệ lỗi hiện tại ${formatPercent(errorRate)} đang vượt vùng an toàn.`,
        source: "metrics"
      });
    } else if (errorRate >= 8) {
      rows.push({
        level: "warn",
        title: "Tỷ lệ lỗi đang tăng",
        detail: `Tỷ lệ lỗi hiện tại là ${formatPercent(errorRate)}.`,
        source: "metrics"
      });
    }

    if (latencyMs >= 1200) {
      rows.push({
        level: "warn",
        title: "Độ trễ cao",
        detail: `Độ trễ trung bình ${latencyMs}ms đang cao hơn mức mục tiêu.`,
        source: "metrics"
      });
    }

    if (sourceCoverage < 50 && state.totalSources > 0) {
      rows.push({
        level: "warn",
        title: "Độ phủ nguồn thấp",
        detail: `${state.enabledSources}/${state.totalSources} nguồn đang bật.`,
        source: "control-tower"
      });
    }

    if (!verificationStackEnabled) {
      rows.push({
        level: "critical",
        title: "Stack kiểm chứng đang tắt",
        detail: "Rule verification hoặc NLI stack đang tắt, cần bật để giữ guardrail production.",
        source: "flow"
      });
    }

    if (rows.length === 0) {
      rows.push({
        level: "info",
        title: "Hệ thống ổn định",
        detail: "Chưa phát hiện tín hiệu bất thường trong khoảng theo dõi hiện tại.",
        source: "system"
      });
    }

    return rows;
  }, [apiTone, errorRate, latencyMs, sourceCoverage, state.apiMessage, state.enabledSources, state.mlReachable, state.mlStatus, state.totalSources, verificationStackEnabled]);

  const riskMatrix = useMemo(
    () =>
      buildRiskMatrix({
        errors,
        errorRate,
        latencyMs,
        sourceCoverage,
        flowEnabled: state.flowEnabledCount
      }),
    [errorRate, errors, latencyMs, sourceCoverage, state.flowEnabledCount]
  );

  const flowRows: Array<{ label: string; enabled: boolean; detail: string }> = [
    { label: "Role Router", enabled: state.flow.roleRouter, detail: "Định tuyến theo vai trò người dùng." },
    { label: "Intent Router", enabled: state.flow.intentRouter, detail: "Tách ý định để chọn pipeline phù hợp." },
    { label: "Rule Verification", enabled: state.flow.ruleVerification, detail: "Kiểm chứng theo luật và policy trước phản hồi." },
    { label: "NLI Model", enabled: state.flow.nliModel, detail: "Mô hình NLI cho quan hệ claim-evidence." },
    { label: "RAG NLI", enabled: state.flow.ragNli, detail: "Bật bước NLI trong pipeline RAG." },
    { label: "Neural Reranker", enabled: state.flow.ragReranker, detail: "Rerank evidence bằng mô hình neural." },
    { label: "GraphRAG", enabled: state.flow.ragGraphRag, detail: "Nhánh truy xuất theo đồ thị tri thức." },
    { label: "DeepSeek Fallback", enabled: state.flow.deepseekFallback, detail: "Dự phòng đường suy luận khi degrade." },
    { label: "Scientific Retrieval", enabled: state.flow.scientificRetrieval, detail: "Ưu tiên nguồn y khoa chuẩn." },
    { label: "Web Retrieval", enabled: state.flow.webRetrieval, detail: "Bổ sung khi nguồn nội bộ thiếu ngữ cảnh." },
    { label: "File Retrieval", enabled: state.flow.fileRetrieval, detail: "Truy xuất dữ liệu tài liệu đã upload." }
  ];

  const friendlySummary = useMemo(() => {
    if (state.error) {
      return {
        tone: "critical",
        title: "Không tải được dữ liệu giám sát",
        detail: "Vui lòng làm mới lại hoặc kiểm tra kết nối tới backend."
      } as const;
    }

    if (alerts.some((alert) => alert.level === "critical")) {
      return {
        tone: "critical",
        title: "Cần xử lý ngay",
        detail: "Có cảnh báo mức nghiêm trọng. Nên ưu tiên xử lý trước khi tiếp tục vận hành."
      } as const;
    }

    if (alerts.some((alert) => alert.level === "warn")) {
      return {
        tone: "warn",
        title: "Có tín hiệu cần theo dõi",
        detail: "Hệ thống vẫn chạy nhưng một số chỉ số đang lệch mục tiêu."
      } as const;
    }

    return {
      tone: "ok",
      title: "Hệ thống đang ổn định",
      detail: "Các chỉ số chính đang trong vùng an toàn."
    } as const;
  }, [alerts, state.error]);

  return (
    <div className="space-y-4">
      <section className="futura-panel rounded-[1.75rem] p-4">
        <div className="relative z-[1] flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Theo Dõi Hệ Thống</p>
            <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Bảng quan sát thân thiện</h3>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Một màn hình duy nhất để theo dõi trạng thái, cảnh báo và chất lượng trả lời.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                className="h-3.5 w-3.5"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
              />
              Tự động 15s
            </label>
            <button
              type="button"
              onClick={() => void load()}
              className="rounded-lg border border-cyan-400/60 bg-cyan-100/80 px-3 py-1.5 text-xs font-semibold text-cyan-800 transition hover:bg-cyan-200 dark:border-cyan-500/45 dark:bg-cyan-950/45 dark:text-cyan-200 dark:hover:bg-cyan-900/65"
            >
              Làm mới
            </button>
          </div>
        </div>

        {state.error ? (
          <p className="relative z-[1] mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/35 dark:text-rose-200">
            {state.error}
          </p>
        ) : null}

        <div
          className={[
            "relative z-[1] mt-3 rounded-lg border px-3 py-2 text-sm",
            friendlySummary.tone === "critical"
              ? "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
              : friendlySummary.tone === "warn"
                ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
                : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
          ].join(" ")}
        >
          <p className="font-semibold">{friendlySummary.title}</p>
          <p className="mt-0.5 text-xs opacity-90">{friendlySummary.detail}</p>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Sức khỏe API</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{state.apiStatus}</p>
          <p className="text-xs text-[var(--text-secondary)]">{state.apiMessage || "Chưa có chi tiết"}</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Trạng thái ML</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{state.mlReachable === false ? "mất kết nối" : "đang hoạt động"}</p>
          <p className="text-xs text-[var(--text-secondary)]">{state.mlStatus}</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Request / Lỗi</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">
            {formatCount(state.requestCount)} <span className="text-sm text-rose-400">/ {formatCount(state.errorCount)}</span>
          </p>
          <p className="text-xs text-[var(--text-secondary)]">Tỷ lệ lỗi {formatPercent(errorRate)}</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Độ trễ</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{latencyMs}ms</p>
          <p className="text-xs text-[var(--text-secondary)]">Độ phủ nguồn {formatPercent(sourceCoverage)}</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Độ ổn định</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{Math.round(runtimeStability)}</p>
          <p className="text-xs text-[var(--text-secondary)]">Tính từ lỗi + độ trễ + phụ thuộc</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Mức kiểm chứng</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{Math.round(verificationStrength)}</p>
          <p className="text-xs text-[var(--text-secondary)]">Ngưỡng low-context {Math.round(state.lowContextThreshold * 100)}%</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Flow đang bật</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{state.flowEnabledCount}/{TOTAL_FLOW_FLAGS}</p>
          <p className="text-xs text-[var(--text-secondary)]">Sức khỏe flow {Math.round(flowHealth)}</p>
        </article>
        <article className="futura-kpi rounded-xl p-3">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Thành công</p>
          <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{success}</p>
          <p className="text-xs text-[var(--text-secondary)]">Số request xử lý thành công</p>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <article className="futura-card rounded-2xl p-4">
          <NeonAreaChart
            title="Áp lực lưu lượng"
            description="Request và lỗi trong khung thời gian theo dõi gần nhất"
            labels={axisLabels}
            series={trafficSeries}
            height={240}
          />
        </article>
        <article className="futura-card rounded-2xl p-4">
          <NeonAreaChart
            title="Hiệu năng tổng quan"
            description="Độ trễ và độ phủ nguồn theo thời gian"
            labels={axisLabels}
            series={performanceSeries}
            height={240}
          />
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="futura-card rounded-2xl p-4">
          <div className="grid grid-cols-2 gap-3">
            <SegmentRingGauge label="Ổn định" value={Math.round(runtimeStability)} tone="cyan" />
            <SegmentRingGauge label="Kiểm chứng" value={Math.round(verificationStrength)} tone="emerald" />
            <SegmentRingGauge label="Độ phủ" value={Math.round(sourceCoverage)} tone="violet" />
            <SegmentRingGauge label="Flow" value={Math.round(flowHealth)} tone="amber" />
          </div>
        </article>

        <article className="futura-card rounded-2xl p-4">
          <RadarPulseChart
            title="Radar điều khiển"
            description="Khả năng ổn định theo 5 chiều quan trọng"
            axes={radarAxes}
            size={260}
          />
        </article>

        <article className="futura-card rounded-2xl p-4">
          <TelemetryBars title="Cụm tín hiệu" description="Điểm sức khỏe thời gian thực theo từng cụm" items={signalItems} />
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr_1fr]">
        <article className="futura-card rounded-2xl p-4">
          <ConduitFlowLine
            title="Luồng xử lý"
            description="Cổng vào -> định tuyến -> kiểm chứng -> ML"
            stages={pipelineStages}
          />

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {flowRows.map((row) => (
              <div key={row.label} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{row.label}</p>
                  <span
                    className={[
                      "inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                      row.enabled
                        ? "border-emerald-300/80 bg-emerald-100/90 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/45 dark:text-emerald-200"
                        : "border-amber-300/80 bg-amber-100/90 text-amber-800 dark:border-amber-700 dark:bg-amber-950/45 dark:text-amber-200"
                    ].join(" ")}
                  >
                    {row.enabled ? "BẬT" : "TẮT"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{row.detail}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="futura-card rounded-2xl p-4">
          <MatrixHeatmapMini
            title="Ma trận áp lực rủi ro"
            description="Cường độ rủi ro theo lỗi, độ trễ, độ phủ và flow"
            rows={["Lỗi", "Độ trễ", "Độ phủ", "Flow"]}
            columns={["Thấp", "Vừa", "Cao", "Nghiêm trọng"]}
            values={riskMatrix}
            minLabel="Áp lực thấp"
            maxLabel="Áp lực cao"
          />
        </article>

        <article className="futura-card rounded-2xl p-4">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Cảnh báo cần xử lý</h3>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Ưu tiên theo mức độ ảnh hưởng và nguồn phát sinh.</p>

          <div className="mt-3 space-y-2">
            {alerts.map((alert, index) => {
              const levelLabel =
                alert.level === "critical" ? "nghiêm trọng" : alert.level === "warn" ? "cảnh báo" : "ổn định";
              const toneClass =
                alert.level === "critical"
                  ? "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
                  : alert.level === "warn"
                    ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
                    : "border-cyan-300 bg-cyan-50 text-cyan-800 dark:border-cyan-800 dark:bg-cyan-950/40 dark:text-cyan-200";

              return (
                <div key={`${alert.title}-${index}`} className={["rounded-lg border p-3", toneClass].join(" ")}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em]">{levelLabel}</p>
                    <span className="rounded-full border border-current/30 px-2 py-0.5 text-[10px] uppercase">{alert.source}</span>
                  </div>
                  <p className="mt-1 text-sm font-semibold">{alert.title}</p>
                  <p className="mt-1 text-xs opacity-90">{alert.detail}</p>
                </div>
              );
            })}
          </div>
        </article>
      </section>
    </div>
  );
}
