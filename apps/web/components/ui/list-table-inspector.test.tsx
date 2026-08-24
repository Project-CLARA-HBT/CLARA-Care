import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ListRow } from "@/components/ui/list-row";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { Sheet, SheetBody, SheetFooter, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Inspector, InspectorField, InspectorSection } from "@/components/ui/inspector";
import { LocalRail, type LocalRailItem } from "@/components/ui/local-rail";
import { SectionIndex, type SectionIndexItem } from "@/components/ui/section-index";

afterEach(cleanup);

/* ========================================================================= */
/* 1. ListRow Tests                                                          */
/* ========================================================================= */

describe("ListRow Component", () => {
  it("renders leading, title, subtitle, badges, meta, and trailing content", () => {
    render(
      <ListRow
        leading={<span data-testid="leading-icon">Icon</span>}
        title="Paracetamol 500mg"
        subtitle="Uống 1 viên sau ăn"
        badges={<span data-testid="badge">Hoạt động</span>}
        meta="Hôm nay"
        trailing={<button type="button">Chi tiết</button>}
      />,
    );

    expect(screen.getByText("Paracetamol 500mg")).toBeInTheDocument();
    expect(screen.getByText("Uống 1 viên sau ăn")).toBeInTheDocument();
    expect(screen.getByTestId("leading-icon")).toBeInTheDocument();
    expect(screen.getByTestId("badge")).toBeInTheDocument();
    expect(screen.getByText("Hôm nay")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chi tiết" })).toBeInTheDocument();
  });

  it("applies density presets (comfortable, compact, dense)", () => {
    const { rerender } = render(
      <ListRow title="Test row" density="comfortable" id="test-row" />,
    );
    let el = document.getElementById("test-row");
    expect(el?.className).toContain("min-h-[56px]");

    rerender(<ListRow title="Test row" density="compact" id="test-row" />);
    el = document.getElementById("test-row");
    expect(el?.className).toContain("min-h-[44px]");

    rerender(<ListRow title="Test row" density="dense" id="test-row" />);
    el = document.getElementById("test-row");
    expect(el?.className).toContain("min-h-[36px]");
  });

  it("renders as Next.js Link when href is provided", () => {
    render(
      <ListRow
        href="/medicines/123"
        title="Thuốc huyết áp"
        ariaLabel="Xem thuốc huyết áp"
      />,
    );

    const link = screen.getByRole("link", { name: "Xem thuốc huyết áp" });
    expect(link).toHaveAttribute("href", "/medicines/123");
  });

  it("handles onClick and keyboard Enter when clickable", () => {
    const handleClick = vi.fn();
    render(
      <ListRow
        title="Bệnh án điện tử"
        onClick={handleClick}
        id="clickable-row"
      />,
    );

    const row = screen.getByRole("button", { name: /Bệnh án điện tử/i });
    fireEvent.click(row);
    expect(handleClick).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(row, { key: "Enter" });
    expect(handleClick).toHaveBeenCalledTimes(2);
  });

  it("applies selected state styling and attributes", () => {
    render(
      <ListRow
        title="Hồ sơ xét nghiệm"
        selected={true}
        id="selected-row"
      />,
    );

    const row = document.getElementById("selected-row");
    expect(row).toHaveAttribute("aria-selected", "true");
    expect(row?.className).toContain("bg-[var(--surface-brand-soft)]");
  });

  it("disables interaction when disabled is true", () => {
    const handleClick = vi.fn();
    render(
      <ListRow
        title="Hồ sơ bị khóa"
        disabled={true}
        onClick={handleClick}
      />,
    );

    const button = screen.getByRole("button", { name: /Hồ sơ bị khóa/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });
});

/* ========================================================================= */
/* 2. DataTable Tests                                                        */
/* ========================================================================= */

interface TestItem {
  id: string;
  name: string;
  category: string;
  dose: string;
  status?: string;
}

const TEST_COLUMNS: DataTableColumn<TestItem>[] = [
  { id: "name", header: "Tên thuốc", accessorKey: "name", sortable: true },
  { id: "category", header: "Phân loại", accessorKey: "category", align: "center" },
  { id: "dose", header: "Liều dùng", accessorFn: (row) => `Liều: ${row.dose}`, align: "right" },
];

const TEST_DATA: TestItem[] = [
  { id: "1", name: "Amoxicillin", category: "Kháng sinh", dose: "500mg", status: "active" },
  { id: "2", name: "Paracetamol", category: "Giảm đau", dose: "650mg", status: "active" },
  { id: "3", name: "Ibuprofen", category: "Kháng viêm", dose: "400mg", status: "stopped" },
];

describe("DataTable Component", () => {
  it("renders table data with headers, sticky header class, and rows", () => {
    const { container } = render(
      <DataTable
        data={TEST_DATA}
        columns={TEST_COLUMNS}
        ariaLabel="Danh sách thuốc"
        stickyHeader={true}
      />,
    );

    expect(screen.getByRole("table", { name: "Danh sách thuốc" })).toBeInTheDocument();
    expect(screen.getByText("Tên thuốc")).toBeInTheDocument();
    expect(screen.getByText("Amoxicillin")).toBeInTheDocument();
    expect(screen.getByText("Liều: 500mg")).toBeInTheDocument();
    expect(container.querySelector("thead")?.className).toContain("sticky top-0");
  });

  it("handles column sorting and triggers onSort callback with toggled direction", () => {
    const handleSort = vi.fn();
    render(
      <DataTable
        data={TEST_DATA}
        columns={TEST_COLUMNS}
        sortColumn="name"
        sortDirection="asc"
        onSort={handleSort}
      />,
    );

    const sortButton = screen.getByRole("button", { name: /Tên thuốc/i });
    expect(sortButton.closest("th")).toHaveAttribute("aria-sort", "ascending");

    fireEvent.click(sortButton);
    expect(handleSort).toHaveBeenCalledWith("name", "desc");
  });

  it("supports density variants (comfortable, compact, dense)", () => {
    const { container, rerender } = render(
      <DataTable data={TEST_DATA} columns={TEST_COLUMNS} density="comfortable" />,
    );
    expect(container.querySelector("th")?.className).toContain("py-3.5 px-4");

    rerender(<DataTable data={TEST_DATA} columns={TEST_COLUMNS} density="compact" />);
    expect(container.querySelector("th")?.className).toContain("py-2.5 px-3.5");

    rerender(<DataTable data={TEST_DATA} columns={TEST_COLUMNS} density="dense" />);
    expect(container.querySelector("th")?.className).toContain("py-1.5 px-2.5");
  });

  it("handles row selection and select-all toggle", () => {
    const handleSelectionChange = vi.fn();
    render(
      <DataTable
        data={TEST_DATA}
        columns={TEST_COLUMNS}
        selectable={true}
        selectedIds={["1"]}
        onSelectionChange={handleSelectionChange}
      />,
    );

    // Header checkbox (select all)
    const selectAllCheckbox = screen.getByLabelText("Chọn tất cả các hàng");
    fireEvent.click(selectAllCheckbox);
    expect(handleSelectionChange).toHaveBeenCalledWith(["1", "2", "3"]);

    // Individual row checkbox
    const rowCheckbox2 = screen.getByLabelText("Chọn hàng 2");
    fireEvent.click(rowCheckbox2);
    expect(handleSelectionChange).toHaveBeenCalledWith(["1", "2"]);
  });

  it("handles pagination controls, page size change, and page switching", () => {
    const handlePageChange = vi.fn();
    const handlePageSizeChange = vi.fn();

    render(
      <DataTable
        data={TEST_DATA}
        columns={TEST_COLUMNS}
        pagination={{
          page: 1,
          pageSize: 2,
          totalCount: 3,
          onPageChange: handlePageChange,
          onPageSizeChange: handlePageSizeChange,
          pageSizeOptions: [2, 5, 10],
        }}
      />,
    );

    expect(screen.getByText("Hiển thị 1 - 2 trên 3 mục")).toBeInTheDocument();
    const prevButton = screen.getByRole("button", { name: "Trang trước" });
    const nextButton = screen.getByRole("button", { name: "Trang sau" });

    expect(prevButton).toBeDisabled();
    expect(nextButton).not.toBeDisabled();

    fireEvent.click(nextButton);
    expect(handlePageChange).toHaveBeenCalledWith(2);

    const pageSizeSelect = screen.getByLabelText("Số dòng mỗi trang");
    fireEvent.change(pageSizeSelect, { target: { value: "5" } });
    expect(handlePageSizeChange).toHaveBeenCalledWith(5);
  });

  it("renders custom emptyState when provided", () => {
    render(
      <DataTable
        data={[]}
        columns={TEST_COLUMNS}
        emptyState={<div data-testid="custom-empty">Trống rỗng</div>}
      />,
    );

    expect(screen.getByTestId("custom-empty")).toBeInTheDocument();
  });

  it("renders loading skeleton rows when loading is true and data is empty", () => {
    render(
      <DataTable
        data={[]}
        columns={TEST_COLUMNS}
        loading={true}
        loadingRowCount={3}
      />,
    );

    const table = screen.getByRole("table");
    expect(table).toHaveAttribute("aria-busy", "true");
  });

  it("triggers onRowClick when row is clicked and applies custom rowClassName", () => {
    const handleRowClick = vi.fn();
    render(
      <DataTable
        data={TEST_DATA}
        columns={TEST_COLUMNS}
        onRowClick={handleRowClick}
        rowClassName={(row) => (row.status === "stopped" ? "row-stopped" : "")}
      />,
    );

    const row = screen.getByText("Amoxicillin").closest("tr");
    if (row) fireEvent.click(row);
    expect(handleRowClick).toHaveBeenCalledWith(TEST_DATA[0], 0);

    const stoppedRow = screen.getByText("Ibuprofen").closest("tr");
    expect(stoppedRow?.className).toContain("row-stopped");
  });
});

/* ========================================================================= */
/* 3. Sheet & Inspector Tests                                                */
/* ========================================================================= */

describe("Sheet Component", () => {
  it("renders slide-over drawer with header, body, footer, and WAI-ARIA dialog attributes", () => {
    const handleClose = vi.fn();
    render(
      <Sheet
        open={true}
        onClose={handleClose}
        title="Chi tiết đơn thuốc"
        description="Thông tin chi tiết về liều lượng và cảnh báo tương tác."
        footer={<button type="button">Xác nhận</button>}
      >
        <p>Nội dung đơn thuốc</p>
      </Sheet>,
    );

    const dialog = screen.getByRole("dialog", { name: "Chi tiết đơn thuốc" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Nội dung đơn thuốc")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận" })).toBeInTheDocument();
  });

  it("closes on Escape key press", () => {
    const handleClose = vi.fn();
    render(
      <Sheet open={true} onClose={handleClose} title="Cửa sổ trượt">
        <div>Nội dung</div>
      </Sheet>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape when dismissible is false", () => {
    const handleClose = vi.fn();
    render(
      <Sheet open={true} onClose={handleClose} title="Cửa sổ trượt" dismissible={false}>
        <div>Nội dung</div>
      </Sheet>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).not.toHaveBeenCalled();
  });

  it("closes on close button click", () => {
    const handleClose = vi.fn();
    render(
      <Sheet
        open={true}
        onClose={handleClose}
        title="Cửa sổ trượt"
        closeLabel="Đóng bảng điều khiển"
      >
        <div>Nội dung</div>
      </Sheet>,
    );

    const closeBtn = screen.getByRole("button", { name: "Đóng bảng điều khiển" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("supports alertdialog semantics", () => {
    render(
      <Sheet open={true} role="alertdialog" onClose={vi.fn()} title="Xóa hồ sơ khám">
        <button type="button">Xác nhận xóa</button>
      </Sheet>,
    );

    expect(screen.getByRole("alertdialog", { name: "Xóa hồ sơ khám" })).toBeInTheDocument();
  });

  it("supports composable subcomponents (SheetHeader, SheetBody, SheetFooter)", () => {
    render(
      <Sheet open={true} onClose={vi.fn()} showCloseButton={false}>
        <SheetHeader>
          <SheetTitle>Tiêu đề tùy chỉnh</SheetTitle>
          <SheetDescription>Mô tả tùy chỉnh</SheetDescription>
        </SheetHeader>
        <SheetBody>
          <p>Thân trang tùy chỉnh</p>
        </SheetBody>
        <SheetFooter>
          <button type="button">Lưu</button>
        </SheetFooter>
      </Sheet>,
    );

    expect(screen.getByRole("dialog", { name: "Tiêu đề tùy chỉnh" })).toBeInTheDocument();
    expect(screen.getByText("Thân trang tùy chỉnh")).toBeInTheDocument();
    expect(screen.getByText("Lưu")).toBeInTheDocument();
  });

  it("traps focus inside the sheet on Tab navigation", () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Bảng bẫy tiêu điểm">
        <button type="button">Nút 1</button>
        <button type="button">Nút 2</button>
      </Sheet>,
    );

    const closeBtn = screen.getByRole("button", { name: "Đóng" });
    const btn1 = screen.getByRole("button", { name: "Nút 1" });
    const btn2 = screen.getByRole("button", { name: "Nút 2" });

    // Focus first element, Shift+Tab should wrap to last element
    closeBtn.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(btn2);

    // Focus last element, Tab should wrap to first element
    btn2.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: false });
    expect(document.activeElement).toBe(closeBtn);
  });
});

describe("Inspector Component", () => {
  it("renders slide-over inspector with entity details, sections, and fields", () => {
    render(
      <Inspector
        open={true}
        onClose={vi.fn()}
        title="Bệnh nhân: Nguyễn Văn A"
        subtitle="Mã BN: #12345"
        badge={<span>BHYT</span>}
        footer={<button type="button">Cập nhật hồ sơ</button>}
      >
        <InspectorSection title="Chỉ số sinh tồn">
          <InspectorField label="Huyết áp" value="120/80 mmHg" copyable={true} />
          <InspectorField label="Nhịp tim" value="72 bpm" />
        </InspectorSection>
      </Inspector>,
    );

    expect(screen.getByRole("dialog", { name: /Bệnh nhân: Nguyễn Văn A/i })).toBeInTheDocument();
    expect(screen.getByText("Mã BN: #12345")).toBeInTheDocument();
    expect(screen.getByText("BHYT")).toBeInTheDocument();
    expect(screen.getByText("Chỉ số sinh tồn")).toBeInTheDocument();
    expect(screen.getByText("Huyết áp")).toBeInTheDocument();
    expect(screen.getByText("120/80 mmHg")).toBeInTheDocument();

    const copyBtn = screen.getByRole("button", { name: "Sao chép giá trị" });
    expect(copyBtn).toBeInTheDocument();
  });

  it("renders inline mode panel with region landmark", () => {
    render(
      <Inspector
        mode="inline"
        title="Bảng kiểm tra chứng cứ"
        subtitle="FIDES Verification Evidence"
      >
        <div>Chứng cứ đối chiếu từ Dược thư Quốc gia</div>
      </Inspector>,
    );

    expect(screen.getByRole("region", { name: "Bảng kiểm tra chứng cứ" })).toBeInTheDocument();
    expect(screen.getByText("Chứng cứ đối chiếu từ Dược thư Quốc gia")).toBeInTheDocument();
  });

  it("supports collapsible InspectorSection toggle", () => {
    render(
      <InspectorSection title="Dị ứng đã ghi nhận" collapsible={true} defaultExpanded={true}>
        <div>Dị ứng Penicillin (Nặng)</div>
      </InspectorSection>,
    );

    expect(screen.getByText("Dị ứng Penicillin (Nặng)")).toBeInTheDocument();

    const toggleHeader = screen.getByRole("button", { name: /Dị ứng đã ghi nhận/i });
    fireEvent.click(toggleHeader);
    expect(screen.queryByText("Dị ứng Penicillin (Nặng)")).not.toBeInTheDocument();

    fireEvent.click(toggleHeader);
    expect(screen.getByText("Dị ứng Penicillin (Nặng)")).toBeInTheDocument();
  });
});

/* ========================================================================= */
/* 4. LocalRail Tests                                                        */
/* ========================================================================= */

const RAIL_ITEMS: LocalRailItem[] = [
  { key: "overview", label: "Tổng quan", icon: "clinical-notes" },
  { key: "records", label: "Hồ sơ bệnh án", icon: "folder", badge: 3 },
  { key: "medicines", label: "Đơn thuốc", icon: "medication" },
  { key: "disabled-item", label: "Không khả dụng", icon: "warning", disabled: true },
];

describe("LocalRail Component", () => {
  it("renders local rail items and active state", () => {
    const handleChange = vi.fn();
    render(
      <LocalRail
        items={RAIL_ITEMS}
        activeKey="overview"
        onChange={handleChange}
        collapsed={false}
        ariaLabel="Thanh điều hướng hồ sơ"
      />,
    );

    expect(screen.getByRole("navigation", { name: "Thanh điều hướng hồ sơ" })).toBeInTheDocument();
    const overviewBtn = screen.getByRole("button", { name: "Tổng quan" });
    expect(overviewBtn).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("handles item selection and ignores disabled items", () => {
    const handleChange = vi.fn();
    render(
      <LocalRail
        items={RAIL_ITEMS}
        activeKey="overview"
        onChange={handleChange}
      />,
    );

    const recordsBtn = screen.getByRole("button", { name: "Hồ sơ bệnh án" });
    fireEvent.click(recordsBtn);
    expect(handleChange).toHaveBeenCalledWith("records");

    const disabledBtn = screen.getByRole("button", { name: "Không khả dụng" });
    expect(disabledBtn).toBeDisabled();
    fireEvent.click(disabledBtn);
    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  it("supports roving keyboard navigation (ArrowDown, ArrowUp, Home, End)", () => {
    const handleChange = vi.fn();
    render(
      <LocalRail
        items={RAIL_ITEMS}
        activeKey="overview"
        onChange={handleChange}
      />,
    );

    const overviewBtn = screen.getByRole("button", { name: "Tổng quan" });
    overviewBtn.focus();

    fireEvent.keyDown(overviewBtn, { key: "ArrowDown" });
    expect(handleChange).toHaveBeenCalledWith("records");

    fireEvent.keyDown(overviewBtn, { key: "End" });
    expect(handleChange).toHaveBeenCalledWith("medicines");

    fireEvent.keyDown(overviewBtn, { key: "Home" });
    expect(handleChange).toHaveBeenCalledWith("overview");
  });

  it("supports toggle collapse button", () => {
    const handleToggle = vi.fn();
    render(
      <LocalRail
        items={RAIL_ITEMS}
        collapsed={true}
        onToggleCollapse={handleToggle}
      />,
    );

    const toggleBtn = screen.getByRole("button", { name: "Mở rộng thanh điều hướng" });
    fireEvent.click(toggleBtn);
    expect(handleToggle).toHaveBeenCalledTimes(1);
  });
});

/* ========================================================================= */
/* 5. SectionIndex Tests                                                     */
/* ========================================================================= */

const SECTION_ITEMS: SectionIndexItem[] = [
  { id: "sec-1", title: "Thông tin hành chính", status: "completed" },
  { id: "sec-2", title: "Tiền sử bệnh lý", status: "current" },
  { id: "sec-3", title: "Khám lâm sàng", status: "pending" },
  { id: "sec-4", title: "Cận lâm sàng & Chẩn đoán hình ảnh", level: 2, status: "error" },
  { id: "sec-5", title: "Đánh giá bổ sung", level: 3, status: "warning", count: 2 },
];

describe("SectionIndex Component", () => {
  it("renders table of contents with progress count, progress bar, and indicators", () => {
    render(
      <SectionIndex
        items={SECTION_ITEMS}
        activeId="sec-2"
        title="Danh mục phiếu khám"
      />,
    );

    expect(screen.getByText("Danh mục phiếu khám")).toBeInTheDocument();
    expect(screen.getByText("1/5")).toBeInTheDocument();
    expect(screen.getByText("Thông tin hành chính")).toBeInTheDocument();
    expect(screen.getByText("Tiền sử bệnh lý")).toBeInTheDocument();
    expect(screen.getByText("Đánh giá bổ sung")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();

    const progress = screen.getByRole("progressbar", { name: "Tiến độ hoàn thành mục" });
    expect(progress).toHaveAttribute("aria-valuenow", "20");

    const currentSectionBtn = screen.getByRole("button", { name: /Tiền sử bệnh lý/i });
    expect(currentSectionBtn).toHaveAttribute("aria-current", "location");
  });

  it("handles jump navigation on click", () => {
    const handleSelect = vi.fn();
    render(
      <SectionIndex
        items={SECTION_ITEMS}
        activeId="sec-1"
        onSectionSelect={handleSelect}
      />,
    );

    const clinicalSectionBtn = screen.getByRole("button", { name: /Khám lâm sàng/i });
    fireEvent.click(clinicalSectionBtn);
    expect(handleSelect).toHaveBeenCalledWith("sec-3");
  });
});
