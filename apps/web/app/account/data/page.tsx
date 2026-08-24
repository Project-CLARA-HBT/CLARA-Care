"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { HealthPageHeader } from "@/components/consumer/health-page-header";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InlineError } from "@/components/ui/surface";
import { Icon } from "@/components/ui/icon";
import {
  isDsarEnabled,
  listDsarRequests,
  requestDsarExport,
  submitDsarRequest,
  type DsarKind,
  type DsarRequestRecord,
} from "@/lib/compliance";
import { triggerBlobDownload } from "@/app/chat/_v2/lib/chat-format";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import {
  formatLocaleDate,
  t,
  type UITranslationKey,
} from "@/lib/i18n/catalog";

/**
 * DSAR Data Rights Center (Spec v5 §6.78, Shell: FOCUS, Archetype: Data Rights Center).
 *
 * Lets an authenticated data subject exercise their statutory PDPD (Decree 13/2023/NĐ-CP)
 * and GDPR data rights:
 *   - Comprehensive machine-readable JSON data export (portability)
 *   - Record rectification / correction request
 *   - Immutable audit log access request
 *   - Granular processing restriction & consent withdrawal
 *   - Irreversible account & health data erasure flow (/account/data/delete/warning)
 *
 * Each request is acknowledged and tracked against the statutory window by the
 * backend; this surface records the request type only (no extra PII).
 *
 * Activates when `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` is on; otherwise shows
 * a graceful feature unavailable notice.
 */

type ActionCopy = {
  kind: DsarKind;
  label: UITranslationKey;
  description: UITranslationKey;
  destructive?: boolean;
};

const ACTIONS: ActionCopy[] = [
  {
    kind: "export",
    label: "dataRights.action.export.label",
    description: "dataRights.action.export.description",
  },
  {
    kind: "correct",
    label: "dataRights.action.correct.label",
    description: "dataRights.action.correct.description",
  },
  {
    kind: "restrict",
    label: "dataRights.action.restrict.label",
    description: "dataRights.action.restrict.description",
  },
  {
    kind: "withdraw",
    label: "dataRights.action.withdraw.label",
    description: "dataRights.action.withdraw.description",
  },
  {
    kind: "delete",
    label: "dataRights.action.delete.label",
    description: "dataRights.action.delete.description",
    destructive: true,
  },
];

const STATUS_LABELS: Record<DsarRequestRecord["status"], UITranslationKey> = {
  received: "dataRights.status.received",
  in_progress: "dataRights.status.inProgress",
  fulfilled: "dataRights.status.fulfilled",
  rejected: "dataRights.status.rejected",
};

