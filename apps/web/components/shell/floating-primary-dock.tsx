"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { isActiveRoute, type UserRole } from "@/lib/navigation.config";
import { ClaraOrb } from "./clara-orb";
import {
  useShellMode,
  type DockMorphState,
  type ShellActiveEntity,
} from "./shell-mode-provider";

export interface DockNavItem {
  id: string;
  href: string;
  label: string;
  icon: IconName;
  badge?: number | string;
  activeMatchPrefix?: string[];
  isCenterHighlight?: boolean;
}

export interface ContextualAction {
  id: string;
  label: string;
  icon?: IconName;
  tone?: "brand" | "ok" | "warn" | "danger" | "neutral";
  onClick: () => void;
  disabled?: boolean;
}

export interface FloatingPrimaryDockProps {
  role?: UserRole;
  morphState?: DockMorphState;
  onMorphStateChange?: (state: DockMorphState) => void;
  onOpenCommandPalette?: () => void;
  onOpenCapture?: () => void;
  contextualActions?: ContextualAction[];
  customEntity?: ShellActiveEntity | null;
  className?: string;
}

export const CONSUMER_DOCK_ITEMS: DockNavItem[] = [
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
    isCenterHighlight: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "medicines",
    href: "/medicines",
    label: "Thuốc men",
    icon: "medication",
    activeMatchPrefix: ["/medicines", "/health/medications"],
  },
  {
    id: "you",
    href: "/you",
    label: "Cá nhân",
    icon: "user-card",
    activeMatchPrefix: ["/you", "/family", "/visits"],
  },
];

export const DOCTOR_DOCK_ITEMS: DockNavItem[] = [
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
    isCenterHighlight: true,
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
    activeMatchPrefix: ["/evidence", "/research"],
  },
];

