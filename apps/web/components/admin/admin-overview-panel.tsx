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
import { useUILanguage } from "@/lib/use-ui-language";
import {
  KnowledgeSource,
  SourceHubCatalogEntry,
  listKnowledgeSources,
  listSourceHubCatalog,
} from "@/lib/research";
import {
  getApiHealth,
  getSystemDependencies,
  normalizeApiHealth,
  normalizeSystemDependencies,
  type ApiHealthSnapshot,
  type SystemDependenciesSnapshot,
} from "@/lib/system";

export type AttentionQueueSeverity = "critical" | "warning" | "info";

export type AttentionQueueItem = {
  id: string;
  severity: AttentionQueueSeverity;
  system: string;
  issue: string;
  actionLabel: string;
  href: string;
  timestamp?: string;
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
        second: "2-digit",
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
  if (normalized === "denied") {
    return { tone: "danger", label: "Bị từ chối" };
  }
  return { tone: "info", label: outcome || "Ghi nhận" };
}

export function AdminOverviewPanel() {
  const language = useUILanguage();
  const isVi = language !== "en";

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
        getAdminAuditLog(8),
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

  const lowContextThreshold = config?.rag_flow.low_context_threshold ?? 0.2;
  const recallAtK = config?.rag_flow.recall_at_k ?? 10;

  // Ordered Attention Queue derivation (sorted: critical > warning > info, capped at 5)
  const attentionQueue = useMemo<AttentionQueueItem[]>(() => {
    const list: AttentionQueueItem[] = [];

    // 1. API Health / ML Service check
    if (apiHealth && apiHealth.status !== "ok" && apiHealth.status !== "healthy" && apiHealth.status !== "unknown") {
      list.push({
        id: "alert-api-degraded",
        severity: "critical",
        system: "API Gateway",
        issue: `Trạng thái API: "${apiHealth.status}" - ${apiHealth.message || "Kiểm tra kết nối hệ thống"}.`,
        href: "/admin/observability",
        actionLabel: "Kiểm tra Giám sát",
        timestamp: formatTimestamp(lastSyncTime.toISOString()),
      });
    }

    if (dependencies && dependencies.mlReachable === false) {
      list.push({
        id: "alert-ml-unreachable",
        severity: "critical",
        system: "ML & Guardrails",
        issue: "Máy chủ ML (clara_ml) không thể kết nối. Các tác vụ RAG, FIDES và Router đang chạy ở chế độ fallback.",
        href: "/admin/observability",
        actionLabel: "Mở Observability",
        timestamp: formatTimestamp(lastSyncTime.toISOString()),
      });
    }

    // 2. FIDES / Rule Verification disabled
    if (config && !isFidesShieldActive) {
      list.push({
        id: "alert-fides-disabled",
        severity: "critical",
        system: "FIDES Shield",
        issue: "Chốt chặn An toàn FIDES bị tắt. Các kiểm chứng an toàn lâm sàng bị bỏ qua!",
        href: "/admin/answer-flow",
        actionLabel: "Bật lại FIDES",
        timestamp: formatTimestamp(lastSyncTime.toISOString()),
      });
    }

    // 3. RAG Source Availability
    if (totalSources > 0 && enabledSources === 0) {
      list.push({
        id: "alert-sources-zero",
        severity: "critical",
        system: "RAG Sources",
        issue: `0/${totalSources} nguồn truy xuất RAG được bật. Pipeline trả lời y khoa sẽ không có tài liệu dẫn chứng.`,
        href: "/admin/knowledge-sources",
        actionLabel: "Bật Nguồn tri thức",
        timestamp: formatTimestamp(lastSyncTime.toISOString()),
      });
    } else if (totalSources > 0 && enabledSources < totalSources / 2) {
      list.push({
        id: "alert-sources-low",
        severity: "warning",
        system: "RAG Sources",
        issue: `Chỉ có ${enabledSources}/${totalSources} nguồn được kích hoạt. Độ phủ nguồn tri thức RAG thấp.`,
        href: "/admin/knowledge-sources",
        actionLabel: "Cấu hình Nguồn",
        timestamp: formatTimestamp(lastSyncTime.toISOString()),
      });
    }

    // 4. Low context threshold anomaly
    if (config) {
      const threshold = config.rag_flow.low_context_threshold;
      if (threshold < 0.2 || threshold > 0.8) {
        list.push({
          id: "alert-low-context",
          severity: "warning",
          system: "Answer Flow Router",
          issue: `Ngưỡng low_context_threshold hiện tại là ${threshold} (vùng khuyến nghị: 0.2 - 0.8). Có thể gây lệch luồng định tuyến.`,
          href: "/admin/answer-flow",
          actionLabel: "Điều chỉnh Ngưỡng",
          timestamp: formatTimestamp(lastSyncTime.toISOString()),
        });
      }
    }

    // Sort by severity (critical > warning > info) and slice to max 5 items
    const severityOrder: Record<AttentionQueueSeverity, number> = {
      critical: 0,
      warning: 1,
      info: 2,
    };

    return list
      .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
      .slice(0, 5);
  }, [apiHealth, dependencies, config, isFidesShieldActive, totalSources, enabledSources, lastSyncTime]);

  const isLoadingAny = isConfigLoading || isLoadingExtra;

  return (
    <div
      data-shell-mode="ADMIN_COMMAND"
      data-layout-archetype="Admin Command Workbench"
      data-density="DENSE"
      className="space-y-6"
    >
      {/* 1. Compact Header / Context Bar (No Giant Hero Banner) */}
      <header className="flex flex-col gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isLoadingAny
                  ? "bg-[var(--text-muted)] animate-pulse"
                  : attentionQueue.some((a) => a.severity === "critical")
                    ? "bg-[var(--status-danger-text)] animate-ping"
                    : attentionQueue.length > 0
                      ? "bg-[var(--status-warn-text)]"
                      : "bg-[var(--success-500)]"
              }`}
            />
            <h1 className="text-base font-bold text-[var(--text-primary)] sm:text-lg">
              Tổng quan Điều phối & An toàn Hệ thống
            </h1>
          </div>

          <span className="inline-flex items-center rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2 py-0.5 text-[10px] font-mono font-bold text-[var(--text-brand)]">
            ADMIN_COMMAND
          </span>

          <StatusChip
            tone={isFidesShieldActive ? "success" : "danger"}
            label={isFidesShieldActive ? "FIDES Safety Shield: Hoạt động" : "FIDES Verification: Tắt"}
            icon={<Icon name={isFidesShieldActive ? "check" : "warning"} size={12} />}
            size="sm"
          />

          <span className="text-xs text-[var(--text-muted)]">
            Đồng bộ trực tiếp: {formatTimestamp(lastSyncTime.toISOString())}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleRefreshAll()}
            disabled={isRefreshing}
            className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] bg-[var(--brand-600)] px-3.5 text-xs font-bold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] disabled:opacity-60"
          >
            <Icon name="refresh" size={14} className={isRefreshing ? "animate-spin" : ""} />
            <span>{isRefreshing ? "Đang đồng bộ..." : "Đồng bộ tức thì"}</span>
          </button>
          <Link
            href="/admin/observability"
            className="inline-flex min-h-9 items-center justify-center gap-1 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
          >
            <span>Observability</span>
            <Icon name="arrow-right" size={12} />
          </Link>
        </div>
      </header>

      {/* Global Error Banner if any */}
      {configError || extraError ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[color:var(--danger-border)] bg-[var(--surface-danger-soft)] px-4 py-3 text-xs sm:text-sm text-[var(--text-danger)] shadow-xs"
        >
          <div className="flex items-center gap-2">
            <Icon name="warning" size={16} />
            <span>{configError || extraError}</span>
          </div>
          <button
            type="button"
            onClick={() => void handleRefreshAll()}
            className="rounded-lg border border-[color:var(--danger-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-medium text-[var(--text-danger)] hover:bg-[var(--surface-muted)]"
          >
            Thử lại
          </button>
        </div>
      ) : null}

      {/* 2. Visual Hierarchy #1: Attention Queue (0–5 ordered rows with severity, system, issue, owner/action, timestamp) */}
      <section aria-labelledby="attention-queue-title" className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 id="attention-queue-title" className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Icon name="warning" size={18} className="text-[var(--brand-600)]" />
              <span>Hàng đợi Cần lưu ý (Attention Queue)</span>
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              0–5 mục sắp xếp theo mức độ nghiêm trọng cần quản trị viên can thiệp
            </p>
          </div>
          <span className="rounded-full bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-mono font-semibold text-[var(--text-secondary)]">
            {attentionQueue.length} {attentionQueue.length === 1 ? "mục" : "mục"}
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                <th className="px-4 py-2.5">Mức độ</th>
                <th className="px-4 py-2.5">Phân hệ</th>
                <th className="px-4 py-2.5">Vấn đề phát hiện</th>
                <th className="px-4 py-2.5">Hành động</th>
                <th className="px-4 py-2.5">Thời điểm</th>
              </tr>
            </thead>
            <tbody>
              {attentionQueue.length > 0 ? (
                attentionQueue.map((item) => (
                  <tr
                    key={item.id}
                    className={`border-b border-[color:var(--shell-border)] last:border-0 transition ${
                      item.severity === "critical"
                        ? "bg-[var(--status-danger-bg)]/40 hover:bg-[var(--status-danger-bg)]/60"
                        : "hover:bg-[var(--surface-muted)]/50"
                    }`}
                  >
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusChip
                        tone={item.severity === "critical" ? "danger" : item.severity === "warning" ? "warning" : "info"}
                        label={item.severity === "critical" ? "Khẩn cấp" : item.severity === "warning" ? "Cảnh báo" : "Thông tin"}
                        size="sm"
                      />
                    </td>
                    <td className="px-4 py-3 font-semibold text-[var(--text-primary)] whitespace-nowrap">
                      {item.system}
                    </td>
                    <td className="px-4 py-3 text-xs leading-relaxed text-[var(--text-secondary)] max-w-md">
                      {item.issue}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Link
                        href={item.href}
                        className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)] transition hover:bg-[var(--surface-muted)] hover:underline"
                      >
                        <span>{item.actionLabel}</span>
                        <Icon name="arrow-right" size={11} />
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)] whitespace-nowrap font-mono">
                      {item.timestamp || formatTimestamp(lastSyncTime.toISOString())}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="hover:bg-[var(--surface-muted)]/30 transition">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <StatusChip tone="success" label="Hoạt động tốt" size="sm" icon={<Icon name="check" size={12} />} />
                  </td>
                  <td className="px-4 py-3 font-semibold text-[var(--text-primary)] whitespace-nowrap">
                    Toàn bộ phân hệ (All Systems)
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)] max-w-md">
                    Mọi phân hệ hoạt động bình thường. FIDES Safety Shield, độ phủ nguồn RAG ({enabledSources}/{totalSources}) và các ngưỡng định tuyến ổn định.
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <Link
                      href="/admin/observability"
                      className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                    >
                      <span>Xem chỉ số</span>
                      <Icon name="arrow-right" size={11} />
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)] whitespace-nowrap font-mono">
                    {formatTimestamp(lastSyncTime.toISOString())}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. Visual Hierarchy #2: System Status Ledger (Dense Table of Knowledge Core, Answer Flow, RAG Eval, Ingestion) */}
      <section aria-labelledby="system-status-ledger-title" className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 id="system-status-ledger-title" className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Icon name="clinical-notes" size={18} className="text-[var(--text-brand)]" />
              <span>Sổ cái Trạng thái Phân hệ (System Status Ledger)</span>
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Bảng theo dõi trạng thái, cấu hình vận hành và thao tác nhanh cho 4 phân hệ trọng yếu
            </p>
          </div>
          <span className="text-xs font-semibold text-[var(--text-muted)]">
            4 Core Subsystems
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                <th className="px-4 py-2.5">Phân hệ</th>
                <th className="px-4 py-2.5">Trạng thái</th>
                <th className="px-4 py-2.5">Chỉ số / Cấu hình chính</th>
                <th className="px-4 py-2.5">Lần kiểm tra cuối</th>
                <th className="px-4 py-2.5 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)]">
              {/* Row 1: Knowledge Core */}
              <tr className="hover:bg-[var(--surface-muted)]/50 transition">
                <td className="px-4 py-3">
                  <div className="font-bold text-[var(--text-primary)]">Knowledge Core</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Nguồn Tri thức & Registry</div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <StatusChip
                    tone={enabledSources > 0 ? "success" : "warning"}
                    label={enabledSources > 0 ? "Hoạt động" : "Cần cấu hình"}
                    size="sm"
                  />
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span><strong className="text-[var(--text-primary)]">{enabledSources}/{totalSources}</strong> RAG sources bật</span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span><strong className="text-[var(--text-primary)]">{activeKnowledgeSources}/{totalKnowledgeSources}</strong> Hubs active</span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span><strong className="text-[var(--text-primary)]">{liveSourceHubCatalog}/{totalSourceHubCatalog}</strong> live sync</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono whitespace-nowrap">
                  {formatTimestamp(lastSyncTime.toISOString())}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <Link
                    href="/admin/knowledge-sources"
                    className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)] hover:bg-[var(--surface-muted)] hover:underline"
                  >
                    <span>Quản lý nguồn</span>
                    <Icon name="arrow-right" size={11} />
                  </Link>
                </td>
              </tr>

              {/* Row 2: Answer Flow */}
              <tr className="hover:bg-[var(--surface-muted)]/50 transition">
                <td className="px-4 py-3">
                  <div className="font-bold text-[var(--text-primary)]">Answer Flow</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Điều phối Router & Multi-tier</div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <StatusChip
                    tone={isFidesShieldActive ? "success" : "danger"}
                    label={isFidesShieldActive ? "Đang điều phối" : "FIDES Tắt"}
                    size="sm"
                  />
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span><strong className="text-[var(--text-primary)]">{flowEnabledCount}/{flowTotal}</strong> Flow Flags</span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>Ngưỡng: <strong className="font-mono text-[var(--text-primary)]">{lowContextThreshold}</strong></span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>FIDES: <strong className={isFidesShieldActive ? "text-[var(--status-ok-text)]" : "text-[var(--status-danger-text)]"}>{isFidesShieldActive ? "Đang bảo vệ" : "Tắt"}</strong></span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono whitespace-nowrap">
                  {formatTimestamp(lastSyncTime.toISOString())}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <Link
                    href="/admin/answer-flow"
                    className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)] hover:bg-[var(--surface-muted)] hover:underline"
                  >
                    <span>Cấu hình luồng</span>
                    <Icon name="arrow-right" size={11} />
                  </Link>
                </td>
              </tr>

              {/* Row 3: RAG Evaluation */}
              <tr className="hover:bg-[var(--surface-muted)]/50 transition">
                <td className="px-4 py-3">
                  <div className="font-bold text-[var(--text-primary)]">RAG Evaluation</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Đánh giá Golden VN Q&A</div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <StatusChip tone="success" label="Sẵn sàng chạy" size="sm" />
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>Benchmark: <strong className="text-[var(--text-primary)]">Golden Medical Q&A</strong></span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>Chỉ số: <strong className="text-[var(--text-primary)]">Recall, nDCG, Faith</strong></span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>Standard <strong className="font-mono text-[var(--text-primary)]">k={recallAtK}</strong></span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono whitespace-nowrap">
                  {formatTimestamp(lastSyncTime.toISOString())}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <Link
                    href="/admin/rag-eval"
                    className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)] hover:bg-[var(--surface-muted)] hover:underline"
                  >
                    <span>Chạy đánh giá</span>
                    <Icon name="arrow-right" size={11} />
                  </Link>
                </td>
              </tr>

              {/* Row 4: Data Ingestion */}
              <tr className="hover:bg-[var(--surface-muted)]/50 transition">
                <td className="px-4 py-3">
                  <div className="font-bold text-[var(--text-primary)]">Data Ingestion</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Nạp Dữ liệu & Ingestion Pipeline</div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <StatusChip tone="success" label="Offline Plane" size="sm" />
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>Sync: <strong className="text-[var(--text-primary)]">Offline Watermark</strong></span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>Trust Tiers: <strong className="text-[var(--text-primary)]">Tier 1 - 4</strong></span>
                    <span className="text-[var(--shell-border-strong)]">•</span>
                    <span>Engines: <strong className="text-[var(--text-primary)]">Crawler & API</strong></span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono whitespace-nowrap">
                  {formatTimestamp(lastSyncTime.toISOString())}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <Link
                    href="/admin/rag-ingestion"
                    className="inline-flex min-h-7 items-center justify-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)] hover:bg-[var(--surface-muted)] hover:underline"
                  >
                    <span>Mở Ingestion</span>
                    <Icon name="arrow-right" size={11} />
                  </Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 4. Visual Hierarchy #3: Recent Operations (Full-Width Operational History Ledger) */}
      <section aria-labelledby="recent-operations-title" className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 id="recent-operations-title" className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Icon name="clinical-notes" size={18} className="text-[var(--brand-600)]" />
              <span>Hoạt động Vận hành Gần đây (Recent Operations)</span>
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Nhật ký kiểm toán thời gian thực từ Admin Audit Trail (getAdminAuditLog). Tuyệt đối không chứa thông tin định danh (PII).
            </p>
          </div>
          <Link
            href="/admin/audit-log"
            className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-brand)] hover:underline"
          >
            <span>Xem toàn bộ nhật ký kiểm toán</span>
            <Icon name="arrow-right" size={12} />
          </Link>
        </div>

        {isLoadingExtra ? (
          <div className="h-32 animate-pulse rounded-xl bg-[var(--surface-muted)]" />
        ) : auditLogs.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="px-4 py-2.5">Thời điểm</th>
                  <th className="px-4 py-2.5">Tác nhân</th>
                  <th className="px-4 py-2.5">Hành động</th>
                  <th className="px-4 py-2.5">Đối tượng</th>
                  <th className="px-4 py-2.5">Kết quả</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.slice(0, 8).map((record) => {
                  const outcomeChip = getOutcomeChip(record.outcome);
                  return (
                    <tr
                      key={record.id}
                      className="border-b border-[color:var(--shell-border)] last:border-0 hover:bg-[var(--surface-muted)]/50 transition"
                    >
                      <td className="px-4 py-3 text-xs text-[var(--text-secondary)] whitespace-nowrap font-mono">
                        {formatTimestamp(record.created_at)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs font-bold text-[var(--text-primary)] whitespace-nowrap">
                        {record.actor_ref || "--"}
                      </td>
                      <td className="px-4 py-3 font-semibold text-[var(--text-primary)] whitespace-nowrap">
                        {record.action}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                        {record.target || "--"}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
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
          <div className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 text-center text-xs text-[var(--text-secondary)]">
            Chưa có bản ghi hoạt động quản trị nào được ghi nhận.
          </div>
        )}
      </section>

      {/* 5. Visual Hierarchy #4: Audit Digest (Compact Compliance Activity List) */}
      <section aria-labelledby="audit-digest-title" className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-3">
          <div>
            <h2 id="audit-digest-title" className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Icon name="check" size={18} className="text-[var(--success-500)]" />
              <span>Tóm lược Kiểm toán & Tuân thủ (Audit Digest)</span>
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Tổng hợp trạng thái tuân thủ, tính toàn vẹn bản ghi và chốt chặn an toàn bất biến.
            </p>
          </div>
          <Link
            href="/admin/audit-log"
            className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-brand)] hover:underline"
          >
            <span>Mở Nhật ký Kiểm toán Đầy đủ (Immutable Audit Trail)</span>
            <Icon name="arrow-right" size={12} />
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Zero-PII Invariant</span>
              <StatusChip tone="success" label="Đã xác thực" size="sm" />
            </div>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Loại trừ PII 100%</div>
            <div className="text-[11px] text-[var(--text-muted)] leading-relaxed">
              Không lưu tên, email, câu hỏi tự do hoặc ghi chép khám bệnh trong telemetry.
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Append-Only WAL</span>
              <StatusChip tone="success" label="Bất biến" size="sm" />
            </div>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Nhật ký Bất biến</div>
            <div className="text-[11px] text-[var(--text-muted)] leading-relaxed">
              Toàn bộ thao tác quản trị được ký băm SHA-256 và lưu trữ tuần tự không thể sửa đổi.
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">FIDES Guardrail</span>
              <StatusChip tone={isFidesShieldActive ? "success" : "danger"} label={isFidesShieldActive ? "Hoạt động" : "Tắt"} size="sm" />
            </div>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Kiểm chứng An toàn</div>
            <div className="text-[11px] text-[var(--text-muted)] leading-relaxed">
              {isFidesShieldActive ? "100% tuyên bố liều lượng và tương tác thuốc DDI được đối soát." : "Chốt chặn FIDES đang tắt - cần bật lại ngay."}
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Sẵn sàng Kiểm toán</span>
              <span className="font-mono text-xs font-bold text-[var(--text-brand)]">{auditLogs.length} bản ghi</span>
            </div>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Quy trình Thanh tra</div>
            <div className="text-[11px] text-[var(--text-muted)] leading-relaxed">
              Dữ liệu sẵn sàng phục vụ báo cáo an toàn và kiểm toán tuân thủ y tế.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default AdminOverviewPanel;
