"use client";

import React, { useId } from "react";

export type EvidenceRibbonVariant = "horizontal" | "vertical" | "curved" | "connector";
export type EvidenceRibbonTone = "azure" | "mint" | "iris";

export interface EvidenceRibbonProps {
  /**
   * Spatial vector motif layout variation linking clinical claims to sources:
   * - "horizontal": Linear lateral stream connecting claim card to source badge
   * - "vertical": Longitudinal cascading spline linking query claim to reference evidence
   * - "curved": Sweeping diagonal sigmoid arc spanning multidirectional evidence layers
   * - "connector": Multi-claim intake fork converging into a verified citation beacon
   */
  variant?: EvidenceRibbonVariant;
  /** Brand color tone palette */
  tone?: EvidenceRibbonTone;
  /** Whether the evidence link is active / highlighted */
  active?: boolean;
  /** Additional CSS class names */
  className?: string;
  /** Optional inline styles */
  style?: React.CSSProperties;
}

interface TonePalette {
  start: string;
  mid: string;
  end: string;
  glow: string;
  ambient: string;
  subtleStroke: string;
  accentNode: string;
  beaconStroke: string;
  waypointFill: string;
  highlightGlow: string;
}

const TONE_CONFIG: Record<EvidenceRibbonTone, TonePalette> = {
  azure: {
    start: "#0B6FD8",
    mid: "#1A86F5",
    end: "#38BDF8",
    glow: "rgba(26, 134, 245, 0.45)",
    ambient: "rgba(11, 111, 216, 0.1)",
    subtleStroke: "rgba(11, 111, 216, 0.22)",
    accentNode: "#0B6FD8",
    beaconStroke: "#1A86F5",
    waypointFill: "#38BDF8",
    highlightGlow: "#EFF7FF",
  },
  mint: {
    start: "#0E856F",
    mid: "#14A88D",
    end: "#2DD4BF",
    glow: "rgba(20, 168, 141, 0.45)",
    ambient: "rgba(20, 168, 141, 0.1)",
    subtleStroke: "rgba(20, 168, 141, 0.22)",
    accentNode: "#14A88D",
    beaconStroke: "#2DD4BF",
    waypointFill: "#5EEAD4",
    highlightGlow: "#ECFDF8",
  },
  iris: {
    start: "#6D5BD0",
    mid: "#8B7CF6",
    end: "#C4B5FD",
    glow: "rgba(139, 124, 246, 0.45)",
    ambient: "rgba(139, 124, 246, 0.1)",
    subtleStroke: "rgba(139, 124, 246, 0.22)",
    accentNode: "#8B7CF6",
    beaconStroke: "#A78BFA",
    waypointFill: "#DDD6FE",
    highlightGlow: "#F5F3FF",
  },
};

/**
 * EvidenceRibbon Artwork Component
 *
 * Spatial vector motif connecting clinical claims to primary literature & guidelines.
 * Features smooth bezier curves, subtle multi-stop gradient strokes, dashed flow on desktop,
 * and clean static paths for Lite/Reduced-Motion tiers.
 */
