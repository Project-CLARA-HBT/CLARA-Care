"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import {
  getDefaultWorkspace,
  getWorkspaceForPath,
  isActiveRoute,
  type UserRole,
  type WorkspaceId,
} from "@/lib/navigation.config";
import { ChromeSurface } from "./chrome-surface";
import { ClaraOrb } from "./clara-orb";
import { SessionContext } from "./session-boundary";
import { useShellMode, type ClaraOrbState } from "./shell-mode-provider";

export type WorkspaceType = WorkspaceId;
export type { WorkspaceId };

export interface FloatingNavItem {
  id: string;
  href: string;
  label: string;
  icon: IconName;
  isCenter?: boolean;
  activeMatchPrefix?: string[];
  badge?: number | string;
}

export interface FloatingNavbarProps {
  workspace?: WorkspaceId;
  role?: UserRole;
  orbState?: ClaraOrbState;
  onOrbClick?: () => void;
  onNavigate?: (href: string) => void;
  className?: string;
  "aria-label"?: string;
}

/**
 * Workspace-adaptive 5-destination navigation items matching Section 10 of Spec v1.
 * Center item (index 2) is always the interactive CLARA Orb hub (/chat).
 */
export const PERSONAL_NAV_ITEMS: FloatingNavItem[] = [
  {
    id: "today",
    href: "/today",
    label: "Hôm nay",
    icon: "calendar",
    activeMatchPrefix: ["/today", "/home"],
  },
  {
    id: "lifemap",
    href: "/lifemap",
    label: "Hành trình",
    icon: "body",
    activeMatchPrefix: ["/lifemap", "/phr"],
  },
  {
    id: "chat",
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat",
    isCenter: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "medicines",
    href: "/medicines",
    label: "Thuốc men",
    icon: "medication",
    activeMatchPrefix: [
      "/medicines",
      "/health/medications",
      "/selfmed",
      "/careguard",
    ],
  },
  {
    id: "you",
    href: "/you",
    label: "Cá nhân",
    icon: "user-card",
    activeMatchPrefix: ["/you", "/family", "/visits", "/account"],
  },
];

export const CLINICAL_NAV_ITEMS: FloatingNavItem[] = [
  {
    id: "dashboard",
    href: "/dashboard",
    label: "Tổng quan",
    icon: "calendar",
    activeMatchPrefix: ["/dashboard"],
  },
  {
    id: "council",
    href: "/council",
    label: "Hội chẩn",
    icon: "contact",
    activeMatchPrefix: ["/council"],
  },
  {
    id: "chat",
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat",
    isCenter: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "scribe",
    href: "/scribe",
    label: "Scribe",
    icon: "mic",
    activeMatchPrefix: ["/scribe"],
  },
  {
    id: "evidence",
    href: "/evidence",
    label: "Bằng chứng",
    icon: "scan",
    activeMatchPrefix: ["/evidence"],
  },
];

export const RESEARCH_NAV_ITEMS: FloatingNavItem[] = [
  {
    id: "evidence",
    href: "/evidence",
    label: "Bằng chứng",
    icon: "scan",
    activeMatchPrefix: ["/evidence"],
  },
  {
    id: "source-hub",
    href: "/research/source-hub",
    label: "Nguồn Y văn",
    icon: "folder",
    activeMatchPrefix: [
      "/research/source-hub",
      "/research/sources",
      "/research",
    ],
  },
  {
    id: "chat",
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat",
    isCenter: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "dashboard",
    href: "/dashboard",
    label: "Tổng quan",
    icon: "calendar",
    activeMatchPrefix: ["/dashboard"],
  },
  {
    id: "you",
    href: "/you",
    label: "Cá nhân",
    icon: "user-card",
    activeMatchPrefix: ["/you", "/account"],
  },
];

