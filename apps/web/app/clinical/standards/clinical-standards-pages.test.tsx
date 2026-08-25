import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ClinicalStandardsPage from "./page";
import ClinicalStandardsRootPage from "@/app/clinical-standards/page";

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

describe("Clinical Standards Route Pages (/clinical/standards and /clinical-standards)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders /clinical/standards subroute page", () => {
    render(<ClinicalStandardsPage />);

    expect(screen.getByText("Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế")).toBeInTheDocument();
    expect(screen.getByText(/Đặc tả kiến trúc hệ thống hỗ trợ quyết định/i)).toBeInTheDocument();
    expect(screen.getByText(/Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA/i)).toBeInTheDocument();
  });

  it("renders /clinical-standards canonical root page", () => {
    render(<ClinicalStandardsRootPage />);

    expect(screen.getByText("Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế")).toBeInTheDocument();
    expect(screen.getByText(/Đặc tả kiến trúc hệ thống hỗ trợ quyết định/i)).toBeInTheDocument();
    expect(screen.getByText(/Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA/i)).toBeInTheDocument();
  });
});
