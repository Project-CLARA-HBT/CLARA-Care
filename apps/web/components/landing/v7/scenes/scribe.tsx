"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { SpatialStage } from "../primitives/spatial-stage";
import { AmbientField } from "../primitives/ambient-field";
import { ScribeDemo } from "../demo/scribe-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { FloatingMetadata } from "../primitives/floating-metadata";

/**
 * ScribeScene (Landing v7)
 *
 * Ambient Clinical Scribe Transformation Scene:
 * - 5-Step Pipeline: Consent ➔ Acoustic Capture (CaptureWave) ➔ Clinical NLP ➔ Structured SOAP Note ➔ Physician Sign-Off.
 * - Bilingual Vietnamese-English medical term normalization.
 * - Zero-CoT privacy boundary with end-to-end encryption.
 * - Ambient lighting field, spatial product stage wrapping ScribeDemo with floating metadata and continuous transitions.
 */
export function ScribeScene() {
  const { language, isEnhanced } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.scribe ?? LANDING_COPY_V7.vi.scribe;

  const scribeBadge =
    lang === "vi"
      ? "TRỢ LÝ GHI CHÉP Y KHOA • BẢO MẬT ZERO-COT"
      : "AMBIENT CLINICAL SCRIBE • ZERO-COT";

  const metaLabel1 = lang === "vi" ? "Tiến trình chuyển hóa" : "Transformation Flow";
  const metaValue1 =
    lang === "vi" ? "5 Bước • Hội thoại ➔ SOAP" : "5 Steps • Voice ➔ SOAP";
  const metaTag1 = "48kHz NLP";

  const metaLabel2 = lang === "vi" ? "Bảo mật hội thoại" : "Audio Privacy";
  const metaValue2 =
    lang === "vi"
      ? "Mã hóa E2EE • Vùng an toàn Zero-CoT"
      : "E2EE • Zero-CoT Enclave";
  const metaTag2 = "Zero Leak";

  return (
    <LandingScene
      id="scribe"
      scale="standard"
      tone="mint"
      className="relative overflow-hidden pt-20 pb-24 md:pt-28 md:pb-36"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="mint" />

      {/* Background Top Transition Ribbon (Handoff from Council scene) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-30 flex items-center justify-center overflow-hidden"
      >
        <EvidenceRibbon variant="horizontal" tone="mint" active={true} className="w-full max-w-6xl" />
      </div>

      {/* Scene Editorial Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14 px-2 sm:px-4">
        <SceneHeader
          eyebrow={copy.eyebrow}
          badge={scribeBadge}
          title={copy.title}
          description={copy.description}
          align="center"
          tone="mint"
          className="mb-0"
        />
      </div>

      {/* Main Interactive Product Stage wrapping ScribeDemo & CaptureWave */}
      <div className="relative mx-auto max-w-5xl w-full px-2 sm:px-4">
        <SpatialStage enablePointerTilt={isEnhanced}>
          <div className="relative">
            <ScribeDemo />

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
        </SpatialStage>
      </div>

      {/* Transition Ribbon Flowing toward Evidence Hub */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="iris" active={true} className="h-20 w-full" />
      </div>
    </LandingScene>
  );
}

export default ScribeScene;