export const ADMIN_NAV_ITEMS: FloatingNavItem[] = [
  {
    id: "overview",
    href: "/admin/overview",
    label: "Tổng quan",
    icon: "calendar",
    activeMatchPrefix: ["/admin/overview", "/admin"],
  },
  {
    id: "users",
    href: "/admin/users",
    label: "Người dùng",
    icon: "user-card",
    activeMatchPrefix: ["/admin/users"],
  },
  {
    id: "chat",
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat",
    isCenter: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "system",
    href: "/admin/system",
    label: "Hệ thống",
    icon: "settings",
    activeMatchPrefix: [
      "/admin/system",
      "/admin/observability",
      "/admin/flow-debugger",
      "/admin/experiments",
    ],
  },
  {
    id: "audit",
    href: "/admin/audit",
    label: "Nhật ký",
    icon: "clinical-notes",
    activeMatchPrefix: ["/admin/audit", "/admin/audit-log", "/admin/dsar"],
  },
];

export const WORKSPACE_NAV_ITEMS: Record<WorkspaceId, FloatingNavItem[]> = {
  personal: PERSONAL_NAV_ITEMS,
  clinical: CLINICAL_NAV_ITEMS,
  research: RESEARCH_NAV_ITEMS,
  admin: ADMIN_NAV_ITEMS,
};

/**
 * FloatingNavbar: Single authoritative floating navigation dock across all 4 workspaces.
 * Built on ChromeSurface (variant="navbar", elevation="floating").
 * - Mobile viewport (<640px): 5 distinct destinations with visible labels (no horizontal scroll or hidden text).
 * - Desktop viewport (>=640px): Centered floating pill with active state indicators.
 * - Center item: ClaraOrb interactive hub (/chat).
 */
