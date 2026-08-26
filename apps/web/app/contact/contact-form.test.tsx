import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ContactFeedbackForm } from "./contact-form";

describe("ContactFeedbackForm Component", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders all categories and default fields correctly", () => {
    render(<ContactFeedbackForm initialCategory="patient" />);

    expect(screen.getByTestId("contact-feedback-form")).toBeInTheDocument();
    expect(screen.getByText(/Hỗ trợ người bệnh/i)).toBeInTheDocument();
    expect(screen.getByText(/Cố vấn y khoa/i)).toBeInTheDocument();
    expect(screen.getByText(/Hợp tác nghiên cứu/i)).toBeInTheDocument();
    expect(screen.getByText(/Quyền riêng tư & DPO/i)).toBeInTheDocument();
    expect(screen.getByText(/Góp ý chất lượng/i)).toBeInTheDocument();

    expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email liên hệ/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Số điện thoại/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Vai trò của bạn/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tiêu đề yêu cầu/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nội dung chi tiết/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tôi đồng ý cho phép/i)).toBeChecked();
  });

  it("displays real-time validation errors on blur for empty required fields", () => {
    render(<ContactFeedbackForm />);

    const nameInput = screen.getByLabelText(/Họ và tên/i);
    const emailInput = screen.getByLabelText(/Email liên hệ/i);
    const subjectInput = screen.getByLabelText(/Tiêu đề yêu cầu/i);
    const messageInput = screen.getByLabelText(/Nội dung chi tiết/i);

    fireEvent.focus(nameInput);
    fireEvent.blur(nameInput);
    expect(screen.getByText(/Vui lòng nhập họ và tên của bạn/i)).toBeInTheDocument();

    fireEvent.focus(emailInput);
    fireEvent.blur(emailInput);
    expect(screen.getByText(/Vui lòng nhập email liên hệ/i)).toBeInTheDocument();

    fireEvent.focus(subjectInput);
    fireEvent.blur(subjectInput);
    expect(screen.getByText(/Vui lòng nhập tiêu đề yêu cầu/i)).toBeInTheDocument();

    fireEvent.focus(messageInput);
    fireEvent.blur(messageInput);
    expect(screen.getByText(/Vui lòng mô tả chi tiết nội dung cần hỗ trợ/i)).toBeInTheDocument();
  });

  it("validates invalid email format and short message length", () => {
    render(<ContactFeedbackForm />);

    const emailInput = screen.getByLabelText(/Email liên hệ/i);
    const messageInput = screen.getByLabelText(/Nội dung chi tiết/i);

    fireEvent.change(emailInput, { target: { value: "not-an-email" } });
    fireEvent.blur(emailInput);
    expect(screen.getByText(/Địa chỉ email không hợp lệ/i)).toBeInTheDocument();

    fireEvent.change(messageInput, { target: { value: "ngắn" } });
    fireEvent.blur(messageInput);
    expect(screen.getByText(/Nội dung cần có ít nhất 10 ký tự/i)).toBeInTheDocument();
  });

  it("blocks submission if consent is unchecked", () => {
    render(<ContactFeedbackForm />);

    const consentCheckbox = screen.getByLabelText(/Tôi đồng ý cho phép/i);
    fireEvent.click(consentCheckbox); // Uncheck consent
    expect(consentCheckbox).not.toBeChecked();

    const submitBtn = screen.getByTestId("contact-submit-btn");
    fireEvent.click(submitBtn);

    expect(screen.getByText(/Bạn cần đồng ý với điều khoản xử lý thông tin để tiếp tục/i)).toBeInTheDocument();
  });

  it("successfully submits with valid data and allows opening the receipt modal", () => {
    vi.useFakeTimers();
    render(<ContactFeedbackForm initialCategory="research" />);

    // Select DPO category
    const dpoCategoryBtn = screen.getByRole("button", { name: /Quyền riêng tư & DPO/i });
    fireEvent.click(dpoCategoryBtn);

    const nameInput = screen.getByLabelText(/Họ và tên/i);
    const emailInput = screen.getByLabelText(/Email liên hệ/i);
    const phoneInput = screen.getByLabelText(/Số điện thoại/i);
    const subjectInput = screen.getByLabelText(/Tiêu đề yêu cầu/i);
    const messageInput = screen.getByLabelText(/Nội dung chi tiết/i);

    fireEvent.change(nameInput, { target: { value: "Nguyễn Thị C" } });
    fireEvent.change(emailInput, { target: { value: "nguyen.thi.c@example.vn" } });
    fireEvent.change(phoneInput, { target: { value: "0912345678" } });
    fireEvent.change(subjectInput, { target: { value: "Yêu cầu trích xuất dữ liệu DSAR" } });
    fireEvent.change(messageInput, {
      target: { value: "Tôi muốn trích xuất dữ liệu hồ sơ sức khỏe cá nhân theo Điều 9 Nghị định 13/2023/NĐ-CP." },
    });

    const submitBtn = screen.getByTestId("contact-submit-btn");
    act(() => {
      fireEvent.click(submitBtn);
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByTestId("contact-form-success")).toBeInTheDocument();
    expect(screen.getByText(/Tiếp nhận thành công/i)).toBeInTheDocument();
    expect(screen.getByText(/nguyen.thi.c@example.vn/i)).toBeInTheDocument();
    expect(screen.getByText(/72 giờ \(theo luật\)/i)).toBeInTheDocument();

    // Open receipt modal
    const viewReceiptBtn = screen.getByTestId("view-receipt-btn");
    fireEvent.click(viewReceiptBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Nguyễn Thị C/i)).toBeInTheDocument();
    expect(screen.getByText(/0912345678/i)).toBeInTheDocument();

    // Close receipt modal
    const closeBtn = screen.getByRole("button", { name: /Đóng biên nhận/i });
    fireEvent.click(closeBtn);

    // Submit another request
    const submitAnotherBtn = screen.getByTestId("submit-another-btn");
    fireEvent.click(submitAnotherBtn);
    expect(screen.getByTestId("contact-feedback-form")).toBeInTheDocument();

    vi.useRealTimers();
  });
});
