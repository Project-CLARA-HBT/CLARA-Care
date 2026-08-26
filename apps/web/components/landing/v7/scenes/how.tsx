"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";
import { AmbientField } from "../primitives/ambient-field";

/**
 * HowScene (Transforming 4-Stage Verification Pipeline)
 *
 * Interactive demonstration of CLARA's 4-stage safety pipeline:
 * 1. User Intake (Bạn đặt câu hỏi)
 * 2. Context Retrieval (CLARA tìm bối cảnh liên quan)
 * 3. FIDES Safety Validation (Kiểm tra nguồn & an toàn FIDES)
 * 4. Structured Actionable Response (Trả lời rõ ràng & gợi ý bước tiếp)
 *
 * Features an interactive step switcher that fluidly transforms ONE central product surface.
 */
export function HowScene() {
  const { language, isReducedMotion } = useMotionTier();
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
      icon: "💬",
      chips:
        lang === "vi"
          ? ["🎙 Nhập liệu thoại / văn bản", "⏱ Bắt đầu luồng xử lý", "🔒 Mã hóa Zero-CoT"]
          : ["🎙 Voice / Text Intake", "⏱ Pipeline Initiated", "🔒 Zero-CoT Enclave"],
    },
    {
      title: lang === "vi" ? "Trích xuất & Khớp bối cảnh hồ sơ" : "Context & History Alignment",
      detail:
        lang === "vi"
          ? "Hồ sơ: Metformin 500mg (T2D), Amlodipine 5mg (Tăng HA). Tiền sử dạ dày nhạy cảm."
          : "Profile: Metformin 500mg (T2D), Amlodipine 5mg (Hypertension). Sensitive GI history.",
      badge: lang === "vi" ? "Khớp bối cảnh" : "Context Loaded",
      icon: "🗂",
      chips:
        lang === "vi"
          ? ["💊 Metformin 500mg (T2D)", "💊 Amlodipine 5mg (Tăng HA)", "🛡 Dạ dày nhạy cảm"]
          : ["💊 Metformin 500mg (T2D)", "💊 Amlodipine 5mg (HTN)", "🛡 Sensitive GI History"],
    },
    {
      title: lang === "vi" ? "Chạy thẩm định FIDES & Dược thư" : "FIDES & Pharmacopoeia Verification",
      detail:
        lang === "vi"
          ? "Kiểm tra DDI: Không đối kháng dược lý trực tiếp. Cảnh báo hấp thu khi dạ dày rỗng."
          : "DDI Crosscheck: No direct antagonism. GI absorption warning with food timing.",
      badge: lang === "vi" ? "Thẩm định an toàn" : "FIDES Passed",
      icon: "🛡",
      chips:
        lang === "vi"
          ? ["✅ DDI: 0 Đối kháng trực tiếp", "📖 Dược thư Quốc gia VN", "🧬 DrugBank 5.1 Matched"]
          : ["✅ DDI: 0 Direct Antagonisms", "📖 National Pharmacopoeia", "🧬 DrugBank 5.1 Matched"],
    },
    {
      title: lang === "vi" ? "Định dạng câu trả lời & Hành động" : "Structured & Actionable Response",
      detail:
        lang === "vi"
          ? "Đưa ra lời khuyên uống thuốc sau bữa ăn cố định và lịch đo huyết áp theo dõi."
          : "Provides structured guidance on post-meal dosing and longitudinal BP log recommendations.",
      badge: lang === "vi" ? "Phản hồi có cấu trúc" : "Actionable Response Ready",
      icon: "✦",
      chips:
        lang === "vi"
          ? ["➔ Khuyến nghị uống sau ăn", "➔ Theo dõi huyết áp 3 ngày", "➔ Đồng bộ LifeMap"]
          : ["➔ Take with fixed meals", "➔ Log 3-day home BP", "➔ LifeMap Synced"],
    },
  ];

  return (
    <LandingScene
      id="how-it-works"
      scale="signature"
      tone="canvas"
      className="relative overflow-hidden py-20 md:py-28 clara-transition-manifesto-how"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Top Transition Ribbon from Manifesto Scene */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-14 opacity-35"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={!isReducedMotion} className="w-full max-w-6xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <SceneHeader
          eyebrow={copy.eyebrow}
          title={copy.title}
          description={copy.description}
          align="left"
          tone="azure"
          className="mb-10 md:mb-14"
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (5 cols): Interactive 4-Step Switcher */}
          <div className="lg:col-span-5 space-y-3" role="list">
            <RevealGroup staggerMs={70}>
              {copy.steps.map((step, idx) => {
                const isSelected = activeStep === idx;
                return (
                  <Reveal key={step.number} delayMs={idx * 60} direction="up">
                    <button
                      type="button"
                      role="listitem"
                      aria-label={`${step.number} ${step.title}`}
                      aria-current={isSelected ? "step" : undefined}
                      onClick={() => setActiveStep(idx)}
                      className={`w-full flex items-start gap-4 rounded-2xl p-4 sm:p-5 text-left transition-all duration-200 border clara-focus-ring cursor-pointer group ${
                        isSelected
                          ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-md -translate-y-0.5 ring-1 ring-[#0B6FD8]/30"
                          : "bg-white border-[#E3E8EF] hover:border-[#CBD5E1] hover:bg-[#F8FAFD] shadow-xs"
                      }`}
                    >
                      {/* Step Number Badge */}
                      <span
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-black transition-all ${
                          isSelected
                            ? "bg-[#0B6FD8] text-white shadow-xs scale-105"
                            : "bg-[#F1F5F9] text-[#6D7A8E] group-hover:bg-[#E2E8F0] group-hover:text-[#162033]"
                        }`}
                      >
                        {step.number}
                      </span>

                      {/* Step Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h3
                            className={`text-sm font-bold transition-colors ${
                              isSelected ? "text-[#0B6FD8]" : "text-[#162033] group-hover:text-[#0B6FD8]"
                            }`}
                          >
                            {step.title}
                          </h3>
                          <span
                            className={`rounded-md px-2 py-0.5 text-[10px] font-bold border transition-colors shrink-0 ${
                              isSelected
                                ? "bg-[#0B6FD8] text-white border-[#0B6FD8]"
                                : "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/20"
                            }`}
                          >
                            {step.stateBadge}
                          </span>
                        </div>
                        <p className="text-xs text-[#48566A] mt-1 leading-relaxed">
                          {step.description}
                        </p>
                      </div>
                    </button>
                  </Reveal>
                );
              })}
            </RevealGroup>
          </div>

          {/* Right Column (7 cols): ONE Transforming Product Surface Object */}
          <div className="lg:col-span-7">
            <Reveal delayMs={100} direction="scale">
              <div className="clara-product-surface p-6 sm:p-8 bg-white border border-[#E3E8EF] shadow-xl rounded-3xl relative overflow-hidden transition-all duration-300">
                {/* Ambient glow in background of product surface */}
                <div
                  aria-hidden="true"
                  className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-gradient-to-br from-[#0B6FD8]/15 via-[#38BDF8]/10 to-transparent blur-2xl pointer-events-none"
                />

                {/* Header Chrome: Stage Counter & Live State Badge */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF] pb-4 mb-5 relative z-10">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                        {lang === "vi" ? "Giai đoạn" : "Stage"} {copy.steps[activeStep]?.number ?? "01"} / 04
                      </span>
                      <span className="text-xs font-mono text-[#6D7A8E]">
                        • {stepPreviews[activeStep]?.icon}
                      </span>
                    </div>
                    <h4 className="text-base sm:text-lg font-bold text-[#162033] mt-0.5">
                      {stepPreviews[activeStep]?.title}
                    </h4>
                  </div>

                  {/* Live State Badge */}
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-xs">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D] animate-pulse" />
                    <span>{stepPreviews[activeStep]?.badge}</span>
                  </span>
                </div>

                {/* Step Progress Bar Track */}
                <div className="w-full bg-[#F1F5F9] h-1.5 rounded-full overflow-hidden flex gap-1 mb-5 relative z-10">
                  {[0, 1, 2, 3].map((stepIdx) => (
                    <div
                      key={`progress-seg-${stepIdx}`}
                      className={`h-full flex-1 rounded-full transition-all duration-300 ${
                        stepIdx <= activeStep ? "bg-[#0B6FD8]" : "bg-transparent"
                      }`}
                    />
                  ))}
                </div>

                {/* Dynamic Transforming Content Card Area */}
                <div className="rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] min-h-[140px] flex flex-col justify-between space-y-4 relative z-10">
                  <p className="text-sm sm:text-base text-[#162033] leading-relaxed font-medium">
                    {stepPreviews[activeStep]?.detail}
                  </p>

                  {/* Stage-Specific Contextual Chips */}
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#E3E8EF]/80">
                    {stepPreviews[activeStep]?.chips.map((chip) => (
                      <span
                        key={chip}
                        className="inline-flex items-center rounded-lg bg-white px-2.5 py-1 text-[11px] font-semibold text-[#48566A] border border-[#E3E8EF] shadow-2xs"
                      >
                        {chip}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Transforming Product Footer Chrome */}
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-[#E3E8EF] text-xs text-[#6D7A8E] relative z-10">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#0B6FD8] animate-pulse" />
                    <span>CLARA Multi-Tier Safety Pipeline</span>
                  </span>
                  <span className="font-semibold text-[#0B6FD8]">
                    {lang === "vi" ? "Bảo vệ liên tục" : "Continuous Verification"} ✦
                  </span>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </div>

      {/* Downward Transition Ribbon Towards Chat Scene (Peak 2) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 right-1/4 w-80 opacity-45 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={!isReducedMotion} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default HowScene;

