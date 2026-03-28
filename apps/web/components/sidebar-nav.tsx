"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getGroupedNavItems, isActiveRoute, type UserRole } from "@/lib/navigation.config";

type SidebarNavProps = {
  role: UserRole;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị",
};

export default function SidebarNav({ role }: SidebarNavProps) {
  const pathname = usePathname();
  const groups = getGroupedNavItems(role);

  return (
    <aside className="sticky top-0 hidden h-screen w-80 shrink-0 border-r border-slate-200/80 bg-white/90 px-4 py-5 backdrop-blur lg:block">
      <div className="glass-card rounded-2xl px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700">CLARA Care</p>
        <div className="mt-2 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">Không gian làm việc</p>
            <p className="text-xs text-slate-500">Trải nghiệm đơn giản, rõ hành động</p>
          </div>
          <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700">
            {ROLE_LABELS[role]}
          </span>
        </div>
      </div>

      {groups.map((group) => (
        <div key={group.key} className="mt-5">
          <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{group.label}</p>
          <nav className="space-y-2">
            {group.items.map((item) => {
              const active = isActiveRoute(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`group block rounded-xl border px-3 py-2.5 transition ${
                    active
                      ? "border-sky-200 bg-sky-50 shadow-sm"
                      : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-semibold ${active ? "text-sky-700" : "text-slate-800"}`}>{item.label}</span>
                    <span className={`h-2 w-2 rounded-full ${active ? "bg-sky-600" : "bg-slate-300 group-hover:bg-slate-400"}`} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{item.desc}</p>
                </Link>
              );
            })}
          </nav>
        </div>
      ))}

      <div className="mt-5 border-t border-slate-200 pt-4">
        <Link href="/role-select" className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100">
          Đổi vai trò
        </Link>
      </div>
    </aside>
  );
}
