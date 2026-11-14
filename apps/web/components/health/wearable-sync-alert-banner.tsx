"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  evaluateWearableFleet,
  type WearableFleetEvaluation,
  type WearableSyncEvaluation,
} from "@/lib/wearable-sync";
import type { ConnectedHealthSourceDto } from "@/lib/api/v2-client";
import { WearableReauthModal } from "@/components/health/wearable-reauth-modal";

export interface WearableSyncAlertBannerProps {
  sources?: ConnectedHealthSourceDto[] | null;
  locale?: "vi" | "en";
  onTriggerSync?: (sourceId: string) => Promise<void>;
  onReauthorizeSuccess?: () => void;
  className?: string;
  compact?: boolean;
}

export function WearableSyncAlertBanner({
  sources,
  locale = "vi",
  onTriggerSync,
  onReauthorizeSuccess,
  className = "",
  compact = false,
}: WearableSyncAlertBannerProps) {
  const isEn = locale === "en";
  const [activeReauthSource, setActiveReauthSource] = useState<ConnectedHealthSourceDto | null>(null);
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const fleet: WearableFleetEvaluation = useMemo(() => {
    return evaluateWearableFleet(sources);
  }, [sources]);

  if (dismissed || !sources || sources.length === 0) {
    return null;
  }

  // If all fresh or no connected sources, no warning needed
  if (fleet.allFresh || fleet.totalConnected === 0) {
    return null;
  }

  // If there are no issues at all
  if (!fleet.hasReauthRequired && !fleet.hasErrors && !fleet.hasStaleData) {
    return null;
  }

  const handleSyncClick = async (sourceId: string) => {
    if (!onTriggerSync) return;
    setSyncingSourceId(sourceId);
    try {
      await onTriggerSync(sourceId);
    } finally {
      setSyncingSourceId(null);
    }
  };

  // 1. Critical Priority: Reauthorization Required
  if (fleet.hasReauthRequired) {
    const primarySource = fleet.reauthSources[0].source;
    return (
      <>
        <div
          role="alert"
          aria-live="assertive"
          className={`rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-[var(--status-danger-text)] shadow-sm ${className}`}
          data-testid="wearable-reauth-alert-banner"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--status-danger-text)]/10 text-[var(--status-danger-text)]">
                <Icon name="warning" size="1.25rem" />
              </span>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold">
                    {isEn
                      ? `Reauthorization Required: ${primarySource.title}`
                      : `Cần cấp lại quyền: ${primarySource.title}`}
                  </h4>
                  <Badge tone="danger" size="sm">
                    {isEn ? "Action Required" : "Cần thao tác"}
                  </Badge>
                </div>
                <p className="text-xs opacity-90 leading-relaxed">
                  {primarySource.error_message ||
                    (isEn
                      ? "OAuth security grant expired or was revoked. Automated health data sync is paused."
                      : "Mã xác thực OAuth đã hết hạn hoặc bị thu hồi. Quá trình đồng bộ dữ liệu sinh hiệu đang tạm dừng.")}
                </p>
                {primarySource.recovery_guidance && !compact && (
                  <p className="text-[11px] font-semibold opacity-95">
                    {primarySource.recovery_guidance}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
              <Button
                type="button"
                variant="primary"
                size="sm"
                icon="refresh"
                onClick={() => setActiveReauthSource(primarySource)}
                data-testid="banner-reauth-btn"
              >
                {isEn ? "Reauthorize Now" : "Cấp lại quyền"}
              </Button>
              <Link
                href="/you/integrations"
                className="text-xs font-semibold underline underline-offset-2 px-2 hover:opacity-80"
              >
                {isEn ? "Manage" : "Chi tiết"}
              </Link>
            </div>
          </div>
        </div>

        {activeReauthSource && (
          <WearableReauthModal
            open={Boolean(activeReauthSource)}
            onClose={() => setActiveReauthSource(null)}
            source={activeReauthSource}
            locale={locale}
            onSuccess={() => {
              if (onReauthorizeSuccess) onReauthorizeSuccess();
            }}
          />
        )}
      </>
    );
  }

  // 2. High Priority: General Sync Errors
  if (fleet.hasErrors) {
    const errorEval = fleet.errorSources[0];
    const isSyncing = syncingSourceId === errorEval.source.id;
    return (
      <div
        role="alert"
        aria-live="polite"
        className={`rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-[var(--status-danger-text)] shadow-sm ${className}`}
        data-testid="wearable-sync-error-banner"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--status-danger-text)]/10 text-[var(--status-danger-text)]">
              <Icon name="warning" size="1.25rem" />
            </span>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold">
                  {isEn
                    ? `Wearable Sync Error: ${errorEval.source.title}`
                    : `Lỗi đồng bộ thiết bị: ${errorEval.source.title}`}
                </h4>
                <Badge tone="danger" size="sm">
                  {isEn ? "Sync Failed" : "Thất bại"}
                </Badge>
              </div>
              <p className="text-xs opacity-90 leading-relaxed">
                {errorEval.source.error_message ||
                  (isEn
                    ? "Failed to synchronize recent telemetry from your connected health device."
                    : "Không thể nhận dữ liệu sinh hiệu mới nhất từ thiết bị y tế đã kết nối.")}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onTriggerSync && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="refresh"
                loading={isSyncing}
                onClick={() => void handleSyncClick(errorEval.source.id)}
                data-testid="banner-retry-sync-btn"
              >
                {isEn ? "Retry Sync" : "Thử lại"}
              </Button>
            )}
            <Link
              href="/you/integrations"
              className="text-xs font-semibold underline underline-offset-2 px-2 hover:opacity-80"
            >
              {isEn ? "Settings" : "Cài đặt"}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 3. Medium Priority: Stale Data Warning (> 24 hours without sync)
  if (fleet.hasStaleData) {
    const staleEval = fleet.staleSources[0];
    const isSyncing = syncingSourceId === staleEval.source.id;
    const isCriticalStale = staleEval.staleSeverity === "critical";

    return (
      <div
        role="region"
        aria-label={isEn ? "Stale Wearable Data Warning" : "Cảnh báo dữ liệu thiết bị chưa cập nhật"}
        className={`rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-[var(--status-warn-text)] shadow-sm ${className}`}
        data-testid="wearable-stale-data-banner"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--status-warn-text)]/10 text-[var(--status-warn-text)]">
              <Icon name="progress" size="1.25rem" />
            </span>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold">
                  {isEn
                    ? `Wearable Data Not Updated: ${staleEval.source.title}`
                    : `Dữ liệu chưa cập nhật: ${staleEval.source.title}`}
                </h4>
                <Badge tone={isCriticalStale ? "danger" : "warn"} size="sm">
                  {isEn
                    ? staleEval.syncFreshnessText.en
                    : staleEval.syncFreshnessText.vi}
                </Badge>
              </div>
              <p className="text-xs opacity-90 leading-relaxed">
                {isEn
                  ? `Device metrics have not synchronized in over 24 hours (${staleEval.syncFreshnessText.en}). Displayed vitals may not reflect current physiological status.`
                  : `Chỉ số từ thiết bị chưa được đồng bộ trong hơn 24 giờ (${staleEval.syncFreshnessText.vi}). Dữ liệu hiển thị có thể không phản ánh chính xác tình trạng sinh hiệu hiện thời.`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onTriggerSync && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="refresh"
                loading={isSyncing}
                onClick={() => void handleSyncClick(staleEval.source.id)}
                data-testid="banner-stale-sync-btn"
              >
                {isEn ? "Sync Now" : "Đồng bộ ngay"}
              </Button>
            )}
            <Link
              href="/you/integrations"
              className="text-xs font-semibold underline underline-offset-2 px-2 hover:opacity-80"
            >
              {isEn ? "Check Devices" : "Kiểm tra thiết bị"}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
