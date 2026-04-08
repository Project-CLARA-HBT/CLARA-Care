"use client";

import { useEffect, useMemo, useState } from "react";
import { BarBlocks } from "@/components/admin/admin-visuals";
import AdminFlowDebugger from "@/components/admin/admin-flow-debugger";
import AdminFlowRuntimePanel from "@/components/admin/admin-flow-runtime-panel";
import AdminFlowVisualizer, {
  FLOW_NODE_INFOS,
  type FlowNodeId
} from "@/components/admin/admin-flow-visualizer";
import AdminNeuralNetworkVisualizer from "@/components/admin/admin-neural-network-visualizer";
import CouncilFlowCanvas from "@/components/council/council-flow-canvas";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const DEFAULT_SELECTED_NODE: FlowNodeId = "role_router";
const NODE_IDS = Object.keys(FLOW_NODE_INFOS) as FlowNodeId[];

export default function AdminAnswerFlowPanel() {
  const [selectedNode, setSelectedNode] = useState<FlowNodeId>(DEFAULT_SELECTED_NODE);
  const [debugLowContextScore, setDebugLowContextScore] = useState(0.3);

  const {
    config,
    error,
    message,
    isDirty,
    isLoading,
    isSaving,
    reload,
    save,
    flowToggleKeys,
    setFlowToggle,
    setLowContextThreshold,
    setLlmProvider,
    setLlmBaseUrl,
    setLlmModel,
    setLlmApiKey
  } = useControlTowerConfig();

  useEffect(() => {
    if (!NODE_IDS.includes(selectedNode)) {
      setSelectedNode(DEFAULT_SELECTED_NODE);
    }
  }, [selectedNode]);

  const selectedNodeInfo = FLOW_NODE_INFOS[selectedNode];
  const selectedToggleKey = selectedNodeInfo.toggleKey;
  const selectedToggleEnabled =
    selectedToggleKey && config ? Boolean(config.rag_flow[selectedToggleKey]) : null;

  const flowVisual = config
    ? [...flowToggleKeys.map((key) => (config.rag_flow[key] ? 100 : 24)), config.rag_flow.low_context_threshold * 100]
    : [];
  const enabledFlowCount = config ? flowToggleKeys.filter((key) => config.rag_flow[key]).length : 0;

  const flowHealthLabel = useMemo(() => {
    if (!config) return "n/a";
    if (enabledFlowCount >= 8) return "ổn định";
    if (enabledFlowCount >= 5) return "trung bình";
    return "cần kiểm tra";
  }, [config, enabledFlowCount]);

  const lowContextThreshold = config?.rag_flow.low_context_threshold;
  useEffect(() => {
    if (typeof lowContextThreshold !== "number") return;
    const next = Math.max(0, Math.min(1, lowContextThreshold + 0.15));
    setDebugLowContextScore(next);
  }, [lowContextThreshold]);

  const councilNeedsMoreInfo =
    typeof lowContextThreshold === "number" ? debugLowContextScore >= lowContextThreshold : false;
  const verificationGateEnabled = Boolean(
    config?.rag_flow.rule_verification_enabled ?? config?.rag_flow.verification_enabled
  );
  const councilHasCitations =
    verificationGateEnabled &&
    Boolean(config?.rag_flow.nli_model_enabled) &&
    Boolean(config?.rag_flow.rag_nli_enabled) &&
    Boolean(
      config?.rag_flow.scientific_retrieval_enabled ||
      config?.rag_flow.web_retrieval_enabled ||
      config?.rag_flow.file_retrieval_enabled
    );
  const councilConfidenceScore = Number(Math.max(0.12, Math.min(0.98, 1 - debugLowContextScore * 0.7)).toFixed(2));
  const llmProvider = config?.rag_flow.llm_provider ?? "hitechcloud_gpt53_codex_high";
  const llmBaseUrl = config?.rag_flow.llm_base_url ?? "https://platform.hitechcloud.one/v1";
  const llmModel = config?.rag_flow.llm_model ?? "gpt-5.3-codex-high";
  const llmApiKey = config?.rag_flow.llm_api_key ?? "";

  const applyHitechcloudPreset = () => {
    setLlmProvider("hitechcloud_gpt53_codex_high");
    setLlmBaseUrl("https://platform.hitechcloud.one/v1");
    setLlmModel("gpt-5.3-codex-high");
  };

  const applyDeepseekPreset = () => {
    setLlmProvider("deepseek");
    if (!llmBaseUrl) setLlmBaseUrl("");
    if (!llmModel) setLlmModel("");
  };

  return (
    <div className="space-y-4">
      <section className="relative overflow-hidden rounded-[30px] border border-cyan-200/60 bg-[radial-gradient(circle_at_10%_8%,rgba(34,211,238,0.2),transparent_34%),radial-gradient(circle_at_90%_92%,rgba(59,130,246,0.14),transparent_38%),linear-gradient(162deg,rgba(255,255,255,0.95),rgba(236,254,255,0.9))] p-4 shadow-[0_24px_72px_rgba(14,116,144,0.18)] dark:border-cyan-600/35 dark:bg-[radial-gradient(circle_at_10%_8%,rgba(34,211,238,0.14),transparent_34%),radial-gradient(circle_at_90%_92%,rgba(59,130,246,0.12),transparent_38%),linear-gradient(162deg,rgba(2,6,23,0.94),rgba(15,23,42,0.9))] dark:shadow-[0_30px_84px_rgba(2,6,23,0.82)]">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(14,165,233,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(14,165,233,0.08)_1px,transparent_1px)] bg-[size:24px_24px] dark:bg-[linear-gradient(to_right,rgba(14,165,233,0.16)_1px,transparent_1px),linear-gradient(to_bottom,rgba(14,165,233,0.16)_1px,transparent_1px)]" />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Answer Flow Block</p>
            <h3 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">CLARA Research Flow Visualizer</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
              Bản đồ runtime cho pipeline research thật: session guard, legal hard guard, planner, deep/deep_beta, retrieval, verification và responder.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void reload()}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            >
              Reload
            </button>
            <button
              type="button"
              disabled={!isDirty || isSaving || isLoading || !config}
              onClick={() => void save()}
              className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-500 disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save Flow"}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-4">
          <div className="rounded-xl border border-cyan-200/70 bg-white/70 px-3 py-2 backdrop-blur dark:border-cyan-700/40 dark:bg-slate-900/70">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Flags</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {enabledFlowCount}/{flowToggleKeys.length}
            </p>
          </div>
          <div className="rounded-xl border border-cyan-200/70 bg-white/70 px-3 py-2 backdrop-blur dark:border-cyan-700/40 dark:bg-slate-900/70">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Health</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{flowHealthLabel}</p>
          </div>
          <div className="rounded-xl border border-cyan-200/70 bg-white/70 px-3 py-2 backdrop-blur dark:border-cyan-700/40 dark:bg-slate-900/70">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">low_context_threshold</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}</p>
          </div>
          <div className="rounded-xl border border-cyan-200/70 bg-white/70 px-3 py-2 backdrop-blur dark:border-cyan-700/40 dark:bg-slate-900/70">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Fallback</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {config?.rag_flow.deepseek_fallback_enabled ? "enabled" : "disabled"}
            </p>
          </div>
        </div>

        <section className="mt-3 rounded-2xl border border-slate-200 bg-white/85 p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">LLM Runtime</p>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                Chọn nhanh provider cho toàn bộ chat/research runtime từ Control Tower.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={applyHitechcloudPreset}
                className="rounded-lg border border-cyan-300 bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700 hover:bg-cyan-100 dark:border-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300"
              >
                Preset HitechCloud GPT-5.3
              </button>
              <button
                type="button"
                onClick={applyDeepseekPreset}
                className="rounded-lg border border-violet-300 bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700 hover:bg-violet-100 dark:border-violet-700 dark:bg-violet-900/40 dark:text-violet-300"
              >
                Preset DeepSeek Installed
              </button>
            </div>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
              Provider
              <select
                value={llmProvider}
                onChange={(event) =>
                  setLlmProvider(
                    event.target.value === "hitechcloud_gpt53_codex_high"
                      ? "hitechcloud_gpt53_codex_high"
                      : "deepseek"
                  )
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="hitechcloud_gpt53_codex_high">hitechcloud + gpt-5.3-codex-high</option>
                <option value="deepseek">deepseek (installed)</option>
              </select>
            </label>

            <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
              Model
              <input
                type="text"
                value={llmModel}
                onChange={(event) => setLlmModel(event.target.value)}
                placeholder={llmProvider === "deepseek" ? "deepseek-v3.2" : "gpt-5.3-codex-high"}
                className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>

            <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
              Base URL
              <input
                type="url"
                value={llmBaseUrl}
                onChange={(event) => setLlmBaseUrl(event.target.value)}
                placeholder={
                  llmProvider === "deepseek"
                    ? "https://api.deepseek.com"
                    : "https://platform.hitechcloud.one/v1"
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>

            <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
              API Key
              <input
                type="password"
                value={llmApiKey}
                onChange={(event) => setLlmApiKey(event.target.value)}
                placeholder="sk-..."
                className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
          </div>
        </section>

        {error ? (
          <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300">
            {error}
          </p>
        ) : null}
        {message ? (
          <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
            {message}
          </p>
        ) : null}

        {isLoading ? (
          <div className="mt-4 h-48 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
        ) : (
          <>
            <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_0.45fr]">
              <AdminFlowVisualizer
                ragFlow={config?.rag_flow}
                onToggle={(key) => setFlowToggle(key, !Boolean(config?.rag_flow[key]))}
                onSelectNode={setSelectedNode}
                selectedNodeId={selectedNode}
              />

              <section className="rounded-2xl border border-cyan-200/60 bg-white/78 p-4 shadow-[0_16px_42px_rgba(14,116,144,0.14)] backdrop-blur dark:border-cyan-700/35 dark:bg-slate-900/80 dark:shadow-[0_20px_48px_rgba(2,6,23,0.74)]">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Node Inspector</p>
                <h4 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">{selectedNodeInfo.title}</h4>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{selectedNodeInfo.subtitle}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedNodeInfo.description}</p>

                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-900 dark:bg-amber-950/50">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">Risk Note</p>
                  <p className="mt-1 text-xs leading-5 text-amber-800 dark:text-amber-200">{selectedNodeInfo.riskNote}</p>
                </div>

                {selectedToggleKey ? (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                    <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">Flow Toggle</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <p className="text-xs text-slate-600 dark:text-slate-300">Bật/tắt node này trực tiếp từ inspector.</p>
                      <button
                        type="button"
                        onClick={() => setFlowToggle(selectedToggleKey, !Boolean(selectedToggleEnabled))}
                        className={[
                          "rounded-full px-3 py-1 text-xs font-semibold transition",
                          selectedToggleEnabled
                            ? "border border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                            : "border border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600"
                        ].join(" ")}
                      >
                        {selectedToggleEnabled ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>
                ) : null}

                {selectedNode === "deepseek_fallback" || selectedNode === "verification" ? (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                    <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">Threshold Tuning</p>
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      Điều chỉnh ngưỡng để quyết định khi nào kích hoạt fallback low-context.
                    </p>
                    <div className="mt-3 grid gap-2">
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={config?.rag_flow.low_context_threshold ?? 0}
                        onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
                      />
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        value={config?.rag_flow.low_context_threshold ?? 0}
                        onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                      />
                    </div>
                  </div>
                ) : null}
              </section>
            </div>

            <section className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Research Debug Preview</p>
              <h4 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">Debugger luồng trả lời theo thời gian thực</h4>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                Mô phỏng các nhánh route/retrieve/verify/policy và xem khi nào nhánh fallback được kích hoạt trước khi publish.
              </p>
              <div className="mt-3 grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    Low-context score giả lập cho phiên debug
                  </p>
                  <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200">
                    {debugLowContextScore.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={debugLowContextScore}
                  onChange={(event) => setDebugLowContextScore(toNumber(event.target.value))}
                />
              </div>
              <div className="mt-3">
                <AdminFlowDebugger
                  ragFlow={config?.rag_flow}
                  lowContextThreshold={debugLowContextScore}
                />
              </div>
            </section>
          </>
        )}
      </section>

      <AdminFlowRuntimePanel />

      <AdminNeuralNetworkVisualizer ragFlow={config?.rag_flow} />

      <section className="rounded-2xl border border-cyan-200/60 bg-white/78 p-4 shadow-[0_16px_42px_rgba(14,116,144,0.14)] backdrop-blur dark:border-cyan-700/35 dark:bg-slate-900/80 dark:shadow-[0_20px_48px_rgba(2,6,23,0.74)]">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Council Flow</p>
        <h3 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">Sơ đồ hội chẩn ở phần quản trị</h3>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
          Flow canvas được chuyển vào Admin. Trạng thái `needs_more_info` dùng debug score hiện tại để mô phỏng nhanh.
        </p>
        <div className="mt-3">
          <CouncilFlowCanvas
            isEmergency={false}
            needsMoreInfo={councilNeedsMoreInfo}
            hasCitations={councilHasCitations}
            confidenceScore={councilConfidenceScore}
          />
        </div>
      </section>

      <section className="rounded-2xl border border-cyan-200/60 bg-white/78 p-4 shadow-[0_16px_42px_rgba(14,116,144,0.14)] backdrop-blur dark:border-cyan-700/35 dark:bg-slate-900/80 dark:shadow-[0_20px_48px_rgba(2,6,23,0.74)]">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Flow Signal Blocks</h3>
          <span className="text-xs text-slate-500 dark:text-slate-400">{flowToggleKeys.length} flags + threshold</span>
        </div>
        <div className="mt-3">
          {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" /> : <BarBlocks values={flowVisual} />}
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          Khối cuối là `low_context_threshold`; các khối trước là trạng thái flow flags hiện tại.
        </p>
      </section>
    </div>
  );
}
