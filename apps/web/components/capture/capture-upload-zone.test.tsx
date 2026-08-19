import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CaptureUploadZone, formatBytes } from "./capture-upload-zone";

afterEach(cleanup);

describe("CaptureUploadZone Component", () => {
  it("formats bytes accurately", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1024 * 1024 * 5)).toBe("5 MB");
  });

  it("renders upload zone with drag-and-drop prompt and file/camera buttons", () => {
    const onFileSelect = vi.fn();
    render(<CaptureUploadZone onFileSelect={onFileSelect} locale="vi" />);

    expect(screen.getByTestId("capture-upload-zone")).toBeInTheDocument();
    expect(screen.getByText("Kéo thả tài liệu y tế vào đây")).toBeInTheDocument();
    expect(screen.getByTestId("capture-browse-btn")).toBeInTheDocument();
    expect(screen.getByTestId("capture-camera-btn")).toBeInTheDocument();
  });

  it("triggers file select when file is chosen via input", () => {
    const onFileSelect = vi.fn();
    render(<CaptureUploadZone onFileSelect={onFileSelect} locale="vi" />);

    const input = screen.getByTestId("capture-file-input") as HTMLInputElement;
    const file = new File(["test document content"], "prescription.png", { type: "image/png" });

    fireEvent.change(input, { target: { files: [file] } });
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("triggers camera photo upload via camera input", () => {
    const onFileSelect = vi.fn();
    render(<CaptureUploadZone onFileSelect={onFileSelect} captureMode="camera" locale="vi" />);

    const input = screen.getByTestId("capture-camera-input") as HTMLInputElement;
    const photo = new File(["photo bytes"], "camera-snap.jpg", { type: "image/jpeg" });

    fireEvent.change(input, { target: { files: [photo] } });
    expect(onFileSelect).toHaveBeenCalledWith(photo);
  });

  it("validates maximum file size limit and displays error message", () => {
    const onFileSelect = vi.fn();
    // 5MB limit
    render(<CaptureUploadZone onFileSelect={onFileSelect} maxSizeMb={5} locale="vi" />);

    const input = screen.getByTestId("capture-file-input") as HTMLInputElement;
    // Create an oversized file (10MB)
    const largeFile = new File([new ArrayBuffer(10 * 1024 * 1024)], "huge_scan.pdf", {
      type: "application/pdf",
    });

    fireEvent.change(input, { target: { files: [largeFile] } });
    expect(onFileSelect).not.toHaveBeenCalled();
    expect(screen.getByTestId("capture-validation-error")).toBeInTheDocument();
    expect(screen.getByText(/vượt quá dung lượng tối đa/i)).toBeInTheDocument();
  });

  it("validates unsupported file formats and displays error message", () => {
    const onFileSelect = vi.fn();
    render(<CaptureUploadZone onFileSelect={onFileSelect} locale="vi" />);

    const input = screen.getByTestId("capture-file-input") as HTMLInputElement;
    const unsupportedFile = new File(["executable"], "script.exe", {
      type: "application/x-msdownload",
    });

    fireEvent.change(input, { target: { files: [unsupportedFile] } });
    expect(onFileSelect).not.toHaveBeenCalled();
    expect(screen.getByTestId("capture-validation-error")).toBeInTheDocument();
    expect(screen.getByText(/Định dạng tệp không được hỗ trợ/i)).toBeInTheDocument();
  });

  it("handles drag over and drop events properly", () => {
    const onFileSelect = vi.fn();
    render(<CaptureUploadZone onFileSelect={onFileSelect} locale="vi" />);

    const dropRegion = screen.getByRole("region", { name: "Khu vực tải và kéo thả tệp" });

    fireEvent.dragOver(dropRegion);
    expect(screen.getByText("Thả tệp vào đây để bắt đầu nhận diện")).toBeInTheDocument();

    const file = new File(["pdf content"], "lab-report.pdf", { type: "application/pdf" });
    fireEvent.drop(dropRegion, {
      dataTransfer: { files: [file] },
    });

    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("renders progress bar and cancellation button when uploading/processing", () => {
    const onFileSelect = vi.fn();
    const onCancel = vi.fn();

    render(
      <CaptureUploadZone
        onFileSelect={onFileSelect}
        onCancel={onCancel}
        isUploading={true}
        uploadProgress={65}
        statusMessage="Đang tải lên tài liệu..."
        locale="vi"
      />,
    );

    expect(screen.getByTestId("capture-busy-state")).toBeInTheDocument();
    expect(screen.getByText("Đang tải lên tài liệu...")).toBeInTheDocument();
    expect(screen.getByTestId("upload-progress-value")).toHaveTextContent("65%");

    const cancelBtn = screen.getByTestId("capture-cancel-button");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
