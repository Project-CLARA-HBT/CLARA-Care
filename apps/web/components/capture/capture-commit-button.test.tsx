import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CaptureCommitButton,
  determineTargetSection,
  getSectionRoute,
} from "./capture-commit-button";
import { v2Client, type CaptureCandidateV2 } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const mockAcceptedCandidates: CaptureCandidateV2[] = [
  {
    id: "c1",
    category: "medication",
    field_name: "medication_name",
    value: "Paracetamol 500mg",
    status: "accepted",
  },
  {
    id: "c2",
    category: "medication",
    field_name: "dosage",
    value: "2 viên/ngày",
    status: "accepted",
  },
];

describe("CaptureCommitButton Component", () => {
  it("determines target section correctly based on candidate categories", () => {
    expect(determineTargetSection(mockAcceptedCandidates)).toBe("medications");
    expect(getSectionRoute("medications")).toBe("/health/medications");

    const measurementCand: CaptureCandidateV2[] = [
      { id: "m1", category: "measurement", field_name: "blood_pressure", value: "120/80", status: "accepted" },
    ];
    expect(determineTargetSection(measurementCand)).toBe("measurements");
    expect(getSectionRoute("measurements")).toBe("/health/measurements");

    expect(determineTargetSection([])).toBe("timeline");
  });

  it("disables button when no candidates are accepted", () => {
    render(
      <CaptureCommitButton
        sessionId="sess-1"
        acceptedCandidates={[]}
        locale="vi"
      />,
    );

    const btn = screen.getByTestId("capture-commit-button");
    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent("Chưa chọn mục nào để lưu");
  });

  it("submits accepted items and displays success banner and triggers router navigation", async () => {
    vi.spyOn(v2Client, "commitCaptureSession").mockResolvedValueOnce({
      success: true,
      committed_count: 2,
      target_section: "medications",
      redirect_url: "/health/medications",
    });

    const onCommitSuccess = vi.fn();

    render(
      <CaptureCommitButton
        sessionId="sess-1"
        acceptedCandidates={mockAcceptedCandidates}
        onCommitSuccess={onCommitSuccess}
        locale="vi"
      />,
    );

    const btn = screen.getByTestId("capture-commit-button");
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveTextContent("Lưu 2 mục vào hồ sơ sức khỏe");

    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByTestId("commit-success-banner")).toBeInTheDocument();
    });

    expect(onCommitSuccess).toHaveBeenCalledWith(
      expect.objectContaining({ success: true, committed_count: 2 }),
    );
  });

  it("displays error banner when committing fails", async () => {
    vi.spyOn(v2Client, "commitCaptureSession").mockRejectedValueOnce(new Error("Lỗi máy chủ khi lưu"));

    render(
      <CaptureCommitButton
        sessionId="sess-1"
        acceptedCandidates={mockAcceptedCandidates}
        locale="vi"
      />,
    );

    const btn = screen.getByTestId("capture-commit-button");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByTestId("commit-error-banner")).toBeInTheDocument();
    });

    expect(screen.getByText("Lỗi máy chủ khi lưu")).toBeInTheDocument();
  });
});
