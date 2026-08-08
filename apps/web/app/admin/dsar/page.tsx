"use client";

import { useCallback, useEffect, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  isDsarEnabled,
  listAdminDsarQueue,
  updateDsarStatus,
  type DsarKind,
  type DsarRequestRecord,
  type DsarStatus,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";

/**
 * Admin DSAR queue (regulatory-compliance Requirement 3.6, design §C, Property
 * P7).
 *
 * An admin-only surface that lists every Data Subject Access Request and tracks
 * each against its statutory response window, flagging overdue items. Admins
 * can advance a request's resolution status. The queue rows carry only request
 * type/status/timestamps and an opaque reference — never PII.
 *
 * RBAC is enforced authoritatively by the backend (`/compliance/dsar/admin/*`
 * return 401/403 for non-admin; Property P7). This surface additionally hides
 * itself client-side for non-admin roles and only activates when
 * `NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED` is on, otherwise current behavior is
 * preserved (Requirement 8.1, 8.2).
 */

const KIND_LABEL_KEYS: Record<DsarKind, UITranslationKey> = {
  export: "admin.dsar.kind.export",
  correct: "admin.dsar.kind.correct",
  delete: "admin.dsar.kind.delete",
  restrict: "admin.dsar.kind.restrict",
  withdraw: "admin.dsar.kind.withdraw",
};

const STATUS_LABEL_KEYS: Record<DsarStatus, UITranslationKey> = {
  received: "admin.dsar.status.received",
  in_progress: "admin.dsar.status.inProgress",
  fulfilled: "admin.dsar.status.fulfilled",
  rejected: "admin.dsar.status.rejected",
};

const STATUS_ORDER: DsarStatus[] = [
  "received",
  "in_progress",
  "fulfilled",
  "rejected",
];

export default function AdminDsarQueuePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState<number | string | null>(null);
  const [requests, setRequests] = useState<DsarRequestRecord[]>([]);
  const [overdueCount, setOverdueCount] = useState(0);

  const copy = (key: UITranslationKey, values?: Record<string, number>) =>
    t(uiLanguage, key, values);
  const queueErrorText = copy("admin.dsar.loadError");
  const flagOn = isDsarEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    setRoleState(getRole());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const isAdmin = role === "admin";

  const refresh = useCallback(async () => {
    if (!flagOn || !isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listAdminDsarQueue();
      setEnabled(Boolean(data.enabled));
      setRequests(data.requests ?? []);
      setOverdueCount(data.overdue_count ?? 0);
    } catch {
      setError(queueErrorText);
    } finally {
      setLoading(false);
    }
  }, [flagOn, isAdmin, queueErrorText]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onChangeStatus = useCallback(
    async (id: number | string, status: DsarStatus) => {
      setPendingId(id);
      setError("");
      try {
        await updateDsarStatus(id, status);
        await refresh();
      } catch {
        // The administrator can inspect authorized audit data in the queue,
        // but a transport or upstream error is neither an audit fact nor safe
        // user-facing operational copy.
        setError(queueErrorText);
      } finally {
        setPendingId(null);
      }
    },
    [queueErrorText, refresh],
  );

  // Role is resolved on mount; treat the brief null state as still loading.
  const roleResolved = role !== null;
  const showForbidden = roleResolved && !isAdmin;
  const showDisabled = !flagOn || (!loading && roleResolved && isAdmin && !enabled);

  return (
    <PageShell
      variant="plain"
      title={copy("admin.dsar.title")}
      description={copy("admin.dsar.description")}
    >
      <div className="space-y-4">
        {showForbidden ? (
          <p
            role="alert"
            className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm font-medium text-[var(--status-danger-text)]"
          >
            {copy("admin.dsar.forbidden")}
          </p>
        ) : showDisabled ? (
          <p
            role="status"
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {copy("admin.dsar.disabled")}
          </p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3">
              <span
                className={[
                  "rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em]",
                  overdueCount > 0
                    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                    : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
                ].join(" ")}
              >
                {overdueCount > 0
                  ? copy("admin.dsar.overdueSummary", { count: overdueCount })
                  : copy("admin.dsar.none")}
              </span>
            </div>

            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-2.5 text-sm font-medium text-[var(--status-danger-text)]"
              >
                {error}
              </p>
            ) : null}

            {loading ? (
              <p className="text-sm text-[var(--text-secondary)]">
                {copy("admin.dsar.loading")}
              </p>
            ) : requests.length ? (
              <ul className="space-y-2">
                {requests.map((request) => (
                  <li
                    key={request.id}
                    className={[
                      "rounded-2xl border bg-[var(--surface-panel)] p-4",
                      request.overdue
                        ? "border-[color:var(--status-danger-border)]"
                        : "border-[color:var(--shell-border)]",
                    ].join(" ")}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-bold text-[var(--text-primary)]">
                            {copy(KIND_LABEL_KEYS[request.kind])}
                          </p>
                          {request.overdue ? (
                            <span className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--status-danger-text)]">
                              {copy("admin.dsar.overdueBadge")}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                          {copy("admin.dsar.refId")}: {request.id}
                          {request.created_at
                            ? ` · ${copy("admin.dsar.submittedAt")}: ${formatLocaleDate(uiLanguage, request.created_at, { dateStyle: "medium", timeStyle: "short" })}`
                            : ""}
                          {request.due_at
                            ? ` · ${copy("admin.dsar.dueAt")}: ${formatLocaleDate(uiLanguage, request.due_at)}`
                            : ""}
                          {request.resolved_at
                            ? ` · ${copy("admin.dsar.resolvedAt")}: ${formatLocaleDate(uiLanguage, request.resolved_at)}`
                            : ""}
                        </p>
                      </div>
                      <label className="flex shrink-0 items-center gap-2 text-[12px] text-[var(--text-secondary)]">
                        <span className="sr-only">{copy("admin.dsar.statusLabel")}</span>
                        <select
                          aria-label={copy("admin.dsar.statusLabel")}
                          disabled={pendingId === request.id}
                          value={request.status}
                          onChange={(e) =>
                            void onChangeStatus(
                              request.id,
                              e.target.value as DsarStatus,
                            )
                          }
                          className="min-h-[36px] rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-sm font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {STATUS_ORDER.map((status) => (
                            <option key={status} value={status}>
                              {copy(STATUS_LABEL_KEYS[status])}
                            </option>
                          ))}
                        </select>
                        {pendingId === request.id ? (
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {copy("admin.dsar.saving")}
                          </span>
                        ) : null}
                      </label>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">
                {copy("admin.dsar.empty")}
              </p>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
