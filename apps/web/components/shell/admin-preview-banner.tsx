"use client";

import Icon, { type IconName } from "@/components/ui/icon";
import { useSession, type AdminPreviewMode } from "./session-boundary";

export interface AdminPreviewBannerProps {
  className?: string;
}

interface PreviewModeConfig {
  mode: AdminPreviewMode;
  labelVi: string;
  code: string;
  badgeClass: string;
  activeBtnClass: string;
  icon: IconName;
}

const PREVIEW_MODES: Record<AdminPreviewMode, PreviewModeConfig> = {
  clinical: {
    mode: "clinical",
    labelVi: "Bác sĩ",
    code: "CLINICAL",
    badgeClass: "bg-teal-950 text-teal-200 border-teal-500/60 ring-1 ring-teal-500/30",
    activeBtnClass: "bg-teal-900 text-teal-100 ring-1 ring-teal-400 font-bold shadow-sm",
    icon: "clinical-notes",
  },
  research: {
    mode: "research",
    labelVi: "Nghiên cứu",
    code: "RESEARCH",
    badgeClass: "bg-purple-950 text-purple-200 border-purple-500/60 ring-1 ring-purple-500/30",
    activeBtnClass: "bg-purple-900 text-purple-100 ring-1 ring-purple-400 font-bold shadow-sm",
    icon: "search",
  },
  personal: {
    mode: "personal",
    labelVi: "Cá nhân",
    code: "PERSONAL",
    badgeClass: "bg-sky-950 text-sky-200 border-sky-500/60 ring-1 ring-sky-500/30",
    activeBtnClass: "bg-sky-900 text-sky-100 ring-1 ring-sky-400 font-bold shadow-sm",
    icon: "user-card",
  },
};

interface SwitcherItem {
  key: "admin" | AdminPreviewMode;
  mode: AdminPreviewMode | null;
  label: string;
  icon: IconName;
  activeClass: string;
  title: string;
}

const SWITCHER_ITEMS: SwitcherItem[] = [
  {
    key: "admin",
    mode: null,
    label: "Quản trị",
    icon: "settings",
    activeClass: "bg-amber-950 text-amber-200 shadow-sm font-bold",
    title: "Chế độ Quản trị (Admin Workbench)",
  },
  {
    key: "clinical",
    mode: "clinical",
    label: "Bác sĩ",
    icon: "clinical-notes",
    activeClass: "bg-teal-900 text-teal-100 ring-1 ring-teal-400 font-bold shadow-sm",
    title: "Chế độ Bác sĩ (Clinical)",
  },
  {
    key: "research",
    mode: "research",
    label: "Nghiên cứu",
    icon: "search",
    activeClass: "bg-purple-900 text-purple-100 ring-1 ring-purple-400 font-bold shadow-sm",
    title: "Chế độ Nghiên cứu (Research)",
  },
  {
    key: "personal",
    mode: "personal",
    label: "Cá nhân",
    icon: "user-card",
    activeClass: "bg-sky-900 text-sky-100 ring-1 ring-sky-400 font-bold shadow-sm",
    title: "Chế độ Cá nhân (Personal)",
  },
];

export function AdminPreviewBanner({ className = "" }: AdminPreviewBannerProps) {
  const { role, adminPreviewMode, setAdminPreviewMode } = useSession();

  if (role !== "admin" || !adminPreviewMode) {
    return null;
  }

  const modeUpper = adminPreviewMode.toUpperCase();
  const currentConfig = PREVIEW_MODES[adminPreviewMode] || {
    mode: adminPreviewMode,
    labelVi: adminPreviewMode,
    code: modeUpper,
    badgeClass: "bg-amber-950 text-amber-300 border-amber-700/60 ring-1 ring-amber-500/30",
    activeBtnClass: "bg-amber-950 text-amber-200",
    icon: "eye" as IconName,
  };

  return (
    <aside
      role="status"
      aria-label="Admin Preview Banner"
      data-testid="admin-preview-banner"
      className={[
        "sticky top-0 z-50 flex min-h-[38px] w-full flex-wrap items-center justify-between gap-2.5 border-b border-amber-500/50 bg-amber-400 text-amber-950 px-3 sm:px-4 py-1.5 text-xs font-semibold shadow-md backdrop-blur-md",
        className,
      ].join(" ")}
    >
      {/* Left: Active Mode Badge */}
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <span
          data-testid={`preview-badge-${adminPreviewMode}`}
          className={[
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider shadow-sm border",
            currentConfig.badgeClass,
          ].join(" ")}
        >
          <Icon name={currentConfig.icon} size={13} aria-hidden="true" />
          <span>ADMIN PREVIEW · {modeUpper}</span>
          <span className="opacity-80 font-normal">({currentConfig.labelVi})</span>
        </span>
        <span className="hidden sm:inline-block text-[11px] font-medium text-amber-950/80">
          (RBAC Untouched · UI Presentation Only)
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
            const isActive = adminPreviewMode === item.mode;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setAdminPreviewMode(item.mode)}
                aria-pressed={isActive}
                data-testid={`preview-switch-${item.key}`}
                title={item.title}
                className={[
                  "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold transition active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-900",
                  item.key === "admin" ? "rounded-l" : item.key === "personal" ? "rounded-r" : "",
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
          onClick={() => setAdminPreviewMode(null)}
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

export default AdminPreviewBanner;

