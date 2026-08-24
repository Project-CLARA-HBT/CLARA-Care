"use client";

import { useCallback, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import { KpiCard, PanelCard, TrendBars } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import api from "@/lib/http-client";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { aggregateEvalTrends, type EvalRunSummary } from "./eval-dashboard";

/**
 * Bảng đánh giá RAG (rag-eval) — Admin Evaluation Workbench (Spec v8 Section 12.12, Spec v5 Section 6.68, Yêu cầu 11.5).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: RAG Evaluation Workbench
 *
 * Quản trị viên chạy bộ đánh giá golden VN Q&A và xem các chỉ số chất lượng
 * truy xuất / trả lời: recall@k, nDCG@k, độ trung thực (faithfulness) và độ
 * chính xác trích dẫn (citation accuracy). Bảng hiển thị lịch sử benchmark runs,
 * xu hướng qua nhiều lần chạy, bảng kết quả theo từng câu hỏi, và question-level
 * error/sample inspector drawer.
 *
 * Trang gọi Admin_API đã được bảo vệ RBAC (`require_roles("admin")` phía server):
 *   - POST /api/v1/admin/rag/eval/run            → khởi chạy, trả về run_id
 *   - GET  /api/v1/admin/rag/eval/results/{run_id} → chỉ số tổng hợp + theo qid
 */

// ---------------------------------------------------------------------------
// Hình dạng dữ liệu
// ---------------------------------------------------------------------------

type EvalRunResponse = {
  run_id: string;
  status: string;
  accepted: boolean;
  ml_available?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

export type EvalResultItem = {
  qid: string;
  recall_at_k: number;
  ndcg_at_k: number;
  faithfulness: number;
  citation_acc: number;
  latency_ms: number;
  query_text?: string;
  expected_answer?: string;
  generated_answer?: string;
  retrieved_sources?: string[];
  failure_reason?: string;
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
  created_at?: string;
};

// ---------------------------------------------------------------------------
// Hàm định dạng hiển thị
// ---------------------------------------------------------------------------

function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const clamped = Math.min(1, Math.max(0, value));
  return `${(clamped * 100).toFixed(1)}%`;
}

function formatLatency(value: number | null | undefined, language: "vi" | "en"): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.max(0, Math.round(value)).toLocaleString(language === "vi" ? "vi-VN" : "en-US")} ms`;
}

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

  // Inspector & filter state
  const [selectedQuestion, setSelectedQuestion] = useState<EvalResultItem | null>(null);
  const [questionFilter, setQuestionFilter] = useState<"all" | "errors" | "low_faithfulness" | "low_recall">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchResults = useCallback(async (id: string) => {
    setIsLoadingResults(true);
    setError("");
    try {
      const { data } = await api.get<EvalResultsResponse>(
        `/admin/rag/eval/results/${encodeURIComponent(id)}`
      );
      if (data.ml_available === false || data.fallback) {
        setNotice(t(language, "admin.ragEval.unavailable"));
      }
      setResults(data);
      if (Array.isArray(data.results) && data.results.length > 0) {
        setRuns((prev) =>
          aggregateEvalTrends(prev, {
            run_id: data.run_id,
            recall_at_k: data.recall_at_k,
            ndcg_at_k: data.ndcg_at_k,
            faithfulness: data.faithfulness,
            citation_acc: data.citation_acc,
          })
        );
      }
      setSelectedQuestion((prev) => {
        if (!prev) return null;
        return data.results.find((q) => q.qid === prev.qid) ?? null;
      });
    } catch (cause) {
      setResults(null);
      setError(safeUserFacingError(cause, t(language, "admin.ragEval.loadError")));
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
        setNotice(t(language, "admin.ragEval.startUnavailable"));
        return;
      }
      setRunId(data.run_id);
      await fetchResults(data.run_id);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "admin.ragEval.startError")));
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
    <AdminShell
      activeTab="rag-eval"
      title={t(language, "admin.ragEval.title")}
      description={t(language, "admin.ragEval.description")}
    >
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="RAG Evaluation Workbench"
        data-density="DENSE"
        className="space-y-5"
      >
        {/* Run Controls Separated from Inspection (Spec 6.68 #1) */}
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                {language === "vi" ? "Bộ điều khiển đánh giá RAG" : "RAG Benchmark Controls"}
              </h2>
              <p className="mt-1 max-w-2xl text-xs text-[var(--text-secondary)]">
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
                className="rounded-[var(--radius-md)] bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-600)] focus-visible:ring-offset-2 disabled:opacity-60"
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
            <p className="mt-3 text-xs font-mono text-[var(--text-muted)]">
              {t(language, "admin.ragEval.latestRun", { runId })}
            </p>
          ) : null}
        </div>

        {notice ? (
          <p
            role="status"
            className="rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
          >
            {notice}
          </p>
        ) : null}

        {/* Historical Runs Table (Spec 6.68 #2) */}
        {runs.length > 0 ? (
          <PanelCard
            title={language === "vi" ? "Lịch sử các lần chạy Benchmark" : "Historical Benchmark Runs"}
            description={language === "vi" ? "Theo dõi tiến độ nâng cấp qua các đợt kiểm thử golden dataset." : "Track RAG performance across evaluation runs."}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                    <th className="py-2 pr-3 font-semibold">Lần chạy / Run ID</th>
                    <th className="py-2 pr-3 font-semibold">Recall@k</th>
                    <th className="py-2 pr-3 font-semibold">nDCG@k</th>
                    <th className="py-2 pr-3 font-semibold">Độ trung thực</th>
                    <th className="py-2 pr-3 font-semibold">Trích dẫn</th>
                    <th className="py-2 text-right font-semibold">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r, idx) => (
                    <tr
                      key={r.run_id}
                      className={[
                        "border-b border-[color:var(--shell-border)] last:border-0",
                        r.run_id === runId ? "bg-[var(--surface-brand-soft)]" : "",
                      ].join(" ")}
                    >
                      <td className="py-2.5 pr-3 font-mono font-bold text-[var(--text-primary)]">
                        {r.run_id} {r.run_id === runId ? `(${language === "vi" ? "Hiện tại" : "Active"})` : ""}
                      </td>
                      <td className="py-2.5 pr-3 font-semibold text-[var(--text-secondary)]">
                        {formatRatio(r.recall_at_k)}
                      </td>
                      <td className="py-2.5 pr-3 font-semibold text-[var(--text-secondary)]">
                        {formatRatio(r.ndcg_at_k)}
                      </td>
                      <td className="py-2.5 pr-3 font-semibold text-[var(--text-secondary)]">
                        {formatRatio(r.faithfulness)}
                      </td>
                      <td className="py-2.5 pr-3 font-semibold text-[var(--text-secondary)]">
                        {formatRatio(r.citation_acc)}
                      </td>
                      <td className="py-2.5 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={r.run_id === runId || isLoadingResults}
                          onClick={() => {
                            setRunId(r.run_id);
                            void fetchResults(r.run_id);
                          }}
                          className="!min-h-[28px] !px-2.5 text-xs"
                        >
                          {language === "vi" ? "Xem kết quả" : "Load Run"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PanelCard>
        ) : null}

        <AsyncSection<EvalResultsResponse>
          state={state}
          loadingLabel={t(language, "admin.ragEval.loading")}
          emptyTitle={t(language, "admin.ragEval.emptyTitle")}
          emptyDescription={t(language, "admin.ragEval.emptyDescription")}
        >
          {(data) => (
            <RagEvalResults
              data={data}
              k={k}
              runs={runs}
              showTrend={showTrend}
              language={language}
              selectedQuestion={selectedQuestion}
              setSelectedQuestion={setSelectedQuestion}
              questionFilter={questionFilter}
              setQuestionFilter={setQuestionFilter}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
            />
          )}
        </AsyncSection>
      </div>
    </AdminShell>
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
  language,
  selectedQuestion,
  setSelectedQuestion,
  questionFilter,
  setQuestionFilter,
  searchQuery,
  setSearchQuery,
}: {
  data: EvalResultsResponse;
  k: number;
  runs: EvalRunSummary[];
  showTrend: boolean;
  language: "vi" | "en";
  selectedQuestion: EvalResultItem | null;
  setSelectedQuestion: (item: EvalResultItem | null) => void;
  questionFilter: "all" | "errors" | "low_faithfulness" | "low_recall";
  setQuestionFilter: (f: "all" | "errors" | "low_faithfulness" | "low_recall") => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
}) {
  const runLabels = runs.map((_, index) => t(language, "admin.ragEval.runLabel", { index: index + 1 }));

  const filteredResults = useMemo(() => {
    return data.results.filter((row) => {
      if (questionFilter === "errors" && (row.recall_at_k >= 0.5 && row.faithfulness >= 0.5 && row.citation_acc >= 0.5)) {
        return false;
      }
      if (questionFilter === "low_faithfulness" && row.faithfulness >= 0.7) {
        return false;
      }
      if (questionFilter === "low_recall" && row.recall_at_k >= 0.7) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const qidMatch = row.qid.toLowerCase().includes(q);
        const textMatch = (row.query_text ?? "").toLowerCase().includes(q);
        if (!qidMatch && !textMatch) return false;
      }
      return true;
    });
  }, [data.results, questionFilter, searchQuery]);

  return (
    <div className="space-y-5">
      {/* Selected Run Metrics (Spec 6.68 #3) */}
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

      {/* Main Results Split: Question Table + Error Inspector Drawer */}
      <div className="grid grid-cols-12 gap-5">
        <div className={selectedQuestion ? "col-span-12 xl:col-span-7" : "col-span-12"}>
          <PanelCard
            title={t(language, "admin.ragEval.questionResults")}
            description={t(language, "admin.ragEval.questionResultsDescription")}
          >
            {/* Filter toolbar */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  {language === "vi" ? "Bộ lọc:" : "Filter:"}
                </span>
                <select
                  aria-label="Filter Questions"
                  value={questionFilter}
                  onChange={(e) => setQuestionFilter(e.target.value as any)}
                  className="min-h-[32px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)]"
                >
                  <option value="all">{language === "vi" ? "Tất cả câu hỏi" : "All Questions"}</option>
                  <option value="errors">{language === "vi" ? "Câu hỏi có lỗi / điểm thấp" : "Low Score / Errors"}</option>
                  <option value="low_faithfulness">{language === "vi" ? "Độ trung thực thấp (<70%)" : "Low Faithfulness (<70%)"}</option>
                  <option value="low_recall">{language === "vi" ? "Recall thấp (<70%)" : "Low Recall (<70%)"}</option>
                </select>
              </div>

              <input
                type="text"
                placeholder={language === "vi" ? "Tìm theo mã QID..." : "Search QID..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="min-h-[32px] w-40 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs text-[var(--text-primary)] focus-visible:outline-none sm:w-48"
              />
            </div>

            {filteredResults.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                      <th className="py-2 pr-3 font-semibold">{t(language, "admin.ragEval.questionId")}</th>
                      <th className="py-2 pr-3 font-semibold">Recall@{k}</th>
                      <th className="py-2 pr-3 font-semibold">nDCG@{k}</th>
                      <th className="py-2 pr-3 font-semibold">{t(language, "admin.ragEval.faithfulness")}</th>
                      <th className="py-2 pr-3 font-semibold">{t(language, "admin.ragEval.citationAccuracy")}</th>
                      <th className="py-2 pr-3 font-semibold">{t(language, "admin.ragEval.latency")}</th>
                      <th className="py-2 text-right font-semibold">{language === "vi" ? "Thao tác" : "Action"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.map((row) => {
                      const isSelected = selectedQuestion?.qid === row.qid;
                      const hasLowScore = row.recall_at_k < 0.5 || row.faithfulness < 0.5 || row.citation_acc < 0.5;

                      return (
                        <tr
                          key={row.qid}
                          onClick={() => setSelectedQuestion(row)}
                          className={[
                            "cursor-pointer border-b border-[color:var(--shell-border)] transition last:border-0 hover:bg-[var(--surface-muted)]",
                            isSelected ? "bg-[var(--surface-brand-soft)]" : "",
                            hasLowScore ? "bg-[var(--status-danger-bg)]/20" : "",
                          ].join(" ")}
                        >
                          <td className="py-2.5 pr-3 font-mono font-bold text-[var(--text-primary)]">
                            {row.qid}
                          </td>
                          <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                            <span className={row.recall_at_k < 0.5 ? "font-bold text-[var(--status-danger-text)]" : ""}>
                              {formatRatio(row.recall_at_k)}
                            </span>
                          </td>
                          <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                            {formatRatio(row.ndcg_at_k)}
                          </td>
                          <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                            <span className={row.faithfulness < 0.5 ? "font-bold text-[var(--status-danger-text)]" : ""}>
                              {formatRatio(row.faithfulness)}
                            </span>
                          </td>
                          <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                            <span className={row.citation_acc < 0.5 ? "font-bold text-[var(--status-danger-text)]" : ""}>
                              {formatRatio(row.citation_acc)}
                            </span>
                          </td>
                          <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                            {formatLatency(row.latency_ms, language)}
                          </td>
                          <td className="py-2.5 text-right">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedQuestion(row);
                              }}
                              className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                            >
                              {language === "vi" ? "Kiểm tra" : "Inspect"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-4 text-center text-sm text-[var(--text-muted)]">
                {t(language, "admin.ragEval.noRows")}
              </p>
            )}
          </PanelCard>
        </div>

        {/* Question-Level Error / Sample Inspector Drawer (Spec 6.68 #6) */}
        {selectedQuestion ? (
          <div className="col-span-12 xl:col-span-5">
            <div className="rounded-[var(--radius-lg)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
              {/* Drawer Header */}
              <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-[var(--text-primary)]">
                      {selectedQuestion.qid}
                    </span>
                    <span className="rounded-md bg-[var(--surface-brand-soft)] px-2 py-0.5 text-xs font-semibold text-[var(--text-brand)]">
                      {language === "vi" ? "Chi tiết câu hỏi" : "Question Inspector"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {language === "vi"
                      ? "Phân tích sai lệch truy xuất, độ tin cậy câu trả lời và trích dẫn."
                      : "Detailed retrieval breakdown and error diagnosis."}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon="close"
                  aria-label={language === "vi" ? "Đóng kiểm tra" : "Close inspector"}
                  onClick={() => setSelectedQuestion(null)}
                />
              </div>

              <div className="mt-4 space-y-4">
                {/* Metric Summary Chips */}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Recall</span>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">
                      {formatRatio(selectedQuestion.recall_at_k)}
                    </p>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">nDCG</span>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">
                      {formatRatio(selectedQuestion.ndcg_at_k)}
                    </p>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Faithful</span>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">
                      {formatRatio(selectedQuestion.faithfulness)}
                    </p>
                  </div>
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Citation</span>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">
                      {formatRatio(selectedQuestion.citation_acc)}
                    </p>
                  </div>
                </div>

                {/* Error / Failure Diagnostics */}
                {selectedQuestion.recall_at_k < 0.5 || selectedQuestion.faithfulness < 0.5 || selectedQuestion.failure_reason ? (
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3.5">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--status-danger-text)]">
                      <Icon name="warning" size={16} />
                      <span>{language === "vi" ? "Chẩn đoán sai số" : "Error Diagnosis"}</span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--status-danger-text)]">
                      {selectedQuestion.failure_reason ||
                        (selectedQuestion.recall_at_k < 0.5
                          ? language === "vi"
                            ? "Truy xuất không tìm thấy tài liệu gốc trong top k."
                            : "Retrieval missed ground-truth context in top k."
                          : language === "vi"
                            ? "Câu trả lời suy luận chứa nhận định chưa được hỗ trợ bởi ngữ cảnh RAG."
                            : "Generated answer contains unsupported claims (hallucination risk).")}
                    </p>
                  </div>
                ) : (
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-xs font-medium text-[var(--status-ok-text)]">
                    {language === "vi"
                      ? "Câu hỏi đạt chuẩn chất lượng golden dataset (Recall & Faithfulness > 50%)."
                      : "Question passes all benchmark quality thresholds."}
                  </div>
                )}

                {/* Question Text Box */}
                <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Nội dung câu hỏi kiểm thử" : "Test Query"}
                  </p>
                  <p className="mt-2 text-xs font-medium text-[var(--text-primary)]">
                    {selectedQuestion.query_text || `[QID: ${selectedQuestion.qid}] Yêu cầu tư vấn lâm sàng / phác đồ điều trị.`}
                  </p>
                </div>

                {/* Expected vs Generated Answer */}
                <div className="space-y-2">
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {language === "vi" ? "Đáp án chuẩn (Ground Truth)" : "Expected Ground Truth"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      {selectedQuestion.expected_answer ||
                        (language === "vi"
                          ? "Phác đồ chuẩn theo Dược thư Quốc gia và khuyến cáo Bộ Y Tế."
                          : "Reference guideline under national medical compendium.")}
                    </p>
                  </div>

                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {language === "vi" ? "Câu trả lời mô hình (Generated Answer)" : "Generated Answer"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--text-primary)]">
                      {selectedQuestion.generated_answer ||
                        (language === "vi"
                          ? "Hệ thống tổng hợp câu trả lời dựa trên các đoạn văn bản truy xuất từ kho RAG."
                          : "Synthesized response grounded in retrieved chunks.")}
                    </p>
                  </div>
                </div>

                {/* Latency & Hardware Metrics */}
                <div className="flex items-center justify-between rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-muted)]">
                  <span>{language === "vi" ? "Độ trễ xử lý:" : "Latency:"}</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">
                    {formatLatency(selectedQuestion.latency_ms, language)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TrendMetric({
  title,
  labels,
  values,
}: {
  title: string;
  labels: string[];
  values: number[];
}) {
  const points = labels.map((label, index) => ({
    label,
    value: toPercentPoint(values[index]),
  }));
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-[var(--text-secondary)]">{title}</p>
      <TrendBars points={points} />
    </div>
  );
}
