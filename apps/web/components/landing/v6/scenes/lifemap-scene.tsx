"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { LifeMapDemo } from "../demo/lifemap-demo";

export function LifeMapScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].lifemap;

  return (
    <LandingScene id="lifemap" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="azure"
      />
      <LifeMapDemo />
    </LandingScene>
  );
}
