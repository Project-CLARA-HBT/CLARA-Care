"use client";

import type { EntryContextDto } from "@/lib/api/v2-client";
import { Icon, type IconName } from "@/components/ui/icon";

export interface EntryContextBannerProps {
  context: EntryContextDto | null | undefined;
  onClear?: () => void;
  className?: string;
}

function resolveContextIcon(kind?: string): IconName {
  switch (kind?.toLowerCase()) {
    case "medication":
      return "medication";
    case "result":
    case "lab":
      return "scan";
    case "visit":
      return "calendar";
    case "timeline_period":
    case "timeline":
      return "progress";
    case "document":
      return "folder";
    default:
      return "clinical-notes";
  }
}

function resolveContextPrefix(kind?: string): string {
  switch (kind?.toLowerCase()) {
    case "medication":
      return "Hỏi về thuốc:";
    case "result":
    case "lab":
      return "Hỏi về kết quả:";
    case "visit":
      return "Hỏi về lần khám:";
    case "timeline_period":
    case "timeline":
      return "Hỏi về mốc thời gian:";
    case "document":
      return "Hỏi về tài liệu:";
    default:
      return "Bối cảnh câu hỏi:";
  }
}

export function EntryContextBanner({
  context,
  onClear,
  className = "",
}: EntryContextBannerProps) {
  if (!context || !context.kind || context.kind === "global") {
    return null;
  }

  const iconName = resolveContextIcon(context.kind);
  const prefix = resolveContextPrefix(context.kind);
  const label = context.label || context.resource_id || "Đã gắn bối cảnh";

  return (
    <div
      className={`flex items-center justify-between gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--brand-500)]/25 bg-[var(--surface-brand-soft)] px-3.5 py-2 text-xs font-medium text-[var(--text-brand)] shadow-sm ${className}`}
      data-testid="entry-context-banner"
    >
      <div className="flex min-w-0 items-center gap-2">
        <span
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-xs"
          aria-hidden="true"
        >
          <Icon name={iconName} size={14} />
        </span>
        <div className="min-w-0 truncate">
          <span className="font-semibold text-[var(--text-primary)]">{prefix} </span>
          <span className="font-medium text-[var(--text-brand)]" title={label}>
            {label}
          </span>
        </div>
      </div>

      {onClear ? (
        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-6 items-center gap-1 rounded-[var(--radius-md)] px-2 text-[11px] font-semibold text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-ring"
          title="Bỏ gắn bối cảnh này"
          aria-label="Bỏ gắn bối cảnh"
          data-testid="entry-context-clear-button"
        >
          <Icon name="close" size={13} aria-hidden="true" />
          <span className="hidden sm:inline">Hỏi chung</span>
        </button>
      ) : null}
    </div>
  );
}

export default EntryContextBanner;
