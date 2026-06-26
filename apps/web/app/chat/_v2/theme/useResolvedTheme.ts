"use client";

import { useEffect, useState } from "react";

import type { ResolvedTheme } from "@/lib/theme";

/**
 * Light/dark theme integration for the rebuilt CLARA Chat (CHAT_V2).
 *
 * The app owns theme application in `lib/theme.ts`, which writes a `dark` class
 * and `data-theme` attribute onto `<html>`; the global token layer
 * (`styles/globals.css`) swaps every `--*` design token off those signals. The
 * chat shell therefore inherits light/dark automatically through tokens
 * (Requirement 4.1, 4.2) and must NOT own its own theme store.
 *
 * This hook simply observes that same `<html>` signal so v2 components that need
 * JS-level theme awareness (e.g. choosing an asset or aria description) stay in
 * lockstep with the rest of the app rather than forking a second source of
 * truth. SSR/test safe: defaults to `"light"` when no document is present.
 */

/** One-shot, non-reactive read of the currently applied theme. */
export function getResolvedTheme(): ResolvedTheme {
  if (typeof document === "undefined") {
    return "light";
  }
  const root = document.documentElement;
  const isDark =
    root.classList.contains("dark") || root.getAttribute("data-theme") === "dark";
  return isDark ? "dark" : "light";
}

/**
 * Reactive hook: returns the resolved theme and re-renders when the app toggles
 * it (via the `<html>` class / `data-theme` attribute).
 */
export function useResolvedTheme(): ResolvedTheme {
  const [theme, setTheme] = useState<ResolvedTheme>(getResolvedTheme);

  useEffect(() => {
    if (typeof document === "undefined" || typeof MutationObserver === "undefined") {
      return;
    }
    const root = document.documentElement;
    const update = () => setTheme(getResolvedTheme());
    // Reconcile in case the theme changed between first render and effect.
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });
    return () => observer.disconnect();
  }, []);

  return theme;
}
