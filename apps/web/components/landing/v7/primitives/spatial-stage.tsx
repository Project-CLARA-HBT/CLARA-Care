"use client";

import React, { forwardRef } from "react";
import { usePointerDepth } from "../runtime/use-pointer-depth";

export interface SpatialStageProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  enablePointerTilt?: boolean;
  className?: string;
}

export const SpatialStage = forwardRef<HTMLDivElement, SpatialStageProps>(
  ({ children, enablePointerTilt = false, className = "", ...rest }, forwardedRef) => {
    const tiltRef = usePointerDepth<HTMLDivElement>({ disabled: !enablePointerTilt });

    const setRef = (node: HTMLDivElement | null) => {
      (tiltRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }
    };

    return (
      <div
        ref={setRef}
        className={`clara-spatial-stage relative w-full transition-transform duration-300 ease-out ${className}`}
        {...rest}
      >
        {children}
      </div>
    );
  }
);

SpatialStage.displayName = "SpatialStage";
