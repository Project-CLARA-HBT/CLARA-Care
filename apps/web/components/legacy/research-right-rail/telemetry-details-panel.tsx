import { useMemo } from "react";
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

function formatTraceValue(value: string | number | boolean): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  return value.length > 56 ? `${value.slice(0, 56)}...` : value;
}

function getTraceMetadataValue(
  metadata: ResearchTier2Telemetry["traceMetadata"],
  candidates: string[]
): string | number | boolean | undefined {
  if (!metadata) return undefined;
  const entries = Object.entries(metadata);
  const normalizedCandidates = candidates.map((item) => item.toLowerCase());

  for (const [key, value] of entries) {
    const normalizedKey = key.toLowerCase();
    if (
      normalizedCandidates.some(
        (candidate) => normalizedKey === candidate || normalizedKey.endsWith(`.${candidate}`)
      )
    ) {
      return value;
    }
  }

  return undefined;
}

function parseTimestampForSort(value?: string): number | undefined {
  if (!value) return undefined;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function supportStatusBadgeClass(status?: string): string {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "supported") {
    return "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]";
  }
  if (normalized === "contradicted") {
    return "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]";
  }
  if (normalized === "insufficient" || normalized === "unsupported") {
    return "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]";
  }
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function clampTelemetryBar(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(95, Math.max(14, Math.round(value)));
}

export default function TelemetryDetailsPanel({
  telemetry,
  isProcessing
}: TelemetryDetailsPanelProps) {
  const traceEntries = Object.entries(telemetry.traceMetadata ?? {});
  const traceRuntime = {
    traceId: getTraceMetadataValue(telemetry.traceMetadata, [
      "trace_id",
      "traceid",
      "trace-id",
      "traceparent"
    ]),
    runId: getTraceMetadataValue(telemetry.traceMetadata, [
      "run_id",
      "runid",
      "execution_run_id"
    ]),
    service: getTraceMetadataValue(telemetry.traceMetadata, [
      "service_name",
      "service",
      "service.name"
    ]),
    component: getTraceMetadataValue(telemetry.traceMetadata, [
      "component",
      "component_name",
      "component.name"
    ])
  };
  const hasTraceRuntime =
    traceRuntime.traceId !== undefined ||
    traceRuntime.runId !== undefined ||
    traceRuntime.service !== undefined ||
    traceRuntime.component !== undefined;
  const stageSpans = [...(telemetry.stageSpans ?? [])].sort((left, right) => {
    const leftStart = parseTimestampForSort(left.start);
    const rightStart = parseTimestampForSort(right.start);
    if (leftStart !== undefined && rightStart !== undefined) return leftStart - rightStart;
    if (leftStart !== undefined) return -1;
    if (rightStart !== undefined) return 1;
    return 0;
  });
  const contradictionSummary = telemetry.contradictionSummary;
  const hasContradictionSummary =
    contradictionSummary?.hasContradiction !== undefined ||
    contradictionSummary?.count !== undefined ||
    Boolean(contradictionSummary?.severity) ||
    Boolean(contradictionSummary?.status) ||
    Boolean(contradictionSummary?.summary);
  const safetyOverride = telemetry.safetyOverride;
  const hasSafetyOverride = Boolean(safetyOverride?.applied || safetyOverride?.reason || safetyOverride?.note);
  const hasData =
    telemetry.keywords.length > 0 ||
    telemetry.searchPlan.subqueries.length > 0 ||
    telemetry.sourceAttempts.length > 0 ||
    telemetry.docs.length > 0 ||
    telemetry.scores.length > 0 ||
    telemetry.sourceReasoning.length > 0 ||
    telemetry.verificationMatrix.length > 0 ||
    hasSafetyOverride ||
    hasContradictionSummary ||
    stageSpans.length > 0 ||
    traceEntries.length > 0 ||
    telemetry.errors.length > 0;
  const telemetryBars = useMemo(() => {
    const raw = [
      24 + telemetry.keywords.length * 2.2,
      28 + telemetry.searchPlan.subqueries.length * 6.4,
      22 + telemetry.docs.length * 8.4,
      30 + telemetry.sourceAttempts.length * 5.8,
      20 + telemetry.verificationMatrix.length * 8.2,
      18 + stageSpans.length * 5.5,
      14 + telemetry.errors.length * 18
    ];
    return raw.map((value) => clampTelemetryBar(value));
  }, [
    stageSpans.length,
    telemetry.docs.length,
    telemetry.errors.length,
    telemetry.keywords.length,
    telemetry.searchPlan.subqueries.length,
    telemetry.sourceAttempts.length,
    telemetry.verificationMatrix.length
  ]);

  return (
    <section className="research-panel-modern rounded-[1.35rem] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          Telemetry Detail
        </p>
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="research-chip rounded-full px-2 py-0.5">
            kw:{telemetry.keywords.length}
          </span>
          <span className="research-chip rounded-full px-2 py-0.5">
            docs:{telemetry.docs.length}
          </span>
          <span className="rounded-full border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-2 py-0.5 text-[var(--status-warn-text)]">
            vm:{telemetry.verificationMatrix.length}
          </span>
          <span className="research-chip rounded-full px-2 py-0.5">
            trace:{traceEntries.length}
          </span>
          <span className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[var(--status-danger-text)]">
            err:{telemetry.errors.length}
          </span>
        </div>
      </div>

      <div className="research-live-engine mt-3 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-[var(--text-brand)]">
            Neural Reasoning
          </p>
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-brand)]">
            <span className="research-pulse-dot" />
            Runtime
          </span>
        </div>
        <div className="h-16">
          <div className="research-live-bars">
            {telemetryBars.map((height, index) => (
              <span
                key={`telemetry-bar-${index}`}
                className="research-live-bar"
                style={{
                  height: `${height}%`,
                  opacity: `${0.36 + index * 0.08}`
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {!hasData ? (
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          {isProcessing
            ? "Đang đợi telemetry runtime từ backend..."
            : "Chưa có telemetry chi tiết cho phiên này."}
        </p>
      ) : null}

      {telemetry.keywords.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Keywords
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {telemetry.keywords.slice(0, 20).map((keyword) => (
              <span
                key={keyword}
                className="rounded-full border border-[color:var(--border-brand-subtle)] bg-[var(--surface-brand-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-brand)]"
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
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Search Plan
          </p>
          {telemetry.searchPlan.query ? (
            <p className="text-xs text-[var(--text-primary)]">
              query: <span className="font-medium">{telemetry.searchPlan.query}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.researchMode ? (
            <p className="text-xs text-[var(--text-primary)]">
              mode: <span className="font-medium">{telemetry.searchPlan.researchMode}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.topK !== undefined ? (
            <p className="text-xs text-[var(--text-primary)]">
              top_k: <span className="font-medium">{formatScore(telemetry.searchPlan.topK)}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.totalCandidates !== undefined ? (
            <p className="text-xs text-[var(--text-primary)]">
              total_candidates:{" "}
              <span className="font-medium">
                {formatScore(telemetry.searchPlan.totalCandidates)}
              </span>
            </p>
          ) : null}
          {telemetry.searchPlan.durationMs !== undefined ? (
            <p className="text-xs text-[var(--text-primary)]">
              duration_ms:{" "}
              <span className="font-medium">{formatScore(telemetry.searchPlan.durationMs)}</span>
            </p>
          ) : null}
          {telemetry.searchPlan.subqueries.length ? (
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2 text-xs text-[var(--text-secondary)]">
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
                  className="rounded-full border border-[color:var(--border-brand-subtle)] bg-[var(--surface-brand-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-brand)]"
                >
                  {connector}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {(telemetry.verificationMatrix.length || hasContradictionSummary || hasSafetyOverride) ? (
        <div className="mt-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Verification
          </p>
          {hasSafetyOverride && safetyOverride ? (
            <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-2 text-xs text-[var(--status-danger-text)]">
              <p className="font-semibold">Safety Override</p>
              <p className="mt-1">
                applied: {String(Boolean(safetyOverride.applied))}
                {safetyOverride.policyAction ? ` · policy_action ${safetyOverride.policyAction}` : ""}
                {safetyOverride.verificationState ? ` · state ${safetyOverride.verificationState}` : ""}
                {safetyOverride.affectedClaimCount !== undefined
                  ? ` · affected_claims ${formatScore(safetyOverride.affectedClaimCount)}`
                  : ""}
              </p>
              {safetyOverride.reason ? <p className="mt-1 text-[11px]">reason: {safetyOverride.reason}</p> : null}
              {safetyOverride.note ? <p className="mt-1 text-[11px]">{safetyOverride.note}</p> : null}
              {safetyOverride.claims.length ? (
                <p className="mt-1 text-[11px]">claims: {safetyOverride.claims.slice(0, 5).join(" | ")}</p>
              ) : null}
            </div>
          ) : null}
          {telemetry.verificationMatrix.length ? (
            <ul className="space-y-1.5">
              {telemetry.verificationMatrix.slice(0, 8).map((item, index) => (
                <li
                  key={`${item.claim}-${item.supportStatus ?? item.verdict ?? "na"}-${index}`}
                  className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-2 py-2 text-xs text-[var(--status-warn-text)]"
                >
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="font-semibold">{item.claim}</p>
                    {(item.supportStatus || item.verdict) ? (
                      <span
                        className={[
                          "rounded-full border px-1.5 py-0.5 text-[10px] font-semibold",
                          supportStatusBadgeClass(item.supportStatus ?? item.verdict)
                        ].join(" ")}
                      >
                        {item.supportStatus ?? item.verdict}
                      </span>
                    ) : null}
                    {item.claimType ? (
                      <span className="rounded-full border border-[color:var(--border-brand-subtle)] bg-[var(--surface-brand-soft)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-brand)]">
                        {item.claimType}
                      </span>
                    ) : null}
                    {item.severity ? (
                      <span className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--status-danger-text)]">
                        {item.severity}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1">
                    {item.verdict ? `verdict: ${item.verdict}` : "verdict: n/a"}
                    {item.confidence !== undefined ? ` · conf ${formatScore(item.confidence)}` : ""}
                    {item.overlapScore !== undefined ? ` · overlap ${formatScore(item.overlapScore)}` : ""}
                    {item.evidence.length ? ` · evidence ${item.evidence.length}` : ""}
                    {item.evidenceRef ? ` · ref ${item.evidenceRef}` : ""}
                    {item.source ? ` · source ${item.source}` : ""}
                  </p>
                  {item.note ? <p className="mt-1 text-[11px]">{item.note}</p> : null}
                </li>
              ))}
            </ul>
          ) : null}

          {hasContradictionSummary && contradictionSummary ? (
            <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-2 text-xs text-[var(--status-danger-text)]">
              <p className="font-semibold">Contradiction Summary</p>
              <p className="mt-1">
                {contradictionSummary.hasContradiction !== undefined
                  ? `has_contradiction: ${String(contradictionSummary.hasContradiction)}`
                  : "has_contradiction: n/a"}
                {contradictionSummary.count !== undefined
                  ? ` · count ${formatScore(contradictionSummary.count)}`
                  : ""}
                {contradictionSummary.severity ? ` · severity ${contradictionSummary.severity}` : ""}
                {contradictionSummary.status ? ` · status ${contradictionSummary.status}` : ""}
              </p>
              {contradictionSummary.summary ? (
                <p className="mt-1 text-[11px]">{contradictionSummary.summary}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {telemetry.sourceAttempts.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Source Attempts
          </p>
          <ul className="mt-2 space-y-1.5">
            {telemetry.sourceAttempts.slice(0, 12).map((attempt, index) => (
              <li
                key={`${attempt.source}-${attempt.status ?? "status"}-${index}`}
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1.5 text-xs text-[var(--text-secondary)]"
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

      {(telemetry.indexSummary.retrievedCount !== undefined ||
        telemetry.indexSummary.beforeDedupe !== undefined ||
        telemetry.indexSummary.afterDedupe !== undefined ||
        telemetry.indexSummary.selectedCount !== undefined ||
        telemetry.indexSummary.rerankCacheHit !== undefined ||
        telemetry.indexSummary.rerankCacheAgeMs !== undefined ||
        Boolean(telemetry.indexSummary.rerankReason) ||
        (telemetry.indexSummary.sourceCounts &&
          Object.keys(telemetry.indexSummary.sourceCounts).length > 0) ||
        telemetry.crawlSummary.attempted !== undefined ||
        telemetry.crawlSummary.success !== undefined ||
        telemetry.crawlSummary.domains.length > 0) ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2 text-xs text-[var(--text-secondary)]">
            <p className="font-semibold">Index Summary</p>
            {telemetry.indexSummary.retrievedCount !== undefined ? (
              <p>retrieved_count: {formatScore(telemetry.indexSummary.retrievedCount)}</p>
            ) : null}
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
            {telemetry.indexSummary.rerankLatencyMs !== undefined ? (
              <p>rerank_latency_ms: {formatScore(telemetry.indexSummary.rerankLatencyMs)}</p>
            ) : null}
            {telemetry.indexSummary.rerankTopN !== undefined ? (
              <p>rerank_topn: {formatScore(telemetry.indexSummary.rerankTopN)}</p>
            ) : null}
            {telemetry.indexSummary.rerankModel ? (
              <p>rerank_model: {telemetry.indexSummary.rerankModel}</p>
            ) : null}
            {telemetry.indexSummary.rerankReason ? (
              <p>rerank_reason: {telemetry.indexSummary.rerankReason}</p>
            ) : null}
            {telemetry.indexSummary.rerankCacheHit !== undefined ? (
              <p>rerank_cache_hit: {String(telemetry.indexSummary.rerankCacheHit)}</p>
            ) : null}
            {telemetry.indexSummary.rerankCacheAgeMs !== undefined ? (
              <p>rerank_cache_age_ms: {formatScore(telemetry.indexSummary.rerankCacheAgeMs)}</p>
            ) : null}
            {telemetry.indexSummary.sourceCounts &&
            Object.keys(telemetry.indexSummary.sourceCounts).length ? (
              <p>
                source_counts:{" "}
                {Object.entries(telemetry.indexSummary.sourceCounts)
                  .map(([key, value]) => `${key}:${formatScore(value)}`)
                  .join(", ")}
              </p>
            ) : null}
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2 text-xs text-[var(--text-secondary)]">
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
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Scores
          </p>
          <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {telemetry.scores.slice(0, 12).map((score) => (
              <p
                key={`${score.label}-${String(score.value)}`}
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-xs text-[var(--text-secondary)]"
              >
                <span className="font-semibold">{score.label}</span>: {formatScore(score.value)}
              </p>
            ))}
          </div>
        </div>
      ) : null}

      {telemetry.docs.length ? (
        <div className="mt-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Docs
          </p>
          {telemetry.docs.slice(0, 6).map((doc, index) => (
            <article
              key={`${doc.id ?? doc.title}-${index}`}
              className="rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-container)] p-3"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="text-xs font-semibold text-[var(--text-primary)]">{doc.title}</p>
                {doc.source ? (
                  <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
                    {doc.source}
                  </span>
                ) : null}
                {doc.score !== undefined ? (
                  <span className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-1.5 py-0.5 text-[10px] text-[var(--status-ok-text)]">
                    score: {formatScore(doc.score)}
                  </span>
                ) : null}
              </div>
              {doc.reasoning ? (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">reasoning: {doc.reasoning}</p>
              ) : null}
              {doc.snippet ? (
                <p className="mt-1 line-clamp-3 text-xs text-[var(--text-secondary)]">{doc.snippet}</p>
              ) : null}
              {doc.error ? (
                <p className="mt-1 text-xs font-medium text-[var(--status-danger-text)]">error: {doc.error}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {telemetry.sourceReasoning.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Source Reasoning
          </p>
          <ul className="mt-2 space-y-1.5">
            {telemetry.sourceReasoning.slice(0, 8).map((item, index) => (
              <li
                key={`${item.source}-${index}`}
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1.5 text-xs text-[var(--text-secondary)]"
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

      {hasTraceRuntime ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Trace Runtime
          </p>
          <div className="mt-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2 text-xs text-[var(--text-secondary)]">
            {traceRuntime.traceId !== undefined ? (
              <p>
                trace_id: <span className="font-medium">{formatTraceValue(traceRuntime.traceId)}</span>
              </p>
            ) : null}
            {traceRuntime.runId !== undefined ? (
              <p>
                run_id: <span className="font-medium">{formatTraceValue(traceRuntime.runId)}</span>
              </p>
            ) : null}
            {traceRuntime.service !== undefined ? (
              <p>
                service: <span className="font-medium">{formatTraceValue(traceRuntime.service)}</span>
              </p>
            ) : null}
            {traceRuntime.component !== undefined ? (
              <p>
                component: <span className="font-medium">{formatTraceValue(traceRuntime.component)}</span>
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {stageSpans.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Stage Spans
          </p>
          <ul className="mt-2 space-y-1.5">
            {stageSpans.slice(0, 20).map((span, index) => (
              <li
                key={`${span.stage}-${span.start ?? "na"}-${span.end ?? "na"}-${index}`}
                className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1.5 text-xs text-[var(--text-secondary)]"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-semibold">{span.stage}</span>
                  {span.status ? (
                    <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
                      {span.status}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  duration_ms:{" "}
                  <span className="font-medium">
                    {span.durationMs !== undefined ? formatScore(span.durationMs) : "n/a"}
                  </span>
                  {span.eventCount !== undefined
                    ? ` · event_count ${formatScore(span.eventCount)}`
                    : ""}
                  {span.sourceCount !== undefined
                    ? ` · source_count ${formatScore(span.sourceCount)}`
                    : ""}
                  {span.componentCount !== undefined
                    ? ` · component_count ${formatScore(span.componentCount)}`
                    : ""}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {traceEntries.length ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            Trace Metadata
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {traceEntries.slice(0, 12).map(([key, value]) => (
              <span
                key={`${key}-${String(value)}`}
                className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]"
              >
                {key}: {formatTraceValue(value)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {telemetry.errors.length ? (
        <div className="mt-3 rounded-[14px] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--status-danger-text)]">
            Errors
          </p>
          <ul className="mt-1.5 space-y-1">
            {telemetry.errors.slice(0, 10).map((error, index) => (
              <li key={`${error}-${index}`} className="text-xs text-[var(--status-danger-text)]">
                {error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
