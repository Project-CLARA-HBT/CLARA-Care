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
import { PhrDemo } from "../demo/phr-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * PhrScene (Landing v7)
 *
 * Bounded PHR Sharing Scene:
 * - Granular data sovereignty: User explicitly selects what is shared, with whom, and validity duration.
 * - Wraps PhrDemo and PermissionGate spatial data boundary to halt sensitive data at source while allowing vetted clinical packet.
 * - Instant single-tap revocation terminating all active tokens immediately.
 * - Editorial Statement: "Chia sẻ một phần không có nghĩa là chia sẻ toàn bộ hồ sơ."
 */
export function PhrScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.phr ?? LANDING_COPY_V7.vi.phr;

  const securityBadge = lang === "vi" ? "BẢO MẬT ZERO-COT • QUẢN TRỊ DỮ LIỆU" : "ZERO-COT BOUNDARY • DATA GOVERNANCE";
  const metaLabel1 = lang === "vi" ? "Quyền truy cập" : "Access Governance";
  const metaValue1 = lang === "vi" ? "3 trường cho phép • 2 trường khóa" : "3 Permitted • 2 Blocked";
  const metaTag1 = lang === "vi" ? "Zero Leak" : "Zero Leak";

  const metaLabel2 = lang === "vi" ? "Thời hạn Token" : "Token Window";
  const metaValue2 = lang === "vi" ? "30 ngày • Thu hồi tức thì" : "30 Days • Instant Revoke";
  const metaTag2 = lang === "vi" ? "AES-256 GCM" : "AES-256 GCM";

  return (
    <LandingScene
      id="phr"
      scale="standard"
      tone="canvas"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Background Top Transition Ribbon (Handoff from Medicines) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-8 md:mb-12 px-2 sm:px-4">
        <RevealGroup staggerMs={80}>
          <Reveal delayMs={0} direction="up">
            <SceneHeader
              eyebrow={copy.eyebrow}
              badge={securityBadge}
              title={copy.title}
              description={copy.description}
              align="center"
              tone="azure"
              className="mb-0"
            />
          </Reveal>
        </RevealGroup>
      </div>

      {/* Main Interactive Product Stage wrapping PhrDemo */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4">
        <SpatialStage enablePointerTilt={isEnhanced}>
          <div className="relative">
            <PhrDemo />

            {/* Floating Contextual Metadata 1 (Top Left / Overflow) */}
            <FloatingMetadata
              label={metaLabel1}
              value={metaValue1}
              tag={metaTag1}
              tone="azure"
              className="absolute -top-4 -left-4 hidden lg:inline-flex transform-gpu transition-all duration-300 hover:scale-105 hover:-translate-y-1 hover:shadow-xl cursor-default"
            />

            {/* Floating Contextual Metadata 2 (Bottom Right / Overflow) */}
            <FloatingMetadata
              label={metaLabel2}
              value={metaValue2}
              tag={metaTag2}
              tone="mint"
              className="absolute -bottom-4 -right-4 hidden lg:inline-flex transform-gpu transition-all duration-300 hover:scale-105 hover:-translate-y-1 hover:shadow-xl cursor-default"
            />
          </div>
        </SpatialStage>
      </div>

      {/* Bottom Transition Ribbon Towards Adaptive Modes */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/3 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="iris" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

// Named alias for backward compatibility
export const Phr = PhrScene;

export default PhrScene;
