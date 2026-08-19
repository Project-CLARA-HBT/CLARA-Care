import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AskComposer } from "./ask-composer";

afterEach(cleanup);

describe("AskComposer", () => {
  it("renders text input, send button, camera, file, and voice affordances", () => {
    render(<AskComposer onSend={vi.fn()} />);

    expect(screen.getByTestId("ask-composer")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer-textarea")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer-send-button")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer-camera-button")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer-file-button")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer-voice-button")).toBeInTheDocument();

    // Verify STRICTLY NO Fast/Deep/Research or model selector controls
    expect(screen.queryByText(/Fast/i)).toBeNull();
    expect(screen.queryByText(/Deep/i)).toBeNull();
    expect(screen.queryByText(/Research/i)).toBeNull();
    expect(screen.queryByText(/Tư duy/i)).toBeNull();
    expect(screen.queryByText(/Mô hình/i)).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("submits text on button click and Enter key", () => {
    const onSend = vi.fn();
    render(<AskComposer onSend={onSend} />);

    const textarea = screen.getByTestId("ask-composer-textarea");
    fireEvent.change(textarea, { target: { value: "Tôi bị đau đầu sau khi uống thuốc" } });

    const sendBtn = screen.getByTestId("ask-composer-send-button");
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledWith("Tôi bị đau đầu sau khi uống thuốc", []);
  });

  it("shows Stop button during submission and handles cancel without losing draft in parent", () => {
    const onCancel = vi.fn();
    render(<AskComposer onSend={vi.fn()} isSubmitting={true} onCancel={onCancel} />);

    const stopBtn = screen.getByTestId("ask-composer-stop-button");
    expect(stopBtn).toBeInTheDocument();
    expect(screen.queryByTestId("ask-composer-send-button")).toBeNull();

    fireEvent.click(stopBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("handles file attachments and removal", () => {
    const onSend = vi.fn();
    render(<AskComposer onSend={onSend} />);

    const fileInput = screen.getByTestId("ask-composer-file-input");
    const testFile = new File(["test-content"], "xet_nghiem.pdf", { type: "application/pdf" });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    expect(screen.getByText("xet_nghiem.pdf")).toBeInTheDocument();

    const textarea = screen.getByTestId("ask-composer-textarea");
    fireEvent.change(textarea, { target: { value: "Đọc kết quả này giúp tôi" } });

    const sendBtn = screen.getByTestId("ask-composer-send-button");
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledWith(
      "Đọc kết quả này giúp tôi",
      expect.arrayContaining([
        expect.objectContaining({ name: "xet_nghiem.pdf" }),
      ])
    );
  });
});
