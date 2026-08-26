import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerYouPage from "./page";
import YouSettingsPage from "./settings/page";
import { v2Client } from "@/lib/api/v2-client";
import * as themeLib from "@/lib/theme";
import * as uiLangLib from "@/lib/ui-language";
import api from "@/lib/http-client";

// ---------------------------------------------------------------------------
// Mocks & Setup
// ---------------------------------------------------------------------------

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

const sessionState = {
  role: "doctor" as string,
  isLoggingOut: false,
  handleLogout: vi.fn(),
};

vi.mock("@/components/shell/session-boundary", () => ({
  useSession: () => sessionState,
}));

const profileContextState = {
  activeProfile: { id: "p-1", display_name: "Nguyễn Văn A", kind: "self" } as {
    id: string;
    display_name: string;
    kind: string;
  } | null,
  profileContext: {
    profiles: [
      { id: "p-1", display_name: "Nguyễn Văn A", kind: "self" },
      { id: "p-2", display_name: "Nguyễn Thị B", kind: "shared" },
    ],
  },
  handleProfileChange: vi.fn(),
  isProfileChanging: false,
};

vi.mock("@/components/shell/profile-boundary", () => ({
  useProfileContext: () => profileContextState,
}));

vi.mock("@/lib/http-client", () => {
  const get = vi.fn().mockImplementation((url: string) => {
    if (String(url).includes("/emergency-card/eligibility")) {
      return Promise.resolve({
        data: {
          eligible: true,
          reasons: [],
          required_fields: [],
          consent_version: "v2.1",
          subject_binding: "usr-1:p-1",
          generated_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 30 * 86400 * 1000).toISOString(),
        },
      });
    }
    if (String(url).includes("/emergency-card")) {
      return Promise.resolve({
        data: {
          emergency_card: {
            blood_type: "O+",
            allergies: [],
            conditions: [],
          },
        },
      });
    }
    return Promise.resolve({ data: {} });
  });

  const post = vi.fn().mockImplementation((url: string) => {
    if (String(url).includes("/emergency-card")) {
      return Promise.resolve({
        data: {
          success: true,
          token: "v8-signed-token-xyz",
          qr_payload: "https://theclaracare.com/share/emergency?token=v8-signed-token-xyz",
          expires_at: new Date(Date.now() + 30 * 86400 * 1000).toISOString(),
          scope: "emergency_card",
        },
      });
    }
    return Promise.resolve({ data: {} });
  });

  const clientMock = {
    get,
    post,
    patch: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn(), eject: vi.fn() },
      response: { use: vi.fn(), eject: vi.fn() },
    },
    defaults: { baseURL: "http://localhost:8100/api/v1" },
  };

  return {
    default: clientMock,
    api: clientMock,
  };
});

