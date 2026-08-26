"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { AmbientField } from "../primitives/ambient-field";
import { ScenarioPath } from "../artwork/scenario-path";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

const SCENARIO_METADATA = [
  {
    categoryVi: "Dược thư & Tương tác thuốc",
    categoryEn: "Pharmacology & DDI",
    badge: "FIDES Vetted",
    badgeTone: "azure" as const,
  },
  {
    categoryVi: "Chuẩn bị khám & LifeMap",
    categoryEn: "Clinical Prep & LifeMap",
    badge: "LifeMap Timeline",
    badgeTone: "mint" as const,
  },
  {
    categoryVi: "Sàng lọc & An toàn cấp cứu",
    categoryEn: "Triage & Emergency Safety",
    badge: "CareGuard Fast-Path",
    badgeTone: "azure" as const,
  },
  {
    categoryVi: "Dòng thời gian & Xu hướng",
    categoryEn: "Timeline & Longitudinal Insights",
    badge: "Longitudinal Trends",
    badgeTone: "mint" as const,
  },
];

/**
 * ScenariosScene (Landing v7)
 *
 * Human Everyday Scenario Moments:
 * - 4 Real-life clinical dialogue moments with alternating quotes & structured CLARA resolutions.
 * - Dynamic ScenarioPath SVG connectors bridging human questions to clinical answers.
 * - Category badges and FIDES / LifeMap / CareGuard validation indicators.
 */
export function ScenariosScene() {
  const { language, isReducedMotion } = useMotionTier();
  const copy = LANDING_COPY_V7[language]?.scenarios ?? LANDING_COPY_V7.vi.scenarios;
  const [activeCardIndex, setActiveCardIndex] = useState<number | null>(null);

  const contextLabel = language === "vi" ? "Bối cảnh:" : "Context:";
  const resolutionLabel = language === "vi" ? "Giải pháp từ CLARA" : "CLARA Resolution";

  return (
    <LandingScene
      id="scenarios"
      scale="standard"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Background Top Transition Ribbon (Handoff from Privacy scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="mint" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-12 md:mb-16 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          title={copy.title}
          description={copy.description}
          align="left"
          tone="azure"
          className="mb-0"
        />
      </div>

      {/* Main Scenarios List */}
      <div className="relative z-10 flex flex-col gap-8 max-w-5xl mx-auto px-2 sm:px-4">
        {copy.items.map((item, index) => {
          const isEven = index % 2 === 0;
          const meta = SCENARIO_METADATA[index] ?? SCENARIO_METADATA[0];
          const categoryText = language === "vi" ? meta.categoryVi : meta.categoryEn;
          const isActive = activeCardIndex === index;

          return (
            <div
              key={index}
              className={`w-full md:max-w-[90%] transition-all duration-300 ${
                isEven ? "md:self-start md:mr-auto" : "md:self-end md:ml-auto"
              }`}
              onMouseEnter={() => setActiveCardIndex(index)}
              onMouseLeave={() => setActiveCardIndex(null)}
              onFocus={() => setActiveCardIndex(index)}
              onBlur={() => setActiveCardIndex(null)}
            >
              <article
                className={`clara-product-surface bg-white border rounded-3xl p-6 sm:p-8 shadow-sm transition-all duration-300 ${
                  isActive
                    ? "border-[#0B6FD8]/50 shadow-lg ring-1 ring-[#0B6FD8]/20"
                    : "border-[#E3E8EF] hover:border-[#D5DDE7] hover:shadow-md"
                }`}
              >
                {/* Scenario Header: Index Number, Category & Safety Badge */}
                <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-[#EFF7FF] text-[#0B6FD8] text-xs font-bold font-mono border border-[#0B6FD8]/20">
                      0{index + 1}
                    </span>
                    <span className="text-xs font-bold uppercase tracking-wider text-[#6D7A8E]">
                      {categoryText}
                    </span>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-xs font-semibold border shadow-2xs ${
                      meta.badgeTone === "mint"
                        ? "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20"
                        : "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/20"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        meta.badgeTone === "mint" ? "bg-[#14A88D]" : "bg-[#0B6FD8]"
                      } ${isActive && !isReducedMotion ? "animate-pulse" : ""}`}
                    />
                    {meta.badge}
                  </span>
                </div>

                {/* Human Quote & Everyday Context */}
                <div className="relative pl-4 border-l-2 border-[#0B6FD8]">
                  <blockquote className="text-lg sm:text-xl font-bold text-[#162033] tracking-tight leading-snug">
                    “{item.quote}”
                  </blockquote>
                  <p className="text-sm text-[#48566A] mt-2.5 leading-relaxed">
                    <span className="font-semibold text-[#6D7A8E]">{contextLabel} </span>
                    {item.context}
                  </p>
                </div>

                {/* ScenarioPath Artwork Transition */}
                <div className="my-3 -mx-2 sm:mx-0 overflow-hidden">
                  <ScenarioPath
                    index={index}
                    active={isActive}
                    className="h-10 sm:h-12 w-full"
                  />
                </div>

                {/* CLARA Clinical Resolution */}
                <div className="pt-2 border-t border-[#E3E8EF]/80">
                  <div className="rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border border-[#E3E8EF] transition-colors duration-200">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex h-5 w-5 items-center justify-center rounded-lg bg-[#0B6FD8] text-white text-[11px] font-black shadow-2xs">
                        ✦
                      </div>
                      <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                        {resolutionLabel}
                      </span>
                    </div>
                    <p className="text-sm sm:text-base font-medium text-[#162033] leading-relaxed">
                      {item.resolution}
                    </p>
                  </div>
                </div>
              </article>
            </div>
          );
        })}
      </div>

      {/* Transition Ribbon Flowing toward Comparison Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default ScenariosScene;
