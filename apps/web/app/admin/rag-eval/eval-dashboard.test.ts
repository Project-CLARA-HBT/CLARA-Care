import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  MAX_TREND_RUNS,
  aggregateEvalTrends,
  canViewEvalDashboard,
  clampUnit,
  selectVisibleEvalTrends,
  type EvalRunSummary
} from "./eval-dashboard";
import type { UserRole } from "@/lib/auth-store";

/**
 * Feature: rag-knowledge-pipeline — eval-dashboard data transform / role gating.
 *
 *  - Property (a): the trend-aggregation transform is TOTAL and ORDER-STABLE.
 *    Every metric it emits is bounded to [0, 1] with no NaN, de-duplicated by
 *    `run_id`, capped at MAX_TREND_RUNS, and ordered by timestamp when present.
 *    Validates Requirement 11.5.
 *  - Property (b): the eval dashboard data/controls are gated to the admin role.
 *    A non-admin (or missing) role yields the gated/empty state.
 *    Validates Requirements 11.5, 13.1.
 */

const METRIC_KEYS = ["recall_at_k", "ndcg_at_k", "faithfulness", "citation_acc"] as const;
const ALL_ROLES: UserRole[] = ["normal", "researcher", "doctor", "admin"];

/** Possibly-out-of-range / non-finite metric values to stress totality. */
const wildMetricArb: fc.Arbitrary<number> = fc.oneof(
  fc.double({ min: 0, max: 1, noNaN: true }),
  fc.double({ noDefaultInfinity: false, noNaN: false }),
  fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, -0.5, 2, -10, 42)
);

const runIdArb: fc.Arbitrary<string> = fc.constantFrom(
  "run-a",
  "run-b",
  "run-c",
  "run-d",
  "run-e"
);

const runArb = (withTs: boolean): fc.Arbitrary<EvalRunSummary> =>
  fc.record(
    {
      run_id: runIdArb,
      recall_at_k: wildMetricArb,
      ndcg_at_k: wildMetricArb,
      faithfulness: wildMetricArb,
      citation_acc: wildMetricArb,
      ts: withTs ? fc.integer({ min: 0, max: 5_000 }) : fc.constant(undefined)
    },
    { requiredKeys: ["run_id", "recall_at_k", "ndcg_at_k", "faithfulness", "citation_acc"] }
  );

function isBounded(value: number): boolean {
  return Number.isFinite(value) && !Number.isNaN(value) && value >= 0 && value <= 1;
}

function allMetricsBounded(runs: readonly EvalRunSummary[]): boolean {
  return runs.every((run) => METRIC_KEYS.every((key) => isBounded(run[key])));
}

// ---------------------------------------------------------------------------
// clampUnit (unit + edge cases)
// ---------------------------------------------------------------------------

