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
  allowRetrieverFallback: boolean;
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
    allowRetrieverFallback: true,
    requiresVerification: false
  },
  {
    id: "evidence-heavy",
    label: "evidence-heavy",
    description: "Ưu tiên bằng chứng khoa học + verification.",
    primaryRetriever: "scientific",
    allowRetrieverFallback: true,
    requiresVerification: true
  },
  {
    id: "low-context",
    label: "low-context",
    description: "Mô phỏng ngữ cảnh yếu để quan sát fallback branch.",
    primaryRetriever: "web",
    allowRetrieverFallback: true,
    requiresVerification: false
  },
  {
    id: "upload-first",
    label: "upload-first",
    description: "Ưu tiên tài liệu người dùng upload trước.",
    primaryRetriever: "file",
    allowRetrieverFallback: true,
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
  rag_graphrag_enabled: false,
  verification_enabled: true,
  deepseek_fallback_enabled: true,
  low_context_threshold: 0.2,
  scientific_retrieval_enabled: true,
  web_retrieval_enabled: true,
  file_retrieval_enabled: true,
  llm_provider: "hitechcloud_gpt53_codex_high",
  llm_base_url: "https://platform.hitechcloud.one/v1",
  llm_model: "gpt-5.3-codex-high",
  llm_api_key: ""
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
  if (status === "success") return "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300";
  if (status === "warn") return "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300";
  return "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300";
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

  const availableRetrievers = useMemo(() => {
    const retrievers: RetrieverId[] = [];
    if (flow.web_retrieval_enabled) retrievers.push("web");
    if (flow.scientific_retrieval_enabled) retrievers.push("scientific");
    if (flow.file_retrieval_enabled) retrievers.push("file");
    return retrievers;
  }, [flow]);

  const routeActive = flow.role_router_enabled || flow.intent_router_enabled;

  const primaryRetrieverEnabled = isRetrieverEnabled(flow, scenario.primaryRetriever);
  const retrieveActive =
    primaryRetrieverEnabled ||
    (scenario.allowRetrieverFallback && availableRetrievers.length > 0);

  const fallbackCondition =
    Number.isFinite(lowContextThreshold) &&
    lowContextThreshold > flow.low_context_threshold;

  const fallbackBranchActive =
    fallbackCondition &&
    flow.deepseek_fallback_enabled &&
    (scenario.id === "low-context" || !retrieveActive);

  const synthesizeActive = retrieveActive || fallbackBranchActive;
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
    : verifyActive && fallbackBranchActive
      ? "warn"
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
        ? `Using ${RETRIEVER_LABEL[scenario.primaryRetriever]}${
            primaryRetrieverEnabled ? "" : " (fallback retriever được chọn)"
          }.`
        : "Không có retriever nào đang bật trong ragFlow.",
      active: retrieveActive
    },
    {
      id: "synthesize",
      title: "synthesize",
      detail: synthesizeActive
        ? "Node tổng hợp bằng chứng đang chạy."
        : "Bị skip vì cả retrieval và fallback đều không chạy.",
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
      status: policyAction === "allow" ? "success" : policyAction === "warn" ? "warn" : "blocked",
      policyAction,
      durationMs: fallbackBranchActive ? 1850 : 1320
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
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Flow Debugger
          </p>
          <h3 className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Scenario Timeline + Run History
          </h3>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
            Mô phỏng kiểu Dify: route -&gt; retrieve -&gt; synthesize -&gt; verify -&gt; policy -&gt; respond
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-800">
          <p className="text-slate-500 dark:text-slate-400">low-context score</p>
          <p className="font-semibold text-slate-900 dark:text-slate-100">
            {formatNumber(lowContextThreshold)}
          </p>
          <p className="text-slate-500 dark:text-slate-400">
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
                  ? "border-sky-400 bg-sky-50 text-sky-900 dark:border-sky-500 dark:bg-sky-950/40 dark:text-sky-100"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-600"
              ].join(" ")}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.1em]">{preset.label}</p>
              <p className="mt-1 text-xs opacity-80">{preset.description}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
        <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
          Active preset: <span className="font-semibold">{scenario.label}</span>
        </p>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{scenario.description}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300">
            Primary: {RETRIEVER_LABEL[scenario.primaryRetriever]}
          </span>
          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300">
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
                  className="absolute left-[11px] top-7 h-[calc(100%-0.35rem)] w-px bg-slate-300 dark:bg-slate-700"
                />
              ) : null}

              <span
                aria-hidden
                className={[
                  "absolute left-0 top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold",
                  step.active
                    ? "border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                    : "border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400"
                ].join(" ")}
              >
                {index + 1}
              </span>

              <div
                className={[
                  "rounded-xl border px-3 py-2",
                  step.active
                    ? "border-emerald-200 bg-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/30"
                    : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900/70"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-800 dark:text-slate-100">
                    {step.title}
                  </p>
                  <span
                    className={[
                      "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      step.active
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                    ].join(" ")}
                  >
                    {step.active ? "active" : "inactive"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{step.detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {fallbackCondition ? (
          <span className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            Branch fallback: low-context ({formatNumber(lowContextThreshold)}) &gt; threshold ({formatNumber(flow.low_context_threshold)})
          </span>
        ) : (
          <span className="rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
            Branch fallback: standby (low-context chưa vượt threshold)
          </span>
        )}

        <span
          className={[
            "rounded-full border px-3 py-1 text-xs font-semibold",
            fallbackBranchActive
              ? "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
              : "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
          ].join(" ")}
        >
          Fallback route: {fallbackBranchActive ? "active" : "inactive"}
        </span>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
        <div className="bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          Run History (mô phỏng)
        </div>
        <table className="min-w-full text-left text-xs">
          <thead className="bg-white text-slate-500 dark:bg-slate-900/80 dark:text-slate-400">
            <tr>
              <th className="px-3 py-2 font-medium">Run ID</th>
              <th className="px-3 py-2 font-medium">Scenario</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Policy</th>
              <th className="px-3 py-2 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-slate-900">
            {simulatedRuns.map((run) => (
              <tr key={run.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-200">{run.id}</td>
                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{run.scenario}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${runStatusClass(run.status)}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{run.policyAction}</td>
                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{run.durationMs} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
