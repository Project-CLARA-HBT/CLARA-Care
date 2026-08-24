"use client";

import React, { forwardRef } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { useSceneProgress } from "../runtime/use-scene-progress";

export interface StickyStageProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "children"> {
  id: string;
  stageHeightMultiplier?: number;
  children: React.ReactNode | ((progress: number) => React.ReactNode);
  className?: string;
  stageClassName?: string;
}

export const StickyStage = forwardRef<HTMLDivElement, StickyStageProps>(
  (
    {
      id,
      stageHeightMultiplier = 2.0,
      children,
      className = "",
      stageClassName = "",
      ...rest
    },
    forwardedRef
  ) => {
    const { isReducedMotion, isLite } = useMotionTier();
    const shouldSticky = !isReducedMotion && !isLite;
    const { ref: internalRef, progress } = useSceneProgress<HTMLDivElement>(id, {
      sticky: shouldSticky,
    });

    const setRef = (node: HTMLDivElement | null) => {
      (internalRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }
    };

    const renderedContent =
      typeof children === "function" ? children(shouldSticky ? progress : 1) : children;

    // Gracefully collapses on Lite/Reduced motion into a standard flow container
    if (!shouldSticky) {
      return (
        <div
          id={id}
          ref={setRef}
          data-sticky-stage={id}
          data-collapsed="true"
          className={`relative w-full py-12 md:py-16 ${className}`}
          {...rest}
        >
          <div className={`w-full ${stageClassName}`}>{renderedContent}</div>
        </div>
      );
    }

    return (
      <div
        id={id}
        ref={setRef}
        data-sticky-stage={id}
        style={{ height: `${Math.max(stageHeightMultiplier, 1) * 100}vh` }}
        className={`relative w-full ${className}`}
        {...rest}
      >
        <div
          className={`sticky top-0 h-screen w-full flex items-center justify-center overflow-hidden ${stageClassName}`}
        >
          {renderedContent}
        </div>
      </div>
    );
  }
);

StickyStage.displayName = "StickyStage";
