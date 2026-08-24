"use client";

import type { ReactNode } from "react";
import { ShellLayoutContext } from "@/components/shell/shell-context";

export default function ProfessionalRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <ShellLayoutContext.Provider value="professional">
      {children}
    </ShellLayoutContext.Provider>
  );
}
