export type MotionTier = "enhanced" | "standard" | "lite" | "reduced";

export interface MotionTierSignals {
  prefersReducedMotion: boolean;
  saveData: boolean;
  deviceMemory?: number;
  hardwareConcurrency?: number;
  pointerFine: boolean;
  shortFrameProbeHealthy: boolean;
}

export function getDeviceMotionSignals(): MotionTierSignals {
  if (typeof window === "undefined") {
    return {
      prefersReducedMotion: false,
      saveData: false,
      pointerFine: true,
      shortFrameProbeHealthy: true,
    };
  }

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pointerFine = window.matchMedia("(pointer: fine)").matches;

  // Safe access to experimental/non-standard navigator properties
  const nav = navigator as unknown as {
    connection?: { saveData?: boolean };
    deviceMemory?: number;
    hardwareConcurrency?: number;
  };

  const saveData = Boolean(nav.connection?.saveData);
  const deviceMemory = typeof nav.deviceMemory === "number" ? nav.deviceMemory : undefined;
  const hardwareConcurrency =
    typeof nav.hardwareConcurrency === "number" ? nav.hardwareConcurrency : undefined;

  return {
    prefersReducedMotion,
    saveData,
    deviceMemory,
    hardwareConcurrency,
    pointerFine,
    shortFrameProbeHealthy: true,
  };
}

export function resolveMotionTier(signals: MotionTierSignals): MotionTier {
  if (signals.prefersReducedMotion) {
    return "reduced";
  }

  // Constrained hardware conditions trigger Lite tier
  if (signals.saveData) {
    return "lite";
  }
  if (typeof signals.deviceMemory === "number" && signals.deviceMemory <= 4) {
    return "lite";
  }
  if (typeof signals.hardwareConcurrency === "number" && signals.hardwareConcurrency <= 4) {
    return "lite";
  }
  if (!signals.shortFrameProbeHealthy) {
    return "lite";
  }

  // Enhanced tier: Desktop fine pointer with healthy resources
  if (
    signals.pointerFine &&
    !signals.saveData &&
    (signals.deviceMemory === undefined || signals.deviceMemory > 4) &&
    (signals.hardwareConcurrency === undefined || signals.hardwareConcurrency > 4) &&
    signals.shortFrameProbeHealthy
  ) {
    return "enhanced";
  }

  return "standard";
}

/**
 * Short Frame-Health Probe:
 * Measures natural frame intervals for ~600ms after load.
 * If >20% of frames exceed 33ms (dropped below ~30fps) on idle/basic scroll, flags downgrade.
 * Automatically stops measuring after the probe completes.
 */
export function runShortFrameHealthProbe(onResult: (healthy: boolean) => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  let rafId: number | null = null;
  let lastTime = performance.now();
  let frameCount = 0;
  let slowFrameCount = 0;
  const startTime = performance.now();
  const PROBE_DURATION_MS = 600;

  const probeLoop = (time: number) => {
    const delta = time - lastTime;
    lastTime = time;

    frameCount++;
    if (delta > 33.3) {
      slowFrameCount++;
    }

    if (time - startTime < PROBE_DURATION_MS) {
      rafId = requestAnimationFrame(probeLoop);
    } else {
      // Completed probe: if >25% frames were sluggish, mark unhealthy
      const slowRatio = frameCount > 0 ? slowFrameCount / frameCount : 0;
      const isHealthy = slowRatio < 0.25;
      onResult(isHealthy);
    }
  };

  rafId = requestAnimationFrame(probeLoop);

  return () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
  };
}
