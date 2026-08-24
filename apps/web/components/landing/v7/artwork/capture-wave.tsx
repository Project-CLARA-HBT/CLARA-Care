"use client";

import React, { useId, useMemo } from "react";

export type ScribeState = "consent" | "recording" | "transcript" | "soap" | "review";

export interface CaptureWaveProps {
  /**
   * Scribe pipeline state:
   * - "consent": Patient electronic consent & recording boundary verification
   * - "recording": Active ambient acoustic capture with real-time waveform oscillations
   * - "transcript": Standardized bilingual clinical transcript synthesis
   * - "soap": Document fold transformation guide (Subjective, Objective, Assessment, Plan)
   * - "review": Physician verification seal and digital sign-off
   */
  state?: ScribeState;
  /**
   * Explicit recording active flag. Defaults to true when state === "recording" or active === true.
   */
  isRecording?: boolean;
  /**
   * Additional CSS class names.
   */
  className?: string;
  /**
   * Optional step number (1: consent, 2: recording, 3: transcript, 4: soap, 5: review).
   */
  step?: 1 | 2 | 3 | 4 | 5 | number;
  /**
   * Optional active motion state indicator.
   */
  active?: boolean;
  /**
   * Optional custom timer string (e.g. "02:45 • Đang thu âm").
   */
  timer?: string;
  /**
   * Optional inline styles.
   */
  style?: React.CSSProperties;
  /**
   * Optional accessible label for the artwork container.
   */
  ariaLabel?: string;
  /**
   * Optional callback when an interactive state tab or node is selected.
   */
  onStateChange?: (state: ScribeState) => void;
}

const STEP_TO_STATE: Record<number, ScribeState> = {
  1: "consent",
  2: "recording",
  3: "transcript",
  4: "soap",
  5: "review",
};

const STATE_METADATA: Record<
  ScribeState,
  {
    step: string;
    stepNumber: number;
    titleVi: string;
    titleEn: string;
    descVi: string;
    descEn: string;
    badgeTextVi: string;
    badgeTextEn: string;
    accentColor: string;
    badgeBg: string;
    badgeBorder: string;
  }
> = {
  consent: {
    step: "01",
    stepNumber: 1,
    titleVi: "Xác nhận đồng thuận",
    titleEn: "Patient Consent Verification",
    descVi: "Bệnh nhân đồng ý ghi âm bảo mật với mã hóa đầu cuối E2EE.",
    descEn: "Patient confirms secure recording consent with end-to-end encryption.",
    badgeTextVi: "Đã xác thực đồng thuận",
    badgeTextEn: "Consent Verified",
    accentColor: "#14A88D",
    badgeBg: "rgba(20, 168, 141, 0.08)",
    badgeBorder: "rgba(20, 168, 141, 0.25)",
  },
  recording: {
    step: "02",
    stepNumber: 2,
    titleVi: "Ghi âm hội thoại",
    titleEn: "Ambient Acoustic Capture",
    descVi: "Thu âm giọng nói trực tiếp tại phòng khám với bộ lọc giảm ồn y tế 48kHz.",
    descEn: "Live clinical dialogue recording with 48kHz medical noise-suppression array.",
    badgeTextVi: "02:45 • Đang thu âm đa kênh",
    badgeTextEn: "02:45 • Live Multichannel Audio",
    accentColor: "#E11D48",
    badgeBg: "rgba(225, 29, 72, 0.08)",
    badgeBorder: "rgba(225, 29, 72, 0.25)",
  },
  transcript: {
    step: "03",
    stepNumber: 3,
    titleVi: "Biên dịch y khoa",
    titleEn: "Clinical Transcription",
    descVi: "Tự động chuẩn hóa thuật ngữ lâm sàng tiếng Việt và tiếng Anh.",
    descEn: "Automated standardization of Vietnamese and English clinical terminology.",
    badgeTextVi: "Chuẩn hóa thuật ngữ VN/EN",
    badgeTextEn: "Bilingual Terminology Mapping",
    accentColor: "#0B6FD8",
    badgeBg: "rgba(11, 111, 216, 0.08)",
    badgeBorder: "rgba(11, 111, 216, 0.25)",
  },
  soap: {
    step: "04",
    stepNumber: 4,
    titleVi: "Dự thảo bệnh án SOAP",
    titleEn: "SOAP Transformation Guide",
    descVi: "Tự động gấp nếp và trích xuất 4 phân hệ: Subjective, Objective, Assessment, Plan.",
    descEn: "Document transformation origami folding into Subjective, Objective, Assessment, Plan.",
    badgeTextVi: "Cấu trúc SOAP 4 Phân hệ",
    badgeTextEn: "4-Quadrant SOAP Structure",
    accentColor: "#8B7CF6",
    badgeBg: "rgba(139, 124, 246, 0.08)",
    badgeBorder: "rgba(139, 124, 246, 0.25)",
  },
  review: {
    step: "05",
    stepNumber: 5,
    titleVi: "Bác sĩ xem xét & Ký duyệt",
    titleEn: "Physician Review & Sign",
    descVi: "Bác sĩ chỉnh sửa, xác nhận và ký duyệt bệnh án trước khi lưu vào EMR/FHIR.",
    descEn: "Physician reviews, validates, and signs structured note before EMR export.",
    badgeTextVi: "Sẵn sàng duyệt ký bởi BS",
    badgeTextEn: "Ready for Physician Sign-off",
    accentColor: "#14A88D",
    badgeBg: "rgba(20, 168, 141, 0.08)",
    badgeBorder: "rgba(20, 168, 141, 0.25)",
  },
};

