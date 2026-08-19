import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CandidateReviewSheet } from "./candidate-review-sheet";
import type { CaptureCandidateV2 } from "@/lib/api/v2-client";

afterEach(cleanup);

const mockCandidates: CaptureCandidateV2[] = [
  {
    id: "cand-1",
    category: "medication",
    field_name: "medication_name",
    value: "Amoxicillin 500mg",
    status: "pending",
    confidence: 0.95,
    source_snippet: "Uống Amoxicillin 500mg ngày 2 lần",
    source_page: 1,
  },
  {
    id: "cand-2",
    category: "measurement",
    field_name: "blood_pressure",
    value: { systolic: 135, diastolic: 85, unit: "mmHg" },
    status: "pending",
    confidence: 0.65, // low confidence -> uncertainty badge
    has_uncertainty: true,
    uncertainty_reason: "OCR disagreement with visual model",
    source_snippet: "Huyết áp phòng khám: 135/85",
  },
  {
    id: "cand-3",
    category: "condition",
    field_name: "condition_name",
    value: "Viêm họng cấp",
    status: "accepted",
    confidence: 0.9,
  },
];

describe("CandidateReviewSheet Component", () => {
  it("renders list of extracted cards with category badges, field names, and source snippets", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    const onEdit = vi.fn();

    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={onAccept}
        onRejectCandidate={onReject}
        onEditCandidate={onEdit}
        locale="vi"
      />,
    );

    expect(screen.getByTestId("candidate-review-sheet")).toBeInTheDocument();
    expect(screen.getByText("Kiểm tra thông tin trích xuất")).toBeInTheDocument();
    expect(screen.getByText("Amoxicillin 500mg")).toBeInTheDocument();
    expect(screen.getByText("135/85 mmHg")).toBeInTheDocument();
    expect(screen.getByText("Viêm họng cấp")).toBeInTheDocument();
    expect(screen.getByText(/Uống Amoxicillin 500mg ngày 2 lần/i)).toBeInTheDocument();
  });

  it("displays uncertainty badge when OCR disagreement or low confidence occurs", () => {
    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={vi.fn()}
        onRejectCandidate={vi.fn()}
        onEditCandidate={vi.fn()}
        locale="vi"
      />,
    );

    expect(screen.getByTestId("uncertainty-badge-cand-2")).toBeInTheDocument();
    expect(screen.getByText("Chưa chắc chắn")).toBeInTheDocument();
  });

  it("handles confirmation toggle for candidate cards", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();

    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={onAccept}
        onRejectCandidate={onReject}
        onEditCandidate={vi.fn()}
        locale="vi"
      />,
    );

    const toggle1 = screen.getByTestId("candidate-toggle-cand-1") as HTMLInputElement;
    expect(toggle1.checked).toBe(false);

    fireEvent.click(toggle1);
    expect(onAccept).toHaveBeenCalledWith("cand-1");
  });

  it("supports inline editing of values with save and cancel", () => {
    const onEdit = vi.fn();

    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={vi.fn()}
        onRejectCandidate={vi.fn()}
        onEditCandidate={onEdit}
        locale="vi"
      />,
    );

    const editBtn = screen.getByTestId("btn-edit-cand-1");
    fireEvent.click(editBtn);

    expect(screen.getByTestId("inline-edit-form-cand-1")).toBeInTheDocument();
    const input = screen.getByTestId("edit-input-cand-1") as HTMLTextAreaElement;
    expect(input.value).toBe("Amoxicillin 500mg");

    fireEvent.change(input, { target: { value: "Amoxicillin 1000mg (Augmentin)" } });

    const saveBtn = screen.getByTestId("save-edit-cand-1");
    fireEvent.click(saveBtn);

    expect(onEdit).toHaveBeenCalledWith("cand-1", "Amoxicillin 1000mg (Augmentin)");
  });

  it("handles individual Accept and Reject buttons", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();

    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={onAccept}
        onRejectCandidate={onReject}
        onEditCandidate={vi.fn()}
        locale="vi"
      />,
    );

    const acceptBtn = screen.getByTestId("btn-accept-cand-1");
    fireEvent.click(acceptBtn);
    expect(onAccept).toHaveBeenCalledWith("cand-1");

    const rejectBtn = screen.getByTestId("btn-reject-cand-1");
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith("cand-1");
  });

  it("supports bulk Accept All and Reject All actions", () => {
    const onAcceptAll = vi.fn();
    const onRejectAll = vi.fn();

    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={vi.fn()}
        onRejectCandidate={vi.fn()}
        onEditCandidate={vi.fn()}
        onAcceptAll={onAcceptAll}
        onRejectAll={onRejectAll}
        locale="vi"
      />,
    );

    const acceptAllBtn = screen.getByTestId("review-accept-all-btn");
    fireEvent.click(acceptAllBtn);
    expect(onAcceptAll).toHaveBeenCalledTimes(1);

    const rejectAllBtn = screen.getByTestId("review-reject-all-btn");
    fireEvent.click(rejectAllBtn);
    expect(onRejectAll).toHaveBeenCalledTimes(1);
  });

  it("filters candidates by status (All, Pending, Uncertain, Accepted, Rejected)", () => {
    render(
      <CandidateReviewSheet
        candidates={mockCandidates}
        onAcceptCandidate={vi.fn()}
        onRejectCandidate={vi.fn()}
        onEditCandidate={vi.fn()}
        locale="vi"
      />,
    );

    // Click Uncertain filter
    const uncertainTab = screen.getByTestId("filter-uncertain");
    fireEvent.click(uncertainTab);

    expect(screen.getByText("135/85 mmHg")).toBeInTheDocument();
    expect(screen.queryByText("Amoxicillin 500mg")).not.toBeInTheDocument();

    // Click Accepted filter
    const acceptedTab = screen.getByTestId("filter-accepted");
    fireEvent.click(acceptedTab);

    expect(screen.getByText("Viêm họng cấp")).toBeInTheDocument();
    expect(screen.queryByText("135/85 mmHg")).not.toBeInTheDocument();
  });
});
