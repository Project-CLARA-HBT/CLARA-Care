import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AuthSecurityChallenge from "./auth-security-challenge";

describe("AuthSecurityChallenge Component", () => {
  it("renders verification challenge with accessible labels", () => {
    const onSolvedChange = vi.fn();
    render(
      <AuthSecurityChallenge
        onSolvedChange={onSolvedChange}
        isSolved={false}
        language="vi"
      />,
    );

    expect(screen.getByRole("region", { name: /Xác minh bảo mật/i })).toBeInTheDocument();
    expect(screen.getByText(/Vui lòng hoàn thành xác minh bảo mật bên dưới để tiếp tục/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Đổi câu hỏi khác/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Nhập kết quả/i)).toBeInTheDocument();
  });

  it("validates correct answer and triggers onSolvedChange(true)", () => {
    const onSolvedChange = vi.fn();
    render(
      <AuthSecurityChallenge
        onSolvedChange={onSolvedChange}
        isSolved={false}
        language="vi"
      />,
    );

    // Get the challenge question from aria-label or text
    const questionText = screen.getByText(/(\d+)\s*([+-])\s*(\d+)\s*=\s*\?/i);
    expect(questionText).toBeInTheDocument();

    const match = questionText.textContent?.match(/(\d+)\s*([+-])\s*(\d+)/);
    expect(match).not.toBeNull();
    const a = parseInt(match![1], 10);
    const op = match![2];
    const b = parseInt(match![3], 10);
    const expected = op === "+" ? a + b : a - b;

    const input = screen.getByPlaceholderText(/Nhập kết quả/i);
    fireEvent.change(input, { target: { value: String(expected) } });

    expect(onSolvedChange).toHaveBeenCalledWith(true);
  });

  it("displays error on incorrect answer and keeps solved false", () => {
    const onSolvedChange = vi.fn();
    render(
      <AuthSecurityChallenge
        onSolvedChange={onSolvedChange}
        isSolved={false}
        language="vi"
      />,
    );

    const input = screen.getByPlaceholderText(/Nhập kết quả/i);
    fireEvent.change(input, { target: { value: "999" } });

    expect(screen.getByRole("alert")).toHaveTextContent(/Kết quả xác minh không chính xác/i);
    expect(onSolvedChange).toHaveBeenCalledWith(false);
  });

  it("refreshes question when refresh button is clicked", () => {
    const onSolvedChange = vi.fn();
    render(
      <AuthSecurityChallenge
        onSolvedChange={onSolvedChange}
        isSolved={false}
        language="vi"
      />,
    );

    const refreshBtn = screen.getByRole("button", { name: /Đổi câu hỏi khác/i });
    const input = screen.getByPlaceholderText(/Nhập kết quả/i);

    fireEvent.change(input, { target: { value: "12" } });
    fireEvent.click(refreshBtn);

    expect(input).toHaveValue("");
    expect(onSolvedChange).toHaveBeenCalledWith(false);
  });

  it("renders success indicator when isSolved is true", () => {
    const onSolvedChange = vi.fn();
    render(
      <AuthSecurityChallenge
        onSolvedChange={onSolvedChange}
        isSolved={true}
        language="vi"
      />,
    );

    expect(screen.getByText(/Xác minh bảo mật thành công/i)).toBeInTheDocument();
  });
});
