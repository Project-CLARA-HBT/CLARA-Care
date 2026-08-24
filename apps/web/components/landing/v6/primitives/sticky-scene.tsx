"use client";

import React, { useRef } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { useSceneProgress } from "../runtime/use-scene-progress";

export interface StickySceneProps {
  id: string;
  stageHeightMultiplier?: number; // e.g. 1.8 to 2.2 on desktop
  children: ((progress: number) => React.ReactNode) | React.ReactNode;
  className?: string;
  stageClassName?: string;
}

export function StickyScene({
  id,
  stageHeightMultiplier = 2.0,
  children,
  className = "",
  stageClassName = "",
}: StickySceneProps) {
  const { isReducedMotion, isLite } = useMotionTier();
  const { ref, progress } = useSceneProgress<HTMLDivElement>(id, {
    sticky: !isReducedMotion && !isLite,
  });

  // Mobile / Lite / Reduced Motion: Disable long sticky stage
  if (isReducedMotion || isLite) {
    return (
      <div id={id} ref={ref} className={`relative w-full ${className}`}>
        {typeof children === "function" ? children(1) : children}
      </div>
    );
  }

  return (
    <div
      id={id}
      ref={ref}
      className={`relative w-full ${className}`}
      style={{ height: `${stageHeightMultiplier * 100}vh` }}
    >
      <div className={`sticky top-0 min-h-screen flex items-center justify-center overflow-hidden py-12 ${stageClassName}`}>
        {typeof children === "function" ? children(progress) : children}
      </div>
    </div>
  );
}
