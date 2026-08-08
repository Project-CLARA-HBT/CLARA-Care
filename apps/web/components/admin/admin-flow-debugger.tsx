"use client";

import { useMemo, useState } from "react";
import type { ControlTowerRagFlow } from "@/lib/system";

type ScenarioId = "quick-web" | "evidence-heavy" | "low-context" | "upload-first";
type RetrieverId = "web" | "scientific" | "file";
type StepId = "route" | "retrieve" | "synthesize" | "verify" | "policy" | "respond";

type AdminFlowDebuggerProps = {
  ragFlow?: ControlTowerRagFlow | null;
  lowContextThreshold: number;
};

type ScenarioPreset = {
  id: ScenarioId;
  label: string;
  description: string;
  primaryRetriever: RetrieverId;
  requiresVerification: boolean;
};

type StepState = {
  id: StepId;
  title: string;
  detail: string;
  active: boolean;
};

type SimulatedRun = {
  id: string;
  scenario: string;
  status: "success" | "warn" | "blocked";
  policyAction: "allow" | "warn" | "block";
  durationMs: number;
};

const PRESETS: ScenarioPreset[] = [
  {
    id: "quick-web",
    label: "quick-web",
    description: "Nhanh, ưu tiên web retrieval.",
    primaryRetriever: "web",
    requiresVerification: false
  },
  {
    id: "evidence-heavy",
    label: "evidence-heavy",
    description: "Ưu tiên bằng chứng khoa học + verification.",
    primaryRetriever: "scientific",
    requiresVerification: true
  },
  {
    id: "low-context",
    label: "low-context",
    description: "Mô phỏng ngữ cảnh yếu để quan sát policy fail-closed.",
    primaryRetriever: "web",
    requiresVerification: false
  },
  {
    id: "upload-first",
    label: "upload-first",
    description: "Ưu tiên tài liệu người dùng upload trước.",
    primaryRetriever: "file",
    requiresVerification: true
  }
];

const RETRIEVER_LABEL: Record<RetrieverId, string> = {
  web: "web retrieval",
  scientific: "scientific retrieval",
  file: "file retrieval"
};

const DEFAULT_FLOW: ControlTowerRagFlow = {
  role_router_enabled: true,
  intent_router_enabled: true,
  rule_verification_enabled: true,
  nli_model_enabled: true,
  rag_reranker_enabled: true,
  rag_nli_enabled: true,
  rag_graphrag_enabled: true,
  verification_enabled: true,
  deepseek_fallback_enabled: false,
  low_context_threshold: 0.2,
  scientific_retrieval_enabled: true,
  web_retrieval_enabled: true,
  file_retrieval_enabled: true
};

function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return "0.00";
  return value.toFixed(2);
}

function isRetrieverEnabled(flow: ControlTowerRagFlow, retriever: RetrieverId): boolean {
  if (retriever === "web") return Boolean(flow.web_retrieval_enabled);
  if (retriever === "scientific") return Boolean(flow.scientific_retrieval_enabled);
  return Boolean(flow.file_retrieval_enabled);
}

function runStatusClass(status: SimulatedRun["status"]): string {
  if (status === "success") return "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]";
  if (status === "warn") return "bg-[var(--surface-warning-soft)] text-[var(--text-warning)]";
  return "bg-[var(--surface-danger-soft)] text-[var(--text-danger)]";
}

