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
      <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">RAG Configuration Block</p>
            <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Data Source Control</h3>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Quản lý `enabled`, `priority`, `weight`, `category` cho từng nguồn tri thức.
            </p>
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
              {isSaving ? "Saving..." : "Save Sources"}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Sources</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{totalSources}</p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Enabled Ratio</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-brand)]">
              {enabledSources}/{totalSources}
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Priority Band</p>
            <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
              {totalSources === 0 ? "n/a" : `${minPriority}-${maxPriority}`}
            </p>
          </div>
        </div>

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

        <div className="mt-4">
          {isLoading ? (
            <div className="h-24 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs uppercase tracking-wider text-[var(--text-muted)]">
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Priority</th>
                    <th className="px-3 py-2">Weight</th>
                    <th className="px-3 py-2">Enabled</th>
                  </tr>
                </thead>
                <tbody>
                  {(config?.rag_sources ?? []).map((source) => (
                    <tr key={source.id} className="border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)] last:border-0 hover:bg-[var(--surface-muted)]">
                      <td className="px-3 py-2">
                        <p className="font-medium text-[var(--text-primary)]">{source.name}</p>
                        <p className="text-xs text-[var(--text-muted)]">{source.id}</p>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={source.category}
                          onChange={(event) => setSourceCategory(source.id, event.target.value)}
                          className="w-40 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
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
                          className="w-24 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
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
                            className="w-20 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
                          />
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={source.weight}
                            onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                            className="w-24 accent-[#60a5fa]"
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
                              ? "border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                              : "border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-high)]"
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

      <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Priority Distribution</h3>
          <span className="text-xs text-[var(--text-muted)]">Lower number = higher priority</span>
        </div>
        <div className="mt-3">
          {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-[var(--surface-muted)]" /> : <BarBlocks values={priorityVisualData} />}
        </div>
        <p className="mt-2 text-xs text-[var(--text-muted)]">Bar cao hơn tương ứng nguồn có priority cao hơn trong pipeline retrieval.</p>
      </section>
    </div>
  );
}
