"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import type { UILanguage } from "@/lib/ui-language";
import {
  type MotionTier,
  getDeviceMotionSignals,
  resolveMotionTier,
  runShortFrameHealthProbe,
} from "./motion-tier";
import { sceneRegistry } from "./scene-registry";
import { scrollCoordinator } from "./scroll-coordinator";

interface MotionContextValue {
  motionTier: MotionTier;
  isReducedMotion: boolean;
  isLite: boolean;
  isEnhanced: boolean;
  activeSceneId: string | null;
  language: UILanguage;
  setLanguage: (lang: UILanguage) => void;
  setTierOverride: (tier: MotionTier | null) => void;
}

const MotionContext = createContext<MotionContextValue | null>(null);

export interface MotionProviderProps {
  children: React.ReactNode;
  initialLanguage?: UILanguage;
}

export function MotionProvider({ children, initialLanguage = "vi" }: MotionProviderProps) {
  const [tierOverride, setTierOverride] = useState<MotionTier | null>(null);
  const [signals, setSignals] = useState(() => getDeviceMotionSignals());
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [language, setLanguageState] = useState<UILanguage>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("clara_ui_language");
      if (saved === "vi" || saved === "en") return saved;
    }
    return initialLanguage;
  });

  const setLanguage = (lang: UILanguage) => {
    setLanguageState(lang);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("clara_ui_language", lang);
        document.documentElement.lang = lang;
      } catch {
        // Safe ignore
      }
    }
  };

  useEffect(() => {
    // Start scroll coordinator on mount
    scrollCoordinator.start();

    // Subscribe to active scene changes
    const unsubScene = sceneRegistry.subscribeActiveScene((id) => {
      setActiveSceneId(id);
    });

    // Listen for reduced motion preference changes
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handlePrefChange = (e: MediaQueryListEvent) => {
      setSignals((prev) => ({ ...prev, prefersReducedMotion: e.matches }));
    };
    mediaQuery.addEventListener("change", handlePrefChange);

    // Run short frame-health probe after 400ms to avoid checking during initial paint
    const probeTimer = setTimeout(() => {
      const stopProbe = runShortFrameHealthProbe((healthy) => {
        if (!healthy) {
          setSignals((prev) => ({ ...prev, shortFrameProbeHealthy: false }));
        }
      });

      return () => {
        stopProbe();
      };
    }, 400);

    return () => {
      clearTimeout(probeTimer);
      mediaQuery.removeEventListener("change", handlePrefChange);
      unsubScene();
      scrollCoordinator.stop();
    };
  }, []);

  const computedTier = tierOverride ?? resolveMotionTier(signals);

  const value: MotionContextValue = {
    motionTier: computedTier,
    isReducedMotion: computedTier === "reduced",
    isLite: computedTier === "lite",
    isEnhanced: computedTier === "enhanced",
    activeSceneId,
    language,
    setLanguage,
    setTierOverride,
  };

  return <MotionContext.Provider value={value}>{children}</MotionContext.Provider>;
}

export function useMotionTier(): MotionContextValue {
  const context = useContext(MotionContext);
  if (!context) {
    throw new Error("useMotionTier must be used within a MotionProvider");
  }
  return context;
}
