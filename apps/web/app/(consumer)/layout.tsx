import type { ReactNode } from "react";
import { ShellLayoutContext } from "@/components/shell/shell-context";

export default function ConsumerRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <ShellLayoutContext.Provider value="consumer">
      {children}
    </ShellLayoutContext.Provider>
  );
}
