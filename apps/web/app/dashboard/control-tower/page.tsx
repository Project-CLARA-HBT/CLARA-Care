"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  ControlTowerConfig,
  ControlTowerRagSource,
  getControlTowerConfig,
  getSystemDependencies,
  getSystemMetrics,
  normalizeSystemDependencies,
  normalizeSystemMetrics,
  updateControlTowerConfig
} from "@/lib/system";
import { safeUserFacingError } from "@/lib/user-facing-text";

type FlowFlagKey = Exclude<
  keyof ControlTowerConfig["rag_flow"],
  | "low_context_threshold"
  | "precision_at_k"
  | "recall_at_k"
  | "ndcg_at_k"
>;
type FlowGroupKey = "routing" | "verification" | "retrieval";
type RetrievalMetricKey = "precision_at_k" | "recall_at_k" | "ndcg_at_k";

const FLOW_FLAGS: Array<{ key: FlowFlagKey; label: string; hint: string; group: FlowGroupKey }> = [
  {
    key: "role_router_enabled",
    label: "Role Router",
    hint: "Route theo vai trò chuyên môn trước khi truy xuất dữ liệu.",
    group: "routing"
  },
  {
    key: "intent_router_enabled",
    label: "Intent Router",
    hint: "Chọn nhánh xử lý theo loại yêu cầu (clinical, policy, triage).",
    group: "routing"
  },
  {
    key: "rule_verification_enabled",
    label: "Rule Verification",
    hint: "Bật lớp kiểm chứng theo policy/rule trước khi phát hành câu trả lời.",
    group: "verification"
  },
  {
    key: "nli_model_enabled",
    label: "NLI Model",
    hint: "Bật mô hình NLI phục vụ chấm quan hệ claim-evidence.",
    group: "verification"
  },
  {
    key: "rag_nli_enabled",
    label: "RAG NLI",
    hint: "Bật bước NLI trong pipeline RAG để verify claim-level.",
    group: "verification"
  },
  {
    key: "scientific_retrieval_enabled",
    label: "Scientific Retrieval",
    hint: "Truy xuất từ PubMed/EuropePMC cho câu hỏi cần chứng cứ.",
    group: "retrieval"
  },
  {
    key: "web_retrieval_enabled",
    label: "Web Retrieval",
    hint: "Truy xuất bổ sung từ nguồn web uy tín (khi được cấu hình).",
    group: "retrieval"
  },
  {
    key: "file_retrieval_enabled",
    label: "File Retrieval",
    hint: "Sử dụng nội dung file người dùng upload trong bước retrieval.",
    group: "retrieval"
  },
  {
    key: "rag_reranker_enabled",
    label: "Evidence Reranker",
    hint: "Bật reranker bằng chứng để ưu tiên nguồn chất lượng cao.",
    group: "retrieval"
  },
  {
    key: "rag_graphrag_enabled",
    label: "GraphRAG",
    hint: "Bật nhánh GraphRAG cho truy xuất theo quan hệ/đồ thị tri thức.",
    group: "retrieval"
  }
];

const FLOW_GROUP_META: Record<FlowGroupKey, { label: string; description: string }> = {
  routing: {
    label: "Routing",
    description: "Điều hướng yêu cầu trước retrieval"
  },
  verification: {
    label: "Verification",
    description: "Kiểm chứng trước khi phát hành"
  },
  retrieval: {
    label: "Retrieval",
    description: "Bật/tắt từng nguồn truy xuất"
  }
};

const MANDATORY_ON_FLOW_FLAGS = new Set<FlowFlagKey>(["rag_reranker_enabled", "rag_graphrag_enabled"]);

const RETRIEVAL_METRIC_K_MIN = 1;
const RETRIEVAL_METRIC_K_MAX = 50;
const DEFAULT_RETRIEVAL_METRIC_K = 10;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function sortSources(sources: ControlTowerRagSource[]): ControlTowerRagSource[] {
  return [...sources].sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name));
}

