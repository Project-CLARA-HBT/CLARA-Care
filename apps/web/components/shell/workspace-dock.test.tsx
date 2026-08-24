import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as ShellIndex from "@/components/shell";
import * as WorkspaceDockModule from "./workspace-dock";
import WorkspaceDockDefault, {
  CLINICAL_DOCK_ITEMS,
  PERSONAL_DOCK_ITEMS,
  RESEARCH_DOCK_ITEMS,
  WORKSPACE_DOCK_DESKTOP_HEIGHT_CLASS,
  WORKSPACE_DOCK_HEIGHT_RANGE,
  WORKSPACE_DOCK_ITEMS,
  WORKSPACE_DOCK_SAFE_AREA_CLASS,
  WorkspaceDock,
  WorkspaceDockSafeArea,
  isDockItemActive,
} from "./workspace-dock";
import { SessionContext } from "./session-boundary";
import { ShellModeProvider } from "./shell-mode-provider";
import { WorkspaceContext } from "@/lib/workspace/workspace-provider";
import type { WorkspaceContextValue } from "@/lib/workspace/workspace.contract";

const mocks = vi.hoisted(() => ({
  pathname: "/today",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

function createWorkspaceContextValue(
  overrides: Partial<WorkspaceContextValue> = {},
): WorkspaceContextValue {
  return {
    activeWorkspace: "personal",
    permittedWorkspaces: ["personal"],
    setActiveWorkspace: vi.fn(),
    adminPreviewPersona: null,
    setAdminPreviewPersona: vi.fn(),
    ...overrides,
  };
}

describe("WorkspaceDock (Spec v8 Section 4.4 & 5.3)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/today";
  });

  describe("Exports verification", () => {
    it("exports named and default WorkspaceDock from module and barrel", () => {
      expect(WorkspaceDock).toBeDefined();
      expect(WorkspaceDockDefault).toBeDefined();
      expect(WorkspaceDockModule.WorkspaceDock).toBeDefined();
      expect(WorkspaceDockModule.default).toBeDefined();
      expect(ShellIndex.WorkspaceDock).toBeDefined();
    });

    it("exports required constants and helper components", () => {
      expect(WORKSPACE_DOCK_SAFE_AREA_CLASS).toBe("pb-20 sm:pb-24");
      expect(WORKSPACE_DOCK_HEIGHT_RANGE).toBe("52–58px");
      expect(WORKSPACE_DOCK_DESKTOP_HEIGHT_CLASS).toContain("h-[54px]");
      expect(WorkspaceDockSafeArea).toBeDefined();
      expect(PERSONAL_DOCK_ITEMS).toHaveLength(5);
      expect(CLINICAL_DOCK_ITEMS).toHaveLength(5);
      expect(RESEARCH_DOCK_ITEMS).toHaveLength(5);
    });
  });

  describe("Personal Workspace Dock", () => {
    it("renders exactly 5 primary personal destinations with center ClaraOrb", () => {
      render(
        <WorkspaceDock workspace="personal" />,
      );

      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "personal");

      // 5 items: Hôm nay (/today) | Hành trình (/lifemap) | CLARA (/chat) | Thuốc men (/medicines) | Cá nhân (/you)
      expect(screen.getByRole("link", { name: "Hôm nay" })).toHaveAttribute("href", "/today");
      expect(screen.getByRole("link", { name: "Hành trình" })).toHaveAttribute("href", "/lifemap");
      expect(screen.getByRole("link", { name: /CLARA/ })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Thuốc men" })).toHaveAttribute("href", "/medicines");
      expect(screen.getByRole("link", { name: "Cá nhân" })).toHaveAttribute("href", "/you");

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);
    });

    it("marks active link appropriately on /today", () => {
      mocks.pathname = "/today";
      render(<WorkspaceDock workspace="personal" />);

      const todayLink = screen.getByTestId("workspace-dock-item-today");
      expect(todayLink).toHaveAttribute("data-active", "true");
      expect(todayLink).toHaveAttribute("aria-current", "page");

      const lifemapLink = screen.getByTestId("workspace-dock-item-lifemap");
      expect(lifemapLink).toHaveAttribute("data-active", "false");
    });
  });

  describe("Clinical Workspace Dock", () => {
    it("renders clinical items: Tổng quan (/dashboard) | Hội chẩn (/council) | CLARA (/chat) | Scribe (/scribe) | Thêm (/clinical/patients)", () => {
      mocks.pathname = "/dashboard";
      render(
        <WorkspaceDock workspace="clinical" />,
      );

      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "clinical");

      expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/dashboard");
      expect(screen.getByRole("link", { name: "Hội chẩn" })).toHaveAttribute("href", "/council");
      expect(screen.getByRole("link", { name: /CLARA/ })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Scribe" })).toHaveAttribute("href", "/scribe");
      expect(screen.getByRole("link", { name: "Thêm" })).toHaveAttribute("href", "/clinical/patients");

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);
    });

    it("marks active link on /council", () => {
      mocks.pathname = "/council";
      render(<WorkspaceDock workspace="clinical" />);

      const councilLink = screen.getByTestId("workspace-dock-item-council");
      expect(councilLink).toHaveAttribute("data-active", "true");
      expect(councilLink).toHaveAttribute("aria-current", "page");

      const overviewLink = screen.getByTestId("workspace-dock-item-overview");
      expect(overviewLink).toHaveAttribute("data-active", "false");
    });
  });

  describe("Research Workspace Dock", () => {
    it("renders research items: Tra cứu (/research) | Bằng chứng (/evidence) | CLARA (/chat) | Nguồn (/research/source-hub) | Thêm (/you)", () => {
      mocks.pathname = "/evidence";
      render(
        <WorkspaceDock workspace="research" />,
      );

      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "research");

      expect(screen.getByRole("link", { name: "Tra cứu" })).toHaveAttribute("href", "/research");
      expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
      expect(screen.getByRole("link", { name: /CLARA/ })).toHaveAttribute("href", "/chat");
      expect(screen.getByRole("link", { name: "Nguồn" })).toHaveAttribute("href", "/research/source-hub");
      expect(screen.getByRole("link", { name: "Thêm" })).toHaveAttribute("href", "/you");

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(5);
    });

    it("disambiguates active state between /research and /research/source-hub", () => {
      mocks.pathname = "/research/source-hub";
      render(<WorkspaceDock workspace="research" />);

      const sourceHubLink = screen.getByTestId("workspace-dock-item-sources");
      expect(sourceHubLink).toHaveAttribute("data-active", "true");

      const researchLink = screen.getByTestId("workspace-dock-item-research");
      expect(researchLink).toHaveAttribute("data-active", "false");
    });
  });

  describe("Admin gating (Admin does NOT mount consumer bottom dock)", () => {
    it("does NOT mount dock when workspace='admin'", () => {
      render(<WorkspaceDock workspace="admin" />);
      expect(screen.queryByTestId("workspace-dock")).toBeNull();
    });

    it("does NOT mount dock when role='admin' without preview persona", () => {
      render(<WorkspaceDock role="admin" />);
      expect(screen.queryByTestId("workspace-dock")).toBeNull();
    });

    it("suppresses dock on /admin/* routes when no preview persona is active", () => {
      mocks.pathname = "/admin/overview";
      render(<WorkspaceDock role="admin" />);
      expect(screen.queryByTestId("workspace-dock")).toBeNull();

      mocks.pathname = "/admin/users";
      render(<WorkspaceDock />);
      expect(screen.queryByTestId("workspace-dock")).toBeNull();
    });

    it("mounts clinical dock when admin is in clinical preview persona", () => {
      render(<WorkspaceDock role="admin" adminPreviewPersona="clinical" />);
      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "clinical");
      expect(screen.getByRole("link", { name: "Hội chẩn" })).toBeInTheDocument();
    });

    it("mounts research dock when admin is in research preview persona", () => {
      render(<WorkspaceDock role="admin" adminPreviewPersona="research" />);
      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "research");
      expect(screen.getByRole("link", { name: "Nguồn" })).toBeInTheDocument();
    });

    it("mounts personal dock when admin is in personal preview persona", () => {
      render(<WorkspaceDock role="admin" adminPreviewPersona="personal" />);
      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "personal");
      expect(screen.getByRole("link", { name: "Hành trình" })).toBeInTheDocument();
    });

    it("reads preview persona from WorkspaceContext", () => {
      const contextValue = createWorkspaceContextValue({
        activeWorkspace: "admin",
        adminPreviewPersona: "clinical",
      });

      render(
        <WorkspaceContext.Provider value={contextValue}>
          <WorkspaceDock />
        </WorkspaceContext.Provider>,
      );

      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("data-workspace", "clinical");
    });
  });

  describe("Desktop Dimensions & Floating Visual Constraints", () => {
    it("has desktop height within 52–58px and floating positioning", () => {
      render(<WorkspaceDock workspace="personal" />);
      const nav = screen.getByTestId("workspace-dock");

      expect(nav.className).toContain("fixed");
      expect(nav.className).toContain("bottom-3");
      expect(nav.className).toContain("left-1/2");
      expect(nav.className).toContain("-translate-x-1/2");
      expect(nav.className).toContain("h-[54px]");
      expect(nav.className).toContain("min-h-[52px]");
      expect(nav.className).toContain("max-h-[58px]");
    });
  });

  describe("Center Interactive ClaraOrb", () => {
    it("invokes onOrbClick and onNavigate on clicking center CLARA orb", () => {
      const handleOrbClick = vi.fn();
      const handleNavigate = vi.fn();

      render(
        <WorkspaceDock
          workspace="personal"
          onOrbClick={handleOrbClick}
          onNavigate={handleNavigate}
        />,
      );

      const chatLink = screen.getByTestId("workspace-dock-item-chat");
      expect(chatLink).toHaveAttribute("href", "/chat");

      fireEvent.click(chatLink);
      expect(handleOrbClick).toHaveBeenCalledTimes(1);
      expect(handleNavigate).toHaveBeenCalledWith("/chat");
    });

    it("highlights center link when active on /chat", () => {
      mocks.pathname = "/chat";
      render(<WorkspaceDock workspace="personal" />);

      const chatLink = screen.getByTestId("workspace-dock-item-chat");
      expect(chatLink).toHaveAttribute("data-active", "true");
      expect(chatLink).toHaveAttribute("aria-current", "page");
    });
  });

  describe("Safe Area Reservation (Spec UX8-008 & 5.3)", () => {
    it("exports standard safe area class 'pb-20 sm:pb-24'", () => {
      expect(WORKSPACE_DOCK_SAFE_AREA_CLASS).toBe("pb-20 sm:pb-24");
    });

    it("WorkspaceDockSafeArea applies pb-20 sm:pb-24 padding", () => {
      render(
        <WorkspaceDockSafeArea>
          <div data-testid="page-content">Main Page Content</div>
        </WorkspaceDockSafeArea>,
      );

      const safeAreaWrapper = screen.getByTestId("workspace-dock-safe-area");
      expect(safeAreaWrapper).toHaveClass("pb-20");
      expect(safeAreaWrapper).toHaveClass("sm:pb-24");
      expect(screen.getByTestId("page-content")).toBeInTheDocument();
    });

    it("renders spacer when reserveSafeArea is enabled", () => {
      render(<WorkspaceDock workspace="personal" reserveSafeArea={true} />);
      const spacer = screen.getByTestId("workspace-dock-safe-area-spacer");
      expect(spacer).toBeInTheDocument();
      expect(spacer).toHaveClass("h-20");
      expect(spacer).toHaveClass("sm:h-24");
    });
  });

  describe("Compact & Focus scene support", () => {
    it("renders compact mode when morphState='COMPACT'", () => {
      render(
        <ShellModeProvider initialDockState="COMPACT">
          <WorkspaceDock workspace="personal" morphState="COMPACT" />
        </ShellModeProvider>,
      );

      const nav = screen.getByTestId("workspace-dock");
      expect(nav).toBeInTheDocument();
      expect(screen.getAllByRole("link")).toHaveLength(5);
    });
  });

  describe("isDockItemActive utility function", () => {
    it("correctly matches active paths including subroutes and aliases", () => {
      expect(isDockItemActive("/today", PERSONAL_DOCK_ITEMS[0])).toBe(true);
      expect(isDockItemActive("/home", PERSONAL_DOCK_ITEMS[0])).toBe(true);
      expect(isDockItemActive("/lifemap/timeline", PERSONAL_DOCK_ITEMS[1])).toBe(true);
      expect(isDockItemActive("/phr", PERSONAL_DOCK_ITEMS[1])).toBe(true);
      expect(isDockItemActive("/chat", PERSONAL_DOCK_ITEMS[2])).toBe(true);
      expect(isDockItemActive("/ask", PERSONAL_DOCK_ITEMS[2])).toBe(true);
      expect(isDockItemActive("/medicines/detail/123", PERSONAL_DOCK_ITEMS[3])).toBe(true);
      expect(isDockItemActive("/you/profile", PERSONAL_DOCK_ITEMS[4])).toBe(true);

      // Clinical
      expect(isDockItemActive("/dashboard", CLINICAL_DOCK_ITEMS[0])).toBe(true);
      expect(isDockItemActive("/council/review", CLINICAL_DOCK_ITEMS[1])).toBe(true);
      expect(isDockItemActive("/scribe/session-1", CLINICAL_DOCK_ITEMS[3])).toBe(true);
      expect(isDockItemActive("/clinical/patients", CLINICAL_DOCK_ITEMS[4])).toBe(true);

      // Research disambiguation
      expect(isDockItemActive("/research", RESEARCH_DOCK_ITEMS[0])).toBe(true);
      expect(isDockItemActive("/research/source-hub", RESEARCH_DOCK_ITEMS[0])).toBe(false);
      expect(isDockItemActive("/research/source-hub", RESEARCH_DOCK_ITEMS[3])).toBe(true);
    });
  });
});
