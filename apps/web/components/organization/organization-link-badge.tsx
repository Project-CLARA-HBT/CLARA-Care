"use client";

import Icon from "@/components/ui/icon";
import { useUILanguage } from "@/lib/use-ui-language";

export interface OrganizationLinkBadgeProps {
  organizationName?: string | null;
  departmentName?: string | null;
  doctorName?: string | null;
  doctorCchn?: string | null;
  clinicTier?: "hospital" | "clinic" | "practice" | "standard" | string;
  isEmrLinked?: boolean;
  isTransfer?: boolean;
  variant?: "pill" | "compact" | "full";
  className?: string;
}

const TIER_STYLES: Record<string, { bg: string; border: string; text: string; vi: string; en: string }> = {
  hospital: {
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-400",
    vi: "Bệnh viện",
    en: "Hospital",
  },
  clinic: {
    bg: "bg-teal-500/10",
    border: "border-teal-500/30",
    text: "text-teal-400",
    vi: "Phòng khám",
    en: "Clinic",
  },
  practice: {
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    text: "text-purple-400",
    vi: "Chuyên khoa",
    en: "Practice",
  },
  standard: {
    bg: "bg-sky-500/10",
    border: "border-sky-500/30",
    text: "text-sky-400",
    vi: "Cơ sở Y tế",
    en: "Facility",
  },
};

/**
 * OrganizationLinkBadge: Surfaces provider and patient healthcare organization linkage,
 * facility affiliation, CCHN practitioner licensing, and cross-tier transfer indicators.
 */
export function OrganizationLinkBadge({
  organizationName = "Bệnh viện Bạch Mai",
  departmentName,
  doctorName,
  doctorCchn,
  clinicTier = "hospital",
  isEmrLinked = true,
  isTransfer = false,
  variant = "compact",
  className = "",
}: OrganizationLinkBadgeProps) {
  const language = useUILanguage();
  const copy = (vi: string, en: string) => (language === "vi" ? vi : en);

  const style = TIER_STYLES[clinicTier] ?? TIER_STYLES.standard;
  const tierLabel = language === "vi" ? style.vi : style.en;

  if (variant === "pill") {
    return (
      <span
        data-testid="org-link-badge-pill"
        className={[
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold border",
          style.bg,
          style.border,
          style.text,
          className,
        ].join(" ")}
      >
        <Icon name={clinicTier === "hospital" ? "activity" : "contact"} size={12} aria-hidden="true" />
        <span className="truncate max-w-[140px]">{organizationName}</span>
      </span>
    );
  }

  if (variant === "compact") {
    return (
      <div
        data-testid="org-link-badge-compact"
        className={[
          "inline-flex items-center gap-2 rounded-lg border px-2 py-1 text-xs",
          style.bg,
          style.border,
          className,
        ].join(" ")}
      >
        <span
          className={[
            "flex h-4 w-4 shrink-0 items-center justify-center rounded",
            style.text,
          ].join(" ")}
        >
          <Icon name={clinicTier === "hospital" ? "activity" : "contact"} size={13} aria-hidden="true" />
        </span>
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-bold text-[var(--text-primary)] truncate max-w-[150px]">
            {organizationName}
          </span>
          <span className={["rounded px-1 text-[9px] font-bold uppercase", style.text].join(" ")}>
            {tierLabel}
          </span>
        </div>
        {isEmrLinked && (
          <span
            className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium shrink-0"
            title={copy("Đồng bộ dữ liệu EMR tổ chức", "Synced with organization EMR")}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            EMR
          </span>
        )}
      </div>
    );
  }

  // Full variant for dossiers and clinical inspector headers
  return (
    <div
      data-testid="org-link-badge-full"
      className={[
        "rounded-[var(--radius-lg)] border p-3 text-xs space-y-2 backdrop-blur-md",
        style.bg,
        style.border,
        className,
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={[
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-md border",
              style.border,
              style.text,
            ].join(" ")}
          >
            <Icon name={clinicTier === "hospital" ? "activity" : "contact"} size={14} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="font-bold text-[var(--text-primary)] truncate">
              {organizationName}
            </div>
            {departmentName && (
              <div className="text-[11px] text-[var(--text-secondary)]">
                {departmentName}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <span className={["rounded px-1.5 py-0.5 text-[10px] font-bold border uppercase", style.border, style.text].join(" ")}>
            {tierLabel}
          </span>
          {isTransfer && (
            <span className="rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 px-1.5 py-0.5 text-[10px] font-bold uppercase">
              {copy("Chuyển viện", "Transfer")}
            </span>
          )}
        </div>
      </div>

      {(doctorName || doctorCchn) && (
        <div className="pt-1.5 border-t border-[color:var(--shell-border)]/50 flex flex-wrap items-center justify-between gap-1 text-[11px]">
          {doctorName && (
            <span className="text-[var(--text-primary)] font-semibold">
              {copy("Bác sĩ phụ trách:", "Attending:")} {doctorName}
            </span>
          )}
          {doctorCchn && (
            <span className="font-mono text-[var(--text-brand)]">
              {doctorCchn}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default OrganizationLinkBadge;
