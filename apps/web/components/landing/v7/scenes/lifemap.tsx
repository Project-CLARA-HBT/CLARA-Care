"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { LifeMapDemo } from "../demo/lifemap-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * LifeMapScene (Spatial Peak 3)
 *
 * Signature LifeMap scene wrapping LifeMapDemo:
 * - 4-stage longitudinal timeline continuum (April -> May -> June -> Today)
 * - Connects TemporalRibbon curved SVG spine with glowing gradient flow
 * - Radiant TodayBeacon anchor marking the current temporal moment
 * - Interactive milestone inspection and prominent insight callout
 * - Continuous transition handoff ribbons connecting from previous to next scene
 */
export function LifeMapScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.lifemap ?? LANDING_COPY_V7.vi.lifemap;

  const peakBadge = lang === "vi" ? "ĐIỂM NHẤN 3 • DÒNG THỜI GIAN NHÂN QUẢ" : "PEAK 3 • CAUSAL CONTINUUM";
  const metaLabel1 = lang === "vi" ? "Chuỗi nhân quả" : "Causal Linking";
  const metaValue1 = lang === "vi" ? "4 mốc lâm sàng liên tục" : "4-Month Continuum";
  const metaTag1 = lang === "vi" ? "FIDES Linked" : "FIDES Linked";

  const metaLabel2 = lang === "vi" ? "Mốc hiện tại" : "Active Anchor";
  const metaValue2 = lang === "vi" ? "Hôm nay • Tương tác mới" : "Today • New Turn";
  const metaTag2 = lang === "vi" ? "Đang đồng bộ" : "Live Synced";

  return (
    <LandingScene
      id="lifemap"
      scale="signature"
      tone="azure"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Background Top Transition Ribbon (Handoff from Chat scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Editorial Scene Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={peakBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="azure"
          className="mb-0"
        />
      </div>

      {/* Main Spatial Demo Stage (Spatial Peak 3) */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4">
        <SpatialStage enablePointerTilt={isEnhanced}>
          {/* LifeMap Interactive Product Canvas */}
          <div className="relative">
            <LifeMapDemo />

            {/* Floating Contextual Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="azure"
              className="absolute -top-4 -left-4 hidden lg:inline-flex"
            />

            {/* Floating Contextual Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={metaLabel2}
              value={metaValue2}
              tag={metaTag2}
              tone="mint"
              className="absolute -bottom-4 -right-4 hidden lg:inline-flex"
            />
          </div>
        </SpatialStage>
      </div>

      {/* Bottom Transition Ribbon Towards Medicines Workspace */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/4 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="mint" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default LifeMapScene;
