"use client";

import { createContext, useContext } from "react";

export type ShellMode = "consumer" | "professional" | "public";

export const ShellLayoutContext = createContext<ShellMode | null>(null);

export function useShellMode(): ShellMode | null {
  return useContext(ShellLayoutContext);
}

export { useShellMode as useShellLayout };
export default ShellLayoutContext;
