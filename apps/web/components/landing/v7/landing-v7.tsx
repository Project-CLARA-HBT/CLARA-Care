"use client";

import React from "react";
import "./landing-v7.css";
import { MotionProvider } from "./runtime/motion-provider";
import { LandingNav } from "./landing-nav";

// All Scenes in canonical storyboard chapter order
import { HeroScene } from "./scenes/hero";
import { SponsorsScene } from "./scenes/sponsors";
import { TrustScene } from "./scenes/trust";
import { ManifestoScene } from "./scenes/manifesto";
import { HowScene } from "./scenes/how";
import { ChatScene } from "./scenes/chat";
import { LifeMapScene } from "./scenes/lifemap";
import { MedicinesScene } from "./scenes/medicines";
import { PhrScene } from "./scenes/phr";
import { AdaptiveModesScene } from "./scenes/modes";
import { ClinicalTransitionScene } from "./scenes/clinical-transition";
import { CouncilScene } from "./scenes/council";
import { ScribeScene } from "./scenes/scribe";
import { EvidenceScene } from "./scenes/evidence";
import { SafetyScene } from "./scenes/safety";
import { PrivacyScene } from "./scenes/privacy";
import { ScenariosScene } from "./scenes/scenarios";
import { ComparisonScene } from "./scenes/comparison";
import { FaqScene } from "./scenes/faq";
import { FinalCtaScene } from "./scenes/cta";
import { FooterScene } from "./scenes/footer";

export function LandingV7() {
  return (
    <MotionProvider>
      <div className="clara-landing-v7 min-h-screen selection:bg-[#0B6FD8]/15 selection:text-[#0B6FD8]">
        {/* Accessible Skip Link */}
        <a
          href="#hero"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-xl focus:bg-[#0B6FD8] focus:px-4 focus:py-2.5 focus:text-sm focus:font-bold focus:text-white focus:shadow-lg"
        >
          Chuyển đến nội dung chính / Skip to main content
        </a>

        {/* Floating Island Navigation */}
        <LandingNav />

        {/* Storyboard Chapters */}
        <main id="main-content" role="main" className="relative flex flex-col w-full">
          {/* 1. Hero — Spatial Product Reveal (Peak 1) */}
          <HeroScene />

          {/* 1.5. Institutional Partners & Infrastructure Sponsors */}
          <SponsorsScene />

          {/* 2. Trust Transition */}
          <TrustScene />

          {/* 3. Context Manifesto — Spatial Constellation */}
          <ManifestoScene />

          {/* 4. How CLARA Works — 4-Step Pipeline Transformation */}
          <HowScene />

          {/* 5. Chat — Signature Scene: Answer Depth (Peak 2) */}
          <ChatScene />

          {/* 6. LifeMap — Signature Scene: Longitudinal Canvas (Peak 3) */}
          <LifeMapScene />

          {/* 7. Medicines — Interactive Focus Workspace */}
          <MedicinesScene />

          {/* 8. Health Record / PHR — Spatial Permission Boundary */}
          <PhrScene />

          {/* 9. Adaptive Modes — Signature WOW Scene: One Shell Morphs (Peak 4) */}
          <AdaptiveModesScene />

          {/* 10. Clinical Transition — Intentional Visual Silence */}
          <ClinicalTransitionScene />

          {/* 11. Council — Signature Scene: Multi-Specialty Convergence (Peak 5) */}
          <CouncilScene />

          {/* 12. Scribe — Information Transformation */}
          <ScribeScene />

          {/* 13. Evidence — Source Authority Workspace */}
          <EvidenceScene />

          {/* 14. Safety — Typographic Immersion */}
          <SafetyScene />

          {/* 15. Privacy — Interactive Data Boundary */}
          <PrivacyScene />

          {/* 16. Real-life Scenarios — Human Scale */}
          <ScenariosScene />

          {/* 17. Differentiation — Why CLARA is Not Generic AI */}
          <ComparisonScene />

          {/* 18. FAQ — Accessible Accordion */}
          <FaqScene />

          {/* 19. Final CTA — Visual Release */}
          <FinalCtaScene />
        </main>

        {/* 20. Footer — Complete Semantic Navigation */}
        <FooterScene />
      </div>
    </MotionProvider>
  );
}

export default LandingV7;
