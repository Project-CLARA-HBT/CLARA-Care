"use client";

import React, { useId, useMemo } from "react";

export type TodayBeaconTone = "azure" | "mint" | "iris";
export type TodayBeaconSize = "sm" | "md" | "lg";
export type TodayBeaconPlacement = "right" | "bottom" | "top" | "badge" | "none";

export interface TodayBeaconProps {
  /**
   * Whether the beacon is actively pulsing and highlighted (defaults to true).
   */
  active?: boolean;
  /**
   * Text label marking the current temporal moment (e.g., "Hôm nay", "Today", "Hiện tại").
   */
  label?: string;
  /**
   * Brand color tone palette ("azure" | "mint" | "iris", defaults to "azure").
   */
  tone?: TodayBeaconTone;
  /**
   * Additional CSS classes for the root container.
   */
  className?: string;
  /**
   * Size variant of the beacon artwork ("sm" | "md" | "lg", defaults to "md").
   */
  size?: TodayBeaconSize;
  /**
   * Placement of the label relative to the beacon node ("right" | "bottom" | "top" | "badge" | "none", defaults to "right").
   */
  labelPlacement?: TodayBeaconPlacement;
  /**
   * Whether to display the text label badge alongside the beacon (defaults to true if label is provided).
   */
  showLabel?: boolean;
  /**
   * Optional inline styles for custom positioning.
   */
  style?: React.CSSProperties;
  /**
   * Optional accessible label override.
   */
  ariaLabel?: string;
  /**
   * Optional click handler for interactive timeline selection.
   */
  onClick?: () => void;
}

interface ToneTokens {
  accent: string;
  bright: string;
  soft: string;
  glowAura: string;
  ringOuterStroke: string;
  ringOuterFill: string;
  ringMidStroke: string;
  ringInnerStroke: string;
  ringInnerFill: string;
  crosshairStroke: string;
  coreGradStart: string;
  coreGradMid: string;
  coreGradEnd: string;
  coreBorder: string;
  badgeBg: string;
  badgeBorder: string;
  badgeText: string;
  badgeDot: string;
  boxShadow: string;
}