export default function DataRightsPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingKind, setPendingKind] = useState<DsarKind | null>(null);
  const [requests, setRequests] = useState<DsarRequestRecord[]>([]);

  const isEn = uiLanguage === "en";

  const text = useMemo(
    () => ({
      title: t(uiLanguage, "dataRights.title"),
      centerTitle: t(uiLanguage, "dataRights.centerTitle"),
      backToYou: t(uiLanguage, "dataRights.backToYou"),
      actionsTitle: t(uiLanguage, "dataRights.actionsTitle"),
      description: t(uiLanguage, "dataRights.description"),
      overviewTitle: t(uiLanguage, "dataRights.overview.title"),
      overviewSubtitle: t(uiLanguage, "dataRights.overview.subtitle"),
      decree13Title: t(uiLanguage, "dataRights.overview.decree13.title"),
      decree13Desc: t(uiLanguage, "dataRights.overview.decree13.desc"),
      gdprTitle: t(uiLanguage, "dataRights.overview.gdpr.title"),
      gdprDesc: t(uiLanguage, "dataRights.overview.gdpr.desc"),
      sensitiveHealthTitle: t(uiLanguage, "dataRights.overview.sensitiveHealth.title"),
      sensitiveHealthDesc: t(uiLanguage, "dataRights.overview.sensitiveHealth.desc"),
      disabled: t(uiLanguage, "dataRights.disabled"),
      loading: t(uiLanguage, "dataRights.loading"),
      loadError: t(uiLanguage, "dataRights.loadError"),
      submit: t(uiLanguage, "dataRights.submit"),
      submitting: t(uiLanguage, "dataRights.submitting"),
      exporting: t(uiLanguage, "dataRights.exporting"),
      download: t(uiLanguage, "dataRights.download"),
      historyTitle: t(uiLanguage, "dataRights.historyTitle"),
      noHistory: t(uiLanguage, "dataRights.noHistory"),
      retentionNote: t(uiLanguage, "dataRights.retentionNote"),
      acknowledged: t(uiLanguage, "dataRights.acknowledged"),
      submittedAt: t(uiLanguage, "dataRights.submittedAt"),
      dueAt: t(uiLanguage, "dataRights.dueAt"),
      exportLabel: t(uiLanguage, "dataRights.action.export.label"),
      exportDescription: t(uiLanguage, "dataRights.action.export.description"),
      machineReadable: t(uiLanguage, "dataRights.action.export.machineReadable"),
      correctLabel: t(uiLanguage, "dataRights.action.correct.label"),
      correctDescription: t(uiLanguage, "dataRights.action.correct.description"),
      auditLogLabel: t(uiLanguage, "dataRights.action.auditLog.label"),
      auditLogDescription: t(uiLanguage, "dataRights.action.auditLog.description"),
      auditLogButton: t(uiLanguage, "dataRights.action.auditLog.button"),
      restrictLabel: t(uiLanguage, "dataRights.action.restrict.label"),
      restrictDescription: t(uiLanguage, "dataRights.action.restrict.description"),
      withdrawLabel: t(uiLanguage, "dataRights.action.withdraw.label"),
      withdrawDescription: t(uiLanguage, "dataRights.action.withdraw.description"),
      manageConsent: isEn ? "Manage granular consent" : "Quản lý đồng thuận chi tiết",
      destructiveTitle: t(uiLanguage, "dataRights.destructive.title"),
      destructiveBadge: t(uiLanguage, "dataRights.destructive.badge"),
      destructiveDescription: t(uiLanguage, "dataRights.destructive.description"),
      destructiveWarningNote: t(uiLanguage, "dataRights.destructive.warningNote"),
      destructiveAction: t(uiLanguage, "dataRights.destructive.action"),
      flagOnLabel: isEn ? "DSAR Active" : "DSAR Đang kích hoạt",
    }),
    [uiLanguage, isEn],
  );
  const flagOn = isDsarEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const refresh = useCallback(async () => {
    if (!flagOn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listDsarRequests();
      setEnabled(Boolean(data.enabled));
      setRequests(data.requests ?? []);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onExport = useCallback(async () => {
    setPendingKind("export");
    setError("");
    setNotice("");
    try {
      const bundle = await requestDsarExport();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], {
        type: "application/json",
      });
      const stamp = new Date().toISOString().slice(0, 10);
      triggerBlobDownload(blob, `clara-data-export-${stamp}.json`);
      await refresh();
    } catch {
      setError(text.loadError);
    } finally {
      setPendingKind(null);
    }
  }, [refresh, text.loadError]);

  const onSubmit = useCallback(
    async (kind: Exclude<DsarKind, "export" | "delete">) => {
      setPendingKind(kind);
      setError("");
      setNotice("");
      try {
        await submitDsarRequest(kind);
        setNotice(text.acknowledged);
        await refresh();
      } catch {
        setError(text.loadError);
      } finally {
        setPendingKind(null);
      }
    },
    [refresh, text.acknowledged, text.loadError],
  );

  const showDisabled = !flagOn || (!loading && !enabled);

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="data-rights-center">
      {/* 1. Header with back link to /you */}
      <HealthPageHeader
        title={text.centerTitle}
        subtitle={text.description}
        backHref="/you"
        backLabel={text.backToYou}
        badge={<Badge tone="brand">Decree 13 / GDPR</Badge>}
        locale={uiLanguage}
      />

      {showDisabled ? (
        <p
          role="status"
          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          data-testid="dsar-disabled-notice"
        >
          {text.disabled}
        </p>
      ) : (
        <>
          {/* 2. Editorial Overview of Data Rights under Decree 13 & GDPR */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-5 relative overflow-hidden"
            data-testid="editorial-overview-section"
          >
            <div className="absolute top-0 right-0 w-80 h-80 bg-[var(--brand-500)]/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-16" />
            <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 text-[var(--text-brand)]">
                <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)] border border-[color:var(--shell-border)] shrink-0">
                  <Icon name="user-card" size="1.3rem" />
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-brand)]">
                    {text.overviewSubtitle}
                  </span>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {text.overviewTitle}
                  </h2>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="ok">Decree 13</Badge>
                <Badge tone="brand">GDPR</Badge>
              </div>
            </div>

            <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              {/* Pillar 1: Decree 13 */}
              <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)]" />
                  <span>{text.decree13Title}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.decree13Desc}
                </p>
              </div>

              {/* Pillar 2: GDPR Standards */}
              <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="scan" size="0.9rem" className="text-[var(--text-brand)]" />
                  <span>{text.gdprTitle}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.gdprDesc}
                </p>
              </div>

              {/* Pillar 3: Sensitive Health Data */}
              <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
                  <Icon name="clinical-notes" size="0.9rem" className="text-amber-500" />
                  <span>{text.sensitiveHealthTitle}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {text.sensitiveHealthDesc}
                </p>
              </div>
            </div>
          </section>

          {/* Feedback Messages */}
          {notice ? (
            <p
              role="status"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-ok-text)]"
              data-testid="dsar-notice-banner"
            >
              {notice}
            </p>
          ) : null}
          {error ? <InlineError message={error} /> : null}

          {/* 3. Primary Action Rows (Replacing 2-column card grid) */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
            data-testid="primary-actions-section"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                  <Icon name="progress" size="1.15rem" />
                </div>
                <h2 className="text-base font-bold text-[var(--text-primary)]">
                  {text.actionsTitle}
                </h2>
              </div>
              <Badge tone="neutral">{text.flagOnLabel}</Badge>
            </div>

            <div className="divide-y divide-[color:var(--shell-border)]">
              {/* Row 1: Export Data (machine-readable JSON) */}
              <div
                className="py-4.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                data-testid="action-row-export"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-[var(--brand-50)] text-[var(--brand-700)] flex items-center justify-center border border-[color:var(--brand-200)]">
                      <Icon name="download" size="0.95rem" />
                    </div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">
                      {text.exportLabel}
                    </h3>
                    <Badge tone="ok">{text.machineReadable}</Badge>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-2xl pl-9">
                    {text.exportDescription}
                  </p>
                </div>
                <div className="shrink-0 self-start sm:self-center pl-9 sm:pl-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="download"
                    disabled={pendingKind === "export"}
                    onClick={() => void onExport()}
                    data-testid="export-json-button"
                  >
                    {pendingKind === "export" ? text.exporting : text.download}
                  </Button>
                </div>
              </div>

              {/* Row 2: Rectify Record */}
              <div
                className="py-4.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                data-testid="action-row-correct"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-[var(--surface-muted)] text-[var(--text-primary)] flex items-center justify-center border border-[color:var(--shell-border)]">
                      <Icon name="edit" size="0.95rem" />
                    </div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">
                      {text.correctLabel}
                    </h3>
                    <Badge tone="neutral">DSAR §14</Badge>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-2xl pl-9">
                    {text.correctDescription}
                  </p>
                </div>
                <div className="shrink-0 self-start sm:self-center pl-9 sm:pl-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pendingKind === "correct"}
                    onClick={() => void onSubmit("correct")}
                    data-testid="rectify-record-button"
                  >
                    {pendingKind === "correct" ? text.submitting : text.submit}
                  </Button>
                </div>
              </div>

              {/* Row 3: Request Audit Log */}
              <div
                className="py-4.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                data-testid="action-row-audit"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-[var(--surface-muted)] text-[var(--text-primary)] flex items-center justify-center border border-[color:var(--shell-border)]">
                      <Icon name="clinical-notes" size="0.95rem" />
                    </div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">
                      {text.auditLogLabel}
                    </h3>
                    <Badge tone="neutral">Zero-PII Trail</Badge>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-2xl pl-9">
                    {text.auditLogDescription}
                  </p>
                </div>
                <div className="shrink-0 self-start sm:self-center pl-9 sm:pl-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pendingKind === "restrict"}
                    onClick={() => void onSubmit("restrict")}
                    data-testid="request-audit-log-button"
                  >
                    {pendingKind === "restrict" ? text.submitting : text.auditLogButton}
                  </Button>
                </div>
              </div>

              {/* Row 4: Manage Granular Consent & Restrict Processing */}
              <div
                className="py-4.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                data-testid="action-row-consent"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-[var(--surface-muted)] text-[var(--text-primary)] flex items-center justify-center border border-[color:var(--shell-border)]">
                      <Icon name="check" size="0.95rem" />
                    </div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">
                      {text.withdrawLabel}
                    </h3>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-2xl pl-9">
                    {text.withdrawDescription}
                  </p>
                </div>
                <div className="shrink-0 self-start sm:self-center pl-9 sm:pl-0">
                  <Button
                    as="link"
                    href="/account/consent"
                    variant="ghost"
                    size="sm"
                    data-testid="consent-center-link"
                  >
                    {text.manageConsent}
                  </Button>
                </div>
              </div>
            </div>
          </section>

          {/* 4. Dedicated Destructive Section for Delete Account linking to /account/data/delete/warning */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/20 p-6 space-y-4 relative overflow-hidden"
            data-testid="destructive-delete-section"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 text-[var(--status-danger-text)]">
                <div className="w-10 h-10 rounded-xl bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] flex items-center justify-center border border-[color:var(--status-danger-border)] shrink-0">
                  <Icon name="trash" size="1.25rem" />
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--status-danger-text)]">
                    {text.destructiveBadge}
                  </span>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {text.destructiveTitle}
                  </h2>
                </div>
              </div>
              <Badge tone="danger">Destructive Flow</Badge>
            </div>

            <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-3xl">
              {text.destructiveDescription}
            </p>

            <div className="rounded-xl bg-[var(--surface-panel)] p-4 border border-[color:var(--status-danger-border)]/60 text-xs text-[var(--text-secondary)] flex items-start gap-3">
              <Icon name="warning" size="1.15rem" className="text-amber-500 shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                {text.destructiveWarningNote}
              </p>
            </div>

            <div className="pt-2 flex flex-wrap items-center gap-3">
              <Button
                as="link"
                href="/account/data/delete/warning"
                variant="danger"
                size="sm"
                data-testid="delete-account-button"
              >
                {text.destructiveAction}
              </Button>
            </div>
          </section>

          {/* 5. Request Status & Timeline */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
            data-testid="request-history-section"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                  <Icon name="calendar" size="1.15rem" />
                </div>
                <h2 className="text-base font-bold text-[var(--text-primary)]">
                  {text.historyTitle}
                </h2>
              </div>
              <Badge tone="neutral">{requests.length} records</Badge>
            </div>

            {loading ? (
              <p className="text-sm text-[var(--text-secondary)] py-2">
                {text.loading}
              </p>
            ) : requests.length ? (
              <ul className="divide-y divide-[color:var(--shell-border)]" data-testid="requests-timeline-list">
                {requests.map((request) => (
                  <li
                    key={request.id}
                    className="py-3.5 first:pt-1 last:pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-bold text-[var(--text-primary)]">
                          #{request.id} · {t(uiLanguage, ACTIONS.find((action) => action.kind === request.kind)?.label ?? "dataRights.action.unknown")}
                        </p>
                      </div>
                      <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                        {request.created_at
                          ? `${text.submittedAt}: ${formatLocaleDate(uiLanguage, request.created_at, { dateStyle: "medium", timeStyle: "short" })}`
                          : ""}
                        {request.due_at
                          ? ` · ${text.dueAt}: ${formatLocaleDate(uiLanguage, request.due_at)}`
                          : ""}
                      </p>
                    </div>
                    <Badge
                      tone={
                        request.status === "fulfilled"
                          ? "ok"
                          : request.status === "rejected"
                            ? "danger"
                            : request.status === "in_progress"
                              ? "brand"
                              : "neutral"
                      }
                    >
                      {t(uiLanguage, STATUS_LABELS[request.status] ?? "dataRights.status.unknown")}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <div
                className="p-6 text-center text-xs text-[var(--text-muted)] bg-[var(--surface-muted)] rounded-xl border border-[color:var(--shell-border)]"
                data-testid="empty-requests-message"
              >
                {text.noHistory}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
