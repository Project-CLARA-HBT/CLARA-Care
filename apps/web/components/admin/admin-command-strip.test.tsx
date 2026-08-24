import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminCommandStrip from "./admin-command-strip";
import AdminShell from "./admin-shell";
import {
  ADMIN_TOOLS,
  getAdminToolById,
  getAdminToolByHref,
  getAdminToolsByCategory,
  searchAdminTools,
} from "./admin-tools-registry";

describe("AdminToolsRegistry", () => {
  it("contains all 19 admin modules across 4 categories", () => {
    expect(ADMIN_TOOLS.length).toBe(19);

    const platformTools = getAdminToolsByCategory("platform");
    expect(platformTools.map((t) => t.id)).toEqual([
      "overview",
      "control-tower",
      "ecosystem",
      "system",
    ]);

    const knowledgeTools = getAdminToolsByCategory("knowledge");
    expect(knowledgeTools.map((t) => t.id)).toEqual([
      "knowledge-sources",
      "rag-ingestion",
      "source-hub",
    ]);

    const aiTools = getAdminToolsByCategory("ai_systems");
    expect(aiTools.map((t) => t.id)).toEqual([
      "answer-flow",
      "observability",
      "analytics",
      "rag-eval",
      "clinical-analytics",
      "experiments",
    ]);

    const govTools = getAdminToolsByCategory("governance");
    expect(govTools.map((t) => t.id)).toEqual([
      "dsar",
      "audit-log",
      "community-moderation",
      "security",
      "users",
      "feedback",
    ]);
  });

  it("finds tool by ID and Href correctly", () => {
    expect(getAdminToolById("overview")?.title).toBe("Tổng quan hệ thống");
    expect(getAdminToolByHref("/admin/dsar")?.code).toBe("GOV-01");
  });

  it("searches tools across title, description, code, and keywords", () => {
    expect(searchAdminTools("recall@k").map((t) => t.id)).toContain("rag-eval");
    expect(searchAdminTools("PubMed").map((t) => t.id)).toContain("source-hub");
    expect(searchAdminTools("A03").map((t) => t.id)).toContain("answer-flow");
  });
});

describe("AdminShell Integration", () => {
  it("renders AdminCommandStrip and wraps children cleanly", () => {
    render(
      <AdminShell
        activeTab="overview"
        title="Admin Overview Test"
        description="Test description"
      >
        <div data-testid="child-content">Child Panel Content</div>
      </AdminShell>,
    );

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.getByText("Child Panel Content")).toBeInTheDocument();
  });
});

