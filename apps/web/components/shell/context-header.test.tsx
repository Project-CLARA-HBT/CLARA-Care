import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContextHeader } from "./context-header";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";

const mockPush = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/today",
  useRouter: () => ({ refresh: mockRefresh, push: mockPush }),
}));

describe("ContextHeader", () => {
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
    familyNotificationCount: 2,
    handleProfileChange: vi.fn(),
    refreshProfileContext: vi.fn(),
  };

  function renderHeader(props = {}, sessionOverrides = {}) {
    return render(
      <PreferenceContext.Provider value={defaultPreferences}>
        <SessionContext.Provider
          value={{ ...defaultSession, ...sessionOverrides }}
        >
          <ProfileBoundaryContext.Provider value={defaultProfile}>
            <ShellModeProvider>
              <ContextHeader {...props} />
            </ShellModeProvider>
          </ProfileBoundaryContext.Provider>
        </SessionContext.Provider>
      </PreferenceContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Surface and Chrome Contract", () => {
    it("renders using ChromeSurface with variant='header' and blur='medium'", () => {
      renderHeader();

      const header = screen.getByTestId("context-header");
      expect(header).toBeInTheDocument();
      expect(header).toHaveAttribute("data-chrome-surface", "true");
      expect(header).toHaveAttribute("data-variant", "header");
      expect(header).toHaveAttribute("data-blur", "medium");
      expect(header).toHaveAttribute("role", "banner");
      expect(header).toHaveAttribute("aria-label", "Thanh ngữ cảnh toàn cục");
    });
  });

  describe("Left Section: Brand Mark & WorkspaceSwitcher", () => {
    it("renders brand mark linking to the role home path", () => {
      renderHeader();

      const brandLink = screen.getByRole("link", {
        name: "CLARA Care Trang chủ",
      });
      expect(brandLink).toBeInTheDocument();
      expect(brandLink).toHaveAttribute("href", "/home");
      expect(screen.getByText("CLARA")).toBeInTheDocument();
      expect(screen.getByText("Care Platform")).toBeInTheDocument();
    });

    it("renders prominent WorkspaceSwitcher component with active workspace badge", () => {
      renderHeader();

      const switcher = screen.getByTestId("workspace-switcher");
      expect(switcher).toBeInTheDocument();

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      expect(trigger).toHaveTextContent("Cá nhân");
    });

    it("renders active custom entity context chip with clear action", () => {
      renderHeader({
        customEntity: {
          id: "ent-1",
          type: "medication",
          label: "Đơn thuốc ngoại trú: Paracetamol",
          badge: "Đang dùng",
        },
      });

      expect(
        screen.getByText("Đơn thuốc ngoại trú: Paracetamol"),
      ).toBeInTheDocument();
      expect(screen.getByText("Đang dùng")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Xóa ngữ cảnh hiện tại" }),
      ).toBeInTheDocument();
    });
  });

  describe("Center Section: Omni-Search & Cmd+K Trigger", () => {
    it("renders Omni-Search trigger button with ⌘K keyboard indicator", () => {
      renderHeader();

      const searchBtn = screen.getByRole("button", {
        name: /Mở tìm kiếm nhanh hoặc bảng lệnh/,
      });
      expect(searchBtn).toBeInTheDocument();
      expect(screen.getByText("Tìm kiếm hoặc lệnh...")).toBeInTheDocument();
      expect(screen.getByText("⌘")).toBeInTheDocument();
      expect(screen.getByText("K")).toBeInTheDocument();
    });

    it("triggers onOpenSearch callback when search trigger button is clicked", () => {
      const handleOpenSearch = vi.fn();
      renderHeader({ onOpenSearch: handleOpenSearch });

      const searchBtn = screen.getByRole("button", {
        name: /Mở tìm kiếm nhanh hoặc bảng lệnh/,
      });
      fireEvent.click(searchBtn);
      expect(handleOpenSearch).toHaveBeenCalledTimes(1);
    });

    it("triggers onOpenCommandPalette when provided and clicked", () => {
      const handleOpenPalette = vi.fn();
      renderHeader({ onOpenCommandPalette: handleOpenPalette });

      const searchBtn = screen.getByRole("button", {
        name: /Mở tìm kiếm nhanh hoặc bảng lệnh/,
      });
      fireEvent.click(searchBtn);
      expect(handleOpenPalette).toHaveBeenCalledTimes(1);
    });
  });

  describe("Right Section: Quick Toggles, Notification, and Profile Dropdown", () => {
    it("renders Help guide link pointing to /huong-dan", () => {
      renderHeader();

      const helpLink = screen.getByRole("link", {
        name: "Mở trung tâm hướng dẫn",
      });
      expect(helpLink).toBeInTheDocument();
      expect(helpLink).toHaveAttribute("href", "/huong-dan");
    });

    it("renders notification bell with pending task count badge pointing to /you/sharing", () => {
      renderHeader();

      const notifLink = screen.getByRole("link", {
        name: "2 nhiệm vụ chăm sóc được chia sẻ đang chờ",
      });
      expect(notifLink).toBeInTheDocument();
      expect(notifLink).toHaveAttribute("href", "/you/sharing");
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("toggles theme when theme switch button is clicked", () => {
      renderHeader();

      const themeBtn = screen.getByRole("button", {
        name: /Chuyển sang giao diện sáng/,
      });
      fireEvent.click(themeBtn);
      expect(defaultPreferences.handleThemeChange).toHaveBeenCalledWith("light");
    });

    it("toggles language between VI and EN when language switch button is clicked", () => {
      renderHeader();

      const langBtn = screen.getByRole("button", { name: "Đổi ngôn ngữ" });
      expect(langBtn).toHaveTextContent("VI");

      fireEvent.click(langBtn);
      expect(defaultPreferences.handleLanguageChange).toHaveBeenCalledWith("en");
    });

    it("opens user profile dropdown with avatar, role, quick workspaces, and sign out", () => {
      const handleLogout = vi.fn();
      renderHeader({}, { handleLogout });

      const profileTrigger = screen.getByTestId(
        "context-header-profile-trigger",
      );
      expect(profileTrigger).toBeInTheDocument();
      expect(profileTrigger).toHaveAttribute("aria-expanded", "false");

      // Open profile menu
      fireEvent.click(profileTrigger);
      expect(profileTrigger).toHaveAttribute("aria-expanded", "true");

      const profileMenu = screen.getByTestId("context-header-profile-menu");
      expect(profileMenu).toBeInTheDocument();
      expect(profileMenu).toHaveAttribute("data-chrome-surface", "true");
      expect(profileMenu).toHaveAttribute("data-variant", "menu");

      // Displays user info and role badge
      expect(screen.getAllByText("Nguyen Van A").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Người dùng cá nhân (Personal)")).toBeInTheDocument();

      // Displays quick workspace shortcuts
      expect(screen.getByText("Chuyển không gian")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Chuyển tới Cá nhân" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Chuyển tới Lâm sàng" }),
      ).toBeInTheDocument();

      // Sign out action
      const signOutBtn = screen.getByRole("button", { name: "Đăng xuất" });
      expect(signOutBtn).toBeInTheDocument();
      fireEvent.click(signOutBtn);
      expect(handleLogout).toHaveBeenCalledTimes(1);
    });

    it("closes profile menu when clicking outside or pressing Escape", () => {
      renderHeader();

      const profileTrigger = screen.getByTestId(
        "context-header-profile-trigger",
      );
      fireEvent.click(profileTrigger);
      expect(
        screen.getByTestId("context-header-profile-menu"),
      ).toBeInTheDocument();

      // Escape key closes menu
      fireEvent.keyDown(window, { key: "Escape" });
      expect(
        screen.queryByTestId("context-header-profile-menu"),
      ).not.toBeInTheDocument();
    });
  });
});
