"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import Icon from "@/components/ui/icon";
import { ChromeSurface } from "@/components/shell/chrome-surface";
import { useUILanguage } from "@/lib/use-ui-language";
import { useOrganizationSafe } from "./organization-provider";
import type { OrganizationItem } from "@/lib/organization-context";

export interface OrganizationSwitcherProps {
  className?: string;
  triggerClassName?: string;
  menuClassName?: string;
  align?: "left" | "right";
  onOrganizationChange?: (orgId: string) => void;
  showManageLink?: boolean;
  compact?: boolean;
}

const TIER_BADGE_CLASSES: Record<string, string> = {
  hospital: "bg-red-950/80 text-red-300 border-red-600/40",
  enterprise: "bg-purple-950/80 text-purple-300 border-purple-600/40",
  professional: "bg-teal-950/80 text-teal-300 border-teal-600/40",
  standard: "bg-sky-950/80 text-sky-300 border-sky-600/40",
  starter: "bg-slate-900/80 text-slate-300 border-slate-700/40",
};

const TIER_LABELS: Record<string, { vi: string; en: string }> = {
  hospital: { vi: "Bệnh viện", en: "Hospital" },
  enterprise: { vi: "Hệ sinh thái Y tế", en: "Enterprise" },
  professional: { vi: "Phòng khám", en: "Clinic" },
  standard: { vi: "Cơ sở Y tế", en: "Facility" },
  starter: { vi: "Chuyên khoa", en: "Practice" },
};

const ROLE_LABELS: Record<string, { vi: string; en: string }> = {
  owner: { vi: "Chủ sở hữu", en: "Owner" },
  admin: { vi: "Quản trị", en: "Admin" },
  clinician: { vi: "Bác sĩ điều trị", en: "Clinician" },
  member: { vi: "Thành viên", en: "Member" },
  viewer: { vi: "Xem hồ sơ", en: "Viewer" },
};

/**
 * OrganizationSwitcher: Healthcare facility & multi-tenant organization selector.
 * - Displays active hospital/clinic organization context.
 * - Allows 1-click switching with automated cache partition purging.
 * - Enforces anti-IDOR boundaries and zero cross-tenant contamination.
 */
