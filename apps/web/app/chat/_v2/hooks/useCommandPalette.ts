"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * Command-palette state + filtering for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Keyboard-first parity actions (Requirement 5.1, 6.3). The `filterCommands`
 * helper is a pure, exported function so the matching logic can be unit/property
 * tested without React.
 */

export type CommandAction = {
  id: string;
  label: string;
  hint?: string;
  keywords: string[];
  disabled?: boolean;
  run: () => void;
};

/** Pure: filter command actions by a free-text query (case-insensitive). */
export function filterCommands(actions: CommandAction[], query: string): CommandAction[] {
  const keyword = query.trim().toLowerCase();
  if (!keyword) return actions;
  return actions.filter((action) => {
    const haystack = [action.label, action.hint ?? "", ...action.keywords]
      .join(" ")
      .toLowerCase();
    return haystack.includes(keyword);
  });
}

/**
 * Pure: wrap an index into `[0, length)` with arrow-key style wrap-around.
 * Returns 0 for an empty list so callers never index out of bounds.
 */
export function wrapIndex(index: number, length: number): number {
  if (length <= 0) return 0;
  return ((index % length) + length) % length;
}

export type UseCommandPalette = {
  isOpen: boolean;
  query: string;
  filtered: CommandAction[];
  /** Index of the keyboard-highlighted action within `filtered`. */
  activeIndex: number;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setQuery: (value: string) => void;
  setActiveIndex: (index: number) => void;
  /** Move the highlight by `delta` rows (wraps around the filtered list). */
  moveActive: (delta: number) => void;
  execute: (action: CommandAction) => void;
  /** Execute the currently highlighted action (skips when disabled). */
  executeActive: () => void;
  executeFirst: () => void;
};

export function useCommandPalette(actions: CommandAction[]): UseCommandPalette {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQueryState] = useState("");
  const [activeIndex, setActiveIndexState] = useState(0);

  const filtered = useMemo(() => filterCommands(actions, query), [actions, query]);

  const close = useCallback(() => {
    setIsOpen(false);
    setQueryState("");
    setActiveIndexState(0);
  }, []);

  const open = useCallback(() => {
    setIsOpen(true);
    setActiveIndexState(0);
  }, []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  // Typing re-filters the list, so the highlight returns to the top to keep
  // keyboard navigation predictable (Requirement 5.1).
  const setQuery = useCallback((value: string) => {
    setQueryState(value);
    setActiveIndexState(0);
  }, []);

  const setActiveIndex = useCallback((index: number) => {
    setActiveIndexState((prev) => (Number.isFinite(index) ? index : prev));
  }, []);

  const moveActive = useCallback(
    (delta: number) => {
      setActiveIndexState((prev) => wrapIndex(prev + delta, filtered.length));
    },
    [filtered.length]
  );

  const execute = useCallback(
    (action: CommandAction) => {
      if (action.disabled) return;
      action.run();
      close();
    },
    [close]
  );

  const executeActive = useCallback(() => {
    const action = filtered[wrapIndex(activeIndex, filtered.length)];
    if (action) execute(action);
  }, [activeIndex, execute, filtered]);

  const executeFirst = useCallback(() => {
    const first = filtered.find((action) => !action.disabled);
    if (first) execute(first);
  }, [execute, filtered]);

  // Global Escape closes the palette while it is open.
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close, isOpen]);

  return {
    isOpen,
    query,
    filtered,
    activeIndex,
    open,
    close,
    toggle,
    setQuery,
    setActiveIndex,
    moveActive,
    execute,
    executeActive,
    executeFirst,
  };
}
