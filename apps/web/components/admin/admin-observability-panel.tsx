"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, {
  selectAsyncState,
  type AsyncState
} from "@/components/ui/async-section";
import {
  ConduitFlowLine,
  MatrixHeatmapMini,
  NeonAreaChart,
  RadarPulseChart,
  SegmentRingGauge
} from "@/components/dashboard/futuristic-charts";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  acknowledgeObservabilityAlert,
  getApiHealth,
  getControlTowerConfig,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics,
  type RouteLatencyPercentiles
} from "@/lib/system";

type FlowFlags = {
  roleRouter: boolean;
  intentRouter: boolean;
  ruleVerification: boolean;
  nliModel: boolean;
  ragReranker: boolean;
  ragNli: boolean;
  ragGraphRag: boolean;
  scientificRetrieval: boolean;
  webRetrieval: boolean;
  fileRetrieval: boolean;
};

type ObservabilityState = {
  loading: boolean;
  loaded: boolean;
  error: string;
  apiStatus: string;
  apiMessage: string;
  mlReachable: boolean | null;
  mlStatus: string;
  requestCount: number | null;
  errorCount: number | null;
  avgLatencyMs: number | null;
  routePercentiles: RouteLatencyPercentiles[];
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
  /**
   * Stable backend alert id (rule + target dedupe key) this row maps to, when
   * the engine tracks an equivalent condition. Present only for rows that can
   * be acknowledged through `/admin/observability` (Requirement 8.4).
   */
  alertId?: string;
};

// Map a client-surfaced alert source onto the alert engine's stable dedupe id
// (see `observability/alerts.py`: `stable_alert_id`). Only conditions the engine
// actually tracks are acknowledgeable; everything else renders without a button.
const ALERT_SOURCE_TO_STABLE_ID: Record<string, string> = {
  ml: "ml:ml_dependency",
  api: "api:api_runtime",
  metrics: "api:api_runtime"
};

