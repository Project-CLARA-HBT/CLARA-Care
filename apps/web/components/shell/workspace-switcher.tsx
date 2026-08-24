"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import {
  getDefaultWorkspace,
  getWorkspaceForPath,
  isWorkspaceAvailable,
  type UserRole,
  type WorkspaceId,
} from "@/lib/navigation.config";
import { ChromeSurface } from "./chrome-surface";
import {
  SessionContext,
  type AdminPreviewMode,
} from "./session-boundary";

export interface WorkspaceOption {
  id: WorkspaceId;
  label: string;
  shortLabel: string;
  description: string;
  badge: string;
  badgeTone: "brand" | "clinical" | "research" | "admin";
  icon: IconName;
  homeHref: string;
  allowedRoles: UserRole[];
}

export interface WorkspaceSwitcherPreviewOption {
  mode: AdminPreviewMode;
  label: string;
  shortLabel: string;
  description: string;
  badge: string;
  icon: IconName;
  targetHref: string;
}

export const WORKSPACE_OPTIONS: Record<WorkspaceId, WorkspaceOption> = {
  personal: {
    id: "personal",
    label: "Cá nhân",
    shortLabel: "Cá nhân",
    description: "Sức khỏe cá nhân, thuốc men & hồ sơ",
    badge: "Bệnh nhân",
    badgeTone: "brand",
    icon: "user-card",
    homeHref: "/today",
    allowedRoles: ["normal", "researcher", "doctor", "admin"],
  },
  clinical: {
    id: "clinical",
    label: "Lâm sàng",
    shortLabel: "Lâm sàng",
    description: "Hội chẩn đa khoa, Scribe & tổng quan",
    badge: "Bác sĩ",
    badgeTone: "clinical",
    icon: "contact",
    homeHref: "/dashboard",
    allowedRoles: ["doctor", "admin"],
  },
  research: {
    id: "research",
    label: "Nghiên cứu",
    shortLabel: "Nghiên cứu",
    description: "Bằng chứng y văn, PubMed & tổng hợp",
    badge: "Nghiên cứu",
    badgeTone: "research",
    icon: "scan",
    homeHref: "/evidence",
    allowedRoles: ["researcher", "doctor", "admin"],
  },
  admin: {
    id: "admin",
    label: "Quản trị",
    shortLabel: "Quản trị",
    description: "Cấu hình hệ thống, người dùng & nhật ký",
    badge: "Admin",
    badgeTone: "admin",
    icon: "settings",
    homeHref: "/admin/overview",
    allowedRoles: ["admin"],
  },
};

export const WORKSPACE_SWITCHER_PREVIEW_OPTIONS: WorkspaceSwitcherPreviewOption[] = [
  {
    mode: "clinical",
    label: "Bác sĩ (Clinical)",
    shortLabel: "Bác sĩ",
    description: "Trải nghiệm giao diện Bác sĩ lâm sàng",
    badge: "CLINICAL",
    icon: "clinical-notes",
    targetHref: "/dashboard",
  },
  {
    mode: "research",
    label: "Nghiên cứu (Research)",
    shortLabel: "Nghiên cứu",
    description: "Trải nghiệm giao diện Nhà nghiên cứu y khoa",
    badge: "RESEARCH",
    icon: "search",
    targetHref: "/evidence",
  },
  {
    mode: "personal",
    label: "Cá nhân (Personal)",
    shortLabel: "Cá nhân",
    description: "Trải nghiệm giao diện Người dùng / Bệnh nhân",
    badge: "PERSONAL",
    icon: "user-card",
    targetHref: "/today",
  },
];

const BADGE_TONE_CLASSES: Record<
  "brand" | "clinical" | "research" | "admin",
  string
> = {
  brand: "bg-sky-950/80 text-sky-300 border-sky-600/40",
  clinical: "bg-teal-950/80 text-teal-300 border-teal-600/40",
  research: "bg-purple-950/80 text-purple-300 border-purple-600/40",
  admin: "bg-amber-950/80 text-amber-300 border-amber-600/40",
};

export interface WorkspaceSwitcherProps {
  currentWorkspace?: WorkspaceId;
  onWorkspaceChange?: (workspace: WorkspaceId) => void;
  role?: UserRole;
  adminPreviewMode?: AdminPreviewMode | null;
  onAdminPreviewChange?: (mode: AdminPreviewMode | null) => void;
  className?: string;
  triggerClassName?: string;
  menuClassName?: string;
  align?: "left" | "right";
  showDescriptions?: boolean;
}

/**
 * WorkspaceSwitcher: Standalone dropdown component using ChromeSurface (variant="menu").
 * - Lists permitted workspaces with icons, badges, descriptions, and 1-click active switch.
 * - For Admin: lists Admin Preview options (clinical, research, personal) with immediate route navigation.
 */
