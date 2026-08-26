"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { AmbientField } from "../primitives/ambient-field";
import { CouncilDemo } from "../demo/council-demo";
import { DecisionField } from "../artwork/decision-field";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * CouncilScene (Spatial Peak 5)
 *
 * Signature Council Multi-Specialty Convergence Scene:
 * - DecisionField: Spatial SVG convergence canvas illustrating 3 specialty streams
 *   (Cardiology Azure, Nephrology Mint, Pharmacology Iris) converging into a structured decision plane.
 * - CouncilDemo: Progressive structured clinical triage (1. Recommendations, 2. Disagreements,
 *   3. Uncertainty, 4. Action Plan) under strict Physician Ultimate Authority governance.
 * - Two-way synchronized stage switching between DecisionField and CouncilDemo.
 * - Ambient lighting field, floating validation metadata, and continuous transition ribbons.
 */
export function CouncilScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.council ?? LANDING_COPY_V7.vi.council;

  const [activeStage, setActiveStage] = useState<1 | 2 | 3 | 4>(1);

  const peakBadge =
    lang === "vi"
      ? "ĐIỂM NHẤN 5 • HỘI CHẨN ĐA CHUYÊN KHOA"
      : "PEAK 5 • MULTIDISCIPLINARY COUNCIL";

  const metaLabel1 = lang === "vi" ? "Hội đồng đa chuyên khoa" : "3 Specialties Converging";
  const metaValue1 =
    lang === "vi"
      ? "Tim mạch • Thận học • Dược lâm sàng"
      : "Cardiology • Nephrology • Pharmacology";
  const metaTag1 = "FIDES Locked";

  const metaLabel2 = lang === "vi" ? "Phán quyết lâm sàng" : "Clinical Judgment";
  const metaValue2 =
    lang === "vi" ? "Bác sĩ giữ quyền tối cao" : "Physician Holds Authority";
  const metaTag2 = "Human-in-the-Loop";

  return (
    <LandingScene
      id="council"
      scale="signature"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="mint" />

      {/* Background Top Transition Ribbon (Handoff from Clinical Transition scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="mint" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Editorial Scene Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={peakBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="mint"
          className="mb-0"
        />
      </div>

      {/* Main Spatial Stage (Spatial Peak 5 Theater) */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4 space-y-8">
        <SpatialStage enablePointerTilt={isEnhanced}>
          {/* Spatial Decision Convergence Artwork */}
          <div className="relative mb-8">
            <DecisionField
              activeStage={activeStage}
              onStageChange={setActiveStage}
              className="shadow-2xl"
            />

            {/* Floating Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="mint"
              className="absolute -top-4 -left-4 hidden lg:inline-flex"
            />

            {/* Floating Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={metaLabel2}
              value={metaValue2}
              tag={metaTag2}
              tone="azure"
              className="absolute -bottom-4 -right-4 hidden lg:inline-flex"
            />
          </div>

          {/* Interactive Council Case & Results Workspace */}
          <CouncilDemo
            activeStage={activeStage}
            onStageChange={setActiveStage}
            showDecisionField={false}
          />
        </SpatialStage>
      </div>

      {/* Transition Ribbon Flowing toward Scribe Scene */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="mint" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default CouncilScene;
