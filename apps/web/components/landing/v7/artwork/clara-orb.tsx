"use client";

import React, { useId, useMemo } from "react";

export type ClaraOrbSize = "sm" | "md" | "lg" | "xl";
export type ClaraOrbTone = "azure" | "mint" | "iris" | "neutral";

export interface ClaraOrbProps {
  /** Size variant of the orb artwork */
  size?: ClaraOrbSize;
  /** Brand color tone palette (pure product/interaction anchor, no medical severity) */
  tone?: ClaraOrbTone;
  /** Whether ambient soft pulse animation is enabled (defaults to true) */
  pulse?: boolean;
  /** Whether interactive hover and focus transitions are enabled (defaults to false) */
  interactive?: boolean;
  /** Additional CSS class names */
  className?: string;
  /** Optional inline styles for custom positioning */
  style?: React.CSSProperties;
}

interface ToneColorTokens {
  glowAura: string;
  coreRadial: string;
  pulseBorderOuter: string;
  pulseBorderInner: string;
  pulseGlowBg: string;
  orbitStroke: string;
  orbitStrokeSecondary: string;
  gradientStopStart: string;
  gradientStopMid: string;
  gradientStopEnd: string;
  coreHighlight: string;
  sparkleFill: string;
  satelliteFill: string;
  boxShadow: string;
}

const TONE_CONFIG: Record<ClaraOrbTone, ToneColorTokens> = {
  azure: {
    glowAura:
      "radial-gradient(circle, rgba(26, 134, 245, 0.32) 0%, rgba(11, 111, 216, 0.14) 45%, transparent 72%)",
    coreRadial:
      "radial-gradient(circle at 34% 30%, #EFF7FF 0%, #BAE6FD 20%, #1A86F5 55%, #0B6FD8 85%, #084C99 100%)",
    pulseBorderOuter: "rgba(75, 167, 255, 0.35)",
    pulseBorderInner: "rgba(185, 220, 255, 0.45)",
    pulseGlowBg: "rgba(11, 111, 216, 0.12)",
    orbitStroke: "rgba(56, 189, 248, 0.4)",
    orbitStrokeSecondary: "rgba(14, 165, 233, 0.2)",
    gradientStopStart: "#BAE6FD",
    gradientStopMid: "#1A86F5",
    gradientStopEnd: "#0B6FD8",
    coreHighlight: "#FFFFFF",
    sparkleFill: "#FFFFFF",
    satelliteFill: "#38BDF8",
    boxShadow: "0 0 24px rgba(26, 134, 245, 0.4), 0 0 48px rgba(11, 111, 216, 0.18)",
  },
  mint: {
    glowAura:
      "radial-gradient(circle, rgba(20, 168, 141, 0.32) 0%, rgba(15, 138, 117, 0.14) 45%, transparent 72%)",
    coreRadial:
      "radial-gradient(circle at 34% 30%, #ECFDF8 0%, #A7F3DF 20%, #14A88D 55%, #0F8A75 85%, #0A5C4F 100%)",
    pulseBorderOuter: "rgba(58, 210, 182, 0.35)",
    pulseBorderInner: "rgba(167, 243, 223, 0.45)",
    pulseGlowBg: "rgba(20, 168, 141, 0.12)",
    orbitStroke: "rgba(94, 234, 212, 0.4)",
    orbitStrokeSecondary: "rgba(20, 184, 166, 0.2)",
    gradientStopStart: "#A7F3DF",
    gradientStopMid: "#14A88D",
    gradientStopEnd: "#0F8A75",
    coreHighlight: "#FFFFFF",
    sparkleFill: "#FFFFFF",
    satelliteFill: "#2DD4BF",
    boxShadow: "0 0 24px rgba(20, 168, 141, 0.4), 0 0 48px rgba(15, 138, 117, 0.18)",
  },
  iris: {
    glowAura:
      "radial-gradient(circle, rgba(139, 124, 246, 0.32) 0%, rgba(117, 102, 232, 0.14) 45%, transparent 72%)",
    coreRadial:
      "radial-gradient(circle at 34% 30%, #F5F3FF 0%, #DDD6FE 20%, #8B7CF6 55%, #7566E8 85%, #5849C4 100%)",
    pulseBorderOuter: "rgba(167, 139, 250, 0.35)",
    pulseBorderInner: "rgba(221, 214, 254, 0.45)",
    pulseGlowBg: "rgba(139, 124, 246, 0.12)",
    orbitStroke: "rgba(196, 181, 253, 0.4)",
    orbitStrokeSecondary: "rgba(168, 85, 247, 0.2)",
    gradientStopStart: "#DDD6FE",
    gradientStopMid: "#8B7CF6",
    gradientStopEnd: "#7566E8",
    coreHighlight: "#FFFFFF",
    sparkleFill: "#FFFFFF",
    satelliteFill: "#C084FC",
    boxShadow: "0 0 24px rgba(139, 124, 246, 0.4), 0 0 48px rgba(117, 102, 232, 0.18)",
  },
  neutral: {
    glowAura:
      "radial-gradient(circle, rgba(148, 163, 184, 0.26) 0%, rgba(100, 116, 139, 0.1) 45%, transparent 72%)",
    coreRadial:
      "radial-gradient(circle at 34% 30%, #F8FAFC 0%, #E2E8F0 20%, #94A3B8 55%, #64748B 85%, #475569 100%)",
    pulseBorderOuter: "rgba(148, 163, 184, 0.35)",
    pulseBorderInner: "rgba(226, 232, 240, 0.45)",
    pulseGlowBg: "rgba(100, 116, 139, 0.1)",
    orbitStroke: "rgba(203, 213, 225, 0.4)",
    orbitStrokeSecondary: "rgba(148, 163, 184, 0.2)",
    gradientStopStart: "#E2E8F0",
    gradientStopMid: "#94A3B8",
    gradientStopEnd: "#64748B",
    coreHighlight: "#FFFFFF",
    sparkleFill: "#FFFFFF",
    satelliteFill: "#CBD5E1",
    boxShadow: "0 0 20px rgba(148, 163, 184, 0.3), 0 0 40px rgba(100, 116, 139, 0.12)",
  },
};

