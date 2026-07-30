"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import EnterpriseReview from "@/components/scribe/enterprise-review";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { getRole, type UserRole } from "@/lib/auth-store";
import { trackScribeGenerated, trackScribeViewed } from "@/lib/analytics/events";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import type { UILanguage } from "@/lib/ui-language";
import {
  ScribeAnalyticsSummary,
  ScribeSession,
  createScribeSession,
  getScribeAnalyticsSummary,
  getScribeSession,
  listScribeSessions,
  normalizeSoapSections,
  regenerateScribeSession,
  transcribeScribeAudio,
  updateScribeSession,
} from "@/lib/scribe";

type NoticeTone = "success" | "error";
type WorkspaceMode = "workspace" | "review" | "enterprise";

type TranscriptRow = {
  id: string;
  timestamp: string;
  speaker: string;
  text: string;
};

type LiveInsight = {
  id: string;
  title: string;
  detail: string;
};

type ScribeCopy = (
  key: UITranslationKey,
  values?: Record<string, string | number>,
) => string;

const DEFAULT_WAVE_BARS = Array.from({ length: 32 }, (_, index) => 18 + ((index * 13) % 72));
const panelClass = "rounded-xl border border-[color:var(--shell-border)] bg-white shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const panelPaddedClass = `${panelClass} p-4`;
const panelPaddedLgClass = `${panelClass} p-5`;
const softPanelClass = "rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const sectionTitleClass = "text-xs font-black uppercase tracking-[0.18em] text-[color:var(--text-muted)] dark:text-slate-200";
const accentTitleClass = "text-xs font-black uppercase tracking-[0.18em] text-[color:var(--brand-600)] dark:text-sky-100";
const bodyTextClass = "text-[color:var(--text-primary)] dark:text-slate-100";
const secondaryTextClass = "text-[color:var(--text-muted)] dark:text-slate-300";
const mutedTextClass = "text-[color:var(--text-muted)] dark:text-slate-400";
const primaryButtonClass =
  "rounded-lg border border-[color:var(--brand-600)] bg-[color:var(--brand-600)] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-[color:var(--brand-700)] disabled:cursor-not-allowed disabled:border-[color:var(--shell-border)] disabled:bg-[color:var(--surface-brand-soft)] disabled:text-[color:var(--text-primary)] disabled:opacity-100 dark:border-sky-400 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400";
const secondaryButtonClass =
  "rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-[color:var(--brand-700)] transition hover:bg-[color:var(--surface-brand-soft)] disabled:cursor-not-allowed disabled:bg-[color:var(--surface-brand-soft)] disabled:text-[color:var(--text-primary)] disabled:opacity-100 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100";
const dangerButtonClass =
  "rounded-lg border border-rose-700 bg-rose-600 px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-rose-700";
const transcriptInputClass =
  "min-h-[120px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-4 py-3 text-sm leading-6 text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] outline-none transition focus:border-[color:var(--brand-600)] focus:bg-white focus:ring-4 focus:ring-blue-100 dark:border-sky-700/70 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder:text-slate-400 dark:focus:border-sky-400";

