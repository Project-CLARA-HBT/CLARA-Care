import type { ConnectedHealthSourceDto } from "@/lib/api/v2-client";

export type WearableSourceStatus =
  | "active"
  | "syncing"
  | "stale"
  | "error"
  | "reauth_required"
  | "disconnected";

export type StaleSeverity = "none" | "warning" | "critical";

export interface WearableSyncErrorDetail {
  code?: string;
  message: string;
  recoveryGuidance: string;
  requiresReauth: boolean;
}

export interface WearableSyncEvaluation {
  source: ConnectedHealthSourceDto;
  status: WearableSourceStatus;
  isStale: boolean;
  isSyncError: boolean;
  isReauthRequired: boolean;
  hoursSinceSync: number | null;
  staleSeverity: StaleSeverity;
  syncFreshnessText: { vi: string; en: string };
  statusLabel: { vi: string; en: string };
  badgeTone: "ok" | "warn" | "danger" | "neutral";
  errorDetail?: WearableSyncErrorDetail;
}

export interface WearableFleetEvaluation {
  evaluations: WearableSyncEvaluation[];
  hasErrors: boolean;
  hasStaleData: boolean;
  hasReauthRequired: boolean;
  errorSources: WearableSyncEvaluation[];
  staleSources: WearableSyncEvaluation[];
  reauthSources: WearableSyncEvaluation[];
  totalConnected: number;
  allFresh: boolean;
}

export const DEFAULT_STALE_THRESHOLD_HOURS = 24;
export const CRITICAL_STALE_THRESHOLD_HOURS = 72; // 3 days

/**
 * Detects if an error indicates that OAuth credentials, tokens, or permissions have expired.
 */
export function isAuthError(
  errorMessage?: string | null,
  errorCode?: string | null,
): boolean {
  if (errorCode && /oauth|token|auth|unauthorized|forbidden|grant/i.test(errorCode)) {
    return true;
  }
  if (!errorMessage) return false;
  const lower = errorMessage.toLowerCase();
  return (
    lower.includes("token") ||
    lower.includes("oauth") ||
    lower.includes("expired") ||
    lower.includes("reauth") ||
    lower.includes("re-auth") ||
    lower.includes("unauthorized") ||
    lower.includes("reconnect") ||
    lower.includes("grant") ||
    lower.includes("revoked") ||
    lower.includes("hết hạn") ||
    lower.includes("xác thực") ||
    lower.includes("cấp quyền")
  );
}

/**
 * Calculates hours elapsed between past timestamp and reference time.
 */
export function calculateHoursSinceSync(
  lastSyncAt: string | null | undefined,
  now: Date = new Date(),
): number | null {
  if (!lastSyncAt) return null;
  const syncDate = new Date(lastSyncAt);
  if (isNaN(syncDate.getTime())) return null;
  const diffMs = now.getTime() - syncDate.getTime();
  if (diffMs < 0) return 0;
  return diffMs / (1000 * 60 * 60);
}

/**
 * Human-readable freshness label (Vietnamese and English).
 */
