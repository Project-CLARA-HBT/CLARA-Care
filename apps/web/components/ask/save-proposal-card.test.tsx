import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SaveProposalCard } from "./save-proposal-card";
import type { WriteProposalDto } from "@/lib/api/v2-client";

afterEach(cleanup);

describe("SaveProposalCard", () => {
  const sampleProposal: WriteProposalDto = {
    id: "prop-1",
    kind: "medication",
    title: "Amlodipine 5mg",
    summary: "1 viên uống mỗi sáng sau ăn",
    status: "pending",
    data: {
      dosage: "5mg",
      frequency: "Mỗi sáng",
    },
  };

  it("renders proposal details, kind label, and pending action buttons", () => {
    render(<SaveProposalCard proposal={sampleProposal} />);

    expect(screen.getByText("Thuốc mới")).toBeInTheDocument();
    expect(screen.getByText("Đề xuất mới")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();
    expect(screen.getByText("1 viên uống mỗi sáng sau ăn")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-confirm-button")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-edit-button")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-reject-button")).toBeInTheDocument();
  });

  it("handles confirm action and transitions status", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<SaveProposalCard proposal={sampleProposal} onConfirm={onConfirm} />);

    const confirmBtn = screen.getByTestId("proposal-confirm-button");
    fireEvent.click(confirmBtn);

    expect(onConfirm).toHaveBeenCalledWith(sampleProposal);
    expect(await screen.findByText("Đã lưu vào hồ sơ")).toBeInTheDocument();
  });

  it("handles reject action and transitions status", async () => {
    const onReject = vi.fn().mockResolvedValue(undefined);
    render(<SaveProposalCard proposal={sampleProposal} onReject={onReject} />);

    const rejectBtn = screen.getByTestId("proposal-reject-button");
    fireEvent.click(rejectBtn);

    expect(onReject).toHaveBeenCalledWith(sampleProposal);
    expect(await screen.findByText("Đã bỏ qua")).toBeInTheDocument();
  });

  it("allows inline editing and saving updated proposal", async () => {
    const onEditSave = vi.fn().mockResolvedValue(undefined);
    render(<SaveProposalCard proposal={sampleProposal} onEditSave={onEditSave} />);

    // Open edit mode
    fireEvent.click(screen.getByTestId("proposal-edit-button"));

    const titleInput = screen.getByTestId("proposal-edit-title-input");
    const summaryInput = screen.getByTestId("proposal-edit-summary-input");

    fireEvent.change(titleInput, { target: { value: "Amlodipine 10mg" } });
    fireEvent.change(summaryInput, { target: { value: "Uống theo chỉ định mới" } });

    fireEvent.click(screen.getByTestId("proposal-save-edit-button"));

    expect(onEditSave).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "prop-1",
        title: "Amlodipine 10mg",
        summary: "Uống theo chỉ định mới",
        status: "edited",
      })
    );

    expect(await screen.findByText("Đã sửa & lưu")).toBeInTheDocument();
  });
});
