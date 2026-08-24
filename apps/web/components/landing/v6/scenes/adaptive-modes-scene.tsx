"use client";

import React, { useRef, useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { StickyScene } from "../primitives/sticky-scene";
import { AdaptiveShellDemo, type AdaptiveModeId } from "../demo/adaptive-shell-demo";

function getModeFromProgress(progress: number): AdaptiveModeId {
  if (progress < 0.33) return "personal";
  if (progress < 0.67) return "clinical";
  return "research";
}

export function AdaptiveModesScene() {
  const { language, isReducedMotion, isLite } = useMotionTier();
  const copy = LANDING_COPY_V6[language];
  const isInteractiveOnly = isReducedMotion || isLite;

  const [interactiveMode, setInteractiveMode] = useState<AdaptiveModeId>("personal");
  const [userOverride, setUserOverride] = useState<AdaptiveModeId | null>(null);
  const overrideProgressRef = useRef<number>(0);

  const handleModeChange = (mode: AdaptiveModeId, currentProgress = 0) => {
    if (isInteractiveOnly) {
      setInteractiveMode(mode);
    } else {
      setUserOverride(mode);
      overrideProgressRef.current = currentProgress;
    }
  };

  return (
    <LandingScene id="adaptive-modes" scale="signature" tone="canvas">
      <SceneHeader
        eyebrow={copy.adaptive.eyebrow}
        title={copy.adaptive.title}
        description={copy.adaptive.description}
        align="center"
        tone="azure"
      />

      <StickyScene id="adaptive-modes-sticky" stageHeightMultiplier={2.2}>
        {(progress) => {
          const scrollMode = getModeFromProgress(progress);
          const hasScrolledPastOverride =
            userOverride !== null &&
            Math.abs(progress - overrideProgressRef.current) > 0.08;

          const effectiveOverride = hasScrolledPastOverride ? null : userOverride;
          const activeMode = isInteractiveOnly
            ? interactiveMode
            : (effectiveOverride ?? scrollMode);

          return (
            <div className="w-full max-w-5xl mx-auto">
              <AdaptiveShellDemo
                currentMode={activeMode}
                onModeChange={(mode) => handleModeChange(mode, progress)}
              />
            </div>
          );
        }}
      </StickyScene>
    </LandingScene>
  );
}
