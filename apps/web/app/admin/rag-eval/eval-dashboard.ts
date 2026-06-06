import type { UserRole } from "@/lib/auth-store";

/**
 * Pure data helpers for the RAG eval admin dashboard (Yêu cầu 11.5, 13.1).
 *
 * These functions hold the dashboard's non-rendering logic so it can be tested
 * in isolation (see `eval-dashboard.test.ts`):
 *
 *  - {@link aggregateEvalTrends} — the trend-aggregation transform the page
 *    uses to accumulate per-run summaries for the "Xu hướng qua các lần chạy"
 *    chart. It is total (defined for any input), de-duplicates by `run_id`,
 *    keeps run ordering stable (by timestamp when present, otherwise insertion
 *    order), caps history at `MAX_TREND_RUNS`, and clamps every metric into the
 *    closed unit interval [0, 1] with no NaN.
 *  - {@link canViewEvalDashboard} / {@link selectVisibleEvalTrends} — the
 *    admin-only gating predicate. The eval dashboard is an admin surface
 *    (server-side `require_roles("admin")`); a non-admin role yields the gated
 *    (empty) state. This mirrors the RBAC contract rather than replacing it.
 */

/** Aggregate metrics of a single eval run, accumulated client-side for trends. */
export type EvalRunSummary = {
  run_id: string;
  recall_at_k: number;
  ndcg_at_k: number;
  faithfulness: number;
  citation_acc: number;
  /**
   * Optional client capture time (ms since epoch). When every run carries a
   * finite timestamp, the trend is ordered chronologically; otherwise the
   * original insertion order is preserved.
   */
  ts?: number;
};

/** Maximum number of recent runs retained for the trend chart. */
export const MAX_TREND_RUNS = 12;

/**
 * Clamp a value into the closed unit interval [0, 1]. Non-finite or non-numeric
 * inputs (NaN, Infinity, null, undefined) collapse to 0 so the transform is
 * total and never emits NaN.
 */
export function clampUnit(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function normalizeRun(run: EvalRunSummary): EvalRunSummary {
  const normalized: EvalRunSummary = {
    run_id: run.run_id,
    recall_at_k: clampUnit(run.recall_at_k),
    ndcg_at_k: clampUnit(run.ndcg_at_k),
    faithfulness: clampUnit(run.faithfulness),
    citation_acc: clampUnit(run.citation_acc)
  };
  if (typeof run.ts === "number" && Number.isFinite(run.ts)) {
    normalized.ts = run.ts;
  }
  return normalized;
}

/**
 * Merge an incoming run summary into the accumulated trend history.
 *
 * Total / order-stable contract:
 *  - The output never contains duplicate `run_id`s; the last occurrence of a
 *    run wins (so re-running an already-seen run replaces its point and moves
 *    it to the end) while relative order is otherwise preserved.
 *  - When every retained run carries a finite `ts`, the result is ordered by
 *    timestamp ascending (ties broken by stable insertion order); otherwise the
 *    insertion order is preserved unchanged.
 *  - The history is capped at the most recent `maxRuns` entries.
 *  - Every metric is clamped into [0, 1] with no NaN.
 *
 * Passing no `incoming` run de-duplicates, re-orders and bounds the existing
 * history.
 */
export function aggregateEvalTrends(
  prev: readonly EvalRunSummary[] | null | undefined,
  incoming?: EvalRunSummary | null,
  maxRuns: number = MAX_TREND_RUNS
): EvalRunSummary[] {
  const cap =
    typeof maxRuns === "number" && Number.isFinite(maxRuns) && maxRuns > 0
      ? Math.trunc(maxRuns)
      : MAX_TREND_RUNS;

  const base = Array.isArray(prev) ? prev.slice() : [];
  const combined =
    incoming && typeof incoming.run_id === "string" ? [...base, incoming] : base;

  // De-duplicate by `run_id`, keeping the last occurrence (so a re-run replaces
  // its prior point and moves to the end) while preserving relative order. This
  // matches the page's incremental filter-then-append behavior and stays
  // idempotent even when a pre-built list is normalized.
  const seen = new Set<string>();
  const merged: EvalRunSummary[] = [];
  for (let i = combined.length - 1; i >= 0; i -= 1) {
    const row = combined[i];
    if (seen.has(row.run_id)) continue;
    seen.add(row.run_id);
    merged.push(row);
  }
  merged.reverse();

  const allHaveTimestamp = merged.every(
    (row) => typeof row.ts === "number" && Number.isFinite(row.ts)
  );

  const ordered = allHaveTimestamp
    ? merged
        .map((row, index) => ({ row, index }))
        .sort((a, b) => (a.row.ts as number) - (b.row.ts as number) || a.index - b.index)
        .map((entry) => entry.row)
    : merged;

  return ordered.slice(-cap).map(normalizeRun);
}

/**
 * Admin-only gating predicate for the eval dashboard. Returns true only for the
 * `admin` role; every other (or missing) role is denied. Mirrors the server-side
 * `require_roles("admin")` RBAC contract (Yêu cầu 13.1).
 */
export function canViewEvalDashboard(role: UserRole | string | null | undefined): boolean {
  return role === "admin";
}

/**
 * Role-gated projection of the trend data. Admins see the aggregated trend
 * history; any non-admin role yields the gated (empty) state — no eval data or
 * controls are surfaced.
 */
export function selectVisibleEvalTrends(
  role: UserRole | string | null | undefined,
  runs: readonly EvalRunSummary[] | null | undefined,
  maxRuns: number = MAX_TREND_RUNS
): EvalRunSummary[] {
  if (!canViewEvalDashboard(role)) return [];
  return aggregateEvalTrends(runs, null, maxRuns);
}
