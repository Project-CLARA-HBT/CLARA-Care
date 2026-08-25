import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TrafficLightSafetyIndicator } from "./traffic-light-safety-indicator";

describe("TrafficLightSafetyIndicator Component", () => {
  afterEach(cleanup);

  it("renders 🟢 Green: Safe state (Xanh: An toàn)", () => {
    render(
      <TrafficLightSafetyIndicator
        level="safe"
        summary="Không phát hiện tương tác nguy hiểm."
        medications={["Augmentin", "Panadol"]}
      />,
    );

    const indicator = screen.getByTestId("traffic-light-safety-indicator");
    expect(indicator).toHaveAttribute("data-safety-level", "safe");
    expect(screen.getByText("XANH: AN TOÀN")).toBeInTheDocument();
    expect(screen.getByText("An toàn")).toBeInTheDocument();
    expect(screen.getByText("Không phát hiện tương tác nguy hiểm.")).toBeInTheDocument();
  });

  it("renders 🟡 Yellow: Caution state (Vàng: Cần lưu ý)", () => {
    render(
      <TrafficLightSafetyIndicator
        level="caution"
        summary="Cần theo dõi huyết áp và chức năng thận khi dùng chung."
        alerts={[
          {
            drugA: "Coversyl",
            drugB: "Voltaren",
            level: "caution",
            title: "Giảm tác dụng hạ huyết áp",
            mechanism: "NSAID gây co mạch thận đối kháng ACEi",
            clinicalEffect: "Huyết áp tăng nhẹ",
            recommendation: "Theo dõi huyết áp định kỳ",
            symptomsToWatch: ["Phù chân", "Huyết áp tăng"],
            sourceAuthority: "DrugBank v5.1",
          },
        ]}
        medications={["Coversyl", "Voltaren"]}
      />,
    );

    const indicator = screen.getByTestId("traffic-light-safety-indicator");
    expect(indicator).toHaveAttribute("data-safety-level", "caution");
    expect(screen.getByText("VÀNG: CẦN LƯU Ý")).toBeInTheDocument();
    expect(screen.getAllByText("Cần lưu ý").length).toBeGreaterThan(0);
    expect(screen.getByText("Coversyl + Voltaren")).toBeInTheDocument();
    expect(screen.getByText("Giảm tác dụng hạ huyết áp")).toBeInTheDocument();
  });

  it("renders 🔴 Red: Dangerous state (Đỏ: Tương tác nguy hiểm)", () => {
    render(
      <TrafficLightSafetyIndicator
        level="danger"
        summary="Phát hiện tương tác nguy cơ xuất huyết tiêu hóa nặng."
        alerts={[
          {
            drugA: "Plavix",
            drugB: "Aspirin Protect",
            level: "danger",
            title: "Tăng nguy cơ xuất huyết tiêu hóa nghiêm trọng",
            mechanism: "Ức chế kép kết tập tiểu cầu",
            clinicalEffect: "Xuất huyết dạ dày",
            recommendation: "Tham vấn bác sĩ chuyên khoa tim mạch",
            symptomsToWatch: ["Đi ngoài phân đen", "Nôn máu"],
            sourceAuthority: "DrugBank v5.1",
          },
        ]}
        medications={["Plavix", "Aspirin Protect"]}
      />,
    );

    const indicator = screen.getByTestId("traffic-light-safety-indicator");
    expect(indicator).toHaveAttribute("data-safety-level", "danger");
    expect(screen.getByText("ĐỎ: TƯƠNG TÁC NGUY HIỂM")).toBeInTheDocument();
    expect(screen.getAllByText("Nguy hiểm").length).toBeGreaterThan(0);
    expect(screen.getByText("Plavix + Aspirin Protect")).toBeInTheDocument();
    expect(screen.getByText("Tăng nguy cơ xuất huyết tiêu hóa nghiêm trọng")).toBeInTheDocument();
    expect(screen.getByText("Đi ngoài phân đen")).toBeInTheDocument();
  });
});
