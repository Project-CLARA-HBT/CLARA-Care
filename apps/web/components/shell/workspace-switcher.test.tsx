import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  WorkspaceSwitcher,
  WORKSPACE_OPTIONS,
  WORKSPACE_SWITCHER_PREVIEW_OPTIONS,
} from "./workspace-switcher";
import { SessionContext, type SessionContextValue } from "./session-boundary";

const mocks = vi.hoisted(() => ({
  pathname: "/today",
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({
    push: mocks.push,
    replace: mocks.replace,
    refresh: mocks.refresh,
  }),
}));

const createMockSession = (
  overrides?: Partial<SessionContextValue>,
): SessionContextValue => ({
  role: "normal",
  effectiveRole: "normal",
  adminPreviewMode: null,
  setAdminPreviewMode: vi.fn(),
  setRole: vi.fn(),
  isRoleHydrated: true,
  isSessionChecked: true,
  isLoggingOut: false,
  handleLogout: vi.fn(),
  ...overrides,
});

describe("WorkspaceSwitcher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
  });

  afterEach(cleanup);

  describe("Trigger & ChromeSurface Menu Rendering", () => {
    it("renders trigger button displaying current active workspace", () => {
      render(<WorkspaceSwitcher currentWorkspace="personal" />);

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      expect(trigger).toBeInTheDocument();
      expect(trigger).toHaveTextContent("Cá nhân");
      expect(trigger).toHaveAttribute("aria-expanded", "false");
      expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    });

    it("opens dropdown menu using ChromeSurface variant='menu' on trigger click", () => {
      render(<WorkspaceSwitcher currentWorkspace="personal" />);

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      fireEvent.click(trigger);

      expect(trigger).toHaveAttribute("aria-expanded", "true");
      const menu = screen.getByTestId("workspace-switcher-menu");
      expect(menu).toBeInTheDocument();
      expect(menu).toHaveAttribute("data-chrome-surface", "true");
      expect(menu).toHaveAttribute("data-variant", "menu");
      expect(menu).toHaveAttribute("data-elevation", "overlay");
    });

    it("closes menu when Escape key is pressed", () => {
      render(<WorkspaceSwitcher currentWorkspace="personal" />);

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      fireEvent.click(trigger);
      expect(screen.getByTestId("workspace-switcher-menu")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByTestId("workspace-switcher-menu")).not.toBeInTheDocument();
    });

    it("closes menu when clicking outside", () => {
      render(
        <div>
          <div data-testid="outside-target">Outside</div>
          <WorkspaceSwitcher currentWorkspace="personal" />
        </div>,
      );

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      fireEvent.click(trigger);
      expect(screen.getByTestId("workspace-switcher-menu")).toBeInTheDocument();

      fireEvent.mouseDown(screen.getByTestId("outside-target"));
      expect(screen.queryByTestId("workspace-switcher-menu")).not.toBeInTheDocument();
    });
  });

  describe("Permitted Workspaces Matrix by Role", () => {
    it("lists only 'personal' workspace for 'normal' user role", () => {
      render(<WorkspaceSwitcher role="normal" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.getByTestId("workspace-item-personal")).toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-clinical")).not.toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-research")).not.toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-admin")).not.toBeInTheDocument();
    });

    it("lists 'personal' and 'research' workspaces for 'researcher' role", () => {
      render(<WorkspaceSwitcher role="researcher" currentWorkspace="research" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.getByTestId("workspace-item-personal")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-research")).toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-clinical")).not.toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-admin")).not.toBeInTheDocument();
    });

    it("lists 'personal', 'clinical', and 'research' workspaces for 'doctor' role", () => {
      render(<WorkspaceSwitcher role="doctor" currentWorkspace="clinical" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.getByTestId("workspace-item-personal")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-clinical")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-research")).toBeInTheDocument();
      expect(screen.queryByTestId("workspace-item-admin")).not.toBeInTheDocument();
    });

    it("lists all 4 workspaces for 'admin' role", () => {
      render(<WorkspaceSwitcher role="admin" currentWorkspace="admin" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.getByTestId("workspace-item-personal")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-clinical")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-research")).toBeInTheDocument();
      expect(screen.getByTestId("workspace-item-admin")).toBeInTheDocument();
    });
  });

  describe("Workspace Switching & Navigation", () => {
    it("switches workspace on 1-click, triggers onWorkspaceChange, and navigates immediately", () => {
      const handleWorkspaceChange = vi.fn();
      mocks.pathname = "/today";

      render(
        <WorkspaceSwitcher
          role="doctor"
          currentWorkspace="personal"
          onWorkspaceChange={handleWorkspaceChange}
        />,
      );

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));
      fireEvent.click(screen.getByTestId("workspace-item-clinical"));

      expect(handleWorkspaceChange).toHaveBeenCalledWith("clinical");
      expect(mocks.push).toHaveBeenCalledWith("/dashboard");
      expect(screen.queryByTestId("workspace-switcher-menu")).not.toBeInTheDocument();
    });
  });

  describe("Admin Preview Capability (Spec v1 Section 10)", () => {
    it("renders Admin Preview section with clinical, research, and personal options for Admin role", () => {
      render(<WorkspaceSwitcher role="admin" currentWorkspace="admin" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.getByText(/Admin Preview/i)).toBeInTheDocument();
      expect(screen.getByTestId("admin-preview-item-clinical")).toBeInTheDocument();
      expect(screen.getByTestId("admin-preview-item-research")).toBeInTheDocument();
      expect(screen.getByTestId("admin-preview-item-personal")).toBeInTheDocument();

      // Verify constant exports
      expect(WORKSPACE_SWITCHER_PREVIEW_OPTIONS).toHaveLength(3);
    });

    it("does NOT render Admin Preview section for non-admin roles", () => {
      render(<WorkspaceSwitcher role="doctor" currentWorkspace="clinical" />);

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));

      expect(screen.queryByText(/Admin Preview/i)).not.toBeInTheDocument();
      expect(screen.queryByTestId("admin-preview-item-clinical")).not.toBeInTheDocument();
    });

    it("activates clinical admin preview on click, updates preview mode, and navigates to /dashboard", () => {
      const handleAdminPreviewChange = vi.fn();
      const handleWorkspaceChange = vi.fn();

      render(
        <WorkspaceSwitcher
          role="admin"
          currentWorkspace="admin"
          onAdminPreviewChange={handleAdminPreviewChange}
          onWorkspaceChange={handleWorkspaceChange}
        />,
      );

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));
      fireEvent.click(screen.getByTestId("admin-preview-item-clinical"));

      expect(handleAdminPreviewChange).toHaveBeenCalledWith("clinical");
      expect(handleWorkspaceChange).toHaveBeenCalledWith("clinical");
      expect(mocks.push).toHaveBeenCalledWith("/dashboard");
      expect(screen.queryByTestId("workspace-switcher-menu")).not.toBeInTheDocument();
    });

    it("activates research admin preview on click and navigates to /evidence", () => {
      const handleAdminPreviewChange = vi.fn();

      render(
        <WorkspaceSwitcher
          role="admin"
          currentWorkspace="admin"
          onAdminPreviewChange={handleAdminPreviewChange}
        />,
      );

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));
      fireEvent.click(screen.getByTestId("admin-preview-item-research"));

      expect(handleAdminPreviewChange).toHaveBeenCalledWith("research");
      expect(mocks.push).toHaveBeenCalledWith("/evidence");
    });

    it("activates personal admin preview on click and navigates to /today", () => {
      const handleAdminPreviewChange = vi.fn();

      render(
        <WorkspaceSwitcher
          role="admin"
          currentWorkspace="admin"
          onAdminPreviewChange={handleAdminPreviewChange}
        />,
      );

      fireEvent.click(screen.getByTestId("workspace-switcher-trigger"));
      fireEvent.click(screen.getByTestId("admin-preview-item-personal"));

      expect(handleAdminPreviewChange).toHaveBeenCalledWith("personal");
      expect(mocks.push).toHaveBeenCalledWith("/today");
    });

    it("displays 'Thoát chế độ xem trước' button and exits preview back to /admin/overview", () => {
      const handleAdminPreviewChange = vi.fn();
      const handleWorkspaceChange = vi.fn();

      render(
        <WorkspaceSwitcher
          role="admin"
          adminPreviewMode="clinical"
          onAdminPreviewChange={handleAdminPreviewChange}
          onWorkspaceChange={handleWorkspaceChange}
        />,
      );

      // Trigger should show Preview badge
      const trigger = screen.getByTestId("workspace-switcher-trigger");
      expect(trigger).toHaveTextContent("Preview");

      fireEvent.click(trigger);

      const exitBtn = screen.getByTestId("admin-preview-exit");
      expect(exitBtn).toBeInTheDocument();

      fireEvent.click(exitBtn);

      expect(handleAdminPreviewChange).toHaveBeenCalledWith(null);
      expect(handleWorkspaceChange).toHaveBeenCalledWith("admin");
      expect(mocks.push).toHaveBeenCalledWith("/admin/overview");
      expect(screen.queryByTestId("workspace-switcher-menu")).not.toBeInTheDocument();
    });
  });

  describe("Integration with SessionContext", () => {
    it("reads role and adminPreviewMode directly from SessionBoundary context", () => {
      const mockSession = createMockSession({
        role: "admin",
        adminPreviewMode: "research",
        setAdminPreviewMode: vi.fn(),
      });

      render(
        <SessionContext.Provider value={mockSession}>
          <WorkspaceSwitcher />
        </SessionContext.Provider>,
      );

      const trigger = screen.getByTestId("workspace-switcher-trigger");
      expect(trigger).toHaveTextContent("Nghiên cứu");
      expect(trigger).toHaveTextContent("Preview");

      fireEvent.click(trigger);
      fireEvent.click(screen.getByTestId("admin-preview-exit"));

      expect(mockSession.setAdminPreviewMode).toHaveBeenCalledWith(null);
      expect(mocks.push).toHaveBeenCalledWith("/admin/overview");
    });
  });
});
