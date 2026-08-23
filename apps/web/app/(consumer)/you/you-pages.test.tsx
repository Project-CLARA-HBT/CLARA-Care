import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerYouPage from "./page";
import YouProfilePage from "./profile/page";
import YouSharingPage from "./sharing/page";
import YouPrivacyPage from "./privacy/page";
import YouIntegrationsPage from "./integrations/page";
import YouNotificationsPage from "./notifications/page";
import { v2Client } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/you",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/shell/session-boundary", () => ({
  useSession: () => ({
    role: "doctor",
    isLoggingOut: false,
    handleLogout: vi.fn(),
  }),
}));

vi.mock("@/components/shell/profile-boundary", () => ({
  useProfileContext: () => ({
    activeProfile: { id: "p-1", display_name: "Nguyễn Văn A", kind: "self" },
    profileContext: {
      profiles: [{ id: "p-1", display_name: "Nguyễn Văn A", kind: "self" }],
    },
    handleProfileChange: vi.fn(),
    isProfileChanging: false,
  }),
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const mockYouOverview = {
  profile: { id: "p-1", display_name: "Nguyễn Văn A" },
  demographics: { full_name: "Nguyễn Văn A", blood_type: "O+" },
  emergency_card: {
    blood_type: "O+",
    allergies_count: 2,
    conditions_count: 1,
    medications_count: 3,
    medical_alerts: ["Dị ứng nặng Penicillin"],
    emergency_contact: { name: "Nguyễn Thị B", phone: "0901234567", relationship: "Vợ" },
    is_configured: true,
  },
  family_sharing: {
    active_grants_count: 2,
    received_grants_count: 0,
    pending_invites_count: 0,
    members: [{ id: "m-1", name: "Nguyễn Thị B", relationship: "Vợ", role: "caregiver", status: "active" }],
  },
  privacy_ai: {
    data_classes_used: ["medications", "conditions"],
    ai_features_enabled: true,
    cot_disabled: true,
    retention_policy_days: 90,
    consent_status: "granted",
  },
  integrations: {
    total_connected: 2,
    sources: [{ id: "s-1", name: "health_connect", title: "Google Health Connect", connected: true, sync_enabled: true, status: "active" }],
  },
  professional_mode: { eligible: true, role: "doctor", active_workspace: "clinical" },
};

describe("You & Privacy Route Pages", () => {
  describe("You Overview Page (/you)", () => {
    it("renders profile summary, emergency card card, family sharing, AI privacy, connected sources, and professional mode switcher", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverview as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      expect(screen.getByText("Cá nhân & Quyền riêng tư")).toBeInTheDocument();
      expect(screen.getByTestId("profile-summary-card")).toBeInTheDocument();
      expect(screen.getByTestId("emergency-card-summary")).toBeInTheDocument();
      expect(screen.getByTestId("family-sharing-summary")).toBeInTheDocument();
      expect(screen.getByTestId("privacy-ai-summary")).toBeInTheDocument();
      expect(screen.getByTestId("integrations-summary")).toBeInTheDocument();
      expect(screen.getByTestId("notifications-summary")).toBeInTheDocument();
      expect(screen.getByTestId("professional-mode-card")).toBeInTheDocument();
      expect(screen.getByText("Dị ứng nặng Penicillin")).toBeInTheDocument();

      // Trigger Quick Emergency QR Modal
      const openQrBtn = screen.getByTestId("open-emergency-qr-btn");
      fireEvent.click(openQrBtn);

      await waitFor(() => {
        expect(screen.getByTestId("emergency-qr-modal")).toBeInTheDocument();
      });
      expect(screen.getByText("Mã QR Cấp Cứu Y Tế")).toBeInTheDocument();
    });
  });

  describe("You Profile & Emergency Card Page (/you/profile)", () => {
    it("renders demographics editor, emergency contacts, medical alert badges, and card preview", async () => {
      vi.spyOn(v2Client, "getProfileDetails").mockResolvedValueOnce({
        id: "p-1",
        display_name: "Nguyễn Văn A",
        full_name: "Nguyễn Văn A",
        phone: "0912345678",
        email: "nguyen.vana@example.com",
        blood_type: "O+",
        emergency_contact: { name: "Nguyễn Thị B", phone: "0901234567", relationship: "Vợ" },
        allergies: [{ id: "a1", name: "Penicillin", severity: "severe" }],
        conditions: [{ id: "c1", name: "Tăng huyết áp" }],
        medications: [{ id: "m1", name: "Amlodipine 5mg" }],
        medical_alerts: ["Dị ứng Penicillin"],
        emergency_card_included_fields: {
          allergies: true,
          current_medications: true,
          conditions: true,
          blood_type: true,
          emergency_contact: true,
        },
      } as any);

      vi.spyOn(v2Client, "updateProfileDetails").mockResolvedValueOnce({ id: "p-1" } as any);
      vi.spyOn(v2Client, "updateEmergencyCard").mockResolvedValueOnce({} as any);

      render(<YouProfilePage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-profile-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("demographics-editor-section")).toBeInTheDocument();
      expect(screen.getByTestId("emergency-contact-section")).toBeInTheDocument();
      expect(screen.getByTestId("medical-alerts-editor-section")).toBeInTheDocument();
      expect(screen.getByTestId("live-emergency-card-preview")).toBeInTheDocument();

      // Add a medical alert badge
      const input = screen.getByTestId("add-medical-alert-input");
      fireEvent.change(input, { target: { value: "Mang máy tạo nhịp tim" } });
      fireEvent.click(screen.getByTestId("add-medical-alert-btn"));

      expect(screen.getAllByText("Mang máy tạo nhịp tim").length).toBeGreaterThan(0);

      // Save profile
      const saveBtn = screen.getByRole("button", { name: /Lưu thay đổi/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByTestId("profile-save-success")).toBeInTheDocument();
      });
    });
  });

  describe("You Family Sharing Page (/you/sharing)", () => {
    it("renders active grants, steps through 5-step Sharing Grant Wizard, and handles immediate revocation", async () => {
      vi.spyOn(v2Client, "getSharingOverview").mockResolvedValueOnce({
        grants: [
          {
            id: "grant-1",
            grantee_name: "Trần Thị B",
            grantee_relationship: "Vợ",
            categories: ["medications", "allergies", "visits"],
            allowed_actions: ["view"],
            purpose: "care_coordination",
            duration_days: 30,
            created_at: "2026-08-01T08:00:00Z",
            expires_at: "2026-09-01T08:00:00Z",
            status: "active",
          },
        ],
        received_grants: [],
        access_logs: [
          {
            id: "log-1",
            actor_name: "Trần Thị B",
            actor_role: "caregiver",
            action: "view",
            object_type: "medications",
            accessed_at: "2026-08-20T08:00:00Z",
            outcome: "allowed",
          },
        ],
      } as any);

      render(<YouSharingPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-sharing-page")).toBeInTheDocument();
      });

      expect(screen.getAllByText("Trần Thị B").length).toBeGreaterThan(0);
      expect(screen.getByTestId("access-history-section")).toBeInTheDocument();

      // Launch Sharing Wizard
      fireEvent.click(screen.getByRole("button", { name: /Thêm quyền chia sẻ/i }));

      // Step 1: Person
      expect(screen.getByTestId("wizard-step-1")).toBeInTheDocument();
      fireEvent.change(screen.getByTestId("wizard-person-name-input"), {
        target: { value: "Lê Văn C" },
      });
      fireEvent.click(screen.getByTestId("wizard-next-btn"));

      // Step 2: Categories
      expect(screen.getByTestId("wizard-step-2")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("wizard-next-btn"));

      // Step 3: Purpose & Duration
      expect(screen.getByTestId("wizard-step-3")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("duration-btn-90"));
      fireEvent.click(screen.getByTestId("wizard-next-btn"));

      // Step 4: Preview
      expect(screen.getByTestId("wizard-step-4")).toBeInTheDocument();
      expect(screen.getByText(/Lê Văn C/)).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("wizard-next-btn"));

      // Step 5: Confirm
      expect(screen.getByTestId("wizard-step-5")).toBeInTheDocument();
      vi.spyOn(v2Client, "createSharingGrant").mockResolvedValueOnce({
        id: "grant-2",
        token: "tok-abc-123",
      } as any);

      fireEvent.click(screen.getByTestId("wizard-confirm-grant-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("grant-created-notice")).toBeInTheDocument();
        expect(screen.getByText("tok-abc-123")).toBeInTheDocument();
      });

      // Test Revoke Modal
      fireEvent.click(screen.getByTestId("revoke-grant-btn-grant-1"));
      expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
      vi.spyOn(v2Client, "revokeSharingGrant").mockResolvedValueOnce({ success: true, revoked_at: "" });
      fireEvent.click(screen.getByTestId("confirm-revoke-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("revoke-confirm-dialog")).not.toBeInTheDocument();
      });
    });
  });

  describe("You Privacy & AI Transparency Page (/you/privacy)", () => {
    it("renders Zero-CoT assurance, data classes panel, consent status, optional AI controls, and data export", async () => {
      vi.spyOn(v2Client, "getAiTransparency").mockResolvedValueOnce({
        data_classes_used: [
          { key: "meds", name: "Đơn thuốc & Tủ thuốc", purpose: "DDI check", sensitive: true },
        ],
        retention_policy: { days: 90, description: "90 days auto-delete", auto_delete_enabled: true },
        cot_zero_disclosure: {
          operates_without_cot: true,
          description: "Zero-CoT safe pipeline",
          verified_guardrails: ["FIDES Drug Safety", "CareGuard Fast-Path"],
        },
        ai_feature_controls: {
          symptom_insights_enabled: true,
          visit_prep_suggestions_enabled: true,
          medication_safety_ai_enabled: true,
          search_summaries_enabled: true,
        },
        consent_status: {
          version: "v2.1",
          status: "granted",
          purposes: [{ purpose: "core", label: "Core Service", granted: true, locked: true }],
        },
      } as any);

      render(<YouPrivacyPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-privacy-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("zero-cot-banner")).toBeInTheDocument();
      expect(screen.getByTestId("data-classes-panel")).toBeInTheDocument();
      expect(screen.getByTestId("medical-consent-section")).toBeInTheDocument();
      expect(screen.getByTestId("ai-controls-panel")).toBeInTheDocument();
      expect(screen.getByTestId("dsar-actions-panel")).toBeInTheDocument();

      // Toggle optional AI features
      const symptomCheckbox = screen.getByTestId("toggle-symptom-insights");
      expect(symptomCheckbox).toBeChecked();
      fireEvent.click(symptomCheckbox);
      expect(symptomCheckbox).not.toBeChecked();

      vi.spyOn(v2Client, "updateAiPreferences").mockResolvedValueOnce({} as any);
      fireEvent.click(screen.getByTestId("save-ai-prefs-btn"));
      await waitFor(() => {
        expect(screen.getByText("Đã cập nhật tùy chọn AI.")).toBeInTheDocument();
      });

      // Export Data
      fireEvent.click(screen.getByTestId("export-health-data-btn"));
      expect(screen.getByText("Đã tải tệp xuất dữ liệu thành công.")).toBeInTheDocument();
    });
  });

  describe("You Integrations Page (/you/integrations)", () => {
    it("renders connected sources, category permissions toggles, manual sync, and error recovery guidance", async () => {
      vi.spyOn(v2Client, "getIntegrations").mockResolvedValueOnce({
        sources: [
          {
            id: "health_connect",
            name: "health_connect",
            title: "Google Health Connect",
            description: "Android health sync",
            connected: true,
            sync_enabled: true,
            status: "active",
            last_sync_at: "2026-08-20T08:00:00Z",
            category_permissions: {
              steps: true,
              heart_rate: true,
              blood_pressure: true,
              sleep: true,
              blood_glucose: false,
              oxygen_saturation: false,
            },
          },
          {
            id: "garmin",
            name: "garmin",
            title: "Garmin Connect",
            description: "Garmin API",
            connected: true,
            sync_enabled: false,
            status: "error",
            error_message: "OAuth expired",
            recovery_guidance: "Reconnect to renew OAuth",
            category_permissions: { steps: true, heart_rate: true, blood_pressure: false, sleep: false, blood_glucose: false, oxygen_saturation: false },
          },
        ],
      } as any);

      render(<YouIntegrationsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-integrations-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("source-card-health_connect")).toBeInTheDocument();
      expect(screen.getByTestId("source-card-garmin")).toBeInTheDocument();
      expect(screen.getByTestId("error-recovery-box-garmin")).toBeInTheDocument();
      expect(screen.getByText("Reconnect to renew OAuth")).toBeInTheDocument();

      // Trigger manual sync
      vi.spyOn(v2Client, "syncIntegrationSource").mockResolvedValueOnce({ success: true, synced_at: "" });
      fireEvent.click(screen.getByTestId("sync-source-btn-health_connect"));
      await waitFor(() => {
        expect(screen.getByTestId("integration-action-success")).toBeInTheDocument();
      });
    });
  });

  describe("You Notifications Page (/you/notifications)", () => {
    it("renders notification categories, quiet hours schedule, and delivery channels", async () => {
      vi.spyOn(v2Client, "getNotificationPreferences").mockResolvedValueOnce({
        categories: { medications: true, visits: true, review_items: true, safety_alerts: true },
        channels: { push: true, email: true, in_app: true },
        quiet_hours: { enabled: true, start_time: "22:00", end_time: "07:00" },
      } as any);

      render(<YouNotificationsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-notifications-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("notification-categories-section")).toBeInTheDocument();
      expect(screen.getByTestId("quiet-hours-section")).toBeInTheDocument();
      expect(screen.getByTestId("notification-channels-section")).toBeInTheDocument();

      // Toggle quiet hours
      const quietHoursToggle = screen.getByTestId("toggle-quiet-hours");
      expect(quietHoursToggle).toBeChecked();

      // Save
      vi.spyOn(v2Client, "updateNotificationPreferences").mockResolvedValueOnce({} as any);
      fireEvent.click(screen.getByRole("button", { name: /Lưu tùy chọn/i }));

      await waitFor(() => {
        expect(screen.getByTestId("notifications-save-success")).toBeInTheDocument();
      });
    });
  });
});
