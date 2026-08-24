"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { ScribeDemo } from "../demo/scribe-demo";

export function ScribeScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].scribe;

  return (
    <LandingScene id="scribe" scale="standard" tone="mint">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="mint"
      />
      <ScribeDemo />
    </LandingScene>
  );
}
