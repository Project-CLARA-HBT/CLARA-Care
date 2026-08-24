"use client";

import { useCallback, useContext, useState } from "react";
import { useRouter } from "next/navigation";
import Icon, { type IconName } from "@/components/ui/icon";
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import { SessionContext } from "./session-boundary";
import type { AdminPreviewPersona } from "@/lib/workspace/workspace.contract";

export type { AdminPreviewPersona };

export interface PreviewContextStripProps {
  className?: string;
  defaultCollapsed?: boolean;
  isCollapsed?: boolean;
  onCollapseToggle?: (collapsed: boolean) => void;
  onPersonaChange?: (persona: AdminPreviewPersona | null) => void;
}

interface PersonaConfig {
  persona: AdminPreviewPersona;
  displayName: string;
  labelVi: string;
  badgeClass: string;
  activeBtnClass: string;
  icon: IconName;
  homeHref: string;
}

const PERSONA_CONFIGS: Record<AdminPreviewPersona, PersonaConfig> = {
  clinical: {
    persona: "clinical",
    displayName: "Clinical",
    labelVi: "Bác sĩ",
    badgeClass:
      "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-500/20",
    activeBtnClass:
      "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700/60 font-semibold shadow-xs",
    icon: "clinical-notes",
    homeHref: "/dashboard",
  },
  research: {
    persona: "research",
    displayName: "Research",
    labelVi: "Nghiên cứu",
    badgeClass:
      "bg-purple-500/10 text-purple-800 dark:text-purple-300 border-purple-500/20",
    activeBtnClass:
      "bg-purple-100 text-purple-900 dark:bg-purple-950/80 dark:text-purple-200 border-purple-300 dark:border-purple-700/60 font-semibold shadow-xs",
    icon: "search",
    homeHref: "/evidence",
  },
  personal: {
    persona: "personal",
    displayName: "Personal",
    labelVi: "Cá nhân",
    badgeClass:
      "bg-sky-500/10 text-sky-800 dark:text-sky-300 border-sky-500/20",
    activeBtnClass:
      "bg-sky-100 text-sky-900 dark:bg-sky-950/80 dark:text-sky-200 border-sky-300 dark:border-sky-700/60 font-semibold shadow-xs",
    icon: "user-card",
    homeHref: "/today",
  },
};

interface SwitcherItem {
  key: "admin" | AdminPreviewPersona;
  persona: AdminPreviewPersona | null;
  label: string;
  icon: IconName;
  activeClass: string;
  title: string;
  homeHref: string;
}

const SWITCHER_ITEMS: SwitcherItem[] = [
  {
    key: "admin",
    persona: null,
    label: "Quản trị",
    icon: "settings",
    activeClass:
      "bg-stone-200 text-stone-900 dark:bg-stone-700 dark:text-stone-100 font-semibold shadow-xs",
    title: "Chế độ Quản trị (Admin Workbench)",
    homeHref: "/admin/overview",
  },
  {
    key: "clinical",
    persona: "clinical",
    label: "Bác sĩ",
    icon: "clinical-notes",
    activeClass:
      "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700/60 font-semibold shadow-xs",
    title: "Chế độ Bác sĩ (Clinical)",
    homeHref: "/dashboard",
  },
  {
    key: "research",
    persona: "research",
    label: "Nghiên cứu",
    icon: "search",
    activeClass:
      "bg-purple-100 text-purple-900 dark:bg-purple-950/80 dark:text-purple-200 border-purple-300 dark:border-purple-700/60 font-semibold shadow-xs",
    title: "Chế độ Nghiên cứu (Research)",
    homeHref: "/evidence",
  },
  {
    key: "personal",
    persona: "personal",
    label: "Cá nhân",
    icon: "user-card",
    activeClass:
      "bg-sky-100 text-sky-900 dark:bg-sky-950/80 dark:text-sky-200 border-sky-300 dark:border-sky-700/60 font-semibold shadow-xs",
    title: "Chế độ Cá nhân (Personal)",
    homeHref: "/today",
  },
];

