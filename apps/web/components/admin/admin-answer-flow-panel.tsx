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
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const DEFAULT_SELECTED_NODE: FlowNodeId = "role_router";
const NODE_IDS = Object.keys(FLOW_NODE_INFOS) as FlowNodeId[];

export function AdminAnswerFlowPanel() {
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

  // Emit a single named product event when the Answer Flow surface is opened
  // (Req 9.1). No PII — only the coarse Admin view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "answer_flow" });
  }, []);

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
  return (
    <div className="space-y-4">
      <section className="relative overflow-hidden rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              Flow {enabledFlowCount}/{flowToggleKeys.length}
            </span>
            <span className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              Health {flowHealthLabel}
            </span>
            <span className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              Low Context {config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}
            </span>
            <span className="rounded-lg border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-1 font-medium text-[var(--text-brand)]">
              Generation fail-closed
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void reload()}
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:border-[color:var(--brand-primary)]"
            >
              Reload
            </button>
            <button
              type="button"
              disabled={!isDirty || isSaving || isLoading || !config}
              onClick={() => void save()}
              className="rounded-lg bg-[var(--brand-600)] px-3 py-1.5 text-xs font-medium text-[#cdd7ff] transition hover:bg-[var(--brand-700)] disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save Flow"}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Flow Flags</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
              {enabledFlowCount}/{flowToggleKeys.length}
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Flow Health</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{flowHealthLabel}</p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">low_context_threshold</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}</p>
          </div>
          <div className="rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-brand)]">Generation policy</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
              Fail closed
            </p>
          </div>
        </div>

        <section className="mt-3 rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">Governed model runtime</p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            DeepSeek V4 được chọn theo task contract: Pro cho safety/reasoning, Flash cho tác vụ giới hạn độ trễ. Provider, endpoint, model và API key chỉ cấu hình qua môi trường triển khai; Control Tower không thể thay đổi chúng.
          </p>
        </section>

        {error ? (
          <p className="mt-3 rounded-lg border border-[color:var(--danger-border)] bg-[var(--surface-danger-soft)] px-3 py-2 text-sm text-[var(--text-danger)]">
            {error}
          </p>
        ) : null}
        {message ? (
          <p className="mt-3 rounded-lg border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-2 text-sm text-[var(--text-brand)]">
            {message}
          </p>
        ) : null}

        {isLoading ? (
          <div className="mt-4 h-48 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
        ) : (
          <>
            <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_0.45fr]">
              <AdminFlowVisualizer
                ragFlow={config?.rag_flow}
                onToggle={(key) => setFlowToggle(key, !Boolean(config?.rag_flow[key]))}
                onSelectNode={setSelectedNode}
                selectedNodeId={selectedNode}
              />

              <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Node Inspector</p>
                <h4 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{selectedNodeInfo.title}</h4>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{selectedNodeInfo.subtitle}</p>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{selectedNodeInfo.description}</p>

                <div className="mt-3 rounded-xl border border-[color:var(--status-warning-border)] bg-[var(--surface-warning-soft)] px-3 py-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-warning)]">Risk Note</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--text-warning)]">{selectedNodeInfo.riskNote}</p>
                </div>

                {selectedToggleKey ? (
                  <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">Flow Toggle</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <p className="text-xs text-[var(--text-secondary)]">Bật/tắt node này trực tiếp từ inspector.</p>
                      <button
                        type="button"
                        onClick={() => setFlowToggle(selectedToggleKey, !Boolean(selectedToggleEnabled))}
                        className={[
                          "rounded-full px-3 py-1 text-xs font-semibold transition",
                          selectedToggleEnabled
                            ? "border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                            : "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-high)]"
                        ].join(" ")}
                      >
                        {selectedToggleEnabled ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>
                ) : null}

                {selectedNode === "verification" ? (
                  <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">Threshold Tuning</p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      Điều chỉnh ngưỡng để xác định khi nào cần chặn phát hành do thiếu ngữ cảnh.
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
                        className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
                      />
                    </div>
                  </div>
                ) : null}
              </section>
            </div>

            <section className="mt-4 rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Research Debug Preview</p>
              <h4 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Debugger luồng trả lời theo thời gian thực</h4>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                Mô phỏng các nhánh route/retrieve/verify/policy và xem điều kiện nào chặn phát hành trước khi publish.
              </p>
              <div className="mt-3 grid gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-[var(--text-secondary)]">
                    Low-context score giả lập cho phiên debug
                  </p>
                  <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-xs font-semibold text-[var(--text-primary)]">
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

      <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Council Flow</p>
        <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Sơ đồ hội chẩn ở phần quản trị</h3>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Flow canvas được chuyển vào Admin. Trạng thái `needs_more_info` dùng debug score hiện tại để mô phỏng nhanh.
        </p>
        <div className="mt-3">
          <CouncilFlowCanvas
            isEmergency={false}
            needsMoreInfo={councilNeedsMoreInfo}
            hasCitations={councilHasCitations}
          />
        </div>
      </section>

      <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Flow Signal Blocks</h3>
          <span className="text-xs text-[var(--text-muted)]">{flowToggleKeys.length} flags + threshold</span>
        </div>
        <div className="mt-3">
          {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-[var(--surface-muted)]" /> : <BarBlocks values={flowVisual} />}
        </div>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Khối cuối là `low_context_threshold`; các khối trước là trạng thái flow flags hiện tại.
        </p>
      </section>
    </div>
  );
}

export default AdminAnswerFlowPanel;