describe("clampUnit (Feature: rag-knowledge-pipeline)", () => {
  it("maps in-range values to themselves and clamps the boundaries", () => {
    expect(clampUnit(0)).toBe(0);
    expect(clampUnit(1)).toBe(1);
    expect(clampUnit(0.42)).toBe(0.42);
    expect(clampUnit(1.5)).toBe(1);
    expect(clampUnit(-0.3)).toBe(0);
  });

  it("collapses non-finite / non-numeric inputs to 0 (no NaN escapes)", () => {
    expect(clampUnit(Number.NaN)).toBe(0);
    expect(clampUnit(Number.POSITIVE_INFINITY)).toBe(0);
    expect(clampUnit(Number.NEGATIVE_INFINITY)).toBe(0);
    expect(clampUnit(null)).toBe(0);
    expect(clampUnit(undefined)).toBe(0);
  });

  it("Property: clampUnit always returns a finite value within [0, 1]", () => {
    fc.assert(
      fc.property(wildMetricArb, (value) => isBounded(clampUnit(value))),
      { numRuns: 300 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property (a): trend-aggregation transform — total, bounded, order-stable
// Validates: Requirements 11.5
// ---------------------------------------------------------------------------

describe("aggregateEvalTrends — total & bounded (Feature: rag-knowledge-pipeline, Property a)", () => {
  it("is total: never throws and always bounds every metric to [0,1] with no NaN", () => {
    fc.assert(
      fc.property(
        fc.array(runArb(false), { maxLength: 20 }),
        fc.option(runArb(false), { nil: undefined }),
        (prev, incoming) => {
          const out = aggregateEvalTrends(prev, incoming);
          return allMetricsBounded(out);
        }
      ),
      { numRuns: 300 }
    );
  });

  it("handles degenerate inputs (empty / null / undefined prev) without throwing", () => {
    expect(aggregateEvalTrends([], null)).toEqual([]);
    expect(aggregateEvalTrends(null, null)).toEqual([]);
    expect(aggregateEvalTrends(undefined, undefined)).toEqual([]);
    const single = aggregateEvalTrends([], {
      run_id: "run-a",
      recall_at_k: 2,
      ndcg_at_k: -1,
      faithfulness: Number.NaN,
      citation_acc: 0.5
    });
    expect(single).toHaveLength(1);
    expect(single[0]).toMatchObject({
      run_id: "run-a",
      recall_at_k: 1,
      ndcg_at_k: 0,
      faithfulness: 0,
      citation_acc: 0.5
    });
  });

  it("de-duplicates by run_id (re-running a run replaces, never duplicates)", () => {
    fc.assert(
      fc.property(fc.array(runArb(false), { maxLength: 20 }), (runs) => {
        const acc = runs.reduce<EvalRunSummary[]>(
          (prev, run) => aggregateEvalTrends(prev, run),
          []
        );
        const ids = acc.map((row) => row.run_id);
        return new Set(ids).size === ids.length;
      }),
      { numRuns: 300 }
    );
  });

  it("caps history at MAX_TREND_RUNS (and respects a custom cap)", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            run_id: fc.integer({ min: 0, max: 1000 }).map((n) => `run-${n}`),
            recall_at_k: fc.double({ min: 0, max: 1, noNaN: true }),
            ndcg_at_k: fc.double({ min: 0, max: 1, noNaN: true }),
            faithfulness: fc.double({ min: 0, max: 1, noNaN: true }),
            citation_acc: fc.double({ min: 0, max: 1, noNaN: true })
          }),
          { maxLength: 40 }
        ),
        fc.integer({ min: 1, max: 8 }),
        (runs, cap) => {
          const acc = runs.reduce<EvalRunSummary[]>(
            (prev, run) => aggregateEvalTrends(prev, run, cap),
            []
          );
          return acc.length <= cap;
        }
      ),
      { numRuns: 200 }
    );
    // Default cap.
    const many = Array.from({ length: MAX_TREND_RUNS + 7 }, (_, i) => ({
      run_id: `run-${i}`,
      recall_at_k: 0.5,
      ndcg_at_k: 0.5,
      faithfulness: 0.5,
      citation_acc: 0.5
    }));
    const acc = many.reduce<EvalRunSummary[]>((prev, run) => aggregateEvalTrends(prev, run), []);
    expect(acc).toHaveLength(MAX_TREND_RUNS);
    // Keeps the most recent window.
    expect(acc[acc.length - 1].run_id).toBe(`run-${MAX_TREND_RUNS + 6}`);
  });
});

