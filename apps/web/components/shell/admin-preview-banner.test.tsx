import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPreviewBanner } from "./admin-preview-banner";
import { SessionContext, type SessionContextValue } from "./session-boundary";

describe("AdminPreviewBanner", () => {
  const createMockSession = (overrides: Partial<SessionContextValue> = {}): SessionContextValue => ({
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

  function renderBanner(sessionValue: SessionContextValue, className?: string) {
    return render(
      <SessionContext.Provider value={sessionValue}>
        <AdminPreviewBanner className={className} />
      </SessionContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Visibility and Gating", () => {
    it("does not render when role is not admin", () => {
      const session = createMockSession({
        role: "doctor",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      });

      renderBanner(session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("does not render when role is researcher with preview mode", () => {
      const session = createMockSession({
        role: "researcher",
        effectiveRole: "researcher",
        adminPreviewMode: "research",
      });

      renderBanner(session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });

    it("does not render when role is admin but adminPreviewMode is null", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "admin",
        adminPreviewMode: null,
      });

      renderBanner(session);
      expect(screen.queryByTestId("admin-preview-banner")).not.toBeInTheDocument();
    });
  });

  describe("Active Mode Prominent Color Badges", () => {
    it("renders distinct badge for Clinical mode (Bác sĩ)", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      });

      renderBanner(session);

      const banner = screen.getByTestId("admin-preview-banner");
      expect(banner).toBeInTheDocument();
      expect(screen.getByText(/ADMIN PREVIEW · CLINICAL/)).toBeInTheDocument();
      expect(screen.getByText(/\(Bác sĩ\)/)).toBeInTheDocument();
      expect(screen.getByText(/\(RBAC Untouched · UI Presentation Only\)/)).toBeInTheDocument();

      const badge = screen.getByTestId("preview-badge-clinical");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-teal-950");
    });

    it("renders distinct badge for Research mode (Nghiên cứu)", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "researcher",
        adminPreviewMode: "research",
      });

      renderBanner(session);

      expect(screen.getByText(/ADMIN PREVIEW · RESEARCH/)).toBeInTheDocument();
      expect(screen.getByText(/\(Nghiên cứu\)/)).toBeInTheDocument();

      const badge = screen.getByTestId("preview-badge-research");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-purple-950");
    });

    it("renders distinct badge for Personal mode (Cá nhân)", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "normal",
        adminPreviewMode: "personal",
      });

      renderBanner(session);

      expect(screen.getByText(/ADMIN PREVIEW · PERSONAL/)).toBeInTheDocument();
      expect(screen.getByText(/\(Cá nhân\)/)).toBeInTheDocument();

      const badge = screen.getByTestId("preview-badge-personal");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("bg-sky-950");
    });
  });

  describe("Inline Quick-Switcher Button Group", () => {
    it("renders quick-switcher with [Quản trị | Bác sĩ | Nghiên cứu | Cá nhân | ✕ Thoát Preview]", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      });

      renderBanner(session);

      const switcherGroup = screen.getByTestId("admin-preview-quick-switcher");
      expect(switcherGroup).toBeInTheDocument();

      expect(screen.getByTestId("preview-switch-admin")).toHaveTextContent("Quản trị");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveTextContent("Bác sĩ");
      expect(screen.getByTestId("preview-switch-research")).toHaveTextContent("Nghiên cứu");
      expect(screen.getByTestId("preview-switch-personal")).toHaveTextContent("Cá nhân");
      expect(screen.getByTestId("preview-exit-btn")).toHaveTextContent("✕ Thoát Preview");
    });

    it("marks active button with aria-pressed=true for active preview mode", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "researcher",
        adminPreviewMode: "research",
      });

      renderBanner(session);

      expect(screen.getByTestId("preview-switch-admin")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-clinical")).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByTestId("preview-switch-research")).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByTestId("preview-switch-personal")).toHaveAttribute("aria-pressed", "false");
    });
  });

  describe("1-Click Switching Interactions", () => {
    it("switches to Clinical mode in 1 click", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "normal",
        adminPreviewMode: "personal",
        setAdminPreviewMode,
      });

      renderBanner(session);
      fireEvent.click(screen.getByTestId("preview-switch-clinical"));
      expect(setAdminPreviewMode).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewMode).toHaveBeenCalledWith("clinical");
    });

    it("switches to Research mode in 1 click", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderBanner(session);
      fireEvent.click(screen.getByTestId("preview-switch-research"));
      expect(setAdminPreviewMode).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewMode).toHaveBeenCalledWith("research");
    });

    it("switches to Personal mode in 1 click", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderBanner(session);
      fireEvent.click(screen.getByTestId("preview-switch-personal"));
      expect(setAdminPreviewMode).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewMode).toHaveBeenCalledWith("personal");
    });

    it("switches back to Quản trị (null mode) in 1 click", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderBanner(session);
      fireEvent.click(screen.getByTestId("preview-switch-admin"));
      expect(setAdminPreviewMode).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewMode).toHaveBeenCalledWith(null);
    });

    it("exits preview mode via '✕ Thoát Preview' button in 1 click", () => {
      const setAdminPreviewMode = vi.fn();
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
        setAdminPreviewMode,
      });

      renderBanner(session);
      fireEvent.click(screen.getByTestId("preview-exit-btn"));
      expect(setAdminPreviewMode).toHaveBeenCalledTimes(1);
      expect(setAdminPreviewMode).toHaveBeenCalledWith(null);
    });
  });

  describe("Custom Styling and Attributes", () => {
    it("applies custom className passed via props", () => {
      const session = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      });

      renderBanner(session, "custom-banner-class");
      const banner = screen.getByTestId("admin-preview-banner");
      expect(banner.className).toContain("custom-banner-class");
    });
  });
});

