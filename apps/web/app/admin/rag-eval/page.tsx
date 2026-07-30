"use client";

import { useCallback, useMemo, useState } from "react";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import { KpiCard, PanelCard, TrendBars } from "@/components/admin/analytics-primitives";
import api from "@/lib/http-client";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
import { aggregateEvalTrends, type EvalRunSummary } from "./eval-dashboard";

/**
 * Bảng đánh giá RAG (rag-eval) — Admin_Web_Surface (Yêu cầu 11.5).
 *
 * Quản trị viên chạy bộ đánh giá golden VN Q&A và xem các chỉ số chất lượng
 * truy xuất / trả lời: recall@k, nDCG@k, độ trung thực (faithfulness) và độ
 * chính xác trích dẫn (citation accuracy). Bảng hiển thị chỉ số tổng hợp, xu
 * hướng qua nhiều lần chạy (khi có), và bảng kết quả theo từng câu hỏi — toàn
 * bộ qua bốn trạng thái loại trừ lẫn nhau của AsyncSection.
 *
 * Trang gọi Admin_API đã được bảo vệ RBAC (`require_roles("admin")` phía server,
 * trả 403 cho token không phải admin / 401 khi thiếu token):
 *   - POST /api/v1/admin/rag/eval/run            → khởi chạy, trả về run_id
 *   - GET  /api/v1/admin/rag/eval/results/{run_id} → chỉ số tổng hợp + theo qid
 *
 * Styling dùng design token dùng chung với các dashboard admin khác; mọi copy
 * hướng tới người dùng đều bằng tiếng Việt.
 */

// ---------------------------------------------------------------------------
// Hình dạng dữ liệu (giữ nguyên snake_case theo schema của Admin_API)
// ---------------------------------------------------------------------------