export function FloatingNavbar({
  workspace: propWorkspace,
  role: propRole,
  orbState: propOrbState,
  onOrbClick,
  onNavigate,
  className = "",
  "aria-label": ariaLabel = "Thanh điều hướng chính",
}: FloatingNavbarProps) {
  const pathname = usePathname();
  const session = useContext(SessionContext);
  const shellMode = useShellMode();

  const activeRole: UserRole = propRole ?? session?.role ?? "normal";
  const activeOrbState: ClaraOrbState =
    propOrbState ?? shellMode?.orbState ?? "idle";

  // Determine active workspace from props, preview mode, session role, or pathname
  const resolvedWorkspace: WorkspaceId = useMemo(() => {
    if (propWorkspace) return propWorkspace;
    if (session?.adminPreviewMode) {
      return session.adminPreviewMode;
    }
    if (propRole) {
      return getDefaultWorkspace(propRole);
    }
    return getWorkspaceForPath(pathname, activeRole);
  }, [propWorkspace, session?.adminPreviewMode, propRole, pathname, activeRole]);

  const navItems = useMemo(() => {
    return WORKSPACE_NAV_ITEMS[resolvedWorkspace] ?? PERSONAL_NAV_ITEMS;
  }, [resolvedWorkspace]);

  const isItemActive = useCallback(
    (item: FloatingNavItem) => {
      if (isActiveRoute(pathname, item.href)) return true;
      if (item.activeMatchPrefix) {
        return item.activeMatchPrefix.some((prefix) =>
          isActiveRoute(pathname, prefix),
        );
      }
      return false;
    },
    [pathname],
  );

  return (
    <ChromeSurface
      as="nav"
      variant="navbar"
      elevation="floating"
      aria-label={ariaLabel}
      data-testid="floating-navbar"
      data-workspace={resolvedWorkspace}
      className={[
        "fixed bottom-2.5 sm:bottom-5 left-1/2 -translate-x-1/2 z-50",
        "w-[calc(100%-1rem)] max-w-[480px] sm:max-w-none sm:w-auto",
        "rounded-2xl sm:rounded-full px-1.5 py-1.5 sm:px-3 sm:py-2",
        "border border-[color:var(--shell-border)]/50",
        "transition-all duration-300 shadow-2xl",
        className,
      ].join(" ")}
    >
      <div
        role="menubar"
        className="grid grid-cols-5 items-center justify-items-center gap-1 sm:flex sm:items-center sm:gap-1.5 w-full"
      >
        {navItems.map((item) => {
          const active = isItemActive(item);

          if (item.isCenter) {
            return (
              <Link
                key={item.id}
                href={item.href}
                onClick={() => {
                  onOrbClick?.();
                  onNavigate?.(item.href);
                }}
                data-testid={`floating-nav-item-${item.id}`}
                data-active={active ? "true" : "false"}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                title={item.label}
                className={[
                  "group relative flex flex-col sm:flex-row items-center justify-center min-w-0 w-full sm:w-auto",
                  "py-1 px-1 sm:px-3.5 sm:py-1.5 rounded-xl sm:rounded-full transition duration-200",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
                  active
                    ? "text-[var(--text-brand)] sm:bg-[var(--brand-600)] sm:text-white sm:shadow-md sm:ring-1 sm:ring-[var(--brand-500)]/40"
                    : "text-[var(--text-primary)] sm:bg-[var(--interactive-primary-idle,rgba(0,83,219,0.14))] sm:hover:bg-[var(--interactive-primary-hover,rgba(0,83,219,0.22))]",
                ].join(" ")}
              >
                <div className="flex items-center justify-center h-7 sm:h-auto">
                  <ClaraOrb
                    size="sm"
                    state={activeOrbState}
                    interactive={false}
                    showTooltip={false}
                    pulseEffect={active}
                  />
                </div>

                <span
                  className={[
                    "text-[10px] sm:text-xs leading-tight font-semibold truncate block w-full text-center mt-0.5 sm:mt-0 sm:ml-1.5 sm:inline-block sm:w-auto",
                    active
                      ? "text-[var(--text-brand)] sm:text-white"
                      : "text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  {item.label}
                </span>

                {/* Active Indicator on Mobile */}
                {active && (
                  <span
                    className="h-1 w-1 rounded-full bg-[var(--brand-500)] mt-0.5 block sm:hidden"
                    aria-hidden="true"
                  />
                )}
              </Link>
            );
          }

          return (
            <Link
              key={item.id}
              href={item.href}
              onClick={() => onNavigate?.(item.href)}
              data-testid={`floating-nav-item-${item.id}`}
              data-active={active ? "true" : "false"}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              title={item.label}
              className={[
                "group relative flex flex-col sm:flex-row items-center justify-center min-w-0 w-full sm:w-auto",
                "py-1 px-1 sm:px-3 sm:py-2 rounded-xl sm:rounded-full transition duration-200",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
                active
                  ? "text-[var(--text-brand)] font-semibold sm:bg-[var(--surface-active)] sm:shadow-inner"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-muted)]",
              ].join(" ")}
            >
              <div className="flex items-center justify-center h-7 sm:h-auto">
                <Icon
                  name={item.icon}
                  size={18}
                  className={active ? "text-[var(--text-brand)]" : undefined}
                  aria-hidden="true"
                />
              </div>

              <span
                className={[
                  "text-[10px] sm:text-xs leading-tight truncate block w-full text-center mt-0.5 sm:mt-0 sm:ml-1.5 sm:inline-block sm:w-auto",
                  active
                    ? "font-semibold text-[var(--text-brand)]"
                    : "font-medium text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                {item.label}
              </span>

              {/* Active Indicator on Mobile */}
              {active && (
                <span
                  className="h-1 w-1 rounded-full bg-[var(--brand-500)] mt-0.5 block sm:hidden"
                  aria-hidden="true"
                />
              )}

              {item.badge && (
                <span className="absolute -top-1 right-1 sm:static sm:ml-1.5 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[9px] font-bold leading-3 text-white">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </ChromeSurface>
  );
}

export default FloatingNavbar;
