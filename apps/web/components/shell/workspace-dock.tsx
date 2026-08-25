"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useContext,
  useMemo,
  type HTMLAttributes,
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
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import type { AdminPreviewPersona } from "@/lib/workspace/workspace.contract";
import { ClaraOrb } from "./clara-orb";
import { SessionContext } from "./session-boundary";
import { useShellMode, type ClaraOrbState, type DockMorphState } from "./shell-mode-provider";

/**
 * Standard bottom layout safe area class to ensure WorkspaceDock NEVER overlays
 * composer, stats, transcript, or table footers. (Spec v8 UX8-008 & Section 5.3)
 */
export const WORKSPACE_DOCK_SAFE_AREA_CLASS = "pb-20 sm:pb-24";
export const WORKSPACE_DOCK_HEIGHT_RANGE = "52–58px";
export const WORKSPACE_DOCK_DESKTOP_HEIGHT_CLASS = "h-[54px] min-h-[52px] max-h-[58px]";

export interface WorkspaceDockItem {
  id: string;
  href: string;
  label: string;
  icon: IconName;
  isCenter?: boolean;
  activeMatchPrefix?: string[];
  badge?: number | string;
}

/**
 * Clinical workspace primary 5 destinations (Spec v8 Section 4.4):
 * Overview (/dashboard) | Council (/council) | CLARA (/chat) | Scribe (/scribe) | More (/clinical/patients)
 */
export const CLINICAL_DOCK_ITEMS: WorkspaceDockItem[] = [
  {
    id: "overview",
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
    label: "CLARA",
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
    id: "more",
    href: "/clinical/patients",
    label: "Thêm",
    icon: "more",
    activeMatchPrefix: ["/clinical/patients", "/clinical"],
  },
];

/**
 * Research workspace primary 5 destinations (Spec v8 Section 4.4):
 * Research (/research) | Evidence (/evidence) | CLARA (/chat) | Sources (/research/source-hub) | More (/you)
 */
export const RESEARCH_DOCK_ITEMS: WorkspaceDockItem[] = [
  {
    id: "research",
    href: "/research",
    label: "Tra cứu",
    icon: "search",
    activeMatchPrefix: ["/research"],
  },
  {
    id: "evidence",
    href: "/evidence",
    label: "Bằng chứng",
    icon: "scan",
    activeMatchPrefix: ["/evidence"],
  },
  {
    id: "chat",
    href: "/chat",
    label: "CLARA",
    icon: "chat",
    isCenter: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "sources",
    href: "/research/source-hub",
    label: "Nguồn",
    icon: "folder",
    activeMatchPrefix: ["/research/source-hub", "/research/sources"],
  },
  {
    id: "more",
    href: "/you",
    label: "Thêm",
    icon: "user-card",
    activeMatchPrefix: ["/you", "/account"],
  },
];

/**
 * Personal workspace primary 5 destinations (Spec v8 Section 4.4):
 * Today (/today) | LifeMap (/lifemap) | CLARA (/chat) | Medicines (/medicines) | Profile (/you)
 */
