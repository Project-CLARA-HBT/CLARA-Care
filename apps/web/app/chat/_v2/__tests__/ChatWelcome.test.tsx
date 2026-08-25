import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatWelcome from "@/app/chat/_v2/components/ChatWelcome";

describe("ChatWelcome", () => {
  it.each([
    ["normal", "What would you like to understand?", /Check drug interactions/i],
    ["researcher", "Start with a research question", /Evidence overview/i],
    ["doctor", "What do you need to clarify?", /Summarize a case/i],
  ] as const)("shows a focused %s experience", (role, heading, action) => {
    render(
      <ChatWelcome role={role} uiLanguage="en" onChoosePrompt={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: action })).toBeInTheDocument();
  });

  it("renders 6 practical starter prompts and helper tip for everyday Vietnamese health experience", () => {
    render(
      <ChatWelcome role="normal" uiLanguage="vi" onChoosePrompt={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /Kiểm tra tương tác thuốc/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Giải thích chỉ số xét nghiệm/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Thời điểm uống thuốc tốt nhất/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Khi nào triệu chứng cần đi cấp cứu/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Liều Paracetamol hạ sốt/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Thực đơn kiêng khem/i })).toBeInTheDocument();
    expect(screen.getByText(/Mẹo: Bạn có thể nhập ảnh đơn thuốc/i)).toBeInTheDocument();
  });

  it("sends the selected starter prompt back to the composer", () => {
    const onChoosePrompt = vi.fn();
    render(
      <ChatWelcome
        role="researcher"
        uiLanguage="en"
        onChoosePrompt={onChoosePrompt}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Check a claim" }));
    expect(onChoosePrompt).toHaveBeenCalledWith(
      expect.stringContaining("supporting and conflicting"),
    );
  });
});
