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

const GROUP_LABEL_OVERRIDES: Record<string, string> = {
  core: "Quản trị",
  clinical: "Lâm sàng",
  medication: "Thuốc và an toàn",
  admin: "Hệ thống",
  support: "Hỗ trợ",
};

function getNavIcon(href: string): string {
  if (href.startsWith("/dashboard")) return "dashboard";
  if (href.startsWith("/chat")) return "chat_paste_go";
  if (href.startsWith("/research")) return "analytics";
  if (href.startsWith("/council")) return "groups";
  if (href.startsWith("/scribe")) return "clinical_notes";
  if (href.startsWith("/selfmed")) return "pill";
  if (href.startsWith("/careguard")) return "security";
  if (href.startsWith("/admin/knowledge-sources") || href.startsWith("/admin/rag-sources") || href.startsWith("/admin/source-hub")) {
    return "database";
  }
  if (href.startsWith("/admin")) return "settings_input_component";
  return "widgets";
}

export default function SidebarNav({ role }: SidebarNavProps) {
  const pathname = usePathname();
  const groups = getGroupedNavItems(role);

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-200/70 bg-[#eceef0] px-4 py-6 shadow-[inset_-1px_0_0_rgba(0,0,0,0.05)] dark:border-slate-800 dark:bg-slate-900 lg:flex lg:flex-col">
      <div className="mb-8 flex items-center gap-3 px-2">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-gradient-to-br from-cyan-400 to-cyan-700 text-slate-900">
          <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
            clinical_notes
          </span>
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tighter text-[#003461] dark:text-blue-400">CLARA Care</h1>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-500">Digital Surgeon AI</p>
        </div>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto pr-1 clara-scrollbar">
        {groups.map((group) => (
          <section key={group.key}>
            <p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-500">
              {GROUP_LABEL_OVERRIDES[group.key] ?? group.label}
            </p>
            <nav className="space-y-1">
              {group.items.map((item) => {
                const active = isActiveRoute(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={[
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-white font-semibold text-[#003461] shadow-sm dark:bg-slate-800 dark:text-blue-300"
                        : "text-[#424750] hover:bg-[#e0e3e5] hover:text-[#003461] dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-200",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-lg">{getNavIcon(item.href)}</span>
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>

      <div className="mt-6 border-t border-slate-200/70 px-2 pt-4 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-300/70 text-xs font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {ROLE_LABELS[role].slice(0, 1)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">CLARA Operator</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{ROLE_LABELS[role]}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
