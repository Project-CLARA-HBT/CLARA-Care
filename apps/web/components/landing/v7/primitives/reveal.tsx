"use client";

import React, { forwardRef, useEffect, useRef, useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";

export type RevealDirection = "up" | "fade" | "scale";

export interface RevealProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  delayMs?: number;
  direction?: RevealDirection;
  className?: string;
}

export const Reveal = forwardRef<HTMLDivElement, RevealProps>(
  (
    {
      children,
      delayMs = 0,
      direction = "up",
      className = "",
      style,
      ...rest
    },
    forwardedRef
  ) => {
    const { isReducedMotion } = useMotionTier();
    const [isVisible, setIsVisible] = useState(false);
    const internalRef = useRef<HTMLDivElement>(null);

    const setRef = (node: HTMLDivElement | null) => {
      (internalRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }
    };

    useEffect(() => {
      if (isReducedMotion) {
        setIsVisible(true);
        return;
      }

      const el = internalRef.current;
      if (!el) return;

      if (typeof IntersectionObserver === "undefined") {
        setIsVisible(true);
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setIsVisible(true);
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
      );

      observer.observe(el);

      return () => {
        observer.disconnect();
      };
    }, [isReducedMotion]);

    if (isReducedMotion) {
      return (
        <div ref={setRef} className={className} style={style} {...rest}>
          {children}
        </div>
      );
    }

    const directionHiddenClass = {
      up: "opacity-0 translate-y-6",
      fade: "opacity-0",
      scale: "opacity-0 scale-95",
    }[direction];

    const visibleClass = isVisible
      ? "opacity-100 translate-y-0 scale-100"
      : directionHiddenClass;

    return (
      <div
        ref={setRef}
        data-reveal-direction={direction}
        data-visible={isVisible}
        style={{
          transitionDelay: `${delayMs}ms`,
          ...style,
        }}
        className={`transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none motion-reduce:transform-none ${visibleClass} ${className}`}
        {...rest}
      >
        {children}
      </div>
    );
  }
);

Reveal.displayName = "Reveal";
