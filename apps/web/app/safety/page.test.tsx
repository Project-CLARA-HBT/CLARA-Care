import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import SafetyManifestoPage, { metadata } from "./page";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

describe("SafetyManifestoPage (/safety — Clinical Safety & Verification Framework)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("exports rich metadata regarding clinical safety and FIDES verification", () => {
    expect(metadata.title).toContain("Tuyên ngôn an toàn lâm sàng");
    expect(metadata.description).toContain("FIDES");
    expect(metadata.description).toContain("Zero-CoT");
    expect(metadata.description).toContain("5 tầng phân cấp an toàn");
  });

  it("renders with PUBLIC_LEGAL shell mode and Safety Manifesto layout archetype", () => {
    const { container } = render(<SafetyManifestoPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Safety Manifesto");
  });

  it("renders heading and core safety badges", () => {
    render(<SafetyManifestoPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Tuyên ngôn An toàn Lâm sàng & Hàng rào Bảo vệ Đa tầng/i,
      }),
    ).toBeInTheDocument();

    expect(screen.getAllByText(/Xác thực FIDES/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Chuẩn Zero-CoT & Zero-PII/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Luật Khám bệnh 2023/i).length).toBeGreaterThan(0);
  });

  it("renders the 5 clinical safety tiers with explicit protection mechanics", () => {
    render(<SafetyManifestoPage />);

    // 5 Tiers
    expect(screen.getByText(/Tầng 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Phân loại & Chuyển hướng Cấp cứu Khẩn cấp/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Hàng rào Pháp lý & Ranh giới Lâm sàng/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Hệ thống Xác thực Dược lý FIDES/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Hội chẩn Đa tác tử & Neo giữ Y văn/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 5/i)).toBeInTheDocument();
    expect(screen.getByText(/Giám sát & Xác nhận Chuyên môn Bác sĩ/i)).toBeInTheDocument();
  });

  it("renders emergency fast-path 115 link and invariant guarantees", () => {
    render(<SafetyManifestoPage />);

    const emergencyLink = screen.getByRole("link", { name: /GỌI NGAY CẤP CỨU 115/i });
    expect(emergencyLink).toHaveAttribute("href", "tel:115");

    // Invariants
    expect(screen.getByText(/1\. Nguyên tắc Fail-Closed/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Chuẩn Zero-PII Telemetry/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Bảo mật Chuỗi Suy luận Zero-CoT/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Phân quyền RBAC Thẩm quyền Cứng/i)).toBeInTheDocument();
  });

  it("renders navigation back to home and links to sources and consent", () => {
    render(<SafetyManifestoPage />);

    expect(screen.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/");
    expect(screen.getAllByRole("link", { name: /Danh mục nguồn y văn/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Đồng thuận y tế/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Đăng nhập/i }).length).toBeGreaterThan(0);
  });
});
