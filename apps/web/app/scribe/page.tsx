"use client";

import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  ScribeAnalyticsSummary,
  ScribeSession,
  createScribeSession,
  getScribeAnalyticsSummary,
  getScribeSession,
  listScribeSessions,
  normalizeSoapSections,
  regenerateScribeSession,
  updateScribeSession,
} from "@/lib/scribe";

type NoticeTone = "success" | "error";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function safeText(value: string | undefined): string {
  return (value ?? "").trim();
}

export default function ScribePage() {
  const [sessions, setSessions] = useState<ScribeSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [selectedSession, setSelectedSession] = useState<ScribeSession | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [analytics, setAnalytics] = useState<ScribeAnalyticsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [notice, setNotice] = useState<{ tone: NoticeTone; message: string } | null>(null);
  const [error, setError] = useState("");

  const selectedSoap = useMemo(() => {
    const raw = selectedSession?.soap;
    if (!raw || typeof raw !== "object") {
      return normalizeSoapSections({});
    }
    return normalizeSoapSections(raw);
  }, [selectedSession]);

  const transcriptRows = useMemo(() => {
    const content = transcriptDraft.trim();
    if (!content) return [];
    return content
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 30);
  }, [transcriptDraft]);

  const confidenceScore = useMemo(() => {
    const base = analytics?.completed_sessions && analytics.total_sessions > 0
      ? (analytics.completed_sessions / analytics.total_sessions) * 100
      : 0;
    const soapSignal = safeText(selectedSoap.subjective).length > 10 ? 30 : 0;
    const objectiveSignal = safeText(selectedSoap.objective).length > 10 ? 20 : 0;
    const planSignal = safeText(selectedSoap.plan).length > 10 ? 20 : 0;
    return Math.max(5, Math.min(99, Math.round(base * 0.3 + soapSignal + objectiveSignal + planSignal)));
  }, [analytics, selectedSoap]);

  const pushNotice = (tone: NoticeTone, message: string) => {
    setNotice({ tone, message });
    window.setTimeout(() => setNotice(null), 2800);
  };

  const refreshData = async () => {
    setIsLoading(true);
    setError("");
    try {
      const [sessionRes, analyticsRes] = await Promise.all([
        listScribeSessions(25, 0),
        getScribeAnalyticsSummary(),
      ]);
      setSessions(sessionRes.items);
      setAnalytics(analyticsRes);

      const fallbackSelected = selectedSessionId ?? sessionRes.items[0]?.id ?? null;
      if (fallbackSelected) {
        const detail = await getScribeSession(fallbackSelected);
        setSelectedSessionId(detail.id);
        setSelectedSession(detail);
        setTranscriptDraft(detail.transcript ?? "");
      } else {
        setSelectedSessionId(null);
        setSelectedSession(null);
        setTranscriptDraft("");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải dữ liệu Scribe.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSelectSession = async (sessionId: number) => {
    setError("");
    try {
      const detail = await getScribeSession(sessionId);
      setSelectedSessionId(detail.id);
      setSelectedSession(detail);
      setTranscriptDraft(detail.transcript ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể mở session.");
    }
  };

  const onCreateSession = async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createScribeSession({
        title: `Session ${new Date().toLocaleString("vi-VN")}`,
        transcript: transcriptDraft.trim(),
        auto_generate_soap: Boolean(transcriptDraft.trim()),
      });
      pushNotice("success", "Đã tạo session mới.");
      await refreshData();
      await onSelectSession(created.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo session.");
    } finally {
      setIsCreating(false);
    }
  };

  const onSaveTranscript = async () => {
    if (!selectedSession) return;
    setIsSaving(true);
    setError("");
    try {
      const titleCandidate = transcriptDraft.split("\n")[0]?.trim() ?? "";
      const updated = await updateScribeSession(selectedSession.id, {
        transcript: transcriptDraft,
        title: titleCandidate ? titleCandidate.slice(0, 120) : selectedSession.title,
        status: "draft",
      });
      setSelectedSession(updated);
      setSessions((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      pushNotice("success", "Đã lưu transcript.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu transcript.");
    } finally {
      setIsSaving(false);
    }
  };

  const onRegenerateSoap = async () => {
    if (!selectedSession) return;
    if (!transcriptDraft.trim()) {
      pushNotice("error", "Transcript đang trống.");
      return;
    }
    setIsRegenerating(true);
    setError("");
    try {
      const updated = await regenerateScribeSession(selectedSession.id, {
        transcript: transcriptDraft,
        status: "ready",
      });
      setSelectedSession(updated);
      setSessions((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      pushNotice("success", "Đã regenerate SOAP.");
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể regenerate SOAP.");
    } finally {
      setIsRegenerating(false);
    }
  };

  const onFinalize = async () => {
    if (!selectedSession) return;
    setIsSaving(true);
    setError("");
    try {
      const updated = await updateScribeSession(selectedSession.id, { status: "finalized" });
      setSelectedSession(updated);
      setSessions((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      pushNotice("success", "Đã finalize note.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể finalize note.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title=""
      description=""
      variant="plain"
    >
      <section className="grid grid-cols-12 gap-6">
        <aside className="col-span-12 xl:col-span-3 space-y-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">Session Queue</h2>
              <span className="rounded-full bg-cyan-500/12 px-2 py-0.5 text-[10px] font-semibold text-cyan-300">
                {sessions.length} drafts
              </span>
            </div>
            <button
              type="button"
              onClick={() => void onCreateSession()}
              disabled={isCreating}
              className="mt-3 inline-flex min-h-[42px] w-full items-center justify-center rounded-lg border border-cyan-400/40 bg-gradient-to-r from-cyan-500 to-cyan-700 px-3 text-xs font-bold uppercase tracking-widest text-slate-950 disabled:opacity-60"
            >
              {isCreating ? "Đang tạo..." : "New Consultation"}
            </button>
          </div>

          <div className="max-h-[62vh] space-y-2 overflow-y-auto pr-1 clara-scrollbar">
            {sessions.map((item) => {
              const active = item.id === selectedSessionId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => void onSelectSession(item.id)}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    active
                      ? "border-cyan-400/45 bg-cyan-500/10"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-cyan-300/35"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {item.title || `Session #${item.id}`}
                    </p>
                    <span className="text-[10px] uppercase text-[var(--text-muted)]">{item.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {item.transcript?.trim() || "Chưa có transcript."}
                  </p>
                  <p className="mt-2 text-[10px] text-[var(--text-muted)]">{formatDate(item.updated_at)}</p>
                </button>
              );
            })}
            {!isLoading && sessions.length === 0 ? (
              <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-sm text-[var(--text-secondary)]">
                Chưa có session nào.
              </p>
            ) : null}
          </div>
        </aside>

        <div className="col-span-12 xl:col-span-5 space-y-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-300">Acoustic Input Matrix</h3>
              <span className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
                {selectedSession ? `Session #${selectedSession.id}` : "No session"}
              </span>
            </div>
            <div className="flex h-20 items-end gap-[3px]">
              {Array.from({ length: 40 }).map((_, index) => {
                const seed = transcriptDraft.length > 0 ? transcriptDraft.charCodeAt(index % transcriptDraft.length) : 42;
                const h = 16 + (seed % 80);
                return (
                  <div
                    key={`bar-${index}`}
                    className="w-[3px] rounded-[1px] bg-cyan-400/80"
                    style={{ height: `${h}%` }}
                  />
                );
              })}
            </div>
            <p className="mt-3 text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">
              {selectedSession?.last_processed_at ? `Last processed ${formatDate(selectedSession.last_processed_at)}` : "Waiting for processing"}
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-3">
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">Real-Time Transcript</h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void onSaveTranscript()}
                  disabled={!selectedSession || isSaving}
                  className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)] disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Save Draft"}
                </button>
                <button
                  type="button"
                  onClick={() => void onRegenerateSoap()}
                  disabled={!selectedSession || isRegenerating}
                  className="rounded-lg border border-cyan-400/35 bg-cyan-500/12 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-cyan-200 disabled:opacity-60"
                >
                  {isRegenerating ? "Running..." : "Regenerate SOAP"}
                </button>
              </div>
            </div>

            <div className="grid gap-4 p-5 lg:grid-cols-2">
              <textarea
                value={transcriptDraft}
                onChange={(event) => setTranscriptDraft(event.target.value)}
                placeholder="Nhập transcript buổi khám..."
                className="min-h-[360px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-primary)]"
              />
              <div className="max-h-[360px] space-y-4 overflow-y-auto pr-1 clara-scrollbar">
                {transcriptRows.length === 0 ? (
                  <p className="text-sm text-[var(--text-secondary)]">Chưa có transcript.</p>
                ) : (
                  transcriptRows.map((line, index) => (
                    <div key={`${line}-${index}`} className="flex gap-3">
                      <span className="w-12 shrink-0 pt-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
                        {`14:${String(10 + index).padStart(2, "0")}`}
                      </span>
                      <p className="text-sm leading-6 text-[var(--text-secondary)]">{line}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        <aside className="col-span-12 xl:col-span-4 space-y-4">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">SOAP Draft</h3>
              <button
                type="button"
                onClick={() => void onFinalize()}
                disabled={!selectedSession || isSaving}
                className="rounded-lg border border-cyan-400/35 bg-gradient-to-r from-cyan-500 to-cyan-700 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-950 disabled:opacity-60"
              >
                Finalize Note
              </button>
            </div>

            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1 clara-scrollbar">
              {[
                { key: "S", title: "Subjective", value: selectedSoap.subjective },
                { key: "O", title: "Objective", value: selectedSoap.objective },
                { key: "A", title: "Assessment", value: selectedSoap.assessment },
                { key: "P", title: "Plan", value: selectedSoap.plan },
              ].map((item) => (
                <article key={item.key} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-300">{item.title}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
                    {safeText(item.value) || "Chưa có dữ liệu."}
                  </p>
                </article>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">Analytics</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Total Sessions</p>
                <p className="mt-2 text-xl font-black text-[var(--text-primary)]">{analytics?.total_sessions ?? 0}</p>
              </div>
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Completed</p>
                <p className="mt-2 text-xl font-black text-cyan-300">{analytics?.completed_sessions ?? 0}</p>
              </div>
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Today</p>
                <p className="mt-2 text-xl font-black text-[var(--text-primary)]">{analytics?.sessions_today ?? 0}</p>
              </div>
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Confidence</p>
                <p className="mt-2 text-xl font-black text-cyan-300">{confidenceScore}%</p>
              </div>
            </div>
          </div>
        </aside>
      </section>

      {error ? (
        <p className="mt-4 rounded-lg border border-red-300/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          className={`mt-4 rounded-lg border px-4 py-2 text-sm ${
            notice.tone === "success"
              ? "border-emerald-300/40 bg-emerald-500/10 text-emerald-200"
              : "border-red-300/40 bg-red-500/10 text-red-200"
          }`}
        >
          {notice.message}
        </p>
      ) : null}
    </PageShell>
  );
}
