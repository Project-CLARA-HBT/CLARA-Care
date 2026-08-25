"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

export function HowScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.how ?? LANDING_COPY_V7.vi.how;
  const [activeStep, setActiveStep] = useState(0);

  const stepPreviews = [
    {
      title: lang === "vi" ? "Tiếp nhận câu hỏi thô" : "Capture User Question",
      detail:
        lang === "vi"
          ? "“Tôi uống Metformin cùng Amlodipine thì có cần lưu ý gì khi đổi giờ ăn không?”"
          : "“I take Metformin and Amlodipine together; what should I know when changing meal times?”",
      badge: lang === "vi" ? "Tiếp nhận câu hỏi" : "User Input Captured",
    },
    {
      title: lang === "vi" ? "Trích xuất & Khớp bối cảnh hồ sơ" : "Context & History Alignment",
      detail:
        lang === "vi"
          ? "Hồ sơ: Metformin 500mg (T2D), Amlodipine 5mg (Tăng HA). Tiền sử dạ dày nhạy cảm."
          : "Profile: Metformin 500mg (T2D), Amlodipine 5mg (Hypertension). Sensitive GI history.",
      badge: lang === "vi" ? "Khớp bối cảnh" : "Context Loaded",
    },
    {
      title: lang === "vi" ? "Chạy thẩm định FIDES & Dược thư" : "FIDES & Pharmacopoeia Verification",
      detail:
        lang === "vi"
          ? "Kiểm tra DDI: Không đối kháng dược lý trực tiếp. Cảnh báo hấp thu khi dạ dày rỗng."
          : "DDI Crosscheck: No direct antagonism. GI absorption warning with food timing.",
      badge: lang === "vi" ? "Thẩm định an toàn" : "FIDES Passed",
    },
    {
      title: lang === "vi" ? "Định dạng câu trả lời & Hành động" : "Structured & Actionable Response",
      detail:
        lang === "vi"
          ? "Đưa ra lời khuyên uống thuốc sau bữa ăn cố định và lịch đo huyết áp theo dõi."
          : "Provides structured guidance on post-meal dosing and longitudinal BP log recommendations.",
      badge: lang === "vi" ? "Phản hồi có cấu trúc" : "Actionable Response Ready",
    },
  ];

  return (
    <LandingScene id="how-it-works" scale="signature" tone="canvas" className="relative overflow-hidden clara-transition-manifesto-how">
      {/* Top Transition Ribbon from Manifesto */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-14 opacity-35"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-5xl" />
      </div>

      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="azure"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start relative z-10">
        {/* Left Column (5 cols): Step Selector List */}
        <div className="lg:col-span-5 space-y-3" role="list">
          {copy.steps.map((step, idx) => {
            const isSelected = activeStep === idx;
            return (
              <button
                key={step.number}
                type="button"
                role="listitem"
                aria-label={`${step.number} ${step.title}`}
                onClick={() => setActiveStep(idx)}
                className={`w-full flex items-start gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring ${
                  isSelected
                    ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-sm -translate-y-0.5"
                    : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7]"
                }`}
              >
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
                    isSelected ? "bg-[#0B6FD8] text-white" : "bg-[#F1F5F9] text-[#6D7A8E]"
                  }`}
                >
                  {step.number}
                </span>

                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-[#162033]">{step.title}</h3>
                    <span className="text-[10px] font-semibold text-[#0B6FD8]">{step.stateBadge}</span>
                  </div>
                  <p className="text-xs text-[#48566A] mt-1 leading-relaxed">{step.description}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column (7 cols): ONE Transforming Product Surface */}
        <div className="lg:col-span-7 clara-product-surface p-6 sm:p-8 bg-white border border-[#E3E8EF] shadow-lg rounded-3xl">
          <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-5">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                {lang === "vi" ? "Giai đoạn" : "Stage"} {copy.steps[activeStep]?.number ?? "01"} / 04
              </span>
              <h4 className="text-base font-bold text-[#162033] mt-0.5">
                {stepPreviews[activeStep]?.title}
              </h4>
            </div>

            <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
              {stepPreviews[activeStep]?.badge}
            </span>
          </div>

          <div className="rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] min-h-[140px] flex items-center">
            <p className="text-sm sm:text-base text-[#162033] leading-relaxed font-medium">
              {stepPreviews[activeStep]?.detail}
            </p>
          </div>

          <div className="flex items-center justify-between mt-6 pt-4 border-t border-[#E3E8EF] text-xs text-[#6D7A8E]">
            <span>CLARA Multi-Tier Safety Pipeline</span>
            <span className="font-semibold text-[#0B6FD8]">
              {lang === "vi" ? "Bảo vệ liên tục" : "Continuous Verification"}
            </span>
          </div>
        </div>
      </div>

      {/* Downward Transition Ribbon Towards Chat Scene (Peak 2) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 right-1/4 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default HowScene;
