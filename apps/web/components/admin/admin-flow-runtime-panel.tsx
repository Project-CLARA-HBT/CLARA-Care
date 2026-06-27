"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SystemFlowEvent, getSystemFlowEvents } from "@/lib/system";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";

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

export default function AdminFlowRuntimePanel() {
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
      setError(cause instanceof Error ? cause.message : "Không thể tải runtime flow events.");
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, [sourceFilter]);

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
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật realtime flow events.");
    }
  }, [error, mergeEvents, sourceFilter]);

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
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Runtime Monitor
          </p>
          <h3 className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Realtime Flow Events
          </h3>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
            Theo dõi sequence/stage/status/note từ API `/system/flow-events` để kiểm soát pipeline đang chạy.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
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
                ? "border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                : "border-slate-300 bg-white text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
            )}
          >
            {isAutoRefresh ? "Auto refresh: ON" : "Auto refresh: OFF"}
          </button>

          <button
            type="button"
            onClick={() => void loadInitial()}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
          >
            Reload
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">latest sequence</p>
          <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{latestSequence}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-emerald-50 px-3 py-2 dark:border-emerald-900 dark:bg-emerald-950/40">
          <p className="text-[10px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300">ok</p>
          <p className="mt-1 text-sm font-semibold text-emerald-700 dark:text-emerald-300">{statusSummary.ok}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-amber-50 px-3 py-2 dark:border-amber-900 dark:bg-amber-950/40">
          <p className="text-[10px] uppercase tracking-wider text-amber-700 dark:text-amber-300">warn</p>
          <p className="mt-1 text-sm font-semibold text-amber-700 dark:text-amber-300">{statusSummary.warn}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-rose-50 px-3 py-2 dark:border-rose-900 dark:bg-rose-950/40">
          <p className="text-[10px] uppercase tracking-wider text-rose-700 dark:text-rose-300">error</p>
          <p className="mt-1 text-sm font-semibold text-rose-700 dark:text-rose-300">{statusSummary.error}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">pending</p>
          <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{statusSummary.pending}</p>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </p>
      ) : null}

      <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
        <TelemetryPanel
          role={role}
          summary={
            <p className="px-3 py-5 text-xs text-slate-500 dark:text-slate-400">
              Chi tiết telemetry runtime (payload từng flow event) chỉ hiển thị cho quản trị viên. Tổng quan trạng thái phía trên đã được tóm tắt an toàn.
            </p>
          }
        >
          <div className="grid grid-cols-[5.5rem_11rem_1fr_7rem] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
            <span>Sequence</span>
            <span>Time</span>
            <span>Stage / Note</span>
            <span>Status</span>
          </div>

          <div className="max-h-[28rem] overflow-y-auto">
            {isLoading ? (
              <div className="space-y-2 p-3">
                <div className="h-10 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
                <div className="h-10 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
                <div className="h-10 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
              </div>
            ) : items.length ? (
              items.map((item) => {
                const status = normalizeStatus(item.status);
                return (
                  <div
                    key={`${item.sequence}-${item.stage}-${item.timestamp}`}
                    className="grid grid-cols-[5.5rem_11rem_1fr_7rem] gap-3 border-b border-slate-100 px-3 py-2 text-xs text-slate-700 last:border-b-0 dark:border-slate-800 dark:text-slate-200"
                  >
                    <span className="font-mono text-slate-500 dark:text-slate-400">#{item.sequence}</span>
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">{formatTimestamp(item.timestamp)}</span>
                    <div>
                      <p className="font-semibold text-slate-900 dark:text-slate-100">
                        {item.stage}
                        {item.sourceCount !== null ? ` (${item.sourceCount})` : ""}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-300">
                        {item.note || item.eventType || "No note"}
                      </p>
                    </div>
                    <span
                      className={cx(
                        "inline-flex h-fit w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        status === "ok" &&
                          "border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
                        status === "warn" &&
                          "border-amber-300 bg-amber-100 text-amber-700 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
                        status === "error" &&
                          "border-rose-300 bg-rose-100 text-rose-700 dark:border-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
                        status === "pending" &&
                          "border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
                      )}
                    >
                      {item.status || "pending"}
                    </span>
                  </div>
                );
              })
            ) : (
              <p className="px-3 py-5 text-xs text-slate-500 dark:text-slate-400">
                Chưa có flow event nào cho bộ lọc hiện tại.
              </p>
            )}
          </div>
        </TelemetryPanel>
      </div>
    </section>
  );
}
