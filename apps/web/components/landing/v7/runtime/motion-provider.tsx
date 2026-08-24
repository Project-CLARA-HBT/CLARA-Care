"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import type { UILanguage } from "@/lib/ui-language";
import {
  type MotionTier,
  getDeviceMotionSignals,
  resolveMotionTier,
} from "./motion-tier";
import { useFrameHealth } from "./use-frame-health";
import { sceneRegistry } from "./scene-observer";
import { scrollCoordinator } from "./scroll-coordinator";

export interface MotionContextValue {
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
      try {
        const saved = localStorage.getItem("clara_ui_language");
        if (saved === "vi" || saved === "en") return saved;
      } catch {
        // Safe ignore
      }
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

  // Observe frame health in initial window and downgrade on sluggish rate
  useFrameHealth(() => {
    setSignals((prev) => ({ ...prev, shortFrameProbeHealthy: false }));
  });

  useEffect(() => {
    // Start scroll coordinator on mount
    scrollCoordinator.start();

    // Subscribe to active scene changes
    const unsubScene = sceneRegistry.subscribeActiveScene((id) => {
      setActiveSceneId(id);
    });

    // Listen for reduced motion preference changes
    let cleanupMediaQuery: (() => void) | undefined;
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      const handlePrefChange = (e: MediaQueryListEvent) => {
        setSignals((prev) => ({ ...prev, prefersReducedMotion: e.matches }));
      };
      mediaQuery.addEventListener?.("change", handlePrefChange);
      cleanupMediaQuery = () => {
        mediaQuery.removeEventListener?.("change", handlePrefChange);
      };
    }

    return () => {
      cleanupMediaQuery?.();
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
