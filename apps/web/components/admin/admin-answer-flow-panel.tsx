"use client";

import { BarBlocks } from "@/components/admin/admin-visuals";
import { FLOW_FLAG_META } from "@/components/admin/admin-config-meta";
import useControlTowerConfig, { FlowToggleKey } from "@/components/admin/use-control-tower-config";

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function AdminAnswerFlowPanel() {
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

  const flowVisual = config
    ? [...flowToggleKeys.map((key) => (config.rag_flow[key] ? 100 : 25)), config.rag_flow.low_context_threshold * 100]
    : [];
  const enabledFlowCount = config ? flowToggleKeys.filter((key) => config.rag_flow[key]).length : 0;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Answer Flow Block</p>
            <h3 className="mt-2 text-sm font-semibold text-slate-900">Decision Flow Controls</h3>
            <p className="mt-1 text-xs text-slate-600">Điều phối router, verification, fallback và ngưỡng confidence low-context.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void reload()}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
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

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Flow Flags</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {enabledFlowCount}/{flowToggleKeys.length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">low_context_threshold</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{config?.rag_flow.low_context_threshold.toFixed(2) ?? "0.00"}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Fallback Mode</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {config?.rag_flow.deepseek_fallback_enabled ? "enabled" : "disabled"}
            </p>
          </div>
        </div>

        {error ? <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
        {message ? <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p> : null}

        {isLoading ? (
          <div className="mt-4 h-24 animate-pulse rounded-xl bg-slate-100" />
        ) : (
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Flow Toggles</p>
                <p className="text-xs text-slate-600">Router + Verification + Retrieval + Fallback</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {flowToggleKeys.map((key) => {
                  const meta = FLOW_FLAG_META[key as FlowToggleKey];
                  const enabled = Boolean(config?.rag_flow[key]);
                  return (
                    <article key={key} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-800">{meta.label}</p>
                          <p className="mt-1 text-xs text-slate-600">{meta.hint}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setFlowToggle(key, !enabled)}
                          className={[
                            "rounded-full px-3 py-1 text-xs font-semibold transition",
                            enabled
                              ? "border border-emerald-300 bg-emerald-100 text-emerald-700"
                              : "border border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-200"
                          ].join(" ")}
                        >
                          {enabled ? "ON" : "OFF"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </article>

            <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Threshold Tuning</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">low_context_threshold</p>
                  <p className="mt-1 text-xs text-slate-600">Ngưỡng confidence để kích hoạt fallback hoặc escalation.</p>
                </div>
                <p className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                  {config?.rag_flow.low_context_threshold.toFixed(2)}
                </p>
              </div>
              <div className="mt-3 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-sky-500 to-cyan-400"
                  style={{ width: `${Math.round((config?.rag_flow.low_context_threshold ?? 0) * 100)}%` }}
                />
              </div>
              <div className="mt-3 grid gap-3">
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
                  className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                />
              </div>
            </article>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Flow Signal Blocks</h3>
          <span className="text-xs text-slate-500">{flowToggleKeys.length} flags + threshold</span>
        </div>
        <div className="mt-3">
          {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-slate-100" /> : <BarBlocks values={flowVisual} />}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Block cuối cùng là threshold, các block trước là flow flags dạng bật/tắt.
        </p>
      </section>
    </div>
  );
}