export function formatFreshness(
  lastSyncAt: string | null | undefined,
  locale: "vi" | "en",
  now: Date = new Date(),
): string {
  const isEn = locale === "en";
  if (!lastSyncAt) {
    return isEn ? "Never synced" : "Chưa từng đồng bộ";
  }
  const syncDate = new Date(lastSyncAt);
  if (isNaN(syncDate.getTime())) {
    return isEn ? "Unknown sync date" : "Thời gian không xác định";
  }
  const diffSeconds = Math.max(0, Math.floor((now.getTime() - syncDate.getTime()) / 1000));
  if (diffSeconds < 60) {
    return isEn ? "Just now" : "Vừa xong";
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return isEn ? `${diffMinutes}m ago` : `${diffMinutes} phút trước`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return isEn ? `${diffHours}h ago` : `${diffHours} giờ trước`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return isEn ? `${diffDays}d ago` : `${diffDays} ngày trước`;
}

/**
 * Evaluates the sync health, freshness, and authorization state of a connected wearable source.
 */
export function evaluateSourceSyncStatus(
  source: ConnectedHealthSourceDto,
  options?: {
    now?: Date | string | number;
    staleThresholdHours?: number;
  },
): WearableSyncEvaluation {
  const now = options?.now ? new Date(options.now) : new Date();
  const staleThreshold = options?.staleThresholdHours ?? DEFAULT_STALE_THRESHOLD_HOURS;

  const hoursSince = calculateHoursSinceSync(source.last_sync_at, now);

  const freshnessVi = formatFreshness(source.last_sync_at, "vi", now);
  const freshnessEn = formatFreshness(source.last_sync_at, "en", now);

  // Check disconnected first
  if (!source.connected || !source.sync_enabled) {
    return {
      source,
      status: "disconnected",
      isStale: false,
      isSyncError: false,
      isReauthRequired: false,
      hoursSinceSync: hoursSince,
      staleSeverity: "none",
      syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
      statusLabel: { vi: "Chưa kết nối", en: "Disconnected" },
      badgeTone: "neutral",
    };
  }

  // Check sync in progress
  if (source.status === "syncing") {
    return {
      source,
      status: "syncing",
      isStale: false,
      isSyncError: false,
      isReauthRequired: false,
      hoursSinceSync: hoursSince,
      staleSeverity: "none",
      syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
      statusLabel: { vi: "Đang đồng bộ...", en: "Syncing..." },
      badgeTone: "brand",
    };
  }

  // Check Reauthorization Required
  const hasReauth =
    source.status === "reauth_required" ||
    (source.status === "error" && isAuthError(source.error_message, (source as any).error_code));

  if (hasReauth) {
    return {
      source,
      status: "reauth_required",
      isStale: hoursSince !== null ? hoursSince >= staleThreshold : true,
      isSyncError: true,
      isReauthRequired: true,
      hoursSinceSync: hoursSince,
      staleSeverity: hoursSince !== null && hoursSince >= CRITICAL_STALE_THRESHOLD_HOURS ? "critical" : "warning",
      syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
      statusLabel: { vi: "Cần cấp lại quyền", en: "Reauthorization Required" },
      badgeTone: "danger",
      errorDetail: {
        code: (source as any).error_code || "AUTH_TOKEN_EXPIRED",
        message:
          source.error_message ||
          "Mã xác thực tài khoản thiết bị đã hết hạn. Vui lòng cấp lại quyền kết nối an toàn.",
        recoveryGuidance:
          source.recovery_guidance ||
          "Nhấn 'Cấp lại quyền' để xác thực lại token OAuth với nhà cung cấp thiết bị.",
        requiresReauth: true,
      },
    };
  }

  // Check Sync Error
  if (source.status === "error") {
    return {
      source,
      status: "error",
      isStale: hoursSince !== null ? hoursSince >= staleThreshold : true,
      isSyncError: true,
      isReauthRequired: false,
      hoursSinceSync: hoursSince,
      staleSeverity: hoursSince !== null && hoursSince >= CRITICAL_STALE_THRESHOLD_HOURS ? "critical" : "warning",
      syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
      statusLabel: { vi: "Lỗi đồng bộ", en: "Sync Error" },
      badgeTone: "danger",
      errorDetail: {
        code: (source as any).error_code || "SYNC_FAILED",
        message:
          source.error_message ||
          "Không thể đồng bộ dữ liệu với thiết bị y tế. Kiểm tra kết nối mạng và thiết bị.",
        recoveryGuidance:
          source.recovery_guidance ||
          "Thử đồng bộ lại hoặc kiểm tra kết nối Bluetooth / Wi-Fi của thiết bị đeo.",
        requiresReauth: false,
      },
    };
  }

  // Check Stale Data (> staleThreshold hours or never synced while connected)
  const isStale = hoursSince === null || hoursSince >= staleThreshold;
  if (isStale) {
    const isCritical = hoursSince !== null && hoursSince >= CRITICAL_STALE_THRESHOLD_HOURS;
    return {
      source,
      status: "stale",
      isStale: true,
      isSyncError: false,
      isReauthRequired: false,
      hoursSinceSync: hoursSince,
      staleSeverity: isCritical ? "critical" : "warning",
      syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
      statusLabel: {
        vi: isCritical ? "Dữ liệu quá cũ (>72h)" : "Dữ liệu chưa cập nhật (>24h)",
        en: isCritical ? "Critically Stale (>72h)" : "Stale Data (>24h)",
      },
      badgeTone: "warn",
    };
  }

  // Active and fresh
  return {
    source,
    status: "active",
    isStale: false,
    isSyncError: false,
    isReauthRequired: false,
    hoursSinceSync: hoursSince,
    staleSeverity: "none",
    syncFreshnessText: { vi: freshnessVi, en: freshnessEn },
    statusLabel: { vi: "Đang hoạt động", en: "Active & Synced" },
    badgeTone: "ok",
  };
}

/**
 * Aggregates evaluations across all connected sources in the fleet.
 */
export function evaluateWearableFleet(
  sources: ConnectedHealthSourceDto[] | undefined | null,
  options?: {
    now?: Date | string | number;
    staleThresholdHours?: number;
  },
): WearableFleetEvaluation {
  if (!sources || sources.length === 0) {
    return {
      evaluations: [],
      hasErrors: false,
      hasStaleData: false,
      hasReauthRequired: false,
      errorSources: [],
      staleSources: [],
      reauthSources: [],
      totalConnected: 0,
      allFresh: false,
    };
  }

  const evaluations = sources.map((s) => evaluateSourceSyncStatus(s, options));
  const connectedEvaluations = evaluations.filter((e) => e.source.connected && e.source.sync_enabled);

  const reauthSources = connectedEvaluations.filter((e) => e.isReauthRequired);
  const errorSources = connectedEvaluations.filter((e) => e.isSyncError && !e.isReauthRequired);
  const staleSources = connectedEvaluations.filter((e) => e.isStale && !e.isSyncError && !e.isReauthRequired);

  const hasReauthRequired = reauthSources.length > 0;
  const hasErrors = errorSources.length > 0;
  const hasStaleData = staleSources.length > 0;

  const totalConnected = connectedEvaluations.length;
  const allFresh = totalConnected > 0 && !hasReauthRequired && !hasErrors && !hasStaleData;

  return {
    evaluations,
    hasErrors,
    hasStaleData,
    hasReauthRequired,
    errorSources,
    staleSources,
    reauthSources,
    totalConnected,
    allFresh,
  };
}

/**
 * Clinical safety predicate: checks whether a health measurement from a wearable or device
 * is considered stale (e.g., recorded > 24 hours ago).
 */
export function isMeasurementStale(
  measurement: {
    recorded_at?: string | null;
    source_kind?: string | null;
  },
  staleThresholdHours = DEFAULT_STALE_THRESHOLD_HOURS,
  now: Date = new Date(),
): boolean {
  if (!measurement.recorded_at) return true;
  // If explicitly labeled as device, wearable, or health app
  const isDeviceSource =
    measurement.source_kind === "device" ||
    measurement.source_kind === "wearable" ||
    measurement.source_kind === "imported" ||
    !measurement.source_kind;

  if (!isDeviceSource) return false;

  const hours = calculateHoursSinceSync(measurement.recorded_at, now);
  if (hours === null) return true;
  return hours >= staleThresholdHours;
}
