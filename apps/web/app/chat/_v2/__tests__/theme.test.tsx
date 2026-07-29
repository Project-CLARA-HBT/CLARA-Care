import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import {
  getPrefersReducedMotion,
  usePrefersReducedMotion,
} from "@/app/chat/_v2/theme/usePrefersReducedMotion";
import {
  getResolvedTheme,
  useResolvedTheme,
} from "@/app/chat/_v2/theme/useResolvedTheme";

/**
 * Feature: clara-chat-redesign — Task 3.2 theme integration.
 *
 * Requirement 4.5 / 5.5: the chat honours `prefers-reduced-motion` and reacts
 * when it changes at runtime.
 * Requirement 4.2: light/dark stays consistent with the rest of the app by
 * observing the same `<html>` theme signal the shared token layer keys off.
 */

/** Build a controllable `matchMedia` stub for a single query result. */
function installMatchMedia(initialMatches: boolean) {
  const listeners = new Set<() => void>();
  const mql = {
    matches: initialMatches,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: (_: string, cb: () => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: () => void) => listeners.delete(cb),
    addListener: (cb: () => void) => listeners.add(cb),
    removeListener: (cb: () => void) => listeners.delete(cb),
    dispatchEvent: () => true,
  };
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => mql),
  );
  return {
    setMatches(next: boolean) {
      mql.matches = next;
      listeners.forEach((cb) => cb());
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
  document.documentElement.removeAttribute("data-theme");
});

describe("usePrefersReducedMotion", () => {
  it("getPrefersReducedMotion returns false when matchMedia is unavailable", () => {
    // jsdom does not implement matchMedia by default.
    expect(getPrefersReducedMotion()).toBe(false);
  });

  it("reports the initial preference and reacts to runtime changes", async () => {
    const media = installMatchMedia(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);

    act(() => media.setMatches(false));
    await waitFor(() => expect(result.current).toBe(false));
  });
});

describe("useResolvedTheme", () => {
  it("getResolvedTheme reads the <html> dark signal", () => {
    expect(getResolvedTheme()).toBe("light");
    document.documentElement.setAttribute("data-theme", "dark");
    expect(getResolvedTheme()).toBe("dark");
  });

  it("re-renders when the app toggles the theme on <html>", async () => {
    const { result, unmount } = renderHook(() => useResolvedTheme());
    expect(result.current).toBe("light");

    await act(async () => {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current).toBe("dark"));

    await act(async () => {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", "light");
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current).toBe("light"));
    unmount();
  });
});
