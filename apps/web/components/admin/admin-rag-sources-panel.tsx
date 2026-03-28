"use client";

import { useMemo } from "react";
import { BarBlocks } from "@/components/admin/admin-visuals";
import { DEFAULT_SOURCE_CATEGORIES } from "@/components/admin/admin-config-meta";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";

export default function AdminRagSourcesPanel() {
  const {
    config,
    error,
    message,
    isDirty,
    isLoading,
    isSaving,
    reload,
    save,
    setSourceCategory,
    setSourceEnabled,
    setSourcePriority,
    setSourceWeight
  } = useControlTowerConfig();

  const categoryOptions = useMemo(() => {
    const fromConfig = (config?.rag_sources ?? []).map((source) => source.category);
    return Array.from(new Set([...DEFAULT_SOURCE_CATEGORIES, ...fromConfig])).sort();
  }, [config]);

  const totalSources = config?.rag_sources.length ?? 0;
  const enabledSources = config?.rag_sources.filter((source) => source.enabled).length ?? 0;
  const maxPriority = Math.max(...(config?.rag_sources.map((source) => source.priority) ?? [0]));
  const minPriority = Math.min(...(config?.rag_sources.map((source) => source.priority) ?? [0]));

  const priorityVisualData = config?.rag_sources.slice(0, 14).map((source) => Math.max(1, 101 - source.priority)) ?? [];

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">RAG Configuration Block</p>
            <h3 className="mt-2 text-sm font-semibold text-slate-900">Data Source Control</h3>
            <p className="mt-1 text-xs text-slate-600">
              Quản lý `enabled`, `priority`, `weight`, `category` cho từng nguồn tri thức.
            </p>
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
              {isSaving ? "Saving..." : "Save Sources"}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Sources</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{totalSources}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Enabled Ratio</p>
            <p className="mt-1 text-lg font-semibold text-emerald-600">
              {enabledSources}/{totalSources}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Priority Band</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {totalSources === 0 ? "n/a" : `${minPriority}-${maxPriority}`}
            </p>
          </div>
        </div>

        {error ? <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
        {message ? <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p> : null}

        <div className="mt-4">
          {isLoading ? (
            <div className="h-24 animate-pulse rounded-xl bg-slate-100" />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Priority</th>
                    <th className="px-3 py-2">Weight</th>
                    <th className="px-3 py-2">Enabled</th>
                  </tr>
                </thead>
                <tbody>
                  {(config?.rag_sources ?? []).map((source) => (
                    <tr key={source.id} className="border-b border-slate-100 bg-white last:border-0 hover:bg-slate-50/60">
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-800">{source.name}</p>
                        <p className="text-xs text-slate-500">{source.id}</p>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={source.category}
                          onChange={(event) => setSourceCategory(source.id, event.target.value)}
                          className="w-40 rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                        >
                          {categoryOptions.map((category) => (
                            <option key={category} value={category}>
                              {category}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={source.priority}
                          onChange={(event) => setSourcePriority(source.id, Number(event.target.value))}
                          className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex min-w-[200px] items-center gap-2">
                          <input
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            value={source.weight}
                            onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                            className="w-20 rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                          />
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={source.weight}
                            onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                            className="w-24 accent-sky-600"
                            aria-label={`Weight for ${source.name}`}
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => setSourceEnabled(source.id, !source.enabled)}
                          className={[
                            "rounded-full px-3 py-1 text-xs font-semibold transition",
                            source.enabled
                              ? "border border-emerald-300 bg-emerald-100 text-emerald-700"
                              : "border border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-200"
                          ].join(" ")}
                        >
                          {source.enabled ? "Enabled" : "Disabled"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Priority Distribution</h3>
          <span className="text-xs text-slate-500">Lower number = higher priority</span>
        </div>
        <div className="mt-3">
          {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-slate-100" /> : <BarBlocks values={priorityVisualData} />}
        </div>
        <p className="mt-2 text-xs text-slate-500">Bar cao hơn tương ứng nguồn có priority cao hơn trong pipeline retrieval.</p>
      </section>
    </div>
  );
}
