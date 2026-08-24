import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  FloatingNavbar,
  PERSONAL_NAV_ITEMS,
  CLINICAL_NAV_ITEMS,
  RESEARCH_NAV_ITEMS,
  ADMIN_NAV_ITEMS,
} from "./floating-navbar";
import { SessionContext, type SessionContextValue } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";

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

describe("FloatingNavbar (Spec v1 Section 10)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
  });

  afterEach(cleanup);

  describe("Surface and Chrome Contract", () => {
    it("renders built on ChromeSurface with variant='navbar' and elevation='floating'", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      const nav = screen.getByTestId("floating-navbar");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-chrome-surface", "true");
      expect(nav).toHaveAttribute("data-variant", "navbar");
      expect(nav).toHaveAttribute("data-elevation", "floating");
      expect(nav).toHaveAttribute("aria-label", "Thanh điều hướng chính");
    });
  });

  describe("Workspace-adaptive 5-destination navigation items (Spec v1 Section 10)", () => {
    it("renders exactly 5 destinations for 'personal' workspace: Hôm nay, Hành trình, Hỏi CLARA, Thuốc men, Cá nhân", () => {
      mocks.pathname = "/today";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);

      expect(screen.getByRole("link", { name: "Hôm nay" })).toHaveAttribute("href", "/today");
      expect(screen.getByRole("link", { name: "Hành trình" })).toHaveAttribute("href", "/lifemap");
      expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Thuốc men" })).toHaveAttribute("href", "/medicines");
      expect(screen.getByRole("link", { name: "Cá nhân" })).toHaveAttribute("href", "/you");

      // Verify constant exports
      expect(PERSONAL_NAV_ITEMS).toHaveLength(5);
      expect(PERSONAL_NAV_ITEMS[2].isCenter).toBe(true);
      expect(PERSONAL_NAV_ITEMS[2].href).toBe("/chat");
    });

    it("renders exactly 5 destinations for 'clinical' workspace: Tổng quan, Hội chẩn, Hỏi CLARA, Scribe, Bằng chứng", () => {
      mocks.pathname = "/dashboard";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="clinical" />
        </ShellModeProvider>,
      );

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);

      expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/dashboard");
      expect(screen.getByRole("link", { name: "Hội chẩn" })).toHaveAttribute("href", "/council");
      expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Scribe" })).toHaveAttribute("href", "/scribe");
      expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");

      // Verify constant exports
      expect(CLINICAL_NAV_ITEMS).toHaveLength(5);
      expect(CLINICAL_NAV_ITEMS[2].isCenter).toBe(true);
      expect(CLINICAL_NAV_ITEMS[2].href).toBe("/chat");
    });

    it("renders exactly 5 destinations for 'research' workspace: Bằng chứng, Nguồn Y văn, Hỏi CLARA, Tổng quan, Cá nhân", () => {
      mocks.pathname = "/evidence";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="research" />
        </ShellModeProvider>,
      );

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);

      expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
      expect(screen.getByRole("link", { name: "Nguồn Y văn" })).toHaveAttribute("href", "/research/source-hub");
      expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/dashboard");
      expect(screen.getByRole("link", { name: "Cá nhân" })).toHaveAttribute("href", "/you");

      // Verify constant exports
      expect(RESEARCH_NAV_ITEMS).toHaveLength(5);
      expect(RESEARCH_NAV_ITEMS[2].isCenter).toBe(true);
      expect(RESEARCH_NAV_ITEMS[2].href).toBe("/chat");
    });

    it("renders exactly 5 destinations for 'admin' workspace: Tổng quan, Người dùng, Hỏi CLARA, Hệ thống, Nhật ký", () => {
      mocks.pathname = "/admin/overview";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="admin" />
        </ShellModeProvider>,
      );

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);

      expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/admin/overview");
      expect(screen.getByRole("link", { name: "Người dùng" })).toHaveAttribute("href", "/admin/users");
      expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Hệ thống" })).toHaveAttribute("href", "/admin/system");
      expect(screen.getByRole("link", { name: "Nhật ký" })).toHaveAttribute("href", "/admin/audit");

      // Verify constant exports
      expect(ADMIN_NAV_ITEMS).toHaveLength(5);
      expect(ADMIN_NAV_ITEMS[2].isCenter).toBe(true);
      expect(ADMIN_NAV_ITEMS[2].href).toBe("/chat");
    });
  });

  describe("Center Item (ClaraOrb Interactive Hub)", () => {
    it("renders ClaraOrb in the center item position for /chat destination", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      const centerItem = screen.getByTestId("floating-nav-item-chat");
      expect(centerItem).toBeInTheDocument();
      expect(centerItem).toHaveAttribute("href", "/chat");

      // Verify status role element for ClaraOrb inside link
      const orbEl = centerItem.querySelector('[role="status"]');
      expect(orbEl).toBeInTheDocument();
    });

    it("invokes onOrbClick and onNavigate handlers when center item is clicked", () => {
      const handleOrbClick = vi.fn();
      const handleNavigate = vi.fn();

      render(
        <ShellModeProvider>
          <FloatingNavbar
            workspace="clinical"
            onOrbClick={handleOrbClick}
            onNavigate={handleNavigate}
          />
        </ShellModeProvider>,
      );

      const centerItem = screen.getByTestId("floating-nav-item-chat");
      fireEvent.click(centerItem);

      expect(handleOrbClick).toHaveBeenCalledTimes(1);
      expect(handleNavigate).toHaveBeenCalledWith("/chat");
    });
  });

  describe("Active Route Indicators", () => {
    it("marks active item with aria-current='page' and data-active='true'", () => {
      mocks.pathname = "/medicines";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      const medicinesItem = screen.getByTestId("floating-nav-item-medicines");
      expect(medicinesItem).toHaveAttribute("aria-current", "page");
      expect(medicinesItem).toHaveAttribute("data-active", "true");

      const todayItem = screen.getByTestId("floating-nav-item-today");
      expect(todayItem).not.toHaveAttribute("aria-current");
      expect(todayItem).toHaveAttribute("data-active", "false");
    });

    it("correctly identifies active route via activeMatchPrefix", () => {
      mocks.pathname = "/home"; // Should match 'today' item prefix
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      const todayItem = screen.getByTestId("floating-nav-item-today");
      expect(todayItem).toHaveAttribute("aria-current", "page");
      expect(todayItem).toHaveAttribute("data-active", "true");
    });

    it("marks center item active when on /chat or /ask", () => {
      mocks.pathname = "/chat";
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="clinical" />
        </ShellModeProvider>,
      );

      const chatItem = screen.getByTestId("floating-nav-item-chat");
      expect(chatItem).toHaveAttribute("aria-current", "page");
      expect(chatItem).toHaveAttribute("data-active", "true");
    });
  });

  describe("Role and Session Adaptive Derivation", () => {
    it("derives clinical workspace when role prop is 'doctor'", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar role="doctor" />
        </ShellModeProvider>,
      );

      expect(screen.getByTestId("floating-navbar")).toHaveAttribute("data-workspace", "clinical");
      expect(screen.getByRole("link", { name: "Hội chẩn" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Scribe" })).toBeInTheDocument();
    });

    it("derives research workspace when role prop is 'researcher'", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar role="researcher" />
        </ShellModeProvider>,
      );

      expect(screen.getByTestId("floating-navbar")).toHaveAttribute("data-workspace", "research");
      expect(screen.getByRole("link", { name: "Nguồn Y văn" })).toBeInTheDocument();
    });

    it("derives admin workspace when role prop is 'admin'", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar role="admin" />
        </ShellModeProvider>,
      );

      expect(screen.getByTestId("floating-navbar")).toHaveAttribute("data-workspace", "admin");
      expect(screen.getByRole("link", { name: "Hệ thống" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Nhật ký" })).toBeInTheDocument();
    });

    it("adapts to adminPreviewMode from SessionBoundary", () => {
      const mockSession = createMockSession({
        role: "admin",
        effectiveRole: "doctor",
        adminPreviewMode: "clinical",
      });

      render(
        <SessionContext.Provider value={mockSession}>
          <ShellModeProvider>
            <FloatingNavbar />
          </ShellModeProvider>
        </SessionContext.Provider>,
      );

      expect(screen.getByTestId("floating-navbar")).toHaveAttribute("data-workspace", "clinical");
      expect(screen.getByRole("link", { name: "Hội chẩn" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Scribe" })).toBeInTheDocument();
    });
  });

  describe("Mobile and Desktop Viewport Typography Contract", () => {
    it("ensures all 5 destination labels are visible text (no hidden labels on mobile)", () => {
      render(
        <ShellModeProvider>
          <FloatingNavbar workspace="personal" />
        </ShellModeProvider>,
      );

      // Verify each text label is in the DOM
      expect(screen.getByText("Hôm nay")).toBeInTheDocument();
      expect(screen.getByText("Hành trình")).toBeInTheDocument();
      expect(screen.getByText("Hỏi CLARA")).toBeInTheDocument();
      expect(screen.getByText("Thuốc men")).toBeInTheDocument();
      expect(screen.getByText("Cá nhân")).toBeInTheDocument();
    });
  });
});
