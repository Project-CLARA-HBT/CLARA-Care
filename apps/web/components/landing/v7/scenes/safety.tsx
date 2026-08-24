"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function SafetyScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.safety ?? LANDING_COPY_V7.vi.safety;

  return (
    <LandingScene id="safety" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="azure"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8 max-w-6xl mx-auto">
        {copy.principles.map((principle) => (
          <div
            key={principle.number}
            className="rounded-3xl bg-white p-6 sm:p-8 border border-[#E3E8EF] shadow-xs hover:border-[#0B6FD8]/30 hover:shadow-md transition-all text-left flex flex-col justify-between"
          >
            <div>
              <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[#EFF7FF] text-[#0B6FD8] font-mono text-sm font-bold border border-[#0B6FD8]/20 mb-5">
                {principle.number}
              </span>
              <h3 className="text-xl font-bold text-[#162033] tracking-tight">
                {principle.title}
              </h3>
              <p className="text-sm sm:text-base text-[#48566A] mt-3 leading-relaxed">
                {principle.description}
              </p>
            </div>
            <div className="pt-5 mt-5 border-t border-[#E3E8EF]/70 flex items-center gap-2 text-xs font-semibold text-[#0B6FD8]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
              <span>{lang === "vi" ? "Bất biến kỹ thuật" : "Engineered Invariant"}</span>
            </div>
          </div>
        ))}
      </div>
    </LandingScene>
  );
}

export default SafetyScene;
