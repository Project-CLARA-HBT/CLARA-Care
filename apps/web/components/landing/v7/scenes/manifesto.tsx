"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { ContextConstellation } from "../artwork/context-constellation";

export function ManifestoScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.manifesto ?? LANDING_COPY_V7.vi.manifesto;
  const [activeNode, setActiveNode] = useState<string>("clara-core");

  return (
    <LandingScene id="manifesto" scale="signature" tone="azure" className="overflow-hidden">
      <div className="text-center max-w-4xl mx-auto mb-10">
        <span className="text-xs font-bold uppercase tracking-widest text-[#0B6FD8]">
          {copy.eyebrow}
        </span>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#162033] leading-tight mt-2 whitespace-pre-line">
          {copy.headline}
        </h2>
        <p className="text-base sm:text-lg text-[#48566A] mt-4 max-w-2xl mx-auto leading-relaxed">
          {copy.subheadline}
        </p>
      </div>

      {/* Spatial Constellation Canvas */}
      <div className="relative mx-auto max-w-5xl">
        <ContextConstellation
          language={lang}
          activeNodeId={activeNode}
          onNodeClick={(id) => setActiveNode(id)}
        />
      </div>

      {/* Resolving Statement */}
      <div className="text-center mt-12">
        <div className="inline-flex items-center gap-2 rounded-2xl bg-[#EFF7FF] px-6 py-3 border border-[#0B6FD8]/20 shadow-xs">
          <span className="text-sm sm:text-base font-bold text-[#0B6FD8]">
            ➔ {copy.resolveStatement}
          </span>
        </div>
      </div>
    </LandingScene>
  );
}

export default ManifestoScene;
