"use client";

import { useEffect, useMemo, useState } from "react";
import Icon from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import { BarBlocks } from "@/components/admin/admin-visuals";
import AdminFlowDebugger from "@/components/admin/admin-flow-debugger";
import AdminFlowRuntimePanel from "@/components/admin/admin-flow-runtime-panel";
import AdminFlowVisualizer, {
  FLOW_NODE_INFOS,
  type FlowNodeId,
} from "@/components/admin/admin-flow-visualizer";
import AdminNeuralNetworkVisualizer from "@/components/admin/admin-neural-network-visualizer";
import CouncilFlowCanvas from "@/components/council/council-flow-canvas";
import useControlTowerConfig, {
  type FlowToggleKey,
} from "@/components/admin/use-control-tower-config";
import { FLOW_FLAG_META } from "@/components/admin/admin-config-meta";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { useUILanguage } from "@/lib/use-ui-language";

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const DEFAULT_SELECTED_NODE: FlowNodeId = "role_router";
const NODE_IDS = Object.keys(FLOW_NODE_INFOS) as FlowNodeId[];

const FLOW_GROUPS: Array<{
  id: string;
  title: string;
  titleEn: string;
  description: string;
  descriptionEn: string;
  keys: FlowToggleKey[];
}> = [
  {
    id: "routing",
    title: "Phân tầng & Điều hướng (Routing)",
    titleEn: "Routing & Role Decomposition",
    description: "Xác định vai trò người dùng và phân loại loại câu hỏi (clinical, policy, triage) trước khi tìm kiếm dữ liệu.",
    descriptionEn: "Identifies user roles and classifies question intent before retrieval dispatch.",
    keys: ["role_router_enabled", "intent_router_enabled"],
  },
  {
    id: "retrieval",
    title: "Truy xuất Bằng chứng (Multi-source Retrieval)",
    titleEn: "Multi-Source Evidence Retrieval",
    description: "Khai thác đồng thời từ kho y văn PubMed, Web uy tín, tài liệu người dùng đính kèm và xếp hạng bằng chứng qua GraphRAG + Reranker.",
    descriptionEn: "Fetches from PubMed, authoritative web, uploaded files, and reranks via GraphRAG + Cross-Encoder.",
    keys: [
      "scientific_retrieval_enabled",
      "web_retrieval_enabled",
      "file_retrieval_enabled",
      "rag_reranker_enabled",
      "rag_graphrag_enabled",
    ],
  },
  {
    id: "verification",
    title: "Kiểm chứng Bằng chứng & Cổng An toàn (Verification & FIDES Guard)",
    titleEn: "Evidence Verification & FIDES Guard",
    description: "Chấm quan hệ claim-evidence qua mô hình NLI và thực thi kiểm chứng an toàn nghiêm ngặt trước khi trả lời.",
    descriptionEn: "Assesses claim-evidence entailment via NLI model and executes strict safety verification before synthesis.",
    keys: ["rule_verification_enabled", "nli_model_enabled", "rag_nli_enabled"],
  },
];

const KEY_NODES_FOR_QUICK_JUMP: FlowNodeId[] = [
  "role_router",
  "intent_router",
  "vn_drug_dictionary",
  "planner",
  "retrieval_orchestrator",
  "retrieval_scientific",
  "retrieval_web",
  "retrieval_file",
  "evidence_index",
  "contradiction_miner",
  "synthesis",
  "verification",
  "policy_gate",
  "responder",
];

