"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import api from "@/lib/http-client";
import { getRole, type UserRole } from "@/lib/auth-store";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * RAG Ingestion & ETL Monitor (Spec v8 Section 12.13, Spec v5 Section 6.69, Requirement 13.3).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: RAG Ingestion Monitor
 *
 * Dense, high-signal administration plane that drives the offline ingestion pipeline:
 *   - GET  /admin/rag/sources                    — source registry + watermarks
 *   - POST /admin/rag/ingestion/run              — trigger ingestion for a source
 *   - GET  /admin/rag/ingestion/status/{job_id}  — poll running job status
 *   - GET  /admin/rag/stats                       — corpus stats + degraded count
 *
 * Features dense table of active/historical ETL jobs, filters, and a multi-stage
 * inspector (Fetch → Parse/Chunk → Embedding → Indexing) with failure diagnosis.
 */

// ---------------------------------------------------------------------------
// API shapes
// ---------------------------------------------------------------------------

type RagSource = {
  id: number | null;
  source_key: string;
  display_name: string;
  trust_tier: number | null;
  enabled: boolean;
  weight: number | null;
  fetch_mode: string;
  last_watermark: string;
  last_run_at: string | null;
};

type SourcesListResponse = {
  sources: RagSource[];
  ml_available?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

type IngestionRunResponse = {
  job_id: string;
  source_key: string;
  status: string;
  accepted: boolean;
  ml_available?: boolean;
};

export type IngestionStatus = {
  job_id: string;
  source_key: string;
  status: string;
  fetched: number;
  inserted: number;
  updated: number;
  skipped: number;
  degraded: number;
  errors: unknown[];
  ml_available?: boolean;
  started_at?: string;
  completed_at?: string;
};

type CorpusStats = {
  documents: number;
  chunks: number;
  degraded_chunks: number;
  coverage_pct: number;
  sources_total: number;
  sources_enabled: number;
  ml_available?: boolean;
  fallback?: boolean;
};

// ---------------------------------------------------------------------------
// Typed fetchers
// ---------------------------------------------------------------------------

async function fetchSources(): Promise<SourcesListResponse> {
  const response = await api.get<SourcesListResponse>("/admin/rag/sources");
  return response.data;
}

async function fetchStats(): Promise<CorpusStats> {
  const response = await api.get<CorpusStats>("/admin/rag/stats");
  return response.data;
}

async function runIngestion(sourceKey: string): Promise<IngestionRunResponse> {
  const response = await api.post<IngestionRunResponse>("/admin/rag/ingestion/run", {
    source_key: sourceKey,
  });
  return response.data;
}

async function fetchJobStatus(jobId: string): Promise<IngestionStatus> {
  const response = await api.get<IngestionStatus>(
    `/admin/rag/ingestion/status/${encodeURIComponent(jobId)}`
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

function formatCount(value: number | null | undefined, language: UILanguage): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat(language === "vi" ? "vi-VN" : "en-US", {
    maximumFractionDigits: 0,
  }).format(Math.max(0, value));
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.max(0, value).toFixed(1)}%`;
}

function formatDate(value: string | null | undefined, language: UILanguage): string {
  if (!value) return t(language, "admin.ragIngestion.neverRun");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(language === "vi" ? "vi-VN" : "en-US", { hour12: false });
}

function trustTierLabel(tier: number | null | undefined, language: UILanguage): string {
  switch (tier) {
    case 1:
      return t(language, "admin.ragIngestion.tier.one");
    case 2:
      return t(language, "admin.ragIngestion.tier.two");
    case 3:
      return t(language, "admin.ragIngestion.tier.three");
    case 4:
      return t(language, "admin.ragIngestion.tier.four");
    default:
      return t(language, "admin.ragIngestion.tier.unassigned");
  }
}

function fetchModeLabel(mode: string, language: UILanguage): string {
  const key = (mode ?? "").trim().toLowerCase();
  if (key === "api") return "API";
  if (key === "crawl") return t(language, "admin.ragIngestion.crawl");
  return mode || "--";
}

function statusLabel(status: string, language: UILanguage): string {
  const key = (status ?? "").trim().toLowerCase();
  const labels: Record<string, UITranslationKey> = {
    queued: "admin.ragIngestion.status.queued",
    pending: "admin.ragIngestion.status.queued",
    running: "admin.ragIngestion.status.running",
    in_progress: "admin.ragIngestion.status.running",
    completed: "admin.ragIngestion.status.completed",
    done: "admin.ragIngestion.status.completed",
    success: "admin.ragIngestion.status.completed",
    failed: "admin.ragIngestion.status.failed",
    error: "admin.ragIngestion.status.error",
    unavailable: "admin.ragIngestion.status.unavailable",
    cancelled: "admin.ragIngestion.status.cancelled",
    unknown: "admin.ragIngestion.status.unknown",
  };
  return labels[key]
    ? t(language, labels[key])
    : status || t(language, "admin.ragIngestion.status.unknown");
}

const TERMINAL_STATUSES = new Set([
  "completed",
  "done",
  "success",
  "failed",
  "error",
  "unavailable",
  "cancelled",
]);

function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.has((status ?? "").trim().toLowerCase());
}

function isFailureStatus(status: string): boolean {
  const key = (status ?? "").trim().toLowerCase();
  return key === "failed" || key === "error" || key === "unavailable" || key === "cancelled";
}

// ---------------------------------------------------------------------------
// AsyncState builders
// ---------------------------------------------------------------------------

function buildSourcesState(
  loading: boolean,
  error: string,
  sources: RagSource[] | null
): AsyncState<RagSource[]> {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: error };
  if (!sources || sources.length === 0) return { kind: "empty" };
  return { kind: "populated", data: sources };
}

function buildStatsState(
  loading: boolean,
  error: string,
  stats: CorpusStats | null
): AsyncState<CorpusStats> {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: error };
  if (!stats) return { kind: "empty" };
  return { kind: "populated", data: stats };
}

const POLL_INTERVAL_MS = 2500;

export default function AdminRagIngestionPage() {
  const language = useUILanguage();
  const [role, setRole] = useState<UserRole>("normal");
  const [hydrated, setHydrated] = useState(false);

  const [sources, setSources] = useState<RagSource[] | null>(null);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState("");
  const [sourcesDegraded, setSourcesDegraded] = useState(false);

  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  const [runningSourceKey, setRunningSourceKey] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<IngestionStatus | null>(null);
  const [jobHistory, setJobHistory] = useState<IngestionStatus[]>([]);
  const [selectedJob, setSelectedJob] = useState<IngestionStatus | null>(null);
  const [jobError, setJobError] = useState("");

  // Filters
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const loadSources = useCallback(async () => {
    setSourcesLoading(true);
    setSourcesError("");
    try {
      const result = await fetchSources();
      setSources(Array.isArray(result.sources) ? result.sources : []);
      setSourcesDegraded(result.fallback === true || result.ml_available === false);
    } catch (cause) {
      setSources(null);
      setSourcesError(
        sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause))
      );
    } finally {
      setSourcesLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError("");
    try {
      const result = await fetchStats();
      setStats(result);
    } catch (cause) {
      setStats(null);
      setStatsError(sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause)));
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || role !== "admin") return;
    void loadSources();
    void loadStats();
  }, [hydrated, role, loadSources, loadStats]);

  useEffect(() => stopPolling, [stopPolling]);

  const pollJob = useCallback(
    async (jobId: string) => {
      try {
        const status = await fetchJobStatus(jobId);
        setActiveJob(status);
        setSelectedJob(status);
        setJobHistory((prev) => {
          const filtered = prev.filter((j) => j.job_id !== jobId);
          return [status, ...filtered].slice(0, 10);
        });

        if (isTerminalStatus(status.status)) {
          setRunningSourceKey(null);
          stopPolling();
          void loadSources();
          void loadStats();
          return;
        }
        pollTimer.current = setTimeout(() => void pollJob(jobId), POLL_INTERVAL_MS);
      } catch (cause) {
        setJobError(sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause)));
        setRunningSourceKey(null);
        stopPolling();
      }
    },
    [loadSources, loadStats, stopPolling]
  );

  const onRunIngestion = useCallback(
    async (source: RagSource) => {
      if (runningSourceKey) return;
      stopPolling();
      setJobError("");
      setRunningSourceKey(source.source_key);
      try {
        const result = await runIngestion(source.source_key);
        const baseJob: IngestionStatus = {
          job_id: result.job_id ?? `job-${Date.now()}`,
          source_key: result.source_key || source.source_key,
          status: result.status || (result.accepted ? "queued" : "unavailable"),
          fetched: 0,
          inserted: 0,
          updated: 0,
          skipped: 0,
          degraded: 0,
          errors: [],
          started_at: new Date().toISOString(),
        };
        setActiveJob(baseJob);
        setSelectedJob(baseJob);
        setJobHistory((prev) => [baseJob, ...prev.filter((j) => j.job_id !== baseJob.job_id)].slice(0, 10));

        if (!result.accepted || !result.job_id) {
          setRunningSourceKey(null);
          return;
        }
        pollTimer.current = setTimeout(() => void pollJob(result.job_id), 1500);
      } catch (cause) {
        setJobError(sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause)));
        setRunningSourceKey(null);
      }
    },
    [runningSourceKey, pollJob, stopPolling]
  );

  const sourcesState = useMemo(
    () => buildSourcesState(sourcesLoading, sourcesError, sources),
    [sourcesLoading, sourcesError, sources]
  );
  const statsState = useMemo(
    () => buildStatsState(statsLoading, statsError, stats),
    [statsLoading, statsError, stats]
  );

  // Filter sources
  const filteredSources = useMemo(() => {
    if (!sources) return [];
    return sources.filter((s) => {
      if (sourceFilter !== "all" && s.source_key !== sourceFilter) return false;
      if (statusFilter === "enabled" && !s.enabled) return false;
      if (statusFilter === "disabled" && s.enabled) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const keyMatch = s.source_key.toLowerCase().includes(q);
        const nameMatch = (s.display_name ?? "").toLowerCase().includes(q);
        if (!keyMatch && !nameMatch) return false;
      }
      return true;
    });
  }, [sources, sourceFilter, statusFilter, searchQuery]);

  const isRefreshing = sourcesLoading || statsLoading;

  if (!hydrated) {
    return (
      <AdminShell
        activeTab="rag-ingestion"
        title={t(language, "admin.ragIngestion.title")}
        description={t(language, "admin.ragIngestion.description")}
      >
        <AsyncSection<null>
          state={{ kind: "loading" }}
          loadingLabel={t(language, "admin.ragIngestion.checkAccess")}
        >
          {() => null}
        </AsyncSection>
      </AdminShell>
    );
  }

  if (role !== "admin") {
    return (
      <AdminShell
        activeTab="rag-ingestion"
        title={t(language, "admin.ragIngestion.title")}
        description={t(language, "admin.ragIngestion.description")}
      >
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 py-6 text-center"
        >
          <p className="text-base font-semibold text-[color:var(--status-danger-text)]">
            {t(language, "admin.ragIngestion.accessDenied")}
          </p>
          <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">
            {t(language, "admin.ragIngestion.accessDeniedDescription")}
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell
      activeTab="rag-ingestion"
      title={t(language, "admin.ragIngestion.title")}
      description={t(language, "admin.ragIngestion.description")}
    >
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="RAG Ingestion Monitor"
        data-density="DENSE"
        className="space-y-5"
      >
        {/* Corpus Statistics (Spec 6.69 Top Bar) */}
        <AsyncSection<CorpusStats>
          state={statsState}
          loadingLabel={t(language, "admin.ragIngestion.statsLoading")}
          emptyTitle={t(language, "admin.ragIngestion.statsEmptyTitle")}
          emptyDescription={t(language, "admin.ragIngestion.statsEmptyDescription")}
        >
          {(corpus) => <CorpusStatsPanel stats={corpus} language={language} />}
        </AsyncSection>

        {/* Filter Toolbar */}
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">{language === "vi" ? "Nguồn:" : "Source:"}</span>
                <select
                  aria-label="Filter Source"
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="all">{language === "vi" ? "Tất cả nguồn" : "All Sources"}</option>
                  {(sources ?? []).map((s) => (
                    <option key={s.source_key} value={s.source_key}>
                      {s.display_name || s.source_key}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">{language === "vi" ? "Trạng thái:" : "Status:"}</span>
                <select
                  aria-label="Filter Status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="all">{language === "vi" ? "Tất cả" : "All"}</option>
                  <option value="enabled">{language === "vi" ? "Đang bật" : "Enabled"}</option>
                  <option value="disabled">{language === "vi" ? "Đang tắt" : "Disabled"}</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder={language === "vi" ? "Tìm theo tên nguồn / source key..." : "Search source..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="min-h-[34px] w-48 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] focus-visible:outline-none sm:w-64"
              />
              <Button
                variant="secondary"
                size="sm"
                icon="refresh"
                onClick={() => {
                  void loadSources();
                  void loadStats();
                }}
                disabled={isRefreshing}
              >
                {isRefreshing ? t(language, "admin.ragIngestion.refreshing") : t(language, "admin.ragIngestion.refresh")}
              </Button>
            </div>
          </div>
        </div>

        {/* Main Split: Jobs/Sources Table + Stage Inspector */}
        <div className="grid grid-cols-12 gap-5">
          {/* Dense Sources & ETL Trigger Table */}
          <div className={selectedJob ? "col-span-12 xl:col-span-7" : "col-span-12"}>
            <PanelCard
              title={t(language, "admin.ragIngestion.sources")}
              description={t(language, "admin.ragIngestion.sourcesDescription")}
            >
              {sourcesDegraded ? (
                <div
                  role="alert"
                  className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
                >
                  {t(language, "admin.ragIngestion.degradedSources")}
                </div>
              ) : null}

              <AsyncSection<RagSource[]>
                state={sourcesState}
                loadingLabel={t(language, "admin.ragIngestion.sourcesLoading")}
                emptyTitle={t(language, "admin.ragIngestion.sourcesEmptyTitle")}
                emptyDescription={t(language, "admin.ragIngestion.sourcesEmptyDescription")}
              >
                {() => (
                  <SourcesTable
                    sources={filteredSources}
                    runningSourceKey={runningSourceKey}
                    onRun={onRunIngestion}
                    onSelectJob={(s) => {
                      const matched = jobHistory.find((j) => j.source_key === s.source_key) ?? {
                        job_id: `inspect-${s.source_key}`,
                        source_key: s.source_key,
                        status: s.last_run_at ? "completed" : "idle",
                        fetched: 0,
                        inserted: 0,
                        updated: 0,
                        skipped: 0,
                        degraded: 0,
                        errors: [],
                      };
                      setSelectedJob(matched);
                    }}
                    language={language}
                  />
                )}
              </AsyncSection>
            </PanelCard>
          </div>

          {/* Selected Job Stage Inspector Drawer */}
          {selectedJob ? (
            <div className="col-span-12 xl:col-span-5">
              <JobStageInspector
                job={selectedJob}
                error={jobError}
                onClose={() => setSelectedJob(null)}
                language={language}
              />
            </div>
          ) : null}
        </div>
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CorpusStatsPanel({ stats, language }: { stats: CorpusStats; language: UILanguage }) {
  const degraded = stats.degraded_chunks > 0;
  return (
    <PanelCard
      title={t(language, "admin.ragIngestion.statsTitle")}
      description={t(language, "admin.ragIngestion.statsDescription")}
    >
      {degraded ? (
        <div
          role="alert"
          className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3"
        >
          <p className="text-sm font-semibold text-[color:var(--status-danger-text)]">
            {t(language, "admin.ragIngestion.degradedTitle")}
          </p>
          <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">
            {t(language, "admin.ragIngestion.degradedDescription", {
              count: formatCount(stats.degraded_chunks, language),
            })}
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={t(language, "admin.ragIngestion.documents")}
          value={formatCount(stats.documents, language)}
          hint={t(language, "admin.ragIngestion.documentsHint")}
        />
        <KpiCard
          label={t(language, "admin.ragIngestion.chunks")}
          value={formatCount(stats.chunks, language)}
          hint={t(language, "admin.ragIngestion.chunksHint")}
        />
        <KpiCard
          label={t(language, "admin.ragIngestion.degradedChunks")}
          value={formatCount(stats.degraded_chunks, language)}
          hint={
            degraded
              ? t(language, "admin.ragIngestion.needsAttention")
              : t(language, "admin.ragIngestion.noDegraded")
          }
        />
        <KpiCard
          label={t(language, "admin.ragIngestion.coverage")}
          value={formatPercent(stats.coverage_pct)}
          hint={t(language, "admin.ragIngestion.coverageHint")}
        />
      </div>
    </PanelCard>
  );
}

function JobStageInspector({
  job,
  error,
  onClose,
  language,
}: {
  job: IngestionStatus;
  error: string;
  onClose: () => void;
  language: UILanguage;
}) {
  const failed = isFailureStatus(job.status);
  const running = !isTerminalStatus(job.status);

  return (
    <div className="rounded-[var(--radius-lg)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-[var(--text-primary)]">
              {job.source_key}
            </span>
            <span
              className={[
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold",
                failed
                  ? "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[color:var(--status-danger-text)]"
                  : running
                    ? "border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[color:var(--status-warn-text)]"
                    : "border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[color:var(--status-ok-text)]",
              ].join(" ")}
            >
              {running ? (
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                />
              ) : null}
              {statusLabel(job.status, language)}
            </span>
          </div>
          <p className="mt-1 font-mono text-[11px] text-[var(--text-muted)]">
            Job ID: {job.job_id}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon="close"
          aria-label="Close Inspector"
          onClick={onClose}
        />
      </div>

      {error ? (
        <div className="mt-3 rounded-md border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[color:var(--status-danger-text)]">
          {error}
        </div>
      ) : null}

      <div className="mt-4 space-y-4">
        {/* Stage Progression Steps (Spec 6.69 #4) */}
        <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            {language === "vi" ? "Tiến trình các giai đoạn ETL" : "ETL Pipeline Stages"}
          </p>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
            <div className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
              <span className="text-[10px] font-bold text-[var(--text-muted)]">1. Fetch</span>
              <p className="mt-1 font-bold text-[var(--text-primary)]">{formatCount(job.fetched, language)}</p>
            </div>
            <div className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
              <span className="text-[10px] font-bold text-[var(--text-muted)]">2. Insert</span>
              <p className="mt-1 font-bold text-[var(--text-primary)]">{formatCount(job.inserted, language)}</p>
            </div>
            <div className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
              <span className="text-[10px] font-bold text-[var(--text-muted)]">3. Update</span>
              <p className="mt-1 font-bold text-[var(--text-primary)]">{formatCount(job.updated, language)}</p>
            </div>
            <div className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
              <span className="text-[10px] font-bold text-[var(--text-muted)]">4. Degraded</span>
              <p className={["mt-1 font-bold", job.degraded > 0 ? "text-[color:var(--status-danger-text)]" : "text-[var(--text-primary)]"].join(" ")}>
                {formatCount(job.degraded, language)}
              </p>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
            <dt className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {t(language, "admin.ragIngestion.skipped")}
            </dt>
            <dd className="mt-1 font-bold text-[var(--text-primary)]">
              {formatCount(job.skipped, language)}
            </dd>
          </div>
          <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
            <dt className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              {language === "vi" ? "Số lỗi ghi nhận" : "Error Count"}
            </dt>
            <dd className={["mt-1 font-bold", (job.errors?.length ?? 0) > 0 ? "text-[color:var(--status-danger-text)]" : "text-[var(--text-primary)]"].join(" ")}>
              {formatCount(job.errors?.length ?? 0, language)}
            </dd>
          </div>
        </dl>

        {/* Raw Errors / Logs Lazy Section (Spec 6.69 #6) */}
        {Array.isArray(job.errors) && job.errors.length > 0 ? (
          <div className="rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[color:var(--status-danger-text)]">
            <p className="font-bold">{t(language, "admin.ragIngestion.jobErrors", { count: formatCount(job.errors.length, language) })}</p>
            <pre className="mt-2 max-h-32 overflow-y-auto font-mono text-[10px]">
              {JSON.stringify(job.errors, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SourcesTable({
  sources,
  runningSourceKey,
  onRun,
  onSelectJob,
  language,
}: {
  sources: RagSource[];
  runningSourceKey: string | null;
  onRun: (source: RagSource) => void;
  onSelectJob: (source: RagSource) => void;
  language: UILanguage;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.source")}</th>
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.trustTier")}</th>
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.fetchMode")}</th>
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.watermark")}</th>
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.lastRun")}</th>
            <th className="py-2.5 pr-3 font-semibold">{t(language, "admin.ragIngestion.status")}</th>
            <th className="py-2.5 text-right font-semibold">{t(language, "admin.ragIngestion.action")}</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source, index) => {
            const key = source.source_key || (source.id != null ? String(source.id) : `src-${index}`);
            const isRunning = runningSourceKey === source.source_key;
            const isDisabled = Boolean(runningSourceKey) || !source.enabled;
            return (
              <tr
                key={key}
                onClick={() => onSelectJob(source)}
                className="cursor-pointer border-b border-[color:var(--shell-border)] align-top transition last:border-0 hover:bg-[var(--surface-muted)]"
              >
                <td className="py-2.5 pr-3">
                  <p className="font-semibold text-[var(--text-primary)]">
                    {source.display_name || source.source_key}
                  </p>
                  <p className="font-mono text-[10px] text-[var(--text-muted)]">{source.source_key}</p>
                </td>
                <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                  {trustTierLabel(source.trust_tier, language)}
                </td>
                <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                  {fetchModeLabel(source.fetch_mode, language)}
                </td>
                <td className="py-2.5 pr-3">
                  <code className="break-all font-mono text-[10px] text-[var(--text-secondary)]">
                    {source.last_watermark?.trim() ? source.last_watermark : t(language, "admin.ragIngestion.noData")}
                  </code>
                </td>
                <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                  {formatDate(source.last_run_at, language)}
                </td>
                <td className="py-2.5 pr-3">
                  <span
                    className={[
                      "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                      source.enabled
                        ? "bg-[var(--status-ok-bg)] text-[color:var(--status-ok-text)]"
                        : "bg-[var(--surface-muted)] text-[var(--text-muted)]",
                    ].join(" ")}
                  >
                    {source.enabled ? t(language, "admin.ragIngestion.enabled") : t(language, "admin.ragIngestion.disabled")}
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => onSelectJob(source)}
                      className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                    >
                      {language === "vi" ? "Kiểm tra" : "Inspect"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onRun(source)}
                      disabled={isDisabled}
                      title={
                        !source.enabled
                          ? t(language, "admin.ragIngestion.disabledTitle")
                          : t(language, "admin.ragIngestion.runTitle")
                      }
                      className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] bg-[var(--brand-600)] px-2.5 py-1 text-[11px] font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isRunning ? (
                        <span
                          aria-hidden="true"
                          className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-white border-t-transparent"
                        />
                      ) : null}
                      {isRunning ? t(language, "admin.ragIngestion.running") : t(language, "admin.ragIngestion.run")}
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