export function EvidenceRibbon({
  variant = "horizontal",
  tone = "azure",
  active = false,
  className = "",
  style,
}: EvidenceRibbonProps) {
  const rawId = useId();
  const uid = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  const gradPrimaryId = `ribbon-grad-pri-${uid}`;
  const gradSubtleId = `ribbon-grad-sub-${uid}`;
  const gradGlowId = `ribbon-grad-glow-${uid}`;
  const filterGlowId = `ribbon-blur-${uid}`;

  const currentTone = TONE_CONFIG[tone] ?? TONE_CONFIG.azure;

  return (
    <div
      aria-hidden="true"
      data-artwork="evidence-ribbon"
      data-variant={variant}
      data-tone={tone}
      data-active={active}
      className={`pointer-events-none relative select-none overflow-visible transition-opacity duration-300 ${
        active ? "opacity-100" : "opacity-75 hover:opacity-90"
      } ${className}`}
      style={style}
    >
      {/* ------------------------------------------------------------------------- */}
      {/* VARIANT: HORIZONTAL                                                       */}
      {/* ------------------------------------------------------------------------- */}
      {variant === "horizontal" && (
        <svg
          viewBox="0 0 480 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-auto w-full overflow-visible"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            <linearGradient id={gradPrimaryId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity={active ? 0.95 : 0.6} />
              <stop offset="50%" stopColor={currentTone.mid} stopOpacity={active ? 1 : 0.8} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.95 : 0.7} />
            </linearGradient>

            <linearGradient id={gradSubtleId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity="0.2" />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity="0.05" />
            </linearGradient>

            <linearGradient id={gradGlowId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.mid} stopOpacity={active ? 0.7 : 0.2} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.8 : 0.25} />
            </linearGradient>

            <filter id={filterGlowId} x="-20%" y="-40%" width="140%" height="180%">
              <feGaussianBlur stdDeviation={active ? "3" : "1.5"} result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Underlay Ambient Track (Static Clean Path) */}
          <path
            d="M 32 50 C 140 20, 200 80, 240 50 C 280 20, 340 80, 448 50"
            stroke={currentTone.subtleStroke}
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Harmonic Envelope Ribbon Paths */}
          <path
            d="M 32 50 C 120 15, 200 70, 240 50 C 280 30, 360 85, 448 50"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M 32 50 C 120 85, 200 30, 240 50 C 280 70, 360 15, 448 50"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Soft Glow Filter Strand (Active) */}
          {active && (
            <path
              d="M 32 50 C 140 20, 200 80, 240 50 C 280 20, 340 80, 448 50"
              stroke={`url(#${gradGlowId})`}
              strokeWidth="5"
              strokeLinecap="round"
              fill="none"
              filter={`url(#${filterGlowId})`}
            />
          )}

          {/* Primary Flowing Gradient Strand (Desktop dashed pulse / Lite clean static) */}
          <path
            d="M 32 50 C 140 20, 200 80, 240 50 C 280 20, 340 80, 448 50"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "2.5" : "2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "8 8" : undefined}
          />

          {/* Start Node: Clinical Claim Anchor */}
          <g transform="translate(32, 50)" id="claim-anchor-node">
            <circle r={active ? 12 : 9} fill={currentTone.ambient} />
            <circle r="6" fill="#FFFFFF" stroke={currentTone.accentNode} strokeWidth="2" />
            <circle r="2.5" fill={currentTone.accentNode} />
          </g>

          {/* Waypoint Node: Context Verification Bridge */}
          <g transform="translate(240, 50)" id="waypoint-bridge-node">
            <rect
              x="-4"
              y="-4"
              width="8"
              height="8"
              transform="rotate(45)"
              fill={active ? currentTone.waypointFill : "#CBD5E1"}
              stroke="#FFFFFF"
              strokeWidth="1.5"
            />
          </g>

          {/* End Node: Verified Evidence Source Beacon */}
          <g transform="translate(448, 50)" id="source-beacon-node">
            <circle r={active ? 14 : 11} fill={currentTone.ambient} />
            <circle
              r="7"
              fill="#FFFFFF"
              stroke={currentTone.beaconStroke}
              strokeWidth="2"
            />
            {/* Citation Diamond Spark */}
            <path
              d="M 0,-3.5 L 2.5,0 L 0,3.5 L -2.5,0 Z"
              fill={currentTone.accentNode}
            />
          </g>
        </svg>
      )}

      {/* ------------------------------------------------------------------------- */}
      {/* VARIANT: VERTICAL                                                         */}
      {/* ------------------------------------------------------------------------- */}
      {variant === "vertical" && (
        <svg
          viewBox="0 0 100 480"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-auto overflow-visible"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            <linearGradient id={gradPrimaryId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity={active ? 0.95 : 0.6} />
              <stop offset="50%" stopColor={currentTone.mid} stopOpacity={active ? 1 : 0.8} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.95 : 0.7} />
            </linearGradient>

            <linearGradient id={gradSubtleId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity="0.2" />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity="0.05" />
            </linearGradient>

            <linearGradient id={gradGlowId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={currentTone.mid} stopOpacity={active ? 0.7 : 0.2} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.8 : 0.25} />
            </linearGradient>

            <filter id={filterGlowId} x="-40%" y="-20%" width="180%" height="140%">
              <feGaussianBlur stdDeviation={active ? "3" : "1.5"} result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Underlay Ambient Track */}
          <path
            d="M 50 32 C 20 140, 80 200, 50 240 C 20 280, 80 340, 50 448"
            stroke={currentTone.subtleStroke}
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Harmonic Envelope Strands */}
          <path
            d="M 50 32 C 15 120, 70 200, 50 240 C 30 280, 85 360, 50 448"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M 50 32 C 85 120, 30 200, 50 240 C 70 280, 15 360, 50 448"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Glowing Active Underlay */}
          {active && (
            <path
              d="M 50 32 C 20 140, 80 200, 50 240 C 20 280, 80 340, 50 448"
              stroke={`url(#${gradGlowId})`}
              strokeWidth="5"
              strokeLinecap="round"
              fill="none"
              filter={`url(#${filterGlowId})`}
            />
          )}

          {/* Primary Flowing Gradient Strand */}
          <path
            d="M 50 32 C 20 140, 80 200, 50 240 C 20 280, 80 340, 50 448"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "2.5" : "2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "8 8" : undefined}
          />

          {/* Top Node: Clinical Claim Anchor */}
          <g transform="translate(50, 32)" id="claim-anchor-node">
            <circle r={active ? 12 : 9} fill={currentTone.ambient} />
            <circle r="6" fill="#FFFFFF" stroke={currentTone.accentNode} strokeWidth="2" />
            <circle r="2.5" fill={currentTone.accentNode} />
          </g>

          {/* Midpoint Waypoint */}
          <g transform="translate(50, 240)" id="waypoint-bridge-node">
            <rect
              x="-4"
              y="-4"
              width="8"
              height="8"
              transform="rotate(45)"
              fill={active ? currentTone.waypointFill : "#CBD5E1"}
              stroke="#FFFFFF"
              strokeWidth="1.5"
            />
          </g>

          {/* Bottom Node: Source Beacon */}
          <g transform="translate(50, 448)" id="source-beacon-node">
            <circle r={active ? 14 : 11} fill={currentTone.ambient} />
            <circle
              r="7"
              fill="#FFFFFF"
              stroke={currentTone.beaconStroke}
              strokeWidth="2"
            />
            <path
              d="M 0,-3.5 L 2.5,0 L 0,3.5 L -2.5,0 Z"
              fill={currentTone.accentNode}
            />
          </g>
        </svg>
      )}

      {/* ------------------------------------------------------------------------- */}
      {/* VARIANT: CURVED                                                           */}
      {/* ------------------------------------------------------------------------- */}
      {variant === "curved" && (
        <svg
          viewBox="0 0 400 240"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-auto w-full overflow-visible"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            <linearGradient id={gradPrimaryId} x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity={active ? 0.95 : 0.6} />
              <stop offset="50%" stopColor={currentTone.mid} stopOpacity={active ? 1 : 0.8} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.95 : 0.7} />
            </linearGradient>

            <linearGradient id={gradSubtleId} x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity="0.2" />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity="0.05" />
            </linearGradient>

            <linearGradient id={gradGlowId} x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.mid} stopOpacity={active ? 0.7 : 0.2} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.8 : 0.25} />
            </linearGradient>

            <filter id={filterGlowId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation={active ? "3.5" : "1.5"} result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Underlay Ambient Curved Track */}
          <path
            d="M 40 190 C 140 190, 160 50, 360 50"
            stroke={currentTone.subtleStroke}
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Harmonic Envelope Strands */}
          <path
            d="M 40 190 C 120 160, 180 80, 360 50"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M 40 190 C 160 220, 240 20, 360 50"
            stroke={`url(#${gradSubtleId})`}
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Active Glow Arc */}
          {active && (
            <path
              d="M 40 190 C 140 190, 160 50, 360 50"
              stroke={`url(#${gradGlowId})`}
              strokeWidth="5"
              strokeLinecap="round"
              fill="none"
              filter={`url(#${filterGlowId})`}
            />
          )}

          {/* Primary Sweeping Sigmoid Arc Strand */}
          <path
            d="M 40 190 C 140 190, 160 50, 360 50"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "2.5" : "2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "8 8" : undefined}
          />

          {/* Bottom-Left Node: Clinical Claim Anchor */}
          <g transform="translate(40, 190)" id="claim-anchor-node">
            <circle r={active ? 12 : 9} fill={currentTone.ambient} />
            <circle r="6" fill="#FFFFFF" stroke={currentTone.accentNode} strokeWidth="2" />
            <circle r="2.5" fill={currentTone.accentNode} />
          </g>

          {/* Diagonal Waypoint */}
          <g transform="translate(200, 120)" id="waypoint-bridge-node">
            <rect
              x="-4"
              y="-4"
              width="8"
              height="8"
              transform="rotate(45)"
              fill={active ? currentTone.waypointFill : "#CBD5E1"}
              stroke="#FFFFFF"
              strokeWidth="1.5"
            />
          </g>

          {/* Top-Right Node: Source Citation Beacon */}
          <g transform="translate(360, 50)" id="source-beacon-node">
            <circle r={active ? 14 : 11} fill={currentTone.ambient} />
            <circle
              r="7"
              fill="#FFFFFF"
              stroke={currentTone.beaconStroke}
              strokeWidth="2"
            />
            <path
              d="M 0,-3.5 L 2.5,0 L 0,3.5 L -2.5,0 Z"
              fill={currentTone.accentNode}
            />
          </g>
        </svg>
      )}

      {/* ------------------------------------------------------------------------- */}
      {/* VARIANT: CONNECTOR                                                        */}
      {/* ------------------------------------------------------------------------- */}
      {variant === "connector" && (
        <svg
          viewBox="0 0 360 160"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-auto w-full overflow-visible"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            <linearGradient id={gradPrimaryId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity={active ? 0.95 : 0.6} />
              <stop offset="50%" stopColor={currentTone.mid} stopOpacity={active ? 1 : 0.8} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.95 : 0.7} />
            </linearGradient>

            <linearGradient id={gradSubtleId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.start} stopOpacity="0.2" />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity="0.05" />
            </linearGradient>

            <linearGradient id={gradGlowId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={currentTone.mid} stopOpacity={active ? 0.7 : 0.2} />
              <stop offset="100%" stopColor={currentTone.end} stopOpacity={active ? 0.8 : 0.25} />
            </linearGradient>

            <filter id={filterGlowId} x="-20%" y="-30%" width="140%" height="160%">
              <feGaussianBlur stdDeviation={active ? "3" : "1.5"} result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Underlay Ambient Intake Tracks */}
          <path
            d="M 30 40 C 100 40, 130 80, 180 80"
            stroke={currentTone.subtleStroke}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M 30 120 C 100 120, 130 80, 180 80"
            stroke={currentTone.subtleStroke}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          {/* Main Bridge Trunk */}
          <path
            d="M 180 80 L 330 80"
            stroke={currentTone.subtleStroke}
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Active Glowing Fork Strands */}
          {active && (
            <>
              <path
                d="M 30 40 C 100 40, 130 80, 180 80 L 330 80"
                stroke={`url(#${gradGlowId})`}
                strokeWidth="4.5"
                strokeLinecap="round"
                fill="none"
                filter={`url(#${filterGlowId})`}
              />
              <path
                d="M 30 120 C 100 120, 130 80, 180 80 L 330 80"
                stroke={`url(#${gradGlowId})`}
                strokeWidth="4.5"
                strokeLinecap="round"
                fill="none"
                filter={`url(#${filterGlowId})`}
              />
            </>
          )}

          {/* Upper Input Fork Path */}
          <path
            d="M 30 40 C 100 40, 130 80, 180 80"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "2.5" : "2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "6 6" : undefined}
          />

          {/* Lower Input Fork Path */}
          <path
            d="M 30 120 C 100 120, 130 80, 180 80"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "2.5" : "2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "6 6" : undefined}
          />

          {/* Unified Verification Trunk */}
          <path
            d="M 180 80 L 330 80"
            stroke={`url(#${gradPrimaryId})`}
            strokeWidth={active ? "3" : "2.2"}
            strokeLinecap="round"
            fill="none"
            className={active ? "clara-ribbon-path motion-reduce:stroke-dasharray-none" : undefined}
            strokeDasharray={active ? "8 8" : undefined}
          />

          {/* Top Claim Anchor Node */}
          <g transform="translate(30, 40)" id="claim-anchor-node-top">
            <circle r={active ? 10 : 8} fill={currentTone.ambient} />
            <circle r="5" fill="#FFFFFF" stroke={currentTone.accentNode} strokeWidth="1.75" />
            <circle r="2" fill={currentTone.accentNode} />
          </g>

          {/* Bottom Claim Anchor Node */}
          <g transform="translate(30, 120)" id="claim-anchor-node-bottom">
            <circle r={active ? 10 : 8} fill={currentTone.ambient} />
            <circle r="5" fill="#FFFFFF" stroke={currentTone.accentNode} strokeWidth="1.75" />
            <circle r="2" fill={currentTone.accentNode} />
          </g>

          {/* Convergence Junction Hub */}
          <g transform="translate(180, 80)" id="convergence-hub-node">
            <circle r={active ? 12 : 9} fill={currentTone.ambient} />
            <rect
              x="-4.5"
              y="-4.5"
              width="9"
              height="9"
              transform="rotate(45)"
              fill={active ? currentTone.waypointFill : "#94A3B8"}
              stroke="#FFFFFF"
              strokeWidth="1.5"
            />
          </g>

          {/* Destination Source Citation Beacon */}
          <g transform="translate(330, 80)" id="source-beacon-node">
            <circle r={active ? 14 : 11} fill={currentTone.ambient} />
            <circle
              r="7"
              fill="#FFFFFF"
              stroke={currentTone.beaconStroke}
              strokeWidth="2"
            />
            <path
              d="M 0,-3.5 L 2.5,0 L 0,3.5 L -2.5,0 Z"
              fill={currentTone.accentNode}
            />
          </g>
        </svg>
      )}
    </div>
  );
}

export default EvidenceRibbon;
