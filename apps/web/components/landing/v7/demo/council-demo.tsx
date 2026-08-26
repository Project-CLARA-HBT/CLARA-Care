"use client";

import React, { useState, useEffect } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { DecisionField } from "../artwork/decision-field";

export type CouncilStage = 1 | 2 | 3 | 4;

export interface CouncilDemoProps {
  /**
   * Controlled active stage (1 to 4):
   * 1: Multidisciplinary Recommendation / Synthesis
   * 2: Specialty Disagreements & Divergence
   * 3: Data Gaps & Uncertainty Bounds
   * 4: Action Plan & Next Steps
   */
  activeStage?: CouncilStage | number;
  /**
   * Callback when active stage tab changes
   */
  onStageChange?: (stage: CouncilStage) => void;
  /**
   * Whether to include the embedded stage-synchronized DecisionField artwork.
   * Defaults to true for standalone usage; set to false if parent container renders external DecisionField.
   */
  showDecisionField?: boolean;
  /**
   * Additional container CSS classes
   */
  className?: string;
}

/**
 * CouncilDemo (Landing v7 Signature Surface)
 *
 * Renders CLARA's Multidisciplinary Case Deliberation Workspace:
 * 1. Synchronized DecisionField background & embedded spatial convergence field:
 *    - Cardiology (Azure), Nephrology (Mint), and Clinical Pharmacology (Iris) specialty stations.
 *    - Dynamic background contour rays and radiant convergence orbs that pulse with the active stage.
 * 2. Four Smooth Tab Transitions with Glowing Accent Halos:
 *    - Stage 1: Recommendations / Synthesis (Azure Halo)
 *    - Stage 2: Specialty Disagreements & Divergence (Rose Halo)
 *    - Stage 3: Missing Context & Uncertainty Bounds (Amber Halo)
 *    - Stage 4: Recommended Action Plan & Next Steps (Mint Halo)
 * 3. Structured Clinical Deliberation Theater:
 *    - Patient Case Dossier (Vitals, Chief Complaint, Active Regimen, eGFR).
 *    - Real-time Multi-Specialty Convergence Hub with live status metrics.
 * 4. Explicit Clinical Governance & Human Oversight:
 *    - Physician Ultimate Authority disclaimer (Human-in-the-Loop invariant).
 *    - Grade A Evidence reference citations (KDIGO 2023, ADA Standards 2024).
 * 5. Full WCAG 2.1 AA keyboard accessibility, bilingual support (vi/en), zero TypeScript errors.
 */
