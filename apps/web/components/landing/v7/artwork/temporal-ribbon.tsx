"use client";

import React, { useState, useId } from "react";
import { TodayBeacon } from "./today-beacon";

export type TemporalEmphasis = "past" | "recent" | "today";

export interface TemporalEvent {
  period: string;
  title: string;
  detail: string;
  category: string;
  emphasis: TemporalEmphasis;
}

export interface TemporalRibbonProps {
  /**
   * Array of longitudinal health timeline events.
   * Defaults to the standard 4-stage LifeMap continuum if omitted.
   */
  events?: TemporalEvent[];
  /**
   * Controlled index of the currently active/inspected timeline stage.
   */
  selectedIndex?: number;
  /**
   * Callback invoked when a timeline stage is selected.
   */
  onSelect?: (index: number) => void;
  /**
   * Longitudinal timeline progress indicator (0 to 1).
   */
  progress?: number;
  /**
   * Additional CSS class names.
   */
  className?: string;
  /**
   * Optional inline styles.
   */
  style?: React.CSSProperties;
  /**
   * Accessible aria-label override.
   */
  ariaLabel?: string;
}

export const DEFAULT_TEMPORAL_EVENTS: TemporalEvent[] = [
  {
    period: "Tháng 4",
    title: "Khởi phát triệu chứng",
    detail: "Xuất hiện cơn đau đầu âm ỉ vùng chẩm vào buổi sáng sớm.",
    category: "Triệu chứng",
    emphasis: "past",
  },
  {
    period: "Tháng 5",
    title: "Bắt đầu phác đồ thuốc",
    detail: "Bác sĩ chỉ định Amlodipine 5mg/ngày sau khi đo HA 145/90 mmHg.",
    category: "Kê đơn",
    emphasis: "past",
  },
  {
    period: "Tháng 6",
    title: "Khám tái khám định kỳ",
    detail: "Huyết áp ổn định 125/80 mmHg, bổ sung xét nghiệm chức năng thận bình thường.",
    category: "Tái khám",
    emphasis: "recent",
  },
  {
    period: "Hôm nay",
    title: "Câu hỏi về điều chỉnh giờ uống",
    detail: "Cần tham vấn khi đổi lịch làm việc ban đêm và thay đổi thời điểm dùng thuốc.",
    category: "Tương tác mới",
    emphasis: "today",
  },
];

/**
 * Category color styling helper for clinical context badges
 */
export function getCategoryBadgeClass(
  category: string,
  emphasis: TemporalEmphasis
): string {
  const catLower = category.toLowerCase();
  if (emphasis === "today" || catLower.includes("hôm nay") || catLower.includes("tương tác")) {
    return "bg-[#EFF7FF] text-[#0B6FD8] border-[#B2DDFF]";
  }
  if (catLower.includes("triệu chứng") || catLower.includes("symptom")) {
    return "bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]";
  }
  if (catLower.includes("kê đơn") || catLower.includes("thuốc") || catLower.includes("rx")) {
    return "bg-[#F5F3FF] text-[#6941C6] border-[#DDD6FE]";
  }
  if (
    catLower.includes("tái khám") ||
    catLower.includes("xét nghiệm") ||
    catLower.includes("visit") ||
    catLower.includes("lab")
  ) {
    return "bg-[#ECFDF8] text-[#0E856F] border-[#A6F4C5]";
  }
  return "bg-[#F1F5F9] text-[#48566A] border-[#E3E8EF]";
}

/**
 * TemporalRibbon Artwork Component
 *
 * Renders LifeMap's longitudinal curved temporal ribbon connecting historical events to Today.
 * Upgraded Features:
 * - Longitudinal curved timeline spline with dynamic multi-stop gradient progress fill.
 * - Milestone nodes with luminous hover halos and step numbers (1, 2, 3, Today).
 * - Traveling light trail connecting past milestones to TodayBeacon.
 * - Responsive vertical ribbon track on mobile with continuous spline and node anchors.
 * - Interactive node selection with keyboard navigation & high-contrast accessibility.
 * - Graceful reduced-motion degradation.
 */
