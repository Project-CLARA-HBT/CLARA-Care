import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import ContactPage, { metadata } from "./page";
import { LEGAL_CONTACT_EMAIL } from "@/lib/legal";

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

describe("ContactPage (/contact — Professional Support & Multi-Channel Inquiries)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("exports metadata with multi-channel support descriptions", () => {
    expect(metadata.title).toContain("Liên hệ & Trung tâm hỗ trợ");
    expect(metadata.description).toContain("Ban cố vấn lâm sàng");
    expect(metadata.description).toContain("DPO");
  });

  it("renders with PUBLIC_LEGAL shell mode and Contact Hub layout archetype", () => {
    const { container } = render(<ContactPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Contact Hub");
  });

  it("renders 4 dedicated support channels and DPO contact information", () => {
    render(<ContactPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Liên hệ & Trung tâm Hỗ trợ Chuyên môn/i,
      }),
    ).toBeInTheDocument();

    // 4 Channels
    expect(screen.getByText(/1\. Hỗ trợ người bệnh & Người dùng cá nhân/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Ban cố vấn y khoa & Bác sĩ lâm sàng/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Hợp tác nghiên cứu & Dữ liệu y học/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Cán bộ bảo vệ dữ liệu \(DPO\) & DSAR/i)).toBeInTheDocument();

    // DPO email
    const emailLinks = screen.getAllByRole("link", { name: LEGAL_CONTACT_EMAIL });
    expect(emailLinks.length).toBeGreaterThan(0);
    expect(emailLinks[0]).toHaveAttribute("href", `mailto:${LEGAL_CONTACT_EMAIL}`);
  });

  it("submits contact inquiry form and renders ticket confirmation", () => {
    vi.useFakeTimers();
    render(<ContactPage />);

    // Fill form
    const nameInput = screen.getByLabelText(/Họ và tên/i);
    const emailInput = screen.getByLabelText(/Email liên hệ/i);
    const subjectInput = screen.getByLabelText(/Tiêu đề yêu cầu/i);
    const messageInput = screen.getByLabelText(/Nội dung chi tiết/i);

    fireEvent.change(nameInput, { target: { value: "Nguyễn Văn A" } });
    fireEvent.change(emailInput, { target: { value: "nguyenvana@example.com" } });
    fireEvent.change(subjectInput, { target: { value: "Hỗ trợ tích hợp" } });
    fireEvent.change(messageInput, { target: { value: "Cần hỗ trợ tích hợp dữ liệu dược thư lâm sàng." } });

    // Submit form
    const submitBtn = screen.getByTestId("contact-submit-btn");
    act(() => {
      fireEvent.click(submitBtn);
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Confirmation
    expect(screen.getByTestId("contact-form-success")).toBeInTheDocument();
    expect(screen.getByText(/Tiếp nhận thành công/i)).toBeInTheDocument();
    expect(screen.getByText(/Mã tra cứu phiếu/i)).toBeInTheDocument();

    vi.useRealTimers();
  });
});
