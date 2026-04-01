"use client";

import { useEffect, useMemo, useState } from "react";
import { BarBlocks } from "@/components/admin/admin-visuals";
import AdminFlowDebugger from "@/components/admin/admin-flow-debugger";
import AdminFlowRuntimePanel from "@/components/admin/admin-flow-runtime-panel";
import AdminFlowVisualizer, {
  FLOW_NODE_INFOS,
  type FlowNodeId
} from "@/components/admin/admin-flow-visualizer";
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
    setLowContextThreshold
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
    if (enabledFlowCount >= 6) return "ổn định";
    if (enabledFlowCount >= 4) return "trung bình";
    return "cần kiểm tra";
  }, [config, enabledFlowCount]);

  const lowContextThreshold = config?.rag_flow.low_context_threshold;
  useEffect(() => {
    if (typeof lowContextThreshold !== "number") return;
    const next = Math.max(0, Math.min(1, lowContextThreshold + 0.15));
    setDebugLowContextScore(next);
  }, [lowContextThreshold]);

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
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
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Flags</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {enabledFlowCount}/{flowToggleKeys.length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Health</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{flowHealthLabel}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">low_context_threshold</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Fallback</p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {config?.rag_flow.deepseek_fallback_enabled ? "enabled" : "disabled"}
            </p>
          </div>
        </div>

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

              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
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

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
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
