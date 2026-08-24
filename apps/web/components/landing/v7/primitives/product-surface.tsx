"use client";

import React, { forwardRef } from "react";

export type ProductSurfaceElevation = "flat" | "low" | "floating";

export interface ProductSurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  elevation?: ProductSurfaceElevation;
  className?: string;
}

export const ProductSurface = forwardRef<HTMLDivElement, ProductSurfaceProps>(
  ({ children, elevation = "floating", className = "", ...rest }, ref) => {
    const elevationClasses = {
      flat: "shadow-none border border-[#E3E8EF] bg-white",
      low: "shadow-md sm:shadow-lg border border-[#E3E8EF] bg-white",
      floating: "shadow-2xl border border-[#E3E8EF]/90 bg-white",
    }[elevation];

    return (
      <div
        ref={ref}
        data-elevation={elevation}
        className={`clara-product-surface relative overflow-hidden rounded-2xl md:rounded-3xl ${elevationClasses} ${className}`}
        {...rest}
      >
        {children}
      </div>
    );
  }
);

ProductSurface.displayName = "ProductSurface";