export const PERSONAL_DOCK_ITEMS: WorkspaceDockItem[] = [
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
    label: "CLARA",
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

export const WORKSPACE_DOCK_ITEMS: Record<
  "personal" | "clinical" | "research",
  WorkspaceDockItem[]
> = {
  personal: PERSONAL_DOCK_ITEMS,
  clinical: CLINICAL_DOCK_ITEMS,
  research: RESEARCH_DOCK_ITEMS,
};

/**
 * Disambiguated route matcher for workspace dock items.
 */
export function isDockItemActive(
  pathname: string,
  item: WorkspaceDockItem,
): boolean {
  if (!pathname) return false;
  const cleanPath = pathname.split("?")[0].split("#")[0].trim();

  // Disambiguation between /research and /research/source-hub
  if (item.href === "/research") {
    if (
      cleanPath.startsWith("/research/source-hub") ||
      cleanPath.startsWith("/research/sources")
    ) {
      return false;
    }
    return cleanPath === "/research" || cleanPath.startsWith("/research/");
  }

  // Personal today/home equivalence
  if (
    item.href === "/today" &&
    (cleanPath === "/today" || cleanPath === "/home" || cleanPath === "/")
  ) {
    return true;
  }

  // Exact or prefix matching
  if (isActiveRoute(cleanPath, item.href)) {
    return true;
  }

  if (item.activeMatchPrefix) {
    return item.activeMatchPrefix.some((prefix) =>
      isActiveRoute(cleanPath, prefix),
    );
  }

  return false;
}

export interface WorkspaceDockProps {
  workspace?: WorkspaceId;
  role?: UserRole;
  adminPreviewPersona?: AdminPreviewPersona | null;
  orbState?: ClaraOrbState;
  morphState?: DockMorphState;
  onMorphStateChange?: (state: DockMorphState) => void;
  onOrbClick?: () => void;
  onNavigate?: (href: string) => void;
  className?: string;
  reserveSafeArea?: boolean;
  "aria-label"?: string;
}

/**
 * WorkspaceDock component according to Spec v8 Section 4.4 & 5.3:
 * 1. For Personal / Clinical / Research workspaces ONLY (Admin does NOT mount consumer bottom dock).
 * 2. Desktop height: 52–58px, floating, max 5 primary destinations.
 * 3. Centers interactive ClaraOrb (/chat).
 * 4. Clinical: Overview (/dashboard) | Council (/council) | ◉ CLARA (/chat) | Scribe (/scribe) | More (/clinical/patients).
 * 5. Research: Research (/research) | Evidence (/evidence) | ◉ CLARA (/chat) | Sources (/research/source-hub) | More (/you).
 * 6. Personal: Today (/today) | LifeMap (/lifemap) | ◉ CLARA (/chat) | Medicines (/medicines) | Profile (/you).
 * 7. Reserves bottom layout safe area (pb-20 sm:pb-24).
 */
export function WorkspaceDock({
  workspace: propWorkspace,
  role: propRole,
  adminPreviewPersona: propAdminPreviewPersona,
  orbState: propOrbState,
  morphState: propMorphState,
  onOrbClick,
  onNavigate,
  className = "",
  reserveSafeArea = false,
  "aria-label": ariaLabel = "Thanh điều hướng không gian làm việc",
}: WorkspaceDockProps) {
  const pathname = usePathname();
  const workspaceContext = useContext(WorkspaceContext);
  const sessionContext = useContext(SessionContext);
  const shellMode = useShellMode();

  const activeRole: UserRole =
    propRole ??
    sessionContext?.effectiveRole ??
    sessionContext?.role ??
    "normal";

  const previewPersona: AdminPreviewPersona | null =
    propAdminPreviewPersona ??
    workspaceContext?.adminPreviewPersona ??
    sessionContext?.adminPreviewMode ??
    null;

  // Resolve target workspace: props -> preview persona -> path & role -> workspace provider
  const resolvedWorkspace: WorkspaceId = useMemo(() => {
    if (propWorkspace) return propWorkspace;
    if (previewPersona) return previewPersona;
    if (propRole) return getDefaultWorkspace(propRole);
    if (pathname) {
      const pathWs = getWorkspaceForPath(
        pathname,
        activeRole,
        workspaceContext?.activeWorkspace,
      );
      if (pathWs) return pathWs;
    }
    if (workspaceContext?.activeWorkspace) return workspaceContext.activeWorkspace;
    return getDefaultWorkspace(activeRole);
  }, [
    propWorkspace,
    previewPersona,
    propRole,
    pathname,
    activeRole,
    workspaceContext?.activeWorkspace,
  ]);

  // Invariant: Admin workspace does NOT mount consumer bottom dock (suppressed on /admin/*)
  if (
    resolvedWorkspace === "admin" ||
    (pathname && pathname.startsWith("/admin") && !previewPersona)
  ) {
    return null;
  }

  const activeOrbState: ClaraOrbState =
    propOrbState ?? shellMode?.orbState ?? "idle";

  const items =
    WORKSPACE_DOCK_ITEMS[
      resolvedWorkspace as "personal" | "clinical" | "research"
    ] ?? PERSONAL_DOCK_ITEMS;

  const currentMorphState: DockMorphState =
    propMorphState ?? shellMode?.dockMorphState ?? "EXPANDED";

  const isCompact = currentMorphState === "COMPACT";

  return (
    <>
      {reserveSafeArea && (
        <div
          data-testid="workspace-dock-safe-area-spacer"
          className="h-20 sm:h-24 pointer-events-none"
          aria-hidden="true"
        />
      )}

      <nav
        aria-label={ariaLabel}
        data-testid="workspace-dock"
        data-floating-navbar="true"
        data-workspace={resolvedWorkspace}
        className={[
          "fixed bottom-3 sm:bottom-4 md:bottom-5 left-1/2 -translate-x-1/2 z-50",
          "w-[calc(100%-1rem)] max-w-[500px] sm:max-w-none sm:w-auto",
          "h-[54px] min-h-[52px] max-h-[58px]",
          "flex items-center justify-center",
          "rounded-2xl sm:rounded-full px-1.5 sm:px-3",
          "bg-[var(--surface-header)]/92 backdrop-blur-2xl",
          "border border-[color:var(--shell-border)]/60",
          "shadow-2xl transition-all duration-300",
          className,
        ].join(" ")}
      >
        <div
          role="menubar"
          className="grid grid-cols-5 items-center justify-items-center gap-1 sm:flex sm:items-center sm:gap-1.5 h-full w-full"
        >
          {items.map((item) => {
            const active = isDockItemActive(pathname, item);

            if (item.isCenter) {
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  onClick={() => {
                    onOrbClick?.();
                    onNavigate?.(item.href);
                  }}
                  data-testid={`workspace-dock-item-${item.id}`}
                  data-active={active ? "true" : "false"}
                  aria-label={item.label === "CLARA" ? "◉ CLARA" : item.label}
                  aria-current={active ? "page" : undefined}
                  title={item.label}
                  className={[
                    "group relative flex items-center justify-center",
                    "h-10 sm:h-10 px-2 sm:px-3.5 rounded-xl sm:rounded-full transition duration-200",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
                    active
                      ? "bg-[var(--brand-600)] text-white shadow-md ring-2 ring-[var(--brand-500)]/40 font-semibold"
                      : "bg-[var(--interactive-primary-idle,rgba(0,83,219,0.12))] text-[var(--text-primary)] hover:bg-[var(--interactive-primary-hover,rgba(0,83,219,0.2))] font-medium",
                  ].join(" ")}
                >
                  <div className="flex items-center gap-1.5">
                    <ClaraOrb
                      size="sm"
                      state={activeOrbState}
                      interactive={false}
                      showTooltip={false}
                      pulseEffect={active}
                    />
                    {!isCompact && (
                      <span className="text-[11px] sm:text-xs tracking-tight font-bold whitespace-nowrap">
                        {item.label}
                      </span>
                    )}
                  </div>

                  {active && isCompact && (
                    <span
                      className="absolute bottom-1 h-1 w-1 rounded-full bg-white"
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
                data-testid={`workspace-dock-item-${item.id}`}
                data-active={active ? "true" : "false"}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                title={item.label}
                className={[
                  "group relative flex flex-col sm:flex-row items-center justify-center min-w-0",
                  "h-10 sm:h-10 px-2 sm:px-3 rounded-xl sm:rounded-full transition duration-200",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
                  active
                    ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold shadow-inner"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-muted)] font-medium",
                ].join(" ")}
              >
                <div className="flex items-center justify-center">
                  <Icon
                    name={item.icon}
                    size={18}
                    className={active ? "text-[var(--text-brand)]" : undefined}
                    aria-hidden="true"
                  />
                </div>

                {!isCompact && (
                  <span
                    className={[
                      "text-[10px] sm:text-xs leading-tight truncate sm:ml-1.5",
                      active
                        ? "font-semibold text-[var(--text-brand)]"
                        : "font-medium text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    {item.label}
                  </span>
                )}

                {/* Active Indicator in Compact or Mobile view */}
                {active && (
                  <span
                    className="h-1 w-1 rounded-full bg-[var(--brand-500)] mt-0.5 block sm:hidden"
                    aria-hidden="true"
                  />
                )}

                {item.badge && (
                  <span className="ml-1 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[9px] font-bold leading-3 text-white">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}

/**
 * Layout helper to wrap or reserve bottom safe area space so WorkspaceDock never
 * overlays primary page content.
 */
export interface WorkspaceDockSafeAreaProps
  extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  className?: string;
}

export function WorkspaceDockSafeArea({
  children,
  className = "",
  ...rest
}: WorkspaceDockSafeAreaProps) {
  return (
    <div
      data-testid="workspace-dock-safe-area"
      className={`${WORKSPACE_DOCK_SAFE_AREA_CLASS} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export default WorkspaceDock;
