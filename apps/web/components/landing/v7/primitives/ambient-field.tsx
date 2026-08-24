"use client";

import React, { forwardRef } from "react";

export type AmbientTone = "azure" | "mint" | "iris" | "multi";

export interface AmbientFieldProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: AmbientTone;
  className?: string;
}

export const AmbientField = forwardRef<HTMLDivElement, AmbientFieldProps>(
  ({ tone = "azure", className = "", ...rest }, ref) => {
    const toneClass = {
      azure: "clara-ambient-azure",
      mint: "clara-ambient-mint",
      iris: "clara-ambient-iris",
      multi: "clara-ambient-multi",
    }[tone];

    return (
      <div
        ref={ref}
        aria-hidden="true"
        data-ambient-tone={tone}
        className={`pointer-events-none absolute inset-0 -z-10 transition-opacity duration-700 ${toneClass} ${className}`}
        {...rest}
      />
    );
  }
);

AmbientField.displayName = "AmbientField";
