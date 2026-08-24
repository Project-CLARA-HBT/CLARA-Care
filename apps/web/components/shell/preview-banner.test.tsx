import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";
import { PreviewBanner, AdminPreviewBanner } from "./preview-banner";
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import { SessionContext, type SessionContextValue } from "./session-boundary";
import type { WorkspaceContextValue, AdminPreviewPersona } from "@/lib/workspace/workspace.contract";

const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => "/admin",
}));

describe("PreviewBanner (Spec v1 Section 7 & 9)", () => {
  const createMockWorkspace = (
    overrides: Partial<WorkspaceContextValue> = {},
  ): WorkspaceContextValue => ({
    activeWorkspace: "admin",
    permittedWorkspaces: ["admin", "clinical", "research", "personal"],
    setActiveWorkspace: vi.fn(),
    adminPreviewPersona: null,
    setAdminPreviewPersona: vi.fn(),
    ...overrides,
  });

  const createMockSession = (
    overrides: Partial<SessionContextValue> = {},
  ): SessionContextValue => ({
    role: "admin",
    effectiveRole: "admin",
    adminPreviewMode: null,
    setAdminPreviewMode: vi.fn(),
    setRole: vi.fn(),
    isRoleHydrated: true,
    isSessionChecked: true,
    isLoggingOut: false,
    handleLogout: vi.fn(),
    ...overrides,
  });

  function renderWithWorkspace(
    workspaceValue: WorkspaceContextValue,
    sessionValue?: SessionContextValue,
    className?: string,
    onPersonaChange?: (persona: AdminPreviewPersona | null) => void,
  ) {
    const session = sessionValue ?? createMockSession();
    return render(
      <SessionContext.Provider value={session}>
        <WorkspaceContext.Provider value={workspaceValue}>
          <PreviewBanner className={className} onPersonaChange={onPersonaChange} />
        </WorkspaceContext.Provider>
      </SessionContext.Provider>,
    );
  }

  function renderWithSession(
    sessionValue: SessionContextValue,
    className?: string,
    onPersonaChange?: (persona: AdminPreviewPersona | null) => void,
  ) {
    return render(
      <SessionContext.Provider value={sessionValue}>
        <PreviewBanner className={className} onPersonaChange={onPersonaChange} />
      </SessionContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Visibility and Role Gating", () => {
    it("does not render when adminPreviewPersona is null", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: null });
      renderWithWorkspace(workspace);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("does not render when user role is not admin (e.g. doctor)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      const session = createMockSession({ role: "doctor", effectiveRole: "doctor" });
      renderWithWorkspace(workspace, session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("does not render when user role is researcher", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "research" });
      const session = createMockSession({ role: "researcher", effectiveRole: "researcher" });
      renderWithWorkspace(workspace, session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("does not render when user role is normal user", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "personal" });
      const session = createMockSession({ role: "normal", effectiveRole: "normal" });
      renderWithWorkspace(workspace, session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("renders sticky top notification banner when admin user has active adminPreviewPersona", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      const session = createMockSession({ role: "admin" });
      renderWithWorkspace(workspace, session);

      const banner = screen.getByTestId("admin-preview-banner");
      expect(banner).toBeInTheDocument();
      expect(banner.className).toContain("sticky top-0");
      expect(banner).toHaveAttribute("role", "status");
      expect(banner).toHaveAttribute("aria-label", "Admin Preview Banner");
    });
  });

  describe("Color-Coded Badges", () => {
    it("renders Emerald color-coded badge for Clinical mode (Bác sĩ)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const badge = screen.getByTestId("preview-badge-clinical");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-emerald-950");
      expect(badge.className).toContain("text-emerald-200");
      expect(badge.className).toContain("border-emerald-500/60");
      expect(screen.getByText(/ADMIN PREVIEW · CLINICAL/)).toBeInTheDocument();
      expect(screen.getByText(/\(Bác sĩ\)/)).toBeInTheDocument();
      expect(screen.getByText(/\(RBAC Untouched · UI Presentation Only\)/)).toBeInTheDocument();
    });

    it("renders Purple color-coded badge for Research mode (Nghiên cứu)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "research" });
      renderWithWorkspace(workspace);

      const badge = screen.getByTestId("preview-badge-research");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-purple-950");
      expect(badge.className).toContain("text-purple-200");
      expect(badge.className).toContain("border-purple-500/60");
      expect(screen.getByText(/ADMIN PREVIEW · RESEARCH/)).toBeInTheDocument();
      expect(screen.getByText(/\(Nghiên cứu\)/)).toBeInTheDocument();
    });

    it("renders Sky color-coded badge for Personal mode (Cá nhân)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "personal" });
      renderWithWorkspace(workspace);

      const badge = screen.getByTestId("preview-badge-personal");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-sky-950");
      expect(badge.className).toContain("text-sky-200");
      expect(badge.className).toContain("border-sky-500/60");
      expect(screen.getByText(/ADMIN PREVIEW · PERSONAL/)).toBeInTheDocument();
      expect(screen.getByText(/\(Cá nhân\)/)).toBeInTheDocument();
    });
  });

  describe("Inline Quick-Switcher Button Group", () => {
    it("renders all 5 switcher options: [Quản trị | Bác sĩ | Nghiên cứu | Cá nhân | ✕ Thoát Preview]", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const switcherGroup = screen.getByTestId("admin-preview-quick-switcher");
      expect(switcherGroup).toBeInTheDocument();

      expect(screen.getByTestId("preview-switch-admin")).toHaveTextContent("Quản trị");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveTextContent("Bác sĩ");
      expect(screen.getByTestId("preview-switch-research")).toHaveTextContent("Nghiên cứu");
      expect(screen.getByTestId("preview-switch-personal")).toHaveTextContent("Cá nhân");
      expect(screen.getByTestId("preview-exit-btn")).toHaveTextContent("✕ Thoát Preview");
    });

    it("sets aria-pressed='true' on the active persona button and 'false' on others", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "research" });
      renderWithWorkspace(workspace);

      expect(screen.getByTestId("preview-switch-admin")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-research")).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByTestId("preview-switch-personal")).toHaveAttribute("aria-pressed", "false");
    });
  });

  describe("1-Click Mode Switching and Workspace Navigation", () => {
    it("switches to Clinical workspace home (/dashboard) in 1 click", () => {
      const setAdminPreviewPersona = vi.fn();
      const workspace = createMockWorkspace({
        adminPreviewPersona: "personal",
        setAdminPreviewPersona,
      });

      renderWithWorkspace(workspace);
      fireEvent.click(screen.getByTestId("preview-switch-clinical"));

      expect(setAdminPreviewPersona).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewPersona).toHaveBeenCalledWith("clinical");
      expect(mockRouterPush).toHaveBeenCalledWith("/dashboard");
    });

    it("switches to Research workspace home (/evidence) in 1 click", () => {
      const setAdminPreviewPersona = vi.fn();
      const workspace = createMockWorkspace({
        adminPreviewPersona: "clinical",
        setAdminPreviewPersona,
      });

      renderWithWorkspace(workspace);
      fireEvent.click(screen.getByTestId("preview-switch-research"));

      expect(setAdminPreviewPersona).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewPersona).toHaveBeenCalledWith("research");
      expect(mockRouterPush).toHaveBeenCalledWith("/evidence");
    });

    it("switches to Personal workspace home (/today) in 1 click", () => {
      const setAdminPreviewPersona = vi.fn();
      const workspace = createMockWorkspace({
        adminPreviewPersona: "clinical",
        setAdminPreviewPersona,
      });

      renderWithWorkspace(workspace);
      fireEvent.click(screen.getByTestId("preview-switch-personal"));

      expect(setAdminPreviewPersona).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewPersona).toHaveBeenCalledWith("personal");
      expect(mockRouterPush).toHaveBeenCalledWith("/today");
    });

    it("switches to Admin workspace home (/admin/overview) when clicking 'Quản trị'", () => {
      const setAdminPreviewPersona = vi.fn();
      const workspace = createMockWorkspace({
        adminPreviewPersona: "clinical",
        setAdminPreviewPersona,
      });

      renderWithWorkspace(workspace);
      fireEvent.click(screen.getByTestId("preview-switch-admin"));

      expect(setAdminPreviewPersona).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewPersona).toHaveBeenCalledWith(null);
      expect(mockRouterPush).toHaveBeenCalledWith("/admin/overview");
    });

    it("exits preview mode and returns to Admin workspace home (/admin/overview) via '✕ Thoát Preview'", () => {
      const setAdminPreviewPersona = vi.fn();
      const workspace = createMockWorkspace({
        adminPreviewPersona: "clinical",
        setAdminPreviewPersona,
      });

      renderWithWorkspace(workspace);
      fireEvent.click(screen.getByTestId("preview-exit-btn"));

      expect(setAdminPreviewPersona).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewPersona).toHaveBeenCalledWith(null);
      expect(mockRouterPush).toHaveBeenCalledWith("/admin/overview");
    });

    it("calls onPersonaChange callback when provided", () => {
      const onPersonaChange = vi.fn();
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });

      renderWithWorkspace(workspace, undefined, undefined, onPersonaChange);
      fireEvent.click(screen.getByTestId("preview-switch-research"));

      expect(onPersonaChange).toHaveBeenCalledWith("research");
    });
  });

  describe("Backward Compatibility and Aliases", () => {
    it("works with SessionBoundary fallback when WorkspaceProvider is not mounted", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderWithSession(session);

      expect(screen.getByTestId("admin-preview-banner")).toBeInTheDocument();
      expect(screen.getByTestId("preview-badge-clinical")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("preview-switch-personal"));
      expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");
      expect(mockRouterPush).toHaveBeenCalledWith("/today");
    });

    it("AdminPreviewBanner alias works identically", () => {
      const session = createMockSession({
        role: "admin",
        adminPreviewMode: "research",
      });

      render(
        <SessionContext.Provider value={session}>
          <AdminPreviewBanner className="custom-banner" />
        </SessionContext.Provider>,
      );

      const banner = screen.getByTestId("admin-preview-banner");
      expect(banner).toBeInTheDocument();
      expect(banner.className).toContain("custom-banner");
      expect(screen.getByTestId("preview-badge-research")).toBeInTheDocument();
    });
  });
});
