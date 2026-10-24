"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useUILanguage } from "@/lib/use-ui-language";
import type { MultiSourceContradiction } from "@/lib/lifemap-conflict-provenance";

export interface MultiSourceContradictionBannerProps {
  contradiction: MultiSourceContradiction;
  onInspect: (contradiction: MultiSourceContradiction) => void;
  className?: string;
}

export function MultiSourceContradictionBanner({
  contradiction,
  onInspect,
  className = "",
}: MultiSourceContradictionBannerProps) {
  const language = useUILanguage();
  const isEn = language === "en";

  const isResolved = contradiction.status === "resolved";

  const tone = isResolved
    ? "ok"
    : contradiction.severity === "critical"
      ? "danger"
      : contradiction.severity === "warning"
        ? "warn"
        : "neutral";

  const sourceAttributions = contradiction.sources
    .map((s) => s.attribution)
    .filter(Boolean)
    .slice(0, 2)
    .join(" ⚡ ");

  return (
    <div
      className={`rounded-xl border p-3 transition-colors ${
        isResolved
          ? "border-[var(--status-ok-border,#34a853)] bg-[var(--status-ok-bg,rgba(52,168,83,0.06))]"
          : contradiction.severity === "critical"
            ? "border-[var(--status-danger-border,#f87171)] bg-[var(--status-danger-bg,rgba(239,68,68,0.06))]"
            : "border-[var(--status-warn-border,#facc15)] bg-[var(--status-warn-bg,rgba(250,204,21,0.06))]"
      } ${className}`}
      data-testid={`contradiction-banner-${contradiction.id}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <Badge tone={tone}>
            {isResolved
              ? isEn
                ? "RESOLVED"
                : "ĐÃ XỬ LÝ"
              : contradiction.severity.toUpperCase()}
          </Badge>

          <div className="min-w-0">
            <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
              {contradiction.title}
            </p>
            {sourceAttributions ? (
              <p className="text-[11px] text-[var(--text-secondary)] truncate">
                {sourceAttributions}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            size="sm"
            variant="secondary"
            icon="search"
            onClick={() => onInspect(contradiction)}
            aria-label={
              isEn
                ? `Inspect contradiction for ${contradiction.fieldKey}`
                : `Kiểm tra mâu thuẫn cho ${contradiction.fieldKey}`
            }
          >
            {isResolved
              ? isEn
                ? "View Audit Trail"
                : "Xem kiểm toán"
              : isEn
                ? "Inspect & Resolve"
                : "Đối chiếu & Giải quyết"}
          </Button>
        </div>
      </div>
    </div>
  );
}
