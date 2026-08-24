import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GlobalContextBar } from "./global-context-bar";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
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
  });

  it("renders 4 admin preview mode options when role is admin and invokes setAdminPreviewMode on selection", () => {
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

    // 4 Workspace Options
    const adminOpt = screen.getByRole("button", { name: /Quản trị viên \(Administration\)/ });
    const clinicalOpt = screen.getByRole("button", { name: /Lâm sàng \(Clinical\)/ });
    const researchOpt = screen.getByRole("button", { name: /Nghiên cứu \(Research\)/ });
    const personalOpt = screen.getByRole("button", { name: /Cá nhân \(Personal\)/ });

    expect(adminOpt).toBeInTheDocument();
    expect(clinicalOpt).toBeInTheDocument();
    expect(researchOpt).toBeInTheDocument();
    expect(personalOpt).toBeInTheDocument();

    // Select Clinical Preview
    fireEvent.click(clinicalOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("clinical");

    // Select Research Preview
    fireEvent.click(researchOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("research");

    // Select Personal Preview
    fireEvent.click(personalOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");

    // Select Administration (reset)
    fireEvent.click(adminOpt);
    expect(setAdminPreviewMode).toHaveBeenCalledWith(null);
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
  });
});
