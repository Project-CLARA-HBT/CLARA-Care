import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import RootPrivacyPage, { metadata } from "./page";

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

describe("RootPrivacyPage (/privacy — Privacy & Personal Data Protection Policy Alias)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("exports metadata with canonical link to /legal/privacy", () => {
    expect(metadata.title).toContain("Chính sách quyền riêng tư");
    expect(metadata.description).toContain("Nghị định 13/2023/NĐ-CP");
    expect(metadata.alternates?.canonical).toBe("/legal/privacy");
  });

  it("renders Privacy Policy Reader with constrained editorial body and SectionIndex", () => {
    const { container } = render(<RootPrivacyPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders Vietnamese statutory citations and all 11 DSAR rights", () => {
    render(<RootPrivacyPage />);

    // Vietnamese citations
    expect(screen.getAllByText(/Luật Khám bệnh 2023 · NĐ 13\/2023 · Luật AI 134\/2025/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Điều 2 và Điều 9 Nghị định 13\/2023\/NĐ-CP/i)).toBeInTheDocument();

    // 11 DSAR rights
    expect(screen.getByText(/1\. Quyền được biết/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Quyền đồng ý/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Quyền truy cập & xem dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Quyền rút lại sự đồng ý/i)).toBeInTheDocument();
    expect(screen.getByText(/5\. Quyền xóa dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/6\. Quyền hạn chế xử lý/i)).toBeInTheDocument();
    expect(screen.getByText(/7\. Quyền cung cấp dữ liệu \(Portability\)/i)).toBeInTheDocument();
    expect(screen.getByText(/8\. Quyền phản đối xử lý dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/9\. Quyền khiếu nại, tố cáo & khởi kiện/i)).toBeInTheDocument();
    expect(screen.getByText(/10\. Quyền yêu cầu bồi thường thiệt hại/i)).toBeInTheDocument();
    expect(screen.getByText(/11\. Quyền tự bảo vệ/i)).toBeInTheDocument();
  });
});