describe("AdminCommandStrip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Primary Tab Navigation", () => {
    it("renders all 5 primary navigation tabs with appropriate labels and codes", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      const nav = screen.getByRole("navigation", { name: /Admin command strip/i });
      expect(nav).toBeInTheDocument();

      // Check all 5 primary tabs
      expect(within(nav).getByRole("link", { name: /^Tổng quan/i })).toHaveAttribute(
        "href",
        "/admin/overview",
      );
      expect(within(nav).getByRole("link", { name: /^Nguồn tri thức/i })).toHaveAttribute(
        "href",
        "/admin/knowledge-sources",
      );
      expect(within(nav).getByRole("link", { name: /^Luồng trả lời/i })).toHaveAttribute(
        "href",
        "/admin/answer-flow",
      );
      expect(within(nav).getByRole("link", { name: /^Giám sát/i })).toHaveAttribute(
        "href",
        "/admin/observability",
      );
      expect(within(nav).getByRole("link", { name: /^Phân tích/i })).toHaveAttribute(
        "href",
        "/admin/analytics",
      );

      // Verify codes are rendered
      expect(within(nav).getByText("A01")).toBeInTheDocument();
      expect(within(nav).getByText("A02")).toBeInTheDocument();
      expect(within(nav).getByText("A03")).toBeInTheDocument();
      expect(within(nav).getByText("A04")).toBeInTheDocument();
      expect(within(nav).getByText("A05")).toBeInTheDocument();
    });

    it("marks the active tab with aria-current='page'", () => {
      const { rerender } = render(<AdminCommandStrip activeTab="overview" />);
      const nav = screen.getByRole("navigation", { name: /Admin command strip/i });

      const overviewLink = within(nav).getByRole("link", { name: /^Tổng quan/i });
      expect(overviewLink).toHaveAttribute("aria-current", "page");

      const knowledgeLink = within(nav).getByRole("link", { name: /^Nguồn tri thức/i });
      expect(knowledgeLink).not.toHaveAttribute("aria-current");

      // Rerender with activeTab="knowledge-sources"
      rerender(<AdminCommandStrip activeTab="knowledge-sources" />);
      expect(overviewLink).not.toHaveAttribute("aria-current");
      expect(knowledgeLink).toHaveAttribute("aria-current", "page");

      // Rerender with activeTab="product-analytics"
      rerender(<AdminCommandStrip activeTab="product-analytics" />);
      expect(within(nav).getByRole("link", { name: /^Phân tích/i })).toHaveAttribute(
        "aria-current",
        "page",
      );
    });

    it("renders More dropdown trigger and App Launcher search button", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      expect(screen.getByRole("button", { name: /Thêm/i })).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Mở trình khởi chạy tất cả ứng dụng quản trị/i }),
      ).toBeInTheDocument();
    });

    it("displays secondary active module name when a non-primary tab is active", () => {
      render(<AdminCommandStrip activeTab="clinical-analytics" />);

      expect(
        screen.getByRole("button", { name: /Phân tích lâm sàng & An toàn/i }),
      ).toBeInTheDocument();
    });
  });

  describe("Modal Launcher Open and Close", () => {
    it("opens launcher modal when clicking the 'More' button", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      const moreButton = screen.getByRole("button", { name: /Thêm/i });
      fireEvent.click(moreButton);

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();
      expect(
        within(dialog).getByText("Trình khởi chạy Ứng dụng & Công cụ Quản trị"),
      ).toBeInTheDocument();
    });

    it("opens launcher modal when clicking the search button", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      const searchButton = screen.getByRole("button", {
        name: /Mở trình khởi chạy tất cả ứng dụng quản trị/i,
      });
      fireEvent.click(searchButton);

      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("closes modal when clicking the close (X) button", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();

      const closeButton = within(dialog).getByRole("button", {
        name: /Đóng trình khởi chạy ứng dụng/i,
      });
      fireEvent.click(closeButton);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("closes modal when pressing Escape key", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  describe("Category Filtering in Modal", () => {
    it("renders all 14 admin modules by default when opened", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");

      // Check module count footer
      expect(
        within(dialog).getByText(`Hiển thị ${ADMIN_TOOLS.length} / ${ADMIN_TOOLS.length} module quản trị`),
      ).toBeInTheDocument();

      // Check items across categories in dialog
      expect(within(dialog).getByText("Tổng quan hệ thống")).toBeInTheDocument();
      expect(within(dialog).getByText("Tháp Điều phối (Control Tower)")).toBeInTheDocument();
      expect(within(dialog).getByText("Nguồn tri thức")).toBeInTheDocument();
      expect(within(dialog).getByText("Hàng đợi DSAR & Quyền dữ liệu")).toBeInTheDocument();
      expect(within(dialog).getByText("Nhật ký kiểm toán quản trị")).toBeInTheDocument();
      expect(within(dialog).getByText("Kiểm duyệt cộng đồng")).toBeInTheDocument();
    });

    it("filters modules by category pill selection", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");

      // Click "Quản trị" category pill
      const govPill = within(dialog).getByRole("tab", { name: /Quản trị 6/i });
      fireEvent.click(govPill);

      // Governance tools should be visible
      expect(within(dialog).getByText("Hàng đợi DSAR & Quyền dữ liệu")).toBeInTheDocument();
      expect(within(dialog).getByText("Nhật ký kiểm toán quản trị")).toBeInTheDocument();
      expect(within(dialog).getByText("Kiểm duyệt cộng đồng")).toBeInTheDocument();
      expect(within(dialog).getByText("Bảo mật & Khóa API")).toBeInTheDocument();
      expect(within(dialog).getByText("Quản trị người dùng (User Administration)")).toBeInTheDocument();
      expect(within(dialog).getByText("Hàng đợi Xử lý Phản hồi Lâm sàng")).toBeInTheDocument();

      // Other category tools should not be visible
      expect(within(dialog).queryByText("Tháp Điều phối (Control Tower)")).not.toBeInTheDocument();
      expect(within(dialog).queryByText("Nạp dữ liệu RAG (Ingestion Plane)")).not.toBeInTheDocument();

      // Click "Tri thức" category pill
      const knowledgePill = within(dialog).getByRole("tab", { name: /Tri thức 3/i });
      fireEvent.click(knowledgePill);

      expect(within(dialog).getByText("Nguồn tri thức")).toBeInTheDocument();
      expect(within(dialog).getByText("Nạp dữ liệu RAG (Ingestion Plane)")).toBeInTheDocument();
      expect(within(dialog).getByText("Cổng nguồn Y văn (Source Hub)")).toBeInTheDocument();
      expect(within(dialog).queryByText("Hàng đợi DSAR & Quyền dữ liệu")).not.toBeInTheDocument();

      // Click "Tất cả" to reset
      const allPill = within(dialog).getByRole("tab", { name: /Tất cả/i });
      fireEvent.click(allPill);
      expect(within(dialog).getByText("Tổng quan hệ thống")).toBeInTheDocument();
      expect(within(dialog).getByText("Hàng đợi DSAR & Quyền dữ liệu")).toBeInTheDocument();
    });
  });

  describe("Keyword Search in Modal", () => {
    it("filters modules by keyword search query", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");

      const searchInput = within(dialog).getByRole("searchbox");
      fireEvent.change(searchInput, { target: { value: "dsar" } });

      expect(within(dialog).getByText("Hàng đợi DSAR & Quyền dữ liệu")).toBeInTheDocument();
      expect(within(dialog).queryByText("Tổng quan hệ thống")).not.toBeInTheDocument();
      expect(within(dialog).queryByText("Nguồn tri thức")).not.toBeInTheDocument();
    });

    it("finds modules by code (e.g. A04, PLT-02, KNW-02)", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");

      const searchInput = within(dialog).getByRole("searchbox");
      fireEvent.change(searchInput, { target: { value: "PLT-02" } });

      expect(within(dialog).getByText("Tháp Điều phối (Control Tower)")).toBeInTheDocument();
      expect(within(dialog).queryByText("Giám sát AI & Hệ thống")).not.toBeInTheDocument();
    });

    it("displays empty state when no modules match search", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");

      const searchInput = within(dialog).getByRole("searchbox");
      fireEvent.change(searchInput, { target: { value: "nonexistentmodule12345" } });

      expect(
        within(dialog).getByText("Không tìm thấy công cụ quản trị phù hợp"),
      ).toBeInTheDocument();

      // Reset button clears query
      const resetFilterButton = within(dialog).getByRole("button", { name: /Xóa bộ lọc tìm kiếm/i });
      fireEvent.click(resetFilterButton);

      expect(within(dialog).getByText("Tổng quan hệ thống")).toBeInTheDocument();
    });

    it("closes modal upon clicking any tool link", () => {
      render(<AdminCommandStrip activeTab="overview" />);

      fireEvent.click(screen.getByRole("button", { name: /Thêm/i }));
      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();

      const toolLink = within(dialog).getByRole("link", { name: /Hàng đợi DSAR & Quyền dữ liệu/i });
      fireEvent.click(toolLink);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
