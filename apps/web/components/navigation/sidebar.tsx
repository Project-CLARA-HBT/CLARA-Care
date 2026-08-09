"use client";

import Link from "next/link";
import { useMemo } from "react";
import { roleMenus, UserRole } from "@/lib/auth/roles";

export default function Sidebar({ role }: { role: UserRole }) {
  const items = useMemo(() => roleMenus[role], [role]);

  return (
    <aside className="w-64 border-r border-[color:var(--shell-border)] bg-[var(--surface-lowest)] p-4 text-[var(--text-primary)]">
      <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">CLARA (vai trò: {role})</h2>
      <nav className="space-y-2">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block rounded-lg px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
