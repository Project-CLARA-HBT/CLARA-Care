"use client";

import React from "react";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SpatialStage } from "../primitives/spatial-stage";
import { FloatingMetadata } from "../primitives/floating-metadata";

export function HeroScene() {
  const { language, isEnhanced } = useMotionTier();
  const copy = LANDING_COPY_V6[language].hero;

  return (
    <LandingScene
      id="hero"
      scale="signature"
      tone="azure"
      className="pt-32 sm:pt-36 md:pt-44 pb-20 overflow-hidden"
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
              <span className="ml-1.5">➔</span>
            </Link>

            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-sm sm:text-base font-semibold text-[#162033] border border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD] transition-all clara-focus-ring"
            >
              {copy.secondaryCta}
            </a>
          </div>

          <div className="flex items-center gap-4 pt-4 border-t border-[#E3E8EF]/80 text-xs text-[#6D7A8E]">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Y văn Dược thư Quốc gia
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8]" />
              Không suy đoán ngoài thẩm quyền
            </span>
          </div>
        </div>

        {/* Right Column (55-58% Desktop): Large Spatial Product Reveal (3D perspective stage) */}
        <div className="lg:col-span-7 relative">
          <SpatialStage enablePointerTilt={isEnhanced}>
            {/* Main Opaque Product Surface */}
            <div className="clara-product-surface relative p-6 sm:p-8 bg-white border border-[#E3E8EF] shadow-2xl">
              {/* Product Header Chrome */}
              <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0B6FD8] text-white font-black text-sm">
                    C
                  </div>
                  <div>
                    <span className="font-bold text-sm text-[#162033]">CLARA Live Safety Stream</span>
                    <p className="text-[11px] text-[#6D7A8E]">Đối chiếu tương tác thời gian thực</p>
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
                    Câu hỏi người dùng
                  </span>
                  <p className="text-xs sm:text-sm font-medium text-[#162033] mt-1">
                    “{copy.preview.question}”
                  </p>
                </div>

                <div className="rounded-xl bg-white p-4 border border-[#E3E8EF] shadow-xs space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[#0B6FD8]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                      Kết luận lâm sàng
                    </span>
                  </div>
                  <p className="text-xs sm:text-sm text-[#162033] font-medium leading-relaxed">
                    {copy.preview.answerSummary}
                  </p>
                  <p className="text-xs text-[#14A88D] font-semibold pt-1">
                    ➔ Bước tiếp theo: {copy.preview.nextAction}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-1 text-[11px] text-[#6D7A8E]">
                  <span>Nguồn: <strong className="text-[#162033]">{copy.preview.sourceCitation}</strong></span>
                  <span className="text-[#0B6FD8] font-medium">Bảo mật Zero-CoT</span>
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
        </div>
      </div>
    </LandingScene>
  );
}
