"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type ConnectedHealthCategoryPermissionsDto,
  type ConnectedHealthSourceDto,
  type ConnectedHealthSourcesDto,
} from "@/lib/api/v2-client";

const CATEGORY_NAMES: Record<
  keyof ConnectedHealthCategoryPermissionsDto,
  { vi: string; en: string; icon: string }
> = {
  steps: { vi: "Số bước chân", en: "Step Count", icon: "body" },
  heart_rate: { vi: "Nhịp tim (BPM)", en: "Heart Rate", icon: "emergency" },
  blood_pressure: { vi: "Huyết áp (mmHg)", en: "Blood Pressure", icon: "progress" },
  sleep: { vi: "Giấc ngủ & Chu kỳ", en: "Sleep Analysis", icon: "calendar" },
  blood_glucose: { vi: "Đường huyết", en: "Blood Glucose", icon: "scan" },
  oxygen_saturation: { vi: "Nồng độ oxy SpO2", en: "Oxygen Saturation (SpO2)", icon: "scan" },
};

export default function YouIntegrationsPage() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());

  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  const {
    data: integrationsData,
    isLoading,
    error,
    refetch,
  } = useQuery<ConnectedHealthSourcesDto>({
    queryKey: queryKeys.profile(activeProfileId).you.integrations(),
    queryFn: async () => {
      try {
        return await v2Client.getIntegrations(activeProfileId);
      } catch {
        return {
          last_global_sync_at: "2026-08-20T08:30:00Z",
          sources: [
            {
              id: "health_connect",
              name: "health_connect",
              title: "Google Health Connect",
              description: isEn
                ? "Direct Android on-device sync for vitals, activity, and sleep."
                : "Đồng bộ trực tiếp trên thiết bị Android cho sinh hiệu, vận động và giấc ngủ.",
              connected: true,
              sync_enabled: true,
              last_sync_at: "2026-08-20T08:30:00Z",
              status: "active",
              category_permissions: {
                steps: true,
                heart_rate: true,
                blood_pressure: true,
                sleep: true,
                blood_glucose: false,
                oxygen_saturation: true,
              },
            },
            {
              id: "apple_health",
              name: "apple_health",
              title: "Apple Health (HealthKit)",
              description: isEn
                ? "Encrypted iOS HealthKit export for Apple Watch vitals and lab panels."
                : "Đồng bộ mã hóa từ Apple Health và Apple Watch cho chỉ số sinh hiệu.",
              connected: false,
              sync_enabled: false,
              last_sync_at: null,
              status: "disconnected",
              category_permissions: {
                steps: true,
                heart_rate: true,
                blood_pressure: true,
                sleep: false,
                blood_glucose: false,
                oxygen_saturation: false,
              },
            },
            {
              id: "garmin",
              name: "garmin",
              title: "Garmin Connect",
              description: isEn
                ? "Garmin Health API integration for continuous HRV and training load."
                : "Tích hợp Garmin Health API theo dõi biến thiên nhịp tim (HRV) và thể lực.",
              connected: true,
              sync_enabled: false,
              last_sync_at: "2026-08-18T10:00:00Z",
              status: "error",
              error_message: isEn
                ? "OAuth refresh token expired. Re-authentication required."
                : "Mã chứng thực OAuth đã hết hạn. Yêu cầu kết nối lại.",
              recovery_guidance: isEn
                ? "Click 'Reconnect' to refresh the secure API authorization grant."
                : "Nhấn 'Kết nối lại' để cấp lại quyền truy cập API an toàn.",
              category_permissions: {
                steps: true,
                heart_rate: true,
                blood_pressure: false,
                sleep: true,
                blood_glucose: false,
                oxygen_saturation: false,
              },
            },
          ],
        };
      }
    },
  });

  const handleToggleSync = async (source: ConnectedHealthSourceDto) => {
    setActionError("");
    setActionSuccess("");
    try {
      await v2Client.updateIntegrationSource(source.id, {
        sync_enabled: !source.sync_enabled,
      });
      void refetch();
    } catch {
      setActionError(
        isEn
          ? "Failed to update sync status. Please try again."
          : "Không thể cập nhật trạng thái đồng bộ. Vui lòng thử lại.",
      );
    }
  };

  const handleToggleCategoryPermission = async (
    source: ConnectedHealthSourceDto,
    categoryKey: keyof ConnectedHealthCategoryPermissionsDto,
  ) => {
    setActionError("");
    setActionSuccess("");
    try {
      const updatedCategories = {
        ...source.category_permissions,
        [categoryKey]: !source.category_permissions[categoryKey],
      };
      await v2Client.updateIntegrationSource(source.id, {
        category_permissions: updatedCategories,
      });
      void refetch();
    } catch {
      setActionError(
        isEn
          ? "Failed to update category permission."
          : "Không thể cập nhật quyền danh mục.",
      );
    }
  };

  const handleTriggerSync = async (sourceId: string) => {
    setSyncingSourceId(sourceId);
    setActionError("");
    setActionSuccess("");
    try {
      await v2Client.syncIntegrationSource(sourceId);
      setActionSuccess(
        isEn
          ? "Data synchronization triggered successfully."
          : "Đã kích hoạt đồng bộ dữ liệu thành công.",
      );
      void refetch();
    } catch {
      setActionError(
        isEn
          ? "Sync failed. Check device connectivity or reconnect source."
          : "Đồng bộ thất bại. Kiểm tra kết nối thiết bị hoặc thử kết nối lại.",
      );
    } finally {
      setSyncingSourceId(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="you-integrations-page">
      <HealthPageHeader
        title={isEn ? "Connected Health & Wearables" : "Nguồn dữ liệu Sức khỏe & Thiết bị"}
        subtitle={
          isEn
            ? "Connect Apple Health, Google Health Connect, and wearables with granular per-metric sync permissions and recovery guidance."
            : "Kết nối Apple Health, Health Connect và thiết bị đeo với phân quyền từng chỉ số và hướng dẫn khắc phục lỗi."
        }
        backHref="/you"
        backLabel={isEn ? "Back to You" : "Quay lại Cá nhân"}
      />

      {error ? (
        <InlineError
          message={isEn ? "Unable to load integrations" : "Không thể tải danh sách kết nối"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {actionSuccess ? (
        <div
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3.5 text-xs font-semibold text-[var(--status-ok-text)] flex items-center gap-2"
          data-testid="integration-action-success"
        >
          <Icon name="check" size="1rem" />
          <span>{actionSuccess}</span>
        </div>
      ) : null}

      {actionError ? (
        <InlineError message={actionError} onRetry={() => setActionError("")} />
      ) : null}

      {isLoading ? (
        <div className="space-y-4 animate-pulse" aria-busy="true">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-44 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-6" data-testid="integrations-list">
          {integrationsData?.sources?.map((source) => {
            const isSyncing = syncingSourceId === source.id;
            return (
              <section
                key={source.id}
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-5"
                data-testid={`source-card-${source.id}`}
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--surface-muted)] text-[var(--text-brand)] border border-[color:var(--shell-border)]">
                      <Icon name="scan" size="1.5rem" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-[var(--text-primary)]">
                          {source.title}
                        </h3>
                        <Badge
                          tone={
                            source.status === "active"
                              ? "ok"
                              : source.status === "error"
                                ? "danger"
                                : "neutral"
                          }
                        >
                          {source.status === "active"
                            ? isEn
                              ? "Active & Connected"
                              : "Đang kết nối"
                            : source.status === "error"
                              ? isEn
                                ? "Needs Attention"
                                : "Cần xử lý"
                              : isEn
                                ? "Disconnected"
                                : "Chưa kết nối"}
                        </Badge>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                        {source.description}
                      </p>
                    </div>
                  </div>

                  {/* Actions & Master Switch */}
                  <div className="flex items-center gap-2.5">
                    {source.connected ? (
                      <>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          icon="refresh"
                          loading={isSyncing}
                          onClick={() => void handleTriggerSync(source.id)}
                          data-testid={`sync-source-btn-${source.id}`}
                        >
                          {isEn ? "Sync Now" : "Đồng bộ ngay"}
                        </Button>

                        <button
                          type="button"
                          role="switch"
                          aria-checked={source.sync_enabled}
                          aria-label={`Toggle sync for ${source.title}`}
                          onClick={() => void handleToggleSync(source)}
                          className={`inline-flex h-6 w-11 items-center rounded-full border transition ${
                            source.sync_enabled
                              ? "border-[color:var(--brand-600)] bg-[var(--brand-600)]"
                              : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                          }`}
                          data-testid={`toggle-sync-switch-${source.id}`}
                        >
                          <span
                            aria-hidden="true"
                            className={`ml-0.5 h-5 w-5 rounded-full bg-[var(--text-primary)] transition-transform ${
                              source.sync_enabled ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </>
                    ) : (
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        icon="plus"
                        onClick={() => void handleToggleSync(source)}
                        data-testid={`connect-source-btn-${source.id}`}
                      >
                        {isEn ? "Connect Source" : "Kết nối nguồn"}
                      </Button>
                    )}
                  </div>
                </div>

                {/* Error Recovery Guidance Banner if in error */}
                {source.status === "error" ? (
                  <div
                    className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 space-y-2 text-xs text-[var(--status-danger-text)]"
                    data-testid={`error-recovery-box-${source.id}`}
                  >
                    <div className="flex items-center gap-2 font-bold">
                      <Icon name="warning" size="1.1rem" />
                      <span>{isEn ? "Sync Error Detected" : "Phát hiện lỗi đồng bộ"}</span>
                    </div>
                    <p>{source.error_message}</p>
                    {source.recovery_guidance ? (
                      <p className="font-semibold">{source.recovery_guidance}</p>
                    ) : null}
                    <div className="pt-1">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void handleTriggerSync(source.id)}
                        data-testid={`retry-connect-btn-${source.id}`}
                      >
                        {isEn ? "Reconnect & Retry" : "Kết nối lại & Thử lại"}
                      </Button>
                    </div>
                  </div>
                ) : null}

                {/* Per-Category Permissions Toggle Grid */}
                {source.connected ? (
                  <div className="space-y-3 pt-2 border-t border-[color:var(--shell-border)]/60">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-[var(--text-primary)]">
                        {isEn ? "Granular Metric Permissions" : "Phân quyền từng chỉ số dữ liệu"}
                      </h4>
                      <span className="text-[11px] text-[var(--text-muted)]">
                        {source.last_sync_at
                          ? `${isEn ? "Last synced: " : "Đồng bộ lần cuối: "}${formatLocaleDate(
                              uiLanguage,
                              source.last_sync_at,
                              { dateStyle: "short", timeStyle: "short" },
                            )}`
                          : isEn
                            ? "Never synced"
                            : "Chưa từng đồng bộ"}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                      {(
                        Object.keys(
                          source.category_permissions,
                        ) as Array<keyof ConnectedHealthCategoryPermissionsDto>
                      ).map((catKey) => {
                        const isGranted = source.category_permissions[catKey];
                        const meta = CATEGORY_NAMES[catKey];
                        return (
                          <label
                            key={catKey}
                            className={`flex items-center justify-between p-2.5 rounded-[var(--radius-lg)] border cursor-pointer text-xs font-semibold transition ${
                              isGranted
                                ? "border-[color:var(--brand-400)] bg-[var(--brand-50)]/20 text-[var(--text-primary)]"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] opacity-70"
                            }`}
                            data-testid={`category-perm-${source.id}-${catKey}`}
                          >
                            <span className="truncate">{isEn ? meta.en : meta.vi}</span>
                            <input
                              type="checkbox"
                              checked={isGranted}
                              onChange={() =>
                                void handleToggleCategoryPermission(source, catKey)
                              }
                              className="rounded text-[var(--brand-600)] ml-2 shrink-0"
                            />
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
