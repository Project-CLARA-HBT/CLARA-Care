"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { V6_DEMO_SOURCES, type V6DemoSource } from "../landing-data-v6";

export function ChatDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].chat;
  const [selectedSource, setSelectedSource] = useState<V6DemoSource | null>(V6_DEMO_SOURCES[0]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10">
      {/* Header Chrome */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#0B6FD8] text-white font-bold text-base shadow-sm">
            C
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-[#162033] text-base">CLARA Clinical Assistant</span>
              <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
                FIDES Verified
              </span>
            </div>
            <p className="text-xs text-[#6D7A8E]">Phiên tham vấn bối cảnh sức khỏe cá nhân</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-xl bg-[#F1F5F9] px-3 py-1.5 text-xs font-medium text-[#48566A]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
            Zero-CoT Security Active
          </span>
        </div>
      </div>

      {/* Question Turn */}
      <div className="mt-6 flex justify-end">
        <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-[#EFF7FF] p-4 sm:p-5 border border-[#0B6FD8]/15 text-[#162033]">
          <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">Câu hỏi của bạn</span>
          <p className="mt-1 text-sm sm:text-base font-medium leading-relaxed">
            Tôi mới bắt đầu uống Amlodipine 5mg được 3 ngày, gần đây đứng dậy hay thấy hơi chóng mặt nhẹ. Có cần ngừng thuốc ngay không?
          </p>
        </div>
      </div>

      {/* Answer Body: Progressive Tiered Surface */}
      <div className="mt-6 flex gap-4">
        <div className="hidden sm:flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#EFF7FF] text-[#0B6FD8] font-bold text-sm">
          AI
        </div>

        <div className="flex-1 space-y-5">
          {/* 1. Direct Answer */}
          <div className="rounded-2xl bg-white p-5 border border-[#E3E8EF] shadow-sm">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-[#0B6FD8]" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                {copy.directAnswerTitle}
              </h4>
            </div>
            <p className="mt-2 text-base text-[#162033] font-medium leading-relaxed">
              {copy.directAnswerBody}
            </p>
          </div>

          {/* 2. Next Actions */}
          <div className="rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF]">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#14A88D]">
              {copy.nextActionTitle}
            </h4>
            <div className="mt-2 space-y-1.5 text-sm text-[#48566A] whitespace-pre-line leading-relaxed font-normal">
              {copy.nextActionBody}
            </div>
          </div>

          {/* 3. Uncertainty / Missing Context */}
          <div className="rounded-2xl bg-[#FFFBEB] p-4 border border-[#FDE68A]/60">
            <div className="flex items-start gap-2.5">
              <span className="text-amber-600 font-bold text-sm">⚠</span>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-800">
                  {copy.uncertaintyTitle}
                </h4>
                <p className="mt-1 text-xs sm:text-sm text-amber-900/80 leading-relaxed">
                  {copy.uncertaintyBody}
                </p>
              </div>
            </div>
          </div>

          {/* 4. Referenced Sources Rail */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[#6D7A8E]">
                {copy.sourcesTitle}
              </span>
              <span className="text-xs text-[#6D7A8E]">{copy.sourcesDisclaimer}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {V6_DEMO_SOURCES.slice(0, 4).map((source) => {
                const isSelected = selectedSource?.id === source.id;
                return (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() => setSelectedSource(source)}
                    className={`flex items-start gap-3 rounded-xl p-3 text-left transition-all border clara-focus-ring ${
                      isSelected
                        ? "bg-[#EFF7FF] border-[#0B6FD8] text-[#0B6FD8]"
                        : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7] text-[#162033]"
                    }`}
                  >
                    <span className="mt-0.5 rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] font-bold text-[#48566A]">
                      {source.authorityLevel}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold truncate">{source.name}</p>
                      <p className="text-[11px] text-[#6D7A8E] truncate">{source.authority}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Source Inspector (when clicked) */}
            {selectedSource && (
              <div className="rounded-2xl bg-[#EFF7FF]/70 p-4 border border-[#0B6FD8]/20 mt-3 animate-fadeIn">
                <div className="flex items-center justify-between border-b border-[#0B6FD8]/15 pb-2 mb-2">
                  <span className="text-xs font-bold text-[#0B6FD8]">
                    {copy.inspectorTitle}: {selectedSource.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedSource(null)}
                    className="text-xs text-[#6D7A8E] hover:text-[#162033] clara-focus-ring px-1"
                  >
                    ✕
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-[#48566A]">
                  <div>
                    <span className="font-semibold text-[#162033]">Lý do phù hợp: </span>
                    {language === "vi" ? selectedSource.relevanceVi : selectedSource.relevanceEn}
                  </div>
                  <div>
                    <span className="font-semibold text-[#162033]">Phạm vi áp dụng: </span>
                    {language === "vi" ? selectedSource.applicabilityVi : selectedSource.applicabilityEn}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 5. Advanced Pharmacological Detail (Toggle) */}
          <div className="border-t border-[#E3E8EF] pt-4">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="inline-flex items-center gap-2 text-xs font-semibold text-[#0B6FD8] hover:text-[#0855A8] clara-focus-ring rounded-lg py-1"
            >
              <span>{showAdvanced ? "▼ Thu gọn" : "▶ Xem thêm"}</span>
              <span>{copy.advancedDetailTitle}</span>
            </button>

            {showAdvanced && (
              <div className="mt-3 rounded-2xl bg-[#F5F3FF] p-4 border border-[#8B7CF6]/20 text-xs text-[#48566A] leading-relaxed animate-fadeIn">
                <p className="font-medium text-[#162033] mb-1">Cơ chế dược động học & dược lực học:</p>
                {copy.advancedDetailBody}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
