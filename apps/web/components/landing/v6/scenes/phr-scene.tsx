"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { PhrSharingDemo } from "../demo/phr-sharing-demo";

export function PhrScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].phr;

  return (
    <LandingScene id="phr" scale="standard" tone="canvas">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="center"
        tone="azure"
      />
      <PhrSharingDemo />
    </LandingScene>
  );
}
