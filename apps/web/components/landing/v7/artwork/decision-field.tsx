"use client";

import React, { useId, useMemo } from "react";

export interface DecisionFieldProps {
  /**
   * Active stage of Council convergence pipeline (1 to 4):
   * 1: Multidisciplinary Recommendation / Synthesis
   * 2: Specialty Disagreements & Divergence
   * 3: Data Gaps & Uncertainty Bounds
   * 4: Action Plan & Next Steps
   */
  activeStage?: 1 | 2 | 3 | 4 | number;
  /**
   * Additional container CSS classes
   */
  className?: string;
  /**
   * Optional custom accessible label
   */
  ariaLabel?: string;
  /**
   * Optional callback when an interactive node or stage is clicked
   */
  onStageChange?: (stage: 1 | 2 | 3 | 4) => void;
}

export function DecisionField({
  activeStage = 1,
  className = "",
  ariaLabel,
  onStageChange,
}: DecisionFieldProps) {
  const uid = useId().replace(/:/g, "_");
  const normalizedStage = Math.max(1, Math.min(4, Math.round(activeStage))) as 1 | 2 | 3 | 4;

  const stageAriaDescription = useMemo(() => {
    switch (normalizedStage) {
      case 1:
        return "Giai đoạn 1: Khuyến nghị tổng hợp đa chuyên khoa";
      case 2:
        return "Giai đoạn 2: Điểm bất đồng và xung đột chuyên khoa";
      case 3:
        return "Giai đoạn 3: Ranh giới dữ liệu chưa chắc chắn";
      case 4:
        return "Giai đoạn 4: Kế hoạch hành động và bước tiếp theo";
    }
  }, [normalizedStage]);

  return (
    <div
      className={`relative w-full overflow-hidden rounded-3xl border border-[#E3E8EF] bg-gradient-to-b from-[#FFFFFF] via-[#F8FAFD] to-[#F1F5F9] p-4 sm:p-6 lg:p-8 shadow-xl ${className}`}
      data-testid="decision-field"
      data-active-stage={normalizedStage}
    >
      {/* Visual Header / Context Rail */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#0B6FD8] text-[11px] font-black text-white shadow-xs">
            ✦
          </span>
          <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
            Council Multi-Specialty Convergence Field
          </span>
        </div>

        {/* Stage Pills */}
        <div
          className="flex items-center gap-1 rounded-xl bg-[#EFF4FA] p-1 border border-[#E3E8EF]"
          role="tablist"
          aria-label="Council Convergence Stages"
        >
          {([1, 2, 3, 4] as const).map((stageNum) => {
            const labels = ["Khuyến nghị", "Bất đồng", "Chưa chắc", "Hành động"];
            const isCurrent = normalizedStage === stageNum;
            return (
              <button
                key={stageNum}
                type="button"
                role="tab"
                aria-selected={isCurrent}
                onClick={() => onStageChange?.(stageNum)}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all ${
                  isCurrent
                    ? "bg-white text-[#0B6FD8] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    stageNum === 1
                      ? isCurrent ? "bg-[#0B6FD8]" : "bg-[#0B6FD8]/40"
                      : stageNum === 2
                      ? isCurrent ? "bg-rose-500" : "bg-rose-400/40"
                      : stageNum === 3
                      ? isCurrent ? "bg-amber-500" : "bg-amber-400/40"
                      : isCurrent ? "bg-[#14A88D]" : "bg-[#14A88D]/40"
                  }`}
                />
                <span>0{stageNum}</span>
                <span className="hidden md:inline">{labels[stageNum - 1]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SVG Spatial Convergence Artwork */}
      <div className="relative aspect-[16/9] w-full min-h-[360px] max-h-[580px]">
        <svg
          viewBox="0 0 940 520"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full select-none"
          role="img"
          aria-label={ariaLabel || `Ma trận hội chẩn Council đa chuyên khoa - ${stageAriaDescription}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <title>CLARA Council Decision Convergence Artwork</title>
          <desc>Cardiology (Azure), Nephrology (Mint), and Pharmacology (Iris) streams converging into a structured Decision Result Plane</desc>

          <defs>
            {/* Ambient Lighting Gradients */}
            <radialGradient id={`${uid}-bgGlow`} cx="48%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.05" />
              <stop offset="60%" stopColor="#14A88D" stopOpacity="0.03" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </radialGradient>

            {/* Stream Gradients */}
            {/* 1. Cardiology: Azure */}
            <linearGradient id={`${uid}-gradCardio`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.9" />
              <stop offset="70%" stopColor="#1A86F5" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id={`${uid}-gradCardioSubtle`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0.1" />
            </linearGradient>

            {/* 2. Nephrology: Mint */}
            <linearGradient id={`${uid}-gradNephro`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.9" />
              <stop offset="70%" stopColor="#2DD4BF" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id={`${uid}-gradNephroSubtle`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#14A88D" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.1" />
            </linearGradient>

            {/* 3. Pharmacology: Iris */}
            <linearGradient id={`${uid}-gradPharm`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#8B7CF6" stopOpacity="0.9" />
              <stop offset="70%" stopColor="#A78BFA" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#6D5BD0" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id={`${uid}-gradPharmSubtle`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#8B7CF6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#8B7CF6" stopOpacity="0.1" />
            </linearGradient>

            {/* Tension Conflict Gradient for Stage 2 */}
            <linearGradient id={`${uid}-gradTension`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#FB7185" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#8B7CF6" stopOpacity="0.8" />
            </linearGradient>

            {/* Synthesized Plane Glow */}
            <radialGradient id={`${uid}-planeGlow`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0" />
            </radialGradient>

            {/* Drop Shadows */}
            <filter id={`${uid}-cardShadow`} x="-10%" y="-10%" width="120%" height="125%" filterUnits="userSpaceOnUse">
              <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#162033" floodOpacity="0.08" />
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#162033" floodOpacity="0.04" />
            </filter>
            <filter id={`${uid}-activeShadow`} x="-15%" y="-15%" width="130%" height="135%" filterUnits="userSpaceOnUse">
              <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#0B6FD8" floodOpacity="0.18" />
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0B6FD8" floodOpacity="0.08" />
            </filter>
            <filter id={`${uid}-glow`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Spatial Grid & Perspective Lines */}
          <rect width="940" height="520" fill={`url(#${uid}-bgGlow)`} rx="20" />
          
          <g opacity="0.45" stroke="#E3E8EF" strokeWidth="0.75" strokeDasharray="3 4">
            <line x1="220" y1="40" x2="220" y2="480" />
            <line x1="420" y1="40" x2="420" y2="480" />
            <line x1="560" y1="40" x2="560" y2="480" />
            <line x1="40" y1="130" x2="560" y2="130" />
            <line x1="40" y1="260" x2="560" y2="260" />
            <line x1="40" y1="390" x2="560" y2="390" />
          </g>

          {/* Subtle Isometric Convergence Rays */}
          <g opacity="0.35" stroke="#D5DDE7" strokeWidth="1">
            <path d="M 220 100 L 490 240" strokeDasharray="2 3" />
            <path d="M 220 260 L 490 260" strokeDasharray="2 3" />
            <path d="M 220 420 L 490 280" strokeDasharray="2 3" />
          </g>

          {/* ========================================================================= */}
          {/* 1. CONVERGING STREAM LINES (Cardiology, Nephrology, Pharmacology)        */}
          {/* ========================================================================= */}

          {/* --- CARDIOLOGY (AZURE) STREAMS --- */}
          <g id="stream-cardiology" className="transition-opacity duration-300">
            {/* Satellite harmonic glow lines */}
            <path
              d="M 220 85 C 310 85, 390 180, 500 242"
              stroke={`url(#${uid}-gradCardioSubtle)`}
              strokeWidth="4"
              fill="none"
              opacity={normalizedStage === 1 ? "0.8" : "0.4"}
            />
            <path
              d="M 220 115 C 300 115, 380 200, 500 252"
              stroke={`url(#${uid}-gradCardioSubtle)`}
              strokeWidth="2"
              strokeDasharray="4 4"
              fill="none"
              opacity="0.6"
            />
            {/* Primary stream line */}
            <path
              d="M 220 100 C 320 100, 400 210, 500 247"
              stroke={`url(#${uid}-gradCardio)`}
              strokeWidth={normalizedStage === 1 ? "3.5" : "2.5"}
              fill="none"
              filter={`url(#${uid}-glow)`}
            />
            {/* Animated Stream Pulse Dots */}
            <circle cx="340" cy="140" r="3.5" fill="#0B6FD8" opacity="0.9">
              <animate attributeName="opacity" values="0.4;1;0.4" dur="2.4s" repeatCount="indefinite" />
              <animate attributeName="r" values="2.5;4;2.5" dur="2.4s" repeatCount="indefinite" />
            </circle>
            <circle cx="440" cy="215" r="3" fill="#1A86F5" opacity="0.8">
              <animate attributeName="opacity" values="0.3;0.9;0.3" dur="2.8s" repeatCount="indefinite" />
            </circle>
          </g>

          {/* --- NEPHROLOGY (MINT) STREAMS --- */}
          <g id="stream-nephrology" className="transition-opacity duration-300">
            {/* Satellite harmonic glow lines */}
            <path
              d="M 220 245 C 320 245, 410 255, 500 258"
              stroke={`url(#${uid}-gradNephroSubtle)`}
              strokeWidth="4"
              fill="none"
              opacity={normalizedStage === 4 ? "0.9" : "0.4"}
            />
            <path
              d="M 220 275 C 320 275, 410 265, 500 264"
              stroke={`url(#${uid}-gradNephroSubtle)`}
              strokeWidth="2"
              strokeDasharray="4 4"
              fill="none"
              opacity="0.6"
            />
            {/* Primary stream line */}
            <path
              d="M 220 260 C 320 260, 420 260, 500 260"
              stroke={`url(#${uid}-gradNephro)`}
              strokeWidth={normalizedStage === 4 ? "3.5" : "2.5"}
              fill="none"
              filter={`url(#${uid}-glow)`}
            />
            {/* Animated Stream Pulse Dots */}
            <circle cx="360" cy="260" r="3.5" fill="#14A88D" opacity="0.9">
              <animate attributeName="opacity" values="0.4;1;0.4" dur="2.1s" repeatCount="indefinite" />
              <animate attributeName="r" values="2.5;4;2.5" dur="2.1s" repeatCount="indefinite" />
            </circle>
          </g>

          {/* --- PHARMACOLOGY (IRIS) STREAMS --- */}
          <g id="stream-pharmacology" className="transition-opacity duration-300">
            {/* Satellite harmonic glow lines */}
            <path
              d="M 220 405 C 300 405, 380 320, 500 268"
              stroke={`url(#${uid}-gradPharmSubtle)`}
              strokeWidth="4"
              fill="none"
              opacity={normalizedStage === 2 ? "0.9" : "0.4"}
            />
            <path
              d="M 220 435 C 310 435, 390 340, 500 278"
              stroke={`url(#${uid}-gradPharmSubtle)`}
              strokeWidth="2"
              strokeDasharray="4 4"
              fill="none"
              opacity="0.6"
            />
            {/* Primary stream line */}
            <path
              d="M 220 420 C 320 420, 400 310, 500 273"
              stroke={`url(#${uid}-gradPharm)`}
              strokeWidth={normalizedStage === 2 ? "3.5" : "2.5"}
              fill="none"
              filter={`url(#${uid}-glow)`}
            />
            {/* Animated Stream Pulse Dots */}
            <circle cx="340" cy="380" r="3.5" fill="#8B7CF6" opacity="0.9">
              <animate attributeName="opacity" values="0.4;1;0.4" dur="2.6s" repeatCount="indefinite" />
              <animate attributeName="r" values="2.5;4;2.5" dur="2.6s" repeatCount="indefinite" />
            </circle>
            <circle cx="440" cy="305" r="3" fill="#A78BFA" opacity="0.8">
              <animate attributeName="opacity" values="0.3;0.9;0.3" dur="2.3s" repeatCount="indefinite" />
            </circle>
          </g>

          {/* --- STAGE 2: CROSS-SPECIALTY DISAGREEMENT TENSION ARC --- */}
          {normalizedStage === 2 && (
            <g id="stage2-conflict-tension" className="animate-fadeIn">
              {/* Divergence Tension Arch between Pharmacology & Cardiology */}
              <path
                d="M 210 120 Q 320 260 210 400"
                stroke={`url(#${uid}-gradTension)`}
                strokeWidth="2"
                strokeDasharray="5 4"
                fill="none"
              />
              <circle cx="280" cy="260" r="14" fill="#FFE4E6" stroke="#F43F5E" strokeWidth="1.5" />
              <text x="280" y="264" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#E11D48">
                ⚡
              </text>
              <rect x="235" y="282" width="90" height="20" rx="6" fill="#FFF1F2" stroke="#FDA4AF" strokeWidth="1" />
              <text x="280" y="295" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill="#BE123C">
                Xung đột: Ngừng vs Giảm
              </text>
            </g>
          )}

          {/* --- STAGE 3: UNCERTAINTY BOUNDING PERIMETER --- */}
          {normalizedStage === 3 && (
            <g id="stage3-uncertainty-bounds" className="animate-fadeIn">
              {/* Bounding Scanner Ring around Convergence Core */}
              <rect
                x="440"
                y="180"
                width="110"
                height="160"
                rx="18"
                fill="#FEF3C7"
                fillOpacity="0.25"
                stroke="#F59E0B"
                strokeWidth="1.5"
                strokeDasharray="6 4"
              />
              <rect x="445" y="160" width="100" height="18" rx="5" fill="#FEF3C7" stroke="#FBBF24" strokeWidth="1" />
              <text x="495" y="172" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill="#B45309">
                Thiếu uACR & Điện giải
              </text>
            </g>
          )}

          {/* ========================================================================= */}
          {/* 2. CONVERGENCE CHOKE POINT & SYNTHESIS LENS CORE                          */}
          {/* ========================================================================= */}
          <g id="convergence-lens">
            {/* Outer Radiant Aperture */}
            <circle cx="500" cy="260" r="26" fill={`url(#${uid}-planeGlow)`} />
            <circle cx="500" cy="260" r="16" fill="#FFFFFF" stroke="#0B6FD8" strokeWidth="2" filter={`url(#${uid}-glow)`} />
            <circle cx="500" cy="260" r="8" fill="#162033" />
            <circle cx="500" cy="260" r="3.5" fill="#FFFFFF">
              <animate attributeName="r" values="2.5;4;2.5" dur="1.8s" repeatCount="indefinite" />
            </circle>

            {/* Diffraction Ray Connectors into Decision Result Plane */}
            <path d="M 516 250 L 580 120" stroke="#0B6FD8" strokeWidth={normalizedStage === 1 ? "2.5" : "1.2"} strokeOpacity={normalizedStage === 1 ? "1" : "0.4"} />
            <path d="M 516 256 L 580 210" stroke="#E11D48" strokeWidth={normalizedStage === 2 ? "2.5" : "1.2"} strokeOpacity={normalizedStage === 2 ? "1" : "0.4"} />
            <path d="M 516 264 L 580 300" stroke="#D97706" strokeWidth={normalizedStage === 3 ? "2.5" : "1.2"} strokeOpacity={normalizedStage === 3 ? "1" : "0.4"} />
            <path d="M 516 270 L 580 390" stroke="#14A88D" strokeWidth={normalizedStage === 4 ? "2.5" : "1.2"} strokeOpacity={normalizedStage === 4 ? "1" : "0.4"} />
          </g>

          {/* ========================================================================= */}
          {/* 3. INPUT SPECIALTY STATIONS (LEFT SIDE)                                  */}
          {/* ========================================================================= */}

          {/* Node 1: Cardiology (Azure) */}
          <g id="node-cardiology" transform="translate(30, 60)">
            <rect
              x="0"
              y="0"
              width="180"
              height="80"
              rx="16"
              fill="#FFFFFF"
              stroke="#0B6FD8"
              strokeWidth={normalizedStage === 1 ? "2" : "1"}
              filter={`url(#${uid}-cardShadow)`}
            />
            {/* Accent left indicator */}
            <rect x="0" y="0" width="5" height="80" rx="2.5" fill="#0B6FD8" />
            
            {/* Header Icon + Title */}
            <circle cx="24" cy="24" r="10" fill="#EFF7FF" stroke="#0B6FD8" strokeWidth="1" />
            <text x="24" y="27.5" textAnchor="middle" fontSize="10" fill="#0B6FD8">♥</text>
            <text x="42" y="22" fontSize="11" fontWeight="bold" fill="#162033">
              Tim mạch
            </text>
            <text x="42" y="33" fontSize="8.5" fontWeight="semibold" fill="#0B6FD8">
              Cardiology Spec
            </text>

            {/* Metric pill */}
            <rect x="14" y="44" width="152" height="24" rx="8" fill="#F8FAFD" stroke="#E3E8EF" strokeWidth="0.8" />
            <text x="22" y="59" fontSize="8.5" fontWeight="medium" fill="#48566A">
              HA: 152/88 • HR: 74 bpm • CAD
            </text>
          </g>

          {/* Node 2: Nephrology (Mint) */}
          <g id="node-nephrology" transform="translate(30, 220)">
            <rect
              x="0"
              y="0"
              width="180"
              height="80"
              rx="16"
              fill="#FFFFFF"
              stroke="#14A88D"
              strokeWidth={normalizedStage === 4 ? "2" : "1"}
              filter={`url(#${uid}-cardShadow)`}
            />
            {/* Accent left indicator */}
            <rect x="0" y="0" width="5" height="80" rx="2.5" fill="#14A88D" />

            {/* Header Icon + Title */}
            <circle cx="24" cy="24" r="10" fill="#ECFDF8" stroke="#14A88D" strokeWidth="1" />
            <text x="24" y="28" textAnchor="middle" fontSize="10" fill="#14A88D">◈</text>
            <text x="42" y="22" fontSize="11" fontWeight="bold" fill="#162033">
              Thận học
            </text>
            <text x="42" y="33" fontSize="8.5" fontWeight="semibold" fill="#14A88D">
              Nephrology Spec
            </text>

            {/* Metric pill */}
            <rect x="14" y="44" width="152" height="24" rx="8" fill="#F8FAFD" stroke="#E3E8EF" strokeWidth="0.8" />
            <text x="22" y="59" fontSize="8.5" fontWeight="medium" fill="#48566A">
              eGFR: 38 mL/min • Cr: 142
            </text>
          </g>

          {/* Node 3: Pharmacology (Iris) */}
          <g id="node-pharmacology" transform="translate(30, 380)">
            <rect
              x="0"
              y="0"
              width="180"
              height="80"
              rx="16"
              fill="#FFFFFF"
              stroke="#8B7CF6"
              strokeWidth={normalizedStage === 2 ? "2" : "1"}
              filter={`url(#${uid}-cardShadow)`}
            />
            {/* Accent left indicator */}
            <rect x="0" y="0" width="5" height="80" rx="2.5" fill="#8B7CF6" />

            {/* Header Icon + Title */}
            <circle cx="24" cy="24" r="10" fill="#F5F3FF" stroke="#8B7CF6" strokeWidth="1" />
            <text x="24" y="27.5" textAnchor="middle" fontSize="9" fill="#8B7CF6">⬡</text>
            <text x="42" y="22" fontSize="11" fontWeight="bold" fill="#162033">
              Dược lâm sàng
            </text>
            <text x="42" y="33" fontSize="8.5" fontWeight="semibold" fill="#8B7CF6">
              Pharmacology Spec
            </text>

            {/* Metric pill */}
            <rect x="14" y="44" width="152" height="24" rx="8" fill="#F8FAFD" stroke="#E3E8EF" strokeWidth="0.8" />
            <text x="22" y="59" fontSize="8.5" fontWeight="medium" fill="#48566A">
              Metformin 1000mg • Risk DDI
            </text>
          </g>

          {/* ========================================================================= */}
          {/* 4. UNIFIED STRUCTURED DECISION RESULT PLANE (RIGHT SIDE)                  */}
          {/* ========================================================================= */}
          <g id="decision-result-plane">
            {/* Outer Decision Plane Backdrop Canvas */}
            <rect
              x="580"
              y="30"
              width="330"
              height="460"
              rx="22"
              fill="#FFFFFF"
              stroke="#D5DDE7"
              strokeWidth="1.5"
              filter={`url(#${uid}-cardShadow)`}
            />

            {/* Plane Header Bar */}
            <rect x="580" y="30" width="330" height="42" rx="22" fill="#F8FAFD" />
            <rect x="580" y="60" width="330" height="12" fill="#F8FAFD" />
            <line x1="580" y1="72" x2="910" y2="72" stroke="#E3E8EF" strokeWidth="1" />
            
            <circle cx="602" cy="51" r="5" fill="#0B6FD8" />
            <circle cx="616" cy="51" r="5" fill="#14A88D" />
            <circle cx="630" cy="51" r="5" fill="#8B7CF6" />
            <text x="646" y="55" fontSize="11" fontWeight="bold" fill="#162033">
              KẾT QUẢ HỘI CHẨN CẤU TRÚC
            </text>
            <rect x="836" y="42" width="60" height="18" rx="6" fill="#EFF7FF" stroke="#0B6FD8" strokeWidth="0.8" />
            <text x="866" y="54" textAnchor="middle" fontSize="8" fontWeight="bold" fill="#0B6FD8">
              FIDES VETTED
            </text>

            {/* LAYER 1: Recommendation Synthesis */}
            <g
              id="layer-recommendation"
              transform="translate(595, 84)"
              style={{ cursor: "pointer" }}
              onClick={() => onStageChange?.(1)}
            >
              <rect
                x="0"
                y="0"
                width="300"
                height="86"
                rx="14"
                fill={normalizedStage === 1 ? "#EFF7FF" : "#FFFFFF"}
                stroke={normalizedStage === 1 ? "#0B6FD8" : "#E3E8EF"}
                strokeWidth={normalizedStage === 1 ? "1.8" : "1"}
                filter={normalizedStage === 1 ? `url(#${uid}-activeShadow)` : undefined}
              />
              <circle cx="16" cy="18" r="8" fill={normalizedStage === 1 ? "#0B6FD8" : "#EFF7FF"} />
              <text x="16" y="21.5" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill={normalizedStage === 1 ? "#FFFFFF" : "#0B6FD8"}>
                01
              </text>
              <text x="32" y="21" fontSize="10.5" fontWeight="bold" fill="#0B6FD8">
                Khuyến nghị tổng hợp
              </text>
              <text x="16" y="42" fontSize="9" fontWeight="medium" fill="#162033">
                • Cân nhắc giảm liều/ngừng Metformin (eGFR 38)
              </text>
              <text x="16" y="56" fontSize="9" fontWeight="medium" fill="#162033">
                • Chuyển đổi SGLT2i chỉnh theo mức lọc cầu thận
              </text>
              <text x="16" y="70" fontSize="8.5" fontWeight="normal" fill="#6D7A8E">
                Đồng thuận: Tim mạch & Thận học
              </text>
            </g>

            {/* LAYER 2: Specialty Disagreements */}
            <g
              id="layer-disagreements"
              transform="translate(595, 180)"
              style={{ cursor: "pointer" }}
              onClick={() => onStageChange?.(2)}
            >
              <rect
                x="0"
                y="0"
                width="300"
                height="86"
                rx="14"
                fill={normalizedStage === 2 ? "#FFF1F2" : "#FFFFFF"}
                stroke={normalizedStage === 2 ? "#E11D48" : "#E3E8EF"}
                strokeWidth={normalizedStage === 2 ? "1.8" : "1"}
                filter={normalizedStage === 2 ? `url(#${uid}-activeShadow)` : undefined}
              />
              <circle cx="16" cy="18" r="8" fill={normalizedStage === 2 ? "#E11D48" : "#FFF1F2"} />
              <text x="16" y="21.5" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill={normalizedStage === 2 ? "#FFFFFF" : "#E11D48"}>
                02
              </text>
              <text x="32" y="21" fontSize="10.5" fontWeight="bold" fill="#BE123C">
                Điểm bất đồng chuyên khoa
              </text>
              <text x="16" y="42" fontSize="9" fontWeight="medium" fill="#162033">
                • Dược: Đề xuất ngừng hẳn Metformin ngay lập tức
              </text>
              <text x="16" y="56" fontSize="9" fontWeight="medium" fill="#162033">
                • Tim mạch: Duy trì 500mg kèm giám sát eGFR
              </text>
              <text x="16" y="70" fontSize="8.5" fontWeight="bold" fill="#E11D48">
                Cần quyết định lâm sàng của Bác sĩ điều trị
              </text>
            </g>

            {/* LAYER 3: Missing Context & Uncertainty */}
            <g
              id="layer-uncertainty"
              transform="translate(595, 276)"
              style={{ cursor: "pointer" }}
              onClick={() => onStageChange?.(3)}
            >
              <rect
                x="0"
                y="0"
                width="300"
                height="86"
                rx="14"
                fill={normalizedStage === 3 ? "#FFFBEB" : "#FFFFFF"}
                stroke={normalizedStage === 3 ? "#D97706" : "#E3E8EF"}
                strokeWidth={normalizedStage === 3 ? "1.8" : "1"}
                filter={normalizedStage === 3 ? `url(#${uid}-activeShadow)` : undefined}
              />
              <circle cx="16" cy="18" r="8" fill={normalizedStage === 3 ? "#D97706" : "#FEF3C7"} />
              <text x="16" y="21.5" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill={normalizedStage === 3 ? "#FFFFFF" : "#D97706"}>
                03
              </text>
              <text x="32" y="21" fontSize="10.5" fontWeight="bold" fill="#B45309">
                Điều chưa đủ dữ liệu
              </text>
              <text x="16" y="42" fontSize="9" fontWeight="medium" fill="#162033">
                • Chưa có chỉ số uACR niệu gần nhất
              </text>
              <text x="16" y="56" fontSize="9" fontWeight="medium" fill="#162033">
                • Thiếu điện giải đồ Kali/Natri máu hiện tại
              </text>
              <text x="16" y="70" fontSize="8.5" fontWeight="normal" fill="#92400E">
                Phân loại: Cần chỉ định xét nghiệm bổ sung
              </text>
            </g>

            {/* LAYER 4: Action Plan & Next Steps */}
            <g
              id="layer-nextsteps"
              transform="translate(595, 372)"
              style={{ cursor: "pointer" }}
              onClick={() => onStageChange?.(4)}
            >
              <rect
                x="0"
                y="0"
                width="300"
                height="92"
                rx="14"
                fill={normalizedStage === 4 ? "#ECFDF8" : "#FFFFFF"}
                stroke={normalizedStage === 4 ? "#14A88D" : "#E3E8EF"}
                strokeWidth={normalizedStage === 4 ? "1.8" : "1"}
                filter={normalizedStage === 4 ? `url(#${uid}-activeShadow)` : undefined}
              />
              <circle cx="16" cy="18" r="8" fill={normalizedStage === 4 ? "#14A88D" : "#ECFDF8"} />
              <text x="16" y="21.5" textAnchor="middle" fontSize="8.5" fontWeight="bold" fill={normalizedStage === 4 ? "#FFFFFF" : "#14A88D"}>
                04
              </text>
              <text x="32" y="21" fontSize="10.5" fontWeight="bold" fill="#0E856F">
                Bước tiếp theo cho Bác sĩ
              </text>
              <text x="16" y="42" fontSize="9" fontWeight="medium" fill="#162033">
                1. Chỉ định xét nghiệm: uACR + K+/Na+
              </text>
              <text x="16" y="56" fontSize="9" fontWeight="medium" fill="#162033">
                2. Hẹn tái khám đánh giá đáp ứng sau 14 ngày
              </text>
              <text x="16" y="72" fontSize="8.5" fontWeight="semibold" fill="#14A88D">
                Nguồn: KDIGO 2023 • ADA Standards 2024
              </text>
            </g>
          </g>
        </svg>
      </div>

      {/* Interactive Stage Context Description Footer */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-3.5 border border-[#E3E8EF] text-xs">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-[#0B6FD8] animate-pulse" />
          <span className="font-semibold text-[#162033]">
            {stageAriaDescription}
          </span>
        </div>
        <div className="text-[11px] text-[#6D7A8E]">
          <span>Phân tầng: </span>
          <strong className="text-[#0B6FD8]">Tim mạch</strong> (Azure) •{" "}
          <strong className="text-[#14A88D]">Thận học</strong> (Mint) •{" "}
          <strong className="text-[#8B7CF6]">Dược lâm sàng</strong> (Iris)
        </div>
      </div>
    </div>
  );
}

export default DecisionField;
