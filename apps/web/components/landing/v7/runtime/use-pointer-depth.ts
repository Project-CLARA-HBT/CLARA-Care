import { useEffect, useRef } from "react";
import { useMotionTier } from "./motion-provider";

export interface PointerDepthOptions {
  maxRotateX?: number; // default 1.8deg, capped at 1.8deg
  maxRotateY?: number; // default 1.8deg, capped at 1.8deg
  maxTranslate?: number; // default 4px, capped at 4px
  disabled?: boolean;
}

export function usePointerDepth<T extends HTMLElement = HTMLElement>(
  options: PointerDepthOptions = {}
): React.RefObject<T> {
  const ref = useRef<T>(null);
  const { motionTier } = useMotionTier();
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Subtle 2.5D bounded pointer tilt for Enhanced tier only
    if (motionTier !== "enhanced" || options.disabled) {
      el.style.transform = "";
      return;
    }

    let rect: DOMRect | null = null;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;
    let rafId: number | null = null;
    let isHovering = false;

    // Hard bounded <= 1.8deg, <= 4px
    const maxRotX = Math.min(Math.max(optionsRef.current.maxRotateX ?? 1.8, 0), 1.8);
    const maxRotY = Math.min(Math.max(optionsRef.current.maxRotateY ?? 1.8, 0), 1.8);
    const maxTrans = Math.min(Math.max(optionsRef.current.maxTranslate ?? 4, 0), 4);

    const updateTransform = () => {
      // Linear interpolation (ease towards target)
      currentX += (targetX - currentX) * 0.12;
      currentY += (targetY - currentY) * 0.12;

      const rotX = -currentY * maxRotX;
      const rotY = currentX * maxRotY;
      const transX = currentX * maxTrans;
      const transY = currentY * maxTrans;

      el.style.transform = `perspective(1400px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) translate3d(${transX.toFixed(1)}px, ${transY.toFixed(1)}px, 0px)`;

      // Continue loop if still hovering or still settling
      const isSettled =
        Math.abs(targetX - currentX) < 0.005 && Math.abs(targetY - currentY) < 0.005;

      if (isHovering || !isSettled) {
        rafId = requestAnimationFrame(updateTransform);
      } else {
        rafId = null;
        if (!isHovering) {
          el.style.transform = "";
        }
      }
    };

    const handleMouseEnter = () => {
      rect = el.getBoundingClientRect();
      isHovering = true;
      if (rafId === null) {
        rafId = requestAnimationFrame(updateTransform);
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!rect) {
        rect = el.getBoundingClientRect();
      }
      const width = rect.width || 1;
      const height = rect.height || 1;
      const x = (e.clientX - rect.left) / width; // 0 to 1
      const y = (e.clientY - rect.top) / height; // 0 to 1

      // Normalize to -1 to +1
      targetX = Math.max(Math.min((x - 0.5) * 2, 1), -1);
      targetY = Math.max(Math.min((y - 0.5) * 2, 1), -1);

      if (rafId === null) {
        rafId = requestAnimationFrame(updateTransform);
      }
    };

    const handleMouseLeave = () => {
      isHovering = false;
      targetX = 0;
      targetY = 0;
      rect = null;
      if (rafId === null) {
        rafId = requestAnimationFrame(updateTransform);
      }
    };

    el.addEventListener("mouseenter", handleMouseEnter);
    el.addEventListener("mousemove", handleMouseMove, { passive: true });
    el.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      el.removeEventListener("mouseenter", handleMouseEnter);
      el.removeEventListener("mousemove", handleMouseMove);
      el.removeEventListener("mouseleave", handleMouseLeave);
      if (rafId !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(rafId);
      }
      el.style.transform = "";
    };
  }, [motionTier, options.disabled]);

  return ref;
}