const TONE_CONFIG: Record<TodayBeaconTone, ToneTokens> = {
  azure: {
    accent: "#0B6FD8",
    bright: "#1A86F5",
    soft: "#EFF7FF",
    glowAura:
      "radial-gradient(circle, rgba(26, 134, 245, 0.35) 0%, rgba(11, 111, 216, 0.12) 50%, transparent 75%)",
    ringOuterStroke: "rgba(26, 134, 245, 0.3)",
    ringOuterFill: "rgba(11, 111, 216, 0.04)",
    ringMidStroke: "#1A86F5",
    ringInnerStroke: "#0B6FD8",
    ringInnerFill: "rgba(11, 111, 216, 0.12)",
    crosshairStroke: "#0B6FD8",
    coreGradStart: "#EFF7FF",
    coreGradMid: "#1A86F5",
    coreGradEnd: "#0B6FD8",
    coreBorder: "rgba(255, 255, 255, 0.95)",
    badgeBg: "bg-[#EFF7FF]",
    badgeBorder: "border-[#B2DDFF]",
    badgeText: "text-[#0B6FD8]",
    badgeDot: "bg-[#0B6FD8]",
    boxShadow: "0 0 16px rgba(26, 134, 245, 0.35), 0 0 32px rgba(11, 111, 216, 0.15)",
  },
  mint: {
    accent: "#14A88D",
    bright: "#2DD4BF",
    soft: "#ECFDF8",
    glowAura:
      "radial-gradient(circle, rgba(20, 168, 141, 0.35) 0%, rgba(14, 133, 111, 0.12) 50%, transparent 75%)",
    ringOuterStroke: "rgba(45, 212, 191, 0.3)",
    ringOuterFill: "rgba(20, 168, 141, 0.04)",
    ringMidStroke: "#2DD4BF",
    ringInnerStroke: "#14A88D",
    ringInnerFill: "rgba(20, 168, 141, 0.12)",
    crosshairStroke: "#14A88D",
    coreGradStart: "#ECFDF8",
    coreGradMid: "#2DD4BF",
    coreGradEnd: "#14A88D",
    coreBorder: "rgba(255, 255, 255, 0.95)",
    badgeBg: "bg-[#ECFDF8]",
    badgeBorder: "border-[#A6F4C5]",
    badgeText: "text-[#0E856F]",
    badgeDot: "bg-[#14A88D]",
    boxShadow: "0 0 16px rgba(20, 168, 141, 0.35), 0 0 32px rgba(14, 133, 111, 0.15)",
  },
  iris: {
    accent: "#8B7CF6",
    bright: "#A78BFA",
    soft: "#F5F3FF",
    glowAura:
      "radial-gradient(circle, rgba(139, 124, 246, 0.35) 0%, rgba(109, 91, 208, 0.12) 50%, transparent 75%)",
    ringOuterStroke: "rgba(167, 139, 250, 0.3)",
    ringOuterFill: "rgba(139, 124, 246, 0.04)",
    ringMidStroke: "#A78BFA",
    ringInnerStroke: "#8B7CF6",
    ringInnerFill: "rgba(139, 124, 246, 0.12)",
    crosshairStroke: "#8B7CF6",
    coreGradStart: "#F5F3FF",
    coreGradMid: "#A78BFA",
    coreGradEnd: "#8B7CF6",
    coreBorder: "rgba(255, 255, 255, 0.95)",
    badgeBg: "bg-[#F5F3FF]",
    badgeBorder: "border-[#DDD6FE]",
    badgeText: "text-[#6D5BD0]",
    badgeDot: "bg-[#8B7CF6]",
    boxShadow: "0 0 16px rgba(139, 124, 246, 0.35), 0 0 32px rgba(109, 91, 208, 0.15)",
  },
};

const SIZE_CONFIG: Record<
  TodayBeaconSize,
  {
    nodeBox: string;
    outerAura: string;
    badgeTextSize: string;
    dotSize: string;
    gap: string;
  }
> = {
  sm: {
    nodeBox: "w-8 h-8 min-w-[2rem] min-h-[2rem]",
    outerAura: "-inset-1.5",
    badgeTextSize: "text-[10px] px-2 py-0.5",
    dotSize: "h-1.5 w-1.5",
    gap: "gap-1.5",
  },
  md: {
    nodeBox: "w-12 h-12 min-w-[3rem] min-h-[3rem]",
    outerAura: "-inset-2.5",
    badgeTextSize: "text-[11px] px-2.5 py-0.5",
    dotSize: "h-2 w-2",
    gap: "gap-2.5",
  },
  lg: {
    nodeBox: "w-16 h-16 min-w-[4rem] min-h-[4rem]",
    outerAura: "-inset-3.5",
    badgeTextSize: "text-xs px-3 py-1",
    dotSize: "h-2.5 w-2.5",
    gap: "gap-3",
  },
};

/**
 * TodayBeacon Artwork Component
 *
 * Renders the "Today" spatial pulse anchor marking the present moment on the timeline.
 * Features:
 * - Luminous central node with specular gloss and micro-flare core
 * - Subtle concentric ring waves (radiant outer pulse, middle constellation line, inner core halo)
 * - Precision temporal crosshair ticks (N, S, E, W)
 * - Crisp static rendering in Reduced Motion and Lite modes
 * - Zero medical severity encoding (pure temporal & spatial navigation anchor)
 */
