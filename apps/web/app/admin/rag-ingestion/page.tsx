"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import api from "@/lib/http-client";
import { getRole, type UserRole } from "@/lib/auth-store";
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

const COUNT_FORMATTER = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return COUNT_FORMATTER.format(Math.max(0, value));
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.max(0, value).toFixed(1)}%`;
}

function formatDate(value?: string | null): string {
  if (!value) return "Chưa chạy";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN", { hour12: false });
}

/** Authority tier → Vietnamese label (1 = cao nhất). */
function trustTierLabel(tier: number | null | undefined): string {
  switch (tier) {
    case 1:
      return "Bậc 1 · Cơ quan quản lý / nhãn thuốc";
    case 2:
      return "Bậc 2 · Hướng dẫn lâm sàng";
    case 3:
      return "Bậc 3 · Tài liệu bình duyệt";
    case 4:
      return "Bậc 4 · Nguồn bổ sung";
    default:
      return "Chưa phân bậc";
  }
}

function fetchModeLabel(mode: string): string {
  const key = (mode ?? "").trim().toLowerCase();
  if (key === "api") return "API";
  if (key === "crawl") return "Thu thập web";
  return mode || "--";
}

const STATUS_LABELS: Record<string, string> = {
  queued: "Đang chờ",
  pending: "Đang chờ",
  running: "Đang chạy",
  in_progress: "Đang chạy",
  completed: "Hoàn tất",
  done: "Hoàn tất",
  success: "Hoàn tất",
  failed: "Thất bại",
  error: "Lỗi",
  unavailable: "Không khả dụng",
  cancelled: "Đã hủy",
  unknown: "Không xác định"
};

function statusLabel(status: string): string {
  const key = (status ?? "").trim().toLowerCase();
  return STATUS_LABELS[key] ?? status ?? "Không xác định";
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
        title="Thu thập tri thức (RAG)"
        description="Kích hoạt và theo dõi luồng thu thập tri thức ngoại tuyến."
      >
        <AsyncSection<null>
          state={{ kind: "loading" }}
          loadingLabel="Đang kiểm tra quyền truy cập..."
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
        title="Thu thập tri thức (RAG)"
        description="Kích hoạt và theo dõi luồng thu thập tri thức ngoại tuyến."
      >
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 py-6 text-center"
        >
          <p className="text-base font-semibold text-[color:var(--status-danger-text)]">
            Bạn không có quyền truy cập
          </p>
          <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">
            Trang quản trị thu thập tri thức chỉ dành cho quản trị viên.
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell
      activeTab="knowledge-sources"
      title="Thu thập tri thức (RAG)"
      description="Kích hoạt và theo dõi luồng thu thập tri thức ngoại tuyến."
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-[var(--text-muted)]">
            Quản lý các nguồn, kích hoạt thu thập theo từng nguồn và theo dõi trạng thái cùng cảnh
            báo chế độ suy giảm.
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
            {isRefreshing ? "Đang làm mới..." : "Làm mới"}
          </button>
        </div>

        {/* Corpus statistics + degraded-mode alert (Req 13.3) */}
        <AsyncSection<CorpusStats>
          state={statsState}
          loadingLabel="Đang tải thống kê kho tri thức..."
          emptyTitle="Chưa có thống kê kho tri thức"
          emptyDescription="Hiện chưa có số liệu kho tri thức để hiển thị."
        >
          {(corpus) => <CorpusStatsPanel stats={corpus} />}
        </AsyncSection>

        {/* Active ingestion job status */}
        <JobStatusPanel job={activeJob} error={jobError} />

        {/* Source registry table + per-source ingestion trigger */}
        <PanelCard
          title="Nguồn tri thức"
          description="Bậc tin cậy, chế độ thu thập, watermark gần nhất và trạng thái kích hoạt của từng nguồn."
        >
          {sourcesDegraded ? (
            <div
              role="alert"
              className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
            >
              Dịch vụ xử lý tạm thời không khả dụng — danh sách nguồn có thể chưa đầy đủ. Vui lòng
              thử lại sau ít phút.
            </div>
          ) : null}

          <AsyncSection<RagSource[]>
            state={sourcesState}
            loadingLabel="Đang tải danh sách nguồn..."
            emptyTitle="Chưa có nguồn nào"
            emptyDescription="Chưa có nguồn tri thức nào được đăng ký trong hệ thống."
          >
            {(rows) => (
              <SourcesTable
                sources={rows}
                runningSourceKey={runningSourceKey}
                onRun={onRunIngestion}
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

function CorpusStatsPanel({ stats }: { stats: CorpusStats }) {
  const degraded = stats.degraded_chunks > 0;
  return (
    <PanelCard
      title="Thống kê kho tri thức"
      description="Tổng quan tài liệu, đoạn văn bản và độ phủ của kho tri thức hiện tại."
    >
      {degraded ? (
        <div
          role="alert"
          className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3"
        >
          <p className="text-sm font-semibold text-[color:var(--status-danger-text)]">
            Cảnh báo chế độ suy giảm
          </p>
          <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">
            Có {formatCount(stats.degraded_chunks)} đoạn được lưu ở chế độ suy giảm (embedding dự
            phòng). Cần kiểm tra dịch vụ embedding và thu thập lại các nguồn bị ảnh hưởng.
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Tài liệu" value={formatCount(stats.documents)} hint="Số tài liệu đã thu thập" />
        <KpiCard label="Đoạn văn bản" value={formatCount(stats.chunks)} hint="Số chunk đã lập chỉ mục" />
        <KpiCard
          label="Đoạn suy giảm"
          value={formatCount(stats.degraded_chunks)}
          hint={degraded ? "Cần xử lý" : "Không có đoạn suy giảm"}
        />
        <KpiCard
          label="Độ phủ"
          value={formatPercent(stats.coverage_pct)}
          hint="Tỉ lệ độ phủ kho tri thức"
        />
      </div>

      <p className="mt-4 text-xs text-[var(--text-muted)]">
        Nguồn đã kích hoạt: {formatCount(stats.sources_enabled)} / {formatCount(stats.sources_total)}
      </p>
    </PanelCard>
  );
}

function JobStatusPanel({ job, error }: { job: IngestionStatus | null; error: string }) {
  if (error) {
    return (
      <div
        role="alert"
        className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 py-4"
      >
        <p className="text-sm font-semibold text-[color:var(--status-danger-text)]">
          Không thể thực hiện thu thập
        </p>
        <p className="mt-1 text-sm text-[color:var(--status-danger-text)]">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <PanelCard
        title="Trạng thái thu thập"
        description="Chọn một nguồn bên dưới và nhấn “Chạy thu thập” để bắt đầu."
      >
        <p className="text-sm text-[var(--text-muted)]">Chưa có tác vụ thu thập nào đang chạy.</p>
      </PanelCard>
    );
  }

  const failed = isFailureStatus(job.status);
  const running = !isTerminalStatus(job.status);

  return (
    <PanelCard
      title="Trạng thái thu thập"
      description={`Nguồn: ${job.source_key}${job.job_id ? ` · Mã tác vụ: ${job.job_id}` : ""}`}
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
          {statusLabel(job.status)}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <JobMetric label="Đã lấy" value={job.fetched} />
        <JobMetric label="Đã thêm" value={job.inserted} />
        <JobMetric label="Đã cập nhật" value={job.updated} />
        <JobMetric label="Đã bỏ qua" value={job.skipped} />
        <JobMetric label="Suy giảm" value={job.degraded} tone={job.degraded > 0 ? "danger" : "default"} />
      </dl>

      {job.degraded > 0 ? (
        <p className="mt-3 text-xs font-medium text-[color:var(--status-danger-text)]">
          Cảnh báo: tác vụ này tạo {formatCount(job.degraded)} đoạn ở chế độ suy giảm.
        </p>
      ) : null}

      {Array.isArray(job.errors) && job.errors.length > 0 ? (
        <p className="mt-3 text-xs text-[color:var(--status-danger-text)]">
          Có {formatCount(job.errors.length)} lỗi trong quá trình thu thập.
        </p>
      ) : null}
    </PanelCard>
  );
}

function JobMetric({
  label,
  value,
  tone = "default"
}: {
  label: string;
  value: number;
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
        {formatCount(value)}
      </dd>
    </div>
  );
}

function SourcesTable({
  sources,
  runningSourceKey,
  onRun
}: {
  sources: RagSource[];
  runningSourceKey: string | null;
  onRun: (source: RagSource) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
            <th className="py-2 pr-4 font-semibold">Nguồn</th>
            <th className="py-2 pr-4 font-semibold">Bậc tin cậy</th>
            <th className="py-2 pr-4 font-semibold">Chế độ thu thập</th>
            <th className="py-2 pr-4 font-semibold">Watermark gần nhất</th>
            <th className="py-2 pr-4 font-semibold">Lần chạy gần nhất</th>
            <th className="py-2 pr-4 font-semibold">Trạng thái</th>
            <th className="py-2 font-semibold text-right">Hành động</th>
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
                  {trustTierLabel(source.trust_tier)}
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {fetchModeLabel(source.fetch_mode)}
                </td>
                <td className="py-3 pr-4">
                  <code className="break-all text-xs text-[var(--text-secondary)]">
                    {source.last_watermark?.trim() ? source.last_watermark : "Chưa có"}
                  </code>
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {formatDate(source.last_run_at)}
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
                    {source.enabled ? "Đang bật" : "Đã tắt"}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onRun(source)}
                    disabled={isDisabled}
                    title={
                      !source.enabled
                        ? "Nguồn đang tắt — không thể thu thập"
                        : "Kích hoạt thu thập cho nguồn này"
                    }
                    className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--brand-600)] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isRunning ? (
                      <span
                        aria-hidden="true"
                        className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent"
                      />
                    ) : null}
                    {isRunning ? "Đang chạy..." : "Chạy thu thập"}
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
