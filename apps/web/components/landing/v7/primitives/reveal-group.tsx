"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";

export interface RevealGroupProps {
  children: React.ReactNode;
  staggerMs?: number;
  className?: string;
}

export function RevealGroup({
  children,
  staggerMs = 80,
  className = "",
}: RevealGroupProps) {
  const { isReducedMotion } = useMotionTier();

  if (isReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div
      className={className}
      style={{
        // Custom CSS property for CSS staggered transitions if desired
        ["--stagger-delay" as string]: `${staggerMs}ms`,
      }}
    >
      {children}
    </div>
  );
}