function formatDate(language: UILanguage, value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return formatLocaleDate(language, date, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatClock(language: UILanguage, value: Date = new Date()): string {
  return value.toLocaleTimeString(language === "vi" ? "vi-VN" : "en-US", { hour12: false });
}

function formatDuration(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hh = String(Math.floor(safe / 3600)).padStart(2, "0");
  const mm = String(Math.floor((safe % 3600) / 60)).padStart(2, "0");
  const ss = String(safe % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function safeText(value: string | undefined): string {
  return (value ?? "").trim();
}

function parseTranscriptRows(copy: ScribeCopy, transcript: string): TranscriptRow[] {
  const lines = transcript
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(-120);

  return lines.map((line, index) => {
    const pipeIndex = line.indexOf("|");
    const timeCandidate = pipeIndex > 0 ? line.slice(0, pipeIndex).trim() : "";
    const hasClock = /^\d{2}:\d{2}(?::\d{2})?$/.test(timeCandidate);
    const payload = hasClock ? line.slice(pipeIndex + 1).trim() : line;

    const doctorMatch = /^(dr\.?|doctor|bác sĩ)\s*[:|-]\s*/i;
    const patientMatch = /^(patient|bệnh nhân)\s*[:|-]\s*/i;

    let speaker = copy("scribe.speaker.audio");
    let text = payload;

    if (doctorMatch.test(payload)) {
      speaker = copy("scribe.speaker.clinician");
      text = payload.replace(doctorMatch, "").trim();
    } else if (patientMatch.test(payload)) {
      speaker = copy("scribe.speaker.patient");
      text = payload.replace(patientMatch, "").trim();
    }

    return {
      id: `${index}-${line}`,
      timestamp: hasClock ? timeCandidate : "--:--:--",
      speaker,
      text: text || payload,
    };
  });
}

function buildLiveInsights(session: ScribeSession | null, transcript: string, copy: ScribeCopy): LiveInsight[] {
  if (!session) return [];
  const soap = normalizeSoapSections(asRecord(session.soap) ?? {});
  const soapRecord = asRecord(session.soap);
  const medicalRecord = asRecord(soapRecord?.medical_record_note);
  const warnings = Array.isArray(medicalRecord?.warnings)
    ? (medicalRecord?.warnings as unknown[]).map((item) => String(item).trim()).filter(Boolean)
    : [];

  // Backend-derived clinical text is sanitized through `stripTelemetryLabels`
  // so internal telemetry jargon never reaches the End_User view (Req 4.1).
  const insights: LiveInsight[] = [];
  if (safeText(soap.assessment)) {
    insights.push({
      id: "assessment",
      title: copy("scribe.insight.assessment"),
      detail: stripTelemetryLabels(safeText(soap.assessment)).slice(0, 220),
    });
  }
  if (safeText(soap.plan)) {
    insights.push({
      id: "plan",
      title: copy("scribe.insight.plan"),
      detail: stripTelemetryLabels(safeText(soap.plan)).slice(0, 220),
    });
  }
  warnings.slice(0, 2).forEach((warning, index) => {
    insights.push({
      id: `warning-${index}`,
      title: copy("scribe.insight.warning"),
      detail: stripTelemetryLabels(warning),
    });
  });

  if (insights.length === 0 && transcript.trim()) {
    insights.push({
      id: "transcript",
      title: copy("scribe.insight.transcript"),
      detail: copy("scribe.insight.transcriptDetail", { count: transcript.trim().split(/\s+/).length }),
    });
  }

  return insights.slice(0, 3);
}

function scribeStatusLabel(status: string | undefined, copy: ScribeCopy): string {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "finalized" || normalized === "completed") return copy("scribe.status.finalized");
  if (normalized === "ready") return copy("scribe.status.ready");
  if (normalized === "processing") return copy("scribe.status.processing");
  if (normalized === "error" || normalized === "failed") return copy("scribe.status.error");
  return copy("scribe.status.draft");
}

export default function ScribePage() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values: Record<string, string | number> = {}) => t(language, key, values),
    [language],
  );
  const soapSectionLabels = useMemo(() => [
    { key: "subjective", title: copy("scribe.soap.subjective"), valueKey: "subjective" },
    { key: "objective", title: copy("scribe.soap.objective"), valueKey: "objective" },
    { key: "assessment", title: copy("scribe.soap.assessment"), valueKey: "assessment" },
    { key: "plan", title: copy("scribe.soap.plan"), valueKey: "plan" },
  ] as const, [copy]);
  const [mode, setMode] = useState<WorkspaceMode>("workspace");
  const [sessions, setSessions] = useState<ScribeSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [selectedSession, setSelectedSession] = useState<ScribeSession | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [analytics, setAnalytics] = useState<ScribeAnalyticsSummary | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isLiveAnalyzing, setIsLiveAnalyzing] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastTranscribeMs, setLastTranscribeMs] = useState<number | null>(null);
  const [waveBars, setWaveBars] = useState<number[]>(DEFAULT_WAVE_BARS);
  const [notice, setNotice] = useState<{ tone: NoticeTone; message: string } | null>(null);
  const [error, setError] = useState("");
  const [role, setRole] = useState<UserRole>("normal");

  const selectedSessionIdRef = useRef<number | null>(null);
  const transcriptDraftRef = useRef("");
  const persistTimerRef = useRef<number | null>(null);
  const liveAnalyzeTimerRef = useRef<number | null>(null);
  const recordingTickTimerRef = useRef<number | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  // Timer xoay vòng recorder: stop()/start() recorder mới mỗi chu kỳ để mỗi blob
  // là một file webm hoàn chỉnh (start(timeslice) chỉ chunk đầu có header EBML,
  // các chunk sau không decode độc lập được → backend 422).
  const recorderCycleTimerRef = useRef<number | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const analyserDataRef = useRef<Uint8Array | null>(null);
  const waveformFrameRef = useRef<number | null>(null);

  const chunkQueueRef = useRef<Blob[]>([]);
  const chunkCounterRef = useRef(0);
  const processingChunksRef = useRef(false);
  const analyzingInFlightRef = useRef(false);

  const selectedSoap = useMemo(() => {
    const raw = asRecord(selectedSession?.soap) ?? {};
    return normalizeSoapSections(raw);
  }, [selectedSession]);

  const transcriptRows = useMemo(() => parseTranscriptRows(copy, transcriptDraft), [copy, transcriptDraft]);
  const transcriptPreviewRows = useMemo(() => transcriptRows.slice(-40), [transcriptRows]);
  const liveInsights = useMemo(
    () => buildLiveInsights(selectedSession, transcriptDraft, copy),
    [copy, selectedSession, transcriptDraft]
  );

  const pushNotice = useCallback((tone: NoticeTone, message: string) => {
    setNotice({ tone, message });
    window.setTimeout(() => setNotice(null), 2800);
  }, []);

  const upsertSession = useCallback((next: ScribeSession) => {
    setSessions((current) => {
      const existed = current.some((item) => item.id === next.id);
      const merged = existed
        ? current.map((item) => (item.id === next.id ? next : item))
        : [next, ...current];
      return merged.sort((a, b) => {
        const aTime = new Date(a.updated_at).getTime();
        const bTime = new Date(b.updated_at).getTime();
        return bTime - aTime;
      });
    });
  }, []);

  const clearPersistTimer = useCallback(() => {
    if (persistTimerRef.current !== null) {
      window.clearTimeout(persistTimerRef.current);
      persistTimerRef.current = null;
    }
  }, []);

  const clearLiveAnalyzeTimer = useCallback(() => {
    if (liveAnalyzeTimerRef.current !== null) {
      window.clearTimeout(liveAnalyzeTimerRef.current);
      liveAnalyzeTimerRef.current = null;
    }
  }, []);

  const stopWaveformLoop = useCallback(() => {
    if (waveformFrameRef.current !== null) {
      window.cancelAnimationFrame(waveformFrameRef.current);
      waveformFrameRef.current = null;
    }
  }, []);

  const teardownAudioPipeline = useCallback(() => {
    stopWaveformLoop();

    if (recorderCycleTimerRef.current !== null) {
      window.clearInterval(recorderCycleTimerRef.current);
      recorderCycleTimerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }

    analyserRef.current = null;
    analyserDataRef.current = null;
    setWaveBars(DEFAULT_WAVE_BARS);
  }, [stopWaveformLoop]);

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [sessionRes, analyticsRes] = await Promise.all([
        listScribeSessions(25, 0),
        getScribeAnalyticsSummary(),
      ]);
      setSessions(sessionRes.items);
      setAnalytics(analyticsRes);

      const fallbackSelected = selectedSessionIdRef.current ?? sessionRes.items[0]?.id ?? null;
      if (fallbackSelected) {
        const detail = await getScribeSession(fallbackSelected);
        setSelectedSessionId(detail.id);
        selectedSessionIdRef.current = detail.id;
        setSelectedSession(detail);
        setTranscriptDraft(detail.transcript ?? "");
      } else {
        setSelectedSessionId(null);
        selectedSessionIdRef.current = null;
        setSelectedSession(null);
        setTranscriptDraft("");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.load"));
    } finally {
      setIsLoading(false);
    }
  }, [copy]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  useEffect(() => {
    setRole(getRole());
    // The Scribe surface was viewed (Req 9.1). Consent/PII guarded by the
    // facade; only the coarse surface label is sent — no transcript or note.
    trackScribeViewed();
  }, []);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  useEffect(() => {
    transcriptDraftRef.current = transcriptDraft;
  }, [transcriptDraft]);

  const saveTranscript = useCallback(
    async (nextTranscript: string) => {
      const sessionId = selectedSessionIdRef.current;
      const activeSession = selectedSession;
      if (!sessionId || !activeSession) return;
      try {
        const titleCandidate = nextTranscript.split("\n")[0]?.trim() ?? "";
        const updated = await updateScribeSession(sessionId, {
          transcript: nextTranscript,
          title: titleCandidate ? titleCandidate.slice(0, 120) : activeSession.title,
          status: "draft",
        });
        setSelectedSession(updated);
        upsertSession(updated);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : copy("scribe.error.saveTranscript"));
      }
    },
    [copy, selectedSession, upsertSession]
  );

  const schedulePersistTranscript = useCallback(
    (nextTranscript: string, immediate = false) => {
      clearPersistTimer();
      const delayMs = immediate ? 80 : 1200;
      persistTimerRef.current = window.setTimeout(() => {
        void saveTranscript(nextTranscript);
      }, delayMs);
    },
    [clearPersistTimer, saveTranscript]
  );

  const runLiveAnalyze = useCallback(
    async (nextTranscript: string) => {
      const sessionId = selectedSessionIdRef.current;
      if (!sessionId || nextTranscript.trim().length < 24 || analyzingInFlightRef.current) return;

      analyzingInFlightRef.current = true;
      setIsLiveAnalyzing(true);
      try {
        const updated = await regenerateScribeSession(sessionId, {
          transcript: nextTranscript,
          status: "ready",
        });
        setSelectedSession(updated);
        upsertSession(updated);
        const summary = await getScribeAnalyticsSummary();
        setAnalytics(summary);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : copy("scribe.error.liveAnalysis"));
      } finally {
        analyzingInFlightRef.current = false;
        setIsLiveAnalyzing(false);
      }
    },
    [copy, upsertSession]
  );

  const scheduleLiveAnalyze = useCallback(
    (nextTranscript: string) => {
      clearLiveAnalyzeTimer();
      liveAnalyzeTimerRef.current = window.setTimeout(() => {
        void runLiveAnalyze(nextTranscript);
      }, 2200);
    },
    [clearLiveAnalyzeTimer, runLiveAnalyze]
  );

  const processChunkQueue = useCallback(async () => {
    if (processingChunksRef.current) return;
    const sessionId = selectedSessionIdRef.current;
    if (!sessionId) return;

    processingChunksRef.current = true;
    setIsTranscribing(true);

    try {
      while (chunkQueueRef.current.length > 0) {
        const chunk = chunkQueueRef.current.shift();
        if (!chunk) continue;

        const chunkIndex = chunkCounterRef.current;
        chunkCounterRef.current += 1;

        const response = await transcribeScribeAudio({
          audioFile: chunk,
          filename: `scribe-${sessionId}-${chunkIndex}.webm`,
          language: "vi",
          chunkIndex,
          sessionId,
          appendToSession: false,
        });

        setLastTranscribeMs(typeof response.processing_ms === "number" ? response.processing_ms : null);
        const text = String(response.text ?? "").trim();
        if (!text) continue;

        const stamped = `${formatClock(language)} | ${text}`;
        setTranscriptDraft((prev) => {
          const merged = prev.trim() ? `${prev.trimEnd()}\n${stamped}` : stamped;
          schedulePersistTranscript(merged);
          scheduleLiveAnalyze(merged);
          return merged;
        });
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.transcribe"));
      pushNotice("error", copy("scribe.error.transcribeNotice"));
    } finally {
      processingChunksRef.current = false;
      setIsTranscribing(false);
    }
  }, [copy, language, pushNotice, scheduleLiveAnalyze, schedulePersistTranscript]);

  const ensureSessionReady = useCallback(async (): Promise<number | null> => {
    if (selectedSessionIdRef.current) return selectedSessionIdRef.current;

    const created = await createScribeSession({
      title: copy("scribe.sessionTitle.recording", { date: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }) }),
      transcript: "",
      auto_generate_soap: false,
    });
    setSelectedSessionId(created.id);
    selectedSessionIdRef.current = created.id;
    setSelectedSession(created);
    upsertSession(created);
    return created.id;
  }, [copy, language, upsertSession]);

  const startWaveformLoop = useCallback(() => {
    const analyser = analyserRef.current;
    const dataArray = analyserDataRef.current;
    if (!analyser || !dataArray) return;

    const tick = () => {
      analyser.getByteFrequencyData(dataArray);
      const segment = Math.max(1, Math.floor(dataArray.length / DEFAULT_WAVE_BARS.length));
      const next = Array.from({ length: DEFAULT_WAVE_BARS.length }, (_, index) => {
        const sample = dataArray[index * segment] ?? 0;
        return Math.max(8, Math.min(100, Math.round((sample / 255) * 100)));
      });
      setWaveBars(next);
      waveformFrameRef.current = window.requestAnimationFrame(tick);
    };

    stopWaveformLoop();
    waveformFrameRef.current = window.requestAnimationFrame(tick);
  }, [stopWaveformLoop]);

  const onStartRecording = useCallback(async () => {
    setError("");
    setMode("workspace");

    if (typeof window === "undefined" || !window.navigator?.mediaDevices?.getUserMedia) {
      setError(copy("scribe.error.browserRecording"));
      return;
    }

    try {
      const sessionId = await ensureSessionReady();
      if (!sessionId) {
        setError(copy("scribe.error.createSession"));
        return;
      }

      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      analyserRef.current = analyser;
      analyserDataRef.current = new Uint8Array(analyser.frequencyBinCount);
      startWaveformLoop();

      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const selectedMime = mimeCandidates.find((item) => {
        if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
          return false;
        }
        return MediaRecorder.isTypeSupported(item);
      });

      // Mỗi đoạn 2.8s là MỘT MediaRecorder riêng: stop() nhả ra blob webm hoàn
      // chỉnh (đủ header) để backend decode độc lập từng chunk.
      const startRecorderSegment = () => {
        const activeStream = mediaStreamRef.current;
        if (!activeStream || !activeStream.active) return;
        const recorder = selectedMime
          ? new MediaRecorder(activeStream, { mimeType: selectedMime })
          : new MediaRecorder(activeStream);
        recorder.ondataavailable = (event: BlobEvent) => {
          if (event.data.size <= 0) return;
          chunkQueueRef.current.push(event.data);
          void processChunkQueue();
        };
        recorder.start(); // không timeslice — blob duy nhất khi stop()
        mediaRecorderRef.current = recorder;
      };

      startRecorderSegment();
      recorderCycleTimerRef.current = window.setInterval(() => {
        const current = mediaRecorderRef.current;
        if (current && current.state === "recording") {
          current.stop(); // nhả blob hoàn chỉnh của đoạn vừa rồi
        }
        startRecorderSegment();
      }, 2800);

      chunkCounterRef.current = 0;
      setElapsedSeconds(0);
      if (recordingTickTimerRef.current !== null) {
        window.clearInterval(recordingTickTimerRef.current);
      }
      recordingTickTimerRef.current = window.setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);

      setIsRecording(true);
      pushNotice("success", copy("scribe.notice.started"));
    } catch (cause) {
      teardownAudioPipeline();
      setIsRecording(false);
      setError(cause instanceof Error ? cause.message : copy("scribe.error.startRecording"));
    }
  }, [copy, ensureSessionReady, processChunkQueue, pushNotice, startWaveformLoop, teardownAudioPipeline]);

  const onStopRecording = useCallback(() => {
    setIsRecording(false);
    if (recordingTickTimerRef.current !== null) {
      window.clearInterval(recordingTickTimerRef.current);
      recordingTickTimerRef.current = null;
    }
    teardownAudioPipeline();
    clearPersistTimer();
    schedulePersistTranscript(transcriptDraftRef.current, true);
    clearLiveAnalyzeTimer();
    scheduleLiveAnalyze(transcriptDraftRef.current);
    pushNotice("success", copy("scribe.notice.stopped"));
  }, [clearLiveAnalyzeTimer, clearPersistTimer, copy, pushNotice, scheduleLiveAnalyze, schedulePersistTranscript, teardownAudioPipeline]);

  const onSelectSession = useCallback(async (sessionId: number) => {
    setError("");
    try {
      const detail = await getScribeSession(sessionId);
      setSelectedSessionId(detail.id);
      selectedSessionIdRef.current = detail.id;
      setSelectedSession(detail);
      setTranscriptDraft(detail.transcript ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.openSession"));
    }
  }, [copy]);

  const onCreateSession = useCallback(async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createScribeSession({
        title: copy("scribe.sessionTitle.default", { date: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }) }),
        transcript: "",
        auto_generate_soap: false,
      });
      setSelectedSessionId(created.id);
      selectedSessionIdRef.current = created.id;
      setSelectedSession(created);
      setTranscriptDraft(created.transcript ?? "");
      upsertSession(created);
      pushNotice("success", copy("scribe.notice.created"));
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.create"));
    } finally {
      setIsCreating(false);
    }
  }, [copy, language, pushNotice, upsertSession]);

  const onSaveTranscript = useCallback(async () => {
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
      upsertSession(updated);
      pushNotice("success", copy("scribe.notice.saved"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.saveTranscript"));
    } finally {
      setIsSaving(false);
    }
  }, [copy, pushNotice, selectedSession, transcriptDraft, upsertSession]);

  const onRegenerateSoap = useCallback(async () => {
    if (!selectedSession) return;
    if (!transcriptDraft.trim()) {
      pushNotice("error", copy("scribe.error.emptyTranscript"));
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
      upsertSession(updated);
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
      pushNotice("success", copy("scribe.notice.regenerated"));
      // Coarse, non-PII product event (Req 9.1, 9.4); no transcript/note content.
      trackScribeGenerated({ action: "regenerate" });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.regenerate"));
    } finally {
      setIsRegenerating(false);
    }
  }, [copy, pushNotice, selectedSession, transcriptDraft, upsertSession]);

  const onFinalize = useCallback(async () => {
    if (!selectedSession) return;
    setIsSaving(true);
    setError("");
    try {
      const updated = await updateScribeSession(selectedSession.id, { status: "finalized" });
      setSelectedSession(updated);
      upsertSession(updated);
      pushNotice("success", copy("scribe.notice.finalized"));
      // Coarse, non-PII product event (Req 9.1, 9.4); no transcript/note content.
      trackScribeGenerated({ action: "finalize" });
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("scribe.error.finalize"));
    } finally {
      setIsSaving(false);
    }
  }, [copy, pushNotice, selectedSession, upsertSession]);

  useEffect(() => {
    return () => {
      if (recordingTickTimerRef.current !== null) {
        window.clearInterval(recordingTickTimerRef.current);
      }
      clearPersistTimer();
      clearLiveAnalyzeTimer();
      teardownAudioPipeline();
    };
  }, [clearLiveAnalyzeTimer, clearPersistTimer, teardownAudioPipeline]);

  return (
    <PageShell title="" description="" variant="plain">
      <section className="space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-white px-4 py-3 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
          <div className="flex items-center gap-6">
            <span className="text-lg font-black tracking-tight text-[color:var(--brand-600)] dark:text-sky-100">ScribeOS v2.4</span>
            <nav className="inline-flex items-center gap-1 rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] p-1 dark:border-sky-700/70 dark:bg-slate-800/90">
              <button
                type="button"
                onClick={() => setMode("workspace")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "workspace"
                    ? "bg-[color:var(--brand-600)] text-white shadow-sm"
                    : "text-[color:var(--text-primary)] hover:bg-[color:var(--surface-brand-soft)] dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {copy("scribe.tab.workspace")}
              </button>
              <button
                type="button"
                onClick={() => setMode("review")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "review" ? "bg-[color:var(--brand-600)] text-white shadow-sm" : "text-[color:var(--text-primary)] hover:bg-[color:var(--surface-brand-soft)] dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {copy("scribe.tab.review")}
              </button>
              <button
                type="button"
                onClick={() => setMode("enterprise")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "enterprise" ? "bg-[color:var(--brand-600)] text-white shadow-sm" : "text-[color:var(--text-primary)] hover:bg-[color:var(--surface-brand-soft)] dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {copy("scribe.tab.enterprise")}
              </button>
            </nav>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isRecording ? (
              <button
                type="button"
                onClick={onStopRecording}
                className={dangerButtonClass}
              >
                {copy("scribe.action.stopRecording")}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void onStartRecording()}
                className={primaryButtonClass}
              >
                {copy("scribe.action.startRecording")}
              </button>
            )}

            <button
              type="button"
              onClick={() => void onRegenerateSoap()}
              disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
              className={secondaryButtonClass}
            >
              {isRegenerating || isLiveAnalyzing ? copy("scribe.status.analyzing") : copy("scribe.action.regenerate")}
            </button>

            <button
              type="button"
              onClick={() => void onFinalize()}
              disabled={!selectedSession || isSaving}
              className={primaryButtonClass}
            >
              {copy("scribe.action.complete")}
            </button>
          </div>
        </header>

        <section className="grid grid-cols-12 gap-5">
          <aside className="col-span-12 xl:col-span-3 space-y-3">
            <div className={panelPaddedClass}>
              <div className="flex items-center justify-between">
                <h2 className={sectionTitleClass}>{copy("scribe.sessions.title")}</h2>
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-2 py-0.5 text-[10px] font-bold text-[color:var(--brand-700)] dark:border-sky-600 dark:bg-sky-500/20 dark:text-sky-100">
                  {copy("scribe.sessions.count", { count: formatLocaleNumber(language, sessions.length) })}
                </span>
              </div>
              <button
                type="button"
                onClick={() => void onCreateSession()}
                disabled={isCreating}
                className={`mt-3 inline-flex min-h-[42px] w-full items-center justify-center ${secondaryButtonClass}`}
              >
                {isCreating ? copy("scribe.action.creating") : copy("scribe.action.createSession")}
              </button>
            </div>

            <div className="max-h-[66vh] space-y-2 overflow-y-auto pr-1 clara-scrollbar">
              {sessions.map((item) => {
                const active = item.id === selectedSessionId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => void onSelectSession(item.id)}
                    className={`w-full rounded-xl border p-3 text-left transition ${
                      active
                        ? "border-[color:var(--brand-600)] bg-[color:var(--surface-brand-soft)] shadow-sm dark:border-sky-400 dark:bg-sky-500/20"
                        : "border-[color:var(--shell-border)] bg-white hover:border-[color:var(--brand-600)] hover:bg-[color:var(--surface-muted)] dark:border-sky-800 dark:bg-slate-900/90 dark:hover:border-sky-500"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className={`line-clamp-1 text-sm font-bold ${bodyTextClass}`}>
                        {item.title || copy("scribe.sessions.untitled", { id: item.id })}
                      </p>
                      <span className={`text-[10px] font-bold uppercase ${mutedTextClass}`}>{scribeStatusLabel(item.status, copy)}</span>
                    </div>
                    <p className={`mt-1 line-clamp-2 text-xs ${secondaryTextClass}`}>
                      {item.transcript?.trim() || copy("scribe.transcript.empty")}
                    </p>
                    <p className={`mt-2 text-[10px] font-semibold ${mutedTextClass}`}>{formatDate(language, item.updated_at)}</p>
                  </button>
                );
              })}

              {!isLoading && sessions.length === 0 ? (
                <p className={`rounded-xl border border-[color:var(--shell-border)] bg-white p-4 text-sm font-medium ${secondaryTextClass}`}>
                  {copy("scribe.sessions.empty")}
                </p>
              ) : null}
            </div>
          </aside>

          {mode === "enterprise" ? (
            <EnterpriseReview
              session={selectedSession}
              onSessionChange={(updated) => {
                setSelectedSession(updated);
                setTranscriptDraft(updated.transcript ?? "");
                upsertSession(updated);
              }}
              pushNotice={pushNotice}
            />
          ) : mode === "workspace" ? (
            <>
              <article className="col-span-12 2xl:col-span-6 space-y-4">
                <div className={panelPaddedLgClass}>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h3 className={accentTitleClass}>{copy("scribe.audio.title")}</h3>
                      <p className={`mt-1 text-[11px] font-medium ${secondaryTextClass}`}>
                        {isRecording ? copy("scribe.audio.microphoneRecording") : copy("scribe.audio.recorderWaiting")} · {formatDuration(elapsedSeconds)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-[10px] font-bold uppercase tracking-[0.15em] ${mutedTextClass}`}>{copy("scribe.audio.realtime")}</p>
                      <p className={`text-sm font-bold ${bodyTextClass}`}>
                        {isTranscribing ? copy("scribe.status.transcribing") : copy("scribe.status.waiting")}
                      </p>
                    </div>
                  </div>

                  <div className="flex h-20 items-end gap-[3px]">
                    {waveBars.map((height, index) => (
                      <div
                        key={`wave-${index}`}
                        className={`w-[3px] rounded-[1px] ${isRecording ? "bg-[color:var(--brand-600)]" : "bg-[color:var(--shell-border)]"}`}
                        style={{ height: `${height}%` }}
                      />
                    ))}
                  </div>

                  <p className={`mt-3 text-[10px] font-bold uppercase tracking-[0.18em] ${mutedTextClass}`}>
                    {selectedSession?.last_processed_at
                      ? copy("scribe.audio.lastProcessed", { date: formatDate(language, selectedSession.last_processed_at) })
                      : copy("scribe.status.waiting")}
                  </p>
                </div>

                <div className={panelClass}>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-3 dark:border-sky-800">
                    <h3 className={sectionTitleClass}>{copy("scribe.transcript.liveTitle")}</h3>
                    <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-[color:var(--brand-700)] dark:text-sky-100">
                      <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-[color:var(--brand-600)] animate-pulse" : "bg-slate-500"}`} />
                      {isRecording ? copy("scribe.status.recording") : copy("scribe.status.stopped")}
                    </div>
                  </div>

                  <div className="max-h-[420px] space-y-4 overflow-y-auto p-5 clara-scrollbar">
                    {transcriptPreviewRows.length === 0 ? (
                      <p className={`text-sm font-medium ${secondaryTextClass}`}>{copy("scribe.transcript.liveEmpty")}</p>
                    ) : (
                      transcriptPreviewRows.map((row) => (
                        <div key={row.id} className="flex gap-3">
                          <span className={`w-16 shrink-0 pt-1 text-[10px] font-bold ${mutedTextClass}`}>
                            {row.timestamp}
                          </span>
                          <div className="space-y-1">
                            <p className="text-[10px] font-black uppercase tracking-[0.1em] text-[color:var(--brand-600)] dark:text-sky-100">{row.speaker}</p>
                            <p className={`text-sm leading-6 ${secondaryTextClass}`}>{stripTelemetryLabels(row.text)}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="border-t border-[color:var(--shell-border)] p-4 dark:border-sky-800">
                    <textarea
                      value={transcriptDraft}
                      onChange={(event) => setTranscriptDraft(event.target.value)}
                      placeholder={copy("scribe.transcript.placeholder")}
                      className={transcriptInputClass}
                    />
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <p className={`text-[10px] font-bold uppercase tracking-[0.12em] ${mutedTextClass}`}>
                        {copy("scribe.transcript.wordCount", { count: formatLocaleNumber(language, transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0) })}
                      </p>
                      <button
                        type="button"
                        onClick={() => void onSaveTranscript()}
                        disabled={!selectedSession || isSaving}
                        className={secondaryButtonClass}
                      >
                        {isSaving ? copy("scribe.action.saving") : copy("scribe.action.saveDraft")}
                      </button>
                    </div>
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className={panelPaddedLgClass}>
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className={sectionTitleClass}>{copy("scribe.soap.title")}</h3>
                    <button
                      type="button"
                      onClick={() => void onRegenerateSoap()}
                      disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
                      className={secondaryButtonClass}
                    >
                      {isRegenerating || isLiveAnalyzing ? copy("scribe.status.analyzing") : copy("scribe.action.regenerate")}
                    </button>
                  </div>

                  <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1 clara-scrollbar">
                    {soapSectionLabels.map((item) => (
                      <article key={item.key} className={`${softPanelClass} p-3`}>
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-[color:var(--brand-600)] dark:text-sky-100">{item.title}</p>
                        <p className={`mt-2 whitespace-pre-wrap text-sm leading-6 ${secondaryTextClass}`}>
                          {stripTelemetryLabels(safeText(selectedSoap[item.valueKey])) || copy("scribe.noData")}
                        </p>
                      </article>
                    ))}
                  </div>
                </div>

                <div className={panelPaddedLgClass}>
                  <h3 className={sectionTitleClass}>{copy("scribe.liveAnalysis.title")}</h3>
                  <div className="mt-3 space-y-2">
                    <p className={`text-sm font-medium ${secondaryTextClass}`}>
                      {isLiveAnalyzing ? copy("scribe.status.liveAnalyzing") : copy("scribe.status.liveReady")}
                    </p>
                    {/* Raw pipeline timing is internal telemetry — admin only (Req 4.3). */}
                    <TelemetryPanel role={role}>
                      <p className={`text-[11px] font-medium ${mutedTextClass}`}>
                        {copy("scribe.processingSpeed")}: {lastTranscribeMs !== null ? `${lastTranscribeMs.toFixed(1)} ms${copy("scribe.processingPerSegment")}` : "--"}
                      </p>
                    </TelemetryPanel>
                  </div>
                  <div className="mt-4 space-y-2">
                    {liveInsights.length === 0 ? (
                      <p className={`text-xs font-medium ${secondaryTextClass}`}>{copy("scribe.liveAnalysis.empty")}</p>
                    ) : (
                      liveInsights.map((item) => (
                        <article key={item.id} className={`${softPanelClass} p-3`}>
                          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-[color:var(--brand-600)] dark:text-sky-100">{item.title}</p>
                          <p className={`mt-1 text-xs leading-5 ${secondaryTextClass}`}>{item.detail}</p>
                        </article>
                      ))
                    )}
                  </div>
                </div>
              </aside>
            </>
          ) : (
            <>
              <article className="col-span-12 2xl:col-span-6 space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className={`col-span-1 ${panelPaddedClass}`}>
                    <p className={sectionTitleClass}>{copy("scribe.review.statusTitle")}</p>
                    <p className={`mt-4 text-xs leading-5 ${secondaryTextClass}`}>
                      {copy("scribe.review.statusDescription")}
                    </p>
                  </div>

                  <div className={`col-span-2 ${panelPaddedClass}`}>
                    <p className={sectionTitleClass}>{copy("scribe.review.signalStability")}</p>
                    <div className="mt-4 flex h-28 items-end gap-1">
                      {waveBars.slice(0, 16).map((value, index) => (
                        <div
                          key={`review-wave-${index}`}
                          className="flex-1 rounded-sm bg-[color:var(--brand-600)]"
                          style={{ height: `${Math.max(10, Math.round((value / 100) * 100))}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] p-6 shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90">
                  <div className="mb-5 flex items-center justify-between">
                    <div>
                      <h2 className={`text-2xl font-black tracking-tight ${bodyTextClass}`}>{copy("scribe.review.summaryTitle")}</h2>
                      <p className={`text-sm font-medium ${secondaryTextClass}`}>
                        {copy("scribe.review.sessionCode", { code: selectedSession ? `#${selectedSession.id}` : "--" })}
                      </p>
                    </div>
                    <span className="rounded-full border border-[color:var(--shell-border)] bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-[color:var(--brand-700)] dark:border-sky-600 dark:bg-slate-900 dark:text-sky-100">
                      {scribeStatusLabel(selectedSession?.status, copy)}
                    </span>
                  </div>

                  <div className="space-y-5">
                    {soapSectionLabels.map((item) => (
                      <section key={item.key}>
                        <h5 className="text-[10px] font-black uppercase tracking-[0.2em] text-[color:var(--brand-600)] dark:text-sky-100">{item.title}</h5>
                        <div className="mt-2 rounded-lg border border-[color:var(--shell-border)] bg-white p-4 dark:border-sky-800 dark:bg-slate-900/90">
                          <p className={`whitespace-pre-wrap text-sm leading-6 ${secondaryTextClass}`}>
                            {stripTelemetryLabels(safeText(selectedSoap[item.valueKey])) || copy("scribe.noData")}
                          </p>
                        </div>
                      </section>
                    ))}
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className={panelPaddedClass}>
                  <h3 className={sectionTitleClass}>{copy("scribe.review.specialistCoding")}</h3>
                  <p className={`mt-3 text-xs leading-5 ${secondaryTextClass}`}>
                    {copy("scribe.review.codingDescription")}
                  </p>
                </div>

                <div className={panelPaddedClass}>
                  <h3 className={accentTitleClass}>{copy("scribe.review.council")}</h3>
                  <div className={`mt-3 ${softPanelClass} p-3`}>
                    <p className="text-[10px] font-black uppercase text-[color:var(--brand-600)] dark:text-sky-100">{copy("scribe.review.keySummary")}</p>
                    <p className={`mt-2 text-xs leading-5 ${secondaryTextClass}`}>
                      {liveInsights[0]?.detail || copy("scribe.review.noSummary")}
                    </p>
                    <p className={`mt-3 text-[10px] font-medium ${mutedTextClass}`}>
                      {copy("scribe.review.wordCount", { count: formatLocaleNumber(language, transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0) })}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={`mt-3 w-full ${secondaryButtonClass}`}
                  >
                    {copy("scribe.action.saveToRecord")}
                  </button>
                </div>

                <div className={panelPaddedClass}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-[8px] font-bold uppercase tracking-[0.15em] ${mutedTextClass}`}>{copy("scribe.processingSpeed")}</p>
                      <div className="text-sm font-black text-[color:var(--brand-700)] dark:text-sky-100">
                        {/* Raw per-segment pipeline latency is internal telemetry — admin only (Req 4.3). */}
                        <TelemetryPanel role={role} summaryText="--" className="inline">
                          <span>
                            {lastTranscribeMs !== null ? `${(lastTranscribeMs / 1000).toFixed(2)}s` : "--"}
                          </span>
                        </TelemetryPanel>
                        <span className={`text-[10px] ${secondaryTextClass}`}> {copy("scribe.processingPerSegment")}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
                      <span className="text-[10px] font-black uppercase text-emerald-700 dark:text-emerald-300">{isRecording ? copy("scribe.status.recording") : copy("scribe.status.waiting")}</span>
                    </div>
                  </div>
                </div>
              </aside>
            </>
          )}
        </section>

        <section className={`grid grid-cols-2 gap-3 md:grid-cols-4 ${panelPaddedClass}`}>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>{copy("scribe.metrics.totalSessions")}</p>
            <p className={`mt-2 text-xl font-black ${bodyTextClass}`}>{analytics?.total_sessions ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>{copy("scribe.metrics.completedSessions")}</p>
            <p className="mt-2 text-xl font-black text-[color:var(--brand-700)] dark:text-sky-100">{analytics?.completed_sessions ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>{copy("scribe.metrics.today")}</p>
            <p className={`mt-2 text-xl font-black ${bodyTextClass}`}>{analytics?.sessions_today ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>{copy("scribe.metrics.averageCharacters")}</p>
            <p className={`mt-2 text-xl font-black ${bodyTextClass}`}>
              {Math.round(analytics?.avg_transcript_chars ?? 0)}
            </p>
          </div>
        </section>
      </section>

      {error ? (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 dark:border-rose-500/70 dark:bg-rose-500/20 dark:text-rose-100">{error}</p>
      ) : null}
      {notice ? (
        <p
          className={`mt-4 rounded-lg border px-4 py-2 text-sm font-semibold ${
            notice.tone === "success"
              ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100"
              : "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/70 dark:bg-rose-500/20 dark:text-rose-100"
          }`}
        >
          {notice.message}
        </p>
      ) : null}
    </PageShell>
  );
}
