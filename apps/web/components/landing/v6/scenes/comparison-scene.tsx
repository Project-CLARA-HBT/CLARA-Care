"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function ComparisonScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];
  const compCopy = copy.comparison;

  return (
    <LandingScene id="comparison" scale="standard" tone="canvas">
      <SceneHeader
        eyebrow={copy.comparison.eyebrow}
        title={copy.comparison.title}
        description={copy.comparison.description}
        align="center"
        tone="azure"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch max-w-6xl mx-auto">
        {/* Left: Generic Chatbot Column (5 cols on Desktop) */}
        <div className="lg:col-span-5 rounded-3xl bg-white border border-[#E3E8EF] p-6 sm:p-8 flex flex-col justify-between shadow-sm">
          <div>
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-6">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {language === "vi" ? "Tiếp cận thông thường" : "Standard Approach"}
                </span>
                <h3 className="text-lg sm:text-xl font-bold text-[#162033] mt-0.5">
                  {compCopy.genericAi.title}
                </h3>
              </div>
              <span className="rounded-full bg-[#F1F5F9] px-2.5 py-1 text-[11px] font-semibold text-[#6D7A8E] border border-[#E3E8EF]">
                3 {language === "vi" ? "bước rời rạc" : "unverified steps"}
              </span>
            </div>

            {/* Pipeline Flow: Question -> Guess next token -> Output */}
            <div className="space-y-2.5" role="list">
              {compCopy.genericAi.flow.map((step, idx) => {
                const isLast = idx === compCopy.genericAi.flow.length - 1;
                return (
                  <React.Fragment key={idx}>
                    <div
                      role="listitem"
                      className={`flex items-center gap-3.5 rounded-2xl p-3.5 border transition-all ${
                        isLast
                          ? "bg-[#FFF8F8] border-[#FECDD3]/80 text-[#991B1B]"
                          : "bg-[#F8FAFD] border-[#E3E8EF] text-[#48566A]"
                      }`}
                    >
                      <span
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-xl text-xs font-bold font-mono ${
                          isLast
                            ? "bg-[#FFE4E6] text-[#E11D48]"
                            : "bg-[#E3E8EF] text-[#6D7A8E]"
                        }`}
                      >
                        0{idx + 1}
                      </span>
                      <span
                        className={`text-xs sm:text-sm font-semibold flex-1 ${
                          isLast ? "text-[#991B1B]" : "text-[#162033]"
                        }`}
                      >
                        {step}
                      </span>
                      {isLast && (
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#E11D48] bg-[#FFE4E6] px-2 py-0.5 rounded-md">
                          {language === "vi" ? "Chưa kiểm chứng" : "Unverified"}
                        </span>
                      )}
                    </div>

                    {!isLast && (
                      <div className="flex justify-center py-0.5">
                        <span className="text-xs font-bold text-[#CBD5E1]">↓</span>
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Drawback Warning Box */}
          <div className="mt-8 rounded-2xl bg-[#FEF2F2] p-4 border border-[#FCA5A5]/40 flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#FEE2E2] text-xs font-bold text-[#991B1B]">
              ⚠
            </span>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#991B1B]">
                {language === "vi" ? "Hạn chế y khoa" : "Medical Risk & Limitations"}
              </span>
              <p className="text-xs sm:text-sm text-[#7F1D1D] mt-1 leading-relaxed font-normal">
                {compCopy.genericAi.drawback}
              </p>
            </div>
          </div>
        </div>

        {/* Right: CLARA Multi-Tier Safety Pipeline Column (7 cols on Desktop) */}
        <div className="lg:col-span-7 clara-product-surface rounded-3xl bg-white border-2 border-[#0B6FD8]/30 p-6 sm:p-8 flex flex-col justify-between shadow-xl relative overflow-hidden">
          {/* Subtle Ambient Background Highlight */}
          <div
            aria-hidden="true"
            className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-[#EFF7FF] via-[#ECFDF8]/40 to-transparent rounded-full -mr-20 -mt-20 pointer-events-none"
          />

          <div className="relative z-10">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-6">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                  {language === "vi" ? "Kiến trúc Suy luận An toàn" : "Multi-Tier Reasoning Architecture"}
                </span>
                <h3 className="text-lg sm:text-xl font-bold text-[#162033] mt-0.5">
                  {compCopy.claraCare.title}
                </h3>
              </div>
              <span className="rounded-full bg-[#ECFDF8] px-3 py-1 text-xs font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-xs">
                ✦ {language === "vi" ? "7 tầng an toàn" : "7 safety tiers"}
              </span>
            </div>

            {/* Pipeline Flow: Question -> Context -> Evidence -> FIDES -> Boundaries -> Next action -> LifeMap */}
            <div className="space-y-2" role="list">
              {compCopy.claraCare.flow.map((step, idx) => {
                const isFides = idx === 3; // FIDES verification step
                const isLifeMap = idx === 6; // LifeMap step
                return (
                  <div
                    key={idx}
                    role="listitem"
                    className={`flex items-center gap-3.5 rounded-2xl p-3 border transition-all ${
                      isFides
                        ? "bg-[#EFF7FF] border-[#0B6FD8]/40 shadow-xs"
                        : isLifeMap
                        ? "bg-[#ECFDF8] border-[#14A88D]/30"
                        : "bg-[#F8FAFD] border-[#E3E8EF] hover:border-[#D5DDE7]"
                    }`}
                  >
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-xl text-xs font-bold font-mono ${
                        isFides
                          ? "bg-[#0B6FD8] text-white shadow-xs"
                          : isLifeMap
                          ? "bg-[#14A88D] text-white shadow-xs"
                          : "bg-white text-[#0B6FD8] border border-[#0B6FD8]/20"
                      }`}
                    >
                      0{idx + 1}
                    </span>

                    <div className="flex-1 min-w-0">
                      <span className="text-xs sm:text-sm font-bold text-[#162033] block truncate">
                        {step}
                      </span>
                    </div>

                    {isFides && (
                      <span className="text-[10px] font-bold text-[#0B6FD8] bg-white border border-[#0B6FD8]/20 px-2 py-0.5 rounded-md shrink-0">
                        FIDES Check
                      </span>
                    )}

                    {isLifeMap && (
                      <span className="text-[10px] font-bold text-[#14A88D] bg-white border border-[#14A88D]/20 px-2 py-0.5 rounded-md shrink-0">
                        LifeMap
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Benefit Box */}
          <div className="relative z-10 mt-8 rounded-2xl bg-[#ECFDF8] p-4 border border-[#14A88D]/30 flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#D1FAE5] text-xs font-bold text-[#0E856F]">
              ✓
            </span>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#0E856F]">
                {language === "vi" ? "Bảo chứng an toàn y tế" : "Clinical Safety Guarantee"}
              </span>
              <p className="text-xs sm:text-sm text-[#064E3B] mt-1 leading-relaxed font-medium">
                {compCopy.claraCare.benefit}
              </p>
            </div>
          </div>
        </div>
      </div>
    </LandingScene>
  );
}
