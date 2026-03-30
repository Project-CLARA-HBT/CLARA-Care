import { ResearchTier2Telemetry } from "@/lib/research";

type TelemetryDetailsPanelProps = {
  telemetry: ResearchTier2Telemetry;
  isProcessing: boolean;
};

function formatScore(value: number | string): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return value;
}

export default function TelemetryDetailsPanel({
  telemetry,
  isProcessing
}: TelemetryDetailsPanelProps) {
  const hasData =
    telemetry.keywords.length > 0 ||
    telemetry.searchPlan.subqueries.length > 0 ||
    telemetry.sourceAttempts.length > 0 ||
    telemetry.docs.length > 0 ||
    telemetry.scores.length > 0 ||
    telemetry.sourceReasoning.length > 0 ||
    telemetry.errors.length > 0;

  return (
    <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
          Telemetry Detail
        </p>
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
            kw:{telemetry.keywords.length}
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
            docs:{telemetry.docs.length}
          </span>
          <span className="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
            err:{telemetry.errors.length}
          </span>
        </div>
      </div>

      {!hasData ? (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          {isProcessing
            ? "Đang đợi telemetry runtime từ backend..."
            : "Chưa có telemetry chi tiết cho phiên này."}
        </p>
      ) : null}

      {telemetry.keywords.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Keywords
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {telemetry.keywords.slice(0, 20).map((keyword) => (
              <span
                key={keyword}
                className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-300"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {(telemetry.searchPlan.query ||
        telemetry.searchPlan.subqueries.length > 0 ||
        telemetry.searchPlan.connectors.length > 0) ? (
        <div className="mt-3 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Search Plan
          </p>
          {telemetry.searchPlan.query ? (
            <p className="text-xs text-slate-700 dark:text-slate-200">
              query: <span className="font-medium">{telemetry.searchPlan.query}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.researchMode ? (
            <p className="text-xs text-slate-700 dark:text-slate-200">
              mode: <span className="font-medium">{telemetry.searchPlan.researchMode}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.topK !== undefined ? (
            <p className="text-xs text-slate-700 dark:text-slate-200">
              top_k: <span className="font-medium">{formatScore(telemetry.searchPlan.topK)}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.totalCandidates !== undefined ? (
            <p className="text-xs text-slate-700 dark:text-slate-200">
              total_candidates:{" "}
              <span className="font-medium">
                {formatScore(telemetry.searchPlan.totalCandidates)}
              </span>
            </p>
          ) : null}
          {telemetry.searchPlan.durationMs !== undefined ? (
            <p className="text-xs text-slate-700 dark:text-slate-200">
              duration_ms:{" "}
              <span className="font-medium">{formatScore(telemetry.searchPlan.durationMs)}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.subqueries.length ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200">
              <p className="font-semibold">subqueries:</p>
              <ul className="mt-1 space-y-0.5">
                {telemetry.searchPlan.subqueries.slice(0, 8).map((subquery, index) => (
                  <li key={`${subquery}-${index}`}>- {subquery}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {telemetry.searchPlan.connectors.length ? (
            <div className="flex flex-wrap gap-1.5">
              {telemetry.searchPlan.connectors.map((connector) => (
                <span
                  key={connector}
                  className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:border-violet-700 dark:bg-violet-950/40 dark:text-violet-300"
                >
                  {connector}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {telemetry.sourceAttempts.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Source Attempts
          </p>
          <ul className="mt-2 space-y-1.5">
            {telemetry.sourceAttempts.slice(0, 12).map((attempt, index) => (
              <li
                key={`${attempt.source}-${attempt.status ?? "status"}-${index}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200"
              >
                <span className="font-semibold">{attempt.source}</span>
                {attempt.status ? ` · ${attempt.status}` : ""}
                {attempt.documents !== undefined ? ` · docs ${formatScore(attempt.documents)}` : ""}
                {attempt.durationMs !== undefined ? ` · ${formatScore(attempt.durationMs)}ms` : ""}
                {attempt.passIndex !== undefined ? ` · pass ${formatScore(attempt.passIndex)}` : ""}
                {attempt.error ? ` · error ${attempt.error}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {(telemetry.indexSummary.beforeDedupe !== undefined ||
        telemetry.indexSummary.afterDedupe !== undefined ||
        telemetry.indexSummary.selectedCount !== undefined ||
        telemetry.crawlSummary.attempted !== undefined ||
        telemetry.crawlSummary.success !== undefined ||
        telemetry.crawlSummary.domains.length > 0) ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200">
            <p className="font-semibold">Index Summary</p>
            {telemetry.indexSummary.beforeDedupe !== undefined ? (
              <p>before_dedupe: {formatScore(telemetry.indexSummary.beforeDedupe)}</p>
            ) : null}
            {telemetry.indexSummary.afterDedupe !== undefined ? (
              <p>after_dedupe: {formatScore(telemetry.indexSummary.afterDedupe)}</p>
            ) : null}
            {telemetry.indexSummary.selectedCount !== undefined ? (
              <p>selected: {formatScore(telemetry.indexSummary.selectedCount)}</p>
            ) : null}
            {telemetry.indexSummary.durationMs !== undefined ? (
              <p>duration_ms: {formatScore(telemetry.indexSummary.durationMs)}</p>
            ) : null}
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200">
            <p className="font-semibold">Crawl Summary</p>
            {telemetry.crawlSummary.enabled !== undefined ? (
              <p>enabled: {String(telemetry.crawlSummary.enabled)}</p>
            ) : null}
            {telemetry.crawlSummary.attempted !== undefined ? (
              <p>attempted: {formatScore(telemetry.crawlSummary.attempted)}</p>
            ) : null}
            {telemetry.crawlSummary.success !== undefined ? (
              <p>success: {formatScore(telemetry.crawlSummary.success)}</p>
            ) : null}
            {telemetry.crawlSummary.durationMs !== undefined ? (
              <p>duration_ms: {formatScore(telemetry.crawlSummary.durationMs)}</p>
            ) : null}
            {telemetry.crawlSummary.domains.length ? (
              <p>domains: {telemetry.crawlSummary.domains.join(", ")}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      {telemetry.scores.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Scores
          </p>
          <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {telemetry.scores.slice(0, 12).map((score) => (
              <p
                key={`${score.label}-${String(score.value)}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200"
              >
                <span className="font-semibold">{score.label}</span>: {formatScore(score.value)}
              </p>
            ))}
          </div>
        </div>
      ) : null}

      {telemetry.docs.length ? (
        <div className="mt-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Docs
          </p>
          {telemetry.docs.slice(0, 6).map((doc, index) => (
            <article
              key={`${doc.id ?? doc.title}-${index}`}
              className="rounded-2xl border border-slate-200 bg-slate-50/90 p-3 dark:border-slate-700 dark:bg-slate-800/70"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-100">{doc.title}</p>
                {doc.source ? (
                  <span className="rounded-full border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-600 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300">
                    {doc.source}
                  </span>
                ) : null}
                {doc.score !== undefined ? (
                  <span className="rounded-full border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                    score: {formatScore(doc.score)}
                  </span>
                ) : null}
              </div>
              {doc.reasoning ? (
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">reasoning: {doc.reasoning}</p>
              ) : null}
              {doc.snippet ? (
                <p className="mt-1 line-clamp-3 text-xs text-slate-500 dark:text-slate-400">{doc.snippet}</p>
              ) : null}
              {doc.error ? (
                <p className="mt-1 text-xs font-medium text-rose-700 dark:text-rose-300">error: {doc.error}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {telemetry.sourceReasoning.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Source Reasoning
          </p>
          <ul className="mt-2 space-y-1.5">
            {telemetry.sourceReasoning.slice(0, 8).map((item, index) => (
              <li
                key={`${item.source}-${index}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/75 dark:text-slate-200"
              >
                <span className="font-semibold">{item.source}</span>
                {item.score !== undefined ? ` · score ${formatScore(item.score)}` : ""}
                {item.reasoning ? ` · ${item.reasoning}` : ""}
                {item.error ? ` · error ${item.error}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {telemetry.errors.length ? (
        <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50/90 p-3 dark:border-rose-800 dark:bg-rose-950/40">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-rose-700 dark:text-rose-300">
            Errors
          </p>
          <ul className="mt-1.5 space-y-1">
            {telemetry.errors.slice(0, 10).map((error, index) => (
              <li key={`${error}-${index}`} className="text-xs text-rose-700 dark:text-rose-200">
                {error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
