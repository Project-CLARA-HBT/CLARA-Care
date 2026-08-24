"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";

export function TrustScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].trust;

  return (
    <LandingScene id="trust" scale="transition" tone="canvas" className="border-y border-[#E3E8EF]/60">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-8">
        {/* Left: Concise Trust Headline */}
        <div className="max-w-md">
          <span className="text-xs font-bold uppercase tracking-widest text-[#6D7A8E]">
            {copy.eyebrow}
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#162033] mt-1">
            {copy.title}
          </h2>
          <p className="text-sm text-[#48566A] mt-2 leading-relaxed">
            {copy.description}
          </p>
        </div>

        {/* Right: Restrained Verified Source Rail (No auto-marquee / No flashy carousel) */}
        <div className="flex-1 max-w-2xl">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {copy.sources.map((src) => (
              <div
                key={src.name}
                className="flex flex-col justify-center rounded-2xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs text-left"
              >
                <span className="font-bold text-xs text-[#162033]">{src.name}</span>
                <span className="text-[10px] text-[#6D7A8E] mt-0.5 line-clamp-1">{src.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </LandingScene>
  );
}
