"use client";

import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  ControlTowerConfig,
  ControlTowerRagSource,
  getControlTowerConfig,
  updateControlTowerConfig
} from "@/lib/system";

type FlowFlagKey = Exclude<
  keyof ControlTowerConfig["rag_flow"],
  | "low_context_threshold"
  | "precision_at_k"
  | "recall_at_k"
  | "ndcg_at_k"
  | "llm_provider"
  | "llm_base_url"
  | "llm_model"
  | "llm_api_key"
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
    key: "deepseek_fallback_enabled",
    label: "DeepSeek Fallback",
    hint: "Fallback khi RAG confidence thấp hoặc context không đủ.",
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
    label: "Neural Reranker",
    hint: "Bật reranker neural để ưu tiên bằng chứng chất lượng cao.",
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
    description: "Kiểm chứng và cơ chế fallback"
  },
  retrieval: {
    label: "Retrieval",
    description: "Bật/tắt từng nguồn truy xuất"
  }
};

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
    rag_graphrag_enabled: flow?.rag_graphrag_enabled ?? false,
    verification_enabled: flow?.verification_enabled ?? ruleVerificationEnabled,
    deepseek_fallback_enabled: flow?.deepseek_fallback_enabled ?? true,
    low_context_threshold: clamp(Number(flow?.low_context_threshold ?? 0.2), 0, 1),
    precision_at_k: clamp(precisionAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    recall_at_k: clamp(recallAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    ndcg_at_k: clamp(ndcgAtK, RETRIEVAL_METRIC_K_MIN, RETRIEVAL_METRIC_K_MAX),
    scientific_retrieval_enabled: flow?.scientific_retrieval_enabled ?? true,
    web_retrieval_enabled: flow?.web_retrieval_enabled ?? true,
    file_retrieval_enabled: flow?.file_retrieval_enabled ?? true,
    llm_provider:
      flow?.llm_provider === "hitechcloud_gpt53_codex_high"
        ? "hitechcloud_gpt53_codex_high"
        : "deepseek",
    llm_base_url:
      typeof flow?.llm_base_url === "string" && flow.llm_base_url.trim()
        ? flow.llm_base_url.trim()
        : "https://platform.hitechcloud.one/v1",
    llm_model:
      typeof flow?.llm_model === "string" && flow.llm_model.trim()
        ? flow.llm_model.trim()
        : "gpt-5.3-codex-high",
    llm_api_key: typeof flow?.llm_api_key === "string" ? flow.llm_api_key.trim() : ""
  };
}

