"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page/page-header";
import { WorkflowLayout, type WorkflowStep } from "@/components/page/workflow-layout";
import { SurfaceCard } from "@/components/ui/surface";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ListRow } from "@/components/ui/list-row";
import { InlineError } from "@/components/shared/inline-error";
import { EmptyState } from "@/components/shared/empty-state";
import Modal from "@/components/ui/modal";
import EnterpriseReview from "@/components/scribe/enterprise-review";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { getRole, type UserRole } from "@/lib/auth-store";
import { trackScribeGenerated, trackScribeViewed } from "@/lib/analytics/events";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import type { UILanguage } from "@/lib/ui-language";
import {
  ScribeAnalyticsSummary,
  ScribeSession,
  captureScribeConsent,
  createScribeSession,
  deleteScribeRecordingData,
  getScribeAnalyticsSummary,
  getScribeRecordingDataCapability,
  getScribeSession,
  listScribeSessions,
  normalizeSoapSections,
  regenerateScribeSession,
  transcribeScribeAudio,
  updateScribeSession,
} from "@/lib/scribe";

type NoticeTone = "success" | "error";
type WorkspaceMode = "workspace" | "review" | "enterprise";

export type ScribeWorkflowStepId =
  | "consent"
  | "recording"
  | "transcript"
  | "soap"
  | "finalize";

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

const DEFAULT_WAVE_BARS = Array.from({ length: 32 }, () => 8);

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
  if (normalized === "recording") return copy("scribe.status.recording");
  if (normalized === "ready" || normalized === "transcript_ready") return copy("scribe.status.transcriptReady");
  if (normalized === "signed") return copy("scribe.status.signed");
  if (normalized === "exported") return copy("scribe.status.exported");
  if (normalized === "amended") return copy("scribe.status.amended");
  if (normalized === "in_review" || normalized === "reviewed" || normalized === "finalized" || normalized === "completed") {
    return copy("scribe.status.reviewed");
  }
  if (normalized === "processing") return copy("scribe.status.processing");
  if (normalized === "error" || normalized === "failed") return copy("scribe.status.error");
  return copy("scribe.status.draft");
}

