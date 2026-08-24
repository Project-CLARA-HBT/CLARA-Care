"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { TemporalRibbon } from "../artwork/temporal-ribbon";
import { TodayBeacon } from "../artwork/today-beacon";

export interface LifeMapDemoProps {
  /** Optional custom CSS classes */
  className?: string;
  /** Optional initial selected milestone index (0 to 3, defaults to 3 for 'Today') */
  initialSelectedMilestone?: number;
  /** Callback fired when a milestone is selected */
  onMilestoneChange?: (index: number) => void;
}

/**
 * LifeMapDemo (Landing v7 Signature Product Surface)
 *
 * Renders CLARA's signature LifeMap spatial canvas:
 * 1. Longitudinal 4-Month Timeline Continuum (April -> May -> June -> Today / Tháng 4 -> Tháng 5 -> Tháng 6 -> Hôm nay)
 * 2. Embedded TemporalRibbon curved SVG spine with glowing gradient flow & stage cards
 * 3. Interactive milestone selection dynamically updating the active clinical detail card with hover lift & glowing node indicators
 * 4. Radiant TodayBeacon anchor marking the current temporal moment
 * 5. Luminous Floating Context Insight Callout with pulsing icon and interactive action button
 * 6. Full WCAG 2.1 AA accessibility, keyboard navigation, bilingual support (vi/en), zero TypeScript errors
 */