export function CouncilDemo({
  activeStage,
  onStageChange,
  showDecisionField = true,
  className = "",
}: CouncilDemoProps) {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.council ?? LANDING_COPY_V7.vi.council;

  const [internalStage, setInternalStage] = useState<CouncilStage>(1);

  const currentStage = (
    activeStage !== undefined
      ? Math.max(1, Math.min(4, Math.round(activeStage)))
      : internalStage
  ) as CouncilStage;

  useEffect(() => {
    if (activeStage !== undefined) {
      const normalized = Math.max(1, Math.min(4, Math.round(activeStage))) as CouncilStage;
      setInternalStage(normalized);
    }
  }, [activeStage]);

  const handleStageSelect = (stage: CouncilStage) => {
    setInternalStage(stage);
    onStageChange?.(stage);
  };

  const tabs: {
    stage: CouncilStage;
    id: string;
    label: string;
    accentColor: string;
    activeClass: string;
    dotClass: string;
    glowingHaloClass: string;
    badgeText: string;
    badgeClass: string;
  }[] = [
    {
      stage: 1,
      id: "recommendation",
      label: lang === "vi" ? "1. Khuyến nghị" : "1. Recommendation",
      accentColor: "#0B6FD8",
      activeClass:
        "bg-white text-[#0B6FD8] shadow-lg shadow-[#0B6FD8]/20 ring-2 ring-[#0B6FD8]/40 -translate-y-0.5",
      dotClass: "bg-[#0B6FD8] shadow-[0_0_10px_rgba(11,111,216,0.9)] ring-2 ring-[#0B6FD8]/30",
      glowingHaloClass:
        "shadow-[0_0_35px_rgba(11,111,216,0.18)] border-[#0B6FD8]/40 ring-1 ring-[#0B6FD8]/25 bg-gradient-to-br from-white via-[#EFF7FF]/70 to-[#F8FAFD]",
      badgeText: lang === "vi" ? "Đồng thuận đa khoa" : "Multidisciplinary Consensus",
      badgeClass:
        "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/30 shadow-[0_0_10px_rgba(11,111,216,0.15)]",
    },
    {
      stage: 2,
      id: "disagreements",
      label: lang === "vi" ? "2. Điểm bất đồng" : "2. Disagreements",
      accentColor: "#E11D48",
      activeClass:
        "bg-white text-rose-700 shadow-lg shadow-rose-600/20 ring-2 ring-rose-500/40 -translate-y-0.5",
      dotClass: "bg-rose-600 shadow-[0_0_10px_rgba(225,29,72,0.9)] ring-2 ring-rose-400/30",
      glowingHaloClass:
        "shadow-[0_0_35px_rgba(225,29,72,0.18)] border-rose-300 ring-1 ring-rose-400/25 bg-gradient-to-br from-white via-rose-50/70 to-[#F8FAFD]",
      badgeText: lang === "vi" ? "Cần bác sĩ phán quyết" : "Requires Clinician Choice",
      badgeClass:
        "bg-rose-50 text-rose-700 border-rose-300 shadow-[0_0_10px_rgba(225,29,72,0.15)]",
    },
    {
      stage: 3,
      id: "uncertainty",
      label: lang === "vi" ? "3. Chưa chắc chắn" : "3. Uncertainty",
      accentColor: "#D97706",
      activeClass:
        "bg-white text-amber-800 shadow-lg shadow-amber-600/20 ring-2 ring-amber-500/40 -translate-y-0.5",
      dotClass: "bg-amber-600 shadow-[0_0_10px_rgba(217,119,6,0.9)] ring-2 ring-amber-400/30",
      glowingHaloClass:
        "shadow-[0_0_35px_rgba(217,119,6,0.18)] border-amber-300 ring-1 ring-amber-400/25 bg-gradient-to-br from-white via-amber-50/70 to-[#F8FAFD]",
      badgeText: lang === "vi" ? "Thiếu dữ liệu" : "Missing Parameter",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 shadow-[0_0_10px_rgba(217,119,6,0.15)]",
    },
    {
      stage: 4,
      id: "nextSteps",
      label: lang === "vi" ? "4. Bước tiếp theo" : "4. Next Steps",
      accentColor: "#14A88D",
      activeClass:
        "bg-white text-[#0E856F] shadow-lg shadow-[#14A88D]/20 ring-2 ring-[#14A88D]/40 -translate-y-0.5",
      dotClass: "bg-[#14A88D] shadow-[0_0_10px_rgba(20,168,141,0.9)] ring-2 ring-[#14A88D]/30",
      glowingHaloClass:
        "shadow-[0_0_35px_rgba(20,168,141,0.18)] border-[#14A88D]/40 ring-1 ring-[#14A88D]/25 bg-gradient-to-br from-white via-[#ECFDF8]/70 to-[#F8FAFD]",
      badgeText: lang === "vi" ? "Kế hoạch đề xuất" : "Action Checklist",
      badgeClass:
        "bg-[#ECFDF8] text-[#0E856F] border-[#14A88D]/30 shadow-[0_0_10px_rgba(20,168,141,0.15)]",
    },
  ];

  const currentTabConfig = tabs[currentStage - 1] || tabs[0];

  return (
    <div
      data-testid="council-demo"
      aria-label={lang === "vi" ? "Không gian Hội chẩn Đa chuyên khoa" : "Multidisciplinary Case Deliberation Workspace"}
      className={`w-full space-y-6 ${className}`}
    >
      {/* Explicit Clinical Governance Disclaimer */}
      <div className="rounded-2xl bg-gradient-to-r from-[#EFF7FF] via-[#F8FAFD] to-[#F1F5F9] p-4 border border-[#0B6FD8]/25 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-all duration-300 hover:border-[#0B6FD8]/40">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[#0B6FD8] text-white text-xs font-bold shadow-sm shadow-[#0B6FD8]/25">
            i
          </span>
          <p className="text-xs sm:text-sm font-semibold text-[#0B6FD8]">
            {copy.disclaimer}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#48566A] bg-white px-3 py-1 rounded-lg border border-[#E3E8EF] shadow-2xs">
            <span className="h-2 w-2 rounded-full bg-[#14A88D] animate-pulse" />
            {lang === "vi" ? "Bác sĩ giữ quyền tối cao" : "Physician Holds Ultimate Authority"}
          </span>
        </div>
      </div>

      {/* Embedded Stage-Synchronized DecisionField Artwork */}
      {showDecisionField && (
        <div className="relative">
          <DecisionField
            activeStage={currentStage}
            onStageChange={(stg) => handleStageSelect(stg as CouncilStage)}
            className="shadow-xl"
          />
        </div>
      )}

      {/* Main Council Deliberation Workspace Surface */}
      <div className="clara-product-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-10 border border-[#E3E8EF] shadow-xl bg-white transition-all duration-300">
        {/* Dynamic Synchronized DecisionField Watermark / Contour Background */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden opacity-35 select-none"
        >
          <svg
            viewBox="0 0 1000 600"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="h-full w-full object-cover"
          >
            <defs>
              <radialGradient id="council-ambient-glow" cx="60%" cy="50%" r="60%">
                <stop
                  offset="0%"
                  stopColor={
                    currentStage === 1
                      ? "#0B6FD8"
                      : currentStage === 2
                      ? "#E11D48"
                      : currentStage === 3
                      ? "#D97706"
                      : "#14A88D"
                  }
                  stopOpacity="0.12"
                />
                <stop offset="60%" stopColor="#FFFFFF" stopOpacity="0" />
              </radialGradient>
            </defs>
            <rect width="1000" height="600" fill="url(#council-ambient-glow)" />

            {/* Specialty Convergence Ray Tracks */}
            <path
              d="M 120 120 C 300 120, 480 260, 680 300"
              stroke="#0B6FD8"
              strokeWidth={currentStage === 1 ? "2" : "1"}
              strokeDasharray="4 6"
              opacity={currentStage === 1 ? "0.6" : "0.2"}
            />
            <path
              d="M 120 300 C 320 300, 480 300, 680 300"
              stroke="#14A88D"
              strokeWidth={currentStage === 4 ? "2" : "1"}
              strokeDasharray="4 6"
              opacity={currentStage === 4 ? "0.6" : "0.2"}
            />
            <path
              d="M 120 480 C 300 480, 480 340, 680 300"
              stroke="#8B7CF6"
              strokeWidth={currentStage === 2 ? "2" : "1"}
              strokeDasharray="4 6"
              opacity={currentStage === 2 ? "0.6" : "0.2"}
            />

            {/* Central Convergence Focal Core */}
            <circle
              cx="680"
              cy="300"
              r="40"
              fill="none"
              stroke={
                currentStage === 1
                  ? "#0B6FD8"
                  : currentStage === 2
                  ? "#E11D48"
                  : currentStage === 3
                  ? "#D97706"
                  : "#14A88D"
              }
              strokeWidth="1.5"
              strokeDasharray="5 5"
              opacity="0.35"
            />
          </svg>
        </div>

        {/* Workspace Content Grid */}
        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (38%): Multidisciplinary Case Context & Specialty Stations */}
          <div className="lg:col-span-5 rounded-2xl bg-gradient-to-b from-[#F8FAFD] via-white to-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] space-y-4 shadow-sm">
            {/* Header & Case Tag */}
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Bối cảnh ca bệnh phức tạp" : "Complex Case Context"}
                </span>
                <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                  {lang === "vi" ? "Đa bệnh lý" : "Multimorbidity"}
                </span>
              </div>
              <h4 className="text-base font-bold text-[#162033] mt-1.5 tracking-tight">
                {copy.caseContext.patient}
              </h4>
              <p className="text-xs text-[#48566A] mt-1 leading-relaxed">
                {copy.caseContext.ageGender}
              </p>
            </div>

            {/* Structured Vitals & Labs Card */}
            <div className="rounded-xl bg-white p-4 border border-[#E3E8EF] space-y-3 text-xs shadow-2xs">
              <div>
                <span className="font-bold text-[#162033] block">
                  {lang === "vi" ? "Lý do hội chẩn:" : "Chief Complaint:"}
                </span>
                <p className="text-[#48566A] mt-0.5 leading-relaxed">{copy.caseContext.chiefComplaint}</p>
              </div>
              <div className="pt-2.5 border-t border-[#E3E8EF]">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#162033] block">
                    {lang === "vi" ? "Sinh hiệu & Xét nghiệm:" : "Vitals & Labs:"}
                  </span>
                  <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    eGFR 38 (Stage 3b)
                  </span>
                </div>
                <p className="text-[#0B6FD8] font-mono font-semibold mt-1">{copy.caseContext.vitals}</p>
              </div>
              <div className="pt-2.5 border-t border-[#E3E8EF]">
                <span className="font-bold text-[#162033] block">
                  {lang === "vi" ? "Thuốc đang dùng:" : "Active Regimen:"}
                </span>
                <p className="text-[#48566A] mt-0.5 leading-relaxed">{copy.caseContext.activeMeds}</p>
              </div>
            </div>

            {/* 3 Participating Specialty Stations */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#162033]">
                  {lang === "vi" ? "3 Chuyên khoa tham gia hội chẩn:" : "3 Specialties Engaged:"}
                </span>
                <span className="text-[10px] font-bold text-[#6D7A8E]">FIDES Synced</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-2">
                {/* 1. Tim mạch (Cardiology - Azure) */}
                <div
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs transition-all ${
                    currentStage === 1
                      ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-[0_0_12px_rgba(11,111,216,0.15)] ring-1 ring-[#0B6FD8]/30"
                      : "bg-white border-[#E3E8EF] hover:border-sky-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#EFF7FF] text-[#0B6FD8] border border-[#0B6FD8]/25 text-xs font-bold">
                      ♥
                    </span>
                    <div>
                      <span className="font-bold text-[#162033] block">
                        {lang === "vi" ? "Tim mạch" : "Cardiology"}
                      </span>
                      <span className="text-[10px] text-[#0B6FD8] font-medium">HA 152/88 • CAD</span>
                    </div>
                  </div>
                  <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[9px] font-bold text-[#0B6FD8] border border-sky-200">
                    {lang === "vi" ? "Kiểm soát HA" : "BP Control"}
                  </span>
                </div>

                {/* 2. Thận học (Nephrology - Mint) */}
                <div
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs transition-all ${
                    currentStage === 4
                      ? "bg-[#ECFDF8] border-[#14A88D] shadow-[0_0_12px_rgba(20,168,141,0.15)] ring-1 ring-[#14A88D]/30"
                      : "bg-white border-[#E3E8EF] hover:border-teal-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#ECFDF8] text-[#14A88D] border border-[#14A88D]/25 text-xs font-bold">
                      ◈
                    </span>
                    <div>
                      <span className="font-bold text-[#162033] block">
                        {lang === "vi" ? "Thận học" : "Nephrology"}
                      </span>
                      <span className="text-[10px] text-[#14A88D] font-medium">eGFR 38 mL/min</span>
                    </div>
                  </div>
                  <span className="rounded bg-teal-50 px-1.5 py-0.5 text-[9px] font-bold text-[#14A88D] border border-teal-200">
                    {lang === "vi" ? "Bảo vệ thận" : "Renal Guard"}
                  </span>
                </div>

                {/* 3. Dược lâm sàng (Pharmacology - Iris) */}
                <div
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs transition-all ${
                    currentStage === 2
                      ? "bg-[#F5F3FF] border-[#8B7CF6] shadow-[0_0_12px_rgba(139,124,246,0.15)] ring-1 ring-[#8B7CF6]/30"
                      : "bg-white border-[#E3E8EF] hover:border-purple-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#F5F3FF] text-[#8B7CF6] border border-[#8B7CF6]/25 text-xs font-bold">
                      ⬡
                    </span>
                    <div>
                      <span className="font-bold text-[#162033] block">
                        {lang === "vi" ? "Dược lâm sàng" : "Pharmacology"}
                      </span>
                      <span className="text-[10px] text-[#8B7CF6] font-medium">Metformin DDI Risk</span>
                    </div>
                  </div>
                  <span className="rounded bg-purple-50 px-1.5 py-0.5 text-[9px] font-bold text-[#8B7CF6] border border-purple-200">
                    {lang === "vi" ? "Giảm liều" : "Dose Check"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column (62%): Progressive Structured Council Deliberation Tabs */}
          <div className="lg:col-span-7 space-y-5">
            {/* Section Switcher Tabs with Silky Active Halos */}
            <div
              className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1.5 border border-[#E3E8EF] shadow-inner"
              role="tablist"
              aria-label={lang === "vi" ? "Các phần kết quả hội chẩn Council" : "Council deliberation sections"}
            >
              {tabs.map((tab) => {
                const isSelected = currentStage === tab.stage;
                return (
                  <button
                    key={tab.stage}
                    type="button"
                    role="tab"
                    id={`council-tab-${tab.id}`}
                    aria-selected={isSelected}
                    aria-controls={`council-panel-${tab.id}`}
                    onClick={() => handleStageSelect(tab.stage)}
                    className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
                      isSelected
                        ? tab.activeClass
                        : "text-[#48566A] hover:text-[#162033] hover:bg-white/70 hover:-translate-y-0.5"
                    }`}
                  >
                    <span className={`h-2.5 w-2.5 rounded-full transition-all ${tab.dotClass}`} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Structured Result Display with Dynamic Accent Color Halo */}
            <div
              className={`rounded-2xl p-6 sm:p-7 border min-h-[300px] flex flex-col justify-between transition-all duration-300 ${currentTabConfig.glowingHaloClass}`}
            >
              <div key={`stage-content-${currentStage}`} className="animate-fadeIn space-y-4">
                {currentStage === 1 && (
                  <div
                    id="council-panel-recommendation"
                    role="tabpanel"
                    aria-labelledby="council-tab-recommendation"
                    aria-label={lang === "vi" ? "1. Khuyến nghị" : "1. Recommendation"}
                    className="space-y-3.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="h-3 w-3 rounded-full bg-[#0B6FD8] shadow-[0_0_10px_rgba(11,111,216,0.9)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                          {copy.recommendationTitle}
                        </h4>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${currentTabConfig.badgeClass}`}>
                        {currentTabConfig.badgeText}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed whitespace-pre-line bg-white/90 p-4 sm:p-5 rounded-xl border border-[#0B6FD8]/25 shadow-xs">
                      {copy.recommendationBody}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-[#48566A] pt-1">
                      <span className="font-bold text-[#162033]">
                        {lang === "vi" ? "Đóng góp chuyên khoa:" : "Specialty Contributions:"}
                      </span>
                      <span className="rounded bg-[#EFF7FF] px-2 py-0.5 font-medium text-[#0B6FD8] border border-[#0B6FD8]/20">
                        {lang === "vi" ? "Tim mạch: Hướng dẫn HA" : "Cardiology: BP Target"}
                      </span>
                      <span className="rounded bg-[#ECFDF8] px-2 py-0.5 font-medium text-[#14A88D] border border-[#14A88D]/20">
                        {lang === "vi" ? "Thận học: Chỉnh liều eGFR" : "Nephrology: Renal Titration"}
                      </span>
                    </div>
                  </div>
                )}

                {currentStage === 2 && (
                  <div
                    id="council-panel-disagreements"
                    role="tabpanel"
                    aria-labelledby="council-tab-disagreements"
                    aria-label={lang === "vi" ? "2. Điểm bất đồng" : "2. Disagreements"}
                    className="space-y-3.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="h-3 w-3 rounded-full bg-rose-600 shadow-[0_0_10px_rgba(225,29,72,0.9)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700">
                          {copy.disagreementsTitle}
                        </h4>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${currentTabConfig.badgeClass}`}>
                        {currentTabConfig.badgeText}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-white/90 p-4 sm:p-5 rounded-xl border border-rose-200 shadow-xs">
                      {copy.disagreementsBody}
                    </div>
                    <div className="rounded-xl bg-rose-50/80 p-3 border border-rose-200 text-xs text-rose-900 space-y-1">
                      <span className="font-bold block text-rose-800">
                        {lang === "vi" ? "Xung đột Dược lực học vs Nguy cơ Lâm sàng:" : "Pharmacodynamic Conflict vs Clinical Risk:"}
                      </span>
                      <p className="text-[11px] leading-relaxed text-rose-900">
                        {lang === "vi"
                          ? "• Dược lâm sàng: Nguy cơ nhiễm toan lactic khi eGFR < 45 mL/min.\n• Tim mạch: Duy trì Metformin đem lại lợi ích mạch máu dài hạn."
                          : "• Pharmacology: Lactic acidosis risk when eGFR < 45 mL/min.\n• Cardiology: Long-term cardiovascular protection with continued regimen."}
                      </p>
                    </div>
                  </div>
                )}

                {currentStage === 3 && (
                  <div
                    id="council-panel-uncertainty"
                    role="tabpanel"
                    aria-labelledby="council-tab-uncertainty"
                    aria-label={lang === "vi" ? "3. Chưa chắc chắn" : "3. Uncertainty"}
                    className="space-y-3.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="h-3 w-3 rounded-full bg-amber-600 shadow-[0_0_10px_rgba(217,119,6,0.9)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">
                          {copy.uncertaintyTitle}
                        </h4>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${currentTabConfig.badgeClass}`}>
                        {currentTabConfig.badgeText}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-white/90 p-4 sm:p-5 rounded-xl border border-amber-200 shadow-xs">
                      {copy.uncertaintyBody}
                    </div>
                    <div className="rounded-xl bg-amber-50/80 p-3 border border-amber-200 text-xs text-amber-900 space-y-1">
                      <span className="font-bold block text-amber-800">
                        {lang === "vi" ? "Tham số cần định lượng bổ sung:" : "Pending Parameters to Quantify:"}
                      </span>
                      <p className="text-[11px] leading-relaxed text-amber-900">
                        {lang === "vi"
                          ? "• Tỷ lệ Albumin/Creatinine niệu (uACR)\n• Điện giải đồ huyết thanh (K+, Na+, Cl-)\n• HbA1c 3 tháng gần nhất"
                          : "• Urine Albumin-to-Creatinine Ratio (uACR)\n• Serum Electrolytes (K+, Na+, Cl-)\n• Recent 3-month HbA1c"}
                      </p>
                    </div>
                  </div>
                )}

                {currentStage === 4 && (
                  <div
                    id="council-panel-nextSteps"
                    role="tabpanel"
                    aria-labelledby="council-tab-nextSteps"
                    aria-label={lang === "vi" ? "4. Bước tiếp theo" : "4. Next Steps"}
                    className="space-y-3.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="h-3 w-3 rounded-full bg-[#14A88D] shadow-[0_0_10px_rgba(20,168,141,0.9)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                          {copy.nextStepsTitle}
                        </h4>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${currentTabConfig.badgeClass}`}>
                        {currentTabConfig.badgeText}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-white/90 p-4 sm:p-5 rounded-xl border border-[#14A88D]/25 shadow-xs">
                      {copy.nextStepsBody}
                    </div>
                    <div className="rounded-xl bg-[#ECFDF8]/80 p-3 border border-[#14A88D]/25 text-xs text-[#0E856F] space-y-1">
                      <span className="font-bold block text-[#0E856F]">
                        {lang === "vi" ? "Lộ trình theo dõi điều trị:" : "Clinical Surveillance Pathway:"}
                      </span>
                      <p className="text-[11px] leading-relaxed text-[#162033]">
                        {lang === "vi"
                          ? "✓ Tái khám đánh giá chức năng thận và HA sau 14 ngày\n✓ Cảnh báo bệnh nhân dấu hiệu tụt đường huyết khi chỉnh liều"
                          : "✓ Re-evaluate renal function and BP at 14 days\n✓ Patient education on hypoglycemia warning signs during titration"}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Reference Evidence Footer */}
              <div className="pt-4 mt-5 border-t border-[#E3E8EF] flex flex-wrap items-center justify-between gap-3 text-xs text-[#6D7A8E]">
                <div className="space-y-0.5">
                  <span className="block">
                    <strong className="text-[#162033]">{copy.evidenceTitle}:</strong>{" "}
                    <span className="font-medium text-[#48566A]">{copy.evidenceBody}</span>
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="rounded-md bg-[#EFF7FF] px-2.5 py-0.5 text-[11px] text-[#0B6FD8] font-bold border border-[#0B6FD8]/25 shadow-2xs">
                    Grade A Evidence
                  </span>
                  <span className="rounded-md bg-[#ECFDF8] px-2.5 py-0.5 text-[11px] text-[#14A88D] font-bold border border-[#14A88D]/25 shadow-2xs">
                    FIDES Vetted
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CouncilDemo;
