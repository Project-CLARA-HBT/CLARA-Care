"use client";

import { useEffect, useState } from "react";

/**
 * `prefers-reduced-motion` integration for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Centralizes the media-query read so motion-sensitive surfaces (auto-scroll,
 * streaming affordances, decorative transitions) share one source of truth and
 * react when the OS preference changes at runtime (Requirement 4.5, 5.5).
 *
 * SSR/test safe: when `window`/`matchMedia` is unavailable it reports `false`
 * (motion allowed) so server renders and jsdom tests never throw.
 */

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** One-shot, non-reactive read. Safe to call during SSR or in event handlers. */
export function getPrefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * Reactive hook: returns `true` when the user has asked for reduced motion and
 * updates if the preference changes while the chat is open.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(getPrefersReducedMotion);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia(REDUCED_MOTION_QUERY);
    const onChange = () => setReduced(mql.matches);
    // Sync immediately in case the preference changed before the listener bound.
    onChange();
    // `addEventListener` is the modern API; fall back to the deprecated
    // `addListener` for older Safari/JSDOM shims that only expose that.
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    mql.addListener(onChange);
    return () => mql.removeListener(onChange);
  }, []);

  return reduced;
}