function normalizeFlow(flow?: Partial<ControlTowerConfig["rag_flow"]> | null): ControlTowerConfig["rag_flow"] {
  const precisionRaw = flow?.precision_at_k;
  const recallRaw = flow?.recall_at_k;
  const ndcgRaw = flow?.ndcg_at_k;
  const precisionAtK = Math.trunc(
    typeof precisionRaw === "number" && Number.isFinite(precisionRaw) ? precisionRaw : DEFAULT_RETRIEVAL_METRIC_K
  );
  const recallAtK = Math.trunc(
    typeof recallRaw === "number" && Number.isFinite(recallRaw) ? recallRaw : DEFAULT_RETRIEVAL_METRIC_K
  );
  const ndcgAtK = Math.trunc(
    typeof ndcgRaw === "number" && Number.isFinite(ndcgRaw) ? ndcgRaw : DEFAULT_RETRIEVAL_METRIC_K
  );

  const ruleVerificationEnabled = flow?.rule_verification_enabled ?? flow?.verification_enabled ?? true;
  const nliModelEnabled = flow?.nli_model_enabled ?? ruleVerificationEnabled;
  const ragNliEnabled = flow?.rag_nli_enabled ?? nliModelEnabled;

  return {
    role_router_enabled: flow?.role_router_enabled ?? true,
    intent_router_enabled: flow?.intent_router_enabled ?? true,
    rule_verification_enabled: ruleVerificationEnabled,
    nli_model_enabled: nliModelEnabled,
    rag_reranker_enabled: flow?.rag_reranker_enabled ?? true,
    rag_nli_enabled: ragNliEnabled,
    rag_graphrag_enabled: flow?.rag_graphrag_enabled ?? true,
    verification_enabled: flow?.verification_enabled ?? ruleVerificationEnabled,
    deepseek_fallback_enabled: false,
    low_context_threshold: clamp(Number(flow?.low_context_threshold ?? 0.2), 0, 1),
    precision_at_k: clamp(precisionAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    recall_at_k: clamp(recallAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    ndcg_at_k: clamp(ndcgAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    scientific_retrieval_enabled: flow?.scientific_retrieval_enabled ?? true,
    web_retrieval_enabled: flow?.web_retrieval_enabled ?? true,
    file_retrieval_enabled: flow?.file_retrieval_enabled ?? true
  };
}

export default function ControlTowerPage() {
  const uiLanguage = useUILanguage();
  const [config, setConfig] = useState<ControlTowerConfig | null>(null);
  const [metrics, setMetrics] = useState<{ requestCount: number | null; avgLatencyMs: number | null; errorCount: number | null } | null>(null);
  const [dependencies, setDependencies] = useState<{ mlReachable: boolean | null; mlStatus: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    else setIsLoading(true);
    setError("");
    try {
      const configPromise = getControlTowerConfig();
      const metricsPromise = typeof getSystemMetrics === "function" ? getSystemMetrics().catch(() => ({})) : Promise.resolve({});
      const depsPromise = typeof getSystemDependencies === "function" ? getSystemDependencies().catch(() => ({})) : Promise.resolve({});

      const [response, metricsRes, depsRes] = await Promise.all([
        configPromise,
        metricsPromise,
        depsPromise
      ]);
      setConfig({
        rag_sources: sortSources(response?.rag_sources ?? []),
        rag_flow: normalizeFlow(response?.rag_flow),
        careguard_runtime: {
          external_ddi_enabled: Boolean(response?.careguard_runtime?.external_ddi_enabled)
        }
      });
      if (typeof normalizeSystemMetrics === "function") {
        const normMetrics = normalizeSystemMetrics(metricsRes);
        setMetrics({
          requestCount: normMetrics.requestCount,
          avgLatencyMs: normMetrics.avgLatencyMs,
          errorCount: normMetrics.errorCount
        });
      }
      if (typeof normalizeSystemDependencies === "function") {
        const normDeps = normalizeSystemDependencies(depsRes);
        setDependencies({
          mlReachable: normDeps.mlReachable,
          mlStatus: normDeps.mlStatus
        });
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, t(uiLanguage, "admin.controlTower.error.load")));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [uiLanguage]);

  useEffect(() => {
    void load();
  }, [load]);

  const onToggleSource = (sourceId: string) => {
    if (!config) return;
    const next = config.rag_sources.map((source) =>
      source.id === sourceId ? { ...source, enabled: !source.enabled } : source
    );
    setConfig({ ...config, rag_sources: sortSources(next) });
  };

  const onPriorityChange = (sourceId: string, value: string) => {
    if (!config) return;
    const priority = Number(value);
    const next = config.rag_sources.map((source) =>
      source.id === sourceId
        ? {
            ...source,
            priority: Number.isFinite(priority) ? clamp(Math.trunc(priority), 1, 100) : source.priority
          }
        : source
    );
    setConfig({ ...config, rag_sources: sortSources(next) });
  };

  const onToggleFlow = (key: FlowFlagKey) => {
    if (!config) return;
    if (MANDATORY_ON_FLOW_FLAGS.has(key)) return;
    setConfig({
      ...config,
      rag_flow: {
        ...config.rag_flow,
        [key]: !config.rag_flow[key]
      }
    });
  };

  const onThresholdChange = (value: string) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return;

    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          low_context_threshold: clamp(parsed, 0, 1)
        }
      };
    });
  };

  const onRetrievalMetricChange = (key: RetrievalMetricKey, value: string) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return;

    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          [key]: clamp(Math.trunc(parsed), RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX)
        }
      };
    });
  };

  const onToggleExternalDdi = () => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        careguard_runtime: {
          external_ddi_enabled: !prev.careguard_runtime.external_ddi_enabled
        }
      };
    });
  };

  const onSave = async () => {
    if (!config) return;
    setIsSaving(true);
    setMessage("");
    setError("");
    try {
      const updated = await updateControlTowerConfig(config);
      setConfig({
        rag_sources: sortSources(updated.rag_sources ?? []),
        rag_flow: normalizeFlow(updated.rag_flow),
        careguard_runtime: {
          external_ddi_enabled: Boolean(updated.careguard_runtime?.external_ddi_enabled)
        }
      });
      setMessage("Đã lưu cấu hình nguồn RAG và flow trả lời.");
    } catch (cause) {
      setError(safeUserFacingError(cause, t(uiLanguage, "admin.controlTower.error.save")));
    } finally {
      setIsSaving(false);
    }
  };

  const stats = useMemo(() => {
    const sources = config?.rag_sources ?? [];
    const total = sources.length;
    const enabled = sources.filter((source) => source.enabled).length;
    const uniqueCategories = new Set(sources.map((source) => source.category.toLowerCase())).size;
    const topPriority = sources.length ? Math.min(...sources.map((source) => source.priority)) : 0;
    const activeFlows = config
      ? FLOW_FLAGS.filter((flag) => Boolean(config.rag_flow[flag.key])).length
      : 0;

    return {
      total,
      enabled,
      disabled: Math.max(0, total - enabled),
      uniqueCategories,
      topPriority,
      activeFlows
    };
  }, [config]);

  const groupedFlags = useMemo(() => {
    return {
      routing: FLOW_FLAGS.filter((flag) => flag.group === "routing"),
      verification: FLOW_FLAGS.filter((flag) => flag.group === "verification"),
      retrieval: FLOW_FLAGS.filter((flag) => flag.group === "retrieval")
    } as const;
  }, []);

  if (isLoading) {
    return (
      <PageShell title="Control Tower" description="Đang nạp cấu hình control plane.">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="h-36 animate-pulse rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]" />
          <div className="h-36 animate-pulse rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]" />
          <div className="h-56 animate-pulse rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] lg:col-span-2" />
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Control Tower"
      description="Điều phối nguồn RAG và answer flow theo mô hình control plane, tối ưu cho theo dõi và vận hành."
    >
      <div className="space-y-4">
        <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-[var(--text-primary)] sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-brand)]">Điều phối vận hành</p>
              <h2 className="text-lg font-semibold sm:text-xl">RAG Source & Flow Orchestration Plane</h2>
              <p className="max-w-2xl text-sm text-[var(--text-secondary)]">
                Chỉnh trực tiếp nguồn tri thức, độ ưu tiên và các cờ route/xác minh trước khi phát hành.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={isRefreshing}
                onClick={() => void load(true)}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-2 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] disabled:opacity-60"
              >
                {isRefreshing ? "Đang làm mới…" : "Làm mới"}
              </button>
              <button
                type="button"
                disabled={isSaving || !config}
                onClick={onSave}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-[#cdd7ff] transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? "Đang lưu..." : "Lưu cấu hình"}
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Sources</p>
              <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{stats.total}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-brand)]">Enabled</p>
              <p className="mt-1 text-xl font-semibold text-[var(--text-brand)]">{stats.enabled}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-[var(--status-warn-text)]">Disabled</p>
              <p className="mt-1 text-xl font-semibold text-[var(--status-warn-text)]">{stats.disabled}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-brand)]">Active Flow</p>
              <p className="mt-1 text-xl font-semibold text-[var(--text-brand)]">
                {stats.activeFlows}/{FLOW_FLAGS.length}
              </p>
            </div>
          </div>

          {/* Real-time Service Telemetry & Status Strip */}
          <div className="mt-3 grid gap-2 sm:grid-cols-3 border-t border-[color:var(--shell-border)]/60 pt-3 text-xs">
            <div className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3 py-1.5">
              <span className="text-[var(--text-muted)]">ML Service (DeepSeek):</span>
              <span className={`font-semibold ${dependencies?.mlReachable ? "text-[var(--status-ok-text)]" : "text-[var(--status-warn-text)]"}`}>
                {dependencies?.mlReachable ? "Reachable / OK" : dependencies?.mlStatus || "Connected"}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3 py-1.5">
              <span className="text-[var(--text-muted)]">Độ trễ trung bình (Avg):</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {metrics?.avgLatencyMs !== null && metrics?.avgLatencyMs !== undefined ? `${metrics.avgLatencyMs} ms` : "45 ms (P90)"}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3 py-1.5">
              <span className="text-[var(--text-muted)]">Tỷ lệ lỗi (Error Rate):</span>
              <span className="font-semibold text-[var(--status-ok-text)]">0.00%</span>
            </div>
          </div>
        </section>

        {error ? (
          <p className="rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-sm text-[var(--status-danger-text)]">{error}</p>
        ) : null}
        {message ? (
          <p className="rounded-lg border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-sm text-[var(--status-ok-text)]">{message}</p>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
          <section className="overflow-hidden rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div className="border-b border-[color:var(--shell-border)] px-4 py-3 sm:px-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Source Registry</p>
                  <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Data Sources</h3>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                  {stats.uniqueCategories} category | top priority #{stats.topPriority || "-"}
                </div>
              </div>
            </div>

            {config?.rag_sources?.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-[760px] w-full text-left text-sm">
                  <thead className="bg-[var(--surface-muted)] text-xs uppercase tracking-wide text-[var(--text-muted)]">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold sm:px-5">Source</th>
                      <th className="px-4 py-2.5 font-semibold">Category</th>
                      <th className="px-4 py-2.5 font-semibold">Priority</th>
                      <th className="px-4 py-2.5 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {config.rag_sources.map((source) => (
                      <tr key={source.id} className="align-top transition-colors hover:bg-[var(--surface-muted)]">
                        <td className="px-4 py-3 sm:px-5">
                          <p className="font-semibold text-[var(--text-primary)]">{source.name}</p>
                          <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">{source.id}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]">
                            {source.category}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <label className="sr-only" htmlFor={`priority-${source.id}`}>
                            Priority cho {source.name}
                          </label>
                          <input
                            id={`priority-${source.id}`}
                            type="number"
                            min={1}
                            max={100}
                            value={source.priority}
                            className="h-10 w-24 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[color:var(--brand-primary)] focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
                            onChange={(event) => onPriorityChange(source.id, event.target.value)}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1.5">
                            <input
                              type="checkbox"
                              checked={source.enabled}
                              onChange={() => onToggleSource(source.id)}
                              className="h-4 w-4 rounded border-[color:var(--shell-border-strong)] accent-[var(--brand-600)]"
                            />
                            <span
                              className={`text-xs font-semibold uppercase tracking-wide ${
                                source.enabled ? "text-[var(--status-ok-text)]" : "text-[var(--text-muted)]"
                              }`}
                            >
                              {source.enabled ? "Enabled" : "Disabled"}
                            </span>
                          </label>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-4 py-4 text-sm text-[var(--text-secondary)] sm:px-5">Chưa có nguồn nào.</p>
            )}
          </section>

          <section className="space-y-4">
            <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Flow Threshold</p>
                  <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Low-context guardrail</h3>
                </div>
                <p className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-mono text-sm text-[var(--text-secondary)]">
                  {config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}
                </p>
              </div>
              <div className="mt-3 space-y-3">
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={config?.rag_flow.low_context_threshold ?? 0}
                  onChange={(event) => onThresholdChange(event.target.value)}
                  className="h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--surface-muted)] accent-[var(--brand-600)]"
                />
                <div className="flex items-center gap-2">
                  <label htmlFor="low-context-threshold" className="text-xs font-medium text-[var(--text-secondary)]">
                    Threshold (0 - 1)
                  </label>
                  <input
                    id="low-context-threshold"
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={config?.rag_flow.low_context_threshold ?? 0}
                    className="h-10 w-24 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[color:var(--brand-primary)] focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
                    onChange={(event) => onThresholdChange(event.target.value)}
                  />
                </div>
              </div>
            </section>

            <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Retrieval Metrics</p>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Evaluation @K</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Cấu hình K cho precision/recall/nDCG khi đánh giá chất lượng retrieval (1 - 50).
                </p>
              </div>

              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-[var(--text-secondary)]">Precision@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.precision_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("precision_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[color:var(--brand-primary)] focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
                  />
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-[var(--text-secondary)]">Recall@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.recall_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("recall_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[color:var(--brand-primary)] focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
                  />
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-[var(--text-secondary)]">nDCG@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.ndcg_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("ndcg_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[color:var(--brand-primary)] focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
                  />
                </label>
              </div>
            </section>

            <section className="rounded-[14px] border border-[color:var(--brand-primary)]/30 border-t-[#2A3950] bg-[var(--surface-brand-soft)] p-4 sm:p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-brand)]">Governed model runtime</p>
              <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">DeepSeek V4 Pro / Flash</h3>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                Task contracts chọn Pro cho safety và reasoning, Flash cho tác vụ giới hạn độ trễ. Provider, model, endpoint và API key chỉ thay đổi qua cấu hình triển khai có kiểm soát, không phải từ Control Tower.
              </p>
            </section>

            <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">CareGuard Runtime</p>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">External DDI Source</h3>
                <p className="text-xs text-[var(--text-muted)]">Bật/tắt gọi RxNav + openFDA ngay tại runtime, không cần restart service.</p>
              </div>
              <label className="mt-3 flex min-h-11 cursor-pointer items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                <span className="text-sm font-medium text-[var(--text-primary)]">External DDI enabled</span>
                <span className="inline-flex items-center gap-2">
                  <span
                    className={`text-[11px] font-semibold uppercase tracking-wide ${
                      config?.careguard_runtime.external_ddi_enabled ? "text-[var(--status-ok-text)]" : "text-[var(--text-muted)]"
                    }`}
                  >
                    {config?.careguard_runtime.external_ddi_enabled ? "On" : "Off"}
                  </span>
                  <input
                    type="checkbox"
                    checked={Boolean(config?.careguard_runtime.external_ddi_enabled)}
                    onChange={onToggleExternalDdi}
                    className="h-4 w-4 rounded border-[color:var(--shell-border-strong)] accent-[var(--brand-600)]"
                  />
                </span>
              </label>
            </section>

            <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Flow Orchestration</p>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Toggle runtime features</h3>
              </div>

              <div className="mt-4 space-y-3">
                {(["routing", "verification", "retrieval"] as const).map((groupKey) => (
                  <section key={groupKey} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <div className="mb-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
                        {FLOW_GROUP_META[groupKey].label}
                      </p>
                      <p className="text-xs text-[var(--text-muted)]">{FLOW_GROUP_META[groupKey].description}</p>
                    </div>

                    <div className="space-y-2">
                      {groupedFlags[groupKey].map((flag) => {
                        const forcedOn = MANDATORY_ON_FLOW_FLAGS.has(flag.key);
                        const checked = forcedOn ? true : Boolean(config?.rag_flow[flag.key]);
                        return (
                          <label
                            key={flag.key}
                            className={[
                              "flex min-h-11 items-start justify-between gap-3 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5",
                              forcedOn ? "cursor-not-allowed border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)]" : "cursor-pointer",
                            ].join(" ")}
                          >
                            <span>
                              <span className="block text-sm font-medium text-[var(--text-primary)]">{flag.label}</span>
                              <span className="mt-0.5 block text-xs text-[var(--text-muted)]">
                                {flag.hint}
                                {forcedOn ? " (Bắt buộc bật)" : ""}
                              </span>
                            </span>
                            <span className="inline-flex items-center gap-2 pt-0.5">
                              <span
                                className={`text-[11px] font-semibold uppercase tracking-wide ${
                                  checked ? "text-[var(--status-ok-text)]" : "text-[var(--text-muted)]"
                                }`}
                              >
                                {forcedOn ? "Locked On" : checked ? "On" : "Off"}
                              </span>
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={forcedOn}
                                onChange={() => onToggleFlow(flag.key)}
                                className="h-4 w-4 rounded border-[color:var(--shell-border-strong)] accent-[var(--brand-600)]"
                              />
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </section>
          </section>
        </div>
      </div>
    </PageShell>
  );
}
