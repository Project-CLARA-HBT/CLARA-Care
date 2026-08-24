"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";

export function ManifestoScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].manifesto;

  return (
    <LandingScene id="manifesto" scale="signature" tone="azure" className="overflow-hidden">
      <div className="text-center max-w-4xl mx-auto mb-14">
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

      {/* Spatial Constellation Stage (Desktop Orbit + Mobile Linear) */}
      <div className="relative mx-auto max-w-4xl py-6">
        {/* SVG Connector Layer */}
        <svg
          aria-hidden="true"
          className="absolute inset-0 h-full w-full pointer-events-none hidden md:block"
          viewBox="0 0 800 400"
          fill="none"
        >
          <line x1="200" y1="80" x2="400" y2="200" stroke="#0B6FD8" strokeWidth="1.5" className="clara-constellation-line" />
          <line x1="600" y1="80" x2="400" y2="200" stroke="#14A88D" strokeWidth="1.5" className="clara-constellation-line" />
          <line x1="150" y1="320" x2="400" y2="200" stroke="#0B6FD8" strokeWidth="1.5" className="clara-constellation-line" />
          <line x1="650" y1="320" x2="400" y2="200" stroke="#8B7CF6" strokeWidth="1.5" className="clara-constellation-line" />
          <line x1="400" y1="40" x2="400" y2="200" stroke="#0B6FD8" strokeWidth="1.5" className="clara-constellation-line" />
        </svg>

        {/* Nodes Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center relative z-10">
          {/* Left Context Nodes */}
          <div className="space-y-4">
            <div className="rounded-2xl bg-white p-4 border border-[#0B6FD8]/25 shadow-sm text-left">
              <span className="h-2 w-2 rounded-full bg-[#0B6FD8] inline-block mr-2" />
              <span className="text-xs font-bold text-[#162033]">{copy.nodes.medications}</span>
              <p className="text-[11px] text-[#6D7A8E] mt-0.5">Metformin 500mg • Amlodipine 5mg</p>
            </div>
            <div className="rounded-2xl bg-white p-4 border border-[#E3E8EF] shadow-sm text-left">
              <span className="h-2 w-2 rounded-full bg-[#6D7A8E] inline-block mr-2" />
              <span className="text-xs font-bold text-[#162033]">{copy.nodes.recentChanges}</span>
              <p className="text-[11px] text-[#6D7A8E] mt-0.5">Đổi giờ làm việc & lịch uống thuốc</p>
            </div>
          </div>

          {/* Center Convergence Node: CLARA CORE */}
          <div className="flex flex-col items-center justify-center p-6 rounded-3xl bg-white border-2 border-[#0B6FD8] shadow-xl text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0B6FD8] text-white text-2xl font-black shadow-md mb-3">
              ✦
            </div>
            <h3 className="text-base font-bold text-[#162033]">{copy.centerTitle}</h3>
            <span className="text-xs text-[#0B6FD8] font-semibold mt-0.5">{copy.centerSubtitle}</span>
          </div>

          {/* Right Context Nodes */}
          <div className="space-y-4">
            <div className="rounded-2xl bg-white p-4 border border-[#14A88D]/25 shadow-sm text-left">
              <span className="h-2 w-2 rounded-full bg-[#14A88D] inline-block mr-2" />
              <span className="text-xs font-bold text-[#162033]">{copy.nodes.healthRecord}</span>
              <p className="text-[11px] text-[#6D7A8E] mt-0.5">Tiền sử tăng HA 10 năm, Dị ứng Penicillin</p>
            </div>
            <div className="rounded-2xl bg-white p-4 border border-[#8B7CF6]/25 shadow-sm text-left">
              <span className="h-2 w-2 rounded-full bg-[#8B7CF6] inline-block mr-2" />
              <span className="text-xs font-bold text-[#162033]">{copy.nodes.sources}</span>
              <p className="text-[11px] text-[#6D7A8E] mt-0.5">Dược thư Quốc gia • DrugBank 5.1</p>
            </div>
          </div>
        </div>
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
