"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useShellMode } from "./shell-mode-provider";
import type { PaletteAction } from "./command-palette";

export interface CommandPaletteContextValue {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;
  customActions: PaletteAction[];
  registerActions: (actions: PaletteAction[]) => () => void;
}

export const CommandPaletteContext =
  createContext<CommandPaletteContextValue | null>(null);

export interface CommandPaletteProviderProps {
  children: ReactNode;
  initialOpen?: boolean;
}

export function CommandPaletteProvider({
  children,
  initialOpen = false,
}: CommandPaletteProviderProps) {
  const shellMode = useShellMode();
  const [localOpen, setLocalOpen] = useState(initialOpen);
  const [customActions, setCustomActions] = useState<PaletteAction[]>([]);

  // Prefer ShellModeContext state if wrapped, otherwise local state
  const isOpen = shellMode.isCommandPaletteOpen ?? localOpen;

  const setIsOpen = useCallback(
    (open: boolean) => {
      setLocalOpen(open);
      shellMode.setCommandPaletteOpen(open);
    },
    [shellMode],
  );

  const openPalette = useCallback(() => {
    setLocalOpen(true);
    shellMode.openCommandPalette();
  }, [shellMode]);

  const closePalette = useCallback(() => {
    setLocalOpen(false);
    shellMode.closeCommandPalette();
  }, [shellMode]);

  const togglePalette = useCallback(() => {
    setLocalOpen((prev) => !prev);
    shellMode.toggleCommandPalette();
  }, [shellMode]);

  const registerActions = useCallback((newActions: PaletteAction[]) => {
    setCustomActions((prev) => [...prev, ...newActions]);
    return () => {
      setCustomActions((prev) =>
        prev.filter((a) => !newActions.some((na) => na.id === a.id)),
      );
    };
  }, []);

  const value = useMemo<CommandPaletteContextValue>(
    () => ({
      isOpen,
      setIsOpen,
      openPalette,
      closePalette,
      togglePalette,
      customActions,
      registerActions,
    }),
    [
      isOpen,
      setIsOpen,
      openPalette,
      closePalette,
      togglePalette,
      customActions,
      registerActions,
    ],
  );

  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
    </CommandPaletteContext.Provider>
  );
}

const DEFAULT_COMMAND_PALETTE_VALUE: CommandPaletteContextValue = {
  isOpen: false,
  setIsOpen: () => {},
  openPalette: () => {},
  closePalette: () => {},
  togglePalette: () => {},
  customActions: [],
  registerActions: () => () => {},
};

export function useCommandPaletteContext(): CommandPaletteContextValue {
  const context = useContext(CommandPaletteContext);
  if (!context) {
    return DEFAULT_COMMAND_PALETTE_VALUE;
  }
  return context;
}

export default CommandPaletteProvider;
