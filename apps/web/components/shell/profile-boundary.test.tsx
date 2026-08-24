import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileBoundary, useProfileBoundary } from "./profile-boundary";
import { SessionContext } from "./session-boundary";
import { PROFILE_CONTEXT_CHANGE_EVENT } from "@/lib/profile-context";

const mocks = vi.hoisted(() => {
  const routerRefresh = vi.fn();
  return {
    getProfileContext: vi.fn(),
    activateOwnedProfile: vi.fn(),
    listFamilyNotifications: vi.fn(),
    clearProfileScopedClientState: vi.fn(),
    setActiveProfileId: vi.fn(),
    getActiveProfileId: vi.fn(),
    routerRefresh,
    pathname: "/home",
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ refresh: mocks.routerRefresh }),
}));

vi.mock("@/lib/profile-context-api", () => ({
  getProfileContext: mocks.getProfileContext,
  activateOwnedProfile: mocks.activateOwnedProfile,
}));

vi.mock("@/lib/visit-family", () => ({
  listFamilyNotifications: mocks.listFamilyNotifications,
}));

vi.mock("@/lib/profile-context", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/profile-context")>();
  return {
    ...actual,
    clearProfileScopedClientState: mocks.clearProfileScopedClientState,
    setActiveProfileId: mocks.setActiveProfileId,
    getActiveProfileId: mocks.getActiveProfileId,
  };
});

function ProfileConsumer() {
  const {
    activeProfile,
    activeProfileId,
    isProfileChanging,
    familyNotificationCount,
    handleProfileChange,
    profileContext,
  } = useProfileBoundary();

  return (
    <div>
      <span data-testid="active-id">{activeProfileId ?? "none"}</span>
      <span data-testid="active-name">{activeProfile?.display_name ?? "none"}</span>
      <span data-testid="changing">{String(isProfileChanging)}</span>
      <span data-testid="notifications">{familyNotificationCount}</span>
      <button onClick={() => void handleProfileChange("prof-2")}>Switch to Profile 2</button>
      <button onClick={() => void handleProfileChange("prof-shared")}>Switch to Shared</button>
    </div>
  );
}

describe("ProfileBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/home";
    mocks.getActiveProfileId.mockReturnValue("prof-1");
    mocks.getProfileContext.mockResolvedValue({
      active_profile_id: "prof-1",
      active_kind: "self",
      cache_scope: "scope-1",
      reset_required: false,
      profiles: [
        {
          id: "prof-1",
          display_name: "Nguyen Van A",
          kind: "self",
          active: true,
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "prof-2",
          display_name: "Nguyen Van B",
          kind: "self",
          active: false,
          created_at: "2026-01-02T00:00:00Z",
        },
        {
          id: "prof-shared",
          display_name: "Nguyen Thi C (Shared)",
          kind: "shared",
          active: false,
          created_at: "2026-01-03T00:00:00Z",
        },
      ],
    });
    mocks.activateOwnedProfile.mockResolvedValue({
      active_profile_id: "prof-2",
      reset_required: false,
      cache_scope: "scope-2",
      profile: {
        id: "prof-2",
        display_name: "Nguyen Van B",
        kind: "self",
        active: true,
        created_at: "2026-01-02T00:00:00Z",
      },
    });
    mocks.listFamilyNotifications.mockResolvedValue([{ id: "notif-1" }]);
  });

  const defaultSessionValue = {
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

  it("loads profile context and family notifications when session is checked", async () => {
    render(
      <SessionContext.Provider value={defaultSessionValue}>
        <ProfileBoundary>
          <ProfileConsumer />
        </ProfileBoundary>
      </SessionContext.Provider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-id")).toHaveTextContent("prof-1");
      expect(screen.getByTestId("active-name")).toHaveTextContent("Nguyen Van A");
      expect(screen.getByTestId("notifications")).toHaveTextContent("1");
    });
  });

  it("switches profile, clears profile-scoped cache, and refreshes router", async () => {
    render(
      <SessionContext.Provider value={defaultSessionValue}>
        <ProfileBoundary>
          <ProfileConsumer />
        </ProfileBoundary>
      </SessionContext.Provider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-id")).toHaveTextContent("prof-1");
    });

    fireEvent.click(screen.getByRole("button", { name: "Switch to Profile 2" }));

    await waitFor(() => {
      expect(mocks.activateOwnedProfile).toHaveBeenCalledWith("prof-2");
      expect(mocks.clearProfileScopedClientState).toHaveBeenCalled();
      expect(mocks.setActiveProfileId).toHaveBeenCalledWith("prof-2");
      expect(mocks.routerRefresh).toHaveBeenCalled();
    });
  });

  it("rejects activating a non-self profile", async () => {
    render(
      <SessionContext.Provider value={defaultSessionValue}>
        <ProfileBoundary>
          <ProfileConsumer />
        </ProfileBoundary>
      </SessionContext.Provider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-id")).toHaveTextContent("prof-1");
    });

    fireEvent.click(screen.getByRole("button", { name: "Switch to Shared" }));

    expect(mocks.activateOwnedProfile).not.toHaveBeenCalled();
    expect(mocks.clearProfileScopedClientState).not.toHaveBeenCalled();
  });

  it("refreshes profile context on external PROFILE_CONTEXT_CHANGE_EVENT", async () => {
    render(
      <SessionContext.Provider value={defaultSessionValue}>
        <ProfileBoundary>
          <ProfileConsumer />
        </ProfileBoundary>
      </SessionContext.Provider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-id")).toHaveTextContent("prof-1");
    });

    mocks.getProfileContext.mockClear();
    window.dispatchEvent(new CustomEvent(PROFILE_CONTEXT_CHANGE_EVENT));

    await waitFor(() => {
      expect(mocks.getProfileContext).toHaveBeenCalled();
    });
  });
});