// Subtle 10-bar acoustic waveform configuration (8-12 bars required)
const WAVEFORM_BARS = [
  { id: "bar-1", height: 16, delay: "0.1s", label: "125Hz" },
  { id: "bar-2", height: 28, delay: "0.3s", label: "250Hz" },
  { id: "bar-3", height: 42, delay: "0.2s", label: "500Hz" },
  { id: "bar-4", height: 22, delay: "0.45s", label: "1kHz" },
  { id: "bar-5", height: 50, delay: "0.15s", label: "2kHz" },
  { id: "bar-6", height: 38, delay: "0.35s", label: "4kHz" },
  { id: "bar-7", height: 54, delay: "0.25s", label: "8kHz" },
  { id: "bar-8", height: 32, delay: "0.5s", label: "12kHz" },
  { id: "bar-9", height: 44, delay: "0.18s", label: "16kHz" },
  { id: "bar-10", height: 20, delay: "0.4s", label: "20kHz" },
];

/**
 * CaptureWave Artwork Component (Landing v7)
 *
 * Renders Scribe's ambient acoustic waveform and document fold transformation guide:
 * 1. Acoustic Waveform: 10 dynamic spectrum bars with subtle oscillation during recording.
 * 2. Document Fold Guide: Isometric origami transformation plane folding clinical speech into 4 SOAP quadrants.
 * 3. Supports all 5 Scribe lifecycle states: Consent -> Recording -> Transcript -> SOAP Draft -> Review.
 * 4. Responsive vector SVG + CSS with Lite/Reduced Motion tier support.
 */
