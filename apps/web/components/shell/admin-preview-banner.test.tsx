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

  function renderBanner(sessionValue: SessionContextValue) {
    return render(
      <SessionContext.Provider value={sessionValue}>
        <AdminPreviewBanner />
      </SessionContext.Provider>,
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when role is not admin", () => {
    const session = createMockSession({
      role: "doctor",
      effectiveRole: "doctor",
      adminPreviewMode: "clinical",
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

  it("renders slim high-contrast banner when role is admin and adminPreviewMode is clinical", () => {
    const setAdminPreviewMode = vi.fn();
    const session = createMockSession({
      role: "admin",
      effectiveRole: "doctor",
      adminPreviewMode: "clinical",
      setAdminPreviewMode,
    });

    renderBanner(session);

    const banner = screen.getByTestId("admin-preview-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/ADMIN PREVIEW · CLINICAL/)).toBeInTheDocument();
    expect(screen.getByText(/\(RBAC Untouched · UI Presentation Only\)/)).toBeInTheDocument();

    const exitBtn = screen.getByRole("button", { name: /Thoát Preview \/ Exit Preview/ });
    expect(exitBtn).toBeInTheDocument();

    fireEvent.click(exitBtn);
    expect(setAdminPreviewMode).toHaveBeenCalledWith(null);
  });

  it("renders correctly for research and personal preview modes", () => {
    const sessionResearch = createMockSession({
      role: "admin",
      effectiveRole: "researcher",
      adminPreviewMode: "research",
    });
    const { unmount } = renderBanner(sessionResearch);
    expect(screen.getByText(/ADMIN PREVIEW · RESEARCH/)).toBeInTheDocument();
    unmount();

    const sessionPersonal = createMockSession({
      role: "admin",
      effectiveRole: "normal",
      adminPreviewMode: "personal",
    });
    renderBanner(sessionPersonal);
    expect(screen.getByText(/ADMIN PREVIEW · PERSONAL/)).toBeInTheDocument();
  });
});
