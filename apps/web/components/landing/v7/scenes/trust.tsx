"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

export function TrustScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V7[language]?.trust ?? LANDING_COPY_V7.vi.trust;

  return (
    <LandingScene
      id="trust"
      scale="transition"
      tone="canvas"
      className="border-y border-[#E3E8EF]/60 relative overflow-hidden"
    >
      {/* EvidenceRibbon Background Handoff Across Rail */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-12 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-5xl" />
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-8 relative z-10">
        {/* Left: Concise Trust Headline */}
        <div className="max-w-md text-left">
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

        {/* Right: Restrained Verified Source Rail */}
        <div className="flex-1 max-w-2xl">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {copy.sources.map((src) => (
              <div
                key={src.name}
                className="flex flex-col justify-between rounded-2xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs text-left transition-all hover:border-[#0B6FD8]/40 hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-bold text-xs text-[#162033]">{src.name}</span>
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" title="Verified source" />
                  </div>
                  <span className="text-[10px] text-[#6D7A8E] line-clamp-1 block">{src.type}</span>
                </div>
                {src.authority && (
                  <span className="text-[9px] font-semibold text-[#0B6FD8] mt-2 block line-clamp-1">
                    {src.authority}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Transition Ribbon Towards Context Manifesto */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-6 right-1/4 w-72 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="iris" active={true} className="h-12 w-full" />
      </div>
    </LandingScene>
  );
}

export default TrustScene;
