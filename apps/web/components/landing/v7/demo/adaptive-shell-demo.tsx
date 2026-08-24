"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { ClaraOrb } from "../artwork/clara-orb";

export type AdaptiveModeId = "personal" | "clinical" | "research";

export interface AdaptiveShellDemoProps {
  currentMode?: AdaptiveModeId;
  onModeChange?: (mode: AdaptiveModeId) => void;
  className?: string;
}

interface SlotIconProps {
  mode: AdaptiveModeId;
  slotIndex: number;
  className?: string;
}

function NavSlotIcon({ mode, slotIndex, className = "h-4 w-4" }: SlotIconProps) {
  if (slotIndex === 2) {
    // Slot 2 is always the center CLARA anchor
    return null;
  }

  // Personal Mode Icons
  if (mode === "personal") {
    switch (slotIndex) {
      case 0: // Hôm nay / Today (Calendar & Sun)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <rect x="3" y="4" width="14" height="13" rx="3" />
            <line x1="3" y1="8" x2="17" y2="8" />
            <line x1="7" y1="2" x2="7" y2="5" />
            <line x1="13" y1="2" x2="13" y2="5" />
            <circle cx="10" cy="12.5" r="1.5" fill="currentColor" stroke="none" />
          </svg>
        );
      case 1: // LifeMap (Longitudinal timeline)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <path d="M3 13.5 C5 13.5, 6 7, 9 7 C12 7, 13 14, 17 10" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="3" cy="13.5" r="1.75" fill="currentColor" />
            <circle cx="9" cy="7" r="1.75" fill="currentColor" />
            <circle cx="17" cy="10" r="1.75" fill="currentColor" />
          </svg>
        );
      case 3: // Thuốc / Meds (Capsule pill)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <rect x="4" y="8" width="12" height="7" rx="3.5" transform="rotate(-30 10 11.5)" />
            <line x1="7.5" y1="7.5" x2="12.5" y2="15.5" strokeDasharray="1.5 1.5" />
          </svg>
        );
      case 4: // Hồ sơ / Records (Health profile badge)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <rect x="4" y="3" width="12" height="14" rx="2.5" />
            <path d="M7 7h6M7 10h6M7 13h3" strokeLinecap="round" />
          </svg>
        );
    }
  }

  // Clinical Mode Icons
  if (mode === "clinical") {
    switch (slotIndex) {
      case 0: // Tổng quan / Overview (Clinical Dashboard)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <rect x="3" y="3" width="6" height="6" rx="1.5" />
            <rect x="11" y="3" width="6" height="6" rx="1.5" />
            <rect x="3" y="11" width="6" height="6" rx="1.5" />
            <rect x="11" y="11" width="6" height="6" rx="1.5" />
          </svg>
        );
      case 1: // Council (Multi-specialty convergence)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <circle cx="10" cy="5" r="2.25" />
            <circle cx="5" cy="14" r="2.25" />
            <circle cx="15" cy="14" r="2.25" />
            <path d="M10 7.25 L6.5 12M10 7.25 L13.5 12M7.25 14 h5.5" strokeWidth="1.4" strokeDasharray="1.5 1.5" />
          </svg>
        );
      case 3: // Scribe (Audio Waveform & Ambient Recording)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <rect x="8" y="2.5" width="4" height="8" rx="2" />
            <path d="M5 8.5 C5 11.5, 8 13.5, 10 13.5 C12 13.5, 15 11.5, 15 8.5" strokeLinecap="round" />
            <line x1="10" y1="13.5" x2="10" y2="17.5" strokeLinecap="round" />
            <line x1="7" y1="17.5" x2="13" y2="17.5" strokeLinecap="round" />
          </svg>
        );
      case 4: // Thêm / More (Menu grid)
        return (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
            <circle cx="5" cy="10" r="1.5" fill="currentColor" stroke="none" />
            <circle cx="10" cy="10" r="1.5" fill="currentColor" stroke="none" />
            <circle cx="15" cy="10" r="1.5" fill="currentColor" stroke="none" />
          </svg>
        );
    }
  }

  // Research Mode Icons
  switch (slotIndex) {
    case 0: // Nghiên cứu / Research (Microscope / Exploration)
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
          <circle cx="9" cy="8" r="4.5" />
          <path d="M12.5 11.5 L17 16" strokeLinecap="round" strokeWidth="2" />
          <path d="M7 8h4M9 6v4" strokeLinecap="round" strokeWidth="1.4" />
        </svg>
      );
    case 1: // Evidence (Evidence shield & scale)
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
          <path d="M10 2.5 L4 5.5 V10 C4 13.8 6.5 16.8 10 18 C13.5 16.8 16 13.8 16 10 V5.5 L10 2.5 Z" strokeLinejoin="round" />
          <path d="M7.5 10 L9.2 11.8 L12.8 8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case 3: // Nguồn / Sources (Literature library)
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
          <path d="M3.5 5 C5.5 4, 8 4, 10 5.5 C12 4, 14.5 4, 16.5 5 V15 C14.5 14, 12 14, 10 15.5 C8 14, 5.5 14, 3.5 15 Z" strokeLinejoin="round" />
          <line x1="10" y1="5.5" x2="10" y2="15.5" />
        </svg>
      );
    case 4: // Thêm / More
    default:
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
          <circle cx="5" cy="10" r="1.5" fill="currentColor" stroke="none" />
          <circle cx="10" cy="10" r="1.5" fill="currentColor" stroke="none" />
          <circle cx="15" cy="10" r="1.5" fill="currentColor" stroke="none" />
        </svg>
      );
  }
}