export function TemporalRibbon({
  events: propEvents,
  selectedIndex: controlledSelectedIndex,
  onSelect,
  progress,
  className = "",
  style,
  ariaLabel,
}: TemporalRibbonProps) {
  const events = propEvents && propEvents.length > 0 ? propEvents : DEFAULT_TEMPORAL_EVENTS;
  const uid = useId().replace(/:/g, "_");

  // Default to today node (or last node) if not specified
  const defaultIndex = Math.max(
    0,
    events.findIndex((e) => e.emphasis === "today") !== -1
      ? events.findIndex((e) => e.emphasis === "today")
      : events.length - 1
  );

  const [internalIndex, setInternalIndex] = useState<number>(defaultIndex);
  const activeIndex = controlledSelectedIndex !== undefined ? controlledSelectedIndex : internalIndex;

  const handleSelect = (idx: number) => {
    setInternalIndex(idx);
    onSelect?.(idx);
  };

  const selectedEvent = events[activeIndex] || events[0];

  // Normalized progress (0 to 1)
  const effectiveProgress =
    progress !== undefined
      ? Math.max(0, Math.min(1, Number.isFinite(progress) ? progress : 1))
      : (activeIndex + 1) / Math.max(1, events.length);

  // Desktop Ribbon coordinate mapping (4 stages across 1000px width)
  const nodeX = [125, 375, 625, 875];
  const nodeY = [60, 42, 70, 48];

  // SVG Unique IDs for Gradients and Filters
  const ribbonGradId = `ribbon-gradient-${uid}`;
  const ribbonAuraId = `ribbon-aura-${uid}`;
  const ribbonProgressGradId = `ribbon-progress-grad-${uid}`;
  const dropGradId = `drop-gradient-${uid}`;
  const beaconGlowId = `beacon-glow-${uid}`;
  const lightTrailGradId = `light-trail-grad-${uid}`;
  const nodeHaloGradId = `node-halo-grad-${uid}`;

  // Spline Path definition (Longitudinal curved Bezier spanning all 4 milestone coordinates)
  const splinePathD = "M 60 62 C 180 26, 250 42, 375 42 C 500 42, 500 70, 625 70 C 750 70, 750 48, 940 48";

  return (
    <section
      data-testid="temporal-ribbon"
      data-artwork="temporal-ribbon"
      data-selected-index={activeIndex}
      data-progress={effectiveProgress.toFixed(2)}
      aria-label={ariaLabel || "LifeMap Longitudinal Temporal Ribbon"}
      className={`clara-temporal-ribbon-root relative w-full overflow-hidden rounded-3xl border border-[#E3E8EF] bg-white/95 p-5 shadow-lg backdrop-blur-md sm:p-8 lg:p-10 ${className}`}
      style={style}
    >
      {/* Ambient background glow fields */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-20 -top-20 h-72 w-72 rounded-full bg-[#0B6FD8]/8 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-20 -bottom-20 h-72 w-72 rounded-full bg-[#14A88D]/8 blur-3xl"
      />

      {/* Ribbon Header Strip */}
      <header className="relative z-10 mb-8 flex flex-col gap-3 border-b border-[#E3E8EF] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-[#0B6FD8] animate-pulse motion-reduce:animate-none" />
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
              LIFEMAP LONGITUDINAL CONTINUUM
            </span>
          </div>
          <h3 className="text-lg font-bold tracking-tight text-[#162033] sm:text-xl">
            Dòng thời gian sức khỏe liên tục (Longitudinal Ribbon)
          </h3>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#0B6FD8]/20 bg-[#EFF7FF] px-3 py-1 text-xs font-semibold text-[#0B6FD8]">
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>{events.length} Mốc liên kết</span>
          </span>

          <div
            className="hidden items-center gap-1 rounded-full border border-[#E3E8EF] bg-[#F8FAFD] px-2.5 py-1 text-[11px] font-medium text-[#6D7A8E] lg:flex"
            title="Dòng dữ liệu được liên kết theo thời gian thực"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
            <span>Đồng bộ FIDES</span>
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* DESKTOP VIEW: 4-Stage Longitudinal Curved Ribbon Stage                    */}
      {/* ========================================================================= */}
      <div className="relative hidden md:block" data-testid="desktop-timeline-view">
        {/* SVG Longitudinal Curved Timeline Ribbon Canvas */}
        <div className="relative h-28 w-full" aria-hidden="true">
          <svg
            className="h-full w-full overflow-visible"
            viewBox="0 0 1000 110"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="none"
          >
            <defs>
              {/* Primary Ribbon Multi-Stop Gradient */}
              <linearGradient id={ribbonGradId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#94A3B8" stopOpacity="0.4" />
                <stop offset="30%" stopColor="#0B6FD8" stopOpacity="0.75" />
                <stop offset="65%" stopColor="#14A88D" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#1A86F5" stopOpacity="1" />
              </linearGradient>

              {/* Dynamic Progress Fill Multi-Stop Gradient */}
              <linearGradient id={ribbonProgressGradId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#64748B" />
                <stop offset="35%" stopColor="#0B6FD8" />
                <stop offset="70%" stopColor="#14A88D" />
                <stop offset="100%" stopColor="#1A86F5" />
              </linearGradient>

              {/* Glowing Aura Gradient for Ribbon Base Wave */}
              <linearGradient id={ribbonAuraId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#CBD5E1" stopOpacity="0.12" />
                <stop offset="45%" stopColor="#0B6FD8" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#1A86F5" stopOpacity="0.35" />
              </linearGradient>

              {/* Traveling Light Trail Gradient connecting past milestones to Today */}
              <linearGradient id={lightTrailGradId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.2" />
                <stop offset="50%" stopColor="#38BDF8" stopOpacity="0.85" />
                <stop offset="90%" stopColor="#FFFFFF" stopOpacity="1" />
                <stop offset="100%" stopColor="#1A86F5" stopOpacity="0.9" />
              </linearGradient>

              {/* Connector Drop Gradient */}
              <linearGradient id={dropGradId} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.9" />
                <stop offset="60%" stopColor="#0B6FD8" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0.05" />
              </linearGradient>

              {/* Milestone Node Luminous Hover Halo Gradient */}
              <radialGradient id={nodeHaloGradId} cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#1A86F5" stopOpacity="0.5" />
                <stop offset="50%" stopColor="#0B6FD8" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0" />
              </radialGradient>

              {/* Beacon Glow Radial */}
              <radialGradient id={beaconGlowId} cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#1A86F5" stopOpacity="0.55" />
                <stop offset="50%" stopColor="#0B6FD8" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* 1. Background Ribbon Aura Wave (Fluid thick translucent band) */}
            <path
              d={splinePathD}
              stroke={`url(#${ribbonAuraId})`}
              strokeWidth="24"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* 2. Baseline Ribbon Spine Track */}
            <path
              d={splinePathD}
              stroke="#E3E8EF"
              strokeWidth="4"
              strokeLinecap="round"
            />

            {/* 3. Multi-stop Active Colored Longitudinal Spine */}
            <path
              d={splinePathD}
              stroke={`url(#${ribbonGradId})`}
              strokeWidth="3.5"
              strokeLinecap="round"
            />

            {/* 4. Dynamic Gradient Progress Fill Track */}
            {effectiveProgress > 0 && (
              <path
                d={splinePathD}
                stroke={`url(#${ribbonProgressGradId})`}
                strokeWidth="4.5"
                strokeLinecap="round"
                pathLength="1000"
                strokeDasharray="1000"
                strokeDashoffset={1000 * (1 - effectiveProgress)}
                style={{ transition: "stroke-dashoffset 400ms cubic-bezier(0.16, 1, 0.3, 1)" }}
              />
            )}

            {/* 5. Traveling Light Trail: High-tech pulsating dashed trail connecting past to Today */}
            <path
              d={splinePathD}
              stroke={`url(#${lightTrailGradId})`}
              strokeWidth="2.25"
              strokeDasharray="8 14"
              className="clara-ribbon-path motion-reduce:stroke-dasharray-none"
            />

            {/* 6. Secondary traveling particle stream */}
            <path
              d={splinePathD}
              stroke="#FFFFFF"
              strokeWidth="1.25"
              strokeDasharray="4 20"
              className="clara-constellation-line motion-reduce:stroke-dasharray-none opacity-80"
            />

            {/* 7. Spine Drop Connectors & Milestone Nodes for Each Stage */}
            {events.slice(0, 4).map((evt, idx) => {
              const cx = nodeX[idx] ?? 125 + idx * 250;
              const cy = nodeY[idx] ?? 50;
              const isSelected = activeIndex === idx;
              const isToday = evt.emphasis === "today" || idx === 3;

              return (
                <g key={`desktop-node-${evt.period}-${idx}`}>
                  {/* Drop Spine Connector Line to Card */}
                  <line
                    x1={cx}
                    y1={cy}
                    x2={cx}
                    y2={110}
                    stroke={isSelected ? `url(#${dropGradId})` : "#E3E8EF"}
                    strokeWidth={isSelected ? "2.5" : "1.5"}
                    strokeDasharray={isSelected ? "none" : "3 3"}
                  />

                  {/* Node representation on ribbon spine */}
                  {isToday ? (
                    /* Today Beacon Anchor SVG Representation */
                    <g transform={`translate(${cx}, ${cy})`}>
                      {/* Luminous Outer Halo */}
                      <circle
                        r="30"
                        fill={`url(#${beaconGlowId})`}
                        className="animate-ping motion-reduce:animate-none opacity-40"
                      />
                      {/* Calibrated Constellation Orbit Ring */}
                      <circle
                        r="19"
                        fill="none"
                        stroke="#1A86F5"
                        strokeWidth="1.5"
                        strokeDasharray="4 3"
                        className="clara-constellation-line motion-reduce:stroke-dasharray-none"
                      />
                      {/* Luminous Beacon Sphere */}
                      <circle r="12.5" fill="#0B6FD8" stroke="#FFFFFF" strokeWidth="2" className="shadow-lg" />
                      <circle r="4" fill="#FFFFFF" />
                      {/* Precision Crosshairs */}
                      <line x1="-17" y1="0" x2="-13" y2="0" stroke="#0B6FD8" strokeWidth="2" strokeLinecap="round" />
                      <line x1="13" y1="0" x2="17" y2="0" stroke="#0B6FD8" strokeWidth="2" strokeLinecap="round" />
                      <line x1="0" y1="-17" x2="0" y2="-13" stroke="#0B6FD8" strokeWidth="2" strokeLinecap="round" />
                      <line x1="0" y1="13" x2="0" y2="17" stroke="#0B6FD8" strokeWidth="2" strokeLinecap="round" />
                    </g>
                  ) : (
                    /* Historical / Recent Milestone Node with Hover Halo & Step Number */
                    <g transform={`translate(${cx}, ${cy})`}>
                      {/* Luminous Hover & Selection Halo */}
                      {isSelected && (
                        <circle
                          r="18"
                          fill={`url(#${nodeHaloGradId})`}
                          className="animate-pulse motion-reduce:animate-none"
                        />
                      )}
                      {/* Outer Focus/Hover Ring */}
                      <circle
                        r={isSelected ? "13" : "10"}
                        fill="none"
                        stroke={isSelected ? "#0B6FD8" : "#E2E8F0"}
                        strokeWidth={isSelected ? "2" : "1.5"}
                        strokeOpacity={isSelected ? "0.9" : "0.5"}
                      />
                      {/* Solid Milestone Core Disc with Step Indicator */}
                      <circle
                        r={isSelected ? 10 : 8}
                        fill={
                          isSelected
                            ? "#0B6FD8"
                            : evt.emphasis === "recent"
                            ? "#14A88D"
                            : "#64748B"
                        }
                        stroke="#FFFFFF"
                        strokeWidth="2"
                      />
                      {/* Step Number in Milestone Node */}
                      <text
                        x="0"
                        y="0"
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#FFFFFF"
                        fontSize={isSelected ? "9" : "8"}
                        fontWeight="bold"
                        fontFamily="sans-serif"
                      >
                        {idx + 1}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* 4-Stage Interactive Timeline Cards Grid */}
        <div
          className="relative z-10 grid grid-cols-4 gap-4 pt-2"
          role="tablist"
          aria-label="4 Mốc dòng thời gian sức khỏe"
          data-testid="desktop-stage-grid"
        >
          {events.slice(0, 4).map((evt, idx) => {
            const isSelected = activeIndex === idx;
            const isToday = evt.emphasis === "today" || idx === 3;
            const badgeClass = getCategoryBadgeClass(evt.category, evt.emphasis);

            return (
              <button
                key={`card-desktop-${evt.period}-${idx}`}
                type="button"
                role="tab"
                id={`lifemap-desktop-tab-${idx}`}
                data-testid={`desktop-tab-${idx}`}
                aria-selected={isSelected}
                aria-controls={`lifemap-panel-${activeIndex}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => handleSelect(idx)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight") {
                    e.preventDefault();
                    handleSelect((idx + 1) % Math.min(4, events.length));
                  } else if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    handleSelect(
                      (idx - 1 + Math.min(4, events.length)) % Math.min(4, events.length)
                    );
                  }
                }}
                className={`group relative flex flex-col rounded-2xl p-4 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0B6FD8] ${
                  isToday
                    ? isSelected
                      ? "border-2 border-[#0B6FD8] bg-gradient-to-b from-white via-[#EFF7FF]/75 to-[#EFF7FF] shadow-lg -translate-y-1.5 ring-4 ring-[#0B6FD8]/15"
                      : "border border-[#0B6FD8]/40 bg-gradient-to-b from-white to-[#EFF7FF]/40 shadow-sm hover:border-[#0B6FD8] hover:-translate-y-0.5 hover:shadow-md"
                    : isSelected
                    ? "border-2 border-[#0B6FD8] bg-white shadow-md -translate-y-1 ring-4 ring-[#0B6FD8]/10"
                    : "border border-[#E3E8EF] bg-[#F8FAFD] hover:border-[#0B6FD8]/40 hover:bg-white hover:-translate-y-0.5 hover:shadow-sm"
                }`}
              >
                {/* TodayBeacon Anchor Badge */}
                {isToday && (
                  <div className="absolute -top-3 right-3 flex items-center">
                    <TodayBeacon
                      size="sm"
                      tone="azure"
                      active={isSelected || isToday}
                      label={evt.period}
                      labelPlacement="right"
                      showLabel={true}
                    />
                  </div>
                )}

                {/* Card Top Meta: Step Number with Luminous Ring + Period */}
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all ${
                        isToday
                          ? "bg-[#0B6FD8] text-white ring-2 ring-[#EFF7FF] shadow-xs"
                          : isSelected
                          ? "bg-[#162033] text-white ring-2 ring-[#0B6FD8]/30 shadow-xs"
                          : "bg-[#E3E8EF] text-[#6D7A8E] group-hover:bg-[#CBD5E1] group-hover:text-[#162033]"
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <span
                      className={`text-xs font-bold uppercase tracking-wider ${
                        isToday
                          ? "text-[#0B6FD8]"
                          : isSelected
                          ? "text-[#162033]"
                          : "text-[#6D7A8E]"
                      }`}
                    >
                      {evt.period}
                    </span>
                  </div>

                  {!isToday && (
                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold ${badgeClass}`}
                    >
                      {evt.category}
                    </span>
                  )}
                </div>

                {/* Event Title */}
                <h4
                  className={`text-sm font-bold leading-snug line-clamp-1 ${
                    isSelected ? "text-[#0B6FD8]" : "text-[#162033]"
                  }`}
                >
                  {evt.title}
                </h4>

                {/* Event Detail */}
                <p className="mt-1.5 text-xs text-[#48566A] leading-relaxed line-clamp-2">
                  {evt.detail}
                </p>

                {/* Visual Selection Indicator */}
                <div className="mt-3 flex items-center justify-between border-t border-[#E3E8EF]/60 pt-2 text-[11px]">
                  <span
                    className={`font-semibold ${
                      isSelected
                        ? "text-[#0B6FD8]"
                        : "text-[#94A3B8] group-hover:text-[#6D7A8E]"
                    }`}
                  >
                    {isSelected ? "● Đang chọn" : "Xem chi tiết"}
                  </span>
                  <svg
                    className={`h-3 w-3 transition-transform ${
                      isSelected
                        ? "translate-x-0.5 text-[#0B6FD8]"
                        : "text-[#94A3B8] group-hover:text-[#6D7A8E]"
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MOBILE VIEW: Responsive Vertical Ribbon Track                             */}
      {/* ========================================================================= */}
      <div className="relative block md:hidden" data-testid="mobile-timeline-view">
        {/* Continuous Vertical Ribbon Track Container */}
        <div
          className="relative pl-7 space-y-4"
          role="tablist"
          aria-label="Danh sách mốc thời gian di động"
        >
          {/* Ambient Outer Glow Rail */}
          <div
            aria-hidden="true"
            className="absolute left-2.5 top-4 bottom-8 w-2 rounded-full bg-gradient-to-b from-[#94A3B8]/20 via-[#0B6FD8]/25 to-[#1A86F5]/30 blur-xs"
          />

          {/* Continuous Vertical Ribbon Track Rail */}
          <div
            aria-hidden="true"
            className="absolute left-3 top-4 bottom-8 w-1 rounded-full bg-gradient-to-b from-[#94A3B8] via-[#0B6FD8] to-[#1A86F5]"
          />

          {events.map((evt, idx) => {
            const isSelected = activeIndex === idx;
            const isToday = evt.emphasis === "today" || idx === events.length - 1;
            const badgeClass = getCategoryBadgeClass(evt.category, evt.emphasis);

            return (
              <div key={`mobile-node-${evt.period}-${idx}`} className="relative">
                {/* Node Anchor on Vertical Ribbon Track */}
                <div
                  aria-hidden="true"
                  className="absolute -left-7 top-4 flex -translate-x-1/2 items-center justify-center"
                >
                  {isToday ? (
                    <TodayBeacon
                      size="sm"
                      tone="azure"
                      active={true}
                      showLabel={false}
                    />
                  ) : (
                    <div
                      className={`relative flex h-6 w-6 items-center justify-center rounded-full border-2 border-white transition-transform ${
                        isSelected
                          ? "bg-[#0B6FD8] text-white ring-4 ring-[#0B6FD8]/20 shadow-md scale-110"
                          : evt.emphasis === "recent"
                          ? "bg-[#14A88D] text-white ring-2 ring-[#14A88D]/20"
                          : "bg-[#64748B] text-white"
                      }`}
                    >
                      <span className="text-[10px] font-bold">{idx + 1}</span>
                    </div>
                  )}
                </div>

                {/* Interactive Mobile Card */}
                <button
                  type="button"
                  role="tab"
                  id={`lifemap-mobile-tab-${idx}`}
                  data-testid={`mobile-tab-${idx}`}
                  aria-selected={isSelected}
                  aria-controls={`lifemap-panel-${activeIndex}`}
                  onClick={() => handleSelect(idx)}
                  className={`w-full rounded-2xl p-4 text-left transition-all ${
                    isToday
                      ? isSelected
                        ? "border-2 border-[#0B6FD8] bg-gradient-to-br from-white via-[#EFF7FF]/75 to-[#EFF7FF] shadow-md ring-2 ring-[#0B6FD8]/15"
                        : "border border-[#0B6FD8]/40 bg-[#EFF7FF]/30 shadow-sm"
                      : isSelected
                      ? "border-2 border-[#0B6FD8] bg-white shadow-md ring-2 ring-[#0B6FD8]/10"
                      : "border border-[#E3E8EF] bg-[#F8FAFD] hover:bg-white"
                  }`}
                >
                  {/* Period & Category Header */}
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-extrabold uppercase tracking-wider text-[#0B6FD8]">
                        {evt.period}
                      </span>
                      {isToday && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#0B6FD8] px-2 py-0.5 text-[9px] font-bold uppercase text-white">
                          <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse motion-reduce:animate-none" />
                          Hôm nay
                        </span>
                      )}
                    </div>

                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold ${badgeClass}`}
                    >
                      {evt.category}
                    </span>
                  </div>

                  {/* Title & Detail */}
                  <h4
                    className={`text-sm font-bold leading-snug ${
                      isSelected ? "text-[#0B6FD8]" : "text-[#162033]"
                    }`}
                  >
                    {evt.title}
                  </h4>
                  <p className="mt-1 text-xs text-[#48566A] leading-relaxed">
                    {evt.detail}
                  </p>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* EXPANDED STAGE DETAIL / INSIGHT DRAWER                                    */}
      {/* ========================================================================= */}
      {selectedEvent && (
        <div
          id={`lifemap-panel-${activeIndex}`}
          role="region"
          aria-labelledby={`lifemap-desktop-tab-${activeIndex}`}
          className="mt-6 rounded-2xl border border-[#0B6FD8]/20 bg-gradient-to-r from-[#F8FAFD] via-[#EFF7FF]/50 to-[#F8FAFD] p-4 sm:p-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-md bg-[#0B6FD8] px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white">
                  Mốc {activeIndex + 1}/{events.length} • {selectedEvent.period}
                </span>
                <span className="text-xs font-semibold text-[#48566A]">
                  Phân loại: {selectedEvent.category}
                </span>
              </div>

              <h4 className="text-base font-bold text-[#162033]">
                {selectedEvent.title}
              </h4>
              <p className="text-xs text-[#48566A] sm:text-sm leading-relaxed max-w-3xl">
                {selectedEvent.detail}
              </p>
            </div>

            <div className="shrink-0 flex items-center gap-2 pt-2 sm:pt-0">
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-[#14A88D]/20 bg-[#ECFDF8] px-3 py-2 text-xs font-semibold text-[#0E856F]">
                <svg
                  className="h-4 w-4 shrink-0 text-[#14A88D]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
                <span>FIDES Chuỗi nhân quả</span>
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default TemporalRibbon;