export function AdminAnswerFlowPanel() {
  const language = useUILanguage();
  const isVi = language !== "en";

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

  const selectedNodeInfo = FLOW_NODE_INFOS[selectedNode] ?? FLOW_NODE_INFOS[DEFAULT_SELECTED_NODE];
  const selectedToggleKey = selectedNodeInfo.toggleKey;
  const selectedToggleEnabled =
    selectedToggleKey && config ? Boolean(config.rag_flow[selectedToggleKey]) : null;

  const flowVisual = config
    ? [
        ...flowToggleKeys.map((key) => (config.rag_flow[key] ? 100 : 24)),
        config.rag_flow.low_context_threshold * 100,
      ]
    : [];
  const enabledFlowCount = config ? flowToggleKeys.filter((key) => config.rag_flow[key]).length : 0;

  const flowHealthLabel = useMemo(() => {
    if (!config) return "n/a";
    if (enabledFlowCount >= 8) return isVi ? "ổn định" : "healthy";
    if (enabledFlowCount >= 5) return isVi ? "trung bình" : "moderate";
    return isVi ? "cần kiểm tra" : "degraded";
  }, [config, enabledFlowCount, isVi]);

  const flowHealthTone: StatusTone = useMemo(() => {
    if (!config) return "unknown";
    if (enabledFlowCount >= 8) return "success";
    if (enabledFlowCount >= 5) return "warning";
    return "danger";
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
    <div className="space-y-6">
      {/* 1. Header & Operational Control Bar */}
      <section
        aria-label="Answer Flow Header"
        className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <Icon name="scan" size={16} aria-hidden="true" />
              </span>
              <h1 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                {isVi ? "Luồng Suy luận & Điều phối Trả lời" : "Answer Flow & Inference Orchestration"}
              </h1>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Điều khiển 10 flow flags, tinh chỉnh ngưỡng low_context_threshold và giám sát topology suy luận nhiều tầng."
                : "Configure 10 flow flags, tune low_context_threshold, and monitor multi-tier inference topology."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void reload()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-primary)] hover:bg-[var(--surface-panel)]"
            >
              <Icon name="refresh" size={14} className="text-[var(--text-muted)]" />
              <span>{isVi ? "Tải lại" : "Reload"}</span>
            </button>
            <button
              type="button"
              disabled={!isDirty || isSaving || isLoading || !config}
              onClick={() => void save()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3.5 py-1.5 text-xs font-semibold text-[#cdd7ff] shadow-sm transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon name="check" size={14} className="text-[#cdd7ff]" />
              <span>{isSaving ? (isVi ? "Đang lưu..." : "Saving...") : isVi ? "Lưu Cấu hình" : "Save Flow"}</span>
            </button>
          </div>
        </div>

        {/* Live Status Indicators */}
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <StatusChip
            tone={flowHealthTone}
            label={`Flow ${enabledFlowCount}/${flowToggleKeys.length}`}
            size="sm"
          />
          <StatusChip
            tone={flowHealthTone}
            label={`Health: ${flowHealthLabel}`}
            size="sm"
          />
          <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
            low_context_threshold: {config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}
          </span>
          <span className="inline-flex items-center rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-brand)]">
            {isVi ? "Generation fail-closed" : "Generation fail-closed"}
          </span>
          {isDirty ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-2.5 py-0.5 text-xs font-semibold text-[var(--status-warn-text)] animate-pulse">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--status-warn-text)]" />
              {isVi ? "Chưa lưu thay đổi" : "Unsaved changes"}
            </span>
          ) : null}
        </div>

        {/* Dense Status Grid */}
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
            <p className="text-[10px] uppercase font-semibold tracking-wider text-[var(--text-muted)]">
              {isVi ? "Cờ luồng kích hoạt" : "Flow Flags Active"}
            </p>
            <p className="mt-1 text-xl font-bold text-[var(--text-primary)]">
              {enabledFlowCount}/{flowToggleKeys.length}
            </p>
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
              {enabledFlowCount === flowToggleKeys.length
                ? (isVi ? "Toàn bộ cờ đang bật" : "All flow flags enabled")
                : `${flowToggleKeys.length - enabledFlowCount} ${isVi ? "cờ bị tắt" : "flags disabled"}`}
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
            <p className="text-[10px] uppercase font-semibold tracking-wider text-[var(--text-muted)]">
              {isVi ? "Độ tin cậy luồng" : "Flow Health"}
            </p>
            <p className="mt-1 text-xl font-bold text-[var(--text-primary)] capitalize">
              {flowHealthLabel}
            </p>
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
              {enabledFlowCount >= 8
                ? (isVi ? "Hệ thống vận hành tối ưu" : "Optimal system operation")
                : (isVi ? "Một số cổng đang đóng" : "Some gates bypass/disabled")}
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
            <p className="text-[10px] uppercase font-semibold tracking-wider text-[var(--text-muted)]">
              low_context_threshold
            </p>
            <p className="mt-1 text-xl font-bold text-[var(--text-primary)]">
              {config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}
            </p>
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
              {isVi ? "Ngưỡng kích hoạt fail-closed" : "Fail-closed trigger cutoff"}
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] p-3">
            <p className="text-[10px] uppercase font-semibold tracking-wider text-[var(--text-brand)]">
              {isVi ? "Chính sách phát hành" : "Generation Policy"}
            </p>
            <p className="mt-1 text-xl font-bold text-[var(--text-primary)]">
              Fail-closed
            </p>
            <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
              {isVi ? "Chặn câu trả lời khi thiếu căn cứ" : "Blocks answers lacking evidence"}
            </p>
          </div>
        </div>

        {/* Governed Model Runtime Note */}
        <div className="mt-3.5 rounded-xl border border-[color:var(--brand-primary)]/25 bg-[var(--surface-brand-soft)] p-3">
          <div className="flex items-start gap-2">
            <Icon name="check" size={16} className="mt-0.5 text-[var(--text-brand)] shrink-0" />
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                {isVi ? "Môi trường Suy luận Governed Model Runtime" : "Governed Model Runtime"}
              </p>
              <p className="mt-0.5 text-xs leading-5 text-[var(--text-secondary)]">
                {isVi
                  ? "DeepSeek V4 được chọn theo task contract: Pro cho safety/reasoning, Flash cho tác vụ giới hạn độ trễ. Provider, endpoint, model và API key chỉ cấu hình qua môi trường triển khai; Control Tower không thể thay đổi chúng."
                  : "DeepSeek V4 configured per task contract: Pro for safety/reasoning, Flash for latency-bounded tasks. Provider, endpoint, model, and API keys are environment-locked."}
              </p>
            </div>
          </div>
        </div>

        {/* Feedback alerts */}
        {error ? (
          <div
            role="alert"
            className="mt-3 flex items-center gap-2 rounded-lg border border-[color:var(--danger-border)] bg-[var(--surface-danger-soft)] px-3.5 py-2.5 text-xs font-medium text-[var(--text-danger)]"
          >
            <Icon name="warning" size={15} className="shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        {message ? (
          <div
            role="status"
            className="mt-3 flex items-center gap-2 rounded-lg border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3.5 py-2.5 text-xs font-medium text-[var(--text-brand)]"
          >
            <Icon name="check" size={15} className="shrink-0" />
            <span>{message}</span>
          </div>
        ) : null}
      </section>

      {/* 2. Flow Flag Controls & Low Context Threshold Slider */}
      <section
        aria-label="Flow Flags and Threshold Controls"
        className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
              {isVi ? "Bảng Điều khiển Cờ Luồng & Ngưỡng Ngữ cảnh (Flow Flags & Threshold Tuning)" : "Flow Flags & Low Context Threshold Controls"}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Bật/tắt các tầng Router, Retrieval, Reranker và Verification trực tiếp trên pipeline thời gian thực."
                : "Toggle Router, Retrieval, Reranker, and Verification stages directly on the live pipeline."}
            </p>
          </div>
          <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[11px] font-mono font-semibold text-[var(--text-secondary)]">
            {enabledFlowCount}/10 ON
          </span>
        </div>

        {/* Flag Groups Grid */}
        <div className="mt-4 grid gap-5 lg:grid-cols-3">
          {FLOW_GROUPS.map((group) => (
            <div
              key={group.id}
              className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"
            >
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi ? group.title : group.titleEn}
                </h3>
                <p className="mt-1 text-[11px] leading-4 text-[var(--text-muted)]">
                  {isVi ? group.description : group.descriptionEn}
                </p>

                <div className="mt-3 space-y-2">
                  {group.keys.map((key) => {
                    const isEnabled = Boolean(config?.rag_flow[key]);
                    const meta = FLOW_FLAG_META[key];
                    return (
                      <div
                        key={key}
                        className="flex items-center justify-between gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 transition hover:border-[color:var(--brand-primary)]/40"
                      >
                        <div className="min-w-0 pr-1">
                          <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
                            {meta?.label ?? key}
                          </p>
                          <p className="text-[10px] text-[var(--text-muted)] line-clamp-1">
                            {meta?.hint ?? key}
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() => setFlowToggle(key, !isEnabled)}
                          aria-label={`Toggle ${meta?.label ?? key}`}
                          className={[
                            "shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]",
                            isEnabled
                              ? "border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-xs"
                              : "border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-secondary)]",
                          ].join(" ")}
                        >
                          {isEnabled ? "ON" : "OFF"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Low Context Threshold Slider Tuning Bar */}
        <div className="mt-5 rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                {isVi ? "Ngưỡng Ngữ cảnh Thấp (low_context_threshold)" : "Low Context Threshold Slider"}
              </h3>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                {isVi
                  ? "Khi độ tự tin ngữ cảnh < ngưỡng, hệ thống kích hoạt cơ chế Fail-closed, yêu cầu bổ sung thông tin hoặc chuyển sang hội chẩn đa chuyên khoa."
                  : "When context confidence < threshold, the system enforces Fail-closed policy, requesting more user data or escalating to multi-agent council."}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-[var(--text-brand)]">
                {(config?.rag_flow.low_context_threshold ?? 0).toFixed(2)}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setLowContextThreshold(0.15)}
                  className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                >
                  {isVi ? "Nghiêm ngặt (0.15)" : "Strict (0.15)"}
                </button>
                <button
                  type="button"
                  onClick={() => setLowContextThreshold(0.3)}
                  className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                >
                  {isVi ? "Chuẩn (0.30)" : "Standard (0.30)"}
                </button>
                <button
                  type="button"
                  onClick={() => setLowContextThreshold(0.5)}
                  className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                >
                  {isVi ? "Mở rộng (0.50)" : "Permissive (0.50)"}
                </button>
              </div>
            </div>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_90px]">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              aria-label="Low Context Threshold"
              value={config?.rag_flow.low_context_threshold ?? 0}
              onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
              className="h-2 w-full cursor-pointer accent-[var(--brand-primary)]"
            />
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              aria-label="Low Context Threshold Number"
              value={config?.rag_flow.low_context_threshold ?? 0}
              onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
              className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-mono font-semibold text-[var(--text-primary)] text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
            />
          </div>
        </div>
      </section>

      {/* 3. Flow Topology Visualization & Interactive Node Inspector */}
      <section
        aria-label="Pipeline Topology and Stage Inspector"
        className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
              {isVi ? "Sơ đồ Topology Pipeline & Stage Inspector" : "Pipeline Topology Graph & Stage Inspector"}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Sơ đồ đồ thị luồng xử lý toàn diện. Nhấp vào bất kỳ node nào để mở chi tiết cấu hình và rủi ro tương ứng."
                : "Interactive visual pipeline topology graph. Select any node to inspect configuration, dependencies, and risk notes."}
            </p>
          </div>

          {/* Quick node selector shortcuts */}
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mr-1 hidden md:inline">
              {isVi ? "Chuyển nhanh:" : "Jump to:"}
            </span>
            {KEY_NODES_FOR_QUICK_JUMP.slice(0, 6).map((nodeId) => (
              <button
                key={nodeId}
                type="button"
                onClick={() => setSelectedNode(nodeId)}
                className={[
                  "rounded px-2 py-0.5 text-[10px] font-medium transition",
                  selectedNode === nodeId
                    ? "bg-[var(--brand-600)] text-[#cdd7ff]"
                    : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                {FLOW_NODE_INFOS[nodeId]?.title ?? nodeId}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="mt-4 h-64 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
        ) : (
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_0.45fr]">
            {/* Main Interactive Flow Visualizer */}
            <div className="min-w-0">
              <AdminFlowVisualizer
                ragFlow={config?.rag_flow}
                onToggle={(key) => setFlowToggle(key, !Boolean(config?.rag_flow[key]))}
                onSelectNode={setSelectedNode}
                selectedNodeId={selectedNode}
              />
            </div>

            {/* Stage / Node Inspector Drawer */}
            <aside
              aria-label="Node Inspector"
              className="flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-2.5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
                    Node Inspector
                  </p>
                  <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-mono font-semibold text-[var(--text-muted)]">
                    {selectedNode}
                  </span>
                </div>

                <h4 className="mt-3 text-sm font-bold text-[var(--text-primary)]">
                  {selectedNodeInfo.title}
                </h4>
                <p className="mt-0.5 text-xs font-medium text-[var(--text-secondary)]">
                  {selectedNodeInfo.subtitle}
                </p>
                <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                  {selectedNodeInfo.description}
                </p>

                {/* Risk Note */}
                <div className="mt-3.5 rounded-lg border border-[color:var(--status-warning-border)] bg-[var(--surface-warning-soft)] p-3">
                  <div className="flex items-start gap-1.5">
                    <Icon name="warning" size={14} className="mt-0.5 text-[var(--text-warning)] shrink-0" />
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-warning)]">
                        {isVi ? "Ghi chú Rủi ro & Bị chặn" : "Risk & Failure Mode"}
                      </p>
                      <p className="mt-1 text-xs leading-4.5 text-[var(--text-warning)]">
                        {selectedNodeInfo.riskNote}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Node Toggle Control if toggleable */}
                {selectedToggleKey ? (
                  <div className="mt-3.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold text-[var(--text-primary)]">
                          {isVi ? "Cờ kích hoạt node" : "Flow Toggle"}
                        </p>
                        <p className="text-[10px] text-[var(--text-muted)]">
                          {isVi ? "Bật/tắt node này trực tiếp từ inspector." : "Toggle node status directly."}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFlowToggle(selectedToggleKey, !Boolean(selectedToggleEnabled))}
                        className={[
                          "rounded-full px-3 py-1 text-xs font-bold transition",
                          selectedToggleEnabled
                            ? "border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                            : "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-muted)] hover:bg-[var(--surface-muted)]",
                        ].join(" ")}
                      >
                        {selectedToggleEnabled ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>
                ) : null}

                {/* Verification Node special tuning */}
                {selectedNode === "verification" ? (
                  <div className="mt-3.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">
                      {isVi ? "Điều chỉnh Ngưỡng Kiểm chứng" : "Threshold Tuning"}
                    </p>
                    <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                      {isVi
                        ? "Điều chỉnh ngưỡng để xác định khi nào cần chặn phát hành do thiếu ngữ cảnh."
                        : "Tune threshold to enforce fail-closed answer block."}
                    </p>
                    <div className="mt-2.5 grid gap-2">
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        aria-label="Inspector Low Context Threshold Slider"
                        value={config?.rag_flow.low_context_threshold ?? 0}
                        onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
                        className="accent-[var(--brand-primary)]"
                      />
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        aria-label="Inspector Low Context Threshold Number"
                        value={config?.rag_flow.low_context_threshold ?? 0}
                        onChange={(event) => setLowContextThreshold(toNumber(event.target.value))}
                        className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs font-mono font-semibold text-[var(--text-primary)]"
                      />
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Quick stage jumping in inspector footer */}
              <div className="mt-4 border-t border-[color:var(--shell-border)] pt-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  {isVi ? "Các node lân cận" : "Connected Stages"}
                </p>
                <div className="flex flex-wrap gap-1">
                  {KEY_NODES_FOR_QUICK_JUMP.slice(6, 12).map((nodeId) => (
                    <button
                      key={nodeId}
                      type="button"
                      onClick={() => setSelectedNode(nodeId)}
                      className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] hover:border-[color:var(--brand-primary)]"
                    >
                      {FLOW_NODE_INFOS[nodeId]?.title ?? nodeId}
                    </button>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        )}
      </section>

      {/* 4. Runtime Inference Debugger */}
      <section
        aria-label="Runtime Inference Debugger"
        className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
              Research Debug Preview
            </p>
            <h2 className="mt-0.5 text-sm sm:text-base font-bold text-[var(--text-primary)]">
              {isVi ? "Debugger Luồng Trả lời Theo Thời gian Thực" : "Real-time Answer Flow Inference Debugger"}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Mô phỏng các nhánh route/retrieve/verify/policy và quan sát điều kiện nào chặn phát hành trước khi publish."
                : "Simulate route/retrieve/verify/policy branches and inspect gating rules prior to publishing."}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-muted)]">
              {isVi ? "Điểm test giả lập:" : "Simulation Score:"}
            </span>
            <span className="rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-mono font-bold text-[var(--text-brand)]">
              {debugLowContextScore.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="mt-4 grid gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium text-[var(--text-secondary)]">
              {isVi
                ? "Low-context score giả lập cho phiên debug (Kéo để kiểm tra policy phản hồi khi điểm số dao động)"
                : "Simulated low-context score for debugging (Drag to test policy response under varying confidence)"}
            </p>
            <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-xs font-mono font-bold text-[var(--text-primary)]">
              {debugLowContextScore.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            aria-label="Debug Simulation Low Context Score"
            value={debugLowContextScore}
            onChange={(event) => setDebugLowContextScore(toNumber(event.target.value))}
            className="accent-[var(--brand-primary)]"
          />
        </div>

        <div className="mt-4">
          <AdminFlowDebugger
            ragFlow={config?.rag_flow}
            lowContextThreshold={debugLowContextScore}
          />
        </div>
      </section>

      {/* 5. Live Flow Event Stream Monitor */}
      <AdminFlowRuntimePanel />

      {/* 6. Neural Network Pathway Visualizer */}
      <AdminNeuralNetworkVisualizer ragFlow={config?.rag_flow} />

      {/* 7. Council Multi-Agent Flow Canvas */}
      <section
        aria-label="Council Flow Diagram"
        className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="border-b border-[color:var(--shell-border)] pb-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
            Council Multi-Agent Orchestration
          </p>
          <h2 className="mt-0.5 text-sm sm:text-base font-bold text-[var(--text-primary)]">
            Council Flow
          </h2>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            {isVi
              ? "Sơ đồ hội chẩn đa chuyên khoa ở tầng quản trị. Trạng thái `needs_more_info` dùng debug score hiện tại để mô phỏng nhanh."
              : "Multi-agent clinical council orchestration. Uses current debug score to simulate needs_more_info state."}
          </p>
        </div>
        <div className="mt-4">
          <CouncilFlowCanvas
            isEmergency={false}
            needsMoreInfo={councilNeedsMoreInfo}
            hasCitations={councilHasCitations}
          />
        </div>
      </section>

      {/* 8. Flow Signal Spectrum Blocks */}
      <section
        aria-label="Flow Signal Blocks"
        className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
      >
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
              Flow Signal Blocks
            </h2>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Dải tín hiệu trạng thái của 10 cờ luồng kèm khối cuối là low_context_threshold."
                : "Status signal spectrum across 10 flow flags plus trailing low_context_threshold."}
            </p>
          </div>
          <span className="text-xs font-mono text-[var(--text-muted)]">
            {flowToggleKeys.length} flags + threshold
          </span>
        </div>
        <div className="mt-4">
          {isLoading ? (
            <div className="h-16 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
          ) : (
            <BarBlocks values={flowVisual} />
          )}
        </div>
      </section>
    </div>
  );
}

export default AdminAnswerFlowPanel;
