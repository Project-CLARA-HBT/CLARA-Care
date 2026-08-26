"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { AmbientField } from "../primitives/ambient-field";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

/**
 * SafetyScene (Landing v7)
 *
 * Typography as Artwork Scene:
 * - Pure typographic editorial immersion without heavy card wrappers.
 * - 4 Non-Negotiable Invariant Principles:
 *   01. Unambiguous Source Attribution
 *   02. Never Conceal Uncertainty
 *   03. Never Label 'Unchecked' as 'Safe'
 *   04. Know When to Escalate to Humans
 * - Monumental display numerals, architectural hairline grid, ambient lighting.
 */
export function SafetyScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.safety ?? LANDING_COPY_V7.vi.safety;
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const safetyBadge =
    lang === "vi"
      ? "NGUYÊN TẮC BẤT BIẾN • FIDES GROUNDING"
      : "NON-NEGOTIABLE SAFETY • FIDES GROUNDED";

  const invariantLabel =
    lang === "vi" ? "Bất biến kỹ thuật" : "Engineered Invariant";

  return (
    <LandingScene
      id="safety"
      scale="signature"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Background Top Transition Ribbon (Handoff from Evidence scene) */}
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
          badge={safetyBadge}
          title={copy.title}
          description={copy.description}
          align="left"
          tone="azure"
          className="mb-0"
        />
      </div>

      {/* Pure Typographic Artwork Grid (Zero generic boxiness, architectural typography) */}
      <div className="relative z-10 max-w-6xl mx-auto px-2 sm:px-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-10 lg:gap-x-16 lg:gap-y-12">
          {copy.principles.map((principle, idx) => {
            const isHovered = hoveredIndex === idx;

            return (
              <div
                key={principle.number}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className={`group relative pt-6 border-t transition-all duration-300 ${
                  isHovered
                    ? "border-[#0B6FD8] text-[#162033]"
                    : "border-[#E3E8EF] text-[#162033]"
                }`}
              >
                {/* Active Accent Highlight Line */}
                <div
                  aria-hidden="true"
                  className={`absolute top-0 left-0 h-0.5 bg-[#0B6FD8] transition-all duration-300 ${
                    isHovered ? "w-full opacity-100" : "w-12 opacity-40"
                  }`}
                />

                <div className="flex items-baseline gap-4 sm:gap-6">
                  {/* Monumental Display Numeral */}
                  <span
                    className={`font-mono text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter transition-colors duration-300 select-none ${
                      isHovered
                        ? "text-[#0B6FD8]"
                        : "text-[#0B6FD8]/30 group-hover:text-[#0B6FD8]/60"
                    }`}
                  >
                    {principle.number}
                  </span>

                  {/* Principle Content Body */}
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                        {invariantLabel}
                      </span>
                    </div>

                    <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#162033] leading-snug">
                      {principle.title}
                    </h3>

                    <p className="text-sm sm:text-base text-[#48566A] leading-relaxed pt-1">
                      {principle.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Transition Ribbon Flowing toward Privacy Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default SafetyScene;
