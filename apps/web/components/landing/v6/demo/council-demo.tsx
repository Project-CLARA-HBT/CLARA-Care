"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";

export function CouncilDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].council;
  const [activeTab, setActiveTab] = useState<"recommendation" | "disagreements" | "uncertainty" | "nextSteps">("recommendation");

  return (
    <div className="w-full space-y-6">
      {/* Explicit Clinical Governance Disclaimer */}
      <div className="rounded-2xl bg-[#EFF7FF] p-4 border border-[#0B6FD8]/20 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[#0B6FD8] text-white text-xs font-bold">
            i
          </span>
          <p className="text-xs sm:text-sm font-semibold text-[#0B6FD8]">
            {copy.disclaimer}
          </p>
        </div>
        <span className="shrink-0 text-xs font-bold text-[#48566A] bg-white px-2.5 py-1 rounded-lg border border-[#E3E8EF]">
          Bác sĩ giữ quyền tối cao
        </span>
      </div>

      {/* Main Council Decision Theater */}
      <div className="clara-product-surface relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (35%): Case Context */}
          <div className="lg:col-span-4 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] space-y-4">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                Bối cảnh ca bệnh phức tạp
              </span>
              <h4 className="text-base font-bold text-[#162033] mt-0.5">
                {copy.caseContext.patient}
              </h4>
              <p className="text-xs text-[#48566A] mt-1 leading-relaxed">
                {copy.caseContext.ageGender}
              </p>
            </div>

            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] space-y-2 text-xs">
              <div>
                <span className="font-bold text-[#162033] block">Lý do hội chẩn:</span>
                <p className="text-[#48566A] mt-0.5">{copy.caseContext.chiefComplaint}</p>
              </div>
              <div className="pt-2 border-t border-[#E3E8EF]">
                <span className="font-bold text-[#162033] block">Sinh hiệu & Xét nghiệm:</span>
                <p className="text-[#0B6FD8] font-mono font-medium mt-0.5">{copy.caseContext.vitals}</p>
              </div>
              <div className="pt-2 border-t border-[#E3E8EF]">
                <span className="font-bold text-[#162033] block">Thuốc đang dùng:</span>
                <p className="text-[#48566A] mt-0.5">{copy.caseContext.activeMeds}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1 text-[11px] font-medium text-[#6D7A8E]">
              <span>3 Chuyên khoa tham gia:</span>
              <span className="font-semibold text-[#162033]">Tim mạch • Thận • Dược</span>
            </div>
          </div>

          {/* Right Column (65%): Progressive Structured Council Result (DOMINATES) */}
          <div className="lg:col-span-8 space-y-5">
            {/* Section Switcher Tabs */}
            <div className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1 border border-[#E3E8EF]" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "recommendation"}
                onClick={() => setActiveTab("recommendation")}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                  activeTab === "recommendation"
                    ? "bg-white text-[#0B6FD8] shadow-sm"
                    : "text-[#48566A] hover:text-[#162033]"
                }`}
              >
                1. Khuyến nghị
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "disagreements"}
                onClick={() => setActiveTab("disagreements")}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                  activeTab === "disagreements"
                    ? "bg-white text-rose-700 shadow-sm"
                    : "text-[#48566A] hover:text-[#162033]"
                }`}
              >
                2. Điểm bất đồng
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "uncertainty"}
                onClick={() => setActiveTab("uncertainty")}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                  activeTab === "uncertainty"
                    ? "bg-white text-amber-700 shadow-sm"
                    : "text-[#48566A] hover:text-[#162033]"
                }`}
              >
                3. Điều chưa chắc chắn
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "nextSteps"}
                onClick={() => setActiveTab("nextSteps")}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring ${
                  activeTab === "nextSteps"
                    ? "bg-white text-[#14A88D] shadow-sm"
                    : "text-[#48566A] hover:text-[#162033]"
                }`}
              >
                4. Bước tiếp theo
              </button>
            </div>

            {/* Structured Result Display */}
            <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] shadow-sm space-y-4">
              {activeTab === "recommendation" && (
                <div className="space-y-2 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-[#0B6FD8]" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                      {copy.recommendationTitle}
                    </h4>
                  </div>
                  <div className="text-sm font-medium text-[#162033] leading-relaxed whitespace-pre-line">
                    {copy.recommendationBody}
                  </div>
                </div>
              )}

              {activeTab === "disagreements" && (
                <div className="space-y-2 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700">
                      {copy.disagreementsTitle}
                    </h4>
                  </div>
                  <p className="text-sm font-medium text-[#162033] leading-relaxed">
                    {copy.disagreementsBody}
                  </p>
                </div>
              )}

              {activeTab === "uncertainty" && (
                <div className="space-y-2 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">
                      {copy.uncertaintyTitle}
                    </h4>
                  </div>
                  <p className="text-sm font-medium text-[#162033] leading-relaxed">
                    {copy.uncertaintyBody}
                  </p>
                </div>
              )}

              {activeTab === "nextSteps" && (
                <div className="space-y-2 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-[#14A88D]" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                      {copy.nextStepsTitle}
                    </h4>
                  </div>
                  <p className="text-sm font-medium text-[#162033] leading-relaxed">
                    {copy.nextStepsBody}
                  </p>
                </div>
              )}

              {/* Reference Evidence Footer */}
              <div className="mt-6 pt-4 border-t border-[#E3E8EF] flex items-center justify-between text-xs text-[#6D7A8E]">
                <span>
                  <strong className="text-[#162033]">{copy.evidenceTitle}:</strong> {copy.evidenceBody}
                </span>
                <span className="rounded bg-[#EFF7FF] px-2 py-0.5 text-[#0B6FD8] font-semibold">
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