export default function AdminFlowDebugger({
  ragFlow,
  lowContextThreshold
}: AdminFlowDebuggerProps) {
  const [scenarioId, setScenarioId] = useState<ScenarioId>("quick-web");

  const flow = ragFlow ?? DEFAULT_FLOW;

  const scenario = useMemo(
    () => PRESETS.find((preset) => preset.id === scenarioId) ?? PRESETS[0],
    [scenarioId]
  );

  const routeActive = flow.role_router_enabled || flow.intent_router_enabled;

  const primaryRetrieverEnabled = isRetrieverEnabled(flow, scenario.primaryRetriever);
  const retrieveActive = primaryRetrieverEnabled;

  const contextBlocked =
    Number.isFinite(lowContextThreshold) &&
    lowContextThreshold > flow.low_context_threshold;

  const synthesizeActive = retrieveActive && !contextBlocked;
  const verificationGateEnabled = Boolean(flow.rule_verification_enabled ?? flow.verification_enabled);
  const nliActive = Boolean(flow.nli_model_enabled) && Boolean(flow.rag_nli_enabled);
  const verifyActive =
    synthesizeActive &&
    verificationGateEnabled &&
    nliActive &&
    scenario.requiresVerification;

  const policyActive = synthesizeActive;
  const respondActive = policyActive;
  const policyAction: SimulatedRun["policyAction"] = !policyActive
    ? "block"
    : "allow";

  const steps: StepState[] = [
    {
      id: "route",
      title: "route",
      detail: routeActive
        ? "Role/intent router đang hoạt động."
        : "Cả role router và intent router đều đang tắt.",
      active: routeActive
    },
    {
      id: "retrieve",
      title: "retrieve",
      detail: retrieveActive
        ? `Using ${RETRIEVER_LABEL[scenario.primaryRetriever]}.`
        : "Retriever được yêu cầu đang tắt trong ragFlow.",
      active: retrieveActive
    },
    {
      id: "synthesize",
      title: "synthesize",
      detail: synthesizeActive
        ? "Node tổng hợp bằng chứng đang chạy."
        : contextBlocked
          ? "Bị chặn fail-closed do low-context vượt ngưỡng."
          : "Bị skip vì retriever được yêu cầu không chạy.",
      active: synthesizeActive
    },
    {
      id: "verify",
      title: "verify",
      detail: verifyActive
        ? "Rule verification + NLI đang bật cho scenario này."
        : verificationGateEnabled && nliActive
          ? "Scenario này đi nhánh không bắt buộc verify."
          : "Rule verification hoặc NLI đang bị tắt trong ragFlow.",
      active: verifyActive
    },
    {
      id: "policy",
      title: "policy",
      detail: policyActive
        ? "Policy gate được áp dụng trước khi phản hồi."
        : "Không đi tới policy gate.",
      active: policyActive
    },
    {
      id: "respond",
      title: "respond",
      detail: respondActive
        ? "Đường phản hồi cuối đang thông."
        : "Đường phản hồi bị chặn ở bước trước.",
      active: respondActive
    }
  ];

  const simulatedRuns: SimulatedRun[] = [
    {
      id: "run-3",
      scenario: scenario.label,
      status: policyAction === "allow" ? "success" : "blocked",
      policyAction,
      durationMs: contextBlocked ? 0 : 1320
    },
    {
      id: "run-2",
      scenario: "evidence-heavy",
      status: verificationGateEnabled && nliActive ? "success" : "warn",
      policyAction: verificationGateEnabled && nliActive ? "allow" : "warn",
      durationMs: 2240
    },
    {
      id: "run-1",
      scenario: "quick-web",
      status: flow.web_retrieval_enabled ? "success" : "blocked",
      policyAction: flow.web_retrieval_enabled ? "allow" : "block",
      durationMs: 980
    }
  ];

  return (
    <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Flow Debugger
          </p>
          <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
            Scenario Timeline + Run History
          </h3>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Mô phỏng kiểu Dify: route -&gt; retrieve -&gt; synthesize -&gt; verify -&gt; policy -&gt; respond
          </p>
        </div>

        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs">
          <p className="text-[var(--text-muted)]">low-context score</p>
          <p className="font-semibold text-[var(--text-primary)]">
            {formatNumber(lowContextThreshold)}
          </p>
          <p className="text-[var(--text-muted)]">
            threshold: {formatNumber(flow.low_context_threshold)}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {PRESETS.map((preset) => {
          const selected = preset.id === scenario.id;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => setScenarioId(preset.id)}
              className={[
                "rounded-xl border px-3 py-2 text-left transition",
                selected
                  ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-[color:var(--brand-primary)]"
              ].join(" ")}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.1em]">{preset.label}</p>
              <p className="mt-1 text-xs opacity-80">{preset.description}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
        <p className="text-xs font-medium text-[var(--text-primary)]">
          Active preset: <span className="font-semibold">{scenario.label}</span>
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{scenario.description}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
            Primary: {RETRIEVER_LABEL[scenario.primaryRetriever]}
          </span>
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
            Policy action: {policyAction}
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          return (
            <div key={step.id} className="relative pl-8">
              {!isLast ? (
                <span
                  aria-hidden
                  className="absolute left-[11px] top-7 h-[calc(100%-0.35rem)] w-px bg-[var(--shell-border)]"
                />
              ) : null}

              <span
                aria-hidden
                className={[
                  "absolute left-0 top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold",
                  step.active
                    ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]"
                ].join(" ")}
              >
                {index + 1}
              </span>

              <div
                className={[
                  "rounded-xl border px-3 py-2",
                  step.active
                    ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[var(--text-primary)]">
                    {step.title}
                  </p>
                  <span
                    className={[
                      "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      step.active
                        ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                        : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                    ].join(" ")}
                  >
                    {step.active ? "active" : "inactive"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{step.detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={[
          "rounded-full border px-3 py-1 text-xs font-semibold",
          contextBlocked
            ? "border border-[color:var(--status-warning-border)] bg-[var(--surface-warning-soft)] text-[var(--text-warning)]"
            : "border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
        ].join(" ")}>
          {contextBlocked
            ? `Fail-closed: low-context (${formatNumber(lowContextThreshold)}) &gt; threshold (${formatNumber(flow.low_context_threshold)})`
            : "Context gate: pass"}
        </span>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
        <div className="bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
          Run History (mô phỏng)
        </div>
        <table className="min-w-full text-left text-xs">
          <thead className="bg-[var(--surface-panel)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 font-medium">Run ID</th>
              <th className="px-3 py-2 font-medium">Scenario</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Policy</th>
              <th className="px-3 py-2 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody className="bg-[var(--surface-panel)]">
            {simulatedRuns.map((run) => (
              <tr key={run.id} className="border-t border-[color:var(--shell-border)]">
                <td className="px-3 py-2 font-medium text-[var(--text-primary)]">{run.id}</td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{run.scenario}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${runStatusClass(run.status)}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{run.policyAction}</td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{run.durationMs} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
