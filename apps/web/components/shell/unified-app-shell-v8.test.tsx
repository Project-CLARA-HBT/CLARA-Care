import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function renderUnifiedShellV8(
  children: ReactNode,
  initialPreviewMode?: AdminPreviewMode | null,
  initialShellMode?: "explore" | "focus" | "immersive" | "read" | "dense",
) {
  return render(
    <PreferenceProvider initialLanguage="vi">
      <ServerSessionProvider initialPreviewMode={initialPreviewMode}>
        <ProfileProvider>
          <WorkspaceProvider initialAdminPreviewPersona={initialPreviewMode}>
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

describe("UnifiedAppShell V8 Structural Hierarchy (Spec v8)", () => {
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

  describe("Hierarchy Composition: PreviewContextStrip -> GlobalCommandBar -> <main id='main-content'> -> WorkspaceDock -> CommandPalette", () => {
    it("mounts the canonical shell hierarchy on standard /today route", async () => {
      renderUnifiedShellV8(<div>Personal Dashboard Content</div>);

      // 1. Skip Link
      const skipLink = screen.getByText("Bỏ qua, tới nội dung chính");
      expect(skipLink).toBeInTheDocument();
      expect(skipLink).toHaveAttribute("href", "#main-content");

      // 2. GlobalCommandBar / ContextHeader
      const commandBar = await screen.findByRole("banner", {
        name: "Thanh ngữ cảnh toàn cục",
      });
      expect(commandBar).toBeInTheDocument();

      // 3. Main Content: ContentFrame with id="main-content"
      const main = screen.getByTestId("content-frame");
      expect(main).toHaveAttribute("id", "main-content");
      expect(screen.getByText("Personal Dashboard Content")).toBeInTheDocument();

      // 4. WorkspaceDock (Personal Workspace with ClaraOrb)
      const dock = screen.getByRole("navigation", {
        name: "Thanh điều hướng không gian làm việc",
      });
      expect(dock).toBeInTheDocument();
      expect(dock).toHaveAttribute("data-workspace", "personal");
      expect(within(dock).getByRole("link", { name: "Hôm nay" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Hành trình" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "◉ CLARA" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Thuốc men" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Cá nhân" })).toBeInTheDocument();
    });

    it("mounts PreviewContextStrip at the very top when admin preview persona is active", async () => {
      mocks.pathname = "/admin/overview";
      mocks.apiGet.mockResolvedValue({ data: { role: "admin" } });

      renderUnifiedShellV8(<div>Admin Viewport</div>, "clinical");

      await waitFor(() => {
        expect(screen.getByText("Admin Viewport")).toBeInTheDocument();
      });

      // Top: PreviewContextStrip is mounted
      const previewStrip = screen.getByTestId("preview-context-strip");
      expect(previewStrip).toBeInTheDocument();
      expect(previewStrip).toHaveAttribute("data-preview-persona", "clinical");
      expect(screen.getByText(/Admin Preview · Clinical/)).toBeInTheDocument();

      // Followed by GlobalCommandBar
      expect(screen.getByRole("banner")).toBeInTheDocument();

      // Followed by <main id="main-content">
      expect(screen.getByTestId("content-frame")).toHaveAttribute("id", "main-content");

      // In clinical preview, WorkspaceDock displays Clinical items
      const dock = screen.getByRole("navigation", {
        name: "Thanh điều hướng không gian làm việc",
      });
      expect(dock).toHaveAttribute("data-workspace", "clinical");
      expect(within(dock).getByRole("link", { name: "Tổng quan" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Hội chẩn" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Scribe" })).toBeInTheDocument();
    });

    it("mounts Research WorkspaceDock on /evidence route", async () => {
      mocks.pathname = "/evidence";
      mocks.apiGet.mockResolvedValue({ data: { role: "researcher" } });

      renderUnifiedShellV8(<div>Living Evidence Content</div>);

      await waitFor(() => {
        expect(screen.getByText("Living Evidence Content")).toBeInTheDocument();
      });

      const dock = screen.getByRole("navigation", {
        name: "Thanh điều hướng không gian làm việc",
      });
      expect(dock).toHaveAttribute("data-workspace", "research");
      expect(within(dock).getByRole("link", { name: "Tra cứu" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Bằng chứng" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "◉ CLARA" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Nguồn" })).toBeInTheDocument();
      expect(within(dock).getByRole("link", { name: "Thêm" })).toBeInTheDocument();
    });
  });

  describe("Suppression and Receding Invariants", () => {
    it("suppresses GlobalCommandBar, PreviewStrip and WorkspaceDock on unauthenticated public routes (/login)", async () => {
      mocks.pathname = "/login";

      renderUnifiedShellV8(<div>Public Login Form</div>);

      expect(screen.getByText("Public Login Form")).toBeInTheDocument();

      // Suppressed
      expect(screen.queryByRole("banner")).not.toBeInTheDocument();
      expect(screen.queryByTestId("preview-context-strip")).not.toBeInTheDocument();
      expect(screen.queryByTestId("workspace-dock")).not.toBeInTheDocument();

      // Clean unauthenticated container
      const main = screen.getByRole("main");
      expect(main).toHaveAttribute("id", "main-content");
    });

    it("suppresses GlobalCommandBar and WorkspaceDock on share routes (/share/[token])", async () => {
      mocks.pathname = "/share/safe-share-token-123";

      renderUnifiedShellV8(<div>Shared Packet Reader</div>);

      expect(screen.getByText("Shared Packet Reader")).toBeInTheDocument();
      expect(screen.queryByRole("banner")).not.toBeInTheDocument();
      expect(screen.queryByTestId("workspace-dock")).not.toBeInTheDocument();
      expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    });

    it("smoothly recedes bottom WorkspaceDock in immersive mode (e.g. Scribe recording, full-screen conversation)", async () => {
      mocks.pathname = "/scribe";
      mocks.apiGet.mockResolvedValue({ data: { role: "doctor" } });

      renderUnifiedShellV8(<div>Live Scribe Audio Recording</div>, null, "immersive");

      await waitFor(() => {
        expect(screen.getByText("Live Scribe Audio Recording")).toBeInTheDocument();
      });

      // GlobalCommandBar remains accessible
      expect(screen.getByRole("banner")).toBeInTheDocument();

      // WorkspaceDock recedes in immersive mode
      expect(screen.queryByTestId("workspace-dock")).not.toBeInTheDocument();

      // ContentFrame marked as immersive
      const contentFrame = screen.getByTestId("content-frame");
      expect(contentFrame).toHaveAttribute("data-immersive", "true");
    });
  });

  describe("CommandPalette Universal Shortcut", () => {
    it("opens CommandPalette dialog via Cmd+K / Ctrl+K keyboard shortcut", async () => {
      renderUnifiedShellV8(<div>Main Workspace View</div>);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent.keyDown(window, { key: "k", metaKey: true });

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });

      const searchInput = screen.getByRole("combobox");
      expect(searchInput).toBeInTheDocument();
    });
  });
});
