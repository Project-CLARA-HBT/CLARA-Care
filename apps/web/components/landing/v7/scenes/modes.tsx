"use client";

import React, { useRef, useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { StickyScene } from "../primitives/sticky-scene";
import { AdaptiveShellDemo, type AdaptiveModeId } from "../demo/adaptive-shell-demo";
import { ClaraOrb } from "../artwork/clara-orb";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

function getModeFromProgress(progress: number): AdaptiveModeId {
  if (progress < 0.33) return "personal";
  if (progress < 0.67) return "clinical";
  return "research";
}

/**
 * ModesScene (Spatial Peak 4)
 *
 * Adaptive Modes Scene:
 * - One unified system shell adapting seamlessly across 3 distinct workflows:
 *   1. Personal Mode (Azure): Daily adherence, longitudinal LifeMap, medication tracking.
 *   2. Clinical Mode (Mint): Multidisciplinary Council triage, Ambient Scribe, SOAP drafting.
 *   3. Research Mode (Iris): Living evidence synthesis, RCT trial matrices, guideline citations.
 * - Dynamic ClaraOrb anchor and spatial theme morphing.
 * - Scroll-coordinated sticky progression with manual tab override support.
 */
export function ModesScene() {
  const { language, isReducedMotion, isLite } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.adaptive ?? LANDING_COPY_V7.vi.adaptive;
  const isInteractiveOnly = isReducedMotion || isLite;

  const [interactiveMode, setInteractiveMode] = useState<AdaptiveModeId>("personal");
  const [userOverride, setUserOverride] = useState<AdaptiveModeId | null>(null);
  const overrideProgressRef = useRef<number>(0);

  const handleModeChange = (mode: AdaptiveModeId, currentProgress = 0) => {
    if (isInteractiveOnly) {
      setInteractiveMode(mode);
    } else {
      setUserOverride(mode);
      overrideProgressRef.current = currentProgress;
    }
  };

  const peakBadge = lang === "vi" ? "ĐIỂM NHẤN 4 • MỘT KHUNG HỆ THỐNG DUY NHẤT" : "PEAK 4 • ONE SYSTEM SHELL";
  const metaLabel1 = lang === "vi" ? "Kiến trúc Thích nghi" : "Adaptive Shell";
  const metaValue1 = lang === "vi" ? "3 Chế độ • 1 Nền tảng" : "3 Roles • 1 Unified Core";
  const metaTag1 = lang === "vi" ? "Zero Latency" : "Zero Latency";

  const metaLabel2 = lang === "vi" ? "Thanh Dock Cố định" : "Centered Spatial Dock";
  const metaValue2 = lang === "vi" ? "5 vị trí chuẩn xác" : "5 Locked Slot Geometry";
  const metaTag2 = lang === "vi" ? "ClaraOrb Core" : "ClaraOrb Core";

  return (
    <LandingScene
      id="adaptive-modes"
      scale="signature"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-20 md:pt-28 md:pb-28"
    >
      {/* Background Top Transition Ribbon (Handoff from PHR) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="iris" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-8 md:mb-12 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={peakBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="iris"
          className="mb-0"
        />
      </div>

      {/* Sticky Spatial Canvas (Spatial Peak 4) */}
      <StickyScene id="adaptive-modes-sticky" totalScrollHeight="240vh">
        {(progress) => {
          const scrollMode = getModeFromProgress(progress);
          const hasScrolledPastOverride =
            userOverride !== null &&
            Math.abs(progress - overrideProgressRef.current) > 0.08;

          const effectiveOverride = hasScrolledPastOverride ? null : userOverride;
          const activeMode = isInteractiveOnly
            ? interactiveMode
            : (effectiveOverride ?? scrollMode);

          const orbTone = activeMode === "personal" ? "azure" : activeMode === "clinical" ? "mint" : "iris";

          return (
            <div className="w-full max-w-5xl mx-auto px-2 sm:px-4 relative">
              {/* Product Surface */}
              <AdaptiveShellDemo
                currentMode={activeMode}
                onModeChange={(mode) => handleModeChange(mode, progress)}
              />

              {/* Ambient Floating Artwork Anchor (ClaraOrb) */}
              <div className="absolute -top-6 -right-3 hidden xl:block pointer-events-none opacity-80">
                <ClaraOrb size="md" tone={orbTone} pulse={true} />
              </div>

              {/* Floating Contextual Metadata 1 */}
              <FloatingMetadata
                label={metaLabel1}
                value={metaValue1}
                tag={metaTag1}
                tone={orbTone}
                className="absolute -top-3 -left-3 hidden lg:inline-flex"
              />

              {/* Floating Contextual Metadata 2 */}
              <FloatingMetadata
                label={metaLabel2}
                value={metaValue2}
                tag={metaTag2}
                tone={orbTone}
                className="absolute -bottom-3 -right-3 hidden lg:inline-flex"
              />
            </div>
          );
        }}
      </StickyScene>

      {/* Bottom Transition Ribbon Towards Clinical Transition */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/4 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="mint" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

// Named alias for backward compatibility
export const AdaptiveModesScene = ModesScene;

export default ModesScene;
