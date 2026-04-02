"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BarBlocks, Sparkline } from "@/components/admin/admin-visuals";
import {
  getApiHealth,
  getControlTowerConfig,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics
} from "@/lib/system";

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
  lowContextThreshold: 0
};

function toInt(value: number | null): number {
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value ?? 0)) : 0;
}

export default function AdminObservabilityPanel() {
  const [state, setState] = useState<ObservabilityState>(INITIAL_STATE);
  const [grafanaTheme, setGrafanaTheme] = useState<"dark" | "light">("dark");
  const grafanaBaseUrl = useMemo(() => {
    const raw = (process.env.NEXT_PUBLIC_GRAFANA_URL ?? "/grafana").trim();
    if (!raw) return "";
    return raw.endsWith("/") ? raw.slice(0, -1) : raw;
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    const syncTheme = () => {
      const isDark = root.classList.contains("dark") || root.dataset.theme === "dark";
      setGrafanaTheme(isDark ? "dark" : "light");
    };
    syncTheme();
    const observer = new MutationObserver(syncTheme);
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["class", "data-theme"]
    });
    return () => observer.disconnect();
  }, []);

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
      const flowEnabledCount = [
        config.rag_flow.role_router_enabled,
        config.rag_flow.intent_router_enabled,
        config.rag_flow.verification_enabled,
        config.rag_flow.deepseek_fallback_enabled
      ].filter(Boolean).length;

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
        lowContextThreshold: config.rag_flow.low_context_threshold
      });
    } catch (cause) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: cause instanceof Error ? cause.message : "Unable to load observability snapshot."
      }));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const requestCount = toInt(state.requestCount);
  const errorCount = toInt(state.errorCount);
  const successCount = Math.max(0, requestCount - errorCount);
  const latencyMs = toInt(state.avgLatencyMs);

  const requestShape = useMemo(() => {
    const base = requestCount || 1;
    return [Math.max(1, base * 0.45), Math.max(1, base * 0.72), Math.max(1, base * 0.84), Math.max(1, base)];
  }, [requestCount]);

  const healthBars = [
    successCount || 1,
    errorCount || 1,
    Math.max(1, Math.round((state.mlReachable ? 1 : 0.3) * 100)),
    Math.max(1, state.flowEnabledCount * 25),
    Math.max(1, Math.round(state.lowContextThreshold * 100))
  ];

  const apiHealthy = state.apiStatus.toLowerCase().includes("ok") || state.apiStatus.toLowerCase().includes("healthy");
  const grafanaEmbeddedUrl = grafanaBaseUrl
    ? `${grafanaBaseUrl}/d/clara-observability/clara-observability?orgId=1&from=now-6h&to=now&refresh=10s&kiosk=tv&theme=${grafanaTheme}`
    : "";
  const grafanaOpenUrl = grafanaBaseUrl
    ? `${grafanaBaseUrl}/d/clara-observability/clara-observability?orgId=1&from=now-24h&to=now`
    : "";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-cyan-300/45 bg-[linear-gradient(145deg,rgba(255,255,255,0.94),rgba(236,254,255,0.86))] p-4 shadow-[0_26px_60px_-42px_rgba(8,47,73,0.42)] dark:border-cyan-500/30 dark:bg-[linear-gradient(150deg,rgba(2,6,23,0.92),rgba(8,47,73,0.76))]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Grafana Integration</p>
            <h3 className="mt-1 text-base font-semibold text-slate-900 dark:text-slate-100">Admin Observability Wall</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
              Bảng Grafana thật được mount trực tiếp từ stack monitoring (Prometheus + Grafana provisioning).
            </p>
          </div>
          {grafanaOpenUrl ? (
            <a
              href={grafanaOpenUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-cyan-400/60 bg-cyan-100/80 px-3 py-1.5 text-xs font-semibold text-cyan-800 transition hover:bg-cyan-200 dark:border-cyan-500/45 dark:bg-cyan-950/45 dark:text-cyan-200 dark:hover:bg-cyan-900/65"
            >
              Open Grafana ↗
            </a>
          ) : null}
        </div>

        {grafanaEmbeddedUrl ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white/85 dark:border-slate-700 dark:bg-slate-900/70">
            <iframe
              title="CLARA Grafana Observability"
              src={grafanaEmbeddedUrl}
              className="h-[560px] w-full"
              loading="lazy"
            />
          </div>
        ) : (
          <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-200">
            Thiếu cấu hình `NEXT_PUBLIC_GRAFANA_URL`. Hãy set env này để embed Grafana.
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Runtime Signals</p>
            <h3 className="mt-2 text-sm font-semibold text-slate-900">Observability Snapshot</h3>
            <p className="mt-1 text-xs text-slate-600">Ghép health + dependencies + metrics với snapshot cấu hình control tower.</p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
          >
            Refresh
          </button>
        </div>

        {state.error ? <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{state.error}</p> : null}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">API Health</p>
            <p className={[
              "mt-1 text-lg font-semibold",
              apiHealthy ? "text-emerald-600" : "text-amber-600"
            ].join(" ")}>{state.apiStatus}</p>
            <p className="mt-1 text-xs text-slate-600">{state.apiMessage || "No details"}</p>
          </article>

          <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">ML Dependency</p>
            <p className={[
              "mt-1 text-lg font-semibold",
              state.mlReachable === false ? "text-rose-600" : "text-emerald-600"
            ].join(" ")}>{state.mlReachable === false ? "unreachable" : "reachable"}</p>
            <p className="mt-1 text-xs text-slate-600">{state.mlStatus}</p>
          </article>

          <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">Requests / Errors</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {requestCount} <span className="text-sm text-rose-600">/ {errorCount}</span>
            </p>
            <p className="mt-1 text-xs text-slate-600">Tổng request và lỗi tại thời điểm snapshot</p>
          </article>

          <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">Avg Latency</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{latencyMs}ms</p>
            <p className="mt-1 text-xs text-slate-600">Nguồn enable: {state.enabledSources}/{state.totalSources}</p>
          </article>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Traffic Sparkline</h3>
            <span className="text-xs text-slate-500">Request momentum</span>
          </div>
          <div className="mt-3">
            {state.loading ? <div className="h-14 animate-pulse rounded-lg bg-slate-100" /> : <Sparkline points={requestShape} />}
          </div>
          <p className="mt-2 text-xs text-slate-500">Chuỗi tín hiệu suy diễn từ request count để theo dõi biến thiên tải.</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Signal Blocks</h3>
            <span className="text-xs text-slate-500">success/error/ml/flow/threshold</span>
          </div>
          <div className="mt-3">
            {state.loading ? <div className="h-16 animate-pulse rounded-lg bg-slate-100" /> : <BarBlocks values={healthBars} />}
          </div>
          <p className="mt-2 text-xs text-slate-500">Theo thứ tự: success, error, ML dependency, flow flags, low-context threshold.</p>
        </article>
      </section>
    </div>
  );
}