// Mock Overview DTO
const mockYouOverviewData = {
  profile: { id: "p-1", display_name: "Nguyễn Văn A" },
  demographics: { full_name: "Nguyễn Văn A", blood_type: "O+" },
  emergency_card: {
    blood_type: "O+",
    allergies_count: 2,
    conditions_count: 1,
    medications_count: 3,
    medical_alerts: ["Dị ứng nặng Penicillin (sốc phản vệ)"],
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

// Mock Security Settings DTO
const mockSecuritySettingsData = {
  mfa_enabled: false,
  mfa_method: "totp" as const,
  mfa_configured_at: null,
  inactivity_timeout_minutes: 30,
  new_login_alerts: true,
  reauth_for_sensitive: true,
  active_sessions: [
    {
      id: "sess-current",
      device_name: "Chrome 127 • Windows 11",
      device_type: "desktop" as const,
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
      device_type: "mobile" as const,
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
      device_type: "tablet" as const,
      platform: "iPadOS 17.5",
      browser: "Safari 17",
      ip_address: "113.190.23.88",
      location: "Đà Nẵng, Việt Nam",
      last_active_at: new Date(Date.now() - 3 * 86400 * 1000).toISOString(),
      is_current: false,
    },
  ],
};

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  if (typeof window !== "undefined") {
    window.localStorage.clear();
    uiLangLib.saveUILanguage("vi");
    themeLib.saveThemePreference("dark");
  }
  sessionState.role = "doctor";
  sessionState.isLoggingOut = false;
  sessionState.handleLogout = vi.fn();
  profileContextState.activeProfile = { id: "p-1", display_name: "Nguyễn Văn A", kind: "self" };
});

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe("Spec v8 Section 7.15: Consumer You Architecture Verification", () => {
  describe("1. /you (Account & Preferences Hub)", () => {
    it("renders Identity/Profile Card with demographics, medical alerts, QR action, and profile switcher", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      // SettingsLayout metadata
      const page = screen.getByTestId("you-overview-page");
      expect(page).toHaveAttribute("data-workspace", "personal");
      expect(page).toHaveAttribute("data-archetype", "settings");

      // Profile Card & Identity
      const profileCard = screen.getByTestId("profile-summary-card");
      expect(profileCard).toBeInTheDocument();
      expect(within(profileCard).getByRole("heading", { level: 2, name: "Nguyễn Văn A" })).toBeInTheDocument();

      // Emergency Card Summary
      const emergencySummary = screen.getByTestId("emergency-card-summary");
      expect(emergencySummary).toBeInTheDocument();
      expect(within(emergencySummary).getByText("O+")).toBeInTheDocument();
      expect(within(emergencySummary).getByText(/2 dị ứng quan trọng/i)).toBeInTheDocument();
      expect(within(emergencySummary).getByText(/1 bệnh lý đang theo dõi/i)).toBeInTheDocument();

      // Medical Alert Banner & Contact
      expect(screen.getByText("Dị ứng nặng Penicillin (sốc phản vệ)")).toBeInTheDocument();
      expect(screen.getByText(/Nguyễn Thị B \(Vợ\)/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "0901234567" })).toHaveAttribute("href", "tel:0901234567");

      // Quick Actions
      expect(screen.getByTestId("open-emergency-qr-btn")).toBeInTheDocument();
      expect(screen.getByTestId("edit-profile-btn")).toHaveAttribute("href", "/you/profile");

      // Multi-profile switcher
      const switcher = screen.getByTestId("profile-switcher-select") as HTMLSelectElement;
      expect(switcher).toBeInTheDocument();
      expect(switcher.value).toBe("p-1");
      fireEvent.change(switcher, { target: { value: "p-2" } });
      expect(profileContextState.handleProfileChange).toHaveBeenCalledWith("p-2");
    });

    it("renders all 8 categorized vertical list rows with appropriate links, badges, and icons", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("categorized-account-rows")).toBeInTheDocument();
      });

      // Row 1: Health Record (PHR)
      const phrRow = screen.getByTestId("phr-summary");
      expect(phrRow).toBeInTheDocument();
      expect(within(phrRow).getByRole("link")).toHaveAttribute("href", "/phr");
      expect(within(phrRow).getByText("Hồ sơ Sức khỏe Cá nhân (PHR)")).toBeInTheDocument();

      // Row 2: Family & Care Sharing
      const familyRow = screen.getByTestId("family-sharing-summary");
      expect(familyRow).toBeInTheDocument();
      expect(within(familyRow).getByRole("link")).toHaveAttribute("href", "/you/sharing");
      expect(within(familyRow).getByText("Chia sẻ Người thân & Người chăm sóc")).toBeInTheDocument();
      expect(within(familyRow).getByText("2 Đang chia sẻ")).toBeInTheDocument();

      // Row 3: Connected Health Devices
      const integrationsRow = screen.getByTestId("integrations-summary");
      expect(integrationsRow).toBeInTheDocument();
      expect(within(integrationsRow).getByRole("link")).toHaveAttribute("href", "/you/integrations");
      expect(within(integrationsRow).getByText("Thiết bị & Nguồn kết nối (Integrations)")).toBeInTheDocument();
      expect(within(integrationsRow).getByText("2 Đã kết nối")).toBeInTheDocument();

      // Row 4: Privacy & Medical Consent
      const privacyRow = screen.getByTestId("privacy-ai-summary");
      expect(privacyRow).toBeInTheDocument();
      expect(within(privacyRow).getByRole("link")).toHaveAttribute("href", "/you/privacy");
      expect(within(privacyRow).getByText("Quyền riêng tư & Đồng thuận Y tế")).toBeInTheDocument();
      expect(within(privacyRow).getByText("Zero-CoT")).toBeInTheDocument();
      expect(within(privacyRow).getByText("Đã đồng thuận")).toBeInTheDocument();

      // Row 5: Data Rights (Decree 13 / GDPR)
      const dataRightsRow = screen.getByTestId("data-rights-summary");
      expect(dataRightsRow).toBeInTheDocument();
      expect(within(dataRightsRow).getByRole("link")).toHaveAttribute("href", "/account/data");
      expect(within(dataRightsRow).getByText("Quyền Dữ liệu (Nghị định 13 / GDPR)")).toBeInTheDocument();

      // Row 6: Notifications
      const notificationsRow = screen.getByTestId("notifications-summary");
      expect(notificationsRow).toBeInTheDocument();
      expect(within(notificationsRow).getByRole("link")).toHaveAttribute("href", "/you/notifications");
      expect(within(notificationsRow).getByText("Cài đặt Thông báo & Nhắc nhở")).toBeInTheDocument();

      // Row 7: Security & Preferences
      const securityRow = screen.getByTestId("security-preferences-summary");
      expect(securityRow).toBeInTheDocument();
      expect(within(securityRow).getByRole("link")).toHaveAttribute("href", "/you/settings");
      expect(within(securityRow).getByText("Bảo mật & Tùy chọn Tài khoản")).toBeInTheDocument();

      // Row 8: Help & Guides
      const helpRow = screen.getByTestId("help-guide-summary");
      expect(helpRow).toBeInTheDocument();
      expect(within(helpRow).getByRole("link")).toHaveAttribute("href", "/huong-dan");
      expect(within(helpRow).getByText("Hướng dẫn & Trợ giúp")).toBeInTheDocument();
    });

    it("renders Professional Mode card for clinical/research/admin roles and allows signing out", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("professional-mode-card")).toBeInTheDocument();
      });

      expect(screen.getByTestId("switch-professional-mode-link")).toHaveAttribute("href", "/dashboard");

      // Sign out action
      const signOutBtn = screen.getByTestId("you-sign-out-btn");
      fireEvent.click(signOutBtn);
      expect(sessionState.handleLogout).toHaveBeenCalledTimes(1);
    });

    it("hides Professional Mode card for normal user role", async () => {
      sessionState.role = "normal";
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("professional-mode-card")).not.toBeInTheDocument();
    });

    it("displays shared profile badge when viewing a shared profile", async () => {
      profileContextState.activeProfile = { id: "p-2", display_name: "Nguyễn Thị B", kind: "shared" };
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      expect(screen.getAllByText("Hồ sơ chia sẻ").length).toBeGreaterThan(0);
    });

    it("opens Emergency QR Modal when clicking Quick Emergency QR button", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("open-emergency-qr-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("open-emergency-qr-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("emergency-qr-modal")).toBeInTheDocument();
      });

      expect(screen.getByText("Mã QR Cấp Cứu Y Tế")).toBeInTheDocument();
    });

    it("displays honest error state when overview query fails without mock fallback hallucination", async () => {
      vi.spyOn(v2Client, "getYouOverview").mockRejectedValueOnce(new Error("Failed to fetch"));

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByText("Không thể tải tổng quan cá nhân")).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
      expect(screen.queryByTestId("profile-summary-card")).not.toBeInTheDocument();
    });

    it("renders English copy when UI language is English", async () => {
      uiLangLib.saveUILanguage("en");
      vi.spyOn(v2Client, "getYouOverview").mockResolvedValueOnce(mockYouOverviewData as any);

      render(<ConsumerYouPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-overview-page")).toBeInTheDocument();
      });

      expect(screen.getByRole("heading", { level: 1, name: "Account & Preferences" })).toBeInTheDocument();
      expect(screen.getByTestId("open-emergency-qr-btn")).toHaveTextContent("Quick Emergency QR");
      expect(screen.getByTestId("edit-profile-btn")).toHaveTextContent("Edit Profile & Emergency Card");
      expect(screen.getByTestId("you-sign-out-btn")).toHaveTextContent("Sign Out");
    });
  });

  describe("2. /you/settings (Theme, Language, 2FA/TOTP, Sessions, Auto-lock)", () => {
    it("renders Appearance & Localization with Theme mode and Language toggles", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce(mockSecuritySettingsData as any);
      const applyThemeSpy = vi.spyOn(themeLib, "applyThemePreference");
      const saveThemeSpy = vi.spyOn(themeLib, "saveThemePreference");
      const saveLangSpy = vi.spyOn(uiLangLib, "saveUILanguage");

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-settings-page")).toBeInTheDocument();
      });

      // SettingsLayout adoption
      const settingsPage = screen.getByTestId("you-settings-page");
      expect(settingsPage).toHaveAttribute("data-workspace", "personal");
      expect(settingsPage).toHaveAttribute("data-archetype", "settings");

      // Theme toggle
      expect(screen.getByTestId("appearance-language-section")).toBeInTheDocument();
      const lightBtn = screen.getByRole("tab", { name: /Sáng/i });
      fireEvent.click(lightBtn);

      expect(saveThemeSpy).toHaveBeenCalledWith("light");
      expect(applyThemeSpy).toHaveBeenCalledWith("light");

      // Language toggle
      const enBtn = screen.getByRole("tab", { name: /English/i });
      fireEvent.click(enBtn);

      expect(saveLangSpy).toHaveBeenCalledWith("en");
    });

    it("walks through 3-step 2FA / TOTP setup wizard with code verification and backup recovery codes", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce({
        ...mockSecuritySettingsData,
        mfa_enabled: false,
      } as any);

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("mfa-management-section")).toBeInTheDocument();
      });

      // Initial state: Disabled
      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent("Chưa Kích Hoạt");

      // Step 1: Open modal
      fireEvent.click(screen.getByTestId("setup-mfa-btn"));
      expect(screen.getByTestId("mfa-setup-modal")).toBeInTheDocument();
      expect(screen.getByTestId("mfa-secret-display")).toBeInTheDocument();

      // Proceed to Step 2
      fireEvent.click(screen.getByTestId("mfa-next-step-btn"));

      // Code input validation
      const codeInput = screen.getByTestId("mfa-verification-code-input");
      fireEvent.change(codeInput, { target: { value: "12" } });
      fireEvent.click(screen.getByTestId("mfa-verify-code-btn"));
      expect(screen.getByText("Vui lòng nhập mã gồm đúng 6 chữ số.")).toBeInTheDocument();

      // Valid 6 digits
      fireEvent.change(codeInput, { target: { value: "123456" } });
      fireEvent.click(screen.getByTestId("mfa-verify-code-btn"));

      // Step 3: Backup recovery codes grid
      expect(screen.getByTestId("backup-codes-grid")).toBeInTheDocument();
      const codes = screen.getAllByText(/[A-Z0-9]{4}-[A-Z0-9]{4}/);
      expect(codes.length).toBe(8);

      // Copy recovery codes
      const copyBtn = screen.getByTestId("copy-backup-codes-btn");
      Object.assign(navigator, {
        clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
      });
      fireEvent.click(copyBtn);

      // Complete setup
      const updateSecuritySpy = vi
        .spyOn(v2Client, "updateSecuritySettings")
        .mockResolvedValueOnce({ ...mockSecuritySettingsData, mfa_enabled: true } as any);

      fireEvent.click(screen.getByTestId("mfa-finish-setup-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("mfa-setup-modal")).not.toBeInTheDocument();
      });

      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent("Đang Bật (Bảo vệ cao)");
      expect(updateSecuritySpy).toHaveBeenCalledWith({ mfa_enabled: true, mfa_method: "totp" });

      // View recovery codes button
      fireEvent.click(screen.getByTestId("view-backup-codes-btn"));
      expect(screen.getByTestId("backup-codes-grid")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("mfa-finish-setup-btn"));

      // Disable 2FA via confirmation modal
      fireEvent.click(screen.getByTestId("disable-mfa-btn"));
      expect(screen.getByTestId("disable-mfa-modal")).toBeInTheDocument();

      vi.spyOn(v2Client, "updateSecuritySettings").mockResolvedValueOnce({
        ...mockSecuritySettingsData,
        mfa_enabled: false,
      } as any);

      fireEvent.click(screen.getByTestId("confirm-disable-mfa-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("disable-mfa-modal")).not.toBeInTheDocument();
      });

      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent("Chưa Kích Hoạt");
    });

    it("manages active logins: revokes single session and revokes all other sessions", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce(mockSecuritySettingsData as any);
      const revokeSessionSpy = vi
        .spyOn(v2Client, "revokeSession")
        .mockResolvedValueOnce({ success: true, revoked_id: "sess-mobile-1" });
      const revokeAllSpy = vi
        .spyOn(v2Client, "revokeAllOtherSessions")
        .mockResolvedValueOnce({ success: true, revoked_count: 1 });

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("active-logins-section")).toBeInTheDocument();
      });

      expect(screen.getByTestId("sessions-count-badge")).toHaveTextContent("3 Thiết bị");
      expect(screen.getByTestId("session-card-sess-current")).toBeInTheDocument();
      expect(screen.getByTestId("session-card-sess-mobile-1")).toBeInTheDocument();
      expect(screen.getByTestId("session-card-sess-tablet-1")).toBeInTheDocument();

      // Revoke single mobile session
      const revokeMobileBtn = screen.getByTestId("revoke-session-btn-sess-mobile-1");
      fireEvent.click(revokeMobileBtn);

      await waitFor(() => {
        expect(revokeSessionSpy).toHaveBeenCalledWith("sess-mobile-1");
        expect(screen.queryByTestId("session-card-sess-mobile-1")).not.toBeInTheDocument();
        expect(screen.getByTestId("session-revoke-notice")).toBeInTheDocument();
      });

      // Dismiss revocation notice
      const dismissBtn = screen.getByText("✕");
      fireEvent.click(dismissBtn);
      expect(screen.queryByTestId("session-revoke-notice")).not.toBeInTheDocument();

      // Revoke all other sessions
      const revokeAllBtn = screen.getByTestId("revoke-all-others-btn");
      fireEvent.click(revokeAllBtn);
      expect(screen.getByTestId("revoke-all-sessions-modal")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("confirm-revoke-all-btn"));

      await waitFor(() => {
        expect(revokeAllSpy).toHaveBeenCalledTimes(1);
        expect(screen.queryByTestId("revoke-all-sessions-modal")).not.toBeInTheDocument();
        expect(screen.queryByTestId("session-card-sess-tablet-1")).not.toBeInTheDocument();
      });

      expect(screen.getByTestId("session-card-sess-current")).toBeInTheDocument();
    });

    it("changes password with input validation and server sync", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce(mockSecuritySettingsData as any);
      const postSpy = vi.spyOn(api, "post").mockResolvedValueOnce({ data: { message: "Password updated successfully." } });

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("change-password-section")).toBeInTheDocument();
      });

      const currentInput = screen.getByTestId("current-password-input");
      const newInput = screen.getByTestId("new-password-input");
      const confirmInput = screen.getByTestId("confirm-password-input");
      const submitBtn = screen.getByTestId("submit-change-password-btn");

      // Test short password
      fireEvent.change(currentInput, { target: { value: "oldPassword123" } });
      fireEvent.change(newInput, { target: { value: "short" } });
      fireEvent.change(confirmInput, { target: { value: "short" } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("password-change-error")).toHaveTextContent("Mật khẩu mới phải có ít nhất 8 ký tự.");
      });

      // Test password without numbers
      fireEvent.change(newInput, { target: { value: "allletterspass" } });
      fireEvent.change(confirmInput, { target: { value: "allletterspass" } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("password-change-error")).toHaveTextContent("Mật khẩu mới phải chứa cả chữ cái và chữ số.");
      });

      // Test password mismatch
      fireEvent.change(newInput, { target: { value: "newPassword123" } });
      fireEvent.change(confirmInput, { target: { value: "different123" } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("password-change-error")).toHaveTextContent("Mật khẩu xác nhận không khớp.");
      });

      // Test valid password change
      fireEvent.change(newInput, { target: { value: "newSecurePass123" } });
      fireEvent.change(confirmInput, { target: { value: "newSecurePass123" } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("/auth/change-password", {
          current_password: "oldPassword123",
          new_password: "newSecurePass123",
        });
        expect(screen.getByTestId("password-change-success")).toHaveTextContent("Đổi mật khẩu thành công.");
      });
    });

    it("configures inactivity auto-lock window and policy toggles, saving changes successfully", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce(mockSecuritySettingsData as any);
      const updateSecuritySpy = vi
        .spyOn(v2Client, "updateSecuritySettings")
        .mockResolvedValueOnce(mockSecuritySettingsData as any);

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("session-security-section")).toBeInTheDocument();
      });

      // Change auto-lock window to 60 minutes
      const timeoutSelect = screen.getByTestId("inactivity-timeout-select");
      fireEvent.change(timeoutSelect, { target: { value: "60" } });

      // Toggle new login alerts
      const loginAlertsToggle = screen.getByTestId("toggle-new-login-alerts");
      expect(loginAlertsToggle).toBeChecked();
      fireEvent.click(loginAlertsToggle);
      expect(loginAlertsToggle).not.toBeChecked();

      // Save preferences
      const saveBtn = screen.getByTestId("save-settings-btn");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(updateSecuritySpy).toHaveBeenCalledWith(
          expect.objectContaining({
            inactivity_timeout_minutes: 60,
            new_login_alerts: false,
          })
        );
        expect(screen.getByTestId("settings-save-success")).toBeInTheDocument();
      });
    });

    it("handles save failure gracefully with inline error", async () => {
      vi.spyOn(v2Client, "getSecuritySettings").mockResolvedValueOnce(mockSecuritySettingsData as any);
      vi.spyOn(v2Client, "updateSecuritySettings").mockRejectedValueOnce(new Error("Save failed"));

      render(<YouSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("you-settings-page")).toBeInTheDocument();
      });

      const saveBtn = screen.getByTestId("save-settings-btn");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByText("Không thể lưu cài đặt. Vui lòng thử lại.")).toBeInTheDocument();
      });
    });
  });
});
