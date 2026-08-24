import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as ShellIndex from "@/components/shell";
import * as AdminCommandStripModule from "./admin-command-strip";
import AdminCommandStripDefault, {
  ADMIN_COMMAND_STRIP_DESKTOP_HEIGHT_CLASS,
  ADMIN_COMMAND_STRIP_HEIGHT_RANGE,
  ADMIN_PRIMARY_TABS,
  AdminCommandStrip,
} from "./admin-command-strip";

describe("AdminCommandStrip (Spec v8 §4.5 & 5.4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("1. Exports & Dimensional Contract", () => {
    it("exports named and default AdminCommandStrip from module and barrel", () => {
      expect(AdminCommandStrip).toBeDefined();
      expect(AdminCommandStripDefault).toBeDefined();
      expect(AdminCommandStripModule.AdminCommandStrip).toBeDefined();
      expect(AdminCommandStripModule.default).toBeDefined();
      expect(ShellIndex.AdminCommandStrip).toBeDefined();
    });

    it("exports height constants matching 44–48px compact range", () => {
      expect(ADMIN_COMMAND_STRIP_HEIGHT_RANGE).toBe("44–48px");
      expect(ADMIN_COMMAND_STRIP_DESKTOP_HEIGHT_CLASS).toContain("h-[46px]");
      expect(ADMIN_COMMAND_STRIP_DESKTOP_HEIGHT_CLASS).toContain("min-h-[44px]");
      expect(ADMIN_COMMAND_STRIP_DESKTOP_HEIGHT_CLASS).toContain("max-h-[48px]");
    });

    it("has exactly 5 primary admin navigation tabs configured", () => {
      expect(ADMIN_PRIMARY_TABS).toHaveLength(5);
      expect(ADMIN_PRIMARY_TABS.map((t) => t.key)).toEqual([
        "overview",
        "knowledge-sources",
        "answer-flow",
        "observability",
        "product-analytics",
      ]);
    });
  });

  describe("2. Compact Top Navigation (44–48px)", () => {
    it("renders navigation container with compact 44–48px height", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      const nav = screen.getByTestId("admin-command-strip");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("role", "navigation");
      expect(nav).toHaveAttribute("aria-label", "Admin command strip");

      expect(nav.className).toContain("h-[46px]");
      expect(nav.className).toContain("min-h-[44px]");
      expect(nav.className).toContain("max-h-[48px]");
    });

    it("renders all primary navigation tabs with labels, codes, and correct hrefs", () => {
      render(<AdminCommandStrip activeTab="overview" />);
      const nav = screen.getByTestId("admin-command-strip");

      // 1. Tổng quan (/admin/overview)
      const overviewLink = within(nav).getByTestId("admin-command-tab-overview");
      expect(overviewLink).toHaveAttribute("href", "/admin/overview");
      expect(overviewLink).toHaveTextContent("Tổng quan");
      expect(overviewLink).toHaveTextContent("A01");

      // 2. Nguồn tri thức (/admin/knowledge-sources)
      const knowledgeLink = within(nav).getByTestId("admin-command-tab-knowledge-sources");
      expect(knowledgeLink).toHaveAttribute("href", "/admin/knowledge-sources");
      expect(knowledgeLink).toHaveTextContent("Nguồn tri thức");
      expect(knowledgeLink).toHaveTextContent("A02");

      // 3. Luồng suy luận (/admin/answer-flow)
      const flowLink = within(nav).getByTestId("admin-command-tab-answer-flow");
      expect(flowLink).toHaveAttribute("href", "/admin/answer-flow");
      expect(flowLink).toHaveTextContent(/Luồng (suy luận|trả lời)/);
      expect(flowLink).toHaveTextContent("A03");

      // 4. Giám sát (/admin/observability)
      const observabilityLink = within(nav).getByTestId("admin-command-tab-observability");
      expect(observabilityLink).toHaveAttribute("href", "/admin/observability");
      expect(observabilityLink).toHaveTextContent("Giám sát");
      expect(observabilityLink).toHaveTextContent("A04");

      // 5. Phân tích (/admin/analytics)
      const analyticsLink = within(nav).getByTestId("admin-command-tab-product-analytics");
      expect(analyticsLink).toHaveAttribute("href", "/admin/analytics");
      expect(analyticsLink).toHaveTextContent("Phân tích");
      expect(analyticsLink).toHaveTextContent("A05");
    });
  });

  describe("3. Active Tab Highlighting", () => {
    it("marks the active tab with aria-current='page'", () => {
      const { rerender } = render(<AdminCommandStrip activeTab="overview" />);

      const overviewLink = screen.getByTestId("admin-command-tab-overview");
      expect(overviewLink).toHaveAttribute("aria-current", "page");

      const knowledgeLink = screen.getByTestId("admin-command-tab-knowledge-sources");
      expect(knowledgeLink).not.toHaveAttribute("aria-current");

      // Rerender with activeTab="knowledge-sources"
      rerender(<AdminCommandStrip activeTab="knowledge-sources" />);
      expect(overviewLink).not.toHaveAttribute("aria-current");
      expect(knowledgeLink).toHaveAttribute("aria-current", "page");

      // Rerender with activeTab="answer-flow"
      rerender(<AdminCommandStrip activeTab="answer-flow" />);
      const flowLink = screen.getByTestId("admin-command-tab-answer-flow");
      expect(flowLink).toHaveAttribute("aria-current", "page");
    });

    it("displays secondary active tool title when a non-primary tab is active", () => {
      render(<AdminCommandStrip activeTab="clinical-analytics" />);

      const moreButton = screen.getByTestId("admin-command-more-button");
      expect(moreButton).toHaveTextContent("Phân tích lâm sàng & An toàn");
    });
  });

  describe("4. All Tools & App Launcher Modal Triggers", () => {
    it("opens AdminAppLauncherModal when clicking 'Thêm' (All Tools)", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      const moreButton = screen.getByTestId("admin-command-more-button");
      fireEvent.click(moreButton);

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();
      expect(
        within(dialog).getByText("Trình khởi chạy Ứng dụng & Công cụ Quản trị"),
      ).toBeInTheDocument();
    });

    it("opens AdminAppLauncherModal when clicking search button ('Tìm công cụ...')", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      const searchButton = screen.getByTestId("admin-command-search-trigger");
      fireEvent.click(searchButton);

      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("triggers launcher on Cmd+K or Ctrl+K shortcut", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent.keyDown(window, { key: "k", metaKey: true });
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("invokes onOpenLauncher callback if provided", () => {
      const handleOpenLauncher = vi.fn();
      render(<AdminCommandStrip onOpenLauncher={handleOpenLauncher} />);

      const moreButton = screen.getByTestId("admin-command-more-button");
      fireEvent.click(moreButton);

      expect(handleOpenLauncher).toHaveBeenCalledTimes(1);
    });

    it("closes launcher modal when close button is clicked", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByTestId("admin-command-more-button"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      const closeButton = within(screen.getByRole("dialog")).getByRole("button", {
        name: /Đóng/i,
      });
      fireEvent.click(closeButton);

      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });
});
