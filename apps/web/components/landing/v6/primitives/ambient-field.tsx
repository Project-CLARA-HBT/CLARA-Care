"use client";

import React from "react";

export interface AmbientFieldProps {
  tone?: "azure" | "mint" | "iris" | "multi";
  className?: string;
}

export function AmbientField({ tone = "azure", className = "" }: AmbientFieldProps) {
  const gradientStyles = {
    azure:
      "radial-gradient(circle 600px at 50% 50%, rgba(11, 111, 216, 0.05), transparent 70%)",
    mint:
      "radial-gradient(circle 600px at 50% 50%, rgba(20, 168, 141, 0.05), transparent 70%)",
    iris:
      "radial-gradient(circle 600px at 50% 50%, rgba(139, 124, 246, 0.05), transparent 70%)",
    multi:
      "radial-gradient(circle 450px at 20% 30%, rgba(11, 111, 216, 0.04), transparent 60%), radial-gradient(circle 450px at 80% 70%, rgba(20, 168, 141, 0.04), transparent 60%)",
  }[tone];

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 z-0 overflow-hidden ${className}`}
      style={{ background: gradientStyles }}
    />
  );
}
