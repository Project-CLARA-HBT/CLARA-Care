"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import api from "@/lib/http-client";
import { getRole, type UserRole } from "@/lib/auth-store";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * RAG ingestion admin surface (Requirement 13.3).
 *
 * Vietnamese-only admin page that drives the offline ingestion plane through
 * the RBAC `/admin/rag/*` endpoints (task 10.1):
 *   - GET  /admin/rag/sources                    — source registry + watermarks
 *   - POST /admin/rag/ingestion/run              — trigger ingestion for a source
 *   - GET  /admin/rag/ingestion/status/{job_id}  — poll a running job
 *   - GET  /admin/rag/stats                       — corpus stats + degraded count
 *
 * Every async region renders through one of the four mutually-exclusive
 * AsyncSection states (loading / empty / error / populated). Error copy is
 * routed through `sanitizeUpstreamError` so no raw upstream detail reaches the
 * admin view. All styling uses design tokens; all user-facing copy is in
 * Vietnamese. The page is admin-only (reuses the `getRole()` gate convention).
 */

// ---------------------------------------------------------------------------
// API shapes — mirror the Pydantic models in admin_rag.py (snake_case kept 1:1)
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

type IngestionStatus = {
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
// Typed fetchers over the admin axios client (baseURL already ends in /api/v1)
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
    source_key: sourceKey
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
// Display helpers (Vietnamese)
// ---------------------------------------------------------------------------

function formatCount(value: number | null | undefined, language: UILanguage): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat(language === "vi" ? "vi-VN" : "en-US", { maximumFractionDigits: 0 }).format(Math.max(0, value));
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

/** Authority tier → Vietnamese label (1 = cao nhất). */
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
    unknown: "admin.ragIngestion.status.unknown"
  };
  return labels[key] ? t(language, labels[key]) : status || t(language, "admin.ragIngestion.status.unknown");
}