const INITIAL_STATE: ObservabilityState = {
  loading: true,
  loaded: false,
  error: "",
  apiStatus: "unknown",
  apiMessage: "",
  mlReachable: null,
  mlStatus: "unknown",
  requestCount: null,
  errorCount: null,
  avgLatencyMs: null,
  routePercentiles: [],
  totalSources: 0,
  enabledSources: 0,
  flowEnabledCount: 0,
  lowContextThreshold: 0,
  flow: {
    roleRouter: false,
    intentRouter: false,
    ruleVerification: false,
    nliModel: false,
    ragReranker: true,
    ragNli: false,
    ragGraphRag: true,
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

function formatLatencyMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(Math.max(0, value))}ms`;
}

function formatClock(value: number): string {
  const date = new Date(value);
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
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
  const optionalOn = [flow.webRetrieval, flow.fileRetrieval, flow.ragGraphRag].filter(Boolean).length;
  return clamp(requiredOn * 11 + optionalOn * 6);
}

export function AdminObservabilityPanel() {
  const uiLanguage = useUILanguage();
  const [state, setState] = useState<ObservabilityState>(INITIAL_STATE);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  // Per-alert acknowledge UI state keyed by the stable alert id (in-flight,
  // acknowledged, and a sanitized error message). Kept local to the panel so an
  // ack never blocks the 15s telemetry refresh.
  const [ackPending, setAckPending] = useState<Record<string, boolean>>({});
  const [ackDone, setAckDone] = useState<Record<string, boolean>>({});
  const [ackError, setAckError] = useState<Record<string, string>>({});

  const handleAcknowledge = useCallback(async (alertId: string) => {
    setAckPending((prev) => ({ ...prev, [alertId]: true }));
    setAckError((prev) => ({ ...prev, [alertId]: "" }));
    try {
      await acknowledgeObservabilityAlert(alertId);
      setAckDone((prev) => ({ ...prev, [alertId]: true }));
    } catch (cause) {
      setAckError((prev) => ({
        ...prev,
        [alertId]: safeUserFacingError(cause, t(uiLanguage, "admin.observability.error.acknowledge"))
      }));
    } finally {
      setAckPending((prev) => ({ ...prev, [alertId]: false }));
    }
  }, [uiLanguage]);

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
        scientificRetrieval: Boolean(config.rag_flow.scientific_retrieval_enabled),
        webRetrieval: Boolean(config.rag_flow.web_retrieval_enabled),
        fileRetrieval: Boolean(config.rag_flow.file_retrieval_enabled)
      };

      const flowEnabledCount = Object.values(flow).filter(Boolean).length;
      const sourceCoverage = sources.length > 0 ? (enabledSources / sources.length) * 100 : 0;

      setState({
        loading: false,
        loaded: true,
        error: "",
        apiStatus: health.status,
        apiMessage: health.message,
        mlReachable: dependencies.mlReachable,
        mlStatus: dependencies.mlStatus,
        requestCount: metrics.requestCount,
        errorCount: metrics.errorCount,
        avgLatencyMs: metrics.avgLatencyMs,
        routePercentiles: metrics.routePercentiles,
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
        error: safeUserFacingError(cause, t(uiLanguage, "admin.observability.error.load"))
      }));
    }
  }, [uiLanguage]);

  useEffect(() => {
    void load();
  }, [load]);

  // Emit a single named product event when the Observability surface is opened
  // (Req 9.1). No PII — only the coarse Admin view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "observability" });
  }, []);

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

  const effectiveTimeline = useMemo<TimelinePoint[]>(() => {
    if (timeline.length > 0) return timeline;

    const now = Date.now();
    return Array.from({ length: 6 }).map((_, index) => ({
      at: now - (5 - index) * 60_000,
      requests: Math.max(0, requests - (5 - index) * 2),
      errors: Math.max(0, errors - (5 - index > 2 ? 1 : 0)),
      latencyMs: Math.max(0, latencyMs + (index % 2 === 0 ? 4 : -3)),
      flowEnabledCount: state.flowEnabledCount,
      sourceCoverage: Math.round(sourceCoverage)
    }));
  }, [errors, latencyMs, requests, sourceCoverage, state.flowEnabledCount, timeline]);

  const apiTone = toneForStatus(state.apiStatus);
  const mlTone = state.mlReachable === false ? "error" : toneForStatus(state.mlStatus);
  const runtimeStability = clamp(100 - errorRate * 2.2 - latencyMs / 58 - (state.mlReachable === false ? 24 : 0));
  const verificationStrength = clamp(flowHealth - state.lowContextThreshold * 28 + 12);

  const axisLabels = useMemo(() => {
    return effectiveTimeline.map((item) => {
      const date = new Date(item.at);
      return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
    });
  }, [effectiveTimeline]);

  const trafficSeries = useMemo(
    () => [
      {
        id: "requests",
        label: "Request",
        color: "#60a5fa",
        values: effectiveTimeline.map((item) => item.requests)
      },
      {
        id: "errors",
        label: "Lỗi",
        color: "#fb7185",
        values: effectiveTimeline.map((item) => item.errors)
      }
    ],
    [effectiveTimeline]
  );

  const performanceSeries = useMemo(
    () => [
      {
        id: "latency",
        label: "Độ trễ",
        color: "#60a5fa",
        values: effectiveTimeline.map((item) => item.latencyMs)
      },
      {
        id: "sourceCoverage",
        label: "Độ phủ nguồn",
        color: "#34d399",
        values: effectiveTimeline.map((item) => item.sourceCoverage)
      }
    ],
    [effectiveTimeline]
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

    return rows.map((row) => ({
      ...row,
      alertId: ALERT_SOURCE_TO_STABLE_ID[row.source]
    }));
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

  const latestPoint = effectiveTimeline[effectiveTimeline.length - 1];
  const lastUpdate = latestPoint ? formatClock(latestPoint.at) : "--:--:--";

  // Fold loading/error/loaded into one of the four mutually-exclusive
  // AsyncSection states. The loading slot is only shown on the first load so
  // 15s auto-refreshes don't blank an already-populated dashboard; the toolbar
  // already reflects in-flight syncs. Errors carry the pre-sanitized message
  // (no stack traces / upstream codes) from `safeUserFacingError` (Req 5.6).
  const dashboardState = useMemo<AsyncState<true>>(
    () =>
      selectAsyncState<true>({
        loading: state.loading && !state.loaded,
        // First-load failures surface as the AsyncSection error state. Once a
        // snapshot exists, a failed refresh keeps the populated dashboard and
        // the sanitized message is shown as a non-blocking banner instead.
        error: state.loaded ? null : state.error || null,
        data: state.loaded ? true : null,
        isEmpty: () =>
          state.requestCount === null &&
          state.mlReachable === null &&
          state.totalSources === 0 &&
          state.routePercentiles.length === 0
      }),
    [state.error, state.loaded, state.loading, state.mlReachable, state.requestCount, state.routePercentiles.length, state.totalSources]
  );

  const percentilesEnabled = state.routePercentiles.length > 0;

  const flowRows: Array<{ label: string; enabled: boolean; detail: string }> = [
    { label: "Role Router", enabled: state.flow.roleRouter, detail: "Định tuyến theo vai trò người dùng." },
    { label: "Intent Router", enabled: state.flow.intentRouter, detail: "Tách ý định để chọn pipeline phù hợp." },
    { label: "Rule Verification", enabled: state.flow.ruleVerification, detail: "Kiểm chứng theo luật và policy trước phản hồi." },
    { label: "NLI Model", enabled: state.flow.nliModel, detail: "Mô hình NLI cho quan hệ claim-evidence." },
    { label: "RAG NLI", enabled: state.flow.ragNli, detail: "Bật bước NLI trong pipeline RAG." },
    { label: "Neural Reranker", enabled: state.flow.ragReranker, detail: "Rerank evidence bằng mô hình neural." },
    { label: "GraphRAG", enabled: state.flow.ragGraphRag, detail: "Nhánh truy xuất theo đồ thị tri thức." },
    { label: "Scientific Retrieval", enabled: state.flow.scientificRetrieval, detail: "Ưu tiên nguồn y khoa chuẩn." },
    { label: "Web Retrieval", enabled: state.flow.webRetrieval, detail: "Bổ sung khi nguồn nội bộ thiếu ngữ cảnh." },
    { label: "File Retrieval", enabled: state.flow.fileRetrieval, detail: "Truy xuất dữ liệu tài liệu đã upload." }
  ];

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-secondary)]">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 accent-[var(--brand-primary)]"
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
            />
            Auto refresh 15s
          </label>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-[var(--radius-md)] border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--text-brand)] transition-colors hover:bg-[var(--surface-muted)]"
          >
            Refresh
          </button>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
          <span>Ảnh chụp telemetry</span>
          <span className="text-[var(--text-muted)]">|</span>
          <span>Đồng bộ: {state.loading ? "đang cập nhật" : state.error ? "cần thử lại" : "đã cập nhật"}</span>
          <span className="text-[var(--text-muted)]">|</span>
          <span>UPDATED: {lastUpdate} GMT+7</span>
        </div>
      </section>

      {state.error && state.loaded ? (
        <p className="rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-xs text-[var(--status-warn-text)]">
          {state.error}
        </p>
      ) : null}

      <AsyncSection<true>
        state={dashboardState}
        loadingLabel="Đang tải ảnh chụp trạng thái hệ thống..."
        emptyTitle="Chưa có dữ liệu quan trắc"
        emptyDescription="Hiện chưa có tín hiệu telemetry nào để hiển thị trong khung theo dõi."
        errorTitle="Không tải được dữ liệu quan trắc"
      >
        {() => (
          <div className="grid grid-cols-12 gap-6">
        <section className="col-span-12 lg:col-span-8 grid grid-cols-2 gap-4 xl:grid-cols-3 [&>article]:rounded-[14px] [&>article]:border [&>article]:border-t-[#2A3950] [&>article]:border-[color:var(--shell-border)] [&>article]:bg-[var(--surface-panel)]">
          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Sức khỏe API</p>
            <p className="mt-2 text-2xl font-black text-[var(--text-brand)]">{state.apiStatus || "UNKNOWN"}</p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">{state.apiMessage || "Không có chi tiết"}</p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--surface-muted)]">
              <div className="h-full bg-[#60a5fa]" style={{ width: `${clamp(runtimeStability)}%` }} />
            </div>
          </article>

          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Trạng thái ML</p>
            <p className="mt-2 text-xl font-bold text-[var(--text-primary)]">{state.mlReachable === false ? "Mất kết nối" : "Đang hoạt động"}</p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">{state.mlStatus || "Unknown"}</p>
            <p className="mt-3 text-[11px] font-semibold text-[var(--text-secondary)]">Trạng thái phụ thuộc do API báo cáo.</p>
          </article>

          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Request / Lỗi</p>
            <p className="mt-2 text-2xl font-black text-[var(--text-primary)]">
              {formatCount(state.requestCount)} <span className="text-lg text-[var(--status-danger-text)]">/ {formatCount(state.errorCount)}</span>
            </p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">Trong khung theo dõi gần nhất</p>
          </article>

          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Độ trễ</p>
            <p className="mt-2 text-2xl font-black text-[var(--text-primary)]">{latencyMs}ms</p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">Độ trễ trung bình trong ảnh chụp hiện tại.</p>
          </article>

          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Độ ổn định</p>
            <p className="mt-2 text-2xl font-black text-[var(--text-primary)]">{Math.round(runtimeStability)}</p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">Chỉ số dẫn xuất từ telemetry hiện có.</p>
          </article>

          <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Mức kiểm chứng</p>
            <p className="mt-2 text-2xl font-black text-[var(--text-brand)]">{Math.round(verificationStrength)}%</p>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">Low-context threshold: {Math.round(state.lowContextThreshold * 100)}%</p>
          </article>
        </section>

        <section className="col-span-12 lg:col-span-4 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <RadarPulseChart
            title="Radar điều khiển"
            description="Vận hành, kiểm chứng, độ phủ, flow, API"
            axes={radarAxes}
            size={250}
          />

          <div className="mt-4 grid grid-cols-2 gap-2">
            {signalItems.map((item) => (
              <div key={item.label} className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2">
                <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{item.label}</p>
                <p
                  className={[
                    "mt-1 text-base font-bold",
                    item.tone === "danger" ? "text-[var(--status-danger-text)]" : item.tone === "warn" ? "text-[var(--status-warn-text)]" : "text-[var(--text-brand)]"
                  ].join(" ")}
                >
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="col-span-12 lg:col-span-6 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <NeonAreaChart
            title="Áp lực lưu lượng"
            description="Request và lỗi theo thời gian"
            labels={axisLabels}
            series={trafficSeries}
            height={220}
          />
        </section>

        <section className="col-span-12 lg:col-span-6 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="grid grid-cols-2 gap-3">
            <SegmentRingGauge label="Độ trễ" value={clamp(100 - latencyMs / 5)} tone="cyan" />
            <SegmentRingGauge label="Độ phủ" value={Math.round(sourceCoverage)} tone="violet" />
            <SegmentRingGauge label="Flow" value={Math.round(flowHealth)} tone="emerald" />
            <SegmentRingGauge label="Success" value={clamp(100 - errorRate)} tone="amber" />
          </div>
          <div className="mt-4 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
            <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Hiệu năng tổng quan</p>
            <NeonAreaChart
              title=""
              description=""
              labels={axisLabels}
              series={performanceSeries}
              height={120}
            />
          </div>
        </section>

        <section className="col-span-12 lg:col-span-7 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Luồng Xử Lý (Processing Pipeline)</h3>
            <div className="flex gap-2">
              <span className="rounded bg-[var(--surface-brand-soft)] px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-brand)]">Live Flow</span>
              <span className="rounded bg-[var(--surface-muted)] px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Latency {latencyMs}ms</span>
            </div>
          </div>
          <ConduitFlowLine title="" description="" stages={pipelineStages} />
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {flowRows.map((row) => (
              <div key={row.label} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{row.label}</p>
                  <span
                    className={[
                      "inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                      row.enabled ? "border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]" : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
                    ].join(" ")}
                  >
                    {row.enabled ? "Bật" : "Tắt"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{row.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="col-span-12 lg:col-span-5 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
          <MatrixHeatmapMini
            title="Ma Trận Áp Lực Rủi Ro"
            description="Lỗi, độ trễ, độ phủ, flow"
            rows={["Lỗi", "Độ trễ", "Độ phủ", "Flow"]}
            columns={["Thấp", "Vừa", "Cao", "Nghiêm trọng"]}
            values={riskMatrix}
            minLabel="Thấp"
            maxLabel="Nghiêm trọng"
          />

          <div className="mt-4 border-t border-[color:var(--shell-border)] pt-4">
            <h4 className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--text-secondary)]">Cảnh Báo Cần Xử Lý</h4>
            <div className="mt-3 space-y-2">
              {alerts.map((alert, index) => {
                const levelLabel = alert.level === "critical" ? "Nghiêm trọng" : alert.level === "warn" ? "Cảnh báo" : "Ổn định";
                const toneClass =
                  alert.level === "critical"
                    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                    : alert.level === "warn"
                      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                      : "border-[color:var(--brand-primary)]/35 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]";

                return (
                  <div key={`${alert.title}-${index}`} className={["rounded-lg border p-3", toneClass].join(" ")}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em]">{levelLabel}</p>
                      <span className="rounded-full border border-current/30 px-2 py-0.5 text-[10px] uppercase">{alert.source}</span>
                    </div>
                    <p className="mt-1 text-sm font-semibold">{alert.title}</p>
                    <p className="mt-1 text-xs opacity-90">{alert.detail}</p>
                    {alert.alertId ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => void handleAcknowledge(alert.alertId as string)}
                          disabled={Boolean(ackPending[alert.alertId]) || Boolean(ackDone[alert.alertId])}
                          className="rounded-md border border-current/40 bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition hover:bg-[var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {ackDone[alert.alertId]
                            ? "Đã xác nhận"
                            : ackPending[alert.alertId]
                              ? "Đang xác nhận..."
                              : "Xác nhận"}
                        </button>
                        {ackError[alert.alertId] ? (
                          <span className="text-[11px] text-[var(--status-danger-text)]">{ackError[alert.alertId]}</span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="col-span-12 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Độ trễ theo tuyến (p50 / p90 / p99)</h3>
              <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                Phân vị độ trễ cho từng route từ ảnh chụp `/system/metrics`.
              </p>
            </div>
            <span
              className={[
                "rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                percentilesEnabled
                  ? "border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
              ].join(" ")}
            >
              {percentilesEnabled ? "Đang bật" : "Chưa bật"}
            </span>
          </div>

          {percentilesEnabled ? (
            <div className="overflow-x-auto rounded-lg border border-[color:var(--shell-border)]">
              <table className="w-full min-w-[480px] text-left text-xs">
                <thead className="bg-[var(--surface-muted)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Tuyến</th>
                    <th className="px-3 py-2 text-right font-semibold">p50</th>
                    <th className="px-3 py-2 text-right font-semibold">p90</th>
                    <th className="px-3 py-2 text-right font-semibold">p99</th>
                  </tr>
                </thead>
                <tbody>
                  {state.routePercentiles.map((row) => (
                    <tr key={row.route} className="border-t border-[color:var(--shell-border)]">
                      <td className="px-3 py-2 font-mono text-[11px] text-[var(--text-primary)]">{row.route}</td>
                      <td className="px-3 py-2 text-right font-semibold text-[var(--text-brand)]">{formatLatencyMs(row.p50Ms)}</td>
                      <td className="px-3 py-2 text-right font-semibold text-[var(--status-warn-text)]">{formatLatencyMs(row.p90Ms)}</td>
                      <td className="px-3 py-2 text-right font-semibold text-[var(--status-danger-text)]">{formatLatencyMs(row.p99Ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-6 text-center text-xs text-[var(--text-secondary)]">
              Phân vị độ trễ theo tuyến chưa được bật. Hệ thống đang hiển thị độ trễ trung bình ({latencyMs}ms).
            </p>
          )}
        </section>
          </div>
        )}
      </AsyncSection>

      <footer className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-[11px] font-mono text-[var(--text-secondary)]">
        <span>Ảnh chụp telemetry</span>
        <span>Đồng bộ: {state.loading ? "đang cập nhật" : state.error ? "cần thử lại" : "đã cập nhật"}</span>
        <span>LAST UPDATE: {lastUpdate} GMT+7</span>
      </footer>
    </div>
  );
}

export default AdminObservabilityPanel;
