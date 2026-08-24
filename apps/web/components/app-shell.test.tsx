import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PreferenceProvider } from "@/components/shell/preference-provider";
import { SessionBoundary, type AdminPreviewMode } from "@/components/shell/session-boundary";
import { ProfileBoundary } from "@/components/shell/profile-boundary";
import { ShellModeProvider } from "@/components/shell/shell-mode-provider";
import { CommandPaletteProvider } from "@/components/shell/command-palette-provider";
import AppShell from "@/components/app-shell";

const mocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  const routerPush = vi.fn();
  return {
    apiGet: vi.fn(),
    getOnboarding: vi.fn(),
    getProfileContext: vi.fn(),
    listFamilyNotifications: vi.fn(),
    routerReplace,
    routerPush,
    router: { replace: routerReplace, push: routerPush, refresh: vi.fn() },
    pathname: "/chat",
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/compliance/transparency-notice-gate", () => ({
  default: () => null,
}));

vi.mock("@/lib/auth-store", () => ({
  clearTokens: vi.fn(),
  getRole: () => "normal",
  setRole: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: mocks.apiGet,
  },
}));

vi.mock("@/lib/logout", () => ({
  beginLogout: vi.fn(),
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: mocks.getOnboarding,
}));

vi.mock("@/lib/profile-context-api", () => ({
  activateOwnedProfile: vi.fn(),
  getProfileContext: mocks.getProfileContext,
}));

vi.mock("@/lib/visit-family", () => ({
  listFamilyNotifications: mocks.listFamilyNotifications,
}));

function renderShell(
  children: ReactNode,
  initialPreviewMode?: AdminPreviewMode | null,
) {
  return render(
    <PreferenceProvider initialLanguage="vi">
      <SessionBoundary initialPreviewMode={initialPreviewMode}>
        <ProfileBoundary>
          <ShellModeProvider>
            <CommandPaletteProvider>
              <AppShell>{children}</AppShell>
            </CommandPaletteProvider>
          </ShellModeProvider>
        </ProfileBoundary>
      </SessionBoundary>
    </PreferenceProvider>,
  );
}

describe("AppShell Spatial Editorial Architecture", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/chat";
    window.localStorage.clear();
    mocks.apiGet.mockResolvedValue({ data: { role: "normal" } });
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: false });
    mocks.getProfileContext.mockResolvedValue({
      active_profile_id: "prof-1",
      reset_required: false,
      profiles: [
        {
          id: "prof-1",
          display_name: "Nguyen Van A",
          kind: "self",
          active: true,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    mocks.listFamilyNotifications.mockResolvedValue([]);
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

  it("mounts GlobalContextBar (top) and FloatingPrimaryDock (bottom) on /chat", async () => {
    renderShell(<div>Chat content</div>);

    // Top: GlobalContextBar
    expect(
      screen.getByRole("banner", { name: "Thanh ngữ cảnh toàn cục" }),
    ).toBeInTheDocument();

    // Bottom: FloatingPrimaryDock
    expect(
      screen.getByRole("navigation", { name: "Thanh điều hướng chính" }),
    ).toBeInTheDocument();

    // Content
    expect(screen.getByText("Chat content")).toBeInTheDocument();

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith("/auth/me", {
        timeout: 15000,
      });
    });
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });

  it("opens CommandPalette on universal Ctrl+K / Cmd+K keyboard shortcut", async () => {
    renderShell(<div>Chat content</div>);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Trigger Cmd+K
    fireEvent.keyDown(window, { key: "k", metaKey: true });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const input = screen.getByRole("combobox");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("data-pii-safe", "true");
  });

  it("retains backwards compatibility for utility onboarding routes without global chrome", async () => {
    mocks.pathname = "/welcome/body";
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

    const { container } = renderShell(<div>Body measurements</div>);

    expect(screen.getByText("Body measurements")).toBeInTheDocument();
    expect(
      screen.queryByRole("banner", { name: "Thanh ngữ cảnh toàn cục" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Thanh điều hướng chính" }),
    ).not.toBeInTheDocument();
    expect(container.querySelectorAll("main")).toHaveLength(1);
    await waitFor(() => expect(mocks.getOnboarding).toHaveBeenCalled());
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });

  it("redirects an unfinished user to the canonical first welcome step", async () => {
    mocks.pathname = "/today";
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

    renderShell(<div>Today content</div>);

    await waitFor(() => {
      expect(mocks.routerReplace).toHaveBeenCalledWith("/welcome/start");
    });
  });

  it("does not redirect a doctor with needs_onboarding to /welcome/start", async () => {
    mocks.pathname = "/council";
    mocks.apiGet.mockResolvedValue({ data: { role: "doctor" } });
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

    renderShell(<div>Council workspace</div>);

    await waitFor(() => {
      expect(screen.getByText("Council workspace")).toBeInTheDocument();
    });
    expect(mocks.routerReplace).not.toHaveBeenCalledWith("/welcome/start");
  });

  it("hides FloatingPrimaryDock on /admin routes when adminPreviewMode is null", async () => {
    mocks.pathname = "/admin/flow-debugger";
    mocks.apiGet.mockResolvedValue({ data: { role: "admin" } });

    renderShell(<div>Admin Flow Debugger</div>);

    await waitFor(() => {
      expect(screen.getByText("Admin Flow Debugger")).toBeInTheDocument();
    });

    // On /admin without preview mode, dock is completely hidden (no clutter)
    expect(
      screen.queryByRole("navigation", { name: "Thanh điều hướng chính" }),
    ).not.toBeInTheDocument();
    // Banner is not shown
    expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
  });

  it("shows FloatingPrimaryDock with doctor dock and AdminPreviewBanner when clinical preview is active on /admin", async () => {
    mocks.pathname = "/admin/flow-debugger";
    mocks.apiGet.mockResolvedValue({ data: { role: "admin" } });

    renderShell(<div>Admin Flow Debugger</div>, "clinical");

    await waitFor(() => {
      expect(screen.getByText("Admin Flow Debugger")).toBeInTheDocument();
    });

    // In clinical preview, dock is visible
    expect(
      screen.getByRole("navigation", { name: "Thanh điều hướng chính" }),
    ).toBeInTheDocument();
    // Doctor dock items (like Scribe) are present
    expect(screen.getByRole("link", { name: "Scribe" })).toBeInTheDocument();

    // Banner is mounted above top bar
    const banner = screen.getByTestId("admin-preview-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/ADMIN PREVIEW · CLINICAL/)).toBeInTheDocument();
  });
});
