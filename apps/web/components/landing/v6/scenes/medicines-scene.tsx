"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { MedicinesDemo } from "../demo/medicines-demo";

export function MedicinesScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].medicines;

  return (
    <LandingScene id="medicines" scale="standard" tone="mint">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="left"
        tone="mint"
      />
      <div className="mx-auto max-w-5xl w-full">
        <MedicinesDemo />
      </div>
    </LandingScene>
  );
}
