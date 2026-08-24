"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";

export function ScribeDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].scribe;
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4 | 5>(4); // Default SOAP Draft

  return (
    <div className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10">
      {/* Scribe Header & Stepper */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">CLARA Ambient Clinical Scribe</h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
              Bilingual VN/EN
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">
            Ghi chép hội thoại phòng khám & trích xuất bệnh án SOAP tự động
          </p>
        </div>

        {/* 5-Step Progress Indicators */}
        <div className="flex items-center gap-1.5" role="tablist">
          {[1, 2, 3, 4, 5].map((stepNum) => {
            const isCurrent = currentStep === stepNum;
            const isPassed = currentStep > stepNum;
            return (
              <button
                key={stepNum}
                type="button"
                role="tab"
                aria-selected={isCurrent}
                onClick={() => setCurrentStep(stepNum as 1 | 2 | 3 | 4 | 5)}
                className={`flex h-8 w-8 items-center justify-center rounded-xl text-xs font-bold transition-all clara-focus-ring ${
                  isCurrent
                    ? "bg-[#14A88D] text-white shadow-sm scale-105"
                    : isPassed
                    ? "bg-[#ECFDF8] text-[#14A88D] border border-[#14A88D]/30"
                    : "bg-[#F1F5F9] text-[#6D7A8E] hover:bg-[#E3E8EF]"
                }`}
              >
                0{stepNum}
              </button>
            );
          })}
        </div>
      </div>

      {/* Transforming Workspace Body */}
      <div className="mt-6">
        {/* Step 1: Consent */}
        {currentStep === 1 && (
          <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-3 animate-fadeIn">
            <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
              Bước 01 • {copy.states.consent.title}
            </span>
            <p className="text-sm font-semibold text-[#162033]">{copy.states.consent.desc}</p>
            <div className="rounded-xl bg-[#ECFDF8] p-4 border border-[#14A88D]/20 text-xs text-[#14A88D] font-medium">
              ✓ Bệnh nhân đã xác nhận đồng thuận qua cổng điện tử bảo mật.
            </div>
          </div>
        )}

        {/* Step 2: Recording with Waveform */}
        {currentStep === 2 && (
          <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-600">
                Bước 02 • {copy.states.recording.title}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 border border-rose-200">
                <span className="h-2 w-2 rounded-full bg-rose-600 animate-ping" />
                {copy.states.recording.timer}
              </span>
            </div>
            <p className="text-sm text-[#48566A]">{copy.states.recording.desc}</p>

            {/* Subtle Audio Waveform (8 bars) */}
            <div className="flex items-center justify-center gap-1.5 h-12 py-2 bg-[#F8FAFD] rounded-xl border border-[#E3E8EF]">
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-1" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-2" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-3" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-4" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-5" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-6" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-7" />
              <span className="w-1.5 rounded-full bg-[#14A88D] clara-wave-8" />
            </div>
          </div>
        )}

        {/* Step 3: Clinical Transcript */}
        {currentStep === 3 && (
          <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-3 animate-fadeIn">
            <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
              Bước 03 • {copy.states.transcript.title}
            </span>
            <p className="text-xs text-[#6D7A8E]">{copy.states.transcript.desc}</p>
            <div className="rounded-xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] font-mono text-xs text-[#162033] leading-relaxed">
              {copy.states.transcript.text}
            </div>
          </div>
        )}

        {/* Step 4: Structured SOAP Draft */}
        {currentStep === 4 && (
          <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
                Bước 04 • {copy.states.soap.title}
              </span>
              <span className="rounded-md bg-[#EFF7FF] px-2 py-0.5 text-xs font-bold text-[#0B6FD8]">
                Bệnh án cấu trúc
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF]">
                <strong className="text-[#0B6FD8] block mb-1">S — Subjective (Chủ quan):</strong>
                <p className="text-[#48566A]">{copy.states.soap.s}</p>
              </div>
              <div className="rounded-xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF]">
                <strong className="text-[#14A88D] block mb-1">O — Objective (Khách quan):</strong>
                <p className="text-[#48566A]">{copy.states.soap.o}</p>
              </div>
              <div className="rounded-xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF]">
                <strong className="text-[#8B7CF6] block mb-1">A — Assessment (Đánh giá):</strong>
                <p className="text-[#48566A]">{copy.states.soap.a}</p>
              </div>
              <div className="rounded-xl bg-[#F8FAFD] p-3.5 border border-[#E3E8EF]">
                <strong className="text-amber-700 block mb-1">P — Plan (Kế hoạch):</strong>
                <p className="text-[#48566A]">{copy.states.soap.p}</p>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Review & Sign */}
        {currentStep === 5 && (
          <div className="rounded-2xl bg-white p-6 border border-[#E3E8EF] space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                Bước 05 • {copy.states.review.title}
              </span>
              <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
                {copy.states.review.status}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-[#48566A]">{copy.states.review.desc}</p>
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                className="rounded-xl bg-[#14A88D] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#0E856F] transition-all clara-focus-ring"
              >
                Ký duyệt & Đồng bộ vào EMR
              </button>
              <button
                type="button"
                className="rounded-xl bg-[#F1F5F9] px-4 py-2.5 text-xs font-bold text-[#48566A] hover:bg-[#E3E8EF] transition-all clara-focus-ring"
              >
                Chỉnh sửa bản nháp
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