export const RESEARCHER_DOCK_ITEMS: DockNavItem[] = [
  {
    id: "evidence",
    href: "/evidence",
    label: "Bằng chứng",
    icon: "scan",
    activeMatchPrefix: ["/evidence", "/research/evidence"],
  },
  {
    id: "source-hub",
    href: "/research/source-hub",
    label: "Nguồn Y văn",
    icon: "folder",
    activeMatchPrefix: ["/research/source-hub", "/research/sources", "/research"],
  },
  {
    id: "chat",
    href: "/chat",
    label: "Hỏi CLARA",
    icon: "chat",
    isCenterHighlight: true,
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

export const ADMIN_DOCK_ITEMS: DockNavItem[] = [
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
    isCenterHighlight: true,
    activeMatchPrefix: ["/chat", "/ask"],
  },
  {
    id: "system",
    href: "/admin/system",
    label: "Hệ thống",
    icon: "settings",
    activeMatchPrefix: ["/admin/system", "/admin/observability", "/admin/flow-debugger"],
  },
  {
    id: "audit",
    href: "/admin/audit",
    label: "Nhật ký",
    icon: "clinical-notes",
    activeMatchPrefix: ["/admin/audit", "/admin/audit-log", "/admin/dsar"],
  },
];

export function FloatingPrimaryDock({
  role = "normal",
  morphState: propMorphState,
  onMorphStateChange,
  onOpenCommandPalette,
  onOpenCapture,
  contextualActions = [],
  customEntity,
  className = "",
}: FloatingPrimaryDockProps) {
  const pathname = usePathname();
  const shellContext = useShellMode();

  const dockState = propMorphState ?? shellContext.dockMorphState;
  const setDockState = onMorphStateChange ?? shellContext.setDockMorphState;
  const activeEntity = customEntity ?? shellContext.activeEntity;
  const orbState = shellContext.orbState;

  const dockNavRef = useRef<HTMLDivElement>(null);

  const navItems = useMemo(() => {
    switch (role) {
      case "doctor":
        return DOCTOR_DOCK_ITEMS;
      case "researcher":
        return RESEARCHER_DOCK_ITEMS;
      case "admin":
        return ADMIN_DOCK_ITEMS;
      case "normal":
      default:
        return CONSUMER_DOCK_ITEMS;
    }
  }, [role]);

  const isItemActive = useCallback(
    (item: DockNavItem) => {
      if (isActiveRoute(pathname, item.href)) return true;
      if (item.activeMatchPrefix) {
        return item.activeMatchPrefix.some((prefix) => isActiveRoute(pathname, prefix));
      }
      return false;
    },
    [pathname],
  );

  // Cycle Morph State handler
  const cycleState = useCallback(() => {
    const states: DockMorphState[] = [
      "EXPANDED",
      "COMPACT",
      "ORB_ONLY",
      "HIDDEN_WITH_ESCAPE",
    ];
    const currentIndex = states.indexOf(dockState);
    const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % states.length;
    setDockState(states[nextIndex]);
  }, [dockState, setDockState]);

  // Handle Escape key to morph state
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // Toggle dock to hidden or return to expanded
        if (dockState !== "HIDDEN_WITH_ESCAPE") {
          setDockState("HIDDEN_WITH_ESCAPE");
        } else {
          setDockState("EXPANDED");
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dockState, setDockState]);

  // 1. HIDDEN_WITH_ESCAPE STATE: Small minimal reveal handle at screen bottom
  if (dockState === "HIDDEN_WITH_ESCAPE") {
    return (
      <div
        data-testid="floating-primary-dock"
        className={[
          "fixed bottom-3 left-1/2 -translate-x-1/2 z-50 transition-all duration-300",
          className,
        ].join(" ")}
      >
        <button
          type="button"
          onClick={() => setDockState("EXPANDED")}
          className="group flex items-center gap-2 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-header)]/90 backdrop-blur-lg px-3.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] shadow-lg hover:text-[var(--text-primary)] hover:border-[color:var(--brand-500)]/40 transition"
          aria-label="Mở thanh điều hướng (Phím Esc)"
          title="Mở thanh điều hướng (Phím Esc)"
        >
          <ClaraOrb size="sm" state={orbState} interactive={false} />
          <span>Điều hướng</span>
          <kbd className="hidden sm:inline-block rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1.5 text-[10px] font-semibold text-[var(--text-muted)]">
            Esc
          </kbd>
        </button>
      </div>
    );
  }

  // 2. ORB_ONLY STATE: Floating CLARA Orb button at bottom right
  if (dockState === "ORB_ONLY") {
    return (
      <div
        data-testid="floating-primary-dock"
        className={[
          "fixed bottom-5 right-5 z-50 flex items-center gap-3 transition-all duration-300",
          className,
        ].join(" ")}
      >
        <button
          type="button"
          onClick={() => setDockState("EXPANDED")}
          aria-label="Mở rộng thanh điều hướng"
          title="Mở rộng thanh điều hướng"
          className="group relative flex items-center justify-center p-1 rounded-full bg-[var(--surface-header)]/80 backdrop-blur-xl border border-[color:var(--shell-border)] shadow-xl hover:border-[color:var(--brand-500)] transition"
        >
          <ClaraOrb
            size="lg"
            state={orbState}
            interactive={false}
            showTooltip={false}
          />
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--brand-600)] text-[9px] font-bold text-white shadow-sm">
            ▲
          </span>
        </button>
      </div>
    );
  }

  // 3. CONTEXTUAL STATE: Task / Entity focused dock
  if (dockState === "CONTEXTUAL" && (activeEntity || contextualActions.length > 0)) {
    return (
      <div
        ref={dockNavRef}
        data-testid="floating-primary-dock"
        className={[
          "fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[min(94vw,680px)]",
          "rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/90 backdrop-blur-xl",
          "p-2 shadow-2xl transition-all duration-300",
          className,
        ].join(" ")}
        role="toolbar"
        aria-label="Thanh công cụ ngữ cảnh"
      >
        <div className="flex items-center justify-between gap-3">
          {/* Active Entity Chip on Left */}
          <div className="flex min-w-0 items-center gap-2 px-2">
            <ClaraOrb size="sm" state={orbState} interactive={false} />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                  {activeEntity?.label ?? "Ngữ cảnh làm việc"}
                </span>
                {activeEntity?.badge && (
                  <span className="rounded bg-[var(--surface-brand-soft)] px-1.5 py-0.2 text-[10px] font-semibold text-[var(--text-brand)]">
                    {activeEntity.badge}
                  </span>
                )}
              </div>
              {activeEntity?.sublabel && (
                <p className="truncate text-[11px] text-[var(--text-muted)]">
                  {activeEntity.sublabel}
                </p>
              )}
            </div>
          </div>

          {/* Contextual Action Buttons */}
          <div className="flex items-center gap-2">
            {contextualActions.map((action) => {
              const toneClasses =
                action.tone === "brand"
                  ? "bg-[var(--brand-600)] text-white hover:bg-[var(--brand-700)]"
                  : action.tone === "ok"
                    ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]"
                    : action.tone === "warn"
                      ? "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border border-[color:var(--status-warn-border)]"
                      : action.tone === "danger"
                        ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border border-[color:var(--status-danger-border)]"
                        : "bg-[var(--surface-panel)] text-[var(--text-primary)] hover:bg-[var(--surface-muted)]";

              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={[
                    "inline-flex h-9 items-center gap-1.5 rounded-xl px-3 text-xs font-semibold shadow-sm transition",
                    toneClasses,
                    action.disabled ? "opacity-50 cursor-not-allowed" : "",
                  ].join(" ")}
                >
                  {action.icon && <Icon name={action.icon} size={15} aria-hidden="true" />}
                  <span>{action.label}</span>
                </button>
              );
            })}

            {/* Return to standard navigation */}
            <button
              type="button"
              onClick={() => setDockState("EXPANDED")}
              aria-label="Quay lại điều hướng chính"
              title="Quay lại điều hướng chính"
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
            >
              <Icon name="close" size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 4. COMPACT STATE: Slim icon-only pill bar with tooltips
  if (dockState === "COMPACT") {
    return (
      <nav
        ref={dockNavRef}
        data-testid="floating-primary-dock"
        className={[
          "fixed bottom-4 left-1/2 -translate-x-1/2 z-50",
          "flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-header)]/90 backdrop-blur-xl",
          "p-1.5 shadow-2xl transition-all duration-300",
          className,
        ].join(" ")}
        aria-label="Thanh điều hướng thu gọn"
      >
        {/* CLARA Orb trigger */}
        <div className="px-1">
          <ClaraOrb
            size="sm"
            state={orbState}
            onClick={() => shellContext.openCommandPalette()}
            label="Mở bảng lệnh CLARA (Ctrl+K)"
          />
        </div>

        <div className="h-5 w-px bg-[color:var(--shell-border)]" aria-hidden="true" />

        {/* Compact Nav Item Icons */}
        <div className="flex items-center gap-1">
          {navItems.map((item) => {
            const active = isItemActive(item);
            return (
              <Link
                key={item.id}
                href={item.href}
                className={[
                  "group relative inline-flex h-10 w-10 items-center justify-center rounded-full transition",
                  active
                    ? "bg-[var(--surface-active)] text-[var(--text-brand)] shadow-sm font-semibold"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <Icon name={item.icon} size={18} aria-hidden="true" />
                {active && (
                  <span
                    className="absolute bottom-1 h-1 w-1 rounded-full bg-[var(--brand-500)]"
                    aria-hidden="true"
                  />
                )}
              </Link>
            );
          })}
        </div>

        <div className="h-5 w-px bg-[color:var(--shell-border)]" aria-hidden="true" />

        {/* Morph to Expanded Button */}
        <button
          type="button"
          onClick={() => setDockState("EXPANDED")}
          aria-label="Mở rộng thanh điều hướng"
          title="Mở rộng thanh điều hướng"
          className="inline-flex h-10 w-8 items-center justify-center rounded-full text-[var(--text-muted)] hover:text-[var(--text-primary)] transition"
        >
          <Icon name="arrow-right" size={15} aria-hidden="true" />
        </button>
      </nav>
    );
  }

  // 5. EXPANDED STATE (Default): Full featured role-adaptive floating dock
  const workspaceAttr =
    role === "doctor"
      ? "clinical"
      : role === "researcher"
      ? "research"
      : role === "admin"
      ? "admin"
      : "personal";

  return (
    <nav
      ref={dockNavRef}
      data-testid="workspace-dock"
      data-workspace={workspaceAttr}
      className={[
        "fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[min(96vw,840px)]",
        "rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/92 backdrop-blur-2xl",
        "px-3 py-2 shadow-2xl transition-all duration-300",
        className,
      ].join(" ")}
      aria-label="Thanh điều hướng chính"
    >
      <div className="flex items-center justify-between gap-2">
        {/* Left: CLARA Intelligent Orb Core */}
        <div className="flex shrink-0 items-center gap-2.5 pr-1">
          <ClaraOrb
            size="md"
            state={orbState}
            onClick={() => {
              if (onOpenCommandPalette) {
                onOpenCommandPalette();
              } else {
                shellContext.openCommandPalette();
              }
            }}
            label="Hỏi CLARA / Bảng lệnh nhanh (Ctrl+K)"
          />
          <span className="hidden xl:inline-block">
            <span className="block text-xs font-bold tracking-tight text-[var(--text-primary)]">
              CLARA
            </span>
            <span className="block text-[10px] text-[var(--text-muted)] capitalize">
              {role === "normal" ? "Trợ lý sức khỏe" : role}
            </span>
          </span>
        </div>

        <div className="h-8 w-px bg-[color:var(--shell-border)] shrink-0" aria-hidden="true" />

        {/* Center: Role Adaptive Navigation Items */}
        <div className="flex flex-1 items-center justify-center gap-1 overflow-x-auto clara-scrollbar py-0.5">
          {navItems.map((item) => {
            const active = isItemActive(item);

            if (item.isCenterHighlight) {
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className={[
                    "relative flex h-10 items-center gap-2 rounded-xl px-3.5 text-xs font-semibold shadow-sm transition shrink-0",
                    active
                      ? "bg-[var(--brand-600)] text-white ring-2 ring-[var(--brand-500)]/40"
                      : "bg-[var(--interactive-primary-idle)] text-[var(--on-primary)] hover:bg-[var(--interactive-primary-hover)]",
                  ].join(" ")}
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  title={item.label}
                >
                  <ClaraOrb
                    size="sm"
                    state={orbState}
                    interactive={false}
                    showTooltip={false}
                  />
                  <span className="whitespace-nowrap">{item.label}</span>
                </Link>
              );
            }

            return (
              <Link
                key={item.id}
                href={item.href}
                className={[
                  "group relative flex h-10 items-center gap-2 rounded-xl px-3 text-xs font-medium transition shrink-0",
                  active
                    ? "bg-[var(--surface-active)] font-semibold text-[var(--text-brand)] shadow-inner"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <Icon
                  name={item.icon}
                  size={17}
                  className={active ? "text-[var(--text-brand)]" : undefined}
                  aria-hidden="true"
                />
                <span className="hidden sm:inline-block whitespace-nowrap">{item.label}</span>
                {item.badge && (
                  <span className="min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[10px] font-bold leading-4 text-white">
                    {item.badge}
                  </span>
                )}
                {active && (
                  <span
                    className="absolute bottom-1 left-1/2 -translate-x-1/2 h-0.5 w-4 rounded-full bg-[var(--brand-500)] sm:hidden"
                    aria-hidden="true"
                  />
                )}
              </Link>
            );
          })}
        </div>

        <div className="h-8 w-px bg-[color:var(--shell-border)] shrink-0" aria-hidden="true" />

        {/* Right: Quick Actions + Dock Morph Controls */}
        <div className="flex shrink-0 items-center gap-1.5 pl-1">
          {/* Universal Capture (+) Button */}
          {onOpenCapture && (
            <button
              type="button"
              onClick={onOpenCapture}
              aria-label="Tải lên tài liệu y tế (+)"
              title="Tải lên tài liệu y tế (+)"
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--surface-panel)] border border-[color:var(--shell-border)] text-[var(--text-brand)] hover:bg-[var(--surface-muted)] transition"
            >
              <Icon name="plus" size={16} aria-hidden="true" />
            </button>
          )}

          {/* Command Palette Trigger (Ctrl+K) */}
          <button
            type="button"
            onClick={() => {
              if (onOpenCommandPalette) {
                onOpenCommandPalette();
              } else {
                shellContext.openCommandPalette();
              }
            }}
            aria-label="Mở bảng lệnh (Ctrl+K)"
            title="Mở bảng lệnh (Ctrl+K)"
            className="hidden md:inline-flex h-9 items-center gap-1 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-muted)] transition"
          >
            <Icon name="search" size={14} aria-hidden="true" />
            <kbd className="text-[10px] font-semibold">⌘K</kbd>
          </button>

          {/* Morph State Toggle Button */}
          <button
            type="button"
            onClick={cycleState}
            aria-label="Thu gọn thanh điều hướng"
            title="Thu gọn thanh điều hướng (Phím Esc)"
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-muted)] transition"
          >
            <Icon name="arrow-left" size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
    </nav>
  );
}

export default FloatingPrimaryDock;
