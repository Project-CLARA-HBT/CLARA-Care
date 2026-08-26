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

// 12-bar acoustic soundwave visualizer covering medical/clinical frequency bands
const WAVEFORM_BARS = [
  { id: "bar-1", height: 18, delay: "0.1s", label: "64Hz" },
  { id: "bar-2", height: 28, delay: "0.28s", label: "125Hz" },
  { id: "bar-3", height: 40, delay: "0.18s", label: "250Hz" },
  { id: "bar-4", height: 52, delay: "0.35s", label: "500Hz" },
  { id: "bar-5", height: 32, delay: "0.12s", label: "1kHz" },
  { id: "bar-6", height: 58, delay: "0.3s", label: "2kHz" },
  { id: "bar-7", height: 62, delay: "0.22s", label: "4kHz" },
  { id: "bar-8", height: 44, delay: "0.42s", label: "8kHz" },
  { id: "bar-9", height: 50, delay: "0.16s", label: "12kHz" },
  { id: "bar-10", height: 34, delay: "0.38s", label: "16kHz" },
  { id: "bar-11", height: 26, delay: "0.24s", label: "20kHz" },
  { id: "bar-12", height: 18, delay: "0.44s", label: "24kHz" },
];

/**
 * CaptureWave Artwork Component (Landing v7)
 *
 * Upgraded Features:
 * 1. 12-Bar Acoustic Soundwave Visualizer: High-precision 12-channel frequency spectrum with dynamic harmonic oscillation and lower-mirror reflections.
 * 2. Glowing Mic Aura: Multi-layered pulsing electromagnetic aura with noise-cancelling 48kHz audio array indicators.
 * 3. Isometric SOAP Document Fold Guide: 3D origami isometric projection with folding creases, diagonal facets, and 4 structured quadrants (S, O, A, P).
 * 4. Supports all 5 Scribe lifecycle states with responsive vector SVG + CSS Lite/Reduced Motion tier support.
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
  const gradDocIsoFacetId = `capture-wave-grad-iso-facet-${uid}`;
  const gradFoldCreaseId = `capture-wave-grad-crease-${uid}`;
  const gradAcousticAuraId = `capture-wave-grad-aura-${uid}`;
  const gradMicPulseGlowId = `capture-wave-grad-mic-pulse-${uid}`;
  const gradSoapQuadrantS = `capture-wave-soap-s-${uid}`;
  const gradSoapQuadrantO = `capture-wave-soap-o-${uid}`;
  const gradSoapQuadrantA = `capture-wave-soap-a-${uid}`;
  const gradSoapQuadrantP = `capture-wave-soap-p-${uid}`;
  const filterGlowMintId = `capture-wave-glow-mint-${uid}`;
  const filterGlowMicId = `capture-wave-glow-mic-${uid}`;
  const filterDropShadowDocId = `capture-wave-shadow-doc-${uid}`;
  const filterDropShadowIsoId = `capture-wave-shadow-iso-${uid}`;

  const ariaDescription = useMemo(() => {
    switch (resolvedState) {
      case "consent":
        return "Bảo mật & Đồng thuận: Bệnh nhân đã xác nhận đồng thuận ghi âm y khoa.";
      case "recording":
        return "Thu âm hội thoại lâm sàng với visualizer âm học 12 dải tần và hào quang mic phát sáng.";
      case "transcript":
        return "Biên dịch luồng hội thoại thành văn bản chuẩn hóa thuật ngữ song ngữ.";
      case "soap":
        return "Hướng dẫn chuyển đổi nếp gấp đẳng cự SOAP: Phân bổ vào 4 phân hệ bệnh án.";
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
          <title>CLARA Scribe Capture Wave & Isometric SOAP Fold Guide</title>
          <desc>
            12-bar acoustic soundwave visualizer with glowing mic aura folding into an isometric 4-quadrant
            clinical SOAP document.
          </desc>

          <defs>
            {/* Waveform Gradient */}
            <linearGradient id={gradWaveformId} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#14A88D" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="1" />
            </linearGradient>

            {/* Glowing Microphone Aura Gradient */}
            <radialGradient id={gradAcousticAuraId} cx="50%" cy="50%" r="50%">
              <stop
                offset="0%"
                stopColor={effectiveIsRecording ? "#E11D48" : "#14A88D"}
                stopOpacity={effectiveIsRecording ? "0.45" : "0.2"}
              />
              <stop
                offset="40%"
                stopColor={effectiveIsRecording ? "#F43F5E" : "#0B6FD8"}
                stopOpacity={effectiveIsRecording ? "0.22" : "0.08"}
              />
              <stop offset="80%" stopColor="#0B6FD8" stopOpacity="0.04" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0" />
            </radialGradient>

            {/* High-intensity Mic Energy Core Glow */}
            <radialGradient id={gradMicPulseGlowId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
              <stop
                offset="35%"
                stopColor={effectiveIsRecording ? "#FB7185" : "#5EEAD4"}
                stopOpacity="0.75"
              />
              <stop
                offset="100%"
                stopColor={effectiveIsRecording ? "#E11D48" : "#14A88D"}
                stopOpacity="0"
              />
            </radialGradient>

            {/* Isometric Document Base Plane Gradient */}
            <linearGradient id={gradDocumentPlaneId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.98" />
              <stop offset="50%" stopColor="#F8FAFD" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#EEF4FB" stopOpacity="0.92" />
            </linearGradient>

            {/* Isometric Edge Depth Facet Gradient */}
            <linearGradient id={gradDocIsoFacetId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#CBD5E1" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#94A3B8" stopOpacity="0.9" />
            </linearGradient>

            {/* Origami Fold Crease Gradient */}
            <linearGradient id={gradFoldCreaseId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.1" />
              <stop offset="30%" stopColor="#8B7CF6" stopOpacity="0.8" />
              <stop offset="70%" stopColor="#14A88D" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0.1" />
            </linearGradient>

            {/* SOAP Quadrant Gradients */}
            <linearGradient id={gradSoapQuadrantS} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#EFF6FF" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.98" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantO} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#ECFDF5" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.98" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantA} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#F5F3FF" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.98" />
            </linearGradient>

            <linearGradient id={gradSoapQuadrantP} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FFFBEB" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.98" />
            </linearGradient>

            {/* Glowing Aura & Drop Shadow Filters */}
            <filter id={filterGlowMicId} x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id={filterGlowMintId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            <filter id={filterDropShadowDocId} x="-10%" y="-10%" width="125%" height="125%">
              <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#162033" floodOpacity="0.08" />
            </filter>

            <filter id={filterDropShadowIsoId} x="-15%" y="-10%" width="135%" height="135%">
              <feDropShadow dx="6" dy="16" stdDeviation="14" floodColor="#0F172A" floodOpacity="0.12" />
            </filter>
          </defs>

          {/* Background Grid & Spatial Matrix */}
          <g id="spatial-grid-matrix" opacity="0.45">
            <line x1="40" y1="220" x2="880" y2="220" stroke="#E3E8EF" strokeDasharray="4 4" />
            <line x1="450" y1="25" x2="450" y2="415" stroke="#E3E8EF" strokeDasharray="4 4" />
            <circle cx="210" cy="220" r="165" stroke="#EDF2F7" strokeWidth="1" />
            <circle cx="210" cy="220" r="115" stroke="#EDF2F7" strokeWidth="1" />
            <circle cx="210" cy="220" r="65" stroke="#EDF2F7" strokeWidth="1" />
          </g>

          {/* SECTION 1: 12-BAR ACOUSTIC SOUNDWAVE VISUALIZER & GLOWING MIC AURA (Left Zone: x: 40 to 420) */}
          <g
            id="ambient-acoustic-waveform-system"
            className="transition-opacity duration-500"
            opacity={resolvedState === "consent" ? 0.45 : 1}
          >
            {/* Glowing Microphone Capture Node */}
            <g id="mic-capture-core" transform="translate(75, 220)">
              {/* Outer Radiant Ambient Aura */}
              <circle
                r="64"
                fill={`url(#${gradAcousticAuraId})`}
                filter={`url(#${filterGlowMicId})`}
                className={effectiveIsRecording ? "motion-safe:animate-pulse" : ""}
                style={{ animationDuration: "2.5s" }}
              />

              {/* Dynamic Concentric Acoustic Propagation Rings */}
              {effectiveIsRecording && (
                <>
                  <circle
                    r="54"
                    fill="none"
                    stroke="#E11D48"
                    strokeWidth="1.5"
                    strokeOpacity="0.4"
                    className="motion-safe:animate-ping motion-reduce:animate-none"
                    style={{ transformOrigin: "0 0", animationDuration: "3s" }}
                  />
                  <circle
                    r="40"
                    fill="none"
                    stroke="#14A88D"
                    strokeWidth="1.5"
                    strokeOpacity="0.5"
                    className="motion-safe:animate-ping motion-reduce:animate-none"
                    style={{ transformOrigin: "0 0", animationDuration: "2s" }}
                  />
                  <circle
                    r="28"
                    fill="none"
                    stroke="#0B6FD8"
                    strokeWidth="1.5"
                    strokeOpacity="0.6"
                    className="motion-safe:animate-ping motion-reduce:animate-none"
                    style={{ transformOrigin: "0 0", animationDuration: "1.5s" }}
                  />
                </>
              )}

              {/* Glowing Mic Ambient Core Background */}
              <circle r="26" fill={`url(#${gradMicPulseGlowId})`} />

              {/* Outer Mic Pill Body */}
              <rect
                x="-15"
                y="-22"
                width="30"
                height="44"
                rx="15"
                fill={resolvedState === "recording" ? "#FFF1F2" : "#ECFDF8"}
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="2"
                filter={`url(#${filterGlowMintId})`}
              />

              {/* Mic Acoustic Grille Mesh */}
              <line
                x1="-8"
                y1="-8"
                x2="8"
                y2="-8"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <line
                x1="-8"
                y1="-2"
                x2="8"
                y2="-2"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <line
                x1="-8"
                y1="4"
                x2="8"
                y2="4"
                stroke={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />

              {/* Live Audio Telemetry Indicator Dot */}
              <circle
                cx="0"
                cy="12"
                r="3"
                fill={resolvedState === "recording" ? "#E11D48" : "#14A88D"}
                className={resolvedState === "recording" ? "motion-safe:animate-pulse" : ""}
              />
            </g>

            {/* 12-Bar Acoustic Waveform Spectrum Visualizer */}
            <g id="acoustic-spectrum-bars" transform="translate(128, 220)">
              {WAVEFORM_BARS.map((bar, index) => {
                const barX = index * 22;
                const barHeight = effectiveIsRecording ? bar.height : Math.max(10, bar.height * 0.35);
                const isCenterPeak = index >= 4 && index <= 7;

                return (
                  <g key={bar.id} id={bar.id} transform={`translate(${barX}, 0)`}>
                    {/* Upper Bar Harmonic */}
                    <rect
                      x="-4"
                      y={-barHeight}
                      width="8"
                      height={barHeight}
                      rx="4"
                      fill={
                        effectiveIsRecording
                          ? isCenterPeak
                            ? "#0B6FD8"
                            : "#14A88D"
                          : "#94A3B8"
                      }
                      fillOpacity={effectiveIsRecording ? 0.92 : 0.4}
                      className={
                        effectiveIsRecording
                          ? `clara-wave-${(index % 12) + 1} motion-reduce:animate-none`
                          : ""
                      }
                    />
                    {/* Lower Mirror Reflection Bar */}
                    <rect
                      x="-4"
                      y="4"
                      width="8"
                      height={barHeight * 0.55}
                      rx="3.5"
                      fill={
                        effectiveIsRecording
                          ? isCenterPeak
                            ? "#0B6FD8"
                            : "#14A88D"
                          : "#CBD5E1"
                      }
                      fillOpacity={effectiveIsRecording ? 0.35 : 0.18}
                    />

                    {/* Frequency Axis Label */}
                    <text
                      x="0"
                      y="46"
                      textAnchor="middle"
                      fill="#6D7A8E"
                      fontSize="8.5"
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
              d="M 45,220 Q 120,150 185,220 T 290,220 T 385,220"
              fill="none"
              stroke="#14A88D"
              strokeWidth="2"
              strokeOpacity={effectiveIsRecording ? 0.8 : 0.25}
              strokeDasharray="4 4"
            />
          </g>

          {/* SECTION 2: TRANSFORMATION VECTORS & FOLD GUIDELINES (Center Zone: x: 375 to 505) */}
          <g id="transformation-guidelines" className="transition-all duration-500">
            {/* Vector Spline S (Subjective -> Iso Quad S) */}
            <path
              id="vector-spline-s"
              d="M 375,195 C 420,175 450,115 515,100"
              fill="none"
              stroke="#0B6FD8"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.9" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline O (Objective -> Iso Quad O) */}
            <path
              id="vector-spline-o"
              d="M 375,205 C 430,205 470,125 690,95"
              fill="none"
              stroke="#14A88D"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.9" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline A (Assessment -> Iso Quad A) */}
            <path
              id="vector-spline-a"
              d="M 375,235 C 420,245 450,285 515,280"
              fill="none"
              stroke="#8B7CF6"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.9" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />
            {/* Vector Spline P (Plan -> Iso Quad P) */}
            <path
              id="vector-spline-p"
              d="M 375,245 C 430,255 470,330 690,285"
              fill="none"
              stroke="#D97706"
              strokeWidth={resolvedState === "soap" ? "2.5" : "1.5"}
              strokeOpacity={resolvedState === "soap" || resolvedState === "transcript" ? "0.9" : "0.35"}
              strokeDasharray={resolvedState === "soap" ? "none" : "6 4"}
            />

            {/* Central Transformation Hub */}
            <g transform="translate(440, 220)">
              <circle
                r="18"
                fill="#FFFFFF"
                stroke={resolvedState === "soap" ? "#8B7CF6" : "#E3E8EF"}
                strokeWidth="2"
                filter={`url(#${filterDropShadowDocId})`}
              />
              <path
                d="M -5,-4 L 5,0 L -5,4 Z"
                fill={resolvedState === "soap" ? "#8B7CF6" : "#6D7A8E"}
              />
              {resolvedState === "soap" && (
                <circle
                  r="24"
                  fill="none"
                  stroke="#8B7CF6"
                  strokeWidth="1.2"
                  strokeDasharray="3 3"
                  className="motion-safe:animate-spin"
                  style={{ transformOrigin: "0 0", animationDuration: "12s" }}
                />
              )}
            </g>
          </g>

          {/* SECTION 3: ISOMETRIC SOAP DOCUMENT FOLD GUIDE & 4-QUADRANT STRUCTURE (Right Zone: x: 495 to 895) */}
          <g
            id="document-fold-transformation-guide"
            filter={`url(#${filterDropShadowIsoId})`}
            className="transition-all duration-500"
          >
            {/* 3D Isometric Extrusion Underlay (Bevel Depth) */}
            <g id="iso-depth-extrusion">
              {/* Bottom Depth Bevel */}
              <polygon
                points="505,385 865,385 873,393 513,393"
                fill={`url(#${gradDocIsoFacetId})`}
                opacity="0.85"
              />
              {/* Right Depth Bevel */}
              <polygon
                points="865,35 873,43 873,393 865,385"
                fill="#94A3B8"
                opacity="0.9"
              />
            </g>

            {/* Isometric Base Document Sheet with Rounded Chamfer Facets */}
            <rect
              id="doc-base-plane"
              x="505"
              y="35"
              width="360"
              height="350"
              rx="16"
              fill={`url(#${gradDocumentPlaneId})`}
              stroke="#CBD5E1"
              strokeWidth="1.5"
            />

            {/* 3D Top-Right Origami Corner Fold Guide */}
            <g id="document-corner-fold">
              {/* Triangular Fold Backing Shadow */}
              <path
                d="M 825,35 L 865,75 L 825,75 Z"
                fill="#CBD5E1"
                opacity="0.7"
              />
              {/* Fold Flap Facing Facet */}
              <path
                d="M 825,35 L 865,75 L 825,75 Z"
                fill="#F1F5F9"
                stroke="#94A3B8"
                strokeWidth="1.2"
              />
              {/* Origami Fold Crease Axis */}
              <path
                d="M 825,35 L 865,75"
                stroke="#64748B"
                strokeWidth="1.5"
                strokeDasharray="2 2"
              />
            </g>

            {/* Document Header Band */}
            <g id="doc-header-band">
              <rect x="520" y="50" width="295" height="26" rx="6" fill="#F1F5F9" stroke="#E2E8F0" strokeWidth="1" />
              <circle cx="534" cy="63" r="4" fill="#14A88D" />
              <text x="546" y="67" fill="#162033" fontSize="10" fontWeight="bold">
                CLINICAL SOAP RECORD • BỆNH ÁN ĐIỆN TỬ
              </text>
              <text x="770" y="67" fill="#6D7A8E" fontSize="9" fontWeight="600">
                FHIR v4
              </text>
            </g>

            {/* QUADRANT 1: S (Subjective) - Top-Left Isometric Tile */}
            <g
              id="soap-quadrant-s"
              transform="translate(520, 88)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="160"
                height="130"
                rx="12"
                fill={`url(#${gradSoapQuadrantS})`}
                stroke={resolvedState === "soap" ? "#0B6FD8" : "#E2E8F0"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* S Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#0B6FD8" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                S
              </text>
              <text x="38" y="24" fill="#0B6FD8" fontSize="10.5" fontWeight="bold">
                Subjective
              </text>
              <text x="10" y="46" fill="#334155" fontSize="9" fontWeight="500">
                • Đau tức ngực khi gắng sức
              </text>
              <text x="10" y="62" fill="#334155" fontSize="9" fontWeight="500">
                • Cơn kéo dài ~3 phút
              </text>
              <text x="10" y="78" fill="#64748B" fontSize="8">
                Lịch sử: Tăng huyết áp 3 năm
              </text>
              {/* Acoustic Wave to S conversion indicator */}
              <line x1="10" y1="102" x2="150" y2="102" stroke="#0B6FD8" strokeOpacity="0.25" strokeWidth="1" />
              <text x="10" y="116" fill="#0B6FD8" fontSize="8.5" fontWeight="bold">
                ✓ Trích xuất từ hội thoại
              </text>
            </g>

            {/* QUADRANT 2: O (Objective) - Top-Right Isometric Tile */}
            <g
              id="soap-quadrant-o"
              transform="translate(690, 88)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="160"
                height="130"
                rx="12"
                fill={`url(#${gradSoapQuadrantO})`}
                stroke={resolvedState === "soap" ? "#14A88D" : "#E2E8F0"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* O Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#14A88D" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                O
              </text>
              <text x="38" y="24" fill="#14A88D" fontSize="10.5" fontWeight="bold">
                Objective
              </text>
              <text x="10" y="46" fill="#334155" fontSize="9" fontWeight="500">
                • HA: 135/85 mmHg
              </text>
              <text x="10" y="62" fill="#334155" fontSize="9" fontWeight="500">
                • Tim đều, T1-T2 rõ
              </text>
              <text x="10" y="78" fill="#64748B" fontSize="8">
                SpO2: 98% khí phòng
              </text>
              <line x1="10" y1="102" x2="150" y2="102" stroke="#14A88D" strokeOpacity="0.25" strokeWidth="1" />
              <text x="10" y="116" fill="#14A88D" fontSize="8.5" fontWeight="bold">
                ✓ Đối chiếu chỉ số khám
              </text>
            </g>

            {/* QUADRANT 3: A (Assessment) - Bottom-Left Isometric Tile */}
            <g
              id="soap-quadrant-a"
              transform="translate(520, 230)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="160"
                height="130"
                rx="12"
                fill={`url(#${gradSoapQuadrantA})`}
                stroke={resolvedState === "soap" ? "#8B7CF6" : "#E2E8F0"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* A Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#8B7CF6" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                A
              </text>
              <text x="38" y="24" fill="#8B7CF6" fontSize="10.5" fontWeight="bold">
                Assessment
              </text>
              <text x="10" y="46" fill="#334155" fontSize="9" fontWeight="500">
                • Cơn đau thắt ngực (CCS II)
              </text>
              <text x="10" y="62" fill="#334155" fontSize="9" fontWeight="500">
                • Tăng huyết áp vô căn (I10)
              </text>
              <text x="10" y="78" fill="#64748B" fontSize="8">
                Phân tầng nguy cơ: Trung bình
              </text>
              <line x1="10" y1="102" x2="150" y2="102" stroke="#8B7CF6" strokeOpacity="0.25" strokeWidth="1" />
              <text x="10" y="116" fill="#8B7CF6" fontSize="8.5" fontWeight="bold">
                ✓ Mã hóa ICD-10 tự động
              </text>
            </g>

            {/* QUADRANT 4: P (Plan) - Bottom-Right Isometric Tile */}
            <g
              id="soap-quadrant-p"
              transform="translate(690, 230)"
              className="transition-all duration-300"
            >
              <rect
                x="0"
                y="0"
                width="160"
                height="130"
                rx="12"
                fill={`url(#${gradSoapQuadrantP})`}
                stroke={resolvedState === "soap" ? "#D97706" : "#E2E8F0"}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
              />
              {/* P Badge */}
              <rect x="10" y="10" width="22" height="20" rx="6" fill="#D97706" />
              <text x="21" y="24" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="900">
                P
              </text>
              <text x="38" y="24" fill="#D97706" fontSize="10.5" fontWeight="bold">
                Plan
              </text>
              <text x="10" y="46" fill="#334155" fontSize="9" fontWeight="500">
                • Điện tâm đồ gắng sức (ECG)
              </text>
              <text x="10" y="62" fill="#334155" fontSize="9" fontWeight="500">
                • Siêu âm tim Doppler màu
              </text>
              <text x="10" y="78" fill="#64748B" fontSize="8">
                Thuốc: Tiếp tục Amlodipine 5mg
              </text>
              <line x1="10" y1="102" x2="150" y2="102" stroke="#D97706" strokeOpacity="0.25" strokeWidth="1" />
              <text x="10" y="116" fill="#D97706" fontSize="8.5" fontWeight="bold">
                ✓ Hướng xử trí theo phác đồ
              </text>
            </g>

            {/* DOCUMENT ORIGAMI FOLD CREASES & ISOMETRIC AXIS GUIDES */}
            <g id="document-fold-creases">
              {/* Horizontal Fold Crease */}
              <line
                id="fold-crease-horizontal"
                x1="515"
                y1="224"
                x2="855"
                y2="224"
                stroke={`url(#${gradFoldCreaseId})`}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
                strokeDasharray="6 4"
              />
              {/* Vertical Fold Crease */}
              <line
                id="fold-crease-vertical"
                x1="685"
                y1="82"
                x2="685"
                y2="366"
                stroke={`url(#${gradFoldCreaseId})`}
                strokeWidth={resolvedState === "soap" ? "2" : "1"}
                strokeDasharray="6 4"
              />

              {/* Fold Axis Intersection Hub */}
              <g transform="translate(685, 224)">
                <circle
                  r="7.5"
                  fill="#FFFFFF"
                  stroke="#8B7CF6"
                  strokeWidth="2"
                  filter={`url(#${filterDropShadowDocId})`}
                />
                <circle r="3" fill="#8B7CF6" />
              </g>

              {/* Fold Axis Metadata Callout */}
              {resolvedState === "soap" && (
                <g id="fold-guide-callout" transform="translate(615, 368)">
                  <rect
                    x="-6"
                    y="-12"
                    width="152"
                    height="20"
                    rx="10"
                    fill="#162033"
                    fillOpacity="0.92"
                  />
                  <text
                    x="70"
                    y="1"
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
                transform="translate(685, 224)"
                className="motion-safe:animate-fadeIn"
              >
                <circle
                  r="50"
                  fill="#FFFFFF"
                  stroke="#14A88D"
                  strokeWidth="3"
                  strokeDasharray="8 4"
                  filter={`url(#${filterDropShadowDocId})`}
                />
                <circle r="42" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1.2" />
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
          {/* 12-Bar Waveform Micro Equalizer Display */}
          <div
            className="flex items-center justify-center gap-1 h-8 px-2.5 bg-[#F8FAFD] rounded-xl border border-[#E3E8EF]"
            aria-hidden="true"
          >
            {WAVEFORM_BARS.map((bar, i) => (
              <span
                key={bar.id}
                className={`w-1 rounded-full ${
                  effectiveIsRecording
                    ? i >= 4 && i <= 7
                      ? "bg-[#0B6FD8]"
                      : "bg-[#14A88D]"
                    : "bg-[#CBD5E1]"
                } ${
                  effectiveIsRecording
                    ? `clara-wave-${(i % 12) + 1} motion-reduce:animate-none`
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
                  ? "Visualizer âm học 12 dải tần & bộ lọc giảm ồn 48kHz đang hoạt động"
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
                ? "12 dải tần số 64Hz-24kHz • Zero-Latency VAD • Chuẩn hóa thuật ngữ lâm sàng tức thời"
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
