"use client";

import React, { useState, useEffect } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { CaptureWave } from "../artwork/capture-wave";

export type ScribeStep = 1 | 2 | 3 | 4 | 5;

export interface ScribeDemoProps {
  className?: string;
  initialStep?: ScribeStep;
}

/**
 * ScribeDemo (Landing v7)
 *
 * 5-Step Ambient Clinical Scribe Transformation Pipeline:
 * 1. Step 01: Patient Audio Consent (Zero-CoT Security & E2EE verification)
 * 2. Step 02: Ambient Acoustic Capture (Lively CaptureWave visualizer & 48kHz noise-filtering)
 * 3. Step 03: Clinical NLP Transcript (Bilingual Vietnamese/English normalization & SNOMED CT / ICD-10 NER)
 * 4. Step 04: Structured SOAP Draft (4-Quadrant clinical notes: Subjective, Objective, Assessment, Plan)
 * 5. Step 05: Physician Review & Sign-Off (Attending Clinician verification seal & PKI EMR commit)
 */
export function ScribeDemo({ className = "", initialStep = 4 }: ScribeDemoProps) {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.scribe ?? LANDING_COPY_V7.vi.scribe;

  const [currentStep, setCurrentStep] = useState<ScribeStep>(initialStep);
  const [isRecordingActive, setIsRecordingActive] = useState(true);
  const [recordingSeconds, setRecordingSeconds] = useState(165); // 02:45
  const [isSigned, setIsSigned] = useState(false);
  const [consentAcknowledged, setConsentAcknowledged] = useState(true);
  const [selectedSoapQuadrant, setSelectedSoapQuadrant] = useState<"S" | "O" | "A" | "P" | null>(null);

  // Timer simulation during recording step
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (currentStep === 2 && isRecordingActive && !isReducedMotion) {
      interval = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentStep, isRecordingActive, isReducedMotion]);

  const formatTimer = (totalSecs: number) => {
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const stepLabels: Record<ScribeStep, { number: string; title: string; subtitle: string; icon: string }> = {
    1: {
      number: "01",
      title: copy.states.consent.title,
      subtitle: lang === "vi" ? "Đồng thuận Y tế" : "Patient Consent",
      icon: "🔒",
    },
    2: {
      number: "02",
      title: copy.states.recording.title,
      subtitle: lang === "vi" ? "Thu âm Hội thoại" : "Ambient Recording",
      icon: "🎙",
    },
    3: {
      number: "03",
      title: copy.states.transcript.title,
      subtitle: lang === "vi" ? "Biên dịch Y khoa" : "Clinical NLP",
      icon: "📝",
    },
    4: {
      number: "04",
      title: copy.states.soap.title,
      subtitle: lang === "vi" ? "Dự thảo SOAP" : "SOAP Draft",
      icon: "📋",
    },
    5: {
      number: "05",
      title: copy.states.review.title,
      subtitle: lang === "vi" ? "Ký duyệt Bác sĩ" : "Physician Review",
      icon: "✍️",
    },
  };

  return (
    <div
      data-testid="scribe-demo"
      className={`clara-product-surface relative w-full overflow-hidden p-5 sm:p-7 lg:p-9 transition-all duration-300 shadow-xl ${className}`}
    >
      {/* Scribe Header & 5-Step Transformation Stepper */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg sm:text-xl font-bold text-[#162033]">
              CLARA Ambient Clinical Scribe
            </h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
              Bilingual VN/EN • Zero-CoT
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#6D7A8E] mt-0.5">
            {lang === "vi"
              ? "Quy trình chuyển đổi 5 bước từ hội thoại trực tiếp đến bệnh án SOAP đã xác nhận"
              : "5-step pipeline transforming raw doctor-patient dialogue into structured SOAP clinical notes"}
          </p>
        </div>

        {/* 5-Step Stepper Navigation Buttons */}
        <div
          className="flex items-center gap-1 sm:gap-1.5 rounded-2xl bg-[#F1F5F9] p-1 sm:p-1.5 border border-[#E3E8EF]"
          role="tablist"
          aria-label={lang === "vi" ? "Các bước tiến trình Scribe" : "Scribe pipeline steps"}
        >
          {([1, 2, 3, 4, 5] as const).map((stepNum) => {
            const isCurrent = currentStep === stepNum;
            const isPassed = currentStep > stepNum;
            return (
              <button
                key={stepNum}
                type="button"
                role="tab"
                id={`scribe-step-tab-${stepNum}`}
                aria-selected={isCurrent}
                aria-controls={`scribe-step-panel-${stepNum}`}
                onClick={() => setCurrentStep(stepNum)}
                className={`flex items-center gap-1.5 rounded-xl px-2.5 sm:px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring cursor-pointer ${
                  isCurrent
                    ? "bg-[#14A88D] text-white shadow-sm scale-[1.02]"
                    : isPassed
                    ? "bg-white text-[#14A88D] border border-[#14A88D]/30 shadow-2xs hover:bg-[#ECFDF8]"
                    : "bg-transparent text-[#6D7A8E] hover:text-[#162033] hover:bg-white/60"
                }`}
              >
                <span>0{stepNum}</span>
                <span className="hidden md:inline text-[11px] font-medium">
                  {stepLabels[stepNum].subtitle}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Transforming Workspace Body */}
      <div className="mt-6">
        {/* Step 1: Patient Consent */}
        {currentStep === 1 && (
          <div
            id="scribe-step-panel-1"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-1"
            className="rounded-2xl bg-white p-5 sm:p-7 border border-[#E3E8EF] space-y-5 animate-fadeIn shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E3E8EF]/80 pb-3.5">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#ECFDF8] text-[#14A88D] text-xs font-bold">
                  01
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                  Bước 01 • {copy.states.consent.title}
                </span>
              </div>
              <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
                {lang === "vi" ? "Đã cấp phép điện tử" : "Consent Verified"}
              </span>
            </div>

            <p className="text-sm sm:text-base font-semibold text-[#162033] leading-relaxed">
              {copy.states.consent.desc}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1 text-xs">
              <div className="rounded-2xl bg-[#ECFDF8]/70 p-4 sm:p-5 border border-[#14A88D]/25 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold text-[#14A88D] text-xs sm:text-sm">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#14A88D] text-white text-[10px]">
                      ✓
                    </span>
                    <span>{lang === "vi" ? "Đồng thuận Ghi âm Bệnh nhân" : "Patient Audio Consent"}</span>
                  </div>
                  <span className="text-[10px] font-mono text-[#0E856F] bg-white px-2 py-0.5 rounded border border-[#14A88D]/20">
                    SIGN-2026-OK
                  </span>
                </div>
                <p className="text-[#48566A] text-xs leading-relaxed">
                  {lang === "vi"
                    ? "Bệnh nhân đã ký xác nhận qua biểu mẫu điện tử trên tablet trước khi bắt đầu buổi khám. Quyền thu hồi có hiệu lực bất cứ lúc nào."
                    : "Patient authenticated consent via electronic tablet signature prior to intake. Revocable at any point during consultation."}
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] text-[#6D7A8E]">
                  <span>{lang === "vi" ? "Xác thực chữ ký:" : "Biometric Witness:"}</span>
                  <strong className="text-[#162033] font-semibold">{lang === "vi" ? "Nguyễn Văn An (Tablet Touch ID)" : "Nguyen Van An (Tablet Touch ID)"}</strong>
                </div>
              </div>

              <div className="rounded-2xl bg-[#EFF7FF]/70 p-4 sm:p-5 border border-[#0B6FD8]/25 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold text-[#0B6FD8] text-xs sm:text-sm">
                    <span>🔒</span>
                    <span>{lang === "vi" ? "Mã hóa Đầu cuối Zero-CoT" : "Zero-CoT Security Guard"}</span>
                  </div>
                  <span className="text-[10px] font-mono text-[#0B6FD8] bg-white px-2 py-0.5 rounded border border-[#0B6FD8]/20">
                    AES-256-GCM
                  </span>
                </div>
                <p className="text-[#48566A] text-xs leading-relaxed">
                  {lang === "vi"
                    ? "Dữ liệu âm thanh được bảo vệ trong bộ nhớ cô lập (enclave), không sử dụng để huấn luyện mô hình khi chưa được phép."
                    : "Audio stream is encrypted in transit and processed within an isolated enclave with strict no-model-training guarantees."}
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] text-[#6D7A8E]">
                  <span>{lang === "vi" ? "Chuẩn bảo mật:" : "Standard:"}</span>
                  <strong className="text-[#0B6FD8] font-semibold">Decree 13/2023/ND-CP & HIPAA</strong>
                </div>
              </div>
            </div>

            {/* Interactive Consent Checkbox Confirmation */}
            <div className="rounded-xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF] flex items-center justify-between gap-3 text-xs">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={consentAcknowledged}
                  onChange={(e) => setConsentAcknowledged(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-[#14A88D] focus:ring-[#14A88D]"
                />
                <span className="text-[#334155] font-medium">
                  {lang === "vi"
                    ? "Bệnh nhân đã nghe giải thích và xác nhận đồng thuận kích hoạt ghi âm lâm sàng"
                    : "Patient acknowledges audio recording and authorizes ambient clinical transcription"}
                </span>
              </label>
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                disabled={!consentAcknowledged}
                className={`rounded-xl px-4 py-2 text-xs font-bold text-white transition-all clara-focus-ring cursor-pointer shadow-xs ${
                  consentAcknowledged
                    ? "bg-[#14A88D] hover:bg-[#0E856F] active:scale-95"
                    : "bg-slate-300 cursor-not-allowed"
                }`}
              >
                {lang === "vi" ? "Bắt đầu Ghi âm →" : "Start Recording →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Recording with Lively CaptureWave Artwork */}
        {currentStep === 2 && (
          <div
            id="scribe-step-panel-2"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-2"
            className="rounded-2xl bg-white p-5 sm:p-7 border border-[#E3E8EF] space-y-5 animate-fadeIn shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3.5">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose-50 text-rose-600 text-xs font-bold">
                  02
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-rose-600">
                  Bước 02 • {copy.states.recording.title}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsRecordingActive((prev) => !prev)}
                  className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1 text-xs font-bold border transition-all cursor-pointer ${
                    isRecordingActive
                      ? "bg-rose-50 text-rose-700 border-rose-200 shadow-xs"
                      : "bg-slate-100 text-slate-600 border-slate-200"
                  }`}
                >
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      isRecordingActive
                        ? isReducedMotion
                          ? "bg-rose-600"
                          : "bg-rose-600 animate-ping"
                        : "bg-slate-400"
                    }`}
                  />
                  <span>
                    {isRecordingActive
                      ? `${formatTimer(recordingSeconds)} • ${lang === "vi" ? "Đang thu âm đa kênh" : "Live Recording"}`
                      : `${formatTimer(recordingSeconds)} • ${lang === "vi" ? "Tạm dừng" : "Paused"}`}
                  </span>
                </button>
              </div>
            </div>

            <p className="text-sm text-[#48566A]">{copy.states.recording.desc}</p>

            {/* Integrated Vector CaptureWave Artwork */}
            <div className="my-2">
              <CaptureWave
                state="recording"
                isRecording={isRecordingActive && !isReducedMotion}
                timer={`${formatTimer(recordingSeconds)} • ${lang === "vi" ? "Đang thu âm 48kHz" : "48kHz Live Audio"}`}
                className="w-full shadow-sm"
              />
            </div>

            {/* Audio Telemetry Footer & Step Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2 text-xs text-[#6D7A8E]">
                <span className="h-2 w-2 rounded-full bg-[#14A88D] animate-pulse" />
                <span>
                  {lang === "vi"
                    ? "Bộ lọc giảm ồn y tế 48kHz & Tách kênh bác sĩ/bệnh nhân đang hoạt động"
                    : "48kHz medical acoustic noise reduction & active speaker diarization running"}
                </span>
              </div>

              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setCurrentStep(1)}
                  className="rounded-xl px-3 py-2 text-xs font-bold text-[#6D7A8E] hover:text-[#162033] hover:bg-[#F1F5F9] transition-all"
                >
                  ← {lang === "vi" ? "Quay lại" : "Back"}
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentStep(3)}
                  className="rounded-xl bg-[#0B6FD8] px-4 py-2 text-xs font-bold text-white hover:bg-[#084C99] transition-all clara-focus-ring cursor-pointer shadow-xs active:scale-95"
                >
                  {lang === "vi" ? "Chuyển thành Văn bản →" : "Generate Transcript →"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Bilingual Medical NLP Transcript */}
        {currentStep === 3 && (
          <div
            id="scribe-step-panel-3"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-3"
            className="rounded-2xl bg-white p-5 sm:p-7 border border-[#E3E8EF] space-y-5 animate-fadeIn shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3.5">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#EFF7FF] text-[#0B6FD8] text-xs font-bold">
                  03
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                  Bước 03 • {copy.states.transcript.title}
                </span>
              </div>
              <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                {lang === "vi" ? "Nhận diện Thực thể Y khoa (NER)" : "Medical NER Extraction"}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-[#6D7A8E]">{copy.states.transcript.desc}</p>

            {/* Formatted Bilingual Transcript Dialogue */}
            <div className="rounded-2xl bg-[#F8FAFD] p-4 sm:p-6 border border-[#E3E8EF] space-y-3.5 font-sans text-xs text-[#162033] leading-relaxed">
              {/* Doctor Turn 1 */}
              <div className="flex items-start gap-3 rounded-xl bg-white p-3 border border-[#E3E8EF]/60 shadow-2xs">
                <span className="rounded-lg bg-[#EFF7FF] px-2.5 py-1 font-bold text-[#0B6FD8] shrink-0 text-xs">
                  {lang === "vi" ? "Bác sĩ" : "Doctor"}
                </span>
                <div className="space-y-1 flex-1">
                  <p className="text-[#162033] font-medium">
                    {lang === "vi"
                      ? "Bác thấy cơn đau tức ngực xuất hiện lúc nào và kéo dài bao lâu?"
                      : "When do you notice the chest tightness, and how long does each episode last?"}
                  </p>
                  <span className="inline-block text-[10px] font-mono text-[#6D7A8E]">00:14 • Clinician Audio Channel</span>
                </div>
              </div>

              {/* Patient Turn 1 */}
              <div className="flex items-start gap-3 rounded-xl bg-[#ECFDF8]/60 p-3 border border-[#14A88D]/20 shadow-2xs">
                <span className="rounded-lg bg-[#ECFDF8] px-2.5 py-1 font-bold text-[#14A88D] shrink-0 text-xs">
                  {lang === "vi" ? "Bệnh nhân" : "Patient"}
                </span>
                <div className="space-y-1.5 flex-1">
                  <p className="text-[#334155] leading-relaxed">
                    {lang === "vi"
                      ? "Dạ thường là lúc tôi leo cầu thang lên tầng 2 hoặc xách đồ nặng. Cảm giác đau thắt đè nặng vùng ngực trái khoảng 3 phút, khi ngồi nghỉ thì dịu bớt."
                      : "Usually when climbing stairs to the second floor or lifting groceries. It feels like a heavy squeezing pressure over my left chest for about 3 minutes, which eases after resting."}
                  </p>
                  {/* Extracted Clinical Tag */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
                      SNOMED: 426396005 (Retrosternal chest pain on exertion)
                    </span>
                    <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold text-[#8B7CF6] border border-[#8B7CF6]/20">
                      Duration: ~3 mins
                    </span>
                  </div>
                </div>
              </div>

              {/* Doctor Turn 2 */}
              <div className="flex items-start gap-3 rounded-xl bg-white p-3 border border-[#E3E8EF]/60 shadow-2xs">
                <span className="rounded-lg bg-[#EFF7FF] px-2.5 py-1 font-bold text-[#0B6FD8] shrink-0 text-xs">
                  {lang === "vi" ? "Bác sĩ" : "Doctor"}
                </span>
                <div className="space-y-1.5 flex-1">
                  <p className="text-[#162033] font-medium">
                    {lang === "vi"
                      ? "Huyết áp đo tại phòng khám hiện tại là 135/85 mmHg, tim đều. Tôi sẽ chỉ định điện tâm đồ gắng sức và siêu âm tim để tầm soát mạch vành."
                      : "In-clinic blood pressure is 135/85 mmHg with regular heart sounds. I will order an Exercise Stress ECG and Doppler echocardiogram to evaluate coronary perfusion."}
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    <span className="rounded bg-[#EFF7FF] px-2 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                      Vital: BP 135/85 mmHg
                    </span>
                    <span className="rounded bg-[#FFFBEB] px-2 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
                      Orders: Stress ECG + Echo
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Transcript Actions & Step Transition */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <span className="text-xs text-[#6D7A8E]">
                {lang === "vi" ? "Chuẩn hóa thuật ngữ SNOMED CT / ICD-10 tự động" : "Normalized against SNOMED CT & ICD-10"}
              </span>
              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setCurrentStep(2)}
                  className="rounded-xl px-3 py-2 text-xs font-bold text-[#6D7A8E] hover:text-[#162033] hover:bg-[#F1F5F9] transition-all"
                >
                  ← {lang === "vi" ? "Quay lại" : "Back"}
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentStep(4)}
                  className="rounded-xl bg-[#14A88D] px-4 py-2 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring cursor-pointer shadow-xs active:scale-95"
                >
                  {lang === "vi" ? "Trích xuất Dự thảo SOAP →" : "Synthesize SOAP Draft →"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Structured SOAP Draft */}
        {currentStep === 4 && (
          <div
            id="scribe-step-panel-4"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-4"
            className="rounded-2xl bg-white p-5 sm:p-7 border border-[#E3E8EF] space-y-5 animate-fadeIn shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF] pb-3.5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#ECFDF8] text-[#14A88D] text-xs font-bold">
                    04
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                    Bước 04 • {copy.states.soap.title}
                  </span>
                </div>
                <p className="text-xs text-[#6D7A8E] mt-0.5">{copy.states.soap.desc}</p>
              </div>
              <span className="rounded-md bg-[#EFF7FF] px-2.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                {lang === "vi" ? "Bệnh án cấu trúc SOAP" : "Structured SOAP Protocol"}
              </span>
            </div>

            {/* 4-Quadrant SOAP Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              {/* S: Subjective */}
              <div
                onClick={() => setSelectedSoapQuadrant(selectedSoapQuadrant === "S" ? null : "S")}
                className={`rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border transition-all duration-200 cursor-pointer space-y-2 shadow-2xs ${
                  selectedSoapQuadrant === "S"
                    ? "border-[#0B6FD8] ring-2 ring-[#0B6FD8]/20 bg-[#EFF7FF]/30"
                    : "border-[#E3E8EF] hover:border-[#0B6FD8]/40"
                }`}
              >
                <div className="flex items-center justify-between border-b border-[#0B6FD8]/15 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#0B6FD8] text-white text-xs font-black">
                      S
                    </span>
                    <strong className="text-[#0B6FD8] font-bold text-xs uppercase tracking-wide">
                      S — Subjective ({lang === "vi" ? "Chủ quan" : "History of Present Illness"})
                    </strong>
                  </div>
                  <span className="text-[10px] font-semibold text-[#0B6FD8] bg-[#EFF7FF] px-2 py-0.5 rounded-full border border-[#0B6FD8]/20">
                    {lang === "vi" ? "Triệu chứng cơ năng" : "Symptoms"}
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.s}</p>
                <div className="pt-1 flex items-center gap-2 text-[10px] text-[#6D7A8E]">
                  <span>Khớp nguồn: Lời kể bệnh nhân (00:14)</span>
                  <span className="text-[#0B6FD8] font-bold">100% Verified</span>
                </div>
              </div>

              {/* O: Objective */}
              <div
                onClick={() => setSelectedSoapQuadrant(selectedSoapQuadrant === "O" ? null : "O")}
                className={`rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border transition-all duration-200 cursor-pointer space-y-2 shadow-2xs ${
                  selectedSoapQuadrant === "O"
                    ? "border-[#14A88D] ring-2 ring-[#14A88D]/20 bg-[#ECFDF8]/30"
                    : "border-[#E3E8EF] hover:border-[#14A88D]/40"
                }`}
              >
                <div className="flex items-center justify-between border-b border-[#14A88D]/15 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#14A88D] text-white text-xs font-black">
                      O
                    </span>
                    <strong className="text-[#14A88D] font-bold text-xs uppercase tracking-wide">
                      O — Objective ({lang === "vi" ? "Khách quan" : "Clinical Examination"})
                    </strong>
                  </div>
                  <span className="text-[10px] font-semibold text-[#14A88D] bg-[#ECFDF8] px-2 py-0.5 rounded-full border border-[#14A88D]/20">
                    {lang === "vi" ? "Thực thể & Sinh hiệu" : "Physical & Vitals"}
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.o}</p>
                <div className="pt-1 flex items-center gap-2 text-[10px] text-[#6D7A8E]">
                  <span>Sinh hiệu: HA 135/85 mmHg • Nhịp tim 76 bpm</span>
                  <span className="text-[#14A88D] font-bold">In-Clinic</span>
                </div>
              </div>

              {/* A: Assessment */}
              <div
                onClick={() => setSelectedSoapQuadrant(selectedSoapQuadrant === "A" ? null : "A")}
                className={`rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border transition-all duration-200 cursor-pointer space-y-2 shadow-2xs ${
                  selectedSoapQuadrant === "A"
                    ? "border-[#8B7CF6] ring-2 ring-[#8B7CF6]/20 bg-[#F5F3FF]/30"
                    : "border-[#E3E8EF] hover:border-[#8B7CF6]/40"
                }`}
              >
                <div className="flex items-center justify-between border-b border-[#8B7CF6]/15 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#8B7CF6] text-white text-xs font-black">
                      A
                    </span>
                    <strong className="text-[#8B7CF6] font-bold text-xs uppercase tracking-wide">
                      A — Assessment ({lang === "vi" ? "Đánh giá sơ bộ" : "Clinical Impression"})
                    </strong>
                  </div>
                  <span className="text-[10px] font-semibold text-[#8B7CF6] bg-[#F5F3FF] px-2 py-0.5 rounded-full border border-[#8B7CF6]/20">
                    {lang === "vi" ? "Chẩn đoán sơ bộ" : "ICD-10 (I20.9)"}
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.a}</p>
                <div className="pt-1 flex items-center gap-2 text-[10px] text-[#6D7A8E]">
                  <span>Mã hóa: ICD-10 I20.9 (Angina pectoris, unspecified)</span>
                  <span className="text-[#8B7CF6] font-bold">CCS Class II</span>
                </div>
              </div>

              {/* P: Plan */}
              <div
                onClick={() => setSelectedSoapQuadrant(selectedSoapQuadrant === "P" ? null : "P")}
                className={`rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border transition-all duration-200 cursor-pointer space-y-2 shadow-2xs ${
                  selectedSoapQuadrant === "P"
                    ? "border-amber-600 ring-2 ring-amber-500/20 bg-amber-50/30"
                    : "border-[#E3E8EF] hover:border-amber-500/40"
                }`}
              >
                <div className="flex items-center justify-between border-b border-amber-600/15 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-600 text-white text-xs font-black">
                      P
                    </span>
                    <strong className="text-amber-700 font-bold text-xs uppercase tracking-wide">
                      P — Plan ({lang === "vi" ? "Kế hoạch xử trí" : "Diagnostic & Care Plan"})
                    </strong>
                  </div>
                  <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                    {lang === "vi" ? "Chỉ định & Đơn thuốc" : "Care Plan"}
                  </span>
                </div>
                <p className="text-[#162033] font-medium leading-relaxed">{copy.states.soap.p}</p>
                <div className="pt-1 flex items-center gap-2 text-[10px] text-[#6D7A8E]">
                  <span>Chỉ định: Điện tâm đồ gắng sức • Siêu âm tim Doppler</span>
                  <span className="text-amber-700 font-bold">Tái khám 7 ngày</span>
                </div>
              </div>
            </div>

            {/* Step 4 Footer Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <span className="text-xs text-[#6D7A8E]">
                {lang === "vi"
                  ? "Bản nháp tự động — Chờ Bác sĩ điều trị kiểm tra & ký duyệt"
                  : "Automated draft — Pending Attending Physician review & signature"}
              </span>
              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setCurrentStep(3)}
                  className="rounded-xl px-3 py-2 text-xs font-bold text-[#6D7A8E] hover:text-[#162033] hover:bg-[#F1F5F9] transition-all"
                >
                  ← {lang === "vi" ? "Quay lại" : "Back"}
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentStep(5)}
                  className="rounded-xl bg-[#14A88D] px-4 py-2 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring cursor-pointer shadow-xs active:scale-95"
                >
                  {lang === "vi" ? "Tiến hành Ký duyệt →" : "Proceed to Sign-Off →"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Review & Sign-Off by Attending Physician with Verification Seal */}
        {currentStep === 5 && (
          <div
            id="scribe-step-panel-5"
            role="tabpanel"
            aria-labelledby="scribe-step-tab-5"
            className="rounded-2xl bg-white p-5 sm:p-7 border border-[#E3E8EF] space-y-5 animate-fadeIn shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF] pb-3.5">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#ECFDF8] text-[#14A88D] text-xs font-bold">
                  05
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                  Bước 05 • {copy.states.review.title}
                </span>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-bold border transition-all ${
                  isSigned
                    ? "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/30"
                    : "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/25"
                }`}
              >
                {isSigned
                  ? lang === "vi"
                    ? "✓ ĐÃ KÝ DUYỆT & ĐỒNG BỘ EMR"
                    : "✓ SIGNED & COMMITTED TO EMR"
                  : copy.states.review.status}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-[#48566A]">{copy.states.review.desc}</p>

            {/* Attending Physician Certification Box & Digital Seal */}
            <div className="rounded-2xl bg-gradient-to-br from-[#F8FAFD] to-[#EFF7FF]/40 p-5 sm:p-6 border border-[#E3E8EF] space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8] block">
                    {lang === "vi" ? "Bác sĩ Phụ trách Lâm sàng" : "Attending Clinical Physician"}
                  </span>
                  <h4 className="text-base font-bold text-[#162033]">
                    BS. CKI Nguyễn Minh Tuấn
                  </h4>
                  <p className="text-xs text-[#6D7A8E]">
                    Khoa Nội Tim mạch • Bệnh viện Đại học Y Dược TP.HCM
                  </p>
                </div>

                {/* Official Attending Physician Verification Seal Badge */}
                <div className="shrink-0 flex items-center gap-3">
                  <div
                    className={`flex items-center gap-2.5 rounded-2xl p-3 border transition-all duration-300 ${
                      isSigned
                        ? "bg-[#ECFDF8] border-[#14A88D]/40 shadow-sm ring-2 ring-[#14A88D]/20"
                        : "bg-white border-[#E3E8EF] shadow-2xs"
                    }`}
                  >
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl font-bold text-sm text-white transition-colors duration-300 ${
                        isSigned ? "bg-[#14A88D]" : "bg-slate-400"
                      }`}
                    >
                      {isSigned ? "✓" : "✍️"}
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] block">
                        Chứng thư số PKI
                      </span>
                      <span className="text-xs font-mono font-bold text-[#162033]">
                        CA-MED-9948-VN
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Clinician Certification Statement */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-2xs">
                <p className="text-xs text-[#48566A] italic leading-relaxed">
                  {lang === "vi"
                    ? "«Tôi xác nhận đã kiểm tra nội dung bệnh án SOAP, đối chiếu triệu chứng thực tế của bệnh nhân và đồng ý lưu trữ vào hồ sơ bệnh án điện tử (EMR/FHIR).»"
                    : "«I certify that I have reviewed this SOAP clinical note against direct patient examination and authorize its synchronization into the electronic medical record (EMR/FHIR).»"}
                </p>
              </div>

              {/* Integrity Hash / Metadata */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#6D7A8E] pt-1">
                <span>
                  {lang === "vi" ? "Mã băm toàn vẹn (SHA-256):" : "Integrity Hash (SHA-256):"}{" "}
                  <strong className="font-mono text-[#0B6FD8]">e3b0c442...98fc1c14</strong>
                </span>
                <span className="font-semibold text-[#14A88D]">
                  {isSigned
                    ? lang === "vi"
                      ? "Đã lưu vào EMR (FHIR v4)"
                      : "Stored in EMR (FHIR v4)"
                    : lang === "vi"
                    ? "Chờ xác nhận"
                    : "Awaiting Commit"}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsSigned(true)}
                className={`rounded-xl px-5 py-2.5 text-xs font-bold text-white transition-all clara-focus-ring shadow-sm cursor-pointer ${
                  isSigned
                    ? "bg-[#0E856F] ring-2 ring-[#14A88D]/40"
                    : "bg-[#14A88D] hover:bg-[#0E856F] active:scale-95"
                }`}
              >
                {isSigned
                  ? lang === "vi"
                    ? "✓ Đã ký duyệt thành công"
                    : "✓ Signed Successfully"
                  : lang === "vi"
                  ? "Ký số & Đồng bộ EMR"
                  : "Sign Digitally & Commit to EMR"}
              </button>

              <button
                type="button"
                onClick={() => setCurrentStep(4)}
                className="rounded-xl bg-[#F1F5F9] px-4 py-2.5 text-xs font-bold text-[#48566A] hover:bg-[#E3E8EF] hover:text-[#162033] transition-all clara-focus-ring cursor-pointer"
              >
                {lang === "vi" ? "Chỉnh sửa bản nháp" : "Edit SOAP Draft"}
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsSigned(false);
                  setCurrentStep(1);
                }}
                className="rounded-xl bg-transparent px-3 py-2.5 text-xs font-medium text-[#6D7A8E] hover:text-[#162033] transition-all cursor-pointer"
              >
                {lang === "vi" ? "Khởi tạo ca mới" : "Start New Encounter"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ScribeDemo;
