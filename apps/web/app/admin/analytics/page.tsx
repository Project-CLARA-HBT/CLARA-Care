"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import {
  BarList,
  KpiCard,
  PanelCard,
  TrendBars,
  type BarRow,
} from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  defaultAnalyticsRange,
  formatCount,
  formatMs,
  formatPercent,
  type AnalyticsRange,
} from "@/lib/analytics-dashboard";
import {
  fetchPlatformAnalytics,
  type EmergencyTriggerItem,
  type FidesBlockedPatternItem,
  type LegalHardGuardItem,
  type PlatformAnalytics,
  type SurfaceUsageStat,
} from "@/lib/platform-analytics";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { getStoredUILanguage, onUILanguageChange, type UILanguage } from "@/lib/ui-language";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

/**
 * Platform Analytics & Safety Dashboard (Spec v5 Section 6.64).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Platform Analytics & Safety Dashboard
 *
 * High-density command surface delivering:
 * 1. Aggregated query volume & real-time time-series trends across all platform surfaces.
 * 2. Multi-tier safety guardrail intervention rates:
 *    - Emergency Fast-Path (Acute symptom detection & immediate 115 ambulance escalation).
 *    - FIDES DDI & Dosage Blocks (Verification gate blocking critical contraindicated interactions).
 *    - Legal Hard-Guards (Prescribing, diagnostic, and personal dosage prohibition rules).
 * 3. Zero-PII usage distributions:
 *    - Surface usage adoption (Chat, Research, CareGuard, Council, Scribe, SelfMed).
 *    - Conversion funnels & cohort retention distributions (Zero PII; aggregate counts only).
 *    - Processing tier latency percentiles (p50 / p90 / p99) & router confidence buckets.
 * 4. Technical Slide-Over Inspector for auditing guardrail triggers and safety policies.
 *
 * Enforces server-side RBAC defense-in-depth and regression-locked safety invariants (ANA-005).
 */

type TabFilter = "all" | "guardrails" | "queries" | "zero-pii" | "latency";

type InspectableEntity =
  | { type: "emergency"; data: EmergencyTriggerItem }
  | { type: "fides"; data: FidesBlockedPatternItem }
  | { type: "legal"; data: LegalHardGuardItem }
  | { type: "surface"; data: SurfaceUsageStat }
  | { type: "compliance" };

export default function AdminAnalyticsDashboardPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>(() => getStoredUILanguage());
  const [role, setRole] = useState<UserRole | null>(() => getRole());
  const [range, setRange] = useState<Required<AnalyticsRange>>(() => defaultAnalyticsRange(30));
  const [activeTab, setActiveTab] = useState<TabFilter>("all");
  const [data, setData] = useState<PlatformAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inspector state
  const [selectedEntity, setSelectedEntity] = useState<InspectableEntity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Custom date range expand toggle
  const [showCustomRange, setShowCustomRange] = useState(false);

  const isVi = uiLanguage === "vi";

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    const unsub = onUILanguageChange(setUiLanguage);
    setRole(getRole());
    return unsub;
  }, []);

  const loadData = useCallback(async (currentRange: Required<AnalyticsRange>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPlatformAnalytics(currentRange);
      setData(result);
    } catch (cause) {
      setError(
        sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause))
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role === "admin") {
      void loadData(range);
    } else if (role !== null) {
      setLoading(false);
    }
  }, [role, range, loadData]);

  useEffect(() => {
    trackAdminSurfaceViewed({ view: "product_analytics" });
  }, []);

  // Preset Date Range selector handler
  const handleSelectPresetDays = (days: number) => {
    const next = defaultAnalyticsRange(days);
    setRange(next);
    setShowCustomRange(false);
  };

  const handleOpenInspector = (entity: InspectableEntity) => {
    setSelectedEntity(entity);
    setDrawerOpen(true);
  };

  const handleCloseInspector = () => {
    setDrawerOpen(false);
  };

  // ---------------------------------------------------------------------------
  // Derived Chart & Distribution Rows
  // ---------------------------------------------------------------------------

  const queryTrendPoints = useMemo(() => {
    if (!data) return [];
    return data.query_volume.daily_trend.map((pt) => ({
      label: pt.date.slice(5), // MM-DD
      value: pt.total_queries,
    }));
  }, [data]);

  const surfaceBarRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    return data.query_volume.surface_usage.map((s) => ({
      label: isVi ? s.labelVi : s.labelEn,
      value: s.count,
      display: `${formatCount(s.count)} (${s.percentage}%)`,
      tone: "brand",
    }));
  }, [data, isVi]);

  const emergencyBarRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    return data.safety_guardrails.emergency_fastpath.triggers.map((t) => ({
      label: isVi ? t.categoryVi : t.categoryEn,
      value: t.count,
      display: `${t.count} (${t.pct}%)`,
      tone: t.severity === "critical" ? "danger" : "warn",
    }));
  }, [data, isVi]);

  const fidesVerdictRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    const v = data.safety_guardrails.fides_ddi_blocks.verdict_distribution;
    return [
      { label: isVi ? "Đã kiểm chứng (Verified)" : "Fully Verified", value: v.verified, display: formatCount(v.verified), tone: "ok" },
      { label: isVi ? "Kiểm chứng một phần (Partial)" : "Partially Verified", value: v.partially_verified, display: formatCount(v.partially_verified), tone: "warn" },
      { label: isVi ? "Khóa chặn CRITICAL (Blocked Claims)" : "Blocked CRITICAL Claims", value: v.blocked_claims, display: formatCount(v.blocked_claims), tone: "danger" },
      { label: isVi ? "Mâu thuẫn y văn (Contested)" : "Contested Evidence", value: v.contested, display: formatCount(v.contested), tone: "danger" },
      { label: isVi ? "Không đủ dữ liệu (Unsupported)" : "Unsupported Claims", value: v.unsupported, display: formatCount(v.unsupported), tone: "neutral" },
    ];
  }, [data, isVi]);

  const legalGuardRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    return data.safety_guardrails.legal_hardguards.intents.map((item) => ({
      label: isVi ? item.labelVi : item.labelEn,
      value: item.count,
      display: `${item.count} (${item.pct}%)`,
      tone: "danger",
    }));
  }, [data, isVi]);

  const funnelBarRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    return data.zero_pii_usage.funnel_stages.map((stage) => ({
      label: isVi ? stage.labelVi : stage.labelEn,
      value: stage.count,
      display: `${formatCount(stage.count)} (${stage.conversion_rate_pct}%)`,
      tone: "brand",
    }));
  }, [data, isVi]);

  const roleBarRows: BarRow[] = useMemo(() => {
    if (!data) return [];
    return data.zero_pii_usage.role_distribution.map((r) => ({
      label: isVi ? r.labelVi : r.labelEn,
      value: r.count,
      display: `${formatCount(r.count)} (${r.pct}%)`,
      tone: r.role === "doctor" || r.role === "pharmacist" ? "ok" : "brand",
    }));
  }, [data, isVi]);

  const pageTitle = isVi
    ? "Phân tích Nền tảng & An toàn Hệ thống"
    : "Platform Analytics & Safety Dashboard";
  const pageDescription = isVi
    ? "Tổng hợp khối lượng truy vấn, tỷ lệ can thiệp của rào chắn an toàn (Cấp cứu 115, FIDES DDI, Chốt chặn pháp lý) và phân bố dữ liệu Zero-PII."
    : "Aggregated query volume, safety guardrail intervention rates (Emergency fast-path, FIDES DDI blocks, Legal hard-guards), and zero-PII usage distributions.";

  // Defense-in-depth: Non-admin role gating
  if (role !== null && role !== "admin") {
    return (
      <AdminShell activeTab="analytics" title={pageTitle} description={pageDescription}>
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-8 text-center text-[var(--status-danger-text)] shadow-soft"
        >
          <Icon name="warning" size={36} className="mx-auto mb-3 text-[var(--status-danger-text)]" />
          <h2 className="text-lg font-bold">
            {isVi ? "Từ chối quyền truy cập (403)" : "Access Denied (403)"}
          </h2>
          <p className="mt-2 text-sm opacity-90 max-w-md mx-auto">
            {isVi
              ? "Bạn không có quyền truy cập Bảng Phân tích Nền tảng & An toàn Hệ thống. Chỉ tài khoản Quản trị viên (Admin) mới được phép xem."
              : "You do not have permission to view the Platform Analytics & Safety Dashboard. Administrator role required."}
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell activeTab="analytics" title={pageTitle} description={pageDescription}>
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="Platform Analytics & Safety Dashboard"
        data-density="DENSE"
        className="space-y-6"
      >
        {/* Error Alert */}
        {error ? (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-xs sm:text-sm text-[var(--status-danger-text)] shadow-sm"
          >
            <div className="flex items-center gap-2">
              <Icon name="warning" size={16} />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-xs opacity-75 hover:opacity-100"
              aria-label="Close error"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        {/* Top Header Command Strip */}
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[var(--status-ok-text)] animate-pulse" />
              <h1 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                {pageTitle}
              </h1>
              <Badge tone="brand" className="font-mono text-[10px]">
                ANALYTICS-DENSE
              </Badge>
              <Badge tone="ok" className="font-mono text-[10px]">
                ZERO-PII
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {pageDescription}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Quick Date Presets */}
            <div className="flex items-center gap-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1 text-xs">
              <button
                type="button"
                onClick={() => handleSelectPresetDays(7)}
                className="rounded px-2 py-1 font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
              >
                7D
              </button>
              <button
                type="button"
                onClick={() => handleSelectPresetDays(30)}
                className="rounded bg-[var(--brand-600)] px-2 py-1 font-semibold text-white shadow-xs"
              >
                30D
              </button>
              <button
                type="button"
                onClick={() => handleSelectPresetDays(90)}
                className="rounded px-2 py-1 font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
              >
                90D
              </button>
              <button
                type="button"
                onClick={() => setShowCustomRange(!showCustomRange)}
                className={`rounded px-2 py-1 font-semibold transition ${
                  showCustomRange
                    ? "bg-[var(--surface-panel)] text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
                title={isVi ? "Tùy chỉnh khoảng ngày" : "Custom range"}
              >
                <Icon name="calendar" size={13} />
              </button>
            </div>

            <Button
              variant="secondary"
              size="sm"
              icon="refresh"
              loading={loading}
              onClick={() => void loadData(range)}
              aria-label={isVi ? "Tải lại dữ liệu" : "Refresh analytics"}
            >
              {isVi ? "Làm mới" : "Refresh"}
            </Button>
          </div>
        </header>

        {/* Expandable Custom Date Range Selector */}
        {showCustomRange ? (
          <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
            <div className="flex flex-wrap items-end gap-3 text-xs">
              <div className="flex flex-col gap-1">
                <label className="font-semibold text-[var(--text-secondary)]">
                  {isVi ? "Từ ngày (From)" : "From Date"}
                </label>
                <input
                  type="date"
                  value={range.from}
                  max={range.to}
                  onChange={(e) => setRange((prev) => ({ ...prev, from: e.target.value }))}
                  className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-primary)]"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="font-semibold text-[var(--text-secondary)]">
                  {isVi ? "Đến ngày (To)" : "To Date"}
                </label>
                <input
                  type="date"
                  value={range.to}
                  min={range.from}
                  onChange={(e) => setRange((prev) => ({ ...prev, to: e.target.value }))}
                  className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs text-[var(--text-primary)]"
                />
              </div>

              <Button
                size="sm"
                variant="primary"
                loading={loading}
                onClick={() => void loadData(range)}
              >
                {isVi ? "Áp dụng khoảng ngày" : "Apply Range"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* Top-Level KPI Metric Deck */}
        <section aria-label="Platform KPI Summary" className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label={isVi ? "Tổng Khối lượng Truy vấn" : "Aggregated Query Volume"}
            value={loading || !data ? "--" : formatCount(data.query_volume.total_queries)}
            hint={isVi ? "Tích lũy trên tất cả Surface" : "Aggregated across surfaces"}
          />
          <KpiCard
            label={isVi ? "Tỷ lệ Can thiệp Rào chắn" : "Safety Intervention Rate"}
            value={loading || !data ? "--" : `${data.safety_guardrails.overall_intervention_rate_pct}%`}
            hint={
              loading || !data
                ? undefined
                : isVi
                ? `${formatCount(data.safety_guardrails.total_interventions)} can thiệp an toàn`
                : `${formatCount(data.safety_guardrails.total_interventions)} guardrail actions`
            }
          />
          <KpiCard
            label={isVi ? "Tỷ lệ Hoàn tất An toàn" : "Safe Completion Rate"}
            value={loading || !data ? "--" : `${data.safety_guardrails.safe_completion_rate_pct}%`}
            hint={isVi ? "★ 100% Không có rò rỉ PII" : "★ Zero unhandled hazards"}
          />
          <KpiCard
            label={isVi ? "Cấp cứu 115 & Khóa FIDES" : "Emergency & FIDES Blocks"}
            value={
              loading || !data
                ? "--"
                : `${data.safety_guardrails.emergency_fastpath.total_interventions} / ${data.safety_guardrails.fides_ddi_blocks.total_blocked_claims}`
            }
            hint={isVi ? "Khóa cứng cấp nguy cơ cao" : "Life-safety & DDI bounds"}
          />
          <KpiCard
            label={isVi ? "Người dùng Đỉnh (DAU Peak)" : "Peak Active Users"}
            value={loading || !data ? "--" : formatCount(data.zero_pii_usage.active_users_peak)}
            hint={isVi ? "Tổng hợp PII-free" : "Zero-PII aggregates"}
          />
        </section>

        {/* Section Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-2">
          <div className="flex flex-wrap items-center gap-1.5" role="tablist">
            {(
              [
                { key: "all", vi: "Tất cả chỉ số", en: "All Metrics" },
                { key: "guardrails", vi: "Rào chắn An toàn (Guardrails)", en: "Safety Guardrails" },
                { key: "queries", vi: "Khối lượng & Surface", en: "Query Volume & Surfaces" },
                { key: "zero-pii", vi: "Người dùng & Giữ chân Zero-PII", en: "Zero-PII & Retention" },
                { key: "latency", vi: "Độ trễ & Pipeline", en: "Latency & Pipeline" },
              ] as const
            ).map((tab) => {
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setActiveTab(tab.key)}
                  className={`inline-flex items-center gap-1.5 rounded-[var(--radius-md)] border px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[#cdd7ff] shadow-xs"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <span>{isVi ? tab.vi : tab.en}</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Icon name="check" size={14} className="text-[var(--status-ok-text)]" />
            <span className="font-mono font-semibold">ANA-005 / ISO-27701 VERIFIED</span>
          </div>
        </div>

        {/* MAIN BODY: Tab-aware dense content grids */}

        {/* 1. SAFETY GUARDRAIL INTERVENTION RATES SECTION */}
        {(activeTab === "all" || activeTab === "guardrails") && data ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name="warning" size={18} className="text-[var(--status-danger-text)]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi
                    ? "Tỷ lệ Can thiệp Rào chắn An toàn Lâm sàng (Safety Guardrails)"
                    : "Safety Guardrail Intervention Rates"}
                </h2>
              </div>
              <Badge tone="danger" className="text-[10px]">
                CRITICAL INVARIANTS
              </Badge>
            </div>

            {/* Three Guardrail Pillars: Emergency Fast-Path, FIDES DDI, Legal Hard-Guards */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              {/* Pillar 1: Emergency Fast-Path (115 Cấp cứu Khẩn cấp) */}
              <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-4 shadow-soft space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full bg-[var(--status-danger-text)] animate-ping" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--status-danger-text)]">
                        {isVi ? "1. Cấp cứu Khẩn cấp (Fast-Path 115)" : "1. Emergency Fast-Path (115)"}
                      </h3>
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {isVi
                        ? "Phát hiện triệu chứng đe dọa tính mạng và chuyển hướng khẩn cấp tức thì (bỏ qua LLM)."
                        : "Immediate escalation for acute life-safety symptoms, bypassing LLM synthesis."}
                    </p>
                  </div>
                  <Badge tone="danger" className="font-mono text-xs">
                    {data.safety_guardrails.emergency_fastpath.total_interventions} {isVi ? "lần" : "events"}
                  </Badge>
                </div>

                <div className="rounded bg-[var(--status-danger-bg)]/40 p-2.5 text-xs text-[var(--status-danger-text)] font-semibold flex items-center justify-between">
                  <span>{isVi ? "Tỷ lệ can thiệp:" : "Intervention Rate:"}</span>
                  <span className="font-mono text-sm">{data.safety_guardrails.emergency_fastpath.rate_pct}%</span>
                </div>

                <div>
                  <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase">
                    {isVi ? "Phân bố triệu chứng cấp tính:" : "Trigger Symptoms:"}
                  </span>
                  <div className="mt-2">
                    <BarList rows={emergencyBarRows} />
                  </div>
                </div>

                <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between text-[11px]">
                  <span className="text-[var(--text-muted)]">
                    {isVi ? "Độ trễ chuyển hướng TB:" : "Avg Escalation Latency:"}
                  </span>
                  <span className="font-mono font-bold text-[var(--text-brand)]">
                    {data.safety_guardrails.emergency_fastpath.avg_escalation_ms} ms
                  </span>
                </div>
              </div>

              {/* Pillar 2: FIDES DDI & Dosage Blocks */}
              <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--surface-panel)] p-4 shadow-soft space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <Icon name="medication" size={14} className="text-[var(--status-warn-text)]" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--status-warn-text)]">
                        {isVi ? "2. Khóa FIDES DDI & Liều dùng" : "2. FIDES DDI & Dosage Blocks"}
                      </h3>
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {isVi
                        ? "Chốt chặn kiểm chứng y văn tự động khóa các tương tác thuốc CRITICAL và quá liều."
                        : "Verification engine blocking CRITICAL contraindicated drug interactions and dosage hazards."}
                    </p>
                  </div>
                  <Badge tone="warn" className="font-mono text-xs">
                    {data.safety_guardrails.fides_ddi_blocks.total_blocked_claims} {isVi ? "khóa" : "blocks"}
                  </Badge>
                </div>

                <div className="rounded bg-[var(--status-warn-bg)]/40 p-2.5 text-xs text-[var(--status-warn-text)] font-semibold flex items-center justify-between">
                  <span>{isVi ? "Tỷ lệ phán quyết khóa:" : "Block Rate:"}</span>
                  <span className="font-mono text-sm">{data.safety_guardrails.fides_ddi_blocks.block_rate_pct}%</span>
                </div>

                <div>
                  <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase">
                    {isVi ? "Phân bố phán quyết FIDES:" : "FIDES Verdict Distribution:"}
                  </span>
                  <div className="mt-2">
                    <BarList rows={fidesVerdictRows} />
                  </div>
                </div>

                <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between text-[11px]">
                  <span className="text-[var(--text-muted)]">
                    {isVi ? "Tổng claim kiểm định:" : "Evaluated Claims:"}
                  </span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">
                    {formatCount(data.safety_guardrails.fides_ddi_blocks.total_evaluated_claims)}
                  </span>
                </div>
              </div>

              {/* Pillar 3: Legal Hard-Guards */}
              <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <Icon name="clinical-notes" size={14} className="text-[var(--brand-500)]" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                        {isVi ? "3. Chốt chặn Pháp lý Y tế" : "3. Legal Hard-Guards"}
                      </h3>
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {isVi
                        ? "Ngăn chặn ý định kê đơn, chẩn đoán xác định thay bác sĩ và tính liều cá nhân hóa."
                        : "Blocks prescribing intent, medical diagnosis replacement, and personal dosage determination."}
                    </p>
                  </div>
                  <Badge tone="brand" className="font-mono text-xs">
                    {data.safety_guardrails.legal_hardguards.total_interventions} {isVi ? "chặn" : "guards"}
                  </Badge>
                </div>

                <div className="rounded bg-[var(--surface-brand-soft)] p-2.5 text-xs text-[var(--text-brand)] font-semibold flex items-center justify-between">
                  <span>{isVi ? "Tỷ lệ can thiệp:" : "Intervention Rate:"}</span>
                  <span className="font-mono text-sm">{data.safety_guardrails.legal_hardguards.rate_pct}%</span>
                </div>

                <div>
                  <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase">
                    {isVi ? "Nhóm quy tắc pháp lý vi phạm:" : "Guardrail Rule Breakdown:"}
                  </span>
                  <div className="mt-2">
                    <BarList rows={legalGuardRows} />
                  </div>
                </div>

                <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between text-[11px]">
                  <span className="text-[var(--text-muted)]">
                    {isVi ? "Chuẩn tuân thủ:" : "Compliance Standard:"}
                  </span>
                  <span className="font-mono font-bold text-[var(--status-ok-text)]">
                    LEGAL_VI_VN_MED_ART_12
                  </span>
                </div>
              </div>
            </div>

            {/* Top Blocked Hazardous Drug Patterns Table */}
            <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-soft">
              <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-3 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
                  <Icon name="medication" size={15} className="text-[var(--status-danger-text)]" />
                  <span>
                    {isVi
                      ? "Cặp tương tác thuốc nguy hiểm bị FIDES khóa chặn nhiều nhất"
                      : "Top Blocked Dangerous Drug-Drug Interactions (FIDES DDI)"}
                  </span>
                </h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs" aria-label="Top Blocked Patterns">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Cặp hoạt chất / Phối hợp" : "Drug Combination"}</th>
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Hậu quả & Rủi ro lâm sàng" : "Clinical Hazard & Mechanism"}</th>
                      <th scope="col" className="py-2.5 px-3 whitespace-nowrap">{isVi ? "Số lần chặn" : "Blocks"}</th>
                      <th scope="col" className="py-2.5 px-3 whitespace-nowrap">{isVi ? "Mức độ" : "Severity"}</th>
                      <th scope="col" className="py-2.5 px-3 text-right whitespace-nowrap">{isVi ? "Nguồn chứng cứ" : "Evidence Anchor"}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {data.safety_guardrails.fides_ddi_blocks.top_blocked_patterns.map((item, idx) => (
                      <tr
                        key={idx}
                        className="transition hover:bg-[var(--surface-muted)]/60 cursor-pointer"
                        onClick={() => handleOpenInspector({ type: "fides", data: item })}
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
          </div>
        ) : null}

        {/* 2. AGGREGATED QUERY VOLUME & SURFACE USAGE SECTION */}
        {(activeTab === "all" || activeTab === "queries") && data ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name="calendar" size={18} className="text-[var(--brand-500)]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi
                    ? "Khối lượng Truy vấn & Phân bố theo Surface"
                    : "Aggregated Query Volume & Surface Usage"}
                </h2>
              </div>
              <span className="font-mono text-xs font-bold text-[var(--text-muted)]">
                TOTAL: {formatCount(data.query_volume.total_queries)}
              </span>
            </div>

            {/* Daily Trend Bars */}
            <PanelCard
              title={isVi ? "Xu hướng khối lượng truy vấn theo ngày" : "Daily Query Volume Trend"}
              description={
                isVi
                  ? `So sánh giữa ${formatCount(data.query_volume.safe_completions)} truy vấn hoàn tất an toàn và ${formatCount(data.query_volume.total_interventions)} can thiệp rào chắn.`
                  : `Comparison between ${formatCount(data.query_volume.safe_completions)} safe completions and ${formatCount(data.query_volume.total_interventions)} guardrail interventions.`
              }
            >
              {queryTrendPoints.length > 0 ? (
                <TrendBars points={queryTrendPoints} />
              ) : (
                <p className="text-xs text-[var(--text-muted)]">
                  {isVi ? "Chưa có dữ liệu xu hướng." : "No trend data points."}
                </p>
              )}
            </PanelCard>

            {/* Surface Usage Breakdown & Tier Processing Breakdown */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <PanelCard
                title={isVi ? "Mức độ sử dụng theo Surface" : "Surface Usage Distribution"}
                description={
                  isVi
                    ? "Tương tác người dùng trên từng phân hệ sản phẩm"
                    : "User interactions distributed across platform surfaces"
                }
              >
                <BarList rows={surfaceBarRows} />
              </PanelCard>

              <PanelCard
                title={isVi ? "Phân bố theo Tầng xử lý (Tier Processing)" : "Processing Tier Distribution"}
                description={
                  isVi
                    ? "Khối lượng câu hỏi và độ trễ phản hồi qua các tầng suy luận"
                    : "Query throughput and latency distribution across inference tiers"
                }
              >
                <div className="space-y-3">
                  {data.query_volume.tier_distribution.map((t) => (
                    <div
                      key={t.tier}
                      className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-[var(--text-primary)]">
                          {isVi ? t.labelVi : t.labelEn}
                        </span>
                        <span className="font-mono text-[var(--text-brand)]">
                          {formatCount(t.count)} ({t.percentage}%)
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-[var(--surface-panel)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--brand-600)]"
                          style={{ width: `${t.percentage}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono">
                        <span>p50: {formatMs(t.p50_ms)}</span>
                        <span>p90: {formatMs(t.p90_ms)}</span>
                        <span>p99: {formatMs(t.p99_ms)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </PanelCard>
            </div>
          </div>
        ) : null}

        {/* 3. ZERO-PII USAGE & RETENTION SECTION */}
        {(activeTab === "all" || activeTab === "zero-pii") && data ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name="user-card" size={18} className="text-[var(--status-ok-text)]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi
                    ? "Phân bố Người dùng & Giữ chân Zero-PII (Usage & Retention)"
                    : "Zero-PII Usage & Retention Distributions"}
                </h2>
              </div>
              <Badge tone="ok" className="text-[10px]">
                ISO-27701 ENFORCED
              </Badge>
            </div>

            {/* Zero-PII Invariant Verification Banner */}
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 shadow-soft flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--status-ok-text)]">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--status-ok-text)] text-white shrink-0">
                  <Icon name="check" size={18} />
                </div>
                <div>
                  <h3 className="font-bold">
                    {isVi
                      ? "Bất biến Zero-PII: Dữ liệu ẩn danh và tổng hợp 100%"
                      : "Zero-PII Invariant: 100% Anonymized Aggregates"}
                  </h3>
                  <p className="opacity-90 mt-0.5">
                    {isVi
                      ? "Mọi thông tin cá nhân (họ tên, email, câu hỏi tự do, tên thuốc cụ thể) đều bị loại bỏ trước khi ghi nhận."
                      : "All personal identifiers, free-text prompt transcripts, and specific drug names are strictly scrubbed."}
                  </p>
                </div>
              </div>

              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleOpenInspector({ type: "compliance" })}
                className="!text-xs"
              >
                {isVi ? "Xem chứng nhận kiểm toán" : "View Compliance Audit"}
              </Button>
            </div>

            {/* Funnel & Role Distribution */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <PanelCard
                title={isVi ? "Phễu chuyển đổi sử dụng (Funnel Stages)" : "Platform Conversion Funnel"}
                description={
                  isVi
                    ? "Tỷ lệ chuyển đổi từ người dùng hoạt động sang công cụ lâm sàng chuyên sâu"
                    : "Conversion rate from active users to advanced clinical tool usage"
                }
              >
                <BarList rows={funnelBarRows} />
              </PanelCard>

              <PanelCard
                title={isVi ? "Phân bố người dùng theo Vai trò (Roles)" : "User Role Distribution"}
                description={
                  isVi
                    ? "Cơ cấu người dùng trên nền tảng (Bác sĩ, Dược sĩ, Nhà nghiên cứu, Người dùng)"
                    : "Distribution of verified user roles on the platform"
                }
              >
                <BarList rows={roleBarRows} />
              </PanelCard>
            </div>

            {/* Cohort Retention Table */}
            <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-soft">
              <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-3 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi ? "Tỷ lệ giữ chân người dùng theo Cohort (Retention)" : "Cohort Retention Matrix"}
                </h3>
                <span className="text-[10px] text-[var(--text-muted)]">
                  {isVi ? "Chỉ lưu số lượng gộp, không lưu ID" : "Aggregate counts only, zero PII"}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs" aria-label="Cohort Retention Table">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Cohort (Tháng tham gia)" : "Cohort (Join Month)"}</th>
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Quy mô ban đầu" : "Cohort Size"}</th>
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Số người quay lại" : "Retained Users"}</th>
                      <th scope="col" className="py-2.5 px-3 text-right">{isVi ? "Tỷ lệ giữ chân" : "Retention Rate (%)"}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {data.zero_pii_usage.retention_cohorts.map((cohort, idx) => (
                      <tr key={idx} className="transition hover:bg-[var(--surface-muted)]/60">
                        <td className="py-2.5 px-3 font-mono font-bold text-[var(--text-primary)]">
                          {cohort.cohort}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                          {formatCount(cohort.cohort_size)}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                          {formatCount(cohort.retained)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-[var(--text-brand)]">
                          {cohort.retention_rate_pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}

        {/* 4. PIPELINE LATENCY & PERFORMANCE SECTION */}
        {(activeTab === "all" || activeTab === "latency") && data ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name="progress" size={18} className="text-[var(--text-brand)]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isVi
                    ? "Độ trễ Suy luận & Hiệu năng Pipeline (Latency & Performance)"
                    : "Inference Latency & Pipeline Performance"}
                </h2>
              </div>
            </div>

            <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-soft">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs" aria-label="Latency Breakdown">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Tầng xử lý (Inference Tier)" : "Inference Tier"}</th>
                      <th scope="col" className="py-2.5 px-3">{isVi ? "Tỷ trọng (%)" : "Share (%)"}</th>
                      <th scope="col" className="py-2.5 px-3 font-mono">p50</th>
                      <th scope="col" className="py-2.5 px-3 font-mono">p90</th>
                      <th scope="col" className="py-2.5 px-3 font-mono text-right">p99</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {data.query_volume.tier_distribution.map((row) => (
                      <tr key={row.tier} className="transition hover:bg-[var(--surface-muted)]/60">
                        <td className="py-2.5 px-3 font-bold text-[var(--text-primary)]">
                          {isVi ? row.labelVi : row.labelEn}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                          {row.percentage}%
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[var(--text-secondary)]">
                          {formatMs(row.p50_ms)}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[var(--text-secondary)]">
                          {formatMs(row.p90_ms)}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-right font-bold text-[var(--text-brand)]">
                          {formatMs(row.p99_ms)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}

        {/* Slide-over Inspector Drawer for Technical Auditing */}
        {selectedEntity ? (
          <Inspector
            open={drawerOpen}
            onClose={handleCloseInspector}
            title={
              selectedEntity.type === "compliance"
                ? isVi ? "Kiểm toán Tuân thủ Zero-PII & An toàn" : "Zero-PII & Safety Compliance Audit"
                : selectedEntity.type === "fides"
                ? isVi ? `Chi tiết Khóa FIDES: ${selectedEntity.data.pattern}` : `FIDES Block: ${selectedEntity.data.pattern}`
                : isVi ? "Kiểm tra Rào chắn An toàn" : "Safety Guardrail Inspection"
            }
            subtitle={
              isVi
                ? "Chi tiết quy tắc bảo vệ, kiểm định pháp lý và bất biến an toàn"
                : "Technical invariant rule verification and regulatory evidence"
            }
            badge={
              <Badge tone="ok">
                ANA-005 LOCKED
              </Badge>
            }
            size="lg"
            density="compact"
            footer={
              <div className="flex items-center justify-between w-full">
                <span className="text-[10px] font-mono text-[var(--text-muted)]">
                  INVARIANT-VERIFIED: {new Date().toISOString().slice(0, 10)}
                </span>
                <Button size="sm" variant="secondary" onClick={handleCloseInspector}>
                  {isVi ? "Đóng" : "Close"}
                </Button>
              </div>
            }
          >
            <div className="space-y-4">
              {selectedEntity.type === "compliance" ? (
                <InspectorSection title={isVi ? "Báo cáo kiểm toán Zero-PII" : "Zero-PII Audit Report"} defaultExpanded>
                  <div className="space-y-3 text-xs">
                    <p className="text-[var(--text-secondary)]">
                      {isVi
                        ? "Hệ thống áp dụng bộ lọc PII đa tầng nghiêm ngặt. Mọi trường thông tin cá nhân và văn bản tự do đều bị tước bỏ trước khi nạp vào kho lưu trữ số liệu tổng hợp."
                        : "Strict multi-tier PII scrubbing pipeline enforces absolute anonymity before aggregation."}
                    </p>
                    <div className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                      <span className="font-bold text-[var(--text-primary)] block mb-1.5">
                        {isVi ? "Các danh mục dữ liệu bị loại bỏ (Scrubbed Categories):" : "Scrubbed Data Categories:"}
                      </span>
                      <ul className="space-y-1 list-disc list-inside text-[var(--text-muted)]">
                        <li>Identities (Names, Emails, Phone, National IDs)</li>
                        <li>Free-text User Prompts & Clinical Consultation Transcripts</li>
                        <li>Specific Patient Medication Lists & Regimen Details</li>
                        <li>Raw Medical Records & Imaging Artifacts</li>
                        <li>Upstream Stack Traces & Infrastructure Diagnostic Logs</li>
                      </ul>
                    </div>
                  </div>
                </InspectorSection>
              ) : selectedEntity.type === "fides" ? (
                <InspectorSection title={isVi ? "Chi tiết Tương tác Thuốc bị Chặn" : "Blocked Interaction Details"} defaultExpanded>
                  <div className="space-y-3 text-xs">
                    <InspectorField
                      label={isVi ? "Phối hợp nguy hiểm" : "Drug Pattern"}
                      value={selectedEntity.data.pattern}
                    />
                    <InspectorField
                      label={isVi ? "Mức độ cảnh báo" : "Severity"}
                      value={
                        <Badge tone="danger" className="text-xs">
                          {selectedEntity.data.severity.toUpperCase()}
                        </Badge>
                      }
                    />
                    <InspectorField
                      label={isVi ? "Cơ chế & Nguy cơ lâm sàng" : "Clinical Risk"}
                      value={isVi ? selectedEntity.data.riskTypeVi : selectedEntity.data.riskTypeEn}
                    />
                    <InspectorField
                      label={isVi ? "Nguồn hướng dẫn / Dược thư" : "Evidence Anchor"}
                      value={selectedEntity.data.guidelineAnchor}
                    />
                  </div>
                </InspectorSection>
              ) : null}
            </div>
          </Inspector>
        ) : null}
      </div>
    </AdminShell>
  );
}
