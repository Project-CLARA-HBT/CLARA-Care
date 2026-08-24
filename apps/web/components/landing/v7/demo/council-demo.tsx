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
 * Renders CLARA's Multidisciplinary Deliberation & Clinical Triage Workspace:
 * 1. Stage-synchronized DecisionField integration illustrating Cardiology (Azure), Nephrology (Mint), and Pharmacology (Iris).
 * 2. Strict 4-Stage Progressive Deliberation:
 *    - Stage 1: Multidisciplinary Recommendation / Synthesis (Azure Halo)
 *    - Stage 2: Specialty Disagreements & Divergence (Rose Halo)
 *    - Stage 3: Data Gaps & Uncertainty Bounds (Amber Halo)
 *    - Stage 4: Action Plan & Next Steps (Mint Halo)
 * 3. Smooth tab transitions with accent color halos, glowing indicators, and hover lift.
 * 4. Explicit Clinical Governance Disclaimer (Physician Ultimate Authority).
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
    activeClass: string;
    dotClass: string;
    glowingHaloClass: string;
  }[] = [
    {
      stage: 1,
      id: "recommendation",
      label: lang === "vi" ? "1. Khuyến nghị" : "1. Recommendation",
      activeClass: "bg-white text-[#0B6FD8] shadow-md shadow-[#0B6FD8]/15 ring-2 ring-[#0B6FD8]/30 -translate-y-0.5",
      dotClass: "bg-[#0B6FD8] shadow-[0_0_8px_rgba(11,111,216,0.8)]",
      glowingHaloClass: "shadow-[0_0_24px_rgba(11,111,216,0.18)] border-[#0B6FD8]/35 bg-gradient-to-b from-white via-[#EFF7FF]/30 to-white",
    },
    {
      stage: 2,
      id: "disagreements",
      label: lang === "vi" ? "2. Điểm bất đồng" : "2. Disagreements",
      activeClass: "bg-white text-rose-700 shadow-md shadow-rose-600/15 ring-2 ring-rose-400/40 -translate-y-0.5",
      dotClass: "bg-rose-600 shadow-[0_0_8px_rgba(225,29,72,0.8)]",
      glowingHaloClass: "shadow-[0_0_24px_rgba(225,29,72,0.18)] border-rose-300/80 bg-gradient-to-b from-white via-rose-50/30 to-white",
    },
    {
      stage: 3,
      id: "uncertainty",
      label: lang === "vi" ? "3. Chưa chắc chắn" : "3. Uncertainty",
      activeClass: "bg-white text-amber-800 shadow-md shadow-amber-600/15 ring-2 ring-amber-400/40 -translate-y-0.5",
      dotClass: "bg-amber-600 shadow-[0_0_8px_rgba(217,119,6,0.8)]",
      glowingHaloClass: "shadow-[0_0_24px_rgba(217,119,6,0.18)] border-amber-300/80 bg-gradient-to-b from-white via-amber-50/30 to-white",
    },
    {
      stage: 4,
      id: "nextSteps",
      label: lang === "vi" ? "4. Bước tiếp theo" : "4. Next Steps",
      activeClass: "bg-white text-[#0E856F] shadow-md shadow-[#14A88D]/15 ring-2 ring-[#14A88D]/40 -translate-y-0.5",
      dotClass: "bg-[#14A88D] shadow-[0_0_8px_rgba(20,168,141,0.8)]",
      glowingHaloClass: "shadow-[0_0_24px_rgba(20,168,141,0.18)] border-[#14A88D]/35 bg-gradient-to-b from-white via-[#ECFDF8]/30 to-white",
    },
  ];

  const currentTabConfig = tabs[currentStage - 1] || tabs[0];

  return (
    <div
      data-testid="council-demo"
      className={`w-full space-y-6 ${className}`}
    >
      {/* Explicit Clinical Governance Disclaimer */}
      <div className="rounded-2xl bg-gradient-to-r from-[#EFF7FF] to-[#F8FAFD] p-4 border border-[#0B6FD8]/25 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[#0B6FD8] text-white text-xs font-bold shadow-xs">
            i
          </span>
          <p className="text-xs sm:text-sm font-semibold text-[#0B6FD8]">
            {copy.disclaimer}
          </p>
        </div>
        <span className="shrink-0 text-xs font-bold text-[#48566A] bg-white px-3 py-1 rounded-lg border border-[#E3E8EF] shadow-2xs">
          {lang === "vi" ? "Bác sĩ giữ quyền tối cao" : "Physician Holds Ultimate Authority"}
        </span>
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

      {/* Main Council Decision Theater */}
      <div className="clara-product-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-10 border border-[#E3E8EF] shadow-lg bg-white transition-all duration-300">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (35-40%): Case Context & Multi-Specialty Engagement */}
          <div className="lg:col-span-5 rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] space-y-4 shadow-xs">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Bối cảnh ca bệnh phức tạp" : "Complex Case Context"}
                </span>
                <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                  {lang === "vi" ? "Đa bệnh lý" : "Multimorbidity"}
                </span>
              </div>
              <h4 className="text-base font-bold text-[#162033] mt-1">
                {copy.caseContext.patient}
              </h4>
              <p className="text-xs text-[#48566A] mt-1 leading-relaxed">
                {copy.caseContext.ageGender}
              </p>
            </div>

            <div className="rounded-xl bg-white p-4 border border-[#E3E8EF] space-y-2.5 text-xs shadow-2xs">
              <div>
                <span className="font-bold text-[#162033] block">
                  {lang === "vi" ? "Lý do hội chẩn:" : "Chief Complaint:"}
                </span>
                <p className="text-[#48566A] mt-0.5 leading-relaxed">{copy.caseContext.chiefComplaint}</p>
              </div>
              <div className="pt-2 border-t border-[#E3E8EF]">
                <span className="font-bold text-[#162033] block">
                  {lang === "vi" ? "Sinh hiệu & Xét nghiệm:" : "Vitals & Labs:"}
                </span>
                <p className="text-[#0B6FD8] font-mono font-medium mt-0.5">{copy.caseContext.vitals}</p>
              </div>
              <div className="pt-2 border-t border-[#E3E8EF]">
                <span className="font-bold text-[#162033] block">
                  {lang === "vi" ? "Thuốc đang dùng:" : "Active Regimen:"}
                </span>
                <p className="text-[#48566A] mt-0.5">{copy.caseContext.activeMeds}</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-medium text-[#6D7A8E]">
              <span className="font-bold text-[#162033]">
                {lang === "vi" ? "3 Chuyên khoa tham gia:" : "3 Specialties Engaged:"}
              </span>
              <div className="flex items-center gap-1.5 font-semibold text-[#162033]">
                <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 px-2 py-0.5 text-[#0B6FD8] text-[10px] border border-sky-200/60 shadow-2xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] shadow-[0_0_6px_rgba(11,111,216,0.6)]" />
                  {lang === "vi" ? "Tim mạch" : "Cardiology"}
                </span>
                <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-0.5 text-[#14A88D] text-[10px] border border-teal-200/60 shadow-2xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D] shadow-[0_0_6px_rgba(20,168,141,0.6)]" />
                  {lang === "vi" ? "Thận học" : "Nephrology"}
                </span>
                <span className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-[#8B7CF6] text-[10px] border border-purple-200/60 shadow-2xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#8B7CF6] shadow-[0_0_6px_rgba(139,124,246,0.6)]" />
                  {lang === "vi" ? "Dược lâm sàng" : "Pharmacology"}
                </span>
              </div>
            </div>
          </div>

          {/* Right Column (60-65%): Progressive Structured Council Result */}
          <div className="lg:col-span-7 space-y-5">
            {/* Section Switcher Tabs with Silky Active Halos */}
            <div
              className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1.5 border border-[#E3E8EF]"
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
                    className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
                      isSelected
                        ? tab.activeClass
                        : "text-[#48566A] hover:text-[#162033] hover:bg-white/60 hover:-translate-y-0.5"
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full transition-all ${tab.dotClass}`} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Structured Result Display with Accent Color Halo */}
            <div
              className={`rounded-2xl p-6 sm:p-7 border min-h-[270px] flex flex-col justify-between transition-all duration-300 ${currentTabConfig.glowingHaloClass}`}
            >
              <div key={`stage-content-${currentStage}`} className="animate-fadeIn">
                {currentStage === 1 && (
                  <div
                    id="council-panel-recommendation"
                    role="tabpanel"
                    aria-labelledby="council-tab-recommendation"
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#0B6FD8] shadow-[0_0_8px_rgba(11,111,216,0.8)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                          {copy.recommendationTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/25 shadow-2xs">
                        {lang === "vi" ? "Đồng thuận đa khoa" : "Multidisciplinary Consensus"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed whitespace-pre-line bg-[#F8FAFD] p-4 rounded-xl border border-[#E3E8EF]">
                      {copy.recommendationBody}
                    </div>
                  </div>
                )}

                {currentStage === 2 && (
                  <div
                    id="council-panel-disagreements"
                    role="tabpanel"
                    aria-labelledby="council-tab-disagreements"
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-rose-600 shadow-[0_0_8px_rgba(225,29,72,0.8)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700">
                          {copy.disagreementsTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200 shadow-2xs">
                        {lang === "vi" ? "Cần bác sĩ phán quyết" : "Requires Clinician Choice"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-rose-50/50 p-4 rounded-xl border border-rose-100">
                      {copy.disagreementsBody}
                    </div>
                  </div>
                )}

                {currentStage === 3 && (
                  <div
                    id="council-panel-uncertainty"
                    role="tabpanel"
                    aria-labelledby="council-tab-uncertainty"
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-amber-600 shadow-[0_0_8px_rgba(217,119,6,0.8)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">
                          {copy.uncertaintyTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200 shadow-2xs">
                        {lang === "vi" ? "Thiếu dữ liệu" : "Missing Parameter"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-amber-50/50 p-4 rounded-xl border border-amber-100">
                      {copy.uncertaintyBody}
                    </div>
                  </div>
                )}

                {currentStage === 4 && (
                  <div
                    id="council-panel-nextSteps"
                    role="tabpanel"
                    aria-labelledby="council-tab-nextSteps"
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#14A88D] shadow-[0_0_8px_rgba(20,168,141,0.8)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                          {copy.nextStepsTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                        {lang === "vi" ? "Kế hoạch đề xuất" : "Action Checklist"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-[#ECFDF8]/50 p-4 rounded-xl border border-[#14A88D]/20">
                      {copy.nextStepsBody}
                    </div>
                  </div>
                )}
              </div>

              {/* Reference Evidence Footer */}
              <div className="pt-4 mt-4 border-t border-[#E3E8EF] flex flex-wrap items-center justify-between gap-2 text-xs text-[#6D7A8E]">
                <span>
                  <strong className="text-[#162033]">{copy.evidenceTitle}:</strong>{" "}
                  <span className="font-medium text-[#48566A]">{copy.evidenceBody}</span>
                </span>
                <span className="rounded-md bg-[#EFF7FF] px-2.5 py-0.5 text-[11px] text-[#0B6FD8] font-bold border border-[#0B6FD8]/25 shadow-2xs">
                  Grade A Evidence
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CouncilDemo;
