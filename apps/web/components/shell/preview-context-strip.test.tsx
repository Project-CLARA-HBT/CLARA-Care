import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";
import {
  PreviewContextStrip,
  type PreviewContextStripProps,
} from "./preview-context-strip";
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import { SessionContext, type SessionContextValue } from "./session-boundary";
import type {
  WorkspaceContextValue,
  AdminPreviewPersona,
} from "@/lib/workspace/workspace.contract";

const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => "/admin",
}));

describe("PreviewContextStrip (Spec v8 Section 4.3 & 5.2)", () => {
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
    props: PreviewContextStripProps = {},
  ) {
    const session = sessionValue ?? createMockSession();
    return render(
      <SessionContext.Provider value={session}>
        <WorkspaceContext.Provider value={workspaceValue}>
          <PreviewContextStrip {...props} />
        </WorkspaceContext.Provider>
      </SessionContext.Provider>,
    );
  }

  function renderWithSession(
    sessionValue: SessionContextValue,
    props: PreviewContextStripProps = {},
  ) {
    return render(
      <SessionContext.Provider value={sessionValue}>
        <PreviewContextStrip {...props} />
      </SessionContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("1. Exact Vertical Height (24–32px) & Visual Bounds", () => {
    it("renders with exact height bounds of 24–32px (min-h-[24px] max-h-[32px] h-7 sm:h-8)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const strip = screen.getByTestId("preview-context-strip");
      expect(strip).toBeInTheDocument();
      expect(strip.className).toContain("min-h-[24px]");
      expect(strip.className).toContain("max-h-[32px]");
      expect(strip.className).toContain("h-7");
      expect(strip.className).toContain("sm:h-8");
    });

    it("maintains <=32px height constraint (24–32px) in collapsed mode", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace, undefined, { defaultCollapsed: true });

      const collapsedStrip = screen.getByTestId("preview-context-strip-collapsed");
      expect(collapsedStrip).toBeInTheDocument();
      expect(collapsedStrip.className).toContain("min-h-[24px]");
      expect(collapsedStrip.className).toContain("max-h-[32px]");
      expect(collapsedStrip.className).toContain("h-7");
    });
  });

  describe("2. Muted Warm Neutral Tone (Not bright overwhelming yellow)", () => {
    it("uses muted warm neutral palette and avoids bright yellow warning banner styles", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const strip = screen.getByTestId("preview-context-strip");
      // Must NOT use the old bright yellow banner styles
      expect(strip.className).not.toContain("bg-amber-400");
      expect(strip.className).not.toContain("text-amber-950 bg-amber-400");

      // Must use muted neutral background
      expect(strip.className).toContain("bg-stone-100");
      expect(strip.className).toContain("dark:bg-stone-900");
    });
  });

  describe("3. Label Formatting: Admin Preview · [Clinical | Research | Personal]", () => {
    it("renders 'Admin Preview · Clinical' for clinical preview mode", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      expect(screen.getByText("Admin Preview · Clinical")).toBeInTheDocument();
      expect(screen.getByTestId("preview-badge-clinical")).toBeInTheDocument();
    });

    it("renders 'Admin Preview · Research' for research preview mode", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "research" });
      renderWithWorkspace(workspace);

      expect(screen.getByText("Admin Preview · Research")).toBeInTheDocument();
      expect(screen.getByTestId("preview-badge-research")).toBeInTheDocument();
    });

    it("renders 'Admin Preview · Personal' for personal preview mode", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "personal" });
      renderWithWorkspace(workspace);

      expect(screen.getByText("Admin Preview · Personal")).toBeInTheDocument();
      expect(screen.getByTestId("preview-badge-personal")).toBeInTheDocument();
    });
  });

  describe("4. Subtitle: Presentation only · RBAC unchanged", () => {
    it("renders exact subtitle 'Presentation only · RBAC unchanged'", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const subtitle = screen.getByTestId("preview-strip-subtitle");
      expect(subtitle).toBeInTheDocument();
      expect(subtitle).toHaveTextContent("Presentation only · RBAC unchanged");
    });
  });

  describe("5. Grouped Preview Persona Controls on Right: [Quản trị | Bác sĩ | Nghiên cứu | Cá nhân | ✕ Thoát Preview]", () => {
    it("renders grouped controls container with role='group'", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      const group = screen.getByRole("group", { name: "Admin Preview Controls" });
      expect(group).toBeInTheDocument();
    });

    it("renders all 5 switcher options: [Quản trị | Bác sĩ | Nghiên cứu | Cá nhân | ✕ Thoát Preview]", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      renderWithWorkspace(workspace);

      expect(screen.getByTestId("preview-switch-admin")).toHaveTextContent("Quản trị");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveTextContent("Bác sĩ");
      expect(screen.getByTestId("preview-switch-research")).toHaveTextContent("Nghiên cứu");
      expect(screen.getByTestId("preview-switch-personal")).toHaveTextContent("Cá nhân");
      expect(screen.getByTestId("preview-exit-btn")).toHaveTextContent("✕ Thoát Preview");
    });

    it("sets aria-pressed='true' on active button and 'false' on other buttons", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "research" });
      renderWithWorkspace(workspace);

      expect(screen.getByTestId("preview-switch-admin")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-research")).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByTestId("preview-switch-personal")).toHaveAttribute("aria-pressed", "false");
    });
  });

  describe("6. 1-Click Navigation & Role/Persona State Changes", () => {
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

    it("switches to Admin workspace home (/admin/overview) via 'Quản trị'", () => {
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

    it("exits preview mode via '✕ Thoát Preview' and returns to /admin/overview", () => {
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

    it("fires onPersonaChange callback when persona changes", () => {
      const onPersonaChange = vi.fn();
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });

      renderWithWorkspace(workspace, undefined, { onPersonaChange });
      fireEvent.click(screen.getByTestId("preview-switch-research"));

      expect(onPersonaChange).toHaveBeenCalledWith("research");
    });
  });

  describe("7. Collapsible Behavior & Accessibility", () => {
    it("can be collapsed and expanded via toggle buttons", () => {
      const onCollapseToggle = vi.fn();
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });

      renderWithWorkspace(workspace, undefined, { onCollapseToggle });

      // Initially expanded
      const collapseBtn = screen.getByTestId("preview-collapse-toggle");
      expect(collapseBtn).toHaveAttribute("aria-expanded", "true");

      // Click collapse
      fireEvent.click(collapseBtn);
      expect(onCollapseToggle).toHaveBeenCalledWith(true);

      // Now in collapsed state
      expect(screen.getByTestId("preview-context-strip-collapsed")).toBeInTheDocument();
      const expandBtn = screen.getByTestId("preview-expand-toggle");
      expect(expandBtn).toHaveAttribute("aria-expanded", "false");

      // Click expand
      fireEvent.click(expandBtn);
      expect(onCollapseToggle).toHaveBeenCalledWith(false);

      // Back to expanded
      expect(screen.getByTestId("preview-context-strip")).toBeInTheDocument();
    });

    it("respects controlled isCollapsed prop", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });
      const { rerender } = render(
        <SessionContext.Provider value={createMockSession()}>
          <WorkspaceContext.Provider value={workspace}>
            <PreviewContextStrip isCollapsed={true} />
          </WorkspaceContext.Provider>
        </SessionContext.Provider>,
      );

      expect(screen.getByTestId("preview-context-strip-collapsed")).toBeInTheDocument();

      rerender(
        <SessionContext.Provider value={createMockSession()}>
          <WorkspaceContext.Provider value={workspace}>
            <PreviewContextStrip isCollapsed={false} />
          </WorkspaceContext.Provider>
        </SessionContext.Provider>,
      );

      expect(screen.getByTestId("preview-context-strip")).toBeInTheDocument();
    });
  });

  describe("8. Gating, Safety & Server RBAC Preservation", () => {
    it("does not render when adminPreviewPersona is null", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: null });
      renderWithWorkspace(workspace);

      expect(screen.queryByTestId("preview-context-strip")).not.toBeInTheDocument();
      expect(screen.queryByTestId("preview-context-strip-collapsed")).not.toBeInTheDocument();
    });

    it("does not render for non-admin roles (doctor, researcher, normal)", () => {
      const workspace = createMockWorkspace({ adminPreviewPersona: "clinical" });

      const doctorSession = createMockSession({ role: "doctor", effectiveRole: "doctor" });
      const { unmount } = renderWithWorkspace(workspace, doctorSession);
      expect(screen.queryByTestId("preview-context-strip")).not.toBeInTheDocument();
      unmount();

      const researcherSession = createMockSession({ role: "researcher", effectiveRole: "researcher" });
      const { unmount: unmount2 } = renderWithWorkspace(workspace, researcherSession);
      expect(screen.queryByTestId("preview-context-strip")).not.toBeInTheDocument();
      unmount2();

      const normalSession = createMockSession({ role: "normal", effectiveRole: "normal" });
      renderWithWorkspace(workspace, normalSession);
      expect(screen.queryByTestId("preview-context-strip")).not.toBeInTheDocument();
    });

    it("falls back to SessionBoundary when WorkspaceContext is not present", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderWithSession(session);

      expect(screen.getByTestId("preview-context-strip")).toBeInTheDocument();
      expect(screen.getByText("Admin Preview · Clinical")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("preview-switch-personal"));
      expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");
      expect(mockRouterPush).toHaveBeenCalledWith("/today");
    });
  });
});
