"use client";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { formatFreshness, calculateHoursSinceSync } from "@/lib/wearable-sync";

export interface WearableStaleBadgeProps {
  recordedAt?: string | null;
  locale?: "vi" | "en";
  staleThresholdHours?: number;
  severity?: "warning" | "critical";
  compact?: boolean;
  className?: string;
}

export function WearableStaleBadge({
  recordedAt,
  locale = "vi",
  staleThresholdHours = 24,
  severity,
  compact = false,
  className = "",
}: WearableStaleBadgeProps) {
  const isEn = locale === "en";
  const hoursSince = calculateHoursSinceSync(recordedAt);

  const isCritical =
    severity === "critical" || (hoursSince !== null && hoursSince >= 72);

  const tone = isCritical ? "danger" : "warn";
  const freshness = formatFreshness(recordedAt, locale);

  const titleText = isEn
    ? `Measurement older than ${staleThresholdHours}h (${freshness}). May not reflect current physiological status.`
    : `Chỉ số đã đo cách đây hơn ${staleThresholdHours}h (${freshness}). Có thể không phản ánh chính xác trạng thái hiện tại.`;

  return (
    <span
      className={`inline-flex items-center gap-1 ${className}`}
      title={titleText}
      data-testid="wearable-stale-badge"
    >
      <Badge tone={tone} size="sm">
        <Icon name="warning" size="0.75rem" />
        <span>
          {compact
            ? isEn
              ? "Stale"
              : "Dữ liệu cũ"
            : isEn
              ? `Stale (${freshness})`
              : `Dữ liệu cũ (${freshness})`}
        </span>
      </Badge>
    </span>
  );
}