export function AdaptiveShellDemo({
  currentMode: controlledMode,
  onModeChange,
  className = "",
}: AdaptiveShellDemoProps) {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V7[language].adaptive;
  const [internalMode, setInternalMode] = useState<AdaptiveModeId>("personal");
  const [activeSlotIndex, setActiveSlotIndex] = useState<number>(0);

  const activeMode = controlledMode ?? internalMode;

  const handleSelectMode = (mode: AdaptiveModeId) => {
    setInternalMode(mode);
    onModeChange?.(mode);
  };

  const modeConfig = copy.modes[activeMode];

  const themeConfig = {
    personal: {
      tone: "azure" as const,
      ambientClass: "clara-ambient-azure",
      badgeClass: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/25",
      accentText: "text-[#0B6FD8]",
      btnClass: "bg-[#0B6FD8] text-white hover:bg-[#0855A8]",
      activeNavClass: "bg-[#EFF7FF] text-[#0B6FD8] font-bold border-[#0B6FD8]/30 shadow-xs",
      dockActiveClass: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/40 shadow-sm",
      widgetCardClass: "bg-[#EFF7FF]/70 border-[#0B6FD8]/20",
      dotIndicator: "bg-[#0B6FD8]",
      tagline: language === "vi" ? "Chế độ Cá nhân (Azure)" : "Personal Mode (Azure)",
    },
    clinical: {
      tone: "mint" as const,
      ambientClass: "clara-ambient-mint",
      badgeClass: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/25",
      accentText: "text-[#14A88D]",
      btnClass: "bg-[#14A88D] text-white hover:bg-[#0E856F]",
      activeNavClass: "bg-[#ECFDF8] text-[#14A88D] font-bold border-[#14A88D]/30 shadow-xs",
      dockActiveClass: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/40 shadow-sm",
      widgetCardClass: "bg-[#ECFDF8]/70 border-[#14A88D]/20",
      dotIndicator: "bg-[#14A88D]",
      tagline: language === "vi" ? "Chế độ Lâm sàng (Mint)" : "Clinical Mode (Mint)",
    },
    research: {
      tone: "iris" as const,
      ambientClass: "clara-ambient-iris",
      badgeClass: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/25",
      accentText: "text-[#8B7CF6]",
      btnClass: "bg-[#8B7CF6] text-white hover:bg-[#6D5BD0]",
      activeNavClass: "bg-[#F5F3FF] text-[#8B7CF6] font-bold border-[#8B7CF6]/30 shadow-xs",
      dockActiveClass: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/40 shadow-sm",
      widgetCardClass: "bg-[#F5F3FF]/70 border-[#8B7CF6]/20",
      dotIndicator: "bg-[#8B7CF6]",
      tagline: language === "vi" ? "Chế độ Nghiên cứu (Iris)" : "Research Mode (Iris)",
    },
  }[activeMode];

  return (
    <div className={`w-full space-y-6 ${className}`} data-testid="adaptive-shell-demo">
      {/* 1. Mode Segmented Controls (Top Switcher) */}
      <div className="flex flex-col items-center justify-center gap-2">
        <div
          className="inline-flex items-center gap-1.5 rounded-2xl bg-white p-1.5 border border-[#E3E8EF] shadow-sm"
          role="tablist"
          aria-label={language === "vi" ? "Chuyển đổi chế độ thích nghi" : "Adaptive mode switcher"}
        >
          {(["personal", "clinical", "research"] as const).map((modeKey) => {
            const isSelected = activeMode === modeKey;
            const modeItem = copy.modes[modeKey];
            return (
              <button
                key={modeKey}
                type="button"
                role="tab"
                aria-selected={isSelected}
                onClick={() => handleSelectMode(modeKey)}
                className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs sm:text-sm font-bold transition-all clara-focus-ring ${
                  isSelected
                    ? "bg-[#162033] text-white shadow-sm"
                    : "text-[#48566A] hover:text-[#162033] hover:bg-[#F8FAFD]"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full transition-colors ${
                    isSelected
                      ? modeKey === "personal"
                        ? "bg-[#38BDF8]"
                        : modeKey === "clinical"
                        ? "bg-[#2DD4BF]"
                        : "bg-[#C084FC]"
                      : "bg-[#D5DDE7]"
                  }`}
                />
                <span>{modeItem.label}</span>
              </button>
            );
          })}
        </div>
        <p className="text-[11px] text-[#6D7A8E] font-medium">
          {language === "vi"
            ? "Cùng một khung hệ thống duy nhất — Biến đổi nhãn, biểu tượng, widget bối cảnh và phổ màu"
            : "One unified system shell — Morphing labels, icons, context widgets, and ambient tints"}
        </p>
      </div>

      {/* 2. THE ONE ADAPTIVE APPLICATION SHELL (Exact geometry preserved) */}
      <div
        className={`clara-product-surface relative overflow-hidden p-5 sm:p-7 lg:p-9 transition-all duration-500 ${themeConfig.ambientClass}`}
      >
        {/* Shell Top App Bar with Window Controls & Ambient Orb */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-4">
          <div className="flex items-center gap-3">
            {/* Window Traffic Dots */}
            <div className="hidden sm:flex items-center gap-1.5 mr-1" aria-hidden="true">
              <span className="h-2.5 w-2.5 rounded-full bg-[#E2E8F0] border border-[#CBD5E1]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#E2E8F0] border border-[#CBD5E1]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#E2E8F0] border border-[#CBD5E1]" />
            </div>

            {/* ClaraOrb Anchor */}
            <ClaraOrb
              size="sm"
              tone={themeConfig.tone}
              pulse={true}
              interactive={false}
              className="shrink-0"
            />

            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-[#162033] tracking-tight">CLARA Care</span>
                <span className="rounded-md bg-[#162033] px-2 py-0.5 text-[10px] font-mono font-bold text-white uppercase tracking-wider">
                  Adaptive Shell
                </span>
              </div>
              <p className="text-[11px] text-[#6D7A8E] font-mono">v7.0 • {themeConfig.tagline}</p>
            </div>
          </div>

          <span
            className={`rounded-full px-3 py-1 text-xs font-bold border transition-all duration-300 ${themeConfig.badgeClass}`}
          >
            {modeConfig.label} • {modeConfig.tagline}
          </span>
        </div>

        {/* Shell Layout: Left Morphing Rail + Main Workspace Surface */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          {/* Left Navigation Rail (Preserves exact slot geometry) */}
          <div
            className="md:col-span-3 space-y-1.5 rounded-2xl bg-white/70 p-3 border border-[#E3E8EF] backdrop-blur-xs"
            role="navigation"
            aria-label={language === "vi" ? "Thanh điều hướng vai trò" : "Role navigation rail"}
          >
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] px-2 block mb-2">
              {language === "vi" ? "Điều hướng vai trò" : "Role Navigation"}
            </span>

            {modeConfig.navItems.map((item, idx) => {
              const isSelected = activeSlotIndex === idx;
              const isCenterSlot = idx === 2;

              return (
                <button
                  key={`slot-${idx}-${item}`}
                  type="button"
                  onClick={() => setActiveSlotIndex(idx)}
                  className={`w-full flex items-center justify-between rounded-xl px-3 py-2.5 text-xs transition-all border text-left clara-focus-ring ${
                    isSelected
                      ? themeConfig.activeNavClass
                      : "border-transparent text-[#48566A] hover:bg-[#F8FAFD] hover:text-[#162033]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {isCenterSlot ? (
                      <span className="flex h-5 w-5 items-center justify-center shrink-0">
                        <ClaraOrb size="sm" tone={themeConfig.tone} pulse={false} />
                      </span>
                    ) : (
                      <span className="shrink-0 text-current">
                        <NavSlotIcon mode={activeMode} slotIndex={idx} className="h-4 w-4" />
                      </span>
                    )}
                    <span className="truncate font-semibold">{item}</span>
                  </div>

                  {isSelected && (
                    <span className={`h-1.5 w-1.5 rounded-full ${themeConfig.dotIndicator} shrink-0`} />
                  )}
                </button>
              );
            })}
          </div>

          {/* Morphing Main Workspace Surface (Preserves exact layout dimensions) */}
          <div className="md:col-span-9 rounded-2xl bg-white p-5 sm:p-6 border border-[#E3E8EF] shadow-sm space-y-5">
            {/* Workspace Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF] pb-4">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {language === "vi" ? "Không gian làm việc chính" : "Active Workspace"}
                </span>
                <h4 className="text-base sm:text-lg font-bold text-[#162033] mt-0.5">
                  {modeConfig.headline}
                </h4>
              </div>
              <button
                type="button"
                className={`rounded-xl px-4 py-2 text-xs font-bold transition-all shadow-xs clara-focus-ring ${themeConfig.btnClass}`}
              >
                {language === "vi" ? "Mở tác vụ" : "Open Task"} →
              </button>
            </div>

            {/* Role-Specific Priority Action Card */}
            <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                  {language === "vi" ? "Tác vụ ưu tiên hàng đầu" : "Top Priority Protocol"}
                </span>
              </div>
              <p className="text-xs sm:text-sm font-medium text-[#48566A] leading-relaxed">
                {modeConfig.actionItem}
              </p>
            </div>

            {/* Inner Mode Data Widgets (Strict Geometry Alignment) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
              {activeMode === "personal" && (
                <>
                  <div className={`rounded-xl p-4 border transition-all ${themeConfig.widgetCardClass}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#0B6FD8] uppercase tracking-wider">
                        {language === "vi" ? "Tuân thủ phác đồ thuốc" : "Medication Adherence"}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                        100%
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">Metformin 500mg • Amlodipine 5mg</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi"
                        ? "Đã uống 30 ngày liên tục đúng lịch • 0 tương tác thuốc đối kháng"
                        : "30 consecutive days verified on schedule • 0 adverse DDIs"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#48566A] uppercase tracking-wider">
                        {language === "vi" ? "Theo dõi huyết áp LifeMap" : "LifeMap BP Surveillance"}
                      </span>
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                        {language === "vi" ? "Ổn định" : "Stable"}
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">Trung bình 125/80 mmHg (60 ngày)</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi" ? "Lần tái khám tiếp theo: 24/09/2026" : "Next scheduled follow-up: Sep 24, 2026"}
                    </p>
                  </div>
                </>
              )}

              {activeMode === "clinical" && (
                <>
                  <div className={`rounded-xl p-4 border transition-all ${themeConfig.widgetCardClass}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#14A88D] uppercase tracking-wider">
                        {language === "vi" ? "Ca hội chẩn Council chờ duyệt" : "Pending Council Consults"}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
                        3 ca
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">Tim mạch + Thận học + Dược lâm sàng</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi"
                        ? "Phát hiện xung đột liều Metformin trên eGFR 38 mL/min"
                        : "Identified Metformin dose tension on baseline eGFR 38 mL/min"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#48566A] uppercase tracking-wider">
                        {language === "vi" ? "Phiên Ambient Scribe đã ký" : "Signed Scribe Encounters"}
                      </span>
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                        8 / 8
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">100% bệnh án SOAP đã hoàn tất</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi"
                        ? "Biên phiên âm song ngữ Việt - Anh chuẩn hóa quốc tế"
                        : "Standardized bilingual Vietnamese-English clinical note drafts"}
                    </p>
                  </div>
                </>
              )}

              {activeMode === "research" && (
                <>
                  <div className={`rounded-xl p-4 border transition-all ${themeConfig.widgetCardClass}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#8B7CF6] uppercase tracking-wider">
                        {language === "vi" ? "Ma trận Bằng chứng Y văn" : "Living Evidence Matrix"}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-[#8B7CF6] border border-[#8B7CF6]/20">
                        14 RCTs
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">SGLT2i trên bệnh nhân HFpEF</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi"
                        ? "Tổng hợp khuyến cáo KDIGO 2023 + ADA Standards 2024"
                        : "KDIGO 2023 guidelines + ADA 2024 standards integrated"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[#48566A] uppercase tracking-wider">
                        {language === "vi" ? "Cấp bậc thẩm quyền" : "Authority Hierarchy"}
                      </span>
                      <span className="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-bold text-purple-700 border border-purple-200">
                        Grade A
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#162033]">Dược thư Quốc gia VN + DrugBank 5.1</p>
                    <p className="text-[11px] text-[#6D7A8E] mt-1">
                      {language === "vi"
                        ? "Trích xuất định lượng kèm phạm vi chưa chắc chắn"
                        : "Quantitative extraction with explicit uncertainty bounds"}
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* 3. FLOATING PRIMARY DOCK (Preserves Exact 5-Slot Geometry across Morphs) */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {language === "vi" ? "Thanh Dock trung tâm cố định" : "Centered Spatial Dock Parity"}
                </span>
                <span className="text-[10px] font-mono text-[#6D7A8E]">
                  5 slots • locked geometry
                </span>
              </div>

              <div
                className="clara-floating-chrome rounded-2xl p-1.5 sm:p-2 border border-[#E3E8EF] shadow-md flex items-center justify-between gap-1 sm:gap-2 max-w-lg mx-auto"
                role="toolbar"
                aria-label={language === "vi" ? "Thanh công cụ Dock thích nghi" : "Adaptive Primary Dock"}
              >
                {modeConfig.navItems.map((item, idx) => {
                  const isSelected = activeSlotIndex === idx;
                  const isCenterSlot = idx === 2;

                  if (isCenterSlot) {
                    return (
                      <button
                        key={`dock-slot-${idx}-${item}`}
                        type="button"
                        onClick={() => setActiveSlotIndex(idx)}
                        className="group relative flex flex-1 flex-col items-center justify-center rounded-xl py-1 sm:py-1.5 px-1 transition-all clara-focus-ring"
                        aria-label={`CLARA Central Copilot (${item})`}
                      >
                        <div className="relative -mt-3 flex h-10 w-10 sm:h-11 sm:w-11 items-center justify-center rounded-full shadow-md bg-white border border-[#E3E8EF] transition-transform group-hover:scale-105">
                          <ClaraOrb size="sm" tone={themeConfig.tone} pulse={true} />
                        </div>
                        <span className={`text-[10px] sm:text-[11px] font-bold mt-0.5 transition-colors ${themeConfig.accentText}`}>
                          {item}
                        </span>
                      </button>
                    );
                  }

                  return (
                    <button
                      key={`dock-slot-${idx}-${item}`}
                      type="button"
                      onClick={() => setActiveSlotIndex(idx)}
                      className={`flex flex-1 flex-col items-center justify-center rounded-xl py-1.5 px-1 sm:px-2 text-center transition-all border clara-focus-ring ${
                        isSelected
                          ? themeConfig.dockActiveClass
                          : "border-transparent text-[#48566A] hover:bg-[#F8FAFD] hover:text-[#162033]"
                      }`}
                    >
                      <span className="shrink-0 text-current mb-0.5">
                        <NavSlotIcon mode={activeMode} slotIndex={idx} className="h-4 w-4" />
                      </span>
                      <span className="text-[10px] sm:text-[11px] font-semibold truncate max-w-full">
                        {item}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdaptiveShellDemo;
