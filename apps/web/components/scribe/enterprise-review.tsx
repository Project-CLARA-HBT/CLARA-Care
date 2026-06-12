"use client";

/**
 * Clara Scribe — enterprise review/sign/export flow (task 2.7, Req 1, 8, 9).
 *
 * A self-contained, additive surface layered over the existing batch Scribe
 * page. The flow is: consent gate → live transcript (speaker chips) + process
 * panel → template picker → generated-note editor → sign → export. When the
 * server's enterprise flags are off (endpoints return 404) or the streaming
 * transport is unavailable, every step degrades to the existing batch behavior
 * (`transcribeScribeAudio` + `regenerateScribeSession` + finalize) so the page
 * keeps working unchanged.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ScribeSession,
  ScribeStreamSegment,
  amendScribeNote,
  captureScribeConsent,
  exportScribeNote,
  generateScribeNote,
  getScribeGrounding,
  regenerateScribeSession,
  signScribeNote,
  streamScribe,
  transcribeScribeAudio,
  updateScribeSession,
  type ScribeExportFormat,
  type ScribeGroundingReport,
} from "@/lib/scribe";
import {
  DEFAULT_SCRIBE_TEMPLATE_ID,
  NoteSectionEntry,
  SCRIBE_REVIEW_TEMPLATES,
  ScribeFlowState,
  computePipelineStages,
  concatSegmentsText,
  formatGroundedClaimRate,
  groundingChip,
  groundingHasData,
  normalizeGroundingReport,
  orderedNoteSections,
  partitionGroundingStatements,
  resolveTranscriptSpan,
  speakerChip,
  type GroundingStatus,
  type ScribeStageStatus,
} from "@/lib/scribe-review";

type NoticeTone = "success" | "error";

export type EnterpriseReviewProps = {
  session: ScribeSession | null;
  onSessionChange: (session: ScribeSession) => void;
  pushNotice: (tone: NoticeTone, message: string) => void;
};

// --- shared styling (kept consistent with the surrounding scribe page) -------
const panelClass =
  "rounded-xl border border-[#B6D4FE] bg-white shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const panelPaddedClass = `${panelClass} p-4`;
const softPanelClass =
  "rounded-lg border border-[#93C5FD] bg-[#EEF6FF] shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const sectionTitleClass =
  "text-xs font-black uppercase tracking-[0.18em] text-[#4B5563] dark:text-slate-200";
const secondaryTextClass = "text-[#4B5563] dark:text-slate-300";
const mutedTextClass = "text-[#64748B] dark:text-slate-400";
const bodyTextClass = "text-[#1F2937] dark:text-slate-100";
const primaryButtonClass =
  "rounded-lg border border-[#2563EB] bg-[#2563EB] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-[#1D4ED8] disabled:cursor-not-allowed disabled:border-[#93C5FD] disabled:bg-[#DBEAFE] disabled:text-[#1F2937] disabled:opacity-100 dark:border-sky-400 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400";
const secondaryButtonClass =
  "rounded-lg border border-[#93C5FD] bg-[#EFF6FF] px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-[#1D4ED8] transition hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:bg-[#DBEAFE] disabled:text-[#1F2937] disabled:opacity-100 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100";
const dangerButtonClass =
  "rounded-lg border border-rose-700 bg-rose-600 px-3 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-sm transition hover:bg-rose-700";
const sectionTextareaClass =
  "min-h-[88px] w-full rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 py-2 text-sm leading-6 text-[#1F2937] outline-none transition focus:border-[#2563EB] focus:bg-white focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-[#EEF2F7] dark:border-sky-700/70 dark:bg-slate-950/60 dark:text-slate-100";

const SPEAKER_CHIP_CLASSES: Record<string, string> = {
  clinician:
    "border-[#2563EB] bg-[#DBEAFE] text-[#1D4ED8] dark:border-sky-400 dark:bg-sky-500/20 dark:text-sky-100",
  patient:
    "border-emerald-500 bg-emerald-50 text-emerald-700 dark:border-emerald-400 dark:bg-emerald-500/20 dark:text-emerald-100",
  other:
    "border-amber-500 bg-amber-50 text-amber-700 dark:border-amber-400 dark:bg-amber-500/20 dark:text-amber-100",
  unknown:
    "border-slate-400 bg-slate-100 text-slate-600 dark:border-slate-500 dark:bg-slate-700/40 dark:text-slate-200",
};

const STAGE_DOT_CLASSES: Record<ScribeStageStatus, string> = {
  pending: "bg-slate-300 dark:bg-slate-600",
  in_progress: "bg-[#2563EB] animate-pulse",
  completed: "bg-emerald-500",
  failed: "bg-rose-500",
  warning: "bg-amber-500",
};

const STAGE_STATUS_LABELS: Record<ScribeStageStatus, string> = {
  pending: "đang chờ",
  in_progress: "đang xử lý",
  completed: "hoàn tất",
  failed: "lỗi",
  warning: "cảnh báo",
};

// Grounding chip tones (Req 12.7): grounded statements are evidenced, unverified
// statements need clinician confirmation. Kept in the same palette family as the
// speaker chips so the editor reads consistently.
const GROUNDING_CHIP_CLASSES: Record<GroundingStatus, string> = {
  grounded:
    "border-emerald-500 bg-emerald-50 text-emerald-700 dark:border-emerald-400 dark:bg-emerald-500/20 dark:text-emerald-100",
  unverified:
    "border-amber-500 bg-amber-50 text-amber-700 dark:border-amber-400 dark:bg-amber-500/20 dark:text-amber-100",
};

const SIGNED_STATUSES = new Set(["signed", "exported"]);

function isMissingCapability(error: unknown): boolean {
  // The enterprise endpoints answer 404 when their feature flag is off; the
  // http-client surfaces the server detail as the Error message.
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  return (
    message.includes("disabled") ||
    message.includes("not found") ||
    message.includes("404") ||
    message.includes("kh\u00f4ng t\u1ed3n t\u1ea1i")
  );
}

function downloadTextFile(filename: string, contents: string, mime: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([contents], { type: mime });
  downloadBlob(filename, blob);
}

function downloadBlob(filename: string, blob: Blob): void {
  if (typeof window === "undefined") return;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function sectionsToRecord(sections: NoteSectionEntry[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const section of sections) record[section.key] = section.value;
  return record;
}

export default function EnterpriseReview({ session, onSessionChange, pushNotice }: EnterpriseReviewProps) {
  const sessionId = session?.id ?? null;
  const sessionStatus = (session?.status ?? "").trim().toLowerCase();
  const alreadySigned = SIGNED_STATUSES.has(sessionStatus);

  // --- flow state ----------------------------------------------------------
  const [consentCaptured, setConsentCaptured] = useState(false);
  const [consentRequired, setConsentRequired] = useState(true);
  const [capturingConsent, setCapturingConsent] = useState(false);

  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [segments, setSegments] = useState<ScribeStreamSegment[]>([]);
  const [partialText, setPartialText] = useState("");
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [usedBatchFallback, setUsedBatchFallback] = useState(false);
  const [degradedCount, setDegradedCount] = useState(0);
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null);

  const [templateId, setTemplateId] = useState<string>(DEFAULT_SCRIBE_TEMPLATE_ID);
  const [generating, setGenerating] = useState(false);
  const [noteSections, setNoteSections] = useState<NoteSectionEntry[]>([]);
  const [noteTemplateId, setNoteTemplateId] = useState<string>(DEFAULT_SCRIBE_TEMPLATE_ID);
  const [noteReady, setNoteReady] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  const [signing, setSigning] = useState(false);
  const [signed, setSigned] = useState(false);
  const [exported, setExported] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<ScribeExportFormat | null>(null);

  // Grounding / claim-traceability surface (Req 12.7). Additive + best-effort:
  // `grounding` stays null when the flag is off / the version has no metadata
  // (the read 404s), so the editor renders exactly as before. `noteVersionNo`
  // tracks the version generated in this session so we can fetch its report;
  // it increments per generate/amend (the server increments the same way).
  const [grounding, setGrounding] = useState<ScribeGroundingReport | null>(null);
  const [noteVersionNo, setNoteVersionNo] = useState<number | null>(null);
  const [expandedStatement, setExpandedStatement] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // --- hydrate from the selected session ----------------------------------
  useEffect(() => {
    setTranscriptDraft(session?.transcript ?? "");
    setSegments([]);
    setPartialText("");
    setUsedBatchFallback(false);
    setDegradedCount(0);
    setTranscriptionError(null);
    setSigned(SIGNED_STATUSES.has((session?.status ?? "").trim().toLowerCase()));
    setExported((session?.status ?? "").trim().toLowerCase() === "exported");

    const existing = orderedNoteSections((session?.soap as Record<string, unknown>) ?? null, DEFAULT_SCRIBE_TEMPLATE_ID);
    const hasContent = existing.some((entry) => entry.value.trim().length > 0);
    setNoteSections(existing);
    setNoteReady(hasContent);
    setNoteTemplateId(DEFAULT_SCRIBE_TEMPLATE_ID);
    // Grounding is re-fetched per generated version; reset it on session switch
    // so a prior session's report never leaks onto another note.
    setGrounding(null);
    setNoteVersionNo(null);
    setExpandedStatement(null);
    // Consent re-gates per session; a signed/exported session has clearly
    // already passed consent so we don't block review of it.
    const signedAlready = SIGNED_STATUSES.has((session?.status ?? "").trim().toLowerCase());
    setConsentCaptured(signedAlready);
    setConsentRequired(!signedAlready);
  }, [session]);

  const flowState: ScribeFlowState = useMemo(
    () => ({
      consentCaptured,
      consentRequired,
      transcribing,
      transcriptReady: transcriptDraft.trim().length > 0,
      usedBatchFallback,
      degradedCount,
      generating,
      noteReady,
      signing,
      signed,
      exported,
      transcriptionError,
    }),
    [
      consentCaptured,
      consentRequired,
      transcribing,
      transcriptDraft,
      usedBatchFallback,
      degradedCount,
      generating,
      noteReady,
      signing,
      signed,
      exported,
      transcriptionError,
    ]
  );

  const stages = useMemo(() => computePipelineStages(flowState), [flowState]);
  const transcriptReady = transcriptDraft.trim().length > 0;
  const canRecord = (consentCaptured || !consentRequired) && !alreadySigned;

  // --- consent gate --------------------------------------------------------
  const onCaptureConsent = useCallback(async () => {
    if (!sessionId) {
      pushNotice("error", "Hãy chọn hoặc tạo phiên trước khi ghi đồng thuận.");
      return;
    }
    setCapturingConsent(true);
    try {
      await captureScribeConsent(sessionId, { method: "verbal", scope: "encounter" });
      setConsentCaptured(true);
      setConsentRequired(true);
      pushNotice("success", "Đã ghi nhận đồng thuận của người bệnh.");
    } catch (error) {
      if (isMissingCapability(error)) {
        // Consent capture is flag-gated server-side; when unavailable we treat
        // consent as not required so the legacy flow keeps working.
        setConsentCaptured(true);
        setConsentRequired(false);
        pushNotice("success", "Đồng thuận không bắt buộc ở chế độ hiện tại.");
      } else {
        pushNotice("error", error instanceof Error ? error.message : "Không thể ghi nhận đồng thuận.");
      }
    } finally {
      setCapturingConsent(false);
    }
  }, [pushNotice, sessionId]);

  // --- transcription (streaming + batch fallback) --------------------------
  const runBatchFallback = useCallback(
    async (blob: Blob) => {
      if (!sessionId) return;
      try {
        const response = await transcribeScribeAudio({
          audioFile: blob,
          filename: `scribe-${sessionId}.webm`,
          language: "vi",
          sessionId,
          appendToSession: true,
        });
        const text = String(response.text ?? "").trim();
        setUsedBatchFallback(true);
        if (text) {
          setTranscriptDraft((prev) => (prev.trim() ? `${prev.trimEnd()}\n${text}` : text));
        }
        pushNotice("success", "Đã phiên âm theo lô (chế độ dự phòng).");
      } catch (error) {
        pushNotice("error", error instanceof Error ? error.message : "Phiên âm dự phòng thất bại.");
      }
    },
    [pushNotice, sessionId]
  );

  const processAudioBlob = useCallback(
    async (blob: Blob) => {
      if (!sessionId) {
        pushNotice("error", "Không có phiên để phiên âm.");
        return;
      }
      setTranscribing(true);
      setTranscriptionError(null);
      setPartialText("");

      let sawError = false;
      try {
        await streamScribe(sessionId, blob, {
          language: "vi",
          templateId,
          onSegment: (segment) => {
            setSegments((prev) => [...prev, segment]);
            if (segment.degraded) setDegradedCount((count) => count + 1);
          },
          onPartial: (partial) => setPartialText(partial.text ?? ""),
          onDone: (result) => {
            setPartialText("");
            if (typeof result.transcript === "string" && result.transcript.trim()) {
              setTranscriptDraft(result.transcript.trim());
            } else {
              setSegments((prev) => {
                const text = concatSegmentsText(prev);
                if (text) setTranscriptDraft(text);
                return prev;
              });
            }
            if (typeof result.asr_meta?.degraded_count === "number") {
              setDegradedCount(result.asr_meta.degraded_count);
            }
            if (result.note?.sections) {
              const entries = orderedNoteSections(result.note.sections, result.note.template_id ?? templateId);
              if (entries.some((entry) => entry.value.trim())) {
                setNoteSections(entries);
                setNoteTemplateId(result.note.template_id ?? templateId);
              }
            }
          },
          onError: (message) => {
            sawError = true;
            setTranscriptionError(message);
          },
        });
        if (sawError) await runBatchFallback(blob);
      } catch (error) {
        // Transport-level failure (flag off, network) ⇒ batch fallback.
        const message = error instanceof Error ? error.message : "Streaming không khả dụng.";
        setTranscriptionError(message);
        await runBatchFallback(blob);
      } finally {
        setTranscribing(false);
        setPartialText("");
      }
    },
    [pushNotice, runBatchFallback, sessionId, templateId]
  );

  const stopMediaRecorder = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

  const onStartRecording = useCallback(async () => {
    if (!canRecord) {
      pushNotice("error", "Hãy ghi nhận đồng thuận trước khi ghi âm.");
      return;
    }
    if (typeof window === "undefined" || !window.navigator?.mediaDevices?.getUserMedia) {
      pushNotice("error", "Trình duyệt không hỗ trợ ghi âm. Hãy tải tệp âm thanh lên.");
      fileInputRef.current?.click();
      return;
    }
    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      recordedChunksRef.current = [];

      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const selectedMime = mimeCandidates.find(
        (item) =>
          typeof MediaRecorder !== "undefined" &&
          typeof MediaRecorder.isTypeSupported === "function" &&
          MediaRecorder.isTypeSupported(item)
      );
      const recorder = selectedMime
        ? new MediaRecorder(stream, { mimeType: selectedMime })
        : new MediaRecorder(stream);
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) recordedChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const chunks = recordedChunksRef.current;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        setRecording(false);
        if (chunks.length === 0) return;
        const blob = new Blob(chunks, { type: selectedMime ?? "audio/webm" });
        void processAudioBlob(blob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setSegments([]);
      setRecording(true);
      pushNotice("success", "Đang ghi âm cuộc khám.");
    } catch (error) {
      pushNotice("error", error instanceof Error ? error.message : "Không thể bắt đầu ghi âm.");
    }
  }, [canRecord, processAudioBlob, pushNotice]);

  const onUploadAudio = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;
      if (!canRecord) {
        pushNotice("error", "Hãy ghi nhận đồng thuận trước khi phiên âm.");
        return;
      }
      setSegments([]);
      void processAudioBlob(file);
    },
    [canRecord, processAudioBlob, pushNotice]
  );

  // --- note generation -----------------------------------------------------
  // Best-effort fetch of the additive grounding report for a generated version
  // (Req 12.7). Silently no-ops when grounding is unavailable (flag off / 404 /
  // transport error) so the editor degrades to the prior chip-less behavior.
  const loadGrounding = useCallback(
    async (versionNo: number) => {
      if (!sessionId || !Number.isFinite(versionNo) || versionNo < 1) return;
      try {
        const response = await getScribeGrounding(sessionId, versionNo);
        const report = normalizeGroundingReport(response.grounding);
        setGrounding(groundingHasData(report) ? report : null);
      } catch {
        // Grounding is flag-gated server-side; absence is expected, not an error.
        setGrounding(null);
      }
      setExpandedStatement(null);
    },
    [sessionId]
  );

  const onGenerateNote = useCallback(async () => {
    if (!sessionId) return;
    if (!transcriptReady) {
      pushNotice("error", "Bản ghi đang trống.");
      return;
    }
    setGenerating(true);
    try {
      const updated = await generateScribeNote(sessionId, {
        template_id: templateId,
        transcript: transcriptDraft,
      });
      onSessionChange(updated);
      const entries = orderedNoteSections((updated.soap as Record<string, unknown>) ?? null, templateId);
      setNoteSections(entries);
      setNoteTemplateId(templateId);
      setNoteReady(true);
      // Each generate inserts the next note version server-side; mirror that
      // count locally so we can fetch the matching grounding report (Req 12.7).
      const nextVersion = (noteVersionNo ?? 0) + 1;
      setNoteVersionNo(nextVersion);
      void loadGrounding(nextVersion);
      pushNotice("success", "Đã soạn ghi chú theo mẫu.");
    } catch (error) {
      if (isMissingCapability(error)) {
        // Sign-workflow/templates flag off ⇒ fall back to the legacy SOAP path.
        try {
          const updated = await regenerateScribeSession(sessionId, {
            transcript: transcriptDraft,
            status: "ready",
          });
          onSessionChange(updated);
          const entries = orderedNoteSections((updated.soap as Record<string, unknown>) ?? null, DEFAULT_SCRIBE_TEMPLATE_ID);
          setNoteSections(entries);
          setNoteTemplateId(DEFAULT_SCRIBE_TEMPLATE_ID);
          setNoteReady(true);
          // Legacy SOAP path produces no grounding metadata; clear any prior report.
          setGrounding(null);
          pushNotice("success", "Đã tạo ghi chú SOAP (chế độ tiêu chuẩn).");
        } catch (fallbackError) {
          pushNotice("error", fallbackError instanceof Error ? fallbackError.message : "Không thể soạn ghi chú.");
        }
      } else {
        pushNotice("error", error instanceof Error ? error.message : "Không thể soạn ghi chú.");
      }
    } finally {
      setGenerating(false);
    }
  }, [onSessionChange, pushNotice, sessionId, templateId, transcriptDraft, transcriptReady, loadGrounding, noteVersionNo]);

  const onSaveNoteEdits = useCallback(async () => {
    if (!sessionId) return;
    setSavingNote(true);
    try {
      const updated = await updateScribeSession(sessionId, {
        soap: sectionsToRecord(noteSections),
        status: "in_review",
      });
      onSessionChange(updated);
      pushNotice("success", "Đã lưu chỉnh sửa ghi chú.");
    } catch (error) {
      pushNotice("error", error instanceof Error ? error.message : "Không thể lưu ghi chú.");
    } finally {
      setSavingNote(false);
    }
  }, [noteSections, onSessionChange, pushNotice, sessionId]);

  // --- sign ----------------------------------------------------------------
  const onSign = useCallback(async () => {
    if (!sessionId) return;
    setSigning(true);
    try {
      const updated = await signScribeNote(sessionId);
      onSessionChange(updated);
      setSigned(true);
      pushNotice("success", "Đã ký ghi chú lâm sàng.");
    } catch (error) {
      if (isMissingCapability(error)) {
        try {
          const updated = await updateScribeSession(sessionId, { status: "finalized" });
          onSessionChange(updated);
          setSigned(true);
          pushNotice("success", "Đã hoàn tất ghi chú (chế độ tiêu chuẩn).");
        } catch (fallbackError) {
          pushNotice("error", fallbackError instanceof Error ? fallbackError.message : "Không thể ký ghi chú.");
        }
      } else {
        pushNotice("error", error instanceof Error ? error.message : "Không thể ký ghi chú.");
      }
    } finally {
      setSigning(false);
    }
  }, [onSessionChange, pushNotice, sessionId]);

  const onAmend = useCallback(async () => {
    if (!sessionId) return;
    try {
      const updated = await amendScribeNote(sessionId, { template_id: noteTemplateId, transcript: transcriptDraft });
      onSessionChange(updated);
      setSigned(false);
      setExported(false);
      // Amend inserts a fresh note version; refresh grounding for it (Req 12.7).
      const nextVersion = (noteVersionNo ?? 0) + 1;
      setNoteVersionNo(nextVersion);
      void loadGrounding(nextVersion);
      pushNotice("success", "Đã tạo bản sửa đổi mới (amended).");
    } catch (error) {
      pushNotice("error", error instanceof Error ? error.message : "Không thể tạo bản sửa đổi.");
    }
  }, [noteTemplateId, onSessionChange, pushNotice, sessionId, transcriptDraft, loadGrounding, noteVersionNo]);

  // --- export --------------------------------------------------------------
  const onExport = useCallback(
    async (format: ScribeExportFormat) => {
      if (!sessionId) return;
      setExportingFormat(format);
      try {
        const result = await exportScribeNote(sessionId, format);
        const base = `clinical-note-${sessionId}`;
        if (result.format === "md") {
          downloadTextFile(`${base}.md`, result.markdown || "", "text/markdown;charset=utf-8");
        } else if (result.format === "fhir") {
          downloadTextFile(`${base}.fhir.json`, JSON.stringify(result.document, null, 2), "application/json");
        } else {
          downloadBlob(result.filename, result.blob);
        }
        setExported(true);
        pushNotice("success", `Đã xuất bản ghi chú (${format.toUpperCase()}).`);
      } catch (error) {
        if (isMissingCapability(error)) {
          pushNotice("error", "Tính năng xuất bản chưa được bật cho phiên này.");
        } else {
          pushNotice("error", error instanceof Error ? error.message : "Không thể xuất bản ghi chú.");
        }
      } finally {
        setExportingFormat(null);
      }
    },
    [pushNotice, sessionId]
  );

  // --- cleanup -------------------------------------------------------------
  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const transcriptRows = useMemo(() => {
    if (segments.length > 0) return segments;
    // Derive lightweight rows from the persisted/batch transcript so speaker
    // chips still render (defaulting to `unknown`) when there are no segments.
    return transcriptDraft
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map<ScribeStreamSegment>((line, index) => ({
        index,
        text: line,
        speaker: "unknown",
        start_ms: 0,
        end_ms: 0,
        degraded: false,
      }));
  }, [segments, transcriptDraft]);

  if (!session) {
    return (
      <div className={`col-span-12 ${panelPaddedClass}`}>
        <p className={`text-sm font-medium ${secondaryTextClass}`}>
          Hãy chọn hoặc tạo một phiên ở cột bên trái để bắt đầu quy trình rà soát doanh nghiệp.
        </p>
      </div>
    );
  }

  return (
    <div className="col-span-12 grid grid-cols-12 gap-5">
      {renderProcessPanel({ stages, sessionStatus })}
      {renderTranscriptColumn({
        consentCaptured,
        consentRequired,
        capturingConsent,
        canRecord,
        recording,
        transcribing,
        transcriptRows,
        partialText,
        transcriptDraft,
        usedBatchFallback,
        degradedCount,
        transcriptionError,
        alreadySigned,
        onCaptureConsent,
        onStartRecording,
        onStopRecording: stopMediaRecorder,
        onTranscriptChange: setTranscriptDraft,
        onUploadClick: () => fileInputRef.current?.click(),
      })}
      {renderNoteColumn({
        templateId,
        onTemplateChange: setTemplateId,
        generating,
        transcriptReady,
        noteReady,
        noteSections,
        noteTemplateId,
        savingNote,
        signed,
        exported,
        signing,
        exportingFormat,
        grounding,
        transcriptSegments: transcriptRows,
        expandedStatement,
        onToggleStatement: (key) => setExpandedStatement((prev) => (prev === key ? null : key)),
        onGenerateNote,
        onSectionChange: (key, value) =>
          setNoteSections((prev) => prev.map((entry) => (entry.key === key ? { ...entry, value } : entry))),
        onSaveNoteEdits,
        onSign,
        onAmend,
        onExport,
      })}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={onUploadAudio}
        data-testid="scribe-audio-upload"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Render helpers (kept as plain functions returning JSX for readability).
// ---------------------------------------------------------------------------

function renderProcessPanel({
  stages,
  sessionStatus,
}: {
  stages: ReturnType<typeof computePipelineStages>;
  sessionStatus: string;
}) {
  return (
    <aside className="col-span-12 xl:col-span-3 space-y-3">
      <div className={panelPaddedClass} data-testid="scribe-process-panel">
        <div className="flex items-center justify-between">
          <h2 className={sectionTitleClass}>Luồng xử lý</h2>
          <span className="rounded-full border border-[#93C5FD] bg-[#EFF6FF] px-2 py-0.5 text-[10px] font-bold text-[#1D4ED8] dark:border-sky-600 dark:bg-sky-500/20 dark:text-sky-100">
            {sessionStatus || "draft"}
          </span>
        </div>
        <ol className="mt-3 space-y-3">
          {stages.map((stage, index) => (
            <li key={stage.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className={`mt-1 h-3 w-3 rounded-full ${STAGE_DOT_CLASSES[stage.status]}`} />
                {index < stages.length - 1 ? (
                  <span className="mt-1 h-7 w-px bg-[#B6D4FE] dark:bg-sky-800" />
                ) : null}
              </div>
              <div>
                <p className={`text-sm font-bold ${bodyTextClass}`}>{stage.label}</p>
                <p className={`text-[10px] font-bold uppercase tracking-[0.12em] ${mutedTextClass}`}>
                  {STAGE_STATUS_LABELS[stage.status]}
                </p>
                {stage.detail ? (
                  <p className={`mt-0.5 text-[11px] leading-4 ${secondaryTextClass}`}>{stage.detail}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}

function renderTranscriptColumn(props: {
  consentCaptured: boolean;
  consentRequired: boolean;
  capturingConsent: boolean;
  canRecord: boolean;
  recording: boolean;
  transcribing: boolean;
  transcriptRows: ScribeStreamSegment[];
  partialText: string;
  transcriptDraft: string;
  usedBatchFallback: boolean;
  degradedCount: number;
  transcriptionError: string | null;
  alreadySigned: boolean;
  onCaptureConsent: () => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onTranscriptChange: (value: string) => void;
  onUploadClick: () => void;
}) {
  const consentGateOpen = props.consentRequired && !props.consentCaptured;
  return (
    <article className="col-span-12 xl:col-span-5 space-y-4">
      {consentGateOpen ? (
        <div className={`${panelPaddedClass} border-amber-300`} data-testid="scribe-consent-gate">
          <h3 className="text-xs font-black uppercase tracking-[0.18em] text-amber-700 dark:text-amber-200">
            Cổng đồng thuận
          </h3>
          <p className={`mt-2 text-sm leading-6 ${secondaryTextClass}`}>
            Cần ghi nhận đồng thuận của người bệnh trước khi ghi âm hoặc phiên âm cuộc khám.
          </p>
          <button
            type="button"
            onClick={props.onCaptureConsent}
            disabled={props.capturingConsent}
            className={`mt-3 ${primaryButtonClass}`}
            data-testid="scribe-capture-consent"
          >
            {props.capturingConsent ? "Đang ghi nhận..." : "Ghi nhận đồng thuận"}
          </button>
        </div>
      ) : null}

      <div className={panelClass}>
        <div className="flex items-center justify-between border-b border-[#B6D4FE] px-5 py-3 dark:border-sky-800">
          <h3 className={sectionTitleClass}>Bản ghi trực tiếp</h3>
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-[#1D4ED8] dark:text-sky-100">
            <span className={`h-2 w-2 rounded-full ${props.recording ? "bg-rose-500 animate-pulse" : props.transcribing ? "bg-[#2563EB] animate-pulse" : "bg-slate-500"}`} />
            {props.recording ? "Đang ghi" : props.transcribing ? "Đang phiên âm" : "Sẵn sàng"}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b border-[#B6D4FE] px-5 py-3 dark:border-sky-800">
          {props.recording ? (
            <button type="button" onClick={props.onStopRecording} className={dangerButtonClass}>
              Dừng ghi âm
            </button>
          ) : (
            <button
              type="button"
              onClick={props.onStartRecording}
              disabled={!props.canRecord || props.transcribing}
              className={primaryButtonClass}
              data-testid="scribe-start-recording"
            >
              Bắt đầu ghi âm
            </button>
          )}
          <button
            type="button"
            onClick={props.onUploadClick}
            disabled={!props.canRecord || props.transcribing || props.recording}
            className={secondaryButtonClass}
          >
            Tải tệp âm thanh
          </button>
          {props.alreadySigned ? (
            <span className={`text-[11px] font-semibold ${mutedTextClass}`}>Ghi chú đã ký — chỉ đọc.</span>
          ) : null}
        </div>

        <div className="max-h-[320px] space-y-3 overflow-y-auto p-5 clara-scrollbar" data-testid="scribe-transcript">
          {props.transcriptRows.length === 0 ? (
            <p className={`text-sm font-medium ${secondaryTextClass}`}>Chưa có nội dung phiên âm.</p>
          ) : (
            props.transcriptRows.map((segment) => {
              const chip = speakerChip(segment.speaker);
              return (
                <div key={`${segment.index}-${segment.start_ms}`} className="flex gap-3">
                  <span
                    className={`h-fit shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.08em] ${SPEAKER_CHIP_CLASSES[chip.tone]}`}
                  >
                    {chip.label}
                  </span>
                  <p className={`text-sm leading-6 ${segment.degraded ? "italic " + mutedTextClass : secondaryTextClass}`}>
                    {segment.text}
                    {segment.degraded ? " (tín hiệu yếu)" : ""}
                  </p>
                </div>
              );
            })
          )}
          {props.partialText ? (
            <div className="flex gap-3 opacity-70">
              <span className={`h-fit shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.08em] ${SPEAKER_CHIP_CLASSES.unknown}`}>
                …
              </span>
              <p className={`text-sm italic leading-6 ${mutedTextClass}`}>{props.partialText}</p>
            </div>
          ) : null}
        </div>

        {props.transcriptionError ? (
          <p className="mx-5 mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
            Streaming gặp sự cố ({props.transcriptionError}). Đã chuyển sang phiên âm theo lô.
          </p>
        ) : null}

        <div className="border-t border-[#B6D4FE] p-4 dark:border-sky-800">
          <textarea
            value={props.transcriptDraft}
            onChange={(event) => props.onTranscriptChange(event.target.value)}
            placeholder="Bản ghi sẽ hiển thị ở đây; bạn có thể chỉnh sửa trước khi soạn ghi chú."
            disabled={props.alreadySigned}
            className={sectionTextareaClass}
          />
          <p className={`mt-2 text-[10px] font-bold uppercase tracking-[0.12em] ${mutedTextClass}`}>
            {props.usedBatchFallback ? "Nguồn: phiên âm theo lô" : "Nguồn: phiên âm trực tiếp"}
            {props.degradedCount > 0 ? ` · ${props.degradedCount} đoạn tín hiệu yếu` : ""}
          </p>
        </div>
      </div>
    </article>
  );
}

function renderNoteColumn(props: {
  templateId: string;
  onTemplateChange: (value: string) => void;
  generating: boolean;
  transcriptReady: boolean;
  noteReady: boolean;
  noteSections: NoteSectionEntry[];
  noteTemplateId: string;
  savingNote: boolean;
  signed: boolean;
  exported: boolean;
  signing: boolean;
  exportingFormat: ScribeExportFormat | null;
  grounding: ScribeGroundingReport | null;
  transcriptSegments: ScribeStreamSegment[];
  expandedStatement: string | null;
  onToggleStatement: (key: string) => void;
  onGenerateNote: () => void;
  onSectionChange: (key: string, value: string) => void;
  onSaveNoteEdits: () => void;
  onSign: () => void;
  onAmend: () => void;
  onExport: (format: ScribeExportFormat) => void;
}) {
  const editorLocked = props.signed || props.exported;
  return (
    <aside className="col-span-12 xl:col-span-4 space-y-4">
      <div className={panelPaddedClass}>
        <h3 className={sectionTitleClass}>Mẫu ghi chú</h3>
        <div className="mt-3 flex gap-2">
          <select
            value={props.templateId}
            onChange={(event) => props.onTemplateChange(event.target.value)}
            disabled={editorLocked}
            className="flex-1 rounded-lg border border-[#93C5FD] bg-white px-3 py-2 text-sm font-semibold text-[#1F2937] outline-none focus:border-[#2563EB] disabled:cursor-not-allowed disabled:bg-[#EEF2F7] dark:border-sky-700/70 dark:bg-slate-950/60 dark:text-slate-100"
            data-testid="scribe-template-picker"
          >
            {SCRIBE_REVIEW_TEMPLATES.map((template) => (
              <option key={template.id} value={template.id}>
                {template.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={props.onGenerateNote}
            disabled={props.generating || !props.transcriptReady || editorLocked}
            className={primaryButtonClass}
            data-testid="scribe-generate-note"
          >
            {props.generating ? "Đang soạn..." : "Soạn ghi chú"}
          </button>
        </div>
      </div>

      <div className={panelPaddedClass}>
        <div className="flex items-center justify-between">
          <h3 className={sectionTitleClass}>Ghi chú lâm sàng</h3>
          {editorLocked ? (
            <span className="rounded-full border border-emerald-400 bg-emerald-50 px-2 py-0.5 text-[10px] font-black uppercase text-emerald-700 dark:border-emerald-400 dark:bg-emerald-500/20 dark:text-emerald-100">
              {props.exported ? "Đã xuất bản" : "Đã ký"}
            </span>
          ) : null}
        </div>

        <div className="mt-3 space-y-3">
          {props.noteSections.length === 0 ? (
            <p className={`text-sm font-medium ${secondaryTextClass}`}>
              Chưa có ghi chú. Chọn mẫu và bấm “Soạn ghi chú”.
            </p>
          ) : (
            props.noteSections.map((section) => (
              <div key={section.key}>
                <label className="text-[10px] font-black uppercase tracking-[0.14em] text-[#2563EB] dark:text-sky-100">
                  {section.label}
                </label>
                <textarea
                  value={section.value}
                  onChange={(event) => props.onSectionChange(section.key, event.target.value)}
                  disabled={editorLocked}
                  className={`mt-1 ${sectionTextareaClass}`}
                  data-testid={`scribe-note-section-${section.key}`}
                />
              </div>
            ))
          )}
        </div>

        {props.noteReady && !editorLocked ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={props.onSaveNoteEdits} disabled={props.savingNote} className={secondaryButtonClass}>
              {props.savingNote ? "Đang lưu..." : "Lưu chỉnh sửa"}
            </button>
            <button
              type="button"
              onClick={props.onSign}
              disabled={props.signing}
              className={primaryButtonClass}
              data-testid="scribe-sign"
            >
              {props.signing ? "Đang ký..." : "Ký ghi chú"}
            </button>
          </div>
        ) : null}

        {renderGroundingPanel({
          grounding: props.grounding,
          segments: props.transcriptSegments,
          expandedStatement: props.expandedStatement,
          onToggleStatement: props.onToggleStatement,
        })}

        {editorLocked ? (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-2" data-testid="scribe-export-actions">
              {(["md", "docx", "fhir"] as ScribeExportFormat[]).map((format) => (
                <button
                  key={format}
                  type="button"
                  onClick={() => props.onExport(format)}
                  disabled={props.exportingFormat !== null}
                  className={secondaryButtonClass}
                  data-testid={`scribe-export-${format}`}
                >
                  {props.exportingFormat === format ? "Đang xuất..." : `Xuất ${format.toUpperCase()}`}
                </button>
              ))}
            </div>
            <button type="button" onClick={props.onAmend} className={`w-full ${secondaryButtonClass}`}>
              Tạo bản sửa đổi (amend)
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Grounding panel (Requirement 12.7) — per-statement grounded/unverified chips
// with transcript-span drill-down + an unverified-candidate review panel. The
// whole surface is additive: when grounding is absent (flag off / no metadata)
// `groundingHasData` is false and nothing renders, so the editor is unchanged.
// ---------------------------------------------------------------------------

function renderGroundingPanel({
  grounding,
  segments,
  expandedStatement,
  onToggleStatement,
}: {
  grounding: ScribeGroundingReport | null;
  segments: ScribeStreamSegment[];
  expandedStatement: string | null;
  onToggleStatement: (key: string) => void;
}) {
  if (!groundingHasData(grounding) || !grounding) return null;

  const { grounded, unverified } = partitionGroundingStatements(grounding);
  const significant = [...grounded, ...unverified];
  const candidates = grounding.unverified_candidates;

  return (
    <div className="mt-4 space-y-3 border-t border-[#B6D4FE] pt-4 dark:border-sky-800" data-testid="scribe-grounding">
      <div className="flex items-center justify-between gap-2">
        <h4 className={sectionTitleClass}>Đối chiếu bản ghi</h4>
        <span
          className="rounded-full border border-emerald-400 bg-emerald-50 px-2 py-0.5 text-[10px] font-black uppercase text-emerald-700 dark:border-emerald-400 dark:bg-emerald-500/20 dark:text-emerald-100"
          data-testid="scribe-grounding-rate"
        >
          {formatGroundedClaimRate(grounding.grounded_claim_rate)} có dẫn chứng
        </span>
      </div>
      <p className={`text-[11px] leading-4 ${mutedTextClass}`}>
        {grounded.length} câu có dẫn chứng · {unverified.length} câu chưa xác minh
      </p>

      {significant.length > 0 ? (
        <ul className="space-y-2" data-testid="scribe-grounding-statements">
          {significant.map((statement, index) => {
            const chip = groundingChip(statement);
            const key = `${statement.section}:${index}:${statement.statement}`;
            const open = expandedStatement === key;
            const spans = statement.supporting_span_ids.map((spanId) =>
              resolveTranscriptSpan(spanId, segments)
            );
            return (
              <li
                key={key}
                className={`rounded-lg border px-3 py-2 ${GROUNDING_CHIP_CLASSES[chip.tone]}`}
                data-testid={`scribe-grounding-statement-${chip.status}`}
              >
                <button
                  type="button"
                  onClick={() => onToggleStatement(key)}
                  className="flex w-full items-start gap-2 text-left"
                  aria-expanded={open}
                >
                  <span className="mt-0.5 shrink-0 rounded-full border border-current px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.08em]">
                    {chip.label}
                  </span>
                  <span className={`flex-1 text-sm leading-5 ${bodyTextClass}`}>
                    {statement.statement}
                    {chip.critical ? (
                      <span className="ml-1 text-[10px] font-black uppercase text-rose-600 dark:text-rose-300">
                        · an toàn
                      </span>
                    ) : null}
                  </span>
                  <span className={`mt-0.5 text-[10px] font-bold ${mutedTextClass}`}>
                    {statement.supporting_span_ids.length > 0
                      ? `${statement.supporting_span_ids.length} đoạn`
                      : open
                        ? "▲"
                        : "▾"}
                  </span>
                </button>
                {open ? (
                  <div className="mt-2 space-y-1" data-testid="scribe-grounding-spans">
                    {spans.length === 0 ? (
                      <p className={`text-[11px] italic ${mutedTextClass}`}>
                        Không có đoạn bản ghi nào hỗ trợ câu này.
                      </p>
                    ) : (
                      spans.map((span, spanIndex) => (
                        <div
                          key={`${span.spanId}-${spanIndex}`}
                          className="rounded-md border border-[#B6D4FE] bg-white/70 px-2 py-1 dark:border-sky-800 dark:bg-slate-950/50"
                        >
                          <p className={`text-[10px] font-bold uppercase tracking-[0.1em] ${mutedTextClass}`}>
                            {span.spanId}
                            {span.resolved ? ` · ${speakerChip(span.speaker).label}` : " · chưa khớp"}
                          </p>
                          <p className={`text-sm leading-5 ${secondaryTextClass}`}>
                            {span.text || "(không tìm thấy nội dung)"}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {candidates.length > 0 ? (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-3 dark:border-rose-500/70 dark:bg-rose-500/15"
          data-testid="scribe-unverified-candidates"
        >
          <h5 className="text-[11px] font-black uppercase tracking-[0.14em] text-rose-700 dark:text-rose-200">
            Cần bác sĩ xác nhận ({candidates.length})
          </h5>
          <p className={`mt-1 text-[11px] leading-4 ${secondaryTextClass}`}>
            Các phát biểu an toàn quan trọng dưới đây không có dẫn chứng trong bản ghi nên không được
            khẳng định trong ghi chú.
          </p>
          <ul className="mt-2 space-y-1">
            {candidates.map((candidate, index) => (
              <li
                key={`${index}-${candidate}`}
                className="flex gap-2 text-sm leading-5 text-rose-800 dark:text-rose-100"
              >
                <span aria-hidden className="mt-0.5 text-rose-500">
                  ⚠
                </span>
                <span>{candidate}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
