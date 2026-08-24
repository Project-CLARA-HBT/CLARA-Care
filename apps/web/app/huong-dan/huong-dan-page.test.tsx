import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import GuidePage from "./page";

afterEach(cleanup);

describe("GuidePage (/huong-dan - Spec v5 Section 6.73 Help Library Archetype)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders the Help Library with omni-search hero, role selectors, topic list, selected guide reader, and mode glossary", () => {
    render(<GuidePage />);

    // Header & Omni-search
    expect(screen.getByText("Trung tâm hướng dẫn")).toBeInTheDocument();
    expect(screen.getByTestId("omni-guide-search-input")).toBeInTheDocument();

    // Role category selectors
    expect(screen.getByRole("button", { name: "Tất cả" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Người dùng" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lâm sàng" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nghiên cứu" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quản trị" })).toBeInTheDocument();

    // Default Selected Guide Reader (Chat / Hỏi CLARA)
    expect(screen.getByRole("heading", { name: /Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc/i })).toBeInTheDocument();
    expect(screen.getByText(/Quy trình thực hiện từng bước/i)).toBeInTheDocument();
    expect(screen.getByText("Mở hỏi CLARA")).toBeInTheDocument();

    // Mode glossary
    expect(screen.getByText("Các nhãn trong ô chat nghĩa là gì?")).toBeInTheDocument();
    expect(screen.getByText("Nhanh")).toBeInTheDocument();
    expect(screen.getByText("Tư duy")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
  });

  it("filters task guides dynamically when typing into omni search input", () => {
    render(<GuidePage />);

    const searchInput = screen.getByTestId("omni-guide-search-input");
    fireEvent.change(searchInput, { target: { value: "hội chẩn" } });

    // Council AI task appears in both heading and list
    expect(screen.getAllByText("Tôi là bác sĩ và cần hội chẩn ca khó").length).toBeGreaterThan(0);
    expect(screen.queryByText("Tôi muốn lưu thuốc đang dùng")).not.toBeInTheDocument();

    // Reset search
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.getAllByText("Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc").length).toBeGreaterThan(0);
  });

  it("populates search query when clicking suggestion pills", () => {
    render(<GuidePage />);

    const pill = screen.getByRole("button", { name: "Ghi âm buổi khám" });
    fireEvent.click(pill);

    expect(screen.getByDisplayValue("Ghi âm buổi khám")).toBeInTheDocument();
    expect(screen.getAllByText("Tôi muốn ghi lại buổi khám").length).toBeGreaterThan(0);
  });

  it("filters tasks by role scope (Personal, Clinical, Research, Admin)", () => {
    render(<GuidePage />);

    // 1. Personal / Consumer role filter
    const personalBtn = screen.getByRole("button", { name: "Người dùng" });
    fireEvent.click(personalBtn);

    expect(screen.getAllByText("Tôi muốn lưu thuốc đang dùng").length).toBeGreaterThan(0);
    expect(screen.queryByText("Tôi muốn ghi lại buổi khám")).not.toBeInTheDocument();
    expect(screen.queryByText("Truy xuất y văn & Tổng hợp bằng chứng lâm sàng")).not.toBeInTheDocument();

    // 2. Clinical role filter
    const clinicalBtn = screen.getByRole("button", { name: "Lâm sàng" });
    fireEvent.click(clinicalBtn);

    expect(screen.getAllByText("Tôi là bác sĩ và cần hội chẩn ca khó").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tôi muốn ghi lại buổi khám").length).toBeGreaterThan(0);
    expect(screen.queryByText("Tôi muốn lưu thuốc đang dùng")).not.toBeInTheDocument();

    // 3. Research role filter
    const researchBtn = screen.getByRole("button", { name: "Nghiên cứu" });
    fireEvent.click(researchBtn);

    expect(screen.getAllByText(/Truy xuất y văn/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Tôi muốn lưu thuốc đang dùng")).not.toBeInTheDocument();

    // 4. Admin role filter
    const adminBtn = screen.getByRole("button", { name: "Quản trị" });
    fireEvent.click(adminBtn);

    expect(screen.getAllByText(/CÔNG CỤ QUẢN TRỊ: GIÁM SÁT HỆ THỐNG/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Tôi muốn lưu thuốc đang dùng")).not.toBeInTheDocument();

    // 5. Reset to All
    const allBtn = screen.getByRole("button", { name: "Tất cả" });
    fireEvent.click(allBtn);
    expect(screen.getAllByText("Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc").length).toBeGreaterThan(0);
  });

  it("selects a different guide from the topic list and updates the Guide Reader with illustrations", () => {
    render(<GuidePage />);

    // Click on Medicine Cabinet task in the list
    const cabinetButtons = screen.getAllByText("Tôi muốn lưu thuốc đang dùng");
    const listButton = cabinetButtons[0].closest("button");
    if (listButton) {
      fireEvent.click(listButton);
    }

    // Selected guide heading should update
    expect(screen.getByRole("heading", { name: /Tôi muốn lưu thuốc đang dùng/i })).toBeInTheDocument();
    expect(screen.getByText("CÔNG CỤ KHUYÊN DÙNG: TỦ THUỐC")).toBeInTheDocument();
    expect(screen.getByText("Mở tủ thuốc")).toBeInTheDocument();

    // Illustrated mock snippet should be visible
    expect(screen.getByText(/Thêm thuốc hoặc quét ảnh đơn thuốc/i)).toBeInTheDocument();
    expect(screen.getByText("Báo cáo an toàn tủ thuốc")).toBeInTheDocument();
  });
});
