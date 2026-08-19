import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfessionalLayout } from "./professional-layout";
import { PreferenceContext } from "./preference-provider";
import { ProfileBoundaryContext } from "./profile-boundary";
import { SessionContext } from "./session-boundary";

const mocks = vi.hoisted(() => {
  const routerPush = vi.fn();
  return {
    routerPush,
    pathname: "/dashboard",
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: mocks.routerPush }),
}));

vi.mock("@/components/compliance/transparency-notice-gate", () => ({
  default: () => null,
}));

describe("ProfessionalLayout", () => {
  const defaultPreferences = {
    themePreference: "dark" as const,
    setThemePreference: vi.fn(),
    handleThemeChange: vi.fn(),
    uiLanguage: "vi" as const,
    setUiLanguage: vi.fn(),
    handleLanguageChange: vi.fn(),
  };

  const defaultSession = {
    role: "doctor" as const,
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
          display_name: "Dr. Nguyen Van A",
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
      display_name: "Dr. Nguyen Van A",
      kind: "self",
      active: true,
      created_at: "2026-01-01T00:00:00Z",
    },
    activeProfileId: "prof-1",
    isProfileChanging: false,
    familyNotificationCount: 0,
    handleProfileChange: vi.fn(),
    refreshProfileContext: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/dashboard";
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        media: "(min-width: 1024px)",
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    );
  });

  function renderLayout() {
    return render(
      <PreferenceContext.Provider value={defaultPreferences}>
        <SessionContext.Provider value={defaultSession}>
          <ProfileBoundaryContext.Provider value={defaultProfile}>
            <ProfessionalLayout>
              <div data-testid="pro-content">Dashboard Content</div>
            </ProfessionalLayout>
          </ProfileBoundaryContext.Provider>
        </SessionContext.Provider>
      </PreferenceContext.Provider>,
    );
  }

  it("renders professional navigation elements and content", () => {
    renderLayout();

    expect(screen.getByTestId("pro-content")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mở điều hướng trên điện thoại" }),
    ).toBeInTheDocument();
  });

  it("allows switching professional workspaces", () => {
    renderLayout();

    const select = screen.getByLabelText("Chọn không gian làm việc");
    expect(select).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "research" } });
    expect(mocks.routerPush).toHaveBeenCalledWith("/chat");
  });
});
