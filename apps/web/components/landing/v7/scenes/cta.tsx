"use client";

import React from "react";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { AmbientField } from "../primitives/ambient-field";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";
import { ClaraOrb } from "../artwork/clara-orb";

/**
 * FinalCtaScene (Visual Silence & Clarity)
 *
 * Requirements:
 * - Visual silence with expansive breathing room and calm authority.
 * - Centered glowing ClaraOrb anchor with layered soft radial aura.
 * - Staggered entrance cascade for eyebrow, headline, description, primary & secondary CTAs.
 * - Verifiable zero-CoT security badge.
 */
export function FinalCtaScene() {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.finalCta ?? LANDING_COPY_V7.vi.finalCta;

  return (
    <LandingScene
      id="cta"
      scale="signature"
      tone="azure"
      className="text-center overflow-hidden relative py-28 sm:py-36 md:py-44"
    >
      {/* Layer 1: Ambient Azure Field */}
      <AmbientField tone="azure" />

      {/* Layer 2: Visual Silence Soft Radial Aura */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[560px] w-[560px] sm:h-[720px] sm:w-[720px] rounded-full opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(11, 111, 216, 0.18) 0%, rgba(20, 168, 141, 0.08) 45%, transparent 72%)",
        }}
      />

      {/* Layer 3: Concentric Geometric Guidance Rings for Visual Silence & Focus */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[420px] w-[420px] sm:h-[580px] sm:w-[580px] rounded-full border border-[#0B6FD8]/10 opacity-70"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[260px] w-[260px] sm:h-[380px] sm:w-[380px] rounded-full border border-[#0B6FD8]/15 opacity-80"
      />

      <div className="relative z-10 mx-auto max-w-4xl flex flex-col items-center px-4">
        <RevealGroup staggerMs={90}>
          {/* Centered Glowing ClaraOrb Visual Anchor */}
          <Reveal delayMs={0} direction="scale">
            <div className="relative mb-6 sm:mb-8 flex items-center justify-center">
              {/* Luminous Pulsing Outer Halo */}
              <div
                aria-hidden="true"
                className="absolute -inset-6 sm:-inset-8 rounded-full bg-[#0B6FD8]/20 blur-xl opacity-80 pointer-events-none clara-orb-glow"
              />
              <ClaraOrb size="lg" tone="azure" pulse={!isReducedMotion} />
            </div>
          </Reveal>

          {/* Eyebrow Badge */}
          <Reveal delayMs={90} direction="up">
            <div className="inline-flex items-center gap-2 rounded-full bg-[#EFF7FF] px-4 py-1.5 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/25 shadow-xs mb-5 backdrop-blur-xs">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
              {copy.eyebrow}
            </div>
          </Reveal>

          {/* Headline */}
          <Reveal delayMs={180} direction="up">
            <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-[#162033] leading-[1.12]">
              {copy.title}
            </h2>
          </Reveal>

          {/* Description */}
          <Reveal delayMs={270} direction="up">
            <p className="text-base sm:text-lg md:text-xl text-[#48566A] mt-5 max-w-2xl mx-auto leading-relaxed">
              {copy.description}
            </p>
          </Reveal>

          {/* Actions: Primary & Secondary CTAs */}
          <Reveal delayMs={360} direction="up">
            <div className="flex flex-wrap items-center justify-center gap-4 mt-8 pt-2">
              <Link
                href="/chat"
                className="inline-flex items-center justify-center gap-2.5 rounded-2xl bg-[#0B6FD8] px-8 py-4 text-base font-bold text-white shadow-lg hover:bg-[#0855A8] hover:shadow-xl hover:-translate-y-0.5 transition-all clara-focus-ring active:scale-98"
              >
                <span>{copy.primaryCta}</span>
                <svg
                  aria-hidden="true"
                  className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                  />
                </svg>
              </Link>

              <a
                href="#safety"
                className="inline-flex items-center justify-center rounded-2xl bg-white px-7 py-4 text-base font-semibold text-[#162033] border border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD] hover:-translate-y-0.5 shadow-xs transition-all clara-focus-ring"
              >
                {copy.secondaryCta}
              </a>
            </div>
          </Reveal>

          {/* Security & Privacy Badge */}
          <Reveal delayMs={450} direction="up">
            <div className="mt-10 inline-flex items-center gap-2.5 rounded-full bg-white/90 backdrop-blur-md px-4 py-2 text-xs font-medium text-[#48566A] border border-[#E3E8EF] shadow-sm hover:border-[#CBD5E1] transition-all">
              <svg
                className="w-4 h-4 text-[#14A88D] shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                />
              </svg>
              <span>{copy.securityBadge}</span>
            </div>
          </Reveal>
        </RevealGroup>
      </div>
    </LandingScene>
  );
}

export { FinalCtaScene as CtaScene };
export default FinalCtaScene;
