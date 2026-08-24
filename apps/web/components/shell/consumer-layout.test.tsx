import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConsumerLayout } from "./consumer-layout";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";

const mocks = vi.hoisted(() => ({
  pathname: "/home",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("@/components/compliance/transparency-notice-gate", () => ({
  default: () => null,
}));

describe("ConsumerLayout", () => {
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

  function renderLayout(sessionOverrides = {}) {
    return render(
      <PreferenceContext.Provider value={defaultPreferences}>
        <SessionContext.Provider value={{ ...defaultSession, ...sessionOverrides }}>
          <ProfileBoundaryContext.Provider value={defaultProfile}>
            <ConsumerLayout>
              <div data-testid="page-content">Home Content</div>
            </ConsumerLayout>
          </ProfileBoundaryContext.Provider>
        </SessionContext.Provider>
      </PreferenceContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/home";
  });

  it("renders desktop sidebar with Ask button and 4 canonical items", () => {
    renderLayout();

    expect(screen.getByTestId("page-content")).toBeInTheDocument();

    // Check Ask CLARA button
    const askButtons = screen.getAllByRole("link", { name: "Hỏi CLARA" });
    expect(askButtons.length).toBeGreaterThanOrEqual(1);

    // Check canonical 4 items in sidebar
    const homeLinks = screen.getAllByRole("link", { name: "Hôm nay" });
    expect(homeLinks.length).toBeGreaterThanOrEqual(1);

    const healthLinks = screen.getAllByRole("link", { name: "Sức khỏe" });
    expect(healthLinks.length).toBeGreaterThanOrEqual(1);

    const careLinks = screen.getAllByRole("link", { name: "Chăm sóc" });
    expect(careLinks.length).toBeGreaterThanOrEqual(1);

    const youLinks = screen.getAllByRole("link", { name: "Cá nhân" });
    expect(youLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("renders mobile bottom navigation with 5 canonical items", () => {
    renderLayout();

    const navs = screen.getAllByRole("navigation", { name: "Điều hướng chính" });
    expect(navs.length).toBe(2);

    const mobileNav = navs[1];
    expect(mobileNav).toBeInTheDocument();

    const links = mobileNav.querySelectorAll("a");
    expect(links.length).toBe(5);
    expect(links[0]).toHaveAttribute("href", "/home");
    expect(links[1]).toHaveAttribute("href", "/health");
    expect(links[2]).toHaveAttribute("href", "/ask");
    expect(links[3]).toHaveAttribute("href", "/care");
    expect(links[4]).toHaveAttribute("href", "/you");
  });

  it("highlights the active route", () => {
    mocks.pathname = "/health";
    renderLayout();

    const activeLinks = screen.getAllByRole("link", { current: "page" });
    expect(activeLinks.length).toBeGreaterThanOrEqual(1);
    expect(activeLinks[0]).toHaveAttribute("href", "/health");
  });

  it("includes professional workspace link for doctor/researcher/admin role", () => {
    renderLayout({ role: "doctor" });

    // Doctor profile dropdown contains link to professional workspace
    const proLinks = screen.getAllByRole("link", { name: /Lâm sàng/ });
    expect(proLinks.length).toBeGreaterThanOrEqual(1);
  });
});
