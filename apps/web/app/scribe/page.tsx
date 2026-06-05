"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
const panelClass = "rounded-xl border border-[#B6D4FE] bg-white shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const panelPaddedClass = `${panelClass} p-4`;
const panelPaddedLgClass = `${panelClass} p-5`;
const softPanelClass = "rounded-lg border border-[#93C5FD] bg-[#EEF6FF] shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const sectionTitleClass = "text-xs font-black uppercase tracking-[0.18em] text-[#4B5563] dark:text-slate-200";
const accentTitleClass = "text-xs font-black uppercase tracking-[0.18em] text-[#2563EB] dark:text-sky-100";
const bodyTextClass = "text-[#1F2937] dark:text-slate-100";
const secondaryTextClass = "text-[#4B5563] dark:text-slate-300";
const mutedTextClass = "text-[#64748B] dark:text-slate-400";
const primaryButtonClass =
  "rounded-lg border border-[#2563EB] bg-[#2563EB] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-[#1D4ED8] disabled:cursor-not-allowed disabled:border-[#93C5FD] disabled:bg-[#DBEAFE] disabled:text-[#1F2937] disabled:opacity-100 dark:border-sky-400 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400";
const secondaryButtonClass =
  "rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-[#1D4ED8] transition hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:bg-[#DBEAFE] disabled:text-[#1F2937] disabled:opacity-100 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100";
const dangerButtonClass =
  "rounded-lg border border-rose-700 bg-rose-600 px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-rose-700";
const transcriptInputClass =
  "min-h-[120px] w-full rounded-xl border border-[#93C5FD] bg-[#F8FBFF] px-4 py-3 text-sm leading-6 text-[#1F2937] placeholder:text-[#6B7280] outline-none transition focus:border-[#2563EB] focus:bg-white focus:ring-4 focus:ring-blue-100 dark:border-sky-700/70 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder:text-slate-400 dark:focus:border-sky-400";

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

    let speaker = "Âm thanh";
    let text = payload;

    if (doctorMatch.test(payload)) {
      speaker = "Bác sĩ";
      text = payload.replace(doctorMatch, "").trim();
    } else if (patientMatch.test(payload)) {
      speaker = "Người bệnh";
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
    add("K80.20", "Sỏi túi mật");
    add("47562", "Nội soi cắt túi mật");
  }
  if (/hypertension|tăng huyết áp|blood pressure|bp/.test(lowered)) {
    add("I10", "Tăng huyết áp nguyên phát");
  }
  if (/diabetes|đái tháo đường|metformin|insulin/.test(lowered)) {
    add("E11.9", "Đái tháo đường type 2");
  }
  if (/warfarin|bleeding|xuất huyết/.test(lowered)) {
    add("Z79.01", "Dùng thuốc chống đông dài hạn");
  }

  if (rows.length === 0) {
    add("R69", "Bệnh hoặc triệu chứng chưa xác định");
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
      title: "Tín hiệu đánh giá",
      detail: safeText(soap.assessment).slice(0, 220),
    });
  }
  if (safeText(soap.plan)) {
    insights.push({
      id: "plan",
      title: "Kế hoạch nháp",
      detail: safeText(soap.plan).slice(0, 220),
    });
  }
  warnings.slice(0, 2).forEach((warning, index) => {
    insights.push({
      id: `warning-${index}`,
      title: "Cảnh báo an toàn",
      detail: warning,
    });
  });

  if (insights.length === 0 && transcript.trim()) {
    insights.push({
      id: "transcript",
      title: "Đã ghi nhận bản ghi",
      detail: `Đã ghi nhận ${transcript.trim().split(/\s+/).length} từ để phân tích tiếp.`,
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

function scribeStatusLabel(status: string | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "finalized" || normalized === "completed") return "Hoàn tất";
  if (normalized === "ready") return "Sẵn sàng";
  if (normalized === "processing") return "Đang xử lý";
  if (normalized === "error" || normalized === "failed") return "Lỗi";
  return "Bản nháp";
}

const SOAP_SECTION_LABELS = [
  { key: "subjective", title: "Chủ quan", valueKey: "subjective" },
  { key: "objective", title: "Khách quan", valueKey: "objective" },
  { key: "assessment", title: "Đánh giá", valueKey: "assessment" },
  { key: "plan", title: "Kế hoạch", valueKey: "plan" },
] as const;

export default function ScribePage() {
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
      setError(cause instanceof Error ? cause.message : "Không thể tải dữ liệu Scribe.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

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
        setError(cause instanceof Error ? cause.message : "Không thể lưu bản ghi.");
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
        setError(cause instanceof Error ? cause.message : "Phân tích trực tiếp thất bại.");
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
      setError(cause instanceof Error ? cause.message : "Không thể chuyển âm thanh trực tiếp thành chữ.");
      pushNotice("error", "Chuyển âm thanh thành chữ thất bại.");
    } finally {
      processingChunksRef.current = false;
      setIsTranscribing(false);
    }
  }, [pushNotice, scheduleLiveAnalyze, schedulePersistTranscript]);

  const ensureSessionReady = useCallback(async (): Promise<number | null> => {
    if (selectedSessionIdRef.current) return selectedSessionIdRef.current;

    const created = await createScribeSession({
      title: `Phiên ghi âm ${new Date().toLocaleString("vi-VN")}`,
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
        setError("Không thể tạo phiên để ghi âm.");
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
      pushNotice("success", "Đã bắt đầu ghi âm trực tiếp.");
    } catch (cause) {
      teardownAudioPipeline();
      setIsRecording(false);
      setError(cause instanceof Error ? cause.message : "Không thể bắt đầu ghi âm trực tiếp.");
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
      setError(cause instanceof Error ? cause.message : "Không thể mở phiên.");
    }
  }, []);

  const onCreateSession = useCallback(async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createScribeSession({
        title: `Phiên ${new Date().toLocaleString("vi-VN")}`,
        transcript: "",
        auto_generate_soap: false,
      });
      setSelectedSessionId(created.id);
      selectedSessionIdRef.current = created.id;
      setSelectedSession(created);
      setTranscriptDraft(created.transcript ?? "");
      upsertSession(created);
      pushNotice("success", "Đã tạo phiên mới.");
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo phiên.");
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
      pushNotice("success", "Đã lưu bản ghi.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu bản ghi.");
    } finally {
      setIsSaving(false);
    }
  }, [pushNotice, selectedSession, transcriptDraft, upsertSession]);

  const onRegenerateSoap = useCallback(async () => {
    if (!selectedSession) return;
    if (!transcriptDraft.trim()) {
      pushNotice("error", "Bản ghi đang trống.");
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
      pushNotice("success", "Đã tạo lại ghi chú SOAP.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo lại ghi chú SOAP.");
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
      pushNotice("success", "Đã hoàn tất ghi chú.");
      const nextAnalytics = await getScribeAnalyticsSummary();
      setAnalytics(nextAnalytics);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể hoàn tất ghi chú.");
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
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#B6D4FE] bg-white px-4 py-3 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90">
          <div className="flex items-center gap-6">
            <span className="text-lg font-black tracking-tight text-[#2563EB] dark:text-sky-100">ScribeOS v2.4</span>
            <nav className="inline-flex items-center gap-1 rounded-xl border border-[#93C5FD] bg-[#EFF6FF] p-1 dark:border-sky-700/70 dark:bg-slate-800/90">
              <button
                type="button"
                onClick={() => setMode("workspace")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "workspace"
                    ? "bg-[#2563EB] text-white shadow-sm"
                    : "text-[#1F2937] hover:bg-[#DBEAFE] dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                Ghi âm trực tiếp
              </button>
              <button
                type="button"
                onClick={() => setMode("review")}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] ${
                  mode === "review" ? "bg-[#2563EB] text-white shadow-sm" : "text-[#1F2937] hover:bg-[#DBEAFE] dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                Rà soát
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
                Dừng ghi âm
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void onStartRecording()}
                className={primaryButtonClass}
              >
                Bắt đầu ghi âm
              </button>
            )}

            <button
              type="button"
              onClick={() => void onRegenerateSoap()}
              disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
              className={secondaryButtonClass}
            >
              {isRegenerating || isLiveAnalyzing ? "Đang phân tích..." : "Tạo lại ghi chú"}
            </button>

            <button
              type="button"
              onClick={() => void onFinalize()}
              disabled={!selectedSession || isSaving}
              className={primaryButtonClass}
            >
              Hoàn tất
            </button>
          </div>
        </header>

        <section className="grid grid-cols-12 gap-5">
          <aside className="col-span-12 xl:col-span-3 space-y-3">
            <div className={panelPaddedClass}>
              <div className="flex items-center justify-between">
                <h2 className={sectionTitleClass}>Danh sách phiên</h2>
                <span className="rounded-full border border-[#93C5FD] bg-[#EFF6FF] px-2 py-0.5 text-[10px] font-bold text-[#1D4ED8] dark:border-sky-600 dark:bg-sky-500/20 dark:text-sky-100">
                  {sessions.length} bản nháp
                </span>
              </div>
              <button
                type="button"
                onClick={() => void onCreateSession()}
                disabled={isCreating}
                className={`mt-3 inline-flex min-h-[42px] w-full items-center justify-center ${secondaryButtonClass}`}
              >
                {isCreating ? "Đang tạo..." : "Tạo phiên khám mới"}
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
                        ? "border-[#2563EB] bg-[#DBEAFE] shadow-sm dark:border-sky-400 dark:bg-sky-500/20"
                        : "border-[#B6D4FE] bg-white hover:border-[#2563EB] hover:bg-[#F8FBFF] dark:border-sky-800 dark:bg-slate-900/90 dark:hover:border-sky-500"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className={`line-clamp-1 text-sm font-bold ${bodyTextClass}`}>
                        {item.title || `Phiên #${item.id}`}
                      </p>
                      <span className={`text-[10px] font-bold uppercase ${mutedTextClass}`}>{scribeStatusLabel(item.status)}</span>
                    </div>
                    <p className={`mt-1 line-clamp-2 text-xs ${secondaryTextClass}`}>
                      {item.transcript?.trim() || "Chưa có bản ghi."}
                    </p>
                    <p className={`mt-2 text-[10px] font-semibold ${mutedTextClass}`}>{formatDate(item.updated_at)}</p>
                  </button>
                );
              })}

              {!isLoading && sessions.length === 0 ? (
                <p className={`rounded-xl border border-[#B6D4FE] bg-white p-4 text-sm font-medium ${secondaryTextClass}`}>
                  Chưa có phiên nào.
                </p>
              ) : null}
            </div>
          </aside>

          {mode === "workspace" ? (
            <>
              <article className="col-span-12 2xl:col-span-6 space-y-4">
                <div className={panelPaddedLgClass}>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h3 className={accentTitleClass}>Tín hiệu âm thanh</h3>
                      <p className={`mt-1 text-[11px] font-medium ${secondaryTextClass}`}>
                        {isRecording ? "Micro đang ghi" : "Bộ ghi đang chờ"} · {formatDuration(elapsedSeconds)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-[10px] font-bold uppercase tracking-[0.15em] ${mutedTextClass}`}>Thời gian thực</p>
                      <p className={`text-sm font-bold ${bodyTextClass}`}>
                        {isTranscribing ? "Đang chuyển thành chữ" : "Chờ xử lý"}
                      </p>
                    </div>
                  </div>

                  <div className="flex h-20 items-end gap-[3px]">
                    {waveBars.map((height, index) => (
                      <div
                        key={`wave-${index}`}
                        className={`w-[3px] rounded-[1px] ${isRecording ? "bg-[#2563EB]" : "bg-[#93C5FD]"}`}
                        style={{ height: `${height}%` }}
                      />
                    ))}
                  </div>

                  <p className={`mt-3 text-[10px] font-bold uppercase tracking-[0.18em] ${mutedTextClass}`}>
                    {selectedSession?.last_processed_at
                      ? `Xử lý lần cuối ${formatDate(selectedSession.last_processed_at)}`
                      : "Chờ xử lý"}
                  </p>
                </div>

                <div className={panelClass}>
                  <div className="flex items-center justify-between border-b border-[#B6D4FE] px-5 py-3 dark:border-sky-800">
                    <h3 className={sectionTitleClass}>Bản ghi thời gian thực</h3>
                    <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-[#1D4ED8] dark:text-sky-100">
                      <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-[#2563EB] animate-pulse" : "bg-slate-500"}`} />
                      {isRecording ? "Đang ghi" : "Đã dừng"}
                    </div>
                  </div>

                  <div className="max-h-[420px] space-y-4 overflow-y-auto p-5 clara-scrollbar">
                    {transcriptPreviewRows.length === 0 ? (
                      <p className={`text-sm font-medium ${secondaryTextClass}`}>Chưa có bản ghi thời gian thực.</p>
                    ) : (
                      transcriptPreviewRows.map((row) => (
                        <div key={row.id} className="flex gap-3">
                          <span className={`w-16 shrink-0 pt-1 text-[10px] font-bold ${mutedTextClass}`}>
                            {row.timestamp}
                          </span>
                          <div className="space-y-1">
                            <p className="text-[10px] font-black uppercase tracking-[0.1em] text-[#2563EB] dark:text-sky-100">{row.speaker}</p>
                            <p className={`text-sm leading-6 ${secondaryTextClass}`}>{row.text}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="border-t border-[#B6D4FE] p-4 dark:border-sky-800">
                    <textarea
                      value={transcriptDraft}
                      onChange={(event) => setTranscriptDraft(event.target.value)}
                      placeholder="Nhập hoặc chỉnh sửa nội dung đã ghi..."
                      className={transcriptInputClass}
                    />
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <p className={`text-[10px] font-bold uppercase tracking-[0.12em] ${mutedTextClass}`}>
                        {(transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0)} từ đã ghi nhận
                      </p>
                      <button
                        type="button"
                        onClick={() => void onSaveTranscript()}
                        disabled={!selectedSession || isSaving}
                        className={secondaryButtonClass}
                      >
                        {isSaving ? "Đang lưu..." : "Lưu bản nháp"}
                      </button>
                    </div>
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className={panelPaddedLgClass}>
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className={sectionTitleClass}>Bản nháp SOAP</h3>
                    <button
                      type="button"
                      onClick={() => void onRegenerateSoap()}
                      disabled={!selectedSession || isRegenerating || isLiveAnalyzing}
                      className={secondaryButtonClass}
                    >
                      {isRegenerating || isLiveAnalyzing ? "Đang chạy..." : "Tạo lại"}
                    </button>
                  </div>

                  <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1 clara-scrollbar">
                    {SOAP_SECTION_LABELS.map((item) => (
                      <article key={item.key} className={`${softPanelClass} p-3`}>
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-[#2563EB] dark:text-sky-100">{item.title}</p>
                        <p className={`mt-2 whitespace-pre-wrap text-sm leading-6 ${secondaryTextClass}`}>
                          {safeText(selectedSoap[item.valueKey]) || "Chưa có dữ liệu."}
                        </p>
                      </article>
                    ))}
                  </div>
                </div>

                <div className={panelPaddedLgClass}>
                  <h3 className={sectionTitleClass}>Phân tích trực tiếp</h3>
                  <div className="mt-3 space-y-2">
                    <p className={`text-sm font-medium ${secondaryTextClass}`}>
                      {isLiveAnalyzing ? "Đang phân tích trực tiếp..." : "Sẵn sàng phân tích trực tiếp."}
                    </p>
                    <p className={`text-[11px] font-medium ${mutedTextClass}`}>
                      Tốc độ xử lý: {lastTranscribeMs !== null ? `${lastTranscribeMs.toFixed(1)} ms/đoạn` : "--"}
                    </p>
                  </div>
                  <div className="mt-4 space-y-2">
                    {liveInsights.length === 0 ? (
                      <p className={`text-xs font-medium ${secondaryTextClass}`}>Chưa có gợi ý.</p>
                    ) : (
                      liveInsights.map((item) => (
                        <article key={item.id} className={`${softPanelClass} p-3`}>
                          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-[#2563EB] dark:text-sky-100">{item.title}</p>
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
                    <p className={sectionTitleClass}>Độ tin cậy AI</p>
                    <div className="mt-4 flex items-center justify-center">
                      <div className="relative h-28 w-28">
                        <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
                          <circle cx="60" cy="60" r="50" stroke="rgba(96, 165, 250,0.12)" strokeWidth="8" fill="none" />
                          <circle
                            cx="60"
                            cy="60"
                            r="50"
                            stroke="#60a5fa"
                            strokeWidth="8"
                            fill="none"
                            strokeDasharray={314}
                            strokeDashoffset={314 - (314 * confidenceScore) / 100}
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center text-2xl font-black text-[#1D4ED8] dark:text-sky-100">
                          {confidenceScore}%
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className={`col-span-2 ${panelPaddedClass}`}>
                    <p className={sectionTitleClass}>Độ ổn định tín hiệu</p>
                    <div className="mt-4 flex h-28 items-end gap-1">
                      {waveBars.slice(0, 16).map((value, index) => (
                        <div
                          key={`review-wave-${index}`}
                          className="flex-1 rounded-sm bg-[#2563EB]"
                          style={{ height: `${Math.max(10, Math.round((value / 100) * 100))}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-[#93C5FD] bg-[#EEF6FF] p-6 shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90">
                  <div className="mb-5 flex items-center justify-between">
                    <div>
                      <h2 className={`text-2xl font-black tracking-tight ${bodyTextClass}`}>Tổng hợp ghi chú lâm sàng</h2>
                      <p className={`text-sm font-medium ${secondaryTextClass}`}>
                        Mã phiên: {selectedSession ? `#PHIEN-${selectedSession.id}` : "--"}
                      </p>
                    </div>
                    <span className="rounded-full border border-[#93C5FD] bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-[#1D4ED8] dark:border-sky-600 dark:bg-slate-900 dark:text-sky-100">
                      {scribeStatusLabel(selectedSession?.status)}
                    </span>
                  </div>

                  <div className="space-y-5">
                    {SOAP_SECTION_LABELS.map((item) => (
                      <section key={item.key}>
                        <h5 className="text-[10px] font-black uppercase tracking-[0.2em] text-[#2563EB] dark:text-sky-100">{item.title}</h5>
                        <div className="mt-2 rounded-lg border border-[#B6D4FE] bg-white p-4 dark:border-sky-800 dark:bg-slate-900/90">
                          <p className={`whitespace-pre-wrap text-sm leading-6 ${secondaryTextClass}`}>
                            {safeText(selectedSoap[item.valueKey]) || "Chưa có dữ liệu."}
                          </p>
                        </div>
                      </section>
                    ))}
                  </div>
                </div>
              </article>

              <aside className="col-span-12 2xl:col-span-3 space-y-4">
                <div className={panelPaddedClass}>
                  <h3 className={sectionTitleClass}>Mã hóa lâm sàng</h3>
                  <div className="mt-3 space-y-2">
                    {clinicalCodes.map((code) => (
                      <article key={code.code} className={`flex items-center justify-between ${softPanelClass} p-3`}>
                        <div>
                          <p className="text-xs font-black text-[#1D4ED8] dark:text-sky-100">{code.code}</p>
                          <p className={`text-[10px] font-medium ${secondaryTextClass}`}>{code.label}</p>
                        </div>
                        <span className="material-symbols-outlined text-[#2563EB] dark:text-sky-100">add_circle</span>
                      </article>
                    ))}
                  </div>
                </div>

                <div className={panelPaddedClass}>
                  <h3 className={accentTitleClass}>Chuyển hội chẩn AI</h3>
                  <div className={`mt-3 ${softPanelClass} p-3`}>
                    <p className="text-[10px] font-black uppercase text-[#2563EB] dark:text-sky-100">Tóm tắt chính</p>
                    <p className={`mt-2 text-xs leading-5 ${secondaryTextClass}`}>
                      {liveInsights[0]?.detail || "Chưa có dữ liệu tổng hợp để chuyển hội chẩn."}
                    </p>
                    <p className={`mt-3 text-[10px] font-medium ${mutedTextClass}`}>
                      Số từ bản ghi: {transcriptDraft.trim().split(/\s+/).filter(Boolean).length || 0}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={`mt-3 w-full ${secondaryButtonClass}`}
                  >
                    Lưu vào hồ sơ
                  </button>
                </div>

                <div className={panelPaddedClass}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-[8px] font-bold uppercase tracking-[0.15em] ${mutedTextClass}`}>Tốc độ xử lý</p>
                      <p className="text-sm font-black text-[#1D4ED8] dark:text-sky-100">
                        {lastTranscribeMs !== null ? `${(lastTranscribeMs / 1000).toFixed(2)}s` : "--"}
                        <span className={`text-[10px] ${secondaryTextClass}`}> / đoạn</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
                      <span className="text-[10px] font-black uppercase text-emerald-700 dark:text-emerald-300">{isRecording ? "Đang ghi" : "Chờ"}</span>
                    </div>
                  </div>
                </div>
              </aside>
            </>
          )}
        </section>

        <section className={`grid grid-cols-2 gap-3 md:grid-cols-4 ${panelPaddedClass}`}>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>Tổng số phiên</p>
            <p className={`mt-2 text-xl font-black ${bodyTextClass}`}>{analytics?.total_sessions ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>Đã hoàn tất</p>
            <p className="mt-2 text-xl font-black text-[#1D4ED8] dark:text-sky-100">{analytics?.completed_sessions ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>Hôm nay</p>
            <p className={`mt-2 text-xl font-black ${bodyTextClass}`}>{analytics?.sessions_today ?? 0}</p>
          </div>
          <div className={`${softPanelClass} p-3`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest ${mutedTextClass}`}>Ký tự trung bình</p>
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
