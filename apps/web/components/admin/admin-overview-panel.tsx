"use client";

import { useEffect, useMemo, useState } from "react";
import { BarBlocks, Sparkline } from "@/components/admin/admin-visuals";
import { FLOW_FLAG_META } from "@/components/admin/admin-config-meta";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
import {
  KnowledgeSource,
  SourceHubCatalogEntry,
  listKnowledgeSources,
  listSourceHubCatalog
} from "@/lib/research";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export default function AdminOverviewPanel() {
  const { config, error, isLoading, reload } = useControlTowerConfig();
  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([]);
  const [sourceHubCatalog, setSourceHubCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [inventoryError, setInventoryError] = useState("");
  const [isInventoryLoading, setIsInventoryLoading] = useState(true);
  const [inventoryReloadTick, setInventoryReloadTick] = useState(0);

  useEffect(() => {
    let active = true;

    const loadInventory = async () => {
      setIsInventoryLoading(true);
      setInventoryError("");
      try {
        const [knowledge, catalog] = await Promise.all([
          listKnowledgeSources(),
          listSourceHubCatalog()
        ]);
        if (!active) return;
        setKnowledgeSources(knowledge);
        setSourceHubCatalog(catalog);
      } catch (cause) {
        if (!active) return;
        setInventoryError(
          sanitizeUpstreamError(
            cause instanceof Error
              ? cause.message
              : "Không thể tải danh mục nguồn tổng hợp cho admin dashboard."
          )
        );
      } finally {
        if (active) setIsInventoryLoading(false);
      }
    };

    void loadInventory();
    return () => {
      active = false;
    };
  }, [inventoryReloadTick]);

  // Emit a single named product event when the Admin overview is opened
  // (Req 9.1). No PII — only the coarse Admin view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "overview" });
  }, []);

  const totalSources = config?.rag_sources.length ?? 0;
  const enabledSources = config?.rag_sources.filter((source) => source.enabled).length ?? 0;
  const categoryCount = new Set(config?.rag_sources.map((source) => source.category) ?? []).size;
  const totalKnowledgeSources = knowledgeSources.length;
  const activeKnowledgeSources = knowledgeSources.filter((source) => source.is_active).length;
  const totalSourceHubCatalog = sourceHubCatalog.length;
  const liveSourceHubCatalog = sourceHubCatalog.filter((source) => source.supports_live_sync).length;

  const flowEnabledCount = config
    ? Object.keys(FLOW_FLAG_META).filter((key) => config.rag_flow[key as keyof typeof FLOW_FLAG_META]).length
    : 0;
  const flowTotal = Object.keys(FLOW_FLAG_META).length;

  const sourceCoverage = totalSources > 0 ? enabledSources / totalSources : 0;
  const flowCoverage = flowTotal > 0 ? flowEnabledCount / flowTotal : 0;
  const prioritySeries =
    config?.rag_sources.slice(0, 10).map((source) => Math.max(1, 101 - source.priority)) ?? [];
  const thresholdSeries = config
    ? [
        config.rag_flow.low_context_threshold * 100,
        Math.max(0, 100 - config.rag_flow.low_context_threshold * 100),
        flowEnabledCount * 22
      ]
    : [];
  const unifiedRows = useMemo(() => {
    const ragRows = (config?.rag_sources ?? []).map((source) => ({
      key: `rag-${source.id}`,
      group: "RAG",
      name: source.name,
      id: source.id,
      status: source.enabled ? "enabled" : "disabled",
      meta1: source.category,
      meta2: `priority=${source.priority} | weight=${source.weight.toFixed(2)}`
    }));
    const knowledgeRows = knowledgeSources.map((source) => ({
      key: `knowledge-${source.id}`,
      group: "Knowledge",
      name: source.name,
      id: String(source.id),
      status: source.is_active ? "active" : "inactive",
      meta1: "knowledge_source",
      meta2: `documents=${source.documents_count}`
    }));
    const sourceHubRows = sourceHubCatalog.map((source) => ({
      key: `source-hub-${source.key}`,
      group: "SourceHub",
      name: source.label,
      id: source.key,
      status: source.supports_live_sync ? "live-sync" : "catalog-only",
      meta1: source.description,
      meta2: source.default_query ? `default_query=${source.default_query}` : "-"
    }));
    return [...ragRows, ...knowledgeRows, ...sourceHubRows];
  }, [config?.rag_sources, knowledgeSources, sourceHubCatalog]);
  const totalUnifiedSources = unifiedRows.length;
  const totalActiveUnifiedSources =
    enabledSources + activeKnowledgeSources + liveSourceHubCatalog;

  return (
    <div className="space-y-4">
      {error ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void reload()}
            className="rounded-lg border border-rose-300 bg-white px-2 py-1 text-xs font-medium text-rose-700 dark:border-rose-800 dark:bg-slate-900 dark:text-rose-300"
          >
            Retry
          </button>
        </div>
      ) : null}
      {inventoryError ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <span>{inventoryError}</span>
          <button
            type="button"
            onClick={() => setInventoryReloadTick((prev) => prev + 1)}
            className="rounded-lg border border-amber-300 bg-white px-2 py-1 text-xs font-medium text-amber-700 dark:border-amber-800 dark:bg-slate-900 dark:text-amber-200"
          >
            Reload
          </button>
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">RAG Configuration Block</p>
              <h3 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">Source Matrix</h3>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Theo dõi coverage, taxonomy và mức ưu tiên của nguồn tri thức.</p>
            </div>
            <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-mono text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
              sources:{totalSources}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Enabled</p>
              <p className="mt-1 text-lg font-semibold text-emerald-600">{enabledSources}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Categories</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{categoryCount}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Coverage</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{pct(sourceCoverage)}</p>
            </div>
          </div>
          <div className="mt-3 overflow-hidden rounded-full border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-800">
            <div className="h-2 rounded-full bg-gradient-to-r from-sky-500 to-cyan-400" style={{ width: `${Math.round(sourceCoverage * 100)}%` }} />
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Answer Flow Block</p>
              <h3 className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">Decision Orchestration</h3>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Giám sát trạng thái các flow flags và ngưỡng low-context của router.</p>
            </div>
            <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-mono text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
              flags:{flowEnabledCount}/{flowTotal}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Flags</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {flowEnabledCount}/{flowTotal}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Coverage</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{pct(flowCoverage)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">low_context_threshold</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{config?.rag_flow.low_context_threshold ?? 0}</p>
            </div>
          </div>
          <div className="mt-3 overflow-hidden rounded-full border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-800">
            <div className="h-2 rounded-full bg-gradient-to-r from-cyan-500 to-sky-500" style={{ width: `${Math.round(flowCoverage * 100)}%` }} />
          </div>
        </article>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Retrieval Connectors</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">{totalSources}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Nguồn dữ liệu đang khai báo</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Enabled Sources</p>
          <p className="mt-2 text-3xl font-semibold text-emerald-600">{enabledSources}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Coverage {pct(sourceCoverage)}</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Flags</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">
            {flowEnabledCount}/{flowTotal}
          </p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Router, verification, fallback</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Categories</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">{categoryCount}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Nhóm nguồn dữ liệu</p>
        </article>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Knowledge Hubs</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">{totalKnowledgeSources}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Active {activeKnowledgeSources}</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Federated Connectors</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">{totalSourceHubCatalog}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Live sync {liveSourceHubCatalog}</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Unified Sources</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">{totalUnifiedSources}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Connectors + Knowledge + Federation</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Unified Active</p>
          <p className="mt-2 text-3xl font-semibold text-emerald-600">{totalActiveUnifiedSources}</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Đang usable trong pipeline</p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr] [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Source Priority Trend</h3>
            <span className="text-xs text-slate-500 dark:text-slate-400">Top 10 sources</span>
          </div>
          <div className="mt-3">
            {isLoading ? (
              <div className="h-14 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
            ) : (
              <Sparkline points={prioritySeries} stroke="#2563eb" />
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Điểm cao hơn thể hiện ưu tiên cao hơn (priority gần 1).</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Flow Balance</h3>
            <span className="text-xs text-slate-500 dark:text-slate-400">Threshold vs Flags</span>
          </div>
          <div className="mt-3">
            {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" /> : <BarBlocks values={thresholdSeries} />}
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">`low_context_threshold` đang là {config?.rag_flow.low_context_threshold ?? 0}.</p>
        </article>
      </section>

      <section className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Unified Source Inventory</h3>
          <span className="text-xs text-slate-500 dark:text-slate-400">Hiển thị toàn bộ source hiện có</span>
        </div>
        {isLoading || isInventoryLoading ? (
          <div className="mt-3 h-24 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
        ) : (
          <div className="mt-3 max-h-[32rem] overflow-auto rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                  <th className="px-2 py-2">Group</th>
                  <th className="px-2 py-2">Source</th>
                  <th className="px-2 py-2">Id</th>
                  <th className="px-2 py-2">Meta</th>
                  <th className="px-2 py-2">Detail</th>
                  <th className="px-2 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {unifiedRows.map((source) => (
                  <tr key={source.key} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{source.group}</td>
                    <td className="px-2 py-2 font-medium text-slate-800 dark:text-slate-100">{source.name}</td>
                    <td className="px-2 py-2 font-mono text-xs text-slate-600 dark:text-slate-300">{source.id}</td>
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{source.meta1}</td>
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{source.meta2}</td>
                    <td className="px-2 py-2">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                          source.status === "enabled" ||
                          source.status === "active" ||
                          source.status === "live-sync"
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                            : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                        ].join(" ")}
                      >
                        {source.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
