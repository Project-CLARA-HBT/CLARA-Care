"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard, InlineError } from "@/components/ui/surface";
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
 * DSAR self-service (regulatory-compliance Requirement 3, design §C, Property
 * P7).
 *
 * Lets an authenticated data subject exercise their PDPD rights: export
 * (portability), correct, delete, restrict processing, and withdraw consent.
 * Each request is acknowledged and tracked against the statutory window by the
 * backend; this surface records the request type only (no extra PII).
 *
 * The surface activates only when `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` is on;
 * otherwise it shows a "feature unavailable" notice and current behavior is
 * preserved (Requirement 8.1, 8.2).
 */

type ActionCopy = {
  kind: DsarKind;
  label: UITranslationKey;
  description: UITranslationKey;
  /** Destructive actions require an explicit confirm step. */
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

  const text = useMemo(
    () => ({
      title: t(uiLanguage, "dataRights.title"),
      description: t(uiLanguage, "dataRights.description"),
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
    }),
    [uiLanguage],
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
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-4">
        {showDisabled ? (
          <p
            role="status"
            className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {text.disabled}
          </p>
        ) : (
          <>
            {notice ? (
              <p
                role="status"
                className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-ok-text)]"
              >
                {notice}
              </p>
            ) : null}
            {error ? <InlineError message={error} /> : null}

            <ul className="grid gap-3 md:grid-cols-2">
              {ACTIONS.map((action) => {
                const isPending = pendingKind === action.kind;
                const isExport = action.kind === "export";
                return (
                  <SurfaceCard
                    key={action.kind}
                    className="flex flex-col p-4"
                  >
                    <p className="text-sm font-bold text-[var(--text-primary)]">
                      {t(uiLanguage, action.label)}
                    </p>
                    <p className="mt-1 flex-1 text-[13px] leading-6 text-[var(--text-secondary)]">
                      {t(uiLanguage, action.description)}
                    </p>
                    {action.destructive && action.kind === "delete" ? (
                      <p className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">
                        {text.retentionNote}
                      </p>
                    ) : null}

                    {action.destructive && action.kind === "delete" ? (
                      <div className="mt-3">
                        <Button
                          as="link"
                          href="/account/data/delete/review"
                          variant="danger"
                          size="sm"
                        >
                          {t(uiLanguage, action.label)}
                        </Button>
                      </div>
                    ) : (
                      <div className="mt-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={isPending}
                          onClick={() =>
                            isExport
                              ? void onExport()
                              : void onSubmit(
                                  action.kind as Exclude<DsarKind, "export" | "delete">,
                                )
                          }
                        >
                          {isPending
                            ? isExport
                              ? text.exporting
                              : text.submitting
                            : isExport
                              ? text.download
                              : text.submit}
                        </Button>
                      </div>
                    )}
                  </SurfaceCard>
                );
              })}
            </ul>

            <SurfaceCard className="p-4">
              <p className="text-sm font-bold text-[var(--text-primary)]">
                {text.historyTitle}
              </p>
              {loading ? (
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  {text.loading}
                </p>
              ) : requests.length ? (
                <ul className="mt-3 space-y-2">
                  {requests.map((request) => (
                    <li
                      key={request.id}
                      className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                          {t(
                            uiLanguage,
                            ACTIONS.find((action) => action.kind === request.kind)
                              ?.label ?? "dataRights.action.unknown",
                          )}
                        </p>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {request.created_at
                            ? `${text.submittedAt}: ${formatLocaleDate(uiLanguage, request.created_at, { dateStyle: "medium", timeStyle: "short" })}`
                            : ""}
                          {request.due_at
                            ? ` · ${text.dueAt}: ${formatLocaleDate(uiLanguage, request.due_at)}`
                            : ""}
                        </p>
                      </div>
                      <Badge tone="neutral">
                        {t(
                          uiLanguage,
                          STATUS_LABELS[request.status] ??
                            "dataRights.status.unknown",
                        )}
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--text-muted)]">
                  {text.noHistory}
                </p>
              )}
            </SurfaceCard>
          </>
        )}
      </div>
    </PageShell>
  );
}