export default function ScribePage() {
  const language = useUILanguage();
  const isVi = language !== "en";
  const copy = useCallback(
    (key: UITranslationKey, values: Record<string, string | number> = {}) => t(language, key, values),
    [language],
  );

  const soapSectionLabels = useMemo(() => [
    { key: "subjective", title: copy("scribe.soap.subjective"), valueKey: "subjective" as const },
    { key: "objective", title: copy("scribe.soap.objective"), valueKey: "objective" as const },
    { key: "assessment", title: copy("scribe.soap.assessment"), valueKey: "assessment" as const },
    { key: "plan", title: copy("scribe.soap.plan"), valueKey: "plan" as const },
  ], [copy]);

  const [mode, setMode] = useState<WorkspaceMode>("workspace");
  const [sessions, setSessions] = useState<ScribeSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [selectedSession, setSelectedSession] = useState<ScribeSession | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [analytics, setAnalytics] = useState<ScribeAnalyticsSummary | null>(null);

  // Workflow State Machine: 0: Consent, 1: Recording, 2: Transcript, 3: SOAP Draft, 4: Finalize
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isLiveAnalyzing, setIsLiveAnalyzing] = useState(false);
  const [isDeletingRecordingData, setIsDeletingRecordingData] = useState(false);
  const [showRecordingDataDeleteConfirmation, setShowRecordingDataDeleteConfirmation] = useState(false);
  const [recordingConsentCaptured, setRecordingConsentCaptured] = useState(false);
  const [showEnterpriseModal, setShowEnterpriseModal] = useState(false);
  const [showTelemetryModal, setShowTelemetryModal] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastTranscribeMs, setLastTranscribeMs] = useState<number | null>(null);
  const [waveBars, setWaveBars] = useState<number[]>(DEFAULT_WAVE_BARS);
  const [notice, setNotice] = useState<{ tone: NoticeTone; message: string } | null>(null);
  const [error, setError] = useState("");
  const [role, setRole] = useState<UserRole>("normal");

  const selectedSessionIdRef = useRef<number | null>(null);
  const transcriptDraftRef = useRef("");
  const persistTimerRef = useRef<number | null>(null);
  const pendingTranscriptSavesRef = useRef<Set<Promise<void>>>(new Set());
  const liveAnalyzeTimerRef = useRef<number | null>(null);
  const recordingTickTimerRef = useRef<number | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
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
  const liveInsights = useMemo(
    () => buildLiveInsights(selectedSession, transcriptDraft, copy),
    [copy, selectedSession, transcriptDraft]
  );
  const [recordingDataDeletionAvailable, setRecordingDataDeletionAvailable] = useState(false);
  const canDeleteSelectedRecordingData = selectedSession !== null && recordingDataDeletionAvailable;

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

  const refreshRecordingDataDeletionCapability = useCallback(async (sessionId: number) => {
    try {
      const capability = await getScribeRecordingDataCapability(sessionId);
      if (selectedSessionIdRef.current === sessionId) {
        setRecordingDataDeletionAvailable(capability.recording_data_deletion_available);
      }
    } catch {
      if (selectedSessionIdRef.current === sessionId) setRecordingDataDeletionAvailable(false);
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
        transcriptDraftRef.current = detail.transcript ?? "";
        const detailSoap = normalizeSoapSections(asRecord(detail.soap) ?? {});
        const isConsentDone = Boolean(asRecord(detail.metadata)?.consent_captured || detail.status === "recording" || detail.status === "ready" || detail.status === "signed");
        setRecordingConsentCaptured(isConsentDone);
        await refreshRecordingDataDeletionCapability(detail.id);

        // Auto-compute appropriate step
        if (detail.status === "signed" || detail.status === "completed") {
          setCurrentStepIndex(4);
        } else if (safeText(detailSoap.assessment) || safeText(detailSoap.subjective)) {
          setCurrentStepIndex(3);
        } else if (safeText(detail.transcript)) {
          setCurrentStepIndex(2);
        } else if (isConsentDone) {
          setCurrentStepIndex(1);
        } else {
          setCurrentStepIndex(0);
        }
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("scribe.error.load")));
    } finally {
      setIsLoading(false);
    }
  }, [copy, refreshRecordingDataDeletionCapability]);

  useEffect(() => {
    setRole(getRole());
    trackScribeViewed();
    void refreshData();
  }, [refreshData]);

  useEffect(() => {
    transcriptDraftRef.current = transcriptDraft;
  }, [transcriptDraft]);

  const schedulePersistTranscript = useCallback(
    (nextTranscript: string, immediate = false) => {
      const sessionId = selectedSessionIdRef.current;
      if (!sessionId) return;

      clearPersistTimer();
      const execute = async () => {
        setIsSaving(true);
        try {
          const updated = await updateScribeSession(sessionId, { transcript: nextTranscript });
          if (selectedSessionIdRef.current === sessionId) {
            setSelectedSession(updated);
            upsertSession(updated);
          }
        } catch (cause) {
          setError(safeUserFacingError(cause, copy("scribe.error.saveTranscript")));
        } finally {
          setIsSaving(false);
        }
      };

      if (immediate) {
        const p = execute();
        pendingTranscriptSavesRef.current.add(p);
        p.finally(() => pendingTranscriptSavesRef.current.delete(p));
        return;
      }

      persistTimerRef.current = window.setTimeout(() => {
        const p = execute();
        pendingTranscriptSavesRef.current.add(p);
        p.finally(() => pendingTranscriptSavesRef.current.delete(p));
      }, 700);
    },
    [clearPersistTimer, copy, upsertSession]
  );

  const runLiveAnalyze = useCallback(
    async (transcriptText: string) => {
      const sessionId = selectedSessionIdRef.current;
      if (!sessionId || !transcriptText.trim()) return;
      if (analyzingInFlightRef.current) return;

      analyzingInFlightRef.current = true;
      setIsLiveAnalyzing(true);
      try {
        const updated = await updateScribeSession(sessionId, {
          transcript: transcriptText,
        });
        if (selectedSessionIdRef.current === sessionId) {
          setSelectedSession(updated);
          upsertSession(updated);
        }
      } catch {
        // Live auto-generate is best-effort
      } finally {
        analyzingInFlightRef.current = false;
        setIsLiveAnalyzing(false);
      }
    },
    [upsertSession]
  );

  const scheduleLiveAnalyze = useCallback(
    (transcriptText: string) => {
      clearLiveAnalyzeTimer();
      liveAnalyzeTimerRef.current = window.setTimeout(() => {
        void runLiveAnalyze(transcriptText);
      }, 1600);
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
      setError(safeUserFacingError(cause, copy("scribe.error.transcribe")));
      pushNotice("error", copy("scribe.error.transcribeNotice"));
    } finally {
      processingChunksRef.current = false;
      setIsTranscribing(false);
    }
  }, [copy, language, pushNotice, scheduleLiveAnalyze, schedulePersistTranscript]);

  const ensureSessionReady = useCallback(async (): Promise<number | null> => {
    if (selectedSessionIdRef.current) return selectedSessionIdRef.current;

    const created = await createScribeSession({
      title: copy("scribe.sessionTitle.recording", {
        date: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }),
      }),
      transcript: "",
      auto_generate_soap: false,
    });
    setSelectedSessionId(created.id);
    selectedSessionIdRef.current = created.id;
    setSelectedSession(created);
    upsertSession(created);
    await refreshRecordingDataDeletionCapability(created.id);
    return created.id;
  }, [copy, language, refreshRecordingDataDeletionCapability, upsertSession]);

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

  const onCaptureRecordingConsent = useCallback(async () => {
    setError("");
    try {
      const sessionId = await ensureSessionReady();
      if (!sessionId) {
        setError(copy("scribe.error.createSession"));
        return;
      }
      await captureScribeConsent(sessionId, { method: "verbal", scope: "encounter" });
      setRecordingConsentCaptured(true);
      pushNotice("success", copy("scribe.notice.consentCaptured"));
      setCurrentStepIndex(1); // Advance to recording stage
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("scribe.error.consent")));
    }
  }, [copy, ensureSessionReady, pushNotice]);

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

      if (!recordingConsentCaptured) {
        setError(copy("scribe.error.consentRequired"));
        setCurrentStepIndex(0);
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
        recorder.start();
        mediaRecorderRef.current = recorder;
      };

      startRecorderSegment();
      recorderCycleTimerRef.current = window.setInterval(() => {
        const current = mediaRecorderRef.current;
        if (current && current.state === "recording") {
          current.stop();
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
      setCurrentStepIndex(1);
      pushNotice("success", copy("scribe.notice.started"));
    } catch (cause) {
      teardownAudioPipeline();
      setIsRecording(false);
      setError(safeUserFacingError(cause, copy("scribe.error.startRecording")));
    }
  }, [copy, ensureSessionReady, processChunkQueue, pushNotice, recordingConsentCaptured, startWaveformLoop, teardownAudioPipeline]);

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
    setCurrentStepIndex(2); // Advance to transcript review
  }, [clearLiveAnalyzeTimer, clearPersistTimer, copy, pushNotice, scheduleLiveAnalyze, schedulePersistTranscript, teardownAudioPipeline]);

  const onSelectSession = useCallback(async (sessionId: number) => {
    setError("");
    try {
      const detail = await getScribeSession(sessionId);
      setSelectedSessionId(detail.id);
      selectedSessionIdRef.current = detail.id;
      setSelectedSession(detail);
      setTranscriptDraft(detail.transcript ?? "");
      transcriptDraftRef.current = detail.transcript ?? "";
      const detailSoap = normalizeSoapSections(asRecord(detail.soap) ?? {});
      const isConsentDone = Boolean(asRecord(detail.metadata)?.consent_captured || detail.status === "recording" || detail.status === "ready" || detail.status === "signed");
      setRecordingConsentCaptured(isConsentDone);
      await refreshRecordingDataDeletionCapability(detail.id);

      if (detail.status === "signed" || detail.status === "completed") {
        setCurrentStepIndex(4);
      } else if (safeText(detailSoap.assessment) || safeText(detailSoap.subjective)) {
        setCurrentStepIndex(3);
      } else if (safeText(detail.transcript)) {
        setCurrentStepIndex(2);
      } else if (isConsentDone) {
        setCurrentStepIndex(1);
      } else {
        setCurrentStepIndex(0);
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("scribe.error.openSession")));
    }
  }, [copy, refreshRecordingDataDeletionCapability]);

  const onCreateSession = useCallback(async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createScribeSession({
        title: copy("scribe.sessionTitle.recording", {
          date: formatLocaleDate(language, new Date(), { dateStyle: "short", timeStyle: "short" }),
        }),
        transcript: "",
        auto_generate_soap: false,
      });
      setSelectedSessionId(created.id);
      selectedSessionIdRef.current = created.id;
      setSelectedSession(created);
      setTranscriptDraft("");
      transcriptDraftRef.current = "";
      setRecordingConsentCaptured(false);
      upsertSession(created);
      setCurrentStepIndex(0); // Start at consent gate
      pushNotice("success", copy("scribe.notice.created"));
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("scribe.error.createSession")));
    } finally {
      setIsCreating(false);
    }
  }, [copy, language, pushNotice, upsertSession]);

  const onRegenerateSoap = useCallback(async () => {
    const sessionId = selectedSessionIdRef.current;
    if (!sessionId) return;

    setIsRegenerating(true);
    setError("");
    try {
      const updated = await regenerateScribeSession(sessionId, {});
      trackScribeGenerated({ action: "regenerate" });
      setSelectedSession(updated);
      upsertSession(updated);
      pushNotice("success", copy("scribe.notice.regenerated"));
      setCurrentStepIndex(3);
    } catch (cause) {
      setError(safeUserFacingError(cause, copy("scribe.error.regenerate")));
    } finally {
      setIsRegenerating(false);
    }
  }, [copy, pushNotice, upsertSession]);

  const onFinalizeEncounter = useCallback(async () => {
    const sessionId = selectedSessionIdRef.current;
    if (!sessionId) return;

    setIsSaving(true);
    setError("");
    try {
      const updated = await updateScribeSession(sessionId, {
        status: "signed",
      });
      trackScribeGenerated({ action: "finalize" });
      setSelectedSession(updated);
      upsertSession(updated);
      pushNotice("success", isVi ? "Đã ký và hoàn tất bệnh án!" : "Note signed and finalized!");
      setCurrentStepIndex(4);
    } catch (cause) {
      setError(safeUserFacingError(cause, isVi ? "Không thể ký bệnh án" : "Failed to sign note"));
    } finally {
      setIsSaving(false);
    }
  }, [isVi, pushNotice, upsertSession]);

  const onDeleteRecordingData = useCallback(async () => {
    const sessionId = selectedSessionIdRef.current;
    if (!sessionId) return;

    setIsDeletingRecordingData(true);
    try {
      await deleteScribeRecordingData(sessionId);
      setShowRecordingDataDeleteConfirmation(false);
      pushNotice("success", isVi ? "Đã xóa bản ghi âm an toàn." : "Recording data deleted safely.");
      await refreshData();
    } catch (cause) {
      setError(safeUserFacingError(cause, isVi ? "Không thể xóa bản ghi âm" : "Failed to delete audio"));
    } finally {
      setIsDeletingRecordingData(false);
    }
  }, [isVi, pushNotice, refreshData]);

  // Step Definitions for WorkflowLayout (Spec v8 §7.4)
  const workflowSteps: WorkflowStep[] = useMemo(
    () => [
      {
        id: "consent",
        label: isVi ? "01 Đồng thuận" : "01 Consent",
        description: isVi ? "Đồng thuận bệnh nhân" : "Patient consent",
        completed:
          recordingConsentCaptured ||
          Boolean(
            asRecord(selectedSession?.metadata)?.consent_captured ||
              selectedSession?.status === "recording" ||
              selectedSession?.status === "ready" ||
              selectedSession?.status === "signed"
          ),
      },
      {
        id: "recording",
        label: isVi ? "02 Ghi âm" : "02 Record",
        description: isVi ? "Thu âm phiên khám" : "Encounter audio",
        completed: transcriptDraft.trim().length > 0,
      },
      {
        id: "transcript",
        label: isVi ? "03 Lời thoại" : "03 Transcript",
        description: isVi ? "Biên tập hội thoại" : "Dialogue review",
        completed: Boolean(safeText(selectedSoap.subjective) || safeText(selectedSoap.assessment)),
      },
      {
        id: "soap",
        label: isVi ? "04 Dự thảo SOAP" : "04 SOAP Draft",
        description: isVi ? "Hồ sơ SOAP y khoa" : "Clinical SOAP note",
        completed: selectedSession?.status === "signed" || selectedSession?.status === "completed",
      },
      {
        id: "finalize",
        label: isVi ? "05 Ký & Ban hành" : "05 Finalize & Sign",
        description: isVi ? "Ký số & Lưu trữ" : "Sign & Publish",
        completed: selectedSession?.status === "signed",
      },
    ],
    [isVi, recordingConsentCaptured, selectedSession, selectedSoap, transcriptDraft]
  );

  return (
    <WorkflowLayout
      workspace="clinical"
      steps={workflowSteps}
      currentStep={currentStepIndex}
      onStepClick={(idx) => setCurrentStepIndex(idx)}
      title={isVi ? "CLARA Scribe — Trợ lý Biên tập Bệnh án SOAP" : "CLARA Scribe — Clinical SOAP Assistant"}
      subtitle={
        isVi
          ? "Ghi âm hội thoại khám lâm sàng, nhận dạng giọng nói tiếng Việt và tổng hợp bệnh án SOAP chuẩn FIDES."
          : "Voice-driven clinical dialogue transcription and SOAP note synthesis with FIDES safety verification."
      }
      badges={
        selectedSession ? (
          <div className="flex items-center gap-2">
            <Badge tone="brand">{selectedSession.title}</Badge>
            <Badge tone="ok">{scribeStatusLabel(selectedSession.status, copy)}</Badge>
          </div>
        ) : undefined
      }
      headerActions={
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setShowEnterpriseModal(true)}
          >
            <Icon name="scan" size="1rem" />
            <span>{isVi ? "Enterprise Review" : "Enterprise Review"}</span>
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setShowTelemetryModal(true)}
          >
            <Icon name="settings" size="1rem" />
            <span>{isVi ? "Telemetry" : "Telemetry"}</span>
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={onCreateSession}
            disabled={isCreating}
          >
            <Icon name="plus" size="1rem" />
            <span>{isVi ? "Phiên khám mới" : "New Encounter"}</span>
          </Button>
        </div>
      }
      maxWidth="workbench"
    >
      {/* Toast Notifications */}
      {notice && (
        <div
          role="status"
          className={`fixed bottom-6 right-6 z-50 rounded-xl px-4 py-2.5 text-xs font-bold text-white shadow-xl ${
            notice.tone === "success" ? "bg-emerald-600" : "bg-rose-600"
          }`}
        >
          {notice.message}
        </div>
      )}

      {error && (
        <InlineError message={error} onDismiss={() => setError("")} className="mb-6" />
      )}

      {/* State Machine Main Stages */}
      <div className="space-y-6">
        {/* =========================================================================
            STATE 1: IDLE / SESSION SELECTION
            ========================================================================= */}
        {currentStepIndex === 0 &&
        !recordingConsentCaptured &&
        !Boolean(
          asRecord(selectedSession?.metadata)?.consent_captured ||
            selectedSession?.status === "recording" ||
            selectedSession?.status === "ready" ||
            selectedSession?.status === "signed"
        ) ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start" id="scribe-step-panel-0" role="tabpanel" aria-labelledby="scribe-step-tab-0">
            {/* Left: Concentrated Consent Gate */}
            <div className="lg:col-span-8 space-y-6">
              <SurfaceCard className="p-8 text-center space-y-6 relative overflow-hidden" data-testid="scribe-consent-gate">
                <div className="w-16 h-16 rounded-2xl bg-amber-500/10 text-amber-600 flex items-center justify-center mx-auto border border-amber-500/20">
                  <Icon name="warning" size="2rem" />
                </div>
                <div className="max-w-md mx-auto space-y-2">
                  <h3 className="text-xl font-bold text-[var(--text-primary)]">
                    {isVi ? "Đồng thuận Thu âm Phiên khám" : "Patient Encounter Consent"}
                  </h3>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                    {isVi
                      ? "Để bảo vệ quyền riêng tư và tuân thủ tiêu chuẩn y tế, bác sĩ cần thông báo và nhận được sự đồng thuận bằng lời nói hoặc văn bản từ người bệnh trước khi bắt đầu ghi âm."
                      : "To protect patient privacy and comply with clinical standards, ensure verbal or written consent is obtained prior to dialogue capture."}
                  </p>
                </div>

                <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    onClick={onCaptureRecordingConsent}
                    data-testid="scribe-capture-consent"
                    className="w-full sm:w-auto px-8"
                  >
                    <Icon name="check" size="1.2rem" />
                    <span>{isVi ? "Xác nhận Đã có Đồng thuận" : "Confirm Patient Consent"}</span>
                  </Button>
                </div>
              </SurfaceCard>
            </div>

            {/* Right: Recent Encounter Sessions list */}
            <div className="lg:col-span-4 space-y-4">
              <SurfaceCard className="p-5 space-y-3">
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2.5">
                  <h4 className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)]">
                    {isVi ? "Phiên khám gần đây" : "Recent Sessions"}
                  </h4>
                  <Badge tone="neutral">{sessions.length}</Badge>
                </div>
                <div className="space-y-1.5 max-h-[380px] overflow-y-auto clara-scrollbar">
                  {sessions.map((s) => (
                    <ListRow
                      key={s.id}
                      density="compact"
                      selected={s.id === selectedSessionId}
                      onClick={() => void onSelectSession(s.id)}
                      title={s.title || `Phiên #${s.id}`}
                      subtitle={formatDate(language, s.updated_at)}
                      badges={<Badge tone={s.status === "signed" ? "ok" : "brand"}>{scribeStatusLabel(s.status, copy)}</Badge>}
                    />
                  ))}
                </div>
              </SurfaceCard>

              {/* Analytics Snapshot */}
              {analytics && (
                <SurfaceCard className="p-4 space-y-2 text-xs text-[var(--text-secondary)]">
                  <div className="flex justify-between">
                    <span>{isVi ? "Tổng số phiên:" : "Total Sessions:"}</span>
                    <strong className="text-[var(--text-primary)]">{analytics.total_sessions}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>{isVi ? "Đã hoàn tất:" : "Completed Sessions:"}</span>
                    <strong className="text-[var(--text-primary)]">{analytics.completed_sessions}</strong>
                  </div>
                </SurfaceCard>
              )}
            </div>
          </div>
        ) : null}

        {/* =========================================================================
            STATE 2: RECORDING STAGE (IMMERSIVE WAVEFORM)
            ========================================================================= */}
        {currentStepIndex === 1 || isRecording ? (
          <div className="space-y-6" id="scribe-step-panel-1" role="tabpanel" aria-labelledby="scribe-step-tab-1">
            <SurfaceCard className="p-8 sm:p-12 text-center space-y-8 relative overflow-hidden bg-gradient-to-b from-[var(--surface-panel)] to-[var(--surface-muted)]" data-testid="scribe-process-panel">
              {/* Status Header */}
              <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-600 font-bold text-xs animate-pulse">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-600" />
                <span>{isRecording ? (isVi ? "ĐANG THU ÂM TRỰC TIẾP" : "LIVE CAPTURE RECORDING") : (isVi ? "SẴN SÀNG GHI ÂM" : "READY TO RECORD")}</span>
              </div>

              {/* Large Digital Timer */}
              <div className="space-y-1">
                <div className="font-mono text-5xl sm:text-7xl font-extrabold tracking-tight text-[var(--text-primary)]">
                  {formatDuration(elapsedSeconds)}
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  {isVi ? "Thời lượng buổi hội thoại lâm sàng" : "Clinical encounter dialogue elapsed time"}
                </p>
              </div>

              {/* 32-Bar Live Waveform */}
              <div className="flex items-center justify-center gap-1 sm:gap-1.5 h-20 px-4">
                {waveBars.map((bar, i) => (
                  <div
                    key={i}
                    style={{ height: `${bar}%` }}
                    className={`w-1.5 sm:w-2 rounded-full transition-all duration-75 ${
                      isRecording ? "bg-rose-500 shadow-sm shadow-rose-500/50" : "bg-[var(--text-muted)] opacity-30"
                    }`}
                  />
                ))}
              </div>

              {/* Action Bar */}
              <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
                {!isRecording ? (
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    onClick={() => void onStartRecording()}
                    data-testid="scribe-start-recording"
                    className="px-10 py-3 rounded-full shadow-lg shadow-rose-600/20"
                  >
                    <Icon name="mic" size="1.25rem" />
                    <span>{isVi ? "Bắt đầu Thu âm" : "Start Live Recording"}</span>
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="danger"
                    size="lg"
                    onClick={onStopRecording}
                    className="px-10 py-3 rounded-full shadow-lg shadow-rose-600/30 animate-bounce"
                  >
                    <Icon name="stop" size="1.25rem" />
                    <span>{isVi ? "Dừng & Chuyển sang Lời thoại" : "Stop & Review Transcript"}</span>
                  </Button>
                )}
              </div>
            </SurfaceCard>
          </div>
        ) : null}

        {/* =========================================================================
            STATE 3: TRANSCRIPT REVIEW
            ========================================================================= */}
        {currentStepIndex === 2 ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start" id="scribe-step-panel-2" role="tabpanel" aria-labelledby="scribe-step-tab-2">
            <div className="lg:col-span-8 space-y-4">
              <SurfaceCard className="p-6 space-y-4" data-testid="scribe-transcript">
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="chat" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h3 className="font-bold text-base text-[var(--text-primary)]">
                      {isVi ? "Biên tập Lời thoại Hội thoại" : "Clinical Dialogue Transcript"}
                    </h3>
                  </div>
                  <Badge tone="brand">{transcriptRows.length} {isVi ? "dòng thoại" : "lines"}</Badge>
                </div>

                {/* Editable Transcript Text Area */}
                <textarea
                  value={transcriptDraft}
                  onChange={(e) => {
                    setTranscriptDraft(e.target.value);
                    schedulePersistTranscript(e.target.value);
                  }}
                  placeholder={isVi ? "Nội dung lời thoại ghi âm sẽ hiển thị ở đây..." : "Transcript will appear here..."}
                  className="w-full min-h-[360px] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm font-sans leading-relaxed text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]"
                />

                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isSaving ? (isVi ? "Đang lưu..." : "Saving...") : (isVi ? "Đã lưu tự động" : "Auto-saved")}
                  </span>
                  <Button
                    type="button"
                    variant="primary"
                    size="md"
                    onClick={() => void onRegenerateSoap()}
                    disabled={isRegenerating || !transcriptDraft.trim()}
                    data-testid="scribe-generate-note"
                  >
                    <Icon name="clinical-notes" size="1rem" />
                    <span>{isRegenerating ? (isVi ? "Đang tạo SOAP..." : "Generating...") : (isVi ? "Tạo Dự thảo SOAP" : "Generate SOAP Draft")}</span>
                  </Button>
                </div>
              </SurfaceCard>
            </div>

            {/* Right: Live Clinical Insights */}
            <div className="lg:col-span-4 space-y-4">
              <SurfaceCard className="p-5 space-y-3">
                <h4 className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)] border-b border-[color:var(--shell-border)]/60 pb-2">
                  {isVi ? "Phát hiện lâm sàng trích xuất" : "Extracted Insights"}
                </h4>
                <div className="space-y-3">
                  {liveInsights.map((ins) => (
                    <div key={ins.id} className="p-3 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1">
                      <strong className="text-xs font-bold text-[var(--text-brand)] block">{ins.title}</strong>
                      <p className="text-xs text-[var(--text-secondary)]">{ins.detail}</p>
                    </div>
                  ))}
                </div>
              </SurfaceCard>
            </div>
          </div>
        ) : null}

        {/* =========================================================================
            STATE 4: SOAP DRAFT REVIEW (DOCUMENT VIEW)
            ========================================================================= */}
        {currentStepIndex === 3 ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start" id="scribe-step-panel-3" role="tabpanel" aria-labelledby="scribe-step-tab-3">
            <div className="lg:col-span-8 space-y-6">
              <SurfaceCard className="p-6 sm:p-8 space-y-6 relative overflow-hidden" data-testid="scribe-step-panel-4">
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--shell-border)]/60 pb-4">
                  <div>
                    <h3 className="text-xl font-bold text-[var(--text-primary)]">
                      {isVi ? "Hồ sơ Khám Bệnh Án SOAP" : "SOAP Clinical Document"}
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      {isVi ? "Dự thảo tổng hợp tự động từ lời thoại phiên khám" : "Synthesized encounter summary note"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="ok">{isVi ? "FIDES Verified" : "FIDES Verified"}</Badge>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => void onRegenerateSoap()}
                      disabled={isRegenerating}
                    >
                      <Icon name="refresh" size="0.9rem" />
                      <span>{isRegenerating ? (isVi ? "Đang tạo lại..." : "Regenerating...") : (isVi ? "Tạo lại SOAP" : "Regenerate")}</span>
                    </Button>
                  </div>
                </div>

                {/* 4 Core SOAP Sections */}
                <div className="space-y-6">
                  {soapSectionLabels.map((item) => (
                    <section key={item.key} className="space-y-2 border-l-2 border-[var(--brand-500)] pl-4">
                      <h4 className="font-bold text-sm text-[var(--text-primary)] uppercase tracking-wide">
                        {item.title}
                      </h4>
                      <div className="p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] text-sm text-[var(--text-primary)] leading-relaxed">
                        {stripTelemetryLabels(safeText(selectedSoap[item.valueKey])) || (
                          <span className="text-[var(--text-muted)] italic">{isVi ? "Chưa có thông tin ghi nhận" : "No content recorded"}</span>
                        )}
                      </div>
                    </section>
                  ))}
                </div>

                {/* Advance Action */}
                <div className="pt-4 border-t border-[color:var(--shell-border)]/60 flex justify-end">
                  <Button
                    type="button"
                    variant="primary"
                    size="md"
                    onClick={() => setCurrentStepIndex(4)}
                  >
                    <span>{isVi ? "Chuyển sang Bước Ký & Hoàn tất" : "Proceed to Finalize & Sign"}</span>
                    <Icon name="arrow-right" size="1rem" />
                  </Button>
                </div>
              </SurfaceCard>
            </div>

            {/* Right: Collapsed Transcript Side View */}
            <div className="lg:col-span-4 space-y-4">
              <SurfaceCard className="p-4 space-y-3 max-h-[500px] overflow-y-auto clara-scrollbar">
                <h4 className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)] border-b border-[color:var(--shell-border)]/60 pb-2">
                  {isVi ? "Lời thoại gốc đối chiếu" : "Source Transcript"}
                </h4>
                <div className="space-y-2 text-xs text-[var(--text-secondary)]">
                  {transcriptRows.map((r) => (
                    <div key={r.id} className="p-2 rounded-lg bg-[var(--surface-muted)] space-y-0.5">
                      <span className="font-bold text-[var(--text-brand)]">{r.speaker} ({r.timestamp}):</span>
                      <p>{r.text}</p>
                    </div>
                  ))}
                </div>
              </SurfaceCard>
            </div>
          </div>
        ) : null}

        {/* =========================================================================
            STATE 5: FINALIZE & SIGN
            ========================================================================= */}
        {currentStepIndex === 4 ? (
          <div className="max-w-2xl mx-auto space-y-6" id="scribe-step-panel-4" role="tabpanel" aria-labelledby="scribe-step-tab-4">
            <SurfaceCard className="p-8 space-y-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-500/20">
                <Icon name="check" size="2rem" />
              </div>

              <div className="space-y-2">
                <h3 className="text-2xl font-bold text-[var(--text-primary)]">
                  {selectedSession?.status === "signed" ? (isVi ? "Bệnh án đã được Ký số" : "Encounter Note Signed") : (isVi ? "Ký & Ban hành Bệnh án SOAP" : "Sign & Finalize SOAP Note")}
                </h3>
                <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto leading-relaxed">
                  {isVi
                    ? "Bệnh án sẽ được niêm phong chữ ký điện tử, cập nhật vào hồ sơ bệnh án điện tử (PHR) và khóa chỉnh sửa trực tiếp."
                    : "The clinical note will be signed with electronic audit integrity and committed to the patient health record."}
                </p>
              </div>

              {/* Pre-sign Checklist */}
              <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] text-left text-xs space-y-2 max-w-md mx-auto">
                <div className="flex items-center gap-2 text-emerald-600 font-semibold">
                  <Icon name="check" size="1rem" />
                  <span>{isVi ? "Đồng thuận bệnh nhân đã xác nhận" : "Patient consent verified"}</span>
                </div>
                <div className="flex items-center gap-2 text-emerald-600 font-semibold">
                  <Icon name="check" size="1rem" />
                  <span>{isVi ? "4 phân mục SOAP đã hoàn chỉnh" : "4 SOAP sections validated"}</span>
                </div>
                <div className="flex items-center gap-2 text-emerald-600 font-semibold">
                  <Icon name="check" size="1rem" />
                  <span>{isVi ? "Kiểm tra tương tác thuốc FIDES thông qua" : "FIDES safety checks cleared"}</span>
                </div>
              </div>

              <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                {selectedSession?.status !== "signed" ? (
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    onClick={() => void onFinalizeEncounter()}
                    disabled={isSaving}
                    data-testid="scribe-sign"
                    className="w-full sm:w-auto px-10"
                  >
                    <Icon name="clinical-notes" size="1.2rem" />
                    <span>{isSaving ? (isVi ? "Đang ký số..." : "Signing...") : (isVi ? "Ký & Ban hành Bệnh án" : "Sign & Finalize Note")}</span>
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="lg"
                    onClick={() => setCurrentStepIndex(3)}
                    className="w-full sm:w-auto px-8"
                  >
                    <Icon name="arrow-left" size="1.1rem" />
                    <span>{isVi ? "Xem lại Bệnh án SOAP" : "Review SOAP Document"}</span>
                  </Button>
                )}
              </div>
            </SurfaceCard>

            {/* Recording Data Deletion Option */}
            {canDeleteSelectedRecordingData && (
              <section className="p-5 rounded-2xl border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] space-y-3" data-testid="scribe-recording-data-controls">
                <div className="flex items-center justify-between">
                  <div>
                    <h5 className="font-bold text-xs text-[var(--status-danger-text)] uppercase tracking-wider">
                      {isVi ? "Quản trị quyền riêng tư bản ghi âm" : "Audio Data Governance"}
                    </h5>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      {isVi ? "Xóa vĩnh viễn tệp âm thanh gốc sau khi đã hoàn tất dự thảo SOAP." : "Permanently erase raw encounter audio after SOAP completion."}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={() => setShowRecordingDataDeleteConfirmation(true)}
                  >
                    <Icon name="trash" size="0.9rem" />
                    <span>{isVi ? "Xóa tệp âm thanh" : "Delete Audio"}</span>
                  </Button>
                </div>
              </section>
            )}
          </div>
        ) : null}
      </div>

      {/* Enterprise Review Modal */}
      {showEnterpriseModal && (
        <Modal
          open={showEnterpriseModal}
          title="Enterprise Scribe Review"
          onClose={() => setShowEnterpriseModal(false)}
          size="lg"
        >
          <div className="p-4">
            <EnterpriseReview
              session={selectedSession}
              onSessionChange={setSelectedSession}
              pushNotice={pushNotice}
            />
          </div>
        </Modal>
      )}

      {/* Telemetry Modal */}
      {showTelemetryModal && (
        <Modal
          open={showTelemetryModal}
          title="Scribe Pipeline Telemetry"
          onClose={() => setShowTelemetryModal(false)}
          size="lg"
        >
          <div className="p-4">
            <TelemetryPanel role={role}>
              <div className="space-y-2 text-xs">
                <p>Last transcribe processing: {lastTranscribeMs ? `${lastTranscribeMs}ms` : "--"}</p>
                <p>Current role: {role}</p>
              </div>
            </TelemetryPanel>
          </div>
        </Modal>
      )}

      {/* Recording Delete Confirmation Modal */}
      {showRecordingDataDeleteConfirmation && (
        <Modal
          open={showRecordingDataDeleteConfirmation}
          title={isVi ? "Xác nhận xóa tệp ghi âm" : "Confirm Audio Deletion"}
          onClose={() => setShowRecordingDataDeleteConfirmation(false)}
          size="sm"
        >
          <div className="p-5 space-y-4">
            <p className="text-sm text-[var(--text-secondary)]">
              {isVi
                ? "Hành động này sẽ xóa vĩnh viễn tệp âm thanh gốc khỏi máy chủ. Bản ghi lời thoại và bệnh án SOAP sẽ được giữ nguyên."
                : "This will permanently delete the raw audio recording from the server. The transcript and SOAP note will be preserved."}
            </p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => setShowRecordingDataDeleteConfirmation(false)}>
                {isVi ? "Hủy" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                onClick={() => void onDeleteRecordingData()}
                disabled={isDeletingRecordingData}
              >
                {isDeletingRecordingData ? (isVi ? "Đang xóa..." : "Deleting...") : (isVi ? "Xóa vĩnh viễn" : "Delete Permanently")}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </WorkflowLayout>
  );
}
