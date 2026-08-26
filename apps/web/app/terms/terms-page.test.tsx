import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import RootTermsPage, { metadata } from "./page";

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

describe("RootTermsPage (/terms — Terms of Service Policy Alias)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("exports metadata with canonical link to /legal/terms", () => {
    expect(metadata.title).toContain("Điều khoản sử dụng");
    expect(metadata.description).toContain("Luật Khám bệnh 2023");
    expect(metadata.alternates?.canonical).toBe("/legal/terms");
  });

  it("renders Terms of Service Reader with constrained editorial body and SectionIndex", () => {
    const { container } = render(<RootTermsPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Điều khoản sử dụng & Thỏa thuận người dùng/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders medical disclaimer under Law on Medical Examination 2023 and dispute resolution", () => {
    render(<RootTermsPage />);

    expect(screen.getByText(/TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM LÂM SÀNG QUAN TRỌNG:/i)).toBeInTheDocument();
    expect(screen.getByText(/The Clara Care KHÔNG PHẢI là cơ sở khám bệnh, chữa bệnh/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Luật Khám bệnh, chữa bệnh số 15\/2023\/QH15/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Điều 14: Điều khoản thi hành & Giải quyết tranh chấp/i).length).toBeGreaterThan(0);
  });
});
