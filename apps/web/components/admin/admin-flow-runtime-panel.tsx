"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SystemFlowEvent, getSystemFlowEvents } from "@/lib/system";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

const DEFAULT_LIMIT = 120;
const MAX_KEEP_ITEMS = 180;
const AUTO_REFRESH_MS = 1300;

type SourceFilter = "chat" | "all";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function formatTimestamp(value: string): string {
  if (!value) return "--";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return timestamp.toLocaleString("vi-VN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function normalizeStatus(value: string): "ok" | "warn" | "error" | "pending" {
  const text = value.toLowerCase();
  if (["completed", "done", "success", "pass", "allow", "verified"].some((token) => text.includes(token))) {
    return "ok";
  }
  if (["warn", "warning", "degraded"].some((token) => text.includes(token))) {
    return "warn";
  }
  if (["error", "failed", "timeout", "block", "reject"].some((token) => text.includes(token))) {
    return "error";
  }
  return "pending";
}

export function AdminFlowRuntimePanel() {
  const uiLanguage = useUILanguage();
  const [items, setItems] = useState<SystemFlowEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const [error, setError] = useState("");
  const [latestSequence, setLatestSequence] = useState(0);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("chat");
  // Detailed/raw flow-event telemetry is admin-only (Requirement 11.4,
  // Property 25). The `/system/flow-events` read is operational (doctor+admin),
  // so a non-admin reaching this surface must see only the sanitized summary —
  // never the raw per-event payloads. Visibility is a pure function of role via
  // the shared role-gated TelemetryPanel; hydrate the role client-side so the
  // gate matches the active session (getRole() is "normal" during SSR).
  const [role, setRole] = useState<UserRole>("normal");

  useEffect(() => {
    setRole(getRole());
  }, []);

  const latestSequenceRef = useRef(0);

  const mergeEvents = useCallback((incoming: SystemFlowEvent[]) => {
    if (!incoming.length) return;
    setItems((prev) => {
      const bySeq = new Map<number, SystemFlowEvent>(prev.map((item) => [item.sequence, item]));
      for (const item of incoming) {
        bySeq.set(item.sequence, item);
      }
      const merged = Array.from(bySeq.values()).sort((a, b) => b.sequence - a.sequence);
      return merged.slice(0, MAX_KEEP_ITEMS);
    });
  }, []);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);
    setError("");
    latestSequenceRef.current = 0;
    setLatestSequence(0);

    try {
      const snapshot = await getSystemFlowEvents({
        limit: DEFAULT_LIMIT,
        source: sourceFilter === "all" ? undefined : sourceFilter
      });
      latestSequenceRef.current = snapshot.latestSequence;
      setLatestSequence(snapshot.latestSequence);
      setItems(snapshot.items.slice().sort((a, b) => b.sequence - a.sequence));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(uiLanguage, "admin.flowRuntime.error.load")));
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, [sourceFilter, uiLanguage]);

  const pollNewEvents = useCallback(async () => {
    try {
      const snapshot = await getSystemFlowEvents({
        limit: DEFAULT_LIMIT,
        afterSequence: latestSequenceRef.current || undefined,
        source: sourceFilter === "all" ? undefined : sourceFilter
      });
      if (snapshot.latestSequence > latestSequenceRef.current) {
        latestSequenceRef.current = snapshot.latestSequence;
        setLatestSequence(snapshot.latestSequence);
      }
      mergeEvents(snapshot.items);
      if (error) setError("");
    } catch (cause) {
      setError(safeUserFacingError(cause, t(uiLanguage, "admin.flowRuntime.error.refresh")));
    }
  }, [error, mergeEvents, sourceFilter, uiLanguage]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (!isAutoRefresh) return;
    const timer = window.setInterval(() => {
      void pollNewEvents();
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [isAutoRefresh, pollNewEvents]);

  const statusSummary = useMemo(() => {
    return items.reduce(
      (acc, item) => {
        const normalized = normalizeStatus(item.status);
        if (normalized === "ok") acc.ok += 1;
        else if (normalized === "warn") acc.warn += 1;
        else if (normalized === "error") acc.error += 1;
        else acc.pending += 1;
        return acc;
      },
      { ok: 0, warn: 0, error: 0, pending: 0 }
    );
  }, [items]);

  return (
    <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Runtime Monitor
          </p>
          <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
            Realtime Flow Events
          </h3>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Theo dõi sequence/stage/status/note từ API `/system/flow-events` để kiểm soát pipeline đang chạy.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}
            className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-xs font-medium text-[var(--text-primary)]"
          >
            <option value="chat">source: chat</option>
            <option value="all">source: all</option>
          </select>

          <button
            type="button"
            onClick={() => setIsAutoRefresh((prev) => !prev)}
            className={cx(
              "rounded-lg border px-3 py-1.5 text-xs font-medium transition",
              isAutoRefresh
                ? "border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            )}
          >
            {isAutoRefresh ? "Auto refresh: ON" : "Auto refresh: OFF"}
          </button>

          <button
            type="button"
            onClick={() => void loadInitial()}
            className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:border-[color:var(--brand-primary)]"
          >
            Reload
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-5">
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">latest sequence</p>
          <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{latestSequence}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-brand)]">ok</p>
          <p className="mt-1 text-sm font-semibold text-[var(--text-brand)]">{statusSummary.ok}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-warning)]">warn</p>
          <p className="mt-1 text-sm font-semibold text-[var(--text-warning)]">{statusSummary.warn}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-danger)]">error</p>
          <p className="mt-1 text-sm font-semibold text-[var(--text-danger)]">{statusSummary.error}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">pending</p>
          <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{statusSummary.pending}</p>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]">
          {error}
        </p>
      ) : null}

      <div className="mt-3 overflow-hidden rounded-xl border border-[color:var(--shell-border)]">
        <TelemetryPanel
          role={role}
          summary={
            <p className="px-3 py-5 text-xs text-[var(--text-muted)]">
              Chi tiết telemetry runtime (payload từng flow event) chỉ hiển thị cho quản trị viên. Tổng quan trạng thái phía trên đã được tóm tắt an toàn.
            </p>
          }
        >
          <div className="grid grid-cols-[5.5rem_11rem_1fr_7rem] gap-3 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
            <span>Sequence</span>
            <span>Time</span>
            <span>Stage / Note</span>
            <span>Status</span>
          </div>

          <div className="max-h-[28rem] overflow-y-auto">
            {isLoading ? (
              <div className="space-y-2 p-3">
                <div className="h-10 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
                <div className="h-10 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
                <div className="h-10 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
              </div>
            ) : items.length ? (
              items.map((item) => {
                const status = normalizeStatus(item.status);
                return (
                  <div
                    key={`${item.sequence}-${item.stage}-${item.timestamp}`}
                    className="grid grid-cols-[5.5rem_11rem_1fr_7rem] gap-3 border-b border-[color:var(--shell-border)] px-3 py-2 text-xs text-[var(--text-secondary)] last:border-b-0"
                  >
                    <span className="font-mono text-[var(--text-muted)]">#{item.sequence}</span>
                    <span className="text-[11px] text-[var(--text-muted)]">{formatTimestamp(item.timestamp)}</span>
                    <div>
                      <p className="font-semibold text-[var(--text-primary)]">
                        {item.stage}
                        {item.sourceCount !== null ? ` (${item.sourceCount})` : ""}
                      </p>
                      <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                        {item.note || item.eventType || "No note"}
                      </p>
                    </div>
                    <span
                      className={cx(
                        "inline-flex h-fit w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        status === "ok" &&
                          "border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
                        status === "warn" &&
                          "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
                        status === "error" &&
                          "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
                        status === "pending" &&
                          "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                      )}
                    >
                      {item.status || "pending"}
                    </span>
                  </div>
                );
              })
            ) : (
              <p className="px-3 py-5 text-xs text-[var(--text-muted)]">
                Chưa có flow event nào cho bộ lọc hiện tại.
              </p>
            )}
          </div>
        </TelemetryPanel>
      </div>
    </section>
  );
}

export default AdminFlowRuntimePanel;
