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
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[color:var(--danger-border)] bg-[var(--surface-danger-soft)] px-3 py-2 text-sm text-[var(--text-danger)]">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void reload()}
            className="rounded-lg border border-[color:var(--danger-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs font-medium text-[var(--text-danger)]"
          >
            Retry
          </button>
        </div>
      ) : null}
      {inventoryError ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[color:var(--status-warning-border)] bg-[var(--surface-warning-soft)] px-3 py-2 text-sm text-[var(--text-warning)]">
          <span>{inventoryError}</span>
          <button
            type="button"
            onClick={() => setInventoryReloadTick((prev) => prev + 1)}
            className="rounded-lg border border-[color:var(--status-warning-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs font-medium text-[var(--text-warning)]"
          >
            Reload
          </button>
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">RAG Configuration Block</p>
              <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Source Matrix</h3>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">Theo dõi coverage, taxonomy và mức ưu tiên của nguồn tri thức.</p>
            </div>
            <span className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[11px] font-mono text-[var(--text-secondary)]">
              sources:{totalSources}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Enabled</p>
              <p className="mt-1 text-lg font-semibold text-[var(--status-ok-text)]">{enabledSources}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Categories</p>
              <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{categoryCount}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Coverage</p>
              <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{pct(sourceCoverage)}</p>
            </div>
          </div>
          <div className="mt-3 overflow-hidden rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
            <div className="h-2 rounded-full bg-[#60a5fa]" style={{ width: `${Math.round(sourceCoverage * 100)}%` }} />
          </div>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Answer Flow Block</p>
              <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Decision Orchestration</h3>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">Giám sát trạng thái các flow flags và ngưỡng low-context của router.</p>
            </div>
            <span className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[11px] font-mono text-[var(--text-secondary)]">
              flags:{flowEnabledCount}/{flowTotal}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Flow Flags</p>
              <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                {flowEnabledCount}/{flowTotal}
              </p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Flow Coverage</p>
              <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{pct(flowCoverage)}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">low_context_threshold</p>
              <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{config?.rag_flow.low_context_threshold ?? 0}</p>
            </div>
          </div>
          <div className="mt-3 overflow-hidden rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
            <div className="h-2 rounded-full bg-[#60a5fa]" style={{ width: `${Math.round(flowCoverage * 100)}%` }} />
          </div>
        </article>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Retrieval Connectors</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{totalSources}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Nguồn dữ liệu đang khai báo</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Enabled Sources</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--status-ok-text)]">{enabledSources}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Coverage {pct(sourceCoverage)}</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Flow Flags</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">
            {flowEnabledCount}/{flowTotal}
          </p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Router, verification, fail-closed generation</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Categories</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{categoryCount}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Nhóm nguồn dữ liệu</p>
        </article>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Knowledge Hubs</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{totalKnowledgeSources}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Active {activeKnowledgeSources}</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Federated Connectors</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{totalSourceHubCatalog}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Live sync {liveSourceHubCatalog}</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Unified Sources</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{totalUnifiedSources}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Connectors + Knowledge + Federation</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Unified Active</p>
          <p className="mt-2 text-3xl font-semibold text-[var(--status-ok-text)]">{totalActiveUnifiedSources}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Đang usable trong pipeline</p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr] [&>article]:!rounded-[var(--radius-xl)] [&>article]:!border-t-[#2A3950] [&>article]:!border-[color:var(--shell-border)] [&>article]:!bg-[var(--surface-panel)] [&>article]:!shadow-none">
        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Source Priority Trend</h3>
            <span className="text-xs text-[var(--text-muted)]">Top 10 sources</span>
          </div>
          <div className="mt-3">
            {isLoading ? (
              <div className="h-14 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
            ) : (
              <Sparkline points={prioritySeries} stroke="#a4c9ff" />
            )}
          </div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">Điểm cao hơn thể hiện ưu tiên cao hơn (priority gần 1).</p>
        </article>

        <article className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Flow Balance</h3>
            <span className="text-xs text-[var(--text-muted)]">Threshold vs Flags</span>
          </div>
          <div className="mt-3">
            {isLoading ? <div className="h-16 animate-pulse rounded-lg bg-[var(--surface-muted)]" /> : <BarBlocks values={thresholdSeries} />}
          </div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">`low_context_threshold` đang là {config?.rag_flow.low_context_threshold ?? 0}.</p>
        </article>
      </section>

      <section className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Unified Source Inventory</h3>
          <span className="text-xs text-[var(--text-muted)]">Hiển thị toàn bộ source hiện có</span>
        </div>
        {isLoading || isInventoryLoading ? (
          <div className="mt-3 h-24 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
        ) : (
          <div className="mt-3 max-h-[32rem] overflow-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="sticky top-0 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs uppercase tracking-wider text-[var(--text-muted)]">
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
                  <tr key={source.key} className="border-b border-[color:var(--shell-border)] last:border-0">
                    <td className="px-2 py-2 text-[var(--text-secondary)]">{source.group}</td>
                    <td className="px-2 py-2 font-medium text-[var(--text-primary)]">{source.name}</td>
                    <td className="px-2 py-2 font-mono text-xs text-[var(--text-secondary)]">{source.id}</td>
                    <td className="px-2 py-2 text-[var(--text-secondary)]">{source.meta1}</td>
                    <td className="px-2 py-2 text-[var(--text-secondary)]">{source.meta2}</td>
                    <td className="px-2 py-2">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                          source.status === "enabled" ||
                          source.status === "active" ||
                          source.status === "live-sync"
                            ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                            : "bg-[var(--surface-muted)] text-[var(--text-secondary)]"
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
