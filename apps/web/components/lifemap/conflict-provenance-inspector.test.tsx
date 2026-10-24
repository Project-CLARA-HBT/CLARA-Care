import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConflictProvenanceInspector,
  type ConflictProvenanceInspectorProps,
} from "./conflict-provenance-inspector";
import type { MultiSourceContradiction } from "@/lib/lifemap-conflict-provenance";

describe("ConflictProvenanceInspector (PH12 A05)", () => {
  const mockContradiction: MultiSourceContradiction = {
    id: "contra-101",
    eventId: "evt-bp-01",
    fieldKey: "blood_pressure",
    title: "Mâu thuẫn thông tin: blood_pressure",
    description: "Phát hiện chênh lệch chỉ số huyết áp giữa EMR bệnh viện và máy đo Bluetooth.",
    severity: "critical",
    type: "contradiction",
    detectedAt: "2026-08-10T12:00:00Z",
    status: "unresolved",
    sources: [
      {
        sourceId: "src-emr-1",
        sourceType: "EMR_INTEGRATION",
        attribution: "Bệnh viện Bạch Mai",
        occurredAt: "2026-08-10T08:00:00Z",
        recordedAt: "2026-08-10T09:30:00Z",
        revision: 1,
        truthState: "confirmed",
        valueDisplay: "145/95 mmHg (Cao độ 1)",
        payload: { systolic: 145, diastolic: 95 },
        confidence: 0.99,
        contentHash: "sha256-emr-hash",
        isAuthoritative: true,
        authorName: "BS. Hoàng",
      },
      {
        sourceId: "src-device-1",
        sourceType: "WEARABLE_DEVICE",
        attribution: "Máy đo Omron Bluetooth",
        occurredAt: "2026-08-10T08:15:00Z",
        recordedAt: "2026-08-10T08:20:00Z",
        revision: 1,
        truthState: "user_reported",
        valueDisplay: "125/82 mmHg (Bình thường)",
        payload: { systolic: 125, diastolic: 82 },
        confidence: 0.85,
        contentHash: "sha256-device-hash",
        isAuthoritative: false,
      },
    ],
  };

  afterEach(cleanup);

  it("renders multi-source contradiction matrix with attribution and bitemporal times", () => {
    render(
      <ConflictProvenanceInspector
        contradiction={mockContradiction}
        open={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText(/Đối chiếu & Thẩm định mâu thuẫn: blood_pressure/i),
    ).toBeInTheDocument();
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();

    // Sources rendered
    expect(screen.getByText("Bệnh viện Bạch Mai")).toBeInTheDocument();
    expect(screen.getByText("145/95 mmHg (Cao độ 1)")).toBeInTheDocument();
    expect(screen.getByText("Máy đo Omron Bluetooth")).toBeInTheDocument();
    expect(screen.getByText("125/82 mmHg (Bình thường)")).toBeInTheDocument();
    expect(screen.getByText(/BS. Hoàng/)).toBeInTheDocument();
    expect(screen.getByText(/sha256-emr-hash/)).toBeInTheDocument();
  });

  it("submits 'accept_source' resolution with valid rationale", async () => {
    const handleResolve = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();

    render(
      <ConflictProvenanceInspector
        contradiction={mockContradiction}
        open={true}
        onClose={handleClose}
        onResolve={handleResolve}
      />,
    );

    const dialog = screen.getByRole("dialog");
    const reasonInput = within(dialog).getByLabelText(/Căn cứ kiểm toán & Lý do/i);
    fireEvent.change(reasonInput, {
      target: {
        value: "Chấp nhận chỉ số từ Bệnh viện Bạch Mai do được bác sĩ đo bằng máy thủy ngân chuẩn.",
      },
    });

    const submitBtn = within(dialog).getByRole("button", {
      name: "Ghi nhận quyết định & Lưu kiểm toán",
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleResolve).toHaveBeenCalledWith({
        conflictId: "contra-101",
        eventId: "evt-bp-01",
        currentRevision: 1,
        action: "accept_source",
        chosenSourceId: "src-emr-1",
        reason:
          "Chấp nhận chỉ số từ Bệnh viện Bạch Mai do được bác sĩ đo bằng máy thủy ngân chuẩn.",
      });
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("submits 'dispute_all' escalation to clinical expert", async () => {
    const handleResolve = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();

    render(
      <ConflictProvenanceInspector
        contradiction={mockContradiction}
        open={true}
        onClose={handleClose}
        onResolve={handleResolve}
      />,
    );

    const dialog = screen.getByRole("dialog");
    const actionSelect = within(dialog).getByLabelText(/Hành động xử lý/i);
    fireEvent.change(actionSelect, { target: { value: "dispute_all" } });

    const reasonInput = within(dialog).getByLabelText(/Căn cứ kiểm toán & Lý do/i);
    fireEvent.change(reasonInput, {
      target: {
        value: "Cần hội chẩn thêm do có nghi ngờ máy đo cá nhân bị sai lệch chuẩn.",
      },
    });

    const submitBtn = within(dialog).getByRole("button", {
      name: "Ghi nhận quyết định & Lưu kiểm toán",
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleResolve).toHaveBeenCalledWith({
        conflictId: "contra-101",
        eventId: "evt-bp-01",
        currentRevision: 1,
        action: "dispute_all",
        reason: "Cần hội chẩn thêm do có nghi ngờ máy đo cá nhân bị sai lệch chuẩn.",
      });
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("submits 'amendment' with amendment payload", async () => {
    const handleResolve = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();

    render(
      <ConflictProvenanceInspector
        contradiction={mockContradiction}
        open={true}
        onClose={handleClose}
        onResolve={handleResolve}
      />,
    );

    const dialog = screen.getByRole("dialog");
    const actionSelect = within(dialog).getByLabelText(/Hành động xử lý/i);
    fireEvent.change(actionSelect, { target: { value: "amendment" } });

    const amendmentInput = within(dialog).getByLabelText(/Nội dung giá trị điều chỉnh/i);
    fireEvent.change(amendmentInput, {
      target: { value: "135/88 mmHg (Đo lại sau 15 phút nghỉ ngơi)" },
    });

    const reasonInput = within(dialog).getByLabelText(/Căn cứ kiểm toán & Lý do/i);
    fireEvent.change(reasonInput, {
      target: { value: "Bệnh nhân đo lại tại phòng y tế sau khi ổn định tâm lý." },
    });

    const submitBtn = within(dialog).getByRole("button", {
      name: "Ghi nhận quyết định & Lưu kiểm toán",
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleResolve).toHaveBeenCalledWith({
        conflictId: "contra-101",
        eventId: "evt-bp-01",
        currentRevision: 1,
        action: "amendment",
        reason: "Bệnh nhân đo lại tại phòng y tế sau khi ổn định tâm lý.",
        amendmentPayload: {
          note: "135/88 mmHg (Đo lại sau 15 phút nghỉ ngơi)",
        },
      });
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("displays existing audit receipt when contradiction is already resolved", () => {
    const resolvedContradiction: MultiSourceContradiction = {
      ...mockContradiction,
      status: "resolved",
      resolution: {
        action: "accept_source",
        chosenSourceId: "src-emr-1",
        reason: "Đã thẩm định theo đơn EMR số 987",
        resolvedAt: "2026-08-10T14:00:00Z",
        auditReceiptId: "rec-verified-999",
      },
    };

    render(
      <ConflictProvenanceInspector
        contradiction={resolvedContradiction}
        open={true}
        onClose={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Mâu thuẫn đã được xử lý qua kiểm toán"),
    ).toBeInTheDocument();
    expect(screen.getByText("Đã thẩm định theo đơn EMR số 987")).toBeInTheDocument();
    expect(screen.getByText(/rec-verified-999/)).toBeInTheDocument();
    expect(screen.queryByTestId("resolution-form")).not.toBeInTheDocument();
  });

  it("hides resolution form in readOnly mode", () => {
    render(
      <ConflictProvenanceInspector
        contradiction={mockContradiction}
        open={true}
        onClose={vi.fn()}
        readOnly={true}
      />,
    );

    expect(screen.queryByTestId("resolution-form")).not.toBeInTheDocument();
  });
});
