"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function HowScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].how;
  const [activeStep, setActiveStep] = useState(0);

  const stepPreviews = [
    {
      title: "Tiếp nhận câu hỏi thô",
      detail: "“Tôi uống Metformin cùng Amlodipine thì có cần lưu ý gì khi đổi giờ ăn không?”",
      badge: "User Input Captured",
    },
    {
      title: "Trích xuất & Khớp bối cảnh hồ sơ",
      detail: "Hồ sơ: Metformin 500mg (T2D), Amlodipine 5mg (Tăng HA). Tiền sử dạ dày nhạy cảm.",
      badge: "Context Loaded",
    },
    {
      title: "Chạy thẩm định FIDES & Dược thư",
      detail: "Kiểm tra DDI: Không đối kháng dược lý trực tiếp. Cảnh báo hấp thu khi dạ dày rỗng.",
      badge: "FIDES Passed",
    },
    {
      title: "Định dạng câu trả lời & Hành động",
      detail: "Đưa ra lời khuyên uống thuốc sau bữa ăn cố định và lịch đo huyết áp theo dõi.",
      badge: "Actionable Response Ready",
    },
  ];

  return (
    <LandingScene id="how-it-works" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="azure"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column (5 cols): Step Selector List */}
        <div className="lg:col-span-5 space-y-3" role="list">
          {copy.steps.map((step, idx) => {
            const isSelected = activeStep === idx;
            return (
              <button
                key={step.number}
                type="button"
                role="listitem"
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
        <div className="lg:col-span-7 clara-product-surface p-6 sm:p-8 bg-white border border-[#E3E8EF] shadow-lg">
          <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-5">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                Giai đoạn {copy.steps[activeStep].number} / 04
              </span>
              <h4 className="text-base font-bold text-[#162033] mt-0.5">
                {stepPreviews[activeStep].title}
              </h4>
            </div>

            <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
              {stepPreviews[activeStep].badge}
            </span>
          </div>

          <div className="rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] min-h-[140px] flex flex-col justify-center">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E] mb-1">
              Trạng thái xử lý nội bộ
            </span>
            <p className="text-sm sm:text-base font-medium text-[#162033] leading-relaxed">
              {stepPreviews[activeStep].detail}
            </p>
          </div>

          <div className="mt-5 flex items-center justify-between text-xs text-[#6D7A8E] pt-3 border-t border-[#E3E8EF]">
            <span>Thuật toán: FIDES Clinical Router</span>
            <span className="text-[#0B6FD8] font-semibold">Tự động chuyển tiếp</span>
          </div>
        </div>
      </div>
    </LandingScene>
  );
}
