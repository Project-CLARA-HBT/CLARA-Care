"use client";

import React from "react";
import { StickyStage, type StickyStageProps } from "./sticky-stage";

export interface StickySceneProps {
  id: string;
  totalScrollHeight?: string;
  children: (progress: number) => React.ReactNode;
  className?: string;
}

export function StickyScene({
  id,
  totalScrollHeight = "250vh",
  children,
  className = "",
}: StickySceneProps) {
  // Parse totalScrollHeight (e.g. "250vh" -> 2.5)
  const multiplier = parseFloat(totalScrollHeight) / 100 || 2.5;

  return (
    <StickyStage
      id={id}
      stageHeightMultiplier={multiplier}
      className={className}
    >
      {children}
    </StickyStage>
  );
}

export { StickyStage, type StickyStageProps };
