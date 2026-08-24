"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";

export interface RevealGroupProps {
  children: React.ReactNode;
  delayMs?: number;
  className?: string;
  stagger?: boolean;
}

export function RevealGroup({
  children,
  delayMs = 0,
  className = "",
  stagger = false,
}: RevealGroupProps) {
  const { isReducedMotion } = useMotionTier();

  if (isReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div
      className={`transition-all duration-500 ease-out ${className}`}
      style={{
        transitionDelay: `${delayMs}ms`,
        animationFillMode: "both",
      }}
    >
      {children}
    </div>
  );
}
