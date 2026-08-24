"use client";

import React, { forwardRef } from "react";
import { useSceneProgress } from "../runtime/use-scene-progress";

export type LandingSceneScale = "transition" | "standard" | "signature";
export type LandingTone = "canvas" | "azure" | "mint" | "iris" | "neutral";

export interface LandingSceneProps extends React.HTMLAttributes<HTMLElement> {
  id: string;
  scale?: LandingSceneScale;
  tone?: LandingTone;
  sticky?: boolean;
  children: React.ReactNode;
  className?: string;
  containerClassName?: string;
}

export const LandingScene = forwardRef<HTMLElement, LandingSceneProps>(
  (
    {
      id,
      scale = "standard",
      tone = "canvas",
      sticky = false,
      children,
      className = "",
      containerClassName = "",
      ...rest
    },
    forwardedRef
  ) => {
    const { ref: internalRef, progress } = useSceneProgress<HTMLElement>(id, { sticky });

    // Set merged ref
    const setRef = (node: HTMLElement | null) => {
      (internalRef as React.MutableRefObject<HTMLElement | null>).current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        (forwardedRef as React.MutableRefObject<HTMLElement | null>).current = node;
      }
    };

    const scaleClasses = {
      transition: "py-16 md:py-24",
      standard: "py-24 md:py-32",
      signature: "py-28 md:py-40",
    }[scale];

    const toneClasses = {
      canvas: "bg-transparent",
      azure: "clara-ambient-azure",
      mint: "clara-ambient-mint",
      iris: "clara-ambient-iris",
      neutral: "bg-[#F1F5F9]/50",
    }[tone];

    return (
      <section
        id={id}
        ref={setRef}
        data-scene-id={id}
        data-scene-scale={scale}
        data-scene-tone={tone}
        className={`relative w-full ${scaleClasses} ${toneClasses} ${className}`}
        {...rest}
      >
        <div className={`mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 ${containerClassName}`}>
          {children}
        </div>
      </section>
    );
  }
);

LandingScene.displayName = "LandingScene";
