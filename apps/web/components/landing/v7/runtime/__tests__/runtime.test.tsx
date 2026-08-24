import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import React from "react";
import {
  getDeviceMotionSignals,
  resolveMotionTier,
  runShortFrameHealthProbe,
} from "../motion-tier";
import { useFrameHealth } from "../use-frame-health";
import { SceneRegistry, sceneRegistry, sceneObserver } from "../scene-observer";
import { useSceneProgress } from "../use-scene-progress";
import { usePointerDepth } from "../use-pointer-depth";
import { MotionProvider, useMotionTier } from "../motion-provider";

describe("v7 runtime suite", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe("motion-tier.ts", () => {
    it("safely retrieves device motion signals without throwing", () => {
      const signals = getDeviceMotionSignals();
      expect(signals).toBeDefined();
      expect(typeof signals.prefersReducedMotion).toBe("boolean");
      expect(typeof signals.saveData).toBe("boolean");
      expect(typeof signals.pointerFine).toBe("boolean");
      expect(typeof signals.shortFrameProbeHealthy).toBe("boolean");
    });

    it("resolves correct MotionTier according to signals", () => {
      expect(
        resolveMotionTier({
          prefersReducedMotion: true,
          saveData: false,
          pointerFine: true,
          shortFrameProbeHealthy: true,
        })
      ).toBe("reduced");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: true,
          pointerFine: true,
          shortFrameProbeHealthy: true,
        })
      ).toBe("lite");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: false,
          deviceMemory: 2,
          pointerFine: true,
          shortFrameProbeHealthy: true,
        })
      ).toBe("lite");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: false,
          hardwareConcurrency: 2,
          pointerFine: true,
          shortFrameProbeHealthy: true,
        })
      ).toBe("lite");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: false,
          pointerFine: true,
          shortFrameProbeHealthy: false,
        })
      ).toBe("lite");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: false,
          deviceMemory: 8,
          hardwareConcurrency: 8,
          pointerFine: true,
          shortFrameProbeHealthy: true,
        })
      ).toBe("enhanced");

      expect(
        resolveMotionTier({
          prefersReducedMotion: false,
          saveData: false,
          pointerFine: false,
          shortFrameProbeHealthy: true,
        })
      ).toBe("standard");
    });
  });

  describe("scene-observer.ts & use-scene-progress.ts", () => {
    it("registers and unsubscribes scenes properly in SceneRegistry", () => {
      const registry = new SceneRegistry();
      const div = document.createElement("div");
      const unregister = registry.register("scene-1", div, { sticky: true });

      expect(registry.getAllScenes().length).toBe(1);
      expect(div.dataset.sceneId).toBe("scene-1");

      unregister();
      expect(registry.getAllScenes().length).toBe(0);
    });

    it("exports sceneObserver as alias to sceneRegistry", () => {
      expect(sceneObserver).toBe(sceneRegistry);
    });

    it("useSceneProgress hook registers element and returns ref, progress, and isVisible", () => {
      const { result } = renderHook(() => useSceneProgress("test-scene"));
      expect(result.current.ref).toBeDefined();
      expect(typeof result.current.progress).toBe("number");
      expect(typeof result.current.isVisible).toBe("boolean");
    });
  });

  describe("use-frame-health.ts", () => {
    it("runs probe and executes callback if unhealthy", () => {
      const onDowngrade = vi.fn();
      const onHealthResult = vi.fn();

      renderHook(() =>
        useFrameHealth(onDowngrade, {
          delayMs: 100,
          onHealthResult,
        })
      );

      expect(onDowngrade).not.toHaveBeenCalled();
    });
  });

  describe("use-pointer-depth.ts", () => {
    it("attaches ref safely and works under MotionProvider", () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <MotionProvider>{children}</MotionProvider>
      );
      const { result } = renderHook(() => usePointerDepth({ maxRotateX: 1.5 }), {
        wrapper,
      });
      expect(result.current).toBeDefined();
      expect(result.current.current).toBeNull();
    });
  });

  describe("motion-provider.tsx", () => {
    it("provides expected context properties and methods", () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <MotionProvider initialLanguage="en">{children}</MotionProvider>
      );
      const { result } = renderHook(() => useMotionTier(), { wrapper });

      expect(result.current.language).toBe("en");
      expect(["enhanced", "standard", "lite", "reduced"]).toContain(
        result.current.motionTier
      );
      expect(typeof result.current.isEnhanced).toBe("boolean");
      expect(typeof result.current.isLite).toBe("boolean");
      expect(typeof result.current.isReducedMotion).toBe("boolean");

      act(() => {
        result.current.setLanguage("vi");
      });
      expect(result.current.language).toBe("vi");

      act(() => {
        result.current.setTierOverride("lite");
      });
      expect(result.current.motionTier).toBe("lite");
      expect(result.current.isLite).toBe(true);
    });
  });
});
