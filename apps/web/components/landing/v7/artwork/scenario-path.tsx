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
 * ScenarioPath Artwork Component
 *
 * Renders the Human Scenario Path connecting everyday patient moments
 * to CLARA's verified clinical resolution with a curving directional SVG spline.
 */
export function ScenarioPath({
  index = 0,
  active = false,
  className = "",
  style,
}: ScenarioPathProps) {
  const rawId = useId();
  // Sanitize useId for SVG ID references
  const uniqueId = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  const gradientId = `scenario-path-grad-${uniqueId}`;
  const activeGlowId = `scenario-path-glow-${uniqueId}`;
  const filterGlowId = `scenario-path-blur-${uniqueId}`;
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
            <stop offset="0%" stopColor="#0B6FD8" stopOpacity={active ? 0.9 : 0.4} />
            <stop offset="45%" stopColor="#14A88D" stopOpacity={active ? 0.95 : 0.6} />
            <stop offset="80%" stopColor="#0B6FD8" stopOpacity={active ? 1 : 0.75} />
            <stop offset="100%" stopColor="#059669" stopOpacity={active ? 1 : 0.85} />
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
            <stop offset="0%" stopColor="#38BDF8" stopOpacity={active ? 0.8 : 0.2} />
            <stop offset="50%" stopColor="#34D399" stopOpacity={active ? 1 : 0.4} />
            <stop offset="100%" stopColor="#60A5FA" stopOpacity={active ? 0.9 : 0.3} />
          </linearGradient>

          {/* Glow Filter */}
          <filter id={filterGlowId} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation={active ? "3.5" : "1.5"} result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
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

        {/* Ambient Subtle Underlay Track */}
        <path
          d={config.d}
          stroke="#E2E8F0"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeDasharray="6 6"
          className="opacity-60 dark:opacity-20"
        />

        {/* Ambient Blurred Glow Path (Active Mode) */}
        {active && (
          <path
            d={config.d}
            stroke={`url(#${activeGlowId})`}
            strokeWidth="5"
            strokeLinecap="round"
            filter={`url(#${filterGlowId})`}
            className="opacity-70 transition-all duration-500"
          />
        )}

        {/* Primary Curving Directional Path */}
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

        {/* Flow particles / Dynamic stream line when active */}
        {active && (
          <path
            d={config.d}
            stroke="#FFFFFF"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeDasharray="4 28"
            className="opacity-80"
            style={{
              animation: "clara-path-flow 8s linear infinite",
            }}
          />
        )}

        {/* --- START NODE: Everyday Patient Moment / Human Question --- */}
        <g
          transform={`translate(${config.start.x}, ${config.start.y})`}
          className="transition-transform duration-300"
        >
          {/* Outer halo */}
          <circle
            r={active ? 14 : 10}
            fill="#0B6FD8"
            fillOpacity={active ? 0.15 : 0.08}
            className="transition-all duration-300"
          />
          {/* Inner ring */}
          <circle
            r="6"
            fill="#FFFFFF"
            stroke="#0B6FD8"
            strokeWidth="2"
            className="shadow-sm"
          />
          {/* Center core */}
          <circle
            r="2.5"
            fill={active ? "#0B6FD8" : "#64748B"}
            className="transition-colors duration-300"
          />
        </g>

        {/* --- MIDPOINT WAYPOINT: Context & Safety Verification --- */}
        <g
          transform={`translate(${config.mid.x}, ${config.mid.y})`}
          className="transition-transform duration-300"
        >
          {/* FIDES checkpoint diamond node */}
          <rect
            x="-4"
            y="-4"
            width="8"
            height="8"
            transform="rotate(45)"
            fill={active ? "#14A88D" : "#94A3B8"}
            fillOpacity={active ? 0.9 : 0.5}
            stroke="#FFFFFF"
            strokeWidth="1.5"
            className="transition-all duration-300"
          />
        </g>

        {/* --- END NODE: Clinical Resolution Beacon --- */}
        <g
          transform={`translate(${config.end.x}, ${config.end.y})`}
          className="transition-transform duration-300"
        >
          {/* Outer radiating beacon */}
          <circle
            r={active ? 16 : 12}
            fill="#10B981"
            fillOpacity={active ? 0.2 : 0.08}
            className="transition-all duration-300"
          />
          {/* Outer border ring */}
          <circle
            r={active ? 8 : 6.5}
            fill="#FFFFFF"
            stroke={active ? "#10B981" : "#0B6FD8"}
            strokeWidth="2"
            className="transition-colors duration-300"
          />
          {/* Clinical Spark / Diamond Core */}
          <path
            d="M 0,-3.5 L 2.5,0 L 0,3.5 L -2.5,0 Z"
            fill={active ? "#10B981" : "#0B6FD8"}
            className="transition-colors duration-300"
          />
        </g>
      </svg>
    </div>
  );
}

export default ScenarioPath;
