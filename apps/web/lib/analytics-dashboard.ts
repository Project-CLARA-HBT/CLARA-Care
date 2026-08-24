import api from "@/lib/http-client";

/**
 * Admin analytics dashboard data access.
 *
 * Thin typed client over the admin-gated analytics endpoints:
 *   - GET /system/analytics/product  (Product_Analytics, Requirement 7)
 *   - GET /system/analytics/clinical (Clinical_Analytics, Requirement 8)
 *
 * The TypeScript shapes mirror the Pydantic response schemas in
 * `services/api/src/clara_api/api/v1/endpoints/analytics.py` (snake_case is
 * preserved so the raw JSON maps 1:1). Every shape is PII-free by construction
 * — only counts, distributions, percentiles, verdicts, timestamps, and opaque
 * cohort labels are carried.
 *
 * Both endpoints are gated by `require_roles("admin")` server-side (403 for any
 * non-admin role); this module never weakens that contract.
 */

// ---------------------------------------------------------------------------
// Product_Analytics shapes (Requirement 7)
// ---------------------------------------------------------------------------

export type ActiveUsersPoint = {
  date: string;
  active_users: number;
};

export type SurfaceUsage = {
  surface: string;
  count: number;
};

export type FunnelStage = {
  stage: string;
  count: number;
};

/** Retention cohort row. The API emits cohort label + counts only (no PII). */
export type RetentionCohort = {
  cohort?: string;
  cohort_size?: number;
  retained?: number;
  [key: string]: unknown;
};

export type ProductAnalytics = {
  generated_at: string;
  range: [string, string];
  active_user_trend: ActiveUsersPoint[];
  surface_usage: SurfaceUsage[];
  funnels: FunnelStage[];
  retention: RetentionCohort[];
  has_data: boolean;
};

// ---------------------------------------------------------------------------
// Clinical_Analytics shapes (Requirement 8)
// ---------------------------------------------------------------------------

export type VerdictDistribution = {
  verified: number;
  partially_verified: number;
  contested: number;
  unsupported: number;
  /** CRITICAL claims blocked by FIDES verification (8.4). */
  blocked_claims: number;
};

export type DdiSeverityDistribution = {
  low: number;
  medium: number;
  high: number;
  critical: number;
};

export type LatencyPercentiles = {
  /** tier1 | tier2_deep | tier2_deep_beta | council */
  tier: string;
  p50_ms: number;
  p90_ms: number;
  p99_ms: number;
};

import type { FidesBlockedPatternItem } from "./platform-analytics";

export type ClinicalAnalytics = {
  generated_at: string;
  range: [string, string];
  verdicts: VerdictDistribution;
  ddi_severity: DdiSeverityDistribution;
  router_confidence: Record<string, number>;
  fallback_rate_pct: number;
  latency: LatencyPercentiles[];
  has_data: boolean;
  top_hazardous_pairs?: FidesBlockedPatternItem[];
};

// ---------------------------------------------------------------------------
// Date-range helpers
// ---------------------------------------------------------------------------

export type AnalyticsRange = {
  from?: string;
  to?: string;
};

/** Format a Date as an ISO `YYYY-MM-DD` calendar date (the API range format). */
export function toIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

/**
 * Default trailing window ending today (UTC). Mirrors the API's
 * `ANALYTICS_DEFAULT_RANGE_DAYS` behavior so the dashboards open on a sensible
 * range before the admin narrows it.
 */
export function defaultAnalyticsRange(days = 30): Required<AnalyticsRange> {
  const safeDays = Number.isFinite(days) && days > 0 ? Math.trunc(days) : 30;
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - safeDays);
  return { from: toIsoDate(from), to: toIsoDate(to) };
}

function buildRangeQuery(range: AnalyticsRange): string {
  const params = new URLSearchParams();
  if (range.from) params.set("from", range.from);
  if (range.to) params.set("to", range.to);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------------
// Fetchers
// ---------------------------------------------------------------------------

export async function getProductAnalytics(range: AnalyticsRange = {}): Promise<ProductAnalytics> {
  const response = await api.get<ProductAnalytics>(
    `/system/analytics/product${buildRangeQuery(range)}`
  );
  return response.data;
}

export async function getClinicalAnalytics(
  range: AnalyticsRange = {}
): Promise<ClinicalAnalytics> {
  const response = await api.get<ClinicalAnalytics>(
    `/system/analytics/clinical${buildRangeQuery(range)}`
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const COUNT_FORMATTER = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

/** Format a non-negative integer count for display, with a `--` fallback. */
export function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return COUNT_FORMATTER.format(Math.max(0, value));
}

/** Format a percentage value (already 0–100) with one decimal place. */
export function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${Math.max(0, value).toFixed(1)}%`;
}

/** Format a latency value (milliseconds) for display. */
export function formatMs(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${COUNT_FORMATTER.format(Math.max(0, Math.round(value)))} ms`;
}

/** Vietnamese labels for the known product Surfaces. */
const SURFACE_LABELS: Record<string, string> = {
  chat: "Chat",
  research: "Nghiên cứu",
  selfmed: "Tủ thuốc",
  careguard: "Kiểm tra tương tác",
  council: "Hội chẩn AI",
  scribe: "Medical Scribe",
  admin: "Quản trị",
  dashboard: "Tổng quan"
};

export function toSurfaceLabel(surface: string): string {
  const key = (surface ?? "").trim().toLowerCase();
  return SURFACE_LABELS[key] ?? surface;
}

/** Vietnamese labels for the known funnel stages. */
const FUNNEL_LABELS: Record<string, string> = {
  active_users: "Người dùng hoạt động",
  ran_query: "Đã đặt câu hỏi",
  used_clinical_tools: "Đã dùng công cụ lâm sàng"
};

export function toFunnelLabel(stage: string): string {
  const key = (stage ?? "").trim().toLowerCase();
  return FUNNEL_LABELS[key] ?? stage;
}

/** Vietnamese labels for the known latency tiers. */
const TIER_LABELS: Record<string, string> = {
  tier1: "Tier 1 (Nhanh)",
  tier2_deep: "Tier 2 (Tư duy)",
  tier2_deep_beta: "Tier 2 (Pro)",
  council: "Hội chẩn AI"
};

export function toTierLabel(tier: string): string {
  const key = (tier ?? "").trim().toLowerCase();
  return TIER_LABELS[key] ?? tier;
}
