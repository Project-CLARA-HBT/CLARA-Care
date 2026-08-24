import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerYouPage from "./page";
import YouProfilePage from "./profile/page";
import YouSharingPage from "./sharing/page";
import YouPrivacyPage from "./privacy/page";
import YouIntegrationsPage from "./integrations/page";
import YouNotificationsPage from "./notifications/page";
import YouSettingsPage from "./settings/page";
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
  describe("You Overview Page (/you — Spec v5 Section 6.74 Account & Preferences Hub)", () => {
    it("renders Identity & Profile card, all 8 categorized vertical list rows, emergency alerts, and quick QR modal", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverview as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      expect(screen.getByText("Cá nhân & Quyền riêng tư")).toBeInTheDocument();

      // 1. Identity & Profile card
      expect(screen.getByTestId("profile-summary-card")).toBeInTheDocument();
      expect(screen.getByTestId("emergency-card-summary")).toBeInTheDocument();
      expect(screen.getByTestId("edit-profile-btn")).toHaveAttribute("href", "/you/profile");
      expect(screen.getByText("Dị ứng nặng Penicillin")).toBeInTheDocument();

      // 2. Categorized vertical list rows (Spec v5 Section 6.74)
      expect(screen.getByTestId("categorized-account-rows")).toBeInTheDocument();

      // Row 1: Health Record (PHR)
      expect(screen.getByTestId("phr-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Hồ sơ Sức khỏe Cá nhân \(PHR\)|Health Record \(PHR\)/i })).toHaveAttribute("href", "/phr");

      // Row 2: Family & Care Sharing
      expect(screen.getByTestId("family-sharing-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Chia sẻ Người thân & Người chăm sóc|Family & Care Sharing/i })).toHaveAttribute("href", "/you/sharing");

      // Row 3: Connected Health Devices
      expect(screen.getByTestId("integrations-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Thiết bị & Nguồn kết nối|Connected Health Devices/i })).toHaveAttribute("href", "/you/integrations");

      // Row 4: Privacy & Medical Consent
      expect(screen.getByTestId("privacy-ai-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Quyền riêng tư & Đồng thuận Y tế|Privacy & Medical Consent/i })).toHaveAttribute("href", "/you/privacy");

      // Row 5: Data Rights (Decree 13 / GDPR)
      expect(screen.getByTestId("data-rights-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Quyền Dữ liệu \(Nghị định 13 \/ GDPR\)|Data Rights \(Decree 13 \/ GDPR\)/i })).toHaveAttribute("href", "/account/data");

      // Row 6: Notifications
      expect(screen.getByTestId("notifications-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Cài đặt Thông báo & Nhắc nhở|Notifications/i })).toHaveAttribute("href", "/you/notifications");

      // Row 7: Security & Preferences (Settings & Security)
      const secSummary = screen.getByTestId("security-preferences-summary");
      expect(secSummary).toBeInTheDocument();
      expect(within(secSummary).getByRole("link")).toHaveAttribute("href", "/you/settings");

      // Row 8: Help & Guides
      expect(screen.getByTestId("help-guide-summary")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Hướng dẫn & Trợ giúp|Help & Guides/i })).toHaveAttribute("href", "/huong-dan");

      // 3. Professional Mode Card
      expect(screen.getByTestId("professional-mode-card")).toBeInTheDocument();

      // 4. Sign out button
      expect(screen.getByTestId("you-sign-out-btn")).toBeInTheDocument();

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
        categories: {
          medications: true,
          visits: true,
          review_items: true,
          safety_alerts: true,
          journey_milestones: true,
          family_activity: true,
        },
        channels: { push: true, email: true, in_app: true },
        quiet_hours: { enabled: true, start_time: "22:00", end_time: "07:00" },
      } as any);

      render(<YouNotificationsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-notifications-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("notification-feed-section")).toBeInTheDocument();
      expect(screen.getByTestId("notification-filter-tabs")).toBeInTheDocument();
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

    it("supports filtering notification categories and taking interactive actions", async () => {
      vi.spyOn(v2Client, "getNotificationPreferences").mockResolvedValueOnce({
        categories: { medications: true, visits: true, review_items: true, safety_alerts: true },
        channels: { push: true, email: true, in_app: true },
        quiet_hours: { enabled: true, start_time: "22:00", end_time: "07:00" },
      } as any);

      render(<YouNotificationsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-notifications-page")).toBeInTheDocument();
      });

      // Filter by medications tab
      const medTab = screen.getByTestId("tab-filter-medications");
      fireEvent.click(medTab);
      expect(screen.getByTestId("notif-card-notif-med-1")).toBeInTheDocument();

      // Mark medication as taken
      const actionBtn = screen.getByTestId("action-btn-notif-med-1");
      fireEvent.click(actionBtn);
      expect(screen.getByText("Đã uống")).toBeInTheDocument();

      // Toggle read state
      const toggleReadBtn = screen.getByTestId("toggle-read-btn-notif-med-1");
      fireEvent.click(toggleReadBtn);
      expect(screen.getByText("Đánh dấu đã đọc")).toBeInTheDocument();

      // Filter by safety tab
      const safetyTab = screen.getByTestId("tab-filter-safety");
      fireEvent.click(safetyTab);
      expect(screen.getByTestId("notif-card-notif-safe-1")).toBeInTheDocument();

      // Return to all
      const allTab = screen.getByTestId("tab-filter-all");
      fireEvent.click(allTab);
      expect(screen.getByTestId("notif-card-notif-mile-1")).toBeInTheDocument();

      // Mark all as read
      const markAllBtn = screen.getByTestId("mark-all-read-btn");
      fireEvent.click(markAllBtn);
      expect(screen.queryByTestId("unread-count-badge")).not.toBeInTheDocument();
    });
  });

  describe("You Settings & Security Page (/you/settings)", () => {
    it("renders appearance (theme/language), MFA management, active logins, and session policies", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce({
        mfa_enabled: false,
        mfa_method: "totp",
        mfa_configured_at: null,
        inactivity_timeout_minutes: 30,
        new_login_alerts: true,
        reauth_for_sensitive: true,
        active_sessions: [
          {
            id: "sess-current",
            device_name: "Chrome 127 • Windows 11",
            device_type: "desktop",
            platform: "Windows 11",
            browser: "Chrome 127",
            ip_address: "118.69.182.45",
            location: "Hà Nội, Việt Nam",
            last_active_at: new Date().toISOString(),
            is_current: true,
          },
          {
            id: "sess-mobile-1",
            device_name: "CLARA Mobile App • iOS 18 (iPhone 15 Pro)",
            device_type: "mobile",
            platform: "iOS 18",
            browser: "CLARA App 2.1",
            ip_address: "14.161.34.12",
            location: "TP. Hồ Chí Minh, Việt Nam",
            last_active_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
            is_current: false,
          },
        ],
      } as any);

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-settings-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("appearance-language-section")).toBeInTheDocument();
      expect(screen.getByTestId("mfa-management-section")).toBeInTheDocument();
      expect(screen.getByTestId("active-logins-section")).toBeInTheDocument();
      expect(screen.getByTestId("session-security-section")).toBeInTheDocument();

      // Theme toggle
      const lightOption = screen.getByRole("tab", { name: /Sáng/i });
      fireEvent.click(lightOption);

      // Inactivity timeout select
      const timeoutSelect = screen.getByTestId("inactivity-timeout-select");
      fireEvent.change(timeoutSelect, { target: { value: "60" } });

      // Save settings
      vi.spyOn(v2Client, "updateSecuritySettings").mockResolvedValueOnce({} as any);
      fireEvent.click(screen.getByRole("button", { name: /Lưu thay đổi/i }));

      await waitFor(() => {
        expect(screen.getByTestId("settings-save-success")).toBeInTheDocument();
      });
    });

    it("steps through MFA 2FA setup wizard, generates backup codes, and allows disabling MFA", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce({
        mfa_enabled: false,
        mfa_method: "totp",
        mfa_configured_at: null,
        inactivity_timeout_minutes: 30,
        new_login_alerts: true,
        reauth_for_sensitive: true,
        active_sessions: [],
      } as any);

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-settings-page")).toBeInTheDocument();
      });

      // Launch 2FA Setup
      const setupMfaBtn = screen.getByTestId("setup-mfa-btn");
      fireEvent.click(setupMfaBtn);

      expect(screen.getByTestId("mfa-setup-modal")).toBeInTheDocument();
      expect(screen.getByTestId("mfa-secret-display")).toHaveTextContent("CLARA-SEC-8894-K9VT-2026");

      // Next step
      fireEvent.click(screen.getByTestId("mfa-next-step-btn"));

      // Enter code (invalid first)
      const codeInput = screen.getByTestId("mfa-verification-code-input");
      fireEvent.change(codeInput, { target: { value: "123" } });
      fireEvent.click(screen.getByTestId("mfa-verify-code-btn"));
      expect(screen.getByText("Vui lòng nhập mã gồm đúng 6 chữ số.")).toBeInTheDocument();

      // Enter valid 6-digit code
      fireEvent.change(codeInput, { target: { value: "654321" } });
      fireEvent.click(screen.getByTestId("mfa-verify-code-btn"));

      // Step 3: Backup codes
      expect(screen.getByTestId("backup-codes-grid")).toBeInTheDocument();
      expect(screen.getByText("A7X9-K2M4")).toBeInTheDocument();

      // Copy backup codes
      const copyBtn = screen.getByTestId("copy-backup-codes-btn");
      Object.assign(navigator, {
        clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
      });
      fireEvent.click(copyBtn);

      // Finish setup
      vi.spyOn(v2Client, "updateSecuritySettings").mockResolvedValueOnce({} as any);
      fireEvent.click(screen.getByTestId("mfa-finish-setup-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("mfa-setup-modal")).not.toBeInTheDocument();
      });

      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent("Đang Bật (Bảo vệ cao)");

      // Disable MFA
      const disableBtn = screen.getByTestId("disable-mfa-btn");
      fireEvent.click(disableBtn);
      expect(screen.getByTestId("disable-mfa-modal")).toBeInTheDocument();

      vi.spyOn(v2Client, "updateSecuritySettings").mockResolvedValueOnce({} as any);
      fireEvent.click(screen.getByTestId("confirm-disable-mfa-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("disable-mfa-modal")).not.toBeInTheDocument();
      });
      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent("Chưa Kích Hoạt");
    });

    it("revokes individual sessions and terminates all other active sessions", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce({
        mfa_enabled: true,
        mfa_method: "totp",
        mfa_configured_at: "2026-08-01T00:00:00Z",
        inactivity_timeout_minutes: 30,
        new_login_alerts: true,
        reauth_for_sensitive: true,
        active_sessions: [
          {
            id: "sess-current",
            device_name: "Chrome 127 • Windows 11",
            device_type: "desktop",
            platform: "Windows 11",
            browser: "Chrome 127",
            ip_address: "118.69.182.45",
            location: "Hà Nội, Việt Nam",
            last_active_at: new Date().toISOString(),
            is_current: true,
          },
          {
            id: "sess-mobile-1",
            device_name: "CLARA Mobile App • iOS 18 (iPhone 15 Pro)",
            device_type: "mobile",
            platform: "iOS 18",
            browser: "CLARA App 2.1",
            ip_address: "14.161.34.12",
            location: "TP. Hồ Chí Minh, Việt Nam",
            last_active_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
            is_current: false,
          },
          {
            id: "sess-tablet-1",
            device_name: "Safari 17 • iPadOS 17.5 (iPad Air)",
            device_type: "tablet",
            platform: "iPadOS 17.5",
            browser: "Safari 17",
            ip_address: "113.190.23.88",
            location: "Đà Nẵng, Việt Nam",
            last_active_at: new Date(Date.now() - 3 * 86400 * 1000).toISOString(),
            is_current: false,
          },
        ],
      } as any);

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-settings-page")).toBeInTheDocument();
      });

      expect(screen.getByTestId("session-card-sess-mobile-1")).toBeInTheDocument();
      expect(screen.getByTestId("session-card-sess-tablet-1")).toBeInTheDocument();

      // Revoke single session
      vi.spyOn(v2Client, "revokeSession").mockResolvedValueOnce({ success: true, revoked_id: "sess-mobile-1" });
      const revokeMobileBtn = screen.getByTestId("revoke-session-btn-sess-mobile-1");
      fireEvent.click(revokeMobileBtn);

      await waitFor(() => {
        expect(screen.queryByTestId("session-card-sess-mobile-1")).not.toBeInTheDocument();
        expect(screen.getByTestId("session-revoke-notice")).toBeInTheDocument();
      });

      // Terminate all other sessions
      const revokeAllBtn = screen.getByTestId("revoke-all-others-btn");
      fireEvent.click(revokeAllBtn);
      expect(screen.getByTestId("revoke-all-sessions-modal")).toBeInTheDocument();

      vi.spyOn(v2Client, "revokeAllOtherSessions").mockResolvedValueOnce({ success: true, revoked_count: 1 });
      fireEvent.click(screen.getByTestId("confirm-revoke-all-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("revoke-all-sessions-modal")).not.toBeInTheDocument();
        expect(screen.queryByTestId("session-card-sess-tablet-1")).not.toBeInTheDocument();
      });
      expect(screen.getByTestId("session-card-sess-current")).toBeInTheDocument();
    });
  });
});
