import { describe, expect, it } from "vitest";
import {
  calculateHoursSinceSync,
  evaluateSourceSyncStatus,
  evaluateWearableFleet,
  formatFreshness,
  isAuthError,
  isMeasurementStale,
  type WearableSyncEvaluation,
} from "./wearable-sync";
import type { ConnectedHealthSourceDto } from "./api/v2-client";

describe("Wearable Sync Utilities & Clinical Freshness Logic", () => {
  const baseSource: ConnectedHealthSourceDto = {
    id: "health_connect",
    name: "health_connect",
    title: "Google Health Connect",
    description: "Android vitals sync",
    connected: true,
    sync_enabled: true,
    last_sync_at: "2026-08-20T10:00:00Z",
    status: "active",
    category_permissions: {
      steps: true,
      heart_rate: true,
      blood_pressure: true,
      sleep: true,
      blood_glucose: false,
      oxygen_saturation: false,
    },
  };

  const fixedNow = new Date("2026-08-20T12:00:00Z"); // 2 hours after baseSource

  describe("isAuthError", () => {
    it("identifies OAuth token expiration in English", () => {
      expect(isAuthError("OAuth refresh token expired. Re-authentication required.")).toBe(true);
      expect(isAuthError("Unauthorized 401: Token revoked")).toBe(true);
      expect(isAuthError("User permission grant revoked by provider")).toBe(true);
    });

    it("identifies authorization expiration in Vietnamese", () => {
      expect(isAuthError("Mã xác thực tài khoản đã hết hạn")).toBe(true);
      expect(isAuthError("Yêu cầu cấp quyền kết nối lại")).toBe(true);
    });

    it("identifies error codes related to auth", () => {
      expect(isAuthError(null, "ERR_OAUTH_TOKEN_EXPIRED")).toBe(true);
      expect(isAuthError(undefined, "AUTH_REQUIRED")).toBe(true);
    });

    it("returns false for non-auth errors", () => {
      expect(isAuthError("Network timeout connecting to server")).toBe(false);
      expect(isAuthError("Rate limit exceeded. Please back off.", "RATE_LIMIT_429")).toBe(false);
      expect(isAuthError(null, null)).toBe(false);
    });
  });

  describe("calculateHoursSinceSync & formatFreshness", () => {
    it("returns null for empty timestamps", () => {
      expect(calculateHoursSinceSync(null, fixedNow)).toBeNull();
      expect(calculateHoursSinceSync(undefined, fixedNow)).toBeNull();
      expect(formatFreshness(null, "vi", fixedNow)).toBe("Chưa từng đồng bộ");
      expect(formatFreshness(null, "en", fixedNow)).toBe("Never synced");
    });

    it("calculates exact hours elapsed", () => {
      const hours = calculateHoursSinceSync("2026-08-20T10:00:00Z", fixedNow);
      expect(hours).toBeCloseTo(2);
    });

    it("formats recent sync as minutes ago or just now", () => {
      const justNow = new Date("2026-08-20T12:00:20Z");
      expect(formatFreshness("2026-08-20T12:00:00Z", "vi", justNow)).toBe("Vừa xong");
      expect(formatFreshness("2026-08-20T12:00:00Z", "en", justNow)).toBe("Just now");

      const fifteenMinAgo = "2026-08-20T11:45:00Z";
      expect(formatFreshness(fifteenMinAgo, "vi", fixedNow)).toBe("15 phút trước");
      expect(formatFreshness(fifteenMinAgo, "en", fixedNow)).toBe("15m ago");
    });

    it("formats hours and days ago", () => {
      const threeHoursAgo = "2026-08-20T09:00:00Z";
      expect(formatFreshness(threeHoursAgo, "vi", fixedNow)).toBe("3 giờ trước");
      expect(formatFreshness(threeHoursAgo, "en", fixedNow)).toBe("3h ago");

      const threeDaysAgo = "2026-08-17T12:00:00Z";
      expect(formatFreshness(threeDaysAgo, "vi", fixedNow)).toBe("3 ngày trước");
      expect(formatFreshness(threeDaysAgo, "en", fixedNow)).toBe("3d ago");
    });
  });

  describe("evaluateSourceSyncStatus", () => {
    it("evaluates active and fresh source (< 24h)", () => {
      const res = evaluateSourceSyncStatus(baseSource, { now: fixedNow });
      expect(res.status).toBe("active");
      expect(res.isStale).toBe(false);
      expect(res.isSyncError).toBe(false);
      expect(res.isReauthRequired).toBe(false);
      expect(res.badgeTone).toBe("ok");
      expect(res.staleSeverity).toBe("none");
    });

    it("evaluates disconnected source", () => {
      const disconnected: ConnectedHealthSourceDto = {
        ...baseSource,
        connected: false,
        sync_enabled: false,
      };
      const res = evaluateSourceSyncStatus(disconnected, { now: fixedNow });
      expect(res.status).toBe("disconnected");
      expect(res.badgeTone).toBe("neutral");
      expect(res.isStale).toBe(false);
    });

    it("evaluates syncing source", () => {
      const syncing: ConnectedHealthSourceDto = {
        ...baseSource,
        status: "syncing",
      };
      const res = evaluateSourceSyncStatus(syncing, { now: fixedNow });
      expect(res.status).toBe("syncing");
      expect(res.badgeTone).toBe("brand");
      expect(res.statusLabel.en).toBe("Syncing...");
    });

    it("evaluates stale data when last sync > 24 hours ago", () => {
      const staleDate = "2026-08-19T08:00:00Z"; // 28 hours before fixedNow
      const staleSource: ConnectedHealthSourceDto = {
        ...baseSource,
        last_sync_at: staleDate,
      };
      const res = evaluateSourceSyncStatus(staleSource, { now: fixedNow });
      expect(res.status).toBe("stale");
      expect(res.isStale).toBe(true);
      expect(res.staleSeverity).toBe("warning");
      expect(res.badgeTone).toBe("warn");
      expect(res.statusLabel.vi).toContain("Dữ liệu chưa cập nhật (>24h)");
      expect(res.statusLabel.en).toContain("Stale Data (>24h)");
    });

    it("evaluates critically stale data when last sync > 72 hours ago", () => {
      const veryStaleDate = "2026-08-16T10:00:00Z"; // 98 hours before fixedNow
      const veryStaleSource: ConnectedHealthSourceDto = {
        ...baseSource,
        last_sync_at: veryStaleDate,
      };
      const res = evaluateSourceSyncStatus(veryStaleSource, { now: fixedNow });
      expect(res.status).toBe("stale");
      expect(res.isStale).toBe(true);
      expect(res.staleSeverity).toBe("critical");
      expect(res.statusLabel.vi).toContain("quá cũ (>72h)");
      expect(res.statusLabel.en).toContain("Critically Stale (>72h)");
    });

    it("evaluates reauthorization required status when token expired", () => {
      const expiredSource: ConnectedHealthSourceDto = {
        ...baseSource,
        status: "error",
        error_message: "OAuth token expired. Re-authentication required.",
        recovery_guidance: "Reconnect to renew OAuth token",
      };
      const res = evaluateSourceSyncStatus(expiredSource, { now: fixedNow });
      expect(res.status).toBe("reauth_required");
      expect(res.isReauthRequired).toBe(true);
      expect(res.isSyncError).toBe(true);
      expect(res.badgeTone).toBe("danger");
      expect(res.statusLabel.vi).toBe("Cần cấp lại quyền");
      expect(res.statusLabel.en).toBe("Reauthorization Required");
      expect(res.errorDetail?.requiresReauth).toBe(true);
    });

    it("evaluates generic sync error when non-auth error occurs", () => {
      const errorSource: ConnectedHealthSourceDto = {
        ...baseSource,
        status: "error",
        error_message: "HTTP 500: Failed to fetch telemetry payload from wearable API",
        recovery_guidance: "Retry sync in a few minutes",
      };
      const res = evaluateSourceSyncStatus(errorSource, { now: fixedNow });
      expect(res.status).toBe("error");
      expect(res.isSyncError).toBe(true);
      expect(res.isReauthRequired).toBe(false);
      expect(res.badgeTone).toBe("danger");
      expect(res.statusLabel.vi).toBe("Lỗi đồng bộ");
      expect(res.statusLabel.en).toBe("Sync Error");
      expect(res.errorDetail?.requiresReauth).toBe(false);
    });
  });

  describe("evaluateWearableFleet", () => {
    it("handles null or empty list safely", () => {
      const res = evaluateWearableFleet([]);
      expect(res.hasErrors).toBe(false);
      expect(res.hasStaleData).toBe(false);
      expect(res.allFresh).toBe(false);
      expect(res.totalConnected).toBe(0);
    });

    it("aggregates fleet with mixed states", () => {
      const sources: ConnectedHealthSourceDto[] = [
        {
          ...baseSource,
          id: "fresh_source",
          last_sync_at: "2026-08-20T11:00:00Z", // 1h ago
        },
        {
          ...baseSource,
          id: "stale_source",
          last_sync_at: "2026-08-18T10:00:00Z", // 50h ago
        },
        {
          ...baseSource,
          id: "reauth_source",
          status: "error",
          error_message: "OAuth token expired",
        },
      ];

      const fleet = evaluateWearableFleet(sources, { now: fixedNow });
      expect(fleet.totalConnected).toBe(3);
      expect(fleet.hasReauthRequired).toBe(true);
      expect(fleet.hasStaleData).toBe(true);
      expect(fleet.hasErrors).toBe(false); // error is reauth
      expect(fleet.allFresh).toBe(false);
      expect(fleet.reauthSources).toHaveLength(1);
      expect(fleet.staleSources).toHaveLength(1);
    });

    it("marks allFresh when all connected sources are synced and operational", () => {
      const sources: ConnectedHealthSourceDto[] = [
        { ...baseSource, id: "s1", last_sync_at: "2026-08-20T11:30:00Z" },
        { ...baseSource, id: "s2", last_sync_at: "2026-08-20T11:45:00Z" },
      ];

      const fleet = evaluateWearableFleet(sources, { now: fixedNow });
      expect(fleet.allFresh).toBe(true);
      expect(fleet.hasErrors).toBe(false);
      expect(fleet.hasStaleData).toBe(false);
      expect(fleet.hasReauthRequired).toBe(false);
    });
  });

  describe("isMeasurementStale", () => {
    it("flags measurement older than 24h from medical device as stale", () => {
      const staleMeasurement = {
        recorded_at: "2026-08-19T06:00:00Z", // 30 hours ago
        source_kind: "device",
      };
      expect(isMeasurementStale(staleMeasurement, 24, fixedNow)).toBe(true);
    });

    it("does not flag measurement younger than 24h as stale", () => {
      const freshMeasurement = {
        recorded_at: "2026-08-20T11:00:00Z", // 1 hour ago
        source_kind: "device",
      };
      expect(isMeasurementStale(freshMeasurement, 24, fixedNow)).toBe(false);
    });

    it("does not flag clinician diagnoses as stale", () => {
      const clinicianMeasurement = {
        recorded_at: "2026-08-10T10:00:00Z", // 10 days ago
        source_kind: "clinician",
      };
      expect(isMeasurementStale(clinicianMeasurement, 24, fixedNow)).toBe(false);
    });

    it("flags missing recorded_at as stale", () => {
      expect(isMeasurementStale({ recorded_at: null, source_kind: "device" }, 24, fixedNow)).toBe(true);
    });
  });
});
