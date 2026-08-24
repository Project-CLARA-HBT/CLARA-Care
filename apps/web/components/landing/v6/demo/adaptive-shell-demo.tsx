"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";

export type AdaptiveModeId = "personal" | "clinical" | "research";

export interface AdaptiveShellDemoProps {
  currentMode?: AdaptiveModeId;
  onModeChange?: (mode: AdaptiveModeId) => void;
}

export function AdaptiveShellDemo({
  currentMode: controlledMode,
  onModeChange,
}: AdaptiveShellDemoProps) {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].adaptive;
  const [internalMode, setInternalMode] = useState<AdaptiveModeId>("personal");

  const activeMode = controlledMode ?? internalMode;

  const handleSelectMode = (mode: AdaptiveModeId) => {
    setInternalMode(mode);
    onModeChange?.(mode);
  };

  const modeConfig = copy.modes[activeMode];

  const themeClasses = {
    personal: {
      ambient: "clara-ambient-azure",
      badge: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/20",
      accent: "text-[#0B6FD8]",
      btn: "bg-[#0B6FD8] text-white hover:bg-[#0855A8]",
      activeNav: "bg-[#EFF7FF] text-[#0B6FD8] font-bold",
    },
    clinical: {
      ambient: "clara-ambient-mint",
      badge: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20",
      accent: "text-[#14A88D]",
      btn: "bg-[#14A88D] text-white hover:bg-[#0E856F]",
      activeNav: "bg-[#ECFDF8] text-[#14A88D] font-bold",
    },
    research: {
      ambient: "clara-ambient-iris",
      badge: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/20",
      accent: "text-[#8B7CF6]",
      btn: "bg-[#8B7CF6] text-white hover:bg-[#6D5BD0]",
      activeNav: "bg-[#F5F3FF] text-[#8B7CF6] font-bold",
    },
  }[activeMode];

  return (
    <div className="w-full space-y-6">
      {/* Mode Segmented Controls */}
      <div className="flex justify-center">
        <div
          className="inline-flex items-center gap-2 rounded-2xl bg-white p-1.5 border border-[#E3E8EF] shadow-sm"
          role="tablist"
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
                className={`rounded-xl px-4 py-2 text-xs sm:text-sm font-bold transition-all clara-focus-ring ${
                  isSelected
                    ? "bg-[#162033] text-white shadow-sm scale-100"
                    : "text-[#48566A] hover:text-[#162033]"
                }`}
              >
                {modeItem.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* THE ONE ADAPTIVE SHELL (Preserves exact geometry) */}
      <div
        className={`clara-product-surface relative overflow-hidden p-6 sm:p-8 lg:p-10 transition-colors duration-500 ${themeClasses.ambient}`}
      >
        {/* Shell Top App Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#162033] text-white text-xs font-black">
              ✦
            </div>
            <div>
              <span className="text-sm font-bold text-[#162033]">CLARA Unified Shell</span>
              <span className="text-xs text-[#6D7A8E] ml-2 font-mono">v6.2-adaptive</span>
            </div>
          </div>

          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold border transition-all duration-300 ${themeClasses.badge}`}
          >
            {modeConfig.label} • {modeConfig.tagline}
          </span>
        </div>

        {/* Shell Layout: Sidebar Navigation + Main View */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          {/* Morphing Nav Items (Left 3 columns) */}
          <div className="md:col-span-3 space-y-1.5" role="navigation">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] px-2 block mb-1">
              Điều hướng vai trò
            </span>
            {modeConfig.navItems.map((item, idx) => {
              const isActive = idx === 0 || idx === 2;
              return (
                <div
                  key={item}
                  className={`flex items-center justify-between rounded-xl px-3 py-2 text-xs transition-all ${
                    isActive
                      ? themeClasses.activeNav
                      : "text-[#48566A] hover:bg-[#F1F5F9] hover:text-[#162033]"
                  }`}
                >
                  <span>{item}</span>
                  {isActive && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
                </div>
              );
            })}
          </div>

          {/* Morphing Main Surface (Right 9 columns) */}
          <div className="md:col-span-9 rounded-2xl bg-white p-6 border border-[#E3E8EF] shadow-sm space-y-5">
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  Không gian làm việc chính
                </span>
                <h4 className="text-base font-bold text-[#162033] mt-0.5">
                  {modeConfig.headline}
                </h4>
              </div>
              <button
                type="button"
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${themeClasses.btn}`}
              >
                Mở tác vụ
              </button>
            </div>

            {/* Role-Specific Content Card */}
            <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF]">
              <div className="flex items-center gap-2 mb-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-bold text-[#162033]">Tác vụ ưu tiên hàng đầu</span>
              </div>
              <p className="text-xs sm:text-sm font-medium text-[#48566A] leading-relaxed">
                {modeConfig.actionItem}
              </p>
            </div>

            {/* Inner Mode Data Widgets */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              {activeMode === "personal" && (
                <>
                  <div className="rounded-xl bg-[#EFF7FF] p-3 border border-[#0B6FD8]/20">
                    <span className="text-[11px] font-bold text-[#0B6FD8]">Tuân thủ phác đồ</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">100% 30 ngày qua</p>
                  </div>
                  <div className="rounded-xl bg-[#F8FAFD] p-3 border border-[#E3E8EF]">
                    <span className="text-[11px] font-bold text-[#48566A]">Nhắc nhở tiếp theo</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">Khám định kỳ 25/09</p>
                  </div>
                </>
              )}

              {activeMode === "clinical" && (
                <>
                  <div className="rounded-xl bg-[#ECFDF8] p-3 border border-[#14A88D]/20">
                    <span className="text-[11px] font-bold text-[#14A88D]">Ca hội chẩn chờ duyệt</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">3 ca đa chuyên khoa</p>
                  </div>
                  <div className="rounded-xl bg-[#F8FAFD] p-3 border border-[#E3E8EF]">
                    <span className="text-[11px] font-bold text-[#48566A]">Phiên Scribe đã ký</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">8/8 hồ sơ hôm nay</p>
                  </div>
                </>
              )}

              {activeMode === "research" && (
                <>
                  <div className="rounded-xl bg-[#F5F3FF] p-3 border border-[#8B7CF6]/20">
                    <span className="text-[11px] font-bold text-[#8B7CF6]">Nguồn đối chiếu</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">DrugBank + PubMed RCT</p>
                  </div>
                  <div className="rounded-xl bg-[#F8FAFD] p-3 border border-[#E3E8EF]">
                    <span className="text-[11px] font-bold text-[#48566A]">Cấp bậc thẩm quyền</span>
                    <p className="text-xs font-semibold text-[#162033] mt-1">Grade A Guideline</p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
