import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AskBar } from "./ask-bar";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

afterEach(cleanup);
beforeEach(() => {
  mockRouter.push.mockReset();
});

describe("AskBar", () => {
  it("renders input with placeholder and submit button", () => {
    render(<AskBar locale="vi" />);

    const input = screen.getByTestId("ask-bar-input");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute(
      "placeholder",
      "Hỏi CLARA về sức khỏe, triệu chứng, đơn thuốc...",
    );
  });

  it("calls onSubmit when typed and submitted via button", () => {
    const onSubmit = vi.fn();
    render(<AskBar onSubmit={onSubmit} />);

    const input = screen.getByTestId("ask-bar-input");
    fireEvent.change(input, { target: { value: "Uống thuốc đau đầu khi nào?" } });

    const submitBtn = screen.getByTestId("ask-bar-submit-button");
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith("Uống thuốc đau đầu khi nào?", "text");
  });

  it("submits on Enter keypress", () => {
    const onSubmit = vi.fn();
    render(<AskBar onSubmit={onSubmit} />);

    const input = screen.getByTestId("ask-bar-input");
    fireEvent.change(input, { target: { value: "Chỉ số đường huyết 6.5 có cao không?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(onSubmit).toHaveBeenCalledWith("Chỉ số đường huyết 6.5 có cao không?", "text");
  });

  it("navigates to targetHref when onSubmit is not provided", () => {
    render(<AskBar targetHref="/ask" />);

    const input = screen.getByTestId("ask-bar-input");
    fireEvent.change(input, { target: { value: "triệu chứng cúm" } });

    const submitBtn = screen.getByTestId("ask-bar-submit-button");
    fireEvent.click(submitBtn);

    expect(mockRouter.push).toHaveBeenCalledWith("/ask?q=tri%E1%BB%87u%20ch%E1%BB%A9ng%20c%C3%BAm");
  });

  it("triggers camera/file/voice action callbacks", () => {
    const onCamera = vi.fn();
    const onFile = vi.fn();
    const onVoice = vi.fn();

    render(
      <AskBar
        onCameraClick={onCamera}
        onFileClick={onFile}
        onVoiceClick={onVoice}
      />,
    );

    fireEvent.click(screen.getByTestId("ask-bar-camera-button"));
    expect(onCamera).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("ask-bar-file-button"));
    expect(onFile).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("ask-bar-voice-button"));
    expect(onVoice).toHaveBeenCalledTimes(1);
  });
});
