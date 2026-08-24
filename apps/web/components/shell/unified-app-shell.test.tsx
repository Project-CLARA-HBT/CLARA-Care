import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PreferenceProvider } from "@/components/shell/preference-provider";
import {
  ServerSessionProvider,
  type AdminPreviewMode,
} from "@/components/shell/session-boundary";
import { ProfileProvider } from "@/components/shell/profile-boundary";
import { WorkspaceProvider } from "@/lib/workspace/workspace-provider";
import { ShellModeProvider } from "@/components/shell/shell-mode-provider";
import { CommandPaletteProvider } from "@/components/shell/command-palette-provider";
import UnifiedAppShell from "@/components/shell/unified-app-shell";

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
    pathname: "/today",
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

vi.mock("@/lib/auth-store", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-store")>();
  return {
    ...actual,
    clearTokens: vi.fn(),
    getRole: () => "normal",
    setRole: vi.fn(),
  };
});

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

function renderUnifiedShell(
  children: ReactNode,
  initialPreviewMode?: AdminPreviewMode | null,
  initialShellMode?: "explore" | "focus" | "immersive" | "read" | "dense",
) {
  return render(
    <PreferenceProvider initialLanguage="vi">
      <ServerSessionProvider initialPreviewMode={initialPreviewMode}>
        <ProfileProvider>
          <WorkspaceProvider>
            <ShellModeProvider initialMode={initialShellMode}>
              <CommandPaletteProvider>
                <UnifiedAppShell>{children}</UnifiedAppShell>
              </CommandPaletteProvider>
            </ShellModeProvider>
          </WorkspaceProvider>
        </ProfileProvider>
      </ServerSessionProvider>
    </PreferenceProvider>,
  );
}

describe("UnifiedAppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
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
  });

  describe("Composition on Standard/Focus/Dense routes", () => {
    it("composes ContextHeader (top), ContentFrame (<main id='main-content'>), FloatingNavbar (bottom), and CommandPalette on /today", async () => {
      renderUnifiedShell(<div>Today Content</div>);

      // Top: ContextHeader
      const contextHeader = await screen.findByTestId("context-header");
      expect(contextHeader).toBeInTheDocument();
      expect(contextHeader).toHaveAttribute("role", "banner");

      // Main: ContentFrame
      const contentFrame = screen.getByTestId("content-frame");
      expect(contentFrame).toBeInTheDocument();
      expect(contentFrame).toHaveAttribute("id", "main-content");
      expect(screen.getByText("Today Content")).toBeInTheDocument();

      // Bottom: FloatingNavbar
      const floatingNavbar = screen.getByTestId("floating-navbar");
      expect(floatingNavbar).toBeInTheDocument();

      // Skip link
      const skipLink = screen.getByText("Bỏ qua, tới nội dung chính");
      expect(skipLink).toBeInTheDocument();
      expect(skipLink).toHaveAttribute("href", "#main-content");

      // No preview banner on standard normal role
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("mounts ContextHeader and FloatingNavbar on dense /dashboard route for doctor role", async () => {
      mocks.pathname = "/dashboard";
      mocks.apiGet.mockResolvedValue({ data: { role: "doctor" } });

      renderUnifiedShell(<div>Dashboard Overview</div>, null, "dense");

      await waitFor(() => {
        expect(screen.getByText("Dashboard Overview")).toBeInTheDocument();
      });

      expect(screen.getByTestId("context-header")).toBeInTheDocument();
      expect(screen.getByTestId("floating-navbar")).toBeInTheDocument();
    });
  });

  describe("Public/Auth/Share Route Suppression", () => {
    it("suppresses ContextHeader and FloatingNavbar on public /login route, mounting clean unauthenticated container", async () => {
      mocks.pathname = "/login";

      renderUnifiedShell(<div>Login Form</div>);

      expect(screen.getByText("Login Form")).toBeInTheDocument();
      expect(screen.queryByTestId("context-header")).not.toBeInTheDocument();
      expect(screen.queryByTestId("floating-navbar")).not.toBeInTheDocument();

      // Still mounts clean <main id="main-content">
      const main = screen.getByRole("main");
      expect(main).toHaveAttribute("id", "main-content");
    });

    it("suppresses ContextHeader and FloatingNavbar on public share routes (/share/[token])", async () => {
      mocks.pathname = "/share/sample-share-token";

      renderUnifiedShell(<div>Shared Packet Content</div>);

      expect(screen.getByText("Shared Packet Content")).toBeInTheDocument();
      expect(screen.queryByTestId("context-header")).not.toBeInTheDocument();
      expect(screen.queryByTestId("floating-navbar")).not.toBeInTheDocument();
    });

    it("suppresses ContextHeader and FloatingNavbar on utility onboarding routes (/welcome/start)", async () => {
      mocks.pathname = "/welcome/start";
      mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

      renderUnifiedShell(<div>Welcome Step 1</div>);

      expect(screen.getByText("Welcome Step 1")).toBeInTheDocument();
      expect(screen.queryByTestId("context-header")).not.toBeInTheDocument();
      expect(screen.queryByTestId("floating-navbar")).not.toBeInTheDocument();

      await waitFor(() => {
        expect(mocks.getOnboarding).toHaveBeenCalled();
      });
    });
  });

  describe("Immersive Route Receding Behavior", () => {
    it("smoothly recedes FloatingNavbar on immersive mode (e.g. Scribe recording, full-screen conversation)", async () => {
      mocks.pathname = "/scribe";
      mocks.apiGet.mockResolvedValue({ data: { role: "doctor" } });

      renderUnifiedShell(<div>Scribe Recording Active</div>, null, "immersive");

      await waitFor(() => {
        expect(screen.getByText("Scribe Recording Active")).toBeInTheDocument();
      });

      // ContextHeader remains visible for top-level navigation and breadcrumbs
      expect(screen.getByTestId("context-header")).toBeInTheDocument();

      // FloatingNavbar smoothly recedes in immersive mode
      expect(screen.queryByTestId("floating-navbar")).not.toBeInTheDocument();

      // ContentFrame marked as immersive
      const contentFrame = screen.getByTestId("content-frame");
      expect(contentFrame).toHaveAttribute("data-immersive", "true");
    });
  });

  describe("Admin Preview Banner Integration", () => {
    it("renders PreviewBanner at top when admin preview is active", async () => {
      mocks.pathname = "/admin/overview";
      mocks.apiGet.mockResolvedValue({ data: { role: "admin" } });

      renderUnifiedShell(<div>Admin Workbench</div>, "clinical");

      await waitFor(() => {
        expect(screen.getByText("Admin Workbench")).toBeInTheDocument();
      });

      const banner = screen.getByTestId("admin-preview-banner");
      expect(banner).toBeInTheDocument();
      expect(screen.getByText(/ADMIN PREVIEW · CLINICAL/)).toBeInTheDocument();

      // ContextHeader and FloatingNavbar also mount
      expect(screen.getByTestId("context-header")).toBeInTheDocument();
      expect(screen.getByTestId("floating-navbar")).toBeInTheDocument();
    });
  });

  describe("Universal Command Palette Integration", () => {
    it("opens CommandPalette on universal Ctrl+K / Cmd+K shortcut", async () => {
      renderUnifiedShell(<div>Main Screen</div>);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent.keyDown(window, { key: "k", metaKey: true });

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });

      const input = screen.getByRole("combobox");
      expect(input).toBeInTheDocument();
    });
  });
});
