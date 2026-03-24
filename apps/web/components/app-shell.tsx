"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";

type Props = {
  children: ReactNode;
};

const HIDE_SIDEBAR_ROUTES = new Set(["/", "/huong-dan", "/login", "/register", "/role-select"]);

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const hideSidebar = HIDE_SIDEBAR_ROUTES.has(pathname);

  if (hideSidebar) {
    return <main className="min-h-screen bg-slate-50">{children}</main>;
  }

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <SidebarNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