type EvalRunResponse = {
  run_id: string;
  status: string;
  accepted: boolean;
  ml_available?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

type EvalResultItem = {
  qid: string;
  recall_at_k: number;
  ndcg_at_k: number;
  faithfulness: number;
  citation_acc: number;
  latency_ms: number;
};

type EvalResultsResponse = {
  run_id: string;
  results: EvalResultItem[];
  recall_at_k: number;
  ndcg_at_k: number;
  faithfulness: number;
  citation_acc: number;
  ml_available?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

// `EvalRunSummary` (chỉ số tổng hợp của một lần chạy, tích luỹ phía client để
// vẽ xu hướng) và phép gộp xu hướng được tách sang `./eval-dashboard` để kiểm
// thử thuần (pure) độc lập với phần render.

// ---------------------------------------------------------------------------
// Hàm định dạng hiển thị
// ---------------------------------------------------------------------------

/** Định dạng giá trị chỉ số trong [0,1] thành phần trăm, fallback `--`. */
function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const clamped = Math.min(1, Math.max(0, value));
  return `${(clamped * 100).toFixed(1)}%`;
}

/** Định dạng độ trễ (mili-giây) để hiển thị. */
function formatLatency(value: number | null | undefined, language: "vi" | "en"): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.max(0, Math.round(value)).toLocaleString(language === "vi" ? "vi-VN" : "en-US")} ms`;
}

/** Chuẩn hoá [0,1] về thang 0–100 cho chiều cao cột xu hướng. */
function toPercentPoint(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.round(Math.min(1, Math.max(0, value)) * 100);
}

// ---------------------------------------------------------------------------
// Trang
// ---------------------------------------------------------------------------

export default function AdminRagEvalPage() {
  const language = useUILanguage();
  const [k, setK] = useState(10);
  const [runId, setRunId] = useState("");
  const [results, setResults] = useState<EvalResultsResponse | null>(null);
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const fetchResults = useCallback(async (id: string) => {
    setIsLoadingResults(true);
    setError("");
    try {
      const { data } = await api.get<EvalResultsResponse>(
        `/admin/rag/eval/results/${encodeURIComponent(id)}`
      );
      if (data.ml_available === false || data.fallback) {
        setNotice(
          t(language, "admin.ragEval.unavailable")
        );
      }
      setResults(data);
      if (Array.isArray(data.results) && data.results.length > 0) {
        setRuns((prev) =>
          aggregateEvalTrends(prev, {
            run_id: data.run_id,
            recall_at_k: data.recall_at_k,
            ndcg_at_k: data.ndcg_at_k,
            faithfulness: data.faithfulness,
            citation_acc: data.citation_acc
          })
        );
      }
    } catch (cause) {
      setResults(null);
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : t(language, "admin.ragEval.loadError")
        )
      );
    } finally {
      setIsLoadingResults(false);
    }
  }, [language]);

  const onRunEval = useCallback(async () => {
    if (isRunning) return;
    setIsRunning(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.post<EvalRunResponse>("/admin/rag/eval/run", { k });
      if (data.ml_available === false || !data.accepted || !data.run_id) {
        setNotice(
          t(language, "admin.ragEval.startUnavailable")
        );
        return;
      }
      setRunId(data.run_id);
      await fetchResults(data.run_id);
    } catch (cause) {
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : t(language, "admin.ragEval.startError")
        )
      );
    } finally {
      setIsRunning(false);
    }
  }, [isRunning, k, fetchResults, language]);

  const onReloadResults = useCallback(() => {
    if (!runId) return;
    void fetchResults(runId);
  }, [runId, fetchResults]);

  const state = useMemo<AsyncState<EvalResultsResponse>>(() => {
    if (isLoadingResults) return { kind: "loading" };
    if (error) return { kind: "error", message: error };
    if (!results || results.results.length === 0) return { kind: "empty" };
    return { kind: "populated", data: results };
  }, [isLoadingResults, error, results]);

  const showTrend = runs.length >= 2;

  return (
    <div className="space-y-5">
      <header className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">{t(language, "admin.ragEval.title")}</h1>
            <p className="mt-1 max-w-2xl text-sm text-[var(--text-secondary)]">
              {t(language, "admin.ragEval.description")}
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                {t(language, "admin.ragEval.k")}
              </span>
              <input
                type="number"
                min={1}
                max={100}
                value={k}
                disabled={isRunning}
                onChange={(event) => {
                  const parsed = Number(event.target.value);
                  if (Number.isFinite(parsed)) {
                    setK(Math.max(1, Math.min(100, Math.trunc(parsed))));
                  }
                }}
                className="w-20 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)]"
              />
            </label>

            <button
              type="button"
              onClick={() => void onRunEval()}
              disabled={isRunning}
              className="rounded-[var(--radius-md)] bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] focus-visible:ring-offset-2 disabled:opacity-60"
            >
              {isRunning ? t(language, "admin.ragEval.running") : t(language, "admin.ragEval.run")}
            </button>

            <button
              type="button"
              onClick={onReloadResults}
              disabled={!runId || isLoadingResults || isRunning}
              className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] disabled:opacity-50"
            >
              {t(language, "admin.ragEval.reload")}
            </button>
          </div>
        </div>

        {runId ? (
          <p className="mt-3 text-xs text-[var(--text-muted)]">
            {t(language, "admin.ragEval.latestRun", { runId })}
          </p>
        ) : null}
      </header>

      {notice ? (
        <p
          role="status"
          className="rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
        >
          {notice}
        </p>
      ) : null}

      <AsyncSection<EvalResultsResponse>
        state={state}
        loadingLabel={t(language, "admin.ragEval.loading")}
        emptyTitle={t(language, "admin.ragEval.emptyTitle")}
        emptyDescription={t(language, "admin.ragEval.emptyDescription")}
      >
        {(data) => (
          <RagEvalResults data={data} k={k} runs={runs} showTrend={showTrend} language={language} />
        )}
      </AsyncSection>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Nội dung kết quả (component cục bộ)
// ---------------------------------------------------------------------------

function RagEvalResults({
  data,
  k,
  runs,
  showTrend,
  language
}: {
  data: EvalResultsResponse;
  k: number;
  runs: EvalRunSummary[];
  showTrend: boolean;
  language: "vi" | "en";
}) {
  const runLabels = runs.map((_, index) => t(language, "admin.ragEval.runLabel", { index: index + 1 }));

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={`Recall@${k}`}
          value={formatRatio(data.recall_at_k)}
          hint={t(language, "admin.ragEval.recallHint")}
        />
        <KpiCard
          label={`nDCG@${k}`}
          value={formatRatio(data.ndcg_at_k)}
          hint={t(language, "admin.ragEval.ndcgHint")}
        />
        <KpiCard
          label={t(language, "admin.ragEval.faithfulness")}
          value={formatRatio(data.faithfulness)}
          hint={t(language, "admin.ragEval.faithfulnessHint")}
        />
        <KpiCard
          label={t(language, "admin.ragEval.citationAccuracy")}
          value={formatRatio(data.citation_acc)}
          hint={t(language, "admin.ragEval.citationHint")}
        />
      </div>

      {showTrend ? (
        <PanelCard
          title={t(language, "admin.ragEval.trends")}
          description={t(language, "admin.ragEval.trendsDescription", { count: runs.length })}
        >
          <div className="grid gap-5 lg:grid-cols-2">
            <TrendMetric
              title={`Recall@${k}`}
              labels={runLabels}
              values={runs.map((row) => row.recall_at_k)}
            />
            <TrendMetric
              title={`nDCG@${k}`}
              labels={runLabels}
              values={runs.map((row) => row.ndcg_at_k)}
            />
            <TrendMetric
              title={t(language, "admin.ragEval.faithfulness")}
              labels={runLabels}
              values={runs.map((row) => row.faithfulness)}
            />
            <TrendMetric
              title={t(language, "admin.ragEval.citationAccuracy")}
              labels={runLabels}
              values={runs.map((row) => row.citation_acc)}
            />
          </div>
        </PanelCard>
      ) : null}

      <PanelCard
        title={t(language, "admin.ragEval.questionResults")}
        description={t(language, "admin.ragEval.questionResultsDescription")}
      >
        {data.results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                  <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragEval.questionId")}</th>
                  <th className="py-2 pr-4 font-semibold">Recall@{k}</th>
                  <th className="py-2 pr-4 font-semibold">nDCG@{k}</th>
                  <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragEval.faithfulness")}</th>
                  <th className="py-2 pr-4 font-semibold">{t(language, "admin.ragEval.citationAccuracy")}</th>
                  <th className="py-2 font-semibold">{t(language, "admin.ragEval.latency")}</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((row) => (
                  <tr
                    key={row.qid}
                    className="border-b border-[color:var(--shell-border)] last:border-0"
                  >
                    <td className="py-2 pr-4 font-mono text-[var(--text-primary)]">{row.qid}</td>
                    <td className="py-2 pr-4 text-[var(--text-secondary)]">
                      {formatRatio(row.recall_at_k)}
                    </td>
                    <td className="py-2 pr-4 text-[var(--text-secondary)]">
                      {formatRatio(row.ndcg_at_k)}
                    </td>
                    <td className="py-2 pr-4 text-[var(--text-secondary)]">
                      {formatRatio(row.faithfulness)}
                    </td>
                    <td className="py-2 pr-4 text-[var(--text-secondary)]">
                      {formatRatio(row.citation_acc)}
                    </td>
                    <td className="py-2 text-[var(--text-secondary)]">
                      {formatLatency(row.latency_ms, language)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.ragEval.noRows")}</p>
        )}
      </PanelCard>
    </div>
  );
}

function TrendMetric({
  title,
  labels,
  values
}: {
  title: string;
  labels: string[];
  values: number[];
}) {
  const points = labels.map((label, index) => ({
    label,
    value: toPercentPoint(values[index])
  }));
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-[var(--text-secondary)]">{title}</p>
      <TrendBars points={points} />
    </div>
  );
}
