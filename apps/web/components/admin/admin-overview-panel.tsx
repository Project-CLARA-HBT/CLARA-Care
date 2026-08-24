"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import Icon from "@/components/ui/icon";
import { StatusChip, type StatusTone } from "@/components/ui/status-chip";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import { FLOW_FLAG_META } from "@/components/admin/admin-config-meta";
import { getAdminAuditLog, type AdminAuditRecord } from "@/lib/admin-audit";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
import {
  KnowledgeSource,
  SourceHubCatalogEntry,
  listKnowledgeSources,
  listSourceHubCatalog
} from "@/lib/research";
import {
  getApiHealth,
  getSystemDependencies,
  normalizeApiHealth,
  normalizeSystemDependencies,
  type ApiHealthSnapshot,
  type SystemDependenciesSnapshot
} from "@/lib/system";

type AdminAlert = {
  id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  href: string;
  actionLabel: string;
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("vi-VN", {
        hour12: false,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
}

function getOutcomeChip(outcome: string): { tone: StatusTone; label: string } {
  const normalized = (outcome || "").toLowerCase().trim();
  if (normalized === "success" || normalized === "ok" || normalized === "done") {
    return { tone: "success", label: "Thành công" };
  }
  if (normalized === "failure" || normalized === "error" || normalized === "failed") {
    return { tone: "danger", label: "Thất bại" };
  }
  if (normalized === "warning" || normalized === "warn") {
    return { tone: "warning", label: "Cảnh báo" };
  }
  return { tone: "info", label: outcome || "Ghi nhận" };
}

export function AdminOverviewPanel() {
  const { config, error: configError, isLoading: isConfigLoading, reload: reloadConfig } =
    useControlTowerConfig();

  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([]);
  const [sourceHubCatalog, setSourceHubCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [apiHealth, setApiHealth] = useState<ApiHealthSnapshot | null>(null);
  const [dependencies, setDependencies] = useState<SystemDependenciesSnapshot | null>(null);
  const [auditLogs, setAuditLogs] = useState<AdminAuditRecord[]>([]);

  const [isLoadingExtra, setIsLoadingExtra] = useState(true);
  const [extraError, setExtraError] = useState("");
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadSupplementalData = useCallback(async () => {
    setIsLoadingExtra(true);
    setExtraError("");
    try {
      const [knowledge, catalog, healthRaw, depsRaw, auditResp] = await Promise.allSettled([
        listKnowledgeSources(),
        listSourceHubCatalog(),
        getApiHealth(),
        getSystemDependencies(),
        getAdminAuditLog(6)
      ]);

      if (knowledge.status === "fulfilled") {
        setKnowledgeSources(knowledge.value);
      }
      if (catalog.status === "fulfilled") {
        setSourceHubCatalog(catalog.value);
      }
      if (healthRaw.status === "fulfilled") {
        setApiHealth(normalizeApiHealth(healthRaw.value));
      }
      if (depsRaw.status === "fulfilled") {
        setDependencies(normalizeSystemDependencies(depsRaw.value));
      }
      if (auditResp.status === "fulfilled") {
        setAuditLogs(auditResp.value.records || []);
      }
      setLastSyncTime(new Date());
    } catch (cause) {
      setExtraError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể tải dữ liệu bổ trợ cho Control Tower."
        )
      );
    } finally {
      setIsLoadingExtra(false);
    }
  }, []);

  useEffect(() => {
    void loadSupplementalData();
  }, [loadSupplementalData]);

  useEffect(() => {
    trackAdminSurfaceViewed({ view: "overview" });
  }, []);

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([reloadConfig(), loadSupplementalData()]);
      setLastSyncTime(new Date());
    } finally {
      setIsRefreshing(false);
    }
  };

  // Real metrics calculated from live props (Zero fabricated KPIs)
  const totalSources = config?.rag_sources.length ?? 0;
  const enabledSources = config?.rag_sources.filter((source) => source.enabled).length ?? 0;
  const totalKnowledgeSources = knowledgeSources.length;
  const activeKnowledgeSources = knowledgeSources.filter((source) => source.is_active).length;
  const totalSourceHubCatalog = sourceHubCatalog.length;
  const liveSourceHubCatalog = sourceHubCatalog.filter((source) => source.supports_live_sync).length;

  const flowEnabledCount = config
    ? Object.keys(FLOW_FLAG_META).filter((key) => config.rag_flow[key as keyof typeof FLOW_FLAG_META]).length
    : 0;
  const flowTotal = Object.keys(FLOW_FLAG_META).length;

  const isFidesShieldActive = Boolean(
    config?.rag_flow.rule_verification_enabled ?? config?.rag_flow.verification_enabled ?? true
  );

  // Critical Alerts derivation from real config and service health
  const alerts = useMemo<AdminAlert[]>(() => {
    const list: AdminAlert[] = [];

    // 1. API Health / ML Service check
    if (apiHealth && apiHealth.status !== "ok" && apiHealth.status !== "healthy" && apiHealth.status !== "unknown") {
      list.push({
        id: "alert-api-degraded",
        severity: "critical",
        title: "Dịch vụ API Gateway suy giảm",
        message: `Trạng thái API: "${apiHealth.status}" - ${apiHealth.message || "Kiểm tra kết nối hệ thống"}.`,
        href: "/admin/observability",
        actionLabel: "Kiểm tra Giám sát"
      });
    }

    if (dependencies && dependencies.mlReachable === false) {
      list.push({
        id: "alert-ml-unreachable",
        severity: "critical",
        title: "Dịch vụ ML & Guardrails không phản hồi",
        message: "Máy chủ ML (clara_ml) không thể kết nối. Các tác vụ RAG, FIDES và Router đang chạy ở chế độ fallback.",
        href: "/admin/observability",
        actionLabel: "Mở Observability"
      });
    }

    // 2. FIDES / Rule Verification disabled
    if (config && !isFidesShieldActive) {
      list.push({
        id: "alert-fides-disabled",
        severity: "critical",
        title: "Chốt chặn An toàn FIDES bị tắt",
        message: "Rule verification / FIDES guardrail đang ở trạng thái tắt. Các kiểm chứng an toàn lâm sàng bị bỏ qua!",
        href: "/admin/answer-flow",
        actionLabel: "Bật lại FIDES"
      });
    }

    // 3. RAG Source Availability
    if (totalSources > 0 && enabledSources === 0) {
      list.push({
        id: "alert-sources-zero",
        severity: "critical",
        title: "Toàn bộ nguồn RAG đang bị tắt",
        message: `0/${totalSources} nguồn truy xuất RAG được bật. Pipeline trả lời y khoa sẽ không có tài liệu dẫn chứng.`,
        href: "/admin/knowledge-sources",
        actionLabel: "Bật Nguồn tri thức"
      });
    } else if (totalSources > 0 && enabledSources < totalSources / 2) {
      list.push({
        id: "alert-sources-low",
        severity: "warning",
        title: "Độ phủ nguồn tri thức RAG thấp",
        message: `Chỉ có ${enabledSources}/${totalSources} nguồn được kích hoạt. Hãy kiểm tra các connector y văn.`,
        href: "/admin/knowledge-sources",
        actionLabel: "Cấu hình Nguồn"
      });
    }

    // 4. Low context threshold anomaly
    if (config) {
      const threshold = config.rag_flow.low_context_threshold;
      if (threshold < 0.2 || threshold > 0.8) {
        list.push({
          id: "alert-low-context",
          severity: "warning",
          title: "Ngưỡng low_context_threshold bất thường",
          message: `Ngưỡng router hiện tại là ${threshold} (vùng khuyến nghị: 0.2 - 0.8). Có thể gây lệch luồng định tuyến.`,
          href: "/admin/answer-flow",
          actionLabel: "Điều chỉnh Ngưỡng"
        });
      }
    }

    return list;
  }, [apiHealth, dependencies, config, isFidesShieldActive, totalSources, enabledSources]);

  const isLoadingAny = isConfigLoading || isLoadingExtra;

  return (
    <div className="space-y-6">
      {/* 1. System Overview Headline (Editorial Header) */}
      <section className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 shadow-sm">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[var(--brand-600)]/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[var(--brand-primary)]/5 blur-3xl" />

        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[var(--text-brand)]">
                <Icon name="progress" size={14} />
                TRUNG TÂM CHỈ HUY HỆ THỐNG
              </span>
              <StatusChip
                tone={isFidesShieldActive ? "success" : "danger"}
                label={isFidesShieldActive ? "FIDES Safety Shield: Hoạt động" : "FIDES Verification: Tắt"}
                icon={<Icon name={isFidesShieldActive ? "check" : "warning"} size={13} />}
                size="sm"
              />
              <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                <Icon name="progress" size={13} className="text-[var(--text-brand)]" />
                4 Phân hệ Trọng yếu
              </span>
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Tổng quan Điều phối & An toàn Hệ thống
            </h1>

            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
              Giám sát thời gian thực các phân hệ tri thức RAG, luồng điều phối router, chốt chặn an toàn FIDES và
              nhật ký kiểm toán vận hành hệ thống CLARA.
            </p>

            <div className="flex flex-wrap items-center gap-2 pt-2">
              <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-primary)] sm:w-auto sm:rounded-full sm:py-0">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    isLoadingAny
                      ? "bg-[var(--text-muted)] animate-pulse"
                      : alerts.some((a) => a.severity === "critical")
                        ? "bg-[var(--status-danger-text)] animate-ping"
                        : alerts.length > 0
                          ? "bg-[var(--status-warn-text)]"
                          : "bg-[var(--success-500)]"
                  }`}
                />
                Trạng thái:{" "}
                {isLoadingAny
                  ? "Đang tải dữ liệu..."
                  : alerts.some((a) => a.severity === "critical")
                    ? "Cần can thiệp khẩn"
                    : alerts.length > 0
                      ? "Có mục cần rà soát"
                      : "Hoạt động bình thường"}
              </span>
              <span className="flex min-h-9 w-full max-w-full items-center gap-2 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-secondary)] sm:w-auto sm:rounded-full sm:py-0">
                <Icon name="progress" size={14} />
                Đồng bộ trực tiếp: {formatTimestamp(lastSyncTime.toISOString())}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 lg:flex-col lg:items-end">
            <button
              type="button"
              onClick={() => void handleRefreshAll()}
              disabled={isRefreshing}
              className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-[var(--brand-600)] px-6 text-sm font-bold text-[var(--on-secondary-container)] shadow-sm transition hover:bg-[var(--brand-700)] disabled:opacity-60"
            >
              <Icon name="refresh" size={18} className={isRefreshing ? "animate-spin" : ""} />
              {isRefreshing ? "Đang đồng bộ..." : "Đồng bộ tức thì"}
            </button>
            <Link
              href="/admin/observability"
              className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
            >
              <Icon name="progress" size={14} />
              Chi tiết Observability →
            </Link>
          </div>
        </div>
      </section>

      {/* Global Error Banner if any */}
      {configError || extraError ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[color:var(--danger-border)] bg-[var(--surface-danger-soft)] px-4 py-3 text-sm text-[var(--text-danger)]"
        >
          <span>{configError || extraError}</span>
          <button
            type="button"
            onClick={() => void handleRefreshAll()}
            className="rounded-lg border border-[color:var(--danger-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-medium text-[var(--text-danger)] hover:bg-[var(--surface-muted)]"
          >
            Thử lại
          </button>
        </div>
      ) : null}

      {/* 2. Attention / Critical Alerts Block */}
      <section aria-labelledby="overview-alerts-title" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="overview-alerts-title" className="flex items-center gap-2 text-lg font-bold text-[var(--text-primary)]">
            <Icon name="warning" className="text-[var(--brand-600)]" />
            Cảnh báo & Mục cần lưu ý (Attention / Critical Alerts)
          </h2>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            Nguồn: useControlTowerConfig & API Health
          </span>
        </div>

        {alerts.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {alerts.map((alert) => (
              <article
                key={alert.id}
                className={`flex flex-col justify-between rounded-2xl border p-5 transition-all shadow-sm ${
                  alert.severity === "critical"
                    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                    : "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider">
                      <Icon name="warning" size={16} />
                      {alert.severity === "critical" ? "Cảnh báo khẩn cấp" : "Lưu ý cấu hình"}
                    </span>
                    <span className="rounded-md border border-current px-2 py-0.5 text-[10px] font-mono font-bold">
                      {alert.id}
                    </span>
                  </div>
                  <h3 className="mt-2 text-base font-bold text-[var(--text-primary)]">{alert.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed opacity-90">{alert.message}</p>
                </div>

                <div className="mt-4 pt-2">
                  <Link
                    href={alert.href}
                    className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-current bg-[var(--surface-panel)] px-4 text-xs font-bold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
                  >
                    <span>{alert.actionLabel}</span>
                    <Icon name="arrow-right" size={13} />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 text-sm text-[var(--text-secondary)] shadow-sm">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--success-500)]">
                <Icon name="check" size={20} />
              </span>
              <div>
                <p className="font-bold text-[var(--text-primary)]">Mọi phân hệ hoạt động bình thường (All Systems Operational)</p>
                <p className="text-xs text-[var(--text-muted)]">
                  Chốt chặn an toàn FIDES, độ phủ nguồn RAG ({enabledSources}/{totalSources}) và các ngưỡng định tuyến đều ở trạng thái ổn định.
                </p>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 3. Systems Status Stream (4 Phân hệ Trọng yếu) */}
      <section aria-labelledby="overview-systems-stream" className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 id="overview-systems-stream" className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]">
              <Icon name="clinical-notes" className="text-[var(--text-brand)]" />
              4 Phân hệ Trọng yếu (Systems Status Stream)
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Điều phối trực tiếp các phân hệ cốt lõi của nền tảng y tế CLARA
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {/* Phân hệ 1: Knowledge Core */}
          <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg">
            <div>
              <div className="flex items-center justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                  <Icon name="clinical-notes" size={22} />
                </span>
                <StatusChip
                  tone={enabledSources > 0 ? "success" : "warning"}
                  label={enabledSources > 0 ? "Hoạt động" : "Cần cấu hình"}
                  size="sm"
                />
              </div>

              <h3 className="mt-4 text-base font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                Knowledge Core
              </h3>
              <p className="text-xs font-semibold text-[var(--text-brand)]">Nguồn Tri thức & Registry</p>

              <div className="mt-4 space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">RAG Sources:</span>
                  <span className="font-bold text-[var(--text-primary)]">{enabledSources}/{totalSources} bật</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Knowledge Hubs:</span>
                  <span className="font-bold text-[var(--text-primary)]">{activeKnowledgeSources}/{totalKnowledgeSources} active</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Federated Sync:</span>
                  <span className="font-bold text-[var(--text-primary)]">{liveSourceHubCatalog}/{totalSourceHubCatalog} live</span>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-2 border-t border-[color:var(--shell-border)]">
              <Link
                href="/admin/knowledge-sources"
                className="flex items-center justify-between text-xs font-bold text-[var(--text-brand)] group-hover:underline"
              >
                <span>Quản lý nguồn tri thức</span>
                <Icon name="arrow-right" size={13} className="transition group-hover:translate-x-1" />
              </Link>
            </div>
          </div>

          {/* Phân hệ 2: Answer Flow */}
          <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg">
            <div>
              <div className="flex items-center justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                  <Icon name="progress" size={22} />
                </span>
                <StatusChip
                  tone="info"
                  label={flowEnabledCount > 0 ? "Đang điều phối" : "Chưa cấu hình"}
                  size="sm"
                />
              </div>

              <h3 className="mt-4 text-base font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                Answer Flow
              </h3>
              <p className="text-xs font-semibold text-[var(--text-brand)]">Điều phối Router & Multi-tier</p>

              <div className="mt-4 space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Flow Flags:</span>
                  <span className="font-bold text-[var(--text-primary)]">{flowEnabledCount}/{flowTotal} flags</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Ngưỡng Router:</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{config?.rag_flow.low_context_threshold ?? 0.2}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">FIDES Check:</span>
                  <span className="font-bold text-[var(--status-ok-text)]">{isFidesShieldActive ? "Đang bảo vệ" : "Tắt"}</span>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-2 border-t border-[color:var(--shell-border)]">
              <Link
                href="/admin/answer-flow"
                className="flex items-center justify-between text-xs font-bold text-[var(--text-brand)] group-hover:underline"
              >
                <span>Cấu hình luồng trả lời</span>
                <Icon name="arrow-right" size={13} className="transition group-hover:translate-x-1" />
              </Link>
            </div>
          </div>

          {/* Phân hệ 3: RAG Evaluation */}
          <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg">
            <div>
              <div className="flex items-center justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                  <Icon name="scan" size={22} />
                </span>
                <StatusChip
                  tone="success"
                  label="Sẵn sàng chạy"
                  size="sm"
                />
              </div>

              <h3 className="mt-4 text-base font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                RAG Evaluation
              </h3>
              <p className="text-xs font-semibold text-[var(--text-brand)]">Đánh giá Golden VN Q&A</p>

              <div className="mt-4 space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Bộ chỉ số:</span>
                  <span className="font-bold text-[var(--text-primary)]">Recall, nDCG, Faith</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Standard K:</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">k={config?.rag_flow.recall_at_k ?? 10}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Benchmark:</span>
                  <span className="font-bold text-[var(--text-primary)]">Golden Medical Q&A</span>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-2 border-t border-[color:var(--shell-border)]">
              <Link
                href="/admin/rag-eval"
                className="flex items-center justify-between text-xs font-bold text-[var(--text-brand)] group-hover:underline"
              >
                <span>Chạy đánh giá RAG</span>
                <Icon name="arrow-right" size={13} className="transition group-hover:translate-x-1" />
              </Link>
            </div>
          </div>

          {/* Phân hệ 4: Data Ingestion */}
          <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 transition-all duration-200 hover:-translate-y-1 hover:border-[color:var(--text-brand)] hover:shadow-lg">
            <div>
              <div className="flex items-center justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)] transition group-hover:scale-105 group-hover:bg-[var(--surface-brand-soft)]">
                  <Icon name="upload" size={22} />
                </span>
                <StatusChip
                  tone="success"
                  label="Offline Plane"
                  size="sm"
                />
              </div>

              <h3 className="mt-4 text-base font-bold text-[var(--text-primary)] transition group-hover:text-[var(--text-brand)]">
                Data Ingestion
              </h3>
              <p className="text-xs font-semibold text-[var(--text-brand)]">Nạp Dữ liệu & Ingestion Pipeline</p>

              <div className="mt-4 space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Ingestion Plane:</span>
                  <span className="font-bold text-[var(--text-primary)]">Offline Watermark Sync</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Trust Tiers:</span>
                  <span className="font-bold text-[var(--text-primary)]">Tier 1 - 4 Standards</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">Sync Engines:</span>
                  <span className="font-bold text-[var(--text-primary)]">Crawler & API Ingest</span>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-2 border-t border-[color:var(--shell-border)]">
              <Link
                href="/admin/rag-ingestion"
                className="flex items-center justify-between text-xs font-bold text-[var(--text-brand)] group-hover:underline"
              >
                <span>Mở trung tâm nạp dữ liệu</span>
                <Icon name="arrow-right" size={13} className="transition group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Recent Operational Activity (Real audit trail stream) */}
      <section aria-labelledby="overview-audit-title" className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="overview-audit-title" className="flex items-center gap-2 text-xl font-bold text-[var(--text-primary)]">
              <Icon name="clinical-notes" className="text-[var(--brand-600)]" />
              Hoạt động Vận hành Gần đây (Recent Operational Activity)
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Nhật ký kiểm toán thời gian thực từ Admin Audit Trail (getAdminAuditLog). Tuyệt đối không chứa thông tin định danh (PII).
            </p>
          </div>
          <Link
            href="/admin/audit-log"
            className="text-xs font-bold text-[var(--text-brand)] hover:underline"
          >
            Xem toàn bộ nhật ký kiểm toán →
          </Link>
        </div>

        {isLoadingExtra ? (
          <div className="h-40 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
        ) : auditLogs.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="px-4 py-3">Thời điểm</th>
                  <th className="px-4 py-3">Tác nhân</th>
                  <th className="px-4 py-3">Hành động</th>
                  <th className="px-4 py-3">Đối tượng</th>
                  <th className="px-4 py-3">Kết quả</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.slice(0, 6).map((record) => {
                  const outcomeChip = getOutcomeChip(record.outcome);
                  return (
                    <tr
                      key={record.id}
                      className="border-b border-[color:var(--shell-border)] last:border-0 hover:bg-[var(--surface-muted)]/50 transition"
                    >
                      <td className="px-4 py-3 text-xs text-[var(--text-secondary)] whitespace-nowrap">
                        {formatTimestamp(record.created_at)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs font-bold text-[var(--text-primary)]">
                        {record.actor_ref || "--"}
                      </td>
                      <td className="px-4 py-3 font-semibold text-[var(--text-primary)]">
                        {record.action}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                        {record.target || "--"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusChip
                          tone={outcomeChip.tone}
                          label={outcomeChip.label}
                          size="sm"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 text-center text-sm text-[var(--text-secondary)]">
            Chưa có bản ghi hoạt động quản trị nào được ghi nhận.
          </div>
        )}
      </section>
    </div>
  );
}

export default AdminOverviewPanel;