export function CaptureWave({
  state,
  isRecording,
  className = "",
  step,
  active,
  timer,
  style,
  ariaLabel,
  onStateChange,
}: CaptureWaveProps) {
  const rawId = useId();
  const uid = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  // Resolve current state
  const validStates: ScribeState[] = ["consent", "recording", "transcript", "soap", "review"];
  let resolvedState: ScribeState = "recording";
  if (state && validStates.includes(state)) {
    resolvedState = state;
  } else if (step && STEP_TO_STATE[step]) {
    resolvedState = STEP_TO_STATE[step];
  }

  // Resolve recording flag
  const effectiveIsRecording =
    isRecording !== undefined
      ? Boolean(isRecording)
      : active !== undefined
      ? Boolean(active) && resolvedState === "recording"
      : resolvedState === "recording";

  const meta = STATE_METADATA[resolvedState];
  const displayBadgeText = timer || meta.badgeTextVi;

  // SVG Unique Filter/Gradient IDs
  const gradWaveformId = `capture-wave-grad-wave-${uid}`;
  const gradDocumentPlaneId = `capture-wave-grad-doc-${uid}`;
  const gradFoldCreaseId = `capture-wave-grad-crease-${uid}`;
  const gradAcousticAuraId = `capture-wave-grad-aura-${uid}`;
  const gradSoapQuadrantS = `capture-wave-soap-s-${uid}`;
  const gradSoapQuadrantO = `capture-wave-soap-o-${uid}`;
  const gradSoapQuadrantA = `capture-wave-soap-a-${uid}`;
  const gradSoapQuadrantP = `capture-wave-soap-p-${uid}`;
  const filterGlowMintId = `capture-wave-glow-mint-${uid}`;
  const filterGlowAzureId = `capture-wave-glow-azure-${uid}`;
  const filterDropShadowDocId = `capture-wave-shadow-doc-${uid}`;

  const ariaDescription = useMemo(() => {
    switch (resolvedState) {
      case "consent":
        return "Bảo mật & Đồng thuận: Bệnh nhân đã xác nhận đồng thuận ghi âm y khoa.";
      case "recording":
        return "Thu âm hội thoại lâm sàng với dạng sóng âm học 10 dải tần.";
      case "transcript":
        return "Biên dịch luồng hội thoại thành văn bản chuẩn hóa thuật ngữ song ngữ.";
      case "soap":
        return "Hướng dẫn chuyển đổi nếp gấp tài liệu: Phân bổ vào 4 phân hệ bệnh án SOAP.";
      case "review":
        return "Xem xét và ký duyệt bệnh án cấu trúc hoàn chỉnh.";
    }
  }, [resolvedState]);

  return (
    <div
      data-testid="capture-wave"
      data-artwork="capture-wave"
      data-state={resolvedState}
      data-recording={String(effectiveIsRecording)}
      className={`relative w-full overflow-hidden rounded-3xl border border-[#E3E8EF] bg-gradient-to-b from-[#FFFFFF] via-[#F8FAFD] to-[#F1F5F9] p-4 sm:p-6 lg:p-8 shadow-xl transition-all duration-300 ${className}`}
      style={style}
    >
      {/* Top Visual Telemetry Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-xl text-xs font-black text-white shadow-xs transition-colors duration-300"
            style={{ backgroundColor: meta.accentColor }}
          >
            {resolvedState === "recording" ? "🎙" : resolvedState === "soap" ? "📄" : "✦"}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                CLARA Ambient Scribe • {meta.titleVi}
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold border transition-colors duration-300"
                style={{
                  backgroundColor: meta.badgeBg,
                  color: meta.accentColor,
                  borderColor: meta.badgeBorder,
                }}
              >
                Bước {meta.step} / 05
              </span>
            </div>
            <p className="text-[11px] text-[#6D7A8E]">{meta.descVi}</p>
          </div>
        </div>

        {/* 5-Stage Stepper Navigation */}
        <div
          className="flex items-center gap-1 rounded-xl bg-[#EFF4FA] p-1 border border-[#E3E8EF]"
          role="tablist"
          aria-label="Scribe Transformation Stages"
        >
          {(["consent", "recording", "transcript", "soap", "review"] as const).map((stepKey) => {
            const stepMeta = STATE_METADATA[stepKey];
            const isCurrent = resolvedState === stepKey;
            const isPassed = meta.stepNumber > stepMeta.stepNumber;

            return (
              <button
                key={stepKey}
                type="button"
                role="tab"
                aria-selected={isCurrent}
                onClick={() => onStateChange?.(stepKey)}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all ${
                  isCurrent
                    ? "bg-white text-[#162033] shadow-xs scale-102"
                    : isPassed
                    ? "text-[#14A88D] hover:text-[#0E856F]"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    isCurrent
                      ? "bg-[#14A88D] animate-pulse"
                      : isPassed
                      ? "bg-[#14A88D]/60"
                      : "bg-[#6D7A8E]/40"
                  }`}
                />
                <span>{stepMeta.step}</span>
                <span className="hidden md:inline">
                  {stepKey === "consent"
                    ? "Đồng thuận"
                    : stepKey === "recording"
                    ? "Ghi âm"
                    : stepKey === "transcript"
                    ? "Biên dịch"
                    : stepKey === "soap"
                    ? "SOAP"
                    : "Ký duyệt"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main SVG Transformation Stage */}
      <div className="relative aspect-[16/9] w-full min-h-[320px] max-h-[500px]">
        <svg
          viewBox="0 0 920 440"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full select-none"
          role="img"
          aria-label={ariaLabel || `Minh họa âm học và hướng dẫn chuyển đổi SOAP Scribe - ${ariaDescription}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <title>CLARA Scribe Capture Wave & Document Fold Guide</title>
          <desc>
            Ambient acoustic capture wave propagating through clinical speech processing and folding into
            a structured 4-quadrant SOAP document.
          </desc>

          <defs>
            {/* Waveform Gradient */}
            <linearGradient id={gradWaveformId} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#14A88D" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="1" />
            </linearGradient>

            {/* Acoustic Microphone Aura Gradient */}
            <radialGradient id={gradAcousticAuraId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.3" />
              <stop offset="45%" stopColor="#0B6FD8" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0" />
            </radialGradient>

            {/* Document Base Plane Gradient */}
            <linearGradient id={gradDocumentPlaneId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="100%" stopColor="#F8FAFD" />
            </linearGradient>

            {/* Origami Fold Crease Gradient */}
            <linearGradient id={gradFoldCreaseId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#8B7CF6" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.1" />
            </linearGradient>

            {/* SOAP Quadrant Gradients */}
            <linearGradient id={gradSoapQuadrantS} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#EFF7FF" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.95" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantO} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#ECFDF8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.95" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantA} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#F5F3FF" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.95" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantP} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FFFBEB" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.95" />
            </linearGradient>

            {/* Glow and Drop Shadow Filters */}
            <filter id={filterGlowMintId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            <filter id={filterGlowAzureId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            <filter id={filterDropShadowDocId} x="-10%" y="-10%" width="125%" height="125%">
              <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#162033" floodOpacity="0.08" />
            </filter>
          </defs>

          {/* Background Grid & Spatial Matrix */}
          <g id="spatial-grid-matrix" opacity="0.45">
            <line x1="40" y1="220" x2="880" y2="220" stroke="#E3E8EF" strokeDasharray="4 4" />
            <line x1="480" y1="30" x2="480" y2="410" stroke="#E3E8EF" strokeDasharray="4 4" />
            <circle cx="210" cy="220" r="160" stroke="#EDF2F7" strokeWidth="1" />
            <circle cx="210" cy="220" r="110" stroke="#EDF2F7" strokeWidth="1" />
            <circle cx="210" cy="220" r="60" stroke="#EDF2F7" strokeWidth="1" />
          </g>

          {/* SECTION 1: ACOUSTIC CAPTURE WAVEFORM (Left Zone: x: 40 to 440) */}
          <g
            id="ambient-acoustic-waveform-system"
            className="transition-opacity duration-500"
            opacity={resolvedState === "consent" ? 0.45 : 1}
          >
            {/* Microphone Capture Node */}
            <g id="mic-capture-core" transform="translate(100, 220)">
              {/* Radial Propagation Rings */}
              {effectiveIsRecording && (
                <>
                  <circle
                    r="46"
                    fill="none"
                    stroke="#14A88D"
                    strokeWidth="1.5"
                    strokeOpacity="0.4"
                    className="motion-safe:animate-ping motion-reduce:animate-none"
                    style={{ transformOrigin: "0 0", animationDuration: "3s" }}
                  />
                  <circle
                    r="32"
                    fill="none"
                    stroke="#0B6FD8"
                    strokeWidth="1.5"
                    strokeOpacity="0.5"
                    className="motion-safe:animate-ping motion-reduce:animate-none"
                    style={{ transformOrigin: "0 0", animationDuration: "2s" }}
                  />
                </>
              )}

              {/* Ambient Aura */}
              <circle r="36" fill={`url(#${gradAcousticAuraId})`} />

              {/* Outer Core Pill */}
              <rect
                x="-16"
                y="-22"
                width="32"
                height="44"
                rx="16"
                fill={resolvedState === "recording" ? "#FFF1F2" : "#ECFDF8"}
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="2"
              />

              {/* Mic Mesh Lines */}
              <line
                x1="-8"
                y1="-8"
                x2="8"
                y2="-8"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
              />
              <line
                x1="-8"
                y1="-2"
                x2="8"
                y2="-2"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
              />
              <line
                x1="-8"
                y1="4"
                x2="8"
                y2="4"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
              />

              {/* Live Audio Telemetry Dot */}
              <circle
                cx="0"
                cy="12"
                r="3"
                fill={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                className={resolvedState === "recording" ? "motion-safe:animate-pulse" : ""}
              />
            </g>

            {/* 10-Bar Ambient Acoustic Waveform Spectrum (8-12 bars required) */}
            <g id="acoustic-spectrum-bars" transform="translate(160, 220)">
              {WAVEFORM_BARS.map((bar, index) => {
                const barX = index * 24;
                const barHeight = effectiveIsRecording ? bar.height : Math.max(10, bar.height * 0.4);
                const isCenterPeak = index >= 4 && index <= 6;

                return (
                  <g key={bar.id} id={bar.id} transform={`translate(${barX}, 0)`}>
                    {/* Upper Bar Harmonic */}
                    <rect
                      x="-5"
                      y={-barHeight}
                      width="10"
                      height={barHeight}
                      rx="5"
                      fill={
                        effectiveIsRecording
                          ? isCenterPeak
                            ? "#0B6FD8"
                            : "#14A88D"
                          : "#94A3B8"
                      }
                      fillOpacity={effectiveIsRecording ? 0.9 : 0.4}
                      className={
                        effectiveIsRecording
                          ? `clara-wave-${(index % 8) + 1} motion-reduce:animate-none`
                          : ""
                      }
                    />
                    {/* Lower Bar Reflection Mirror */}
                    <rect
                      x="-5"
                      y="4"
                      width="10"
                      height={barHeight * 0.6}
                      rx="4"
                      fill={
                        effectiveIsRecording
                          ? isCenterPeak
                            ? "#0B6FD8"
                            : "#14A88D"
                          : "#CBD5E1"
                      }
                      fillOpacity={effectiveIsRecording ? 0.35 : 0.2}
                    />

                    {/* Frequency Axis Label */}
                    <text
                      x="0"
                      y="48"
                      textAnchor="middle"
                      fill="#6D7A8E"
                      fontSize="9"
                      fontWeight="600"
                      fontFamily="monospace"
                    >
                      {bar.label}
                    </text>
                  </g>
                );
              })}
            </g>

            {/* Continuous Acoustic Envelope Curve */}
            <path
              id="acoustic-envelope-spline"
              d="M 60,220 Q 140,160 210,220 T 320,220 T 400,220"
              fill="none"
              stroke="#14A88D"
              strokeWidth="2"
              strokeOpacity={effectiveIsRecording ? 0.8 : 0.3}
              strokeDasharray="4 4"
            />
          </g>

          {/* SECTION 2: TRANSFORMATION VECTORS & FOLD GUIDELINES (Center Splines: x: 400 to 540) */}
          <g id="transformation-guidelines" className="transition-all duration-500">
            {/* Vector Spline S (Subjective) */}
            <path
              id="vector-spline-s"
              d="M 390,200 C 440,180 470,120 540,110"
              fill="none"
              stroke="#0B6FD8"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.85" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline O (Objective) */}
            <path
              id="vector-spline-o"
              d="M 390,210 C 450,210 490,140 700,110"
              fill="none"
              stroke="#14A88D"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.85" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline A (Assessment) */}
            <path
              id="vector-spline-a"
              d="M 390,230 C 440,240 470,280 540,270"
              fill="none"
              stroke="#8B7CF6"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.85" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline P (Plan) */}
            <path
              id="vector-spline-p"
              d="M 390,240 C 450,250 490,320 700,270"
              fill="none"
              stroke="#D97706"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.85" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />

            {/* Central Transformation Aperture Node */}
            <g transform="translate(460, 220)">
              <circle
                r="18"
                fill="#FFFFFF"
                stroke={resolvedState === "soap" ? "#8B7CF6" : "#E3E8EF"}
                strokeWidth="2"
                filter={`url(#${filterDropShadowDocId})`}
              />
              <path
                d="M -6,-4 L 6,0 L -6,4 Z"
                fill={resolvedState === "soap" ? "#8B7CF6" : "#6D7A8E"}
              />
            </g>
          </g>

          {/* SECTION 3: DOCUMENT FOLD GUIDE & SOAP QUADRANTS (Right Zone: x: 530 to 890) */}
          <g
            id="document-fold-transformation-guide"
            filter={`url(#${filterDropShadowDocId})`}
            className="transition-all duration-500"
          >
            {/* Base Document Sheet with Rounded Corners */}
            <rect
              id="doc-base-plane"
              x="530"
              y="40"
              width="350"
              height="340"
              rx="18"
              fill={`url(#${gradDocumentPlaneId})`}
              stroke="#D5DDE7"
              strokeWidth="1.5"
            />

            {/* 3D Top-Right Corner Fold Guide (Origami Corner Crease) */}
            <g id="document-corner-fold">
              <path
                d="M 840,40 L 880,80 L 840,80 Z"
                fill="#E3E8EF"
                stroke="#CBD5E1"
                strokeWidth="1"
              />
              <path
                d="M 840,40 L 880,80"
                stroke="#94A3B8"
                strokeWidth="1.5"
                strokeDasharray="2 2"
              />
            </g>

            {/* Document Header Bar */}
            <g id="doc-header-band">
              <rect x="546" y="56" width="280" height="24" rx="6" fill="#F1F5F9" />
              <circle cx="560" cy="68" r="4" fill="#14A88D" />
              <text x="572" y="72" fill="#162033" fontSize="10" fontWeight="bold">
                CLINICAL SOAP RECORD • BỆNH ÁN ĐIỆN TỬ
              </text>
              <text x="790" y="72" fill="#6D7A8E" fontSize="9" fontWeight="600">
                FHIR v4
              </text>
            </g>

            {/* QUADRANT 1: S (Subjective) - Top-Left */}
            <g
              id="soap-quadrant-s"
              transform="translate(546, 92)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="154"
                height="124"
                rx="12"
                fill={`url(#${gradSoapQuadrantS})`}
                stroke={resolvedState === "soap" ? "#0B6FD8" : "#E3E8EF"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* S Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#0B6FD8" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                S
              </text>
              <text x="38" y="24" fill="#0B6FD8" fontSize="10" fontWeight="bold">
                Subjective
              </text>
              <text x="10" y="46" fill="#48566A" fontSize="9" fontWeight="500">
                • Đau tức ngực khi gắng sức
              </text>
              <text x="10" y="62" fill="#48566A" fontSize="9" fontWeight="500">
                • Cơn kéo dài ~3 phút
              </text>
              <text x="10" y="78" fill="#6D7A8E" fontSize="8">
                Lịch sử: Tăng huyết áp 3 năm
              </text>
              {/* Acoustic Wave to S conversion indicator */}
              <line x1="10" y1="100" x2="140" y2="100" stroke="#0B6FD8" strokeOpacity="0.2" strokeWidth="1" />
              <text x="10" y="112" fill="#0B6FD8" fontSize="8" fontWeight="bold">
                ✓ Trích xuất từ hội thoại
              </text>
            </g>

            {/* QUADRANT 2: O (Objective) - Top-Right */}
            <g
              id="soap-quadrant-o"
              transform="translate(712, 92)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="154"
                height="124"
                rx="12"
                fill={`url(#${gradSoapQuadrantO})`}
                stroke={resolvedState === "soap" ? "#14A88D" : "#E3E8EF"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* O Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#14A88D" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                O
              </text>
              <text x="38" y="24" fill="#14A88D" fontSize="10" fontWeight="bold">
                Objective
              </text>
              <text x="10" y="46" fill="#48566A" fontSize="9" fontWeight="500">
                • HA: 135/85 mmHg
              </text>
              <text x="10" y="62" fill="#48566A" fontSize="9" fontWeight="500">
                • Tim đều, T1-T2 rõ
              </text>
              <text x="10" y="78" fill="#6D7A8E" fontSize="8">
                SpO2: 98% khí phòng
              </text>
              <line x1="10" y1="100" x2="140" y2="100" stroke="#14A88D" strokeOpacity="0.2" strokeWidth="1" />
              <text x="10" y="112" fill="#14A88D" fontSize="8" fontWeight="bold">
                ✓ Đối chiếu chỉ số khám
              </text>
            </g>

            {/* QUADRANT 3: A (Assessment) - Bottom-Left */}
            <g
              id="soap-quadrant-a"
              transform="translate(546, 226)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="154"
                height="124"
                rx="12"
                fill={`url(#${gradSoapQuadrantA})`}
                stroke={resolvedState === "soap" ? "#8B7CF6" : "#E3E8EF"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* A Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#8B7CF6" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                A
              </text>
              <text x="38" y="24" fill="#8B7CF6" fontSize="10" fontWeight="bold">
                Assessment
              </text>
              <text x="10" y="46" fill="#48566A" fontSize="9" fontWeight="500">
                • Cơn đau thắt ngực (CCS II)
              </text>
              <text x="10" y="62" fill="#48566A" fontSize="9" fontWeight="500">
                • Tăng huyết áp vô căn (I10)
              </text>
              <text x="10" y="78" fill="#6D7A8E" fontSize="8">
                Phân tầng nguy cơ: Trung bình
              </text>
              <line x1="10" y1="100" x2="140" y2="100" stroke="#8B7CF6" strokeOpacity="0.2" strokeWidth="1" />
              <text x="10" y="112" fill="#8B7CF6" fontSize="8" fontWeight="bold">
                ✓ Mã hóa ICD-10 tự động
              </text>
            </g>

            {/* QUADRANT 4: P (Plan) - Bottom-Right */}
            <g
              id="soap-quadrant-p"
              transform="translate(712, 226)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="154"
                height="124"
                rx="12"
                fill={`url(#${gradSoapQuadrantP})`}
                stroke={resolvedState === "soap" ? "#D97706" : "#E3E8EF"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* P Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#D97706" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                P
              </text>
              <text x="38" y="24" fill="#D97706" fontSize="10" fontWeight="bold">
                Plan
              </text>
              <text x="10" y="46" fill="#48566A" fontSize="9" fontWeight="500">
                • Điện tâm đồ gắng sức (ECG)
              </text>
              <text x="10" y="62" fill="#48566A" fontSize="9" fontWeight="500">
                • Siêu âm tim Doppler màu
              </text>
              <text x="10" y="78" fill="#6D7A8E" fontSize="8">
                Thuốc: Tiếp tục Amlodipine 5mg
              </text>
              <line x1="10" y1="100" x2="140" y2="100" stroke="#D97706" strokeOpacity="0.2" strokeWidth="1" />
              <text x="10" y="112" fill="#D97706" fontSize="8" fontWeight="bold">
                ✓ Hướng xử trí theo phác đồ
              </text>
            </g>

            {/* DOCUMENT ORIGAMI FOLD CREASES & AXIS GUIDES */}
            <g id="document-fold-creases">
              {/* Horizontal Fold Crease */}
              <line
                id="fold-crease-horizontal"
                x1="540"
                y1="221"
                x2="872"
                y2="221"
                stroke={`url(#${gradFoldCreaseId})`}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
                strokeDasharray="6 4"
              />
              {/* Vertical Fold Crease */}
              <line
                id="fold-crease-vertical"
                x1="706"
                y1="86"
                x2="706"
                y2="356"
                stroke={`url(#${gradFoldCreaseId})`}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
                strokeDasharray="6 4"
              />

              {/* Fold Axis Intersection Hub */}
              <g transform="translate(706, 221)">
                <circle
                  r="7"
                  fill="#FFFFFF"
                  stroke="#8B7CF6"
                  strokeWidth="2"
                  filter={`url(#${filterDropShadowDocId})`}
                />
                <circle r="2.5" fill="#8B7CF6" />
              </g>

              {/* Fold Axis Metadata Callout */}
              {resolvedState === "soap" && (
                <g id="fold-guide-callout" transform="translate(640, 362)">
                  <rect
                    x="-6"
                    y="-12"
                    width="144"
                    height="18"
                    rx="9"
                    fill="#162033"
                    fillOpacity="0.9"
                  />
                  <text
                    x="66"
                    y="0"
                    textAnchor="middle"
                    fill="#FFFFFF"
                    fontSize="9"
                    fontWeight="bold"
                  >
                    ✦ Nếp gấp chuyển hóa SOAP
                  </text>
                </g>
              )}
            </g>

            {/* PHYSICIAN VERIFICATION SEAL (Visible during review state) */}
            {resolvedState === "review" && (
              <g
                id="physician-review-seal"
                transform="translate(706, 221)"
                className="motion-safe:animate-fadeIn"
              >
                <circle
                  r="48"
                  fill="#FFFFFF"
                  stroke="#14A88D"
                  strokeWidth="3"
                  strokeDasharray="8 4"
                  filter={`url(#${filterDropShadowDocId})`}
                />
                <circle r="40" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1" />
                <text x="0" y="-8" textAnchor="middle" fill="#14A88D" fontSize="18" fontWeight="bold">
                  ✓
                </text>
                <text x="0" y="8" textAnchor="middle" fill="#162033" fontSize="9" fontWeight="bold">
                  BÁC SĨ ĐÃ DUYỆT
                </text>
                <text x="0" y="20" textAnchor="middle" fill="#0E856F" fontSize="8" fontWeight="600">
                  Ký điện tử PKI
                </text>
              </g>
            )}
          </g>
        </svg>
      </div>

      {/* Bottom Live Waveform / Transformation Control Bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-white p-3.5 sm:p-4 border border-[#E3E8EF]">
        <div className="flex items-center gap-3">
          {/* Waveform Micro-Bar Equalizer Display */}
          <div
            className="flex items-center justify-center gap-1 h-8 px-2.5 bg-[#F8FAFD] rounded-xl border border-[#E3E8EF]"
            aria-hidden="true"
          >
            {WAVEFORM_BARS.map((bar, i) => (
              <span
                key={bar.id}
                className={`w-1 rounded-full ${
                  effectiveIsRecording
                    ? i >= 4 && i <= 6
                      ? "bg-[#0B6FD8]"
                      : "bg-[#14A88D]"
                    : "bg-[#CBD5E1]"
                } ${
                  effectiveIsRecording
                    ? `clara-wave-${(i % 8) + 1} motion-reduce:animate-none`
                    : ""
                }`}
                style={{
                  height: effectiveIsRecording ? `${Math.max(6, bar.height * 0.45)}px` : "6px",
                }}
              />
            ))}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[#162033]">
                {effectiveIsRecording
                  ? "Bộ lọc giảm ồn âm học Y tế đang hoạt động"
                  : resolvedState === "soap"
                  ? "Hướng dẫn chuyển đổi cấu trúc tài liệu SOAP"
                  : resolvedState === "review"
                  ? "Bệnh án cấu trúc sẵn sàng tích hợp EMR"
                  : "Scribe Transformation Ready"}
              </span>
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: meta.accentColor }}
              />
            </div>
            <p className="text-[11px] text-[#6D7A8E]">
              {effectiveIsRecording
                ? "48kHz Stereo Array • Zero-Latency VAD • Chuẩn hóa thuật ngữ lâm sàng tức thời"
                : meta.descVi}
            </p>
          </div>
        </div>

        {/* Live Status Pill */}
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold border transition-colors duration-300"
            style={{
              backgroundColor: meta.badgeBg,
              color: meta.accentColor,
              borderColor: meta.badgeBorder,
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full animate-pulse"
              style={{ backgroundColor: meta.accentColor }}
            />
            {displayBadgeText}
          </span>
        </div>
      </div>
    </div>
  );
}

export default CaptureWave;
