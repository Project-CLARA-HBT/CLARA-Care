"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import {
  BarList,
  KpiCard,
  PanelCard,
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
  fetchSystemTelemetry,
  getSanitizedEnvironmentJson,
  type ErrorCategoryBreakdown,
  type LatencyPercentileTier,
  type RouteLatencyMetric,
  type ServiceHealthCardData,
  type ServiceId,
  type ServiceTier,
  type SystemTelemetrySnapshot,
} from "@/lib/admin-system";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * System Telemetry & Health Dashboard (Spec v8 Section 12.9, Spec v5 Section 6.63).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: System Telemetry & Health
 *
 * Comprehensive real-time observability, health monitoring, latency percentiles,
 * error rate breakdown, and environment configuration inspector across all 6 core
 * services: API Gateway, ML Inference, PostgreSQL Database, Redis Cache/Queue,
 * OCR Prescription Sidecar, and ASR Scribe Sidecar.
 *
 * Enforces Zero-PII invariants and authoritative RBAC defense-in-depth.
 */

type ServiceFilterTab = "all" | "core" | "reasoning" | "data" | "multimodal" | "attention";

export default function AdminSystemTelemetryPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Telemetry Snapshot
  const [snapshot, setSnapshot] = useState<SystemTelemetrySnapshot | null>(null);

  // Auto-refresh interval (seconds, 0 = paused)
  const [refreshInterval, setRefreshInterval] = useState<number>(15);

  // Filters & Search
  const [filterTab, setFilterTab] = useState<ServiceFilterTab>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Inspectors (Environment Inspector & Service Inspector)
  const [isEnvInspectorOpen, setIsEnvInspectorOpen] = useState(false);
  const [selectedService, setSelectedService] = useState<ServiceHealthCardData | null>(null);
  const [isEnvJsonView, setIsEnvJsonView] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  const loadTelemetry = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    setError(null);
    try {
      const data = await fetchSystemTelemetry();
      setSnapshot(data);
    } catch (err) {
      setError(safeUserFacingError(err, uiLanguage === "vi" ? "Lỗi tải telemetry" : "Failed to load telemetry"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [uiLanguage]);

  useEffect(() => {
    void loadTelemetry();
  }, [loadTelemetry]);

  // Auto-refresh timer loop
  useEffect(() => {
    if (refreshInterval <= 0) return;
    const timer = setInterval(() => {
      void loadTelemetry(false);
    }, refreshInterval * 1000);
    return () => clearInterval(timer);
  }, [refreshInterval, loadTelemetry]);

  const isEn = uiLanguage === "en";

  // Filtered Services List
  const filteredServices = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.services.filter((svc) => {
      const matchesSearch =
        searchQuery.trim() === "" ||
        svc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        svc.nameVi.toLowerCase().includes(searchQuery.toLowerCase()) ||
        svc.endpoint.toLowerCase().includes(searchQuery.toLowerCase()) ||
        svc.version.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      if (filterTab === "all") return true;
      if (filterTab === "attention") return svc.status !== "healthy";
      return svc.tier === filterTab;
    });
  }, [snapshot, filterTab, searchQuery]);

  // Error categories as BarRows for BarList primitive
  const errorBarRows = useMemo<BarRow[]>(() => {
    if (!snapshot) return [];
    return snapshot.errorCategories.map((item) => ({
      label: isEn ? item.categoryEn : item.categoryVi,
      value: item.percentage,
      display: `${item.percentage.toFixed(1)}% (${item.count} reqs)`,
      tone: item.tone,
    }));
  }, [snapshot, isEn]);

  const handleCopyEnvConfig = useCallback(() => {
    if (!snapshot) return;
    const json = getSanitizedEnvironmentJson(snapshot.envConfig);
    void navigator.clipboard.writeText(json);
    setIsCopied(true);
    setToastMessage(
      isEn
        ? "Sanitized configuration manifest copied to clipboard!"
        : "Đã sao chép cấu hình môi trường đã chuẩn hóa vào clipboard!"
    );
    setTimeout(() => {
      setIsCopied(false);
      setToastMessage(null);
    }, 3500);
  }, [snapshot, isEn]);

  const getSlaBadge = (status: "nominal" | "warning" | "breached") => {
    if (status === "nominal") {
      return (
        <Badge tone="ok" icon="check">
          {isEn ? "SLA Met" : "Đạt SLA"}
        </Badge>
      );
    }
    if (status === "warning") {
      return (
        <Badge tone="warn" icon="warning">
          {isEn ? "Near SLA" : "Gần ngưỡng"}
        </Badge>
      );
    }
    return (
      <Badge tone="danger" icon="warning">
        {isEn ? "SLA Breached" : "Vi phạm SLA"}
      </Badge>
    );
  };

  const getStatusChipForService = (status: "healthy" | "degraded" | "down") => {
    if (status === "healthy") {
      return <StatusChip tone="success" label={isEn ? "Healthy" : "Hoạt động"} size="sm" />;
    }
    if (status === "degraded") {
      return <StatusChip tone="warning" label={isEn ? "Degraded" : "Suy giảm"} size="sm" />;
    }
    return <StatusChip tone="danger" label={isEn ? "Down / Offline" : "Ngừng hoạt động"} size="sm" />;
  };

  // RBAC Access Control Defense-in-Depth
  const isAuthorized = role === "admin" || role === "doctor";
  if (role && !isAuthorized) {
    return (
      <AdminShell
        activeTab="system"
        title={isEn ? "System Telemetry & Health" : "Giám sát Hệ thống & Sức khỏe"}
        description={
          isEn
            ? "Real-time service health, latency percentiles, error rate charts, and environment configuration."
            : "Giám sát thời gian thực sức khỏe dịch vụ, percentiles độ trễ, biểu đồ lỗi và cấu hình môi trường."
        }
      >
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/20 p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]">
            <Icon name="warning" size={24} />
          </div>
          <h3 className="mt-4 text-base font-bold text-[var(--text-primary)]">
            {isEn ? "Access Restricted" : "Không đủ quyền truy cập"}
          </h3>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            {isEn
              ? "You do not have permission to view administrative system telemetry and environment configuration."
              : "Bạn không có quyền truy cập vào bảng điều khiển giám sát hệ thống và cấu hình môi trường quản trị."}
          </p>
        </div>
      </AdminShell>
    );
  }

  const pageTitle = isEn ? "System Telemetry & Health" : "Giám sát Hệ thống & Sức khỏe Dịch vụ";
  const pageDescription = isEn
    ? "Real-time service health cards (API, ML, Database, Redis, OCR, ASR), latency percentiles, error rate analytics, and environment configuration inspector."
    : "Bảng điều khiển giám sát thời gian thực 6 dịch vụ trọng yếu (API, ML, DB, Redis, OCR, ASR), phân vị độ trễ p50/p90/p95/p99, phân tích tỉ lệ lỗi và cấu hình môi trường.";

  return (
    <AdminShell activeTab="system" title={pageTitle} description={pageDescription}>
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="System Telemetry & Health"
        data-density="DENSE"
        className="space-y-5"
      >
        {/* Toast message banner */}
      {toastMessage ? (
        <div
          role="status"
          className="flex items-center justify-between rounded-xl border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] p-3 text-xs font-semibold text-[var(--text-brand)] shadow-sm animate-in fade-in"
        >
          <div className="flex items-center gap-2">
            <Icon name="check" size={16} />
            <span>{toastMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setToastMessage(null)}
            className="text-[var(--text-brand)] hover:opacity-80"
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      ) : null}

      {/* Top Command Bar / Control Strip */}
      <div className="flex flex-col gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`h-3 w-3 rounded-full ${
                snapshot?.overallStatus === "healthy"
                  ? "bg-[var(--status-success-text)] shadow-[0_0_8px_var(--status-success-text)]"
                  : snapshot?.overallStatus === "degraded"
                    ? "bg-[var(--status-warning-text)] shadow-[0_0_8px_var(--status-warning-text)] animate-pulse"
                    : "bg-[var(--status-danger-text)] shadow-[0_0_8px_var(--status-danger-text)] animate-ping"
              }`}
            />
            <h1 className="text-base font-bold text-[var(--text-primary)] sm:text-lg">
              {isEn ? "System Telemetry & Health" : "Giám sát Hệ thống & Sức khỏe"}
            </h1>
          </div>

          {snapshot ? (
            <div className="flex items-center gap-1.5">
              <StatusChip
                tone={snapshot.overallStatusTone}
                label={
                  snapshot.overallStatus === "healthy"
                    ? isEn
                      ? "ALL SYSTEMS NOMINAL"
                      : "TOÀN BỘ HỆ THỐNG HOẠT ĐỘNG TỐT"
                    : snapshot.overallStatus === "degraded"
                      ? isEn
                        ? "SYSTEM DEGRADED"
                        : "HỆ THỐNG ĐANG SUY GIẢM"
                      : isEn
                        ? "CRITICAL ATTENTION REQUIRED"
                        : "CẦN XỬ LÝ KHẨN CẤP"
                }
                size="sm"
              />
              <span className="hidden text-xs text-[var(--text-muted)] sm:inline">
                • {snapshot.kpis.servicesHealthyCount}/{snapshot.kpis.servicesTotalCount} {isEn ? "Services Online" : "Dịch vụ sẵn sàng"}
              </span>
            </div>
          ) : null}
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Refresh interval selector */}
          <div className="flex items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-xs">
            <span className="mr-1.5 text-[var(--text-muted)]">{isEn ? "Auto:" : "Tự động:"}</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              aria-label={isEn ? "Auto-refresh interval" : "Tần suất tự động làm mới"}
              className="bg-transparent text-xs font-semibold text-[var(--text-primary)] focus:outline-none"
            >
              <option value={0}>{isEn ? "Paused" : "Tạm dừng"}</option>
              <option value={5}>5s</option>
              <option value={15}>15s</option>
              <option value={30}>30s</option>
              <option value={60}>60s</option>
            </select>
          </div>

          {/* Manual Refresh button */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void loadTelemetry(true)}
            disabled={refreshing || loading}
            aria-label={isEn ? "Refresh telemetry data" : "Làm mới dữ liệu telemetry"}
            className="flex items-center gap-1.5 text-xs font-semibold"
          >
            <Icon
              name="refresh"
              size={14}
              className={refreshing ? "animate-spin text-[var(--text-brand)]" : ""}
            />
            <span>{isEn ? "Refresh" : "Làm mới"}</span>
          </Button>

          {/* Environment Inspector Button */}
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsEnvInspectorOpen(true)}
            aria-label={isEn ? "Inspect environment configuration" : "Kiểm tra cấu hình môi trường"}
            className="flex items-center gap-1.5 text-xs font-semibold"
          >
            <Icon name="settings" size={14} />
            <span>{isEn ? "Inspect Env" : "Cấu hình môi trường"}</span>
          </Button>
        </div>
      </div>

      {/* KPI Overview Strip */}
      {snapshot ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <KpiCard
            label={isEn ? "Health Status" : "Trạng thái Dịch vụ"}
            value={`${snapshot.kpis.servicesHealthyCount} / ${snapshot.kpis.servicesTotalCount}`}
            hint={isEn ? "All core nodes online" : "Tất cả node hoạt động"}
          />
          <KpiCard
            label={isEn ? "Avg Gateway Latency" : "Độ trễ TB Gateway"}
            value={`${snapshot.kpis.avgLatencyMs.toFixed(1)} ms`}
            hint={isEn ? "p50 median response" : "Phân vị p50 trung vị"}
          />
          <KpiCard
            label={isEn ? "Error Rate (5xx/4xx)" : "Tỉ lệ Lỗi Hệ thống"}
            value={`${snapshot.kpis.errorRatePct.toFixed(3)}%`}
            hint={isEn ? "< 0.1% SLA Target" : "Đạt mục tiêu SLA < 0.1%"}
          />
          <KpiCard
            label={isEn ? "Total Requests" : "Tổng Lưu lượng Yêu cầu"}
            value={snapshot.kpis.totalRequests.toLocaleString("en-US")}
            hint={isEn ? "Trailing window" : "Cửa sổ thống kê"}
          />
          <KpiCard
            label={isEn ? "Service Uptime" : "Thời gian Sẵn sàng"}
            value={`${snapshot.kpis.overallUptimePct.toFixed(2)}%`}
            hint={isEn ? "30-day reliability" : "Độ tin cậy 30 ngày"}
          />
          <KpiCard
            label={isEn ? "Zero-PII Guard" : "Bảo vệ Zero-PII"}
            value={isEn ? "ENFORCED" : "KÍCH HOẠT"}
            hint={isEn ? "Telemetry scrubbed" : "Telemetry đã lọc PII"}
          />
        </div>
      ) : null}

      {/* Section 1: Real-time Service Health Cards (6 Services: API, ML, Database, Redis, OCR, ASR) */}
      <section aria-labelledby="services-health-heading" className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 id="services-health-heading" className="text-sm font-bold text-[var(--text-primary)] sm:text-base">
              {isEn ? "Real-Time Service Health Cards" : "Trạng thái Sức khỏe Dịch vụ Thời gian Thực"}
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              {isEn
                ? "Live status, latency, error rate, throughput, and diagnostic reachability for all 6 architecture services."
                : "Giám sát trực tiếp trạng thái, độ trễ, tỉ lệ lỗi, thông lượng và khả năng kết nối của 6 dịch vụ kiến trúc."}
            </p>
          </div>

          {/* Search and Tier Filter Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex items-center">
              <Icon
                name="search"
                size={14}
                className="pointer-events-none absolute left-2.5 text-[var(--text-muted)]"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={isEn ? "Filter services..." : "Tìm dịch vụ..."}
                aria-label={isEn ? "Filter services by name or endpoint" : "Lọc dịch vụ theo tên hoặc endpoint"}
                className="w-40 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-1.5 pl-8 pr-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-primary)] focus:outline-none sm:w-48"
              />
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5 text-xs">
              {(
                [
                  { key: "all", labelVi: "Tất cả", labelEn: "All" },
                  { key: "core", labelVi: "API", labelEn: "API" },
                  { key: "reasoning", labelVi: "ML", labelEn: "ML" },
                  { key: "data", labelVi: "Data", labelEn: "Data" },
                  { key: "multimodal", labelVi: "OCR/ASR", labelEn: "OCR/ASR" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setFilterTab(tab.key)}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                    filterTab === tab.key
                      ? "bg-[var(--brand-600)] text-[#cdd7ff] shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {isEn ? tab.labelEn : tab.labelVi}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 6 Service Health Cards Grid */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredServices.map((svc) => (
            <article
              key={svc.id}
              onClick={() => setSelectedService(svc)}
              className="group relative flex cursor-pointer flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft transition-all hover:border-[color:var(--brand-primary)]/60 hover:bg-[var(--surface-panel)]/90 hover:shadow-md"
            >
              <div>
                {/* Header: Icon, Name, Tier Badge, Status */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)] transition group-hover:scale-105">
                      <Icon name={svc.icon} size={20} />
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-[var(--text-brand)]">
                        {isEn ? svc.name : svc.nameVi}
                      </h3>
                      <p className="text-[11px] font-medium text-[var(--text-muted)]">
                        {isEn ? svc.tierLabelEn : svc.tierLabelVi} • Port {svc.port}
                      </p>
                    </div>
                  </div>

                  {getStatusChipForService(svc.status)}
                </div>

                {/* Endpoint & Version */}
                <div className="mt-3 rounded-lg border border-[color:var(--shell-border)]/50 bg-[var(--surface-muted)]/80 px-2.5 py-1.5 font-mono text-[11px] text-[var(--text-secondary)]">
                  <div className="flex items-center justify-between gap-2 overflow-hidden">
                    <span className="truncate" title={svc.endpoint}>
                      {svc.endpoint}
                    </span>
                    <span className="shrink-0 rounded bg-[var(--surface-panel)] px-1 py-0.2 text-[10px] text-[var(--text-muted)]">
                      {svc.version}
                    </span>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-[color:var(--shell-border)]/60 pt-3 text-center">
                  <div className="rounded-lg bg-[var(--surface-muted)]/40 p-2">
                    <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">
                      {isEn ? "Latency" : "Độ trễ"}
                    </p>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">
                      {svc.latencyMs < 10 ? svc.latencyMs.toFixed(1) : Math.round(svc.latencyMs)} ms
                    </p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-muted)]/40 p-2">
                    <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">
                      {isEn ? "Throughput" : "Lưu lượng"}
                    </p>
                    <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">{svc.throughput}</p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-muted)]/40 p-2">
                    <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">
                      {isEn ? "Error Rate" : "Tỉ lệ lỗi"}
                    </p>
                    <p
                      className={`mt-1 text-sm font-bold ${
                        svc.errorRatePct === 0
                          ? "text-[var(--status-success-text)]"
                          : svc.errorRatePct < 1
                            ? "text-[var(--status-warning-text)]"
                            : "text-[var(--status-danger-text)]"
                      }`}
                    >
                      {svc.errorRatePct.toFixed(2)}%
                    </p>
                  </div>
                </div>

                {/* Diagnostic excerpt */}
                <p className="mt-3 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2">
                  {svc.diagnosticMessage}
                </p>
              </div>

              {/* Footer action */}
              <div className="mt-4 flex items-center justify-between border-t border-[color:var(--shell-border)]/40 pt-3">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "Uptime:" : "Khả dụng:"} <strong className="text-[var(--text-primary)]">{svc.uptimePct}%</strong>
                </span>
                <span className="flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] group-hover:translate-x-0.5 transition-transform">
                  <span>{isEn ? "Inspect" : "Kiểm tra chi tiết"}</span>
                  <Icon name="arrow-right" size={13} />
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Section 2: Latency Percentiles (p50 / p90 / p95 / p99) and SLA Targets */}
      <section aria-labelledby="latency-percentiles-heading" className="space-y-4">
        <PanelCard
          title={isEn ? "Latency Percentiles & SLA Compliance" : "Phân vị Độ trễ & Tuân thủ Cam kết SLA"}
          description={
            isEn
              ? "Detailed latency distribution across architectural tiers (p50, p90, p95, p99, Max) compared to SLA targets."
              : "Phân vị độ trễ chi tiết qua từng tầng kiến trúc (p50, p90, p95, p99, Max) và đánh giá đối chuẩn SLA."
          }
        >
          {snapshot ? (
            <div className="space-y-6">
              {/* Latency Tiers Matrix Table */}
              <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    <tr>
                      <th scope="col" className="px-4 py-3">
                        {isEn ? "Service Tier" : "Tầng Dịch vụ"}
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        p50 (Median)
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        p90
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        p95
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        p99 (Tail)
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        {isEn ? "Max Latency" : "Độ trễ Max"}
                      </th>
                      <th scope="col" className="px-3 py-3 text-right">
                        {isEn ? "SLA Target (p95)" : "Mục tiêu SLA (p95)"}
                      </th>
                      <th scope="col" className="px-4 py-3 text-center">
                        {isEn ? "SLA Compliance" : "Đánh giá SLA"}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)] bg-[var(--surface-panel)]">
                    {snapshot.latencyTiers.map((tier) => (
                      <tr key={tier.tier} className="hover:bg-[var(--surface-muted)]/50 transition-colors">
                        <td className="px-4 py-3 font-semibold text-[var(--text-primary)]">
                          {isEn ? tier.tierLabelEn : tier.tierLabelVi}
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-medium text-[var(--text-primary)]">
                          {tier.p50Ms < 10 ? tier.p50Ms.toFixed(1) : Math.round(tier.p50Ms)} ms
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-medium text-[var(--text-primary)]">
                          {tier.p90Ms < 10 ? tier.p90Ms.toFixed(1) : Math.round(tier.p90Ms)} ms
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-bold text-[var(--text-brand)]">
                          {tier.p95Ms < 10 ? tier.p95Ms.toFixed(1) : Math.round(tier.p95Ms)} ms
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-medium text-[var(--text-primary)]">
                          {tier.p99Ms < 10 ? tier.p99Ms.toFixed(1) : Math.round(tier.p99Ms)} ms
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-[var(--text-muted)]">
                          {tier.maxMs < 10 ? tier.maxMs.toFixed(1) : Math.round(tier.maxMs)} ms
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-[var(--text-secondary)]">
                          &lt; {tier.targetSlaP95Ms} ms
                        </td>
                        <td className="px-4 py-3 text-center">{getSlaBadge(tier.slaStatus)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Per-Route Latency Table */}
              <div>
                <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {isEn ? "Core API Route Latency Distribution" : "Phân bố Độ trễ Tuyến API Trọng yếu"}
                </h4>
                <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <tr>
                        <th scope="col" className="px-4 py-2.5">
                          {isEn ? "Method & Path" : "Phương thức & Đường dẫn"}
                        </th>
                        <th scope="col" className="px-3 py-2.5 text-right">
                          {isEn ? "Requests" : "Lượt gọi"}
                        </th>
                        <th scope="col" className="px-3 py-2.5 text-right">
                          p50
                        </th>
                        <th scope="col" className="px-3 py-2.5 text-right">
                          p90
                        </th>
                        <th scope="col" className="px-3 py-2.5 text-right">
                          p99
                        </th>
                        <th scope="col" className="px-3 py-2.5 text-right">
                          {isEn ? "Error %" : "Tỉ lệ lỗi"}
                        </th>
                        <th scope="col" className="px-4 py-2.5 text-center">
                          {isEn ? "Status" : "Trạng thái"}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[color:var(--shell-border)] bg-[var(--surface-panel)] font-mono">
                      {snapshot.routeMetrics.map((r) => (
                        <tr key={r.route} className="hover:bg-[var(--surface-muted)]/50 transition-colors">
                          <td className="px-4 py-2.5 text-[var(--text-primary)]">
                            <span
                              className={`mr-2 rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                r.method === "POST"
                                  ? "bg-[var(--brand-600)] text-[#cdd7ff]"
                                  : "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                              }`}
                            >
                              {r.method}
                            </span>
                            <span className="font-sans font-medium">{r.route.replace(`${r.method} `, "")}</span>
                          </td>
                          <td className="px-3 py-2.5 text-right text-[var(--text-secondary)]">
                            {r.requestsTotal.toLocaleString("en-US")}
                          </td>
                          <td className="px-3 py-2.5 text-right text-[var(--text-primary)]">{r.p50Ms} ms</td>
                          <td className="px-3 py-2.5 text-right text-[var(--text-primary)]">{r.p90Ms} ms</td>
                          <td className="px-3 py-2.5 text-right font-bold text-[var(--text-brand)]">{r.p99Ms} ms</td>
                          <td className="px-3 py-2.5 text-right text-[var(--text-secondary)]">
                            {r.errorRatePct.toFixed(2)}%
                          </td>
                          <td className="px-4 py-2.5 text-center">{getSlaBadge(r.slaStatus)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : null}
        </PanelCard>
      </section>

      {/* Section 3: Error Rate & HTTP Status Code Analytics */}
      <section aria-labelledby="error-analytics-heading" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Status Code Distribution Panel */}
        <PanelCard
          title={isEn ? "HTTP Status Code Distribution" : "Phân bố Mã Trạng thái HTTP"}
          description={
            isEn
              ? "Aggregated response status classification (2xx, 3xx, 4xx Client, 5xx Server)."
              : "Phân loại mã phản hồi theo nhóm (2xx Thành công, 3xx Chuyển hướng, 4xx Lỗi Client, 5xx Lỗi Server)."
          }
        >
          {snapshot ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-2 text-center font-mono">
                <div className="rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/20 p-3">
                  <p className="text-[10px] font-bold text-[var(--status-ok-text)]">2xx SUCCESS</p>
                  <p className="mt-1 text-lg font-bold text-[var(--text-primary)]">
                    {snapshot.statusDistribution.status2xx.toLocaleString("en-US")}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {((snapshot.statusDistribution.status2xx / snapshot.statusDistribution.totalRequests) * 100).toFixed(
                      1
                    )}
                    %
                  </p>
                </div>
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold text-[var(--text-muted)]">3xx REDIRECT</p>
                  <p className="mt-1 text-lg font-bold text-[var(--text-primary)]">
                    {snapshot.statusDistribution.status3xx.toLocaleString("en-US")}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {((snapshot.statusDistribution.status3xx / snapshot.statusDistribution.totalRequests) * 100).toFixed(
                      1
                    )}
                    %
                  </p>
                </div>
                <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/20 p-3">
                  <p className="text-[10px] font-bold text-[var(--status-warn-text)]">4xx CLIENT</p>
                  <p className="mt-1 text-lg font-bold text-[var(--text-primary)]">
                    {snapshot.statusDistribution.status4xx.toLocaleString("en-US")}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {((snapshot.statusDistribution.status4xx / snapshot.statusDistribution.totalRequests) * 100).toFixed(
                      2
                    )}
                    %
                  </p>
                </div>
                <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/20 p-3">
                  <p className="text-[10px] font-bold text-[var(--status-danger-text)]">5xx SERVER</p>
                  <p className="mt-1 text-lg font-bold text-[var(--text-primary)]">
                    {snapshot.statusDistribution.status5xx.toLocaleString("en-US")}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {((snapshot.statusDistribution.status5xx / snapshot.statusDistribution.totalRequests) * 100).toFixed(
                      3
                    )}
                    %
                  </p>
                </div>
              </div>

              {/* Status Visual Ratio Bar */}
              <div className="space-y-1.5">
                <div className="flex h-3 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
                  <div
                    style={{
                      width: `${(snapshot.statusDistribution.status2xx / snapshot.statusDistribution.totalRequests) * 100}%`,
                    }}
                    className="bg-[var(--status-ok-text)]"
                    title="2xx Success"
                  />
                  <div
                    style={{
                      width: `${(snapshot.statusDistribution.status3xx / snapshot.statusDistribution.totalRequests) * 100}%`,
                    }}
                    className="bg-[var(--text-muted)]"
                    title="3xx Redirect"
                  />
                  <div
                    style={{
                      width: `${(snapshot.statusDistribution.status4xx / snapshot.statusDistribution.totalRequests) * 100}%`,
                    }}
                    className="bg-[var(--status-warn-text)]"
                    title="4xx Client Error"
                  />
                  <div
                    style={{
                      width: `${(snapshot.statusDistribution.status5xx / snapshot.statusDistribution.totalRequests) * 100}%`,
                    }}
                    className="bg-[var(--status-danger-text)]"
                    title="5xx Server Error"
                  />
                </div>
                <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
                  <span>99.9% Normal Traffic</span>
                  <span>0.07% Total Error Ratio</span>
                </div>
              </div>
            </div>
          ) : null}
        </PanelCard>

        {/* Error Categories Breakdown */}
        <PanelCard
          title={isEn ? "Error Categories & Root Causes" : "Phân loại Lỗi & Nguyên nhân Gốc"}
          description={
            isEn
              ? "Breakdown of non-200 responses categorized by root cause and trigger type."
              : "Chi tiết các phản hồi không thành công theo nhóm nguyên nhân và sự kiện kích hoạt."
          }
        >
          {snapshot ? <BarList rows={errorBarRows} /> : null}
        </PanelCard>
      </section>

      {/* Environment Configuration Inspector (Slide-Over Drawer / Sheet) */}
      {snapshot ? (
        <Inspector
          open={isEnvInspectorOpen}
          onClose={() => setIsEnvInspectorOpen(false)}
          title={isEn ? "Environment Configuration Inspector" : "Thanh tra Cấu hình Môi trường & Runtime"}
          subtitle={
            isEn
              ? "Zero-PII verified parameters, active feature flags, and security governance invariants."
              : "Các tham số runtime đã khử PII, cờ tính năng kích hoạt và các bất biến quản trị an toàn."
          }
          badges={
            <div className="flex items-center gap-1.5">
              <Badge tone="brand">Production</Badge>
              <Badge tone="ok">Zero-PII</Badge>
            </div>
          }
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsEnvJsonView(!isEnvJsonView)}
                className="text-xs"
              >
                <Icon name={isEnvJsonView ? "clinical-notes" : "scan"} size={14} />
                <span>{isEnvJsonView ? (isEn ? "Form View" : "Dạng bảng") : (isEn ? "JSON View" : "Dạng JSON")}</span>
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleCopyEnvConfig}
                className="text-xs font-semibold"
              >
                <Icon name={isCopied ? "check" : "download"} size={14} />
                <span>{isCopied ? (isEn ? "Copied!" : "Đã chép!") : (isEn ? "Copy Manifest" : "Chép Manifest")}</span>
              </Button>
            </div>
          }
          side="right"
          size="lg"
          density="compact"
        >
          {isEnvJsonView ? (
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 font-mono text-xs text-[var(--text-primary)]">
              <pre className="overflow-x-auto whitespace-pre-wrap">
                {getSanitizedEnvironmentJson(snapshot.envConfig)}
              </pre>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Section 1: Runtime & Deployment */}
              <InspectorSection
                title={isEn ? "1. Runtime & Deployment Architecture" : "1. Kiến trúc Runtime & Triển khai"}
                description={isEn ? "Node, Python, and build container topology" : "Môi trường thực thi và phiên bản build"}
                defaultExpanded={true}
              >
                <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs">
                  <InspectorField
                    label="NODE_ENV"
                    value={<code className="text-xs font-bold text-[var(--text-brand)]">{snapshot.envConfig.runtime.nodeEnv}</code>}
                  />
                  <InspectorField
                    label={isEn ? "App Version" : "Phiên bản ứng dụng"}
                    value={snapshot.envConfig.runtime.appVersion}
                  />
                  <InspectorField
                    label={isEn ? "Python Runtime" : "Môi trường Python"}
                    value={snapshot.envConfig.runtime.pythonVersion}
                  />
                  <InspectorField
                    label={isEn ? "Next.js Engine" : "Môi trường Web Frontend"}
                    value={snapshot.envConfig.runtime.nextRuntime}
                  />
                  <InspectorField
                    label={isEn ? "Deployment Target" : "Mục tiêu triển khai"}
                    value={snapshot.envConfig.runtime.deploymentTarget}
                  />
                  <InspectorField
                    label={isEn ? "Edge Cluster Region" : "Vùng Cluster biên"}
                    value={snapshot.envConfig.runtime.clusterRegion}
                  />
                  <InspectorField
                    label={isEn ? "Build Git Commit" : "Mã Commit Git"}
                    value={<code>{snapshot.envConfig.runtime.buildCommit}</code>}
                    copyable
                  />
                </div>
              </InspectorSection>

              {/* Section 2: Feature Flags */}
              <InspectorSection
                title={isEn ? "2. Feature Flags & AI Gating" : "2. Cờ Tính năng & Điều hướng AI"}
                description={isEn ? "Active runtime operational flags" : "Trạng thái bật/tắt các module tính năng"}
                defaultExpanded={true}
              >
                <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs">
                  <InspectorField
                    label="LLM_DEEPSEEK_ONLY"
                    value={
                      snapshot.envConfig.featureFlags.llmDeepseekOnly ? (
                        <Badge tone="ok">Enabled (Default)</Badge>
                      ) : (
                        <Badge tone="neutral">Disabled</Badge>
                      )
                    }
                    hint={isEn ? "Enforces DeepSeek-R1-Distill client only" : "Bắt buộc dùng client DeepSeek duy nhất"}
                  />
                  <InspectorField
                    label="FIDES_VERIFICATION"
                    value={
                      snapshot.envConfig.featureFlags.fidesVerificationEnabled ? (
                        <Badge tone="ok">Active Strict</Badge>
                      ) : (
                        <Badge tone="danger">Bypassed</Badge>
                      )
                    }
                    hint={isEn ? "Critical drug-dosage claims blocked on fail" : "Chặn khuyến cáo sai liều/tương tác thuốc"}
                  />
                  <InspectorField
                    label="RAG_GRAPHRAG"
                    value={
                      snapshot.envConfig.featureFlags.ragGraphRagEnabled ? (
                        <Badge tone="ok">Enabled</Badge>
                      ) : (
                        <Badge tone="neutral">Disabled</Badge>
                      )
                    }
                  />
                  <InspectorField
                    label="SCRIBE_AUDIO"
                    value={
                      snapshot.envConfig.featureFlags.scribeAudioEnabled ? (
                        <Badge tone="ok">Enabled (faster-whisper)</Badge>
                      ) : (
                        <Badge tone="neutral">Disabled</Badge>
                      )
                    }
                  />
                  <InspectorField
                    label="CAREGUARD_DDI_AUTO"
                    value={
                      snapshot.envConfig.featureFlags.careguardDdiAutoCheck ? (
                        <Badge tone="ok">Auto-Check On</Badge>
                      ) : (
                        <Badge tone="neutral">Manual Only</Badge>
                      )
                    }
                  />
                  <InspectorField
                    label="SOCIAL_PLATFORM"
                    value={
                      snapshot.envConfig.featureFlags.socialPlatformEnabled ? (
                        <Badge tone="brand">Enabled</Badge>
                      ) : (
                        <Badge tone="neutral">Disabled (Flag-Gated)</Badge>
                      )
                    }
                  />
                </div>
              </InspectorSection>

              {/* Section 3: Security & Governance Invariants */}
              <InspectorSection
                title={isEn ? "3. Security & Governance Invariants" : "3. Bất biến Bảo mật & Tuân thủ Quy chuẩn"}
                description={isEn ? "Regression-locked safety properties" : "Các quy tắc an toàn bất khả xâm phạm"}
                defaultExpanded={true}
              >
                <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs">
                  <InspectorField
                    label={isEn ? "Zero-PII Telemetry" : "Không thu thập PII"}
                    value={<Badge tone="ok">Strict Invariant</Badge>}
                    hint={isEn ? "Metrics exclude names, queries, and medication lists" : "Mọi telemetry đều không chứa dữ liệu định danh"}
                  />
                  <InspectorField
                    label={isEn ? "Authoritative RBAC" : "Kiểm soát quyền RBAC"}
                    value={<Badge tone="ok">Active</Badge>}
                    hint={isEn ? "require_roles() on all protected routes" : "Chặn 403 tác nhân không có quyền"}
                  />
                  <InspectorField
                    label={isEn ? "CSRF Protection" : "Chống giả mạo CSRF"}
                    value={<Badge tone="ok">Active (Cookie Mutations)</Badge>}
                  />
                  <InspectorField
                    label={isEn ? "Rate Limiting Policy" : "Chính sách giới hạn tốc độ"}
                    value={snapshot.envConfig.securityGovernance.rateLimitingPolicy}
                  />
                  <InspectorField
                    label={isEn ? "Consent Version Gate" : "Phiên bản đồng thuận y khoa"}
                    value={<code>{snapshot.envConfig.securityGovernance.medicalConsentVersion}</code>}
                  />
                  <InspectorField
                    label={isEn ? "Access Token TTL" : "Thời hạn Access Token"}
                    value={snapshot.envConfig.securityGovernance.jwtAccessTokenTtl}
                  />
                </div>
              </InspectorSection>

              {/* Section 4: Service Endpoints & Upstream URLs */}
              <InspectorSection
                title={isEn ? "4. Internal Service Endpoints & Upstream URLs" : "4. Đầu mối Dịch vụ & URL Nội bộ"}
                description={isEn ? "Masked network endpoints" : "Các cổng giao tiếp nội bộ"}
                defaultExpanded={false}
              >
                <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs font-mono">
                  <InspectorField
                    label="API Gateway"
                    value={snapshot.envConfig.serviceEndpoints.apiGatewayUrl}
                    copyable
                  />
                  <InspectorField
                    label="ML Service"
                    value={snapshot.envConfig.serviceEndpoints.mlServiceUrl}
                    copyable
                  />
                  <InspectorField
                    label="PostgreSQL URL"
                    value={snapshot.envConfig.serviceEndpoints.databaseUrlMasked}
                  />
                  <InspectorField
                    label="Redis URL"
                    value={snapshot.envConfig.serviceEndpoints.redisUrlMasked}
                  />
                  <InspectorField
                    label="OCR Service"
                    value={snapshot.envConfig.serviceEndpoints.ocrServiceUrl}
                    copyable
                  />
                  <InspectorField
                    label="ASR Service"
                    value={snapshot.envConfig.serviceEndpoints.asrServiceUrl}
                    copyable
                  />
                </div>
              </InspectorSection>
            </div>
          )}
        </Inspector>
      ) : null}

      {/* Service Diagnostic Inspector (When clicking a specific card) */}
      {selectedService ? (
        <Inspector
          open={Boolean(selectedService)}
          onClose={() => setSelectedService(null)}
          title={isEn ? selectedService.name : selectedService.nameVi}
          subtitle={`${isEn ? selectedService.tierLabelEn : selectedService.tierLabelVi} • Port ${selectedService.port}`}
          badges={
            <div className="flex items-center gap-1.5">
              {getStatusChipForService(selectedService.status)}
              <Badge tone="brand">{selectedService.version}</Badge>
            </div>
          }
          side="right"
          size="md"
          density="compact"
        >
          <div className="space-y-4">
            <InspectorSection
              title={isEn ? "Service Overview & Health" : "Tổng quan & Sức khỏe Dịch vụ"}
              defaultExpanded={true}
            >
              <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs">
                <InspectorField
                  label={isEn ? "Internal Endpoint" : "Đầu mối Nội bộ"}
                  value={<code className="text-xs font-mono">{selectedService.endpoint}</code>}
                  copyable
                />
                <InspectorField
                  label={isEn ? "Latency" : "Độ trễ trung bình"}
                  value={`${selectedService.latencyMs.toFixed(1)} ms`}
                />
                <InspectorField
                  label={isEn ? "Throughput Load" : "Thông lượng xử lý"}
                  value={selectedService.throughput}
                />
                <InspectorField
                  label={isEn ? "Error Rate" : "Tỉ lệ lỗi"}
                  value={`${selectedService.errorRatePct.toFixed(2)}%`}
                />
                <InspectorField
                  label={isEn ? "Reliability Uptime" : "Tỉ lệ sẵn sàng"}
                  value={`${selectedService.uptimePct}%`}
                />
                <InspectorField
                  label={isEn ? "Last Health Check" : "Kiểm tra gần nhất"}
                  value={formatLocaleDate(uiLanguage, new Date(selectedService.lastChecked))}
                />
              </div>
            </InspectorSection>

            <InspectorSection
              title={isEn ? "Runtime & Protocol Diagnostics" : "Chẩn đoán Runtime & Giao thức"}
              defaultExpanded={true}
            >
              <div className="divide-y divide-[color:var(--shell-border)]/40 text-xs">
                <InspectorField
                  label={isEn ? "Runtime Engine" : "Môi trường thực thi"}
                  value={selectedService.details.runtime}
                />
                <InspectorField
                  label={isEn ? "Wire Protocol" : "Giao thức truyền tải"}
                  value={selectedService.details.protocol}
                />
                {selectedService.details.connectionPool ? (
                  <InspectorField
                    label={isEn ? "Connection Pool" : "Bể kết nối"}
                    value={selectedService.details.connectionPool}
                  />
                ) : null}
                {selectedService.details.modelName ? (
                  <InspectorField
                    label={isEn ? "Active Model" : "Mô hình chính"}
                    value={<Badge tone="brand">{selectedService.details.modelName}</Badge>}
                  />
                ) : null}
                {selectedService.details.accuracyConfidence ? (
                  <InspectorField
                    label={isEn ? "Accuracy / Factor" : "Độ chính xác / Hệ số"}
                    value={selectedService.details.accuracyConfidence}
                  />
                ) : null}
              </div>
            </InspectorSection>

            <InspectorSection
              title={isEn ? "Diagnostic Notes" : "Ghi chú Chẩn đoán"}
              defaultExpanded={true}
            >
              <div className="rounded-lg bg-[var(--surface-muted)] p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
                {selectedService.diagnosticMessage}
              </div>
            </InspectorSection>
          </div>
        </Inspector>
      ) : null}
      </div>
    </AdminShell>
  );
}
