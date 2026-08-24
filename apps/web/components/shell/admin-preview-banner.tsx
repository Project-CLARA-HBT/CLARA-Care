"use client";

import Icon from "@/components/ui/icon";
import { useSession } from "./session-boundary";

export interface AdminPreviewBannerProps {
  className?: string;
}

export function AdminPreviewBanner({ className = "" }: AdminPreviewBannerProps) {
  const { role, adminPreviewMode, setAdminPreviewMode } = useSession();

  if (role !== "admin" || !adminPreviewMode) {
    return null;
  }

  const modeUpper = adminPreviewMode.toUpperCase();

  return (
    <aside
      role="status"
      aria-label="Admin Preview Banner"
      data-testid="admin-preview-banner"
      className={[
        "sticky top-0 z-50 flex min-h-[34px] w-full items-center justify-between gap-3 border-b border-amber-500/50 bg-amber-400 text-amber-950 px-4 py-1 text-xs font-semibold shadow-md backdrop-blur-md",
        className,
      ].join(" ")}
    >
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <span className="inline-flex items-center gap-1.5 rounded bg-amber-950 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-amber-300 shadow-sm">
          <Icon name="eye" size={13} aria-hidden="true" />
          <span>ADMIN PREVIEW · {modeUpper}</span>
        </span>
        <span className="text-[11px] font-medium text-amber-900">
          (RBAC Untouched · UI Presentation Only)
        </span>
      </div>

      <button
        type="button"
        onClick={() => setAdminPreviewMode(null)}
        className="inline-flex shrink-0 items-center gap-1 rounded bg-amber-950/90 px-2.5 py-1 text-xs font-bold text-amber-200 shadow-sm transition hover:bg-amber-950 hover:text-white active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-900"
        aria-label="Thoát Preview / Exit Preview"
      >
        <span>Thoát Preview / Exit Preview</span>
        <Icon name="close" size={13} aria-hidden="true" />
      </button>
    </aside>
  );
}

export default AdminPreviewBanner;
