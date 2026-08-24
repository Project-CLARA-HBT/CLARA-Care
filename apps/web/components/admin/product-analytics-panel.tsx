"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import AnalyticsDateRange from "@/components/admin/analytics-date-range";
import {
  BarList,
  KpiCard,
  PanelCard,
  TrendBars,
  type BarRow
} from "@/components/admin/analytics-primitives";
import {
  defaultAnalyticsRange,
  formatCount,
  getProductAnalytics,
  toFunnelLabel,
  toSurfaceLabel,
  type AnalyticsRange,
  type ProductAnalytics
} from "@/lib/analytics-dashboard";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * Product_Analytics dashboard panel (Requirements 7.3, 7.5).
 *
 * Renders a date-range picker plus the four mutually-exclusive AsyncSection
 * states (loading / empty / error / populated). When the API returns
 * `has_data=false` for the selected range, an explicit empty state is shown
 * instead of the populated layout (Requirement 7.5). Error copy is routed
 * through `sanitizeUpstreamError` so no raw upstream detail reaches the admin
 * view. All styling uses design tokens.
 */

function buildState(
  loading: boolean,
  error: string,
  data: ProductAnalytics | null
): AsyncState<ProductAnalytics> {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: error };
  // Treat an explicit `has_data=false` range as empty (Requirement 7.5).
  if (!data || !data.has_data) return { kind: "empty" };
  return { kind: "populated", data };
}

export function ProductAnalyticsPanel() {
  const [range, setRange] = useState<Required<AnalyticsRange>>(() => defaultAnalyticsRange());
  const [data, setData] = useState<ProductAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (next: Required<AnalyticsRange>) => {
    setLoading(true);
    setError("");
    try {
      const result = await getProductAnalytics(next);
      setData(result);
    } catch (cause) {
      setData(null);
      setError(sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(range);
    // Initial load only; subsequent loads are triggered via onApply.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Emit a single named product event when the Product_Analytics dashboard is
  // opened (Req 9.1). No PII — only the coarse Admin view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "product_analytics" });
  }, []);

  const state = useMemo(() => buildState(loading, error, data), [loading, error, data]);

  return (
    <div className="space-y-5">
      <AnalyticsDateRange
        value={range}
        onChange={setRange}
        onApply={() => void load(range)}
        busy={loading}
      />

      <AsyncSection<ProductAnalytics>
        state={state}
        loadingLabel="Đang tải số liệu sản phẩm..."
        emptyTitle="Chưa có dữ liệu trong khoảng đã chọn"
        emptyDescription="Không có hoạt động người dùng nào trong khoảng ngày này. Hãy mở rộng khoảng thời gian để xem thêm."
      >
        {(analytics) => <ProductAnalyticsContent analytics={analytics} />}
      </AsyncSection>
    </div>
  );
}

function ProductAnalyticsContent({ analytics }: { analytics: ProductAnalytics }) {
  const totalActiveUsers = analytics.active_user_trend.reduce(
    (acc, point) => Math.max(acc, point.active_users),
    0
  );
  const totalSurfaceUsage = analytics.surface_usage.reduce((acc, row) => acc + row.count, 0);
  const totalRetained = analytics.retention.reduce(
    (acc, cohort) => acc + (typeof cohort.retained === "number" ? cohort.retained : 0),
    0
  );

  const trendPoints = analytics.active_user_trend.map((point) => ({
    label: point.date.slice(5), // MM-DD
    value: point.active_users
  }));

  const surfaceRows: BarRow[] = analytics.surface_usage
    .slice()
    .sort((a, b) => b.count - a.count)
    .map((row) => ({
      label: toSurfaceLabel(row.surface),
      value: row.count,
      display: formatCount(row.count),
      tone: "brand"
    }));

  const funnelRows: BarRow[] = analytics.funnels.map((stage) => ({
    label: toFunnelLabel(stage.stage),
    value: stage.count,
    display: formatCount(stage.count),
    tone: "neutral"
  }));

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Người dùng hoạt động (đỉnh)"
          value={formatCount(totalActiveUsers)}
          hint="Số người dùng hoạt động cao nhất trong một ngày"
        />
        <KpiCard
          label="Lượt dùng theo Surface"
          value={formatCount(totalSurfaceUsage)}
          hint="Tổng lượt tương tác trên các Surface"
        />
        <KpiCard
          label="Người dùng quay lại"
          value={formatCount(totalRetained)}
          hint="Tổng số người dùng được giữ chân theo cohort"
        />
      </div>

      <PanelCard
        title="Xu hướng người dùng hoạt động"
        description="Số người dùng hoạt động theo ngày trong khoảng đã chọn"
      >
        {trendPoints.length > 0 ? (
          <TrendBars points={trendPoints} />
        ) : (
          <p className="text-sm text-[var(--text-muted)]">Không có điểm dữ liệu xu hướng.</p>
        )}
      </PanelCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <PanelCard title="Mức độ sử dụng theo Surface" description="Lượt tương tác trên từng Surface">
          {surfaceRows.length > 0 ? (
            <BarList rows={surfaceRows} />
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Chưa có lượt sử dụng nào.</p>
          )}
        </PanelCard>

        <PanelCard title="Phễu chuyển đổi" description="Số người dùng theo từng bước">
          {funnelRows.length > 0 ? (
            <BarList rows={funnelRows} />
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Chưa có dữ liệu phễu.</p>
          )}
        </PanelCard>
      </div>

      <PanelCard title="Giữ chân theo cohort" description="Quy mô cohort và số người dùng quay lại">
        {analytics.retention.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                  <th className="py-2 pr-4 font-semibold">Cohort</th>
                  <th className="py-2 pr-4 font-semibold">Quy mô</th>
                  <th className="py-2 font-semibold">Giữ chân</th>
                </tr>
              </thead>
              <tbody>
                {analytics.retention.map((cohort, index) => (
                  <tr
                    key={typeof cohort.cohort === "string" ? cohort.cohort : index}
                    className="border-b border-[color:var(--shell-border)] last:border-0"
                  >
                    <td className="py-2 pr-4 text-[var(--text-primary)]">
                      {typeof cohort.cohort === "string" ? cohort.cohort : "--"}
                    </td>
                    <td className="py-2 pr-4 text-[var(--text-secondary)]">
                      {formatCount(typeof cohort.cohort_size === "number" ? cohort.cohort_size : null)}
                    </td>
                    <td className="py-2 text-[var(--text-secondary)]">
                      {formatCount(typeof cohort.retained === "number" ? cohort.retained : null)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">Chưa có dữ liệu cohort.</p>
        )}
      </PanelCard>

      <p className="text-xs text-[var(--text-muted)]">
        Cập nhật lúc {new Date(analytics.generated_at).toLocaleString("vi-VN")} · Khoảng{" "}
        {analytics.range[0]} → {analytics.range[1]}
      </p>
    </div>
  );
}

export default ProductAnalyticsPanel;
