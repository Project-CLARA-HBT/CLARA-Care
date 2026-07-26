"use client";

import Link from "next/link";
import type { NavigationItem } from "@/lib/navigation.config";

type Variant = "sidebar" | "drawer" | "bottom";

/**
 * Single source of truth for a navigation entry across every renderer
 * (desktop sidebar, mobile drawer, bottom bar). One active-state style,
 * fed by `navigation.config.ts`, so the four hand-maintained renderings can
 * no longer drift into two competing color systems.
 */
export function NavItem({
  item,
  active,
  variant,
  collapsed = false,
  onNavigate,
}: {
  item: NavigationItem;
  active: boolean;
  variant: Variant;
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const filled = active ? { fontVariationSettings: "'FILL' 1" } : undefined;

  if (variant === "bottom") {
    return (
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        onClick={onNavigate}
        className={`focus-ring flex min-h-[56px] flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-2 py-1.5 text-center transition ${
          active
            ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
            : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        }`}
      >
        <span className="material-symbols-outlined text-[19px]" style={filled} aria-hidden="true">
          {item.icon}
        </span>
        <span className="text-[11px] font-semibold leading-tight">{item.label}</span>
      </Link>
    );
  }

  if (variant === "drawer") {
    return (
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        onClick={onNavigate}
        className={`focus-ring flex items-start gap-3 rounded-[var(--radius-lg)] px-3 py-2.5 transition ${
          active
            ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
            : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        }`}
      >
        <span
          className={`material-symbols-outlined mt-0.5 shrink-0 text-[20px] ${
            active ? "text-[var(--text-brand)]" : "text-[var(--text-muted)]"
          }`}
          style={filled}
          aria-hidden="true"
        >
          {item.icon}
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-[var(--text-primary)]">
            {item.label}
          </span>
          <span className="mt-0.5 block text-xs leading-5 text-[var(--text-secondary)]">
            {item.desc}
          </span>
        </span>
      </Link>
    );
  }

  // sidebar
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
      title={item.label}
      className={[
        "app-nav-item",
        collapsed ? "justify-center px-0" : "gap-3 px-3",
        active ? "app-nav-item-active" : "",
      ].join(" ")}
    >
      <span
        className="material-symbols-outlined shrink-0 text-[20px]"
        style={filled}
        aria-hidden="true"
      >
        {item.icon}
      </span>
      {!collapsed ? <span className="truncate">{item.label}</span> : null}
      {!collapsed && active ? (
        <span
          className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--brand-600)]"
          aria-hidden="true"
        />
      ) : null}
    </Link>
  );
}

export default NavItem;
