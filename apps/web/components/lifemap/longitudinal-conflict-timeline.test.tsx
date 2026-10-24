import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  LongitudinalConflictTimeline,
  type LongitudinalTimelineEventItem,
} from "./longitudinal-conflict-timeline";
import type { MultiSourceContradiction } from "@/lib/lifemap-conflict-provenance";

describe("LongitudinalConflictTimeline Component (PH12 A05)", () => {
  const mockContradiction: MultiSourceContradiction = {
    id: "contra-200",
    eventId: "evt-med-01",
    fieldKey: "dosage",
    title: "Mâu thuẫn thông tin: dosage",
    description: "Đơn thuốc EMR kê 5mg nhưng nhãn quét OCR ghi 10mg",
    severity: "critical",
    type: "contradiction",
    detectedAt: "2026-08-03T11:00:00Z",
    status: "unresolved",
    sources: [
      {
        sourceId: "s-emr",
        sourceType: "EMR_INTEGRATION",
        attribution: "EMR BV Bạch Mai",
        occurredAt: "2026-08-03T10:00:00Z",
        recordedAt: "2026-08-03T10:15:00Z",
        revision: 1,
        truthState: "confirmed",
        valueDisplay: "5mg",
        payload: { dosage: "5mg" },
        confidence: 0.99,
        contentHash: "hash-emr",
        isAuthoritative: true,
      },
      {
        sourceId: "s-ocr",
        sourceType: "DOCUMENT_OCR",
        attribution: "Đơn thuốc quét OCR",
        occurredAt: "2026-08-03T10:00:00Z",
        recordedAt: "2026-08-03T10:20:00Z",
        revision: 1,
        truthState: "draft",
        valueDisplay: "10mg",
        payload: { dosage: "10mg" },
        confidence: 0.88,
        contentHash: "hash-ocr",
        isAuthoritative: false,
      },
    ],
  };

  const sampleEvents: LongitudinalTimelineEventItem[] = [
    {
      id: "evt-1",
      type: "milestone",
      title: "Khởi động hành trình",
      description: "Đã hoàn thành thiết lập mục tiêu",
      occurred_at: "2026-08-01T08:00:00Z",
      recorded_at: "2026-08-01T08:05:00Z",
      revision: 1,
      truth_state: "confirmed",
      provenance: {
        source_kind: "user_commitment",
        attribution: "Bệnh nhân tự xác nhận",
      },
    },
    {
      id: "evt-2",
      type: "medication",
      title: "Đổi đơn thuốc: Amlodipine",
      description: "Bác sĩ điều chỉnh liều",
      occurred_at: "2026-08-03T10:00:00Z",
      recorded_at: "2026-08-03T10:30:00Z",
      revision: 1,
      truth_state: "disputed",
      provenance: {
        source_kind: "clinical_emr",
        attribution: "BV Bạch Mai",
      },
      contradictions: [mockContradiction],
    },
  ];

  afterEach(cleanup);

  it("renders timeline stream with discrepancy counter and conflict callout banner", () => {
    render(
      <LongitudinalConflictTimeline
        events={sampleEvents}
        perspective="valid_time"
        onInspectAudit={vi.fn()}
        onInspectContradiction={vi.fn()}
        onDisputeEvent={vi.fn()}
      />,
    );

    expect(screen.getByTestId("longitudinal-conflict-timeline")).toBeInTheDocument();
    expect(screen.getByText("1 Điểm mâu thuẫn")).toBeInTheDocument();
    expect(screen.getByText("Chỉ xem mâu thuẫn (1)")).toBeInTheDocument();

    // Both events rendered
    expect(screen.getByText("Khởi động hành trình")).toBeInTheDocument();
    expect(screen.getByText("Đổi đơn thuốc: Amlodipine")).toBeInTheDocument();

    // Contradiction callout
    expect(screen.getByText("Mâu thuẫn thông tin: dosage")).toBeInTheDocument();
    expect(screen.getByText(/EMR BV Bạch Mai ⚡ Đơn thuốc quét OCR/)).toBeInTheDocument();
  });

  it("filters stream to show only conflicted events when filter button is toggled", () => {
    render(
      <LongitudinalConflictTimeline
        events={sampleEvents}
        perspective="valid_time"
      />,
    );

    const toggleBtn = screen.getByTestId("toggle-conflict-filter-btn");
    fireEvent.click(toggleBtn);

    // Filtered: non-conflicted event hidden, conflicted event remains
    expect(screen.queryByText("Khởi động hành trình")).not.toBeInTheDocument();
    expect(screen.getByText("Đổi đơn thuốc: Amlodipine")).toBeInTheDocument();
    expect(screen.getByText("Xem tất cả sự kiện")).toBeInTheDocument();
  });

  it("triggers onInspectContradiction when clicking 'Đối chiếu & Giải quyết' on banner", () => {
    const handleInspectContradiction = vi.fn();

    render(
      <LongitudinalConflictTimeline
        events={sampleEvents}
        perspective="valid_time"
        onInspectContradiction={handleInspectContradiction}
      />,
    );

    const inspectBtn = screen.getByRole("button", {
      name: /Kiểm tra mâu thuẫn cho dosage/i,
    });
    fireEvent.click(inspectBtn);

    expect(handleInspectContradiction).toHaveBeenCalledWith(
      mockContradiction,
      expect.objectContaining({ id: "evt-2" }),
    );
  });

  it("triggers onInspectAudit and onDisputeEvent callbacks from timeline item footer", () => {
    const handleInspectAudit = vi.fn();
    const handleDispute = vi.fn();

    render(
      <LongitudinalConflictTimeline
        events={sampleEvents}
        perspective="valid_time"
        onInspectAudit={handleInspectAudit}
        onDisputeEvent={handleDispute}
      />,
    );

    // Find inspect audit button
    const inspectAuditBtns = screen.getAllByText("Xem nhật ký kiểm toán & nguồn");
    fireEvent.click(inspectAuditBtns[0]);
    expect(handleInspectAudit).toHaveBeenCalled();

    // Find dispute button (only on non-disputed event evt-1)
    const disputeBtn = screen.getByText("Khiếu nại / Báo sai");
    fireEvent.click(disputeBtn);
    expect(handleDispute).toHaveBeenCalledWith(
      expect.objectContaining({ id: "evt-1" }),
    );
  });
});
