"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import AnalyticsDateRange from "@/components/admin/analytics-date-range";
import {
  BarList,
  KpiCard,
  PanelCard,
  type BarRow,
} from "@/components/admin/analytics-primitives";
import {
  defaultAnalyticsRange,
  formatCount,
  formatMs,
  formatPercent,
  getClinicalAnalytics,
  toTierLabel,
  type AnalyticsRange,
  type ClinicalAnalytics,
} from "@/lib/analytics-dashboard";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import {
  DEFAULT_BLOCKED_PATTERNS,
  type FidesBlockedPatternItem,
} from "@/lib/platform-analytics";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

/**
 * Clinical_Analytics dashboard panel (Spec v8 Section 12.4, Requirements 8.3, 8.5, 4.3).
 *
 * Renders:
 * 1. FIDES verdict breakdown (including blocked CRITICAL claims)
 * 2. DDI severity distribution (low, medium, high, critical)
 * 3. Top hazardous drug interaction pairs (with risk mechanism and evidence anchor)
 * 4. Latency percentiles (p50 / p90 / p99 per tier) & Router confidence distribution
 * 5. Role-gated TelemetryPanel and interactive Technical Inspector drawer.
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
  const [uiLanguage, setUiLanguage] = useState<UILanguage>(() => getStoredUILanguage());
  const [role, setRole] = useState<UserRole>("normal");

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    const unsub = onUILanguageChange(setUiLanguage);
    return unsub;
  }, []);

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
        loadingLabel={uiLanguage === "vi" ? "Đang tải số liệu lâm sàng..." : "Loading clinical analytics..."}
        emptyTitle={uiLanguage === "vi" ? "Chưa có dữ liệu trong khoảng đã chọn" : "No clinical data in selected range"}
        emptyDescription={
          uiLanguage === "vi"
            ? "Không có sự kiện kiểm chứng hoặc tương tác nào trong khoảng ngày này. Hãy mở rộng khoảng thời gian để xem thêm."
            : "No verification events or drug interactions recorded in this period. Broaden the date range to view data."
        }
      >
        {(analytics) => (
          <ClinicalAnalyticsContent
            analytics={analytics}
            role={role}
            uiLanguage={uiLanguage}
          />
        )}
      </AsyncSection>
    </div>
  );
}

function ClinicalAnalyticsContent({
  analytics,
  role,
  uiLanguage = "vi",
}: {
  analytics: ClinicalAnalytics;
  role: UserRole;
  uiLanguage?: UILanguage;
}) {
  const { verdicts, ddi_severity, router_confidence } = analytics;
  const isVi = uiLanguage === "vi";

  // Selected drug pair for inspector
  const [selectedPair, setSelectedPair] = useState<FidesBlockedPatternItem | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const hazardousDrugPairs: FidesBlockedPatternItem[] = useMemo(() => {
    if (analytics.top_hazardous_pairs && analytics.top_hazardous_pairs.length > 0) {
      return analytics.top_hazardous_pairs;
    }
    return DEFAULT_BLOCKED_PATTERNS;
  }, [analytics]);

  const verdictRows: BarRow[] = useMemo(() => {
    return [
      {
        label: isVi ? "Đã kiểm chứng (Verified)" : "Fully Verified",
        value: verdicts.verified,
        display: formatCount(verdicts.verified),
        tone: "ok",
      },
      {
        label: isVi ? "Kiểm chứng một phần (Partial)" : "Partially Verified",
        value: verdicts.partially_verified,
        display: formatCount(verdicts.partially_verified),
        tone: "warn",
      },
      {
        label: isVi ? "Khóa chặn CRITICAL (Blocked Claims)" : "Blocked CRITICAL Claims",
        value: verdicts.blocked_claims,
        display: formatCount(verdicts.blocked_claims),
        tone: "danger",
      },
      {
        label: isVi ? "Mâu thuẫn y văn (Contested)" : "Contested Evidence",
        value: verdicts.contested,
        display: formatCount(verdicts.contested),
        tone: "danger",
      },
      {
        label: isVi ? "Không đủ căn cứ (Unsupported)" : "Unsupported Claims",
        value: verdicts.unsupported,
        display: formatCount(verdicts.unsupported),
        tone: "neutral",
      },
    ];
  }, [verdicts, isVi]);

  const severityRows: BarRow[] = useMemo(() => {
    return [
      {
        label: isVi ? "Thấp (Low)" : "Low Severity",
        value: ddi_severity.low,
        display: formatCount(ddi_severity.low),
        tone: "ok",
      },
      {
        label: isVi ? "Trung bình (Medium)" : "Medium Severity",
        value: ddi_severity.medium,
        display: formatCount(ddi_severity.medium),
        tone: "warn",
      },
      {
        label: isVi ? "Cao (High)" : "High Severity",
        value: ddi_severity.high,
        display: formatCount(ddi_severity.high),
        tone: "danger",
      },
      {
        label: isVi ? "Nghiêm trọng (Critical)" : "Critical Severity",
        value: ddi_severity.critical,
        display: formatCount(ddi_severity.critical),
        tone: "danger",
      },
    ];
  }, [ddi_severity, isVi]);

  const confidenceRows: BarRow[] = useMemo(() => {
    return Object.entries(router_confidence ?? {}).map(([bucket, count]) => ({
      label: bucket,
      value: typeof count === "number" ? count : 0,
      display: formatCount(typeof count === "number" ? count : 0),
      tone: "brand",
    }));
  }, [router_confidence]);

  const totalEvaluations =
    verdicts.verified +
    verdicts.partially_verified +
    verdicts.contested +
    verdicts.unsupported;

  const handleOpenPair = (pair: FidesBlockedPatternItem) => {
    setSelectedPair(pair);
    setInspectorOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Top KPI Deck */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={isVi ? "Claim CRITICAL bị chặn" : "Blocked CRITICAL Claims"}
          value={formatCount(verdicts.blocked_claims)}
          hint={isVi ? "Số claim CRITICAL bị FIDES chặn" : "Claims halted by FIDES gate"}
        />
        <KpiCard
          label={isVi ? "Tỉ lệ fallback" : "Fallback Rate"}
          value={formatPercent(analytics.fallback_rate_pct)}
          hint={isVi ? "Tỉ lệ yêu cầu phải dùng đường dự phòng" : "Requests routed to fallback"}
        />
        <KpiCard
          label={isVi ? "Lượt kiểm chứng FIDES" : "FIDES Evaluations"}
          value={formatCount(totalEvaluations)}
          hint={isVi ? "Tổng số phán quyết kiểm chứng FIDES" : "Total verification verdicts"}
        />
        <KpiCard
          label={isVi ? "Tương tác DDI nghiêm trọng" : "Critical DDI Hazards"}
          value={formatCount(ddi_severity.critical)}
          hint={isVi ? "Cảnh báo DDI mức nguy hiểm cao" : "High-risk contraindicated DDI"}
        />
      </div>

      {/* 2-Column: FIDES Verdict Breakdown & DDI Severity Distribution */}
      <div className="grid gap-5 lg:grid-cols-2">
        <PanelCard
          title={isVi ? "Phân bố phán quyết FIDES" : "FIDES Verdict Distribution"}
          description={
            isVi
              ? "Kết quả kiểm chứng claim theo từng nhóm phán quyết"
              : "Claim verification outcomes grouped by decision class"
          }
        >
          <BarList rows={verdictRows} />
        </PanelCard>

        <PanelCard
          title={isVi ? "Phân bố mức độ tương tác (DDI)" : "DDI Severity Distribution"}
          description={
            isVi
              ? "Số cảnh báo tương tác thuốc theo mức độ nghiêm trọng"
              : "Drug-drug interaction warnings by clinical severity"
          }
        >
          <BarList rows={severityRows} />
        </PanelCard>
      </div>

      {/* Top Blocked Hazardous Drug Pairs Table */}
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-soft">
        <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="medication" size={16} className="text-[var(--status-danger-text)]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              {isVi
                ? "Cặp tương tác thuốc nguy hiểm bị FIDES khóa chặn (Top Hazardous Drug Pairs)"
                : "Top Blocked Dangerous Drug-Drug Interactions (FIDES DDI)"}
            </h3>
          </div>
          <Badge tone="danger" className="text-[10px]">
            {hazardousDrugPairs.length} {isVi ? "CẶP NGUY HIỂM" : "HAZARDS"}
          </Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs" aria-label="Hazardous Drug Pairs Table">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                <th scope="col" className="py-2.5 px-3">
                  {isVi ? "Cặp hoạt chất / Phối hợp" : "Drug Combination"}
                </th>
                <th scope="col" className="py-2.5 px-3">
                  {isVi ? "Hậu quả & Rủi ro lâm sàng" : "Clinical Hazard & Mechanism"}
                </th>
                <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                  {isVi ? "Số lần chặn" : "Blocks"}
                </th>
                <th scope="col" className="py-2.5 px-3 whitespace-nowrap">
                  {isVi ? "Mức độ" : "Severity"}
                </th>
                <th scope="col" className="py-2.5 px-3 text-right whitespace-nowrap">
                  {isVi ? "Nguồn chứng cứ" : "Evidence Anchor"}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)]">
              {hazardousDrugPairs.map((item, idx) => (
                <tr
                  key={idx}
                  onClick={() => handleOpenPair(item)}
                  className="transition hover:bg-[var(--surface-muted)]/60 cursor-pointer"
                >
                  <td className="py-2.5 px-3 font-mono font-bold text-[var(--text-primary)]">
                    {item.pattern}
                  </td>
                  <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                    {isVi ? item.riskTypeVi : item.riskTypeEn}
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-[var(--status-danger-text)]">
                    {item.count}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <Badge tone="danger" className="text-[10px]">
                      {item.severity.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-[11px] text-[var(--text-muted)]">
                    {item.guidelineAnchor}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Role-Gated Telemetry: Latency Percentiles & Router Confidence */}
      <TelemetryPanel
        role={role}
        summaryText={
          isVi
            ? "Chi tiết kỹ thuật về độ trễ và độ tin cậy của pipeline chỉ hiển thị cho quản trị viên."
            : "Technical latency percentiles and router confidence telemetry are restricted to administrators."
        }
      >
        <div className="space-y-5" data-testid="clinical-pipeline-telemetry">
          <PanelCard
            title={isVi ? "Độ trễ theo tier (percentile)" : "Per-Tier Latency Percentiles"}
            description={
              isVi
                ? "p50 / p90 / p99 cho từng tier xử lý trong pipeline"
                : "p50 / p90 / p99 across inference tiers"
            }
          >
            {analytics.latency.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs" aria-label="Clinical Latency Table">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <th className="py-2.5 pr-4">Tier</th>
                      <th className="py-2.5 pr-4 font-mono">p50</th>
                      <th className="py-2.5 pr-4 font-mono">p90</th>
                      <th className="py-2.5 font-mono text-right">p99</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {analytics.latency.map((row) => (
                      <tr
                        key={row.tier}
                        className="transition hover:bg-[var(--surface-muted)]/50"
                      >
                        <td className="py-2.5 pr-4 font-semibold text-[var(--text-primary)]">
                          {toTierLabel(row.tier)}
                        </td>
                        <td className="py-2.5 pr-4 font-mono text-[var(--text-secondary)]">
                          {formatMs(row.p50_ms)}
                        </td>
                        <td className="py-2.5 pr-4 font-mono text-[var(--text-secondary)]">
                          {formatMs(row.p90_ms)}
                        </td>
                        <td className="py-2.5 font-mono text-right font-bold text-[var(--text-brand)]">
                          {formatMs(row.p99_ms)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-[var(--text-muted)]">
                {isVi ? "Chưa có mẫu độ trễ." : "No latency samples available."}
              </p>
            )}
          </PanelCard>

          {confidenceRows.length > 0 ? (
            <PanelCard
              title={isVi ? "Độ tin cậy của Router" : "Router Intent & Role Confidence"}
              description={
                isVi
                  ? "Phân nhóm độ tin cậy role/intent của bộ định tuyến"
                  : "Confidence distribution of intent and role classification"
              }
            >
              <BarList rows={confidenceRows} />
            </PanelCard>
          ) : null}
        </div>
      </TelemetryPanel>

      {/* Footer Timestamp & Zero-PII Notice */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[color:var(--shell-border)]/60 pt-3 text-[11px] text-[var(--text-muted)]">
        <span>
          {isVi ? "Cập nhật lúc" : "Generated at"}{" "}
          {new Date(analytics.generated_at).toLocaleString(isVi ? "vi-VN" : "en-US")} ·{" "}
          {isVi ? "Khoảng" : "Range"} {analytics.range[0]} → {analytics.range[1]}
        </span>
        <span className="font-mono text-[10px]">ZERO-PII COMPLIANT · FIDES-V8</span>
      </div>

      {/* Inspector Slide-over for Selected Hazardous Drug Pair */}
      {selectedPair ? (
        <Inspector
          open={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
          title={
            isVi
              ? `Chi tiết Tương tác: ${selectedPair.pattern}`
              : `Drug Interaction Hazard: ${selectedPair.pattern}`
          }
          subtitle={
            isVi
              ? "Chi tiết cảnh báo an toàn FIDES DDI và nguồn chứng cứ y văn"
              : "FIDES DDI verification protocol and clinical evidence anchor"
          }
          badge={<Badge tone="danger">CRITICAL SAFETY</Badge>}
          size="md"
          density="compact"
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="text-[10px] font-mono text-[var(--text-muted)]">
                FIDES-GATE: ENFORCED
              </span>
              <Button size="sm" variant="secondary" onClick={() => setInspectorOpen(false)}>
                {isVi ? "Đóng" : "Close"}
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <InspectorSection
              title={isVi ? "Thông tin phối hợp thuốc" : "Combination Profile"}
              defaultExpanded
            >
              <div className="space-y-3 text-xs">
                <InspectorField
                  label={isVi ? "Cặp hoạt chất" : "Active Substances"}
                  value={selectedPair.pattern}
                />
                <InspectorField
                  label={isVi ? "Mức độ rủi ro" : "Severity Level"}
                  value={
                    <Badge tone="danger" className="text-xs">
                      {selectedPair.severity.toUpperCase()}
                    </Badge>
                  }
                />
                <InspectorField
                  label={isVi ? "Số lần FIDES đã chặn" : "Total Interventions"}
                  value={`${selectedPair.count} ${isVi ? "lần chặn" : "blocks"}`}
                />
                <InspectorField
                  label={isVi ? "Hậu quả & Cơ chế lâm sàng" : "Clinical Risk & Mechanism"}
                  value={isVi ? selectedPair.riskTypeVi : selectedPair.riskTypeEn}
                />
                <InspectorField
                  label={isVi ? "Nguồn chứng cứ / Phác đồ" : "Guideline Reference"}
                  value={selectedPair.guidelineAnchor}
                />
              </div>
            </InspectorSection>
          </div>
        </Inspector>
      ) : null}
    </div>
  );
}

export default ClinicalAnalyticsPanel;