export function OrganizationSwitcher({
  className = "",
  triggerClassName = "",
  menuClassName = "",
  align = "left",
  onOrganizationChange,
  showManageLink = true,
  compact = false,
}: OrganizationSwitcherProps) {
  const language = useUILanguage();
  const copy = useCallback(
    (vi: string, en: string) => (language === "vi" ? vi : en),
    [language],
  );

  const orgContext = useOrganizationSafe();
  const organizations = orgContext?.organizations ?? [];
  const activeOrganization = orgContext?.activeOrganization ?? null;
  const activeOrganizationId = orgContext?.activeOrganizationId ?? null;
  const switchOrganization = orgContext?.switchOrganization;
  const isSwitching = orgContext?.isSwitching ?? false;

  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close dropdown on outside click
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

  const handleSelectOrg = useCallback(
    async (org: OrganizationItem) => {
      if (org.id === activeOrganizationId) {
        setIsOpen(false);
        return;
      }
      if (switchOrganization) {
        await switchOrganization(org.id);
      }
      onOrganizationChange?.(org.id);
      setIsOpen(false);
    },
    [activeOrganizationId, switchOrganization, onOrganizationChange],
  );

  // Fallback state when user has no organization affiliations
  if (organizations.length === 0) {
    return (
      <div
        className={["inline-flex items-center gap-1.5 text-xs text-[var(--text-muted)]", className].join(" ")}
        data-testid="organization-switcher-empty"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-lg border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]">
          <Icon name="contact" size={12} aria-hidden="true" />
        </span>
        <span className="font-medium text-[11px]">
          {copy("Độc lập / Cá nhân", "Independent / Personal")}
        </span>
      </div>
    );
  }

  const activeTier = activeOrganization?.tier ?? "standard";
  const activeTierLabel =
    TIER_LABELS[activeTier]?.[language === "vi" ? "vi" : "en"] ??
    TIER_LABELS.standard[language === "vi" ? "vi" : "en"];
  const activeBadgeTone = TIER_BADGE_CLASSES[activeTier] ?? TIER_BADGE_CLASSES.standard;

  return (
    <div
      ref={containerRef}
      className={["relative inline-block text-left", className].join(" ")}
      data-testid="organization-switcher"
    >
      {/* Switcher Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={isSwitching}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={copy("Chuyển cơ sở y tế / tổ chức", "Switch healthcare facility / organization")}
        data-testid="organization-switcher-trigger"
        className={[
          "group inline-flex items-center gap-2 rounded-xl border border-[color:var(--shell-border)]/70",
          "bg-[var(--surface-header)]/85 px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)]",
          "shadow-xs backdrop-blur-md transition hover:bg-[var(--surface-muted)] hover:border-[color:var(--brand-500)]/40",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
          isSwitching ? "opacity-60 cursor-wait" : "",
          triggerClassName,
        ].join(" ")}
      >
        {/* Tier / Facility Icon Badge */}
        <span
          className={[
            "flex h-5 w-5 shrink-0 items-center justify-center rounded-lg border",
            activeBadgeTone,
          ].join(" ")}
        >
          <Icon name={activeTier === "hospital" ? "activity" : "contact"} size={13} aria-hidden="true" />
        </span>

        {/* Organization Name & Tier Pill */}
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-bold tracking-tight truncate max-w-[140px] sm:max-w-[200px]">
            {activeOrganization?.name ?? copy("Chọn tổ chức", "Select organization")}
          </span>
          {!compact && (
            <span
              className={[
                "hidden sm:inline-block rounded px-1.5 py-0.2 text-[9px] font-bold border uppercase tracking-wider",
                activeBadgeTone,
              ].join(" ")}
            >
              {activeTierLabel}
            </span>
          )}
        </div>

        {/* Chevron Dropdown Indicator */}
        {organizations.length > 1 && (
          <Icon
            name="chevron-down"
            size={13}
            className={[
              "text-[var(--text-muted)] transition-transform duration-200",
              isOpen ? "rotate-180 text-[var(--text-primary)]" : "",
            ].join(" ")}
            aria-hidden="true"
          />
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && organizations.length > 1 && (
        <ChromeSurface
          variant="menu"
          elevation="overlay"
          role="menu"
          aria-label={copy("Danh sách cơ sở y tế", "Healthcare organizations list")}
          data-testid="organization-switcher-menu"
          className={[
            "absolute top-[calc(100%+0.5rem)] z-50 w-72 sm:w-80 rounded-2xl p-2",
            "border border-[color:var(--shell-border)] shadow-2xl",
            align === "right" ? "right-0" : "left-0",
            menuClassName,
          ].join(" ")}
        >
          {/* Menu Header */}
          <div className="px-2 py-1.5 border-b border-[color:var(--shell-border)]/50">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {copy("Cơ sở Y tế & Tổ chức", "Healthcare Organizations")}
              </span>
              <span className="text-[10px] font-semibold text-[var(--text-secondary)]">
                {copy(`${organizations.length} cơ sở`, `${organizations.length} facilities`)}
              </span>
            </div>
          </div>

          {/* List of Organizations */}
          <div className="py-1 space-y-1" role="group" aria-label="Danh sách tổ chức">
            {organizations.map((org) => {
              const isActive = org.id === activeOrganizationId;
              const tierLabel =
                TIER_LABELS[org.tier]?.[language === "vi" ? "vi" : "en"] ??
                TIER_LABELS.standard[language === "vi" ? "vi" : "en"];
              const badgeTone = TIER_BADGE_CLASSES[org.tier] ?? TIER_BADGE_CLASSES.standard;
              const roleLabel = org.user_role
                ? ROLE_LABELS[org.user_role]?.[language === "vi" ? "vi" : "en"] ?? org.user_role
                : null;

              return (
                <button
                  key={org.id}
                  type="button"
                  role="menuitem"
                  data-testid={`org-item-${org.id}`}
                  onClick={() => void handleSelectOrg(org)}
                  className={[
                    "w-full flex items-start gap-2.5 rounded-xl p-2 text-left transition duration-150",
                    "focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--brand-500)]",
                    isActive
                      ? "bg-[var(--surface-active)] text-[var(--text-brand)] shadow-inner font-semibold"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  {/* Facility Icon */}
                  <span
                    className={[
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border mt-0.5",
                      badgeTone,
                    ].join(" ")}
                  >
                    <Icon
                      name={org.tier === "hospital" ? "activity" : "contact"}
                      size={15}
                      aria-hidden="true"
                    />
                  </span>

                  {/* Org Metadata */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span
                        className={[
                          "text-xs font-bold truncate",
                          isActive ? "text-[var(--text-brand)]" : "text-[var(--text-primary)]",
                        ].join(" ")}
                      >
                        {org.name}
                      </span>
                      <span
                        className={[
                          "rounded px-1.5 py-0.2 text-[9px] font-semibold border",
                          badgeTone,
                        ].join(" ")}
                      >
                        {tierLabel}
                      </span>
                    </div>

                    <div className="mt-0.5 flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
                      {roleLabel && (
                        <span className="font-medium text-[var(--text-secondary)]">
                          {roleLabel}
                        </span>
                      )}
                      {org.workspace_count !== undefined && org.workspace_count > 0 && (
                        <span>
                          • {copy(`${org.workspace_count} khoa/phòng`, `${org.workspace_count} depts`)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Active Indicator Checkmark */}
                  {isActive && (
                    <span className="shrink-0 text-[var(--brand-500)] mt-1">
                      <Icon name="check" size={15} aria-hidden="true" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Manage / Add Organization Footer */}
          {showManageLink && (
            <div className="mt-1 pt-1.5 border-t border-[color:var(--shell-border)]/60 px-1">
              <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                <span>{copy("Độc lập dữ liệu theo Nghị định 13", "Tenant isolation via Decree 13")}</span>
                <span className="font-mono text-[10px]">Anti-IDOR</span>
              </div>
            </div>
          )}
        </ChromeSurface>
      )}
    </div>
  );
}

export default OrganizationSwitcher;