const TERMINAL_STATUSES = new Set([
  "completed",
  "done",
  "success",
  "failed",
  "error",
  "unavailable",
  "cancelled"
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
  // Admin-only gate — reuse the stored-role convention used elsewhere.
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
  const [jobError, setJobError] = useState("");

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

  // Clear any pending poll timer on unmount.
  useEffect(() => stopPolling, [stopPolling]);

  const pollJob = useCallback(
    async (jobId: string) => {
      try {
        const status = await fetchJobStatus(jobId);
        setActiveJob(status);
        if (isTerminalStatus(status.status)) {
          setRunningSourceKey(null);
          stopPolling();
          // Refresh registry + corpus stats once a run settles.
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
          job_id: result.job_id ?? "",
          source_key: result.source_key || source.source_key,
          status: result.status || (result.accepted ? "queued" : "unavailable"),
          fetched: 0,
          inserted: 0,
          updated: 0,
          skipped: 0,
          degraded: 0,
          errors: []
        };
        setActiveJob(baseJob);

        if (!result.accepted || !result.job_id) {
          // ML plane unavailable or run rejected — surface the state, no polling.
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

  const isRefreshing = sourcesLoading || statsLoading;

  // Avoid a hydration flash before the stored role is known.
  if (!hydrated) {
    return (
      <AdminShell
        activeTab="knowledge-sources"
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
        activeTab="knowledge-sources"
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
      activeTab="knowledge-sources"
      title={t(language, "admin.ragIngestion.title")}
      description={t(language, "admin.ragIngestion.description")}
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-[var(--text-muted)]">
            {t(language, "admin.ragIngestion.intro")}
          </p>
          <button
            type="button"
            onClick={() => {
              void loadSources();
              void loadStats();
            }}
            disabled={isRefreshing}
            className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:opacity-60"
          >
            {isRefreshing ? t(language, "admin.ragIngestion.refreshing") : t(language, "admin.ragIngestion.refresh")}
          </button>
        </div>

        {/* Corpus statistics + degraded-mode alert (Req 13.3) */}
        <AsyncSection<CorpusStats>
          state={statsState}
          loadingLabel={t(language, "admin.ragIngestion.statsLoading")}
          emptyTitle={t(language, "admin.ragIngestion.statsEmptyTitle")}
          emptyDescription={t(language, "admin.ragIngestion.statsEmptyDescription")}
        >
          {(corpus) => <CorpusStatsPanel stats={corpus} language={language} />}
        </AsyncSection>

        {/* Active ingestion job status */}
        <JobStatusPanel job={activeJob} error={jobError} language={language} />

        {/* Source registry table + per-source ingestion trigger */}
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
            {(rows) => (
              <SourcesTable
                sources={rows}
                runningSourceKey={runningSourceKey}
                onRun={onRunIngestion}
                language={language}
              />
            )}
          </AsyncSection>
        </PanelCard>
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Sub-components (local, single-file)
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
            {t(language, "admin.ragIngestion.degradedDescription", { count: formatCount(stats.degraded_chunks, language) })}
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t(language, "admin.ragIngestion.documents")} value={formatCount(stats.documents, language)} hint={t(language, "admin.ragIngestion.documentsHint")} />
        <KpiCard label={t(language, "admin.ragIngestion.chunks")} value={formatCount(stats.chunks, language)} hint={t(language, "admin.ragIngestion.chunksHint")} />
        <KpiCard
          label={t(language, "admin.ragIngestion.degradedChunks")}
          value={formatCount(stats.degraded_chunks, language)}
          hint={degraded ? t(language, "admin.ragIngestion.needsAttention") : t(language, "admin.ragIngestion.noDegraded")}
        />
        <KpiCard
          label={t(language, "admin.ragIngestion.coverage")}
          value={formatPercent(stats.coverage_pct)}
          hint={t(language, "admin.ragIngestion.coverageHint")}
        />
      </div>

      <p className="mt-4 text-xs text-[var(--text-muted)]">
        {t(language, "admin.ragIngestion.enabledSources", { enabled: formatCount(stats.sources_enabled, language), total: formatCount(stats.sources_total, language) })}
      </p>
    </PanelCard>
  );
}

function JobStatusPanel({ job, error, language }: { job: IngestionStatus | null; error: string; language: UILanguage }) {
  if (error) {
    return (
      <div
        role="alert"
        className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 py-4"
      >
        <p className="text-sm font-semibold text-[color:var(--status-danger-text)]">
          {t(language, "admin.ragIngestion.jobError")}
        </p>
        <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <PanelCard
        title={t(language, "admin.ragIngestion.jobTitle")}
        description={t(language, "admin.ragIngestion.jobEmptyDescription")}
      >
        <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.ragIngestion.noJob")}</p>
      </PanelCard>
    );
  }

  const failed = isFailureStatus(job.status);
  const running = !isTerminalStatus(job.status);

  return (
    <PanelCard
      title={t(language, "admin.ragIngestion.jobTitle")}
      description={job.job_id ? t(language, "admin.ragIngestion.jobSourceWithId", { source: job.source_key, jobId: job.job_id }) : t(language, "admin.ragIngestion.jobSource", { source: job.source_key })}
    >
      <div className="flex items-center gap-2">
        <span
          className={[
            "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold",
            failed
              ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[color:var(--status-danger-text)]"
              : running
                ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[color:var(--status-warn-text)]"
                : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[color:var(--status-ok-text)]"
          ].join(" ")}
        >
          {running ? (
            <span
              aria-hidden="true"
              className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
            />
          ) : null}
          {statusLabel(job.status, language)}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <JobMetric label={t(language, "admin.ragIngestion.fetched")} value={job.fetched} language={language} />
        <JobMetric label={t(language, "admin.ragIngestion.inserted")} value={job.inserted} language={language} />
        <JobMetric label={t(language, "admin.ragIngestion.updated")} value={job.updated} language={language} />
        <JobMetric label={t(language, "admin.ragIngestion.skipped")} value={job.skipped} language={language} />
        <JobMetric label={t(language, "admin.ragIngestion.degraded")} value={job.degraded} language={language} tone={job.degraded > 0 ? "danger" : "default"} />
      </dl>

      {job.degraded > 0 ? (
        <p className="mt-3 text-xs font-medium text-[color:var(--status-danger-text)]">
          {t(language, "admin.ragIngestion.jobDegraded", { count: formatCount(job.degraded, language) })}
        </p>
      ) : null}

      {Array.isArray(job.errors) && job.errors.length > 0 ? (
        <p className="mt-3 text-xs text-[color:var(--status-danger-text)]">
          {t(language, "admin.ragIngestion.jobErrors", { count: formatCount(job.errors.length, language) })}
        </p>
      ) : null}
    </PanelCard>
  );
}

function JobMetric({
  label,
  value,
  language,
  tone = "default"
}: {
  label: string;
  value: number;
  language: UILanguage;
  tone?: "default" | "danger";
}) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        {label}
      </dt>
      <dd
        className={[
          "mt-1 text-lg font-bold",
          tone === "danger"
            ? "text-[color:var(--status-danger-text)]"
            : "text-[var(--text-primary)]"
        ].join(" ")}
      >
        {formatCount(value, language)}
      </dd>
    </div>
  );
}

function SourcesTable({
  sources,
  runningSourceKey,
  onRun,
  language
}: {
  sources: RagSource[];
  runningSourceKey: string | null;
  onRun: (source: RagSource) => void;
  language: UILanguage;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.source")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.trustTier")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.fetchMode")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.watermark")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.lastRun")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragIngestion.status")}</th>
            <th className="py-2 font-semibold text-right">{t(language, "admin.ragIngestion.action")}</th>
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
                className="border-b border-[color:var(--shell-border)] align-top last:border-0"
              >
                <td className="py-3 pr-4">
                  <p className="font-semibold text-[var(--text-primary)]">
                    {source.display_name || source.source_key}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">{source.source_key}</p>
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {trustTierLabel(source.trust_tier, language)}
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {fetchModeLabel(source.fetch_mode, language)}
                </td>
                <td className="py-3 pr-4">
                  <code className="break-all text-xs text-[var(--text-secondary)]">
                    {source.last_watermark?.trim() ? source.last_watermark : t(language, "admin.ragIngestion.noData")}
                  </code>
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {formatDate(source.last_run_at, language)}
                </td>
                <td className="py-3 pr-4">
                  <span
                    className={[
                      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                      source.enabled
                        ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[color:var(--status-ok-text)]"
                        : "border-[color:var(--status-neutral-border)] bg-[var(--status-neutral-bg)] text-[color:var(--status-neutral-text)]"
                    ].join(" ")}
                  >
                    {source.enabled ? t(language, "admin.ragIngestion.enabled") : t(language, "admin.ragIngestion.disabled")}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onRun(source)}
                    disabled={isDisabled}
                    title={
                      !source.enabled
                        ? t(language, "admin.ragIngestion.disabledTitle")
                        : t(language, "admin.ragIngestion.runTitle")
                    }
                    className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--brand-600)] px-3 py-2 text-xs font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isRunning ? (
                      <span
                        aria-hidden="true"
                        className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent"
                      />
                    ) : null}
                    {isRunning ? t(language, "admin.ragIngestion.running") : t(language, "admin.ragIngestion.run")}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
