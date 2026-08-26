"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { AmbientField } from "../primitives/ambient-field";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

/**
 * ComparisonScene (Landing v7)
 *
 * Multi-Tier Safety & Architectural Comparison:
 * - Generic AI Chatbot (Ungrounded, direct unverified generation, no clinical constraints).
 * - CLARA Care Pipeline (7 Governed Multi-Agent Layers: Triage -> PHR Grounding -> RAG -> FIDES DDI Verification -> Synthesis -> LifeMap Commit).
 */
export function ComparisonScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.comparison ?? LANDING_COPY_V7.vi.comparison;

  const comparisonBadge =
    lang === "vi"
      ? "KIẾN TRÚC PHÂN TẦNG • FIDES VS GENERIC AI"
      : "GOVERNED ARCHITECTURE • FIDES VS GENERIC AI";

  return (
    <LandingScene
      id="comparison"
      scale="standard"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Background Top Transition Ribbon (Handoff from Scenarios scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-12 md:mb-16 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={comparisonBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="azure"
          className="mb-0"
        />
      </div>

      {/* Main Multi-Tier Comparison Grid */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch max-w-6xl mx-auto px-2 sm:px-4">
        {/* Left: Generic Chatbot Column (5 Cols) */}
        <div className="lg:col-span-5 rounded-3xl bg-white border border-[#E3E8EF] p-6 sm:p-8 flex flex-col justify-between shadow-xs text-left">
          <div>
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-6">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Tiếp cận thông thường" : "Standard Approach"}
                </span>
                <h3 className="text-lg sm:text-xl font-bold text-[#162033] mt-0.5">
                  {copy.genericAi.title}
                </h3>
              </div>
              <span className="rounded-full bg-[#F1F5F9] px-2.5 py-1 text-[11px] font-semibold text-[#6D7A8E] border border-[#E3E8EF]">
                3 {lang === "vi" ? "bước rời rạc" : "unverified steps"}
              </span>
            </div>

            <div className="space-y-2.5" role="list">
              {copy.genericAi.flow.map((step, idx) => {
                const isLast = idx === copy.genericAi.flow.length - 1;
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
                          {lang === "vi" ? "Chưa kiểm chứng" : "Unverified"}
                        </span>
                      )}
                    </div>

                    {!isLast && (
                      <div className="flex justify-center py-0.5" aria-hidden="true">
                        <span className="text-xs font-bold text-[#CBD5E1]">↓</span>
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          <div className="mt-8 rounded-2xl bg-[#FEF2F2] p-4 border border-[#FCA5A5]/40 flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#FEE2E2] text-xs font-bold text-[#991B1B]">
              ⚠
            </span>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#991B1B]">
                {lang === "vi" ? "Hạn chế y khoa" : "Medical Risk & Limitations"}
              </span>
              <p className="text-xs sm:text-sm text-[#7F1D1D] mt-1 leading-relaxed">
                {copy.genericAi.drawback}
              </p>
            </div>
          </div>
        </div>

        {/* Right: CLARA Care System Column (7 Cols) */}
        <div className="lg:col-span-7 rounded-3xl bg-white border-2 border-[#0B6FD8] p-6 sm:p-8 flex flex-col justify-between shadow-xl text-left relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[#0B6FD8]/5 rounded-bl-full pointer-events-none" />

          <div>
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-6">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                  {lang === "vi" ? "Kiến trúc Chuyên sâu" : "Dedicated Architecture"}
                </span>
                <h3 className="text-lg sm:text-xl font-bold text-[#162033] mt-0.5">
                  {copy.claraCare.title}
                </h3>
              </div>
              <span className="rounded-full bg-[#EFF7FF] px-2.5 py-1 text-[11px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                7 {lang === "vi" ? "tầng kiểm soát" : "governed layers"}
              </span>
            </div>

            <div className="space-y-2.5" role="list">
              {copy.claraCare.flow.map((step, idx) => (
                <div
                  key={idx}
                  role="listitem"
                  className="flex items-center gap-3.5 rounded-2xl p-3 bg-[#F8FAFD] border border-[#E3E8EF] hover:border-[#0B6FD8]/30 transition-colors"
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[#EFF7FF] text-[#0B6FD8] text-xs font-bold font-mono border border-[#0B6FD8]/20">
                    0{idx + 1}
                  </span>
                  <span className="text-xs sm:text-sm font-bold text-[#162033] flex-1">
                    {step}
                  </span>
                  {idx === 3 && (
                    <span className="text-[10px] font-bold text-[#0B6FD8] bg-[#EFF7FF] px-2 py-0.5 rounded-md border border-[#0B6FD8]/20">
                      FIDES Check
                    </span>
                  )}
                  {idx === 6 && (
                    <span className="text-[10px] font-bold text-[#14A88D] bg-[#ECFDF8] px-2 py-0.5 rounded-md border border-[#14A88D]/20">
                      LifeMap
                    </span>
                  )}
                  <span className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 rounded-2xl bg-[#ECFDF8] p-4 border border-[#14A88D]/25 flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-xs font-bold text-[#14A88D]">
              ✦
            </span>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#14A88D]">
                {lang === "vi" ? "Bảo chứng Lâm sàng" : "Clinical Assurance"}
              </span>
              <p className="text-xs sm:text-sm text-[#065F46] mt-1 leading-relaxed">
                {copy.claraCare.benefit}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Transition Ribbon Flowing toward FAQ Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default ComparisonScene;
