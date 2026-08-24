"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { V6_DEMO_SOURCES, type V6DemoSource } from "../landing-data-v6";

export function EvidenceDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].evidence;
  const [selectedSource, setSelectedSource] = useState<V6DemoSource>(V6_DEMO_SOURCES[0]);

  return (
    <div className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10">
      {/* Evidence Hub Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">Living Evidence Hub</h3>
            <span className="rounded-full bg-[#F5F3FF] px-2.5 py-0.5 text-xs font-semibold text-[#8B7CF6] border border-[#8B7CF6]/20">
              Phân cấp Y văn 5 Tầng
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">{copy.selectHint}</p>
        </div>

        <span className="rounded-xl bg-[#F8FAFD] px-3 py-1.5 text-xs font-medium text-[#48566A] border border-[#E3E8EF]">
          5 Nguồn y khoa tích hợp
        </span>
      </div>

      {/* Grid: Source List (Left) + Inspector (Right) */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Source Selector Rail */}
        <div className="lg:col-span-6 space-y-2.5" role="list">
          {V6_DEMO_SOURCES.map((source) => {
            const isSelected = selectedSource.id === source.id;
            return (
              <button
                key={source.id}
                type="button"
                role="listitem"
                onClick={() => setSelectedSource(source)}
                className={`w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring ${
                  isSelected
                    ? "bg-[#F5F3FF] border-[#8B7CF6] shadow-sm -translate-y-0.5"
                    : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7]"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[#162033]">{source.name}</span>
                    <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold text-[#8B7CF6] border border-[#8B7CF6]/20">
                      {source.authorityLevel}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#6D7A8E] mt-1">{source.authority}</p>
                </div>
                <span className="text-xs font-bold text-[#8B7CF6] shrink-0">
                  {isSelected ? "● Đang xem" : "Xem ➔"}
                </span>
              </button>
            );
          })}
        </div>

        {/* Selected Source Inspector */}
        <div className="lg:col-span-6 rounded-2xl bg-[#F8FAFD] p-6 border border-[#E3E8EF] space-y-4">
          <div className="border-b border-[#E3E8EF] pb-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#8B7CF6]">
              {copy.inspector.authorityLevel}: {selectedSource.authorityLevel}
            </span>
            <h4 className="text-base font-bold text-[#162033] mt-0.5">{selectedSource.name}</h4>
            <p className="text-xs text-[#6D7A8E]">{selectedSource.type} • {selectedSource.authority}</p>
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF]">
              <span className="font-bold text-[#162033] block mb-1">
                {copy.inspector.relevance}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.relevanceVi : selectedSource.relevanceEn}
              </p>
            </div>

            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF]">
              <span className="font-bold text-[#162033] block mb-1">
                {copy.inspector.applicability}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.applicabilityVi : selectedSource.applicabilityEn}
              </p>
            </div>

            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF]">
              <span className="font-bold text-amber-800 block mb-1">
                {copy.inspector.limitations}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.limitationsVi : selectedSource.limitationsEn}
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-[#E3E8EF] flex items-center justify-between text-[11px] text-[#6D7A8E]">
            <span>{copy.inspector.updated}: <strong className="text-[#162033]">{selectedSource.updated}</strong></span>
            <span className="text-[#8B7CF6] font-semibold">Tự động xác thực</span>
          </div>
        </div>
      </div>
    </div>
  );
}
