"use client";

import React from "react";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SpatialStage } from "../primitives/spatial-stage";
import { ClaraOrb } from "../artwork/clara-orb";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

export function HeroScene() {
  const { language, isEnhanced, isReducedMotion } = useMotionTier();
  const copy = LANDING_COPY_V7[language]?.hero ?? LANDING_COPY_V7.vi.hero;

  const trustBullets =
    language === "vi"
      ? [
          { dot: "bg-emerald-500", text: "Y văn Dược thư Quốc gia" },
          { dot: "bg-[#0B6FD8]", text: "Không suy đoán ngoài thẩm quyền" },
        ]
      : [
          { dot: "bg-emerald-500", text: "National Pharmacopoeia Vetted" },
          { dot: "bg-[#0B6FD8]", text: "Zero hallucinations beyond scope" },
        ];

  const userQueryLabel = language === "vi" ? "Câu hỏi người dùng" : "User Inquired";
  const clinicalResolutionLabel = language === "vi" ? "Kết luận lâm sàng" : "Clinical Synthesis";
  const nextActionPrefix = language === "vi" ? "➔ Bước tiếp theo:" : "➔ Next action:";
  const sourcePrefix = language === "vi" ? "Nguồn:" : "Source:";
  const securityTag = language === "vi" ? "Bảo mật Zero-CoT" : "Zero-CoT Privacy";
  const streamSubtitle =
    language === "vi" ? "Đối chiếu tương tác thời gian thực" : "Real-time safety stream";

  return (
    <LandingScene
      id="hero"
      scale="signature"
      tone="azure"
      className="pt-32 sm:pt-36 md:pt-44 pb-20 overflow-hidden relative"
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
        {/* Left Column (42-45% Desktop): Calm, Trustworthy Editorial Headline */}
        <div className="lg:col-span-5 space-y-6 text-left">
          <div className="inline-flex items-center gap-2 rounded-full bg-[#EFF7FF] px-3.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
            {copy.badge}
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[#162033] leading-[1.08]">
            {copy.titleStart}{" "}
            <span className="text-[#0B6FD8] block sm:inline">{copy.titleAccent}</span>{" "}
            {copy.titleEnd}
          </h1>

          <p className="text-base sm:text-lg text-[#48566A] leading-relaxed max-w-xl">
            {copy.description}
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/chat"
              className="inline-flex items-center justify-center rounded-2xl bg-[#0B6FD8] px-7 py-3.5 text-sm sm:text-base font-bold text-white shadow-md hover:bg-[#0855A8] transition-all clara-focus-ring active:scale-98"
            >
              <span>{copy.primaryCta}</span>
              <span className="ml-1.5" aria-hidden="true">
                ➔
              </span>
            </Link>

            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-sm sm:text-base font-semibold text-[#162033] border border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD] transition-all clara-focus-ring"
            >
              {copy.secondaryCta}
            </a>
          </div>

          <div className="flex items-center gap-4 pt-4 border-t border-[#E3E8EF]/80 text-xs text-[#6D7A8E]">
            {trustBullets.map((bullet) => (
              <span key={bullet.text} className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${bullet.dot}`} />
                {bullet.text}
              </span>
            ))}
          </div>
        </div>

        {/* Right Column (55-58% Desktop): Large Spatial Product Reveal (Peak 1) */}
        <div className="lg:col-span-7 relative">
          <SpatialStage enablePointerTilt={isEnhanced}>
            {/* Main Opaque Product Surface */}
            <div className="clara-product-surface relative p-6 sm:p-8 bg-white border border-[#E3E8EF] shadow-2xl">
              {/* Product Header Chrome */}
              <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-5">
                <div className="flex items-center gap-3">
                  <ClaraOrb size="sm" tone="azure" pulse={!isReducedMotion} />
                  <div>
                    <span className="font-bold text-sm text-[#162033]">CLARA Live Safety Stream</span>
                    <p className="text-[11px] text-[#6D7A8E]">{streamSubtitle}</p>
                  </div>
                </div>

                <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-bold text-[#14A88D] border border-[#14A88D]/20">
                  {copy.preview.safetyBadge}
                </span>
              </div>

              {/* Product Conversation Flow */}
              <div className="space-y-4 text-left">
                <div className="rounded-xl bg-[#EFF7FF] p-4 border border-[#0B6FD8]/15">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                    {userQueryLabel}
                  </span>
                  <p className="text-xs sm:text-sm font-medium text-[#162033] mt-1">
                    “{copy.preview.question}”
                  </p>
                </div>

                <div className="rounded-xl bg-white p-4 border border-[#E3E8EF] shadow-xs space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[#0B6FD8]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                      {clinicalResolutionLabel}
                    </span>
                  </div>
                  <p className="text-xs sm:text-sm text-[#162033] font-medium leading-relaxed">
                    {copy.preview.answerSummary}
                  </p>
                  <p className="text-xs text-[#14A88D] font-semibold pt-1">
                    {nextActionPrefix} {copy.preview.nextAction}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-1 text-[11px] text-[#6D7A8E]">
                  <span>
                    {sourcePrefix}{" "}
                    <strong className="text-[#162033]">{copy.preview.sourceCitation}</strong>
                  </span>
                  <span className="text-[#0B6FD8] font-medium">{securityTag}</span>
                </div>
              </div>
            </div>

            {/* Floating Contextual Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={copy.floatingContext1.label}
              value={copy.floatingContext1.value}
              tag={copy.floatingContext1.tag}
              tone="azure"
              className="absolute -top-5 -left-4 sm:-left-6 hidden sm:inline-flex"
            />

            {/* Floating Contextual Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={copy.floatingContext2.label}
              value={copy.floatingContext2.value}
              tag={copy.floatingContext2.tag}
              tone="mint"
              className="absolute -bottom-5 -right-4 sm:-right-6 hidden sm:inline-flex"
            />
          </SpatialStage>

          {/* Spatial Evidence Ribbon Handoff to Trust scene */}
          <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-md pointer-events-none opacity-60 hidden lg:block">
            <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-16 w-full" />
          </div>
        </div>
      </div>
    </LandingScene>
  );
}

export default HeroScene;