export function WorkspaceSwitcher({
  currentWorkspace: propCurrentWorkspace,
  onWorkspaceChange,
  role: propRole,
  adminPreviewMode: propAdminPreviewMode,
  onAdminPreviewChange,
  className = "",
  triggerClassName = "",
  menuClassName = "",
  align = "left",
  showDescriptions = true,
}: WorkspaceSwitcherProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useContext(SessionContext);

  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const effectiveRole: UserRole = propRole ?? session?.role ?? "normal";
  const activePreviewMode: AdminPreviewMode | null =
    propAdminPreviewMode !== undefined
      ? propAdminPreviewMode
      : session?.adminPreviewMode ?? null;

  const setPreviewMode = useCallback(
    (mode: AdminPreviewMode | null) => {
      if (onAdminPreviewChange) {
        onAdminPreviewChange(mode);
      } else if (session?.setAdminPreviewMode) {
        session.setAdminPreviewMode(mode);
      }
    },
    [onAdminPreviewChange, session],
  );

  // Derive current active workspace
  const activeWorkspace: WorkspaceId = useMemo(() => {
    if (propCurrentWorkspace) return propCurrentWorkspace;
    if (activePreviewMode) return activePreviewMode;
    if (propRole) return getDefaultWorkspace(propRole);
    return getWorkspaceForPath(pathname, effectiveRole);
  }, [propCurrentWorkspace, activePreviewMode, propRole, pathname, effectiveRole]);

  const activeOption = WORKSPACE_OPTIONS[activeWorkspace] ?? WORKSPACE_OPTIONS.personal;

  // Filter permitted workspaces for current role
  const permittedWorkspaces = useMemo(() => {
    return Object.values(WORKSPACE_OPTIONS).filter((ws) =>
      isWorkspaceAvailable(effectiveRole, ws.id),
    );
  }, [effectiveRole]);

  const isAdmin = effectiveRole === "admin";

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // Close dropdown on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Handle standard workspace selection
  const handleSelectWorkspace = useCallback(
    (wsId: WorkspaceId) => {
      const option = WORKSPACE_OPTIONS[wsId];
      if (!option) return;

      // If in admin preview and selecting a real workspace, reset preview
      if (isAdmin && activePreviewMode) {
        setPreviewMode(null);
      }

      onWorkspaceChange?.(wsId);
      setIsOpen(false);
      router.push(option.homeHref);
    },
    [isAdmin, activePreviewMode, setPreviewMode, onWorkspaceChange, router],
  );

  // Handle admin preview selection
  const handleSelectPreview = useCallback(
    (preview: WorkspaceSwitcherPreviewOption) => {
      setPreviewMode(preview.mode);
      onWorkspaceChange?.(preview.mode as WorkspaceId);
      setIsOpen(false);
      router.push(preview.targetHref);
    },
    [setPreviewMode, onWorkspaceChange, router],
  );

  // Handle exiting admin preview
  const handleExitPreview = useCallback(() => {
    setPreviewMode(null);
    onWorkspaceChange?.("admin");
    setIsOpen(false);
    router.push("/admin/overview");
  }, [setPreviewMode, onWorkspaceChange, router]);

  return (
    <div
      ref={containerRef}
      className={["relative inline-block text-left", className].join(" ")}
      data-testid="workspace-switcher"
    >
      {/* Switcher Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label="Chuyển không gian làm việc"
        data-testid="workspace-switcher-trigger"
        className={[
          "group inline-flex items-center gap-2 rounded-xl border border-[color:var(--shell-border)]/70",
          "bg-[var(--surface-header)]/80 px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)]",
          "shadow-sm backdrop-blur-md transition hover:bg-[var(--surface-muted)] hover:border-[color:var(--brand-500)]/40",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
          triggerClassName,
        ].join(" ")}
      >
        <span
          className={[
            "flex h-5 w-5 items-center justify-center rounded-lg border",
            BADGE_TONE_CLASSES[activeOption.badgeTone],
          ].join(" ")}
        >
          <Icon name={activeOption.icon} size={13} aria-hidden="true" />
        </span>

        <span className="font-bold tracking-tight">{activeOption.label}</span>

        {activePreviewMode && (
          <span className="rounded bg-amber-950/90 border border-amber-600/60 px-1.5 py-0.2 text-[9px] font-bold text-amber-300 uppercase tracking-wider">
            Preview
          </span>
        )}

        <Icon
          name="chevron-down"
          size={14}
          className={[
            "text-[var(--text-muted)] transition-transform duration-200",
            isOpen ? "rotate-180 text-[var(--text-primary)]" : "",
          ].join(" ")}
          aria-hidden="true"
        />
      </button>

      {/* Dropdown Menu Panel */}
      {isOpen && (
        <ChromeSurface
          variant="menu"
          elevation="overlay"
          role="menu"
          aria-label="Danh sách không gian làm việc"
          data-testid="workspace-switcher-menu"
          className={[
            "absolute top-[calc(100%+0.5rem)] z-50 w-72 sm:w-80 rounded-2xl p-2",
            "border border-[color:var(--shell-border)] shadow-2xl",
            align === "right" ? "right-0" : "left-0",
            menuClassName,
          ].join(" ")}
        >
          {/* Header / Active Context */}
          <div className="px-2 py-1.5 border-b border-[color:var(--shell-border)]/50">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Không gian làm việc
              </span>
              <span className="text-[10px] font-semibold text-[var(--text-secondary)]">
                {permittedWorkspaces.length} được cấp quyền
              </span>
            </div>
          </div>

          {/* Permitted Workspaces List */}
          <div className="py-1 space-y-1" role="group" aria-label="Không gian được cấp phép">
            {permittedWorkspaces.map((ws) => {
              const isActive =
                activeWorkspace === ws.id && activePreviewMode === null;

              return (
                <button
                  key={ws.id}
                  type="button"
                  role="menuitem"
                  data-testid={`workspace-item-${ws.id}`}
                  onClick={() => handleSelectWorkspace(ws.id)}
                  className={[
                    "w-full flex items-start gap-2.5 rounded-xl p-2 text-left transition duration-150",
                    "focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--brand-500)]",
                    isActive
                      ? "bg-[var(--surface-active)] text-[var(--text-brand)] shadow-inner font-semibold"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border mt-0.5",
                      BADGE_TONE_CLASSES[ws.badgeTone],
                    ].join(" ")}
                  >
                    <Icon name={ws.icon} size={15} aria-hidden="true" />
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span
                        className={[
                          "text-xs font-bold truncate",
                          isActive
                            ? "text-[var(--text-brand)]"
                            : "text-[var(--text-primary)]",
                        ].join(" ")}
                      >
                        {ws.label}
                      </span>

                      <span
                        className={[
                          "rounded px-1.5 py-0.2 text-[9px] font-semibold border",
                          BADGE_TONE_CLASSES[ws.badgeTone],
                        ].join(" ")}
                      >
                        {ws.badge}
                      </span>
                    </div>

                    {showDescriptions && (
                      <p className="mt-0.5 text-[11px] text-[var(--text-muted)] line-clamp-1">
                        {ws.description}
                      </p>
                    )}
                  </div>

                  {isActive && (
                    <span className="shrink-0 text-[var(--brand-500)] mt-1">
                      <Icon name="check" size={15} aria-hidden="true" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Admin Preview Section (Admin Only) */}
          {isAdmin && (
            <div className="mt-1 pt-1.5 border-t border-[color:var(--shell-border)]/60">
              <div className="px-2 py-1 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Icon
                    name="eye"
                    size={13}
                    className="text-amber-400"
                    aria-hidden="true"
                  />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                    Admin Preview
                  </span>
                </div>
                <span className="text-[10px] text-[var(--text-muted)]">
                  UI Mock Only
                </span>
              </div>

              <div className="space-y-1 pt-1" role="group" aria-label="Tùy chọn Admin Preview">
                {WORKSPACE_SWITCHER_PREVIEW_OPTIONS.map((preview) => {
                  const isCurrentPreview = activePreviewMode === preview.mode;

                  return (
                    <button
                      key={preview.mode}
                      type="button"
                      role="menuitem"
                      data-testid={`admin-preview-item-${preview.mode}`}
                      onClick={() => handleSelectPreview(preview)}
                      className={[
                        "w-full flex items-start gap-2.5 rounded-xl p-2 text-left transition duration-150",
                        "focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-500",
                        isCurrentPreview
                          ? "bg-amber-950/60 border border-amber-600/60 text-amber-200 font-semibold"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-amber-200",
                      ].join(" ")}
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-amber-600/40 bg-amber-950/80 text-amber-300 mt-0.5">
                        <Icon name={preview.icon} size={15} aria-hidden="true" />
                      </span>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-bold text-amber-200 truncate">
                            {preview.label}
                          </span>
                          <span className="rounded bg-amber-950 border border-amber-600/60 px-1 text-[9px] font-bold text-amber-300">
                            {preview.badge}
                          </span>
                        </div>

                        {showDescriptions && (
                          <p className="mt-0.5 text-[11px] text-[var(--text-muted)] line-clamp-1">
                            {preview.description}
                          </p>
                        )}
                      </div>

                      {isCurrentPreview && (
                        <span className="shrink-0 text-amber-400 mt-1">
                          <Icon name="check" size={15} aria-hidden="true" />
                        </span>
                      )}
                    </button>
                  );
                })}

                {/* Exit Preview Option */}
                {activePreviewMode && (
                  <button
                    type="button"
                    role="menuitem"
                    data-testid="admin-preview-exit"
                    onClick={handleExitPreview}
                    className="mt-1 w-full flex items-center justify-center gap-1.5 rounded-xl bg-amber-950/90 border border-amber-600/70 p-2 text-xs font-bold text-amber-200 hover:bg-amber-900 transition active:scale-98"
                  >
                    <span>✕ Thoát chế độ xem trước</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </ChromeSurface>
      )}
    </div>
  );
}

export default WorkspaceSwitcher;
