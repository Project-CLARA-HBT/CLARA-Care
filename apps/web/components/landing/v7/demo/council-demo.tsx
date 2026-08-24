"use client";

import React, { useState, useEffect } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";

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
   * Additional container CSS classes
   */
  className?: string;
}

export function CouncilDemo({
  activeStage,
  onStageChange,
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

  const tabs: { stage: CouncilStage; id: string; label: string; activeClass: string; dotClass: string }[] = [
    {
      stage: 1,
      id: "recommendation",
      label: lang === "vi" ? "1. Khuyến nghị" : "1. Recommendation",
      activeClass: "bg-white text-[#0B6FD8] shadow-xs",
      dotClass: "bg-[#0B6FD8]",
    },
    {
      stage: 2,
      id: "disagreements",
      label: lang === "vi" ? "2. Điểm bất đồng" : "2. Disagreements",
      activeClass: "bg-white text-rose-700 shadow-xs",
      dotClass: "bg-rose-600",
    },
    {
      stage: 3,
      id: "uncertainty",
      label: lang === "vi" ? "3. Chưa chắc chắn" : "3. Uncertainty",
      activeClass: "bg-white text-amber-800 shadow-xs",
      dotClass: "bg-amber-600",
    },
    {
      stage: 4,
      id: "nextSteps",
      label: lang === "vi" ? "4. Bước tiếp theo" : "4. Next Steps",
      activeClass: "bg-white text-[#14A88D] shadow-xs",
      dotClass: "bg-[#14A88D]",
    },
  ];

  return (
    <div
      data-testid="council-demo"
      className={`w-full space-y-6 ${className}`}
    >
      {/* Explicit Clinical Governance Disclaimer */}
      <div className="rounded-2xl bg-[#EFF7FF] p-4 border border-[#0B6FD8]/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[#0B6FD8] text-white text-xs font-bold shadow-xs">
            i
          </span>
          <p className="text-xs sm:text-sm font-semibold text-[#0B6FD8]">
            {copy.disclaimer}
          </p>
        </div>
        <span className="shrink-0 text-xs font-bold text-[#48566A] bg-white px-2.5 py-1 rounded-lg border border-[#E3E8EF] shadow-2xs">
          {lang === "vi" ? "Bác sĩ giữ quyền tối cao" : "Physician Holds Ultimate Authority"}
        </span>
      </div>

      {/* Main Council Decision Theater */}
      <div className="clara-product-surface relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (35-40%): Case Context */}
          <div className="lg:col-span-5 rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Bối cảnh ca bệnh phức tạp" : "Complex Case Context"}
                </span>
                <span className="rounded-full bg-[#ECFDF8] px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
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
                <span className="inline-flex items-center gap-1 rounded bg-sky-50 px-1.5 py-0.5 text-[#0B6FD8] text-[10px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
                  {lang === "vi" ? "Tim mạch" : "Cardiology"}
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-teal-50 px-1.5 py-0.5 text-[#14A88D] text-[10px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
                  {lang === "vi" ? "Thận học" : "Nephrology"}
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-purple-50 px-1.5 py-0.5 text-[#8B7CF6] text-[10px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#8B7CF6]" />
                  {lang === "vi" ? "Dược lâm sàng" : "Pharmacology"}
                </span>
              </div>
            </div>
          </div>

          {/* Right Column (60-65%): Progressive Structured Council Result */}
          <div className="lg:col-span-7 space-y-5">
            {/* Section Switcher Tabs */}
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
                    className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                      isSelected
                        ? tab.activeClass
                        : "text-[#48566A] hover:text-[#162033] hover:bg-white/50"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${tab.dotClass}`} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Structured Result Display */}
            <div className="rounded-2xl bg-white p-6 sm:p-7 border border-[#E3E8EF] shadow-sm space-y-4 min-h-[260px] flex flex-col justify-between">
              <div>
                {currentStage === 1 && (
                  <div
                    id="council-panel-recommendation"
                    role="tabpanel"
                    aria-labelledby="council-tab-recommendation"
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#0B6FD8]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                          {copy.recommendationTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
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
                        <span className="h-2.5 w-2.5 rounded-full bg-rose-600" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700">
                          {copy.disagreementsTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                        {lang === "vi" ? "Cần bác sĩ phán quyết" : "Requires Clinician Choice"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-rose-50/40 p-4 rounded-xl border border-rose-100">
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
                        <span className="h-2.5 w-2.5 rounded-full bg-amber-600" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">
                          {copy.uncertaintyTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
                        {lang === "vi" ? "Thiếu dữ liệu" : "Missing Parameter"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-amber-50/40 p-4 rounded-xl border border-amber-100">
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
                        <span className="h-2.5 w-2.5 rounded-full bg-[#14A88D]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                          {copy.nextStepsTitle}
                        </h4>
                      </div>
                      <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
                        {lang === "vi" ? "Kế hoạch đề xuất" : "Action Checklist"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[#162033] leading-relaxed bg-[#ECFDF8]/40 p-4 rounded-xl border border-[#14A88D]/20">
                      {copy.nextStepsBody}
                    </div>
                  </div>
                )}
              </div>

              {/* Reference Evidence Footer */}
              <div className="pt-4 border-t border-[#E3E8EF] flex flex-wrap items-center justify-between gap-2 text-xs text-[#6D7A8E]">
                <span>
                  <strong className="text-[#162033]">{copy.evidenceTitle}:</strong>{" "}
                  <span className="font-medium text-[#48566A]">{copy.evidenceBody}</span>
                </span>
                <span className="rounded-md bg-[#EFF7FF] px-2 py-0.5 text-[11px] text-[#0B6FD8] font-bold border border-[#0B6FD8]/20">
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