function useSafeRouter() {
  try {
    return useRouter();
  } catch {
    return {
      push: () => {},
      replace: () => {},
      refresh: () => {},
      back: () => {},
      forward: () => {},
      prefetch: () => {},
    };
  }
}

export function PreviewContextStrip({
  className = "",
  defaultCollapsed = false,
  isCollapsed: controlledCollapsed,
  onCollapseToggle,
  onPersonaChange,
}: PreviewContextStripProps) {
  const router = useSafeRouter();
  const workspace = useContext(WorkspaceContext);
  const session = useContext(SessionContext);

  const [uncontrolledCollapsed, setUncontrolledCollapsed] =
    useState(defaultCollapsed);

  const isCollapsed =
    controlledCollapsed !== undefined
      ? controlledCollapsed
      : uncontrolledCollapsed;

  const handleToggleCollapse = useCallback(() => {
    const next = !isCollapsed;
    if (controlledCollapsed === undefined) {
      setUncontrolledCollapsed(next);
    }
    onCollapseToggle?.(next);
  }, [isCollapsed, controlledCollapsed, onCollapseToggle]);

  const adminPreviewPersona =
    workspace?.adminPreviewPersona ?? session?.adminPreviewMode ?? null;

  const setAdminPreviewPersona = useCallback(
    (persona: AdminPreviewPersona | null) => {
      if (workspace?.setAdminPreviewPersona) {
        workspace.setAdminPreviewPersona(persona);
      }
      if (session?.setAdminPreviewMode) {
        session.setAdminPreviewMode(persona);
      }
      onPersonaChange?.(persona);
    },
    [workspace, session, onPersonaChange],
  );

  const role = session?.role;
  if (role && role !== "admin") {
    return null;
  }
  if (!adminPreviewPersona) {
    return null;
  }

  const currentConfig = PERSONA_CONFIGS[adminPreviewPersona] || {
    persona: adminPreviewPersona,
    displayName:
      adminPreviewPersona.charAt(0).toUpperCase() +
      adminPreviewPersona.slice(1),
    labelVi: adminPreviewPersona,
    badgeClass:
      "bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/20",
    activeBtnClass: "bg-stone-200 dark:bg-stone-700 text-stone-900 dark:text-stone-100",
    icon: "eye" as IconName,
    homeHref: "/dashboard",
  };

  const handleSwitchMode = (
    nextPersona: AdminPreviewPersona | null,
    targetHref: string,
  ) => {
    setAdminPreviewPersona(nextPersona);
    try {
      router.push(targetHref);
    } catch {
      // noop
    }
  };

  // When collapsed: render an unobtrusive mini strip (height <= 32px) with expand trigger
  if (isCollapsed) {
    return (
      <aside
        role="status"
        aria-label="Admin Preview Strip (Collapsed)"
        data-testid="preview-context-strip-collapsed"
        data-preview-persona={adminPreviewPersona}
        className={[
          "sticky top-0 z-40 flex h-7 min-h-[24px] max-h-[32px] w-full items-center justify-between border-b border-stone-200/80 bg-stone-100/95 px-3 text-xs text-stone-600 backdrop-blur-md dark:border-stone-800 dark:bg-stone-900/95 dark:text-stone-400",
          className,
        ].join(" ")}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" aria-hidden="true" />
          <span className="font-semibold text-stone-800 dark:text-stone-200 truncate">
            Admin Preview · {currentConfig.displayName}
          </span>
          <span className="hidden sm:inline text-[11px] text-stone-500 dark:text-stone-400">
            (Thu gọn)
          </span>
        </div>

        <button
          type="button"
          onClick={handleToggleCollapse}
          aria-expanded={false}
          aria-label="Mở rộng preview strip"
          data-testid="preview-expand-toggle"
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium text-stone-700 hover:bg-stone-200/60 dark:text-stone-300 dark:hover:bg-stone-800 transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-stone-400"
        >
          <Icon name="chevron-down" size={12} aria-hidden="true" />
          <span>Mở rộng</span>
        </button>
      </aside>
    );
  }

  return (
    <aside
      role="status"
      aria-label="Admin Preview Strip"
      data-testid="preview-context-strip"
      data-preview-persona={adminPreviewPersona}
      className={[
        "sticky top-0 z-40 flex h-7 sm:h-8 min-h-[24px] max-h-[32px] w-full items-center justify-between gap-2 border-b border-stone-200/90 bg-stone-100/95 px-3 sm:px-4 text-xs font-medium text-stone-700 shadow-xs backdrop-blur-md dark:border-stone-800 dark:bg-stone-900/95 dark:text-stone-300",
        className,
      ].join(" ")}
    >
      {/* Left: Label & Subtitle */}
      <div className="flex items-center gap-2 sm:gap-2.5 min-w-0 overflow-hidden">
        {/* Semantic Warm Accent Pill */}
        <span
          data-testid={`preview-badge-${adminPreviewPersona}`}
          className={[
            "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-semibold tracking-wide border shrink-0",
            currentConfig.badgeClass,
          ].join(" ")}
        >
          <Icon name={currentConfig.icon} size={12} aria-hidden="true" />
          <span>Admin Preview · {currentConfig.displayName}</span>
        </span>

        {/* Subtitle: Presentation only · RBAC unchanged */}
        <span
          data-testid="preview-strip-subtitle"
          className="hidden md:inline-block text-[11px] font-normal text-stone-500 dark:text-stone-400 truncate"
        >
          Presentation only · RBAC unchanged
        </span>
      </div>

      {/* Right: Grouped Preview Persona Controls + Collapse Button */}
      <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
        <div
          className="inline-flex items-center rounded-md border border-stone-200/80 bg-stone-200/50 p-0.5 dark:border-stone-800 dark:bg-stone-800/60"
          role="group"
          aria-label="Admin Preview Controls"
          data-testid="admin-preview-quick-switcher"
        >
          {SWITCHER_ITEMS.map((item) => {
            const isActive = adminPreviewPersona === item.persona;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => handleSwitchMode(item.persona, item.homeHref)}
                aria-pressed={isActive}
                data-testid={`preview-switch-${item.key}`}
                title={item.title}
                className={[
                  "inline-flex items-center gap-1 rounded px-1.5 sm:px-2 py-0.5 text-[11px] sm:text-xs transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-stone-400",
                  isActive
                    ? item.activeClass
                    : "text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100 hover:bg-stone-200/60 dark:hover:bg-stone-700/50",
                ].join(" ")}
              >
                <Icon name={item.icon} size={11} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => handleSwitchMode(null, "/admin/overview")}
          data-testid="preview-exit-btn"
          className="inline-flex items-center gap-1 rounded bg-stone-800 px-2 py-0.5 text-[11px] sm:text-xs font-semibold text-stone-100 hover:bg-stone-900 dark:bg-stone-700 dark:text-stone-100 dark:hover:bg-stone-600 transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-stone-400"
          aria-label="✕ Thoát Preview"
          title="Thoát chế độ xem trước"
        >
          <span>✕ Thoát Preview</span>
        </button>

        {/* Collapsible toggle */}
        <button
          type="button"
          onClick={handleToggleCollapse}
          aria-expanded={true}
          aria-label="Thu gọn preview strip"
          data-testid="preview-collapse-toggle"
          title="Thu gọn preview strip"
          className="inline-flex items-center justify-center rounded p-0.5 text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200 hover:bg-stone-200/60 dark:hover:bg-stone-800 transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-stone-400"
        >
          <Icon name="close" size={12} aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}

export default PreviewContextStrip;
