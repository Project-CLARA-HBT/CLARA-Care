"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import { getRole } from "@/lib/auth-store";
import { getPageMeta, isPublicRoute, type UserRole } from "@/lib/navigation.config";

type Props = {
  children: ReactNode;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống",
};

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const [role, setRole] = useState<UserRole>("normal");

  const hideSidebar = isPublicRoute(pathname);

  useEffect(() => {
    setRole(getRole());
  }, [pathname]);

  const currentPage = useMemo(() => getPageMeta(pathname), [pathname]);

  if (hideSidebar) {
    return <main className="min-h-screen bg-[var(--color-bg)]">{children}</main>;
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--text-primary)]">
      <div className="mx-auto flex min-h-screen w-full max-w-[1560px]">
        <SidebarNav role={role} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-[var(--bg-elev-2)] px-4 py-3 backdrop-blur sm:px-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Workspace</p>
                <h1 className="mt-1 text-lg font-semibold text-[var(--text-primary)] sm:text-xl">{currentPage.title}</h1>
                <p className="mt-0.5 text-sm text-slate-600">{currentPage.subtitle}</p>
              </div>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                {ROLE_LABELS[role]}
              </span>
            </div>
          </header>

          <main className="flex-1 p-4 pb-24 sm:p-5 sm:pb-24 lg:p-6 lg:pb-6">
            <div className="mx-auto w-full max-w-[1180px]">{children}</div>
          </main>
        </div>
      </div>

      <MobileBottomNav role={role} />
    </div>
  );
}
