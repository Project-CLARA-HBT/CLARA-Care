"use client";

import React from "react";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";

export function FinalCtaScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].finalCta;

  return (
    <LandingScene
      id="cta"
      scale="signature"
      tone="azure"
      className="text-center overflow-hidden"
    >
      <div className="mx-auto max-w-4xl flex flex-col items-center">
        {/* Small CLARA Orb Icon */}
        <div className="relative inline-flex items-center justify-center mb-6">
          <div
            className="absolute -inset-3 rounded-full bg-[#0B6FD8]/15 blur-md"
            aria-hidden="true"
          />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-tr from-[#0B6FD8] via-[#1A86F5] to-[#38BDF8] text-white shadow-lg shadow-[#0B6FD8]/20 border-2 border-white">
            <span className="text-xl font-black select-none" aria-hidden="true">
              ✦
            </span>
          </div>
        </div>

        {/* Eyebrow Badge */}
        <div className="inline-flex items-center gap-2 rounded-full bg-[#EFF7FF] px-3.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs mb-4">
          <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
          {copy.eyebrow}
        </div>

        {/* Headline */}
        <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-[#162033] leading-[1.12]">
          {copy.title}
        </h2>

        {/* Description */}
        <p className="text-base sm:text-lg md:text-xl text-[#48566A] mt-5 max-w-2xl mx-auto leading-relaxed">
          {copy.description}
        </p>

        {/* Actions: Primary & Secondary CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-4 mt-8 pt-2">
          <Link
            href="/chat"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#0B6FD8] px-8 py-4 text-base font-bold text-white shadow-md hover:bg-[#0855A8] hover:shadow-lg transition-all clara-focus-ring active:scale-98"
          >
            <span>{copy.primaryCta}</span>
            <svg
              aria-hidden="true"
              className="w-4 h-4"
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

          <Link
            href="#safety"
            className="inline-flex items-center justify-center rounded-2xl bg-white px-7 py-4 text-base font-semibold text-[#162033] border border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD] shadow-xs transition-all clara-focus-ring"
          >
            {copy.secondaryCta}
          </Link>
        </div>

        {/* Security Badge */}
        <div className="mt-10 inline-flex items-center gap-2 rounded-full bg-white/90 backdrop-blur-xs px-4 py-2 text-xs font-medium text-[#48566A] border border-[#E3E8EF] shadow-xs">
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
      </div>
    </LandingScene>
  );
}

export default FinalCtaScene;
