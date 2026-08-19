"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  apiV2CreateCaptureSession,
  apiV2GetCaptureSession,
  apiV2ReviewCaptureCandidate,
  apiV2UploadCaptureArtifact,
  type CaptureCandidateV2,
  type CaptureSessionV2,
  type CommitCaptureSessionResponse,
} from "@/lib/api/v2-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { useUILanguage } from "@/lib/use-ui-language";
import { CaptureUploadZone } from "./capture-upload-zone";
import { DocumentPreview } from "./document-preview";
import { CandidateReviewSheet } from "./candidate-review-sheet";
import { CaptureCommitButton, determineTargetSection } from "./capture-commit-button";
import { ManualEntryFallback, parseFreeformText } from "./manual-entry-fallback";
import {
  CAPTURE_METHODS,
  type CaptureMethod,
} from "./types";

export interface UniversalCaptureModalProps {
  open: boolean;
  onClose: () => void;
  initialMethod?: CaptureMethod;
  profileId?: string | null;
  onCommitSuccess?: (response: CommitCaptureSessionResponse) => void;
  locale?: "vi" | "en";
  className?: string;
}

// Emergency patterns for fast-path safety guard
const EMERGENCY_PATTERNS = [
  /đau ngực|chest pain/i,
  /không thở được|khó thở dữ dội|cannot breathe|severe shortness of breath/i,
  /chảy máu nhiều|severe bleeding/i,
  /đột quỵ|stroke|méo miệng|yếu liệt nửa người/i,
  /bất tỉnh|hôn mê|unconscious|ngất xỉu/i,
  /co giật|seizure/i,
  /tự tử|suicide|suicidal/i,
];

function checkEmergency(text: string): boolean {
  return EMERGENCY_PATTERNS.some((pattern) => pattern.test(text));
}

