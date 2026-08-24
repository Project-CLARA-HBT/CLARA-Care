"use client";

import React, { forwardRef } from "react";

export type DepthPlane = "Z0" | "Z1" | "Z2" | "Z3";

export interface ArtworkLayerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  depthPlane?: DepthPlane;
  className?: string;
}

export const ArtworkLayer = forwardRef<HTMLDivElement, ArtworkLayerProps>(
  ({ children, depthPlane = "Z0", className = "", ...rest }, ref) => {
    const depthClasses = {
      Z0: "z-0 pointer-events-none absolute inset-0",
      Z1: "relative z-10",
      Z2: "relative z-20",
      Z3: "relative z-30 pointer-events-auto",
    }[depthPlane];

    return (
      <div
        ref={ref}
        data-depth-plane={depthPlane}
        className={`clara-artwork-layer ${depthClasses} ${className}`}
        {...rest}
      >
        {children}
      </div>
    );
  }
);

ArtworkLayer.displayName = "ArtworkLayer";
