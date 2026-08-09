"use client";

import Link from "next/link";
import Icon, { type IconName } from "@/components/ui/icon";
import type { NavigationItem } from "@/lib/navigation.config";

type Variant = "sidebar" | "drawer" | "bottom";

const NAVIGATION_ICON_NAMES: Record<string, IconName> = {
  account_tree: "progress",
  admin_panel_settings: "settings",
  alt_route: "progress",
  chat_paste_go: "chat",
  clinical_notes: "clinical-notes",
  dashboard: "progress",
  database: "folder",
  database_search: "search",
  description: "clinical-notes",
  event_available: "calendar",
  fact_check: "check",
  family_restroom: "contact",
  favorite: "progress",
  forum: "chat",
  gavel: "warning",
  groups: "contact",
  help: "warning",
  history: "progress",
  hub: "progress",
  insights: "progress",
  medication: "medication",
  monitoring: "progress",
  person: "user-card",
  pill: "medication",
  privacy_tip: "warning",
  route: "progress",
  science: "search",
  security: "warning",
  settings_input_component: "settings",
  shield_person: "warning",
  share: "share",
  stethoscope: "clinical-notes",
  today: "calendar",
  upload_file: "folder",
  vital_signs: "body",
  widgets: "more",
};

export function resolveNavigationIcon(icon: string): IconName {
  return NAVIGATION_ICON_NAMES[icon] ?? "clinical-notes";
}

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
  const iconName = resolveNavigationIcon(item.icon);

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
        <Icon name={iconName} size={19} aria-hidden="true" />
        <span className="max-w-full truncate text-[11px] font-semibold leading-tight">
          {item.shortLabel ?? item.label}
        </span>
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
        <Icon
          name={iconName}
          size={20}
          className={`mt-0.5 ${active ? "text-[var(--text-brand)]" : "text-[var(--text-muted)]"}`}
          aria-hidden="true"
        />
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
      <Icon name={iconName} size={20} aria-hidden="true" />
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
