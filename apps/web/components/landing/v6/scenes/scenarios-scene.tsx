"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function ScenariosScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];

  const scenarioMeta = [
    {
      category: language === "vi" ? "Dược thư & Tương tác thuốc" : "Pharmacology & DDI",
      badge: "FIDES Vetted",
    },
    {
      category: language === "vi" ? "Chuẩn bị khám & LifeMap" : "Clinical Prep & LifeMap",
      badge: "LifeMap Timeline",
    },
    {
      category: language === "vi" ? "Sàng lọc & An toàn cấp cứu" : "Triage & Emergency Safety",
      badge: "CareGuard Fast-Path",
    },
    {
      category: language === "vi" ? "Dòng thời gian & Xu hướng" : "Timeline & Longitudinal Insights",
      badge: "Longitudinal Trends",
    },
  ];

  return (
    <LandingScene id="scenarios" scale="standard" tone="canvas">
      <SceneHeader
        eyebrow={copy.scenarios.eyebrow}
        title={copy.scenarios.title}
        description={copy.scenarios.description}
        align="left"
        tone="azure"
      />

      <div className="flex flex-col gap-6 sm:gap-8 max-w-5xl mx-auto">
        {copy.scenarios.items.map((item, index) => {
          const isEven = index % 2 === 0;
          const meta = scenarioMeta[index] || {
            category: language === "vi" ? "Tình huống thực tế" : "Real-world Scenario",
            badge: "CLARA Verified",
          };

          return (
            <div
              key={index}
              className={`w-full md:max-w-[88%] transition-all ${
                isEven ? "md:self-start md:mr-auto" : "md:self-end md:ml-auto"
              }`}
            >
              <article className="clara-product-surface bg-white border border-[#E3E8EF] rounded-3xl p-6 sm:p-8 shadow-sm transition-all duration-200 hover:shadow-md hover:border-[#D5DDE7]">
                {/* Scenario Header: Index & Badge */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#EFF7FF] text-[#0B6FD8] text-xs font-bold">
                      {index + 1}
                    </span>
                    <span className="text-xs font-bold uppercase tracking-wider text-[#6D7A8E]">
                      {meta.category}
                    </span>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
                    {meta.badge}
                  </span>
                </div>

                {/* Human Quote & Context */}
                <div className="relative pl-4 border-l-2 border-[#0B6FD8]">
                  <blockquote className="text-lg sm:text-xl font-bold text-[#162033] tracking-tight leading-snug">
                    “{item.quote}”
                  </blockquote>
                  <p className="text-sm text-[#48566A] mt-2 leading-relaxed">
                    <span className="font-semibold text-[#6D7A8E]">
                      {language === "vi" ? "Bối cảnh:" : "Context:"}{" "}
                    </span>
                    {item.context}
                  </p>
                </div>

                {/* Clear CLARA Resolution Underneath */}
                <div className="mt-5 pt-4 border-t border-[#E3E8EF]/80">
                  <div className="rounded-2xl bg-[#F8FAFD] p-4 sm:p-5 border border-[#E3E8EF]">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex h-5 w-5 items-center justify-center rounded-lg bg-[#0B6FD8] text-white text-[10px] font-black">
                        ✦
                      </div>
                      <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                        {language === "vi" ? "Giải pháp từ CLARA" : "CLARA Resolution"}
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
    </LandingScene>
  );
}
