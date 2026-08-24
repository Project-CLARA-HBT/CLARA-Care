"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { CouncilDemo } from "../demo/council-demo";

export function CouncilScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];

  return (
    <LandingScene id="council" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.council.eyebrow}
        title={copy.council.title}
        description={copy.council.description}
        align="left"
        tone="mint"
      />
      <CouncilDemo />
    </LandingScene>
  );
}
