"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_SOURCES, type V7DemoSource } from "../landing-data-v7";
import { SourceLens, type AuthorityTier } from "../artwork/source-lens";

export function EvidenceDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V7[language].evidence;
  const [selectedSource, setSelectedSource] = useState<V7DemoSource>(V7_DEMO_SOURCES[0]);

  const getTierBadgeTokens = (tier: V7DemoSource["authorityLevel"]) => {
    switch (tier) {
      case "National":
        return {
          label: language === "vi" ? "Tier I: Quốc gia" : "Tier I: National",
          pillClass: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/25",
          accentColor: "#0B6FD8",
        };
      case "International":
        return {
          label: language === "vi" ? "Tier II: Quốc tế" : "Tier II: International",
          pillClass: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/25",
          accentColor: "#8B7CF6",
        };
      case "Regulatory":
        return {
          label: language === "vi" ? "Tier III: Quản lý Dược" : "Tier III: Regulatory",
          pillClass: "bg-amber-50 text-amber-700 border-amber-200",
          accentColor: "#D97706",
        };
      case "Peer-Reviewed":
        return {
          label: language === "vi" ? "Tier IV: Bình duyệt RCT" : "Tier IV: Peer-Reviewed",
          pillClass: "bg-sky-50 text-sky-700 border-sky-200",
          accentColor: "#0284C7",
        };
    }
  };

  const handleSelectTierFromLens = (tier: AuthorityTier) => {
    const match = V7_DEMO_SOURCES.find((s) => s.authorityLevel === tier);
    if (match) setSelectedSource(match);
  };

  return (
    <div
      data-testid="evidence-demo"
      className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10 transition-all duration-300"
    >
      {/* Evidence Hub Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">
              {language === "vi" ? "Living Evidence Hub" : "Living Evidence Hub"}
            </h3>
            <span className="rounded-full bg-[#F5F3FF] px-2.5 py-0.5 text-xs font-semibold text-[#8B7CF6] border border-[#8B7CF6]/20">
              {language === "vi" ? "Phân cấp Y văn 5 Tầng" : "5-Tier Evidence Hierarchy"}
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">{copy.selectHint}</p>
        </div>

        <span className="rounded-xl bg-[#F8FAFD] px-3 py-1.5 text-xs font-medium text-[#48566A] border border-[#E3E8EF]">
          {language === "vi" ? "5 Nguồn y khoa tích hợp" : "5 Integrated Authoritative Sources"}
        </span>
      </div>

      {/* Grid: 5-Tier Evidence Hierarchy Rail (Left) + Selected Source Inspector (Right) */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Source Selector Rail (Left Column) */}
        <div
          className="lg:col-span-6 space-y-2.5"
          role="tablist"
          aria-label={language === "vi" ? "Danh sách nguồn y văn phân cấp" : "Hierarchical Evidence Source List"}
        >
          {V7_DEMO_SOURCES.map((source) => {
            const isSelected = selectedSource.id === source.id;
            const badgeTokens = getTierBadgeTokens(source.authorityLevel);

            return (
              <button
                key={source.id}
                type="button"
                role="tab"
                id={`evidence-source-tab-${source.id}`}
                aria-selected={isSelected}
                aria-controls={`evidence-inspector-panel-${source.id}`}
                onClick={() => setSelectedSource(source)}
                className={`w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring ${
                  isSelected
                    ? "bg-[#F5F3FF] border-[#8B7CF6] shadow-sm -translate-y-0.5 ring-1 ring-[#8B7CF6]/30"
                    : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD]"
                }`}
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-[#162033] tracking-tight">{source.name}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold border ${badgeTokens.pillClass}`}
                    >
                      {badgeTokens.label}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#6D7A8E]">{source.authority}</p>
                  <p className="text-[11px] text-[#48566A] font-medium pt-0.5 line-clamp-1">{source.type}</p>
                </div>

                <div className="shrink-0 flex items-center pt-1">
                  <span
                    className="text-xs font-bold transition-colors"
                    style={{ color: isSelected ? badgeTokens.accentColor : "#8B7CF6" }}
                  >
                    {isSelected
                      ? language === "vi"
                        ? "● Đang xem"
                        : "● Selected"
                      : language === "vi"
                      ? "Xem ➔"
                      : "Inspect ➔"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Source Inspector & Optical Lens (Right Column) */}
        <div
          id={`evidence-inspector-panel-${selectedSource.id}`}
          role="tabpanel"
          aria-labelledby={`evidence-source-tab-${selectedSource.id}`}
          className="lg:col-span-6 rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] space-y-4"
        >
          {/* Source Lens Integrated Artwork */}
          <SourceLens
            tier={selectedSource.authorityLevel}
            active={true}
            onSelectTier={handleSelectTierFromLens}
            className="mb-2"
          />

          {/* Inspector Header */}
          <div className="border-b border-[#E3E8EF] pb-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#8B7CF6]">
                {copy.inspector.authorityLevel}: {selectedSource.authorityLevel}
              </span>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20 shadow-xs">
                FIDES Grounded
              </span>
            </div>
            <h4 className="text-base font-bold text-[#162033] mt-1">{selectedSource.name}</h4>
            <p className="text-xs text-[#6D7A8E]">
              {selectedSource.type} • {selectedSource.authority}
            </p>
          </div>

          {/* Structured Inspection Criteria */}
          <div className="space-y-3 text-xs">
            {/* Relevance Rationale */}
            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1">
              <span className="font-bold text-[#162033] block">
                {copy.inspector.relevance}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.relevanceVi : selectedSource.relevanceEn}
              </p>
            </div>

            {/* Clinical Applicability */}
            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1">
              <span className="font-bold text-[#162033] block">
                {copy.inspector.applicability}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.applicabilityVi : selectedSource.applicabilityEn}
              </p>
            </div>

            {/* Identified Limitations */}
            <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1">
              <span className="font-bold text-amber-800 block">
                {copy.inspector.limitations}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {language === "vi" ? selectedSource.limitationsVi : selectedSource.limitationsEn}
              </p>
            </div>
          </div>

          {/* Verification & Metadata Footer */}
          <div className="pt-2 border-t border-[#E3E8EF] flex items-center justify-between text-[11px] text-[#6D7A8E]">
            <span>
              {copy.inspector.updated}: <strong className="text-[#162033]">{selectedSource.updated}</strong>
            </span>
            <span className="text-[#8B7CF6] font-semibold">
              {language === "vi" ? "Tự động xác thực qua FIDES" : "FIDES Verified Reference"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EvidenceDemo;