export default function ControlTowerPage() {
  const [config, setConfig] = useState<ControlTowerConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await getControlTowerConfig();
        setConfig({
          rag_sources: sortSources(response.rag_sources ?? []),
          rag_flow: normalizeFlow(response.rag_flow),
          careguard_runtime: {
            external_ddi_enabled: Boolean(response.careguard_runtime?.external_ddi_enabled)
          }
        });
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải cấu hình control tower.");
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, []);

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

  const onLlmProviderChange = (provider: "deepseek" | "hitechcloud_gpt53_codex_high") => {
    setConfig((prev) => {
      if (!prev) return prev;
      const next = { ...prev.rag_flow, llm_provider: provider };
      if (provider === "hitechcloud_gpt53_codex_high") {
        if (!next.llm_base_url) next.llm_base_url = "https://platform.hitechcloud.one/v1";
        if (!next.llm_model) next.llm_model = "gpt-5.3-codex-high";
      }
      return {
        ...prev,
        rag_flow: next,
      };
    });
  };

  const onLlmBaseUrlChange = (value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_base_url: value.trim(),
        },
      };
    });
  };

  const onLlmModelChange = (value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_model: value.trim(),
        },
      };
    });
  };

  const onLlmApiKeyChange = (value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_api_key: value.trim(),
        },
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
      setError(cause instanceof Error ? cause.message : "Không thể lưu cấu hình.");
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
          <div className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-slate-100" />
          <div className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-slate-100" />
          <div className="h-56 animate-pulse rounded-2xl border border-slate-200 bg-slate-100 lg:col-span-2" />
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
        <section className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950 p-4 text-slate-100 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-200/80">Mission Control</p>
              <h2 className="text-lg font-semibold sm:text-xl">RAG Source & Flow Orchestration Plane</h2>
              <p className="max-w-2xl text-sm text-slate-300">
                Chỉnh trực tiếp nguồn tri thức, độ ưu tiên, và các cờ route/verification/fallback trước khi phát hành.
              </p>
            </div>
            <button
              type="button"
              disabled={isSaving || !config}
              onClick={onSave}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-cyan-300/40 bg-cyan-400/90 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSaving ? "Đang lưu..." : "Lưu cấu hình"}
            </button>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-white/15 bg-white/10 px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-slate-300">Sources</p>
              <p className="mt-1 text-xl font-semibold text-white">{stats.total}</p>
            </div>
            <div className="rounded-xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-emerald-200">Enabled</p>
              <p className="mt-1 text-xl font-semibold text-emerald-100">{stats.enabled}</p>
            </div>
            <div className="rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-amber-200">Disabled</p>
              <p className="mt-1 text-xl font-semibold text-amber-100">{stats.disabled}</p>
            </div>
            <div className="rounded-xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-cyan-200">Active Flow</p>
              <p className="mt-1 text-xl font-semibold text-cyan-100">
                {stats.activeFlows}/{FLOW_FLAGS.length}
              </p>
            </div>
          </div>
        </section>

        {error ? (
          <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        ) : null}
        {message ? (
          <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3 sm:px-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Source Registry</p>
                  <h3 className="mt-1 text-sm font-semibold text-slate-900">Data Sources</h3>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                  {stats.uniqueCategories} category | top priority #{stats.topPriority || "-"}
                </div>
              </div>
            </div>

            {config?.rag_sources?.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-[760px] w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold sm:px-5">Source</th>
                      <th className="px-4 py-2.5 font-semibold">Category</th>
                      <th className="px-4 py-2.5 font-semibold">Priority</th>
                      <th className="px-4 py-2.5 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {config.rag_sources.map((source) => (
                      <tr key={source.id} className="align-top hover:bg-slate-50/80">
                        <td className="px-4 py-3 sm:px-5">
                          <p className="font-semibold text-slate-900">{source.name}</p>
                          <p className="mt-1 font-mono text-xs text-slate-500">{source.id}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex rounded-md border border-slate-200 bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
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
                            className="h-10 w-24 rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                            onChange={(event) => onPriorityChange(source.id, event.target.value)}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5">
                            <input
                              type="checkbox"
                              checked={source.enabled}
                              onChange={() => onToggleSource(source.id)}
                              className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                            />
                            <span
                              className={`text-xs font-semibold uppercase tracking-wide ${
                                source.enabled ? "text-emerald-700" : "text-slate-500"
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
              <p className="px-4 py-4 text-sm text-slate-600 sm:px-5">Chưa có nguồn nào.</p>
            )}
          </section>

          <section className="space-y-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Flow Threshold</p>
                  <h3 className="mt-1 text-sm font-semibold text-slate-900">Low-context guardrail</h3>
                </div>
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-sm text-slate-700">
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
                  className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-cyan-600"
                />
                <div className="flex items-center gap-2">
                  <label htmlFor="low-context-threshold" className="text-xs font-medium text-slate-600">
                    Threshold (0 - 1)
                  </label>
                  <input
                    id="low-context-threshold"
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={config?.rag_flow.low_context_threshold ?? 0}
                    className="h-10 w-24 rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                    onChange={(event) => onThresholdChange(event.target.value)}
                  />
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Retrieval Metrics</p>
                <h3 className="text-sm font-semibold text-slate-900">Evaluation @K</h3>
                <p className="text-xs text-slate-500">
                  Cấu hình K cho precision/recall/nDCG khi đánh giá chất lượng retrieval (1 - 50).
                </p>
              </div>

              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-slate-600">Precision@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.precision_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("precision_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-slate-600">Recall@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.recall_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("recall_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-slate-600">nDCG@K</span>
                  <input
                    type="number"
                    min={RETRIEVAL_METRIC_K_MIN}
                    max={RETRIEVAL_METRIC_K_MAX}
                    step={1}
                    value={config?.rag_flow.ndcg_at_k ?? DEFAULT_RETRIEVAL_METRIC_K}
                    onChange={(event) => onRetrievalMetricChange("ndcg_at_k", event.target.value)}
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">LLM Runtime</p>
                <h3 className="text-sm font-semibold text-slate-900">Provider & model switching</h3>
                <p className="text-xs text-slate-500">
                  Cấu hình provider chính cho chat/research ngay trong control tower.
                </p>
              </div>

              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className="space-y-1.5 sm:col-span-2">
                  <span className="text-xs font-medium text-slate-600">Provider</span>
                  <select
                    value={config?.rag_flow.llm_provider ?? "hitechcloud_gpt53_codex_high"}
                    onChange={(event) =>
                      onLlmProviderChange(
                        event.target.value === "hitechcloud_gpt53_codex_high"
                          ? "hitechcloud_gpt53_codex_high"
                          : "deepseek"
                      )
                    }
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  >
                    <option value="hitechcloud_gpt53_codex_high">hitechcloud + gpt-5.3-codex-high</option>
                    <option value="deepseek">deepseek (installed)</option>
                  </select>
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-slate-600">Model</span>
                  <input
                    type="text"
                    value={config?.rag_flow.llm_model ?? ""}
                    onChange={(event) => onLlmModelChange(event.target.value)}
                    placeholder={
                      config?.rag_flow.llm_provider === "deepseek" ? "deepseek-v3.2" : "gpt-5.3-codex-high"
                    }
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>

                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-slate-600">Base URL</span>
                  <input
                    type="url"
                    value={config?.rag_flow.llm_base_url ?? ""}
                    onChange={(event) => onLlmBaseUrlChange(event.target.value)}
                    placeholder={
                      config?.rag_flow.llm_provider === "deepseek"
                        ? "https://api.yescale.vip/v1"
                        : "https://platform.hitechcloud.one/v1"
                    }
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>

                <label className="space-y-1.5 sm:col-span-2">
                  <span className="text-xs font-medium text-slate-600">API Key</span>
                  <input
                    type="password"
                    value={config?.rag_flow.llm_api_key ?? ""}
                    onChange={(event) => onLlmApiKeyChange(event.target.value)}
                    placeholder="sk-..."
                    className="h-10 w-full rounded-lg border border-slate-300 px-2.5 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                  />
                </label>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">CareGuard Runtime</p>
                <h3 className="text-sm font-semibold text-slate-900">External DDI Source</h3>
                <p className="text-xs text-slate-500">Bật/tắt gọi RxNav + openFDA ngay tại runtime, không cần restart service.</p>
              </div>
              <label className="mt-3 flex min-h-11 cursor-pointer items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <span className="text-sm font-medium text-slate-900">External DDI enabled</span>
                <span className="inline-flex items-center gap-2">
                  <span
                    className={`text-[11px] font-semibold uppercase tracking-wide ${
                      config?.careguard_runtime.external_ddi_enabled ? "text-emerald-700" : "text-slate-500"
                    }`}
                  >
                    {config?.careguard_runtime.external_ddi_enabled ? "On" : "Off"}
                  </span>
                  <input
                    type="checkbox"
                    checked={Boolean(config?.careguard_runtime.external_ddi_enabled)}
                    onChange={onToggleExternalDdi}
                    className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                  />
                </span>
              </label>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Flow Orchestration</p>
                <h3 className="text-sm font-semibold text-slate-900">Toggle runtime features</h3>
              </div>

              <div className="mt-4 space-y-3">
                {(["routing", "verification", "retrieval"] as const).map((groupKey) => (
                  <section key={groupKey} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {FLOW_GROUP_META[groupKey].label}
                      </p>
                      <p className="text-xs text-slate-500">{FLOW_GROUP_META[groupKey].description}</p>
                    </div>

                    <div className="space-y-2">
                      {groupedFlags[groupKey].map((flag) => {
                        const checked = Boolean(config?.rag_flow[flag.key]);
                        return (
                          <label
                            key={flag.key}
                            className="flex min-h-11 cursor-pointer items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5"
                          >
                            <span>
                              <span className="block text-sm font-medium text-slate-900">{flag.label}</span>
                              <span className="mt-0.5 block text-xs text-slate-500">{flag.hint}</span>
                            </span>
                            <span className="inline-flex items-center gap-2 pt-0.5">
                              <span
                                className={`text-[11px] font-semibold uppercase tracking-wide ${
                                  checked ? "text-emerald-700" : "text-slate-500"
                                }`}
                              >
                                {checked ? "On" : "Off"}
                              </span>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => onToggleFlow(flag.key)}
                                className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
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
