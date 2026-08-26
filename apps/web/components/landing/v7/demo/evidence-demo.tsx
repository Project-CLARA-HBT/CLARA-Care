"use client";

import React, { useState, useMemo } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_SOURCES, type V7DemoSource } from "../landing-data-v7";
import { SourceLens, type AuthorityTier } from "../artwork/source-lens";

export interface EvidenceDemoProps {
  className?: string;
  initialSourceId?: string;
}

/**
 * EvidenceDemo (Landing v7)
 *
 * Living Evidence Hub & 5-Tier Hierarchy Demonstration Component:
 * 1. 5-Tier Evidence Hierarchy Table/Rail:
 *    - Tier I: National Pharmacopoeia (DAV - Dược thư Quốc gia Việt Nam)
 *    - Tier II: International Pharmacology (DrugBank 5.1 Comprehensive)
 *    - Tier III: Global Practice Guidelines (WHO Guidelines for Essential Medicines)
 *    - Tier IV / Regulatory: Sentinel Pharmacovigilance Alerts (FDA Safety Communications)
 *    - Tier V / Peer-Reviewed: Clinical RCTs & Meta-Analyses (PubMed / MEDLINE)
 * 2. Bidirectional synchronization with SourceLens optical aperture artwork.
 * 3. Detailed Source Inspector with FIDES Grounding Status, Relevance Rationale,
 *    Clinical Applicability bounds, Identified Limitations, and Raw Citation Verification.
 */
