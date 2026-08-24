"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";

export function ClinicalTransitionScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].clinicalTransition;

  return (
    <LandingScene
      id="clinical-transition"
      scale="transition"
      tone="mint"
      className="bg-[#ECFDF8]/40 border-y border-[#14A88D]/15 overflow-hidden"
    >
      <div className="text-center max-w-3xl mx-auto py-4">
        <span className="text-xs font-bold uppercase tracking-widest text-[#14A88D]">
          {copy.eyebrow}
        </span>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#162033] leading-tight mt-3 whitespace-pre-line">
          {copy.headline}
        </h2>
        <p className="text-base sm:text-lg text-[#48566A] mt-4 max-w-2xl mx-auto leading-relaxed">
          {copy.subheadline}
        </p>
      </div>
    </LandingScene>
  );
}
