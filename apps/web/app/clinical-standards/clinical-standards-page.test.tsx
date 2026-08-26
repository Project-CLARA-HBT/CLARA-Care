import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ClinicalStandardsRootPage from "./page";

const mockReplace = vi.fn();
const mockPush = vi.fn();
const mockRouter = {
  replace: mockReplace,
  push: mockPush,
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

describe("ClinicalStandardsRootPage (/clinical-standards)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders /clinical-standards root page with page shell and clinical standards component", () => {
    render(<ClinicalStandardsRootPage />);

    expect(screen.getByText("Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế")).toBeInTheDocument();
    expect(screen.getByText(/Đặc tả kiến trúc hệ thống hỗ trợ quyết định/i)).toBeInTheDocument();
    expect(screen.getByText(/Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA/i)).toBeInTheDocument();
  });
});