export function EvidenceDemo({ className = "", initialSourceId }: EvidenceDemoProps) {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.evidence ?? LANDING_COPY_V7.vi.evidence;

  const [selectedSource, setSelectedSource] = useState<V7DemoSource>(() => {
    if (initialSourceId) {
      const match = V7_DEMO_SOURCES.find((s) => s.id === initialSourceId);
      if (match) return match;
    }
    return V7_DEMO_SOURCES[0];
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [showCitationDetails, setShowCitationDetails] = useState(false);

  const getTierBadgeTokens = (source: V7DemoSource) => {
    switch (source.id) {
      case "dav-national":
        return {
          rank: "Tier I",
          label: lang === "vi" ? "Tier I: Quốc gia" : "Tier I: National",
          pillClass: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/25",
          accentColor: "#0B6FD8",
          weightScore: "1.000 α",
          authorityType: lang === "vi" ? "Quy chuẩn Pháp lý Bắt buộc" : "Mandatory Regulatory Standard",
        };
      case "drugbank-51":
        return {
          rank: "Tier II",
          label: lang === "vi" ? "Tier II: Quốc tế" : "Tier II: International",
          pillClass: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/25",
          accentColor: "#8B7CF6",
          weightScore: "0.985 β",
          authorityType: lang === "vi" ? "Dược lý & Chuyển hóa CYP450" : "Molecular Pharmacology & DDI",
        };
      case "who-guidelines":
        return {
          rank: "Tier III",
          label: lang === "vi" ? "Tier II: Quốc tế" : "Tier II: International",
          pillClass: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/25",
          accentColor: "#14A88D",
          weightScore: "0.990 γ",
          authorityType: lang === "vi" ? "Hướng dẫn Điều trị Toàn cầu" : "Global Clinical Guidelines",
        };
      case "fda-alerts":
        return {
          rank: "Tier IV",
          label: lang === "vi" ? "Tier III: Quản lý Dược" : "Tier III: Regulatory",
          pillClass: "bg-amber-50 text-amber-700 border-amber-200",
          accentColor: "#D97706",
          weightScore: "0.992 δ",
          authorityType: lang === "vi" ? "Cảnh báo An toàn Thời gian thực" : "Real-Time Pharmacovigilance",
        };
      case "pubmed-rct":
      default:
        return {
          rank: "Tier V",
          label: lang === "vi" ? "Tier IV: Bình duyệt RCT" : "Tier IV: Peer-Reviewed",
          pillClass: "bg-sky-50 text-sky-700 border-sky-200",
          accentColor: "#0284C7",
          weightScore: "0.978 ε",
          authorityType: lang === "vi" ? "Thử nghiệm Mù đôi Ngẫu nhiên" : "Randomized Controlled Trials",
        };
    }
  };

  const filteredSources = useMemo(() => {
    if (!searchQuery.trim()) return V7_DEMO_SOURCES;
    const q = searchQuery.toLowerCase();
    return V7_DEMO_SOURCES.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.authority.toLowerCase().includes(q) ||
        s.type.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const handleSelectTierFromLens = (tier: AuthorityTier) => {
    const match = V7_DEMO_SOURCES.find((s) => s.authorityLevel === tier);
    if (match) setSelectedSource(match);
  };

  const selectedBadgeTokens = getTierBadgeTokens(selectedSource);

  return (
    <div
      data-testid="evidence-demo"
      className={`clara-product-surface relative w-full overflow-hidden p-5 sm:p-7 lg:p-9 transition-all duration-300 shadow-xl ${className}`}
    >
      {/* Evidence Hub Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg sm:text-xl font-bold text-[#162033]">
              Living Evidence Hub
            </h3>
            <span className="rounded-full bg-[#F5F3FF] px-2.5 py-0.5 text-xs font-semibold text-[#8B7CF6] border border-[#8B7CF6]/20">
              {lang === "vi" ? "Phân cấp Y văn 5 Tầng" : "5-Tier Evidence Hierarchy"}
            </span>
            <span className="rounded-full bg-[#ECFDF8] px-2 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/20">
              FIDES Verified
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#6D7A8E] mt-0.5">{copy.selectHint}</p>
        </div>

        {/* Search & Source Count Counter */}
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={lang === "vi" ? "Tìm nguồn y văn..." : "Filter sources..."}
              className="rounded-xl border border-[#E3E8EF] bg-white px-3 py-1.5 text-xs text-[#162033] placeholder-[#94A3B8] focus:border-[#8B7CF6] focus:outline-none w-36 sm:w-44 transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1.5 text-xs text-[#94A3B8] hover:text-[#162033]"
              >
                ✕
              </button>
            )}
          </div>
          <span className="rounded-xl bg-[#F8FAFD] px-3 py-1.5 text-xs font-medium text-[#48566A] border border-[#E3E8EF] shrink-0">
            {lang === "vi" ? "5 Nguồn chính thống" : "5 Verified Sources"}
          </span>
        </div>
      </div>

      {/* Grid: 5-Tier Evidence Hierarchy Rail (Left) + Selected Source Inspector & SourceLens (Right) */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* 5-Tier Source Selector Rail (Left Column) */}
        <div
          className="lg:col-span-6 space-y-3"
          role="tablist"
          aria-label={lang === "vi" ? "Danh sách nguồn y văn phân cấp" : "Hierarchical Evidence Source List"}
        >
          {filteredSources.map((source, index) => {
            const isSelected = selectedSource.id === source.id;
            const badgeTokens = getTierBadgeTokens(source);

            return (
              <button
                key={source.id}
                type="button"
                role="tab"
                id={`evidence-source-tab-${source.id}`}
                aria-selected={isSelected}
                aria-controls={`evidence-inspector-panel-${source.id}`}
                onClick={() => setSelectedSource(source)}
                className={`w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring cursor-pointer shadow-2xs ${
                  isSelected
                    ? "bg-[#F5F3FF]/80 border-[#8B7CF6] shadow-sm -translate-y-0.5 ring-2 ring-[#8B7CF6]/25"
                    : "bg-white border-[#E3E8EF] hover:border-[#CBD5E1] hover:bg-[#F8FAFD]"
                }`}
              >
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-md text-[10px] font-black text-white" style={{ backgroundColor: badgeTokens.accentColor }}>
                      0{index + 1}
                    </span>
                    <span className="text-xs sm:text-sm font-bold text-[#162033] tracking-tight">
                      {source.name}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold border ${badgeTokens.pillClass}`}
                    >
                      {badgeTokens.label}
                    </span>
                  </div>

                  <p className="text-xs text-[#6D7A8E]">{source.authority}</p>

                  <div className="flex flex-wrap items-center gap-2 pt-0.5 text-[11px]">
                    <span className="text-[#48566A] font-medium">{source.type}</span>
                    <span className="text-slate-300">•</span>
                    <span className="font-mono text-[#0B6FD8] font-semibold bg-[#EFF7FF] px-1.5 py-0.2 rounded text-[10px]">
                      Trọng số: {badgeTokens.weightScore}
                    </span>
                  </div>
                </div>

                <div className="shrink-0 flex flex-col items-end justify-between self-stretch pt-0.5">
                  <span
                    className="text-xs font-bold transition-colors"
                    style={{ color: isSelected ? badgeTokens.accentColor : "#8B7CF6" }}
                  >
                    {isSelected
                      ? lang === "vi"
                        ? "● Đang xem"
                        : "● Selected"
                      : lang === "vi"
                      ? "Xem ➔"
                      : "Inspect ➔"}
                  </span>
                  <span className="text-[10px] text-[#94A3B8] font-mono">
                    {source.updated}
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
          className="lg:col-span-6 rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] space-y-4 shadow-sm"
        >
          {/* Source Lens Integrated Artwork */}
          <SourceLens
            tier={selectedSource.authorityLevel}
            active={true}
            onSelectTier={handleSelectTierFromLens}
            className="mb-2 shadow-xs"
          />

          {/* Inspector Header */}
          <div className="border-b border-[#E3E8EF] pb-3.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#8B7CF6]">
                {copy.inspector.authorityLevel}: {selectedSource.authorityLevel} ({selectedBadgeTokens.weightScore})
              </span>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[10px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                FIDES Grounded ✓
              </span>
            </div>
            <h4 className="text-base sm:text-lg font-bold text-[#162033]">
              {selectedSource.name}
            </h4>
            <p className="text-xs text-[#6D7A8E]">
              {selectedSource.type} • {selectedSource.authority}
            </p>
          </div>

          {/* Structured Inspection Criteria */}
          <div className="space-y-3 text-xs">
            {/* Relevance Rationale */}
            <div className="rounded-xl bg-white p-3.5 sm:p-4 border border-[#E3E8EF] shadow-2xs space-y-1">
              <span className="font-bold text-[#162033] block">
                {copy.inspector.relevance}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {lang === "vi" ? selectedSource.relevanceVi : selectedSource.relevanceEn}
              </p>
            </div>

            {/* Clinical Applicability */}
            <div className="rounded-xl bg-white p-3.5 sm:p-4 border border-[#E3E8EF] shadow-2xs space-y-1">
              <span className="font-bold text-[#162033] block">
                {copy.inspector.applicability}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {lang === "vi" ? selectedSource.applicabilityVi : selectedSource.applicabilityEn}
              </p>
            </div>

            {/* Identified Limitations */}
            <div className="rounded-xl bg-white p-3.5 sm:p-4 border border-[#E3E8EF] shadow-2xs space-y-1">
              <span className="font-bold text-amber-800 block">
                {copy.inspector.limitations}:
              </span>
              <p className="text-[#48566A] leading-relaxed">
                {lang === "vi" ? selectedSource.limitationsVi : selectedSource.limitationsEn}
              </p>
            </div>
          </div>

          {/* Interactive Raw Citation Verification Drawer/Block */}
          {showCitationDetails ? (
            <div className="rounded-xl bg-slate-900 p-3.5 text-slate-100 text-xs space-y-2 animate-fadeIn font-mono">
              <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-700 pb-1.5">
                <span>FIDES CRYPTO WITNESS COORDINATES</span>
                <button
                  type="button"
                  onClick={() => setShowCitationDetails(false)}
                  className="text-slate-300 hover:text-white"
                >
                  ✕ Đóng
                </button>
              </div>
              <p className="text-[11px] text-emerald-400">
                AUTH_HASH: sha256:{selectedSource.id}-fides-v7-verified
              </p>
              <p className="text-[10px] text-slate-300">
                URI: https://data.clara.care/evidence/v7/{selectedSource.id}
              </p>
              <p className="text-[10px] text-slate-400">
                Cập nhật lần cuối: {selectedSource.updated} • Thẩm quyền: {selectedBadgeTokens.authorityType}
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowCitationDetails(true)}
              className="w-full rounded-xl bg-white p-2.5 border border-[#E3E8EF] text-center text-xs font-semibold text-[#8B7CF6] hover:bg-[#F5F3FF] transition-all cursor-pointer shadow-2xs"
            >
              {lang === "vi" ? "Tra cứu chứng chỉ xác thực FIDES ➔" : "Inspect FIDES Verification Coordinates ➔"}
            </button>
          )}

          {/* Verification & Metadata Footer */}
          <div className="pt-2 border-t border-[#E3E8EF] flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#6D7A8E]">
            <span>
              {copy.inspector.updated}: <strong className="text-[#162033]">{selectedSource.updated}</strong>
            </span>
            <span className="text-[#8B7CF6] font-semibold">
              {lang === "vi" ? "Tự động xác thực qua FIDES Engine" : "FIDES Verified Reference"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EvidenceDemo;
