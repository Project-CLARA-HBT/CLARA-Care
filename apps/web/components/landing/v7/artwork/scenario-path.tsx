"use client";

import React, { useId } from "react";

export interface ScenarioPathProps {
  /** Index of the scenario item (0-based), influencing curvature & accent variations */
  index?: number;
  /** Active focus/in-view state to highlight path flow and glow */
  active?: boolean;
  /** Additional CSS class names */
  className?: string;
  /** Optional inline styles */
  style?: React.CSSProperties;
}

interface PathConfig {
  d: string;
  start: { x: number; y: number };
  mid: { x: number; y: number };
  end: { x: number; y: number };
  label: string;
}

const PATH_VARIANTS: PathConfig[] = [
  // Variant 0: Descending sigmoid S-curve (Intake / Medication DDI context)
  {
    d: "M 40,32 C 180,18 240,112 360,110 C 440,108 500,90 560,96",
    start: { x: 40, y: 32 },
    mid: { x: 300, y: 72 },
    end: { x: 560, y: 96 },
    label: "DDI & Verification Path",
  },
  // Variant 1: Ascending wave arc (Clinical prep & LifeMap alignment)
  {
    d: "M 40,104 C 160,118 260,28 380,32 C 450,35 510,50 560,42",
    start: { x: 40, y: 104 },
    mid: { x: 320, y: 48 },
    end: { x: 560, y: 42 },
    label: "Timeline Synthesis Path",
  },
  // Variant 2: Cascading double harmonic wave (Triage & Safety fast-path)
  {
    d: "M 40,40 C 170,110 260,20 370,100 C 440,120 510,80 560,86",
    start: { x: 40, y: 40 },
    mid: { x: 315, y: 60 },
    end: { x: 560, y: 86 },
    label: "CareGuard Fast-Path",
  },
  // Variant 3: Longitudinal sweeping trajectory (Trends & Health evolution)
  {
    d: "M 40,92 C 190,24 280,124 410,54 C 470,22 520,38 560,48",
    start: { x: 40, y: 92 },
    mid: { x: 345, y: 78 },
    end: { x: 560, y: 48 },
    label: "Longitudinal Trend Path",
  },
];

/**
 * ScenarioPath Artwork Component (Landing v7)
 *
 * Upgraded Features:
 * 1. Smooth Curved SVG Path: Mathematical multi-bezier splines connecting human speech/quotes to clinical resolutions.
 * 2. Traveling Directional Light Beam: High-intensity photon light beam with head flare, trailing comet tail, and dashoffset stream motion.
 * 3. Human Quote Anchor: Conversational quote mark glyph with acoustic ripple rings.
 * 4. FIDES Safety Checkpoint: Intermediate verification checkpoint diamond node.
 * 5. Clinical Resolution Beacon: Radiant 4-point lens flare and emerald clinical resolution seal.
 */
