"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { AmbientField } from "../primitives/ambient-field";
import { EvidenceDemo } from "../demo/evidence-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * EvidenceScene (Landing v7)
 *
 * Living Evidence Hub Scene:
 * - 5-Tier Hierarchical Source Matrix: Tier I DAV (National) ➔ Tier II DrugBank (International) ➔
 *   Tier III FDA Alerts (Regulatory) ➔ Tier IV PubMed/MEDLINE (Peer-Reviewed RCT).
 * - Optical SourceLens aperture focusing on selected authority weights.
 * - FIDES verified citation grounding with transparent limitation warnings.
 * - Editorial Statement: "Không phải mọi nguồn đều có trọng lượng như nhau."
 * - Ambient lighting field, spatial product stage with floating metadata and continuous transitions.
 */
export function EvidenceScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.evidence ?? LANDING_COPY_V7.vi.evidence;

  const evidenceBadge =
    lang === "vi"
      ? "TRUNG TÂM BẰNG CHỨNG Y VĂN • FIDES VERIFIED"
      : "LIVING EVIDENCE HUB • FIDES VERIFIED";

  const metaLabel1 = lang === "vi" ? "Cấp bậc chứng cứ" : "Evidence Hierarchy";
  const metaValue1 =
    lang === "vi" ? "Tier I DAV ➔ Tier IV RCT" : "Tier I DAV ➔ Tier IV RCT";
  const metaTag1 = "5 Tầng";

  const metaLabel2 = lang === "vi" ? "Thẩm định FIDES" : "FIDES Verification";
  const metaValue2 =
    lang === "vi" ? "100% Khớp nguồn y văn" : "100% Citation Grounded";
  const metaTag2 = "Zero Hallucination";

  return (
    <LandingScene
      id="evidence"
      scale="standard"
      tone="iris"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="iris" />

      {/* Background Top Transition Ribbon (Handoff from Scribe scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="iris" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={evidenceBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="iris"
          className="mb-4"
        />

        {copy.editorial && (
          <p className="text-center text-sm sm:text-base font-semibold text-[#8B7CF6] italic max-w-xl mx-auto">
            “{copy.editorial}”
          </p>
        )}
      </div>

      {/* Main Interactive Product Stage wrapping EvidenceDemo & SourceLens */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4">
        <SpatialStage enablePointerTilt={isEnhanced}>
          <div className="relative">
            <EvidenceDemo />

            {/* Floating Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="iris"
              className="absolute -top-4 -left-4 hidden lg:inline-flex"
            />

            {/* Floating Metadata 2 (Bottom Right / Overflow) */}
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

      {/* Transition Ribbon Flowing toward Safety Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default EvidenceScene;
