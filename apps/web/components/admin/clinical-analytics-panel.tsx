"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import AnalyticsDateRange from "@/components/admin/analytics-date-range";
import {
  BarList,
  KpiCard,
  PanelCard,
  type BarRow
} from "@/components/admin/analytics-primitives";
import {
  defaultAnalyticsRange,
  formatCount,
  formatMs,
  formatPercent,
  getClinicalAnalytics,
  toTierLabel,
  type AnalyticsRange,
  type ClinicalAnalytics
} from "@/lib/analytics-dashboard";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";

/**
 * Clinical_Analytics dashboard panel (Requirements 8.3, 8.5, 4.3).
 *
 * Renders FIDES verdict distribution (including blocked CRITICAL claims), DDI
 * severity distribution, and per-tier latency percentiles for a selectable
 * date range, through the four mutually-exclusive AsyncSection states. This
 * surface is intentionally separate from the doctor-facing scribe
 * `/analytics/summary` (Requirement 8.5) and consumes only the admin-gated
 * `/system/analytics/clinical` endpoint. All styling uses design tokens.
 *
 * The raw pipeline-health telemetry (per-tier latency percentiles and router
 * confidence buckets) is wrapped in the shared role-gated `TelemetryPanel` so
 * the detailed view renders ONLY for Admin_Users (Requirement 4.3, Property
 * 11) — defense-in-depth on top of the admin-only route guard.
 */

function buildState(
  loading: boolean,
  error: string,
  data: ClinicalAnalytics | null
): AsyncState<ClinicalAnalytics> {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: error };
  if (!data || !data.has_data) return { kind: "empty" };
  return { kind: "populated", data };
}

