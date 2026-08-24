"use client";

import type { ReactNode } from "react";
import { ShellLayoutContext } from "@/components/shell/shell-context";

export default function PublicRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <ShellLayoutContext.Provider value="public">
      <main
        id="main-content"
        className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      >
        {children}
      </main>
    </ShellLayoutContext.Provider>
  );
}