describe("aggregateEvalTrends — order stability (Feature: rag-knowledge-pipeline, Property a)", () => {
  it("orders by timestamp ascending when every run carries a finite ts", () => {
    fc.assert(
      fc.property(
        fc
          .uniqueArray(runIdArb, { minLength: 1, maxLength: 5 })
          .chain((ids) =>
            fc.tuple(
              ...ids.map((id) =>
                fc.record({
                  run_id: fc.constant(id),
                  recall_at_k: fc.double({ min: 0, max: 1, noNaN: true }),
                  ndcg_at_k: fc.double({ min: 0, max: 1, noNaN: true }),
                  faithfulness: fc.double({ min: 0, max: 1, noNaN: true }),
                  citation_acc: fc.double({ min: 0, max: 1, noNaN: true }),
                  ts: fc.integer({ min: 0, max: 10_000 })
                })
              )
            )
          ),
        (runs) => {
          // Feed in an arbitrary insertion order; result must be sorted by ts.
          const acc = runs.reduce<EvalRunSummary[]>(
            (prev, run) => aggregateEvalTrends(prev, run),
            []
          );
          for (let i = 1; i < acc.length; i += 1) {
            if ((acc[i - 1].ts as number) > (acc[i].ts as number)) return false;
          }
          return true;
        }
      ),
      { numRuns: 300 }
    );
  });

  it("preserves insertion order when timestamps are absent (matches page behavior)", () => {
    const a: EvalRunSummary = {
      run_id: "run-a",
      recall_at_k: 0.1,
      ndcg_at_k: 0.2,
      faithfulness: 0.3,
      citation_acc: 0.4
    };
    const b: EvalRunSummary = { ...a, run_id: "run-b" };
    const c: EvalRunSummary = { ...a, run_id: "run-c" };
    const acc = [a, b, c].reduce<EvalRunSummary[]>(
      (prev, run) => aggregateEvalTrends(prev, run),
      []
    );
    expect(acc.map((r) => r.run_id)).toEqual(["run-a", "run-b", "run-c"]);
    // Re-running an existing run moves it to the end (mirrors filter+push).
    const reran = aggregateEvalTrends(acc, { ...a, run_id: "run-a", recall_at_k: 0.9 });
    expect(reran.map((r) => r.run_id)).toEqual(["run-b", "run-c", "run-a"]);
    expect(reran[reran.length - 1].recall_at_k).toBe(0.9);
  });

  it("is idempotent / stable: re-applying the most recent run yields the same series", () => {
    fc.assert(
      fc.property(fc.array(runArb(false), { minLength: 1, maxLength: 12 }), (runs) => {
        const once = runs.reduce<EvalRunSummary[]>(
          (prev, run) => aggregateEvalTrends(prev, run),
          []
        );
        const last = runs[runs.length - 1];
        const twice = aggregateEvalTrends(once, last);
        return JSON.stringify(once) === JSON.stringify(twice);
      }),
      { numRuns: 200 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property (b): admin-only role gating
// Validates: Requirements 11.5, 13.1
// ---------------------------------------------------------------------------

describe("canViewEvalDashboard — admin gating (Feature: rag-knowledge-pipeline, Property b)", () => {
  it("grants only the admin role", () => {
    expect(canViewEvalDashboard("admin")).toBe(true);
    expect(canViewEvalDashboard("normal")).toBe(false);
    expect(canViewEvalDashboard("researcher")).toBe(false);
    expect(canViewEvalDashboard("doctor")).toBe(false);
    expect(canViewEvalDashboard(null)).toBe(false);
    expect(canViewEvalDashboard(undefined)).toBe(false);
    expect(canViewEvalDashboard("")).toBe(false);
  });

  it("Property: gate is true iff role === 'admin' across all known + arbitrary roles", () => {
    const roleArb = fc.oneof(
      fc.constantFrom<UserRole>(...ALL_ROLES),
      fc.string(),
      fc.constantFrom("Admin", "ADMIN", " admin", "admin ", "superadmin")
    );
    fc.assert(
      fc.property(roleArb, (role) => canViewEvalDashboard(role) === (role === "admin")),
      { numRuns: 300 }
    );
  });
});

describe("selectVisibleEvalTrends — gated/empty state (Feature: rag-knowledge-pipeline, Property b)", () => {
  it("Property: non-admin roles always yield the empty/gated state regardless of data", () => {
    const nonAdminArb = fc.constantFrom<UserRole>("normal", "researcher", "doctor");
    fc.assert(
      fc.property(nonAdminArb, fc.array(runArb(false), { maxLength: 20 }), (role, runs) => {
        return selectVisibleEvalTrends(role, runs).length === 0;
      }),
      { numRuns: 300 }
    );
  });

  it("Property: admins see the aggregated (bounded) trend; gate never fabricates runs", () => {
    fc.assert(
      fc.property(fc.array(runArb(false), { maxLength: 20 }), (runs) => {
        const visible = selectVisibleEvalTrends("admin", runs);
        const distinctIds = new Set(runs.map((r) => r.run_id)).size;
        return (
          allMetricsBounded(visible) &&
          visible.length === Math.min(distinctIds, MAX_TREND_RUNS)
        );
      }),
      { numRuns: 300 }
    );
  });

  it("returns empty for an admin with no runs (still a valid gated-empty surface)", () => {
    expect(selectVisibleEvalTrends("admin", [])).toEqual([]);
    expect(selectVisibleEvalTrends("admin", null)).toEqual([]);
  });
});
