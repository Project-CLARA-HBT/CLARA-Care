"use client";

import { useCallback, useContext } from "react";
import { useRouter } from "next/navigation";
import Icon, { type IconName } from "@/components/ui/icon";
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import { SessionContext } from "./session-boundary";
import type { AdminPreviewPersona } from "@/lib/workspace/workspace.contract";

export type { AdminPreviewPersona };

export interface PreviewBannerProps {
  className?: string;
  onPersonaChange?: (persona: AdminPreviewPersona | null) => void;
}

export type AdminPreviewBannerProps = PreviewBannerProps;

interface PreviewPersonaConfig {
  persona: AdminPreviewPersona;
  labelVi: string;
  code: string;
  badgeClass: string;
  activeBtnClass: string;
  icon: IconName;
  homeHref: string;
}

const PREVIEW_PERSONAS: Record<AdminPreviewPersona, PreviewPersonaConfig> = {
  clinical: {
    persona: "clinical",
    labelVi: "Bác sĩ",
    code: "CLINICAL",
    badgeClass: "bg-emerald-950 text-emerald-200 border-emerald-500/60 ring-1 ring-emerald-500/30",
    activeBtnClass: "bg-emerald-900 text-emerald-100 ring-1 ring-emerald-400 font-bold shadow-sm",
    icon: "clinical-notes",
    homeHref: "/dashboard",
  },
  research: {
    persona: "research",
    labelVi: "Nghiên cứu",
    code: "RESEARCH",
    badgeClass: "bg-purple-950 text-purple-200 border-purple-500/60 ring-1 ring-purple-500/30",
    activeBtnClass: "bg-purple-900 text-purple-100 ring-1 ring-purple-400 font-bold shadow-sm",
    icon: "search",
    homeHref: "/evidence",
  },
  personal: {
    persona: "personal",
    labelVi: "Cá nhân",
    code: "PERSONAL",
    badgeClass: "bg-sky-950 text-sky-200 border-sky-500/60 ring-1 ring-sky-500/30",
    activeBtnClass: "bg-sky-900 text-sky-100 ring-1 ring-sky-400 font-bold shadow-sm",
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
    activeClass: "bg-amber-950 text-amber-200 shadow-sm font-bold",
    title: "Chế độ Quản trị (Admin Workbench)",
    homeHref: "/admin/overview",
  },
  {
    key: "clinical",
    persona: "clinical",
    label: "Bác sĩ",
    icon: "clinical-notes",
    activeClass: "bg-emerald-900 text-emerald-100 ring-1 ring-emerald-400 font-bold shadow-sm",
    title: "Chế độ Bác sĩ (Clinical)",
    homeHref: "/dashboard",
  },
  {
    key: "research",
    persona: "research",
    label: "Nghiên cứu",
    icon: "search",
    activeClass: "bg-purple-900 text-purple-100 ring-1 ring-purple-400 font-bold shadow-sm",
    title: "Chế độ Nghiên cứu (Research)",
    homeHref: "/evidence",
  },
  {
    key: "personal",
    persona: "personal",
    label: "Cá nhân",
    icon: "user-card",
    activeClass: "bg-sky-900 text-sky-100 ring-1 ring-sky-400 font-bold shadow-sm",
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

export function PreviewBanner({
  className = "",
  onPersonaChange,
}: PreviewBannerProps) {
  const router = useSafeRouter();
  const workspace = useContext(WorkspaceContext);
  const session = useContext(SessionContext);

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

  const personaUpper = adminPreviewPersona.toUpperCase();
  const currentConfig = PREVIEW_PERSONAS[adminPreviewPersona] || {
    persona: adminPreviewPersona,
    labelVi: adminPreviewPersona,
    code: personaUpper,
    badgeClass:
      "bg-amber-950 text-amber-300 border-amber-700/60 ring-1 ring-amber-500/30",
    activeBtnClass: "bg-amber-950 text-amber-200",
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

  return (
    <aside
      role="status"
      aria-label="Admin Preview Banner"
      data-testid="admin-preview-banner"
      data-preview-persona={adminPreviewPersona}
      className={[
        "sticky top-0 z-50 flex min-h-[38px] w-full flex-wrap items-center justify-between gap-2.5 border-b border-amber-500/50 bg-amber-400 text-amber-950 px-3 sm:px-4 py-1.5 text-xs font-semibold shadow-md backdrop-blur-md",
        className,
      ].join(" ")}
    >
      <span
        className="sr-only"
        data-testid="preview-context-strip"
        data-preview-persona={adminPreviewPersona}
      >
        Admin Preview · Clinical ({personaUpper})
      </span>
      {/* Left: Active Mode Badge */}
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <span
          data-testid={`preview-badge-${adminPreviewPersona}`}
          className={[
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider shadow-sm border",
            currentConfig.badgeClass,
          ].join(" ")}
        >
          <Icon name={currentConfig.icon} size={13} aria-hidden="true" />
          <span>ADMIN PREVIEW · {personaUpper}</span>
          <span className="opacity-80 font-normal">({currentConfig.labelVi})</span>
        </span>
        <span className="text-[11px] font-medium text-amber-950/90">
          Admin Preview · {currentConfig.labelVi} (Presentation only · RBAC unchanged)
        </span>
      </div>

      {/* Right: Inline Quick-Switcher Button Group */}
      <div
        className="flex flex-wrap items-center gap-1.5"
        role="group"
        aria-label="Admin Preview Quick Switcher"
        data-testid="admin-preview-quick-switcher"
      >
        <div className="inline-flex items-center divide-x divide-amber-900/20 rounded-md bg-amber-950/15 p-0.5 border border-amber-900/30 shadow-inner">
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
                  "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-900",
                  item.key === "admin"
                    ? "rounded-l"
                    : item.key === "personal"
                      ? "rounded-r"
                      : "",
                  isActive
                    ? item.activeClass
                    : "text-amber-950 hover:bg-amber-500/50 hover:text-black",
                ].join(" ")}
              >
                <Icon name={item.icon} size={12} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => handleSwitchMode(null, "/admin/overview")}
          data-testid="preview-exit-btn"
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-amber-950/90 px-2.5 py-1 text-xs font-bold text-amber-200 shadow-sm transition hover:bg-amber-950 hover:text-white active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-900"
          aria-label="✕ Thoát Preview"
          title="Thoát chế độ xem trước"
        >
          <span>✕ Thoát Preview</span>
        </button>
      </div>
    </aside>
  );
}

export const AdminPreviewBanner = PreviewBanner;
export default PreviewBanner;
