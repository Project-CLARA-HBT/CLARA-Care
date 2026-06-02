"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { getRole, type UserRole } from "@/lib/auth-store";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import { trackScribeGenerated, trackScribeViewed } from "@/lib/analytics/events";
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
type WorkspaceMode = "workspace" | "review";

type TranscriptRow = {
  id: string;
  timestamp: string;
  speaker: string;
  text: string;
};

type ClinicalCode = {
  code: string;
  label: string;
};

type LiveInsight = {
  id: string;
  title: string;
  detail: string;
};

const DEFAULT_WAVE_BARS = Array.from({ length: 32 }, (_, index) => 18 + ((index * 13) % 72));

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

function formatClock(value: Date = new Date()): string {
  return value.toLocaleTimeString("vi-VN", { hour12: false });
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

function parseTranscriptRows(transcript: string): TranscriptRow[] {
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

    let speaker = "Live Audio";
    let text = payload;

    if (doctorMatch.test(payload)) {
      speaker = "Doctor";
      text = payload.replace(doctorMatch, "").trim();
    } else if (patientMatch.test(payload)) {
      speaker = "Patient";
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

function deriveClinicalCodes(transcript: string): ClinicalCode[] {
  const lowered = transcript.toLowerCase();
  const rows: ClinicalCode[] = [];

  const add = (code: string, label: string) => {
    if (!rows.some((item) => item.code === code)) rows.push({ code, label });
  };

  if (/gallbladder|chole|sỏi mật|ruq/.test(lowered)) {
    add("K80.20", "Calculus of gallbladder");
    add("47562", "Laparoscopy, cholecystectomy");
  }
  if (/hypertension|tăng huyết áp|blood pressure|bp/.test(lowered)) {
    add("I10", "Essential (primary) hypertension");
  }
  if (/diabetes|đái tháo đường|metformin|insulin/.test(lowered)) {
    add("E11.9", "Type 2 diabetes mellitus");
  }
  if (/warfarin|bleeding|xuất huyết/.test(lowered)) {
    add("Z79.01", "Long term use of anticoagulants");
  }

  if (rows.length === 0) {
    add("R69", "Illness, unspecified");
  }

  return rows.slice(0, 4);
}

function buildLiveInsights(session: ScribeSession | null, transcript: string): LiveInsight[] {
  if (!session) return [];
  const soap = normalizeSoapSections(asRecord(session.soap) ?? {});
  const soapRecord = asRecord(session.soap);
  const medicalRecord = asRecord(soapRecord?.medical_record_note);
  const warnings = Array.isArray(medicalRecord?.warnings)
    ? (medicalRecord?.warnings as unknown[]).map((item) => String(item).trim()).filter(Boolean)
    : [];

  const insights: LiveInsight[] = [];
  if (safeText(soap.assessment)) {
    insights.push({
      id: "assessment",
      title: "Assessment Signal",
      detail: safeText(soap.assessment).slice(0, 220),
    });
  }
  if (safeText(soap.plan)) {
    insights.push({
      id: "plan",
      title: "Plan Draft",
      detail: safeText(soap.plan).slice(0, 220),
    });
  }
  warnings.slice(0, 2).forEach((warning, index) => {
    insights.push({
      id: `warning-${index}`,
      title: "Safety Warning",
      detail: warning,
    });
  });

  if (insights.length === 0 && transcript.trim()) {
    insights.push({
      id: "transcript",
      title: "Transcript Captured",
      detail: `Đã ghi nhận ${transcript.trim().split(/\s+/).length} tokens để phân tích tiếp.`,
    });
  }

  return insights.slice(0, 3);
}

function confidenceFromSoap(analytics: ScribeAnalyticsSummary | null, session: ScribeSession | null): number {
  const soap = normalizeSoapSections(asRecord(session?.soap) ?? {});
  const coverage = [soap.subjective, soap.objective, soap.assessment, soap.plan].filter(
    (item) => safeText(item).length >= 12
  ).length;
  const soapScore = coverage * 20;

  const completedRatio =
    analytics && analytics.total_sessions > 0
      ? (analytics.completed_sessions / analytics.total_sessions) * 100
      : 0;

  return Math.max(5, Math.min(99, Math.round(soapScore + completedRatio * 0.2 + 15)));
}

export default function ScribePage() {
  const [mode, setMode] = useState<WorkspaceMode>("workspace");
  const [role, setRole] = useState<UserRole>("normal");
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

  const selectedSessionIdRef = useRef<number | null>(null);
  const transcriptDraftRef = useRef("");
  const persistTimerRef = useRef<number | null>(null);
  const liveAnalyzeTimerRef = useRef<number | null>(null);
  const recordingTickTimerRef = useRef<number | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
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

  const transcriptRows = useMemo(() => parseTranscriptRows(transcriptDraft), [transcriptDraft]);
  const transcriptPreviewRows = useMemo(() => transcriptRows.slice(-40), [transcriptRows]);
  const liveInsights = useMemo(
    () => buildLiveInsights(selectedSession, transcriptDraft),
    [selectedSession, transcriptDraft]
  );
  const confidenceScore = useMemo(
    () => confidenceFromSoap(analytics, selectedSession),
    [analytics, selectedSession]
  );
  const clinicalCodes = useMemo(() => deriveClinicalCodes(transcriptDraft), [transcriptDraft]);

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
      setError(cause instanceof Error ? cause.message : "Không thể tải dữ liệu Scribe.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  // Read the requesting role for admin-only telemetry gating and emit a single
  // named "scribe_viewed" product event on mount (Req 4.1, 4.3, 9.1).
  useEffect(() => {
    setRole(getRole());
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
        setError(cause instanceof Error ? cause.message : "Không thể lưu transcript.");
      }
    },
    [selectedSession, upsertSession]
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
        setError(cause instanceof Error ? cause.message : "Live analyze thất bại.");
      } finally {
        analyzingInFlightRef.current = false;
        setIsLiveAnalyzing(false);
      }
    },
    [upsertSession]
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

        const stamped = `${formatClock()} | ${text}`;
        setTranscriptDraft((prev) => {
          const merged = prev.trim() ? `${prev.trimEnd()}\n${stamped}` : stamped;
          schedulePersistTranscript(merged);
          scheduleLiveAnalyze(merged);
          return merged;
        });
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể transcribe audio realtime.");
      pushNotice("error", "Transcribe realtime thất bại.");
    } finally {
      processingChunksRef.current = false;
      setIsTranscribing(false);
    }
  }, [pushNotice, scheduleLiveAnalyze, schedulePersistTranscript]);

  const ensureSessionReady = useCallback(async (): Promise<number | null> => {
    if (selectedSessionIdRef.current) return selectedSessionIdRef.current;

    const created = await createScribeSession({
      title: `Live Session ${new Date().toLocaleString("vi-VN")}`,
      transcript: "",
      auto_generate_soap: false,
    });
    setSelectedSessionId(created.id);
    selectedSessionIdRef.current = created.id;
    setSelectedSession(created);
    upsertSession(created);
    return created.id;
  }, [upsertSession]);

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
      setError("Trình duyệt không hỗ trợ ghi âm realtime.");
      return;
    }

    try {
      const sessionId = await ensureSessionReady();
      if (!sessionId) {
        setError("Không thể tạo session để ghi âm.");
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

      const recorder = selectedMime
        ? new MediaRecorder(stream, { mimeType: selectedMime })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size <= 0) return;
        chunkQueueRef.current.push(event.data);
        void processChunkQueue();
      };

      recorder.start(2800);
      mediaRecorderRef.current = recorder;

      chunkCounterRef.current = 0;
      setElapsedSeconds(0);
      if (recordingTickTimerRef.current !== null) {
        window.clearInterval(recordingTickTimerRef.current);
      }
      recordingTickTimerRef.current = window.setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);

      setIsRecording(true);
      pushNotice("success", "Đã bắt đầu ghi âm realtime.");
    } catch (cause) {
      teardownAudioPipeline();
      setIsRecording(false);
      setError(cause instanceof Error ? cause.message : "Không thể bắt đầu ghi âm realtime.");
    }
  }, [ensureSessionReady, processChunkQueue, pushNotice, startWaveformLoop, teardownAudioPipeline]);

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
    pushNotice("success", "Đã dừng ghi âm.");
  }, [clearLiveAnalyzeTimer, clearPersistTimer, pushNotice, scheduleLiveAnalyze, schedulePersistTranscript, teardownAudioPipeline]);

  const onSelectSession = useCallback(async (sessionId: number) => {
    setError("");
    try {
      const detail = await getScribeSession(sessionId);
      setSelectedSessionId(detail.id);
      selectedSessionIdRef.current = detail.id;
      setSelectedSession(detail);
      setTranscriptDraft(detail.transcript ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể mở session.");
    }
  }, []);

  const onCreateSession = useCallback(async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createScribeSession({
        title: `Session ${new Date().toLocaleString("vi-VN")}`,
        transcript: "",
        auto_generate_soap: false,
      });
      setSelectedSessionId(created.id);
      selectedSessionIdRef.current = created.id;
      setSelectedSession(created);
      setTranscriptDraft(created.transcript ?? "");
      upsertSession(created);
      pushNotice("success", "Đã tạo session mới.");
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo session.");
    } finally {
      setIsCreating(false);
    }
  }, [pushNotice, upsertSession]);

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
      pushNotice("success", "Đã lưu transcript.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu transcript.");
    } finally {
      setIsSaving(false);
    }
  }, [pushNotice, selectedSession, transcriptDraft, upsertSession]);

  const onRegenerateSoap = useCallback(async () => {
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
      upsertSession(updated);
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
      trackScribeGenerated({ action: "regenerate" });
      pushNotice("success", "Đã regenerate SOAP.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể regenerate SOAP.");
    } finally {
      setIsRegenerating(false);
    }
  }, [pushNotice, selectedSession, transcriptDraft, upsertSession]);

  const onFinalize = useCallback(async () => {
    if (!selectedSession) return;
    setIsSaving(true);
    setError("");
    try {
      const updated = await updateScribeSession(selectedSession.id, { status: "finalized" });
      setSelectedSession(updated);
      upsertSession(updated);
      trackScribeGenerated({ action: "finalize" });
      pushNotice("success", "Đã finalize note.");
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể finalize note.");
    } finally {
      setIsSaving(false);
    }
  }, [pushNotice, selectedSession, upsertSession]);

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
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-black tracking-tight text-cyan-300">ScribeOS v2.4</span>
            <nav className="inline-flex items-center gap-1 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
              <button
                type="button"
                onClick={() => setMode("workspace")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "workspace"
                    ? "bg-cyan-500/20 text-cyan-200"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                Live Audio
              </button>
              <button
                type="button"
                onClick={() => setMode("review")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "review" ? "bg-cyan-500/20 text-cyan-200" : "text-[var(--text-secondary)]"
                }`}
              >
                Review
              </button>
            </nav>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isRecording ? (
              <button
                type="button"
                onClick={onStopRecording}
                className="rounded-lg border border-red-300/45 bg-red-500/15 px-3 py-2 text-xs font-bold uppercase tracking-[0.12em] text-red-200"
              >
                Stop Recording
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void onStartRecording()}
                className="rounded-lg border border-cyan-400/40 bg-gradient-to-r from-cyan-400 to-cyan-600 px-3 py-2 text-xs font-bold uppercase tracking-[0.12em] text-slate-950"
              >
                Start Recording
              </button>
            )}

            <button
              type="button"
              onClick={() => void onRegenerateSoap()}
              disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
              className="rounded-lg border border-cyan-400/25 bg-cyan-500/10 px-3 py-2 text-xs font-bold uppercase tracking-[0.12em] text-cyan-200 disabled:opacity-60"
            >
              {isRegenerating || isLiveAnalyzing ? "Analyzing..." : "Regenerate"}
            </button>

            <button
              type="button"
              onClick={() => void onFinalize()}
              disabled={!selectedSession || isSaving}
              className="rounded-lg bg-cyan-400 px-3 py-2 text-xs font-bold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-60"
            >
              Finalize
            </button>
          </div>
        </header>

        <section className="grid grid-cols-12 gap-5">
          <aside className="col-span-12 xl:col-span-3 space-y-3">
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
                className="mt-3 inline-flex min-h-[42px] w-full items-center justify-center rounded-lg border border-cyan-400/35 bg-cyan-400/10 px-3 text-xs font-bold uppercase tracking-widest text-cyan-200 disabled:opacity-60"
              >
                {isCreating ? "Đang tạo..." : "New Consultation"}
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
                        ? "border-cyan-400/45 bg-cyan-500/10"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-cyan-300/35"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className="line-clamp-1 text-sm font-semibold text-[var(--text-primary)]">
                        {item.title || `Session #${item.id}`}
                      </p>
                      <span className="text-[10px] uppercase text-[var(--text-muted)]">{item.status}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-[var(--text-secondary)]">
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

          {mode === "workspace" ? (
            <>
              <article className="col-span-12 2xl:col-span-6 space-y-4">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-300">Acoustic Input Matrix</h3>
                      <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
                        {isRecording ? "Microphone live" : "Recorder idle"} · {formatDuration(elapsedSeconds)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Realtime</p>
                      <p className="text-sm font-semibold text-[var(--text-primary)]">
                        {isTranscribing ? "Transcribing" : "Standby"}
                      </p>
                    </div>
                  </div>

                  <div className="flex h-20 items-end gap-[3px]">
                    {waveBars.map((height, index) => (
                      <div
                        key={`wave-${index}`}
                        className={`w-[3px] rounded-[1px] ${isRecording ? "bg-cyan-300" : "bg-cyan-400/45"}`}
                        style={{ height: `${height}%` }}
                      />
                    ))}
                  </div>

                  <p className="mt-3 text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">
                    {selectedSession?.last_processed_at
                      ? `Last processed ${formatDate(selectedSession.last_processed_at)}`
                      : "Waiting for processing"}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-3">
                    <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">Real-Time Transcript</h3>
                    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-cyan-200">
                      <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-cyan-400 animate-pulse" : "bg-slate-500"}`} />
                      {isRecording ? "Streaming" : "Stopped"}
                    </div>
                  </div>

                  <div className="max-h-[420px] space-y-4 overflow-y-auto p-5 clara-scrollbar">
                    {transcriptPreviewRows.length === 0 ? (
                      <p className="text-sm text-[var(--text-secondary)]">Chưa có transcript realtime.</p>
                    ) : (
                      transcriptPreviewRows.map((row) => (
                        <div key={row.id} className="flex gap-3">
                          <span className="w-16 shrink-0 pt-1 text-[10px] font-semibold text-[var(--text-muted)]">
                            {row.timestamp}
                          </span>
                          <div className="space-y-1">
                            <p className="text-[10px] font-black uppercase tracking-[0.1em] text-cyan-300">{row.speaker}</p>
                            <p className="text-sm leading-6 text-[var(--text-secondary)]">{row.text}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="border-t border-[color:var(--shell-border)] p-4">
                    <textarea
                      value={transcriptDraft}
                      onChange={(event) => setTranscriptDraft(event.target.value)}
                      placeholder="Transcript raw để chỉnh sửa thủ công..."
                      className="min-h-[120px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-cyan-300/45"
                    />
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
                        {(transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0)} tokens captured
                      </p>
                      <button
                        type="button"
                        onClick={() => void onSaveTranscript()}
                        disabled={!selectedSession || isSaving}
                        className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)] disabled:opacity-60"
                      >
                        {isSaving ? "Saving..." : "Save Draft"}
                      </button>
                    </div>
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">SOAP Draft</h3>
                    <button
                      type="button"
                      onClick={() => void onRegenerateSoap()}
                      disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
                      className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-cyan-200 disabled:opacity-60"
                    >
                      {isRegenerating || isLiveAnalyzing ? "Running..." : "Regenerate"}
                    </button>
                  </div>

                  <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1 clara-scrollbar">
                    {[
                      { key: "subjective", title: "Subjective", value: selectedSoap.subjective },
                      { key: "objective", title: "Objective", value: selectedSoap.objective },
                      { key: "assessment", title: "Assessment", value: selectedSoap.assessment },
                      { key: "plan", title: "Plan", value: selectedSoap.plan },
                    ].map((item) => (
                      <article key={item.key} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-cyan-300">{item.title}</p>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
                          {safeText(item.value) || "Chưa có dữ liệu."}
                        </p>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
                  <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">Live Analyze</h3>
                  <div className="mt-3 space-y-2">
                    <p className="text-sm text-[var(--text-secondary)]">
                      {isLiveAnalyzing ? "Đang phân tích realtime..." : "Live analyze sẵn sàng."}
                    </p>
                    <TelemetryPanel role={role}>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        Processing speed: {lastTranscribeMs !== null ? `${lastTranscribeMs.toFixed(1)} ms/chunk` : "--"}
                      </p>
                    </TelemetryPanel>
                  </div>
                  <div className="mt-4 space-y-2">
                    {liveInsights.length === 0 ? (
                      <p className="text-xs text-[var(--text-secondary)]">Chưa có insight.</p>
                    ) : (
                      liveInsights.map((item) => (
                        <article key={item.id} className="rounded-lg border border-cyan-400/20 bg-cyan-500/8 p-3">
                          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-cyan-200">{item.title}</p>
                          <p className="mt-1 text-xs leading-5 text-cyan-100/90">{stripTelemetryLabels(item.detail)}</p>
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
                  <div className="col-span-1 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">AI Confidence</p>
                    <div className="mt-4 flex items-center justify-center">
                      <div className="relative h-28 w-28">
                        <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
                          <circle cx="60" cy="60" r="50" stroke="rgba(56,189,248,0.12)" strokeWidth="8" fill="none" />
                          <circle
                            cx="60"
                            cy="60"
                            r="50"
                            stroke="var(--brand-500)"
                            strokeWidth="8"
                            fill="none"
                            strokeDasharray={314}
                            strokeDashoffset={314 - (314 * confidenceScore) / 100}
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center text-2xl font-black text-cyan-200">
                          {confidenceScore}%
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="col-span-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">Evidence Map: Signal Fidelity</p>
                    <div className="mt-4 flex h-28 items-end gap-1">
                      {waveBars.slice(0, 16).map((value, index) => (
                        <div
                          key={`review-wave-${index}`}
                          className="flex-1 rounded-sm bg-cyan-400/70"
                          style={{ height: `${Math.max(10, Math.round((value / 100) * 100))}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
                  <div className="mb-5 flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-black tracking-tight text-[var(--text-primary)]">Clinical Note Synthesis</h2>
                      <p className="text-sm text-[var(--text-secondary)]">
                        Session ID: {selectedSession ? `#SYN-${selectedSession.id}` : "--"}
                      </p>
                    </div>
                    <span className="rounded-full bg-cyan-500/12 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cyan-200">
                      {selectedSession?.status ?? "draft"}
                    </span>
                  </div>

                  <div className="space-y-5">
                    {[
                      { key: "subjective", title: "Subjective", value: selectedSoap.subjective },
                      { key: "objective", title: "Objective", value: selectedSoap.objective },
                      { key: "assessment", title: "Assessment", value: selectedSoap.assessment },
                      { key: "plan", title: "Plan", value: selectedSoap.plan },
                    ].map((item) => (
                      <section key={item.key}>
                        <h5 className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-300">{item.title}</h5>
                        <div className="mt-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                          <p className="whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
                            {safeText(item.value) || "Chưa có dữ liệu."}
                          </p>
                        </div>
                      </section>
                    ))}
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                  <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">Clinical Coding</h3>
                  <div className="mt-3 space-y-2">
                    {clinicalCodes.map((code) => (
                      <article key={code.code} className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                        <div>
                          <p className="text-xs font-black text-cyan-200">{code.code}</p>
                          <p className="text-[10px] text-[var(--text-secondary)]">{code.label}</p>
                        </div>
                        <span className="material-symbols-outlined text-cyan-200">add_circle</span>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-cyan-400/20 bg-[var(--surface-panel)] p-4">
                  <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-200">AI Council Handoff</h3>
                  <div className="mt-3 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="text-[10px] font-bold uppercase text-cyan-300">Executive Summary</p>
                    <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                      {stripTelemetryLabels(liveInsights[0]?.detail ?? "") || "Chưa có dữ liệu tổng hợp để handoff."}
                    </p>
                    <p className="mt-3 text-[10px] text-[var(--text-muted)]">
                      Transcript tokens: {transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="mt-3 w-full rounded-lg bg-cyan-400/15 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-cyan-200"
                  >
                    Commit to Registry
                  </button>
                </div>

                <TelemetryPanel role={role}>
                  <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-[8px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Processing Speed</p>
                        <p className="text-sm font-bold text-cyan-200">
                          {lastTranscribeMs !== null ? `${(lastTranscribeMs / 1000).toFixed(2)}s` : "--"}
                          <span className="text-[10px] text-[var(--text-secondary)]"> / chunk</span>
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
                        <span className="text-[10px] font-bold uppercase text-emerald-300">{isRecording ? "Live" : "Idle"}</span>
                      </div>
                    </div>
                  </div>
                </TelemetryPanel>
              </aside>
            </>
          )}
        </section>

        <section className="grid grid-cols-2 gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 md:grid-cols-4">
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
            <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Avg Chars</p>
            <p className="mt-2 text-xl font-black text-[var(--text-primary)]">
              {Math.round(analytics?.avg_transcript_chars ?? 0)}
            </p>
          </div>
        </section>
      </section>

      {error ? (
        <p className="mt-4 rounded-lg border border-red-300/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">{error}</p>
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
