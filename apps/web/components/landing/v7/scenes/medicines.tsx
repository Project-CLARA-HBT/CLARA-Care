"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { AmbientField } from "../primitives/ambient-field";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";
import { MedicinesDemo } from "../demo/medicines-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * MedicinesScene (Landing v7)
 *
 * Unified Medicines Workspace:
 * - Strict 4-category distinction: Active (Đang dùng), Needs Review (Cần xác nhận), Safety (FIDES Check), Cabinet (Tủ thuốc).
 * - CareGuard Multi-Layer Drug-Drug Interaction (DDI) engine tag & verification status.
 * - Semantic Truth Principle: "Tủ thuốc lưu trữ ≠ Thuốc đang uống hàng ngày."
 * - Spatial stage wrapping MedicinesDemo with floating verification metadata and continuous transition handoffs.
 */
export function MedicinesScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.medicines ?? LANDING_COPY_V7.vi.medicines;

  const careGuardBadge = lang === "vi" ? "CAREGUARD DDI ENGINE • FIDES VETTED" : "CAREGUARD DDI ENGINE • FIDES VETTED";
  const metaLabel1 = lang === "vi" ? "Động lực học Dược lý" : "Pharmacodynamics";
  const metaValue1 = lang === "vi" ? "0 tương tác đối kháng" : "0 Critical Interactions";
  const metaTag1 = lang === "vi" ? "An toàn 100%" : "100% Safe";

  const metaLabel2 = lang === "vi" ? "Dữ liệu Quy chuẩn" : "Normative Sources";
  const metaValue2 = lang === "vi" ? "Dược thư VN & DrugBank" : "National Pharmacopoeia";
  const metaTag2 = lang === "vi" ? "Đã đối chiếu" : "Cross-Checked";

  return (
    <LandingScene
      id="medicines"
      scale="standard"
      tone="mint"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36 clara-transition-lifemap-medicines"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="mint" />

      {/* Background Top Transition Ribbon (Handoff from LifeMap) */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-16 opacity-35"
      >
        <EvidenceRibbon variant="horizontal" tone="mint" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <RevealGroup staggerMs={80}>
          <Reveal delayMs={0} direction="up">
            <SceneHeader
              eyebrow={copy.eyebrow}
              badge={careGuardBadge}
              title={copy.title}
              description={copy.description}
              align="center"
              tone="mint"
              className="mb-0"
            />
          </Reveal>
        </RevealGroup>
      </div>

      {/* Main Product Demo Workspace */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4">
        <SpatialStage enablePointerTilt={isEnhanced}>
          <div className="relative">
            <MedicinesDemo />

            {/* Floating Contextual Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="mint"
              className="absolute -top-4 -left-4 hidden lg:inline-flex transform-gpu transition-all duration-300 hover:scale-105 hover:-translate-y-1 hover:shadow-xl cursor-default"
            />

            {/* Floating Contextual Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={metaLabel2}
              value={metaValue2}
              tag={metaTag2}
              tone="azure"
              className="absolute -bottom-4 -right-4 hidden lg:inline-flex transform-gpu transition-all duration-300 hover:scale-105 hover:-translate-y-1 hover:shadow-xl cursor-default"
            />
          </div>
        </SpatialStage>
      </div>

      {/* Bottom Transition Ribbon Towards PHR Bounded Sharing */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 right-1/4 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

// Named alias for backward compatibility
export const Medicines = MedicinesScene;

export default MedicinesScene;
