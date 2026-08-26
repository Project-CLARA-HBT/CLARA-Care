"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";

/**
 * TrustScene (Verified Source Rail Transition)
 *
 * Highlights authoritative medical databases with:
 * - Verified source rail of clinical repositories (WHO, PubMed, FDA, DrugBank, DAV, EMA, PubChem)
 * - Verified authority badges and clear institutional metadata
 * - Continuous EvidenceRibbon transition handoff bridging across upstream and downstream scenes
 */
export function TrustScene() {
  const { language, isReducedMotion } = useMotionTier();
  const copy = LANDING_COPY_V7[language]?.trust ?? LANDING_COPY_V7.vi.trust;
  const isVi = language !== "en";

  const verifiedBadgeLabel = isVi ? "Bảo chứng y khoa" : "Verified Authority";
  const tierMap: Record<string, string> = {
    WHO: isVi ? "Chuẩn Toàn cầu" : "Global Standard",
    "PubMed / MEDLINE": isVi ? "Y văn Bình duyệt" : "Peer-Reviewed",
    FDA: isVi ? "Cơ quan Quản lý" : "Regulatory",
    "DrugBank 5.1": isVi ? "Dược lý Phân tử" : "Molecular DB",
    EMA: isVi ? "Tiêu chuẩn Châu Âu" : "EU Standards",
    DAV: isVi ? "Dược thư Quốc gia" : "National Tier I",
    PubChem: isVi ? "Cấu trúc Hóa sinh" : "Biochemical DB",
  };

  return (
    <LandingScene
      id="trust"
      scale="transition"
      tone="canvas"
      className="py-16 sm:py-24 border-y border-[#E3E8EF]/60 clara-transition-sponsors-trust relative overflow-hidden"
    >
      {/* EvidenceRibbon Top Handoff Bridge Across Rail */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-14 opacity-40"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={!isReducedMotion} className="w-full max-w-6xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Left Column (5 cols): Editorial Trust Headline & Statement */}
          <div className="lg:col-span-5 text-left space-y-4">
            <RevealGroup staggerMs={80}>
              <Reveal delayMs={0} direction="up">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#EFF7FF] px-3.5 py-1 text-xs font-bold uppercase tracking-widest text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>{copy.eyebrow}</span>
                </div>
              </Reveal>

              <Reveal delayMs={80} direction="up">
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#162033] leading-tight">
                  {copy.title}
                </h2>
              </Reveal>

              <Reveal delayMs={160} direction="up">
                <p className="text-sm sm:text-base text-[#48566A] leading-relaxed">
                  {copy.description}
                </p>
              </Reveal>

              <Reveal delayMs={240} direction="up">
                <div className="pt-2 flex flex-wrap items-center gap-3 text-xs text-[#6D7A8E]">
                  <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3 py-1.5 border border-[#E3E8EF] shadow-2xs font-semibold text-[#162033]">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span>{isVi ? "100% Y văn có thẩm quyền" : "100% Authoritative Sources"}</span>
                  </div>
                  <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3 py-1.5 border border-[#E3E8EF] shadow-2xs font-semibold text-[#0B6FD8]">
                    <span>✦</span>
                    <span>{isVi ? "Kiểm chứng FIDES" : "FIDES Verified"}</span>
                  </div>
                </div>
              </Reveal>
            </RevealGroup>
          </div>

          {/* Right Column (7 cols): Verified Source Rail Cards Grid */}
          <div className="lg:col-span-7">
            <Reveal delayMs={120} direction="scale">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5 sm:gap-4">
                {copy.sources.map((src) => {
                  const tierTag = tierMap[src.name] || (isVi ? "Xác thực" : "Verified");

                  return (
                    <div
                      key={src.name}
                      className="group relative flex flex-col justify-between rounded-2xl bg-white p-4 border border-[#E3E8EF] shadow-xs text-left transition-all duration-300 hover:border-[#0B6FD8]/40 hover:shadow-md hover:-translate-y-1 overflow-hidden"
                    >
                      {/* Ambient corner hover glow */}
                      <div
                        aria-hidden="true"
                        className="absolute -top-8 -right-8 w-20 h-20 rounded-full bg-[#0B6FD8]/5 blur-lg group-hover:bg-[#0B6FD8]/15 transition-all duration-300 pointer-events-none"
                      />

                      <div className="space-y-2 relative z-10">
                        {/* Header: Name + Verified Authority Badge */}
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="font-bold text-sm text-[#162033] group-hover:text-[#0B6FD8] transition-colors truncate">
                            {src.name}
                          </span>
                          <span
                            className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700 border border-emerald-200/80 shrink-0"
                            title={verifiedBadgeLabel}
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            <span className="hidden sm:inline">✓</span>
                          </span>
                        </div>

                        {/* Source Type */}
                        <span className="text-[11px] text-[#6D7A8E] line-clamp-1 block font-medium">
                          {src.type}
                        </span>
                      </div>

                      {/* Footer: Authority & Tier Tag */}
                      <div className="mt-3 pt-2.5 border-t border-[#E3E8EF]/80 flex items-center justify-between gap-2 relative z-10">
                        {src.authority ? (
                          <span className="text-[10px] font-semibold text-[#0B6FD8] line-clamp-1">
                            {src.authority}
                          </span>
                        ) : (
                          <span className="text-[10px] text-[#6D7A8E]">{tierTag}</span>
                        )}
                        <span className="text-[9px] font-bold uppercase text-[#48566A] bg-[#F1F5F9] px-1.5 py-0.5 rounded border border-[#E3E8EF] shrink-0">
                          {tierTag}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Reveal>
          </div>
        </div>
      </div>

      {/* Bottom Transition Ribbon Towards Context Manifesto */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 right-1/4 w-80 opacity-45 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="iris" active={!isReducedMotion} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default TrustScene;

