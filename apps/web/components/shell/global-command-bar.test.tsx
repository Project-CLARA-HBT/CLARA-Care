import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserRole } from "@/lib/auth-store";
import * as ShellIndex from "@/components/shell";
import * as GlobalCommandBarModule from "./global-command-bar";
import GlobalCommandBarDefault, {
  GLOBAL_COMMAND_BAR_DESKTOP_HEIGHT_CLASS,
  GLOBAL_COMMAND_BAR_HEIGHT_RANGE,
  GlobalCommandBar,
} from "./global-command-bar";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";

const mocks = vi.hoisted(() => ({
  pathname: "/today",
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({
    push: mocks.routerPush,
    replace: mocks.routerReplace,
    refresh: vi.fn(),
  }),
}));

describe("GlobalCommandBar (Spec v8 §4.2 & 5.1)", () => {
  const mockHandleThemeChange = vi.fn();
  const mockHandleLanguageChange = vi.fn();
  const mockHandleLogout = vi.fn();
  const mockSetAdminPreviewMode = vi.fn();
  const mockHandleProfileChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
  });

  function renderWithProviders(
    ui: React.ReactElement,
    {
      role = "normal" as UserRole,
      effectiveRole = "normal" as UserRole,
      adminPreviewMode = null,
      uiLanguage = "vi" as const,
      themePreference = "dark" as const,
      profiles = [
        { id: "p1", display_name: "Nguyen Van A", kind: "self" as const, active: true, created_at: "2026-01-01" },
        { id: "p2", display_name: "Me Nguyen Thi B", kind: "shared" as const, active: false, created_at: "2026-01-01" },
      ],
      familyNotificationCount = 3,
    }: {
      role?: UserRole;
      effectiveRole?: UserRole;
      adminPreviewMode?: any;
      uiLanguage?: "vi" | "en";
      themePreference?: "dark" | "light" | "system";
      profiles?: any[];
      familyNotificationCount?: number;
    } = {},
  ) {
    return render(
      <ShellModeProvider>
        <SessionContext.Provider
          value={{
            role,
            effectiveRole,
            adminPreviewMode,
            setAdminPreviewMode: mockSetAdminPreviewMode,
            setRole: vi.fn(),
            isRoleHydrated: true,
            isSessionChecked: true,
            isLoggingOut: false,
            handleLogout: mockHandleLogout,
          }}
        >
          <PreferenceContext.Provider
            value={{
              themePreference,
              setThemePreference: vi.fn(),
              handleThemeChange: mockHandleThemeChange,
              uiLanguage,
              setUiLanguage: vi.fn(),
              handleLanguageChange: mockHandleLanguageChange,
            }}
          >
            <ProfileBoundaryContext.Provider
              value={{
                profileContext: {
                  active_profile_id: "p1",
                  active_kind: "self",
                  cache_scope: null,
                  reset_required: false,
                  profiles,
                },
                activeProfile: profiles[0],
                activeProfileId: "p1",
                handleProfileChange: mockHandleProfileChange,
                refreshProfileContext: vi.fn(async () => {}),
                isProfileChanging: false,
                familyNotificationCount,
              }}
            >
              {ui}
            </ProfileBoundaryContext.Provider>
          </PreferenceContext.Provider>
        </SessionContext.Provider>
      </ShellModeProvider>,
    );
  }

  describe("1. Exports and Contract Verification", () => {
    it("exports named and default GlobalCommandBar from module and barrel", () => {
      expect(GlobalCommandBar).toBeDefined();
      expect(GlobalCommandBarDefault).toBeDefined();
      expect(GlobalCommandBarModule.GlobalCommandBar).toBeDefined();
      expect(GlobalCommandBarModule.default).toBeDefined();
      expect(ShellIndex.GlobalCommandBar).toBeDefined();
    });

    it("exports height constants matching 52–58px range", () => {
      expect(GLOBAL_COMMAND_BAR_HEIGHT_RANGE).toBe("52–58px");
      expect(GLOBAL_COMMAND_BAR_DESKTOP_HEIGHT_CLASS).toContain("h-[54px]");
      expect(GLOBAL_COMMAND_BAR_DESKTOP_HEIGHT_CLASS).toContain("min-h-[52px]");
      expect(GLOBAL_COMMAND_BAR_DESKTOP_HEIGHT_CLASS).toContain("max-h-[58px]");
    });
  });

  describe("2. Visual Chrome & Landmark Structure", () => {
    it("renders banner landmark with height within 52–58px range", () => {
      renderWithProviders(<GlobalCommandBar />);

      const bar = screen.getByTestId("global-command-bar");
      expect(bar).toBeInTheDocument();
      expect(bar.tagName.toLowerCase()).toBe("header");
      expect(bar).toHaveAttribute("role", "banner");
      expect(bar).toHaveAttribute("aria-label", "Thanh lệnh toàn cục");

      expect(bar.className).toContain("sticky");
      expect(bar.className).toContain("top-0");
      expect(bar.className).toContain("h-14");
      expect(bar.className).toContain("min-h-[52px]");
      expect(bar.className).toContain("max-h-[58px]");
    });
  });

  describe("3. LEFT Section: CLARA Brand Mark + WorkspaceSwitcher", () => {
    it("renders CLARA brand mark linking to role home", () => {
      renderWithProviders(<GlobalCommandBar />);

      const brandLink = screen.getByTestId("global-command-bar-brand");
      expect(brandLink).toBeInTheDocument();
      expect(brandLink).toHaveAttribute("href", "/home");
      expect(within(brandLink).getByText("CLARA")).toBeInTheDocument();
      expect(within(brandLink).getByText("Care Platform")).toBeInTheDocument();
    });

    it("renders WorkspaceSwitcher with active workspace", () => {
      renderWithProviders(<GlobalCommandBar workspace="personal" />);

      const switcher = screen.getByTestId("workspace-switcher");
      expect(switcher).toBeInTheDocument();
      expect(screen.getByTestId("workspace-switcher-trigger")).toHaveTextContent("Cá nhân");
    });

    it("opens WorkspaceSwitcher dropdown to switch workspace", () => {
      const handleWorkspaceChange = vi.fn();
      renderWithProviders(
        <GlobalCommandBar
          role="doctor"
          workspace="clinical"
          onWorkspaceChange={handleWorkspaceChange}
        />,
        { role: "doctor", effectiveRole: "doctor" },
      );

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      fireEvent.click(trigger);

      const menu = screen.getByTestId("workspace-switcher-menu");
      expect(menu).toBeInTheDocument();

      const personalItem = screen.getByTestId("workspace-item-personal");
      fireEvent.click(personalItem);

      expect(handleWorkspaceChange).toHaveBeenCalledWith("personal");
      expect(mocks.routerPush).toHaveBeenCalledWith("/today");
    });
  });

  describe("4. CENTER Section: Global Search / Cmd+K Command Palette Trigger", () => {
    it("renders global search trigger button with ⌘K shortcut indicator", () => {
      renderWithProviders(<GlobalCommandBar />);

      const searchTrigger = screen.getByTestId("global-command-bar-search-trigger");
      expect(searchTrigger).toBeInTheDocument();
      expect(searchTrigger).toHaveTextContent("Tìm kiếm hoặc lệnh...");
      expect(searchTrigger).toHaveTextContent("⌘K");
    });

    it("invokes onOpenSearch or onOpenCommandPalette on click", () => {
      const handleOpenSearch = vi.fn();
      renderWithProviders(<GlobalCommandBar onOpenSearch={handleOpenSearch} />);

      const searchTrigger = screen.getByTestId("global-command-bar-search-trigger");
      fireEvent.click(searchTrigger);

      expect(handleOpenSearch).toHaveBeenCalledTimes(1);
    });
  });

  describe("5. RIGHT Section: Help, Notifications, Theme, Language, Profile", () => {
    it("renders Help link navigating to /huong-dan", () => {
      renderWithProviders(<GlobalCommandBar />);

      const helpLink = screen.getByTestId("global-command-bar-help-link");
      expect(helpLink).toBeInTheDocument();
      expect(helpLink).toHaveAttribute("href", "/huong-dan");
    });

    it("renders Notifications indicator with count badge", () => {
      renderWithProviders(<GlobalCommandBar />, { familyNotificationCount: 5 });

      const notifLink = screen.getByTestId("global-command-bar-notifications-link");
      expect(notifLink).toBeInTheDocument();
      expect(notifLink).toHaveAttribute("href", "/you/sharing");

      const badge = screen.getByTestId("global-command-bar-notification-badge");
      expect(badge).toHaveTextContent("5");
    });

    it("renders Theme Switcher and invokes theme toggle", () => {
      renderWithProviders(<GlobalCommandBar />, { themePreference: "dark" });

      const themeToggle = screen.getByTestId("global-command-bar-theme-toggle");
      expect(themeToggle).toBeInTheDocument();

      fireEvent.click(themeToggle);
      expect(mockHandleThemeChange).toHaveBeenCalledWith("light");
    });

    it("renders Language Switcher and invokes language toggle", () => {
      renderWithProviders(<GlobalCommandBar />, { uiLanguage: "vi" });

      const langToggle = screen.getByTestId("global-command-bar-language-toggle");
      expect(langToggle).toBeInTheDocument();
      expect(langToggle).toHaveTextContent("VI");

      fireEvent.click(langToggle);
      expect(mockHandleLanguageChange).toHaveBeenCalledWith("en");
    });

    it("renders Profile chip and opens dropdown menu with profile info, multi-profile select, and logout", () => {
      renderWithProviders(<GlobalCommandBar />);

      const profileTrigger = screen.getByTestId("global-command-bar-profile-trigger");
      expect(profileTrigger).toBeInTheDocument();
      expect(profileTrigger).toHaveTextContent("Nguyen Van A");

      // Open profile menu
      fireEvent.click(profileTrigger);

      const menu = screen.getByTestId("global-command-bar-profile-menu");
      expect(menu).toBeInTheDocument();
      expect(within(menu).getAllByText("Nguyen Van A").length).toBeGreaterThan(0);

      // Multi-profile selector
      const profileSelect = screen.getByRole("combobox", { name: /Hồ sơ đang dùng/i });
      expect(profileSelect).toBeInTheDocument();
      fireEvent.change(profileSelect, { target: { value: "p2" } });
      expect(mockHandleProfileChange).toHaveBeenCalledWith("p2");

      // Sign out action
      const signOutButton = screen.getByRole("button", { name: "Đăng xuất" });
      fireEvent.click(signOutButton);
      expect(mockHandleLogout).toHaveBeenCalledTimes(1);
    });

    it("closes profile menu when Escape key is pressed", () => {
      renderWithProviders(<GlobalCommandBar />);

      const profileTrigger = screen.getByTestId("global-command-bar-profile-trigger");
      fireEvent.click(profileTrigger);
      expect(screen.getByTestId("global-command-bar-profile-menu")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByTestId("global-command-bar-profile-menu")).toBeNull();
    });
  });

  describe("6. NO Page-specific Actions Invariant", () => {
    it("maintains pure global chrome without page-specific action toolbars", () => {
      renderWithProviders(<GlobalCommandBar />);

      // Should not contain local page-specific items like filters, export buttons, or record tools
      expect(screen.queryByTestId("local-action-bar")).toBeNull();
      expect(screen.queryByTestId("page-toolbar")).toBeNull();
    });
  });

  describe("7. Custom Visibility Toggles", () => {
    it("respects visibility toggle flags", () => {
      renderWithProviders(
        <GlobalCommandBar
          showBrand={false}
          showWorkspaceSwitcher={false}
          showSearchTrigger={false}
          showQuickToggles={false}
          showProfile={false}
        />,
      );

      expect(screen.queryByTestId("global-command-bar-brand")).toBeNull();
      expect(screen.queryByTestId("workspace-switcher")).toBeNull();
      expect(screen.queryByTestId("global-command-bar-search-trigger")).toBeNull();
      expect(screen.queryByTestId("global-command-bar-help-link")).toBeNull();
      expect(screen.queryByTestId("global-command-bar-profile-trigger")).toBeNull();
    });
  });
});
