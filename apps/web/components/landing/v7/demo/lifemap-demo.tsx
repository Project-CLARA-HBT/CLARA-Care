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
 * Milestone clinical styling metadata helper
 */
function getMilestoneMeta(idx: number, lang: "vi" | "en") {
  switch (idx) {
    case 0:
      return {
        accentColor: "#B42318",
        bgSoft: "bg-rose-50/80",
        borderSoft: "border-rose-200",
        textColor: "text-rose-700",
        dotColor: "bg-rose-500",
        glowShadow: "shadow-[0_0_10px_rgba(244,63,94,0.6)]",
        badge: "bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]",
        delta: lang === "vi" ? "Mốc khởi đầu • Tháng 4" : "Baseline Onset • April",
        metric: lang === "vi" ? "Ghi nhận triệu chứng sớm" : "Early Symptom Baseline",
        causalNote:
          lang === "vi"
            ? "Triệu chứng đau đầu vùng chẩm buổi sáng là căn cứ khởi phát để theo dõi chỉ số huyết áp."
            : "Morning occipital headache logged as the primary baseline trigger for continuous blood pressure monitoring.",
      };
    case 1:
      return {
        accentColor: "#6941C6",
        bgSoft: "bg-purple-50/80",
        borderSoft: "border-purple-200",
        textColor: "text-purple-700",
        dotColor: "bg-purple-500",
        glowShadow: "shadow-[0_0_10px_rgba(168,85,247,0.6)]",
        badge: "bg-[#F5F3FF] text-[#6941C6] border-[#DDD6FE]",
        delta: lang === "vi" ? "+30 ngày • Tháng 5" : "+30 Days • May",
        metric: lang === "vi" ? "Khởi trị Amlodipine 5mg" : "Amlodipine 5mg Daily",
        causalNote:
          lang === "vi"
            ? "Phác đồ được kích hoạt sau khi chỉ số HA vượt ngưỡng 140/90 mmHg; liên kết với dữ liệu tháng 4."
            : "Pharmacological regimen initiated following clinical BP threshold breach; causally linked to April onset.",
      };
    case 2:
      return {
        accentColor: "#0E856F",
        bgSoft: "bg-emerald-50/80",
        borderSoft: "border-emerald-200",
        textColor: "text-emerald-700",
        dotColor: "bg-[#14A88D]",
        glowShadow: "shadow-[0_0_10px_rgba(20,168,141,0.6)]",
        badge: "bg-[#ECFDF8] text-[#0E856F] border-[#A6F4C5]",
        delta: lang === "vi" ? "+60 ngày • Tháng 6" : "+60 Days • June",
        metric: lang === "vi" ? "HA 125/80 mmHg • Thận học an toàn" : "BP 125/80 mmHg • Renal Panels Normal",
        causalNote:
          lang === "vi"
            ? "Dữ liệu huyết áp và xét nghiệm chức năng thận khẳng định đáp ứng điều trị thuận lợi."
            : "Lab investigations and blood pressure panels confirm favorable therapeutic response with zero adverse signals.",
      };
    case 3:
    default:
      return {
        accentColor: "#0B6FD8",
        bgSoft: "bg-[#EFF7FF]/90",
        borderSoft: "border-[#B2DDFF]",
        textColor: "text-[#0B6FD8]",
        dotColor: "bg-[#1A86F5]",
        glowShadow: "shadow-[0_0_12px_rgba(26,134,245,0.85)]",
        badge: "bg-[#EFF7FF] text-[#0B6FD8] border-[#B2DDFF]",
        delta: lang === "vi" ? "+90 ngày • Hiện tại" : "+90 Days • Today",
        metric: lang === "vi" ? "Tham vấn nhịp sinh học & đổi giờ uống" : "Chronotherapy & Shift Dosing Inquiry",
        causalNote:
          lang === "vi"
            ? "Dữ liệu được kết nối trực tiếp với phiên tham vấn dược lý và nhịp sinh học hôm nay."
            : "Live data correlated with today's pharmacological consultation and circadian schedule adjustment.",
      };
  }
}

