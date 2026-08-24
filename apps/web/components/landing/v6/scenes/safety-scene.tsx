"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { EditorialStatement } from "../primitives/editorial-statement";

export function SafetyScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];

  return (
    <LandingScene id="safety" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.safety.eyebrow}
        title={copy.safety.title}
        description={copy.safety.description}
        align="left"
        tone="azure"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 lg:gap-x-16 gap-y-6 md:gap-y-10 border-t border-[#E3E8EF] pt-4 lg:pt-8">
        {copy.safety.principles.map((principle) => (
          <EditorialStatement
            key={principle.number}
            number={principle.number}
            statement={principle.title}
            subtext={principle.description}
            tone="azure"
          />
        ))}
      </div>
    </LandingScene>
  );
}
