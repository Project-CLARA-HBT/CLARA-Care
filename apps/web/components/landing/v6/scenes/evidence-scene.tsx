"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { EvidenceDemo } from "../demo/evidence-demo";

export function EvidenceScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].evidence;

  return (
    <LandingScene id="evidence" scale="standard" tone="iris">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="iris"
      />
      <EvidenceDemo />
    </LandingScene>
  );
}
