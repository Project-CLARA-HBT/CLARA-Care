import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResultExplanationModal } from "./result-explanation-modal";
import type { HealthRecentResultDto } from "@/lib/api/v2-client";

afterEach(cleanup);

describe("ResultExplanationModal", () => {
  const sampleResult: HealthRecentResultDto = {
    id: "res-1",
    test_name: "Glucose máu",
    category: "Sinh hóa",
    value: 7.2,
    unit: "mmol/L",
    reference_range: "4.1 - 5.9",
    flag: "high",
    effective_at: "2026-08-19T08:30:00Z",
    source_name: "Bệnh viện Đại học Y Dược",
    source_kind: "lab",
    history: [
      { effective_at: "2026-05-10T08:00:00Z", value: 6.5, unit: "mmol/L", flag: "high" },
      { effective_at: "2026-08-19T08:30:00Z", value: 7.2, unit: "mmol/L", flag: "high" },
    ],
  };

  it("renders modal with value, unit, reference range, test purpose, and doctor questions", () => {
    const handleClose = vi.fn();

    render(
      <ResultExplanationModal
        open={true}
        onClose={handleClose}
        result={sampleResult}
        locale="vi"
      />,
    );

    // Modal Title
    expect(screen.getByText("Giải thích xét nghiệm: Glucose máu")).toBeInTheDocument();

    // Value, Unit, Reference Range
    expect(screen.getAllByText(/7.2/)[0]).toBeInTheDocument();
    expect(screen.getAllByText("mmol/L")[0]).toBeInTheDocument();
    expect(screen.getByText(/Khoảng tham chiếu: 4.1 - 5.9/i)).toBeInTheDocument();

    // Source
    expect(screen.getByText("Bệnh viện Đại học Y Dược")).toBeInTheDocument();

    // Purpose Section
    expect(screen.getByText("Tại sao làm xét nghiệm này?")).toBeInTheDocument();
    expect(screen.getByText(/Đo nồng độ đường trong máu/i)).toBeInTheDocument();

    // Plain Explanation Section
    expect(screen.getByText("Ý nghĩa chỉ số của bạn")).toBeInTheDocument();

    // Doctor Questions Section
    expect(screen.getByText("Câu hỏi gợi ý khi trao đổi với bác sĩ")).toBeInTheDocument();
    expect(screen.getByText(/Chỉ số đường huyết này có cần làm lại lúc đói/i)).toBeInTheDocument();

    // Historical Trend Table
    expect(screen.getByText("Lịch sử các lần xét nghiệm")).toBeInTheDocument();

    // Ask CLARA Link
    expect(screen.getByText("Hỏi CLARA thêm về chỉ số này")).toBeInTheDocument();
  });

  it("returns null when open is false or result is null", () => {
    const { container } = render(
      <ResultExplanationModal
        open={false}
        onClose={vi.fn()}
        result={sampleResult}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