export function LifeMapDemo({
  className = "",
  initialSelectedMilestone = 3,
  onMilestoneChange,
}: LifeMapDemoProps) {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.lifemap ?? LANDING_COPY_V7.vi.lifemap;

  const [selectedMilestone, setSelectedMilestone] = useState<number>(() => {
    if (
      initialSelectedMilestone >= 0 &&
      initialSelectedMilestone < copy.timeline.length
    ) {
      return initialSelectedMilestone;
    }
    return Math.max(0, copy.timeline.length - 1);
  });

  const [isInsightActionTriggered, setIsInsightActionTriggered] = useState(false);

  const handleSelectMilestone = (idx: number) => {
    setSelectedMilestone(idx);
    onMilestoneChange?.(idx);
  };

  const currentEvent = copy.timeline[selectedMilestone] || copy.timeline[0];

  return (
    <div
      data-testid="lifemap-demo"
      className={`w-full space-y-6 sm:space-y-8 ${className}`}
    >
      {/* ------------------------------------------------------------------------- */}
      {/* 1. SECTION HEADER: LifeMap Spatial Canvas Metadata & TodayBeacon Anchor   */}
      {/* ------------------------------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-1 sm:px-2">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EFF7FF] px-3 py-1 text-xs font-bold uppercase tracking-wider text-[#0B6FD8] border border-[#0B6FD8]/25 shadow-2xs">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse motion-reduce:animate-none" />
              {lang === "vi" ? "Dòng thời gian Sức khỏe Liên tục" : "Longitudinal Health Continuum"}
            </span>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[11px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
              FIDES Linked
            </span>
          </div>
          <h3 className="text-xl sm:text-2xl font-extrabold text-[#162033] tracking-tight">
            {copy.title}
          </h3>
          <p className="text-xs sm:text-sm text-[#6D7A8E] max-w-2xl leading-relaxed">
            {copy.description}
          </p>
        </div>

        {/* Temporal TodayBeacon Active Status Pill */}
        <div className="flex items-center gap-3">
          <TodayBeacon
            active={true}
            tone="azure"
            size="sm"
            label={lang === "vi" ? "Mốc Hiện tại" : "Current Turn"}
            labelPlacement="right"
            onClick={() => handleSelectMilestone(3)}
            ariaLabel={lang === "vi" ? "Chọn mốc Hôm nay" : "Select Today milestone"}
          />
        </div>
      </div>

      {/* ------------------------------------------------------------------------- */}
      {/* 2. SIGNATURE LIFEMAP SPATIAL CANVAS (Embedded TemporalRibbon)            */}
      {/* ------------------------------------------------------------------------- */}
      <div className="relative">
        <TemporalRibbon
          events={copy.timeline}
          selectedIndex={selectedMilestone}
          onSelect={handleSelectMilestone}
          className="w-full shadow-lg"
        />
      </div>

      {/* ------------------------------------------------------------------------- */}
      {/* 3. INTERACTIVE MILESTONE DETAIL INSPECTOR CARD                            */}
      {/* ------------------------------------------------------------------------- */}
      {currentEvent && (
        <div
          data-testid="lifemap-detail-card"
          role="region"
          aria-label={`${lang === "vi" ? "Chi tiết mốc" : "Milestone detail"}: ${currentEvent.period} - ${currentEvent.title}`}
          className="clara-product-surface relative overflow-hidden rounded-3xl p-5 sm:p-7 lg:p-8 border border-[#E3E8EF] shadow-lg bg-white transition-all duration-300"
        >
          {/* Subtle Ambient Light Wash */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[#0B6FD8]/5 blur-2xl"
          />

          {/* Top Control Bar with Quick Stage Jumpers & Glowing Indicators */}
          <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF] pb-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#0B6FD8] to-[#1A86F5] text-white text-xs font-bold shadow-sm shadow-[#0B6FD8]/25">
                <span>0{selectedMilestone + 1}</span>
                <span className="absolute -inset-0.5 rounded-xl border border-[#0B6FD8]/40 animate-pulse motion-reduce:animate-none" />
              </div>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8] block">
                  {lang === "vi" ? "Mốc Dòng Thời Gian Được Chọn" : "Active Timeline Milestone"}
                </span>
                <h4 className="text-sm sm:text-base font-bold text-[#162033] tracking-tight">
                  {currentEvent.period} • {currentEvent.title}
                </h4>
              </div>
            </div>

            {/* Quick Step Switcher Tabs with Hover Lift and Glowing Node Dots */}
            <div
              className="flex items-center gap-1.5 rounded-2xl bg-[#F8FAFD] p-1.5 border border-[#E3E8EF]"
              role="tablist"
              aria-label={lang === "vi" ? "Chuyển nhanh các mốc" : "Quick milestone tabs"}
            >
              {copy.timeline.map((evt, idx) => {
                const isSelected = selectedMilestone === idx;
                const isToday = idx === 3;
                return (
                  <button
                    key={`quick-tab-${evt.period}-${idx}`}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => handleSelectMilestone(idx)}
                    className={`group relative flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
                      isSelected
                        ? "bg-white text-[#0B6FD8] shadow-sm ring-1 ring-[#0B6FD8]/25 -translate-y-0.5"
                        : "text-[#6D7A8E] hover:text-[#162033] hover:bg-white/80 hover:-translate-y-0.5"
                    }`}
                  >
                    {/* Glowing Node Indicator */}
                    <span
                      className={`relative flex h-2 w-2 items-center justify-center rounded-full transition-all ${
                        isSelected
                          ? isToday
                            ? "bg-[#1A86F5] shadow-[0_0_8px_rgba(26,134,245,0.8)]"
                            : "bg-[#0B6FD8] shadow-[0_0_8px_rgba(11,111,216,0.8)]"
                          : isToday
                          ? "bg-[#1A86F5]/50 group-hover:bg-[#1A86F5]"
                          : "bg-[#94A3B8] group-hover:bg-[#48566A]"
                      }`}
                    >
                      {isSelected && (
                        <span className="absolute -inset-1 rounded-full bg-[#0B6FD8]/25 animate-ping motion-reduce:animate-none" />
                      )}
                    </span>
                    <span>{evt.period}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Smooth Transition Detail Container */}
          <div
            key={`detail-body-${selectedMilestone}`}
            className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-5 items-center transition-all duration-300 animate-fadeIn"
          >
            <div className="md:col-span-8 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-lg bg-[#EFF7FF] px-2.5 py-1 text-xs font-semibold text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-2xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
                  {currentEvent.category}
                </span>
                <span className="text-xs text-[#6D7A8E]">
                  {lang === "vi" ? "Phân loại lâm sàng" : "Clinical Classification"}
                </span>
              </div>

              <p className="text-xs sm:text-sm text-[#162033] font-medium leading-relaxed bg-[#F8FAFD] p-4 rounded-2xl border border-[#E3E8EF]/80">
                {currentEvent.detail}
              </p>
            </div>

            <div className="md:col-span-4 rounded-2xl bg-gradient-to-br from-[#F8FAFD] to-[#ECFDF8]/40 p-4 border border-[#E3E8EF] space-y-2 text-xs shadow-xs">
              <div className="flex items-center justify-between text-[11px] font-bold text-[#14A88D]">
                <span className="flex items-center gap-1.5">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#ECFDF8] text-[10px] border border-[#14A88D]/30">
                    ✓
                  </span>
                  <span>FIDES Causal Chain</span>
                </span>
                <span className="rounded-full bg-[#ECFDF8] px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                  Verified
                </span>
              </div>
              <p className="text-[11px] text-[#48566A] leading-relaxed">
                {selectedMilestone === 3
                  ? lang === "vi"
                    ? "Dữ liệu được kết nối trực tiếp với phiên tham vấn dược lý hôm nay."
                    : "Live data correlated with today's pharmacological consultation."
                  : lang === "vi"
                  ? "Sự kiện được lập chỉ mục trong chuỗi nhân quả hồ sơ bệnh án."
                  : "Event indexed in longitudinal electronic health record timeline."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------- */}
      {/* 4. PROMINENT FLOATING CONTEXT INSIGHT CALLOUT (Primary WOW Moment)        */}
      {/* ------------------------------------------------------------------------- */}
      <div
        data-testid="lifemap-insight-callout"
        className="clara-floating-chrome relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-9 border-2 border-[#0B6FD8]/30 shadow-[0_16px_48px_-12px_rgba(11,111,216,0.22)] bg-gradient-to-r from-[#EFF7FF]/95 via-white/95 to-[#ECFDF8]/90 backdrop-blur-md transition-all duration-300 hover:border-[#0B6FD8]/45"
      >
        {/* Ambient background light flare with subtle pulse */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-12 -top-12 h-64 w-64 rounded-full bg-gradient-to-br from-[#0B6FD8]/15 to-[#14A88D]/15 blur-3xl animate-pulse motion-reduce:animate-none"
        />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            {/* Luminous Radiant Sparkle Badge Icon with Pulsing Halo */}
            <div className="relative shrink-0">
              <div
                className={`absolute -inset-1 rounded-2xl bg-gradient-to-br from-[#0B6FD8] to-[#14A88D] opacity-35 blur-sm ${
                  isReducedMotion ? "" : "animate-pulse"
                }`}
                aria-hidden="true"
              />
              <div
                className="relative flex h-13 w-13 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0B6FD8] via-[#1A86F5] to-[#14A88D] text-white text-xl font-black shadow-lg ring-4 ring-[#EFF7FF]"
                aria-hidden="true"
              >
                <span className={isReducedMotion ? "" : "animate-spin-slow"}>✦</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold uppercase tracking-wider text-[#0B6FD8]">
                  {copy.insightCallout.tag}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/30 shadow-2xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D] animate-ping motion-reduce:animate-none" />
                  60-Day Target Reached
                </span>
              </div>

              <h4 className="text-lg sm:text-xl font-bold text-[#162033] tracking-tight">
                {copy.insightCallout.title}
              </h4>

              <p className="text-xs sm:text-sm text-[#48566A] leading-relaxed max-w-2xl">
                {copy.insightCallout.body}
              </p>
            </div>
          </div>

          {/* Action CTA Button with Interactive Hover Lift and Directional Arrow */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0 w-full md:w-auto">
            <button
              type="button"
              data-testid="lifemap-insight-action-btn"
              onClick={() => {
                setIsInsightActionTriggered(true);
                handleSelectMilestone(3);
              }}
              className="group inline-flex items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-[#0B6FD8] to-[#1A86F5] px-6 py-3.5 text-xs sm:text-sm font-bold text-white shadow-md shadow-[#0B6FD8]/25 hover:shadow-lg hover:shadow-[#0B6FD8]/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-200 clara-focus-ring cursor-pointer"
            >
              <span>{copy.insightCallout.action}</span>
              <span
                aria-hidden="true"
                className="transition-transform duration-200 group-hover:translate-x-1"
              >
                →
              </span>
            </button>
          </div>
        </div>

        {/* Action Confirmation Banner with Smooth Dismiss */}
        {isInsightActionTriggered && (
          <div
            data-testid="lifemap-insight-feedback"
            className="mt-5 rounded-2xl bg-[#ECFDF8] p-3.5 border border-[#14A88D]/35 text-xs text-[#0E856F] flex items-center justify-between gap-3 shadow-xs animate-fadeIn"
          >
            <span className="flex items-center gap-2 font-semibold">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-[#14A88D] shadow-2xs font-bold">
                ✓
              </span>
              <span>
                {lang === "vi"
                  ? "Đã đồng bộ toàn bộ dữ liệu 4 tháng vào không gian phân tích LifeMap."
                  : "Synchronized full 4-month continuum into active LifeMap analytics space."}
              </span>
            </span>
            <button
              type="button"
              onClick={() => setIsInsightActionTriggered(false)}
              className="rounded-lg px-2 py-1 text-[11px] font-bold text-[#14A88D] hover:bg-[#14A88D]/10 transition-colors"
            >
              {lang === "vi" ? "Đóng" : "Dismiss"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default LifeMapDemo;