const SIZE_CONFIG: Record<
  ClaraOrbSize,
  {
    container: string;
    outerAuraPadding: string;
    coreScaleClass: string;
  }
> = {
  sm: {
    container: "w-8 h-8 min-w-[2rem] min-h-[2rem]",
    outerAuraPadding: "-inset-2",
    coreScaleClass: "scale-90",
  },
  md: {
    container: "w-14 h-14 min-w-[3.5rem] min-h-[3.5rem]",
    outerAuraPadding: "-inset-3",
    coreScaleClass: "scale-100",
  },
  lg: {
    container: "w-20 h-20 min-w-[5rem] min-h-[5rem]",
    outerAuraPadding: "-inset-4",
    coreScaleClass: "scale-105",
  },
  xl: {
    container: "w-32 h-32 min-w-[8rem] min-h-[8rem]",
    outerAuraPadding: "-inset-6",
    coreScaleClass: "scale-110",
  },
};

/**
 * ClaraOrb
 *
 * Signature brand artwork anchor for CLARA Landing & Product surfaces.
 * Combines multi-layer soft pulse halos, CSS radial gradients, and precision
 * SVG orbital geometry.
 *
 * Requirements:
 * - Pure brand/interaction artwork anchor (Zero medical diagnosis/severity encoding)
 * - Rendered cleanly with aria-hidden="true" (pure artwork)
 * - Full Lite / Reduced Motion mode support (crisp static artwork without animation loops)
 * - Tones: azure | mint | iris | neutral
 * - Sizes: sm | md | lg | xl
 */
