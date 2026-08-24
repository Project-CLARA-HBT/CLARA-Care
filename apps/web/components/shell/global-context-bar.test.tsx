import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GlobalContextBar, CORE_WORKSPACES } from "./global-context-bar";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";

const mockPush = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
  useRouter: () => ({ refresh: mockRefresh, push: mockPush }),
}));

describe("GlobalContextBar", () => {
  const defaultPreferences = {
    themePreference: "dark" as const,
    setThemePreference: vi.fn(),
    handleThemeChange: vi.fn(),
    uiLanguage: "vi" as const,
    setUiLanguage: vi.fn(),
    handleLanguageChange: vi.fn(),
  };

  const defaultSession = {
    role: "normal" as const,
    effectiveRole: "normal" as const,
    adminPreviewMode: null,
    setAdminPreviewMode: vi.fn(),
    setRole: vi.fn(),
    isRoleHydrated: true,
    isSessionChecked: true,
    isLoggingOut: false,
    handleLogout: vi.fn(),
  };

  const defaultProfile = {
    profileContext: {
      profiles: [
        {
          id: "prof-1",
          display_name: "Nguyen Van A",
          kind: "self",
          active: true,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      active_profile_id: "prof-1",
      active_kind: "self",
      cache_scope: "scope-1",
      reset_required: false,
    },
    activeProfile: {
      id: "prof-1",
      display_name: "Nguyen Van A",
      kind: "self",
      active: true,
      created_at: "2026-01-01T00:00:00Z",
    },
    activeProfileId: "prof-1",
    isProfileChanging: false,
    familyNotificationCount: 1,
    handleProfileChange: vi.fn(),
    refreshProfileContext: vi.fn(),
  };

  function renderBar(props = {}, sessionOverrides = {}) {
    return render(
      <PreferenceContext.Provider value={defaultPreferences}>
        <SessionContext.Provider value={{ ...defaultSession, ...sessionOverrides }}>
          <ProfileBoundaryContext.Provider value={defaultProfile}>
            <ShellModeProvider>
              <GlobalContextBar {...props} />
            </ShellModeProvider>
          </ProfileBoundaryContext.Provider>
        </SessionContext.Provider>
      </PreferenceContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders brand mark, mode switcher, entity chip, search trigger, and user profile", () => {
    renderBar();

    // Brand mark
    expect(screen.getByRole("link", { name: "CLARA Care Trang chủ" })).toBeInTheDocument();

    // Search trigger
    expect(screen.getByRole("button", { name: /Mở tìm kiếm nhanh/ })).toBeInTheDocument();

    // Mode switcher
    expect(screen.getByLabelText(/Chế độ hiển thị/)).toBeInTheDocument();

    // User profile chip
    const profileChips = screen.getAllByLabelText("Nguyen Van A");
    expect(profileChips.length).toBeGreaterThanOrEqual(1);
  });

  it("triggers search/command palette when search trigger button clicked", () => {
    const handleOpenSearch = vi.fn();
    renderBar({ onOpenSearch: handleOpenSearch });

    const searchBtn = screen.getByRole("button", { name: /Mở tìm kiếm nhanh/ });
    fireEvent.click(searchBtn);
    expect(handleOpenSearch).toHaveBeenCalled();
  });

  it("renders active custom entity context chip with clear action", () => {
    renderBar({
      customEntity: {
        id: "ent-1",
        type: "medication",
        label: "Đơn thuốc ngoại trú: Paracetamol",
        badge: "Đang dùng",
      },
    });

    expect(screen.getByText("Đơn thuốc ngoại trú: Paracetamol")).toBeInTheDocument();
    expect(screen.getByText("Đang dùng")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xóa ngữ cảnh hiện tại" })).toBeInTheDocument();
  });

  it("renders quick toggles for theme, language, and notifications", () => {
    renderBar();

    const themeBtn = screen.getByRole("button", { name: /Chuyển sang giao diện sáng/ });
    fireEvent.click(themeBtn);
    expect(defaultPreferences.handleThemeChange).toHaveBeenCalledWith("light");

    const langBtn = screen.getByRole("button", { name: /Đổi ngôn ngữ/ });
    fireEvent.click(langBtn);
    expect(defaultPreferences.handleLanguageChange).toHaveBeenCalledWith("en");
  });

  it("does not render admin preview section for normal consumer role", () => {
    renderBar({}, { role: "normal" });

    expect(screen.queryByText(/Chế độ xem trước \(Admin Preview\)/)).not.toBeInTheDocument();
    expect(screen.getByText(/Không gian làm việc \(Workspaces\)/)).toBeInTheDocument();
  });

  it("renders 4 workspace options when role is admin and invokes setAdminPreviewMode & router.push on selection", () => {
    const setAdminPreviewMode = vi.fn();
    renderBar(
      {},
      {
        role: "admin",
        effectiveRole: "admin",
        adminPreviewMode: null,
        setAdminPreviewMode,
      },
    );

    // Section header
    expect(screen.getByText(/Chế độ xem trước \(Admin Preview\)/)).toBeInTheDocument();

    // 4 Workspace Options in main switcher dropdown
    const adminOpt = screen.getByRole("button", { name: /^Quản trị viên \(Admin\)/ });
    const clinicalOpt = screen.getByRole("button", { name: /^Bác sĩ Lâm sàng \(Doctor \/ Clinical\)/ });
    const researchOpt = screen.getByRole("button", { name: /^Nhà nghiên cứu \(Researcher \/ Evidence\)/ });
    const personalOpt = screen.getByRole("button", { name: /^Người dùng Cá nhân \(Personal \/ Consumer\)/ });

    expect(adminOpt).toBeInTheDocument();
    expect(clinicalOpt).toBeInTheDocument();
    expect(researchOpt).toBeInTheDocument();
    expect(personalOpt).toBeInTheDocument();

    // Select Clinical Preview
    fireEvent.click(clinicalOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("clinical");
    expect(mockPush).toHaveBeenCalledWith("/dashboard");

    // Select Research Preview
    fireEvent.click(researchOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("research");
    expect(mockPush).toHaveBeenCalledWith("/evidence");

    // Select Personal Preview
    fireEvent.click(personalOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");
    expect(mockPush).toHaveBeenCalledWith("/today");

    // Select Administration (reset)
    fireEvent.click(adminOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith(null);
    expect(mockPush).toHaveBeenCalledWith("/admin/overview");
  });

  it("updates the active pill label and styling in ContextBar when adminPreviewMode is active", () => {
    renderBar(
      {},
      {
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      },
    );

    // Context bar summary button should reflect clinical preview
    expect(screen.getByLabelText(/Chế độ xem trước: Lâm sàng/)).toBeInTheDocument();
    expect(screen.getByText("Xem trước: Lâm sàng")).toBeInTheDocument();
    expect(screen.getAllByText("Preview · Clinical").length).toBeGreaterThanOrEqual(1);
  });

  it("renders all 5 shell display modes and switches mode on click", () => {
    renderBar();

    expect(screen.getByText(/Chế độ giao diện \(5 Shell Modes\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Khám phá/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tập trung/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Toàn màn hình/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Đọc tài liệu/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dữ liệu cô đọng/ })).toBeInTheDocument();

    const focusModeBtn = screen.getByRole("button", { name: /Tập trung/ });
    fireEvent.click(focusModeBtn);
  });

  it("surfaces active role and quick workspace switch shortcuts in user profile dropdown menu", () => {
    const setAdminPreviewMode = vi.fn();
    renderBar(
      {},
      {
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      },
    );

    // Active role in profile header
    expect(screen.getByText("Admin (Xem trước: Lâm sàng)")).toBeInTheDocument();

    // Quick workspace shortcuts section
    expect(screen.getByText("Chuyển không gian")).toBeInTheDocument();

    const quickAdmin = screen.getByRole("button", { name: "Chuyển tới Quản trị viên (Admin)" });
    const quickClinical = screen.getByRole("button", { name: "Chuyển tới Bác sĩ Lâm sàng (Doctor / Clinical)" });
    const quickResearch = screen.getByRole("button", { name: "Chuyển tới Nhà nghiên cứu (Researcher / Evidence)" });
    const quickPersonal = screen.getByRole("button", { name: "Chuyển tới Người dùng Cá nhân (Personal / Consumer)" });

    expect(quickAdmin).toBeInTheDocument();
    expect(quickClinical).toBeInTheDocument();
    expect(quickResearch).toBeInTheDocument();
    expect(quickPersonal).toBeInTheDocument();

    // Click quick shortcut
    fireEvent.click(quickPersonal);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");
    expect(mockPush).toHaveBeenCalledWith("/today");
  });
});
