import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WearableSyncAlertBanner } from "./wearable-sync-alert-banner";
import { WearableReauthModal } from "./wearable-reauth-modal";
import { WearableStaleBadge } from "./wearable-stale-badge";
import type { ConnectedHealthSourceDto } from "@/lib/api/v2-client";

afterEach(cleanup);

describe("Wearable Sync Alerts & Indicators UI Components", () => {
  const freshSource: ConnectedHealthSourceDto = {
    id: "health_connect",
    name: "health_connect",
    title: "Google Health Connect",
    description: "Android health data",
    connected: true,
    sync_enabled: true,
    status: "active",
    last_sync_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(), // 15m ago
    category_permissions: {
      steps: true,
      heart_rate: true,
      blood_pressure: true,
      sleep: true,
      blood_glucose: false,
      oxygen_saturation: false,
    },
  };

  const reauthSource: ConnectedHealthSourceDto = {
    id: "garmin",
    name: "garmin",
    title: "Garmin Connect",
    description: "Garmin Health API",
    connected: true,
    sync_enabled: true,
    status: "error",
    error_message: "OAuth token expired. Re-authentication required.",
    recovery_guidance: "Click Reauthorize to renew your security grant.",
    last_sync_at: new Date(Date.now() - 48 * 3600 * 1000).toISOString(),
    category_permissions: {
      steps: true,
      heart_rate: true,
      blood_pressure: false,
      sleep: false,
      blood_glucose: false,
      oxygen_saturation: false,
    },
  };

  const syncErrorSource: ConnectedHealthSourceDto = {
    id: "apple_health",
    name: "apple_health",
    title: "Apple Health",
    description: "iOS vitals sync",
    connected: true,
    sync_enabled: true,
    status: "error",
    error_message: "Network timeout synchronizing vitals chunk",
    last_sync_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    category_permissions: {
      steps: true,
      heart_rate: true,
      blood_pressure: false,
      sleep: false,
      blood_glucose: false,
      oxygen_saturation: false,
    },
  };

  const staleSource: ConnectedHealthSourceDto = {
    id: "fitbit",
    name: "fitbit",
    title: "Fitbit Health",
    description: "Fitbit tracking",
    connected: true,
    sync_enabled: true,
    status: "active",
    last_sync_at: new Date(Date.now() - 36 * 3600 * 1000).toISOString(), // 36 hours ago
    category_permissions: {
      steps: true,
      heart_rate: true,
      blood_pressure: false,
      sleep: false,
      blood_glucose: false,
      oxygen_saturation: false,
    },
  };

  describe("WearableSyncAlertBanner", () => {
    it("renders nothing when sources are fresh and operational", () => {
      const { container } = render(
        <WearableSyncAlertBanner sources={[freshSource]} locale="en" />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("renders nothing when sources list is empty or disconnected", () => {
      const disconnected = { ...freshSource, connected: false };
      const { container } = render(
        <WearableSyncAlertBanner sources={[disconnected]} locale="en" />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("renders Reauthorization Required banner with highest priority", () => {
      render(
        <WearableSyncAlertBanner
          sources={[freshSource, staleSource, reauthSource]}
          locale="en"
        />,
      );

      const banner = screen.getByTestId("wearable-reauth-alert-banner");
      expect(banner).toBeInTheDocument();
      expect(screen.getByText("Reauthorization Required: Garmin Connect")).toBeInTheDocument();
      expect(screen.getByTestId("banner-reauth-btn")).toBeInTheDocument();
    });

    it("renders General Sync Error banner when a non-auth error occurs", async () => {
      const onTriggerSync = vi.fn().mockResolvedValue(undefined);
      render(
        <WearableSyncAlertBanner
          sources={[freshSource, syncErrorSource]}
          locale="en"
          onTriggerSync={onTriggerSync}
        />,
      );

      const banner = screen.getByTestId("wearable-sync-error-banner");
      expect(banner).toBeInTheDocument();
      expect(screen.getByText("Wearable Sync Error: Apple Health")).toBeInTheDocument();

      const retryBtn = screen.getByTestId("banner-retry-sync-btn");
      await act(async () => {
        fireEvent.click(retryBtn);
      });
      expect(onTriggerSync).toHaveBeenCalledWith("apple_health");
    });

    it("renders Stale Data warning banner when data is older than 24h", async () => {
      const onTriggerSync = vi.fn().mockResolvedValue(undefined);
      render(
        <WearableSyncAlertBanner
          sources={[freshSource, staleSource]}
          locale="vi"
          onTriggerSync={onTriggerSync}
        />,
      );

      const banner = screen.getByTestId("wearable-stale-data-banner");
      expect(banner).toBeInTheDocument();
      expect(screen.getByText(/Dữ liệu chưa cập nhật: Fitbit Health/)).toBeInTheDocument();
      expect(screen.getByText(/Chỉ số từ thiết bị chưa được đồng bộ trong hơn 24 giờ/)).toBeInTheDocument();

      const syncBtn = screen.getByTestId("banner-stale-sync-btn");
      await act(async () => {
        fireEvent.click(syncBtn);
      });
      expect(onTriggerSync).toHaveBeenCalledWith("fitbit");
    });

    it("opens Reauthorization Modal when user clicks reauthorize button in banner", () => {
      render(
        <WearableSyncAlertBanner
          sources={[reauthSource]}
          locale="en"
        />,
      );

      const reauthBtn = screen.getByTestId("banner-reauth-btn");
      fireEvent.click(reauthBtn);

      expect(screen.getByTestId("wearable-reauth-modal")).toBeInTheDocument();
      expect(screen.getByRole("dialog", { name: /Reauthorize Garmin Connect/i })).toBeInTheDocument();
    });
  });

  describe("WearableReauthModal", () => {
    it("renders modal details, privacy guarantees, and handles reauthorization flow", async () => {
      const onClose = vi.fn();
      const onReauth = vi.fn().mockResolvedValue(undefined);
      const onSuccess = vi.fn();

      render(
        <WearableReauthModal
          open={true}
          onClose={onClose}
          source={reauthSource}
          locale="en"
          onReauthorize={onReauth}
          onSuccess={onSuccess}
        />,
      );

      expect(screen.getByTestId("wearable-reauth-modal")).toBeInTheDocument();
      expect(screen.getByText(/OAuth Token Expired or Revoked/i)).toBeInTheDocument();
      expect(screen.getByText(/Security & Privacy Guarantees/i)).toBeInTheDocument();
      expect(screen.getByText(/Read-only access/i)).toBeInTheDocument();

      const confirmBtn = screen.getByTestId("confirm-reauth-btn");
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(onReauth).toHaveBeenCalledWith("garmin");
        expect(onSuccess).toHaveBeenCalled();
        expect(screen.getByTestId("reauth-success-view")).toBeInTheDocument();
      });

      const doneBtn = screen.getByTestId("reauth-done-btn");
      fireEvent.click(doneBtn);
      expect(onClose).toHaveBeenCalled();
    });

    it("displays error message if reauthorization fails", async () => {
      const onReauth = vi.fn().mockRejectedValue(new Error("Vendor API 502 Bad Gateway"));

      render(
        <WearableReauthModal
          open={true}
          onClose={vi.fn()}
          source={reauthSource}
          locale="en"
          onReauthorize={onReauth}
        />,
      );

      fireEvent.click(screen.getByTestId("confirm-reauth-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("inline-error-error")).toBeInTheDocument();
        expect(screen.getByText("Vendor API 502 Bad Gateway")).toBeInTheDocument();
      });
    });
  });

  describe("WearableStaleBadge", () => {
    it("renders stale badge with time for timestamps > 24 hours ago", () => {
      const past30Hours = new Date(Date.now() - 30 * 3600 * 1000).toISOString();
      render(<WearableStaleBadge recordedAt={past30Hours} locale="vi" />);

      const badge = screen.getByTestId("wearable-stale-badge");
      expect(badge).toBeInTheDocument();
      expect(screen.getByText(/Dữ liệu cũ/)).toBeInTheDocument();
    });

    it("renders compact mode in English", () => {
      const past30Hours = new Date(Date.now() - 30 * 3600 * 1000).toISOString();
      render(<WearableStaleBadge recordedAt={past30Hours} locale="en" compact />);

      expect(screen.getByText("Stale")).toBeInTheDocument();
    });
  });
});