export function ClaraOrb({
  size = "md",
  tone = "azure",
  pulse = true,
  interactive = false,
  className = "",
  style,
}: ClaraOrbProps) {
  const uniqueId = useId().replace(/:/g, "_");
  const gradientId = `clara-orb-grad-${uniqueId}`;
  const coreGradId = `clara-orb-core-${uniqueId}`;
  const specGradId = `clara-orb-spec-${uniqueId}`;

  const currentTone = TONE_CONFIG[tone] ?? TONE_CONFIG.azure;
  const currentSize = SIZE_CONFIG[size] ?? SIZE_CONFIG.md;

  const pulseClasses = useMemo(() => {
    if (!pulse) return { outer: "", mid: "", inner: "" };
    return {
      outer: "motion-safe:animate-[ping_3.6s_cubic-bezier(0,0,0.2,1)_infinite] motion-reduce:animate-none",
      mid: "motion-safe:animate-[pulse_3s_ease-in-out_infinite] motion-reduce:animate-none",
      inner: "motion-safe:animate-[pulse_2.2s_ease-in-out_infinite] motion-reduce:animate-none",
    };
  }, [pulse]);

  const interactiveClasses = interactive
    ? "cursor-pointer transition-transform duration-300 ease-out hover:scale-105 active:scale-95 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-sky-500"
    : "";

  return (
    <div
      aria-hidden="true"
      data-artwork="clara-orb"
      data-size={size}
      data-tone={tone}
      data-pulse={pulse}
      className={`relative inline-flex items-center justify-center select-none pointer-events-none ${currentSize.container} ${interactiveClasses} ${className}`}
      style={style}
    >
      {/* Layer 1: Atmospheric Outer Glow (CSS Radial Gradient) */}
      <div
        className={`absolute ${currentSize.outerAuraPadding} rounded-full blur-lg opacity-85 pointer-events-none transition-opacity duration-500 motion-reduce:opacity-70`}
        style={{
          background: currentTone.glowAura,
        }}
      />

      {/* Layer 2: Multi-layer Soft Pulse Halos */}
      {pulse && (
        <>
          {/* Outer expanding pulse halo */}
          <div
            className={`absolute -inset-2.5 rounded-full border opacity-30 pointer-events-none ${pulseClasses.outer}`}
            style={{
              borderColor: currentTone.pulseBorderOuter,
              backgroundColor: currentTone.pulseGlowBg,
            }}
          />

          {/* Middle soft breathing pulse aura */}
          <div
            className={`absolute -inset-1 rounded-full border backdrop-blur-[0.5px] opacity-45 pointer-events-none ${pulseClasses.mid}`}
            style={{
              borderColor: currentTone.pulseBorderInner,
              backgroundColor: currentTone.pulseGlowBg,
            }}
          />
        </>
      )}

      {/* Layer 3: Static Structural Glassmorphism Ring (Crisp Anchor in Lite / Reduced Motion) */}
      <div
        className="absolute inset-0 rounded-full border shadow-sm pointer-events-none backdrop-blur-[1px] transition-all duration-300"
        style={{
          borderColor: currentTone.pulseBorderInner,
          boxShadow: currentTone.boxShadow,
        }}
      />

      {/* Layer 4: Precision SVG Vector Artwork & Orbital Geometry */}
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`relative z-10 w-full h-full transform transition-transform duration-300 ${currentSize.coreScaleClass} motion-reduce:transform-none`}
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          {/* Linear Brand Stroke Gradient */}
          <linearGradient
            id={gradientId}
            x1="10"
            y1="10"
            x2="90"
            y2="90"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor={currentTone.gradientStopStart} />
            <stop offset="50%" stopColor={currentTone.gradientStopMid} />
            <stop offset="100%" stopColor={currentTone.gradientStopEnd} />
          </linearGradient>

          {/* Sphere Core Radial Gradient */}
          <radialGradient
            id={coreGradId}
            cx="36%"
            cy="32%"
            r="68%"
            fx="36%"
            fy="32%"
          >
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
            <stop offset="22%" stopColor={currentTone.gradientStopStart} />
            <stop offset="58%" stopColor={currentTone.gradientStopMid} />
            <stop offset="90%" stopColor={currentTone.gradientStopEnd} />
            <stop offset="100%" stopColor="#0B274D" />
          </radialGradient>

          {/* Specular Highlight Gloss Gradient */}
          <radialGradient
            id={specGradId}
            cx="40%"
            cy="35%"
            r="50%"
            fx="40%"
            fy="35%"
          >
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.85" />
            <stop offset="60%" stopColor="#FFFFFF" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Outer Orbital Perimeter Track */}
        <circle
          cx="50"
          cy="50"
          r="44"
          stroke={currentTone.orbitStrokeSecondary}
          strokeWidth="1"
          strokeDasharray="3 3"
        />

        {/* Equatorial Tilted Orbit Ring */}
        <ellipse
          cx="50"
          cy="50"
          rx="43"
          ry="17"
          transform="rotate(-26 50 50)"
          stroke={currentTone.orbitStroke}
          strokeWidth="1.25"
        />

        {/* Satellite Node Pin on Orbit Track */}
        <circle
          cx="82"
          cy="34"
          r="2.5"
          fill={currentTone.satelliteFill}
          stroke="#FFFFFF"
          strokeWidth="0.75"
        />

        {/* Core Sphere Disc */}
        <circle
          cx="50"
          cy="50"
          r="29"
          fill={`url(#${coreGradId})`}
          stroke="rgba(255, 255, 255, 0.45)"
          strokeWidth="1.25"
        />

        {/* Glossy Upper Specular Crescent / Highlight */}
        <ellipse
          cx="45"
          cy="38"
          rx="15"
          ry="9"
          transform="rotate(-25 45 38)"
          fill={`url(#${specGradId})`}
        />

        {/* Signature Brand Sparkle (4-point Diamond Star) */}
        <path
          d="M 50 35 C 50 43.5 43.5 50 35 50 C 43.5 50 50 56.5 50 65 C 50 56.5 56.5 50 65 50 C 56.5 50 50 43.5 50 35 Z"
          fill={currentTone.sparkleFill}
          opacity="0.95"
        />

        {/* Center Sparkle Pin Dot */}
        <circle cx="50" cy="50" r="1.5" fill="#FFFFFF" />

        {/* Accent Flare Micro-Dot */}
        <circle
          cx="62"
          cy="38"
          r="1.25"
          fill="#FFFFFF"
          opacity="0.8"
        />
      </svg>
    </div>
  );
}

export default ClaraOrb;