export function TodayBeacon({
  active = true,
  label = "Hôm nay",
  tone = "azure",
  className = "",
  size = "md",
  labelPlacement = "right",
  showLabel = true,
  style,
  ariaLabel,
  onClick,
}: TodayBeaconProps) {
  const uid = useId().replace(/:/g, "_");
  const coreGradId = `beacon-core-${uid}`;
  const specGradId = `beacon-spec-${uid}`;
  const haloGradId = `beacon-halo-${uid}`;

  const currentTone = TONE_CONFIG[tone] ?? TONE_CONFIG.azure;
  const currentSize = SIZE_CONFIG[size] ?? SIZE_CONFIG.md;

  const accessibleText = ariaLabel || label || "Today timeline beacon";
  const shouldRenderLabel = Boolean(showLabel && label && labelPlacement !== "none");

  // Determine layout class according to label placement
  const layoutClasses = useMemo(() => {
    switch (labelPlacement) {
      case "bottom":
        return "flex-col items-center text-center";
      case "top":
        return "flex-col-reverse items-center text-center";
      case "badge":
        return "relative items-center";
      case "right":
      default:
        return "flex-row items-center";
    }
  }, [labelPlacement]);

  const interactiveClasses = onClick
    ? "cursor-pointer select-none transition-transform duration-200 ease-out hover:scale-105 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#0B6FD8]"
    : "";

  return (
    <div
      data-testid="today-beacon"
      data-artwork="today-beacon"
      data-active={active}
      data-tone={tone}
      data-size={size}
      role={onClick ? "button" : "status"}
      aria-label={accessibleText}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={`relative inline-flex ${layoutClasses} ${currentSize.gap} ${interactiveClasses} ${className}`}
      style={style}
    >
      {/* Node Container */}
      <div
        className={`relative inline-flex items-center justify-center ${currentSize.nodeBox} shrink-0`}
        aria-hidden="true"
      >
        {/* Layer 1: Ambient Outer Radial Glow Field */}
        <div
          className={`absolute ${currentSize.outerAura} rounded-full blur-md transition-opacity duration-300 pointer-events-none ${
            active
              ? "opacity-85 motion-reduce:opacity-60"
              : "opacity-25 motion-reduce:opacity-20"
          }`}
          style={{ background: currentTone.glowAura }}
        />

        {/* Layer 2: Precision SVG Concentric Waves & Central Beacon Node */}
        <svg
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="relative z-10 w-full h-full transform transition-transform duration-300 motion-reduce:transform-none"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            {/* Luminous Core Gradient */}
            <radialGradient
              id={coreGradId}
              cx="35%"
              cy="32%"
              r="68%"
              fx="35%"
              fy="32%"
            >
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.98" />
              <stop offset="25%" stopColor={currentTone.coreGradStart} />
              <stop offset="60%" stopColor={currentTone.coreGradMid} />
              <stop offset="100%" stopColor={currentTone.coreGradEnd} />
            </radialGradient>

            {/* Specular Highlight Gloss Gradient */}
            <radialGradient
              id={specGradId}
              cx="38%"
              cy="35%"
              r="55%"
              fx="38%"
              fy="35%"
            >
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
              <stop offset="65%" stopColor="#FFFFFF" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </radialGradient>

            {/* Outer Halo Wave Gradient */}
            <radialGradient id={haloGradId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={currentTone.bright} stopOpacity="0.35" />
              <stop offset="60%" stopColor={currentTone.accent} stopOpacity="0.12" />
              <stop offset="100%" stopColor={currentTone.accent} stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Concentric Ring Wave 1: Radiant Outer Ring */}
          <circle
            cx="32"
            cy="32"
            r="28"
            fill={`url(#${haloGradId})`}
            stroke={currentTone.ringOuterStroke}
            strokeWidth="1"
            className={
              active
                ? "motion-safe:animate-[ping_3.2s_cubic-bezier(0,0,0.2,1)_infinite] motion-reduce:animate-none opacity-40 motion-reduce:opacity-30"
                : "opacity-15"
            }
          />

          {/* Concentric Ring Wave 2: Middle Constellation Track */}
          <circle
            cx="32"
            cy="32"
            r="20"
            fill="none"
            stroke={currentTone.ringMidStroke}
            strokeWidth="1.25"
            strokeDasharray="3 3"
            className={
              active
                ? "motion-safe:animate-[pulse_2.4s_ease-in-out_infinite] motion-reduce:animate-none opacity-70 motion-reduce:opacity-50"
                : "opacity-25"
            }
          />

          {/* Concentric Ring Wave 3: Inner Radiant Core Aura */}
          <circle
            cx="32"
            cy="32"
            r="14"
            fill={currentTone.ringInnerFill}
            stroke={currentTone.ringInnerStroke}
            strokeWidth="1"
            className={
              active
                ? "motion-safe:animate-[pulse_1.8s_ease-in-out_infinite] motion-reduce:animate-none opacity-85 motion-reduce:opacity-60"
                : "opacity-35"
            }
          />

          {/* Spatial Precision Crosshairs / Temporal Calibration Ticks */}
          <g
            className={`transition-opacity duration-300 ${
              active ? "opacity-80 motion-reduce:opacity-65" : "opacity-30"
            }`}
          >
            {/* North Tick */}
            <line
              x1="32"
              y1="3"
              x2="32"
              y2="8"
              stroke={currentTone.crosshairStroke}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            {/* South Tick */}
            <line
              x1="32"
              y1="56"
              x2="32"
              y2="61"
              stroke={currentTone.crosshairStroke}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            {/* West Tick */}
            <line
              x1="3"
              y1="32"
              x2="8"
              y2="32"
              stroke={currentTone.crosshairStroke}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            {/* East Tick */}
            <line
              x1="56"
              y1="32"
              x2="61"
              y2="32"
              stroke={currentTone.crosshairStroke}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </g>

          {/* Luminous Central Core Sphere Disc */}
          <circle
            cx="32"
            cy="32"
            r="8.5"
            fill={`url(#${coreGradId})`}
            stroke={currentTone.coreBorder}
            strokeWidth="1.5"
          />

          {/* Specular Highlight Crescent */}
          <ellipse
            cx="30.5"
            cy="29.5"
            rx="4"
            ry="2.2"
            transform="rotate(-30 30.5 29.5)"
            fill={`url(#${specGradId})`}
          />

          {/* Central Pin Micro-Sparkle Dot */}
          <circle cx="32" cy="32" r="1.75" fill="#FFFFFF" />

          {/* Diamond Micro-Flare */}
          <path
            d="M 32 29 C 32 30.8 30.8 32 29 32 C 30.8 32 32 33.2 32 35 C 32 33.2 33.2 32 35 32 C 33.2 32 32 30.8 32 29 Z"
            fill="#FFFFFF"
            opacity="0.9"
          />
        </svg>
      </div>

      {/* Label Badge / Anchor Tag */}
      {shouldRenderLabel && (
        <div
          className={`inline-flex items-center gap-1.5 rounded-full border font-bold uppercase tracking-wider shadow-xs backdrop-blur-sm transition-all duration-200 ${
            labelPlacement === "badge" ? "absolute -top-2.5 right-0 z-20" : ""
          } ${currentTone.badgeBg} ${currentTone.badgeBorder} ${currentTone.badgeText} ${
            currentSize.badgeTextSize
          } ${active ? "opacity-100" : "opacity-70"}`}
        >
          {/* Micro-beacon dot inside badge */}
          <span className="relative flex items-center justify-center shrink-0">
            {active && (
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 motion-safe:animate-ping motion-reduce:hidden ${currentTone.badgeDot}`}
              />
            )}
            <span
              className={`relative inline-flex rounded-full ${currentSize.dotSize} ${currentTone.badgeDot}`}
            />
          </span>
          <span className="truncate">{label}</span>
        </div>
      )}
    </div>
  );
}

export default TodayBeacon;
