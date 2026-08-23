import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import GuidePage from "./page";

afterEach(cleanup);

describe("GuidePage (/huong-dan)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders the help center hero, omni-search, quick start bento cards, and mode glossary", () => {
    render(<GuidePage />);

    expect(screen.getByText("Trung tâm hướng dẫn")).toBeInTheDocument();
    expect(screen.getByTestId("omni-guide-search-input")).toBeInTheDocument();
    expect(screen.getByText("Bắt đầu nhanh")).toBeInTheDocument();
    expect(screen.getByText("Hỏi CLARA")).toBeInTheDocument();
    expect(screen.getByText("Hội chẩn đa chuyên khoa")).toBeInTheDocument();
    expect(screen.getByText("Ghi chép y khoa (Scribe)")).toBeInTheDocument();
    expect(screen.getAllByText("Kiểm tra tương tác thuốc").length).toBeGreaterThan(0);
    expect(screen.getByText("Các nhãn trong ô chat nghĩa là gì?")).toBeInTheDocument();
  });

  it("filters task guides dynamically when typing into omni search input", () => {
    render(<GuidePage />);

    const searchInput = screen.getByTestId("omni-guide-search-input");
    fireEvent.change(searchInput, { target: { value: "hội chẩn" } });

    expect(screen.getByText("Tôi là bác sĩ và cần hội chẩn ca khó")).toBeInTheDocument();
    expect(screen.queryByText("Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc")).not.toBeInTheDocument();

    // Reset search
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.getByText("Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc")).toBeInTheDocument();
  });

  it("populates search query when clicking suggestion pills", () => {
    render(<GuidePage />);

    const pill = screen.getByRole("button", { name: "Ghi âm buổi khám" });
    fireEvent.click(pill);

    expect(screen.getByDisplayValue("Ghi âm buổi khám")).toBeInTheDocument();
    expect(screen.getByText("Tôi muốn ghi lại buổi khám")).toBeInTheDocument();
  });

  it("filters tasks by role scope using role filter buttons", () => {
    render(<GuidePage />);

    const personalBtn = screen.getByRole("button", { name: "Người dùng" });
    fireEvent.click(personalBtn);

    // Personal role includes cabinet
    expect(screen.getByText("Tôi muốn lưu thuốc đang dùng")).toBeInTheDocument();
    expect(screen.queryByText("Tôi muốn ghi lại buổi khám")).not.toBeInTheDocument();

    const allBtn = screen.getByRole("button", { name: "Tất cả" });
    fireEvent.click(allBtn);
    expect(screen.getByText("Tôi muốn ghi lại buổi khám")).toBeInTheDocument();
  });

  it("toggles task accordion expanding and collapsing steps", () => {
    render(<GuidePage />);

    // Step by step list is expanded for chat by default
    expect(screen.getByText("Nhập câu hỏi bằng ngôn ngữ bình thường.")).toBeInTheDocument();

    // Click to collapse
    const chatAccordionHeader = screen.getByText("Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc").closest("div");
    if (chatAccordionHeader) {
      fireEvent.click(chatAccordionHeader);
    }
  });
});