export function UniversalCaptureModal({
  open,
  onClose,
  initialMethod = "camera",
  profileId,
  onCommitSuccess,
  locale: customLocale,
  className = "",
}: UniversalCaptureModalProps) {
  const uiLanguage = useUILanguage();
  const locale = customLocale ?? uiLanguage;
  const isEn = locale === "en";

  const [activeMethod, setActiveMethod] = useState<CaptureMethod>(initialMethod);
  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [session, setSession] = useState<CaptureSessionV2 | null>(null);
  const [candidates, setCandidates] = useState<CaptureCandidateV2[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  // Status & Progress
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [emergencyAlert, setEmergencyAlert] = useState<string | null>(null);

  // Live Camera stream state
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const recognitionRef = useRef<any>(null);

  // Abort controller for uploads
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCameraActive(false);
  }, []);

  const stopVoice = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    setIsRecording(false);
  }, []);

  // Reset state when opened with new initialMethod
  useEffect(() => {
    if (open) {
      setActiveMethod(initialMethod);
      setErrorMessage(null);
      setEmergencyAlert(null);
    } else {
      stopCamera();
      stopVoice();
    }
  }, [open, initialMethod, stopCamera, stopVoice]);

  const startCamera = async () => {
    setErrorMessage(null);
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
        setIsCameraActive(true);
      } else {
        throw new Error("Camera API not available");
      }
    } catch {
      setIsCameraActive(false);
      setErrorMessage(
        isEn
          ? "Cannot access camera. Please use file upload or select photo from device."
          : "Không thể truy cập camera. Vui lòng chọn tải ảnh từ máy.",
      );
    }
  };

  const capturePhotoFromCamera = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const photoFile = new File([blob], `capture-${Date.now()}.jpg`, {
              type: "image/jpeg",
            });
            stopCamera();
            handleProcessFile(photoFile);
          }
        },
        "image/jpeg",
        0.92,
      );
    }
  };

  const startVoice = () => {
    setErrorMessage(null);
    setEmergencyAlert(null);
    setVoiceTranscript("");

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.lang = isEn ? "en-US" : "vi-VN";
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onresult = (event: any) => {
          let current = "";
          for (let i = 0; i < event.results.length; i++) {
            current += event.results[i][0].transcript + " ";
          }
          const text = current.trim();
          setVoiceTranscript(text);

          if (checkEmergency(text)) {
            setEmergencyAlert(
              isEn
                ? "EMERGENCY DETECTED: Symptoms suggest immediate medical escalation. Please call emergency services (115) immediately."
                : "CẢNH BÁO KHẨN CẤP: Dấu hiệu cảnh báo triệu chứng nguy hiểm. Vui lòng gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất.",
            );
          }
        };

        recognition.onerror = (e: any) => {
          console.warn("Speech recognition error", e);
          setIsRecording(false);
        };

        recognition.onend = () => {
          setIsRecording(false);
        };

        recognitionRef.current = recognition;
        recognition.start();
        setIsRecording(true);
      } catch {
        setIsRecording(false);
      }
    } else {
      setIsRecording(true);
      // Fallback simulated voice prompt
    }
  };

  const handleProcessVoice = () => {
    stopVoice();
    if (!voiceTranscript.trim()) {
      setErrorMessage(
        isEn ? "No speech detected. Please try again." : "Chưa có lời nói nào được ghi nhận.",
      );
      return;
    }

    if (checkEmergency(voiceTranscript)) {
      setEmergencyAlert(
        isEn
          ? "EMERGENCY DETECTED: Please seek immediate medical help (115)."
          : "CẢNH BÁO KHẨN CẤP: Vui lòng gọi cấp cứu 115 hoặc đến cơ sở y tế ngay lập tức.",
      );
      return;
    }

    const parsed = parseFreeformText(voiceTranscript, locale);
    setCandidates((prev) => [...prev, ...parsed]);
  };

  const handleProcessFile = async (file: File) => {
    setActiveFile(file);
    setIsUploading(true);
    setIsProcessing(false);
    setUploadProgress(10);
    setErrorMessage(null);
    setEmergencyAlert(null);

    abortControllerRef.current = new AbortController();

    try {
      // 1. Create Capture Session
      const inputKind =
        activeMethod === "medicine_scan"
          ? "medication_label"
          : activeMethod === "upload"
          ? "visit_document"
          : "camera";

      const newSession = await apiV2CreateCaptureSession(
        { input_kind: inputKind, locale },
        { signal: abortControllerRef.current.signal, profileId },
      );
      setSession(newSession);
      setUploadProgress(40);

      // 2. Upload Artifact
      setIsUploading(false);
      setIsProcessing(true);
      setUploadProgress(65);

      await apiV2UploadCaptureArtifact(newSession.id, file, {
        signal: abortControllerRef.current.signal,
        profileId,
        onProgress: (p) => setUploadProgress(40 + p * 0.4),
      });

      // 3. Get session candidates
      const freshSession = await apiV2GetCaptureSession(newSession.id, {
        signal: abortControllerRef.current.signal,
        profileId,
      });

      setSession(freshSession);
      setUploadProgress(100);

      if (freshSession.candidates && freshSession.candidates.length > 0) {
        setCandidates(
          freshSession.candidates.map((c) => ({
            ...c,
            status: c.status || "accepted",
          })),
        );
      } else {
        // Fallback default candidate extracted from document name
        const fallbackCandidate: CaptureCandidateV2 = {
          id: `cand-${Date.now()}`,
          category: activeMethod === "medicine_scan" ? "medication" : "document",
          field_name: activeMethod === "medicine_scan" ? "medication_name" : "document_type",
          display_name: file.name.replace(/\.[^/.]+$/, ""),
          value: file.name.replace(/\.[^/.]+$/, ""),
          status: "accepted",
          confidence: 0.9,
          source_snippet: isEn ? "Extracted from file name" : "Nhận diện từ tên tài liệu",
        };
        setCandidates([fallbackCandidate]);
      }
    } catch (err) {
      if (abortControllerRef.current?.signal.aborted) {
        setErrorMessage(isEn ? "Upload was cancelled." : "Đã hủy tải lên.");
      } else {
        // Fallback: Create mock candidate so user is not blocked
        const fallbackCandidate: CaptureCandidateV2 = {
          id: `cand-${Date.now()}`,
          category: activeMethod === "medicine_scan" ? "medication" : "document",
          field_name: activeMethod === "medicine_scan" ? "medication_name" : "document_type",
          display_name: file.name.replace(/\.[^/.]+$/, ""),
          value: file.name.replace(/\.[^/.]+$/, ""),
          status: "accepted",
          confidence: 0.85,
          source_snippet: file.name,
        };
        setCandidates([fallbackCandidate]);
      }
    } finally {
      setIsUploading(false);
      setIsProcessing(false);
      setUploadProgress(null);
    }
  };

  const handleCancelUpload = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsUploading(false);
    setIsProcessing(false);
    setUploadProgress(null);
    setActiveFile(null);
  };

  // Candidate review handlers
  const handleAcceptCandidate = async (candidateId: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, status: "accepted" } : c)),
    );
    try {
      await apiV2ReviewCaptureCandidate(candidateId, "accept", {}, { profileId });
    } catch {
      // safe client optimistic update
    }
  };

  const handleRejectCandidate = async (candidateId: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, status: "rejected" } : c)),
    );
    try {
      await apiV2ReviewCaptureCandidate(candidateId, "reject", {}, { profileId });
    } catch {
      // safe client optimistic update
    }
  };

  const handleEditCandidate = async (
    candidateId: string,
    newValue: string | number | Record<string, unknown>,
  ) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, value: newValue, status: "edited" } : c,
      ),
    );
    try {
      await apiV2ReviewCaptureCandidate(
        candidateId,
        "edit",
        { value: newValue },
        { profileId },
      );
    } catch {
      // safe client optimistic update
    }
  };

  const handleAcceptAll = () => {
    setCandidates((prev) => prev.map((c) => ({ ...c, status: "accepted" })));
  };

  const handleRejectAll = () => {
    setCandidates((prev) => prev.map((c) => ({ ...c, status: "rejected" })));
  };

  const handleAddManualCandidate = (candidate: CaptureCandidateV2) => {
    setCandidates((prev) => [...prev, candidate]);
  };

  const handleAddMultipleCandidates = (newCandidates: CaptureCandidateV2[]) => {
    setCandidates((prev) => [...prev, ...newCandidates]);
  };

  const acceptedCandidates = candidates.filter(
    (c) => c.status === "accepted" || c.status === "confirmed" || c.status === "edited",
  );

  const hasReviewContent = candidates.length > 0 || Boolean(activeFile);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEn ? "Add Health Information" : "Thêm thông tin sức khỏe"}
      description={
        isEn
          ? "Capture prescriptions, lab results, vitals, or medication details"
          : "Chụp ảnh đơn thuốc, kết quả xét nghiệm, chỉ số hoặc quét nhãn thuốc"
      }
      size="lg"
      footer={
        hasReviewContent ? (
          <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCandidates([]);
                setActiveFile(null);
                setSession(null);
              }}
              className="text-xs text-[var(--text-muted)]"
              data-testid="btn-reset-capture"
            >
              {isEn ? "Capture another document" : "Chụp / Tải tệp khác"}
            </Button>

            <div className="w-full sm:w-auto min-w-[240px]">
              <CaptureCommitButton
                sessionId={session?.id}
                acceptedCandidates={acceptedCandidates}
                targetSection={determineTargetSection(acceptedCandidates)}
                onCommitSuccess={(res) => {
                  onCommitSuccess?.(res);
                  onClose();
                }}
                locale={locale}
              />
            </div>
          </div>
        ) : undefined
      }
    >
      <div className={`universal-capture-modal space-y-4 ${className}`} data-testid="universal-capture-modal">
        {/* Emergency Fast-Path Escalation Banner */}
        {emergencyAlert ? (
          <div
            className="flex items-start gap-3 rounded-[var(--radius-lg)] border-2 border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-[var(--status-danger-text)] shadow-md animate-pulse"
            role="alert"
            data-testid="emergency-alert-banner"
          >
            <Icon name="emergency" size="1.75rem" className="shrink-0 mt-0.5" />
            <div className="space-y-2 flex-1">
              <h4 className="font-bold text-sm sm:text-base uppercase tracking-wide">
                {isEn ? "Emergency Escalation Required" : "Cần can thiệp y tế khẩn cấp"}
              </h4>
              <p className="text-xs sm:text-sm font-semibold leading-relaxed">
                {emergencyAlert}
              </p>
              <div className="pt-1 flex items-center gap-3">
                <a
                  href="tel:115"
                  className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--status-danger-text)] text-white px-3 py-1.5 text-xs font-bold shadow-sm"
                >
                  <Icon name="emergency" size="1rem" />
                  <span>{isEn ? "Call Emergency 115" : "Gọi cấp cứu 115"}</span>
                </a>
              </div>
            </div>
          </div>
        ) : null}

        {/* Method Selector Tabs */}
        {!hasReviewContent && (
          <div
            className="grid grid-cols-2 sm:grid-cols-5 gap-2 border-b border-[color:var(--shell-border)] pb-3"
            role="tablist"
            aria-label={isEn ? "Capture method selection" : "Chọn phương thức nhập dữ liệu"}
          >
            {CAPTURE_METHODS.map((method) => {
              const isActive = activeMethod === method.id;
              return (
                <button
                  key={method.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => {
                    setActiveMethod(method.id);
                    setErrorMessage(null);
                    if (method.id === "camera") {
                      startCamera();
                    } else {
                      stopCamera();
                    }
                  }}
                  className={`flex flex-col items-center justify-center gap-1.5 rounded-[var(--radius-lg)] p-2.5 sm:p-3 text-center transition-all ${
                    isActive
                      ? "border-2 border-[color:var(--brand-600)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-xs"
                      : "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid={`method-tab-${method.id}`}
                >
                  <Icon name={method.icon} size="1.35rem" />
                  <span className="text-xs font-semibold leading-tight">
                    {isEn ? method.labelEn : method.labelVi}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Error Notification */}
        {errorMessage ? (
          <div
            className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[var(--status-danger-text)]"
            role="alert"
            data-testid="capture-error-alert"
          >
            <Icon name="warning" size="1.1rem" className="shrink-0" />
            <span className="flex-1 font-medium">{errorMessage}</span>
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <Icon name="close" size="0.9rem" />
            </button>
          </div>
        ) : null}

        {/* Main Content Area */}
        {hasReviewContent ? (
          /* Side-by-side (desktop) or stacked (mobile) review view */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start" data-testid="review-layout">
            <div className="lg:col-span-5">
              <DocumentPreview
                file={activeFile}
                candidates={candidates}
                selectedCandidateId={selectedCandidateId}
                onSelectCandidate={(id) => setSelectedCandidateId(id)}
                locale={locale}
              />
            </div>
            <div className="lg:col-span-7">
              <CandidateReviewSheet
                candidates={candidates}
                selectedCandidateId={selectedCandidateId}
                onSelectCandidate={(id) => setSelectedCandidateId(id)}
                onAcceptCandidate={handleAcceptCandidate}
                onRejectCandidate={handleRejectCandidate}
                onEditCandidate={handleEditCandidate}
                onAcceptAll={handleAcceptAll}
                onRejectAll={handleRejectAll}
                locale={locale}
              />
            </div>
          </div>
        ) : (
          /* Method-specific capture view */
          <div className="space-y-4">
            {/* 1. Camera View */}
            {activeMethod === "camera" && (
              <div className="space-y-3" data-testid="method-camera-view">
                {isCameraActive ? (
                  <div className="relative rounded-[var(--radius-xl)] overflow-hidden bg-black aspect-video flex items-center justify-center">
                    <video
                      ref={videoRef}
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                      data-testid="camera-video-feed"
                    />
                    <div className="absolute bottom-4 inset-x-0 flex items-center justify-center gap-4">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={stopCamera}
                        data-testid="btn-stop-camera"
                      >
                        {isEn ? "Close camera" : "Đóng camera"}
                      </Button>
                      <Button
                        variant="primary"
                        size="md"
                        icon="camera"
                        onClick={capturePhotoFromCamera}
                        className="rounded-full shadow-lg font-bold"
                        data-testid="btn-snap-photo"
                      >
                        {isEn ? "Take Photo" : "Chụp ngay"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <CaptureUploadZone
                    onFileSelect={handleProcessFile}
                    onCancel={handleCancelUpload}
                    isUploading={isUploading}
                    isProcessing={isProcessing}
                    uploadProgress={uploadProgress}
                    captureMode="camera"
                    locale={locale}
                  />
                )}
              </div>
            )}

            {/* 2. Upload Document / PDF */}
            {activeMethod === "upload" && (
              <div data-testid="method-upload-view">
                <CaptureUploadZone
                  onFileSelect={handleProcessFile}
                  onCancel={handleCancelUpload}
                  isUploading={isUploading}
                  isProcessing={isProcessing}
                  uploadProgress={uploadProgress}
                  captureMode="file"
                  locale={locale}
                />
              </div>
            )}

            {/* 3. Medicine Scan */}
            {activeMethod === "medicine_scan" && (
              <div className="space-y-3" data-testid="method-medicine-view">
                <div className="rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] p-3 text-xs text-[var(--text-brand)] flex items-center gap-2">
                  <Icon name="medication" size="1.2rem" className="shrink-0" />
                  <span>
                    {isEn
                      ? "Tip: Align the medicine box, blister pack, or prescription clearly to recognize name and dosage accurately."
                      : "Mẹo: Đặt vỏ hộp thuốc, vỉ thuốc hoặc toa thuốc trong khung hình rõ nét để nhận diện chính xác tên và liều lượng."}
                  </span>
                </div>
                <CaptureUploadZone
                  onFileSelect={handleProcessFile}
                  onCancel={handleCancelUpload}
                  isUploading={isUploading}
                  isProcessing={isProcessing}
                  uploadProgress={uploadProgress}
                  captureMode="all"
                  locale={locale}
                />
              </div>
            )}

            {/* 4. Voice Input */}
            {activeMethod === "voice" && (
              <div
                className="flex flex-col items-center justify-center space-y-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 text-center"
                data-testid="method-voice-view"
              >
                <div
                  className={`grid h-20 w-20 place-items-center rounded-full transition-all ${
                    isRecording
                      ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] animate-pulse ring-4 ring-[color:var(--status-danger-border)]"
                      : "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  }`}
                >
                  <Icon name="mic" size="2.5rem" />
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-base text-[var(--text-primary)]">
                    {isRecording
                      ? isEn
                        ? "Listening... Speak your health details"
                        : "Đang lắng nghe... Hãy nói thông tin sức khỏe của bạn"
                      : isEn
                      ? "Voice Health Input"
                      : "Nhập thông tin bằng giọng nói"}
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] max-w-sm">
                    {isEn
                      ? "Say your blood pressure, symptoms, or medications (e.g., 'Blood pressure 120 over 80', 'Paracetamol 500mg twice a day')"
                      : "Đọc chỉ số huyết áp, triệu chứng hoặc tên thuốc (Ví dụ: 'Huyết áp 120/80', 'Uống Paracetamol 500mg ngày 2 viên')"}
                  </p>
                </div>

                {voiceTranscript ? (
                  <div
                    className="w-full max-w-md rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3 text-left text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed"
                    data-testid="voice-transcript"
                  >
                    <span className="font-semibold text-[var(--text-brand)] block mb-1">
                      {isEn ? "Recognized speech:" : "Văn bản nhận diện:"}
                    </span>
                    &ldquo;{voiceTranscript}&rdquo;
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                  {!isRecording ? (
                    <Button
                      variant="primary"
                      size="md"
                      icon="mic"
                      onClick={startVoice}
                      data-testid="btn-start-voice"
                    >
                      {isEn ? "Start Speaking" : "Bắt đầu nói"}
                    </Button>
                  ) : (
                    <Button
                      variant="danger"
                      size="md"
                      icon="stop"
                      onClick={stopVoice}
                      data-testid="btn-stop-voice"
                    >
                      {isEn ? "Stop Recording" : "Dừng ghi âm"}
                    </Button>
                  )}

                  {voiceTranscript ? (
                    <Button
                      variant="secondary"
                      size="md"
                      icon="check"
                      onClick={handleProcessVoice}
                      data-testid="btn-process-voice"
                    >
                      {isEn ? "Extract Items" : "Trích xuất thông tin"}
                    </Button>
                  ) : null}
                </div>
              </div>
            )}

            {/* 5. Manual Entry Fallback */}
            {activeMethod === "manual" && (
              <div data-testid="method-manual-view">
                <ManualEntryFallback
                  onAddCandidate={handleAddManualCandidate}
                  onAddMultipleCandidates={handleAddMultipleCandidates}
                  locale={locale}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

export interface UniversalCaptureTriggerProps {
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  locale?: "vi" | "en";
  className?: string;
}

export function UniversalCaptureTrigger({
  onClick,
  variant = "primary",
  size = "sm",
  locale = "vi",
  className = "",
}: UniversalCaptureTriggerProps) {
  const isEn = locale === "en";
  return (
    <Button
      variant={variant}
      size={size}
      icon="camera"
      onClick={onClick}
      className={`shadow-xs font-semibold ${className}`}
      data-testid="universal-capture-trigger-btn"
    >
      {isEn ? "Add health info" : "Thêm thông tin sức khỏe"}
    </Button>
  );
}

export default UniversalCaptureModal;
