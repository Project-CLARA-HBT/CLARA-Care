import { useEffect } from "react";
import { runShortFrameHealthProbe } from "./motion-tier";

export interface UseFrameHealthOptions {
  onHealthResult?: (healthy: boolean) => void;
  disabled?: boolean;
  delayMs?: number;
}

/**
 * Hook observing RAF health for an initial probe window (e.g. 600ms),
 * triggering a downgrade callback on sluggish frame rates (<30fps drops).
 * Safe on SSR, jsdom, and missing requestAnimationFrame.
 */
export function useFrameHealth(
  onDowngrade?: () => void,
  options: UseFrameHealthOptions = {}
): void {
  const { onHealthResult, disabled = false, delayMs = 400 } = options;

  useEffect(() => {
    if (disabled || typeof window === "undefined") {
      return;
    }

    let cancelProbe: (() => void) | null = null;

    const timer = setTimeout(() => {
      cancelProbe = runShortFrameHealthProbe((healthy) => {
        if (onHealthResult) {
          onHealthResult(healthy);
        }
        if (!healthy && onDowngrade) {
          onDowngrade();
        }
      });
    }, delayMs);

    return () => {
      clearTimeout(timer);
      if (cancelProbe) {
        cancelProbe();
      }
    };
  }, [disabled, delayMs, onDowngrade, onHealthResult]);
}