export function ScenarioPath({
  index = 0,
  active = false,
  className = "",
  style,
}: ScenarioPathProps) {
  const rawId = useId();
  const uniqueId = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  const gradientId = `scenario-path-grad-${uniqueId}`;
  const activeGlowId = `scenario-path-glow-${uniqueId}`;
  const lightBeamId = `scenario-path-beam-${uniqueId}`;
  const filterGlowId = `scenario-path-blur-${uniqueId}`;
  const filterBeamId = `scenario-path-beam-blur-${uniqueId}`;
  const markerArrowId = `scenario-path-arrow-${uniqueId}`;

  const variantIndex = Math.abs(Math.floor(index)) % PATH_VARIANTS.length;
  const config = PATH_VARIANTS[variantIndex] ?? PATH_VARIANTS[0];

  return (
    <div
      aria-hidden="true"
      style={style}
      className={`pointer-events-none relative select-none w-full overflow-visible transition-opacity duration-500 ${
        active ? "opacity-100" : "opacity-75 hover:opacity-90"
      } ${className}`}
    >
      <svg
        viewBox="0 0 600 140"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-auto overflow-visible"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Main Path Flow Gradient */}
          <linearGradient
            id={gradientId}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#0B6FD8" stopOpacity={active ? 0.95 : 0.45} />
            <stop offset="40%" stopColor="#14A88D" stopOpacity={active ? 0.98 : 0.65} />
            <stop offset="75%" stopColor="#0B6FD8" stopOpacity={active ? 1 : 0.8} />
            <stop offset="100%" stopColor="#10B981" stopOpacity={active ? 1 : 0.9} />
          </linearGradient>

          {/* Active Highlight Glow Gradient */}
          <linearGradient
            id={activeGlowId}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#38BDF8" stopOpacity={active ? 0.85 : 0.25} />
            <stop offset="50%" stopColor="#34D399" stopOpacity={active ? 1 : 0.45} />
            <stop offset="100%" stopColor="#60A5FA" stopOpacity={active ? 0.95 : 0.35} />
          </linearGradient>

          {/* Traveling Directional Light Beam Gradient */}
          <linearGradient
            id={lightBeamId}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="60%" stopColor="#38BDF8" stopOpacity="0.8" />
            <stop offset="90%" stopColor="#34D399" stopOpacity="1" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="1" />
          </linearGradient>

          {/* Path Glow Blur Filter */}
          <filter id={filterGlowId} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation={active ? "3.5" : "1.5"} result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* High-intensity Traveling Light Beam Filter */}
          <filter id={filterBeamId} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur1" />
            <feGaussianBlur stdDeviation="6" result="blur2" />
            <feMerge>
              <feMergeNode in="blur2" />
              <feMergeNode in="blur1" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Directional Terminal Arrow Marker */}
          <marker
            id={markerArrowId}
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path
              d="M 1 2 L 7 5 L 1 8 Z"
              fill={active ? "#10B981" : "#0B6FD8"}
              className="transition-colors duration-300"
            />
          </marker>
        </defs>

        {/* 1. Ambient Subtle Underlay Guide Track */}
        <path
          d={config.d}
          stroke="#E2E8F0"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeDasharray="6 6"
          className="opacity-60 dark:opacity-20"
        />

        {/* 2. Ambient Blurred Glow Path (Active Mode) */}
        {active && (
          <path
            d={config.d}
            stroke={`url(#${activeGlowId})`}
            strokeWidth="6"
            strokeLinecap="round"
            filter={`url(#${filterGlowId})`}
            className="opacity-70 transition-all duration-500"
          />
        )}

        {/* 3. Primary Curving Directional Path */}
        <path
          d={config.d}
          stroke={`url(#${gradientId})`}
          strokeWidth={active ? "2.5" : "2"}
          strokeLinecap="round"
          markerEnd={`url(#${markerArrowId})`}
          className="transition-all duration-300"
          style={{
            strokeDasharray: active ? "12 4" : undefined,
            animation: active ? "clara-path-flow 24s linear infinite" : undefined,
          }}
        />

        {/* 4. Traveling Directional Light Beam (High-intensity stream packet) */}
        {active && (
          <>
            {/* Primary traveling light beam stream */}
            <path
              d={config.d}
              stroke={`url(#${lightBeamId})`}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeDasharray="40 160"
              filter={`url(#${filterBeamId})`}
              style={{
                animation: "clara-path-flow 6s linear infinite",
              }}
            />

            {/* Micro photon particle stream */}
            <path
              d={config.d}
              stroke="#FFFFFF"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="4 28"
              className="opacity-90"
              style={{
                animation: "clara-path-flow 8s linear infinite",
              }}
            />
          </>
        )}

        {/* --- START NODE: Human Quote Anchor (Everyday Patient Moment) --- */}
        <g
          transform={`translate(${config.start.x}, ${config.start.y})`}
          className="transition-transform duration-300"
        >
          {/* Outer acoustic ripple ring */}
          <circle
            r={active ? 16 : 11}
            fill="#0B6FD8"
            fillOpacity={active ? 0.18 : 0.08}
            className="transition-all duration-300"
          />
          {active && (
            <circle
              r="22"
              fill="none"
              stroke="#0B6FD8"
              strokeWidth="1"
              strokeOpacity="0.3"
              strokeDasharray="2 2"
              className="motion-safe:animate-ping motion-reduce:animate-none"
              style={{ animationDuration: "3s" }}
            />
          )}
          {/* Inner ring pill */}
          <circle
            r="7"
            fill="#FFFFFF"
            stroke="#0B6FD8"
            strokeWidth="2"
            className="shadow-sm"
          />
          {/* Human Quote mark icon */}
          <text
            x="0"
            y="3"
            textAnchor="middle"
            fill="#0B6FD8"
            fontSize="9"
            fontWeight="bold"
            fontFamily="serif"
          >
            “
          </text>
        </g>

        {/* --- MIDPOINT WAYPOINT: Context & Safety Verification (FIDES Gate) --- */}
        <g
          transform={`translate(${config.mid.x}, ${config.mid.y})`}
          className="transition-transform duration-300"
        >
          {/* Checkpoint subtle halo */}
          {active && (
            <circle
              r="12"
              fill="#14A88D"
              fillOpacity="0.15"
              className="motion-safe:animate-pulse"
            />
          )}
          {/* FIDES checkpoint diamond node */}
          <rect
            x="-4.5"
            y="-4.5"
            width="9"
            height="9"
            transform="rotate(45)"
            fill={active ? "#14A88D" : "#94A3B8"}
            fillOpacity={active ? 0.95 : 0.5}
            stroke="#FFFFFF"
            strokeWidth="1.5"
            className="transition-all duration-300 shadow-sm"
          />
        </g>

        {/* --- END NODE: Clinical Resolution Beacon --- */}
        <g
          transform={`translate(${config.end.x}, ${config.end.y})`}
          className="transition-transform duration-300"
        >
          {/* Outer radiating beacon halo */}
          <circle
            r={active ? 18 : 13}
            fill="#10B981"
            fillOpacity={active ? 0.22 : 0.08}
            className="transition-all duration-300"
          />
          {active && (
            <>
              {/* Radiating beacon sonar ring */}
              <circle
                r="24"
                fill="none"
                stroke="#10B981"
                strokeWidth="1.2"
                strokeOpacity="0.4"
                className="motion-safe:animate-ping motion-reduce:animate-none"
                style={{ animationDuration: "2.5s" }}
              />

              {/* 4-Point Radiant Lens Flare */}
              <line
                x1="-10"
                y1="0"
                x2="10"
                y2="0"
                stroke="#10B981"
                strokeWidth="1.2"
                filter={`url(#${filterGlowId})`}
              />
              <line
                x1="0"
                y1="-10"
                x2="0"
                y2="10"
                stroke="#10B981"
                strokeWidth="1.2"
                filter={`url(#${filterGlowId})`}
              />
            </>
          )}

          {/* Outer border ring */}
          <circle
            r={active ? 8.5 : 7}
            fill="#FFFFFF"
            stroke={active ? "#10B981" : "#0B6FD8"}
            strokeWidth="2"
            className="transition-colors duration-300"
          />

          {/* Clinical Verification Checkmark Core */}
          <path
            d="M -2.8 -0.2 L -0.8 1.8 L 2.8 -1.8"
            fill="none"
            stroke={active ? "#10B981" : "#0B6FD8"}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="transition-colors duration-300"
          />
        </g>
      </svg>
    </div>
  );
}

export default ScenarioPath;
