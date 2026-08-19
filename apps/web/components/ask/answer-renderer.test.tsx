import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnswerRenderer } from "./answer-renderer";
import type { ConsumerAnswerEnvelope } from "@/lib/api/v2-client";

afterEach(cleanup);

describe("AnswerRenderer", () => {
  const sampleEnvelope: ConsumerAnswerEnvelope = {
    answer: {
      main_message: "Chỉ số đường huyết của bạn hiện trong giới hạn kiểm soát tốt.",
      actions: [
        {
          id: "act-1",
          label: "Xem tủ thuốc hiện tại",
          target: "/health/medications",
          description: "Kiểm tra lại liều dùng Metformin hàng ngày",
        },
      ],
      sections: [
        {
          title: "Giải thích chi tiết",
          content: "Chỉ số HbA1c 6.2% cho thấy phác đồ 3 tháng qua đạt hiệu quả.",
        },
      ],
    },
    personal_evidence: [
      {
        id: "pe-1",
        title: "Xét nghiệm HbA1c",
        resource_type: "result",
        effective_at: "2026-08-12T00:00:00Z",
        state: "confirmed",
      },
    ],
    external_sources: [
      {
        id: "src-1",
        title: "Hướng dẫn điều trị ADA 2026",
        publisher: "American Diabetes Association",
      },
    ],
    unknowns: [
      {
        id: "unk-1",
        missing_factor: "Nhật ký ăn uống",
        why_it_matters: "Chưa rõ lượng carbohydrate gần đây",
      },
    ],
    safety: {
      urgency: "routine",
      guidance: "Tiếp tục duy trì chế độ ăn và tái khám sau 3 tháng.",
    },
    write_proposals: [
      {
        id: "prop-1",
        kind: "task",
        title: "Đo đường huyết lúc đói ngày mai",
        summary: "Ghi lại vào sổ theo dõi",
        status: "pending",
      },
    ],
    disclosure: {
      used_personal_context: true,
      data_classes: ["results", "medications"],
    },
  };

  it("renders all 5 core answer sections cleanly", () => {
    render(<AnswerRenderer envelope={sampleEnvelope} />);

    // 1. Điều quan trọng nhất
    expect(screen.getByTestId("answer-main-message-section")).toBeInTheDocument();
    expect(screen.getByText(/1\. Điều quan trọng nhất/i)).toBeInTheDocument();
    expect(
      screen.getByText("Chỉ số đường huyết của bạn hiện trong giới hạn kiểm soát tốt.")
    ).toBeInTheDocument();
    expect(screen.getByText("Giải thích chi tiết")).toBeInTheDocument();

    // 2. Bạn có thể làm gì tiếp theo
    expect(screen.getByTestId("answer-actions-section")).toBeInTheDocument();
    expect(screen.getByText(/2\. Bạn có thể làm gì tiếp theo/i)).toBeInTheDocument();
    expect(screen.getByText("Xem tủ thuốc hiện tại")).toBeInTheDocument();

    // 3. Dựa trên đâu
    expect(screen.getByTestId("answer-evidence-section")).toBeInTheDocument();
    expect(screen.getByText(/3\. Dựa trên đâu/i)).toBeInTheDocument();
    expect(screen.getByText("Xét nghiệm HbA1c")).toBeInTheDocument();
    expect(screen.getByTestId("context-disclosure-badge")).toBeInTheDocument();

    // 4. Điều CLARA chưa biết hoặc chưa chắc
    expect(screen.getByTestId("answer-unknowns-section")).toBeInTheDocument();
    expect(
      screen.getByText(/4\. Điều CLARA chưa biết hoặc chưa chắc/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Nhật ký ăn uống/)).toBeInTheDocument();

    // 5. Khi nào cần hỗ trợ y tế
    expect(screen.getByTestId("answer-safety-routine-section")).toBeInTheDocument();
    expect(screen.getByText(/5\. Khi nào cần hỗ trợ y tế/i)).toBeInTheDocument();

    // Proposals
    expect(screen.getByTestId("answer-proposals-section")).toBeInTheDocument();
    expect(screen.getByText("Đo đường huyết lúc đói ngày mai")).toBeInTheDocument();
  });

  it("renders prominent emergency banner and call 115 button when urgency is emergency", () => {
    const emergencyEnvelope: ConsumerAnswerEnvelope = {
      ...sampleEnvelope,
      safety: {
        urgency: "emergency",
        guidance: "Cơn đau ngực dữ dội kèm khó thở là tình trạng khẩn cấp.",
        red_flags: ["Đau lan ra cánh tay trái", "Vã mồ hôi lạnh"],
      },
    };

    render(<AnswerRenderer envelope={emergencyEnvelope} />);

    expect(screen.getByTestId("answer-safety-emergency-banner")).toBeInTheDocument();
    expect(screen.getByText("Khẩn cấp / Cấp cứu")).toBeInTheDocument();
    expect(screen.getByTestId("emergency-call-115-button")).toHaveAttribute(
      "href",
      "tel:115"
    );
    expect(screen.getByText("Đau lan ra cánh tay trái")).toBeInTheDocument();
  });

  it("triggers evidence drawer callback when clicking view evidence", () => {
    const onOpenDrawer = vi.fn();
    render(
      <AnswerRenderer
        envelope={sampleEnvelope}
        onOpenEvidenceDrawer={onOpenDrawer}
      />
    );

    const drawerBtn = screen.getByTestId("answer-evidence-drawer-button");
    fireEvent.click(drawerBtn);
    expect(onOpenDrawer).toHaveBeenCalledTimes(1);
  });
});