/**
 * LifeMapDemo (Landing v7 Signature Product Surface Peak)
 *
 * Renders CLARA's signature LifeMap spatial canvas:
 * 1. 4-month longitudinal timeline milestones (Tháng 4 -> Tháng 5 -> Tháng 6 -> Hôm nay / April -> May -> June -> Today)
 * 2. Embedded TemporalRibbon curved SVG spine with glowing gradient flow & stage cards
 * 3. Interactive milestone cards with hover elevation, glowing node indicators, and smooth detail card transition
 * 4. Radiant TodayBeacon anchor marking the current temporal moment
 * 5. Luminous Floating Context Insight Callout with ambient gradient wash, pulsing sparkle badge, and interactive action button
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
    const clamped = Math.max(0, Math.min(copy.timeline.length - 1, idx));
    setSelectedMilestone(clamped);
    onMilestoneChange?.(clamped);
  };

  const currentEvent = copy.timeline[selectedMilestone] || copy.timeline[0];
  const currentMeta = getMilestoneMeta(selectedMilestone, lang);

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
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8] block">
                    {lang === "vi" ? "Mốc Dòng Thời Gian Được Chọn" : "Active Timeline Milestone"}
                  </span>
                  <span className={`inline-flex items-center rounded-md border px-2 py-0.2 text-[10px] font-semibold ${currentMeta.badge}`}>
                    {currentMeta.delta}
                  </span>
                </div>
                <h4 className="text-sm sm:text-base font-bold text-[#162033] tracking-tight">
                  {currentEvent.period} • {currentEvent.title}
                </h4>
              </div>
            </div>

            {/* Quick Step Switcher Tabs with Hover Elevation and Glowing Node Indicators */}
            <div
              className="flex items-center gap-1.5 rounded-2xl bg-[#F8FAFD] p-1.5 border border-[#E3E8EF]"
              role="tablist"
              aria-label={lang === "vi" ? "Chuyển nhanh các mốc" : "Quick milestone tabs"}
            >
              {copy.timeline.map((evt, idx) => {
                const isSelected = selectedMilestone === idx;
                const isToday = idx === 3;
                const nodeMeta = getMilestoneMeta(idx, lang);

                return (
                  <button
                    key={`quick-tab-${evt.period}-${idx}`}
                    type="button"
                    role="tab"
                    id={`quick-milestone-tab-${idx}`}
                    aria-controls={`lifemap-detail-panel-${selectedMilestone}`}
                    aria-selected={isSelected}
                    aria-label={evt.period}
                    onClick={() => handleSelectMilestone(idx)}
                    onKeyDown={(e) => {
                      if (e.key === "ArrowRight") {
                        e.preventDefault();
                        handleSelectMilestone((idx + 1) % copy.timeline.length);
                      } else if (e.key === "ArrowLeft") {
                        e.preventDefault();
                        handleSelectMilestone(
                          (idx - 1 + copy.timeline.length) % copy.timeline.length
                        );
                      }
                    }}
                    className={`group relative flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
                      isSelected
                        ? "bg-white text-[#0B6FD8] shadow-sm ring-2 ring-[#0B6FD8]/30 -translate-y-0.5"
                        : "text-[#6D7A8E] hover:text-[#162033] hover:bg-white hover:-translate-y-0.5 hover:shadow-xs"
                    }`}
                  >
                    {/* Glowing Node Indicator */}
                    <span
                      className={`relative flex h-2 w-2 items-center justify-center rounded-full transition-all ${
                        isSelected
                          ? `${nodeMeta.dotColor} ${nodeMeta.glowShadow}`
                          : isToday
                          ? "bg-[#1A86F5]/60 group-hover:bg-[#1A86F5]"
                          : `${nodeMeta.dotColor} opacity-50 group-hover:opacity-100`
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
            id={`lifemap-detail-panel-${selectedMilestone}`}
            key={`detail-body-${selectedMilestone}`}
            className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch transition-all duration-300 animate-fadeIn"
          >
            {/* Left Column: Clinical Description & Event Details */}
            <div className="md:col-span-8 flex flex-col justify-between space-y-3.5">
              <div className="space-y-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold border shadow-2xs ${currentMeta.badge}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${currentMeta.dotColor}`} />
                    {currentEvent.category}
                  </span>
                  <span className="text-xs text-[#6D7A8E]">
                    {lang === "vi" ? "Phân loại lâm sàng" : "Clinical Classification"}
                  </span>
                  <span className="text-xs text-[#94A3B8]">•</span>
                  <span className="text-xs font-medium text-[#48566A]">
                    {currentMeta.metric}
                  </span>
                </div>

                <div className="rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border border-[#E3E8EF]/90 space-y-2">
                  <p className="text-xs sm:text-sm text-[#162033] font-medium leading-relaxed">
                    {currentEvent.detail}
                  </p>
                  <p className="text-[11px] text-[#6D7A8E] leading-relaxed italic border-t border-[#E3E8EF]/60 pt-2">
                    {currentMeta.causalNote}
                  </p>
                </div>
              </div>

              {/* Step Navigation Controls (Previous / Next Milestone) */}
              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  disabled={selectedMilestone === 0}
                  onClick={() => handleSelectMilestone(selectedMilestone - 1)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6D7A8E] hover:text-[#0B6FD8] disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
                >
                  <span aria-hidden="true">←</span>
                  <span>{lang === "vi" ? "Mốc trước" : "Previous Milestone"}</span>
                </button>

                <div className="text-[11px] font-semibold text-[#94A3B8]">
                  {selectedMilestone + 1} / {copy.timeline.length}
                </div>

                <button
                  type="button"
                  disabled={selectedMilestone === copy.timeline.length - 1}
                  onClick={() => handleSelectMilestone(selectedMilestone + 1)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6D7A8E] hover:text-[#0B6FD8] disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
                >
                  <span>{lang === "vi" ? "Mốc tiếp theo" : "Next Milestone"}</span>
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>

            {/* Right Column: FIDES Causal Chain Integrity Box */}
            <div className="md:col-span-4 rounded-2xl bg-gradient-to-br from-[#F8FAFD] via-white to-[#ECFDF8]/40 p-4 sm:p-5 border border-[#E3E8EF] flex flex-col justify-between space-y-3 text-xs shadow-xs">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-bold text-[#14A88D]">
                  <span className="flex items-center gap-1.5">
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#ECFDF8] text-[10px] border border-[#14A88D]/30 font-bold">
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

              <div className="rounded-xl bg-white p-3 border border-[#E3E8EF]/80 space-y-1">
                <div className="flex items-center justify-between text-[10px] font-bold text-[#6D7A8E]">
                  <span>{lang === "vi" ? "Trạng thái liên kết" : "Linkage Integrity"}</span>
                  <span className="text-[#14A88D]">100% Validated</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-[#E3E8EF] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#0B6FD8] to-[#14A88D] transition-all duration-500"
                    style={{ width: `${((selectedMilestone + 1) / copy.timeline.length) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------- */}
      {/* 4. PROMINENT FLOATING CONTEXT INSIGHT CALLOUT (Primary WOW Moment)        */}
      {/* ------------------------------------------------------------------------- */}
      <div
        data-testid="lifemap-insight-callout"
        className="clara-floating-chrome relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-9 border-2 border-[#0B6FD8]/30 shadow-[0_16px_48px_-12px_rgba(11,111,216,0.22)] bg-gradient-to-r from-[#EFF7FF]/95 via-white/95 to-[#ECFDF8]/90 backdrop-blur-xl transition-all duration-300 hover:border-[#0B6FD8]/45"
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
