"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { ChatDemo } from "../demo/chat-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { AmbientField } from "../primitives/ambient-field";

/**
 * ChatScene (Spatial Peak 2)
 *
 * Signature Chat scene demonstrating CLARA's 5-tier progressive response surface:
 * - Tier 1: Direct Answer (prominent, high-contrast clinical takeaway)
 * - Tier 2: Next Action (interactive checklist with state tracking)
 * - Tier 3: Uncertainty / Data Gaps (explicit clinical context boundary)
 * - Tier 4: Referenced Clinical Sources (interactive citation inspector)
 * - Tier 5: Advanced Pharmacological Detail (expandable mechanism view)
 *
 * Includes continuous EvidenceRibbon handoffs bridging from How scene and transitioning to LifeMap.
 */
export function ChatScene() {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.chat ?? LANDING_COPY_V7.vi.chat;

  const peakBadge =
    lang === "vi"
      ? "ĐIỂM NHẤN 2 • GIAO DIỆN PHẢN HỒI PHÂN TẦNG"
      : "PEAK 2 • 5-TIER RESPONSE SURFACE";

  return (
    <LandingScene
      id="chat"
      scale="signature"
      tone="azure"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36 clara-transition-how-chat"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Top Transition Ribbon from How Scene */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-16 opacity-35"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={!isReducedMotion} className="w-full max-w-6xl" />
      </div>

      {/* Editorial Scene Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-4">
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

      {/* Main Interactive Chat Product Surface (Spatial Peak 2) */}
      <div className="mx-auto max-w-5xl w-full px-2 sm:px-4 relative z-10">
        <ChatDemo />
      </div>

      {/* Downward Transition Ribbon Towards LifeMap Continuum (Peak 3) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/4 w-80 opacity-45 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={!isReducedMotion} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default ChatScene;

