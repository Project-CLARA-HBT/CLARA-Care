"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";
import { ClaraOrb } from "../artwork/clara-orb";

/**
 * ClinicalTransitionScene (Landing v7)
 *
 * Intentional Visual Silence Scene:
 * - A tranquil, spacious pause in pale Mint before the multidisciplinary Council (Spatial Peak 5).
 * - Restrained editorial statement establishing clinical authority and diagnostic depth.
 * - Beginning of the DecisionField multi-specialty convergence thread (Azure, Mint, Iris)
 *   guiding the eye into the Council chamber.
 */
export function ClinicalTransitionScene() {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.clinicalTransition ?? LANDING_COPY_V7.vi.clinicalTransition;

  const specialtyTokens =
    lang === "vi"
      ? [
          { name: "Tim mạch", color: "#0B6FD8", dot: "bg-[#0B6FD8]" },
          { name: "Thận học", color: "#14A88D", dot: "bg-[#14A88D]" },
          { name: "Dược lâm sàng", color: "#8B7CF6", dot: "bg-[#8B7CF6]" },
        ]
      : [
          { name: "Cardiology", color: "#0B6FD8", dot: "bg-[#0B6FD8]" },
          { name: "Nephrology", color: "#14A88D", dot: "bg-[#14A88D]" },
          { name: "Pharmacology", color: "#8B7CF6", dot: "bg-[#8B7CF6]" },
        ];

  return (
    <LandingScene
      id="clinical-transition"
      scale="transition"
      tone="mint"
      className="bg-[#ECFDF8]/45 border-y border-[#14A88D]/15 overflow-hidden relative py-20 md:py-28"
    >
      {/* Ambient Pale Mint Light Flare */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full bg-[#14A88D]/8 blur-3xl"
      />

      <div className="relative z-10 max-w-3xl mx-auto text-center px-4 space-y-6">
        <RevealGroup staggerMs={80}>
          {/* Soft Eyebrow with Ambient Orb */}
          <Reveal delayMs={0} direction="up">
            <div className="inline-flex items-center gap-2.5 rounded-full bg-white/80 px-4 py-1.5 border border-[#14A88D]/20 shadow-xs backdrop-blur-xs">
              <ClaraOrb size="sm" tone="mint" pulse={!isReducedMotion} />
              <span className="text-xs font-extrabold uppercase tracking-widest text-[#0E856F]">
                {copy.eyebrow}
              </span>
            </div>
          </Reveal>

          {/* Intentional Quiet Editorial Headline */}
          <Reveal delayMs={40} direction="up">
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-[#162033] leading-[1.15] whitespace-pre-line">
              {copy.headline}
            </h2>
          </Reveal>

          {/* Subheadline */}
          <Reveal delayMs={80} direction="up">
            <p className="text-base sm:text-lg text-[#48566A] max-w-2xl mx-auto leading-relaxed font-medium">
              {copy.subheadline}
            </p>
          </Reveal>

          {/* Specialty Thread Origin Indicators */}
          <Reveal delayMs={120} direction="up">
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2 text-xs text-[#6D7A8E]">
              {specialtyTokens.map((spec) => (
                <span
                  key={spec.name}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 border border-[#E3E8EF] shadow-2xs font-semibold hover:border-[#14A88D]/30 transition-colors"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${spec.dot}`} />
                  <span className="text-[#162033]">{spec.name}</span>
                </span>
              ))}
            </div>
          </Reveal>
        </RevealGroup>

        {/* Beginning of DecisionField Convergence Thread (SVG Spine flowing into Council) */}
        <div className="pt-6 flex justify-center" aria-hidden="true">
          <svg
            className="w-48 h-16 overflow-visible"
            viewBox="0 0 180 60"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Thread 1: Cardiology Azure */}
            <path
              d="M 30 0 C 30 25, 75 35, 90 60"
              stroke="#0B6FD8"
              strokeWidth="2"
              strokeDasharray="4 3"
              opacity="0.75"
              className={isReducedMotion ? "" : "clara-ribbon-path"}
            />
            {/* Thread 2: Nephrology Mint (Center Spine) */}
            <path
              d="M 90 0 L 90 60"
              stroke="#14A88D"
              strokeWidth="2.5"
              opacity="0.85"
            />
            {/* Thread 3: Pharmacology Iris */}
            <path
              d="M 150 0 C 150 25, 105 35, 90 60"
              stroke="#8B7CF6"
              strokeWidth="2"
              strokeDasharray="4 3"
              opacity="0.75"
              className={isReducedMotion ? "" : "clara-ribbon-path"}
            />
            {/* Central Convergence Sparkle Node */}
            <circle cx="90" cy="56" r="4" fill="#14A88D" />
            <circle cx="90" cy="56" r="1.75" fill="#FFFFFF" />
          </svg>
        </div>
      </div>
    </LandingScene>
  );
}

// Named alias for backward compatibility
export const ClinicalTransition = ClinicalTransitionScene;

export default ClinicalTransitionScene;
