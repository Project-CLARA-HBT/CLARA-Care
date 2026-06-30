"use client";

import { useEffect, type RefObject } from "react";

/**
 * Keyboard focus trap for the rebuilt CLARA Chat (CHAT_V2) modal surfaces —
 * drawers, the workspace panel, and the command palette (Requirement 5.1, 5.4).
 *
 * While active, Tab / Shift+Tab cycle only through the focusable elements inside
 * the trap container (wrap-around), and any focus that escapes the container is
 * pulled back in. This complements (does NOT replace) the per-component initial
 * focus + focus-restore logic: callers still move focus into the surface on open
 * and restore it on close; this hook keeps focus contained while it is open.
 *
 * SSR/test safe: it is a no-op when inactive or before the container mounts.
 */

/** CSS selector matching the natively focusable / tabbable elements. */
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "button:not([disabled])",
  "iframe",
  "object",
  "embed",
  "[contenteditable]:not([contenteditable='false'])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/** Returns the visible, tabbable elements inside `container`, in DOM order. */
export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => {
    if (el.hasAttribute("disabled")) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    if (el.hasAttribute("hidden")) return false;
    // Skip elements hidden via inline styles. We intentionally avoid relying on
    // layout APIs (`offsetParent` / `getClientRects`) so the helper behaves the
    // same under jsdom, where layout is not computed. Inactive tab panels and
    // closed surfaces are removed from the DOM rather than hidden, so this is
    // sufficient for the v2 modal surfaces.
    if (el.style.display === "none" || el.style.visibility === "hidden") {
      return false;
    }
    return true;
  });
}

/**
 * Trap Tab focus within `containerRef` while `active` is true.
 *
 * @param active        Whether the trap is engaged (the surface is open).
 * @param containerRef  Ref to the element that owns the trapped subtree.
 */
export function useFocusTrap(
  active: boolean,
  containerRef: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const focusable = getFocusableElements(container);
      if (focusable.length === 0) {
        // Nothing tabbable inside: keep focus pinned to the container itself.
        event.preventDefault();
        container.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;

      // Focus escaped the trap (e.g. landed on the page behind): pull it back.
      if (!activeEl || !container.contains(activeEl)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && activeEl === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeEl === last) {
        event.preventDefault();
        first.focus();
      }
    };

    container.addEventListener("keydown", onKeyDown);
    return () => container.removeEventListener("keydown", onKeyDown);
  }, [active, containerRef]);
}
