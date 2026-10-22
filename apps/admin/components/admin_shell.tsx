import React from "react";
import { ADMIN_TOKENS } from "./tokens";

export interface AdminShellProps {
  children: React.ReactNode;
  activePath?: string;
  adminEmail?: string;
}

export function AdminAccessibleShell({
  children,
  activePath = "/",
  adminEmail = "admin@theclaracare.com",
}: AdminShellProps) {
  const navItems = [
    { label: "Dashboard", href: "/" },
    { label: "Tenants", href: "/tenants" },
    { label: "Feature Flags", href: "/flags" },
    { label: "Audit Ledger", href: "/audit" },
  ];

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900 p-4">
        <div className="mb-6 px-3 py-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-sky-400">Control Plane</h2>
          <p className="text-xs text-slate-400">Security & Tenant Gov</p>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = activePath === item.href;
            return (
              <a
                key={item.href}
                href={item.href}
                className={`flex items-center rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-sky-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                {item.label}
              </a>
            );
          })}
        </nav>
        <div className="mt-auto pt-6 border-t border-slate-800">
          <p className="text-xs text-slate-400">Operator: {adminEmail}</p>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col">
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