export function ClinicalAnalyticsPanel() {
  const [range, setRange] = useState<Required<AnalyticsRange>>(() => defaultAnalyticsRange());
  const [data, setData] = useState<ClinicalAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Detailed telemetry visibility is a pure function of role (Req 4.3); hydrate
  // the role client-side so the gate matches the active session.
  const [role, setRole] = useState<UserRole>("normal");

  const load = useCallback(async (next: Required<AnalyticsRange>) => {
    setLoading(true);
    setError("");
    try {
      const result = await getClinicalAnalytics(next);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Emit a single named product event when the Clinical_Analytics dashboard is
  // opened (Req 9.1). No PII — only the coarse Admin view label. Hydrate the
  // role here too so the detailed-telemetry gate (Req 4.3) reflects the session.
  useEffect(() => {
    setRole(getRole());
    trackAdminSurfaceViewed({ view: "clinical_analytics" });
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

      <AsyncSection<ClinicalAnalytics>
        state={state}
        loadingLabel="Đang tải số liệu lâm sàng..."
        emptyTitle="Chưa có dữ liệu trong khoảng đã chọn"
        emptyDescription="Không có sự kiện kiểm chứng hoặc tương tác nào trong khoảng ngày này. Hãy mở rộng khoảng thời gian để xem thêm."
      >
        {(analytics) => <ClinicalAnalyticsContent analytics={analytics} role={role} />}
      </AsyncSection>
    </div>
  );
}

function ClinicalAnalyticsContent({
  analytics,
  role
}: {
  analytics: ClinicalAnalytics;
  role: UserRole;
}) {
  const { verdicts, ddi_severity, router_confidence } = analytics;

  const verdictRows: BarRow[] = [
    { label: "Đã kiểm chứng", value: verdicts.verified, display: formatCount(verdicts.verified), tone: "ok" },
    {
      label: "Kiểm chứng một phần",
      value: verdicts.partially_verified,
      display: formatCount(verdicts.partially_verified),
      tone: "warn"
    },
    { label: "Mâu thuẫn", value: verdicts.contested, display: formatCount(verdicts.contested), tone: "danger" },
    {
      label: "Không đủ căn cứ",
      value: verdicts.unsupported,
      display: formatCount(verdicts.unsupported),
      tone: "neutral"
    }
  ];

  const severityRows: BarRow[] = [
    { label: "Thấp", value: ddi_severity.low, display: formatCount(ddi_severity.low), tone: "ok" },
    { label: "Trung bình", value: ddi_severity.medium, display: formatCount(ddi_severity.medium), tone: "warn" },
    { label: "Cao", value: ddi_severity.high, display: formatCount(ddi_severity.high), tone: "danger" },
    {
      label: "Nghiêm trọng",
      value: ddi_severity.critical,
      display: formatCount(ddi_severity.critical),
      tone: "danger"
    }
  ];

  const confidenceRows: BarRow[] = Object.entries(router_confidence ?? {}).map(([bucket, count]) => ({
    label: bucket,
    value: typeof count === "number" ? count : 0,
    display: formatCount(typeof count === "number" ? count : 0),
    tone: "brand"
  }));

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Claim CRITICAL bị chặn"
          value={formatCount(verdicts.blocked_claims)}
          hint="Số claim CRITICAL bị FIDES chặn"
        />
        <KpiCard
          label="Tỉ lệ fallback"
          value={formatPercent(analytics.fallback_rate_pct)}
          hint="Tỉ lệ yêu cầu phải dùng đường dự phòng"
        />
        <KpiCard
          label="Lượt kiểm chứng"
          value={formatCount(
            verdicts.verified + verdicts.partially_verified + verdicts.contested + verdicts.unsupported
          )}
          hint="Tổng số phán quyết kiểm chứng FIDES"
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <PanelCard
          title="Phân bố phán quyết FIDES"
          description="Kết quả kiểm chứng claim theo từng nhóm"
        >
          <BarList rows={verdictRows} />
        </PanelCard>

        <PanelCard
          title="Phân bố mức độ tương tác (DDI)"
          description="Số cảnh báo tương tác theo mức độ nghiêm trọng"
        >
          <BarList rows={severityRows} />
        </PanelCard>
      </div>

      <TelemetryPanel
        role={role}
        summaryText="Chi tiết kỹ thuật về độ trễ và độ tin cậy của pipeline chỉ hiển thị cho quản trị viên."
      >
        <div className="space-y-5" data-testid="clinical-pipeline-telemetry">
          <PanelCard
            title="Độ trễ theo tier (percentile)"
            description="p50 / p90 / p99 cho từng tier xử lý"
          >
            {analytics.latency.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
                      <th className="py-2 pr-4 font-semibold">Tier</th>
                      <th className="py-2 pr-4 font-semibold">p50</th>
                      <th className="py-2 pr-4 font-semibold">p90</th>
                      <th className="py-2 font-semibold">p99</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.latency.map((row) => (
                      <tr
                        key={row.tier}
                        className="border-b border-[color:var(--shell-border)] last:border-0"
                      >
                        <td className="py-2 pr-4 text-[var(--text-primary)]">{toTierLabel(row.tier)}</td>
                        <td className="py-2 pr-4 text-[var(--text-secondary)]">{formatMs(row.p50_ms)}</td>
                        <td className="py-2 pr-4 text-[var(--text-secondary)]">{formatMs(row.p90_ms)}</td>
                        <td className="py-2 text-[var(--text-secondary)]">{formatMs(row.p99_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">Chưa có mẫu độ trễ.</p>
            )}
          </PanelCard>

          {confidenceRows.length > 0 ? (
            <PanelCard
              title="Độ tin cậy của Router"
              description="Phân nhóm độ tin cậy role/intent"
            >
              <BarList rows={confidenceRows} />
            </PanelCard>
          ) : null}
        </div>
      </TelemetryPanel>

      <p className="text-xs text-[var(--text-muted)]">
        Cập nhật lúc {new Date(analytics.generated_at).toLocaleString("vi-VN")} · Khoảng{" "}
        {analytics.range[0]} → {analytics.range[1]}
      </p>
    </div>
  );
}

export default ClinicalAnalyticsPanel;
